"""Test fixtures: a tiny course workdir shaped like a real one (output JSON + images/video)."""
import json
from pathlib import Path

LESSON_HTML = (
    "<div class='nerdit-wrapper'><h2>1 — Make a Project Folder</h2><p>Each project gets its own venv.</p>"
    '<div class="nerdit-figure" data-nerdit-img="fig-demo-1"><svg viewBox="0 0 200 100" role="img" aria-label="Two folders">'
    '<rect x="10" y="10" width="80" height="80" fill="var(--teal)"/></svg></div>'
    "<h2>2 — Install FastAPI</h2><p>pip installs 2 packages here.</p></div>"
)

QUESTIONS = [
    {"id": "q1", "text": "Which command makes a venv?", "options": ["python -m venv .venv", "pip venv", "venv new", "python venv"],
     "correctOptionIndex": 0},
]


def scene(lesson: str, topic: int, title: str, key_idea: str, terms: list[str], myth=None) -> dict:
    return {"kind": "vector", "lessonId": lesson, "topic": topic, "title": title, "vector": f"{lesson}-t{topic}.svg",
            "keyIdea": key_idea, "terms": terms, "focus": [], "myth": myth, "purpose": "p",
            "narration": "Imagine आपके पास दो projects हैं, और project folder बनाते हैं।"}


def write_workdir(root: Path, name: str = "demo", topics: int = 2) -> Path:
    wd = root / name
    vid = wd / "images" / "video"
    vid.mkdir(parents=True)
    course = {"id": f"course-{name}-1", "title": "Demo Course", "lessonIds": ["demo-01"],
              "lessons": [{"id": "demo-01", "title": "Getting Started", "content": LESSON_HTML, "duration": "10 min",
                           "questions": QUESTIONS}]}
    (wd / f"course-{name}_output.json").write_text(json.dumps(course), encoding="utf-8")
    scenes = [scene("demo-01", t, f"Topic {t}", f"Key idea {t}", ["project folder"]) for t in range(1, topics + 1)]
    plan = {"version": 1, "course": "Demo Course", "source": str(wd / f"course-{name}_output.json"),
            "intro": {"title": "Demo", "points": ["a"], "narration": "x"}, "scenes": scenes,
            "recap": {"points": ["a"], "narration": "x"},
            "clips": [{"topic": t, "objective": f"Objective {t}", "lessonId": "demo-01"} for t in range(1, topics + 1)]}
    (vid / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    clips = [{"key": "demo-01-intro-video", "place": "intro", "lessonId": "demo-01", "topic": None, "title": "Intro",
              "start": 0.0, "end": 10.0, "file": "clip-01-demo-01-intro.mp4"}]
    t = 10.0
    for n in range(1, topics + 1):
        clips.append({"key": f"demo-01-t{n}-video", "place": "topic", "lessonId": "demo-01", "topic": n,
                      "title": f"Topic {n}", "start": t, "end": t + 40.0, "file": f"clip-{n + 1:02d}-demo-01-t{n}.mp4"})
        t += 40.0
    clips.append({"key": "demo-01-recap-video", "place": "recap", "lessonId": "demo-01", "topic": None, "title": "Recap",
                  "start": t, "end": t + 12.0, "file": f"clip-{topics + 2:02d}-demo-01-recap.mp4"})
    (vid / "clips.json").write_text(json.dumps(clips), encoding="utf-8")
    return wd


def synthetic_mp4(path: Path, width: int, height: int, seconds: float) -> Path:
    """A small H.264 + AAC test video (lavfi), for checks that need a real file."""
    import subprocess
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=size={width}x{height}:rate=30:duration={seconds}", "-f", "lavfi", "-i",
                    f"sine=frequency=440:duration={seconds}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-shortest", str(path)], check=True)
    return path
