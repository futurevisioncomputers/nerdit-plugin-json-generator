import json
import sys
from pathlib import Path

import pytest

from test_screens import ADS, DEDUPE, DEDUPE_TEXT, GRID, PIP, PIP_TEXT, SCENE, XL, XL_TEXT, block
from visual_briefs import brief_items, main

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "nerdit-lesson-illustrator" / "scripts"))
import manifest  # noqa: E402

GRID_BLOCK = f'<script type="application/json" id="xl-staff">{json.dumps(GRID)}</script>'


def course(*sections):
    body = "".join(f"<section><h2>{i} — Part {i}</h2>{s}</section>" for i, s in enumerate(sections, 1))
    content = f'<div class="nerdit-wrapper nerdit-simple"><h1>Lookups</h1>{GRID_BLOCK}{body}</div>'
    return {"id": "c", "title": "Course", "lessons": [{"id": "l1", "title": "Lookups", "content": content}]}


def sample():
    return course(
        f"<p>{DEDUPE_TEXT}</p>{block(DEDUPE, grid='xl-staff')}<p>After the picture.</p>",
        f"<p>{XL_TEXT}</p>{block(XL, grid='xl-staff')}",
        f"<p>{PIP_TEXT}</p><p>A shop keeps two copies of one bill.</p>{block(SCENE, cls='nerdit-scene')}",
    )


def test_one_item_per_b_screen_and_scene():
    items = brief_items(sample())
    assert [(i["kind"], i["section"]) for i in items] == [("screen", 1), ("illustration", 3)]


def test_screen_item_fields():
    (screen, _) = brief_items(sample())
    assert screen["lessonId"] == "l1" and screen["heading"] == "1 — Part 1"
    assert screen["subject"] == "Excel window: Remove repeated rows"
    assert screen["intro"] == "Here is the screen for this step."
    assert screen["explanation"] == ["Click Data, then Remove Duplicates.", "Click OK."]
    assert screen["sourceRefs"] == ["#xl-staff"] and screen["checkQuestion"] == DEDUPE["check"]


def test_screen_labels_are_exact():
    (screen, _) = brief_items(sample())
    assert {"Data", "Remove Duplicates", "OK"} <= set(screen["labels"])
    assert {"ID", "Name", "101", "Aarav", "103", "Kabir"} <= set(screen["labels"])  # rows 1-4, columns A-B
    assert "Meera" not in screen["labels"] and "Sales" not in screen["labels"]


def test_scene_item_fields():
    (_, scene) = brief_items(sample())
    assert scene["subject"] == SCENE["subject"] and scene["caption"] == SCENE["caption"]
    assert scene["explanation"] == [SCENE["takeaway"]] and scene["labels"] == []
    assert scene["sourceRefs"] == ["#shop-bill"]


def test_anchor_is_the_paragraph_before_the_spec():
    screen, scene = brief_items(sample())
    assert screen["position"] == "after-explanation"
    assert screen["anchor"] == DEDUPE_TEXT[:60].rstrip()
    assert scene["anchor"] == "A shop keeps two copies of one bill."


def test_invalid_lesson_is_an_error():
    bad = course(f"<p>Nothing here.</p>{block(dict(ADS, layout='canvas'))}")
    with pytest.raises(ValueError, match="layout"):
        brief_items(bad)


def items_errors(kind):
    c = sample()
    items = [i for i in brief_items(c) if i["kind"] == kind]
    m = manifest.new_manifest(c, "test")
    return manifest.add_slots_v2(m, c, {"version": 2, "items": items})


def test_scene_item_passes_illustrator_validation():
    assert items_errors("illustration") == []


@pytest.mark.xfail(strict=True, reason="the illustrator learns kind 'screen' in Task 6")
def test_screen_item_passes_illustrator_validation():
    assert items_errors("screen") == []


def test_cli_writes_a_v2_plan(tmp_path):
    src, out = tmp_path / "course.json", tmp_path / "plan.json"
    src.write_text(json.dumps(sample()), encoding="utf-8")
    assert main(["--course", str(src), "--out", str(out)]) == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["version"] == 2 and len(plan["items"]) == 2
