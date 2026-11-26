"""Which sites to post an article to today, and a log of every posting step.

    python runlog.py plan --slug <slug> --posted <site,site,...> [--today YYYY-MM-DD]
    python runlog.py mark --slug <slug> --site <site> --status started|posted|failed|skipped|held [--url U] [--error E] [--today D]

`--posted` is the article's own record (the Articles page: sites with a saved link). The log adds what
happened in runs: a site logged as posted is never planned again, even when its link was not saved
(no double posts); a failed site is retried; a skipped site waits until the next day; a held site (the
owner said wait) waits until it is marked again. Pacing: at most
6 sites per article per run day, and Quora/Reddit (`quora`) and Pinterest at most once a day across
all articles. `plan --scheduled` (the daily unattended run) offers only SCHEDULED_SITES, each at most once a
day across all articles; the own blogs (OWN_BLOGS, posted by API) come first and are not paced. State: ~/.nerdit-social/article-runs/<slug>.json and _daily.json (NERDIT_SOCIAL_HOME
overrides).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Dropped 2026-11-26 (owner): Vocal (not in our region), HackerNoon (banned us), Hacker News (posting errors),
# Indie Hackers (needs a subscription).
SITES = ("medium", "hashnode", "linkedin", "substack", "wordpress", "blogger", "tumblr", "dailydev", "pinterest", "quora")
STATUSES = ("started", "posted", "failed", "skipped", "held")
PER_ARTICLE_PER_DAY = 6
ONCE_A_DAY = ("quora", "pinterest")
# The owner's own blogs, posted by the admin's "Post copy" API buttons: no pacing (no spam risk, no ban risk).
OWN_BLOGS = ("wordpress", "blogger", "tumblr")
# Booked by the server: since 2026-11-26 Publish books the LinkedIn link post (Social posts posts it a day later).
# Never planned; the owner may still name it.
SERVER_BOOKED = ("linkedin",)
# Unattended runs: no Quora/Reddit (automation bans). No daily.dev: since 2026-11-26 it posts from GitHub Actions
# (private repo nerdit-cloud-poster, nightly 02:00 IST); the owner may still name it in a manual run.
SCHEDULED_SITES = OWN_BLOGS + ("medium", "hashnode", "substack", "pinterest")
BLOG_INDEX = "https://nerdit.in/blog"
DUE_AFTER = dt.timedelta(hours=24)
IMAGE_HOSTS = ("firebasestorage.googleapis.com", "storage.googleapis.com", "nerdit.in", "www.nerdit.in")
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def _dir() -> Path:
    base = Path(os.environ.get("NERDIT_SOCIAL_HOME") or Path.home() / ".nerdit-social")
    return base / "article-runs"


def _load(path: Path, empty: dict) -> dict:
    """The JSON at `path`; a corrupt file is moved to <name>.bak and an empty record returned."""
    if not path.is_file():
        return empty
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        os.replace(path, path.with_name(path.name + ".bak"))
        return empty


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _latest(steps: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for s in steps:
        out[s["site"]] = s["status"]
    return out


def unsettled(slug: str) -> list[str]:
    """Sites marked `started` (Publish pressed) with no outcome after it: check them on the site first."""
    latest = _latest(_load(_dir() / f"{slug}.json", {"steps": []})["steps"])
    return [s for s in SITES if latest.get(s) == "started"]


def _touched(today: str) -> set[str]:
    """Sites with any step today in any article log (posted, started, skipped or failed)."""
    out: set[str] = set()
    for path in _dir().glob("*.json"):
        if path.name != "_daily.json":
            out |= {s["site"] for s in _load(path, {"steps": []}).get("steps", []) if s.get("day") == today}
    return out


def plan(slug: str, posted: set[str], today: str, scheduled: bool = False) -> list[str]:
    steps = _load(_dir() / f"{slug}.json", {"steps": []})["steps"]
    daily = _load(_dir() / "_daily.json", {}).get(today, {})
    candidates = SCHEDULED_SITES if scheduled else tuple(s for s in SITES if s not in SERVER_BOOKED)
    done = set(posted) | {s["site"] for s in steps if s["status"] == "posted"}
    waiting = {s["site"] for s in steps if s["status"] == "skipped" and s["day"] == today}
    # Scheduled: one try per site per day across articles, so a signed-out site or a lost Publish is not retried.
    # The own blogs are exempt: every due article may get its API copy the same day.
    full = _touched(today) - set(OWN_BLOGS) if scheduled else {site for site in ONCE_A_DAY if daily.get(site, 0) >= 1}
    # started: Publish pressed, outcome unknown; held: the owner said wait. Either way, not until a later mark.
    waiting |= {s for s, status in _latest(steps).items() if status in ("started", "held")}
    paced = (lambda site: site not in OWN_BLOGS) if scheduled else (lambda site: True)
    left = PER_ARTICLE_PER_DAY - sum(1 for s in steps if s["status"] == "posted" and s["day"] == today and paced(s["site"]))
    open_ = [s for s in candidates if s not in done | waiting | full]
    return [s for s in open_ if not paced(s)] + [s for s in open_ if paced(s)][:max(left, 0)]


def due_slugs(html: str, now: dt.datetime) -> list[str]:
    """Slugs live 24 h or more, newest first, from the blog index's JSON-LD `blogPost` list.

    shortcut: the index lists only the 30 newest articles, so older ones are never due; read Firestore if that matters.
    """
    now = now if now.tzinfo else now.replace(tzinfo=dt.timezone.utc)
    posts: list = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            posts = json.loads(block).get("blogPost") or []
        except (json.JSONDecodeError, AttributeError):
            continue
        if posts:
            break
    due = []
    for p in posts:
        try:
            published = dt.datetime.fromisoformat(p["datePublished"].replace("Z", "+00:00"))
            slug = p["url"].rstrip("/").rsplit("/", 1)[-1]
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        published = published if published.tzinfo else published.replace(tzinfo=dt.timezone.utc)
        if now - published >= DUE_AFTER:
            due.append((published, slug))
    return [slug for _, slug in sorted(due, reverse=True)]


def _get(url: str, timeout: int, limit: int | None = None) -> bytes:
    """One GET with one retry: nerdit.in / Storage sometimes reset the first connection (WinError 10054)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read(limit)
    except OSError:
        time.sleep(3)
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read(limit)


def blog_images(page: str) -> list[str]:
    """The cover (og:image) then the body images of a live article page: NerdIT https addresses only, no repeats.

    The Chrome tool hides any URL with a query string, and Storage URLs carry ?alt=media&token=…, so the
    unattended run cannot read them from the page; runlog reads the public page instead.
    """
    found = re.findall(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', page)
    found += re.findall(r"""<img[^>]+src=["']([^"']+)["']""", page)
    urls = [html.unescape(u) for u in found]
    return [u for u in dict.fromkeys(urls)
            if urllib.parse.urlsplit(u).scheme == "https" and urllib.parse.urlsplit(u).hostname in IMAGE_HOSTS]


def save_images(slug: str, urls: list[str]) -> list[Path]:
    """Download an article's images into <runs>/<slug>/images/ for sites that need file uploads.

    Only https NerdIT image addresses: the unattended run reads untrusted pages, so no general downloader.
    """
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError(f"bad slug {slug!r}")
    for u in urls:
        parts = urllib.parse.urlsplit(u)
        if parts.scheme != "https" or parts.hostname not in IMAGE_HOSTS:
            raise ValueError(f"not a NerdIT image address: {u}")
    folder = _dir() / slug / "images"
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, u in enumerate(urls, 1):
        last = urllib.parse.unquote(urllib.parse.urlsplit(u).path).rsplit("/", 1)[-1]
        name = re.sub(r"[^A-Za-z0-9._-]", "_", last).lstrip(".") or f"image-{i}"
        data = _get(u, 60, MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f"image over 20 MB: {u}")
        path = folder / name
        path.write_bytes(data)
        saved.append(path)
    return saved


def report(today: str) -> str:
    """The day across every article log, as Markdown. The first line is read by scheduled_run.ps1."""
    sections: dict[str, list[str]] = {"Posted": [], "Skipped": [], "Failed": [], "Check first": []}
    for path in sorted(_dir().glob("*.json")):
        if path.name == "_daily.json":
            continue
        slug = path.stem
        latest: dict[str, dict] = {}
        for s in _load(path, {"steps": []}).get("steps", []):
            if s["day"] == today:
                latest[s["site"]] = s
        for site, s in latest.items():
            if s["status"] == "posted":
                sections["Posted"].append(f"- {slug} · {site} · {s['url']}")
            elif s["status"] == "skipped":
                sections["Skipped"].append(f"- {slug} · {site} · {s['error'] or 'skipped'}")
            elif s["status"] == "failed":
                sections["Failed"].append(f"- {slug} · {site} · {s['error']}")
        sections["Check first"] += [f"- {slug} · {site} · Publish was pressed; is it live?" for site in unsettled(slug)]
    head = " · ".join(f"{name}: {len(lines)}" for name, lines in sections.items())
    body = "\n\n".join(f"## {name}\n" + "\n".join(lines) for name, lines in sections.items() if lines)
    return f"{head}\n\n{body or 'Nothing ran today.'}"


def mark(slug: str, site: str, status: str, today: str, url: str = "", error: str = "") -> None:
    if site not in SITES or status not in STATUSES:
        raise ValueError(f"unknown site {site!r} or status {status!r}")
    path = _dir() / f"{slug}.json"
    log = _load(path, {"slug": slug, "steps": []})
    log.setdefault("steps", []).append({"site": site, "status": status, "day": today, "url": url, "error": error,
                                        "at": dt.datetime.now().isoformat(timespec="seconds")})
    _save(path, log)
    if status == "posted" and site in ONCE_A_DAY:
        dpath = _dir() / "_daily.json"
        daily = _load(dpath, {})
        daily.setdefault(today, {})[site] = daily.get(today, {}).get(site, 0) + 1
        _save(dpath, daily)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # redirected output on Windows is cp1252; the report is read as UTF-8
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--slug", required=True); p.add_argument("--posted", default=""); p.add_argument("--today")
    p.add_argument("--scheduled", action="store_true")
    m = sub.add_parser("mark")
    m.add_argument("--slug", required=True); m.add_argument("--site", required=True); m.add_argument("--status", required=True)
    m.add_argument("--url", default=""); m.add_argument("--error", default=""); m.add_argument("--today")
    d = sub.add_parser("due")
    d.add_argument("--now", help="ISO time with offset (default: now)")
    r = sub.add_parser("report")
    r.add_argument("--today"); r.add_argument("--save", action="store_true", help="also write reports/<today>.md (UTF-8)")
    r.add_argument("--extra", action="append", default=[], help="a line to add at the end (repeatable)")
    i = sub.add_parser("images")
    i.add_argument("--slug", required=True)
    i.add_argument("urls", nargs="*", help="default: the cover and body images of the live page nerdit.in/blog/<slug>")
    a = ap.parse_args(argv)
    if a.cmd == "due":
        try:
            now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
            with urllib.request.urlopen(BLOG_INDEX, timeout=30) as r:
                html = r.read().decode("utf-8")
            if '"blogPost"' not in html:
                raise ValueError("no blogPost list on the page (did the blog page change?)")
            slugs = due_slugs(html, now)
        except Exception as e:  # unattended: any failure must be a PROBLEM line, never a traceback
            print(f"PROBLEM could not read {BLOG_INDEX}: {e}")
            return 1
        print("\n".join(slugs) if slugs else "nothing due")
        return 0
    if a.cmd == "images":
        try:
            urls = a.urls
            if not urls:
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a.slug):
                    raise ValueError(f"bad slug {a.slug!r}")
                page_url = f"{BLOG_INDEX}/{a.slug}"
                urls = blog_images(_get(page_url, 30).decode("utf-8", "replace"))
                if not urls:
                    raise ValueError(f"no NerdIT images on {page_url}")
            for path in save_images(a.slug, urls):
                print(path)
        except Exception as e:
            print(f"PROBLEM {e}")
            return 1
        return 0
    today = a.today or dt.date.today().isoformat()
    if a.cmd == "report":
        text = report(today) + ("\n\n" + "\n".join(a.extra) if a.extra else "")
        if a.save:
            path = _dir() / "reports" / f"{today}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
    if a.cmd == "plan":
        sites = plan(a.slug, {s.strip() for s in a.posted.split(",") if s.strip()}, today, a.scheduled)
        print("\n".join(sites) if sites else "nothing to post today")
        for site in unsettled(a.slug):
            print(f"check first: {site} (Publish was pressed but no link was logged: is it live there?)")
        return 0
    try:
        mark(a.slug, a.site, a.status, today, a.url, a.error)
    except ValueError as e:
        print(f"PROBLEM {e}")
        return 1
    print(f"logged {a.site}: {a.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
