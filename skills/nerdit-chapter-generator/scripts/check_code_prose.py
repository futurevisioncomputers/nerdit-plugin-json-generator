#!/usr/bin/env python3
"""Fail when a lesson's explanation and its code disagree.

    python check_code_prose.py --course <course_output.json>

Two mechanical rules, for every paragraph and list item of explanation (not code, outputs,
tables, figures or the cheat sheet):

1. Code the prose names must be on the page. An inline <code> that is code-shaped (it holds
   ( ) . = [ ] or _) must appear, spaces aside, in the lesson's code, outputs, Try It
   editors or seed scripts. `head()` matches a call such as `head(3)`. Placeholders
   (`<item>`, `...`) and plain words (`if`, `None`, `TypeError`) are not judged.
2. A number the prose says is printed must be printed: "prints 12", "returns 1,250",
   "shows 3.5" need that number in the same section's shown output. (Inside an answer's
   <details> the answer checks compare the result instead.)

Exit 0 = prose and code agree; 1 = a disagreement; 2 = an unreadable file. Stdlib only.
Whether a sentence describes the code truly in other ways is judged by the QA agent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from verify_course import parse, text_of, walk

CODE_SHAPED = re.compile(r'[().=\[\]_]')
SAID_PRINTED = re.compile(r'\b(?:prints?|shows?|returns?|gives?|outputs?|displays?)\s+`?(-?\d[\d,]*(?:\.\d+)?)', re.I)
SKIP = {'table', 'figure', 'svg', 'pre', 'textarea', 'script'}
SKIP_CLASSES = {'nerdit-out', 'nerdit-cheatsheet', 'nerdit-syntax', 'nerdit-tryit', 'nerdit-files'}


def _squash(text: str) -> str:
    return ' '.join(text.split())


def _skipped(node) -> bool:
    while node is not None:
        if node.tag in SKIP or SKIP_CLASSES & node.classes:
            return True
        node = node.parent
    return False


def _in_details(node) -> bool:
    node = node.parent
    while node is not None:
        if node.tag == 'details':
            return True
        node = node.parent
    return False


def _has_prose_parent(node) -> bool:
    node = node.parent
    while node is not None:
        if node.tag in ('p', 'li'):
            return True
        node = node.parent
    return False


def _on_page(token: str, corpus: str) -> bool:
    token = _squash(token).rstrip(';')
    if token in corpus:
        return True
    return token.endswith('()') and token[:-1] in corpus  # head() names the call head(3)


def check_lesson(content: str) -> list[str]:
    tree = parse(content)
    corpus = _squash(' '.join(text_of(n) for n in tree.all
                              if n.tag in ('pre', 'textarea') or (n.tag == 'script' and n.attrs.get('type') == 'text/plain')))
    fails, section, outputs = [], 'opening', {}
    sections, lines, walks = [], {}, []
    for node in tree.all:
        if node.tag == 'h2':
            section = _squash(text_of(node))
        elif node.tag == 'pre' and not _skipped(node.parent):
            lines.setdefault(section, set()).update(_squash(ln) for ln in text_of(node).splitlines() if ln.strip())
        elif node.tag == 'ol' and 'nerdit-codewalk' in node.classes:
            walks.append((section, node))
        elif 'nerdit-out' in node.classes or 'nerdit-answer' in node.classes:
            outputs[section] = outputs.get(section, '') + ' ' + text_of(node)
        elif node.tag in ('p', 'li') and not _skipped(node) and not _has_prose_parent(node):
            sections.append((section, node))
    for section, node in sections:
        for code in _codes(node):
            token = text_of(code).strip()
            if (not CODE_SHAPED.search(token) or '<' in token or '...' in token or '…' in token
                    or _on_page(token, corpus)):
                continue
            fails.append(f'{section}: the prose names `{token}`, but no code or output on the page has it')
        if _in_details(node):
            continue  # an answer's own result is checked by the answer checks, not here
        shown = outputs.get(section, '').replace(',', '')
        for number in SAID_PRINTED.findall(text_of(node)):
            value = number.replace(',', '').rstrip('.')
            if not re.search(rf'(?<![\d.]){re.escape(value)}(?!\d)', shown):
                fails.append(f'{section}: the prose says the code gives {number}, but its shown output does not')
    for section, walk in walks:  # each step quotes one whole line of its section's code
        for step in (c for c in walk.children if c.tag == 'li'):
            quoted = next((c for c in step.children if c.tag == 'code'), None)
            token = _squash(text_of(quoted)) if quoted is not None else ''
            if token not in lines.get(section, set()):
                fails.append(f"{section}: code walk step `{token}` is not a whole line of this section's code")
    return fails


WALK_STEP_LINES = 8   # CORE.md §4: one step of a program's walk explains at most 8 code lines


def walk_problems(content: str, new_course: bool = False) -> tuple[list[str], list[str]]:
    """(failures, warnings): every program is followed by <ol class="nerdit-codewalk nerdit-walk-full">
    whose steps quote program lines in order, start at its first code line and cover at most
    WALK_STEP_LINES code lines each. Blank and comment lines do not count. A problem is a failure
    for a new course and a warning for a delivered one."""
    problems = []
    for prog in (n for n in parse(content).all if 'nerdit-program' in n.classes):
        name = prog.attrs.get('data-file') or 'program'
        # The Python file, not the output and not a companion template or stylesheet (nerdit-file).
        half = next((n for n in walk(prog) if 'nerdit-in' in n.classes and 'nerdit-file' not in n.classes), None)
        pre = next((n for n in walk(half) if n.tag == 'pre'), None) if half is not None else None
        lines = [_squash(ln) for ln in (text_of(pre) if pre is not None else '').splitlines()]
        lines = [ln for ln in lines if ln and not ln.startswith('#')]
        sibs = prog.parent.children if prog.parent is not None else []
        after = sibs[sibs.index(prog) + 1:] if prog in sibs else []
        ol = next((n for n in after if n.tag == 'ol'), None)
        if ol is None or 'nerdit-walk-full' not in ol.classes:
            problems.append(f'{name}: no full code walk (<ol class="nerdit-codewalk nerdit-walk-full">) '
                            'after it; explain every line')
            continue
        starts, seen, at = [], [], 0
        for step in (c for c in ol.children if c.tag == 'li'):
            quoted = next((c for c in step.children if c.tag == 'code'), None)
            token = _squash(text_of(quoted)) if quoted is not None else ''
            if token not in lines[at:]:
                problems.append(f'{name}: walk step `{token}` is not the next program line in order')
                continue
            at = lines.index(token, at)
            starts.append(at)
            seen.append(SEEN_STEP in step.classes)
            at += 1
        if not starts or starts[0] != 0:
            problems.append(f'{name}: the walk must start at its first line `{lines[0] if lines else ""}`')
        for a, b, folded in zip(starts, starts[1:] + [len(lines)], seen):
            if b - a > WALK_STEP_LINES and not folded:  # a seen step only points back, at any length
                problems.append(f'{name}: the walk step at `{lines[a]}` covers {b - a} lines; '
                                f'at most {WALK_STEP_LINES} per step')
    return (problems, []) if new_course else ([], problems)


SEEN_STEP = 'nerdit-walk-seen'   # CORE.md §4: folds lines explained earlier into one pointer step
SEEN_STEP_WORDS = 15              # a pointer, not a second explanation


def _walk_steps(content: str):
    """(section, quoted line, seen?, words of prose) for every code-walk step, in page order."""
    section = 'opening'
    for node in parse(content).all:
        if node.tag == 'h2':
            section = _squash(text_of(node))
        elif node.tag == 'ol' and 'nerdit-codewalk' in node.classes:
            for step in (c for c in node.children if c.tag == 'li'):
                codes = [c for c in step.children if c.tag == 'code']
                prose = text_of(step)
                for code in codes:
                    prose = prose.replace(text_of(code), ' ', 1)
                line = _squash(text_of(codes[0])) if codes else ''
                yield section, line, SEEN_STEP in step.classes, len(prose.split())


def repeat_problems(lessons: list[dict], new_course: bool = False,
                    know_earlier: bool = True) -> tuple[list[str], list[str]]:
    """(failures, warnings): each code line is explained once per course (owner, 2026-11-04).
    A walk step quoting a line an earlier step (earlier section or lesson) explained repeats it;
    a <li class="nerdit-walk-seen"> step folds such lines into one short pointer instead. Without
    the earlier lessons (the gate sees one), a seen step's pointer is not judged."""
    walked, problems = {}, []
    for lesson in lessons:
        lid = lesson.get('id', '?')
        for section, line, seen, words in _walk_steps(lesson.get('content', '')):
            if not line:
                continue
            where, first = f'{lid} {section}', walked.get(line)
            if seen:
                if first is None and know_earlier:
                    problems.append(f'{where}: seen step `{line}` was never explained in an earlier '
                                    'section or lesson; explain it here instead')
                if words > SEEN_STEP_WORDS:
                    problems.append(f'{where}: seen step `{line}` has {words} words; keep it short '
                                    f'(at most {SEEN_STEP_WORDS}), it only points back')
            elif first is not None:
                problems.append(f'{where}: walk step `{line}` re-explains a line {first} already explained; '
                                f'drop it, or fold it into one <li class="{SEEN_STEP}"> step')
            else:
                walked[line] = where
    return (problems, []) if new_course else ([], problems)


def _codes(node):
    for child in node.children:
        if child.tag == 'code':
            yield child
        elif child.tag not in ('p', 'li'):
            yield from _codes(child)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--course', required=True)
    ap.add_argument('--new-course', action='store_true', help='a program without a full walk fails')
    args = ap.parse_args(argv)
    try:
        lessons = json.loads(Path(args.course).read_text(encoding='utf-8'))['lessons']
    except (OSError, ValueError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    total = 0
    for lesson in lessons:
        for line in check_lesson(lesson.get('content', '')):
            total += 1
            print(f'FAIL {lesson["id"]}: {line}')
        w_fails, w_warns = walk_problems(lesson.get('content', ''), args.new_course)
        for line in w_fails:
            total += 1
            print(f'FAIL {lesson["id"]}: {line}')
        for line in w_warns:
            print(f'WARN {lesson["id"]}: {line}')
    r_fails, r_warns = repeat_problems(lessons, args.new_course)
    for line in r_fails:
        total += 1
        print(f'FAIL {line}')
    for line in r_warns:
        print(f'WARN {line}')
    print(f'CODE-PROSE: {total} disagreement(s)')
    return 1 if total else 0


if __name__ == '__main__':
    raise SystemExit(main())
