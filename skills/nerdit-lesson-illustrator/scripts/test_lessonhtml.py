import pytest

from fixture_course import ANCHOR_1, course
from lessonhtml import (AnchorNotFound, anchor_of, img_sources, locate, sections, text,
                        top_paragraphs)


def lesson(i):
    return course()["lessons"][i]["content"]


def test_text_strips_tags_decodes_entities_and_collapses_space():
    assert text("<p>A <strong>bold</strong>\n  word &amp; more</p>") == "A bold word & more"


def test_anchor_normalises_entities_tags_and_symbols():
    secs = sections(lesson(0))
    anchors = [a for _, a in top_paragraphs(lesson(0), secs[0])]
    assert anchors[0] == ANCHOR_1
    assert anchor_of("<p>A load copies cleaned rows into the warehouse &amp; keeps a <strong>run log</strong> of ₹ totals 📦.</p>") == ANCHOR_1


def test_sections_numbers_headings_and_teaching_flags():
    secs = sections(lesson(0))
    assert [(s.number, s.heading, s.teaching) for s in secs] == [
        (1, "1 — What a load does", True),
        (2, "2 — Reruns are safe", True),
        (3, "📌 Quick cheat sheet", False),
    ]


def test_old_style_headings_are_sections_too():
    secs = sections(lesson(1))
    assert [(s.heading, s.teaching) for s in secs] == [("Introduction", True), ("Key Takeaways", False)]


def test_top_paragraphs_skip_paragraphs_inside_boxes():
    secs = sections(lesson(0))
    anchors = [a for _, a in top_paragraphs(lesson(0), secs[0])]
    assert anchors == [ANCHOR_1, "The target table only ever receives checked rows."]


def test_locate_after_explanation_returns_end_of_paragraph():
    content = lesson(0)
    off = locate(content, 1, "1 — What a load does", "after-explanation", ANCHOR_1)
    assert content[:off].endswith("totals 📦.</p>")


def test_locate_before_practice_returns_start_of_practice_block():
    content = lesson(0)
    assert content[locate(content, 1, "1 — What a load does", "before-practice", None):].startswith('<div class="nerdit-predict">')
    assert content[locate(content, 2, "2 — Reruns are safe", "before-practice", None):].startswith('<div class="nerdit-fillblank">')


def test_locate_before_practice_without_practice_uses_last_paragraph():
    content = lesson(1)
    off = locate(content, 1, "Introduction", "before-practice", None)
    assert content[:off].endswith("Old lessons start like this.</p>")


def test_locate_raises_instead_of_guessing():
    content = lesson(0)
    with pytest.raises(AnchorNotFound):
        locate(content, 1, "1 — What a load does", "after-explanation", "No such paragraph")
    with pytest.raises(AnchorNotFound):
        locate(content, 1, "1 — Renamed heading", "after-explanation", ANCHOR_1)


def test_img_sources():
    assert img_sources(lesson(1)) == ["https://nerdit.in/lesson-images/test/old-diagram.png"]
    assert img_sources(lesson(0)) == []
