import os

from PIL import Image, ImageDraw

import convert_images as ci
from convert_images import convert_all, encode_webp, find_incoming
from fixture_course import PLAN, course
from manifest import add_slots, new_manifest


def planned():
    m = new_manifest(course(), "course.json")
    assert add_slots(m, course(), PLAN) == []
    return m


def illustration(path, size=(1536, 1024), mode="RGB", fmt=None):
    img = Image.new("RGB", size, (238, 243, 249))
    d = ImageDraw.Draw(img)
    d.rectangle([200, 200, 900, 700], fill=(11, 31, 58))
    d.ellipse([1000, 300, 1400, 700], fill=(20, 184, 166))
    if mode != "RGB":
        img = img.convert(mode)
    img.save(path, fmt)
    return path


def setup(tmp_path):
    (tmp_path / "incoming").mkdir()
    return tmp_path


def test_encode_webp_resizes_and_stays_under_target(tmp_path):
    data, w, h, q = encode_webp(illustration(tmp_path / "a.png"))
    assert (w, h) == (1200, 800) and len(data) <= ci.TARGET_BYTES and q <= ci.START_QUALITY
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def test_unusual_image_modes_convert(tmp_path):
    illustration(tmp_path / "rgba.png", mode="RGBA")
    p = Image.new("P", (300, 200)); p.info["transparency"] = 0; p.save(tmp_path / "pal.png")
    illustration(tmp_path / "cmyk.jpg", mode="CMYK", fmt="JPEG")
    frames = [Image.new("RGB", (300, 200), c) for c in ((255, 0, 0), (0, 0, 255))]
    frames[0].save(tmp_path / "anim.gif", save_all=True, append_images=frames[1:])
    for name in ("rgba.png", "pal.png", "cmyk.jpg", "anim.gif"):
        data, w, h, _ = encode_webp(tmp_path / name)
        assert data[8:12] == b"WEBP" and w > 0 and h > 0


def test_find_incoming_matches_case_and_extension_and_reports_duplicates(tmp_path):
    d = setup(tmp_path)
    illustration(d / "incoming" / "LOAD-BASICS-01-IMG1.PNG")
    illustration(d / "incoming" / "old-style-02-img1.jpeg", fmt="JPEG")
    illustration(d / "incoming" / "old-style-02-img1.png")
    (d / "incoming" / "notes.txt").write_text("x")
    files, missing, unexpected = find_incoming(planned(), d / "incoming")
    assert set(files) == {"load-basics-01-img1", "old-style-02-img1"}
    assert missing == []
    assert "notes.txt" in unexpected and any("(duplicate)" in u for u in unexpected)


def test_convert_all_writes_upload_and_preview_and_updates_slot(tmp_path):
    d = setup(tmp_path)
    illustration(d / "incoming" / "load-basics-01-img1.png")
    m = planned()
    report = convert_all(m, d)
    assert report["converted"] == ["load-basics-01-img1"]
    assert report["missing"] == ["old-style-02-img1"]
    slot = m["images"][0]
    assert slot["status"] == "converted" and (slot["width"], slot["height"]) == (1200, 800)
    assert (d / "upload" / "load-basics-01-img1.webp").stat().st_size == slot["bytes"]
    with Image.open(d / "preview" / "load-basics-01-img1.jpg") as pv:
        assert pv.width == ci.PREVIEW_WIDTH


def test_unchanged_file_is_not_reconverted(tmp_path):
    d = setup(tmp_path)
    illustration(d / "incoming" / "load-basics-01-img1.png")
    m = planned()
    convert_all(m, d)
    assert convert_all(m, d)["unchanged"] == ["load-basics-01-img1"]


def test_new_file_after_fail_is_reconverted_and_check_reset(tmp_path):
    d = setup(tmp_path)
    illustration(d / "incoming" / "load-basics-01-img1.png")
    m = planned()
    convert_all(m, d)
    m["images"][0].update(status="failed", check={"result": "fail", "reason": "garbled text"})
    assert convert_all(m, d)["unchanged"] == ["load-basics-01-img1"]
    illustration(d / "incoming" / "load-basics-01-img1.png", size=(1500, 1000))
    report = convert_all(m, d)
    assert report["converted"] == ["load-basics-01-img1"]
    assert m["images"][0]["status"] == "converted" and m["images"][0]["check"] == {"result": None, "reason": None}


def test_corrupt_file_is_reported_and_slot_unchanged(tmp_path):
    d = setup(tmp_path)
    (d / "incoming" / "load-basics-01-img1.png").write_bytes(b"not an image")
    m = planned()
    report = convert_all(m, d)
    assert any("cannot read image" in e for e in report["errors"])
    assert m["images"][0]["status"] == "planned"


def test_over_hard_limit_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ci, "HARD_LIMIT_BYTES", 1000)
    d = setup(tmp_path)
    illustration(d / "incoming" / "load-basics-01-img1.png")
    m = planned()
    report = convert_all(m, d)
    assert any("over the 250 KB limit" in e for e in report["errors"])
    assert m["images"][0]["status"] == "planned"


def test_screen_converts_like_an_illustration(tmp_path):
    from fixture_course import screen_plan
    from manifest import add_slots_v2
    d = setup(tmp_path)
    m = new_manifest(course(), "course.json")
    assert add_slots_v2(m, course(), screen_plan()) == []
    illustration(d / "incoming" / "old-style-02-img1.png")
    report = convert_all(m, d)
    assert report["converted"] == ["old-style-02-img1"]
    assert (d / "upload" / "old-style-02-img1.webp").is_file()
