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
- the tests run under 80% of the solution's lines (the __main__ block aside);
- a milestone's tests (with the final tests) catch under 80% of the small bugs planted one at a
  time in its block (+ -> -, < -> <=, 0 -> 1, return -> return None ...); survivors are listed.
  --quick skips this for drafts; a final run never uses it;
- with --course/--lesson: a line of the page's run-line code is not in the solution;
- with --manifest: a data/ file is not built from the course world (decision 13);
- with --requirements: the solution imports a library that is not pinned, or that README.md
  does not name (new tools such as charts, images or utilities are welcome, explained).
The interpreter needs pytest (pin it in the course requirements). Exit 0 / 1 / 2 as usual.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types

from capstone import milestones
from check_python_outputs import python_parts

TIMEOUT = 300
MIN_COVERAGE = 80   # % of the solution's executable lines the tests must run
MIN_KILLED = 80     # % of a milestone's planted bugs its tests must catch
MAX_MUTANTS = 12    # per milestone, spread over its block

COVERAGE_RUNNER = '''import json, os, sys, threading
root = os.path.normcase(os.path.realpath(sys.argv[1]))
hits = set()
def local(frame, event, arg):
    if event == "line":
        hits.add((frame.f_code.co_filename, frame.f_lineno))
    return local
def outer(frame, event, arg):
    if os.path.normcase(os.path.realpath(frame.f_code.co_filename)).startswith(root):
        hits.add((frame.f_code.co_filename, frame.f_lineno))
        return local
    return None
sys.settrace(outer)
threading.settrace(outer)
import pytest
rc = pytest.main(["-q", "-p", "no:cacheprovider", *sys.argv[3:]])
sys.settrace(None)
json.dump({"rc": int(rc), "hits": [[os.path.normcase(os.path.realpath(f)), n] for f, n in hits]},
          open(sys.argv[2], "w"))
'''


def _pytest(python: str, root: Path, code_dir: str | Path, test: Path | list) -> int:
    tests = [str(t) for t in (test if isinstance(test, list) else [test])]
    env = {**os.environ, 'PYTHONPATH': str(Path(root) / code_dir), 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    try:
        return subprocess.run([python, '-m', 'pytest', '-q', '-W', 'error', '-p', 'no:cacheprovider', *tests],
                              cwd=root, env=env, capture_output=True, timeout=TIMEOUT).returncode
    except subprocess.TimeoutExpired:
        return -1


def _main_block_lines(tree: ast.Module) -> set[int]:
    lines = set()
    for node in tree.body:
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__'):
            lines |= set(range(node.lineno, node.end_lineno + 1))
    return lines


def executable_lines(path: Path) -> set[int]:
    """Lines Python can run, without the `if __name__ == "__main__":` block (run by check_files)."""
    source = Path(path).read_text(encoding='utf-8')
    stack, lines = [compile(source, str(path), 'exec')], set()
    while stack:
        code = stack.pop()
        lines |= {line for _, _, line in code.co_lines() if line}
        stack += [c for c in code.co_consts if isinstance(c, types.CodeType)]
    return lines - _main_block_lines(ast.parse(source))


def _ranges(numbers: list[int]) -> str:
    out, start = [], None
    for n in sorted(numbers) + [None]:
        if start is None:
            start = prev = n
        elif n is not None and n == prev + 1:
            prev = n
        else:
            out.append(f'{start}' if start == prev else f'{start}-{prev}')
            start = prev = n
    return ', '.join(out)


def coverage(root: Path, python: str = sys.executable) -> tuple[int, list[str]]:
    """(% of the solution's executable lines the whole test suite runs, ['report.py lines 27-30'])."""
    root = Path(root)
    solution = root / 'solution'
    with tempfile.TemporaryDirectory() as tmp:
        runner, result = Path(tmp) / 'cover.py', Path(tmp) / 'hits.json'
        runner.write_text(COVERAGE_RUNNER, encoding='utf-8')
        env = {**os.environ, 'PYTHONPATH': str(solution), 'PYTHONDONTWRITEBYTECODE': '1',
               'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
        tests = [str(p) for p in sorted((root / 'tests').glob('test_*.py'))]
        subprocess.run([python, str(runner), str(solution), str(result), *tests], cwd=root, env=env,
                       capture_output=True, timeout=TIMEOUT)
        hits = json.loads(result.read_text(encoding='utf-8'))['hits'] if result.exists() else []
    ran: dict[str, set[int]] = {}
    for name, line in hits:
        ran.setdefault(name, set()).add(line)
    total = covered = 0
    missed = []
    for path in sorted(solution.rglob('*.py')):
        lines = executable_lines(path)
        done = lines & ran.get(os.path.normcase(os.path.realpath(path)), set())
        total, covered = total + len(lines), covered + len(done)
        if lines - done:
            missed.append(f'{path.relative_to(solution).as_posix()} lines {_ranges(list(lines - done))}')
    return (100 if not total else covered * 100 // total), missed


# Planted bugs: one small change at a time, only inside a milestone's marked block.
OPS = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult, ast.FloorDiv: ast.Mult,
       ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq,
       ast.NotEq: ast.Eq, ast.In: ast.NotIn, ast.NotIn: ast.In, ast.And: ast.Or, ast.Or: ast.And}
SYMBOL = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/', ast.FloorDiv: '//', ast.Lt: '<',
          ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>=', ast.Eq: '==', ast.NotEq: '!=', ast.In: 'in',
          ast.NotIn: 'not in', ast.And: 'and', ast.Or: 'or'}


def _block_lines(source: str) -> dict[int, str]:
    """{line number: milestone} for every line strictly inside a # >>> / # <<< block."""
    inside, current = {}, None
    for number, line in enumerate(source.splitlines(), 1):
        opened, closed = re.match(r'^\s*# >>> (M\d+):', line), re.match(r'^\s*# <<< (M\d+)', line)
        if opened:
            current = opened.group(1)
        elif closed:
            current = None
        elif current:
            inside[number] = current
    return inside


def _changes(node) -> list[tuple[str, callable]]:
    found = []
    if isinstance(node, (ast.BinOp, ast.BoolOp)) and type(node.op) in OPS:
        new = OPS[type(node.op)]
        found.append((f'{SYMBOL[type(node.op)]} -> {SYMBOL[new]}', lambda n, new=new: setattr(n, 'op', new())))
    elif isinstance(node, ast.Compare) and type(node.ops[0]) in OPS:
        new = OPS[type(node.ops[0])]
        found.append((f'{SYMBOL[type(node.ops[0])]} -> {SYMBOL[new]}',
                      lambda n, new=new: n.ops.__setitem__(0, new())))
    elif isinstance(node, ast.Constant) and type(node.value) in (int, float):
        found.append((f'{node.value!r} -> {node.value + 1!r}', lambda n: setattr(n, 'value', n.value + 1)))
    elif isinstance(node, ast.Constant) and type(node.value) is bool:
        found.append((f'{node.value} -> {not node.value}', lambda n: setattr(n, 'value', not n.value)))
    elif isinstance(node, ast.Return) and node.value is not None and not (
            isinstance(node.value, ast.Constant) and node.value.value is None):
        found.append(('return -> return None', lambda n: setattr(n, 'value', ast.Constant(None))))
    return found


def mutants(source: str) -> list[dict]:
    """[{milestone, line, change, source}] — each a copy of the module with one planted bug."""
    inside = _block_lines(source)
    out = []
    for index, node in enumerate(ast.walk(ast.parse(source))):
        milestone = inside.get(getattr(node, 'lineno', 0))
        if not milestone:
            continue
        for k, (label, apply) in enumerate(_changes(node)):
            tree = ast.parse(source)
            target = list(ast.walk(tree))[index]
            _changes(target)[k][1](target)
            out.append({'milestone': milestone, 'line': node.lineno, 'change': label,
                        'source': ast.unparse(ast.fix_missing_locations(tree)) + '\n'})
    by_milestone: dict[str, list[dict]] = {}
    for m in out:
        by_milestone.setdefault(m['milestone'], []).append(m)
    kept = []
    for items in by_milestone.values():
        step = max(1, -(-len(items) // MAX_MUTANTS))
        kept += items[::step][:MAX_MUTANTS]
    return kept


def mutation(root: Path, python: str = sys.executable) -> dict:
    """{'score': {milestone: (caught, planted)}, 'problems'} — each milestone's tests plus the final
    tests must catch at least MIN_KILLED % of the bugs planted in its block."""
    root = Path(root)
    tests = {}
    for path in sorted((root / 'tests').glob('test_*.py')):
        m = re.match(r'test_(m\d+|final)_', path.name)
        if m:
            tests.setdefault(m.group(1).upper() if m.group(1) != 'final' else 'final', []).append(path)
    score, survivors = {}, {}
    work = root / '.mutants'
    try:
        for path in sorted((root / 'solution').rglob('*.py')):
            rel = path.relative_to(root / 'solution')
            for mutant in mutants(path.read_text(encoding='utf-8')):
                mid = mutant['milestone']
                shutil.rmtree(work, ignore_errors=True)
                shutil.copytree(root / 'solution', work / 'solution')
                if (root / 'data').is_dir():
                    shutil.copytree(root / 'data', work / 'data')
                (work / 'solution' / rel).write_text(mutant['source'], encoding='utf-8')
                caught = _pytest(python, root, work / 'solution', tests.get(mid, []) + tests.get('final', [])) != 0
                done, total = score.get(mid, (0, 0))
                score[mid] = (done + caught, total + 1)
                if not caught:
                    survivors.setdefault(mid, []).append(f'{rel.as_posix()} line {mutant["line"]} {mutant["change"]}')
    finally:
        shutil.rmtree(work, ignore_errors=True)
    problems = []
    for mid, (caught, total) in score.items():
        if caught * 100 < MIN_KILLED * total:
            problems.append(f'{mid}: {total - caught} of {total} planted bugs survive the tests (they must catch '
                            f'{MIN_KILLED}%): ' + '; '.join(survivors[mid]))
    return {'score': score, 'problems': problems}


def check(root: Path, python: str = sys.executable, mutate: bool = True) -> dict:
    root = Path(root).resolve()   # pytest runs with cwd=root, so test paths must be absolute
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
    if not problems:  # strict accuracy: the tests must run the solution and catch planted bugs
        pct, missed = coverage(root, python)
        if pct < MIN_COVERAGE:
            problems.append(f'coverage: the tests run {pct}% of the solution lines (at least {MIN_COVERAGE}%); '
                            f'never runs: ' + '; '.join(missed))
        if mutate:
            problems += mutation(root, python)['problems']
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
    ap.add_argument('--quick', action='store_true', help='skip the mutation run (drafts only, never a final pass)')
    args = ap.parse_args(argv)
    try:
        report = check(Path(args.dir), args.python, mutate=not args.quick)
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
