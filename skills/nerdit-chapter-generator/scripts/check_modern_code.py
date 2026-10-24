#!/usr/bin/env python3
"""Fail on deprecated Python a learner would see or download (references/deprecated.md).

    python check_modern_code.py --course <course_output.json> [--new-course]
    python check_modern_code.py --files <pack or files folder> [--new-course]

Scans every Python block a lesson shows (run lines, Try It starters, predict and solution
blocks) and every .py and .ipynb code cell under --files. Comments are not scanned.
--new-course adds the rules for new courses only (httpx2 instead of httpx).

Exit 0 = nothing deprecated; 1 = deprecated code found; 2 = an unreadable file.
Stdlib only. Run-time deprecations are caught by running the files with -W error.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import sys
import tokenize

from check_python_outputs import _code, _first, _in_order, _is_python
from verify_course import parse, text_of

RULES = Path(__file__).resolve().parent.parent / 'references' / 'deprecated.md'


def load_rules(new_course: bool = False, path: Path = RULES) -> list[tuple[re.Pattern, str]]:
    text = path.read_text(encoding='utf-8')
    blocks = ['deprecated'] + (['new-course'] if new_course else [])
    rules = []
    for name in blocks:
        body = re.search(rf'```{name}\n(.*?)```', text, re.S)
        if body is None:
            raise ValueError(f'{path}: no {name} block')
        for line in body.group(1).splitlines():
            if line.strip():
                pattern, _, instead = line.partition('  =>  ')
                rules.append((re.compile(pattern.strip(), re.M), instead.strip()))
    return rules


def _without_comments(code: str) -> str:
    """The code with every comment blanked, line numbers kept."""
    lines = code.splitlines(keepends=True)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type == tokenize.COMMENT:
                row, col = tok.start
                line = lines[row - 1]
                lines[row - 1] = line[:col] + ' ' * (len(line.rstrip('\r\n')) - col) + line[len(line.rstrip('\r\n')):]
    except (tokenize.TokenError, SyntaxError, IndentationError):
        # A Try It may hold a deliberate syntax error: fall back to a plain cut at '#'.
        return re.sub(r'#[^\n]*', '', code)
    return ''.join(lines)


def scan(code: str, new_course: bool = False, rules=None) -> list[dict]:
    """[{line, found, instead}] for each deprecated use, in code order."""
    clean = _without_comments(code)
    found = []
    for pattern, instead in rules if rules is not None else load_rules(new_course):
        for m in pattern.finditer(clean):
            found.append({'line': clean.count('\n', 0, m.start()) + 1, 'found': m.group(0).strip(),
                          'instead': instead})
    return sorted(found, key=lambda f: f['line'])


def lesson_code(html: str) -> list[str]:
    """Every Python block a learner sees on the page, in page order."""
    out = []
    for node in parse(html).all:
        if node.tag == 'pre' and _is_python(node):
            out.append(_code(node))
        elif 'nerdit-tryit' in node.classes:
            calls = ' '.join(n.attrs.get('onclick', '') for n in _in_order(node) if n.tag == 'button')
            if not (_is_python(node) or 'nerditRunPython' in calls or 'nerditRunPlot' in calls):
                continue
            editor = _first(node, lambda n: n.tag == 'textarea')
            if editor is not None:
                out.append(text_of(editor).lstrip('\n'))
    return out


def file_code(path: Path) -> str:
    if path.suffix == '.ipynb':
        nb = json.loads(path.read_text(encoding='utf-8'))
        return '\n'.join(''.join(c.get('source', [])) for c in nb.get('cells', []) if c.get('cell_type') == 'code')
    return path.read_text(encoding='utf-8')


def _report(where: str, code: str, rules) -> int:
    hits = scan(code, rules=rules)
    for h in hits:
        print(f'FAIL {where} line {h["line"]}: {h["found"]} -> write {h["instead"]}')
    return len(hits)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--course')
    ap.add_argument('--files')
    ap.add_argument('--new-course', action='store_true')
    args = ap.parse_args(argv)
    if not args.course and not args.files:
        ap.error('give --course, --files or both')
    try:
        rules = load_rules(args.new_course)
        hits = 0
        if args.course:
            course = json.loads(Path(args.course).read_text(encoding='utf-8'))
            for lesson in course['lessons']:
                for i, code in enumerate(lesson_code(lesson.get('content', '')), 1):
                    hits += _report(f'{lesson["id"]} block {i}', code, rules)
        if args.files:
            for path in sorted(Path(args.files).rglob('*')):
                if path.suffix in ('.py', '.ipynb'):
                    hits += _report(str(path.relative_to(args.files)), file_code(path), rules)
    except (OSError, ValueError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    print(f'{hits} deprecated use(s)' if hits else 'No deprecated code')
    return 1 if hits else 0


if __name__ == '__main__':
    raise SystemExit(main())
