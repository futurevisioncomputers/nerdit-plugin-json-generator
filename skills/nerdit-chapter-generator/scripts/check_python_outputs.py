#!/usr/bin/env python3
"""Check every Python output a lesson shows, on the website's own engine (Pyodide 0.26.2).

    python check_python_outputs.py --course <course_output.json> [--lesson <id>] [--timeout N]
    python check_python_outputs.py --probe numpy,pandas,sklearn

Per lesson:
1. build the dataset block's CSV files, as the browser does;
2. run the Python run lines in page order in one namespace, like notebook cells, and compare
   each printed output with the one the lesson shows (a shown error must contain Python's
   last error line; a run whose output is a chart must draw a figure);
3. run each Python Try It starter alone in a fresh namespace: it must not raise.

Run lines marked data-run="offline" use libraries the browser cannot load. They are
reported as offline, never as a pass.

Exit 0 = every output matches; 1 = a mismatch or a failing Try It starter (or, with
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


def python_parts(content: str) -> dict:
    """{"dataset": recipe | None, "runs": [{"code", "shown", "offline"}], "tryits": [code]}.

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
    return {"dataset": dataset, "runs": runs, "tryits": tryits}


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
    report = {"examples": 0, "match": 0, "mismatch": [], "offline": [], "tryit_fail": [], "details": []}
    try:
        parts = python_parts(content)
        files = build_files(parts["dataset"]) if parts["dataset"] is not None else {}
    except (ValueError, KeyError, TypeError) as exc:
        report["mismatch"].append(f"dataset block: {exc!r}" if not isinstance(exc, ValueError) else f"dataset block: {exc}")
        return report
    runs, tryits = parts["runs"], parts["tryits"]
    if not runs and not tryits:
        return report
    steps = []
    for i, run in enumerate(runs, 1):
        report["examples"] += 1
        if run["offline"]:
            report["offline"].append(f"example {i}: offline run line; check it in the pinned local "
                                     f"environment (not on this engine)")
        else:
            steps.append({"id": f"run{i}", "code": run["code"], "fresh": False})

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
                  f"{len(r['offline'])} offline, {len(r['tryit_fail'])} Try It failures")
            for line in r["mismatch"] + r["tryit_fail"] + r["offline"]:
                print(f"  - {line}")
            for d in r["details"]:  # in full: the regeneration prompt needs the real output
                print(f"    example {d['example']}, Python prints:")
                for out_line in (d["printed"] or "(nothing)").split("\n"):
                    print(f"    | {out_line}")
            bad += len(r["mismatch"]) + len(r["tryit_fail"])
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
    return bool(parts["runs"] or parts["tryits"])


if __name__ == "__main__":
    sys.exit(main())
