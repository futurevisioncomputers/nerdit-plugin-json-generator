"""Collect fresh news and trends into one dated sheet (trends.json) for the Claude check.

Feeds (all free, checked working 2026-11-24): Google News RSS in English for the US and India, one search per
query in references/queries.txt; Google Trends daily RSS for the US, UK and India; Hacker News top stories.
A feed that fails is recorded in `errors` and the others still count; only every request failing stops the run.

CLI: collect.py --days 2|7 --out <run>/trends.json
"""
import argparse
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus, urlparse

UA = "Mozilla/5.0 (compatible; trend-reels)"
GNEWS = (("gnews-us", "hl=en-US&gl=US&ceid=US:en"), ("gnews-in", "hl=en-IN&gl=IN&ceid=IN:en"))
TRENDS = (("trends-us", "US"), ("trends-gb", "GB"), ("trends-in", "IN"))
HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_COUNT = 30
HT = "{https://trends.google.com/trending/rss}"
QUERIES = Path(__file__).resolve().parent.parent / "references" / "queries.txt"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rss_items(xml: str) -> list[ET.Element]:
    root = ET.fromstring(xml)
    if root.tag != "rss":
        raise ValueError(f"not an RSS feed (root <{root.tag}>)")
    return root.findall("./channel/item")


def _text(el: ET.Element | None) -> str:
    return html.unescape((el.text or "").strip()) if el is not None else ""


def _row(headline, outlet, link, published, feed, query) -> dict:
    return {"headline": headline, "outlet": outlet, "link": link, "published": published, "feed": feed, "query": query}


def parse_gnews(xml: str, feed: str, query: str) -> list[dict]:
    rows = []
    for item in _rss_items(xml):
        title, source = _text(item.find("title")), _text(item.find("source"))
        headline, outlet = title, source
        if source and title.endswith(f" - {source}"):
            headline = title[: -len(f" - {source}")]
        elif not source and " - " in title:
            headline, outlet = title.rsplit(" - ", 1)
        published = _iso(parsedate_to_datetime(_text(item.find("pubDate"))))
        rows.append(_row(headline, outlet, _text(item.find("link")), published, feed, query))
    return rows


def parse_trends(xml: str, feed: str) -> list[dict]:
    rows = []
    for item in _rss_items(xml):
        news = item.find(f"{HT}news_item")
        link = _text(news.find(f"{HT}news_item_url")) if news is not None else ""
        outlet = _text(news.find(f"{HT}news_item_source")) if news is not None else ""
        published = _iso(parsedate_to_datetime(_text(item.find("pubDate"))))
        rows.append(_row(_text(item.find("title")), outlet or "Google Trends", link or _text(item.find("link")),
                         published, feed, ""))
    return rows


def parse_hn(items: list[dict]) -> list[dict]:
    rows = []
    for it in items:
        url = it.get("url")
        if not url:
            continue
        outlet = urlparse(url).netloc.removeprefix("www.")
        published = _iso(datetime.fromtimestamp(int(it.get("time", 0)), timezone.utc))
        rows.append(_row(str(it.get("title", "")), outlet, url, published, "hn", ""))
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        key = " ".join(re.findall(r"[a-z0-9]+", r["headline"].lower()))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.read().decode("utf-8")


def collect(days: int, get: Callable[[str], str], now: datetime, queries: list[str]) -> dict:
    rows, errors, ok = [], [], 0

    def fetch(feed: str, url: str, parse: Callable[[str], list[dict]]) -> None:
        nonlocal ok
        try:
            rows.extend(parse(get(url)))
            ok += 1
        except Exception as e:   # one bad feed must not stop the others
            errors.append({"feed": feed, "url": url, "error": f"{type(e).__name__}: {e}"})

    for query in queries:
        for feed, params in GNEWS:
            url = f"https://news.google.com/rss/search?q={quote_plus(f'{query} when:{days}d')}&{params}"
            fetch(feed, url, lambda x, f=feed, q=query: parse_gnews(x, f, q))
    for feed, geo in TRENDS:
        fetch(feed, f"https://trends.google.com/trending/rss?geo={geo}", lambda x, f=feed: parse_trends(x, f))

    def hn(_: str) -> list[dict]:
        ids = json.loads(get(HN_TOP))[:HN_COUNT]
        return parse_hn([json.loads(get(HN_ITEM.format(i))) for i in ids])
    fetch("hn", HN_TOP, hn)

    if ok == 0:
        raise SystemExit(1)
    cutoff = _iso(now - timedelta(days=days))
    fresh = [r for r in rows if r["published"] >= cutoff]
    return {"collected_at": _iso(now), "days": days, "rows": dedupe(fresh), "errors": errors}


def read_queries(path: Path = QUERIES) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Collect news and trends into trends.json")
    ap.add_argument("--days", type=int, choices=(2, 7), default=2)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        out = collect(args.days, http_get, datetime.now(timezone.utc), read_queries())
    except SystemExit:
        print("every feed failed; nothing collected")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    # ASCII only: the Windows console (cp1252) cannot print every headline
    print(f"rows: {len(out['rows'])}, failed feeds: {len(out['errors'])} -> {args.out}")
    for e in out["errors"]:
        print(f"  {e['feed']}: {e['error']}".encode("ascii", "replace").decode())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
