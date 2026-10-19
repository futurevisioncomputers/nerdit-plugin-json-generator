import json

import pytest

from gate_lesson import gate

LESSON = """<div class="nerdit-wrapper nerdit-simple" style="counter-reset:practical-counter challenge-counter;">
<h1>Counting rows</h1>
<section><h2>1 — Count rows</h2>
<p>You count rows with one query.</p>
<div class="nerdit-figure" data-visual="value-table" style="max-width:440px"><table class="nerdit-vtable"><tr><td>3 rows</td><td>count 3</td></tr></table><div class="nerdit-figure-caption">Three rows give a count of 3.</div></div>
<h3 class="nerdit-runhead">SELECT 1 AS n <span class="why">— see one value come back</span></h3>
<p>The query returns the number one.</p>
<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span><pre data-lang="sql"><code>SELECT 1 AS n;</code></pre></div><div class="nerdit-out"><span class="nerdit-tag">SQL shows</span><pre><code>+---+
| n |
+---+
| 1 |
+---+</code></pre></div></div>
<div class="nerdit-predict"><div class="nerdit-predict-head">🤔 Try It</div><p>What does SELECT 2 return?</p><details class="nerdit-predict-answer"><summary>Show answer</summary><p>It returns 2.</p></details></div>
</section></div>"""


def q(text):
    return {"text": text, "options": ["A", "B", "C", "D"], "correctOptionIndex": 0}


QUIZ = {"lessonQuestions": [q("What does SELECT 1 return?"), q("Which word names a column?"), q("What ends a statement?")],
        "assessmentQuestions": [q("Which query counts rows?"), q("What does AS do?"), q("Which result shows one row?")]}
CONCEPTS = {"teaches": ["SELECT", "AS", "result table", "column alias", "statement"], "uses": []}


def setup(tmp_path, html=LESSON):
    d = tmp_path / "w"
    d.mkdir()
    (d / "c-01.html").write_text(html, encoding="utf-8")
    (d / "c-01.quiz.json").write_text(json.dumps(QUIZ), encoding="utf-8")
    (d / "c-01.concepts.json").write_text(json.dumps(CONCEPTS), encoding="utf-8")
    inp = tmp_path / "course-c_input.json"
    inp.write_text(json.dumps([{"id": "c-01", "title": "Counting rows",
                                "description": "Count the rows in a table with one short query and read the answer."}]),
                   encoding="utf-8")
    return inp, d


def test_a_clean_lesson_passes(tmp_path):
    inp, d = setup(tmp_path)
    fails, _ = gate(inp, d, "c-01")
    assert fails == []


def test_wrong_output_and_banned_phrase_fail(tmp_path):
    bad = LESSON.replace("| 1 |", "| 2 |").replace("You count rows", "You delve into rows")
    inp, d = setup(tmp_path, bad)
    fails, _ = gate(inp, d, "c-01")
    assert any(f.startswith("sql:") for f in fails)
    assert any(f.startswith("voice:") for f in fails)


def test_refresh_guard_runs_when_before_dir_is_given(tmp_path):
    inp, d = setup(tmp_path)
    before = tmp_path / "before"
    before.mkdir()
    for f in d.iterdir():
        (before / f.name).write_bytes(f.read_bytes())
    (d / "c-01.html").write_text(LESSON.replace("You count rows with one query.", "Rows get counted."),
                                 encoding="utf-8")
    fails, _ = gate(inp, d, "c-01", before_dir=before, modes={"figures"})
    assert any(f.startswith("refresh:") for f in fails)


def test_missing_lesson_file_raises(tmp_path):
    inp, d = setup(tmp_path)
    (d / "c-01.quiz.json").unlink()
    with pytest.raises(FileNotFoundError):
        gate(inp, d, "c-01")


def test_refresh_does_not_fail_on_a_banned_phrase_it_inherited(tmp_path):
    old = LESSON.replace("You count rows with one query.", "You count rows with one robust query.")
    inp, d = setup(tmp_path, old)
    before = tmp_path / "before"
    before.mkdir()
    for f in d.iterdir():
        (before / f.name).write_bytes(f.read_bytes())
    fails, warns = gate(inp, d, "c-01", before_dir=before, modes={"figures"})
    assert not any(f.startswith("voice:") for f in fails)
    assert any("robust" in w for w in warns)


from pyodide_engine import engine_available  # noqa: E402

PY_RUN = ('<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span>'
          '<pre data-lang="python"><code>print(2 + 2)</code></pre></div><div class="nerdit-out">'
          '<span class="nerdit-tag">Python shows</span><pre><code>4</code></pre></div></div>')
SQL_RUN = LESSON[LESSON.index('<div class="nerdit-run">'):LESSON.index('<div class="nerdit-predict">')]
PY_LESSON = LESSON.replace(SQL_RUN, PY_RUN).replace("SELECT 1 AS n <span", "print(2 + 2) <span")


@pytest.mark.skipif(not engine_available()[0], reason=engine_available()[1])
def test_gate_runs_python_checks(tmp_path):
    inp, d = setup(tmp_path, PY_LESSON)
    assert not [f for f in gate(inp, d, "c-01")[0] if f.startswith("python:")]
    (d / "c-01.html").write_text(PY_LESSON.replace("<code>4</code>", "<code>5</code>"), encoding="utf-8")
    assert any(f.startswith("python:") and "'5'" in f for f in gate(inp, d, "c-01")[0])


def test_gate_fails_when_engine_missing_for_python_lessons(tmp_path, monkeypatch):
    monkeypatch.setenv("NERDIT_PYODIDE_DIR", str(tmp_path))
    inp, d = setup(tmp_path, PY_LESSON)
    assert "python: engine missing (tools/pyodide/README.md)" in gate(inp, d, "c-01")[0]
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    inp, d = setup(sql_dir)  # an SQL lesson does not need the engine
    assert not [f for f in gate(inp, d, "c-01")[0] if f.startswith("python:")]
