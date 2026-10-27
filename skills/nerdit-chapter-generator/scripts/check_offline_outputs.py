#!/usr/bin/env python3
"""Run a course's offline examples for real (plan check b).

    python check_offline_outputs.py --course <course_output.json> \
        [--requirements course-<chapter>_requirements.txt] [--pythons 3.14,3.12] [--workdir work/offline] \n        [--files-dir <pack out-dir>/files] [--capstone <workdir>/capstone]

Run lines marked data-run="offline" use libraries the browser cannot load (FastAPI, httpx2,
TensorFlow ...), so check_python_outputs.py only lists them. Here they run in one fresh venv
built from the course requirements, a lesson's blocks in page order in one namespace (like
notebook cells), with the lesson's dataset files in the working folder and all warnings as
errors. Each must print what the lesson shows (a shown error must contain Python's last line).
--files-dir puts each chapter's built practice files (L<nn>-...) beside its examples; --capstone
makes the project's solution/ modules importable on the capstone page, and not libraries to pin.

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
# One stdout for every example, like a script: a logging handler made in one example keeps
# sys.stdout, so what it prints later lands in the later example's output.
DRIVER = '''import io, json, sys
class Out:
    def __init__(self):
        self.buf = io.StringIO()
    def write(self, text):
        return self.buf.write(text)
    def flush(self):
        pass
blocks = json.load(open(sys.argv[1], encoding="utf-8"))
scope = {"__name__": "__main__"}
results = []
proxy = Out()
for code in blocks:
    out, error = io.StringIO(), None
    proxy.buf, sys.stdout = out, proxy
    try:
        exec(compile(code, "<example>", "exec"), scope)
    except BaseException as exc:  # SystemExit and warnings-as-errors included
        error = f"{type(exc).__name__}: {exc}"
    results.append({"stdout": out.getvalue(), "error": error})
sys.stdout = sys.__stdout__
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


def unpinned(codes: list[str], requirements: str, local: frozenset = frozenset()) -> list[str]:
    pinned, missing = pinned_names(requirements), []
    for code in codes:
        for mod in _imports(code):
            if mod in sys.stdlib_module_names or mod == '__future__' or mod in local:
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


def is_capstone(html: str) -> bool:
    """The capstone chapter declares its project in the files spec."""
    m = re.search(r'class="nerdit-files-spec"[^>]*>(.*?)</script>', html, re.S)
    try:
        return bool(m) and any('capstone' in e for e in json.loads(m.group(1)).get('files', []))
    except (ValueError, AttributeError):
        return False


def local_modules(capstone: Path | None) -> frozenset:
    """The capstone project's own modules: the page imports them from solution/."""
    if capstone is None or not (Path(capstone) / 'solution').is_dir():
        return frozenset()
    sol = Path(capstone) / 'solution'
    return frozenset([p.stem for p in sol.glob('*.py')] + [p.name for p in sol.iterdir() if (p / '__init__.py').is_file()])


def _run_lesson(vpy: Path, lesson: dict, workdir: Path, files: list[Path] = (),
                pythonpath: Path | None = None) -> list[str]:
    parts = python_parts(lesson.get('content', ''))
    numbered = [(i, r) for i, r in enumerate(parts['runs'], 1) if r['offline']]
    folder = workdir / lesson['id']
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for name, text in (build_files(parts['dataset']) if parts['dataset'] else {}).items():
        (folder / name).write_text(text, encoding='utf-8', newline='')
    for path in files:
        shutil.copy(path, folder / path.name)
    (folder / '_blocks.json').write_text(json.dumps([r['code'] for _, r in numbered]), encoding='utf-8')
    (workdir / '_driver.py').write_text(DRIVER, encoding='utf-8')
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    if pythonpath is not None:
        env['PYTHONPATH'] = str(Path(pythonpath).resolve())
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


def lesson_files(files_dir: Path | None, position: int) -> list[Path]:
    """The built pack's data files for chapter `position` (L<nn>-...), not its starter or solutions."""
    if files_dir is None:
        return []
    return sorted(p for p in Path(files_dir).glob(f'L{position:02d}-*')
                  if p.is_file() and '-solutions.' not in p.name and '-practice-starter.' not in p.name)


def check_course(course: Path, requirements: str, pythons: list[str], workdir: Path,
                 files_dir: Path | None = None, capstone: Path | None = None) -> dict:
    workdir = Path(workdir).resolve()   # the driver runs with cwd=<lesson folder>, so paths must be absolute
    every = json.loads(Path(course).read_text(encoding='utf-8'))['lessons']
    lessons = [(pos, ls) for pos, ls in enumerate(every, 1) if offline_blocks(ls.get('content', ''))]
    report = {'python': None, 'examples': sum(len(offline_blocks(ls['content'])) for _, ls in lessons),
              'problems': [], 'tried': {}}
    local = local_modules(capstone)
    project = {ls['id'] for _, ls in lessons if is_capstone(ls['content'])}
    for _, ls in lessons:
        mine = local if ls['id'] in project else frozenset()
        report['problems'] += [f'{ls["id"]}: {m} is used but not pinned in the course requirements'
                               for m in unpinned([b['code'] for b in offline_blocks(ls['content'])], requirements, mine)]
    if report['problems'] or not lessons:
        return report
    for n, spec in enumerate(pythons):
        exe = resolve_python(spec)
        if exe is None:
            report['tried'][spec] = [f'Python {spec} is not installed']
            continue
        vpy, err = _venv(exe, Path(workdir) / f'venv-{n}', requirements)
        problems = [err] if err else [
            p for pos, ls in lessons for p in _run_lesson(
                vpy, ls, Path(workdir) / 'lessons', lesson_files(files_dir, pos),
                Path(capstone) / 'solution' if capstone and ls['id'] in project else None)]
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
    ap.add_argument('--files-dir', help="practice_files.py's <out-dir>/files: each chapter's data files sit "
                                        'beside its examples')
    ap.add_argument('--capstone', help='the capstone project folder: its solution/ modules are importable')
    args = ap.parse_args(argv)
    try:
        reqs = Path(args.requirements).read_text(encoding='utf-8') if args.requirements else ''
        report = check_course(Path(args.course), reqs, args.pythons.split(','), Path(args.workdir),
                              Path(args.files_dir) if args.files_dir else None,
                              Path(args.capstone) if args.capstone else None)
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
