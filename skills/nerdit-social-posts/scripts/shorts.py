"""YouTube Shorts kit (owner 2026-11-20): the pack's Reels, ready titles and descriptions, and the schedule.

Uploads through the YouTube API stay private until the API project passes YouTube's audit, so for now the
owner uploads this kit in YouTube Studio. See docs/superpowers/specs/2026-11-20-youtube-shorts-kit-design.md.
Each Reel's `captions.youtube` holds the title on the first line, then the description with `{link}`.
"""
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

from captions import HASHTAG, caption_errors, fill_links


def _reels(plan: dict) -> list[dict]:
    return [it for it in plan["items"] if it["format"] == "reel"]


def shorts_errors(plan: dict, packdir: Path, texts: dict) -> list[str]:
    """Problems that stop the kit: a Reel without a YouTube caption, a caption that breaks a rule, a missing Reel file."""
    out = []
    for it in _reels(plan):
        text = (it.get("captions") or {}).get("youtube", "")
        if not text.strip():
            out.append(f"{it['id']}: write captions.youtube (title line, blank line, description)")
        else:
            filled = fill_links(text, plan["courseUrl"], "youtube", it)
            lesson = texts.get(it.get("lessonId", ""), "")
            out += [f"{it['id']}: {e}" for e in caption_errors("youtube", "reel", filled, lesson, it, plan["courseUrl"])]
        if not (Path(packdir) / f"{it['id']}.mp4").is_file():
            out.append(f"{it['id']}: {it['id']}.mp4 is missing; run build first")
    return out


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


def write_kit(plan: dict, packdir: Path, start: str | None = None, course: str | None = None,
              texts: dict | None = None) -> Path:
    """Write <packdir>/youtube/: a copy of each Reel and SHORTS.md. `start` is the Day 1 the admin showed after
    import (packs queue, so plan dates move); every date moves by the same number of days. Returns SHORTS.md."""
    packdir = Path(packdir)
    errors = shorts_errors(plan, packdir, texts or {})
    if errors:
        raise SystemExit("\n".join(errors))
    first = date.fromisoformat(start or plan["start"])
    shift = timedelta(days=(first - date.fromisoformat(plan["start"])).days)
    course = course or plan.get("course") or plan["packId"]
    out = packdir / "youtube"
    out.mkdir(exist_ok=True)
    lines = [f"# YouTube Shorts: {course}", "",
             "Upload in YouTube Studio: Create, Upload videos (up to 15 at once). For each Short below, paste the title",
             "and the description, then choose Visibility, Schedule, at the date and time shown (IST).", "",
             f"Settings for every Short: Audience: No, it's not made for kids. Category: Education. Playlist: {course}.", "",
             f"Day 1 = {first.isoformat()}. If the admin showed another Day 1 after import, run:",
             f"`python build_pack.py shorts \"{packdir}\" --start <that day>`", ""]
    for it in _reels(plan):
        moved = {**it, "date": (date.fromisoformat(it["date"]) + shift).isoformat()}
        text = it["captions"]["youtube"]
        title, _, rest = text.partition("\n")
        title = title.strip()
        target = out / f"{it['id']}-{_slug(title)}.mp4"
        source = packdir / f"{it['id']}.mp4"
        if not target.is_file() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)
        day = (date.fromisoformat(moved["date"]) - first).days + 1
        tags = ", ".join(dict.fromkeys(t[1:] for t in HASHTAG.findall(text)))
        lines += [f"## Day {day} · {moved['date']} {it['time']} IST", "", f"File: `{target.name}`", "",
                  f"Title: {title}", "", "Description:", "", "```",
                  fill_links(rest.strip(), plan["courseUrl"], "youtube", moved), "```", "", f"Tags: {tags}", ""]
    md = out / "SHORTS.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    return md
