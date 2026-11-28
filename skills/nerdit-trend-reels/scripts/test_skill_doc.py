from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
RUNNER = Path(__file__).resolve().parent / "scheduled_run.ps1"


def test_step_3_runs_gemini_then_the_checker_with_claude_as_fallback():
    text = SKILL.read_text(encoding="utf-8")
    assert "gemini_check.py <run>" in text and "checked_check.py <run>" in text and "courses.json" in text
    assert "do the check yourself" in text


def test_scheduled_run_may_call_both_new_scripts():
    names = next(line for line in RUNNER.read_text(encoding="utf-8").splitlines() if line.strip().startswith("$names"))
    assert "'gemini_check.py'" in names and "'checked_check.py'" in names


def test_editorial_asks_for_what_the_checker_needs():
    text = (SKILL.parent / "references" / "editorial.md").read_text(encoding="utf-8")
    assert "`published`" in text and "starts with the" in text and "outlet name exactly as in `outlets`" in text
