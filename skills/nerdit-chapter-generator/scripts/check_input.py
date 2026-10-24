#!/usr/bin/env python3
"""Pre-flight the chapter input array before any lesson is generated.

Two live courses shipped with every `description` set to a verbatim copy of its `title`.
Descriptions are what the writers expand into a lesson and what `check_sequence.py` reads
to decide which lesson owns a concept, so a title-echo description degrades generation and
validation at once -- silently, because the run still completes.

Usage:
  python check_input.py --input <course-<chapter>_input.json> [--strict]
"""
import argparse
import json
import re
import sys
from pathlib import Path

from make_world_data import load_world

MIN_DESCRIPTION_WORDS = 12

# CORE.md §2b. A preset decides the run line's tags and which optional blocks a lesson may
# use. It is optional in the input -- when absent the writer derives it from `runner`, then
# by inference -- but a misspelled one would fall through to inference silently.
PRESETS = {"code", "spreadsheet", "visual", "quantitative", "conversational"}
RUNNER_PRESET = {"python": "code", "sql": "code", "plot": "code", "excel": "spreadsheet"}
# CORE.md §4: concept lessons use one run line per concept; hands-on lessons 2-3.
# "project" is the capstone chapter (CORE.md §8b): the single last chapter of a code course.
FOCUS = {"concept", "hands-on", "project"}
CODE_PRESETS = {"code", "spreadsheet"}


def _norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _is_code_course(input_lessons) -> bool:
    return any(str(s.get("runner")).lower() in RUNNER_PRESET or str(s.get("preset")).lower() in CODE_PRESETS
               for s in input_lessons)


def audit(input_lessons, world_declared=None):
    """Return [(severity, lesson_id, message)] -- ERROR blocks a --strict run.

    `world_declared`: whether the course has a world file; None skips the world rule."""
    out, seen = [], {}
    for i, src in enumerate(input_lessons):
        lid = src.get("id") or f"<index {i}>"
        title, desc = src.get("title", ""), src.get("description")
        if lid in seen:
            out.append(("ERROR", lid, f"duplicate id (also at index {seen[lid]})"))
        seen.setdefault(lid, i)
        if not title:
            out.append(("ERROR", lid, "missing title"))
        if desc is None or not str(desc).strip():
            out.append(("ERROR", lid, "missing description -- the writer has nothing "
                                      "to expand beyond the title"))
        elif _norm(desc) == _norm(title):
            out.append(("ERROR", lid, "description repeats the title verbatim -- write "
                                      "what the lesson teaches, in a sentence or two"))
        elif len(str(desc).split()) < MIN_DESCRIPTION_WORDS:
            out.append(("WARN", lid, f"description is {len(str(desc).split())} words; "
                                     f"under {MIN_DESCRIPTION_WORDS} gives the writer "
                                     f"little to work from"))

        preset = src.get("preset")
        if preset is not None and str(preset).lower() not in PRESETS:
            out.append(("ERROR", lid, f"unknown preset {preset!r} -- one of "
                                      f"{', '.join(sorted(PRESETS))}"))

        focus = src.get("focus")
        if focus is not None and str(focus).lower() not in FOCUS:
            out.append(("ERROR", lid, f"unknown focus {focus!r} -- one of concept, hands-on, project (CORE.md §4, §8b)"))

    presets = {str(s.get("preset")).lower() for s in input_lessons if s.get("preset")}
    if len(presets) > 1:
        out.append(("ERROR", "<chapter>", f"chapter mixes presets ({', '.join(sorted(presets))}) "
                                          f"-- one preset per chapter, see CORE.md §2b"))

    if not presets:
        runners = {str(s.get("runner")).lower() for s in input_lessons if s.get("runner")}
        derived = {RUNNER_PRESET[r] for r in runners if r in RUNNER_PRESET}
        if len(derived) > 1:
            out.append(("WARN", "<chapter>", f"runners imply more than one preset "
                                             f"({', '.join(sorted(derived))}) -- set an "
                                             f"explicit \"preset\" so the chapter is consistent"))

    projects = [i for i, s in enumerate(input_lessons) if str(s.get("focus")).lower() == "project"]
    if len(projects) > 1:
        out.append(("ERROR", "<chapter>", f"{len(projects)} project chapters -- a course has one capstone "
                                          f"(CORE.md §8b)"))
    elif projects and projects[0] != len(input_lessons) - 1:
        lid = input_lessons[projects[0]].get("id") or f"<index {projects[0]}>"
        out.append(("ERROR", lid, "the capstone (focus: project) must be the last chapter (CORE.md §8b)"))
    code_course = _is_code_course(input_lessons)
    if code_course and not projects:
        out.append(("WARN", "<chapter>", "code course without a capstone chapter -- add one last chapter "
                                         "with focus: project (plan decision 9, CORE.md §8b)"))
    if code_course and world_declared is False:
        out.append(("ERROR", "<chapter>", "code and data courses declare a world: put "
                                          "course-<chapter>_world.json beside the input or pass --world "
                                          "(plan decision 8)"))

    # No order-inversion check here on purpose. Deciding that lesson 3 should come before
    # lesson 7 needs to know which term is a lesson's *subject* versus a passing mention,
    # and every mechanical proxy tried for that (first mention, title-word overlap) either
    # never fires or flags the course's own subject in every lesson. Order inversions are
    # judged twice with better evidence: by the orchestrator reading the titles in Step 1,
    # and by check_sequence.py against the generated lessons after Step 4.
    return out


def main():
    ap = argparse.ArgumentParser(description="Pre-flight a chapter input array")
    ap.add_argument("--input", required=True)
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero when any ERROR is found")
    ap.add_argument("--world", help="optional course world file or library reference")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        lessons = json.load(f)

    world = args.world
    sibling = Path(args.input).with_name(Path(args.input).name.replace("_input.json", "_world.json"))
    if not world and sibling != Path(args.input) and sibling.is_file():
        world = str(sibling)
    findings = audit(lessons, world_declared=bool(world))
    if world:
        try:
            load_world(Path(world))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            findings.append(("ERROR", "<world>", str(exc)))
    if not findings:
        print(f"INPUT: clean -- {len(lessons)} lessons")
        return
    errors = sum(1 for s, _, _ in findings if s == "ERROR")
    print(f"INPUT: {errors} error(s), {len(findings) - errors} warning(s)")
    for sev, lid, msg in findings:
        print(f"  {sev} {lid}: {msg}")
    if args.strict and errors:
        sys.exit(2)


if __name__ == "__main__":
    main()
