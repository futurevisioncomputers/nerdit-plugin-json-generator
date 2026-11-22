import re

import pytest
from PIL import Image

from draw import CAPTION_BOX, CTA_BOX, HOOK_BOX, LOGO_BOX, VIDEO_BOX, DrawError, cta_html, cue_html, fits, reel_layers, shoot


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
        reel_layers("venv क्यों", "light", "stack")


def test_layers_differ_by_layout_and_front_is_transparent():
    stack, split = reel_layers("Activate first", "violet", "stack"), reel_layers("Activate first", "violet", "split")
    assert stack["front"] != split["front"]
    assert "background:transparent" in stack["front"].replace(" ", "")
    assert "Activate first" in stack["front"] and "Activate first" not in stack["back"]


def test_cues_and_cta_carry_their_text():
    assert "route" in cue_html({"kind": "term", "text": "route", "start": 1, "end": 2}, "ember")
    assert "Full lesson free at nerdit.in" in cta_html("forest")


def test_every_template_is_free_of_devanagari():
    pages = [reel_layers("Hook", "navy", "stack")["front"], cta_html("navy")]
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


@pytest.mark.skipif(not chromium_available(), reason="no Chromium")
def test_fit_shrinks_text_that_overflows_its_box():
    wide = " ".join(["W" * 28] * 2)        # passes the 28x2 wrap guard; wide glyphs overflow the real box
    assert fit_font_sizes(reel_layers(wide, "violet", "stack")["front"], 1080, 1920)[0] < 54.0


@pytest.mark.skipif(not chromium_available(), reason="no Chromium")
def test_shoot_writes_png_of_the_right_size(tmp_path):
    out = tmp_path / "back.png"
    shoot([(reel_layers("Activate first", "violet", "split")["back"], out, 1080, 1920, False)])
    assert Image.open(out).size == (1080, 1920)


# ---- looks: a style in one of the layout families (data-first plan, Task 3) ----
from draw import look_for, reel_frame, style_from_theme  # noqa: E402
LAYOUTS = ("stack", "split", "bleed", "editorial", "bignumber")    # old plans' layout families (stylebook retired)


def navy_look(layout: str = "stack", **over) -> dict:
    return {**style_from_theme("navy"), **over, "layout": layout}


# Slide and card looks moved to brand-studio (part 2b): see brand-studio's tests/test_teaching.py.


def test_reel_frame_layout_is_stack_or_split():
    assert {reel_frame(l) for l in LAYOUTS} == {"stack", "split"}
    assert "Activate first" in reel_layers("Activate first", navy_look("bignumber"), None)["front"]


def test_look_for_reads_the_items_style_or_its_old_theme():
    assert look_for({"style": "ember", "layout": "bleed"})["palette"]["bg"] == "#292524"
    assert look_for({"style": "ember", "layout": "bleed"})["layout"] == "bleed"
    assert look_for({"theme": "violet", "layout": "split"})["layout"] == "split"


# ---- part 2b: Reels take the course's brand-studio look ----
def test_reel_look_takes_the_course_palette_and_stays_light():
    from brand_studio.looks import load_looks
    from draw import reel_look
    bs = load_looks("nerdit")[0]
    rl = reel_look(bs)
    assert rl["name"] == bs["name"] and rl["palette"]["bg"] == bs["palette"]["bg"]
    assert rl["fonts"] == {"head": bs["fonts"]["display"], "body": bs["fonts"]["body"], "code": bs["fonts"]["code"]}
    assert "Split before you fit" in reel_layers("Split before you fit", rl)["front"]
