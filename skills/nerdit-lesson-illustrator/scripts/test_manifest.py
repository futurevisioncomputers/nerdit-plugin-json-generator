import json
import os
import subprocess
import sys

from fixture_course import PLAN, course
from manifest import (MAX_PER_LESSON, add_slots, load, new_manifest, render_prompts, save,
                      style_block, validate)

SCRIPT = os.path.join(os.path.dirname(__file__), "manifest.py")


def planned():
    m = new_manifest(course(), "course.json")
    assert add_slots(m, course(), PLAN) == []
    return m


def test_add_slots_assigns_ids_files_and_full_prompts():
    m = planned()
    a, b = m["images"]
    assert (a["id"], a["requestFile"], a["outputFile"]) == (
        "load-basics-01-img1", "load-basics-01-img1.png", "load-basics-01-img1.webp")
    assert a["status"] == "planned" and a["section"] == {"number": 1, "heading": "1 — What a load does"}
    assert a["prompt"].startswith("A conveyor carrying clean boxes")
    assert "#0B1F3A" in a["prompt"] and "{labels_clause}" not in a["prompt"]
    assert 'except these exact labels: "Start"' in b["prompt"]
    assert b["id"] == "old-style-02-img1" and b["anchor"] == ""


def test_style_block_tolerates_crlf_files(tmp_path):
    p = tmp_path / "style.md"
    p.write_bytes(b"x\r\n```style\r\nLine one{labels_clause}.\r\n```\r\n")
    assert style_block([], path=p) == "Line one."
    assert style_block(["A"], path=p) == 'Line one, except these exact labels: "A".'


def test_add_slots_rejects_bad_items_without_partial_writes():
    m = new_manifest(course(), "course.json")
    bad = [dict(PLAN[0], lessonId="nope"), dict(PLAN[0], anchor="Not in the lesson"), dict(PLAN[0], alt="")]
    errors = add_slots(m, course(), bad)
    assert any("unknown lesson nope" in e for e in errors)
    assert any("no paragraph starting 'Not in the lesson'" in e for e in errors)
    assert any("missing alt" in e for e in errors)


def test_already_planned_lesson_needs_replan_and_replan_replaces():
    m = planned()
    assert any("--replan load-basics-01" in e for e in add_slots(m, course(), [PLAN[0]]))
    m = planned()
    new = dict(PLAN[0], subject="A different picture.")
    assert add_slots(m, course(), [new], replan="load-basics-01") == []
    ids = [s["id"] for s in m["images"] if s["lessonId"] == "load-basics-01"]
    assert ids == ["load-basics-01-img1"]
    assert m["images"][-1]["prompt"].startswith("A different picture.")


def test_per_lesson_cap():
    m = new_manifest(course(), "course.json")
    errors = add_slots(m, course(), [PLAN[0]] * (MAX_PER_LESSON + 1))
    assert any(f"more than {MAX_PER_LESSON} images" in e for e in errors)


def test_validate_alt_and_caption_limits():
    m = planned()
    m["images"][0]["alt"] = "x" * 126
    m["images"][0]["caption"] = " ".join(["word"] * 16)
    errors = validate(m)
    assert any("alt is over 125 characters" in e for e in errors)
    assert any("caption is over 15 words" in e for e in errors)


def test_render_prompts_lists_files_to_generate():
    out = render_prompts(planned())
    assert "### load-basics-01-img1.png" in out and "### old-style-02-img1.png" in out
    assert "2 to generate" in out


def test_save_and_load_round_trip(tmp_path):
    m = planned()
    save(tmp_path, m)
    assert load(tmp_path) == m


def test_cli_add_creates_manifest_prompts_and_incoming(tmp_path):
    src = tmp_path / "course.json"
    src.write_text(json.dumps(course(), ensure_ascii=False), encoding="utf-8")
    plan = tmp_path / "images" / "plan.json"
    plan.parent.mkdir()
    plan.write_text(json.dumps(PLAN, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "add", "--course", str(src), "--plan", str(plan),
                        "--images-dir", str(plan.parent)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (plan.parent / "manifest.json").is_file()
    assert (plan.parent / "PROMPTS.md").is_file()
    assert (plan.parent / "incoming").is_dir()
