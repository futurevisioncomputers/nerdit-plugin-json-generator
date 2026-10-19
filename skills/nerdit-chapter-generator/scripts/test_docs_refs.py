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


def test_writer_trim_rule_matches_the_refresh_guard():
    # check_refresh.py fails a trim that seeds a view, trigger or computed table;
    # the writer and CORE.md must say the same, or the writer keeps tripping the guard.
    writer = (ROOT / "agents" / "nerdit-lesson-writer.md").read_text(encoding="utf-8")
    core = (HERE.parent / "references" / "CORE.md").read_text(encoding="utf-8")
    trim = " ".join(writer.split("- `trim`", 1)[1].split("\n\n", 1)[0].split())
    assert "Never seed a view, a trigger or a computed table" in trim
    assert "view, trigger or computed table" in " ".join(core.split())
    assert "shows in full" not in trim and "seed or a view" not in core
    assert "seed or a view" not in (HERE / "verify_course.py").read_text(encoding="utf-8")


def test_plugin_version_is_3_5_0():
    assert json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"] == "3.5.0"


def test_skill_md_matches_the_v11_figure_rules():
    skill = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
    assert "nine figure templates" not in skill.lower()
    assert "Every lesson ships at least one figure" not in skill


def test_docs_name_python_checker_and_dataset_rules():
    skill = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
    python = (HERE.parent / "references" / "runners" / "python.md").read_text(encoding="utf-8")
    plot = (HERE.parent / "references" / "runners" / "plot.md").read_text(encoding="utf-8")
    core = (HERE.parent / "references" / "CORE.md").read_text(encoding="utf-8")
    writer = (ROOT / "agents" / "nerdit-lesson-writer.md").read_text(encoding="utf-8")
    qa = (ROOT / "agents" / "nerdit-qa-validator.md").read_text(encoding="utf-8")
    assert "scripts/check_python_outputs.py" in skill and "--probe" in skill
    assert "nerdit-dataset" in python and "40 KB" in python and 'data-run="offline"' in python
    assert "no seed block" not in python
    assert "nerdit-dataset" in plot and "runners/python.md" in core
    assert 'data-run="offline"' in writer and "runners/python.md" in writer
    assert "check_python_outputs.py" in qa


def test_dataset_lessons_mark_their_tables_for_the_world_check():
    """check_world.py fails a figure table with neither data-world-entity nor data-world-derived;
    a dataset lesson's file table and CSV rows come from the recipe, not the course world."""
    python = " ".join((HERE.parent / "references" / "runners" / "python.md").read_text(encoding="utf-8").split())
    assert 'data-world-derived="dataset block' in python
    assert "make_world_data.py --recipe" in python
    skill = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
    assert "Python prints" in skill


def test_writer_knows_screen_and_scene_specs():
    writer = (ROOT / "agents" / "nerdit-lesson-writer.md").read_text(encoding="utf-8")
    assert "nerdit-screen" in writer and "nerdit-scene" in writer and "render_screens.py" in writer


def test_figures_has_templates_16_and_17():
    figures = (HERE.parent / "references" / "figures.md").read_text(encoding="utf-8")
    assert "## 16 · Screen walkthrough" in figures and "## 17 · Scene" in figures
    assert "never hand-draw a screen" in figures.lower()
    assert "figures.md template 16" in (HERE.parent / "references" / "runners" / "excel.md").read_text(encoding="utf-8")


def test_visual_map_has_screen_and_scene_rows():
    core = " ".join((HERE.parent / "references" / "CORE.md").read_text(encoding="utf-8").split())
    assert "| a click-path in an app | `screen`" in core
    assert "| one simple idea through a familiar scene | scene spec" in core
    assert "complex to explain → A (drawn)" in core


def test_skill_names_visual_scripts():
    skill = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
    for name in ("render_screens.py", "check_screens.py", "visual_briefs.py"):
        assert f"scripts/{name}" in skill
    qa = (ROOT / "agents" / "nerdit-qa-validator.md").read_text(encoding="utf-8")
    assert "nerdit-screen" in qa and "image forced" in qa
