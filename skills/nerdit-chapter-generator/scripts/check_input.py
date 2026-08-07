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

MIN_DESCRIPTION_WORDS = 12


def _norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def audit(input_lessons):
    """Return [(severity, lesson_id, message)] -- ERROR blocks a --strict run."""
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
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        lessons = json.load(f)

    findings = audit(lessons)
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
