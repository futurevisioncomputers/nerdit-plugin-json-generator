import copy

from fixture_course import PLAN, course
from insert_images import block, insert_lessons, strip_inserted
from manifest import add_slots, new_manifest


def passed():
    m = new_manifest(course(), "course.json")
    assert add_slots(m, course(), PLAN) == []
    for s in m["images"]:
        s.update(status="passed", width=1200, height=800, bytes=90_000)
    return m


def test_block_markup_is_exact_and_escaped():
    s = dict(passed()["images"][0], alt='Boxes "ride" a belt', caption="Rows & checks")
    assert block(s) == (
        '\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="load-basics-01-img1">\n'
        '  <img src="load-basics-01-img1.webp" alt="Boxes &quot;ride&quot; a belt" width="1200" height="800"'
        ' loading="lazy" decoding="async" style="display:block;width:100%;height:auto">\n'
        '  <div class="nerdit-figure-caption">Rows &amp; checks</div>\n</div>')


def test_inserts_at_both_placement_kinds_and_marks_inserted():
    c, m = course(), passed()
    assert insert_lessons(c, m) == []
    new = c["lessons"][0]["content"]
    assert 'totals 📦.</p>\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="load-basics-01-img1">' in new
    old = c["lessons"][1]["content"]
    assert 'Old lessons start like this.</p>\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="old-style-02-img1">' in old
    assert all(s["status"] == "inserted" for s in m["images"])


def test_reinserting_is_idempotent_and_strip_restores_the_original():
    c, m = course(), passed()
    insert_lessons(c, m)
    once = copy.deepcopy(c)
    insert_lessons(c, m)
    assert c == once
    assert [strip_inserted(l["content"]) for l in c["lessons"]] == [l["content"] for l in course()["lessons"]]


def test_missing_anchor_fails_only_that_slot():
    c, m = course(), passed()
    c["lessons"][0]["content"] = c["lessons"][0]["content"].replace("A load copies", "A load moves")
    errors = insert_lessons(c, m)
    assert len(errors) == 1 and "load-basics-01-img1" in errors[0] and "--replan load-basics-01" in errors[0]
    assert m["images"][0]["status"] == "passed" and m["images"][1]["status"] == "inserted"


def test_planned_and_failed_slots_are_not_inserted():
    c, m = course(), passed()
    m["images"][0]["status"] = "failed"
    m["images"][1]["status"] = "planned"
    insert_lessons(c, m)
    assert c["lessons"] == course()["lessons"]
