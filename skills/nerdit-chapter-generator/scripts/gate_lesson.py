#!/usr/bin/env python3
"""One-lesson gate: every check a lesson must pass before it joins its course.

    python gate_lesson.py --input <course_input.json> --dir <lesson dir> --id <lesson-id>
                          [--contract v11] [--before-dir <dir> --modes figures,sql-layout]

Builds a one-lesson course from <dir>/<id>.html, .quiz.json and .concepts.json, then runs:
verify_course (schema, structure, density) -> check_world (with --world; without one, its SVG
number check) -> check_sql_outputs -> check_python_outputs (only
when the lesson has Python, every answer included; a missing engine fails it) -> deprecated code
(check_modern_code) -> prose names only code the page has (check_code_prose) -> computable quiz
answers (check_quiz) -> practice file names (files spec) -> SVG checks -> check_screens ->
check_prose -> check_refresh (only with --before-dir). Offline examples and the practice pack
need a venv; they are course-level steps (SKILL.md Step 4c and 5c). Replaces the course-specific rollout/gate.py.
Exit 0 = pass, 1 = a check failed, 2 = a file or the lesson id is missing. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "nerdit-lesson-illustrator" / "scripts"))

from assemble_course import build_course  # noqa: E402
from check_case import case_problems, world_names  # noqa: E402
from check_code_prose import check_lesson as check_code_prose  # noqa: E402
from check_modern_code import lesson_code, scan as scan_modern  # noqa: E402
from check_prose import banned_patterns, check_lesson as check_voice  # noqa: E402
from check_quiz import check_questions as check_quiz  # noqa: E402
from practice_files import name_problems, read_spec  # noqa: E402
from check_python_outputs import check_lesson as check_python, has_python  # noqa: E402
from pyodide_engine import EngineError, engine_available  # noqa: E402
from check_refresh import check as check_refresh  # noqa: E402
from check_screens import check_lesson as check_screens  # noqa: E402
from check_sql_outputs import check_lesson as check_sql  # noqa: E402
from check_world import check_lesson as check_world, svg_label_failures  # noqa: E402
from make_world_data import generate, load_world  # noqa: E402
from svgcheck import check_svg  # noqa: E402
from verify_course import Report, verify_density, verify_schema, verify_structure  # noqa: E402

SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S | re.I)


def gate(input_path: Path, lesson_dir: Path, lid: str, contract: str = "v11",
         before_dir: Path | None = None, modes=(), world_path: Path | None = None,
         new_course: bool = False) -> tuple[list[str], list[str]]:
    lessons = json.loads(Path(input_path).read_text(encoding="utf-8"))
    one = [s for s in lessons if s.get("id") == lid]
    if not one:
        raise KeyError(f"{lid} is not in {input_path}")
    for ext in (".html", ".quiz.json", ".concepts.json"):
        if not (Path(lesson_dir) / f"{lid}{ext}").is_file():
            raise FileNotFoundError(Path(lesson_dir) / f"{lid}{ext}")

    course = build_course("gate", one, None, str(lesson_dir), now_ms=0)
    fails: list[str] = []
    warns: list[str] = []

    rep = Report()
    verify_schema(rep, course, one)
    verify_structure(rep, course, contract)
    if contract == "v11":
        verify_density(rep, course, one)
    fails += [f"verify: {f}" for f in rep.failures]
    warns += [f"verify: {w}" for w in rep.warnings]

    html = course["lessons"][0]["content"]
    if world_path is not None:
        world = load_world(Path(world_path))
        wf, ww = check_world(html, world, generate(world))
        fails += [f"world: {f}" for f in wf]
        warns += [f"world: {w}" for w in ww]
        # Topic first, case study second: world names only after the section's case study heading.
        first = next(i for i, s in enumerate(lessons) if s.get("id") == lid) == 0
        if before_dir is None:
            fails += [f"case: {p}" for p in case_problems(html, world_names(world), first)]
    else:
        # No world: a diagram must still not draw a number the lesson never states.
        fails += [f"labels: {f}" for f in svg_label_failures(html, {})]
    sql = check_sql(html)
    fails += [f"sql: {m}" for m in sql["mismatch"]]
    warns += [f"sql: {u}" for u in sql["unchecked"]]
    if has_python(html):
        # Python outputs are checked on the website's engine; without it nothing is verified.
        if not engine_available()[0]:
            fails.append("python: engine missing (tools/pyodide/README.md)")
        else:
            try:
                py = check_python(html)
                fails += [f"python: {m}" for m in py["mismatch"] + py["tryit_fail"] + py.get("answer_fail", [])]
                warns += [f"python: {o}" for o in py["offline"]]
            except EngineError as exc:
                fails.append(f"python: engine error: {exc}")

    # Strict code accuracy: modern code only, prose that matches its code, computed quiz answers,
    # and practice file names that trace to this lesson.
    for i, code in enumerate(lesson_code(html), 1):
        fails += [f"modern: block {i} line {h['line']}: {h['found']} -> write {h['instead']}"
                  for h in scan_modern(code, new_course)]
    fails += [f"prose-code: {p}" for p in check_code_prose(html)]
    labelled = [(f"question {i}", qn) for i, qn in enumerate(course["lessons"][0].get("questions", []), 1)]
    labelled += [(f"assessment {i}", qn) for i, qn in enumerate(course["assessment"]["questions"], 1)]
    try:
        q_fails, q_warns = check_quiz(html, labelled)
        fails += [f"quiz: {f}" for f in q_fails]
        warns += [f"quiz: {w}" for w in q_warns]
    except EngineError as exc:
        fails.append(f"quiz: engine missing for a Python question ({exc})")
    try:
        spec = read_spec(html)
    except ValueError as exc:
        fails.append(f"files: {exc}")
        spec = None
    position = next(i for i, s in enumerate(lessons, 1) if s.get("id") == lid)
    for entry in (spec or {}).get("files", []):
        if "name" in entry:
            fails += [f"files: {p}" for p in name_problems(entry["name"], position)]

    for n, svg in enumerate(SVG_RE.findall(html), 1):
        fails += [f"svg {n}: {e}" for e in check_svg(svg, [], 0)]
    s_fails, s_warns = check_screens(html)
    fails += [f"screen: {f}" for f in s_fails]
    warns += [f"screen: {w}" for w in s_warns]

    patterns = banned_patterns()
    v_fails, v_warns = check_voice(html, patterns)
    if before_dir is not None:
        # A refresh may not touch prose, so a phrase the original already had cannot be fixed
        # here; report it, but do not fail a lesson the refresh is not allowed to repair.
        old_html = (Path(before_dir) / f"{lid}.html").read_text(encoding="utf-8")
        inherited = set(check_voice(old_html, patterns)[0])
        v_warns += [f"{f} (already in the original lesson)" for f in v_fails if f in inherited]
        v_fails = [f for f in v_fails if f not in inherited]
    fails += [f"voice: {f}" for f in v_fails]
    warns += [f"voice: {w}" for w in v_warns]

    if before_dir is not None:
        fails += [f"refresh: {p}" for p in check_refresh(Path(before_dir), Path(lesson_dir), lid, set(modes))]
    return fails, warns


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--contract", choices=["v10", "v11"], default="v11")
    ap.add_argument("--before-dir")
    ap.add_argument("--world", help="check seed and figure records against the course world")
    ap.add_argument("--modes", default="", help="comma list for the refresh guard")
    ap.add_argument("--new-course", action="store_true",
                    help="a course made after 2026-10-23: also require httpx2 (references/deprecated.md)")
    args = ap.parse_args()
    modes = {m.strip() for m in args.modes.split(",") if m.strip()}
    try:
        fails, warns = gate(Path(args.input), Path(args.dir), args.id, args.contract,
                            Path(args.before_dir) if args.before_dir else None, modes,
                            Path(args.world) if args.world else None, args.new_course)
    except (OSError, KeyError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(f"{'FAIL' if fails else 'PASS'}  {args.id}: {len(fails)} failure(s), {len(warns)} warning(s)")
    for f in fails:
        print(f"  - {f}")
    for w in warns:
        print(f"  WARN {w}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
