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
