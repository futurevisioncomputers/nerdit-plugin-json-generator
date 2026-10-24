#!/usr/bin/env python3
"""Run a course's offline examples for real (plan check b).

    python check_offline_outputs.py --course <course_output.json> \
        [--requirements course-<chapter>_requirements.txt] [--pythons 3.14,3.12] [--workdir work/offline]

Run lines marked data-run="offline" use libraries the browser cannot load (FastAPI, httpx2,
TensorFlow ...), so check_python_outputs.py only lists them. Here they run in one fresh venv
built from the course requirements, a lesson's blocks in page order in one namespace (like
notebook cells), with the lesson's dataset files in the working folder and all warnings as
errors. Each must print what the lesson shows (a shown error must contain Python's last line).

Every library an offline block imports must be pinned in the requirements; that is checked
first, without running anything. --pythons are tried in order (decision 7).
Full apps (L<nn>-full-app.py) are run by check_files.py --as-learner.

Exit 0 = every offline output matches; 1 = a problem; 2 = no listed Python installed or an
unreadable file.
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

from check_files import _last_line, _version, resolve_python
from check_python_outputs import _short, build_files, normalise, python_parts

TIMEOUT = 300
# Import name -> the package a learner installs, where they differ.
PACKAGES = {'sklearn': 'scikit-learn', 'cv2': 'opencv-python', 'PIL': 'pillow', 'yaml': 'pyyaml',
            'bs4': 'beautifulsoup4', 'dotenv': 'python-dotenv', 'google': 'google-genai',
            'jwt': 'pyjwt', 'dateutil': 'python-dateutil', 'multipart': 'python-multipart'}
DRIVER = '''import contextlib, io, json, sys
blocks = json.load(open(sys.argv[1], encoding="utf-8"))
scope = {"__name__": "__main__"}
results = []
for code in blocks:
    out, error = io.StringIO(), None
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(code, "<example>", "exec"), scope)
    except BaseException as exc:  # SystemExit and warnings-as-errors included
        error = f"{type(exc).__name__}: {exc}"
    results.append({"stdout": out.getvalue(), "error": error})
json.dump(results, open(sys.argv[2], "w", encoding="utf-8"))
'''


def offline_blocks(html: str) -> list[dict]:
    """The lesson's offline run lines, in page order, with their page example numbers."""
    return [{'code': r['code'], 'shown': r['shown']} for r in python_parts(html)['runs'] if r['offline']]


def _norm(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def pinned_names(requirements: str) -> set[str]:
    names = set()
    for line in requirements.splitlines():
        line = line.split('#', 1)[0].strip()
        m = re.match(r'[A-Za-z0-9][A-Za-z0-9._-]*', line) if line and not line.startswith('-') else None
        if m:
            names.add(_norm(m.group(0)))
    return names


def _imports(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return re.findall(r'^\s*(?:import|from)\s+([A-Za-z_]\w*)', code, re.M)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name.split('.')[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.append(node.module.split('.')[0])
    return names


def unpinned(codes: list[str], requirements: str) -> list[str]:
    pinned, missing = pinned_names(requirements), []
    for code in codes:
        for mod in _imports(code):
            if mod in sys.stdlib_module_names or mod == '__future__':
                continue
            package = PACKAGES.get(mod, mod)
            label = package if package == mod else f'{package} (import {mod})'
            if _norm(package) not in pinned and label not in missing:
                missing.append(label)
    return missing


def _venv(python: str, venv_dir: Path, requirements: str) -> tuple[Path | None, str | None]:
    needs_pip = bool(pinned_names(requirements))
    shutil.rmtree(venv_dir, ignore_errors=True)
    made = subprocess.run([python, '-m', 'venv'] + ([] if needs_pip else ['--without-pip']) + [str(venv_dir)],
                          capture_output=True, text=True)
    if made.returncode != 0:
        return None, f'venv: {_last_line(made)}'
    vpy = venv_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if needs_pip:
        req = venv_dir.parent / 'requirements.txt'
        req.write_text(requirements, encoding='utf-8')
        inst = subprocess.run([str(vpy), '-m', 'pip', 'install', '-q', '-r', str(req)], capture_output=True, text=True)
        if inst.returncode != 0:
            return None, f'requirements: pip install failed ({_last_line(inst)})'
    return vpy, None


def _run_lesson(vpy: Path, lesson: dict, workdir: Path) -> list[str]:
    parts = python_parts(lesson.get('content', ''))
    numbered = [(i, r) for i, r in enumerate(parts['runs'], 1) if r['offline']]
    folder = workdir / lesson['id']
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for name, text in (build_files(parts['dataset']) if parts['dataset'] else {}).items():
        (folder / name).write_text(text, encoding='utf-8', newline='')
    (folder / '_blocks.json').write_text(json.dumps([r['code'] for _, r in numbered]), encoding='utf-8')
    (workdir / '_driver.py').write_text(DRIVER, encoding='utf-8')
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    lid = lesson['id']
    try:
        proc = subprocess.run([str(vpy), '-W', 'error', str(workdir / '_driver.py'), '_blocks.json', '_results.json'],
                              cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace',
                              timeout=TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        return [f'{lid}: offline examples still running after {TIMEOUT} s']
    if proc.returncode != 0 or not (folder / '_results.json').exists():
        return [f'{lid}: offline examples could not run ({_last_line(proc)})']
    results = json.loads((folder / '_results.json').read_text(encoding='utf-8'))
    problems = []
    for (i, run), got in zip(numbered, results):
        shown = run['shown']
        if got['error'] is not None:
            if shown is None or got['error'] not in normalise(shown):
                problems.append(f"{lid}: example {i}: Python raises '{got['error']}', which the lesson does not show")
        elif shown is not None and normalise(got['stdout']) != normalise(shown):
            problems.append(f"{lid}: example {i}: shown {_short(shown)!r} but Python prints {_short(got['stdout'])!r}")
    return problems


def check_course(course: Path, requirements: str, pythons: list[str], workdir: Path) -> dict:
    lessons = [ls for ls in json.loads(Path(course).read_text(encoding='utf-8'))['lessons']
               if offline_blocks(ls.get('content', ''))]
    report = {'python': None, 'examples': sum(len(offline_blocks(ls['content'])) for ls in lessons),
              'problems': [], 'tried': {}}
    for ls in lessons:
        report['problems'] += [f'{ls["id"]}: {m} is used but not pinned in the course requirements'
                               for m in unpinned([b['code'] for b in offline_blocks(ls['content'])], requirements)]
    if report['problems'] or not lessons:
        return report
    for n, spec in enumerate(pythons):
        exe = resolve_python(spec)
        if exe is None:
            report['tried'][spec] = [f'Python {spec} is not installed']
            continue
        vpy, err = _venv(exe, Path(workdir) / f'venv-{n}', requirements)
        problems = [err] if err else [p for ls in lessons for p in _run_lesson(vpy, ls, Path(workdir) / 'lessons')]
        report['tried'][spec] = problems
        if not problems:
            report['python'] = spec if re.fullmatch(r'\d+\.\d+', spec) else _version(exe)
            return report
    last = [ps for ps in report['tried'].values() if not (len(ps) == 1 and ps[0].endswith('not installed'))]
    report['problems'] = last[-1] if last else []
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--course', required=True)
    ap.add_argument('--requirements')
    ap.add_argument('--pythons', default='3.14,3.12')
    ap.add_argument('--workdir', default='offline-check')
    args = ap.parse_args(argv)
    try:
        reqs = Path(args.requirements).read_text(encoding='utf-8') if args.requirements else ''
        report = check_course(Path(args.course), reqs, args.pythons.split(','), Path(args.workdir))
    except (OSError, ValueError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    for spec, ps in report['tried'].items():
        print(f'Python {spec}: ' + ('pass' if not ps else f'{len(ps)} problem(s)'))
    for p in report['problems']:
        print(f'FAIL {p}')
    if report['examples'] == 0:
        print('No offline examples')
        return 0
    if report['python']:
        print(f'{report["examples"]} offline examples match on Python {report["python"]}')
        return 0
    if not report['problems'] and report['tried']:
        return 2  # no listed Python is installed: never a pass
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
