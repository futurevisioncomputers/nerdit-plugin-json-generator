import json

import pytest

import check_modern_code as cm


def test_every_rule_in_deprecated_md_compiles_and_has_a_fix():
    rules = cm.load_rules()
    assert len(rules) >= 15
    assert all(r.pattern and fix for r, fix in rules)
    assert len(cm.load_rules(new_course=True)) == len(rules) + 1


@pytest.mark.parametrize('code, fix', [
    ('from typing import List\nx: List[int] = []', 'list'),
    ('from datetime import datetime\nnow = datetime.utcnow()', 'datetime.now(UTC)'),
    ('loop = asyncio.get_event_loop()', 'asyncio.run()'),
    ('try:\n    pass\nexcept asyncio.TimeoutError:\n    pass', 'except TimeoutError'),
    ('@app.on_event("startup")\ndef go():\n    pass', 'lifespan'),
    ('class M(BaseModel):\n    class Config:\n        frozen = True', 'model_config'),
    ('row = m.dict()', 'model_dump'),
    ('df.dropna(inplace=True)', 'assign the result'),
    ('enc = OneHotEncoder(sparse=False)', 'sparse_output'),
])
def test_deprecated_code_is_found(code, fix):
    found = cm.scan(code)
    assert found and fix in found[0]['instead']


@pytest.mark.parametrize('code', [
    'from datetime import UTC, datetime\nnow = datetime.now(UTC)',
    'x: list[int] | None = None',
    '# never call datetime.utcnow() in new code\nprint(1)',
    'msg = "use model_dump"',
    'enc = OneHotEncoder(sparse_output=False)',
    'counts = {}\ncounts.update(a=1)',
])
def test_modern_code_passes(code):
    assert cm.scan(code) == []


def test_line_numbers_point_at_the_call():
    found = cm.scan('import json\n\nx = datetime.utcnow()\n')
    assert found[0]['line'] == 3


def test_httpx_only_flagged_for_new_courses():
    assert cm.scan('import httpx') == []
    assert 'httpx2' in cm.scan('import httpx', new_course=True)[0]['instead']
    assert cm.scan('import httpx2', new_course=True) == []


def test_lesson_blocks_cover_runs_tryits_and_solutions():
    html = ('<div class="nerdit-run"><div class="nerdit-in"><pre data-lang="python"><code>a = 1</code></pre></div></div>'
            '<div class="nerdit-tryit" data-lang="python"><textarea>b = 2</textarea></div>'
            '<details class="nerdit-solution"><pre data-lang="python"><code>c = 3</code></pre></details>'
            '<pre data-lang="sql"><code>SELECT 1;</code></pre>')
    assert cm.lesson_code(html) == ['a = 1', 'b = 2', 'c = 3']


def test_course_and_files_cli(tmp_path, capsys):
    course = {'lessons': [{'id': 'x-01', 'content': '<div class="nerdit-run"><div class="nerdit-in">'
                           '<pre data-lang="python"><code>t = datetime.utcnow()</code></pre></div></div>'}]}
    (tmp_path / 'c.json').write_text(json.dumps(course), encoding='utf-8')
    assert cm.main(['--course', str(tmp_path / 'c.json')]) == 1
    assert 'x-01' in capsys.readouterr().out
    files = tmp_path / 'pack'
    files.mkdir()
    (files / 'L01-solutions.py').write_text('from datetime import UTC, datetime\n', encoding='utf-8')
    nb = {'cells': [{'cell_type': 'markdown', 'source': ['use .dict() never']},
                    {'cell_type': 'code', 'source': ['row = m.dict()\n']}], 'nbformat': 4}
    (files / 'L01-solutions.ipynb').write_text(json.dumps(nb), encoding='utf-8')
    assert cm.main(['--files', str(files)]) == 1
    out = capsys.readouterr().out
    assert 'L01-solutions.ipynb' in out and 'L01-solutions.py' not in out
    (files / 'L01-solutions.ipynb').unlink()
    assert cm.main(['--files', str(files)]) == 0
