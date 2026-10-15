import os
from io import BytesIO

from PIL import Image

from fixture_course import course
from manifest import new_manifest
from optimise_existing import optimise_existing

OLD_SRC = "https://nerdit.in/lesson-images/test/old-diagram.png"


def noisy_png(w=800, h=600) -> bytes:
    buf = BytesIO()
    Image.frombytes("RGB", (w, h), os.urandom(w * h * 3)).save(buf, "PNG")
    return buf.getvalue()  # random pixels: well over 300 KB as PNG


def test_heavy_image_is_converted_repointed_and_recorded(tmp_path):
    c, m = course(), new_manifest(course(), "course.json")
    big = noisy_png()
    report = optimise_existing(c, m, tmp_path, fetch=lambda url: big)
    content = c["lessons"][1]["content"]
    assert 'src="old-diagram.webp"' in content and OLD_SRC not in content
    assert 'width="800"' in content and 'height="600"' in content
    assert (tmp_path / "old-diagram.webp").is_file()
    entry = m["existingOptimised"][0]
    assert (entry["from"], entry["to"], entry["bytesBefore"]) == (OLD_SRC, "old-diagram.webp", len(big))
    assert report["optimised"] == [f"old-style-02: {OLD_SRC} -> old-diagram.webp"]


def test_small_image_is_kept(tmp_path):
    c, m = course(), new_manifest(course(), "course.json")
    report = optimise_existing(c, m, tmp_path, fetch=lambda url: b"tiny")
    assert report["kept"] == [OLD_SRC] and OLD_SRC in c["lessons"][1]["content"]


def test_download_failure_keeps_the_original(tmp_path):
    def boom(url):
        raise OSError("timed out")
    c, m = course(), new_manifest(course(), "course.json")
    report = optimise_existing(c, m, tmp_path, fetch=boom)
    assert "could not download" in report["errors"][0] and OLD_SRC in c["lessons"][1]["content"]


def test_second_run_reuses_the_manifest_entry_without_downloading(tmp_path):
    m = new_manifest(course(), "course.json")
    big = noisy_png()
    optimise_existing(course(), m, tmp_path, fetch=lambda url: big)
    def never(url):
        raise AssertionError("should not download again")
    c = course()
    optimise_existing(c, m, tmp_path, fetch=never)
    assert 'src="old-diagram.webp"' in c["lessons"][1]["content"]
    assert len(m["existingOptimised"]) == 1


def test_name_collision_gets_a_suffix(tmp_path):
    c, m = course(), new_manifest(course(), "course.json")
    m["images"].append({"outputFile": "old-diagram.webp"})
    big = noisy_png()
    optimise_existing(c, m, tmp_path, fetch=lambda url: big)
    assert m["existingOptimised"][0]["to"] == "old-diagram-2.webp"
