import datetime as dt
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


def test_a_site_started_but_not_settled_is_held_back_until_checked():
    runlog.mark("a", "medium", "started", DAY)
    assert "medium" not in runlog.plan("a", set(), DAY)
    assert runlog.unsettled("a") == ["medium"]
    runlog.mark("a", "medium", "failed", DAY, error="publish button missing")
    assert runlog.unsettled("a") == [] and runlog.plan("a", set(), DAY)[0] == "medium"
    runlog.mark("a", "hashnode", "started", DAY)
    runlog.mark("a", "hashnode", "posted", DAY, url="https://nerdit.hashnode.dev/x")
    assert runlog.unsettled("a") == [] and "hashnode" not in runlog.plan("a", set(), NEXT)


def test_cli_plan_names_sites_to_check_first(capsys):
    runlog.mark("a", "medium", "started", DAY)
    assert runlog.main(["plan", "--slug", "a", "--today", DAY]) == 0
    assert "check first: medium" in capsys.readouterr().out


def test_scheduled_plan_offers_own_blogs_first_then_six_paced_sites():
    assert runlog.plan("a", set(), DAY, scheduled=True) == [
        "wordpress", "blogger", "tumblr", "medium", "hashnode", "hackernoon", "substack", "vocal", "dailydev"]


def test_scheduled_own_blogs_are_not_paced_or_held_across_articles():
    for site in ("medium", "hashnode", "hackernoon", "substack", "vocal", "dailydev"):
        runlog.mark("a", site, "posted", DAY, url=f"https://{site}.example/x")
    runlog.mark("b", "wordpress", "posted", DAY, url="https://wp.example/b")
    assert runlog.plan("a", set(), DAY, scheduled=True) == ["wordpress", "blogger", "tumblr"]


def test_scheduled_every_site_once_a_day_across_articles():
    runlog.mark("a", "medium", "posted", DAY, url="https://medium.com/p/1")
    assert "medium" not in runlog.plan("b", set(), DAY, scheduled=True)
    assert "medium" in runlog.plan("b", set(), NEXT, scheduled=True)


def test_manual_plan_ignores_other_articles_posts():
    runlog.mark("a", "medium", "posted", DAY, url="https://medium.com/p/1")
    assert runlog.plan("b", set(), DAY)[0] == "medium"


def test_scheduled_plan_never_offers_manual_only_sites():
    plan = runlog.plan("a", {"medium", "hashnode", "hackernoon", "substack", "vocal"}, DAY, scheduled=True)
    assert plan == ["wordpress", "blogger", "tumblr", "dailydev", "pinterest", "linkedin", "indiehackers"]
    assert not {"hackernews", "quora"} & set(runlog.SCHEDULED_SITES)


def test_cli_plan_scheduled(capsys):
    assert runlog.main(["plan", "--slug", "a", "--scheduled", "--today", DAY]) == 0
    assert capsys.readouterr().out.split()[:2] == ["wordpress", "blogger"]



NOW = dt.datetime(2026, 11, 24, 12, 0, tzinfo=dt.timezone.utc)


def blog(*posts):  # posts: (slug, iso)
    items = ",".join(f'{{"@type":"BlogPosting","headline":"x","url":"https://nerdit.in/blog/{s}","datePublished":"{d}"}}' for s, d in posts)
    return f'<html><script type="application/ld+json">{{"@context":"https://schema.org","@type":"Blog","blogPost":[{items}]}}</script></html>'


def test_due_newest_first_and_skips_under_24_hours():
    html = blog(("old", "2026-11-14T09:00:00.000Z"), ("new", "2026-11-24T06:00:00.000Z"), ("mid", "2026-11-22T11:05:42.209Z"))
    assert runlog.due_slugs(html, NOW) == ["mid", "old"]


def test_due_boundary_is_24_hours():
    assert runlog.due_slugs(blog(("a", "2026-11-23T12:00:00.000Z")), NOW) == ["a"]
    assert runlog.due_slugs(blog(("b", "2026-11-23T12:00:01.000Z")), NOW) == []


def test_due_without_blogpost_is_empty():
    assert runlog.due_slugs("<html>no json-ld</html>", NOW) == []
    assert runlog.due_slugs('<script type="application/ld+json">{"@type":"Blog"}</script>', NOW) == []


def test_cli_due_fetch_error(monkeypatch, capsys):
    def boom(*a, **k): raise OSError("offline")
    monkeypatch.setattr(runlog.urllib.request, "urlopen", boom)
    assert runlog.main(["due"]) == 1
    assert capsys.readouterr().out.startswith("PROBLEM could not read https://nerdit.in/blog")


def test_report_groups_the_day_across_articles():
    runlog.mark("a", "medium", "posted", DAY, url="https://medium.com/p/1")
    runlog.mark("b", "vocal", "skipped", DAY, error="sign in needed")
    runlog.mark("b", "substack", "failed", DAY, error="editor changed")
    runlog.mark("a", "hashnode", "posted", "2026-11-20", url="https://x.hashnode.dev/a")
    text = runlog.report(DAY)
    assert text.splitlines()[0] == "Posted: 1 · Skipped: 1 · Failed: 1 · Check first: 0"
    assert "- a · medium · https://medium.com/p/1" in text and "- b · vocal · sign in needed" in text
    assert "- b · substack · editor changed" in text and "hashnode" not in text


def test_report_lists_unsettled_from_earlier_days():
    runlog.mark("a", "medium", "started", "2026-11-20")
    text = runlog.report(DAY)
    assert text.splitlines()[0].endswith("Check first: 1") and "- a · medium ·" in text


def test_report_with_nothing_today():
    assert runlog.report(DAY) == "Posted: 0 · Skipped: 0 · Failed: 0 · Check first: 0\n\nNothing ran today."


def test_cli_output_is_utf8_when_redirected(home):
    import subprocess, sys
    from pathlib import Path
    env = {k: v for k, v in __import__("os").environ.items() if k != "PYTHONIOENCODING"} | {"NERDIT_SOCIAL_HOME": str(home.parent)}
    out = subprocess.run([sys.executable, str(Path(runlog.__file__)), "report", "--today", DAY], capture_output=True, env=env, check=True).stdout
    assert out.decode("utf-8").startswith("Posted: 0 · Skipped: 0")


def test_skill_has_a_scheduled_run_section_naming_every_scheduled_site():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    section = text.split("## Scheduled run", 1)[1]
    for needle in ("runlog.py due", "plan --scheduled", "runlog.py report", "24 hours", "sign in needed", *runlog.SCHEDULED_SITES):
        assert needle in section, needle


class Page:
    def __init__(self, body: bytes): self.body = body
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self, *a): return self.body


def test_scheduled_cap_counts_any_step_today_not_only_posted():
    runlog.mark("a", "medium", "started", DAY)
    runlog.mark("a", "hashnode", "skipped", DAY, error="sign in needed")
    runlog.mark("a", "hackernoon", "failed", DAY, error="editor changed")
    assert not {"medium", "hashnode", "hackernoon"} & set(runlog.plan("b", set(), DAY, scheduled=True))
    assert runlog.plan("b", set(), NEXT, scheduled=True)[3:6] == ["medium", "hashnode", "hackernoon"]


def test_due_treats_times_without_offset_as_utc():
    assert runlog.due_slugs(blog(("a", "2026-11-23T12:00:00"), ("b", "2026-11-20")), NOW) == ["a", "b"]
    assert runlog.due_slugs(blog(("a", "2026-11-23T12:00:00.000Z")), NOW.replace(tzinfo=None)) == ["a"]


def test_cli_due_turns_any_error_into_a_problem_line(monkeypatch, capsys):
    def bad(*a, **k): raise ValueError("weird")
    monkeypatch.setattr(runlog.urllib.request, "urlopen", bad)
    assert runlog.main(["due"]) == 1
    assert capsys.readouterr().out.startswith("PROBLEM")


def test_cli_due_page_without_blogpost_is_a_problem_but_none_due_is_not(monkeypatch, capsys):
    monkeypatch.setattr(runlog.urllib.request, "urlopen", lambda *a, **k: Page(b"<html>redesigned</html>"))
    assert runlog.main(["due"]) == 1
    assert "no blogPost list" in capsys.readouterr().out
    monkeypatch.setattr(runlog.urllib.request, "urlopen", lambda *a, **k: Page(blog(("n", "2026-11-24T11:00:00Z")).encode()))
    assert runlog.main(["due", "--now", NOW.isoformat()]) == 0
    assert capsys.readouterr().out.strip() == "nothing due"


def test_images_downloads_only_from_nerdit_storage(home, monkeypatch, capsys):
    monkeypatch.setattr(runlog.urllib.request, "urlopen", lambda *a, **k: Page(b"PNG"))
    url = "https://firebasestorage.googleapis.com/v0/b/x/o/articles%2Fslug%2Fdiagram-1.png?alt=media&token=t"
    assert runlog.main(["images", "--slug", "a", url]) == 0
    saved = home / "a" / "images" / "diagram-1.png"
    assert saved.read_bytes() == b"PNG" and str(saved) in capsys.readouterr().out
    assert runlog.main(["images", "--slug", "a", url, "https://evil.example/x.png"]) == 1
    assert "PROBLEM" in capsys.readouterr().out
    assert runlog.main(["images", "--slug", "../x", url]) == 1


def test_images_without_urls_reads_them_from_the_live_blog_page(home, monkeypatch, capsys):
    # The Chrome tool hides URLs with a query string ("[BLOCKED: Cookie/query string data]", 2026-11-25 run),
    # and every Storage URL has ?alt=media&token=…, so runlog reads the public page itself.
    store = "https://firebasestorage.googleapis.com/v0/b/x/o/blog%2Fa%2F"
    page = (f'<meta property="og:image" content="{store}cover.png?alt=media&amp;token=t1">'
            f'<img src="{store}cover.png?alt=media&amp;token=t1"><img src="{store}fig-1.png?alt=media&amp;token=t2">'
            '<img src="https://evil.example/x.png"><img src="/logo.svg">').encode()
    asked = []
    def fake(url, *a, **k):
        asked.append(url)
        return Page(page if url == "https://nerdit.in/blog/a" else b"PNG")
    monkeypatch.setattr(runlog.urllib.request, "urlopen", fake)
    assert runlog.main(["images", "--slug", "a"]) == 0
    assert asked == ["https://nerdit.in/blog/a", f"{store}cover.png?alt=media&token=t1", f"{store}fig-1.png?alt=media&token=t2"]
    out = capsys.readouterr().out.split()
    assert out == [str(home / "a" / "images" / "cover.png"), str(home / "a" / "images" / "fig-1.png")]


def test_images_without_urls_and_no_images_on_the_page_is_a_problem(home, monkeypatch, capsys):
    monkeypatch.setattr(runlog.urllib.request, "urlopen", lambda *a, **k: Page(b"<html><img src='/logo.svg'></html>"))
    assert runlog.main(["images", "--slug", "a"]) == 1
    assert capsys.readouterr().out.startswith("PROBLEM no NerdIT images on https://nerdit.in/blog/a")


def test_report_save_writes_utf8_file_with_extra_lines(home):
    assert runlog.main(["report", "--today", DAY, "--save", "--extra", "a: press Post copy on the Articles page"]) == 0
    text = (home / "reports" / f"{DAY}.md").read_text(encoding="utf-8")
    assert text.startswith("Posted: 0 · Skipped: 0") and text.rstrip().endswith("a: press Post copy on the Articles page")


def test_launcher_puts_the_prompt_first_and_allows_only_runlog_and_chrome(tmp_path):
    import os, shutil, subprocess
    from pathlib import Path
    if not shutil.which("powershell"):
        pytest.skip("Windows PowerShell only")
    script = Path(__file__).resolve().parent / "scheduled_run.ps1"
    env = os.environ | {"NERDIT_SOCIAL_HOME": str(tmp_path)}
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-DryRun"],
                         capture_output=True, text=True, env=env, timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr
    args = out.stdout.split("claude args:\n", 1)[1].split("\nlog:", 1)[0].splitlines()
    assert args[0] == "-p" and "scheduled run" in args[1] and "/runlog.py" in args[1]
    opt = lambda name: args[args.index(name) + 1]
    assert opt("--setting-sources") == "project" and opt("--permission-mode") == "dontAsk"
    assert Path(opt("--plugin-dir")).is_dir() and "--chrome" in args and opt("--disallowedTools") == "PowerShell"
    allowed = args[args.index("--allowedTools") + 1:]
    runlog_rules = [r for r in allowed if r.startswith("Bash(python ")]
    assert len(runlog_rules) == 1 and runlog_rules[0].endswith("/skills/nerdit-article-poster/scripts/runlog.py *)")
    assert not [r for r in allowed if r.startswith(("Write(", "Edit(")) or "curl" in r]
    assert not (tmp_path / "article-runs" / "scheduled.lock").exists()
