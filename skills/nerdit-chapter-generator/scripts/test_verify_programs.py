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
    rep = report(SETUP, program_line(APP, CHECK, "form_app"), RUN_IT, new_course=True)
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
    assert any("python L01-script.py" in f for f in rep.failures)   # every program says how to run it


def test_a_concept_lesson_needs_no_whole_script():
    rep = report(*CELLS, new_course=True, focus="concept")
    assert not any("whole script" in f for f in rep.failures)


# Spec 2026-10-30: real folders, a run-it block after every program, setup before the first one.
SERVER = APP   # has the entry point and app.run()
RUN_IT = ('<div class="nerdit-terminal"><span class="nerdit-prompt">$ </span>'
          '<span class="nerdit-cmd">python form_app.py</span></div>')
SETUP = ('<div class="nerdit-terminal"><span class="nerdit-prompt">$ </span>'
         '<span class="nerdit-cmd">pip install flask</span></div>')


def course_report(*lessons, new_course=True):
    rep = Report()
    out = {"lessons": [{"id": f"x{i}", "content": lesson(*parts)} for i, parts in enumerate(lessons)]}
    inp = [{"id": f"x{i}", "runner": "python", "focus": "hands-on"} for i in range(len(lessons))]
    verify_programs(rep, out, inp, new_course)
    return rep


def test_companion_files_pass_and_silence_the_render_template_warning():
    code = APP.replace("app = Flask(__name__)", "app = Flask(__name__)\nhtml = render_template('a.html')")
    rep = report(SETUP, program_line(code, CHECK, files=(("templates/a.html", "<p>x</p>", "html"),)), RUN_IT,
                 new_course=True)
    assert rep.failures == [] and rep.warnings == [], (rep.failures, rep.warnings)


def test_a_companion_path_stays_inside_the_folder():
    for bad in ("../a.html", "/etc/a.html", "C:/a.html", "templates\a.html"):
        rep = report(program_line(APP, CHECK, files=((bad, "x", "html"),)))
        assert any("companion" in f for f in rep.failures), bad


def test_a_companion_file_is_at_most_80_lines():
    big = "\n".join("<p>x</p>" for _ in range(81))
    assert any("80" in f for f in report(program_line(APP, CHECK, files=(("templates/a.html", big, "html"),))).failures)


def test_two_programs_cannot_ship_the_same_companion_path():
    one = program_line(APP, CHECK, file="a.py", files=(("templates/i.html", "x", "html"),))
    two = program_line(APP, CHECK, file="b.py", files=(("templates/i.html", "y", "html"),))
    assert any("templates/i.html" in f for f in report(one, two).failures)


def test_a_server_program_needs_its_run_it_block():
    rep = course_report([SETUP, program_line(SERVER, CHECK)])
    assert any("python form_app.py" in f for f in rep.failures)
    assert course_report([SETUP, program_line(SERVER, CHECK), RUN_IT]).failures == []
    old = course_report([SETUP, program_line(SERVER, CHECK)], new_course=False)
    assert old.failures == [] and any("python form_app.py" in w for w in old.warnings)


def test_the_run_it_block_belongs_to_the_program_before_it():
    later = program_line(SERVER, CHECK, file="b.py")
    rep = course_report([SETUP, program_line(SERVER, CHECK), later, RUN_IT])
    assert any("python form_app.py" in f for f in rep.failures)


def test_setup_comes_before_the_first_server_program():
    assert any("pip install" in f for f in course_report([program_line(SERVER, CHECK), RUN_IT]).failures)
    assert course_report([SETUP], [program_line(SERVER, CHECK), RUN_IT]).failures == []
    late = course_report([program_line(SERVER, CHECK), RUN_IT], [SETUP])
    assert any("pip install" in f for f in late.failures)


def test_every_program_needs_its_run_it_block_not_only_servers():
    script = 'def f():\n    return 1\nif __name__ == "__main__":\n    print(f())'
    rep = course_report([SETUP, program_line(script, "print(f())", "1", file="s.py")])
    assert any("python s.py" in f for f in rep.failures)
    run = RUN_IT.replace("form_app.py", "s.py")
    assert course_report([SETUP, program_line(script, "print(f())", "1", file="s.py"), run]).failures == []


def test_other_run_commands_count():
    for cmd in ("uvicorn main:app --reload", "streamlit run main.py", "flask --app main run",
                "fastapi dev main.py", "python3 main.py", "py main.py", "python src/main.py"):
        run = RUN_IT.replace("python form_app.py", cmd)
        rep = course_report([SETUP, program_line(SERVER, CHECK, file="main.py"), run])
        assert rep.failures == [], (cmd, rep.failures)


def test_a_test_client_fragment_warns():
    frag = "client = app.test_client()\nprint(client.get('/').status_code)"
    assert any("test_client" in w for w in report(run_line(frag, "200")).warnings)


def test_setup_from_an_earlier_lesson_outside_this_report_counts():
    rep = Report()
    out = {"lessons": [{"id": "x", "content": lesson(program_line(SERVER, CHECK), RUN_IT)}]}
    verify_programs(rep, out, [{"id": "x", "runner": "python"}], True, setup_seen=True)
    assert rep.failures == []
