#!/usr/bin/env python3
"""Explain each code line once per course: fold code-walk steps an earlier walk explained.

    python fold_repeats.py --course <course_output.json> [--dry-run]

Lessons are read in order, keeping every line a code walk explained (CORE.md §4, owner
2026-11-04). A later step quoting such a line is a repeat:

- a short walk (`ol.nerdit-codewalk`) drops it; a walk left with no steps is removed;
- a full walk (`nerdit-walk-full`) must still cover every program line, so each run of repeated
  steps becomes one `<li class="nerdit-walk-seen"><code>first line</code> explained in Lesson 3.</li>`.
  A full-walk step is folded only when every program line it covers was explained before.

assemble_course.py runs this on every assembly, so writers never read earlier lessons to avoid
repeats and no lesson is regenerated for one. The CLI cleans a delivered course the same way.
Deterministic, stdlib only, zero model tokens. Exit 0 = written (or would be, with --dry-run);
2 = an unreadable file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from check_code_prose import SEEN_STEP, _squash
from verify_course import parse, text_of

OL_RE = re.compile(r'<ol\b[^>]*\bclass="[^"]*\bnerdit-codewalk\b[^"]*"[^>]*>(.*?)</ol>', re.S)
LI_RE = re.compile(r'<li\b[^>]*>.*?</li>', re.S)
CODE_RE = re.compile(r'<code\b[^>]*>.*?</code>', re.S)


def _program_lines(ol) -> list[str]:
    """The code lines of the program a full walk follows (as check_code_prose.walk_problems reads them)."""
    sibs = ol.parent.children if ol.parent is not None else []
    before = sibs[:sibs.index(ol)] if ol in sibs else []
    prog = next((n for n in reversed(before) if 'nerdit-program' in n.classes), None)
    if prog is None:
        return []
    stack, half = list(prog.children), None
    while stack and half is None:
        n = stack.pop(0)
        if 'nerdit-in' in n.classes and 'nerdit-file' not in n.classes:
            half = n
        stack.extend(n.children)
    pre = None
    if half is not None:
        stack = list(half.children)
        while stack and pre is None:
            n = stack.pop(0)
            pre = n if n.tag == 'pre' else None
            stack.extend(n.children)
    lines = [_squash(ln) for ln in (text_of(pre) if pre is not None else '').splitlines()]
    return [ln for ln in lines if ln and not ln.startswith('#')]


def walks(content: str):
    """Per code walk, in page order: (section number or None, full?, steps), each step being
    [quoted line, seen?, the program lines it covers, words of prose besides its code]."""
    section = None
    for node in parse(content).all:
        if node.tag == 'h2':
            m = re.match(r'\s*(\d+)', text_of(node))
            section = m.group(1) if m else None
        elif node.tag == 'ol' and 'nerdit-codewalk' in node.classes:
            full = 'nerdit-walk-full' in node.classes
            program = _program_lines(node) if full else []
            steps = []
            for li in (c for c in node.children if c.tag == 'li'):
                codes = [c for c in li.children if c.tag == 'code']
                prose = text_of(li)
                for code in codes:
                    prose = prose.replace(text_of(code), ' ', 1)
                steps.append([_squash(text_of(codes[0])) if codes else '', SEEN_STEP in li.classes, [],
                              len(prose.split())])
            at = 0
            for step in steps:  # a step covers its line up to the next step's line
                step[2] = [step[0]]
                if step[0] in program[at:]:
                    at = program.index(step[0], at)
                    step[2] = [at]
                    at += 1
            starts = [s[2][0] for s in steps if s[2] and isinstance(s[2][0], int)]
            for step in steps:
                if step[2] and isinstance(step[2][0], int):
                    a = step[2][0]
                    b = min([s for s in starts if s > a], default=len(program))
                    step[2] = program[a:b]
            yield section, full, steps


def _pointer(first: tuple[int, str | None], here: int) -> str:
    position, section = first
    if position != here:
        return f'explained in Lesson {position}.'
    return f'explained in section {section} above.' if section else 'explained above.'


def fold_lesson(content: str, position: int, walked: dict[str, tuple[int, str | None]]) -> tuple[str, int]:
    """Fold one lesson's repeats against `walked` (line -> (lesson position, section)), which it
    extends with the lines this lesson explains. Returns (new content, steps folded)."""
    plans = list(walks(content))
    blocks = list(OL_RE.finditer(content))
    if len(plans) != len(blocks):
        return content, 0   # the two readings disagree: leave the lesson as written
    out, last, folded = [], 0, 0
    for (section, full, steps), block in zip(plans, blocks):
        items = LI_RE.findall(block.group(1))
        if len(items) != len(steps):
            continue
        kept, run = [], []

        def close_run():
            if run:
                code = CODE_RE.search(items[run[0]])
                where = walked[steps[run[0]][0]]
                kept.append(f'<li class="{SEEN_STEP}">{code.group(0)} {_pointer(where, position)}</li>')
                run.clear()

        new = {}
        for i, (line, seen, covers, _words) in enumerate(steps):
            old = (not seen and line in walked and CODE_RE.search(items[i]) is not None
                   and all(c in walked for c in covers))
            if old:
                folded += 1
                if full:
                    run.append(i)
                continue
            close_run()
            kept.append(items[i])
            if not seen and line:
                new.setdefault(line, (position, section))
        close_run()
        for line, where in new.items():
            walked.setdefault(line, where)
        if len(kept) == len(items) and kept == items:
            continue
        out.append(content[last:block.start()])
        if kept:
            opening = block.group(0)[:block.start(1) - block.start()]
            out.append(opening + ''.join(kept) + '</ol>')
        last = block.end()
    out.append(content[last:])
    return ''.join(out), folded


def fold_course(lessons: list[dict]) -> int:
    """Fold every lesson in place, in course order. Returns the number of steps folded."""
    walked: dict[str, tuple[int, str | None]] = {}
    total = 0
    for position, lesson in enumerate(lessons, 1):
        lesson['content'], n = fold_lesson(lesson.get('content') or '', position, walked)
        total += n
    return total


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--course', required=True)
    ap.add_argument('--dry-run', action='store_true', help='count the repeats, write nothing')
    args = ap.parse_args(argv)
    path = Path(args.course)
    try:
        course = json.loads(path.read_text(encoding='utf-8'))
        lessons = course['lessons']
    except (OSError, ValueError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    total = fold_course(lessons)
    if not args.dry_run:
        path.write_text(json.dumps(course, ensure_ascii=False, indent=2), encoding='utf-8')
    verb = 'would fold' if args.dry_run else 'folded'
    print(f'FOLD: {verb} {total} walk step(s) across {len(lessons)} lessons')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
