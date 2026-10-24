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


def test_gate_reports_stale_screen(tmp_path):
    from render_screens import render_lesson
    from test_screens import ADS, ADS_TEXT, block
    with_screen = LESSON.replace("<p>You count rows with one query.</p>",
                                 f"<p>You count rows with one query.</p><p>{ADS_TEXT}</p>{block(ADS)}")
    drawn, problems = render_lesson(with_screen)
    assert problems == []
    stale = drawn.replace('"goal": "Start a sales campaign"', '"goal": "Begin a sales campaign"')
    inp, d = setup(tmp_path, stale)
    fails, _ = gate(inp, d, "c-01")
    assert "screen: ads-new: drawn screen is out of date; run render_screens.py" in fails


def test_gate_fails_an_svg_number_the_lesson_never_states_even_without_a_world(tmp_path):
    figure = ('<div class="nerdit-figure" data-visual="diagram" style="max-width:440px">'
              '<svg viewBox="0 0 300 60" role="img" aria-label="Row counts"><text x="10" y="30">3 rows</text>'
              '<text x="10" y="50">₹4,000</text></svg><div class="nerdit-figure-caption">Counts.</div></div>')
    with_figure = LESSON.replace("<p>You count rows with one query.</p>",
                                 "<p>You count rows with one query.</p>" + figure)
    inp, d = setup(tmp_path, with_figure)
    fails, _ = gate(inp, d, "c-01")
    assert "labels: figure svg 1: draws 4,000, which the lesson and its seed never state" in fails
    assert not any("draws 3," in f for f in fails)


# The gate runs every per-lesson accuracy check (plan checks a, c, f, g, h and prose-code).

def with_quiz(tmp_path, html, quiz):
    inp, d = setup(tmp_path, html)
    (d / "c-01.quiz.json").write_text(json.dumps(quiz), encoding="utf-8")
    return inp, d


def test_gate_fails_prose_naming_code_the_page_lacks(tmp_path):
    bad = LESSON.replace("<p>You count rows with one query.</p>",
                         "<p>You count rows with <code>COUNT(id)</code> in one query.</p>")
    inp, d = setup(tmp_path, bad)
    fails, _ = gate(inp, d, "c-01")
    assert any(f.startswith("prose-code:") and "COUNT(id)" in f for f in fails), fails


def test_gate_fails_a_wrongly_marked_quiz_answer(tmp_path):
    quiz = json.loads(json.dumps(QUIZ))
    quiz["lessonQuestions"][0] = {"text": "What does `SELECT 1 AS n;` return?", "options": ["0", "1", "2", "3"],
                                  "correctOptionIndex": 0}
    inp, d = with_quiz(tmp_path, LESSON.replace("<section>", '<script type="text/plain" id="s1">'
                                                "CREATE TABLE t (a INT);</script><section>", 1), quiz)
    fails, _ = gate(inp, d, "c-01")
    assert any(f.startswith("quiz:") and "option 2" in f for f in fails), fails


def test_gate_fails_deprecated_code_and_bad_file_names(tmp_path):
    spec = ('<script type="application/json" class="nerdit-files-spec">'
            '{"python": "3.12", "files": [{"name": "L02-S1-Wrong.csv", "from": {"json": []}}]}</script>')
    bad = LESSON.replace("<h1>Counting rows</h1>", "<h1>Counting rows</h1>" + spec).replace(
        "<p>The query returns the number one.</p>",
        '<p>The query returns the number one.</p><pre data-lang="python"><code>from datetime import datetime\n'
        'stamp = datetime.utcnow()</code></pre>')
    inp, d = setup(tmp_path, bad)
    fails, _ = gate(inp, d, "c-01")
    assert any(f.startswith("modern:") and "utcnow" in f for f in fails), fails
    assert any(f.startswith("files:") and "L01-" in f for f in fails), fails


def test_gate_fails_a_python_answer_with_no_output(tmp_path, monkeypatch):
    import gate_lesson
    monkeypatch.setattr(gate_lesson, "engine_available", lambda: (True, ""))
    monkeypatch.setattr(gate_lesson, "has_python", lambda html: True)
    monkeypatch.setattr(gate_lesson, "check_python", lambda html: {
        "mismatch": [], "tryit_fail": [], "offline": [], "answer_fail": ["practice task 1: shows no output"]})
    inp, d = setup(tmp_path)
    fails, _ = gate(inp, d, "c-01")
    assert "python: practice task 1: shows no output" in fails
