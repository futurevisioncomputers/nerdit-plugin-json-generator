import json

import pytest

from captions import caption_errors, utm_link
from shorts import shorts_errors, write_kit

URL = "https://nerdit.in/course/demo/preview"
LESSON = "A route links a URL to a view function. Python 3.12 works."
ITEM = {"id": "d01-reel", "date": "2026-11-21", "time": "19:00", "format": "reel"}
GOOD = ("A route links a URL to a view function\n\n"
        "Flask routes in one minute, from our free course.\n\nFull lesson: {link}\n\n#python #flask #shorts")


def yt(text, item=ITEM):
    return caption_errors("youtube", "reel", text.replace("{link}", utm_link(URL, "youtube", item)), LESSON, item, URL)


def test_good_youtube_caption_passes():
    assert yt(GOOD) == []


def test_title_over_100_characters_is_refused():
    assert "youtube: title is 101 characters; at most 100" in yt("a" * 101 + GOOD[GOOD.index("\n"):])


def test_angle_brackets_are_refused():
    assert "youtube: no < or > (YouTube rejects them)" in yt(GOOD.replace("one minute", "<h1> in one minute"))


def test_title_must_be_english_and_link_free():
    errors = yt("रूट Flask https://nerdit.in" + GOOD[GOOD.index("\n"):])
    assert "youtube: title in English (no Devanagari)" in errors
    assert "youtube: no link in the title" in errors


def test_youtube_link_is_required():
    assert yt(GOOD.replace("{link}", "nerdit.in")) == ["youtube: needs the course link " + utm_link(URL, "youtube", ITEM)]


def test_more_than_15_hashtags_is_refused():
    assert "youtube: 16 hashtags; at most 15" in yt(GOOD + " " + " ".join(f"#t{c}" for c in "abcdefghijklm"))


def test_empty_title_line_is_refused():
    assert "youtube: first line is the title; it is empty" in yt("\n\nFlask routes {link}")


def plan(captions=True):
    reel = lambda n, title: {"id": f"d0{n}-reel", "date": f"2026-11-2{n}", "time": "19:00", "format": "reel",
                             "lessonId": "l1", "platforms": ["instagram", "facebook"],
                             "captions": {"instagram": "x", "facebook": "y",
                                          **({"youtube": f"{title}\n\nLearn it free: {{link}}\n\n#flask"} if captions else {})}}
    story = {"id": "d01-story", "date": "2026-11-21", "time": "10:00", "format": "story", "lessonId": "l1",
             "platforms": ["instagram"], "captions": {"instagram": ""}}
    return {"packId": "demo-2026-11-21", "courseUrl": URL, "start": "2026-11-21", "days": 10, "course": "Flask Web Development",
            "items": [story, reel(1, "A route links a URL to a view function"), reel(2, "Activate first, then install Flask")]}


def packdir_with_reels(tmp_path, p):
    d = tmp_path / "social-pack" / p["packId"]
    d.mkdir(parents=True)
    for it in p["items"]:
        if it["format"] == "reel":
            (d / f"{it['id']}.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + it["id"].encode())
    (d / "pack-plan.json").write_text(json.dumps(p), encoding="utf-8")
    return d


def test_kit_copies_each_reel_and_lists_title_description_link_and_schedule(tmp_path):
    p = plan()
    d = packdir_with_reels(tmp_path, p)
    md = write_kit(p, d, course="Flask Web Development").read_text(encoding="utf-8")
    files = sorted(f.name for f in (d / "youtube").glob("*.mp4"))
    assert files == ["d01-reel-a-route-links-a-url-to-a-view-function.mp4", "d02-reel-activate-first-then-install-flask.mp4"]
    assert (d / "youtube" / files[0]).read_bytes() == (d / "d01-reel.mp4").read_bytes()
    assert (d / "d01-reel.mp4").exists()                       # copied, not moved
    assert "Day 1 · 2026-11-21 19:00 IST" in md and "Day 2 · 2026-11-22 19:00 IST" in md
    assert "A route links a URL to a view function" in md
    assert utm_link(URL, "youtube", {"id": "d01-reel", "date": "2026-11-21"}) in md
    assert "Tags: flask" in md and "Playlist: Flask Web Development" in md and "not made for kids" in md
    assert "d01-story" not in md


def test_start_moves_every_date_and_the_link_campaign(tmp_path):
    p = plan()
    d = packdir_with_reels(tmp_path, p)
    md = write_kit(p, d, start="2026-11-30", course="Flask Web Development").read_text(encoding="utf-8")
    assert "Day 1 · 2026-11-30 19:00 IST" in md and "Day 2 · 2026-12-01 19:00 IST" in md
    assert "utm_campaign=pack-2026-11-30&utm_content=d01-reel" in md
    assert "2026-11-21 19:00" not in md


def test_errors_name_a_reel_without_a_youtube_caption_and_a_missing_file(tmp_path):
    p = plan(captions=False)
    d = packdir_with_reels(tmp_path, p)
    (d / "d02-reel.mp4").unlink()
    errors = shorts_errors(p, d, {"l1": LESSON})
    assert "d01-reel: write captions.youtube (title line, blank line, description)" in errors
    assert "d02-reel: d02-reel.mp4 is missing; run build first" in errors
    with pytest.raises(SystemExit, match="d01-reel: write captions.youtube"):
        write_kit(p, d, course="Flask Web Development")


def test_errors_include_the_caption_rules(tmp_path):
    p = plan()
    p["items"][1]["captions"]["youtube"] = "a" * 120 + "\n\nLearn it free: {link}"
    d = packdir_with_reels(tmp_path, p)
    assert "d01-reel: youtube: title is 120 characters; at most 100" in shorts_errors(p, d, {"l1": LESSON})


def test_shorts_command_writes_the_kit_with_the_admin_day_1(tmp_path, monkeypatch):
    import build_pack
    p = plan()
    d = packdir_with_reels(tmp_path, p)
    monkeypatch.setattr(build_pack.source, "load_source", lambda wd: {"course": {"title": "Flask Web Development"}})
    monkeypatch.setattr(build_pack.packcheck, "lesson_texts", lambda wd: {"l1": LESSON})
    assert build_pack.main(["shorts", str(d), "--start", "2026-11-30"]) == 0
    md = (d / "youtube" / "SHORTS.md").read_text(encoding="utf-8")
    assert "Day 1 · 2026-11-30 19:00 IST" in md and "Playlist: Flask Web Development" in md


def test_shorts_command_reports_problems_and_fails(tmp_path, monkeypatch, capsys):
    import build_pack
    p = plan(captions=False)
    d = packdir_with_reels(tmp_path, p)
    monkeypatch.setattr(build_pack.source, "load_source", lambda wd: {"course": {"title": "Flask"}})
    monkeypatch.setattr(build_pack.packcheck, "lesson_texts", lambda wd: {"l1": LESSON})
    assert build_pack.main(["shorts", str(d)]) == 1
    assert "PROBLEM d01-reel: write captions.youtube" in capsys.readouterr().out
    assert not (d / "youtube").exists()
