import re

import pytest

import rules_pack as rp

CORE = """# Rules

Intro line.

## 1. Always
Keep this.
<!-- pack: why -->
Not a tag here: tags sit straight under a heading.

## 6. Try It
### 6c. Runner
<!-- pack: code -->
Live runner.
```python
# not a heading
print(1)
```
### 6d. Non-code
<!-- pack: visual, quantitative -->
Steps instead of code.
### 6e. Files
Pack files.

## 7b. Colour
### One more reason this matters
<!-- pack: why -->
Because.
## 8b. Capstone
<!-- pack: project -->
Milestones.
### 8c. Inside the capstone
Still capstone.
## 9. Script
Script rules.
"""

FIGURES = """# Figure templates

Pick one.

## Rules that hold for every template
R1 draw small.

## 1 · Sequence — a pipeline, in order
<svg>seq</svg>

## 16 · Screen walkthrough — a click-path in an app
<svg>screen</svg>

## Choosing between them
Table.
"""


def test_a_code_pack_keeps_its_preset_and_drops_other_presets_rationale_and_capstone():
    text = rp.core_pack(CORE, "code", project=False)
    assert "Live runner." in text and "# not a heading" in text and "Pack files." in text
    assert "Steps instead of code." not in text and "Because." not in text and "Milestones." not in text
    assert "Still capstone." not in text and "Script rules." in text
    assert "Not a tag here" in text            # a pack comment only counts straight under a heading
    assert "<!-- pack" not in text.replace("<!-- pack: why -->\nNot a tag", "")


def test_a_project_pack_keeps_the_capstone_and_a_visual_pack_keeps_its_try_it():
    assert "Milestones." in rp.core_pack(CORE, "code", project=True)
    visual = rp.core_pack(CORE, "visual", project=False)
    assert "Steps instead of code." in visual and "Live runner." not in visual


def test_figure_templates_become_files_read_on_demand(tmp_path):
    rules, templates = rp.split_figures(FIGURES)
    assert "R1 draw small." in rules and "Table." in rules and "<svg>" not in rules
    assert [name for name, _ in templates] == ["01-sequence", "16-screen-walkthrough"]
    assert templates[0][1].startswith("## 1 · Sequence") and "<svg>seq</svg>" in templates[0][1]


def test_build_writes_one_pack_and_the_template_files(tmp_path):
    path = rp.build(tmp_path, "code", project=False, core=CORE, figures=FIGURES)
    assert path == tmp_path / "_rules" / "rules-code.md"
    text = path.read_text(encoding="utf-8")
    assert "Live runner." in text and "R1 draw small." in text
    assert "figures/01-sequence.md" in text and "figures/16-screen-walkthrough.md" in text
    assert (tmp_path / "_rules" / "figures" / "01-sequence.md").read_text(encoding="utf-8").count("<svg>") == 1
    assert rp.build(tmp_path, "code", project=True, core=CORE, figures=FIGURES).name == "rules-code-project.md"


def test_unknown_preset_is_refused(tmp_path):
    with pytest.raises(ValueError):
        rp.build(tmp_path, "poetry", project=False, core=CORE, figures=FIGURES)


def test_the_real_rules_shrink_for_a_python_course(tmp_path):
    path = rp.build(tmp_path, "code", project=False)
    full = len(rp.CORE.read_text(encoding="utf-8")) + len(rp.FIGURES.read_text(encoding="utf-8"))
    packed = len(path.read_text(encoding="utf-8"))
    assert packed < full * 0.75
    text = path.read_text(encoding="utf-8")
    for heading in ("## 2. FIXED LESSON SKELETON", "## 4. THE RUN LINE", "## 10. LANGUAGE RULES",
                    "### The Visual Map", "## Rules that hold for every template"):
        assert heading in text
    assert "### 6d. Try It on a non-code preset" not in text and "## 8b. CAPSTONE" not in text
    assert not re.search(r"<!-- pack:", text)
