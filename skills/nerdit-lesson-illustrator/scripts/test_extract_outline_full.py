import json
import os
import subprocess
import sys

import pytest

from extract_outline import full_section
from fixture_course import ANCHOR_1, course
from lessonhtml import section_fingerprint

SCRIPT = os.path.join(os.path.dirname(__file__), "extract_outline.py")


def test_full_section_prints_context_text_and_fingerprint():
    out = full_section(course(), "load-basics-01", 1)
    fp = section_fingerprint(course()["lessons"][0]["content"], 1, "1 — What a load does")
    assert "COURSE Test Course" in out and "LESSON load-basics-01 Load Basics" in out
    assert "SECTION 1 1 — What a load does" in out and f"FINGERPRINT {fp}" in out
    assert ANCHOR_1 in out
    with pytest.raises(KeyError):
        full_section(course(), "load-basics-01", 9)


def test_cli_full_unknown_lesson_exits_2(tmp_path):
    src = tmp_path / "course.json"
    src.write_text(json.dumps(course(), ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "--course", str(src), "--full", "nope:1"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2 and "unknown lesson nope" in r.stdout
