import json
import os
import subprocess
import sys

import pytest

from assemble_course import (
    build_course, detect_assets, estimate_duration, doc_size_report, load_quiz,
    MAX_DOC_BYTES,
)


def _q(t):
    return {"text": t, "options": ["a", "b", "c", "d"], "correctOptionIndex": 0}


def test_detect_assets():
    # The website serves these from public/ at the site root, not from /assets/js.
    assert detect_assets("uses nerdit-plot-runner.js here") == ["/nerdit-plot-runner.js"]
    assert detect_assets("uses nerdit-excel-engine.js") == ["/nerdit-excel-engine.js"]
    assert detect_assets("plain lesson, no engine") == []


def test_detect_assets_covers_all_four_engines():
    assert detect_assets("uses nerdit-sql-runner.js") == ["/nerdit-sql-runner.js"]
    assert detect_assets("uses nerdit-python-runner.js") == ["/nerdit-python-runner.js"]
    assert detect_assets("uses nerdit-excel-engine.js") == ["/nerdit-excel-engine.js"]
    assert detect_assets("uses nerdit-plot-runner.js") == ["/nerdit-plot-runner.js"]


def test_detect_assets_url_prefix_is_site_root():
    assert all(u.startswith("/nerdit-") for u in detect_assets("nerdit-sql-runner.js"))


def test_detect_assets_multiple_engines_in_engine_files_order():
    # detect_assets iterates ENGINE_FILES, so order follows that constant rather
    # than order of appearance in the HTML.
    html = "<div>nerdit-sql-runner.js and nerdit-plot-runner.js</div>"
    assert detect_assets(html) == ["/nerdit-plot-runner.js", "/nerdit-sql-runner.js"]


def test_lesson_without_engine_has_no_assets_key(tmp_path):
    (tmp_path / "l1.html").write_text("<div>plain lesson</div>", encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    c = build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert "assets" not in c["lessons"][0]


def test_build_course_minimal(tmp_path):
    (tmp_path / "l1.html").write_text('<div class="nerdit-wrapper nerdit-simple">hi</div>', encoding="utf-8")
    inp = [{"id": "l1", "title": "Lesson One", "description": "d"}]
    meta = [{"id": "l1", "title": "Lesson One", "duration": "8m",
             "lessonQuestions": [_q("lq")] * 3, "assessmentQuestions": [_q("aq")] * 3}]
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    assert c["id"] == "course-demo-1700000000000"
    assert c["hasExam"] is True and c["certificatePrice"] == 999 and c["duration"] == "0h 0m"
    assert c["createdAt"] == c["updatedAt"]
    assert list(c.keys())[:3] == ["id", "title", "description"]  # field order preserved
    assert len(c["lessons"]) == 1 and c["lessons"][0]["content"].startswith("<div")
    assert c["lessonIds"] == ["l1"]
    assert len(c["assessment"]["questions"]) == 3
    assert c["assessment"]["passingScore"] == 70 and c["assessment"]["examQuestionCount"] == 20
    assert c["lessons"][0]["questions"][0]["id"] == "lesson-1700000000000-l1-q1-1700000000000"
    assert c["assessment"]["questions"][0]["id"] == "assessment-1700000000000-l1-q1-1700000000000"


def test_missing_html_is_empty(tmp_path):
    inp = [{"id": "l9", "title": "Gone", "description": "d"}]
    meta = [{"id": "l9", "title": "Gone", "duration": "5m",
             "lessonQuestions": [_q("x")] * 3, "assessmentQuestions": [_q("y")] * 3}]
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    assert c["lessons"][0]["content"] == ""


def test_estimate_duration_scales_and_clamps():
    assert estimate_duration("") == "8m"
    short = estimate_duration("<h2>A</h2><p>" + " ".join(["word"] * 20) + "</p>")
    assert short == "8m"  # floored
    big = estimate_duration("<h2>A</h2>" + "<p>" + " ".join(["word"] * 40000) + "</p>")
    assert big == "35m"  # clamped
    mid = estimate_duration("<h2>A</h2><h2>B</h2><h2>C</h2><p>" + " ".join(["w"] * 800) + "</p><pre>x</pre>")
    assert 5 <= int(mid[:-1]) <= 35 and mid.endswith("m")


def test_duration_computed_when_meta_omits_it(tmp_path):
    (tmp_path / "l1.html").write_text("<h2>x</h2><p>" + " ".join(["w"] * 400) + "</p>", encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    meta = [{"id": "l1", "title": "T", "lessonQuestions": [], "assessmentQuestions": []}]  # no duration
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    assert c["lessons"][0]["duration"].endswith("m") and c["lessons"][0]["duration"] != ""


def test_meta_duration_wins_when_present(tmp_path):
    (tmp_path / "l1.html").write_text("<h2>x</h2><p>lots of words here</p>", encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    meta = [{"id": "l1", "title": "T", "duration": "12m", "lessonQuestions": [], "assessmentQuestions": []}]
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    assert c["lessons"][0]["duration"] == "12m"


def test_size_report_under_budget(tmp_path):
    (tmp_path / "l1.html").write_text("<div>small lesson</div>", encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    meta = [{"id": "l1", "title": "T", "lessonQuestions": [], "assessmentQuestions": []}]
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    r = doc_size_report(c)
    assert r["over"] is False
    assert r["total"] > 0
    assert r["lessons"][0][0] == "l1"


def test_size_report_over_budget_flags_biggest(tmp_path):
    (tmp_path / "small.html").write_text("<div>tiny</div>", encoding="utf-8")
    (tmp_path / "big.html").write_text("<div>" + ("x" * 1_100_000) + "</div>", encoding="utf-8")
    inp = [{"id": "small", "title": "S", "description": "d"}, {"id": "big", "title": "B", "description": "d"}]
    meta = [{"id": "small", "title": "S", "lessonQuestions": [], "assessmentQuestions": []},
            {"id": "big", "title": "B", "lessonQuestions": [], "assessmentQuestions": []}]
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    r = doc_size_report(c)
    assert r["over"] is True
    assert r["total"] >= MAX_DOC_BYTES
    assert r["lessons"][0][0] == "big"  # biggest lesson listed first


def test_assets_attached_when_engine_present(tmp_path):
    (tmp_path / "l2.html").write_text('<div>chart</div><script src="/nerdit-plot-runner.js"></script>', encoding="utf-8")
    inp = [{"id": "l2", "title": "Viz", "description": "d"}]
    meta = [{"id": "l2", "title": "Viz", "duration": "9m", "lessonQuestions": [], "assessmentQuestions": []}]
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    assert c["lessons"][0]["assets"] == ["/nerdit-plot-runner.js"]


# --- <id>.quiz.json sidecar (written by nerdit-lesson-writer next to the HTML) ---


def _quizfile(tmp_path, lesson_id, lesson_qs, assessment_qs):
    (tmp_path / f"{lesson_id}.quiz.json").write_text(
        json.dumps({"lessonQuestions": lesson_qs, "assessmentQuestions": assessment_qs}),
        encoding="utf-8",
    )


def test_load_quiz_absent_returns_none(tmp_path):
    assert load_quiz(str(tmp_path), "nope") is None


def test_quiz_file_questions_land_with_ids(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    _quizfile(tmp_path, "l1", [_q("lq")] * 3, [_q("aq")] * 3)
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    c = build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert len(c["lessons"][0]["questions"]) == 3
    assert c["lessons"][0]["questions"][0]["text"] == "lq"
    assert c["lessons"][0]["questions"][0]["id"] == "lesson-1700000000000-l1-q1-1700000000000"
    assert len(c["assessment"]["questions"]) == 3
    assert c["assessment"]["questions"][2]["id"] == "assessment-1700000000000-l1-q3-1700000000000"


def test_quiz_file_beats_meta(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    _quizfile(tmp_path, "l1", [_q("from-file")] * 3, [_q("af")] * 3)
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    meta = [{"id": "l1", "title": "T", "lessonQuestions": [_q("from-meta")] * 3,
             "assessmentQuestions": [_q("am")] * 3}]
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    assert c["lessons"][0]["questions"][0]["text"] == "from-file"
    assert c["assessment"]["questions"][0]["text"] == "af"


def test_meta_duration_survives_quiz_file(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    _quizfile(tmp_path, "l1", [_q("lq")] * 3, [_q("aq")] * 3)
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    meta = [{"id": "l1", "title": "T", "duration": "12m",
             "lessonQuestions": [], "assessmentQuestions": []}]
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    assert c["lessons"][0]["duration"] == "12m"
    assert c["lessons"][0]["questions"][0]["text"] == "lq"


def test_no_quiz_no_meta_is_empty_not_crash(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    c = build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert c["lessons"][0]["questions"] == []
    assert c["assessment"]["questions"] == []


def test_malformed_quiz_json_raises_with_id_and_path(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    (tmp_path / "l1.quiz.json").write_text("{not json", encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    with pytest.raises(ValueError) as e:
        build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert "l1" in str(e.value) and "l1.quiz.json" in str(e.value)


def test_quiz_json_wrong_toplevel_type_raises(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    (tmp_path / "l1.quiz.json").write_text('["a", "b"]', encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    with pytest.raises(ValueError) as e:
        build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert "JSON object" in str(e.value)


def test_quiz_json_wrong_field_type_raises(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    (tmp_path / "l1.quiz.json").write_text(
        '{"lessonQuestions": "oops", "assessmentQuestions": []}', encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    with pytest.raises(ValueError) as e:
        build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert "lessonQuestions" in str(e.value)


# --- CLI: --meta optional, missing-quiz warning, malformed-quiz exit code ---

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assemble_course.py")


def _run_cli(tmp_path, extra=()):
    return subprocess.run(
        [sys.executable, SCRIPT, "--chapter", "demo",
         "--input", str(tmp_path / "in.json"),
         "--html-dir", str(tmp_path),
         "--out", str(tmp_path / "out.json"), *extra],
        capture_output=True, text=True,
    )


def _one_lesson_input(tmp_path):
    (tmp_path / "in.json").write_text(
        json.dumps([{"id": "l1", "title": "T", "description": "d"}]), encoding="utf-8")
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")


def test_cli_runs_without_meta_flag(tmp_path):
    _one_lesson_input(tmp_path)
    _quizfile(tmp_path, "l1", [_q("lq")] * 3, [_q("aq")] * 3)
    r = _run_cli(tmp_path)
    assert r.returncode == 0, r.stderr
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert len(out["lessons"][0]["questions"]) == 3
    assert "missing quiz" not in r.stdout


def test_cli_warns_when_quiz_missing(tmp_path):
    _one_lesson_input(tmp_path)
    r = _run_cli(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "WARNING missing quiz (1): l1" in r.stdout


def test_cli_exits_2_on_malformed_quiz(tmp_path):
    _one_lesson_input(tmp_path)
    (tmp_path / "l1.quiz.json").write_text("{broken", encoding="utf-8")
    r = _run_cli(tmp_path)
    assert r.returncode == 2
    assert "l1" in r.stderr


def test_cli_still_accepts_meta_flag(tmp_path):
    _one_lesson_input(tmp_path)
    (tmp_path / "meta.json").write_text(json.dumps(
        [{"id": "l1", "title": "T", "lessonQuestions": [_q("m")] * 3,
          "assessmentQuestions": [_q("m2")] * 3}]), encoding="utf-8")
    r = _run_cli(tmp_path, ["--meta", str(tmp_path / "meta.json")])
    assert r.returncode == 0, r.stderr
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert out["lessons"][0]["questions"][0]["text"] == "m"
