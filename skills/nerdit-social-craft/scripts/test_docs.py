import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def test_skill_md_names_only_scripts_that_exist():
    skill = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
    named = set(re.findall(r"scripts/(\w+\.py)", skill))
    assert named, "SKILL.md names no scripts"
    assert sorted(n for n in named if not (HERE / n).is_file()) == []


def test_third_party_notice_names_both_repos():
    notice = (HERE.parent / "THIRD_PARTY.md").read_text(encoding="utf-8")
    assert "Jake Schincariol" in notice and "Sergey Bulaev" in notice and notice.count("MIT License") == 2
