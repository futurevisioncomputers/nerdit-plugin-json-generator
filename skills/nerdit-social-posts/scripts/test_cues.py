import copy
import re

import pytest

from conftest import scene
from cues import cues_from_timeline, scene_ends, timeline_errors

MYTH = {"wrong": "pip install works without venv", "right": "Activate venv first", "narration": "x"}
PLAN = {"scenes": [
    scene("demo-01", 1, "One", "Key idea one", ["project folder"]),
    scene("demo-01", 2, "Two", "The decorator ties a path to a function", ["route", "JSON"], MYTH),
    scene("demo-01", 2, "Three", "The dict becomes JSON", []),
]}
# Shaped like story-video timeline.build output.
TL = {"duration": 170.0, "segments": [
    {"kind": "intro", "start": 0.0, "end": 10.0, "points": [0.5]},
    {"kind": "scene", "scene": 1, "start": 10.0, "end": 100.0, "terms": [{"text": "project folder", "t": 20.0}]},
    {"kind": "scene", "scene": 2, "start": 100.0, "end": 130.0,
     "terms": [{"text": "route", "t": 104.0}, {"text": "JSON", "t": 110.0}]},
    {"kind": "myth", "scene": 2, "start": 130.0, "end": 145.0, "rightAt": 136.5},
    {"kind": "scene", "scene": 3, "start": 145.0, "end": 160.0, "terms": []},
    {"kind": "recap", "start": 160.0, "end": 170.0, "points": [160.5]},
]}
CLIP = {"key": "demo-01-t2-video", "start": 100.0, "end": 160.0}


def test_terms_become_clip_local_cues():
    cues = cues_from_timeline(TL, PLAN, CLIP)
    term = next(c for c in cues if c["kind"] == "term")
    assert term["text"] == "route" and term["start"] == pytest.approx(4.0) and term["end"] == pytest.approx(6.2)


def test_key_idea_shows_for_the_whole_scene():
    ideas = [(c["text"], c["start"], c["end"]) for c in cues_from_timeline(TL, PLAN, CLIP) if c["kind"] == "idea"]
    assert ideas == [("The decorator ties a path to a function", 0.0, 30.0), ("The dict becomes JSON", 45.0, 60.0)]


def test_myth_switches_from_wrong_to_right_at_right_at():
    kinds = [(c["kind"], round(c["start"], 1)) for c in cues_from_timeline(TL, PLAN, CLIP) if c["kind"] in ("wrong", "right")]
    assert kinds == [("wrong", 30.0), ("right", 36.5)]


def test_no_devanagari_cue_ever():
    plan = copy.deepcopy(PLAN)
    plan["scenes"][1]["keyIdea"] = "डेकोरेटर path जोड़ता है"
    tl = copy.deepcopy(TL)
    tl["segments"][2]["terms"].append({"text": "रूट", "t": 120.0})
    assert not any(re.search("[ऀ-ॿ]", c["text"]) for c in cues_from_timeline(tl, plan, CLIP))


def test_scene_ends_are_clip_local():
    assert scene_ends(TL, CLIP) == [30.0, 45.0, 60.0]


def src_with_clip(file: str, start: float) -> dict:
    return {"plan": PLAN, "clips": [{"key": "demo-01-t2-video", "place": "topic", "lessonId": "demo-01", "topic": 2,
                                     "start": start, "end": 160.0, "file": file}]}


def test_timeline_mismatch_is_reported():
    assert timeline_errors(TL, src_with_clip(file="clip-02-demo-01-t1.mp4", start=99.0)) == [
        "clip-02-demo-01-t1.mp4: starts 99.000 s in clips.json, 100.000 s in the plan timings; rebuild the video first"]


def test_matching_timeline_has_no_errors():
    assert timeline_errors(TL, src_with_clip(file="clip-03-demo-01-t2.mp4", start=100.0)) == []


def test_checked_timeline_stops_when_the_video_drifted(monkeypatch):
    import cues
    monkeypatch.setattr(cues, "course_timeline", lambda src: TL)
    with pytest.raises(SystemExit, match="rebuild the video first"):
        cues.checked_timeline(src_with_clip(file="clip-02-demo-01-t1.mp4", start=99.0))


def test_course_timeline_falls_back_to_the_workdir_course_when_the_plan_source_moved(monkeypatch, tmp_path):
    import cues
    seen = {}
    monkeypatch.setattr(cues.storyplan, "lesson_practice", lambda path: seen.setdefault("path", path) and None)
    monkeypatch.setattr(cues.build_video, "clip_info", lambda audio, plan: {})
    monkeypatch.setattr(cues.build_video, "vector_labels", lambda plan, vid: {})
    monkeypatch.setattr(cues.timeline, "build", lambda *a: {"segments": [], "duration": 0.0})
    course = tmp_path / "course-x_output.json"
    course.write_text("{}", encoding="utf-8")
    cues.course_timeline({"plan": {"source": str(tmp_path / "moved" / "x.json")}, "video": tmp_path, "course_path": course})
    assert seen["path"] == course
