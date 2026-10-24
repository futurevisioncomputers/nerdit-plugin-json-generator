#!/usr/bin/env python3
"""Check a built practice pack the way a learner would use it (plan checks d and h).

    python check_files.py --out-dir <practice_files.py out-dir> [--course <marked course JSON>]
    python check_files.py --out-dir work --as-learner [--pythons 3.14,3.12]

Static (always): every manifest file exists, matches its sha256 and its copy in the pack;
names follow the tracing rule; sizes within the limits; every file parses (.py compiles,
.json/.jsonl/.ipynb load, .csv reads, .sql runs in SQLite); with --course, every files/ link
has a file and every file is linked.

--as-learner: unzip the pack into an empty folder, make one fresh venv, pip install
requirements.txt, then run every .py (from the pack root and from its own folder), every
notebook's code in its folder, and every .sql in SQLite, with all warnings as errors.
--pythons are tried in order; the first that passes everything is reported (decision 7:
3.14 when the code runs unchanged, otherwise 3.12).

Exit 0 = pass; 1 = a problem; 2 = no listed Python installed or an unreadable out-dir.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

import practice_files as pf

TIMEOUT = 120
LINK = re.compile(r'href="files/([^"]+)"')


def _pack(out_dir: Path) -> tuple[dict, Path]:
    manifest = json.loads((out_dir / 'files.manifest.json').read_text(encoding='utf-8'))
    return manifest, out_dir / manifest['pack']


def _parse_problem(name: str, data: bytes) -> str | None:
    ext = name.rpartition('.')[2]
    try:
        text = data.decode('utf-8')
        if ext == 'py':
            ast.parse(text, filename=name)
        elif ext == 'json':
            json.loads(text)
        elif ext == 'jsonl':
            for line in text.splitlines():
                if line.strip():
                    json.loads(line)
        elif ext == 'ipynb':
            nb = json.loads(text)
            if nb.get('nbformat') != 4 or not isinstance(nb.get('cells'), list):
                return f'{name}: not an nbformat 4 notebook'
        elif ext == 'csv':
            rows = list(csv.reader(io.StringIO(text, newline='')))
            if not rows:
                return f'{name}: empty CSV'
        elif ext == 'sql':
            sqlite3.connect(':memory:').executescript(text)
    except (UnicodeDecodeError, SyntaxError, ValueError, sqlite3.Error) as exc:
        return f'{name}: does not parse ({type(exc).__name__}: {exc})'
    return None


def static_problems(out_dir: Path, course: Path | None = None) -> list[str]:
    out_dir = Path(out_dir)
    manifest, zpath = _pack(out_dir)
    problems = []
    if not zpath.is_file():
        return [f'{zpath.name}: the pack is missing']
    if zpath.stat().st_size > pf.PACK_LIMIT:
        problems.append(f'{zpath.name}: {zpath.stat().st_size} bytes, over the pack limit')
    with zipfile.ZipFile(zpath) as z:
        in_pack = {Path(n).name: z.read(n) for n in z.namelist() if not n.endswith('/')}
        problems += [f'{n}: {len(n)} characters, too long for Windows (at most {pf.MAX_PACK_PATH} inside the pack)'
                     for n in z.namelist() if len(n) > pf.MAX_PACK_PATH]
    for row in manifest['files']:
        name = row['name']
        position = int(row['folder'][1:3]) if re.match(r'L\d{2}-', row.get('folder', '')) else 0
        problems += pf.name_problems(name, position)
        single = out_dir / 'files' / name
        if not single.is_file():
            problems.append(f'{name}: single file missing from files/')
            continue
        data = single.read_bytes()
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            problems.append(f'{name}: sha256 differs from the manifest')
        if name not in in_pack:
            problems.append(f'{name}: not in the pack')
        elif in_pack[name] != data:
            problems.append(f'{name}: single file differs from the pack')
        if len(data) > pf.FILE_LIMIT:
            problems.append(f'{name}: {len(data)} bytes, over the file limit')
        bad = _parse_problem(name, in_pack.get(name, data))
        if bad:
            problems.append(bad)
    if course is not None:
        lessons = json.loads(Path(course).read_text(encoding='utf-8'))['lessons']
        linked = {m for les in lessons for m in LINK.findall(les.get('content', ''))}
        known = {row['name'] for row in manifest['files']} | {manifest['pack']}
        problems += [f'files/{n}: link to no such file' for n in sorted(linked - known)]
        problems += [f'{n}: not linked from any lesson' for n in sorted(known - linked)]
    return problems


def resolve_python(spec: str) -> str | None:
    """An interpreter path for '3.14'-style versions (py launcher or pythonX.Y), or the path itself."""
    if not re.fullmatch(r'\d+\.\d+', spec):
        return spec if Path(spec).exists() else None
    for cmd in (['py', f'-{spec}'], [f'python{spec}']):
        if shutil.which(cmd[0]) is None:
            continue
        try:
            out = subprocess.run(cmd + ['-c', 'import sys; print(sys.executable)'], capture_output=True,
                                 text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    return None


def _version(exe: str) -> str:
    out = subprocess.run([exe, '-c', 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")'],
                         capture_output=True, text=True, timeout=30)
    return out.stdout.strip()


def _last_line(proc) -> str:
    lines = [ln for ln in (proc.stderr or '').splitlines() if ln.strip()]
    return lines[-1].strip() if lines else f'exit code {proc.returncode}'


def _capstone_starter_or_test(path: Path, pack_root: Path) -> bool:
    for parent in path.parents:
        if parent == pack_root:
            return False
        if parent.name in ('starter', 'tests') and (parent.parent / 'solution').is_dir():
            return True
    return False


def _run_with(pack_root: Path, python: str, venv_dir: Path, requirements: str) -> tuple[list[str], list[str]]:
    """Problems and a log of what ran, in one fresh venv of `python`."""
    needs_pip = any(ln.strip() and not ln.lstrip().startswith('#') for ln in requirements.splitlines())
    shutil.rmtree(venv_dir, ignore_errors=True)
    made = subprocess.run([python, '-m', 'venv'] + ([] if needs_pip else ['--without-pip']) + [str(venv_dir)],
                          capture_output=True, text=True)
    if made.returncode != 0:
        return [f'venv: {_last_line(made)}'], []
    vpy = venv_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if needs_pip:
        inst = subprocess.run([str(vpy), '-m', 'pip', 'install', '-q', '-r', str(pack_root / 'requirements.txt')],
                              capture_output=True, text=True)
        if inst.returncode != 0:
            return [f'requirements.txt: pip install failed ({_last_line(inst)})'], []
    problems, ran = [], []
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}

    def run(label: str, args: list[str], cwd: Path):
        try:
            proc = subprocess.run([str(vpy), '-W', 'error'] + args, cwd=cwd, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=TIMEOUT, env=env)
        except subprocess.TimeoutExpired:
            problems.append(f'{label}: still running after {TIMEOUT} s')
            return
        except OSError as exc:   # WinError 267: Windows cannot use a working folder past 260 characters
            problems.append(f'{label}: path too long or not usable ({len(str(cwd))} characters: {exc})')
            return
        ran.append(label)
        if proc.returncode != 0:
            problems.append(f'{label}: {_last_line(proc)}')

    for path in sorted(pack_root.rglob('*')):
        rel = path.relative_to(pack_root).as_posix()
        if path.suffix == '.py' and _capstone_starter_or_test(path, pack_root):
            continue  # check_capstone.py runs these: the starter is meant to fail its tests
        if path.suffix == '.py':
            run(f'{rel} (from the pack root)', [rel], pack_root)
            run(f'{rel} (from its own folder)', [path.name], path.parent)
        elif path.suffix == '.ipynb':
            nb = json.loads(path.read_text(encoding='utf-8'))
            code = '\n'.join(''.join(c.get('source', [])) for c in nb['cells'] if c.get('cell_type') == 'code')
            run(f'{rel} (cells in order, in its folder)', ['-c', code], path.parent)
        elif path.suffix == '.sql':
            try:
                sqlite3.connect(':memory:').executescript(path.read_text(encoding='utf-8'))
                ran.append(f'{rel} (SQLite)')
            except sqlite3.Error as exc:
                problems.append(f'{rel}: SQLite {exc}')
    return problems, ran


def default_workdir(out_dir: Path) -> Path:
    """<out-dir>/learner, except on Windows: a short folder in the system temp, so a deep out-dir
    does not push the unzipped chapter folders past the 260-character limit."""
    if sys.platform == 'win32':
        return Path(tempfile.mkdtemp(prefix='nerdit-learner-'))
    return Path(out_dir) / 'learner'


def run_as_learner(out_dir: Path, pythons: list[str], workdir: Path) -> dict:
    """{'python': the first version that passed or None, 'problems', 'ran', 'tried': {python: problems}}."""
    manifest, zpath = _pack(Path(out_dir))
    unzipped = Path(workdir) / 'unzipped'
    shutil.rmtree(unzipped, ignore_errors=True)
    unzipped.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(unzipped)
    pack_root = unzipped / zpath.stem
    requirements = (pack_root / 'requirements.txt').read_text(encoding='utf-8')
    tried, last = {}, ([], [])
    for i, spec in enumerate(pythons):
        exe = resolve_python(spec)
        if exe is None:
            tried[spec] = [f'Python {spec} is not installed']
            continue
        problems, ran = _run_with(pack_root, exe, Path(workdir) / f'venv-{i}', requirements)
        tried[spec] = problems
        last = (problems, ran)
        if not problems:
            label = spec if re.fullmatch(r'\d+\.\d+', spec) else _version(exe)
            return {'python': label, 'problems': [], 'ran': ran, 'tried': tried}
    problems = last[0] or [p for ps in tried.values() for p in ps]
    return {'python': None, 'problems': problems, 'ran': last[1], 'tried': tried}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--course', help='the marked course JSON practice_files.py wrote')
    ap.add_argument('--as-learner', action='store_true')
    ap.add_argument('--pythons', default='3.14,3.12')
    ap.add_argument('--workdir', help='where to unzip and make venvs (default <out-dir>/learner; '
                                      'on Windows a short folder in the system temp)')
    args = ap.parse_args(argv)
    out = Path(args.out_dir)
    try:
        problems = static_problems(out, Path(args.course) if args.course else None)
        report = None
        if args.as_learner and not problems:
            report = run_as_learner(out, args.pythons.split(','), Path(args.workdir) if args.workdir else default_workdir(out))
    except (OSError, ValueError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    for p in problems:
        print(f'FAIL {p}')
    if report is not None:
        for spec, ps in report['tried'].items():
            print(f'Python {spec}: ' + ('pass' if not ps else f'{len(ps)} problem(s)'))
            for p in ps:
                print(f'  FAIL {p}')
        if report['python']:
            print(f'Learner run passed on Python {report["python"]} ({len(report["ran"])} runs)')
        elif all(ps and ps[0].endswith('is not installed') for ps in report['tried'].values()):
            return 2
    failed = bool(problems) or (report is not None and report['python'] is None)
    if not failed:
        print('Practice files OK')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
