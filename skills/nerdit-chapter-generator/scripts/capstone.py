#!/usr/bin/env python3
"""Build a capstone project folder from the solution the writer wrote once (CORE.md §8b).

    python capstone.py --src <workdir>/capstone --out <folder>

<src> holds README.md, data/ (optional here: practice_files.py adds the world files),
solution/ and tests/ (test_m<k>_*.py per milestone, test_final_*.py). In the solution each
milestone's code sits between two marker lines, at the code's own indentation:

    # >>> M2: retries with backoff and jitter
    ...the milestone's code...
    # <<< M2

starter/ is made from solution/: each marked block becomes a TODO and
`raise NotImplementedError("M2: ...")`, so the starter imports, and each milestone's tests
fail on it until the learner writes that block. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

OPEN = re.compile(r'^(\s*)# >>> (M\d+): (.+?)\s*$')
CLOSE = re.compile(r'^\s*# <<< (M\d+)\s*$')
SKIP = {'__pycache__', '.pytest_cache'}


def milestones(code: str) -> list[str]:
    return [m.group(2) for m in map(OPEN.match, code.splitlines()) if m]


def make_starter(code: str) -> str:
    """The solution with each marked milestone block replaced by its TODO."""
    out, open_id = [], None
    for number, line in enumerate(code.splitlines(keepends=True), 1):
        opened, closed = OPEN.match(line), CLOSE.match(line)
        if open_id is None:
            if closed:
                raise ValueError(f'line {number}: # <<< {closed.group(1)} has no opening # >>> {closed.group(1)}')
            if opened:
                indent, open_id, hint = opened.groups()
                todo = f'{open_id}: {hint}'
                out.append(f'{indent}# TODO {todo}\n{indent}raise NotImplementedError({json.dumps(todo)})\n')
            else:
                out.append(line)
        elif opened:
            raise ValueError(f'line {number}: {opened.group(2)} opens inside {open_id}; close {open_id} first')
        elif closed:
            if closed.group(1) != open_id:
                raise ValueError(f'line {number}: # <<< {closed.group(1)} closes {open_id}')
            open_id = None
    if open_id is not None:
        raise ValueError(f'{open_id} has no closing # <<< {open_id}')
    return ''.join(out)


def _files(folder: Path):
    for path in sorted(folder.rglob('*')):
        if path.is_file() and not SKIP & set(path.relative_to(folder).parts):
            yield path


def build_tree(src: Path) -> dict[str, bytes]:
    """{relative path: bytes} of the whole project: README.md, data/, solution/, starter/, tests/."""
    src = Path(src)
    for need in ('README.md', 'solution', 'tests'):
        if not (src / need).exists():
            raise ValueError(f'{src}: capstone needs {need}')
    tree = {'README.md': (src / 'README.md').read_bytes()}
    for part in ('data', 'solution', 'tests'):
        if (src / part).is_dir():
            for path in _files(src / part):
                tree[f'{part}/{path.relative_to(src / part).as_posix()}'] = path.read_bytes()
    for path in _files(src / 'solution'):
        rel = path.relative_to(src / 'solution').as_posix()
        data = path.read_bytes()
        if path.suffix == '.py':
            try:
                data = make_starter(data.decode('utf-8')).encode('utf-8')
            except ValueError as exc:
                raise ValueError(f'solution/{rel}: {exc}') from None
        tree[f'starter/{rel}'] = data
    return tree


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    try:
        tree = build_tree(Path(args.src))
    except (OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    for rel, data in tree.items():
        path = Path(args.out) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f'Built the capstone: {len(tree)} files')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
