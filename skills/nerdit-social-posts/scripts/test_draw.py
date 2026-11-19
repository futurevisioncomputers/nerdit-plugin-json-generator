import re

import pytest
from PIL import Image

from draw import (CAPTION_BOX, CTA_BOX, HOOK_BOX, LOGO_BOX, VIDEO_BOX, DrawError, card_html, cta_html, cue_html, fits,
                  reel_layers, shoot, slide_html)


def chromium_available() -> bool:
    try:
        import render
        render.chromium()
        return True
    except BaseException:
        return False


def test_reel_boxes_stay_inside_safe_area():
    for x, y, w, h in (LOGO_BOX, HOOK_BOX, CAPTION_BOX, CTA_BOX):
        assert y >= 90 and y + h <= 1700 and x + w <= 900


def test_video_box_is_16_by_9_and_above_the_captions():
    x, y, w, h = VIDEO_BOX
    assert abs(w / h - 16 / 9) < 0.01 and y + h < CAPTION_BOX[1] and y > HOOK_BOX[1] + HOOK_BOX[3] - 1


def test_fits_wraps_on_words():
    assert fits("Activate first, or packages install everywhere", 28, 2)
    assert not fits("Activate first, or packages install everywhere you go today", 28, 2)
    assert not fits("supercalifragilisticexpialidociousword", 28, 2)


def test_hook_longer_than_two_lines_is_refused():
    with pytest.raises(DrawError, match="hook"):
        reel_layers("word " * 40, "navy", "stack")


def test_devanagari_on_screen_is_refused():
    with pytest.raises(DrawError, match="English"):
        slide_html({"kind": "idea", "text": "venv क्यों"}, "light", 2, 6)


def test_layers_differ_by_layout_and_front_is_transparent():
    stack, split = reel_layers("Activate first", "violet", "stack"), reel_layers("Activate first", "violet", "split")
    assert stack["front"] != split["front"]
    assert "background:transparent" in stack["front"].replace(" ", "")
    assert "Activate first" in stack["front"] and "Activate first" not in stack["back"]


def test_cues_and_cta_carry_their_text():
    assert "route" in cue_html({"kind": "term", "text": "route", "start": 1, "end": 2}, "ember")
    assert "Full lesson free at nerdit.in" in cta_html("forest")


def test_every_template_is_free_of_devanagari():
    pages = [reel_layers("Hook", "navy", "stack")["front"], cta_html("navy"),
             slide_html({"kind": "cta", "text": "Full lesson free"}, "navy", 6, 6),
             card_html({"title": "FastAPI", "course": "FastAPI", "topics": ["Routes"], "picture": None}, "navy", 1920)]
    assert not any(re.search("[ऀ-ॿ]", p) for p in pages)


def fit_font_sizes(doc: str, w: int, h: int) -> list[float]:
    import render
    from playwright.sync_api import sync_playwright
    exe = render.chromium()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        page.set_content(doc, wait_until="load")
        sizes = page.evaluate("[...document.querySelectorAll('.fit')].map(e => parseFloat(getComputedStyle(e).fontSize))")
        browser.close()
    return sizes


@pytest.mark.skipif(not chromium_available(), reason="no Chromium")
def test_fit_keeps_the_font_size_of_text_that_fits():
    assert fit_font_sizes(reel_layers("Activate first", "violet", "stack")["front"], 1080, 1920) == [54.0]
    card = card_html({"title": "Getting Started", "course": "FastAPI", "topics": [], "picture": None}, "navy", 1350)
    assert fit_font_sizes(card, 1080, 1350) == [58.0]


@pytest.mark.skipif(not chromium_available(), reason="no Chromium")
def test_fit_shrinks_text_that_overflows_its_box():
    long_title = " ".join(["WWWWWW"] * 9)   # passes the 26x3 wrap guard; wide glyphs overflow the real box
    card = card_html({"title": long_title, "course": "FastAPI", "topics": [], "picture": None}, "navy", 1350)
    assert fit_font_sizes(card, 1080, 1350)[0] < 58.0


@pytest.mark.skipif(not chromium_available(), reason="no Chromium")
def test_shoot_writes_png_of_the_right_size(tmp_path):
    out = tmp_path / "back.png"
    shoot([(reel_layers("Activate first", "violet", "split")["back"], out, 1080, 1920, False)])
    assert Image.open(out).size == (1080, 1920)


# ---- looks: a style in one of the layout families (data-first plan, Task 3) ----
from draw import look_for, reel_frame, style_from_theme  # noqa: E402
from stylebook import LAYOUTS  # noqa: E402


def navy_look(layout: str = "stack", **over) -> dict:
    return {**style_from_theme("navy"), **over, "layout": layout}


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_layout_draws_cover_idea_and_cta(layout):
    for slide in ({"kind": "cover", "hook": "Guess the output", "course": "Flask"},
                  {"kind": "idea", "text": "Routes link a URL to a view"}, {"kind": "cta"}):
        assert f"layout-{layout}" in slide_html(slide, navy_look(layout), 1, 3)


def test_style_fonts_and_background_reach_the_page():
    look = navy_look("editorial", fonts={"head": "Georgia", "body": "Corbel", "code": "Consolas"}, background="grid")
    page = slide_html({"kind": "idea", "text": "x"}, look, 2, 4)
    assert "Georgia" in page and "Corbel" in page and "bg-grid" in page


def test_each_motif_leaves_a_mark():
    for motif in ("stickers", "arrows", "highlight", "underline"):
        assert f"motif-{motif}" in slide_html({"kind": "cta"}, navy_look("stack", motif=motif), 3, 3)


def test_reel_frame_layout_is_stack_or_split():
    assert {reel_frame(l) for l in LAYOUTS} == {"stack", "split"}
    assert "Activate first" in reel_layers("Activate first", navy_look("bignumber"), None)["front"]


def test_look_for_reads_the_items_style_or_its_old_theme():
    assert look_for({"style": "ember", "layout": "bleed"})["palette"]["bg"] == "#292524"
    assert look_for({"style": "ember", "layout": "bleed"})["layout"] == "bleed"
    assert look_for({"theme": "violet", "layout": "split"})["layout"] == "split"


@pytest.mark.skipif(not chromium_available(), reason="no Chromium")
def test_bignumber_layout_shoots_at_slide_size(tmp_path):
    out = tmp_path / "s.jpg"
    shoot([(slide_html({"kind": "idea", "text": "Routes link a URL"}, navy_look("bignumber"), 2, 5), out, 1080, 1350, False)])
    assert Image.open(out).size == (1080, 1350)
