from pathlib import Path
import json
import sys

import check_offline_outputs as co
from test_check_python_outputs import lesson, run_line


def test_offline_blocks_are_only_the_offline_run_lines():
    html = lesson(run_line("print(1)", "1"), run_line("import asyncio\nprint(2)", "2", offline=True))
    assert co.offline_blocks(html) == [{"code": "import asyncio\nprint(2)", "shown": "2"}]


def test_unpinned_libraries_are_named():
    code = "import asyncio\nimport fastapi\nfrom sklearn.linear_model import LinearRegression\nimport httpx2"
    reqs = "fastapi==0.120.0\n# comment\nHTTPX2>=1.0\n"
    assert co.unpinned([code], reqs) == ["scikit-learn (import sklearn)"]


def test_requirement_names_normalise():
    assert co.pinned_names("Scikit_Learn==1.7\npydantic[email]>=2\n-e ./x\n") == {"scikit-learn", "pydantic"}


def course(tmp_path, *parts):
    path = tmp_path / "course.json"
    path.write_text(json.dumps({"lessons": [{"id": "api-02", "content": lesson(*parts)}]}), encoding="utf-8")
    return path


def test_matching_offline_outputs_pass_in_a_real_venv(tmp_path):
    asyncio_code = ("import asyncio\nasync def main():\n    await asyncio.sleep(0)\n    return 3\n"
                    "print(asyncio.run(main()))")
    c = course(tmp_path, run_line(asyncio_code, "3", offline=True),
               run_line("print(asyncio.run(main()) * 2)", "6", offline=True))
    report = co.check_course(c, requirements="", pythons=[sys.executable], workdir=tmp_path / "w")
    assert report["problems"] == [], report
    assert report["examples"] == 2 and report["python"] == f"{sys.version_info[0]}.{sys.version_info[1]}"
    # A path names its interpreter's own version, not the checker's.
    other = co.resolve_python("3.11") if sys.version_info[:2] != (3, 11) else None
    if other:
        r311 = co.check_course(c, requirements="", pythons=[other], workdir=tmp_path / "w311")
        assert r311["python"] == "3.11", r311


# --workdir given as a relative path: the driver runs with cwd set to the lesson folder, so a
# driver path built from a relative workdir pointed nowhere and every lesson failed to run.
def test_a_relative_workdir_runs(tmp_path, monkeypatch):
    c = course(tmp_path, run_line("print(3)", "3", offline=True))
    monkeypatch.chdir(tmp_path)
    report = co.check_course(c, requirements="", pythons=[sys.executable], workdir=Path("w"))
    assert report["problems"] == [], report


def test_changed_output_shown_error_and_warning(tmp_path):
    c = course(tmp_path, run_line("print(41 + 1)", "41", offline=True),
               run_line("print(1 / 0)", "Line 1 — ZeroDivisionError: division by zero", offline=True),
               run_line("import warnings\nwarnings.warn('old', DeprecationWarning)\nprint('x')", "x", offline=True))
    problems = co.check_course(c, requirements="", pythons=[sys.executable], workdir=tmp_path / "w")["problems"]
    assert len(problems) == 2, problems
    assert "example 1" in problems[0] and "'41'" in problems[0] and "'42'" in problems[0]
    assert "example 3" in problems[1] and "DeprecationWarning" in problems[1]


def test_unpinned_library_fails_before_running(tmp_path):
    c = course(tmp_path, run_line("import fastapi\nprint(1)", "1", offline=True))
    report = co.check_course(c, requirements="", pythons=[sys.executable], workdir=tmp_path / "w")
    assert report["problems"] == ["api-02: fastapi is used but not pinned in the course requirements"]


# A lesson that reads its practice files (L02-S1-fees.csv) runs with the built pack's files beside it.
def test_files_dir_puts_the_lessons_pack_files_beside_its_examples(tmp_path):
    c = course(tmp_path, run_line('print(open("L01-S1-fees.csv").read().split())', "['fee', '9000']", offline=True))
    files = tmp_path / "files"
    files.mkdir()
    (files / "L01-S1-fees.csv").write_text("fee\n9000\n", encoding="utf-8")
    (files / "L02-S1-other.csv").write_text("x\n", encoding="utf-8")
    without = co.check_course(c, requirements="", pythons=[sys.executable], workdir=tmp_path / "w0")
    assert without["problems"] and "FileNotFoundError" in without["problems"][0]
    report = co.check_course(c, requirements="", pythons=[sys.executable], workdir=tmp_path / "w", files_dir=files)
    assert report["problems"] == [], report
    assert not (tmp_path / "w" / "lessons" / "api-02" / "L02-S1-other.csv").exists()


# The capstone page imports the project's own modules: they are not libraries to pin, and they import.
def test_capstone_modules_are_local_and_importable(tmp_path):
    spec = '<script type="application/json" class="nerdit-files-spec">{"files": [{"capstone": "capstone"}]}</script>'
    c = course(tmp_path, run_line("from report import total\nprint(total([1, 2]))", "3", offline=True))
    data = json.loads(c.read_text(encoding="utf-8"))
    data["lessons"][0]["content"] = spec + data["lessons"][0]["content"]
    c.write_text(json.dumps(data), encoding="utf-8")
    project = tmp_path / "capstone"
    (project / "solution").mkdir(parents=True)
    (project / "solution" / "report.py").write_text("def total(fees):\n    return sum(fees)\n", encoding="utf-8")
    assert co.check_course(c, requirements="", pythons=[sys.executable], workdir=tmp_path / "w0")["problems"] == [
        "api-02: report is used but not pinned in the course requirements"]
    report = co.check_course(c, requirements="", pythons=[sys.executable], workdir=tmp_path / "w", capstone=project)
    assert report["problems"] == [], report


# A logging handler made in one example keeps sys.stdout; its lines in a later example belong there.
def test_a_handler_from_an_earlier_example_prints_into_the_later_one(tmp_path):
    setup = ("import logging, sys\nlog = logging.getLogger('demo')\n"
             "log.addHandler(logging.StreamHandler(sys.stdout))\nlog.setLevel(logging.INFO)\nprint('ready')")
    c = course(tmp_path, run_line(setup, "ready", offline=True),
               run_line("log.info('GET /x -> 200')\nprint(200)", "GET /x -> 200\n200", offline=True))
    report = co.check_course(c, requirements="", pythons=[sys.executable], workdir=tmp_path / "w")
    assert report["problems"] == [], report


def test_cli_exit_codes(tmp_path):
    c = course(tmp_path, run_line("print(2)", "2", offline=True))
    assert co.main(["--course", str(c), "--pythons", sys.executable, "--workdir", str(tmp_path / "w")]) == 0
    assert co.main(["--course", str(c), "--pythons", "3.97", "--workdir", str(tmp_path / "w")]) == 2
