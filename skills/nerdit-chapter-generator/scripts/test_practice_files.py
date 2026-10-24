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
            f'<script type="application/json" class="nerdit-files-spec">{json.dumps(spec)}</script>')


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
