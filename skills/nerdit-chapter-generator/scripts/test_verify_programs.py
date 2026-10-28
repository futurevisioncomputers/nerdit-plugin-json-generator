"""verify_programs: the program run line rules (CORE.md §4, spec 2026-10-28 §3-4)."""
from test_check_python_outputs import lesson, program_line, run_line
from verify_course import Report, verify_density, verify_programs

APP = "\n".join(["from flask import Flask", "app = Flask(__name__)", 'if __name__ == "__main__":',
                 "    app.run()"])
CHECK = "print(app.name)"


def report(*parts, new_course=False, runner="python", focus="hands-on"):
    rep = Report()
    out = {"lessons": [{"id": "x", "content": lesson(*parts)}]}
    inp = [{"id": "x", "runner": runner, "focus": focus}]
    verify_programs(rep, out, inp, new_course)
    verify_density(rep, out, inp)
    return rep


def test_a_good_program_passes():
    rep = report(program_line(APP, CHECK, "form_app"))
    assert rep.failures == [] and rep.warnings == []


def test_a_program_needs_a_file_name():
    assert any("data-file" in f for f in report(program_line(APP, CHECK, file=None)).failures)


def test_a_program_is_at_most_80_lines():
    code = "\n".join(f"x{i} = {i}" for i in range(81))
    assert any("80" in f for f in report(program_line(code, None, offline=False)).failures)


def test_at_most_two_programs_per_lesson():
    parts = [program_line(APP, CHECK, file=f"app{i}.py") for i in range(3)]
    assert any("2 programs" in f for f in report(*parts).failures)


def test_a_checked_program_needs_its_entry_point():
    assert any("__main__" in f for f in report(program_line("x = 1", CHECK)).failures)


def test_a_checked_program_runs_offline():
    assert any("offline" in f for f in report(program_line(APP, CHECK, offline=False)).failures)


def test_a_long_program_is_exempt_from_the_block_cap():
    code = "\n".join(f"x{i} = {i}" for i in range(70))
    rep = report(program_line(code, None, offline=False))
    assert not any("shows 70 lines" in w for w in rep.warnings)


def test_render_template_in_a_lesson_program_warns():
    code = APP.replace("app = Flask(__name__)", "app = Flask(__name__)\nhtml = render_template('a.html')")
    assert any("render_template" in w for w in report(program_line(code, CHECK)).warnings)


def test_fake_runtime_outside_a_program_warns_but_not_inside():
    fake = "with app.test_request_context('/'):\n    print(1)"
    assert any("test_request_context" in w for w in report(run_line(fake, "1")).warnings)
    inside = APP + "\n" + fake.replace("\n", "\n    ")
    assert not any("test_request_context" in w for w in report(program_line(inside, CHECK)).warnings)


CELLS = [run_line("import pandas as pd\ndf = pd.read_csv('a.csv')", ""), run_line("print(df.shape)", "(1, 1)"),
         run_line("print(df.columns)", "x"), run_line("print(len(df))", "1")]


def test_a_cell_style_lesson_without_a_program_fails_for_a_new_course():
    assert any("whole script" in f for f in report(*CELLS, new_course=True).failures)
    rep = report(*CELLS)
    assert rep.failures == [] and any("whole script" in w for w in rep.warnings)


def test_a_cell_style_lesson_with_its_whole_script_passes():
    script = "import pandas as pd\ndf = pd.read_csv('a.csv')\nprint(df.shape)"
    rep = report(*CELLS, program_line(script, None, file="L01-script.py", offline=False), new_course=True)
    assert not any("whole script" in f for f in rep.failures)


def test_a_concept_lesson_needs_no_whole_script():
    rep = report(*CELLS, new_course=True, focus="concept")
    assert not any("whole script" in f for f in rep.failures)
