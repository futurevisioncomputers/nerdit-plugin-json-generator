#!/usr/bin/env python3
"""Check a lesson's experiment (`nerdit-sim`, references/sim.md) before a learner touches it.

    python check_sims.py --course <course_output.json>

For every <div class="nerdit-sim">: the spec is valid (1-3 controls, a predict question, a new
challenge, at least 3 tests), the model's `simulate` takes exactly the control ids, imports only
what the in-browser Python has, and - run offline in a separate process - answers every test,
the defaults, the prediction, every choice, an empty text box and each slider end with a result
in words, a why, and a picture and code the renderer can draw. Its tests must show both
outcomes: an experiment whose result never changes teaches nothing. At most one per lesson, and
the lesson loads /nerdit-sim.js.

Exit 0 = every experiment works; 1 = a problem; 2 = an unreadable file. Stdlib only.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import subprocess
import sys

SIM = re.compile(r'<div\b[^>]*\bclass="nerdit-sim"[^>]*>(.*?)<script\b[^>]*\bclass="nerdit-sim-spec"[^>]*>(.*?)</script>'
                 r'\s*<script\b[^>]*\bclass="nerdit-sim-model"[^>]*>(.*?)</script>', re.S)
SIM_BOX = re.compile(r'class="nerdit-sim"')
LOADER = '<script src="/nerdit-sim.js"></script>'
CONTROL_TYPES = ("text", "choice", "number", "slider")
PICTURES = ("pieces", "flow", "compare", "bars", "table")
# Modules the browser's Python (Pyodide) has without loading a package.
IMPORTS = {"math", "re", "json", "html", "statistics", "datetime", "itertools", "collections",
           "decimal", "fractions", "string", "textwrap", "functools", "operator"}
TAG_LIKE = re.compile(r"<[/\w!]")   # DOMPurify drops a <script> whose text matches this
MAX_RESULT = 80
TIMEOUT = 20

RUNNER = r'''
import inspect, json, sys
data = json.load(sys.stdin)
ns = {}
try:
    exec(compile(data["model"], "<model>", "exec"), ns)
except Exception as e:
    print(json.dumps({"load": f"{type(e).__name__}: {e}"})); sys.exit()
sim = ns.get("simulate")
if not callable(sim):
    print(json.dumps({"load": "no function simulate"})); sys.exit()
out = []
for call in data["calls"]:
    try:
        r = sim(**call)
        json.dumps(r)
        out.append({"value": r})
    except Exception as e:
        out.append({"error": f"{type(e).__name__}: {e}"})
print(json.dumps({"params": list(inspect.signature(sim).parameters), "results": out}))
'''


def _words(x) -> bool:
    return isinstance(x, str) and bool(x.strip())


def _span(r, n) -> bool:
    return (isinstance(r, list) and len(r) == 2 and all(isinstance(i, int) for i in r)
            and 0 <= r[0] <= r[1] < n)


def picture_problems(p) -> list[str]:
    """What stops the renderer drawing this picture (references/nerdit-sim.js)."""
    if not isinstance(p, dict) or p.get("type") not in PICTURES:
        return [f"picture type must be one of {', '.join(PICTURES)}"]
    t, bad = p["type"], []
    if t == "pieces":
        items = p.get("items")
        if not (isinstance(items, list) and 1 <= len(items) <= 8 and all(_words(i) for i in items)):
            return ["pieces: items must be 1-8 words"]
        for key in ("take", "left"):
            if key in p and not _span(p[key], len(items)):
                bad.append(f"pieces: {key} must be [from, to] inside items")
    elif t == "flow":
        steps = p.get("steps")
        if not (isinstance(steps, list) and 2 <= len(steps) <= 6 and all(_words(s) for s in steps)):
            return ["flow: steps must be 2-6 words"]
        if "reached" in p and not (isinstance(p["reached"], int) and -1 <= p["reached"] < len(steps)):
            bad.append("flow: reached must be a step index")
    elif t == "compare":
        cols = p.get("columns")
        if not (isinstance(cols, list) and 2 <= len(cols) <= 3):
            return ["compare: give 2-3 columns"]
        for c in cols:
            if not (isinstance(c, dict) and _words(c.get("title")) and _words(c.get("verdict"))
                    and isinstance(c.get("ok"), bool) and isinstance(c.get("lines", []), list)
                    and len(c.get("lines", [])) <= 5):
                bad.append("compare: each column needs a title, up to 5 lines, a verdict in words and ok")
    elif t == "bars":
        items = p.get("items")
        if not (isinstance(items, list) and 1 <= len(items) <= 8 and all(
                isinstance(i, dict) and _words(i.get("label")) and isinstance(i.get("value"), (int, float))
                for i in items)):
            bad.append("bars: items must be 1-8 {label, value}")
    elif t == "table":
        head, rows = p.get("head"), p.get("rows")
        if not (isinstance(head, list) and head and isinstance(rows, list) and len(rows) <= 8
                and all(isinstance(r, list) and len(r) == len(head) for r in rows)):
            return ["table: head and up to 8 rows of the same width"]
        if any(not (isinstance(m, int) and 0 <= m < len(rows)) for m in p.get("mark", [])):
            bad.append("table: mark must list row indexes")
    return bad


def result_problems(r) -> list[str]:
    if not isinstance(r, dict):
        return ["simulate must return a dict"]
    bad = []
    if not isinstance(r.get("ok"), bool):
        bad.append("result needs ok: true or false")
    if not (_words(r.get("result")) and len(r["result"]) <= MAX_RESULT):
        bad.append(f"result needs `result`: the outcome in words, up to {MAX_RESULT} characters")
    if not _words(r.get("why")):
        bad.append("result needs `why`: the rule behind the outcome")
    details = r.get("details", [])
    if not (isinstance(details, list) and all(isinstance(d, list) and len(d) == 2
                                              and all(isinstance(x, str) for x in d) for d in details)):
        bad.append("details must be [label, value] pairs of text")
    if "picture" in r:
        bad += picture_problems(r["picture"])
    code = r.get("code")
    if code is not None:
        lines = code.get("lines") if isinstance(code, dict) else None
        if not (isinstance(lines, list) and lines and all(isinstance(x, str) for x in lines)):
            bad.append("code needs lines: a list of text")
        elif any(not (isinstance(h, int) and 0 <= h < len(lines)) for h in code.get("highlight", [])):
            bad.append("code highlight must list line indexes")
    return bad


def _imports(model: str) -> list[str]:
    try:
        tree = ast.parse(model)
    except SyntaxError as e:
        return [f"model does not parse: {e.msg} (line {e.lineno})"]
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            used |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            used.add((node.module or "").split(".")[0])
    return [f"model imports {m}; the browser's Python has only {', '.join(sorted(IMPORTS))}"
            for m in sorted(used - IMPORTS)]


def run_model(model: str, calls: list[dict]) -> dict:
    proc = subprocess.run([sys.executable, "-I", "-c", RUNNER], input=json.dumps({"model": model, "calls": calls}),
                          capture_output=True, text=True, timeout=TIMEOUT)
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"load": (proc.stderr.strip().splitlines() or ["the model printed nothing"])[-1]}


def spec_problems(spec: dict) -> tuple[list[str], dict]:
    bad, controls = [], spec.get("controls")
    if not (isinstance(controls, list) and 1 <= len(controls) <= 3):
        return ["give 1-3 controls"], {}
    ids = {}
    for c in controls:
        cid = c.get("id") if isinstance(c, dict) else None
        if not (isinstance(cid, str) and cid.isidentifier()) or cid in ids:
            bad.append(f"control id {cid!r} must be a unique Python name")
            continue
        ids[cid] = c
        if c.get("type") not in CONTROL_TYPES:
            bad.append(f"control {cid}: type must be one of {', '.join(CONTROL_TYPES)}")
        if not _words(c.get("label")):
            bad.append(f"control {cid}: give it a label")
        if c.get("type") == "choice" and not (isinstance(c.get("options"), list) and 2 <= len(c["options"]) <= 4
                                              and c.get("value") in c["options"]):
            bad.append(f"control {cid}: a choice needs 2-4 options and a value among them")
        if c.get("type") == "slider" and not (all(isinstance(c.get(k), (int, float)) for k in ("min", "max", "value"))
                                              and c["min"] <= c["value"] <= c["max"]):
            bad.append(f"control {cid}: a slider needs min <= value <= max")
    ex = spec.get("examples")
    if ex is not None and not (isinstance(ex, dict) and ex.get("control") in ids
                               and isinstance(ex.get("values"), list) and 1 <= len(ex["values"]) <= 4):
        bad.append("examples: name a control and give 1-4 values")
    pr = spec.get("predict")
    if not (isinstance(pr, dict) and _words(pr.get("question")) and pr["question"].strip().endswith("?")
            and isinstance(pr.get("options"), list) and 2 <= len(pr["options"]) <= 4
            and isinstance(pr.get("answer"), int) and 0 <= pr["answer"] < len(pr["options"])
            and isinstance(pr.get("inputs"), dict) and set(pr["inputs"]) <= set(ids)):
        bad.append("predict: a question ending in ?, 2-4 options, the answer's index and inputs for the controls")
    if not _words(spec.get("challenge")):
        bad.append("challenge: give the learner a new case to try")
    tests = spec.get("tests")
    if not (isinstance(tests, list) and len(tests) >= 3 and all(
            isinstance(t, dict) and isinstance(t.get("inputs"), dict) and set(t["inputs"]) <= set(ids)
            and isinstance(t.get("ok"), bool) for t in tests)):
        bad.append("tests: give at least 3 {inputs, ok, result?} cases")
    elif len({t["ok"] for t in tests}) < 2:
        bad.append("tests: show both outcomes; an experiment whose result never changes teaches nothing")
    return bad, ids


def check_sim(spec_text: str, model: str) -> list[str]:
    try:
        spec = json.loads(spec_text)   # raw: a browser never decodes entities inside <script>
    except ValueError as e:
        return [f"spec is not JSON: {e}"]
    bad, ids = spec_problems(spec if isinstance(spec, dict) else {})
    bad += _imports(model)
    if bad or not ids:
        return bad
    defaults = {k: c.get("value") for k, c in ids.items()}
    calls, labels = [dict(defaults)], ["the starting values"]
    pr = spec["predict"]
    calls.append({**defaults, **pr["inputs"]}); labels.append("the prediction")
    for k, t in enumerate(spec["tests"], 1):
        calls.append({**defaults, **t["inputs"]}); labels.append(f"test {k}")
    for cid, c in ids.items():
        edges = {"choice": c.get("options", []), "text": [""],
                 "slider": [c.get("min"), c.get("max")], "number": [v for v in (c.get("min"), c.get("max")) if v is not None]}
        for v in edges.get(c.get("type"), []):
            calls.append({**defaults, cid: v}); labels.append(f"{cid} = {v!r}")
    try:
        out = run_model(model, calls)
    except subprocess.TimeoutExpired:
        return [f"model did not finish in {TIMEOUT} s"]
    if "load" in out:
        return [f"model does not load: {out['load']}"]
    if set(out["params"]) != set(ids):
        return [f"simulate takes {out['params']}; it must take exactly the control ids {sorted(ids)}"]
    for label, res in zip(labels, out["results"]):
        if "error" in res:
            bad.append(f"{label}: simulate fails with {res['error']}")
            continue
        bad += [f"{label}: {p}" for p in result_problems(res["value"])]
    for k, (t, res) in enumerate(zip(spec["tests"], out["results"][2:2 + len(spec["tests"])]), 1):
        value = res.get("value") or {}
        if value.get("ok") is not t["ok"]:
            bad.append(f"test {k}: expected ok={t['ok']}, the model says {value.get('ok')!r}")
        if t.get("result") and not str(value.get("result", "")).startswith(t["result"]):
            bad.append(f"test {k}: expected a result starting {t['result']!r}, got {value.get('result')!r}")
    return bad


def check_lesson(content: str) -> list[str]:
    sims = SIM.findall(content)
    if not SIM_BOX.search(content):
        return []
    bad = []
    if len(SIM_BOX.findall(content)) > 1:
        bad.append("one experiment per lesson; keep the one that teaches most")
    if len(sims) != len(SIM_BOX.findall(content)):
        bad.append('each nerdit-sim needs its head, goal and note, then a nerdit-sim-spec and a nerdit-sim-model script')
    if LOADER not in content:
        bad.append(f"the lesson uses an experiment but does not load it: add {LOADER} after the wrapper")
    for intro, spec_text, model in sims:
        for name, text, code in (("spec", spec_text, "\\u003c"), ("model", model, "\\x3c")):
            if TAG_LIKE.search(text):
                bad.append(f"the {name} has '{TAG_LIKE.search(text).group()}': write < before a letter, / or ! "
                           f"as {code}; the admin's sanitizer drops a script that looks like a tag, and the "
                           "experiment would vanish on publish")
        for part in ("nerdit-sim-head", "nerdit-sim-goal", "nerdit-sim-note"):
            if f'class="{part}"' not in intro:
                bad.append(f"the experiment has no {part}")
        bad += check_sim(spec_text, model)
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--course", required=True)
    args = ap.parse_args(argv)
    try:
        lessons = json.loads(Path(args.course).read_text(encoding="utf-8"))["lessons"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    total = 0
    for lesson in lessons:
        for problem in check_lesson(lesson.get("content") or ""):
            total += 1
            print(f"FAIL {lesson.get('id')}: sim: {problem}")
    print(f"SIMS: {total} problem(s)")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
