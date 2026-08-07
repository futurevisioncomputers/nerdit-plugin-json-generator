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
