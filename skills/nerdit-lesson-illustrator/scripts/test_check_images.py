from PIL import Image

import check_images as ck
from check_images import check, new_verifier_failures
from fixture_course import PLAN, course
from insert_images import insert_lessons
from manifest import add_slots, new_manifest


def inserted(tmp_path):
    c, m = course(), new_manifest(course(), "course.json")
    assert add_slots(m, c, PLAN) == []
    for s in m["images"]:
        s.update(status="passed", width=1200, height=800)
        Image.new("RGB", (1200, 800), (238, 243, 249)).save(tmp_path / s["outputFile"], "WEBP", quality=80)
    assert insert_lessons(c, m) == []
    return c, m


def test_valid_course_has_no_errors(tmp_path):
    c, m = inserted(tmp_path)
    assert check(c, m, tmp_path) == ([], [])


def test_missing_lazy_and_missing_file_are_errors(tmp_path):
    c, m = inserted(tmp_path)
    c["lessons"][0]["content"] = c["lessons"][0]["content"].replace(' loading="lazy"', "")
    (tmp_path / "old-style-02-img1.webp").unlink()
    errors, _ = check(c, m, tmp_path)
    assert any('load-basics-01-img1: missing loading="lazy"' in e for e in errors)
    assert any("old-style-02-img1.webp not in upload/" in e for e in errors)


def test_size_limits(tmp_path):
    c, m = inserted(tmp_path)
    (tmp_path / "load-basics-01-img1.webp").write_bytes(b"x" * 160_000)
    (tmp_path / "old-style-02-img1.webp").write_bytes(b"x" * 260_000)
    errors, warnings = check(c, m, tmp_path)
    assert any("above 150 KB target" in w for w in warnings)
    assert any("over 250 KB" in e for e in errors)


def test_data_uri_and_outside_host_are_errors(tmp_path):
    c, m = inserted(tmp_path)
    c["lessons"][1]["content"] += '<img src="data:image/png;base64,AAAA"><img src="https://example.com/x.png">'
    errors, _ = check(c, m, tmp_path)
    assert any("embedded data: image" in e for e in errors)
    assert any("outside host example.com" in e for e in errors)


def test_json_over_import_limit_is_an_error(tmp_path, monkeypatch):
    c, m = inserted(tmp_path)
    monkeypatch.setattr(ck, "JSON_LIMIT", 100)
    errors, _ = check(c, m, tmp_path)
    assert any("admin import limit" in e for e in errors)


def test_new_verifier_failures_reports_only_new_ones():
    before = course()
    after = course()
    after["lessons"][1]["content"] += '<div class="nerdit-figure"><p>no caption</p></div>'
    new = new_verifier_failures(before, after)
    assert any("has no nerdit-figure-caption" in f for f in new)
    assert new_verifier_failures(before, course()) == []


def test_figure_renumbering_is_not_a_new_failure(tmp_path):
    before = course()
    before["lessons"][1]["content"] += '<div class="nerdit-figure"><p>no caption</p></div>'
    after, m = course(), new_manifest(course(), "course.json")
    after["lessons"][1]["content"] = before["lessons"][1]["content"]
    assert add_slots(m, after, PLAN) == []
    for s in m["images"]:
        s.update(status="passed", width=1200, height=800)
    insert_lessons(after, m)  # our captioned figure now precedes the caption-less one
    assert new_verifier_failures(before, after) == []
