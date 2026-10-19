import json
from pathlib import Path
import subprocess
import sys

from gate_lesson import gate
from test_gate_lesson import setup
from test_world_data import world

HERE = Path(__file__).resolve().parent


def invoke(script, *args):
    return subprocess.run([sys.executable, str(HERE / script), *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8')


def test_library_reference_and_generator_cli(tmp_path):
    ref = tmp_path / 'course-x_world.json'
    ref.write_text('{"use":"practice-retail"}', encoding='utf-8')
    result = invoke('make_world_data.py', '--world', ref, '--out-dir', tmp_path)
    assert result.returncode == 0, result.stderr
    first = (tmp_path / 'world_data.json').read_bytes()
    assert invoke('make_world_data.py', '--world', ref, '--out-dir', tmp_path).returncode == 0
    assert (tmp_path / 'world_data.json').read_bytes() == first
    assert len(json.loads(first)['orders']) == 24


def test_input_cli_rejects_invalid_world_in_strict_mode(tmp_path):
    inp, _ = setup(tmp_path)
    bad = tmp_path / 'bad-world.json'
    bad.write_text('{}', encoding='utf-8')
    result = invoke('check_input.py', '--input', inp, '--world', bad, '--strict')
    assert result.returncode == 2 and '<world>' in result.stdout


def test_gate_uses_world_and_does_not_allow_missing_disclosure(tmp_path):
    inp, directory = setup(tmp_path)
    wp = tmp_path / 'world.json'
    wp.write_text(json.dumps(world()), encoding='utf-8')
    fails, warns = gate(inp, directory, 'c-01', world_path=wp)
    assert any('world:' in f and 'disclosure' in f for f in fails)
    assert any('course-map' in w for w in warns)


def test_whole_course_cli_enforces_world_only_for_v11(tmp_path):
    from assemble_course import build_course
    inp, directory = setup(tmp_path)
    output = tmp_path / 'course_output.json'
    course = build_course('test', json.loads(inp.read_text()), None, str(directory), now_ms=0)
    output.write_text(json.dumps(course), encoding='utf-8')
    wp = tmp_path / 'world.json'
    wp.write_text(json.dumps(world()), encoding='utf-8')
    v10 = invoke('verify_course.py', '--input', inp, '--output', output, '--world', wp, '--contract', 'v10')
    v11 = invoke('verify_course.py', '--input', inp, '--output', output, '--world', wp, '--contract', 'v11')
    assert v10.returncode == 0, v10.stdout
    assert v11.returncode == 1 and 'world:' in v11.stdout


def test_make_world_data_writes_csv_and_manifest(tmp_path):
    w = world()
    w['profile'] = 'analytics'
    w['entities']['orders']['rows'] = 400
    w['entities']['orders']['defects'] = {'missing': [{'column': 'units', 'rate': 0.05}]}
    w['entities']['ratings'] = {'kind': 'interactions', 'users': 'stores', 'items': 'orders',
                                'user_column': 'store_id', 'item_column': 'order_id', 'k': 2,
                                'density': 0.01, 'scale': [1, 5]}
    wp = tmp_path / 'course-x_world.json'
    wp.write_text(json.dumps(w), encoding='utf-8')
    result = invoke('make_world_data.py', '--world', wp, '--out-dir', tmp_path)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / 'world_data.manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['defects']['orders']['missing']['units']) == 20
    header = (tmp_path / 'orders.csv').read_text(encoding='utf-8').splitlines()[0]
    assert header == ','.join(w['entities']['orders']['columns'])
    assert (tmp_path / 'ratings.csv').read_text(encoding='utf-8').startswith('store_id,order_id,rating\n')
    assert 'CREATE TABLE "ratings"' in (tmp_path / 'world_data.sql').read_text(encoding='utf-8')


def test_make_world_data_builds_a_lesson_recipe_with_its_own_seed(tmp_path):
    from nerdit_world_gen import build_files
    w = world()
    w['entities']['orders']['defects'] = {'missing': [{'column': 'units', 'rate': 0.4}]}
    recipe = {'seed': 3, 'files': {'orders.csv': {'entity': 'orders', 'drop': ['customer']}}, 'world': w}
    lesson = tmp_path / 'x-01.html'
    lesson.write_text('<div><script type="application/json" class="nerdit-dataset">'
                      + json.dumps(recipe) + '</script></div>', encoding='utf-8')
    out = tmp_path / 'out'
    result = invoke('make_world_data.py', '--recipe', lesson, '--out-dir', out)
    assert result.returncode == 0, result.stderr
    assert (out / 'orders.csv').read_bytes() == build_files(recipe)['orders.csv'].encode('utf-8')
    assert (out / 'orders.csv').read_bytes() != build_files(dict(recipe, seed=7))['orders.csv'].encode('utf-8')
    manifest = json.loads((out / 'world_data.manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['defects']['orders']['missing']['units']) == 2
    as_json = tmp_path / 'recipe.json'
    as_json.write_text(json.dumps(recipe), encoding='utf-8')
    assert invoke('make_world_data.py', '--recipe', as_json, '--out-dir', tmp_path / 'j').returncode == 0
    assert (tmp_path / 'j' / 'orders.csv').read_bytes() == (out / 'orders.csv').read_bytes()
    assert invoke('make_world_data.py', '--recipe', tmp_path / 'none.html', '--out-dir', out).returncode == 2
