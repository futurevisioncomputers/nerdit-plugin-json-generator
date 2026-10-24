"""check_python_outputs.py (Plan C Task 10). Engine tests skip, with the reason, when it is not installed."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from check_python_outputs import check_lesson, normalise, python_parts
from pyodide_engine import engine_available
from test_world_data import world

HERE = Path(__file__).resolve().parent
AVAILABLE, REASON = engine_available()
engine = pytest.mark.skipif(not AVAILABLE, reason=REASON)


def run_line(code: str, shown: str | None = "", offline: bool = False, lang: str = "python") -> str:
    attr = ' data-run="offline"' if offline else ""
    out = ('<div class="nerdit-out"><span class="nerdit-tag">Python shows</span><p>A bar chart.</p></div>'
           if shown is None else
           f'<div class="nerdit-out"><span class="nerdit-tag">Python shows</span><pre><code>{shown}</code></pre></div>')
    return (f'<div class="nerdit-run"{attr}><div class="nerdit-in"><span class="nerdit-tag">You type</span>'
            f'<pre data-lang="{lang}"><button class="nerdit-copy-btn">Copy</button><code>{code}</code></pre></div>'
            f'{out}</div>')


def tryit(code: str, runner: str = "nerditRunPython", lang: str = ' data-lang="python"') -> str:
    return (f'<div class="nerdit-tryit"{lang}><textarea class="nerdit-tryit-editor">\n{code}</textarea>'
            f'<div class="nerdit-tryit-bar"><button class="nerdit-run-btn" onclick="{runner}(this)">Run</button>'
            '</div><div class="nerdit-tryit-result"></div></div>')


def dataset() -> str:
    recipe = {"seed": 7, "files": {"orders.csv": {"entity": "orders"}}, "world": world()}
    return f'<script type="application/json" class="nerdit-dataset">{json.dumps(recipe)}</script>'


def lesson(*parts: str) -> str:
    return '<div class="nerdit-wrapper nerdit-simple">' + "".join(parts) + "</div>"


READ = "import pandas as pd\ndf = pd.read_csv(&quot;orders.csv&quot;)\nprint(df.shape)"


def test_python_parts_finds_runs_tryits_offline_and_dataset():
    html = lesson(dataset(), run_line(READ, "(5, 7)"), run_line("plt.bar([1], [2])", None),
                  run_line("import tensorflow", "2.16", offline=True), run_line("SELECT 1;", "1", lang="sql"),
                  tryit("x = 1 &lt; 2\nprint(x)"), tryit("plt.plot([1])", "nerditRunPlot"),
                  tryit("SELECT 1;", "nerditRunSQL", ' data-seed="s1"'))
    parts = python_parts(html)
    assert parts["dataset"]["files"] == {"orders.csv": {"entity": "orders"}}
    assert [r["code"] for r in parts["runs"]] == [READ.replace("&quot;", '"'), "plt.bar([1], [2])", "import tensorflow"]
    assert [r["shown"] for r in parts["runs"]] == ["(5, 7)", None, "2.16"]
    assert [r["offline"] for r in parts["runs"]] == [False, False, True]
    assert parts["tryits"][0] == "x = 1 < 2\nprint(x)"  # the browser drops the newline after <textarea>
    assert len(parts["tryits"]) == 2 and parts["tryits"][1].endswith("plt.plot([1])")
    assert "import matplotlib.pyplot as plt" in parts["tryits"][1]  # the plot runner's prelude
    assert python_parts(lesson(run_line("SELECT 1;", "1", lang="sql")))["runs"] == []


def test_normalise_trims_layout_only():
    assert normalise("a  \r\nb\t\n\n\n") == "a\nb"
    assert normalise("  x\n\ny") == "  x\n\ny"
    assert normalise("") == ""


def test_missing_engine_exits_2(tmp_path):
    course = tmp_path / "course.json"
    course.write_text(json.dumps({"lessons": [{"id": "p1", "content": lesson(run_line("print(1)", "1"))}]}),
                      encoding="utf-8")
    env = dict(os.environ, NERDIT_PYODIDE_DIR=str(tmp_path))
    r = subprocess.run([sys.executable, str(HERE / "check_python_outputs.py"), "--course", str(course)],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 2 and "npm ci" in r.stderr


def test_unreadable_course_exits_2(tmp_path):
    r = subprocess.run([sys.executable, str(HERE / "check_python_outputs.py"), "--course", str(tmp_path / "no.json")],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2


GOOD = lesson(dataset(), run_line(READ, "(5, 7)"), run_line("print(len(df))", "5"),
              tryit('import pandas as pd\nprint(pd.read_csv("orders.csv").head(2))'))


@engine
def test_matching_outputs_pass():
    r = check_lesson(GOOD)
    assert r["examples"] == 2 and r["match"] == 2, r
    assert r["mismatch"] == [] and r["tryit_fail"] == []


@engine
def test_changed_number_fails(tmp_path):
    r = check_lesson(GOOD.replace("(5, 7)", "(5, 8)"))
    assert r["match"] == 1 and len(r["mismatch"]) == 1 and "(5, 8)" in r["mismatch"][0]
    course = tmp_path / "course.json"
    course.write_text(json.dumps({"lessons": [{"id": "good", "content": GOOD},
                                              {"id": "bad", "content": GOOD.replace("(5, 7)", "(5, 8)")}]}),
                      encoding="utf-8")
    cli = [sys.executable, str(HERE / "check_python_outputs.py"), "--course", str(course)]
    assert subprocess.run(cli + ["--lesson", "good"], capture_output=True).returncode == 0
    bad = subprocess.run(cli, capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 1 and "bad:" in bad.stdout


@engine
def test_shown_error_matches_last_line():
    shown = "Line 1 — ZeroDivisionError: division by zero"
    assert check_lesson(lesson(run_line("print(1 / 0)", shown)))["match"] == 1
    r = check_lesson(lesson(run_line("print(1 / 0)", "Line 1 — ValueError: nope")))
    assert r["match"] == 0 and "ZeroDivisionError" in r["mismatch"][0]


@engine
def test_failing_tryit_starter_fails():
    r = check_lesson(lesson(tryit("print(undefined_name)"), tryit("print('fine')")))
    assert len(r["tryit_fail"]) == 1 and "NameError" in r["tryit_fail"][0] and "Try It 1" in r["tryit_fail"][0]


@engine
def test_figure_run_needs_a_figure():
    draws = "import matplotlib.pyplot as plt\nplt.bar([&quot;a&quot;], [2])\nplt.show()"
    assert check_lesson(lesson(run_line(draws, None)))["match"] == 1
    r = check_lesson(lesson(run_line("x = 1", None)))
    assert r["match"] == 0 and "figure" in r["mismatch"][0]


@engine
def test_offline_runs_are_reported_not_passed():
    r = check_lesson(lesson(run_line("import tensorflow as tf\nprint(tf.__version__)", "2.16.1", offline=True)))
    assert r["examples"] == 1 and r["match"] == 0 and r["mismatch"] == []
    assert len(r["offline"]) == 1 and "offline" in r["offline"][0]


@engine
def test_runaway_code_times_out():
    start = time.monotonic()
    r = check_lesson(lesson(run_line("while True:\n    pass", "")), timeout=5)
    assert any("timed out" in m for m in r["mismatch"])
    assert time.monotonic() - start < 20


@engine
def test_probe_prints_versions():
    r = subprocess.run([sys.executable, str(HERE / "check_python_outputs.py"), "--probe", "numpy,nosuchmod"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    assert "numpy " in r.stdout and "nosuchmod: cannot load" in r.stdout


# ---- Final review fixes --------------------------------------------------------------------

def test_python_parts_accepts_py_and_any_case():
    html = lesson(run_line("print(1)", "1", lang="py"), run_line("print(2)", "2", lang=" Python "),
                  tryit("print(3)", lang=' data-lang="Py"'))
    parts = python_parts(html)
    assert [r["code"] for r in parts["runs"]] == ["print(1)", "print(2)"] and parts["tryits"] == ["print(3)"]


def test_a_recipe_the_generator_cannot_build_is_reported(monkeypatch):
    import check_python_outputs

    def broken(recipe):
        raise KeyError("z")
    monkeypatch.setattr(check_python_outputs, "build_files", broken)
    r = check_lesson(GOOD)
    assert r["mismatch"] and "dataset block" in r["mismatch"][0]


@engine
def test_tryit_does_not_see_files_or_modules_from_run_lines():
    html = lesson(dataset(), run_line("open(&quot;clean.csv&quot;, &quot;w&quot;).write(&quot;a&quot;)\nprint(&quot;saved&quot;)",
                                      "saved"),
                  tryit('print(open("clean.csv").read())'), tryit('print(open("orders.csv").read()[:8])'))
    r = check_lesson(html)
    assert r["match"] == 1
    assert len(r["tryit_fail"]) == 1 and "FileNotFoundError" in r["tryit_fail"][0] and "Try It 1" in r["tryit_fail"][0]


@engine
def test_mismatch_report_carries_the_full_output(tmp_path):
    html = lesson(run_line("print(&quot;x&quot; * 120)", "y"))
    r = check_lesson(html)
    assert r["details"] == [{"example": 1, "shown": "y", "printed": "x" * 120}]
    course = tmp_path / "course.json"
    course.write_text(json.dumps({"lessons": [{"id": "long", "content": html}]}), encoding="utf-8")
    out = subprocess.run([sys.executable, str(HERE / "check_python_outputs.py"), "--course", str(course)],
                         capture_output=True, text=True, encoding="utf-8").stdout
    assert "Python prints:" in out and "x" * 120 in out


@pytest.fixture
def offline_engine(tmp_path, monkeypatch):
    """An engine with an empty package cache on a machine with no network."""
    import shutil
    from pyodide_engine import ENGINE_DIR
    shutil.copytree(ENGINE_DIR / "node_modules" / "pyodide", tmp_path / "node_modules" / "pyodide")
    monkeypatch.setenv("NERDIT_PYODIDE_DIR", str(tmp_path))
    monkeypatch.setenv("NERDIT_PYODIDE_NO_NETWORK", "1")
    return tmp_path


@engine
def test_cold_cache_without_network_exits_2(offline_engine, tmp_path):
    from pyodide_engine import EngineError, run_job
    with pytest.raises(EngineError, match="download"):
        run_job({"files": {}, "steps": [{"id": "a", "code": "import pandas", "fresh": True}], "probe": []})
    course = tmp_path / "course.json"
    course.write_text(json.dumps({"lessons": [{"id": "p", "content": lesson(run_line(READ, "(5, 7)"))}]}),
                      encoding="utf-8")
    cli = [sys.executable, str(HERE / "check_python_outputs.py")]
    r = subprocess.run(cli + ["--course", str(course)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2 and "download" in r.stderr
    assert subprocess.run(cli + ["--probe", "pandas"], capture_output=True).returncode == 2
    plain = run_job({"files": {}, "steps": [{"id": "a", "code": "print(6 * 7)", "fresh": True}], "probe": []})
    assert plain["results"][0]["stdout"] == "42"  # the core itself needs no download


# Check a: every answer on the page runs (practice solutions, predict answers, fill-ins).

def task(prompt: str, code: str, shown: str | None = None) -> str:
    out = (f'<div class="nerdit-out"><span class="nerdit-tag">Python shows</span><pre><code>{shown}</code></pre></div>'
           if shown is not None else '')
    return (f'<div class="nerdit-task">{prompt}<details class="nerdit-solution"><summary>Show solution</summary>'
            f'<pre data-lang="python"><code>{code}</code></pre>{out}</details></div>')


def predict(code: str, shown: str | None) -> str:
    out = (f'<div class="nerdit-out"><span class="nerdit-tag">Python shows</span><pre><code>{shown}</code></pre></div>'
           if shown is not None else '<div class="nerdit-out"><div class="nerdit-answer">10</div></div>')
    return (f'<div class="nerdit-predict"><div class="nerdit-predict-head">Predict</div>'
            f'<pre data-lang="python"><code>{code}</code></pre>'
            f'<details class="nerdit-predict-answer"><summary>Show answer</summary>{out}</details></div>')


def fillblank(before: str, answer: str, after: str) -> str:
    return (f'<div class="nerdit-fillblank" data-answer="{answer}"><pre data-lang="python"><code>{before}'
            f'<input class="nerdit-blank" size="7" aria-label="your answer">{after}</code></pre></div>')


def test_python_parts_finds_answers_in_page_order():
    html = lesson(run_line("x = 2", ""), predict("print(x * 5)", "10"), fillblank("print(x ", "+|plus", " 1)"),
                  run_line("y = 3", ""), task("Task 1: Print x.", "print(x)", "2"))
    answers = python_parts(html)["answers"]
    assert [(a["kind"], a["code"], a["shown"], a["after"]) for a in answers] == [
        ("predict", "print(x * 5)", "10", 1), ("fill-in", "print(x + 1)", None, 1),
        ("practice", "print(x)", "2", 2)]


@engine
def test_practice_answers_run_after_the_run_lines():
    good = lesson(dataset(), run_line(READ, "(5, 7)"), task("Task 1: Count rows.", "print(len(df))", "5"),
                  task("Task 2: Columns.", "print(df.shape[1])", "7"))
    r = check_lesson(good)
    assert r["answers"] == 2 and r["answer_fail"] == [], r
    r = check_lesson(good.replace("<code>5</code>", "<code>6</code>"))
    assert len(r["answer_fail"]) == 1 and "practice task 1" in r["answer_fail"][0] and "'6'" in r["answer_fail"][0]
    r = check_lesson(lesson(task("Task 1: Oops.", "print(missing)")))
    assert "NameError" in r["answer_fail"][0]


@engine
def test_predict_and_fill_in_answers_run_in_place():
    html = lesson(run_line("x = 2", ""), predict("x = 5\nprint(x * 2)", "10"), run_line("print(x)", "2"),
                  fillblank("print(x ", "+", " 1)"), predict("print(x)", "2"))
    r = check_lesson(html)
    assert r["match"] == 2 and r["mismatch"] == [], r  # the predict's x = 5 never reaches the run lines
    assert r["answers"] == 3 and r["answer_fail"] == [], r
    r = check_lesson(html.replace("<code>10</code>", "<code>12</code>"))
    assert len(r["answer_fail"]) == 1 and "predict 1" in r["answer_fail"][0]
    r = check_lesson(lesson(run_line("x = 2", ""), fillblank("print(x ", "plus", " 1)")))
    assert "fill-in 1" in r["answer_fail"][0] and "SyntaxError" in r["answer_fail"][0]


@engine
def test_answers_must_show_their_output_strictly():
    # CORE.md §8: a revealed solution shows the work and its result, so the result is compared.
    r = check_lesson(lesson(run_line("x = 2", ""), task("Task 1: Show x.", "print(x)")))
    assert len(r["answer_fail"]) == 1 and "shows no output" in r["answer_fail"][0], r
    r = check_lesson(lesson(run_line("x = 2", ""), predict("print(x * 5)", None)))
    assert "predict 1" in r["answer_fail"][0] and "shows no output" in r["answer_fail"][0]
    chart = "import matplotlib.pyplot as plt\nplt.bar([&quot;a&quot;], [2])\nplt.show()"
    r = check_lesson(lesson(task("Task 1: Draw it.", chart)))
    assert r["answer_fail"] == [], r  # a chart answer is checked by drawing its figure
    r = check_lesson(lesson(task("Task 1: Draw it.", "x = 1")))
    assert "shows no output" in r["answer_fail"][0]
