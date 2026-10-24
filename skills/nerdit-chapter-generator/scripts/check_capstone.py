#!/usr/bin/env python3
"""Check a built capstone project (plan check i).

    python check_capstone.py --dir <capstone folder> [--python <interpreter>]
        [--course <course.json> --lesson <capstone lesson id>] [--manifest <files.manifest.json>]

Fails when:
- a milestone marked in solution/ (# >>> M<k>) has no tests/test_m<k>_*.py, or tests name a
  milestone the solution does not mark;
- a starter module does not import;
- any test file fails on the solution (pytest, warnings as errors);
- a milestone's or the final test file passes on the starter (it proves nothing);
- with --course/--lesson: a line of the page's run-line code is not in the solution;
- with --manifest: a data/ file is not built from the course world (decision 13);
- with --requirements: the solution imports a library that is not pinned, or that README.md
  does not name (new tools such as charts, images or utilities are welcome, explained).
The interpreter needs pytest (pin it in the course requirements). Exit 0 / 1 / 2 as usual.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from capstone import milestones
from check_python_outputs import python_parts

TIMEOUT = 300


def _pytest(python: str, root: Path, code_dir: str, test: Path) -> int:
    env = {**os.environ, 'PYTHONPATH': str(root / code_dir), 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    try:
        return subprocess.run([python, '-m', 'pytest', '-q', '-W', 'error', '-p', 'no:cacheprovider', str(test)],
                              cwd=root, env=env, capture_output=True, timeout=TIMEOUT).returncode
    except subprocess.TimeoutExpired:
        return -1


def check(root: Path, python: str = sys.executable) -> dict:
    root = Path(root)
    problems = []
    marked = []
    for path in sorted((root / 'solution').rglob('*.py')):
        marked += milestones(path.read_text(encoding='utf-8'))
    tests = {}
    for path in sorted((root / 'tests').glob('test_*.py')):
        m = re.match(r'test_(m\d+|final)_', path.name)
        if m:
            tests.setdefault(m.group(1).upper() if m.group(1) != 'final' else 'final', []).append(path)
    ids = sorted(set(marked), key=lambda s: int(s[1:]))
    problems += [f'{mid}: no tests (tests/test_{mid.lower()}_*.py)' for mid in ids if mid not in tests]
    problems += [f'{mid}: tests but no # >>> {mid} block in the solution' for mid in tests
                 if mid != 'final' and mid not in ids]
    if 'final' not in tests:
        problems.append('final: no tests (tests/test_final_*.py)')
    env = {**os.environ, 'PYTHONPATH': str(root / 'starter'), 'PYTHONDONTWRITEBYTECODE': '1'}
    for path in sorted((root / 'starter').glob('*.py')):
        imp = subprocess.run([python, '-W', 'error', '-c', f'import {path.stem}'], cwd=root, env=env,
                             capture_output=True, text=True)
        if imp.returncode != 0:
            last = [ln for ln in imp.stderr.splitlines() if ln.strip()]
            problems.append(f'starter/{path.name}: does not import ({last[-1] if last else imp.returncode})')
    order = ids + ['final']
    for mid in order:
        for test in tests.get(mid, []):
            on_solution = _pytest(python, root, 'solution', test)
            if on_solution != 0:
                problems.append(f'{mid}: tests/{test.name} fail on the solution (pytest exit {on_solution})')
            if _pytest(python, root, 'starter', test) == 0:
                problems.append(f'{mid}: tests/{test.name} pass on the starter, so they prove nothing')
    return {'milestones': [m for m in order if m in tests], 'problems': problems}


def page_code_problems(snippets: list[str], solution: Path) -> list[str]:
    lines = {ln.strip() for path in Path(solution).rglob('*.py')
             for ln in path.read_text(encoding='utf-8').splitlines()}
    return [f'page code line not in the solution: {ln.strip()!r}'
            for code in snippets for ln in code.splitlines()
            if ln.strip() and not ln.strip().startswith('#') and ln.strip() not in lines]


def library_problems(root: Path, requirements: str) -> list[str]:
    """Every library the solution imports is pinned, and the README names it (decision 13: the
    capstone may bring in new tools such as charts, images or utilities, explained for learners)."""
    from check_offline_outputs import PACKAGES, _imports, unpinned
    codes = [p.read_text(encoding='utf-8') for p in sorted((Path(root) / 'solution').rglob('*.py'))]
    local = {p.stem for p in (Path(root) / 'solution').rglob('*.py')}
    problems = [f'solution imports {label}, not pinned in the course requirements'
                for label in unpinned(codes, requirements) if label.split(' (')[0] not in local]
    readme = (Path(root) / 'README.md').read_text(encoding='utf-8').lower()
    packages = []
    for code in codes:
        for mod in _imports(code):
            if mod in sys.stdlib_module_names or mod in local or mod == '__future__':
                continue
            package = PACKAGES.get(mod, mod)
            if package not in packages:
                packages.append(package)
    problems += [f'README.md does not name {p}: say what this tool does in the project' for p in packages
                 if p.lower() not in readme]
    return problems


def data_problems(root: Path, manifest_rows: list[dict]) -> list[str]:
    world = {r['name'] for r in manifest_rows if 'world' in (r.get('source') or {})}
    return [f'data/{p.name}: not built from the course world (declare it with a world source)'
            for p in sorted((Path(root) / 'data').glob('*')) if p.is_file() and p.name not in world]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', required=True)
    ap.add_argument('--python', default=sys.executable)
    ap.add_argument('--course')
    ap.add_argument('--lesson')
    ap.add_argument('--manifest')
    ap.add_argument('--requirements', help='the course requirements.txt (the pack root copy)')
    args = ap.parse_args(argv)
    try:
        report = check(Path(args.dir), args.python)
        if args.requirements:
            report['problems'] += library_problems(Path(args.dir),
                                                   Path(args.requirements).read_text(encoding='utf-8'))
        if args.course and args.lesson:
            lessons = json.loads(Path(args.course).read_text(encoding='utf-8'))['lessons']
            html = next(ls['content'] for ls in lessons if ls['id'] == args.lesson)
            report['problems'] += page_code_problems([r['code'] for r in python_parts(html)['runs']],
                                                     Path(args.dir) / 'solution')
        if args.manifest:
            rows = json.loads(Path(args.manifest).read_text(encoding='utf-8'))['files']
            report['problems'] += data_problems(Path(args.dir), rows)
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        print(f'ERROR: {exc!r}', file=sys.stderr)
        return 2
    for p in report['problems']:
        print(f'FAIL {p}')
    print(f'CAPSTONE: {len(report["milestones"])} milestones, {len(report["problems"])} problem(s)')
    return 1 if report['problems'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
