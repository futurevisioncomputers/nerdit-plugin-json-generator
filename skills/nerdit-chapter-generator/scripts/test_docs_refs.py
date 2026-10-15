import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def test_skill_md_names_only_scripts_that_exist():
    skill = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
    names = set(re.findall(r"(?<!illustrator/)scripts/([a-z_]+\.py)", skill))
    assert {"gate_lesson.py", "build_preview.py", "check_prose.py", "check_refresh.py"} <= names
    assert [n for n in names if not (HERE / n).exists()] == []


def test_writer_knows_refresh_mode_and_voice():
    writer = (ROOT / "agents" / "nerdit-lesson-writer.md").read_text(encoding="utf-8")
    assert "## Refresh mode" in writer and "references/voice.md" in writer and "data-visual" in writer


def test_plugin_version_is_3_3_0():
    assert json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"] == "3.3.0"


def test_skill_md_matches_the_v11_figure_rules():
    skill = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
    assert "nine figure templates" not in skill.lower()
    assert "Every lesson ships at least one figure" not in skill
