import json

import check_code_prose as cp
import fold_repeats as fr
from test_check_python_outputs import program_line

SETUP = "from flask import Flask\napp = Flask(__name__)"


def page(*sections):
    body = "".join(f"<section><h2>{n} — Part</h2>{''.join(parts)}</section>" for n, parts in sections)
    return f'<div class="nerdit-wrapper nerdit-simple">{body}</div>'


def walk(*lines, full=False):
    cls = "nerdit-codewalk nerdit-walk-full" if full else "nerdit-codewalk"
    return f'<ol class="{cls}">' + "".join(f"<li><code>{ln}</code> does a step.</li>" for ln in lines) + "</ol>"


def lesson(lid, html):
    return {"id": lid, "content": html}


def clean(lessons):
    return cp.repeat_problems(lessons, new_course=True) == ([], [])


def test_a_short_walk_drops_steps_an_earlier_lesson_explained():
    first = lesson("L1", page((1, [walk("x = 1", "y = 2")])))
    later = lesson("L2", page((1, [walk("x = 1", "z = 3")])))
    course = [first, later]
    assert not clean(course)
    folded = fr.fold_course(course)
    assert folded == 1
    assert first["content"] == page((1, [walk("x = 1", "y = 2")]))
    assert "<code>x = 1</code>" not in later["content"] and "<code>z = 3</code>" in later["content"]
    assert clean(course)


def test_a_short_walk_with_only_old_lines_is_removed():
    course = [lesson("L1", page((1, [walk("x = 1")]))), lesson("L2", page((1, ["<p>Again.</p>", walk("x = 1")])))]
    fr.fold_course(course)
    assert "nerdit-codewalk" not in course[1]["content"] and "<p>Again.</p>" in course[1]["content"]


def test_a_full_walk_folds_old_lines_into_one_pointer_step():
    first = lesson("L1", page((1, [program_line(SETUP, None, offline=False),
                                   walk("from flask import Flask", "app = Flask(__name__)", full=True)])))
    code = SETUP + "\nx = 1"
    later = lesson("L2", page((1, [program_line(code, None, offline=False),
                                   walk("from flask import Flask", "app = Flask(__name__)", "x = 1", full=True)])))
    course = [first, later]
    fr.fold_course(course)
    html = later["content"]
    assert html.count("<li") == 2
    assert '<li class="nerdit-walk-seen"><code>from flask import Flask</code> explained in Lesson 1.</li>' in html
    assert clean(course)
    assert cp.walk_problems(html, new_course=True) == ([], [])


def test_a_repeat_inside_the_lesson_points_at_its_section():
    html = page((1, [walk("x = 1", "y = 2")]),
                (2, [program_line("x = 1\nz = 3", None, offline=False), walk("x = 1", "z = 3", full=True)]))
    course = [lesson("L1", html)]
    fr.fold_course(course)
    assert "<code>x = 1</code> explained in section 1 above.</li>" in course[0]["content"]
    assert clean(course)


def test_a_full_walk_step_that_also_covers_new_lines_is_kept():
    first = lesson("L1", page((1, [walk("x = 1")])))
    # The step quoting `x = 1` also covers `y = 2`, which nothing explained yet.
    later = lesson("L2", page((1, [program_line("x = 1\ny = 2\nz = 3", None, offline=False),
                                   walk("x = 1", "z = 3", full=True)])))
    before = later["content"]
    fr.fold_course([first, later])
    assert later["content"] == before
    assert clean([first, later])   # the checker agrees: it explains a new line, so it is no repeat


def test_folding_twice_changes_nothing_more():
    course = [lesson("L1", page((1, [walk("x = 1", "y = 2")]))),
              lesson("L2", page((1, [program_line(SETUP + "\nx = 1", None, offline=False),
                                     walk("from flask import Flask", "x = 1", full=True)])))]
    course.insert(0, lesson("L0", page((1, [walk("from flask import Flask", "app = Flask(__name__)")]))))
    fr.fold_course(course)
    once = [l["content"] for l in course]
    assert fr.fold_course(course) == 0
    assert [l["content"] for l in course] == once


def test_cli_rewrites_the_course_file(tmp_path, capsys):
    path = tmp_path / "course.json"
    course = {"lessons": [lesson("L1", page((1, [walk("x = 1", "y = 2")]))),
                          lesson("L2", page((1, [walk("x = 1", "z = 3")])))]}
    path.write_text(json.dumps(course), encoding="utf-8")
    assert fr.main(["--course", str(path), "--dry-run"]) == 0
    assert json.loads(path.read_text(encoding="utf-8")) == course
    assert fr.main(["--course", str(path)]) == 0
    assert "<code>x = 1</code>" not in json.loads(path.read_text(encoding="utf-8"))["lessons"][1]["content"]
    assert "1 walk step(s)" in capsys.readouterr().out
