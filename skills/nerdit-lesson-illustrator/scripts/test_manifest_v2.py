import copy

from fixture_course import PLAN, PLAN_V2, course
from lessonhtml import section_fingerprint
from manifest import (add_slots, add_slots_v2, new_manifest, record_checks, render_prompts,
                      style_block, validate)


def planned_v2():
    m = new_manifest(course(), "course.json")
    assert add_slots_v2(m, course(), copy.deepcopy(PLAN_V2)) == []
    return m


def test_v2_slots_get_kind_specific_ids_files_and_fingerprint():
    m = planned_v2()
    d, i = m["images"]
    assert (d["id"], d["requestFile"], d["outputFile"]) == (
        "load-basics-01-fig1", "load-basics-01-fig1.svg", "load-basics-01-fig1.svg")
    assert (i["id"], i["requestFile"], i["outputFile"]) == (
        "old-style-02-img1", "old-style-02-img1.png", "old-style-02-img1.webp")
    assert d["version"] == 2 and d["prompt"] == ""
    assert d["sourceFingerprint"] == section_fingerprint(course()["lessons"][0]["content"], 1, "1 — What a load does")
    assert m["course"]["cast"].startswith("Asha")


def test_v2_illustration_prompt_carries_context_cast_and_markers():
    p = planned_v2()["images"][1]["prompt"]
    assert "Course: Test Course" in p and "Lesson: Old Style" in p and "Section: Introduction" in p
    assert "Learning objective: Picture a student" in p and "Recurring characters and setting: Asha" in p
    assert "place ① on the part showing: The student opens the notebook." in p
    assert "no words, letters or numbers except the numbered markers ① ②." in p
    assert "{text_clause}" not in p
    assert "No logos, screenshots, user-interface elements or watermarks." in p


def test_v2_label_absent_from_lesson_is_refused():
    plan = copy.deepcopy(PLAN_V2)
    plan["items"][0]["labels"] = ["warehouse", "revenue"]
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(), plan)
    assert any("labels not found in the section or its fixture: ['revenue']" in e for e in errors)


def test_v2_incomplete_check_question_and_missing_fields_are_refused():
    plan = copy.deepcopy(PLAN_V2)
    plan["items"][0]["checkQuestion"] = {"question": "Q?", "answer": "", "reasoning": "R"}
    del plan["items"][1]["subject"]
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(), plan)
    assert any("checkQuestion needs question, answer and reasoning" in e for e in errors)
    assert any("missing subject" in e for e in errors)


def test_v1_and_v2_slots_coexist_and_v2_has_no_quota():
    m = new_manifest(course(), "c.json")
    assert add_slots(m, course(), [PLAN[1]]) == []
    plan = copy.deepcopy(PLAN_V2)
    plan["items"] = [plan["items"][0]] * 4
    assert add_slots_v2(m, course(), plan) == []
    assert validate(m) == []
    assert [s["id"] for s in m["images"]][-1] == "load-basics-01-fig4"


def test_render_lists_diagrams_to_draw_and_record_rebuilds_v2_prompt():
    m = planned_v2()
    out = render_prompts(m)
    assert "## Diagrams to draw" in out and "diagrams/load-basics-01-fig1.svg" in out
    assert "### old-style-02-img1.png" in out
    assert "Landscape 3:2" not in out and "Format line" in out
    m["images"][1]["status"] = "converted"
    assert record_checks(m, [{"id": "old-style-02-img1", "result": "fail", "reason": "Too busy.",
                              "revisedSubject": "One student, one notebook, nothing else."}]) == []
    assert "One student, one notebook, nothing else." in m["images"][1]["prompt"]
    assert "Course: Test Course" in m["images"][1]["prompt"]
    assert style_block(["A"], 2).endswith(
        'People, if any: Indian people in Indian settings. No real brands, companies or celebrities.')
