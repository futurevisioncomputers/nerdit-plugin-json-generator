import json
import os
import subprocess
import sys

from check_input import audit

SCRIPT = os.path.join(os.path.dirname(__file__), "check_input.py")

GOOD = [
    {"id": "a-01", "title": "Variables and Values",
     "description": "Store a value in a name you choose, then read it back later."},
    {"id": "a-02", "title": "Conditions with if",
     "description": "Run a block of code only when a test turns out true."},
]


def test_clean_input_has_no_findings():
    assert audit(GOOD) == []


def test_description_identical_to_title_is_an_error():
    bad = [dict(GOOD[0], description=GOOD[0]["title"])] + GOOD[1:]
    sev, lid, msg = audit(bad)[0]
    assert (sev, lid) == ("ERROR", "a-01")
    assert "description repeats the title" in msg


def test_short_description_is_a_warning():
    bad = [dict(GOOD[0], description="Learn variables.")] + GOOD[1:]
    assert [(s, i) for s, i, _ in audit(bad)] == [("WARN", "a-01")]


def test_missing_description_is_an_error():
    bad = [{"id": "a-01", "title": "Variables and Values"}] + GOOD[1:]
    assert audit(bad)[0][0] == "ERROR"


def test_duplicate_id_is_an_error():
    bad = GOOD + [dict(GOOD[0])]
    assert any(s == "ERROR" and "duplicate id" in m for s, _, m in audit(bad))


def test_missing_title_is_an_error():
    bad = [{"id": "a-01", "description": "A long enough description of the lesson here."}]
    assert any(s == "ERROR" and "missing title" in m for s, _, m in audit(bad))


def test_lessons_sharing_vocabulary_are_not_flagged():
    # The pre-flight judges description quality only. Deciding that one of these lessons
    # should come first is a job for the orchestrator and check_sequence.py, which have
    # the titles in order and the generated lessons respectively.
    lessons = [
        {"id": "x-01", "title": "Building a REST API with Chains",
         "description": "Use LLMChain to serve a web route that answers user questions "
                        "over HTTP."},
        {"id": "x-02", "title": "Chains and Sequential Workflows",
         "description": "Introduce LLMChain and compose several small steps into one "
                        "longer sequential workflow."},
    ]
    assert audit(lessons) == []


def test_description_word_count_boundary_is_inclusive():
    twelve = " ".join(["word"] * 12)
    assert audit([{"id": "b-01", "title": "T", "description": twelve}]) == []
    eleven = " ".join(["word"] * 11)
    assert audit([{"id": "b-01", "title": "T", "description": eleven}])[0][0] == "WARN"


def test_title_echo_detection_ignores_case_and_whitespace():
    lessons = [{"id": "c-01", "title": "Loops and Iteration",
                "description": "  loops   AND iteration \n"}]
    assert any("repeats the title" in m for _, _, m in audit(lessons))


def _write(tmp_path, lessons):
    p = tmp_path / "in.json"
    p.write_text(json.dumps(lessons), encoding="utf-8")
    return p


def test_cli_strict_exits_two_on_error(tmp_path):
    p = _write(tmp_path, [dict(GOOD[0], description=GOOD[0]["title"])] + GOOD[1:])
    r = subprocess.run([sys.executable, SCRIPT, "--input", str(p), "--strict"],
                       capture_output=True, text=True)
    assert r.returncode == 2
    assert "ERROR" in r.stdout


def test_cli_without_strict_reports_but_exits_zero(tmp_path):
    p = _write(tmp_path, [dict(GOOD[0], description=GOOD[0]["title"])] + GOOD[1:])
    r = subprocess.run([sys.executable, SCRIPT, "--input", str(p)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "1 error(s)" in r.stdout


def test_cli_clean_exits_zero(tmp_path):
    p = _write(tmp_path, GOOD)
    r = subprocess.run([sys.executable, SCRIPT, "--input", str(p), "--strict"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "clean" in r.stdout


def test_cli_warning_only_input_exits_zero_under_strict(tmp_path):
    p = _write(tmp_path, [dict(GOOD[0], description="Learn variables.")] + GOOD[1:])
    r = subprocess.run([sys.executable, SCRIPT, "--input", str(p), "--strict"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "WARN" in r.stdout


def test_focus_must_be_concept_or_hands_on():
    bad = [dict(GOOD[0], focus="theory")] + GOOD[1:]
    sev, lid, msg = audit(bad)[0]
    assert (sev, lid) == ("ERROR", "a-01") and "unknown focus" in msg
    assert audit([dict(GOOD[0], focus="concept"), dict(GOOD[1], focus="hands-on")]) == []


# Check c and the capstone (plan decisions 8 and 9).

CODE = [dict(GOOD[0], runner="python"), dict(GOOD[1], runner="python"),
        {"id": "a-03", "title": "Capstone: The Fee Report", "focus": "project", "runner": "python",
         "description": "Build one report from the enquiries data that uses every chapter of the course."}]


def test_project_focus_is_allowed_only_as_the_single_last_chapter():
    assert audit(CODE, world_declared=True) == []
    moved = [CODE[2], CODE[0], CODE[1]]
    assert any(s == "ERROR" and "last chapter" in m for s, _, m in audit(moved, world_declared=True))
    two = CODE + [dict(CODE[2], id="a-04")]
    assert any(s == "ERROR" and "one capstone" in m for s, _, m in audit(two, world_declared=True))


def test_code_course_without_capstone_is_a_warning():
    findings = audit(CODE[:2], world_declared=True)
    assert [(s, m) for s, _, m in findings if "capstone" in m] and all(s == "WARN" for s, _, _ in findings)


def test_code_course_needs_a_world():
    assert any(s == "ERROR" and "world" in m for s, _, m in audit(CODE, world_declared=False))
    assert audit(GOOD, world_declared=False) == []  # no runner, no preset: not a code course


def test_cli_finds_the_sibling_world_file(tmp_path):
    p = tmp_path / "course-fees_input.json"
    p.write_text(json.dumps(CODE), encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "--input", str(p), "--strict"], capture_output=True, text=True)
    assert r.returncode == 2 and "world" in r.stdout
    (tmp_path / "course-fees_world.json").write_text(json.dumps({"use": "fvc-institute"}), encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "--input", str(p), "--strict"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
