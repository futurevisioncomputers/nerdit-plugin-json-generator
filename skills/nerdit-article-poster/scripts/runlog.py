"""Which sites to post an article to today, and a log of every posting step.

    python runlog.py plan --slug <slug> --posted <site,site,...> [--today YYYY-MM-DD]
    python runlog.py mark --slug <slug> --site <site> --status posted|failed|skipped [--url U] [--error E] [--today D]

`--posted` is the article's own record (the Articles page: sites with a saved link). The log adds what
happened in runs: a site logged as posted is never planned again, even when its link was not saved
(no double posts); a failed site is retried; a skipped site waits until the next day. Pacing: at most
6 sites per article per run day, and Quora/Reddit (`quora`) and Pinterest at most once a day across
all articles. State: ~/.nerdit-social/article-runs/<slug>.json and _daily.json (NERDIT_SOCIAL_HOME overrides).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

SITES = ("medium", "hashnode", "hackernoon", "linkedin", "substack", "wordpress", "blogger", "tumblr", "vocal",
         "hackernews", "dailydev", "indiehackers", "pinterest", "quora")
STATUSES = ("posted", "failed", "skipped")
PER_ARTICLE_PER_DAY = 6
ONCE_A_DAY = ("quora", "pinterest")


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


def plan(slug: str, posted: set[str], today: str) -> list[str]:
    steps = _load(_dir() / f"{slug}.json", {"steps": []})["steps"]
    daily = _load(_dir() / "_daily.json", {}).get(today, {})
    done = set(posted) | {s["site"] for s in steps if s["status"] == "posted"}
    waiting = {s["site"] for s in steps if s["status"] == "skipped" and s["day"] == today}
    full = {site for site in ONCE_A_DAY if daily.get(site, 0) >= 1}
    left = PER_ARTICLE_PER_DAY - sum(1 for s in steps if s["status"] == "posted" and s["day"] == today)
    return [s for s in SITES if s not in done | waiting | full][:max(left, 0)]


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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--slug", required=True); p.add_argument("--posted", default=""); p.add_argument("--today")
    m = sub.add_parser("mark")
    m.add_argument("--slug", required=True); m.add_argument("--site", required=True); m.add_argument("--status", required=True)
    m.add_argument("--url", default=""); m.add_argument("--error", default=""); m.add_argument("--today")
    a = ap.parse_args(argv)
    today = a.today or dt.date.today().isoformat()
    if a.cmd == "plan":
        sites = plan(a.slug, {s.strip() for s in a.posted.split(",") if s.strip()}, today)
        print("\n".join(sites) if sites else "nothing to post today")
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
