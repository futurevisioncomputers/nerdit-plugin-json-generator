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

from verify_course import parse, text_of

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
    sections = []
    for node in tree.all:
        if node.tag == 'h2':
            section = _squash(text_of(node))
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
    return fails


def _codes(node):
    for child in node.children:
        if child.tag == 'code':
            yield child
        elif child.tag not in ('p', 'li'):
            yield from _codes(child)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--course', required=True)
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
    print(f'CODE-PROSE: {total} disagreement(s)')
    return 1 if total else 0


if __name__ == '__main__':
    raise SystemExit(main())
