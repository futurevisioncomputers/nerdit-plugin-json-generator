"""Check checked.json (step 3, the two-outlet check) whoever wrote it: Gemini through gemini_check.py, or Claude.

The rules are references/editorial.md "Keep a story only if": two different sites with their own reporting, fresh
inside the window, a live course, numbers the sources carry. The quotes in `evidence` are confirmed against the
outlets' pages; a page that cannot be read (paywall, block, timeout) is only a warning, a readable page without the
quoted words is an error.

CLI: checked_check.py <run> [--no-fetch]   records checks.json["checked"]; exit 1 on errors
"""
import json
import re
import sys
import urllib.request
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from numwords import find, normalise
from runs import record_check

NOT_OUTLETS = {"news.google.com", "news.ycombinator.com"}   # an aggregator link is not an outlet's own reporting
TWO_PART_SUFFIXES = {"co.in", "co.uk", "com.au", "org.uk", "gov.in", "net.in", "ac.in", "org.in", "co.jp"}
MIN_PAGE_TEXT = 2000        # characters of page text that mean the article really loaded
QUOTE_WORDS = 8
QUOTE = re.compile(r'"([^"]{20,})"')
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def site(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if not host or host in NOT_OUTLETS:
        return None
    host = re.sub(r"^(?:www|m)\.", "", host)
    labels = host.split(".")
    keep = 3 if ".".join(labels[-2:]) in TWO_PART_SUFFIXES else 2
    return ".".join(labels[-keep:])


def _ascii_quotes(text: str) -> str:
    return text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")


def checked_errors(checked: dict, courses: list[dict], run_date: date) -> list[str]:
    window = int(checked.get("window_days") or 2)
    first = run_date - timedelta(days=window)
    live = {c.get("id") for c in courses}
    errors = []
    for i, story in enumerate(checked.get("kept") or [], 1):
        label = f"kept {i}"
        headline = (story.get("headline") or "").strip()
        if not headline:
            errors.append(f"{label}: headline is empty")
        sites = {s for s in (site(u) for u in story.get("links") or []) if s}
        if len(sites) < 2:
            errors.append(f"{label}: links come from {len(sites)} site{'s' if len(sites) != 1 else ''}; "
                          "need 2 different sites")
        outlets = [o.strip() for o in story.get("outlets") or [] if o and o.strip()]
        evidence = " ".join(story.get("evidence") or [])
        if len(set(outlets)) < 2:
            errors.append(f"{label}: needs 2 outlets")
        errors += [f"{label}: outlet '{o}' is not named in the evidence" for o in outlets if o not in evidence]
        published = str(story.get("published") or "")
        try:
            day = date.fromisoformat(published)
            if not first <= day <= run_date:
                errors.append(f"{label}: published {published} is outside {first}..{run_date}")
        except ValueError:
            errors.append(f"{label}: published '{published}' is not a YYYY-MM-DD date")
        if story.get("course_id") not in live:
            errors.append(f"{label}: course_id '{story.get('course_id')}' is not a live course in courses.json")
        known = normalise(evidence)
        errors += [f"{label}: headline number {raw} is not in the evidence" for raw, norm in find(headline)
                   if norm not in known]
    for i, story in enumerate(checked.get("dropped") or [], 1):
        if not (story.get("reason") or "").strip():
            errors.append(f"dropped {i}: give the reason")
    return errors


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        self._skip += tag in ("script", "style", "noscript")

    def handle_endtag(self, tag):
        self._skip -= tag in ("script", "style", "noscript") and self._skip > 0

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def page_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    return " ".join(parser.parts)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _ascii_quotes(text).lower())


def fetch(url: str) -> str | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read(3_000_000).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001  any network trouble just means "could not read"
        return None


def quote_problems(kept: list[dict], fetch=fetch) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for i, story in enumerate(kept, 1):
        label = f"kept {i}"
        for outlet, link in zip(story.get("outlets") or [], story.get("links") or []):
            lines = [_ascii_quotes(e) for e in story.get("evidence") or [] if e.strip().startswith(outlet)]
            fragments = [f for line in lines for f in QUOTE.findall(line)]
            if not fragments:
                continue
            html = fetch(link)
            text = page_text(html) if html else ""
            if len(text) < MIN_PAGE_TEXT:
                warnings.append(f"{label}: could not read the {outlet} page to confirm its quote")
                continue
            page = " ".join(_words(text))
            for fragment in fragments:
                head = _words(fragment)[:QUOTE_WORDS]
                if head and " ".join(head) not in page:
                    shown = " ".join(fragment.split()[:QUOTE_WORDS])
                    errors.append(f"{label}: {outlet} quote not found on its page: '{shown}'")
    return errors, warnings


def _say(line: str) -> None:
    print(line.encode("ascii", "replace").decode())   # the Windows console is cp1252


def main(argv: list[str]) -> int:
    args = [a for a in argv if a != "--no-fetch"]
    if len(args) != 1:
        _say(__doc__)
        return 2
    run = Path(args[0])
    checked = json.loads((run / "checked.json").read_text(encoding="utf-8"))
    courses_path = run / "courses.json"
    warnings = []
    if not courses_path.exists():
        errors = ["courses.json is missing: save the live courses from catalogue_status first"]
    else:
        courses = json.loads(courses_path.read_text(encoding="utf-8"))
        errors = checked_errors(checked, courses, date.fromisoformat(run.name[:10]))
        if "--no-fetch" not in argv:
            quote_errors, warnings = quote_problems(checked.get("kept") or [])
            errors += quote_errors
    record_check(run, "checked", errors, [run / "checked.json", courses_path])
    for w in warnings:
        _say(f"warning: {w}")
    for e in errors or [f"checked ok ({len(checked.get('kept') or [])} kept)"]:
        _say(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
