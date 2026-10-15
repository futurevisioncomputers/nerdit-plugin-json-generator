import json
import os
import subprocess
import sys

from extract_outline import outline, render
from fixture_course import ANCHOR_1, course

SCRIPT = os.path.join(os.path.dirname(__file__), "extract_outline.py")


def test_outline_lists_sections_figures_anchors_and_images():
    new, old = outline(course())
    assert new["lessonId"] == "load-basics-01" and new["svgCount"] == 1 and new["images"] == []
    s1 = new["sections"][0]
    assert s1["heading"] == "1 — What a load does" and s1["teaching"] and s1["hasPractice"]
    assert s1["figures"] == ["Rows move from staging to the warehouse."]
    assert s1["anchors"] == [ANCHOR_1, "The target table only ever receives checked rows."]
    assert new["sections"][2]["teaching"] is False
    assert old["images"] == ["https://nerdit.in/lesson-images/test/old-diagram.png"]


def test_render_flags_lessons_with_no_visual():
    c = course()
    c["lessons"][1]["content"] = "<h2>Introduction</h2><p>Plain text only.</p>"
    out = render(outline(c))
    assert 'L02 old-style-02 "Old Style" [NO VISUAL]' in out
    assert 'L01 load-basics-01 "Load Basics" [svg=1 img=0]' in out
    assert f"     ¶ {ANCHOR_1}" in out


def test_cli_writes_json_and_prints_outline(tmp_path):
    src = tmp_path / "course.json"
    src.write_text(json.dumps(course(), ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "outline.json"
    r = subprocess.run([sys.executable, SCRIPT, "--course", str(src), "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert "L01 load-basics-01" in r.stdout
    assert json.loads(out.read_text(encoding="utf-8"))[0]["lessonId"] == "load-basics-01"


def test_hints_from_concept_manifests_reach_the_outline(tmp_path):
    c = course()
    lid = c["lessons"][0]["id"]
    (tmp_path / f"{lid}.concepts.json").write_text(json.dumps({
        "teaches": [], "uses": [],
        "visuals": [{"section": 1, "visual": "value-table", "illustration": "drafts of an essay"}]}),
        encoding="utf-8")
    from extract_outline import load_hints
    lessons = outline(c, load_hints(str(tmp_path)))
    assert lessons[0]["sections"][0]["hint"]["illustration"] == "drafts of an essay"
    assert "image: drafts of an essay" in render(lessons)
