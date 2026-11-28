"""Check checked.json (step 3, the two-outlet check) whoever wrote it: Claude, or Gemini through gemini_check.py.

The rules are references/editorial.md "Keep a story only if": two different sites with their own reporting, fresh
inside the run's window, a live course, numbers the sources carry. Each outlet has its own link (same order) and its
own `Outlet: "quote"` evidence line; every quote's words and numbers are confirmed on that outlet's page. A page that
cannot be read (block, paywall, timeout, or text that is not the story) is only a warning; a page that carries the
story but not the quoted words or numbers is an error. Page text is never printed.

CLI: checked_check.py <run> [--no-fetch]   records checks.json["checked"] (with "fetched"); exit 1 on errors.
     --no-fetch is for tests and dry checks: `runs.py ready` refuses a verdict made without fetching.
"""
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from numwords import find, normalise
from runs import record_check

NOT_OUTLETS = {"news.google.com", "news.ycombinator.com"}   # an aggregator link is not an outlet's own reporting
TWO_PART_SUFFIXES = {"co.in", "co.uk", "com.au", "org.uk", "gov.in", "net.in", "ac.in", "org.in", "co.jp"}
MIN_PAGE_TEXT = 2000        # characters of page text before a page can count as loaded
QUOTE_WORDS = 8
MIN_PART_WORDS = 4          # a quote split at "..." matches each part of at least this many words
PAGE_SECONDS = 15           # one page
TOTAL_SECONDS = 60          # all pages together (fetched in parallel), so the checker never stalls the run
QUOTE = re.compile(r'"([^"]{20,})"')
INVISIBLE = dict.fromkeys(map(ord, "­​‌‍⁠﻿"))
STOP = {"about", "after", "their", "there", "these", "which", "would", "could", "while", "where", "other", "being"}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
WINDOW = {"daily": 2, "weekly": 7}


def site(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if not host or host in NOT_OUTLETS:
        return None
    host = re.sub(r"^(?:www|m)\.", "", host)
    labels = host.split(".")
    keep = 3 if ".".join(labels[-2:]) in TWO_PART_SUFFIXES else 2
    return ".".join(labels[-keep:])


def _straight(text: str) -> str:
    """Quotes straightened and invisible characters gone; the writer's own words otherwise (for messages)."""
    text = text.translate(INVISIBLE)
    return text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")


def _plain(text: str) -> str:
    """For matching only: _straight, digit groups joined, "per cent" as "percent"."""
    text = re.sub(r"(?<=\d),(?=\d)", "", _straight(text))
    return re.sub(r"\bper\s+cent\b", "percent", text, flags=re.I)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _plain(text).lower())


def _quote_lines(story: dict, outlet: str) -> list[str]:
    return [_straight(e) for e in story.get("evidence") or [] if _straight(e).strip().startswith(f"{outlet}:")]


def checked_errors(checked: dict, courses: list[dict], run_date: date, window: int = 2) -> list[str]:
    """`window` comes from the run (trends.json "days"), never from the file being judged."""
    first = run_date - timedelta(days=window)
    live = {c.get("id") for c in courses}
    errors = []
    for i, story in enumerate(checked.get("kept") or [], 1):
        label = f"kept {i}"
        headline = (story.get("headline") or "").strip()
        if not headline:
            errors.append(f"{label}: headline is empty")
        links = list(story.get("links") or [])
        for n, url in enumerate(links, 1):
            host = (urlparse(url).hostname or "").lower()
            if host in NOT_OUTLETS:
                errors.append(f"{label}: link {n} is a {host} link; give the outlet's own article")
        sites = {s for s in (site(u) for u in links) if s}
        if len(sites) < 2:
            errors.append(f"{label}: links come from {len(sites)} site{'s' if len(sites) != 1 else ''}; "
                          "need 2 different sites")
        outlets = [o.strip() for o in story.get("outlets") or [] if o and o.strip()]
        if len(set(outlets)) < 2:
            errors.append(f"{label}: needs 2 outlets")
        if len(links) != len(outlets):
            errors.append(f"{label}: give one link per outlet, in the same order ({len(links)} links, "
                          f"{len(outlets)} outlets)")
        for o in outlets:
            if not any(QUOTE.search(line) for line in _quote_lines(story, o)):
                errors.append(f"{label}: outlet '{o}' has no evidence line starting '{o}: \"...\"'")
        published = str(story.get("published") or "")
        try:
            day = date.fromisoformat(published)
            if not first <= day <= run_date:
                errors.append(f"{label}: published {published} is outside {first}..{run_date}")
        except ValueError:
            errors.append(f"{label}: published '{published}' is not a YYYY-MM-DD date")
        if story.get("course_id") not in live:
            errors.append(f"{label}: course_id '{story.get('course_id')}' is not a live course in courses.json")
        known = normalise(" ".join(story.get("evidence") or []))
        errors += [f"{label}: headline number {raw} is not in the evidence" for raw, norm in find(headline)
                   if norm not in known]
    for i, story in enumerate(checked.get("dropped") or [], 1):
        if not (story.get("reason") or "").strip():
            errors.append(f"dropped {i}: give the reason")
    return errors


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.json_ld, self._skip, self._ld = [], [], 0, False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
            self._ld = tag == "script" and ("type", "application/ld+json") in [(k, (v or "").lower()) for k, v in attrs]

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
            self._ld = False

    def handle_data(self, data):
        if self._ld:
            self.json_ld.append(data)
        elif not self._skip:
            self.parts.append(data)


def _article_bodies(node) -> list[str]:
    if isinstance(node, dict):
        found = [node["articleBody"]] if isinstance(node.get("articleBody"), str) else []
        return found + [b for v in node.values() for b in _article_bodies(v)]
    if isinstance(node, list):
        return [b for v in node for b in _article_bodies(v)]
    return []


def page_text(html: str) -> str:
    """Visible text plus any JSON-LD articleBody (many news sites put the story only there)."""
    parser = _Text()
    parser.feed(html)
    bodies = []
    for block in parser.json_ld:
        try:
            bodies += _article_bodies(json.loads(block))
        except ValueError:
            continue
    return " ".join(parser.parts + bodies)


def fetch(url: str) -> str | None:
    if urlparse(url).scheme not in ("http", "https"):
        return None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=PAGE_SECONDS) as response:
            return response.read(3_000_000).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001  any network trouble just means "could not read"
        return None


def _fetch_all(urls: list[str], fetch, time_limit: float) -> dict[str, str | None]:
    pool = ThreadPoolExecutor(max_workers=6)
    futures = {url: pool.submit(fetch, url) for url in dict.fromkeys(urls)}   # each URL once
    wait(list(futures.values()), timeout=time_limit)
    pool.shutdown(wait=False, cancel_futures=True)
    pages = {}
    for url, future in futures.items():
        try:
            pages[url] = future.result() if future.done() else None
        except Exception:  # noqa: BLE001
            pages[url] = None
    return pages


def _carries_story(words: list[str], numbers: set[str], story: dict) -> bool:
    """A loaded page that is the story: enough text, and the headline's words or the evidence's numbers on it."""
    if len(" ".join(words)) < MIN_PAGE_TEXT:
        return False
    head = {w for w in _words(story.get("headline") or "") if len(w) >= 5 and w not in STOP}
    return len(head & set(words)) >= 2 or bool(normalise(" ".join(story.get("evidence") or [])) & numbers)


def quote_problems(kept: list[dict], fetch=fetch, time_limit: float = TOTAL_SECONDS) -> tuple[list[str], list[str]]:
    pairs = [(i, story, outlet, link) for i, story in enumerate(kept, 1)
             for outlet, link in zip(story.get("outlets") or [], story.get("links") or [])]
    pages = _fetch_all([link for *_, link in pairs], fetch, time_limit)
    errors, warnings = [], []
    for i, story, outlet, link in pairs:
        label = f"kept {i}"
        fragments = [f for line in _quote_lines(story, outlet) for f in QUOTE.findall(line)]
        if not fragments:
            continue                                # checked_errors reports the missing quote line
        html = pages.get(link)
        text = page_text(html) if html else ""
        words = _words(text)
        numbers = normalise(_plain(text))
        if not _carries_story(words, numbers, story):
            warnings.append(f"{label}: could not read the {outlet} page to confirm its quote")
            continue
        page = " ".join(words)
        for fragment in fragments:
            parts = [p for p in re.split(r"\s*(?:…|\.\.\.)\s*", fragment) if len(_words(p)) >= MIN_PART_WORDS]
            for part in parts or [fragment]:
                head = _words(part)[:QUOTE_WORDS]
                if head and " ".join(head) not in page:
                    shown = " ".join(part.split()[:QUOTE_WORDS])
                    errors.append(f"{label}: {outlet} quote not found on its page: '{shown}'")
                    break
            else:
                errors += [f"{label}: {outlet} quote number {raw} is not on its page"
                           for raw, norm in find(fragment) if norm not in numbers]
    return errors, warnings


def run_window(run: Path) -> int:
    """The run's own window: trends.json "days" (collect.py), else the kind in the folder name."""
    trends = run / "trends.json"
    if trends.exists():
        try:
            return int(json.loads(trends.read_text(encoding="utf-8")).get("days") or 2)
        except (ValueError, AttributeError):
            pass
    kind = next((k for k in WINDOW if f"-{k}-" in run.name), "daily")
    return WINDOW[kind]


def _say(line: str) -> None:
    print(line.encode("ascii", "replace").decode())   # the Windows console is cp1252


def main(argv: list[str]) -> int:
    args = [a for a in argv if a != "--no-fetch"]
    if len(args) != 1:
        _say(__doc__)
        return 2
    run = Path(args[0])
    fetched = "--no-fetch" not in argv
    checked = json.loads((run / "checked.json").read_text(encoding="utf-8"))
    courses_path = run / "courses.json"
    warnings = []
    if not courses_path.exists():
        errors = ["courses.json is missing: save the live courses from catalogue_status first"]
    else:
        courses = json.loads(courses_path.read_text(encoding="utf-8"))
        errors = checked_errors(checked, courses, date.fromisoformat(run.name[:10]), run_window(run))
        if fetched:
            start = time.monotonic()
            quote_errors, warnings = quote_problems(checked.get("kept") or [])
            errors += quote_errors
            _say(f"pages checked in {time.monotonic() - start:.0f} s")
    record_check(run, "checked", errors, [run / "checked.json", courses_path], fetched=fetched)
    for w in warnings:
        _say(f"warning: {w}")
    for e in errors or [f"checked ok ({len(checked.get('kept') or [])} kept)"]:
        _say(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
