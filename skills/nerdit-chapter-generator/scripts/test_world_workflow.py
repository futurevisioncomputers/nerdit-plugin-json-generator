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
