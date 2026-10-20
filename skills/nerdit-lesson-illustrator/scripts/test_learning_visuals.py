"""Images that teach: takeaway and misconception in the prompt, contrast panels, course props,
character sheets, and a before-code position."""
import copy

import pytest

from fixture_course import PLAN_V2, course
from lessonhtml import AnchorNotFound, locate
from manifest import add_slots_v2, new_manifest, render_prompts

CODE_LESSON = ('<div class="nerdit-wrapper"><section><h2>1 — Split rows</h2>'
               '<p>A split separates rows.</p>'
               '<h3 class="nerdit-runhead">train_test_split</h3>'
               '<div class="nerdit-run"><pre><code>x</code></pre></div></section>'
               '<section><h2>2 — No code here</h2><p>Only words.</p></section></div>')


def test_before_code_sits_in_front_of_the_first_code_heading():
    off = locate(CODE_LESSON, 1, "1 — Split rows", "before-code", None)
    assert CODE_LESSON[off:].startswith('<h3 class="nerdit-runhead">')


def test_before_code_without_a_heading_sits_in_front_of_the_run_block():
    html = CODE_LESSON.replace('<h3 class="nerdit-runhead">train_test_split</h3>', '')
    off = locate(html, 1, "1 — Split rows", "before-code", None)
    assert html[off:].startswith('<div class="nerdit-run">')


def test_before_code_refuses_a_section_without_code():
    with pytest.raises(AnchorNotFound):
        locate(CODE_LESSON, 2, "2 — No code here", "before-code", None)


def plan_with(**over):
    plan = copy.deepcopy(PLAN_V2)
    plan["items"] = [copy.deepcopy(PLAN_V2["items"][1])]
    plan["items"][0].update(over.pop("item", {}))
    plan.update(over)
    return plan


def planned(plan):
    m = new_manifest(course(), "c.json")
    assert add_slots_v2(m, course(), plan) == []
    return m


def test_prompt_states_the_takeaway_and_the_misconception_to_avoid():
    p = planned(plan_with())["images"][0]["prompt"]
    assert "The picture must make this obvious: Each lesson starts from one idea." in p
    assert "It must not suggest: You do not need to know everything first." in p


def test_contrast_layout_asks_for_two_panels_and_allows_cross_and_tick():
    p = planned(plan_with(item={"layout": "contrast"}))["images"][0]["prompt"]
    assert "Two panels side by side" in p and "left panel" in p and "right panel" in p
    assert "✗" in p and "✓" in p


def test_contrast_layout_is_refused_for_a_diagram():
    plan = copy.deepcopy(PLAN_V2)
    plan["items"] = [copy.deepcopy(PLAN_V2["items"][0])]
    plan["items"][0]["layout"] = "contrast"
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(), plan)
    assert any("layout" in e for e in errors)


def test_course_props_reach_every_prompt():
    m = planned(plan_with(props="planners, wall calendars and sticker sheets"))
    assert "Objects from this course: planners, wall calendars and sticker sheets" in m["images"][0]["prompt"]


def test_character_sheets_are_listed_and_attached_where_the_character_appears():
    m = planned(plan_with(characters=[{"name": "Asha", "look": "invented adult with a green dupatta"}],
                          item={"subject": "Asha opens a notebook beside a laptop."}))
    assert "Attach cast/cast-asha.png as the reference for Asha." in m["images"][0]["prompt"]
    sheet = render_prompts(m)
    assert "## Character sheets" in sheet and "### cast/cast-asha.png" in sheet
    assert "invented adult with a green dupatta" in sheet
