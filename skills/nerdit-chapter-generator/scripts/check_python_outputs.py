#!/usr/bin/env python3
"""Check every Python output a lesson shows, on the website's own engine (Pyodide 0.26.2).

    python check_python_outputs.py --course <course_output.json> [--lesson <id>] [--timeout N]
    python check_python_outputs.py --probe numpy,pandas,sklearn

Per lesson:
1. build the dataset block's CSV files, as the browser does;
2. run the Python run lines in page order in one namespace, like notebook cells, and compare
   each printed output with the one the lesson shows (a shown error must contain Python's
   last error line; a run whose output is a chart must draw a figure);
3. run each Python Try It starter alone in a fresh namespace: it must not raise;
4. run every answer (plan check a): practice solutions after the run lines, in their namespace
   (the order of the downloaded L<nn>-solutions.py); predict blocks and fill-ins (blank filled
   with its first accepted answer) where they sit on the page, in a second engine. An answer
   must not raise, and must print what its <details> shows.

Run lines marked data-run="offline" use libraries the browser cannot load. They are
reported as offline, never as a pass.

Exit 0 = every output matches; 1 = a mismatch, a failing Try It starter or answer (or, with
--probe, a module that cannot load); 2 = engine missing or an unreadable file. Stdlib only;
the engine is set up with `npm ci` in tools/pyodide (see its README).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pyodide_engine import EngineError, EngineTimeout, engine_available, run_job
from verify_course import Node, parse, text_of

REFS = Path(__file__).resolve().parent.parent / "references"
if str(REFS) not in sys.path:
    sys.path.append(str(REFS))
from nerdit_world_gen import build_files  # noqa: E402

PLOT_RUNNER = "nerditRunPlot"
# nerdit-plot-runner.js runs this in the learner's namespace before their code.
PLOT_PRELUDE = ('import warnings\nwarnings.filterwarnings("ignore", message=".*non-GUI backend.*")\n'
                'import matplotlib\nmatplotlib.use("AGG")\nimport matplotlib.pyplot as plt\nplt.close("all")\n')


def _in_order(node: Node):
    """Descendants of `node` in page order."""
    for child in node.children:
        yield child
        yield from _in_order(child)


def _first(node: Node, test) -> Node | None:
    return next((n for n in _in_order(node) if test(n)), None)


def _is_python(node: Node) -> bool:
    """data-lang the way the website reads it (lessonHighlight.ts): trimmed, any case, `py` too."""
    return (node.attrs.get("data-lang") or "").strip().lower() in ("python", "py")


def _code(pre: Node) -> str:
    """The code of a <pre>, without the Copy button that sits beside the <code>."""
    code = _first(pre, lambda n: n.tag == "code")
    return text_of(code if code is not None else pre)


def _inside(node: Node, cls: str) -> bool:
    node = node.parent
    while node is not None:
        if cls in node.classes:
            return True
        node = node.parent
    return False


def _code_filled(pre: Node, answer: str) -> str:
    """The code of a fill-in <pre> with each blank replaced by its first accepted answer."""
    out: list[str] = []

    def walk(node: Node):
        for item in node.content:
            if isinstance(item, str):
                out.append(item)
            elif item.tag == "input" and "nerdit-blank" in item.classes:
                out.append((item.attrs.get("data-answer") or answer).split("|")[0].strip())
            elif item.tag != "button":
                walk(item)
    code = _first(pre, lambda n: n.tag == "code")
    walk(code if code is not None else pre)
    return "".join(out)


def _shown_in(node: Node) -> str | None:
    out = _first(node, lambda n: "nerdit-out" in n.classes)
    pre = out and _first(out, lambda n: n.tag == "pre")
    return _code(pre) if pre is not None else None


def _answers(tree) -> list[dict]:
    """Practice solutions, predict blocks and Python fill-ins, in page order.
    `after` = how many run lines come before the answer on the page."""
    answers, runs_before = [], 0
    for node in tree.all:
        if "nerdit-run" in node.classes:
            runs_before += 1
        elif "nerdit-solution" in node.classes and not _first(node, lambda n: "nerdit-run" in n.classes):
            pre = _first(node, lambda n: n.tag == "pre" and _is_python(n))
            if pre is not None:
                answers.append({"kind": "practice", "code": _code(pre).strip("\n"), "shown": _shown_in(node),
                                "after": runs_before})
        elif "nerdit-predict" in node.classes:
            pre = _first(node, lambda n: n.tag == "pre" and _is_python(n) and not _inside(n, "nerdit-predict-answer"))
            if pre is not None:
                answers.append({"kind": "predict", "code": _code(pre).strip("\n"), "shown": _shown_in(node),
                                "after": runs_before})
        elif "nerdit-fillblank" in node.classes:
            pre = _first(node, lambda n: n.tag == "pre" and _is_python(n))
            if pre is not None:
                answers.append({"kind": "fill-in", "code": _code_filled(pre, node.attrs.get("data-answer") or ""),
                                "shown": None, "after": runs_before})
    return answers


def python_parts(content: str) -> dict:
    """{"dataset": recipe | None, "runs": [{"code", "shown", "offline"}], "tryits": [code],
    "answers": [{"kind", "code", "shown", "after"}]}.

    `shown` is None when the run's output is a chart (its output half has no <pre>).
    Raises ValueError when the dataset block is not valid JSON.
    """
    tree = parse(content)
    dataset = None
    block = next((n for n in tree.all if n.tag == "script" and "nerdit-dataset" in n.classes), None)
    if block is not None:
        raw = "".join(c for c in block.content if isinstance(c, str))
        try:
            dataset = json.loads(raw)
        except ValueError as exc:
            raise ValueError(f"dataset block is not valid JSON ({exc})") from None
    runs, tryits = [], []
    for node in tree.all:
        if "nerdit-run" in node.classes:
            half = _first(node, lambda n: "nerdit-in" in n.classes)
            pre = half and _first(half, lambda n: n.tag == "pre" and _is_python(n))
            if pre is None:
                continue
            out = _first(node, lambda n: "nerdit-out" in n.classes)
            shown_pre = out and _first(out, lambda n: n.tag == "pre")
            runs.append({"code": _code(pre), "shown": _code(shown_pre) if shown_pre is not None else None,
                         "offline": node.attrs.get("data-run") == "offline"})
        elif "nerdit-tryit" in node.classes:
            calls = " ".join(n.attrs.get("onclick", "") for n in _in_order(node) if n.tag == "button")
            if not _is_python(node) and "nerditRunPython" not in calls and PLOT_RUNNER not in calls:
                continue
            editor = _first(node, lambda n: n.tag == "textarea")
            if editor is None:
                continue
            code = text_of(editor)
            code = code[1:] if code.startswith("\n") else code  # browsers drop it too
            tryits.append(PLOT_PRELUDE + code if PLOT_RUNNER in calls else code)
    return {"dataset": dataset, "runs": runs, "tryits": tryits, "answers": _answers(tree)}


def normalise(text: str) -> str:
    """Layout only: LF line ends, no trailing spaces, no trailing blank lines."""
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _short(text: str, n: int = 80) -> str:
    text = normalise(text)
    return text if len(text) <= n else text[:n] + "…"


def check_lesson(content: str, timeout: int = 120) -> dict:
    """Runs one lesson's Python. Raises EngineError when the engine is missing or broken.

    `details` holds the full printed output of every mismatched example: a writer cannot run
    code, so a regeneration needs the real output, not an 80-character excerpt.
    """
    report = {"examples": 0, "match": 0, "mismatch": [], "offline": [], "tryit_fail": [], "details": [],
              "answers": 0, "answer_fail": []}
    try:
        parts = python_parts(content)
        files = build_files(parts["dataset"]) if parts["dataset"] is not None else {}
    except (ValueError, KeyError, TypeError) as exc:
        report["mismatch"].append(f"dataset block: {exc!r}" if not isinstance(exc, ValueError) else f"dataset block: {exc}")
        return report
    runs, tryits, answers = parts["runs"], parts["tryits"], parts["answers"]
    if not runs and not tryits and not answers:
        return report
    steps = []
    for i, run in enumerate(runs, 1):
        report["examples"] += 1
        if run["offline"]:
            report["offline"].append(f"example {i}: offline run line; check it in the pinned local "
                                     f"environment (not on this engine)")
        else:
            steps.append({"id": f"run{i}", "code": run["code"], "fresh": False})
    # Practice answers run after every run line, in one namespace: the order of L<nn>-solutions.py.
    counts: dict[str, int] = {}
    labels = []
    for k, ans in enumerate(answers):
        counts[ans["kind"]] = counts.get(ans["kind"], 0) + 1
        labels.append(f"{'practice task' if ans['kind'] == 'practice' else ans['kind']} {counts[ans['kind']]}")
        if ans["kind"] == "practice":
            steps.append({"id": f"ans{k}", "code": ans["code"], "fresh": False})
    # Predict and fill-in answers run where they sit on the page, in a second engine, so the
    # values they set never change what a later run line prints.
    # Each one runs on a saved copy of the names, restored after it, so a predict's `x = 5`
    # never reaches the next answer either (mutating a shared object still would).
    in_place = []
    for i in range(len(runs) + 1):
        for k, a in enumerate(answers):
            if a["kind"] != "practice" and a["after"] == i:
                in_place += [{"id": f"save{k}", "code": "__nerdit_saved__ = dict(globals())", "fresh": False},
                             {"id": f"ans{k}", "code": a["code"], "fresh": False},
                             {"id": f"restore{k}", "code": "(lambda saved: (globals().clear(), "
                                                           "globals().update(saved)))(__nerdit_saved__)",
                              "fresh": False}]
        if i < len(runs) and not runs[i]["offline"]:
            in_place.append({"id": f"place-run{i + 1}", "code": runs[i]["code"], "fresh": False})

    def engine_run(job_steps: list) -> dict | None:
        try:
            return {r["id"]: r for r in run_job({"files": files, "steps": job_steps, "probe": []}, timeout)["results"]}
        except EngineTimeout:
            report["mismatch"].append(f"timed out after {timeout} s: an example never finishes "
                                      f"(a loop without an end, or a very slow model?)")
            return None

    # Run lines share one engine, like notebook cells. Each Try It gets an engine of its own
    # with only the dataset files: on the site no run line ever executes before it.
    results = engine_run(steps) if steps else {}
    if results is None:
        return report
    for j, code in enumerate(tryits, 1):
        got = engine_run([{"id": f"tryit{j}", "code": code, "fresh": True}])
        if got is None:
            return report
        results.update(got)
    if any(s["id"].startswith("ans") for s in in_place):
        got = engine_run(in_place)
        if got is None:
            return report
        results.update({key: val for key, val in got.items() if key.startswith("ans")})
    has_offline = any(r["offline"] for r in runs)
    for k, ans in enumerate(answers):
        report["answers"] += 1
        got, shown = results[f"ans{k}"], ans["shown"]
        if got["error"] is not None and has_offline and "NameError" in got["error"]:
            report["offline"].append(f"{labels[k]}: uses a value from an offline run line; check it locally")
            continue
        if (shown is None and ans["kind"] != "fill-in" and got["error"] is None
                and not got.get("figures")):
            # CORE.md §8: a revealed answer shows its result, so it is compared, never trusted.
            report["answer_fail"].append(f"{labels[k]}: shows no output, so it cannot be checked; add the "
                                         f"<div class=\"nerdit-out\"> with what Python prints")
        elif got["error"] is not None and (shown is None or got["error"] not in normalise(shown)):
            report["answer_fail"].append(f"{labels[k]}: the answer raises '{got['error']}'")
        elif got["error"] is None and shown is not None and normalise(got["stdout"]) != normalise(shown):
            report["answer_fail"].append(f"{labels[k]}: shown {_short(shown)!r} "
                                         f"but Python prints {_short(got['stdout'])!r}")
    for i, run in enumerate(runs, 1):
        if run["offline"]:
            continue
        got = results[f"run{i}"]
        printed = normalise(got["stdout"] + ("\n" + got["error"] if got["error"] else ""))
        if run["shown"] is None:
            if got["error"] is None and got["figures"] >= 1:
                report["match"] += 1
                continue
            report["mismatch"].append(f"example {i}: a chart example must run and draw a figure "
                                      f"(error: {got['error']}, figures: {got['figures']})")
        elif got["error"] is not None:
            if got["error"] in normalise(run["shown"]):
                report["match"] += 1
                continue
            report["mismatch"].append(f"example {i}: Python raises '{got['error']}', which the lesson does not show")
        elif normalise(got["stdout"]) == normalise(run["shown"]):
            report["match"] += 1
            continue
        else:
            report["mismatch"].append(f"example {i}: shown {_short(run['shown'])!r} "
                                      f"but Python prints {_short(got['stdout'])!r}")
        report["details"].append({"example": i, "shown": run["shown"], "printed": printed})
    for j in range(1, len(tryits) + 1):
        err = results[f"tryit{j}"]["error"]
        if err is not None:
            report["tryit_fail"].append(f"Try It {j}: the starter program raises {err}")
    return report


def probe(modules: list[str]) -> int:
    versions = run_job({"files": {}, "steps": [], "probe": modules})["versions"]
    for m in modules:
        print(f"{m}: cannot load" if versions.get(m) is None else f"{m} {versions[m]}")
    return 1 if any(versions.get(m) is None for m in modules) else 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--course")
    ap.add_argument("--lesson")
    ap.add_argument("--timeout", type=int, default=120,
                    help="seconds for a lesson's run lines, and for each Try It (default 120)")
    ap.add_argument("--probe", help="comma-separated modules: print the version each loads, or cannot load")
    args = ap.parse_args()
    if not args.course and not args.probe:
        ap.error("give --course or --probe")
    ok, reason = engine_available()
    try:
        if args.probe:
            if not ok:
                raise EngineError(reason)
            return probe([m.strip() for m in args.probe.split(",") if m.strip()])
        course = json.loads(Path(args.course).read_text(encoding="utf-8"))
        lessons = [ls for ls in course.get("lessons", []) if not args.lesson or ls.get("id") == args.lesson]
        python = [ls for ls in lessons if has_python(ls.get("content") or "")]
        if python and not ok:
            raise EngineError(reason)
        bad = 0
        for ls in python:
            r = check_lesson(ls.get("content") or "", args.timeout)
            print(f"{ls.get('id')}: {r['examples']} examples, {r['match']} match, {len(r['mismatch'])} mismatch, "
                  f"{len(r['offline'])} offline, {len(r['tryit_fail'])} Try It failures, "
                  f"{r['answers']} answers, {len(r['answer_fail'])} answer failures")
            for line in r["mismatch"] + r["tryit_fail"] + r["answer_fail"] + r["offline"]:
                print(f"  - {line}")
            for d in r["details"]:  # in full: the regeneration prompt needs the real output
                print(f"    example {d['example']}, Python prints:")
                for out_line in (d["printed"] or "(nothing)").split("\n"):
                    print(f"    | {out_line}")
            bad += len(r["mismatch"]) + len(r["tryit_fail"]) + len(r["answer_fail"])
        return 1 if bad else 0
    except (EngineError, OSError, ValueError) as exc:  # a missing engine is never a pass
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def has_python(content: str) -> bool:
    """True when a lesson has Python to check (a broken dataset block counts: it must be reported)."""
    try:
        parts = python_parts(content)
    except ValueError:
        return True
    return bool(parts["runs"] or parts["tryits"] or parts["answers"])


if __name__ == "__main__":
    sys.exit(main())
