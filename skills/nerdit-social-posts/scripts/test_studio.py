"""NERDIT's adapter to brand-studio (part 2b): slides and cards become brand-studio pages in the course's look."""
import pytest

from conftest import write_workdir
from source import load_source

import slides
import studio


def test_cover_and_cta_become_photo_pages():
    t, c = studio.slide_page({"kind": "cover", "hook": "Split before you fit", "course": "C"}, "C", 7)
    assert t == "hook" and c["headline"] == "Split before you fit" and c["subline"] == "C"
    assert c["icon"] == studio.COVER_ICONS[7 % len(studio.COVER_ICONS)]
    t, c = studio.slide_page({"kind": "cta", "text": "Full lesson free at nerdit.in"}, "C", 0)
    assert t == "cta" and c["band"] == "C" and c["subline"] == "Full lesson free at nerdit.in"
    assert c["headline"] == "Keep learning" and c["cta"] == "Save this post for later"


def test_teaching_slides_keep_their_fields_and_diagrams_get_the_lesson_css():
    t, c = studio.slide_page({"kind": "wrong", "head": "h", "code": "x = 1", "lang": "python", "reason": "r"}, "C", 0)
    assert t == "wrong" and c == {"head": "h", "code": "x = 1", "lang": "python", "reason": "r"}
    t, c = studio.slide_page({"kind": "diagram", "svg": "<svg></svg>", "label": "A"}, "C", 0)
    assert t == "diagram" and c["svg"] == "<svg></svg>" and ".nerdit-anim" in c["css"]


def test_card_types_follow_the_format():
    assert studio.card_page({"kind": "cheat", "rows": []}, "story")[0] == "cheat-story"
    assert studio.card_page({"kind": "cheat", "rows": []}, "feed")[0] == "cheat"
    assert studio.card_page({"kind": "compare", "bad": {}, "good": {}}, "feed")[0] == "compare"
    t, c = studio.card_page({"title": "T", "course": "C", "topics": [], "picture": {"svg": "<svg></svg>"}}, "story")
    assert t == "picture-story" and ".nerdit-anim" in c["picture"]["css"]
    assert studio.card_page({"title": "T", "course": "C", "topics": [], "picture": None}, "feed")[0] == "picture"


def test_devanagari_is_refused_before_drawing():
    assert any("English" in e for e in studio.fit_errors([("idea", {"text": "यह गलत है", "title": ""})]))
    assert studio.fit_errors([("idea", {"text": "Short idea.", "title": ""})]) == []


def test_day_of_counts_days_from_the_pack_start():
    assert studio.day_of({"start": "2026-11-22"}, {"date": "2026-11-25"}) == 3


def _carousel(tmp_path):
    src = load_source(write_workdir(tmp_path))
    item = {"id": "d03-carousel", "format": "carousel", "lessonId": "demo-01", "topic": 1,
            "slides": [{"kind": "cover", "hook": "Make a project folder", "course": "Demo Course"},
                       {"kind": "idea", "text": "Each project gets its own venv.", "title": "Topic 1"},
                       {"kind": "cta", "text": "Full lesson free at nerdit.in"}]}
    return src, item


def test_carousel_renders_named_jpegs_in_the_course_look(tmp_path, studio_icons):
    from brand_studio.looks import history_path, load_history
    src, item = _carousel(tmp_path)
    files = slides.make_carousel(src, item, item["slides"], tmp_path / "out", tmp_path / "pack-plan.json", 2)
    assert [f.name for f in files] == ["d03-carousel-01.jpg", "d03-carousel-02.jpg", "d03-carousel-03.jpg"]
    assert all(f.is_file() for f in files)
    entries = load_history(history_path("nerdit"))["looks"]
    assert {e["key"] for e in entries} == {f"{studio.course_key(src)}:d03-carousel"} and len({e["look"] for e in entries}) == 1
    assert [e["variant"] for e in entries] == ["a", "b", "a"]          # day 2: slide 1 starts at variant a


def test_render_problem_names_the_item_and_slot(tmp_path, monkeypatch):
    from brand_studio import api
    src, item = _carousel(tmp_path)
    monkeypatch.setattr(api, "render_set_to", lambda *a, **k: ([], ["02-idea: text does not fit: text"]))
    with pytest.raises(SystemExit, match="d03-carousel: 02-idea: text does not fit: text"):
        slides.make_carousel(src, item, item["slides"], tmp_path / "out", tmp_path / "pack-plan.json", 2)


def test_cards_go_to_brand_studio_as_story_and_feed_pages(tmp_path, monkeypatch):
    from brand_studio import api
    src, _ = _carousel(tmp_path)
    calls = []
    monkeypatch.setattr(api, "render_set_to", lambda brand, key, pages, out, names, **k: (
        calls.append((key, pages, names, k["offset"])) or [out / f"{names[0]}.jpg"], []))
    cheat = {"id": "d03-story", "format": "story", "lessonId": "demo-01", "topic": 1,
             "card": {"kind": "cheat", "headers": ["Keyword"], "rows": [["route", "Links a URL", "@app.route"]], "source": {}}}
    compare = {"id": "d04-feed", "format": "feed", "lessonId": "demo-01", "topic": 1,
               "card": {"kind": "compare", "bad": {"head": "M", "code": "x", "lang": "python", "reason": "r"},
                        "good": {"head": "F", "code": "y", "lang": "python", "reason": "s"}, "source": {}}}
    assert slides.make_card(src, cheat, 1920, tmp_path, tmp_path / "pack-plan.json", 2).name == "d03-story.jpg"
    slides.make_card(src, compare, 1350, tmp_path, tmp_path / "pack-plan.json", 3)
    assert [c[1][0][0] for c in calls] == ["cheat-story", "compare"] and [c[2] for c in calls] == [["d03-story"], ["d04-feed"]]
    assert calls[0][1][0][1] == {"rows": [["route", "Links a URL", "@app.route"]]} and [c[3] for c in calls] == [2, 3]


def test_a_full_four_line_cover_hook_passes_the_guard():
    import draw
    hook = "Never scale before the split: fit the scaler on training rows, then predict"   # 4 lines of 18: 75 characters
    assert len(hook) == 75 and draw.fits(hook, 18, 4)
    assert studio.fit_errors([studio.slide_page({"kind": "cover", "hook": hook, "course": "C"}, "Demo Course", 0)]) == []
