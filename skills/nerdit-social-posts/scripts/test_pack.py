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
    assert reel["captions"] == {"instagram": "", "facebook": "", "pinterest": "", "youtube": ""}
    carousel = next(i for i in plan["items"] if i["format"] == "carousel" and i.get("kind") != "intro")
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


def test_pilot_items_are_the_first_reel_carousel_and_picture_card():
    # part 2b: every card is drawn anew by brand-studio, so picture cards join the pilot
    items = [{"id": "d01-feed", "format": "feed"}, {"id": "d01-reel", "format": "reel"},
             {"id": "d02-reel", "format": "reel"}, {"id": "d03-carousel", "format": "carousel"}]
    assert [i["id"] for i in build_pack.pilot_items(items)] == ["d01-feed", "d01-reel", "d03-carousel"]


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


# test_make_card_draws_the_cheat_and_compare_cards moved to test_studio.py (cards go through brand-studio)


# ---- the course look (part 2b): one brand-studio look per course, reserved at plan time ----
from brand_studio.looks import history_path, load_history, load_looks, save_history  # noqa: E402


def studio_entries() -> list[dict]:
    return load_history(history_path("nerdit"))["looks"]


def test_plan_reserves_one_course_look_and_items_carry_no_style(tmp_path, capsys):
    packdir = run_plan(write_workdir(tmp_path), "2026-11-19", 2)
    entries = studio_entries()
    assert {e["key"] for e in entries} == {"demo:reserved"} and len({e["look"] for e in entries}) == 1
    assert f"course look: {entries[0]['look']}" in capsys.readouterr().out
    items = json.loads((packdir / "pack-plan.json").read_text(encoding="utf-8"))["items"]
    assert not any("style" in i for i in items)


def test_two_courses_never_share_a_look(tmp_path):
    run_plan(write_workdir(tmp_path / "a"), "2026-11-19", 2)
    run_plan(write_workdir(tmp_path / "b", name="demo2"), "2026-11-19", 2)
    looks = {e["key"]: e["look"] for e in studio_entries()}
    assert set(looks) == {"demo:reserved", "demo2:reserved"} and len(set(looks.values())) == 2


def test_force_replan_keeps_the_course_look(tmp_path):
    wd = write_workdir(tmp_path)
    run_plan(wd, "2026-11-19", 2)
    first = {e["look"] for e in studio_entries()}
    run_plan(wd, "2026-11-19", 2, "--force")
    assert {e["look"] for e in studio_entries()} == first and len(studio_entries()) == 2


def test_no_fresh_course_look_stops_plan_and_writes_nothing(tmp_path, capsys):
    held = [{"look": l["name"], "variant": v, "key": f"o{i}", "itemId": "x", "built": True}
            for i, l in enumerate(load_looks("nerdit")) for v in ("a", "b")]
    save_history(history_path("nerdit"), {"looks": held})
    wd = write_workdir(tmp_path)
    assert build_pack.main(["plan", str(wd), "--start", "2026-11-19", "--url", LIVE_URL]) == 1
    assert "No fresh looks left" in capsys.readouterr().out and not list(wd.glob("social-pack/*/pack-plan.json"))


def test_render_items_draws_reels_in_the_course_look(tmp_path, monkeypatch):
    import cues
    import reel
    from source import load_source
    src = load_source(write_workdir(tmp_path))
    out = tmp_path / "out"
    out.mkdir()
    (out / "pack-plan.json").write_text("{}", encoding="utf-8")
    seen = {}

    def fake_reel(src, it, hook, out_dir, tl=None, pad=True, look=None):
        seen["look"] = look
        return out_dir / "d01-reel.mp4", out_dir / "d01-reel-cover.jpg"

    monkeypatch.setattr(cues, "checked_timeline", lambda s: {})
    monkeypatch.setattr(reel, "make_reel", fake_reel)
    item = {"id": "d01-reel", "format": "reel", "date": "2026-11-19", "time": "19:00", "hook": "h",
            "platforms": ["instagram"], "captions": {"instagram": "x"}}
    build_pack.render_items(src, {"courseUrl": LIVE_URL, "start": "2026-11-19"}, [item], out)
    assert seen["look"]["name"] in {l["name"] for l in load_looks("nerdit")}
    assert {e["key"] for e in studio_entries()} == {"demo:reserved"}


def test_pilot_covers_every_format():
    car = lambda iid, kind: {"id": iid, "format": "carousel", "slides": [{"kind": "cover"}, {"kind": kind}, {"kind": "cta"}]}  # noqa: E731
    items = [{"id": "d01-reel", "format": "reel"}, car("d01-carousel", "predict-q"), {"id": "d01-story", "format": "story", "card": {"kind": "cheat"}},
             {"id": "d02-reel", "format": "reel"}, {"id": "d02-story", "format": "story"}, car("d03-carousel", "idea"),
             car("d05-carousel", "wrong"), car("d06-carousel", "predict-q"), {"id": "d04-feed", "format": "feed", "card": {"kind": "compare"}},
             {"id": "d05-feed", "format": "feed"}]
    assert [i["id"] for i in build_pack.pilot_items(items)] == [
        "d01-reel", "d01-carousel", "d01-story", "d02-story", "d03-carousel", "d05-carousel", "d04-feed", "d05-feed"]


def test_every_module_imports_on_its_own():
    import subprocess, sys
    here = Path(__file__).resolve().parent
    for name in ("packcheck", "slides", "teach", "blocks", "studio", "draw", "captions", "reel", "cues", "build_pack"):
        r = subprocess.run([sys.executable, "-c", f"import {name}"], cwd=here, capture_output=True, text=True)
        assert r.returncode == 0, f"{name}: {r.stderr.strip().splitlines()[-1]}"


# ---- final review fixes ----
def compare_carousel(tmp_path):
    from test_teach import ITEM_T2, src_with
    import teach
    src = src_with(tmp_path, FLASK)
    return {**ITEM_T2, "slides": teach.teaching_carousel(src, ITEM_T2, set(), "predict")["slides"]}


def test_a_teaching_slide_without_its_source_is_an_error(tmp_path):
    from packcheck import source_errors
    _, items, blocks = planned(tmp_path)
    del items[0]["slides"][1]["source"]
    items[0]["slides"][1]["code"] = "import os"
    assert source_errors(items, blocks) == ["d01-carousel: slide 2: teaching slide has no source"]


def test_flattened_truncated_and_cross_field_code_is_caught(tmp_path):
    from packcheck import source_errors
    for k, change in enumerate((lambda s: s.replace("\n", " "), lambda s: s.split("\n")[0],
                   lambda s: "The variable name does not matter.")):
        _, items, blocks = planned(tmp_path / str(k))
        items[0]["slides"][1]["code"] = change(items[0]["slides"][1]["code"])
        assert source_errors(items, blocks) == ["d01-carousel: slide 2: text not found in demo-01 predict 0"]


def test_swapped_wrong_and_right_are_caught(tmp_path):
    from packcheck import source_errors
    car = compare_carousel(tmp_path)
    car["slides"][1]["head"], car["slides"][2]["head"] = car["slides"][2]["head"], car["slides"][1]["head"]
    assert source_errors([car], {"demo-01": lesson_blocks(FLASK)}) == [
        "d02-carousel: slide 2: text not found in demo-01 compare 0", "d02-carousel: slide 3: text not found in demo-01 compare 0"]


def test_an_invented_cheat_row_is_caught(tmp_path):
    from packcheck import source_errors
    src, items, blocks = planned(tmp_path)
    import teach
    from test_teach import ITEM_T1
    story = {**ITEM_T1, "id": "d01-story", "format": "story", "card": teach.story_card(src, ITEM_T1, True)}
    story["card"]["rows"][0] = ["route", "Invented meaning", "@app.route('/')"]
    assert source_errors([story], blocks) == ["d01-story: card: text not found in demo-01 cheatsheet 0"]


def test_plan_without_topics_or_video_stops_with_a_clear_message(tmp_path):
    import json
    import shutil
    from datetime import date as _date
    from conftest import write_workdir
    from build_pack import plan_pack
    wd = write_workdir(tmp_path)
    shutil.rmtree(wd / "images" / "video")
    course_file = wd / "course-demo_output.json"
    course = json.loads(course_file.read_text(encoding="utf-8"))
    course["lessons"][0]["content"] = "<p>No numbered sections here.</p>"
    course_file.write_text(json.dumps(course), encoding="utf-8")
    with pytest.raises(SystemExit, match="no lesson topics found"):
        plan_pack(wd, _date(2026, 11, 23), 10, "https://nerdit.in/course/demo/preview")


def test_course_without_video_plans_no_reels(tmp_path):
    import shutil
    from datetime import date as _date
    from conftest import write_workdir
    from build_pack import plan_pack
    wd = write_workdir(tmp_path)
    shutil.rmtree(wd / "images" / "video")
    plan = plan_pack(wd, _date(2026, 11, 23), 10, "https://nerdit.in/course/demo/preview")
    assert plan["items"] and not [i for i in plan["items"] if i["format"] == "reel"]


def test_course_with_video_still_plans_reels_with_hooks(tmp_path):
    from datetime import date as _date
    from conftest import write_workdir
    from build_pack import plan_pack
    plan = plan_pack(write_workdir(tmp_path), _date(2026, 11, 23), 10, "https://nerdit.in/course/demo/preview")
    reels = [i for i in plan["items"] if i["format"] == "reel"]
    assert reels and all(r.get("hook") and r.get("clipKey") for r in reels)


def test_render_items_writes_the_carousel_pin_slides(tmp_path, monkeypatch):
    import slides
    from source import load_source
    src = load_source(write_workdir(tmp_path))
    out = tmp_path / "out"
    out.mkdir()
    (out / "pack-plan.json").write_text("{}", encoding="utf-8")
    kinds = ["cover", "idea", "idea", "diagram", "quiz", "answer", "cta"]
    monkeypatch.setattr(slides, "make_carousel", lambda src, it, sl, out_dir, marker, day=0: [out_dir / f"{it['id']}-{i:02d}.jpg" for i in range(len(sl))])
    item = {"id": "d03-carousel", "format": "carousel", "date": "2026-11-21", "time": "13:00",
            "platforms": ["instagram", "pinterest"], "captions": {"instagram": "x", "pinterest": "T\n\nD"},
            "slides": [{"kind": k} for k in kinds]}
    made = build_pack.render_items(src, {"courseUrl": LIVE_URL, "start": "2026-11-19"}, [item], out)
    assert made[0]["pinterestMedia"] == [0, 1, 2, 3]
    no_pin = dict(item, id="d05-carousel", platforms=["instagram"], captions={"instagram": "x"})
    assert "pinterestMedia" not in build_pack.render_items(src, {"courseUrl": LIVE_URL, "start": "2026-11-19"}, [no_pin], out)[0]
