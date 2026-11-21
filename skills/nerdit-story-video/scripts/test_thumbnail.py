"""The story video's thumbnail is drawn by brand-studio in the course's look (owner 2026-11-20)."""
import json

import pytest
from PIL import Image

RUN = ('<div class="nerdit-run"><div class="nerdit-in"><pre data-lang="python"><button class="nerdit-copy-btn">Copy</button>'
       '<code>app = Flask(__name__)</code></pre></div></div>')


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAND_STUDIO_HOME", str(tmp_path / "studio-home"))
    from brand_studio.assets import add_icons, add_photos
    icons = tmp_path / "icons"
    icons.mkdir()
    Image.new("RGBA", (256, 256), (20, 160, 140, 255)).save(icons / "laptop_3d.png")
    add_icons("nerdit", icons)
    shots = tmp_path / "shots"
    shots.mkdir()
    Image.new("RGB", (928, 1152), (214, 214, 216)).save(shots / "st01.png")
    add_photos("nerdit", shots, {"st01": {"facing": "left", "pose": "p", "outfit": "o", "kind": "cutout"}})
    work = tmp_path / "work"
    vid = work / "images" / "video"
    vid.mkdir(parents=True)
    course = {"id": "c1", "title": "", "lessons": [{"id": "l1", "title": "The Application Object", "content": RUN},
                                                   {"id": "l2", "title": "Routes", "content": "<p>Routes.</p>"}]}
    course_path = work / "course-flask-demo_output.json"
    course_path.write_text(json.dumps(course), encoding="utf-8")
    plan = {"course": "Flask Demo", "scenes": [{"keyIdea": "One app object holds your pages."}]}
    return vid, plan, course_path


def test_thumbnail_uses_the_course_look_and_a_library_photo(setup):
    from brand_studio.looks import history_path, load_history
    from build_video import make_thumbnail
    vid, plan, course_path = setup
    out = make_thumbnail(vid, plan, course_path)
    assert out == vid / "thumbnail.jpg" and Image.open(out).size == (1280, 720)
    keys = {e["key"] for e in load_history(history_path("nerdit"))["looks"]}
    assert keys == {"flask-demo:thumbnail"}


def test_thumbnail_takes_the_owners_photo_when_named(setup):
    from brand_studio.assets import pick_photo
    from build_video import make_thumbnail
    vid, plan, course_path = setup
    Image.new("RGB", (928, 1152), (220, 220, 222)).save(vid / "me.png")
    make_thumbnail(vid, {**plan, "thumbnail": {"photo": "me.png"}}, course_path)
    assert (vid / "thumbnail.jpg").is_file()
    assert pick_photo("nerdit", kind="cutout", course="flask-demo:thumbnail")["used_by"] == []   # library photo untouched


def test_dark_owner_photo_is_refused_with_its_name(setup):
    from build_video import make_thumbnail
    vid, plan, course_path = setup
    Image.new("RGB", (928, 1152), (50, 50, 50)).save(vid / "me.png")
    with pytest.raises(SystemExit, match="me.png: background"):
        make_thumbnail(vid, {**plan, "thumbnail": {"photo": "me.png"}}, course_path)


def test_key_idea_numbers_must_come_from_the_course(setup):
    # final review I5
    from build_video import make_thumbnail
    vid, plan, course_path = setup
    with pytest.raises(SystemExit, match="key idea: 95 is not in the course"):
        make_thumbnail(vid, {**plan, "thumbnail": {"key_idea": "Ship 95 apps in a week."}}, course_path)


def test_a_thumbnail_error_never_loses_clips_json(setup, monkeypatch):
    # final review I2: the thumbnail runs after a long render; clips.json is written first and any error is caught
    import build_video
    vid, plan, course_path = setup
    monkeypatch.setattr(build_video, "make_thumbnail", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    build_video.finish_build(vid, plan, course_path, [{"key": "k"}])
    assert json.loads((vid / "clips.json").read_text(encoding="utf-8")) == [{"key": "k"}]


def test_thumbnail_problems_are_listed_before_the_render(setup):
    from build_video import thumbnail_warnings
    vid, plan, course_path = setup
    Image.new("RGB", (928, 1152), (50, 50, 50)).save(vid / "me.png")
    warnings = thumbnail_warnings(vid, {**plan, "thumbnail": {"photo": "me.png"}}, course_path)
    assert any("me.png: background" in w for w in warnings)
    assert thumbnail_warnings(vid, plan, course_path) == []
