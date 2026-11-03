import json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import lipsync, shorts   # noqa: E402

PROGRAM = ('<pre data-lang="python"><code># hello.py - then open http://127.0.0.1:5000/\n'
           'from flask import Flask\n\napp = Flask(__name__)\n\n\n'
           '@app.route("/")\ndef home():\n    return "Hello"\n</code></pre>')


@pytest.fixture
def course(tmp_path):
    data = {"lessons": [{"id": "flask-hello-01", "title": "Hello",
                         "content": f"<p>Flask in 28 lessons.</p>{PROGRAM}"}]}
    path = tmp_path / "course.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def presenter(tmp_path):
    (tmp_path / "presenter" / "ref").mkdir(parents=True)
    for name in ("CONSENT.md", "ref/face_drive.mp4", "ref/voice_ref10.wav"):
        (tmp_path / "presenter" / name).write_text("x", encoding="utf-8")
    return tmp_path / "presenter"


def plan(**over):
    p = {"lines": [
        {"say": "क्या आप Python से web application बनाना चाहते हैं? तो शुरुआत कीजिए Flask के साथ।",
         "cues": [{"at": "क्या", "lead": "Build with Python", "key": "web application"},
                  {"at": "तो", "lead": "Start with", "key": "Flask"}]},
        {"say": "पहला program सिर्फ़ चार lines का है, और आप इसे अपने computer पर run करेंगे।",
         "explore": [{"at": "पहला", "topic": "First program", "code": {"lesson": "flask-hello-01", "program": 1}}]},
        {"say": "तो चलिए, आज से Flask सीखना शुरू करते हैं, step by step, एक lesson एक दिन।"}],
        "end": {"title": "Flask Web Development", "subtitle": "28 lessons"}}
    p.update(over)
    return p


def test_code_ref_takes_the_file_name_and_drops_its_comment(course):
    lessons = {l["id"]: l for l in shorts.course_lessons(course)}
    name, code = shorts.code_ref({"lesson": "flask-hello-01", "program": 1}, lessons)
    assert name == "hello.py" and code.splitlines()[0] == "from flask import Flask"
    name, code = shorts.code_ref({"lesson": "flask-hello-01", "program": 1, "lines": [7, 8]}, lessons)
    assert code == 'def home():\n    return "Hello"'


def test_a_good_plan_passes(course, presenter):
    assert shorts.check(plan(), course, presenter) == []


def test_consent_is_required(course, presenter):
    (presenter / "CONSENT.md").unlink()
    assert any("CONSENT.md" in e for e in shorts.check(plan(), course, presenter))


def test_screen_text_is_english_and_numbers_come_from_the_course(course, presenter):
    p = plan(end={"title": "Flask सीखें", "subtitle": "40 lessons"})
    errors = shorts.check(p, course, presenter)
    assert any("English only" in e for e in errors) and any("40 on screen" in e for e in errors)


def test_cues_name_a_word_of_their_line_and_code_must_exist(course, presenter):
    p = plan()
    p["lines"][0]["cues"][0]["at"] = "Django"
    p["lines"][1]["explore"][0]["code"]["program"] = 5
    errors = shorts.check(p, course, presenter)
    assert any("'Django' is not a word" in e for e in errors)
    assert any("is not a program in the course" in e for e in errors)


def test_a_line_has_cues_or_explore_not_both(course, presenter):
    p = plan()
    p["lines"][1]["cues"] = [{"at": "पहला", "lead": "x", "key": "y"}]
    assert any("not both" in e for e in shorts.check(p, course, presenter))


def test_timeline_places_events_by_word_position(course):
    spec = shorts.timeline(plan(), course, [4.0, 5.0, 3.0])
    assert spec["duration"] == round(4.0 + 5.0 + 3.0 + 2 * shorts.PAUSE, 2)
    first, second = spec["captions"]
    assert first[0] == 0.0 and first[1] == second[0] and 1.0 < second[0] < 4.0
    explore = spec["explore"][0]
    assert explore[0] == round(4.0 + shorts.PAUSE, 2) and explore[3] == "hello.py"
    assert spec["end"][0] == round(9.0 + 2 * shorts.PAUSE, 2)


def test_lipsync_uses_the_256px_model():
    cmd = lipsync.command("py", Path("f.mp4"), Path("v.wav"), Path("o.mp4"))
    assert "configs/unet/stage2.yaml" in cmd and "--enable_deepcache" in cmd


def test_aspect_is_vertical_or_landscape_and_reaches_the_spec(course, presenter):
    assert any("aspect" in e for e in shorts.check(plan(aspect="4:3"), course, presenter))
    assert shorts.timeline(plan(aspect="16:9"), course, [4.0, 5.0, 3.0])["aspect"] == "16:9"
    assert shorts.scaffold(course, None)["aspect"] == "16:9"
