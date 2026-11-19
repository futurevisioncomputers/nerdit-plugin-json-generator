import json

import pytest

from conftest import write_workdir
from slides import card_spec, default_slides, question_fits
from source import load_source

ITEM = {"id": "d03-carousel", "lessonId": "demo-01", "topic": 1, "clipKey": "demo-01-t1-video", "format": "carousel"}
VECTOR = '<svg class="nerdit-anim" viewBox="0 0 480 360" role="img" aria-label="A folder holds a venv"><g class="na-show"><text>venv</text></g></svg>'


@pytest.fixture
def src(tmp_path):
    return load_source(write_workdir(tmp_path))


def test_default_carousel_has_5_to_8_slides_in_order(src):
    kinds = [s["kind"] for s in default_slides(src, ITEM)]
    assert kinds[0] == "cover" and kinds[-1] == "cta" and 5 <= len(kinds) <= 8
    assert kinds.index("quiz") + 1 == kinds.index("answer")
    assert kinds.count("idea") >= 2


def test_quiz_and_answer_come_from_the_lesson(src):
    slides = {s["kind"]: s for s in default_slides(src, ITEM)}
    assert slides["quiz"]["question"] == "Which command makes a venv?"
    assert slides["answer"]["answer"] == "python -m venv .venv"


def test_long_question_is_skipped():
    assert not question_fits({"text": "x " * 90, "options": ["a", "b", "c", "d"]})
    assert question_fits({"text": "Which command makes a venv?", "options": ["a", "b", "c", "d"]})


def test_a_four_line_question_fits_but_a_three_line_option_does_not():
    question = "Your .env file holds APP_NAME and main.py calls load_dotenv() first. What does os.getenv return?"
    assert question_fits({"text": question, "options": ["The value", "None", "An error", "The file name"]})
    assert not question_fits({"text": "Short?", "options": ["word " * 20, "b", "c", "d"]})


def test_default_cover_hook_falls_back_when_the_key_idea_is_too_long(tmp_path):
    wd = write_workdir(tmp_path)
    plan_path = wd / "images" / "video" / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["scenes"][0]["keyIdea"] = "A missing required field fails; a missing optional field takes its default value instead"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    cover = default_slides(load_source(wd), ITEM)[0]
    assert cover["hook"] == "Topic 1"


def test_no_fitting_question_drops_quiz_and_answer_but_keeps_five_slides(tmp_path):
    wd = write_workdir(tmp_path)
    path = wd / "course-demo_output.json"
    course = json.loads(path.read_text(encoding="utf-8"))
    course["lessons"][0]["questions"][0]["text"] = "word " * 40
    path.write_text(json.dumps(course), encoding="utf-8")
    kinds = [s["kind"] for s in default_slides(load_source(wd), ITEM)]
    assert "quiz" not in kinds and "answer" not in kinds and len(kinds) >= 5


def test_diagram_uses_the_topic_scene_vector_before_lesson_figures(tmp_path):
    wd = write_workdir(tmp_path)
    (wd / "images" / "video" / "vectors").mkdir()
    (wd / "images" / "video" / "vectors" / "demo-01-t1.svg").write_text(VECTOR, encoding="utf-8")
    diagram = next(s for s in default_slides(load_source(wd), ITEM) if s["kind"] == "diagram")
    assert "A folder holds a venv" in diagram["svg"] and diagram["label"] == "A folder holds a venv"


def test_diagram_falls_back_to_a_lesson_figure(src):
    diagram = next(s for s in default_slides(src, ITEM) if s["kind"] == "diagram")
    assert "Two folders" in diagram["svg"]


def test_card_spec_has_lesson_title_topics_and_a_picture(src):
    card = card_spec(src, {**ITEM, "format": "story"})
    assert card["title"] == "Getting Started" and card["course"] == "Demo Course"
    assert card["topics"] == ["Make a Project Folder", "Install FastAPI"]
    assert "svg" in card["picture"]


def test_feed_card_prefers_the_video_thumbnail_when_there_is_one(tmp_path):
    from PIL import Image
    wd = write_workdir(tmp_path)
    Image.new("RGB", (1280, 720), "white").save(wd / "images" / "video" / "thumbnail.jpg")
    card = card_spec(load_source(wd), {**ITEM, "format": "feed"})
    assert card["picture"]["img"].endswith("thumbnail.jpg")
