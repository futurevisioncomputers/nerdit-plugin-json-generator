import copy
import json
from pathlib import Path

import pytest
from PIL import Image

import build_pack
from captions import utm_link
from conftest import synthetic_mp4, write_workdir
from packcheck import check

URL = "https://nerdit.in/course/course-demo-1/preview"
IG = ("Most beginners install packages globally. A venv keeps each project's packages apart.\n\n"
      "Save this and share it with a friend. Full lesson free, link in bio.\n#python #fastapi")


def make_pack(tmp: Path, eleven_slides=False, duplicate_id=False, date=None, leftover_link=False) -> Path:
    wd = write_workdir(tmp)
    pack = wd / "social-pack" / "demo-2026-11-19"
    pack.mkdir(parents=True)
    synthetic_mp4(pack / "d01-reel.mp4", 1080, 1920, 2)
    for name, size in (("d01-reel-cover.jpg", (1080, 1920)), ("d01-story.jpg", (1080, 1920))):
        Image.new("RGB", size, "navy").save(pack / name)
    slides = [f"d02-carousel-{i:02d}.jpg" for i in range(1, (12 if eleven_slides else 3))]
    for name in slides:
        Image.new("RGB", (1080, 1350), "navy").save(pack / name)
    reel = {"id": "d01-reel", "date": "2026-11-19", "time": "19:00", "format": "reel", "platforms": ["instagram", "facebook"],
            "title": "Topic 1", "media": ["d01-reel.mp4"], "cover": "d01-reel-cover.jpg", "lessonId": "demo-01", "topic": 1,
            "theme": "navy", "layout": "stack"}
    reel["captions"] = {"instagram": IG, "facebook": "Free lesson: " + utm_link(URL, "facebook", reel)}
    story = {"id": "d01-story", "date": "2026-11-19", "time": "10:00", "format": "story", "platforms": ["instagram", "facebook"],
             "title": "Topic 1", "media": ["d01-story.jpg"], "captions": {"instagram": "", "facebook": ""},
             "lessonId": "demo-01", "topic": 1, "theme": "violet", "layout": "stack"}
    carousel = {"id": "d02-carousel", "date": "2026-11-20", "time": "13:00", "format": "carousel",
                "platforms": ["instagram", "linkedin"], "title": "Topic 2", "media": slides, "lessonId": "demo-01",
                "topic": 2, "theme": "light", "layout": "split"}
    carousel["captions"] = {"instagram": IG, "linkedin": "Each project gets its own venv. Free lesson: "
                                                         + utm_link(URL, "linkedin", carousel)}
    items = [reel, story, carousel]
    if duplicate_id:
        items.append({**copy.deepcopy(story), "id": "d01-reel"})
    if date:
        story["date"] = date
    if leftover_link:
        reel["captions"]["facebook"] = "Free lesson: {link}"
    manifest = {"version": 1, "packId": "demo-2026-11-19", "courseId": "course-demo-1", "courseUrl": URL,
                "start": "2026-11-19", "days": 2, "items": items}
    (pack / "pack.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return pack


def test_check_passes_a_good_pack(tmp_path):
    assert check(make_pack(tmp_path)) == []


def test_check_lists_every_problem(tmp_path):
    pack = make_pack(tmp_path, eleven_slides=True, duplicate_id=True, date="2026-12-31", leftover_link=True)
    assert check(pack) == [
        "d02-carousel: 11 slides; at most 10",
        "d01-reel: id used twice",
        "d01-story: 2026-12-31 is outside the pack dates",
        "d01-reel: facebook caption still has {link}",
    ]


def test_check_reports_wrong_image_size_missing_file_and_bad_platform(tmp_path):
    pack = make_pack(tmp_path)
    Image.new("RGB", (1080, 1080), "navy").save(pack / "d01-story.jpg")
    (pack / "d01-reel-cover.jpg").unlink()
    manifest = json.loads((pack / "pack.json").read_text(encoding="utf-8"))
    manifest["items"][0]["platforms"] = ["instagram", "linkedin"]
    manifest["items"][0]["captions"]["linkedin"] = "x"
    (pack / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    problems = check(pack)
    assert "d01-reel: a reel cannot go to linkedin" in problems
    assert "d01-reel: missing d01-reel-cover.jpg" in problems
    assert "d01-story: d01-story.jpg is 1080x1080; expected 1080x1920" in problems


LIVE_URL = "https://nerdit.in/course/demo-course-1794042260740/preview"


def run_plan(wd: Path, start: str, days: int, *extra: str) -> Path:
    assert build_pack.main(["plan", str(wd), "--start", start, "--days", str(days), "--url", LIVE_URL, *extra]) == 0
    return wd / "social-pack" / f"{wd.name}-{start}"


def test_plan_writes_a_draft_with_hooks_and_empty_captions(tmp_path):
    packdir = run_plan(write_workdir(tmp_path), "2026-11-19", 3)
    plan = json.loads((packdir / "pack-plan.json").read_text(encoding="utf-8"))
    assert plan["packId"] == "demo-2026-11-19" and plan["courseId"] == "course-demo-1" and plan["days"] == 2
    assert plan["courseUrl"] == LIVE_URL
    reel = next(i for i in plan["items"] if i["id"] == "d01-reel")
    assert reel["hook"] == "Key idea 1" and reel["title"] == "Topic 1"
    assert reel["captions"] == {"instagram": "", "facebook": ""}
    carousel = next(i for i in plan["items"] if i["format"] == "carousel")
    assert carousel["slides"][0]["kind"] == "cover"


def test_plan_never_overwrites_the_agents_edits(tmp_path):
    wd = write_workdir(tmp_path)
    run_plan(wd, "2026-11-19", 2)
    assert build_pack.main(["plan", str(wd), "--start", "2026-11-19", "--days", "2", "--url", LIVE_URL]) == 1


def test_plan_needs_the_live_course_url(tmp_path):
    with pytest.raises(SystemExit):
        build_pack.main(["plan", str(write_workdir(tmp_path)), "--start", "2026-11-19"])


def test_plan_takes_the_live_course_id(tmp_path):
    packdir = run_plan(write_workdir(tmp_path), "2026-11-19", 2, "--course-id", "pbcJxuHrLEYBxfvn34zn")
    assert json.loads((packdir / "pack-plan.json").read_text(encoding="utf-8"))["courseId"] == "pbcJxuHrLEYBxfvn34zn"


def test_pilot_items_are_the_first_reel_and_the_first_carousel():
    items = [{"id": "d01-feed", "format": "feed"}, {"id": "d01-reel", "format": "reel"},
             {"id": "d02-reel", "format": "reel"}, {"id": "d03-carousel", "format": "carousel"}]
    assert [i["id"] for i in build_pack.pilot_items(items)] == ["d01-reel", "d03-carousel"]


def test_numbers_in_hooks_and_slides_must_come_from_the_lesson():
    from packcheck import plan_text_errors
    items = [{"id": "d01-reel", "format": "reel", "lessonId": "demo-01", "hook": "Install in 40 seconds"},
             {"id": "d02-carousel", "format": "carousel", "lessonId": "demo-01",
              "slides": [{"kind": "cover", "hook": "pip installs 2 packages"}, {"kind": "idea", "text": "Saves 3 hours"}]}]
    assert plan_text_errors(items, {"demo-01": "pip installs 2 packages here."}) == [
        "d01-reel: hook: 40 is not in the lesson", "d02-carousel: slide 2: 3 is not in the lesson"]


def test_plan_can_leave_the_pad_out(tmp_path):
    packdir = run_plan(write_workdir(tmp_path), "2026-11-19", 2, "--no-pad")
    assert json.loads((packdir / "pack-plan.json").read_text(encoding="utf-8"))["pad"] is False


def test_a_second_pack_continues_where_the_first_stopped(tmp_path):
    wd = write_workdir(tmp_path, topics=4)
    first = json.loads((run_plan(wd, "2026-11-19", 2) / "pack-plan.json").read_text(encoding="utf-8"))
    second = json.loads((run_plan(wd, "2026-11-21", 2) / "pack-plan.json").read_text(encoding="utf-8"))
    assert first["pad"] is True
    assert {i["topic"] for i in first["items"]} == {1, 2} and {i["topic"] for i in second["items"]} == {3, 4}


def test_build_stops_when_the_video_timeline_drifted(tmp_path, monkeypatch):
    import cues
    def drift(src):
        raise SystemExit("the story video does not match its plan")
    monkeypatch.setattr(cues, "checked_timeline", drift)
    with pytest.raises(SystemExit, match="does not match"):
        build_pack.render_items({}, {"courseUrl": URL}, [{"id": "d01-reel", "format": "reel"}], tmp_path / "out")


# ---- word-for-word checker and new cards (data-first plan, Task 6) ----
from blocks import lesson_blocks  # noqa: E402
from test_blocks import FLASK  # noqa: E402


def planned(tmp_path):
    from test_teach import ITEM_T1, ITEM_T2, src_with
    import teach
    src = src_with(tmp_path, FLASK)
    car = {**ITEM_T1, "slides": teach.teaching_carousel(src, ITEM_T1, set(), None)["slides"]}
    feed = {**ITEM_T2, "id": "d02-feed", "format": "feed", "card": teach.feed_card(src, ITEM_T2, set(), False)}
    return src, [car, feed], {"demo-01": lesson_blocks(FLASK)}


def test_untouched_plan_passes_the_word_for_word_check(tmp_path):
    from packcheck import source_errors
    _, items, blocks = planned(tmp_path)
    assert source_errors(items, blocks) == []


def test_edited_code_and_edited_card_are_caught(tmp_path):
    from packcheck import source_errors
    _, items, blocks = planned(tmp_path)
    items[0]["slides"][1]["code"] += "\nprint('extra')"
    items[1]["card"]["good"]["reason"] = "Invented reason."
    assert source_errors(items, blocks) == ["d01-carousel: slide 2: text not found in demo-01 predict 0",
                                            "d02-feed: card: text not found in demo-01 compare 0"]


def test_make_card_draws_the_cheat_and_compare_cards(tmp_path, monkeypatch):
    import draw
    import slides as slides_mod
    src, items, _ = planned(tmp_path)
    shot = []
    monkeypatch.setattr(draw, "shoot", lambda pages: shot.extend(pages))
    slides_mod.make_card(src, {**items[1], "style": "navy", "layout": "stack"}, 1350, tmp_path)
    cheat = {**items[1], "id": "d03-story", "format": "story", "style": "ember", "layout": "split",
             "card": {"kind": "cheat", "headers": ["Keyword"], "rows": [["route", "Links a URL", "@app.route"]], "source": {}}}
    slides_mod.make_card(src, cheat, 1920, tmp_path)
    assert "Wrong vs right" in shot[0][0] and "Cheat sheet" in shot[1][0] and shot[1][3] == 1920


# ---- looks in the pack (data-first plan, Task 7) ----
from stylebook import LAYOUTS, history_path, load_history, load_styles, save_history  # noqa: E402


def looks_of(packdir: Path) -> set:
    plan = json.loads((packdir / "pack-plan.json").read_text(encoding="utf-8"))
    return {(i["style"], i["layout"]) for i in plan["items"]}


def test_every_item_gets_a_style_and_layout_and_no_theme(tmp_path):
    plan = json.loads((run_plan(write_workdir(tmp_path), "2026-11-19", 2) / "pack-plan.json").read_text(encoding="utf-8"))
    assert all(i["style"] and i["layout"] in LAYOUTS and "theme" not in i for i in plan["items"])
    looks = [(i["style"], i["layout"]) for i in plan["items"]]
    assert len(set(looks)) == len(looks) and all(a[0] != b[0] and a[1] != b[1] for a, b in zip(looks, looks[1:]))


def test_two_packs_never_share_a_look(tmp_path):
    first = run_plan(write_workdir(tmp_path / "a"), "2026-11-19", 2)
    second = run_plan(write_workdir(tmp_path / "b", name="demo2"), "2026-11-19", 2)
    assert looks_of(first) and not (looks_of(first) & looks_of(second))


def test_force_replan_frees_its_own_looks(tmp_path):
    wd = write_workdir(tmp_path)
    packdir = run_plan(wd, "2026-11-19", 2)
    run_plan(wd, "2026-11-19", 2, "--force")
    items = json.loads((packdir / "pack-plan.json").read_text(encoding="utf-8"))["items"]
    assert len(load_history(history_path())["looks"]) == len(items)


def test_no_fresh_looks_stops_plan(tmp_path, capsys):
    styles = load_styles(Path(__file__).resolve().parents[1] / "styles")
    save_history(history_path(), {"looks": [{"style": s["name"], "layout": l, "packId": "old", "itemId": "x"}
                                            for s in styles for l in LAYOUTS]})
    assert build_pack.main(["plan", str(write_workdir(tmp_path)), "--start", "2026-11-19", "--url", LIVE_URL]) == 1
    assert "run the trend refresh" in capsys.readouterr().out


def test_pilot_covers_every_format():
    car = lambda iid, kind: {"id": iid, "format": "carousel", "slides": [{"kind": "cover"}, {"kind": kind}, {"kind": "cta"}]}  # noqa: E731
    items = [{"id": "d01-reel", "format": "reel"}, car("d01-carousel", "predict-q"), {"id": "d01-story", "format": "story", "card": {"kind": "cheat"}},
             {"id": "d02-reel", "format": "reel"}, {"id": "d02-story", "format": "story"}, car("d03-carousel", "idea"),
             car("d05-carousel", "wrong"), car("d06-carousel", "predict-q"), {"id": "d04-feed", "format": "feed", "card": {"kind": "compare"}},
             {"id": "d05-feed", "format": "feed"}]
    assert [i["id"] for i in build_pack.pilot_items(items)] == [
        "d01-reel", "d01-carousel", "d01-story", "d03-carousel", "d05-carousel", "d04-feed"]
