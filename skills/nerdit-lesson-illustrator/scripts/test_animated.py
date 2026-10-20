"""Animated diagrams: lesson-CSS classes only, at most two per course, diagrams only."""
import copy

from fixture_course import PLAN_V2, course
from manifest import MAX_ANIMATED, add_slots_v2, new_manifest
from svgcheck import check_svg

HEAD = '<svg class="nerdit-anim" viewBox="0 0 360 200" role="img" aria-label="x">'


def test_animated_svg_uses_the_lesson_classes():
    svg = HEAD + '<g class="na-show" style="--d:1s"><text>A</text></g></svg>'
    assert check_svg(svg, ["A"], 1, animated=True) == []


def test_animated_svg_needs_the_root_class_and_a_moving_part():
    plain = '<svg viewBox="0 0 360 200" role="img" aria-label="x"><text>A</text></svg>'
    errors = check_svg(plain, ["A"], 1, animated=True)
    assert any("nerdit-anim" in e for e in errors)
    assert any("na-" in e for e in errors)


def test_animated_svg_may_not_carry_its_own_style_script_or_smil():
    for extra in ("<style>.x{}</style>", "<script>1</script>", '<animate attributeName="x"/>'):
        svg = HEAD + '<g class="na-show">' + extra + '<text>A</text></g></svg>'
        assert any("lesson CSS" in e for e in check_svg(svg, ["A"], 1, animated=True)), extra


def test_a_static_diagram_may_not_animate():
    svg = HEAD + '<g class="na-show"><text>A</text></g></svg>'
    assert any("not planned as animated" in e for e in check_svg(svg, ["A"], 1))


def animated_plan(n):
    plan = copy.deepcopy(PLAN_V2)
    item = plan["items"][0]
    plan["items"] = []
    for _ in range(n):
        plan["items"].append(dict(copy.deepcopy(item), animated=True))
    return plan


def test_animated_flag_is_stored_on_the_slot():
    m = new_manifest(course(), "c.json")
    assert add_slots_v2(m, course(), animated_plan(1)) == []
    assert m["images"][0]["animated"] is True


def test_a_course_gets_at_most_two_animations():
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(), animated_plan(MAX_ANIMATED + 1))
    assert any(f"at most {MAX_ANIMATED} animated" in e for e in errors)


def test_only_diagrams_can_be_animated():
    plan = copy.deepcopy(PLAN_V2)
    plan["items"] = [dict(copy.deepcopy(PLAN_V2["items"][1]), animated=True)]
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(), plan)
    assert any("only a diagram can be animated" in e for e in errors)
