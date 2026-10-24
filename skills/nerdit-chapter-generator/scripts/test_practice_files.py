import json
import zipfile

import pytest

import practice_files as pf

WORLD = {
    'enquiry_messages': [
        {'message_id': 'M1', 'intent': 'fees', 'message': 'How much?', 'branch': 'Adajan'},
        {'message_id': 'M2', 'intent': 'batch', 'message': 'Next batch, "evening"?', 'branch': 'Vesu'},
        {'message_id': 'M7', 'intent': 'demo', 'message': 'Free demo?', 'branch': 'Adajan'},
    ],
}


def lesson(spec: dict) -> str:
    return ('<h2>Overview</h2><p>Text.</p>'
            f'<script type="application/json" class="nerdit-files-spec">{json.dumps(spec)}</script>'
            '<h2>1 — First idea</h2><p>One.</p><h2>2 — Second idea</h2><p>Two.</p>')


def spec(*files):
    return {'python': '3.14', 'files': list(files)}


def test_read_spec_from_lesson_html():
    s = pf.read_spec(lesson(spec({'name': 'L02-S2-replies.json', 'sections': [2], 'from': {'json': {'a': 1}}})))
    assert s['python'] == '3.14' and s['files'][0]['name'] == 'L02-S2-replies.json'
    assert pf.read_spec('<p>no spec</p>') is None


def test_read_spec_rejects_two_blocks():
    one = lesson(spec())
    with pytest.raises(ValueError, match='one nerdit-files-spec'):
        pf.read_spec(one + one)


@pytest.mark.parametrize('name', ['L02-S1-enquiry-messages.csv', 'L02-practice-starter.ipynb',
                                  'L02-solutions.py', 'L02-full-app.py'])
def test_good_names(name):
    assert pf.name_problems(name, 2) == []


@pytest.mark.parametrize('name, why', [
    ('L03-S1-x.csv', 'L02-'),
    ('L02-S1-Enquiry.csv', 'lower case'),
    ('L02-S1-x_y.csv', 'lower case'),
    ('L02-S1-' + 'a' * 60 + '.csv', '60'),
    ('L02-S1-x.exe', 'extension'),
    ('L02-S1-x.xlsm', 'extension'),
    ('L02-S1-x.xlsx', 'extension'),
])
def test_bad_names(name, why):
    assert any(why in p for p in pf.name_problems(name, 2))


def test_chapter_folder_slug():
    assert pf.chapter_folder(2, 'Timeouts, Retries & Rate Limits!') == 'L02-timeouts-retries-rate-limits'
    assert len(pf.chapter_folder(1, 'x' * 200)) <= 60


def test_world_slice_picks_rows_and_columns_as_csv():
    entry = {'name': 'L02-S1-msgs.csv', 'from': {'world': 'enquiry_messages', 'rows': ['M1', 'M2'],
                                                  'columns': ['message_id', 'message']}}
    data = pf.build_file(entry, world=WORLD)
    assert data.decode() == 'message_id,message\nM1,How much?\nM2,"Next batch, ""evening""?"\n'


def test_world_slice_unknown_row_fails():
    entry = {'name': 'L02-S1-msgs.csv', 'from': {'world': 'enquiry_messages', 'rows': ['M99']}}
    with pytest.raises(ValueError, match='M99'):
        pf.build_file(entry, world=WORLD)


def test_json_source_two_space_indent():
    data = pf.build_file({'name': 'L02-S2-r.json', 'from': {'json': {'M2': [503, 200]}}})
    assert data.decode() == '{\n  "M2": [\n    503,\n    200\n  ]\n}\n'


def test_jsonl_source_one_object_per_line():
    data = pf.build_file({'name': 'L02-S2-r.jsonl', 'from': {'json': [{'a': 1}, {'b': 2}]}})
    assert data.decode() == '{"a": 1}\n{"b": 2}\n'


def test_file_source_reads_from_workdir(tmp_path):
    (tmp_path / 'full-app.py').write_bytes(b'print("hi")\n')
    data = pf.build_file({'name': 'L02-full-app.py', 'from': {'file': 'full-app.py'}}, workdir=tmp_path)
    assert data == b'print("hi")\n'


def test_file_source_cannot_escape_workdir(tmp_path):
    with pytest.raises(ValueError, match='workdir'):
        pf.build_file({'name': 'L02-x.py', 'from': {'file': '../secret.py'}}, workdir=tmp_path)


PAGE = '''
<section><h2>1. Load the messages</h2>
<div class="nerdit-run"><div class="nerdit-in"><pre data-lang="python"><code>import pandas as pd
df = pd.DataFrame({"a": [1, 2]})</code></pre></div>
<div class="nerdit-out"><pre><code></code></pre></div></div>
<figure class="nerdit-figure"><figcaption>Neha's requests: capacity 3</figcaption>
<table><thead><tr><th>request</th><th>at</th></tr></thead>
<tbody><tr><td>R1</td><td>0.0</td></tr><tr><td>R2, late</td><td>0.4</td></tr></tbody></table></figure>
</section>
<section><h2>2. Count them</h2>
<div class="nerdit-run"><div class="nerdit-in"><pre data-lang="python"><code>print(len(df))</code></pre></div>
<div class="nerdit-out"><pre><code>2</code></pre></div></div>
<div class="nerdit-tryit" data-seed="tryit-seed-1"><textarea class="nerdit-tryit-editor">SELECT 1;</textarea></div>
<script type="text/plain" id="tryit-seed-1">CREATE TABLE requests (id TEXT, at REAL);
INSERT INTO requests VALUES ('R1', 0.0);
</script>
</section>
<section><h2>Practice</h2><div class="nerdit-practical">
<div class="nerdit-task">Task 1: Print the
   sum of column a.
  <details class="nerdit-solution"><summary>Show solution</summary>
  <pre data-lang="python"><code>print(df["a"].sum())</code></pre></details></div>
<div class="nerdit-task">Task 2: Print the first row.
  <details class="nerdit-solution"><summary>Show solution</summary>
  <pre data-lang="python"><code>print(df.iloc[0])</code></pre></details></div>
</div></section>'''

CHAPTER = {'id': 'retries-02', 'title': 'Timeouts and Retries', 'position': 2, 'html': PAGE}


def test_practice_tasks_read_text_and_solution():
    tasks = pf.practice_tasks(PAGE)
    assert tasks == [{'task': 'Task 1: Print the sum of column a.', 'solution': 'print(df["a"].sum())'},
                     {'task': 'Task 2: Print the first row.', 'solution': 'print(df.iloc[0])'}]


def test_starter_py_has_tasks_without_answers():
    text = pf.build_file({'name': 'L02-practice-starter.py', 'from': {'practice': 'starters'}},
                         chapter=CHAPTER).decode()
    assert '# Task 1: Print the sum of column a.' in text and '# Task 2: Print the first row.' in text
    assert 'sum()' not in text and 'iloc' not in text
    assert 'os.chdir' in text
    compile(text, 'starter.py', 'exec')


def test_solutions_py_has_every_example_then_every_answer_in_order():
    text = pf.build_file({'name': 'L02-solutions.py', 'from': {'solutions': 'all'}}, chapter=CHAPTER).decode()
    order = [text.index(s) for s in ('# 1. Load the messages', 'import pandas as pd', '# 2. Count them',
                                     'print(len(df))', '# Task 1:', 'print(df["a"].sum())', '# Task 2:',
                                     'print(df.iloc[0])')]
    assert order == sorted(order)
    assert "HERE.name == 'solutions'" in text
    compile(text, 'solutions.py', 'exec')


def test_solutions_py_runs_from_any_folder(tmp_path):
    import subprocess
    import sys
    text = pf.build_file({'name': 'L02-solutions.py', 'from': {'solutions': 'all'}},
                         chapter={**CHAPTER, 'html': '<div class="nerdit-run"><div class="nerdit-in">'
                                  '<pre data-lang="python"><code>print(open("L02-S1-x.csv").read())'
                                  '</code></pre></div></div>'})
    folder = tmp_path / 'L02-x' / 'solutions'
    folder.mkdir(parents=True)
    (folder / 'L02-solutions.py').write_bytes(text)
    (folder.parent / 'L02-S1-x.csv').write_bytes(b'a\n1\n')
    out = subprocess.run([sys.executable, '-W', 'error', str(folder / 'L02-solutions.py')], cwd=tmp_path,
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout == 'a\n1\n\n'


def test_notebooks_are_valid_nbformat_4():
    start = json.loads(pf.build_file({'name': 'L02-practice-starter.ipynb', 'from': {'practice': 'starters'}},
                                     chapter=CHAPTER))
    assert start['nbformat'] == 4
    kinds = [c['cell_type'] for c in start['cells']]
    assert kinds.count('markdown') >= 2 and kinds.count('code') >= 2
    assert all(c['source'] == [] for c in start['cells'][1:] if c['cell_type'] == 'code')
    sol = json.loads(pf.build_file({'name': 'L02-solutions.ipynb', 'from': {'solutions': 'all'}}, chapter=CHAPTER))
    code = ''.join(''.join(c['source']) for c in sol['cells'] if c['cell_type'] == 'code')
    assert 'print(df.iloc[0])' in code and "os.chdir('..')" in code
    assert all(c['outputs'] == [] for c in sol['cells'] if c['cell_type'] == 'code')


def test_table_source_by_caption():
    data = pf.build_file({'name': 'L02-S1-requests.csv', 'from': {'table': "Neha's requests: capacity 3"}},
                         chapter=CHAPTER)
    assert data.decode() == 'request,at\nR1,0.0\n"R2, late",0.4\n'


def test_table_source_missing_caption_fails():
    with pytest.raises(ValueError, match='no table'):
        pf.build_file({'name': 'L02-S1-x.csv', 'from': {'table': 'Nope'}}, chapter=CHAPTER)


def test_sql_source_is_seed_byte_for_byte_with_header():
    text = pf.build_file({'name': 'L02-S2-requests.sql', 'sections': [2], 'from': {'sql': 'tryit-seed-1'}},
                         chapter=CHAPTER).decode()
    head, _, body = text.partition('\n')
    assert head.startswith('-- L02 Timeouts and Retries, section 2: tables requests')
    assert body == "CREATE TABLE requests (id TEXT, at REAL);\nINSERT INTO requests VALUES ('R1', 0.0);\n"
    import sqlite3
    sqlite3.connect(':memory:').executescript(text)


def chapters():
    return [
        {'id': 'llm-01', 'title': 'LLM API Integration', 'html': lesson(spec(
            {'name': 'L01-S2-chat-payload.json', 'sections': [2], 'about': 'one chat payload',
             'from': {'json': {'model': 'm'}}}))},
        {'id': 'retries-02', 'title': 'Timeouts and Retries', 'html': lesson(spec(
            {'name': 'L02-S1-msgs.csv', 'sections': [1], 'about': '2 messages',
             'from': {'world': 'enquiry_messages', 'rows': ['M1', 'M7']}}))},
        {'id': 'intro-03', 'title': 'No Files Here', 'html': '<p>nothing</p>'},
    ]


def test_build_pack_layout_manifest_and_readme(tmp_path):
    result = pf.build_pack(chapters(), course_short='ai-apis', version=1, world=WORLD,
                           requirements='httpx2==1.0\n', out_dir=tmp_path, image_names={'hero.webp'})
    zpath = tmp_path / 'ai-apis-practice-pack-v1.zip'
    assert result['pack'] == zpath.name
    with zipfile.ZipFile(zpath) as z:
        names = set(z.namelist())
        root = 'ai-apis-practice-pack-v1/'
        assert {root + 'README.txt', root + 'requirements.txt',
                root + 'L01-llm-api-integration/L01-S2-chat-payload.json',
                root + 'L02-timeouts-and-retries/L02-S1-msgs.csv'} <= names
        assert not any('L03' in n for n in names)
        readme = z.read(root + 'README.txt').decode()
        assert 'L02-timeouts-and-retries' in readme and 'L02-S1-msgs.csv' in readme and '2 messages' in readme
        assert z.read(root + 'requirements.txt') == b'httpx2==1.0\n'
    man = json.loads((tmp_path / 'files.manifest.json').read_text(encoding='utf-8'))
    row = next(r for r in man['files'] if r['name'] == 'L02-S1-msgs.csv')
    assert row['lessonId'] == 'retries-02' and row['sections'] == [1] and row['packVersion'] == 1
    assert row['format'] == 'csv' and len(row['sha256']) == 64 and row['bytes'] > 0
    assert (tmp_path / 'files' / 'L02-S1-msgs.csv').is_file()


MARK_PAGE = ('<section><h2>Overview</h2><p>Intro.</p>'
             '<script type="application/json" class="nerdit-files-spec">{}</script></section>'
             '<section><h2>1 — Load the messages</h2><p>Case.</p></section>'
             '<section><h2>2 — Count them</h2><p>More.</p></section>')
MARK_FILES = [
    {'name': 'L02-S1-msgs.csv', 'bytes': 273, 'format': 'csv', 'sections': [1], 'about': '4 rows & <ids>'},
    {'name': 'L02-solutions.py', 'bytes': 900, 'format': 'py', 'sections': 'all', 'about': ''},
]


def test_mark_lesson_adds_folder_box_after_spec_and_section_lines():
    html = pf.mark_lesson(MARK_PAGE, MARK_FILES, folder='L02-timeouts', lesson_id='retries-02', python='3.14')
    spec_end = html.index('</script>')
    box = html.index('data-nerdit-files="retries-02"')
    assert spec_end < box < html.index('1 — Load')
    assert 'folder <code>L02-timeouts</code>' in html and 'Python 3.14' in html
    assert ('<a class="nerdit-file" href="files/L02-S1-msgs.csv" download="L02-S1-msgs.csv" '
            'data-nerdit-file="L02-S1-msgs.csv" data-format="csv" data-bytes="273">') in html
    assert '4 rows &amp; &lt;ids&gt;' in html and '<td>Section 1</td>' in html and '<td>All sections</td>' in html
    use = html.index('class="nerdit-file-use"')
    assert html.index('1 — Load the messages</h2>') < use < html.index('<p>Case.</p>')
    assert html.count('nerdit-file-use') == 1
    assert 'nerdit-course-pack' not in html


def test_mark_lesson_is_idempotent():
    once = pf.mark_lesson(MARK_PAGE, MARK_FILES, folder='L02-timeouts', lesson_id='retries-02', python='3.14')
    twice = pf.mark_lesson(once, MARK_FILES, folder='L02-timeouts', lesson_id='retries-02', python='3.14')
    assert once == twice


def test_mark_lesson_first_chapter_gets_pack_box():
    pack = {'name': 'ai-apis-practice-pack-v1.zip', 'bytes': 48213, 'version': 1, 'chapters': 5,
            'date': '23 Oct 2026'}
    html = pf.mark_lesson(MARK_PAGE, MARK_FILES, folder='L01-x', lesson_id='llm-01', python='3.12', pack=pack)
    assert html.index('nerdit-course-pack') < html.index('data-nerdit-files="llm-01"')
    assert 'href="files/ai-apis-practice-pack-v1.zip"' in html and 'data-format="zip"' in html
    assert 'Download the course practice pack (v1, 47 KB)' in html
    assert '5 chapter folders · updated 23 Oct 2026' in html and 'Python 3.12' in html


def test_mark_lesson_unknown_section_fails():
    files = [{**MARK_FILES[0], 'sections': [7]}]
    with pytest.raises(ValueError, match='section 7'):
        pf.mark_lesson(MARK_PAGE, files, folder='L02-x', lesson_id='x', python='3.14')


def test_mark_course_boxes_every_chapter_with_files(tmp_path):
    ch = chapters()
    result = pf.build_pack(ch, course_short='ai-apis', version=1, world=WORLD, requirements='', out_dir=tmp_path)
    htmls = pf.mark_course(ch, result, date='24 Oct 2026')
    assert 'nerdit-course-pack' in htmls[0] and 'data-nerdit-files="llm-01"' in htmls[0]
    assert 'nerdit-course-pack' not in htmls[1] and 'folder <code>L02-timeouts-and-retries</code>' in htmls[1]
    assert htmls[2] == ch[2]['html']
    assert '2 chapter folders' in htmls[0] and 'Python 3.14' in htmls[1]
    checked = pf.mark_course(ch, result, date='24 Oct 2026', python='3.12')
    assert 'Python 3.14' not in checked[0] + checked[1] and 'Python 3.12' in checked[1]


def test_build_pack_rejects_name_clash_with_image(tmp_path):
    ch = chapters()
    with pytest.raises(ValueError, match='L01-S2-chat-payload.json'):
        pf.build_pack(ch, course_short='ai-apis', version=1, world=WORLD, requirements='', out_dir=tmp_path,
                      image_names={'L01-S2-chat-payload.json'})


def test_build_pack_rejects_bad_name(tmp_path):
    ch = chapters()
    ch[1]['html'] = lesson(spec({'name': 'L01-S1-wrong-chapter.csv', 'from': {'json': []}}))
    with pytest.raises(ValueError, match='L02-'):
        pf.build_pack(ch, course_short='ai-apis', version=1, world=WORLD, requirements='', out_dir=tmp_path)


def test_build_pack_enforces_file_and_pack_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(pf, 'FILE_LIMIT', 10)
    with pytest.raises(ValueError, match='file limit'):
        pf.build_pack(chapters(), course_short='ai-apis', version=1, world=WORLD, requirements='',
                      out_dir=tmp_path)
    monkeypatch.setattr(pf, 'FILE_LIMIT', 10**6)
    monkeypatch.setattr(pf, 'PACK_LIMIT', 50)
    with pytest.raises(ValueError, match='pack limit'):
        pf.build_pack(chapters(), course_short='ai-apis', version=1, world=WORLD, requirements='',
                      out_dir=tmp_path)
