import json
import sys

import pytest

import capstone as cp
import check_capstone as cc

SOLUTION = '''from pathlib import Path
import csv

DATA = Path(__file__).resolve().parents[1] / "data"


def load_fees():
    # >>> M1: read L05-fees.csv into a list of ints
    with open(DATA / "L05-fees.csv", newline="") as f:
        return [int(row["fee"]) for row in csv.DictReader(f)]
    # <<< M1


def total(fees):
    # >>> M2: add up the fees
    return sum(fees)
    # <<< M2


if __name__ == "__main__":
    print(total(load_fees()))
'''

TEST_M1 = 'from report import load_fees\n\n\ndef test_reads_three_fees():\n    assert load_fees() == [9000, 4000, 2500]\n'
TEST_M2 = 'from report import total\n\n\ndef test_adds():\n    assert total([1, 2]) == 3\n'
TEST_FINAL = 'from report import load_fees, total\n\n\ndef test_whole():\n    assert total(load_fees()) == 15500\n'


def project(tmp_path, solution=SOLUTION, tests=None):
    src = tmp_path / 'capstone'
    (src / 'solution').mkdir(parents=True)
    (src / 'tests').mkdir()
    (src / 'data').mkdir()
    (src / 'solution' / 'report.py').write_text(solution, encoding='utf-8')
    for name, body in (tests or {'test_m1_load.py': TEST_M1, 'test_m2_total.py': TEST_M2,
                                 'test_final_report.py': TEST_FINAL}).items():
        (src / 'tests' / name).write_text(body, encoding='utf-8')
    (src / 'data' / 'L05-fees.csv').write_text('fee\n9000\n4000\n2500\n', encoding='utf-8')
    (src / 'README.md').write_text('# The fee report\n', encoding='utf-8')
    return src


def test_starter_replaces_each_milestone_with_a_todo():
    starter = cp.make_starter(SOLUTION)
    assert 'raise NotImplementedError("M1: read L05-fees.csv into a list of ints")' in starter
    assert '# TODO M1: read L05-fees.csv into a list of ints' in starter
    assert 'csv.DictReader' not in starter and 'return sum' not in starter
    assert 'def total(fees):\n    # TODO M2: add up the fees\n    raise NotImplementedError("M2: add up the fees")' in starter
    compile(starter, 'report.py', 'exec')


@pytest.mark.parametrize('bad, why', [
    (SOLUTION.replace('    # <<< M1\n', ''), 'M1'),
    (SOLUTION.replace('# <<< M2', '# <<< M3'), 'M3'),
])
def test_unbalanced_markers_fail(bad, why):
    with pytest.raises(ValueError, match=why):
        cp.make_starter(bad)


def test_build_tree_has_every_part(tmp_path):
    tree = cp.build_tree(project(tmp_path))
    assert set(tree) == {'README.md', 'data/L05-fees.csv', 'solution/report.py', 'starter/report.py',
                         'tests/test_m1_load.py', 'tests/test_m2_total.py', 'tests/test_final_report.py'}
    assert b'NotImplementedError' in tree['starter/report.py']


def written(tmp_path, src):
    out = tmp_path / 'built'
    for rel, data in cp.build_tree(src).items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(data)
    return out


def test_check_capstone_passes_a_good_project(tmp_path):
    out = written(tmp_path, project(tmp_path))
    report = cc.check(out, python=sys.executable)
    assert report['problems'] == [], report
    assert report['milestones'] == ['M1', 'M2', 'final']


# --dir given as a relative path: pytest runs with cwd set to the project, so a test path
# built from a relative root pointed nowhere and every milestone failed with exit 4.
def test_check_capstone_accepts_a_relative_dir(tmp_path, monkeypatch):
    out = written(tmp_path, project(tmp_path))
    monkeypatch.chdir(tmp_path)
    report = cc.check(out.relative_to(tmp_path), python=sys.executable)
    assert report['problems'] == [], report


def test_milestone_test_passing_on_the_starter_fails(tmp_path):
    lazy = {'test_m1_load.py': TEST_M1, 'test_m2_total.py': 'def test_nothing():\n    assert True\n',
            'test_final_report.py': TEST_FINAL}
    out = written(tmp_path, project(tmp_path, tests=lazy))
    problems = cc.check(out, python=sys.executable)['problems']
    assert any('M2' in p and 'pass on the starter' in p for p in problems)


def test_broken_solution_and_missing_tests_fail(tmp_path):
    out = written(tmp_path, project(tmp_path, solution=SOLUTION.replace('return sum(fees)', 'return 0')))
    problems = cc.check(out, python=sys.executable)['problems']
    assert any('M2' in p and 'fail on the solution' in p for p in problems)
    no_m2 = {'test_m1_load.py': TEST_M1, 'test_final_report.py': TEST_FINAL}
    out = written(tmp_path / 'b', project(tmp_path / 'b', tests=no_m2))
    assert any('M2' in p and 'no tests' in p for p in cc.check(out, python=sys.executable)['problems'])


def test_page_code_must_be_part_of_the_solution(tmp_path):
    out = written(tmp_path, project(tmp_path))
    shown = ['def total(fees):\n    return sum(fees)', 'print(total(load_fees()))']
    assert cc.page_code_problems(shown, out / 'solution') == []
    problems = cc.page_code_problems(['return max(fees)'], out / 'solution')
    assert problems and 'return max(fees)' in problems[0]


def test_pack_carries_the_capstone_and_its_world_data(tmp_path):
    import zipfile
    import check_files as cf
    import practice_files as pf
    src = project(tmp_path)
    (src / 'data' / 'L05-fees.csv').unlink()  # the pack builds it from the world
    # A capstone is the course's last chapter; a one-chapter course keeps the fixture small (L01).
    (src / 'solution' / 'report.py').write_text(SOLUTION.replace('L05-fees.csv', 'L01-fees.csv'), encoding='utf-8')
    spec = {'python': '3.12', 'files': [
        {'name': 'L01-fees.csv', 'sections': [1], 'from': {'world': 'enquiries', 'columns': ['fee']}},
        {'capstone': 'capstone', 'about': 'The fee report, end to end'},
    ]}
    html = ('<h2>Overview</h2><script type="application/json" class="nerdit-files-spec">'
            f'{json.dumps(spec)}</script><h2>1 — Milestone 1</h2>')
    chapters = [{'id': 'cap-01', 'title': 'Capstone: The Fee Report', 'html': html}]
    world = {'enquiries': [{'enquiry_id': 'E1', 'fee': 9000}, {'enquiry_id': 'E2', 'fee': 4000},
                           {'enquiry_id': 'E3', 'fee': 2500}]}
    result = pf.build_pack(chapters, course_short='fees', version=1, world=world, requirements='pytest\n',
                           out_dir=tmp_path / 'out', workdir=tmp_path)
    with zipfile.ZipFile(tmp_path / 'out' / result['pack']) as z:
        names = set(z.namelist())
    root = 'fees-practice-pack-v1/L01-capstone-the-fee-report/'
    assert {root + 'data/L01-fees.csv', root + 'solution/report.py', root + 'starter/report.py',
            root + 'tests/test_m1_load.py', root + 'README.md'} <= names
    assert root + 'L01-fees.csv' not in names
    assert cf.static_problems(tmp_path / 'out') == []
    learner = cf.run_as_learner(tmp_path / 'out', pythons=[sys.executable], workdir=tmp_path / 'learner')
    assert not any('starter/' in r or 'tests/' in r for r in learner['ran']), learner['ran']


def test_capstone_solutions_file_finds_the_project_modules_and_data(tmp_path):
    """The page's examples import the project's own modules and read its data/ files by name."""
    import zipfile
    import check_files as cf
    import practice_files as pf
    src = project(tmp_path)
    (src / 'data' / 'L05-fees.csv').unlink()
    (src / 'solution' / 'report.py').write_text(SOLUTION.replace('L05-fees.csv', 'L01-fees.csv'), encoding='utf-8')
    spec = {'python': '3.12', 'files': [
        {'name': 'L01-fees.csv', 'sections': [1], 'from': {'world': 'enquiries', 'columns': ['fee']}},
        {'name': 'L01-solutions.py', 'sections': 'all', 'from': {'solutions': 'all'}},
        {'capstone': 'capstone', 'about': 'The fee report, end to end'},
    ]}
    run = ('<div class="nerdit-run" data-run="offline"><div class="nerdit-in"><pre data-lang="python"><code>'
           'from report import total\nwith open("L01-fees.csv") as f:\n    print(len(f.readlines()))\n'
           'print(total([1, 2]))</code></pre></div><div class="nerdit-out"><pre><code>4\n3</code></pre></div></div>')
    html = ('<h2>Overview</h2><script type="application/json" class="nerdit-files-spec">'
            f'{json.dumps(spec)}</script><h2>1 — Milestone 1</h2>{run}')
    chapters = [{'id': 'cap-01', 'title': 'Capstone: The Fee Report', 'html': html}]
    world = {'enquiries': [{'enquiry_id': 'E1', 'fee': 9000}, {'enquiry_id': 'E2', 'fee': 4000},
                           {'enquiry_id': 'E3', 'fee': 2500}]}
    result = pf.build_pack(chapters, course_short='fees', version=1, world=world, requirements='pytest\n',
                           out_dir=tmp_path / 'out', workdir=tmp_path)
    with zipfile.ZipFile(tmp_path / 'out' / result['pack']) as z:
        assert 'fees-practice-pack-v1/L01-capstone-the-fee-report/solutions/L01-solutions.py' in z.namelist()
    learner = cf.run_as_learner(tmp_path / 'out', pythons=[sys.executable], workdir=tmp_path / 'learner')
    assert learner['problems'] == [], learner['problems']


def test_new_libraries_must_be_pinned_and_explained(tmp_path):
    out = written(tmp_path, project(tmp_path, solution='import matplotlib.pyplot as plt\nfrom PIL import Image\n'
                                    + SOLUTION))
    problems = cc.library_problems(out, 'matplotlib==3.10.7\n')
    assert any('pillow' in p and 'not pinned' in p for p in problems)
    assert any('matplotlib' in p and 'README' in p for p in problems)
    (out / 'README.md').write_text('# Report\n\n## New tools in this project\n\n- **matplotlib** draws the '
                                   'fee chart.\n- **pillow** saves it as a PNG.\n', encoding='utf-8')
    assert cc.library_problems(out, 'matplotlib==3.10.7\npillow==12.0\n') == []


def test_data_files_must_come_from_the_world(tmp_path):
    out = written(tmp_path, project(tmp_path))
    rows = [{'name': 'L05-fees.csv', 'source': {'world': 'enquiries'}}]
    assert cc.data_problems(out, rows) == []
    assert 'not built from the course world' in cc.data_problems(out, [])[0]
    assert cc.data_problems(out, [{'name': 'L05-fees.csv', 'source': {'json': []}}])


# Strict accuracy: tests must run the solution (coverage) and catch planted bugs (mutation).

LOOP_SOLUTION = SOLUTION.replace('''    # >>> M2: add up the fees
    return sum(fees)
    # <<< M2''', '''    # >>> M2: add up the fees
    result = 0
    for fee in fees:
        result = result + fee
    return result
    # <<< M2''')


def test_coverage_counts_solution_lines_the_tests_run(tmp_path):
    out = written(tmp_path, project(tmp_path))
    pct, missed = cc.coverage(out, python=sys.executable)
    assert pct == 100 and missed == [], missed
    extra = SOLUTION + '\n\ndef unused(rows):\n    kept = [r for r in rows if r]\n    kept.sort()\n    return kept\n'
    out = written(tmp_path / 'u', project(tmp_path / 'u', solution=extra))
    pct, missed = cc.coverage(out, python=sys.executable)
    assert pct < 80 and any('report.py' in m for m in missed)
    assert any('runs' in p and 'unused' not in p for p in cc.check(out, python=sys.executable)['problems'])


def test_mutants_are_made_only_inside_milestone_blocks():
    found = cc.mutants(LOOP_SOLUTION)
    assert {m['milestone'] for m in found} == {'M1', 'M2'}
    labels = [m['change'] for m in found if m['milestone'] == 'M2']
    assert '0 -> 1' in labels and '+ -> -' in labels and 'return -> return None' in labels
    for m in found:
        compile(m['source'], 'report.py', 'exec')


def test_strong_tests_kill_the_mutants(tmp_path):
    out = written(tmp_path, project(tmp_path, solution=LOOP_SOLUTION))
    report = cc.mutation(out, python=sys.executable)
    assert report['problems'] == [], report
    assert report['score']['M2'] == (3, 3)


def test_weak_tests_let_mutants_survive_and_fail(tmp_path):
    weak = {'test_m1_load.py': TEST_M1,
            'test_m2_total.py': 'from report import total\n\n\ndef test_type():\n'
                                '    assert isinstance(total([1, 2]), int)\n',
            'test_final_report.py': 'from report import load_fees, total\n\n\ndef test_whole():\n'
                                    '    assert total(load_fees()) is not None\n'}
    out = written(tmp_path, project(tmp_path, solution=LOOP_SOLUTION, tests=weak))
    report = cc.mutation(out, python=sys.executable)
    assert any(p.startswith('M2:') and 'survive' in p and '0 -> 1' in p for p in report['problems']), report
