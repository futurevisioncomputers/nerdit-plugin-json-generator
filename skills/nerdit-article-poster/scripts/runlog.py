"""Which sites to post an article to today, and a log of every posting step.

    python runlog.py plan --slug <slug> --posted <site,site,...> [--today YYYY-MM-DD]
    python runlog.py mark --slug <slug> --site <site> --status started|posted|failed|skipped [--url U] [--error E] [--today D]

`--posted` is the article's own record (the Articles page: sites with a saved link). The log adds what
happened in runs: a site logged as posted is never planned again, even when its link was not saved
(no double posts); a failed site is retried; a skipped site waits until the next day. Pacing: at most
6 sites per article per run day, and Quora/Reddit (`quora`) and Pinterest at most once a day across
all articles. `plan --scheduled` (the daily unattended run) offers only SCHEDULED_SITES, each at most once a
day across all articles. State: ~/.nerdit-social/article-runs/<slug>.json and _daily.json (NERDIT_SOCIAL_HOME
overrides).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

SITES = ("medium", "hashnode", "hackernoon", "linkedin", "substack", "wordpress", "blogger", "tumblr", "vocal",
         "hackernews", "dailydev", "indiehackers", "pinterest", "quora")
STATUSES = ("started", "posted", "failed", "skipped")
PER_ARTICLE_PER_DAY = 6
ONCE_A_DAY = ("quora", "pinterest")
# Unattended runs: no Quora/Reddit, Hacker News or LinkedIn (automation bans); WordPress/Blogger/Tumblr post by API.
SCHEDULED_SITES = ("medium", "hashnode", "hackernoon", "substack", "vocal", "dailydev", "indiehackers", "pinterest")
BLOG_INDEX = "https://nerdit.in/blog"
DUE_AFTER = dt.timedelta(hours=24)


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


def plan(slug: str, posted: set[str], today: str, scheduled: bool = False) -> list[str]:
    steps = _load(_dir() / f"{slug}.json", {"steps": []})["steps"]
    daily = _load(_dir() / "_daily.json", {}).get(today, {})
    candidates = SCHEDULED_SITES if scheduled else SITES
    done = set(posted) | {s["site"] for s in steps if s["status"] == "posted"}
    waiting = {s["site"] for s in steps if s["status"] == "skipped" and s["day"] == today}
    full = {site for site in (candidates if scheduled else ONCE_A_DAY) if daily.get(site, 0) >= 1}
    waiting |= {s for s, status in _latest(steps).items() if status == "started"}
    left = PER_ARTICLE_PER_DAY - sum(1 for s in steps if s["status"] == "posted" and s["day"] == today)
    return [s for s in candidates if s not in done | waiting | full][:max(left, 0)]


def due_slugs(html: str, now: dt.datetime) -> list[str]:
    """Slugs live 24 h or more, newest first, from the blog index's JSON-LD `blogPost` list.

    shortcut: the index lists only the 30 newest articles, so older ones are never due; read Firestore if that matters.
    """
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
        if now - published >= DUE_AFTER:
            due.append((published, slug))
    return [slug for _, slug in sorted(due, reverse=True)]


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
    if status == "posted":
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
    r.add_argument("--today")
    a = ap.parse_args(argv)
    if a.cmd == "due":
        now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
        try:
            with urllib.request.urlopen(BLOG_INDEX, timeout=30) as r:
                html = r.read().decode("utf-8")
        except OSError as e:
            print(f"PROBLEM could not read {BLOG_INDEX}: {e}")
            return 1
        slugs = due_slugs(html, now)
        print("\n".join(slugs) if slugs else "nothing due")
        return 0
    today = a.today or dt.date.today().isoformat()
    if a.cmd == "report":
        print(report(today))
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
