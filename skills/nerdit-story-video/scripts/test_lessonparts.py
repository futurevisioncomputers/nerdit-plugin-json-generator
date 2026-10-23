"""Topic clips mirror their section: the page's own tables and code, coverage of every section."""
import json
from pathlib import Path

import lessonparts
import storyplan

SECTION = '''<section><h2>1 — 📊 an observation becomes a record</h2>
<p>Each line is a <strong>record</strong>; each detail sits in a <strong>column</strong>.
<strong>Tip:</strong> read across.</p>
<div class="nerdit-figure"><p class="nerdit-vtitle">Six enquiries</p><table class="nerdit-vtable">
<thead><tr><th>enquiry_id</th><th>branch</th></tr></thead>
<tbody><tr><td>E1</td><td>Citylight</td></tr><tr class="nerdit-spot"><td>E2</td><td>Pal</td></tr></tbody></table></div>
<h3 class="nerdit-runhead">enquiry["branch"]</h3>
<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span>
<pre><button class="nerdit-copy-btn">Copy</button><code>e = {"branch": "Pal"}
print(e["branch"])</code></pre></div>
<div class="nerdit-out"><span class="nerdit-tag">Python shows</span><pre><code>Pal</code></pre></div></div>
<p>after</p>
<div class="nerdit-predict"><div class="nerdit-out"><pre><code>walk-in</code></pre></div></div>
</section><section><h2>2 — Counting</h2><p>A <strong>count</strong>.</p></section>
<section><h2>📌 Quick cheat sheet</h2></section>'''


def test_section_parts_come_from_the_page():
    p = lessonparts.section_parts(SECTION, 1)
    assert p["heading"] == "an observation becomes a record"
    assert p["tables"] == [{"title": "Six enquiries", "head": ["enquiry_id", "branch"],
                            "rows": [["E1", "Citylight"], ["E2", "Pal"]], "spot": [1]}]
    assert p["runs"] == [{"code": 'e = {"branch": "Pal"}\nprint(e["branch"])', "output": "Pal", "outLabel": "Python shows"}]
    assert p["terms"] == ["record", "column"]            # "Tip:" is a label, not a term
    assert lessonparts.numbered_topics(SECTION) == [1, 2]
    assert lessonparts.section_parts(SECTION, 9) is None


def test_table_and_code_draw_as_animated_svg_with_highlights():
    p = lessonparts.section_parts(SECTION, 1)
    t = lessonparts.table_svg(p["tables"][0], ["row:E2", "col:branch"])
    assert t.startswith('<svg class="nerdit-anim"') and t.count('stroke="var(--nb-vivid)"') == 2 and ">Citylight<" in t
    c = lessonparts.code_svg(p["runs"][0], ["line:2"])
    assert "print(e[&quot;branch&quot;])" in c and "PYTHON SHOWS" in c and ">Pal<" in c and 'fill-opacity=".3"' in c
    assert "#" not in t.replace("&#", "") and "#" not in c.replace("&#", "")     # tokens only, no hex
    assert lessonparts.highlight_problems("table", p["tables"][0], ["row:E9", "col:x", "line:1"]) == [
        "highlight 'row:E9': no row starts with 'E9'", "highlight 'col:x': no column 'x' (columns: enquiry_id, branch)",
        "highlight 'line:1': use row:<first cell> or col:<column>"]
    assert lessonparts.highlight_problems("code", p["runs"][0], ["line:3"]) == ["highlight 'line:3': the code has 2 lines"]


def course_file(tmp_path: Path) -> Path:
    path = tmp_path / "course.json"
    path.write_text(json.dumps({"title": "C", "lessons": [{"id": "l1", "title": "L1", "content": SECTION}]}), encoding="utf-8")
    return path


def test_scaffold_fills_each_section_with_its_table_and_code(tmp_path):
    plan = json.loads(storyplan.scaffold(tmp_path / "images", course_file(tmp_path)).read_text(encoding="utf-8"))
    assert [(s["kind"], s["topic"], s.get("table") or s.get("code")) for s in plan["scenes"]] == [
        ("vector", 1, None), ("table", 1, 1), ("code", 1, 1), ("vector", 2, None)]
    assert plan["scenes"][1]["title"] == "an observation becomes a record" and plan["skipTopics"] == []


def test_coverage_makes_each_clip_explain_its_section(tmp_path):
    parts = storyplan.lesson_parts(course_file(tmp_path))
    talk = "A record is one row and each column holds one detail. " * 17
    plan = {"scenes": [{"lessonId": "l1", "topic": 1, "kind": "vector", "narration": talk},
                       {"lessonId": "l1", "topic": 1, "kind": "table", "table": 1, "narration": "x"},
                       {"lessonId": "l1", "topic": 1, "kind": "code", "code": 1, "narration": "y"}],
            "skipTopics": [{"lessonId": "l1", "topic": 2, "reason": "a one-line reminder"}]}
    assert storyplan.check_coverage(plan, parts) == []
    plan["skipTopics"] = []
    plan["scenes"] = plan["scenes"][:1]
    plan["scenes"][0]["narration"] = "A record is one row."
    errors = storyplan.check_coverage(plan, parts)
    assert any("section 2" in e and "no clip" in e for e in errors)
    assert any("1 scene(s)" in e for e in errors) and any("words of narration" in e for e in errors)
    assert any("own table or code" in e for e in errors) and any("'column'" in e for e in errors)


def test_a_clip_explains_before_it_shows_the_table_or_code(tmp_path):
    parts = storyplan.lesson_parts(course_file(tmp_path))
    talk = "A record is one row and each column holds one detail. " * 17
    plan = {"scenes": [{"lessonId": "l1", "topic": 1, "kind": "broll", "narration": "x"},
                       {"lessonId": "l1", "topic": 1, "kind": "table", "table": 1, "narration": talk},
                       {"lessonId": "l1", "topic": 1, "kind": "vector", "narration": "y"},
                       {"lessonId": "l1", "topic": 1, "kind": "code", "code": 1, "narration": "z"}],
            "skipTopics": [{"lessonId": "l1", "topic": 2, "reason": "a one-line reminder"}]}
    assert any("opens with a table scene" in e for e in storyplan.check_coverage(plan, parts))
    plan["scenes"][1:3] = plan["scenes"][2:0:-1]                 # broll, vector, table, code
    assert not any("opens with" in e for e in storyplan.check_coverage(plan, parts))


def test_table_and_code_scenes_must_point_at_the_page(tmp_path):
    parts = storyplan.lesson_parts(course_file(tmp_path))
    good = {"kind": "code", "lessonId": "l1", "topic": 1, "code": 1}
    assert storyplan.part_of(good, parts)["output"] == "Pal"
    assert storyplan.part_of({**good, "code": 2}, parts) is None
    assert storyplan.part_of({"kind": "table", "lessonId": "l1", "topic": 2, "table": 1}, parts) is None
