import json
import sys
import zipfile

import pytest

import check_files as cf
import practice_files as pf

WORLD = {'enquiries': [{'enquiry_id': 'E1', 'course': 'Python', 'fee': 9000},
                       {'enquiry_id': 'E2', 'course': 'Excel', 'fee': 4000}]}

SPEC = {'python': '3.12', 'files': [
    {'name': 'L01-S1-enquiries.csv', 'sections': [1], 'about': '2 enquiries', 'from': {'world': 'enquiries'}},
    {'name': 'L01-S1-seed.sql', 'sections': [1], 'from': {'sql': 'seed-1'}},
    {'name': 'L01-practice-starter.py', 'sections': ['practice'], 'from': {'practice': 'starters'}},
    {'name': 'L01-practice-starter.ipynb', 'sections': ['practice'], 'from': {'practice': 'starters'}},
    {'name': 'L01-solutions.py', 'sections': 'all', 'from': {'solutions': 'all'}},
    {'name': 'L01-solutions.ipynb', 'sections': 'all', 'from': {'solutions': 'all'}},
]}


def page(solution='print(sum(int(r["fee"]) for r in rows))'):
    return (f'<section><h2>Overview</h2><p>Fees.</p>'
            f'<script type="application/json" class="nerdit-files-spec">{json.dumps(SPEC)}</script></section>'
            '<section><h2>1 — Read the file</h2>'
            '<div class="nerdit-run"><div class="nerdit-in"><pre data-lang="python"><code>import csv\n'
            'with open("L01-S1-enquiries.csv", newline="") as f:\n    rows = list(csv.DictReader(f))\n'
            'print(len(rows))</code></pre></div></div>'
            '<script type="text/plain" id="seed-1">CREATE TABLE t (a INT);\nINSERT INTO t VALUES (1);\n</script>'
            '</section><section><h2>Practice</h2><div class="nerdit-practical">'
            '<div class="nerdit-task">Task 1: Add up the fees.<details class="nerdit-solution">'
            f'<summary>Show solution</summary><pre data-lang="python"><code>{solution}</code></pre>'
            '</details></div></div></section>')


def build(tmp_path, html=None):
    chapters = [{'id': 'fees-01', 'title': 'Reading Fees', 'html': html or page()}]
    result = pf.build_pack(chapters, course_short='fees', version=1, world=WORLD, requirements='',
                           out_dir=tmp_path)
    marked = pf.mark_course(chapters, result, date='24 Oct 2026')
    course = {'lessons': [{'id': 'fees-01', 'title': 'Reading Fees', 'content': marked[0]}]}
    (tmp_path / 'course.json').write_text(json.dumps(course), encoding='utf-8')
    return tmp_path


def test_static_checks_pass_on_a_fresh_build(tmp_path):
    out = build(tmp_path)
    assert cf.static_problems(out, course=out / 'course.json') == []


def test_single_file_differing_from_the_pack_fails(tmp_path):
    out = build(tmp_path)
    (out / 'files' / 'L01-S1-enquiries.csv').write_bytes(b'tampered\n')
    assert any('differs from the pack' in p for p in cf.static_problems(out))


def test_manifest_sha_mismatch_and_missing_file_fail(tmp_path):
    out = build(tmp_path)
    (out / 'files' / 'L01-S1-seed.sql').unlink()
    problems = cf.static_problems(out)
    assert any('L01-S1-seed.sql' in p and 'missing' in p for p in problems)


def test_links_must_resolve_and_every_file_be_linked(tmp_path):
    out = build(tmp_path)
    course = json.loads((out / 'course.json').read_text(encoding='utf-8'))
    html = course['lessons'][0]['content']
    html = html.replace('href="files/L01-S1-seed.sql"', 'href="files/L01-S1-gone.sql"')
    course['lessons'][0]['content'] = html
    (out / 'course.json').write_text(json.dumps(course), encoding='utf-8')
    problems = cf.static_problems(out, course=out / 'course.json')
    assert any('L01-S1-gone.sql' in p and 'no such file' in p for p in problems)
    assert any('L01-S1-seed.sql' in p and 'not linked' in p for p in problems)


def test_unparseable_files_fail(tmp_path):
    out = build(tmp_path)
    zpath = out / 'fees-practice-pack-v1.zip'
    with zipfile.ZipFile(zpath) as z:
        members = {n: z.read(n) for n in z.namelist()}
    bad = next(n for n in members if n.endswith('L01-solutions.py'))
    members[bad] = b'def (:\n'
    with zipfile.ZipFile(zpath, 'w') as z:
        for n, data in members.items():
            z.writestr(n, data)
    (out / 'files' / 'L01-solutions.py').write_bytes(b'def (:\n')
    assert any('L01-solutions.py' in p and 'does not parse' in p for p in cf.static_problems(out))


def test_learner_run_passes_and_reports_the_python(tmp_path):
    out = build(tmp_path)
    report = cf.run_as_learner(out, pythons=[sys.executable], workdir=tmp_path / 'learner')
    assert report['problems'] == [], report['problems']
    assert report['python'] == f'{sys.version_info.major}.{sys.version_info.minor}'
    ran = report['ran']
    assert any('L01-solutions.py' in r and 'pack root' in r for r in ran)
    assert any('L01-solutions.py' in r and 'own folder' in r for r in ran)
    assert any('L01-solutions.ipynb' in r for r in ran) and any('L01-S1-seed.sql' in r for r in ran)


def test_learner_run_fails_on_an_error_and_on_a_warning(tmp_path):
    out = build(tmp_path, page(solution='raise SystemExit(sum(1 for _ in rows) - 3)'))
    report = cf.run_as_learner(out, pythons=[sys.executable], workdir=tmp_path / 'learner')
    assert any('L01-solutions.py' in p for p in report['problems'])
    assert report['python'] is None
    warn = build(tmp_path / 'w', page(solution='import warnings\nwarnings.warn("old", DeprecationWarning)'))
    report = cf.run_as_learner(warn, pythons=[sys.executable], workdir=tmp_path / 'w-learner')
    assert any('DeprecationWarning' in p for p in report['problems'])


def test_learner_run_falls_back_to_the_next_python(tmp_path, monkeypatch):
    out = build(tmp_path)
    calls = []

    def fake(pack_root, python, venv_dir, requirements):
        calls.append(python)
        return (['L01-solutions.py: boom'] if python == 'py-3.99' else []), ['ran']
    monkeypatch.setattr(cf, '_run_with', fake)
    monkeypatch.setattr(cf, 'resolve_python', lambda p: f'py-{p}' if p != '3.97' else None)
    report = cf.run_as_learner(out, pythons=['3.97', '3.99', '3.98'], workdir=tmp_path / 'learner')
    assert calls == ['py-3.99', 'py-3.98'] and report['problems'] == []
    assert report['python'] == '3.98' and report['tried']['3.99'] == ['L01-solutions.py: boom']
    assert report['tried']['3.97'] == ['Python 3.97 is not installed']


# Final review finding 4: Windows "Extract All" adds a second pack-named folder, and a path past
# 260 characters fails there. Every path inside the pack stays within MAX_PACK_PATH.
def test_a_path_too_long_for_windows_fails(tmp_path):
    out = build(tmp_path)
    zpath = out / 'fees-practice-pack-v1.zip'
    with zipfile.ZipFile(zpath, 'a') as z:
        z.writestr('fees-practice-pack-v1/L01-reading-fees/' + 'x' * 120 + '.txt', 'deep\n')
    assert any('too long for Windows' in p for p in cf.static_problems(out))


def test_learner_run_reports_a_folder_windows_cannot_enter(tmp_path, monkeypatch):
    out = build(tmp_path)
    real = cf.subprocess.run

    def refuse(args, **kw):
        if kw.get('cwd') is not None and 'reading-fees' in str(kw['cwd']):
            raise NotADirectoryError(267, 'The directory name is invalid')
        return real(args, **kw)
    monkeypatch.setattr(cf.subprocess, 'run', refuse)
    report = cf.run_as_learner(out, pythons=[sys.executable], workdir=tmp_path / 'learner')
    assert any('own folder' in p and 'path too long' in p for p in report['problems']), report['problems']


def test_the_learner_workdir_is_short_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(cf.sys, 'platform', 'win32')
    work = cf.default_workdir(tmp_path / ('deep' * 30))
    assert len(str(work)) < 120 and work.exists() and 'deep' not in str(work)
    work.rmdir()
    monkeypatch.setattr(cf.sys, 'platform', 'linux')
    assert cf.default_workdir(tmp_path) == tmp_path / 'learner'


def test_size_limits(tmp_path, monkeypatch):
    out = build(tmp_path)
    monkeypatch.setattr(pf, 'PACK_LIMIT', 10)
    assert any('pack limit' in p for p in cf.static_problems(out))


def test_skill_step_5c_commands_run_end_to_end(tmp_path):
    """SKILL.md Step 5c, command by command, as any model would type it."""
    import subprocess
    from pathlib import Path
    here = Path(cf.__file__).resolve().parent
    course = {'lessons': [{'id': 'fees-01', 'title': 'Reading Fees', 'content': page()}]}
    (tmp_path / 'course-fees_output.json').write_text(json.dumps(course), encoding='utf-8')
    (tmp_path / 'world_data.json').write_text(json.dumps(WORLD), encoding='utf-8')
    (tmp_path / 'course-fees_requirements.txt').write_text('', encoding='utf-8')
    pack = tmp_path / 'pack'

    def step2(*extra):
        return subprocess.run([sys.executable, str(here / 'practice_files.py'), '--course',
                               str(tmp_path / 'course-fees_output.json'), '--world', str(tmp_path / 'world_data.json'),
                               '--course-short', 'fees', '--version', '1', '--requirements',
                               str(tmp_path / 'course-fees_requirements.txt'), '--workdir', str(tmp_path),
                               '--out-dir', str(pack), *extra], capture_output=True, text=True, encoding='utf-8')
    built = step2()
    assert built.returncode == 0, built.stderr
    marked = pack / 'course-fees_output.json'
    check = subprocess.run([sys.executable, str(here / 'check_files.py'), '--out-dir', str(pack), '--course',
                            str(marked), '--as-learner', '--pythons', sys.executable],
                           capture_output=True, text=True, encoding='utf-8')
    assert check.returncode == 0, check.stdout + check.stderr
    version = check.stdout.split('Learner run passed on Python ')[1].split()[0]
    assert step2('--python', version).returncode == 0
    assert f'Python {version}' in json.loads(marked.read_text(encoding='utf-8'))['lessons'][0]['content']
