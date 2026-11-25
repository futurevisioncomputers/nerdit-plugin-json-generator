import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from collect import collect, dedupe, parse_gnews, parse_hn, parse_trends

FIX = Path(__file__).parent / "fixtures"
GNEWS = (FIX / "gnews.xml").read_text(encoding="utf-8")
TRENDS = (FIX / "trends.xml").read_text(encoding="utf-8")
HN_ITEMS = json.loads((FIX / "hn_items.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)

ENTITY_RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>AT&amp;T cuts 2,000 jobs as AI takes over support - Reuters</title><link>https://news.google.com/x</link>
<pubDate>Wed, 25 Nov 2026 08:00:00 GMT</pubDate><source url="https://www.reuters.com">Reuters</source></item>
<item><title>No outlet suffix here</title><link>https://news.google.com/y</link>
<pubDate>Wed, 25 Nov 2026 07:00:00 GMT</pubDate><source url="https://apnews.com">AP News</source></item>
</channel></rss>"""


def test_gnews_rows_split_headline_and_outlet():
    rows = parse_gnews(GNEWS, "gnews-us", "AI jobs")
    assert len(rows) == 3
    assert rows[0]["headline"] == "As AI reshapes hiring process, recent college grads feel stuck in job-search purgatory"
    assert rows[0]["outlet"] == "EdSource"
    assert rows[0]["published"] == "2026-11-25T09:23:32Z"
    assert rows[0]["feed"] == "gnews-us" and rows[0]["query"] == "AI jobs"
    assert rows[0]["link"].startswith("https://news.google.com/")


def test_gnews_decodes_entities_and_uses_source_when_no_suffix():
    rows = parse_gnews(ENTITY_RSS, "gnews-in", "AI layoffs")
    assert rows[0]["headline"] == "AT&T cuts 2,000 jobs as AI takes over support"
    assert rows[0]["outlet"] == "Reuters"
    assert rows[1]["headline"] == "No outlet suffix here" and rows[1]["outlet"] == "AP News"


def test_trends_keep_the_search_term_and_first_news_item():
    rows = parse_trends(TRENDS, "trends-us")
    assert rows[0]["headline"] == "j. t. realmuto"
    assert rows[0]["outlet"] == "Forbes"
    assert rows[0]["link"].startswith("https://www.forbes.com/")
    assert rows[0]["published"] == "2026-11-25T10:50:00Z"
    assert rows[0]["query"] == ""


def test_hn_rows_use_the_link_domain_as_outlet():
    rows = parse_hn(HN_ITEMS + [{"id": 1, "title": "Ask HN: no link", "time": 1795600000, "type": "story"}])
    assert len(rows) == 3   # the item without a url is dropped
    assert all(r["feed"] == "hn" for r in rows)
    assert all(not r["outlet"].startswith("www.") and "." in r["outlet"] for r in rows)
    assert rows[0]["published"].endswith("Z")


def test_dedupe_keeps_the_first_of_the_same_headline():
    a = {"headline": "AI Is Making It Hard for Young People to Find Work", "feed": "gnews-us"}
    b = {"headline": "AI is making it hard for young people to find work!", "feed": "gnews-in"}
    assert dedupe([a, b]) == [a]


def fake_get(fail=(), html=()):
    def get(url):
        host = url.split("/")[2]
        if host in fail:
            raise OSError("connection refused")
        if host in html:
            return "<html>blocked</html>"
        if host == "news.google.com":
            return GNEWS
        if host == "trends.google.com":
            return TRENDS
        if url.endswith("topstories.json"):
            return json.dumps([it["id"] for it in HN_ITEMS])
        item_id = int(url.rsplit("/", 1)[1].split(".")[0])
        return json.dumps(next(it for it in HN_ITEMS if it["id"] == item_id))
    return get


def test_collect_gathers_every_feed():
    out = collect(2, get=fake_get(), now=NOW, queries=["AI jobs"])
    assert {r["feed"] for r in out["rows"]} >= {"gnews-us", "trends-us", "hn"}
    assert out["errors"] == [] and out["days"] == 2


def test_one_failing_feed_is_recorded_and_others_kept():
    out = collect(2, get=fake_get(fail={"trends.google.com"}), now=NOW, queries=["AI jobs"])
    assert out["rows"]
    assert {e["feed"] for e in out["errors"]} == {"trends-us", "trends-gb", "trends-in"}


def test_html_instead_of_rss_counts_as_a_failed_feed():
    out = collect(2, get=fake_get(html={"news.google.com"}), now=NOW, queries=["AI jobs"])
    assert {e["feed"] for e in out["errors"]} == {"gnews-us", "gnews-in"}
    assert out["rows"]


def test_all_feeds_failing_exits():
    with pytest.raises(SystemExit):
        collect(2, get=fake_get(fail={"news.google.com", "trends.google.com", "hacker-news.firebaseio.com"}),
                now=NOW, queries=["AI jobs"])


def test_rows_outside_the_window_are_dropped():
    out = collect(2, get=fake_get(), now=NOW + timedelta(days=10), queries=["AI jobs"])
    assert not [r for r in out["rows"] if r["feed"].startswith("gnews")]
