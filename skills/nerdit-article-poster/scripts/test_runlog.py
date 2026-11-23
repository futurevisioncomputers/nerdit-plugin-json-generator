import json

import pytest

import runlog

DAY = "2026-11-23"
NEXT = "2026-11-24"


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NERDIT_SOCIAL_HOME", str(tmp_path))
    return tmp_path / "article-runs"


def test_plan_keeps_panel_order_drops_posted_and_caps_at_six():
    assert runlog.plan("a", {"medium", "linkedin"}, DAY) == ["hashnode", "hackernoon", "substack", "wordpress", "blogger", "tumblr"]


def test_a_site_logged_as_posted_is_never_planned_again_even_if_its_link_was_not_saved():
    runlog.mark("a", "medium", "posted", DAY, url="https://medium.com/p/1")
    assert "medium" not in runlog.plan("a", set(), NEXT)


def test_quora_and_pinterest_post_once_a_day_across_all_articles():
    runlog.mark("a", "quora", "posted", DAY, url="https://quora.com/x")
    posted = set(runlog.SITES) - {"quora", "pinterest"}
    assert runlog.plan("b", posted, DAY) == ["pinterest"]
    assert runlog.plan("b", posted, NEXT) == ["pinterest", "quora"]


def test_failed_today_is_retried_skipped_today_waits_for_tomorrow():
    runlog.mark("a", "medium", "failed", DAY, error="editor did not load")
    runlog.mark("a", "hashnode", "skipped", DAY)
    plan = runlog.plan("a", set(), DAY)
    assert plan[0] == "medium" and "hashnode" not in plan
    assert "hashnode" in runlog.plan("a", set(), NEXT)


def test_mark_records_each_step_and_a_corrupt_log_is_kept_aside(home):
    runlog.mark("a", "medium", "posted", DAY, url="https://medium.com/p/1")
    data = json.loads((home / "a.json").read_text(encoding="utf-8"))
    assert data["steps"][0] | {"at": ""} == {"site": "medium", "status": "posted", "day": DAY, "url": "https://medium.com/p/1",
                                              "error": "", "at": ""}
    (home / "a.json").write_text("{broken", encoding="utf-8")
    runlog.mark("a", "hashnode", "failed", DAY, error="x")
    assert (home / "a.json.bak").read_text(encoding="utf-8") == "{broken"
    assert [s["site"] for s in json.loads((home / "a.json").read_text(encoding="utf-8"))["steps"]] == ["hashnode"]


def test_cli_plan_and_mark(capsys):
    assert runlog.main(["plan", "--slug", "a", "--posted", "medium,hashnode", "--today", DAY]) == 0
    assert capsys.readouterr().out.split()[:2] == ["hackernoon", "linkedin"]
    assert runlog.main(["mark", "--slug", "a", "--site", "hackernoon", "--status", "posted", "--url", "https://hackernoon.com/x",
                        "--today", DAY]) == 0
    assert runlog.main(["mark", "--slug", "a", "--site", "myspace", "--status", "posted", "--today", DAY]) == 1
    assert runlog.main(["mark", "--slug", "a", "--site", "medium", "--status", "done", "--today", DAY]) == 1


def test_six_sites_per_article_per_day_counts_what_was_already_posted_today():
    for site in runlog.SITES[:4]:
        runlog.mark("a", site, "posted", DAY, url=f"https://{site}.example/x")
    assert runlog.plan("a", set(), DAY) == ["substack", "wordpress"]
    for site in ("substack", "wordpress"):
        runlog.mark("a", site, "posted", DAY, url="https://x.example/y")
    assert runlog.plan("a", set(), DAY) == []
    assert runlog.plan("a", set(), NEXT)[:2] == ["blogger", "tumblr"]


def test_every_site_has_a_recipe_with_the_fields_the_skill_reads():
    from pathlib import Path
    sites = Path(__file__).resolve().parents[1] / "references" / "sites"
    for site in runlog.SITES:
        text = (sites / f"{site}.md").read_text(encoding="utf-8")
        for field in ("**Start:**", "**Signed in when:**", "**Kit:**", "**Canonical / original URL:**", "**Publish:**", "**Post URL:**", "**Verified:**"):
            assert field in text, f"{site}: {field}"
