import json
from input_from_output import (
    extract_lessons, derive_chapter, derive_description, slugify, convert,
)


def _course(lessons, cid="course-my-old-course-1779000000000", title="My Old Course"):
    return {"id": cid, "title": title, "lessons": lessons, "lessonIds": [l["id"] for l in lessons]}


def test_extract_from_course_object():
    c = _course([{"id": "l1", "title": "One", "content": "<p>hi</p>"}])
    assert [l["id"] for l in extract_lessons(c)] == ["l1"]


def test_extract_from_bare_array():
    arr = [{"id": "l1", "title": "One", "content": "<p>a</p>"}, {"id": "l2", "title": "Two", "content": "<p>b</p>"}]
    assert [l["id"] for l in extract_lessons(arr)] == ["l1", "l2"]


def test_extract_from_course_wrapped_in_array():
    c = _course([{"id": "l1", "title": "One", "content": "<p>hi</p>"}])
    assert [l["id"] for l in extract_lessons([c])] == ["l1"]


def test_derive_chapter_from_id_title_and_override():
    c = _course([], cid="course-mysql-basics-1779000000000", title="MySQL Basics")
    assert derive_chapter(c, None) == "mysql-basics"          # from id
    assert derive_chapter({"title": "Excel Power"}, None) == "excel-power"  # from title
    assert derive_chapter(c, "Custom Name") == "custom-name"  # override wins


def test_derive_description_first_sentence_then_title_fallback():
    d = derive_description("<h1>x</h1><p>SELECT reads rows. More text here.</p>", "T")
    assert d == "SELECT reads rows."
    assert derive_description("", "Fallback Title") == "Fallback Title"


def test_slugify():
    assert slugify("Hello, World! 123") == "hello-world-123"
    assert slugify("") == "converted-course"


def test_convert_writes_input_and_sources(tmp_path):
    c = _course([
        {"id": "l1", "title": "One", "content": "<p>First lesson body.</p>"},
        {"id": "l2", "title": "Two", "content": "<div>Second body here.</div>"},
    ])
    chapter, input_list, src_paths, input_path = convert(c, str(tmp_path))
    assert chapter == "my-old-course"
    # input array shape
    assert [l["id"] for l in input_list] == ["l1", "l2"]
    assert input_list[0].keys() == {"id", "title", "description"}
    # input file written and parseable
    on_disk = json.loads((tmp_path / "course-my-old-course_input.json").read_text(encoding="utf-8"))
    assert len(on_disk) == 2
    # source html preserved verbatim
    assert (tmp_path / "_src" / "l1.html").read_text(encoding="utf-8") == "<p>First lesson body.</p>"
    assert (tmp_path / "_src" / "l2.html").read_text(encoding="utf-8") == "<div>Second body here.</div>"


def test_convert_empty_content_still_writes_source(tmp_path):
    c = _course([{"id": "l1", "title": "Empty", "content": ""}])
    convert(c, str(tmp_path))
    assert (tmp_path / "_src" / "l1.html").read_text(encoding="utf-8") == ""
