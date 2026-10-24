import json

import pytest

import check_quiz as cq
from pyodide_engine import engine_available
from test_check_python_outputs import lesson, run_line

AVAILABLE, REASON = engine_available()
engine = pytest.mark.skipif(not AVAILABLE, reason=REASON)

SEED = ('<script type="text/plain" id="tryit-seed-1">CREATE TABLE customers (id INT, city TEXT);\n'
        "INSERT INTO customers VALUES (1,'Surat'),(2,'Surat'),(3,'Pune');</script>")


def q(text, options, correct):
    return {'text': text, 'options': options, 'correctOptionIndex': correct}


def test_snippets_and_kind():
    assert cq.snippets('Given `x = [1, 2]`, what does `print(len(x))` show?') == ['x = [1, 2]', 'print(len(x))']
    assert cq.snippets('Run:\n```\nprint(2)\n```\nWhat shows?') == ['print(2)']
    assert cq.kind(['print(1)']) == 'python'
    assert cq.kind(["SELECT COUNT(*) FROM t WHERE c = 'x';"]) == 'sql'
    assert cq.kind(['=SUM(A1:A3)']) is None
    assert cq.kind([]) is None


def test_option_matching_strips_backticks_and_compares_numbers():
    assert cq.matching(['`2`', '3', '2.0 rows', "'2'"], '2') == [0]
    assert cq.matching(['20', '20.0', 'x'], '20') == [0, 1]


def test_sql_question_with_wrong_marked_option_fails():
    html = lesson(SEED)
    good = q("What does `SELECT COUNT(*) FROM customers WHERE city = 'Surat';` return?", ['3', '2', '1', '0'], 1)
    assert cq.check_questions(html, [('lesson q1', good)]) == ([], [])
    bad = dict(good, correctOptionIndex=0)
    fails, _ = cq.check_questions(html, [('lesson q1', bad)])
    assert fails and 'lesson q1' in fails[0] and "option 2 ('2')" in fails[0] and 'marks option 1' in fails[0]


def test_sql_multi_cell_result_is_not_judged():
    html = lesson(SEED)
    question = q('What does `SELECT id, city FROM customers;` show?', ['a', 'b', 'c', 'd'], 0)
    assert cq.check_questions(html, [('q', question)]) == ([], [])


def test_definitional_question_is_skipped():
    question = q('What does a primary key guarantee?', ['Unique rows', 'Speed', 'Order', 'Nothing'], 0)
    assert cq.check_questions(lesson(SEED), [('q', question)]) == ([], [])


@engine
def test_python_question_runs_after_the_lesson_run_lines():
    html = lesson(run_line('prices = [100, 250, 400]', ''))
    good = q('What does `print(sum(prices) // 3)` print?', ['250', '750', '`250.0`', '3'], 0)
    assert cq.check_questions(html, [('q1', good)]) == ([], [])
    fails, _ = cq.check_questions(html, [('q1', dict(good, correctOptionIndex=1))])
    assert "option 1 ('250')" in fails[0]
    error = q('What happens with `print(prices[5])`?', ['400', 'None', 'IndexError', 'KeyError'], 2)
    assert cq.check_questions(html, [('q2', error)]) == ([], [])
    nothing = q('What does `print(len(prices))` print?', ['2', '4', '5', '6'], 0)
    fails, warns = cq.check_questions(html, [('q3', nothing)])
    assert fails == [] and 'no option' in warns[0]


def test_cli_maps_assessment_questions_to_their_lesson(tmp_path):
    good = q("What does `SELECT COUNT(*) FROM customers WHERE city = 'Pune';` return?", ['1', '2', '3', '0'], 0)
    course = {'lessons': [{'id': 'sql-01', 'content': lesson(SEED), 'questions': [good]}],
              'assessment': {'questions': [dict(good, id='assessment-s-sql-01-q1-b', correctOptionIndex=2)]}}
    path = tmp_path / 'c.json'
    path.write_text(json.dumps(course), encoding='utf-8')
    assert cq.main(['--course', str(path)]) == 1
