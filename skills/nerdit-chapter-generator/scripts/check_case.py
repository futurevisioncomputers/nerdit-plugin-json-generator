#!/usr/bin/env python3
"""Topic first, case study second (CORE.md §2, owner 2026-10-27).

    python check_case.py --course <course_output.json> --world <world.json>

Learners were confused by who Future Vision Computer Institute and Neha are when the course
world was woven into the explanation. Each concept section now explains the idea in general
terms, then opens its case study with <h3 class="nerdit-casehead">🌟 Case Study: …</h3>; the
course world's names and data appear only after that heading. The first lesson introduces the
world once, before section 1, in <div class="nerdit-info-box nerdit-case-intro">.

Case studies are used where they teach (owner, 2026-10-28): a section may have none.
Fails: a world name (the business, its short name, the owner, a cast member, a branch) before a
section's case study heading, or in a section without one, in prose, code or a figure; a section
with two case study headings; a lesson with none; a first lesson without the card naming the
business and a cast member. Warns (case_warnings): a case study in every one of 3+ sections.
Cheat sheet and practice sections are not concept sections. Exit 0 = pass, 1 = a problem,
2 = unreadable file. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from make_world_data import load_world
from verify_course import Node, parse, walk

CASEHEAD = "nerdit-casehead"
INTRO = "nerdit-case-intro"
NOT_CONCEPT = {"nerdit-cheatsheet", "nerdit-practical"}


def world_names(world: dict) -> list[str]:
    biz = world.get("business") or {}
    names = [biz.get("name"), (biz.get("owner") or {}).get("name")]
    if biz.get("name") and len(biz["name"].split()) > 2:
        names.append(" ".join(biz["name"].split()[:2]))         # "Future Vision"
    names += [c.get("name") for c in world.get("cast") or []] + list(biz.get("branches") or [])
    return [n for n in dict.fromkeys(names) if n]


def _text(items) -> str:
    parts, stack = [], list(reversed(items))
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            parts.append(item)
        else:
            parts.append(" ")
            stack.extend(reversed(item.content))
    return "".join(parts)


def _named(text: str, names: list[str]) -> str | None:
    for name in names:
        if re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", text):
            return name
    return None


def _before(sec: Node, stop: Node) -> list:
    """The section's content in page order up to `stop` (an element inside it)."""
    out = []
    def visit(node) -> bool:
        for item in node.content:
            if item is stop:
                return True
            if isinstance(item, str) or stop not in list(walk(item)):
                out.append(item)
            elif visit(item):
                return True
        return False
    visit(sec)
    return out


def case_problems(html: str, names: list[str], first: bool) -> list[str]:
    if not names:
        return []
    tree = parse(html)
    problems = []
    sections = concept_sections(tree)
    if first:
        intro = next((n for n in tree.all if INTRO in n.classes), None)
        text = _text(intro.content) if intro is not None else ""
        if not (names[0] in text and _named(text, names[1:])):
            problems.append('the first lesson needs a "Meet the case study" card (<div class="nerdit-info-box '
                            f'{INTRO}">) before section 1: who {names[0]} is, the people in its story, '
                            "and the data the course uses")
    total = 0
    for n_sec, sec in enumerate(sections, 1):
        heads = [n for n in walk(sec) if CASEHEAD in n.classes]
        total += len(heads)
        if not heads:   # a section may teach without the course world (owner, 2026-10-28)
            name = _named(_text(sec.content), names)
            if name:
                problems.append(f'section {n_sec} names "{name}" before its case study; explain the idea in '
                                f'general terms, or add <h3 class="{CASEHEAD}"> before the course world')
            continue
        if len(heads) > 1:
            problems.append(f"section {n_sec} has {len(heads)} case study headings; use one")
        first_head = next(n for n in tree.all if n in heads)
        name = _named(_text(_before(sec, first_head)), names)
        if name:
            problems.append(f'section {n_sec} names "{name}" before its case study; explain the idea in general '
                            f'terms, then put the course world after <h3 class="{CASEHEAD}">')
    if sections and not total:
        problems.append(f'the lesson has no case study; give at least one section a <h3 class="{CASEHEAD}">'
                        "🌟 Case Study: …</h3> where the course world adds a decision or real numbers")
    return problems


def concept_sections(tree) -> list:
    return [n for n in tree.all if n.tag == "section"
            and not any(d.classes & NOT_CONCEPT for d in walk(n)) and not n.classes & NOT_CONCEPT]


def case_warnings(html: str) -> list[str]:
    """A case study in every concept section (3 or more): keep only those that teach (owner, 2026-10-28)."""
    sections = concept_sections(parse(html))
    if len(sections) >= 3 and all(any(CASEHEAD in n.classes for n in walk(sec)) for sec in sections):
        return [f"every one of the {len(sections)} concept sections has a case study; keep the ones that add a "
                "decision or real numbers, and teach the rest with a plain worked example"]
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--course", required=True)
    ap.add_argument("--world", required=True)
    args = ap.parse_args(argv)
    try:
        lessons = json.loads(Path(args.course).read_text(encoding="utf-8"))["lessons"]
        names = world_names(load_world(Path(args.world)))
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    bad = 0
    for i, lesson in enumerate(lessons):
        for p in case_problems(lesson.get("content", ""), names, first=i == 0):
            print(f"FAIL {lesson['id']}: {p}")
            bad += 1
        for w in case_warnings(lesson.get("content", "")):
            print(f"WARN {lesson['id']}: {w}")
    print(f"case study: {len(lessons)} lesson(s), {bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
