from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
RUNNER = Path(__file__).resolve().parent / "scheduled_run.ps1"


def test_step_3_is_claude_first_with_the_checker():
    # Owner 2026-11-28: Gemini passed 0 of 2 replays (docs/superpowers/specs/2026-11-28-phase5-replay.md).
    text = SKILL.read_text(encoding="utf-8")
    assert "checked_check.py <run>" in text and "courses.json" in text and "WebFetch" in text
    assert "gemini_check.py" in text and "optional" in text and "never in a scheduled run" in text


def test_scheduled_run_may_call_the_checker_but_not_gemini():
    names = next(line for line in RUNNER.read_text(encoding="utf-8").splitlines() if line.strip().startswith("$names"))
    assert "'checked_check.py'" in names and "gemini_check.py" not in names


def test_editorial_asks_for_what_the_checker_needs():
    text = (SKILL.parent / "references" / "editorial.md").read_text(encoding="utf-8")
    assert "`published`" in text and "starts with the" in text and "outlet name exactly as in `outlets`" in text


def test_editorial_states_link_order_and_exact_quotes():
    text = (SKILL.parent / "references" / "editorial.md").read_text(encoding="utf-8")
    assert "one link per outlet, in the same order" in text and "never a Google News link" in text
    assert "word for word" in text and "fetch the page once more" in text
