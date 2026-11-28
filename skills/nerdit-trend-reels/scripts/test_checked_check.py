import copy
import json
from datetime import date

from checked_check import checked_errors, main, quote_problems, site

RUN_DATE = date(2026, 11, 27)
COURSES = [{"id": "course-ai-ba-1", "title": "AI-Driven Business Analysis", "slug": "ai-ba-1"}]
GOOD = {
    "window_days": 2,
    "kept": [{
        "headline": "SAP weighs cutting at least 10,000 positions in AI restructuring",
        "links": ["https://www.investing.com/news/sap-cuts-5052712", "https://www.calcalistech.com/ctechnews/article/al8"],
        "outlets": ["Investing.com", "Calcalist/CTech"],
        "published": "2026-11-26",
        "evidence": ['Investing.com: "considering eliminating at least 10,000 positions as it further aligns its business '
                     'to the artificial intelligence boom"',
                     'Calcalist/CTech: "SAP is considering eliminating at least 10,000 positions worldwide as part of a '
                     'new restructuring"'],
        "course_id": "course-ai-ba-1"}],
    "dropped": [{"headline": "NITES seeks policy on AI layoffs", "reason": "syndicated copy; no second outlet"}],
}


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


def test_google_news_and_hacker_news_links_do_not_count():
    c = kept(links=["https://news.google.com/rss/articles/x", "https://www.investing.com/a"])
    assert "kept 1: links come from 1 site; need 2 different sites" in checked_errors(c, COURSES, RUN_DATE)


def test_needs_two_outlets_each_named_in_the_evidence():
    assert "kept 1: needs 2 outlets" in checked_errors(kept(outlets=["Investing.com"]), COURSES, RUN_DATE)
    c = kept(outlets=["Investing.com", "Reuters"])
    assert "kept 1: outlet 'Reuters' is not named in the evidence" in checked_errors(c, COURSES, RUN_DATE)


def test_published_must_be_inside_the_window():
    assert "kept 1: published 2026-11-20 is outside 2026-11-25..2026-11-27" in checked_errors(
        kept(published="2026-11-20"), COURSES, RUN_DATE)
    assert "kept 1: published 'last week' is not a YYYY-MM-DD date" in checked_errors(
        kept(published="last week"), COURSES, RUN_DATE)


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


PAGE = ("<html><body><script>var x = 1;</script><p>SAP is considering eliminating at least 10,000 positions worldwide "
        "as part of a new restructuring, people said.</p>" + "<p>filler text here</p>" * 200 + "</body></html>")
PAGE2 = ("<p>The company is considering eliminating at least 10,000 positions as it further aligns its business to the "
         "artificial intelligence boom.</p>" + "<p>more words</p>" * 200)


def test_quotes_found_on_both_pages():
    pages = {GOOD["kept"][0]["links"][0]: PAGE2, GOOD["kept"][0]["links"][1]: PAGE}
    assert quote_problems(GOOD["kept"], pages.get) == ([], [])


def test_quote_missing_from_a_readable_page_is_an_error():
    pages = {GOOD["kept"][0]["links"][0]: "<p>" + "nothing about it " * 300 + "</p>", GOOD["kept"][0]["links"][1]: PAGE}
    errors, warnings = quote_problems(GOOD["kept"], pages.get)
    assert errors == ["kept 1: Investing.com quote not found on its page: 'considering eliminating at least 10,000 "
                      "positions as it'"] and warnings == []


def test_unreadable_page_is_only_a_warning():
    pages = {GOOD["kept"][0]["links"][1]: PAGE}   # Investing.com refuses (None)
    errors, warnings = quote_problems(GOOD["kept"], pages.get)
    assert errors == [] and warnings == ["kept 1: could not read the Investing.com page to confirm its quote"]


def test_cli_records_the_verdict_and_prints_ascii(tmp_path, capsys):
    run = tmp_path / "2026-11-27-daily-x"
    run.mkdir()
    c = copy.deepcopy(GOOD)
    c["kept"][0]["evidence"][0] += " “₹ curly”"
    (run / "checked.json").write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    (run / "courses.json").write_text(json.dumps(COURSES), encoding="utf-8")
    assert main([str(run), "--no-fetch"]) == 0
    assert json.loads((run / "checks.json").read_text(encoding="utf-8"))["checked"]["ok"] is True
    assert all(ord(ch) < 128 for ch in capsys.readouterr().out)


def test_cli_needs_courses_json(tmp_path):
    run = tmp_path / "2026-11-27-daily-x"
    run.mkdir()
    (run / "checked.json").write_text(json.dumps(GOOD), encoding="utf-8")
    assert main([str(run), "--no-fetch"]) == 1
    errors = json.loads((run / "checks.json").read_text(encoding="utf-8"))["checked"]["errors"]
    assert errors == ["courses.json is missing: save the live courses from catalogue_status first"]
