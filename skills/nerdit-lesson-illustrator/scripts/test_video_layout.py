"""Video-ready layout: fixed panels in the prompt, and the same panels recorded as regions."""
from manifest import MARKERS, build_prompt, regions

M = {"course": {"title": "C"}}
BASE = {"lessonTitle": "L", "section": {"heading": "1 — S"}, "objective": "o", "question": "q?",
        "subject": "A pipeline fills gaps then predicts.", "takeaway": "t", "misconception": "m",
        "labels": [], "layout": "single"}


def slot(**kw):
    return {**BASE, **kw}


def test_three_step_process_gets_three_panels_in_order():
    s = slot(kind="process", explanation=["Rows split.", "Model trains.", "Held rows check it."])
    p = build_prompt(M, s)
    assert "Layout: 3 equal panels side by side, read left to right" in p
    assert ("the left third shows Rows split, with ① in its top-left corner; "
            "the middle third shows Model trains, with ② in its top-left corner; "
            "the right third shows Held rows check it, with ③ in its top-left corner.") in p
    assert [(r["x"], r["w"], r["mark"]) for r in regions(s)] == [(0.0, 0.3333, "①"), (0.3333, 0.3333, "②"),
                                                                 (0.6667, 0.3333, "③")]


def test_contrast_uses_halves_and_keeps_marker_placement():
    s = slot(kind="illustration", layout="contrast", explanation=["Wrong.", "Right."])
    p = build_prompt(M, s)
    assert "split down the middle by a thin divider" in p and "place ① on the part showing: Wrong." in p
    assert "equal panels" not in p
    assert [r["mark"] for r in regions(s)] == ["✗", "✓"]


def test_single_step_and_screens_have_free_layout():
    assert regions(slot(kind="illustration", explanation=["One idea."])) == []
    screen = slot(kind="screen", app="Excel", explanation=["Click A.", "Click B."])
    assert regions(screen) == []
    p = build_prompt(M, screen)
    assert "place ① on the part showing: Click A." in p and "equal panels" not in p and "margin" not in p


def test_every_drawn_picture_asks_for_safe_margins():
    p = build_prompt(M, slot(kind="illustration", explanation=["One idea."]))
    assert "clear margin at every edge, so the picture can be zoomed" in p
    assert MARKERS[0] not in p
