import json

from PIL import Image

from fixture_course import PLAN, course
from insert_images import build_output, output_path
from manifest import add_slots, load, new_manifest, save


def ready(tmp_path, statuses=("passed", "passed")):
    src = tmp_path / "course-test_output.json"
    src.write_text(json.dumps(course(), ensure_ascii=False, indent=2), encoding="utf-8")
    images = tmp_path / "images"
    (images / "upload").mkdir(parents=True)
    m = new_manifest(course(), src.name)
    assert add_slots(m, course(), PLAN) == []
    for s, st in zip(m["images"], statuses):
        s.update(status=st, width=1200, height=800)
        Image.new("RGB", (1200, 800), (238, 243, 249)).save(images / "upload" / s["outputFile"], "WEBP")
    save(images, m)
    return src, images


def tiny(url):
    return b"tiny"  # below MIN_BYTES: existing images are kept


def test_writes_with_images_json_and_marks_inserted(tmp_path):
    src, images = ready(tmp_path)
    assert build_output(src, images, fetch=tiny) == 0
    out = output_path(src)
    assert out.name == "course-test_output.with-images.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["lessons"][0]["content"].count('data-nerdit-img="') == 1
    assert [s["status"] for s in load(images)["images"]] == ["inserted", "inserted"]
    assert json.loads(src.read_text(encoding="utf-8")) == course()  # input untouched


def test_running_twice_gives_identical_output(tmp_path):
    src, images = ready(tmp_path)
    build_output(src, images, fetch=tiny)
    first = output_path(src).read_bytes()
    assert build_output(src, images, fetch=tiny) == 0
    assert output_path(src).read_bytes() == first


def test_failure_writes_nothing_and_keeps_manifest(tmp_path):
    src, images = ready(tmp_path)
    broken = course()
    broken["lessons"][0]["content"] = broken["lessons"][0]["content"].replace("A load copies", "A load moves")
    src.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    before = load(images)
    assert build_output(src, images, fetch=tiny) == 1
    assert not output_path(src).exists()
    assert load(images) == before


def test_only_planned_slots_still_writes_output_with_nothing_inserted(tmp_path):
    src, images = ready(tmp_path, statuses=("planned", "planned"))
    assert build_output(src, images, fetch=tiny) == 0
    data = json.loads(output_path(src).read_text(encoding="utf-8"))
    assert data["lessons"] == course()["lessons"]
