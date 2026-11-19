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


def run_plan(wd: Path, start: str, days: int) -> Path:
    assert build_pack.main(["plan", str(wd), "--start", start, "--days", str(days)]) == 0
    return wd / "social-pack" / f"{wd.name}-{start}"


def test_plan_writes_a_draft_with_hooks_and_empty_captions(tmp_path):
    packdir = run_plan(write_workdir(tmp_path), "2026-11-19", 3)
    plan = json.loads((packdir / "pack-plan.json").read_text(encoding="utf-8"))
    assert plan["packId"] == "demo-2026-11-19" and plan["courseId"] == "course-demo-1" and plan["days"] == 2
    assert plan["courseUrl"] == "https://nerdit.in/course/course-demo-1/preview"
    reel = next(i for i in plan["items"] if i["id"] == "d01-reel")
    assert reel["hook"] == "Key idea 1" and reel["title"] == "Topic 1"
    assert reel["captions"] == {"instagram": "", "facebook": ""}
    carousel = next(i for i in plan["items"] if i["format"] == "carousel")
    assert carousel["slides"][0]["kind"] == "cover"


def test_plan_never_overwrites_the_agents_edits(tmp_path):
    wd = write_workdir(tmp_path)
    run_plan(wd, "2026-11-19", 2)
    assert build_pack.main(["plan", str(wd), "--start", "2026-11-19", "--days", "2"]) == 1


def test_pilot_items_are_the_first_reel_and_the_first_carousel():
    items = [{"id": "d01-feed", "format": "feed"}, {"id": "d01-reel", "format": "reel"},
             {"id": "d02-reel", "format": "reel"}, {"id": "d03-carousel", "format": "carousel"}]
    assert [i["id"] for i in build_pack.pilot_items(items)] == ["d01-reel", "d03-carousel"]
