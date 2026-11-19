"""The social pack, step by step (run from anywhere; paths are arguments):

  python build_pack.py plan  <workdir> --url COURSE_PAGE [--course-id ID] [--start YYYY-MM-DD] [--days 10] [--no-pad] [--force]
      -> <workdir>/social-pack/<name>-<start>/pack-plan.json   (the agent edits hooks, slides, captions)
  python build_pack.py pilot <packdir>   -> <packdir>/pilot/: the first Reel and the first carousel
  python build_pack.py build <packdir>   -> every item's media + pack.json, then the checks
  python build_pack.py check <packdir>   -> prints problems; exit 1 when there are any

Captions use {link} where the course link goes; build fills in each platform's UTM link.
Nothing here uploads or posts anything.
"""
import argparse
import json
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import cues
import draw
import packcheck
import reel
import slides
import source
import teach
from captions import fill_links
from dayplan import day_plan

IST = timezone(timedelta(hours=5, minutes=30))
ITEM_KEYS = ("id", "date", "time", "format", "platforms", "title", "media", "cover", "captions", "lessonId", "topic",
             "theme", "layout")


def _clip_title(src: dict, item: dict) -> str:
    return next((c["title"] for c in src["clips"] if c["key"] == item["clipKey"]), "")


def reel_hook(src: dict, item: dict) -> str:
    """The first of the topic's key ideas (or its title) that fits the Reel's two hook lines."""
    ideas = [s.get("keyIdea", "") for s in src["plan"]["scenes"]
             if s.get("lessonId") == item["lessonId"] and s.get("topic") == item["topic"]]
    for text in ideas + [_clip_title(src, item)]:
        if text and draw.fits(text, draw.HOOK_CHARS, draw.HOOK_LINES) and not draw.DEVANAGARI.search(text):
            return text
    return ""


def used_topics(workdir: Path, pack_id: str) -> set:
    """(lessonId, topic) pairs in the course's other packs (pack.json, else pack-plan.json)."""
    used = set()
    for d in sorted((Path(workdir) / "social-pack").glob("*/")):
        if d.name == pack_id:
            continue
        f = d / "pack.json" if (d / "pack.json").is_file() else d / "pack-plan.json"
        if f.is_file():
            used |= {(i.get("lessonId"), i.get("topic")) for i in json.loads(f.read_text(encoding="utf-8")).get("items", [])}
    return used


def _sources(slides: list[dict]) -> set:
    return {(x["source"]["lessonId"], x["source"]["kind"], x["source"]["index"]) for x in slides if x.get("source")}


def add_teaching(src: dict, items: list[dict], used: set) -> None:
    """Teaching carousels (else the key-idea carousel), cheat-sheet Stories on a lesson's first day, and
    Wrong vs right (else cheat sheet) LinkedIn cards. Items are in posting order."""
    last, cheat_done, story_seen = None, set(), set()
    for it in items:
        if it["format"] == "carousel":
            tc = teach.teaching_carousel(src, it, used, last)
            it["slides"] = tc["slides"] if tc else slides.default_slides(src, it)
            if tc:
                last = tc["format"]
                used |= _sources(tc["slides"])
        elif it["format"] == "story" and it["lessonId"] not in story_seen:
            story_seen.add(it["lessonId"])
            card = teach.story_card(src, it, True, used)
            if card:
                it["card"] = card
                used |= _sources([card])
                cheat_done.add(it["lessonId"])
    for it in items:
        if it["format"] == "feed":
            card = teach.feed_card(src, it, used, it["lessonId"] in cheat_done)
            if card:
                it["card"] = card
                used |= _sources([card])
                if card["kind"] == "cheat":
                    cheat_done.add(it["lessonId"])


def plan_pack(workdir: Path, start: date, days: int, url: str, course_id: str | None = None, pad: bool = True) -> dict:
    """The draft pack. `url` is the live course page; `course_id` the live course's id when known (the admin
    import gives a course a new id, so the JSON's id is only a fallback; the server also finds it by URL)."""
    src = source.load_source(workdir)
    pack_id = f"{src['name']}-{start.isoformat()}"
    skip = used_topics(workdir, pack_id)
    if skip:
        print(f"skipping {len(skip)} topic(s) used by earlier packs")
    items = day_plan(src, start, days, skip)
    for it in items:
        it["title"] = _clip_title(src, it)
        if it["format"] == "reel":
            it["hook"] = reel_hook(src, it)
        it["captions"] = {p: "" for p in it["platforms"]}
    add_teaching(src, items, teach.used_blocks(workdir, pack_id))
    n_days = len({it["date"] for it in items})
    return {"version": 1, "packId": pack_id, "courseId": course_id or src["course"]["id"],
            "courseUrl": url, "start": start.isoformat(), "days": n_days, "pad": pad,
            "items": items}


def pilot_items(items: list[dict]) -> list[dict]:
    first = lambda fmt: next((i for i in items if i["format"] == fmt), None)  # noqa: E731
    return [i for i in (first("reel"), first("carousel")) if i]


def render_items(src: dict, plan: dict, items: list[dict], out_dir: Path) -> list[dict]:
    """Draw every item's media into out_dir; return the manifest items."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tl = cues.checked_timeline(src) if any(i["format"] == "reel" for i in items) else None
    made = []
    for it in items:
        print(f"  {it['id']} ({it['format']})", flush=True)
        entry = dict(it)
        if it["format"] == "reel":
            mp4, cover = reel.make_reel(src, it, it["hook"], out_dir, tl, pad=plan.get("pad", True))
            entry["media"], entry["cover"] = [mp4.name], cover.name
        elif it["format"] == "carousel":
            entry["media"] = [p.name for p in slides.make_carousel(src, it, it["slides"], out_dir)]
        else:
            entry["media"] = [slides.make_card(src, it, 1920 if it["format"] == "story" else 1350, out_dir).name]
        entry["captions"] = {p: fill_links((it.get("captions") or {}).get(p, ""), plan["courseUrl"], p, it)
                             for p in it["platforms"]}
        made.append({k: entry[k] for k in ITEM_KEYS if k in entry})
    shutil.rmtree(out_dir / "_work", ignore_errors=True)
    return made


def _read_plan(packdir: Path) -> dict:
    path = packdir / "pack-plan.json"
    if not path.is_file():
        raise SystemExit(f"no pack-plan.json in {packdir}; run plan first")
    return json.loads(path.read_text(encoding="utf-8"))


def _report(problems: list[str]) -> int:
    for p in problems:
        print("PROBLEM", p)
    print(f"{len(problems)} problem(s)" if problems else "checks passed")
    return 1 if problems else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NERDIT social pack")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_plan = sub.add_parser("plan")
    p_plan.add_argument("workdir", type=Path)
    p_plan.add_argument("--start", type=date.fromisoformat,
                        default=(datetime.now(IST) + timedelta(days=1)).date())
    p_plan.add_argument("--days", type=int, default=10)
    p_plan.add_argument("--url", required=True, help="the live course page, e.g. https://nerdit.in/course/<slug>/preview")
    p_plan.add_argument("--course-id", help="the live course's id (admin); else the JSON's id")
    p_plan.add_argument("--force", action="store_true", help="replace an existing pack-plan.json")
    p_plan.add_argument("--no-pad", action="store_true", help="Reels carry the narration only, no background pad")
    for name in ("pilot", "build", "check"):
        sub.add_parser(name).add_argument("packdir", type=Path)
    a = ap.parse_args(argv)

    if a.cmd == "plan":
        plan = plan_pack(a.workdir, a.start, a.days, a.url, a.course_id, pad=not a.no_pad)
        packdir = Path(a.workdir).resolve() / "social-pack" / plan["packId"]
        target = packdir / "pack-plan.json"
        if target.exists() and not a.force:
            print(f"{target} exists and may hold your edits; pass --force to replace it")
            return 1
        packdir.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {target}: {len(plan['items'])} items over {plan['days']} days")
        return 0

    packdir = Path(a.packdir).resolve()
    if a.cmd == "check":
        return _report(packcheck.check(packdir))
    plan = _read_plan(packdir)
    src = source.load_source(packdir.parents[1])
    texts = packcheck.lesson_texts(packdir.parents[1])
    todo = pilot_items(plan["items"]) if a.cmd == "pilot" else plan["items"]
    written = packcheck.plan_text_errors(todo, texts)      # before drawing: cheap to fix in pack-plan.json
    if written:
        return _report(written)
    if a.cmd == "pilot":
        out = packdir / "pilot"
        items = render_items(src, plan, todo, out)
        print(f"pilot written to {out}")
        return _report(packcheck.check_items({**plan, "items": items}, out, texts))
    items = render_items(src, plan, plan["items"], packdir)
    manifest = {k: plan[k] for k in ("version", "packId", "courseId", "courseUrl", "start", "days")}
    manifest["items"] = items
    (packdir / "pack.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {packdir / 'pack.json'}")
    return _report(packcheck.check_items(manifest, packdir, texts))


if __name__ == "__main__":
    sys.exit(main())
