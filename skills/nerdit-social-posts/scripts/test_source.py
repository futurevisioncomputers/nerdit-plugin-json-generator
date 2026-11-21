import shutil

import pytest

from conftest import write_workdir
from source import load_source, reel_window


def test_load_source_reads_course_and_topic_clips(tmp_path):
    src = load_source(write_workdir(tmp_path))
    assert src["name"] == "demo"
    assert src["course"]["id"] == "course-demo-1"
    assert src["course"]["title"] == "Demo Course"
    assert [c["place"] for c in src["clips"]] == ["topic", "topic"]
    assert src["lessons"]["demo-01"]["questions"][0]["id"] == "q1"
    assert "fig-demo-1" in src["figures"]


def test_no_video_folder_loads_topics_from_headings(tmp_path):
    # owner 2026-11-20 (brand-studio spec): the story video is optional; topics come from the lesson's sections
    wd = write_workdir(tmp_path)
    shutil.rmtree(wd / "images" / "video")
    src = load_source(wd)
    assert src["has_video"] is False and src["video"] is None and src["plan"] == {"scenes": []}
    assert [(c["key"], c["topic"], c["video"]) for c in src["clips"]] == [("demo-01-t1", 1, False), ("demo-01-t2", 2, False)]
    assert src["clips"][0]["title"] == "Make a Project Folder" and src["course"]["title"] == "Demo Course"


def test_video_folder_present_means_has_video(tmp_path):
    assert load_source(write_workdir(tmp_path))["has_video"] is True


def test_missing_clips_json_stops_and_names_it(tmp_path):
    wd = write_workdir(tmp_path)
    (wd / "images" / "video" / "clips.json").unlink()
    with pytest.raises(SystemExit, match="clips.json"):
        load_source(wd)


def test_reel_window_keeps_whole_clip_up_to_90s():
    assert reel_window({"start": 10.0, "end": 82.0}, [20.0, 50.0, 72.0]) == (0.0, 72.0)


def test_reel_window_cuts_long_clip_at_last_scene_end_before_90():
    assert reel_window({"start": 0.0, "end": 130.0}, [40.0, 88.5, 101.0, 130.0]) == (0.0, 88.5)


def test_empty_course_title_falls_back_to_the_video_plan_title(tmp_path):
    import json
    wd = write_workdir(tmp_path)
    path = wd / "course-demo_output.json"
    course = json.loads(path.read_text(encoding="utf-8"))
    course["title"] = ""
    path.write_text(json.dumps(course), encoding="utf-8")
    plan_path = wd / "images" / "video" / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["course"] = "Demo: From the Video"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    assert load_source(wd)["course"]["title"] == "Demo: From the Video"
