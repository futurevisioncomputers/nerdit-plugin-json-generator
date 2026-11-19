"""Read one course workdir for the social pack: the course JSON, the story video's plan and its topic clips.

The workdir holds `course-<name>_output.json` and `images/video/` (made by nerdit-story-video):
`plan.json` (scenes with key ideas and terms), `clips.json` (one MP4 per topic) and `audio/`.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "nerdit-story-video" / "scripts"))
import storyplan  # noqa: E402  story-video's course readers

MAX_REEL = 90.0   # Instagram's Reel limit, seconds


def _course_file(workdir: Path) -> Path:
    found = sorted(workdir.glob("course-*_output.json"))
    if len(found) != 1:
        raise SystemExit(f"expected one course-<name>_output.json in {workdir}, found {len(found)}")
    return found[0]


def load_source(workdir: Path) -> dict:
    """Everything the pack is made from. Stops (SystemExit) when the story video is missing."""
    workdir = Path(workdir).resolve()
    course_path = _course_file(workdir)
    images = workdir / "images"
    video = images / "video"
    if not video.is_dir():
        raise SystemExit(
            f"no {video}: this course has no local story video. Either download the original MP4 from "
            "YouTube Studio (your own upload), put it at images/video/story.mp4 and re-run the nerdit-story-video "
            "split, or make the pack without Reels.")
    for needed in ("plan.json", "clips.json"):
        if not (video / needed).is_file():
            raise SystemExit(f"missing {video / needed}; run the nerdit-story-video build first")
    data = storyplan.load_json(course_path)
    course = data.get("course", data)
    lessons = {l.get("id", ""): {"title": l.get("title", ""), "content": l.get("content") or "",
                                 "questions": l.get("questions") or []}
               for l in storyplan.course_lessons(course_path)}
    clips = [c for c in storyplan.load_json(video / "clips.json") if c.get("place") == "topic"]
    plan = storyplan.load_json(video / "plan.json")
    return {
        "name": course_path.name[len("course-"):-len("_output.json")],
        # The JSON's title can be empty (set later in the admin); the video plan carries it too.
        "course": {"id": course.get("id", ""), "title": course.get("title") or plan.get("course", "")},
        "course_path": course_path,
        "images": images,
        "video": video,
        "lessons": lessons,
        "plan": plan,
        "clips": clips,
        "figures": storyplan.lesson_figures(course_path, images),
    }


def reel_window(clip: dict, scene_ends: list[float]) -> tuple[float, float]:
    """Clip-local (0, end): the whole clip when it fits a Reel, else up to the last scene end within 90 s."""
    length = round(clip["end"] - clip["start"], 3)
    if length <= MAX_REEL:
        return (0.0, length)
    fitting = [e for e in scene_ends if 0 < e <= MAX_REEL]
    if not fitting:
        raise ValueError(f"{clip.get('file', 'clip')}: no scene ends within {MAX_REEL:.0f} s; cannot cut a Reel")
    return (0.0, max(fitting))
