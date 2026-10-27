import sys

import pytest

import lesson_runs as lr

PY = f"{sys.version_info.major}.{sys.version_info.minor}"


def run(code, out, offline=True):
    attr = ' data-run="offline"' if offline else ""
    return (f'<div class="nerdit-run"{attr}><div class="nerdit-in"><span class="nerdit-tag">You type</span>'
            f'<pre data-lang="python"><code>{code}</code></pre></div><div class="nerdit-out">'
            f'<span class="nerdit-tag">Python shows</span><pre><code>{out}</code></pre></div></div>')


def task(n, code):
    return (f'<div class="nerdit-task">Task {n}: do it.<details class="nerdit-solution"><summary>Solution</summary>'
            f'<pre data-lang="python"><code>{code}</code></pre></details></div>')


def lesson(*parts, lid="routes-02"):
    return {"id": lid, "title": "Routes", "content": "<section><h2>1 — Routes</h2>" + "".join(parts) + "</section>"}


@pytest.fixture(scope="module")
def vpy(tmp_path_factory):
    vpy, err = lr.ensure_venv(tmp_path_factory.mktemp("cache"), "", [PY])
    assert err is None
    return vpy


def test_the_venv_is_made_once_and_reused_while_requirements_stay_the_same(tmp_path):
    first, err = lr.ensure_venv(tmp_path, "", [PY])
    assert err is None and first.exists()
    stamp = (tmp_path / "venv.stamp").read_text(encoding="utf-8")
    first.with_name("marker").write_text("kept", encoding="utf-8")
    again, _ = lr.ensure_venv(tmp_path, "", [PY])
    assert again == first and first.with_name("marker").exists()          # reused, not rebuilt
    assert (tmp_path / "venv.stamp").read_text(encoding="utf-8") == stamp


def test_a_lesson_whose_examples_and_answers_run_passes(tmp_path, vpy):
    ls = lesson(run("names = ['a', 'b']\nprint(len(names))", "2"), task(1, "print(len(names) + 1)"))
    assert lr.lesson_runs(ls, 2, vpy, tmp_path) == ([], [])


def test_a_wrong_offline_output_fails(tmp_path, vpy):
    fails, _ = lr.lesson_runs(lesson(run("print(3)", "4")), 2, vpy, tmp_path)
    assert fails and "example 1" in fails[0] and "Python prints '3'" in fails[0]


def test_a_practice_answer_that_crashes_after_the_page_examples_fails(tmp_path, vpy):
    ls = lesson(run("names = ['a']\nprint(len(names))", "1", offline=False), task(1, "print(client.get('/'))"))
    fails, _ = lr.lesson_runs(ls, 3, vpy, tmp_path)
    assert fails == ["practice answers: run after every example on the page, in page order, they stop with "
                     "\"NameError: name 'client' is not defined\"; make each answer build what it needs"]


def test_answers_read_the_lessons_files(tmp_path, vpy):
    data = tmp_path / "L02-S1-enquiries.csv"
    data.write_text("enquiry_id\nE1\nE2\n", encoding="utf-8")
    ls = lesson(task(1, "print(len(open('L02-S1-enquiries.csv').read().split()))"))
    assert lr.lesson_runs(ls, 2, vpy, tmp_path / "w", files=[data]) == ([], [])


def test_a_lesson_without_python_runs_nothing(tmp_path):
    assert lr.lesson_runs(lesson("<p>Only words.</p>"), 1, None, tmp_path) == ([], [])


def test_capstone_answers_are_left_to_check_capstone(tmp_path, vpy):
    spec = '<script type="application/json" class="nerdit-files-spec">{"files": [{"capstone": {}}]}</script>'
    ls = lesson(spec, task(1, "import missing_module"))
    fails, warns = lr.lesson_runs(ls, 11, vpy, tmp_path)
    assert fails == [] and warns == ["practice answers: the capstone's are run by check_capstone.py"]
