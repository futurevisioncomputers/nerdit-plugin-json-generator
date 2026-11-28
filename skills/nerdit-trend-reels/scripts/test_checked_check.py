import copy
import json
import time
from datetime import date

from checked_check import checked_errors, main, quote_problems, site

RUN_DATE = date(2026, 11, 27)
COURSES = [{"id": "course-ai-ba-1", "title": "AI-Driven Business Analysis", "slug": "ai-ba-1"}]
LINK_A = "https://www.investing.com/news/sap-cuts-5052712"
LINK_B = "https://www.calcalistech.com/ctechnews/article/al8"
GOOD = {
    "window_days": 2,
    "kept": [{
        "headline": "SAP weighs cutting at least 10,000 positions in AI restructuring",
        "links": [LINK_A, LINK_B],
        "outlets": ["Investing.com", "Calcalist/CTech"],
        "published": "2026-11-26",
        "evidence": ['Investing.com: "considering eliminating at least 10,000 positions as it further aligns its business '
                     'to the artificial intelligence boom"',
                     'Calcalist/CTech: "SAP is considering eliminating at least 10,000 positions worldwide as part of a '
                     'new restructuring"'],
        "course_id": "course-ai-ba-1"}],
    "dropped": [{"headline": "NITES seeks policy on AI layoffs", "reason": "syndicated copy; no second outlet"}],
}
FILLER = "<p>filler text here</p>" * 200
PAGE_A = ("<p>The company is considering eliminating at least 10,000 positions as it further aligns its business to the "
          "artificial intelligence boom.</p>" + FILLER)
PAGE_B = ("<html><body><script>var x = 1;</script><p>SAP is considering eliminating at least 10,000 positions worldwide "
          "as part of a new restructuring, people said.</p>" + FILLER + "</body></html>")


def kept(**change):
    c = copy.deepcopy(GOOD)
    c["kept"][0].update(change)
    return c


def test_good_checked_passes():
    assert checked_errors(GOOD, COURSES, RUN_DATE) == []


def test_site_strips_www_and_m_and_keeps_country_suffixes():
    assert site("https://www.investing.com/x") == site("https://m.investing.com/y") == "investing.com"
    assert site("https://economictimes.indiatimes.com/a") == "indiatimes.com"
    assert site("https://www.business-standard.co.in/a") == "business-standard.co.in"
    assert site("https://news.google.com/rss/articles/abc") is None
    assert site("https://news.ycombinator.com/item?id=1") is None


def test_one_site_twice_is_not_two_outlets():
    c = kept(links=["https://www.investing.com/a", "https://m.investing.com/b"])
    assert "kept 1: links come from 1 site; need 2 different sites" in checked_errors(c, COURSES, RUN_DATE)


def test_aggregator_link_is_an_error():
    c = kept(links=["https://news.google.com/rss/articles/x", LINK_A])
    errors = checked_errors(c, COURSES, RUN_DATE)
    assert "kept 1: link 1 is a news.google.com link; give the outlet's own article" in errors
    assert "kept 1: links come from 1 site; need 2 different sites" in errors


def test_one_link_per_outlet_in_the_same_order():
    c = kept(links=[LINK_A, LINK_B, "https://www.reuters.com/x"])
    assert "kept 1: give one link per outlet, in the same order (3 links, 2 outlets)" in checked_errors(
        c, COURSES, RUN_DATE)


def test_needs_two_outlets_each_with_its_own_quoted_line():
    assert "kept 1: needs 2 outlets" in checked_errors(kept(outlets=["Investing.com"], links=[LINK_A]), COURSES, RUN_DATE)
    c = kept(outlets=["Investing.com", "Reuters"])
    assert "kept 1: outlet 'Reuters' has no evidence line starting 'Reuters: \"...\"'" in checked_errors(
        c, COURSES, RUN_DATE)
    paraphrase = kept(evidence=[GOOD["kept"][0]["evidence"][0], "Calcalist/CTech: SAP may cut 10,000 jobs"])
    assert ("kept 1: outlet 'Calcalist/CTech' has no evidence line starting 'Calcalist/CTech: \"...\"'"
            in checked_errors(paraphrase, COURSES, RUN_DATE))


def test_published_must_be_inside_the_window():
    assert "kept 1: published 2026-11-20 is outside 2026-11-25..2026-11-27" in checked_errors(
        kept(published="2026-11-20"), COURSES, RUN_DATE)
    assert "kept 1: published 'last week' is not a YYYY-MM-DD date" in checked_errors(
        kept(published="last week"), COURSES, RUN_DATE)


def test_window_comes_from_the_run_not_from_the_file():
    c = kept(published="2026-01-10")
    c["window_days"] = 365
    assert "kept 1: published 2026-01-10 is outside 2026-11-25..2026-11-27" in checked_errors(c, COURSES, RUN_DATE)


def test_weekly_window_keeps_a_five_day_old_story():
    assert checked_errors(kept(published="2026-11-24"), COURSES, date(2026, 11, 29), window=7) == []


def test_course_must_be_live():
    assert "kept 1: course_id 'course-old' is not a live course in courses.json" in checked_errors(
        kept(course_id="course-old"), COURSES, RUN_DATE)


def test_headline_number_must_be_in_the_evidence():
    c = kept(headline="SAP weighs cutting at least 12,000 positions in AI restructuring")
    assert "kept 1: headline number 12,000 is not in the evidence" in checked_errors(c, COURSES, RUN_DATE)


def test_dropped_story_needs_a_reason():
    c = copy.deepcopy(GOOD)
    c["dropped"][0]["reason"] = " "
    assert "dropped 1: give the reason" in checked_errors(c, COURSES, RUN_DATE)


def test_low_news_day_with_nothing_kept_passes():
    c = copy.deepcopy(GOOD)
    c["kept"] = []
    assert checked_errors(c, COURSES, RUN_DATE) == []


# --- quotes on the outlets' pages ---

def test_quotes_found_on_both_pages():
    assert quote_problems(GOOD["kept"], {LINK_A: PAGE_A, LINK_B: PAGE_B}.get) == ([], [])


def test_quote_missing_from_a_readable_page_is_an_error():
    page = "<p>SAP restructuring: the company may cut 10,000 positions, a report says.</p>" + FILLER
    errors, warnings = quote_problems(GOOD["kept"], {LINK_A: page, LINK_B: PAGE_B}.get)
    assert errors == ["kept 1: Investing.com quote not found on its page: 'considering eliminating at least 10,000 "
                      "positions as it'"] and warnings == []


def test_unreadable_page_is_only_a_warning():
    errors, warnings = quote_problems(GOOD["kept"], {LINK_B: PAGE_B}.get)   # Investing.com refuses (None)
    assert errors == [] and warnings == ["kept 1: could not read the Investing.com page to confirm its quote"]


def test_paywall_page_without_the_story_is_only_a_warning():
    menu = "<p>" + "Home Markets News Opinion Subscribe Sign in Prime " * 80 + "</p>"
    errors, warnings = quote_problems(GOOD["kept"], {LINK_A: menu, LINK_B: PAGE_B}.get)
    assert errors == [] and warnings == ["kept 1: could not read the Investing.com page to confirm its quote"]


def test_quote_number_must_be_on_the_page():
    c = kept(evidence=['Investing.com: "considering eliminating at least 10,000 positions as it further aligns its '
                       'business, a cut of 99,000 roles"', GOOD["kept"][0]["evidence"][1]])
    page = PAGE_A.replace("boom.", "boom, a cut of 9,000 roles.")
    errors, _ = quote_problems(c["kept"], {LINK_A: page, LINK_B: PAGE_B}.get)
    assert errors == ["kept 1: Investing.com quote number 99,000 is not on its page"]


def test_quote_matches_despite_digit_groups_per_cent_soft_hyphen_and_ellipsis():
    c = kept(evidence=['Investing.com: "considering eliminating at least 10000 positions ... about 9 percent of its '
                       'global workforce in the restructuring"', GOOD["kept"][0]["evidence"][1]])
    page = ("<p>SAP is considering eliminating at least 10,000 positions worldwide, about 9 per cent of its global "
            "workforce in the restruc­turing.</p>" + FILLER)
    assert quote_problems(c["kept"], {LINK_A: page, LINK_B: PAGE_B}.get) == ([], [])


def test_json_ld_article_body_is_read():
    body = json.dumps({"@type": "NewsArticle", "articleBody": "SAP is considering eliminating at least 10,000 positions "
                       "as it further aligns its business to the artificial intelligence boom."})
    page = '<script type="application/ld+json">' + body + "</script>" + FILLER
    assert quote_problems(GOOD["kept"], {LINK_A: page, LINK_B: PAGE_B}.get) == ([], [])


def test_each_page_is_fetched_once_and_total_time_is_capped():
    calls = []

    def slow(url):
        calls.append(url)
        time.sleep(1.0)
        return PAGE_A

    stories = GOOD["kept"] * 2                      # the same two links twice
    start = time.monotonic()
    errors, warnings = quote_problems(stories, slow, time_limit=0.2)
    assert time.monotonic() - start < 0.9
    assert sorted(set(calls)) == sorted(calls)      # no URL fetched twice
    assert errors == [] and len(warnings) == 4      # unfinished fetches are "could not read"


# --- the command ---

def write_run(tmp_path, name="2026-11-27-daily-x", checked=GOOD, trends_days=None):
    run = tmp_path / name
    run.mkdir()
    (run / "checked.json").write_text(json.dumps(checked, ensure_ascii=False), encoding="utf-8")
    (run / "courses.json").write_text(json.dumps(COURSES), encoding="utf-8")
    if trends_days:
        (run / "trends.json").write_text(json.dumps({"days": trends_days, "rows": []}), encoding="utf-8")
    return run


def test_cli_records_the_verdict_and_prints_ascii(tmp_path, capsys):
    c = copy.deepcopy(GOOD)
    c["kept"][0]["evidence"][0] += " “₹ curly”"
    run = write_run(tmp_path, checked=c)
    assert main([str(run), "--no-fetch"]) == 0
    verdict = json.loads((run / "checks.json").read_text(encoding="utf-8"))["checked"]
    assert verdict["ok"] is True and verdict["fetched"] is False
    assert all(ord(ch) < 128 for ch in capsys.readouterr().out)


def test_cli_reads_the_window_from_trends_json(tmp_path):
    run = write_run(tmp_path, "2026-11-29-weekly-x", kept(published="2026-11-24"), trends_days=7)
    assert main([str(run), "--no-fetch"]) == 0


def test_cli_needs_courses_json(tmp_path):
    run = write_run(tmp_path)
    (run / "courses.json").unlink()
    assert main([str(run), "--no-fetch"]) == 1
    errors = json.loads((run / "checks.json").read_text(encoding="utf-8"))["checked"]["errors"]
    assert errors == ["courses.json is missing: save the live courses from catalogue_status first"]
