"""kind "process": an AI-drawn picture of a process or data flow, markers only, no SVG beside it."""
import copy

from fixture_course import PLAN_V2, course
from manifest import add_slots_v2, new_manifest, record_checks


def process_item(**over):
    item = copy.deepcopy(PLAN_V2["items"][1])
    item.update(kind="process",
                subject="A stack of record cards splits into three coloured piles that move to separate desks.",
                explanation=["The stack splits into piles.", "Each pile moves to its own desk."])
    item.update(over)
    return item


def plan_of(*items):
    return {"version": 2, "cast": PLAN_V2["cast"], "items": list(items)}


def test_process_slot_is_a_raster_image_with_markers_only_prompt():
    m = new_manifest(course(), "c.json")
    assert add_slots_v2(m, course(), plan_of(process_item())) == []
    s = m["images"][0]
    assert (s["kind"], s["id"], s["requestFile"]) == ("process", "old-style-02-img1", "old-style-02-img1.png")
    assert s["prompt"].startswith("Educational process illustration")
    assert "no words, letters or numbers except the numbered markers ① ②." in s["prompt"]


def test_process_needs_two_or_more_steps():
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(),
                          plan_of(process_item(explanation=["Only one step."])))
    assert any("process needs 2-3 explanation steps" in e for e in errors)


def test_process_refuses_labels():
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(),
                          plan_of(process_item(labels=["train"])))
    assert any("process images carry markers only" in e for e in errors)


def test_process_subject_may_not_ask_for_numbers():
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(),
                          plan_of(process_item(subject="A stack of 600 cards splits into 360 and 240.")))
    assert any("subject contains a number" in e for e in errors)


def test_process_replaces_a_diagram_in_the_same_section():
    diagram = copy.deepcopy(PLAN_V2["items"][0])
    proc = process_item(lessonId=diagram["lessonId"], section=diagram["section"], heading=diagram["heading"],
                        position=diagram["position"], anchor=diagram["anchor"])
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(), plan_of(diagram, proc))
    assert any("replaces the diagram" in e for e in errors)


def test_illustration_and_process_in_one_lesson_get_distinct_ids():
    m = new_manifest(course(), "c.json")
    ill = copy.deepcopy(PLAN_V2["items"][1])
    assert add_slots_v2(m, course(), plan_of(ill, process_item())) == []
    assert [s["id"] for s in m["images"]] == ["old-style-02-img1", "old-style-02-img2"]


def test_revised_process_subject_rebuilds_its_prompt():
    m = new_manifest(course(), "c.json")
    add_slots_v2(m, course(), plan_of(process_item()))
    m["images"][0]["status"] = "converted"
    assert record_checks(m, [{"id": "old-style-02-img1", "result": "fail", "reason": "piles unclear",
                              "revisedSubject": "Three clearly separate coloured piles on three desks."}]) == []
    assert "Three clearly separate coloured piles" in m["images"][0]["prompt"]
