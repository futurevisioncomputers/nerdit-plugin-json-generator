import copy

from fixture_course import PLAN_V2, course
from insert_images import insert_lessons, strip_inserted
from manifest import add_slots_v2, new_manifest

SVG = ('<svg viewBox="0 0 200 80" role="img" aria-label="Checked rows reach the warehouse">'
       '<text x="10" y="20" fill="var(--nb)">① warehouse</text>'
       '<text x="10" y="50" fill="var(--orange)">② run log</text></svg>')


def ready(tmp_path):
    m = new_manifest(course(), "c.json")
    assert add_slots_v2(m, course(), copy.deepcopy(PLAN_V2)) == []
    for s in m["images"]:
        s.update(status="passed", width=1200, height=900)
    (tmp_path / "load-basics-01-fig1.svg").write_text(SVG, encoding="utf-8")
    return m


def test_v2_diagram_block_has_intro_figure_steps_and_check(tmp_path):
    c, m = course(), ready(tmp_path)
    assert insert_lessons(c, m, tmp_path) == []
    html = c["lessons"][0]["content"]
    assert ('totals 📦.</p>\n<p class="nerdit-visual-intro" data-nerdit-img="load-basics-01-fig1">'
            'Follow the rows from left to right.</p>') in html
    assert ('<div class="nerdit-figure" data-nerdit-img="load-basics-01-fig1" style="max-width:440px">'
            '\n  <svg viewBox') in html
    assert ('<ol class="nerdit-visual-read" data-nerdit-img="load-basics-01-fig1" '
            'style="list-style:none;padding-left:0"><li>① The rows arrive in the warehouse.</li>'
            '<li>② The run log records the run.</li></ol>') in html
    assert '<div class="nerdit-predict" data-nerdit-img="load-basics-01-fig1">' in html
    assert "Does the load change the row values?" in html
    old = c["lessons"][1]["content"]
    assert '<img src="old-style-02-img1.webp" alt="A student opens a notebook beside a laptop."' in old
    assert all(s["status"] == "inserted" for s in m["images"])


def test_v2_reinsert_is_idempotent_and_strip_restores(tmp_path):
    c, m = course(), ready(tmp_path)
    insert_lessons(c, m, tmp_path)
    once = copy.deepcopy(c)
    insert_lessons(c, m, tmp_path)
    assert c == once
    assert [strip_inserted(l["content"]) for l in c["lessons"]] == [l["content"] for l in course()["lessons"]]


def test_v2_missing_diagram_file_fails_only_that_slot(tmp_path):
    c, m = course(), ready(tmp_path)
    (tmp_path / "load-basics-01-fig1.svg").unlink()
    errors = insert_lessons(c, m, tmp_path)
    assert len(errors) == 1 and "load-basics-01-fig1.svg" in errors[0]
    assert m["images"][1]["status"] == "inserted"
