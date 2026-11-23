from datetime import date

from dayplan import ALLOWED_PLATFORMS, LAYOUTS, PLATFORMS, THEMES, day_plan, layout_for, theme_for

FORMATS = ("reel", "story", "carousel", "feed")


def src_with_topics(n: int) -> dict:
    clips = [{"key": f"l{1 + i // 5:02d}-t{1 + i % 5}-video", "lessonId": f"l{1 + i // 5:02d}", "topic": 1 + i % 5,
              "place": "topic", "start": 40.0 * i, "end": 40.0 * (i + 1)} for i in range(n)]
    return {"clips": clips, "plan": {"scenes": []}}


def test_ten_days_from_a_wednesday():
    items = day_plan(src_with_topics(12), date(2026, 11, 18), 10)
    assert sum(i["format"] == "reel" for i in items) == 10
    assert sum(i["format"] == "story" for i in items) == 10
    assert sum(i["format"] == "carousel" for i in items) == 3    # Fri 20, Tue 24, Fri 27
    assert {i["id"] for i in items if i["date"] == "2026-11-20"} == {"d03-reel", "d03-story", "d03-carousel"}


def test_linkedin_feed_card_on_monday_wednesday_thursday_only():
    items = day_plan(src_with_topics(12), date(2026, 11, 18), 10)
    assert sorted(i["date"] for i in items if i["format"] == "feed") == [
        "2026-11-18", "2026-11-19", "2026-11-23", "2026-11-25", "2026-11-26"]


def test_items_carry_time_platforms_and_the_days_topic():
    items = day_plan(src_with_topics(12), date(2026, 11, 18), 10)
    reel = next(i for i in items if i["id"] == "d02-reel")
    story = next(i for i in items if i["id"] == "d02-story")
    assert reel["time"] == "19:00" and reel["platforms"] == ["instagram", "facebook", "pinterest", "youtube"]
    assert story["time"] == "10:00" and story["clipKey"] == reel["clipKey"] == "l01-t2-video"
    assert {k: reel[k] for k in ("lessonId", "topic")} == {"lessonId": "l01", "topic": 2}


def test_topics_never_repeat_and_pack_shrinks_to_available_topics():
    items = day_plan(src_with_topics(4), date(2026, 11, 18), 10)
    reels = [i for i in items if i["format"] == "reel"]
    assert len(reels) == 4 and len({r["clipKey"] for r in reels}) == 4


def test_same_format_changes_theme_every_day_and_a_day_never_repeats_a_theme():
    for fmt in FORMATS:
        assert all(theme_for(d, fmt) != theme_for(d + 1, fmt) for d in range(30))
    assert all(len({theme_for(d, f) for f in FORMATS}) == 4 for d in range(30))
    assert all(layout_for(d) != layout_for(d + 1) for d in range(30))


def test_themes_layouts_and_platform_tables():
    assert set(THEMES) == {"navy", "violet", "light", "ember", "forest"}
    assert LAYOUTS == ("stack", "split")
    for fmt in FORMATS:
        assert set(PLATFORMS[fmt]) <= set(ALLOWED_PLATFORMS[fmt])
    assert ALLOWED_PLATFORMS["reel"] == ["instagram", "facebook", "pinterest", "youtube"]
    assert all("pinterest" in PLATFORMS[f] and "pinterest" in ALLOWED_PLATFORMS[f] for f in PLATFORMS)   # every pack image pins


def test_topics_used_by_an_earlier_pack_are_skipped():
    items = day_plan(src_with_topics(12), date(2026, 11, 18), 3, skip={("l01", 1), ("l01", 2)})
    assert [i["topic"] for i in items if i["format"] == "reel"] == [3, 4, 5]


def test_no_video_means_no_reels_but_stories_carousels_and_cards_keep_their_days():
    src = src_with_topics(12)
    for c in src["clips"]:
        c["video"] = False
    items = day_plan(src, date(2026, 11, 18), 10)
    assert not [i for i in items if i["format"] == "reel"]
    assert sum(i["format"] == "story" for i in items) == 10 and all(i["time"] == "10:00" for i in items if i["format"] == "story")
    assert sorted(i["date"] for i in items if i["format"] == "carousel") == ["2026-11-20", "2026-11-24", "2026-11-27"]
    assert len([i for i in items if i["format"] == "feed"]) == 5


def test_reels_go_to_youtube_too():
    assert PLATFORMS["reel"] == ["instagram", "facebook", "pinterest", "youtube"]
    assert ALLOWED_PLATFORMS["reel"] == PLATFORMS["reel"]
    assert "youtube" not in PLATFORMS["story"] + PLATFORMS["carousel"] + PLATFORMS["feed"]
