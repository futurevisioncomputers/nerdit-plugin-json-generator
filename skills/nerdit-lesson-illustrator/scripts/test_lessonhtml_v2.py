from fixture_course import course
from lessonhtml import (fixture_text, remove_visual_blocks, section_fingerprint, section_text,
                        sections, visual_elements)

V1 = ('\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="a-img1">\n'
      '  <img src="a.webp" alt="x">\n  <div class="nerdit-figure-caption">Cap</div>\n</div>')
V2 = ('\n<p class="nerdit-visual-intro" data-nerdit-img="a-fig1">Look at the rows.</p>'
      '\n<div class="nerdit-figure" data-nerdit-img="a-fig1">\n'
      '  <svg viewBox="0 0 10 10" role="img" aria-label="x"><text>①</text></svg>\n'
      '  <div class="nerdit-figure-caption">Cap</div>\n</div>'
      '\n<ol class="nerdit-visual-read" data-nerdit-img="a-fig1"><li>① Step.</li></ol>'
      '\n<div class="nerdit-predict" data-nerdit-img="a-fig1"><div class="nerdit-predict-head">Try</div>'
      '<p>Q?</p><details class="nerdit-predict-answer"><summary>Show answer</summary><p>A.</p></details></div>')
ANCHOR = "totals 📦.</p>"


def lesson0():
    return course()["lessons"][0]["content"]


def test_remove_visual_blocks_strips_v1_and_v2_and_keeps_the_rest():
    base = lesson0()
    assert remove_visual_blocks(base.replace(ANCHOR, ANCHOR + V1 + V2)) == base


def test_remove_visual_blocks_keeps_writer_tagged_figures():
    # The lesson writer tags its own figures, steps and Try It boxes with data-nerdit-img
    # ids such as "ml01-examples"; only the illustrator's "-img<n>"/"-fig<n>" ids are ours.
    writer = ('\n<div class="nerdit-figure" data-nerdit-img="ml01-examples"><svg></svg></div>'
              '\n<div class="nerdit-predict" data-nerdit-img="ml-fundamentals-09-v1"><p>Q?</p></div>')
    base = lesson0().replace(ANCHOR, ANCHOR + writer)
    assert remove_visual_blocks(base.replace(ANCHOR, ANCHOR + V1 + V2)) == base


def test_visual_elements_lists_the_siblings_of_one_visual():
    content = lesson0().replace(ANCHOR, ANCHOR + V2)
    assert [tag for tag, _ in visual_elements(content, "a-fig1")] == ["p", "div", "ol", "div"]
    assert visual_elements(content, "nope") == []


def test_section_text_keeps_code_lines_and_drops_visuals():
    content = ('<h2>1 — Q</h2><p>Intro <strong>term</strong>.</p>'
               '<pre><code>SELECT a,\n  b FROM t;</code></pre>' + V2)
    out = section_text(content, sections(content)[0])
    assert "1 — Q" in out and "Intro" in out and "term" in out
    assert "SELECT a,\n  b FROM t;" in out
    assert "Look at the rows" not in out


def test_fingerprint_ignores_inserted_visuals_but_tracks_text_edits():
    base = lesson0()
    fp = section_fingerprint(base, 1, "1 — What a load does")
    assert len(fp) == 16
    assert section_fingerprint(base.replace(ANCHOR, ANCHOR + V2), 1, "1 — What a load does") == fp
    assert section_fingerprint(base.replace("checked rows", "verified rows"), 1, "1 — What a load does") != fp


def test_fixture_text_reads_seed_scripts_and_demo_tables():
    content = ('<div class="nerdit-demo-table"><table><tr><td>Aarav</td><td>Pune</td></tr></table></div>'
               '<script type="text/plain" id="s1">INSERT INTO t VALUES (1);</script>')
    out = fixture_text(content)
    assert "Aarav" in out and "Pune" in out and "INSERT INTO t VALUES (1);" in out


def test_fingerprint_ignores_an_optimised_image_src_and_size():
    old = course()["lessons"][1]["content"]
    fp = section_fingerprint(old, 1, "Introduction")
    optimised = old.replace("https://nerdit.in/lesson-images/test/old-diagram.png", "old-diagram.webp").replace(
        'width="1536" height="1024"', 'width="1200" height="800"')
    assert section_fingerprint(optimised, 1, "Introduction") == fp


def test_fingerprint_tracks_the_lesson_fixture():
    base = lesson0() + '<script type="text/plain" id="s1">INSERT INTO t VALUES (1, \'Pune\');</script>'
    fp = section_fingerprint(base, 1, "1 — What a load does")
    assert section_fingerprint(base.replace("'Pune'", "'Mumbai'"), 1, "1 — What a load does") != fp
