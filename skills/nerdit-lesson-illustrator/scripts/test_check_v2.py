import copy
import json
import re

from PIL import Image

from check_images import check
from convert_images import convert_all
from fixture_course import PLAN_V2, course
from insert_images import build_output, insert_lessons, output_path
from manifest import add_slots_v2, load, new_manifest, record_checks, save

SVG = ('<svg viewBox="0 0 200 80" role="img" aria-label="Checked rows reach the warehouse">'
       '<text x="10" y="20" fill="var(--nb)">① warehouse</text>'
       '<text x="10" y="50" fill="var(--orange)">② run log</text></svg>')


def setup(tmp_path, content_edit=None):
    src = tmp_path / "course-test_output.json"
    src.write_text(json.dumps(course(), ensure_ascii=False, indent=2), encoding="utf-8")
    images = tmp_path / "images"
    for d in ("incoming", "diagrams", "upload"):
        (images / d).mkdir(parents=True)
    m = new_manifest(course(), src.name)
    assert add_slots_v2(m, course(), copy.deepcopy(PLAN_V2)) == []
    (images / "diagrams" / "load-basics-01-fig1.svg").write_text(SVG, encoding="utf-8")
    Image.new("RGB", (1600, 1200), (238, 243, 249)).save(images / "incoming" / "old-style-02-img1.png")
    assert convert_all(m, images)["errors"] == []
    assert record_checks(m, [{"id": s["id"], "result": "pass", "reason": "ok"} for s in m["images"]]) == []
    save(images, m)
    if content_edit:
        c = course()
        c["lessons"][0]["content"] = c["lessons"][0]["content"].replace(*content_edit)
        src.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    return src, images


def tiny(url):
    return b"tiny"


def test_v2_valid_output_is_written(tmp_path):
    src, images = setup(tmp_path)
    assert build_output(src, images, fetch=tiny) == 0
    data = json.loads(output_path(src).read_text(encoding="utf-8"))
    assert 'class="nerdit-visual-read"' in data["lessons"][0]["content"]
    assert [s["status"] for s in load(images)["images"]] == ["inserted", "inserted"]


def test_v2_running_twice_is_identical(tmp_path):
    src, images = setup(tmp_path)
    build_output(src, images, fetch=tiny)
    first = output_path(src).read_bytes()
    assert build_output(src, images, fetch=tiny) == 0
    assert output_path(src).read_bytes() == first


def test_stale_section_blocks_output(tmp_path, capsys):
    src, images = setup(tmp_path, content_edit=("only ever receives checked rows", "receives checked rows"))
    assert build_output(src, images, fetch=tiny) == 1
    assert "section changed since planning" in capsys.readouterr().out
    assert not output_path(src).exists()


def test_v2_missing_reading_step_is_an_error(tmp_path):
    src, images = setup(tmp_path)
    c, m = course(), load(images)
    insert_lessons(c, m, images / "diagrams")
    c["lessons"][0]["content"] = c["lessons"][0]["content"].replace(
        "<li>② The run log records the run.</li>", "")
    errors, _ = check(c, m, images / "upload")
    assert any("load-basics-01-fig1: 1 reading steps shown, 2 expected" in e for e in errors)


def test_v2_check_reports_missing_siblings(tmp_path):
    src, images = setup(tmp_path)
    c, m = course(), load(images)
    insert_lessons(c, m, images / "diagrams")
    content = c["lessons"][0]["content"]
    start = content.index('\n<p class="nerdit-visual-intro"')
    end = content.index("</p>", start) + 4
    c["lessons"][0]["content"] = content[:start] + content[end:]
    errors, _ = check(c, m, images / "upload")
    assert any("load-basics-01-fig1: missing intro paragraph" in e for e in errors)


def test_v2_illustration_missing_size_attributes_is_an_error(tmp_path):
    src, images = setup(tmp_path)
    c, m = course(), load(images)
    insert_lessons(c, m, images / "diagrams")
    c["lessons"][1]["content"] = re.sub(r' width="\d+"', "", c["lessons"][1]["content"])
    errors, _ = check(c, m, images / "upload")
    assert any("old-style-02-img1: missing width" in e for e in errors)
