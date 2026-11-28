import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from gemini_check import build_prompt, candidates, main, parse_answer

ROWS = [
    {"headline": "SAP weighs cutting 10,000 jobs in AI shift", "outlet": "Reuters", "published": "2026-11-26",
     "feed": "gnews-in", "link": "https://news.google.com/rss/articles/x"},
    {"headline": "SAP weighs cutting 10,000 jobs in AI shift", "outlet": "Mint", "published": "2026-11-26",
     "feed": "gnews-us", "link": "https://news.google.com/rss/articles/y"},
    {"headline": "Cricket final tonight", "outlet": "ESPN", "published": "2026-11-26", "feed": "gnews-in", "link": "z"},
    {"headline": "Layoffs hit startups again", "outlet": "Hacker News", "published": "2026-11-26", "feed": "hn",
     "link": "https://techcrunch.com/a"},
    {"headline": "jobs", "outlet": "", "published": "", "feed": "trends-in", "link": ""},
]
COURSES = [{"id": "course-ai-ba-1", "title": "AI-Driven Business Analysis", "slug": "ai-ba-1"}]
ANSWER = {"window_days": 2, "kept": [], "dropped": [{"headline": "Cricket", "reason": "not about work"}]}


def make_run(tmp_path, courses=True):
    run = tmp_path / "2026-11-27-daily-x"
    run.mkdir()
    (run / "trends.json").write_text(json.dumps({"days": 2, "rows": ROWS}), encoding="utf-8")
    if courses:
        (run / "courses.json").write_text(json.dumps(COURSES), encoding="utf-8")
    return run


def fake_runner(stdout="", returncode=0, raises=None, seen=None):
    def run(argv, **kw):
        if seen is not None:
            seen.update(argv=argv, cwd=kw.get("cwd"), cwd_files=os.listdir(kw["cwd"]))
        if raises:
            raise raises
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="boom")
    return run


def test_candidates_keep_work_news_only_once():
    heads = [r["headline"] for r in candidates(ROWS)]
    assert heads == ["SAP weighs cutting 10,000 jobs in AI shift", "Layoffs hit startups again"]


def test_candidates_are_capped():
    rows = [dict(ROWS[0], headline=f"Firm {i} cuts jobs") for i in range(60)]
    assert len(candidates(rows, limit=40)) == 40


def test_prompt_has_rules_candidates_courses_and_window(tmp_path):
    prompt = build_prompt(make_run(tmp_path))
    assert "Two outlets" in prompt and "Not sensitive" in prompt              # editorial.md keep rules
    assert "SAP weighs cutting 10,000 jobs in AI shift" in prompt and "Cricket" not in prompt
    assert "course-ai-ba-1" in prompt
    assert "2026-11-25" in prompt and "2026-11-27" in prompt
    assert len(prompt) < 30000


def test_parse_keeps_the_last_json_block():
    text = 'Here you go.\n```json\n{"kept": [], "draft": true}\n```\nBetter:\n```json\n' + json.dumps(ANSWER) + "\n```"
    assert parse_answer(text) == ANSWER


def test_parse_falls_back_to_the_outer_braces():
    assert parse_answer("Result: " + json.dumps(ANSWER) + " done") == ANSWER


def test_parse_rejects_an_answer_without_kept():
    with pytest.raises(ValueError):
        parse_answer("I could not find any news.")


def test_main_writes_checked_json_marked_as_gemini(tmp_path):
    run = make_run(tmp_path)
    assert main([str(run)], runner=fake_runner("```json\n" + json.dumps(ANSWER) + "\n```")) == 0
    checked = json.loads((run / "checked.json").read_text(encoding="utf-8"))
    assert checked["checked_by"] == "gemini:gemini-4-hydrogen-medium" and checked["dropped"] == ANSWER["dropped"]
    assert (run / "gemini-raw.txt").exists()


def test_agy_runs_sandboxed_in_an_empty_folder(tmp_path):
    seen = {}
    main([str(make_run(tmp_path)), "--model", "gemini-3.8-flash-medium"], runner=fake_runner(json.dumps(ANSWER), seen=seen))
    argv = seen["argv"]
    assert argv[:2] == ["agy", "-p"] and "--sandbox" in argv and "--dangerously-skip-permissions" not in argv
    assert argv[argv.index("--model") + 1] == "gemini-3.8-flash-medium"
    assert seen["cwd_files"] == [] and not os.path.exists(seen["cwd"])   # empty while running, removed after


def test_timeout_exits_1_and_writes_no_checked_json(tmp_path):
    run = make_run(tmp_path)
    assert main([str(run)], runner=fake_runner(raises=subprocess.TimeoutExpired("agy", 420))) == 1
    assert not (run / "checked.json").exists()


def test_missing_agy_exits_1(tmp_path):
    run = make_run(tmp_path)
    assert main([str(run)], runner=fake_runner(raises=FileNotFoundError("agy"))) == 1
    assert "agy is not installed" in (run / "gemini-raw.txt").read_text(encoding="utf-8")


def test_unparseable_answer_exits_1(tmp_path):
    run = make_run(tmp_path)
    assert main([str(run)], runner=fake_runner("Sorry, no results.")) == 1
    assert not (run / "checked.json").exists()


def test_needs_courses_json(tmp_path):
    assert main([str(make_run(tmp_path, courses=False))], runner=fake_runner(json.dumps(ANSWER))) == 1
