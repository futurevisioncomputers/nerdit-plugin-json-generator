import copy
import json
from datetime import date

from PIL import Image

import intro
from build_pack import plan_pack
from conftest import write_workdir
from source import load_source

URL = "https://nerdit.in/course/demo/preview"
WORDS = {
    "hook": {"headline": "Why Learn Demo Course?", "highlight": ["Demo Course"], "subline": "Set up a clean project with Python."},
    "questions": {"headline": "Setup Answers Real Questions", "highlight": ["Real Questions"],
                  "cards": [{"text": "Where do my packages go?", "keyword": "packages", "icon": "envelope"},
                            {"text": "Why does each project need a venv?", "keyword": "venv", "icon": "bullseye"},
                            {"text": "How do I start a clean folder?", "keyword": "clean folder", "icon": "memo"}]},
    "learn": {"headline": "What You'll Learn", "highlight": ["Learn"]},
    "project": {"headline": "Build a Real Project", "highlight": ["Real Project"],
                "text": "Make a project folder with its own venv.", "icon": "rocket"},
    "skills": {"headline": "Skills You Will Use", "highlight": ["Skills"],
               "cards": [{"text": "Make a project folder", "icon": "bullseye"}, {"text": "Create a venv", "icon": "brain"},
                         {"text": "Install a package", "icon": "books"}, {"text": "Keep projects apart", "icon": "laptop"}]},
    "cta": {"subline": "One lesson to a clean, working setup."},
    "icons": {"hook": "brain", "learn": "laptop"},
}


def plan(wd, start=date(2026, 11, 23)):
    return plan_pack(wd, start, 10, URL, history={"looks": []})


def test_first_pack_gets_an_intro_on_day_one(tmp_path):
    items = plan(write_workdir(tmp_path, topics=4))["items"]
    intros = [i for i in items if i.get("kind") == "intro"]
    assert len(intros) == 1 and intros[0]["id"] == "d01-intro" and intros[0]["format"] == "carousel"
    assert intros[0]["date"] == "2026-11-23" and intros[0]["time"] == "13:00"
    assert [i["id"] for i in items if i["date"] == "2026-11-23" and i["format"] == "carousel"] == ["d01-intro"]
    assert intros[0]["intro"] == intro.WORDS_SKELETON and intros[0]["captions"] == {"instagram": "", "linkedin": ""}


def test_second_pack_gets_no_intro(tmp_path):
    wd = write_workdir(tmp_path, topics=4)
    earlier = wd / "social-pack" / "demo-2026-11-01"
    earlier.mkdir(parents=True)
    (earlier / "pack-plan.json").write_text(json.dumps({"items": [{"lessonId": "demo-01", "topic": 1}]}), encoding="utf-8")
    assert not [i for i in plan(wd)["items"] if i.get("kind") == "intro"]


def test_intro_takes_day_ones_carousel_slot_or_adds_one():
    src = {"clips": [{"lessonId": "l1", "topic": 1}]}
    friday = [{"id": "d01-story", "date": "2026-11-27", "time": "10:00", "format": "story", "lessonId": "l1", "topic": 1},
              {"id": "d01-carousel", "date": "2026-11-27", "time": "13:00", "format": "carousel", "lessonId": "l1", "topic": 1}]
    intro.add_intro(friday, src, True)
    assert [i["id"] for i in friday] == ["d01-story", "d01-intro"]
    wednesday = [{"id": "d01-story", "date": "2026-11-25", "time": "10:00", "format": "story", "lessonId": "l1", "topic": 1}]
    intro.add_intro(wednesday, src, True)
    assert [i["id"] for i in wednesday] == ["d01-story", "d01-intro"]
    none = copy.deepcopy(wednesday[:1])
    intro.add_intro(none, src, False)
    assert [i["id"] for i in none] == ["d01-story"]


def test_empty_or_untrue_intro_words_stop_the_build_naming_the_field(tmp_path):
    src = load_source(write_workdir(tmp_path))
    item = {"id": "d01-intro", "kind": "intro", "intro": copy.deepcopy(intro.WORDS_SKELETON)}
    assert "d01-intro: intro.hook.headline is empty" in intro.intro_errors(item, src)
    bad = copy.deepcopy(WORDS)
    bad["cta"]["subline"] = "Get a free certificate in 30 days"
    errors = intro.intro_errors({**item, "intro": bad}, src)
    assert any("free certificate" in e for e in errors) and any(e.startswith("d01-intro: cta.subline: 30") for e in errors)
    assert intro.intro_errors({**item, "intro": WORDS}, src) == []


def test_intro_renders_six_slides_with_item_names(tmp_path):
    from brand_studio.assets import add_icons
    icons = tmp_path / "icons"
    icons.mkdir()
    for name in ("brain", "envelope", "bullseye", "memo", "rocket", "books", "laptop"):
        Image.new("RGBA", (256, 256), (20, 160, 140, 255)).save(icons / f"{name}_3d.png")
    add_icons("nerdit", icons)
    wd = write_workdir(tmp_path)
    src = load_source(wd)
    packdir = wd / "social-pack" / "demo-2026-11-23"
    packdir.mkdir(parents=True)
    (packdir / "pack-plan.json").write_text("{}", encoding="utf-8")
    files = intro.render_intro({"id": "d01-intro", "kind": "intro", "intro": WORDS}, src, packdir, packdir / "pack-plan.json")
    assert [f.name for f in files] == [f"d01-intro-{i:02d}.jpg" for i in range(1, 7)]
    assert all(f.is_file() for f in files)


def test_empty_course_title_falls_back_to_the_video_plans_title(tmp_path):
    # final review I1: chapter-generator outputs have "title": ""; the pack already takes the video plan's title
    wd = write_workdir(tmp_path)
    course_file = wd / "course-demo_output.json"
    course = json.loads(course_file.read_text(encoding="utf-8"))
    course["title"] = ""
    course_file.write_text(json.dumps(course), encoding="utf-8")
    src = load_source(wd)
    assert src["course"]["title"] == "Demo Course"
    assert intro.intro_errors({"id": "d01-intro", "kind": "intro", "intro": WORDS}, src) == []
