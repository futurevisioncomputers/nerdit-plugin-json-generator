"""Check a social pack before it is imported: files, sizes, durations, dates, ids, platforms, captions.

The admin and the server check the manifest again; this catches problems on the PC, where they are
cheap to fix. A pack folder sits at <workdir>/social-pack/<packId>/.
"""
import json
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

import source  # noqa: F401  puts story-video's scripts on sys.path
import storyplan
from captions import caption_errors, unknown_numbers
from dayplan import ALLOWED_PLATFORMS
from hookscore import hook_errors  # social-craft, on sys.path through captions
from humanize import slop_errors

SIZES = {"story": (1080, 1920), "feed": (1080, 1350), "carousel": (1080, 1350), "cover": (1080, 1920)}
MAX_SLIDES, MIN_SLIDES = 10, 2
IMAGE_EXT = (".jpg", ".jpeg", ".png")


def lesson_texts(workdir: Path) -> dict:
    return storyplan.lesson_texts(source._course_file(Path(workdir)))


def check(packdir: Path) -> list[str]:
    packdir = Path(packdir)
    path = packdir / "pack.json"
    if not path.is_file():
        return [f"no pack.json in {packdir}; run build first"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return check_items(manifest, packdir, lesson_texts(packdir.parents[1]))


def check_items(manifest: dict, packdir: Path, texts: dict) -> list[str]:
    """Problems with manifest["items"], grouped: counts, ids, dates, platforms, files, captions."""
    items = manifest.get("items") or []
    counts, ids, dates, platforms, files, caps = [], [], [], [], [], []
    start = date.fromisoformat(manifest["start"])
    last = start + timedelta(days=int(manifest.get("days") or 1) - 1)
    seen, dup = set(), []
    for it in items:
        iid, fmt, media = it.get("id", "?"), it.get("format"), list(it.get("media") or [])
        if iid in seen and iid not in dup:
            dup.append(iid)
        seen.add(iid)
        if fmt == "carousel":
            if len(media) > MAX_SLIDES:
                counts.append(f"{iid}: {len(media)} slides; at most {MAX_SLIDES}")
            elif len(media) < MIN_SLIDES:
                counts.append(f"{iid}: {len(media)} slide(s); at least {MIN_SLIDES}")
        elif fmt in ("reel", "story", "feed"):
            if len(media) != 1:
                counts.append(f"{iid}: a {fmt} takes 1 file, got {len(media)}")
        else:
            counts.append(f"{iid}: unknown format {fmt!r}")
            continue
        try:
            if not start <= date.fromisoformat(it.get("date", "")) <= last:
                dates.append(f"{iid}: {it.get('date')} is outside the pack dates")
        except ValueError:
            dates.append(f"{iid}: bad date {it.get('date')!r}")
        for p in it.get("platforms") or []:
            if p not in ALLOWED_PLATFORMS[fmt]:
                platforms.append(f"{iid}: a {fmt} cannot go to {p}")
        files += _file_problems(it, packdir)
        lesson = texts.get(it.get("lessonId", ""), "")
        for p in it.get("platforms") or []:
            text = (it.get("captions") or {}).get(p, "")
            if "{link}" in text:
                caps.append(f"{iid}: {p} caption still has {{link}}")
            else:
                caps += [f"{iid}: {e}" for e in caption_errors(p, fmt, text, lesson, it, manifest.get("courseUrl", ""))]
    ids = [f"{i}: id used twice" for i in dup]
    return counts + ids + dates + platforms + files + caps


def plan_text_errors(items: list[dict], texts: dict) -> list[str]:
    """Every number in a hook or a written slide line must be in the lesson (lesson-made slides are not checked);
    Reel hooks and carousel covers must score at least 50 (social-craft hookscore); no stock words or dashes."""
    out = []
    for it in items:
        lesson = texts.get(it.get("lessonId", ""), "")
        if it.get("hook"):
            out += [f"{it['id']}: hook: {n} is not in the lesson" for n in unknown_numbers(it["hook"], lesson)]
            out += hook_errors(it["hook"], it["id"]) + slop_errors(it["hook"], f"{it['id']}: hook")
        for i, s in enumerate(it.get("slides") or [], 1):
            if i == 1 and s.get("kind") == "cover" and s.get("hook"):
                out += hook_errors(s["hook"], f"{it['id']}: cover")
            for field in ("hook", "text"):
                if s.get("kind") in ("cover", "idea", "cta") and s.get(field):
                    out += [f"{it['id']}: slide {i}: {n} is not in the lesson" for n in unknown_numbers(s[field], lesson)]
                    out += slop_errors(s[field], f"{it['id']}: slide {i}")
    return out


TEACH_SLIDES = {"predict-q", "predict-a", "wrong", "right", "data", "code", "output"}
SIDE_FIELDS = ("head", "code", "reason")


def _block(blocks: dict, ref: dict):
    lesson = blocks.get(ref.get("lessonId"), {})
    if ref.get("kind") == "cheatsheet":
        return lesson.get("cheatsheet")
    for topic in lesson.get("topics", {}).values():
        for b in topic.get(ref.get("kind"), []):
            if b.get("index") == ref.get("index"):
                return b
    return None


def _matches(s: dict, block, csv_head) -> bool:
    """Each drawn field equals its source field exactly (newlines and indentation kept)."""
    kind = s.get("kind")
    if block is None:
        return False
    if kind == "predict-q":
        return s.get("question", "") == block["question"] and s.get("code") == block["code"]
    if kind == "predict-a":
        return s.get("output") == block["output"] and s.get("explanation", "") == block["explanation"]
    if kind in ("wrong", "right"):
        side = block["bad" if kind == "wrong" else "good"]
        return all(s.get(f, "") == side[f] for f in SIDE_FIELDS)
    if kind == "code":
        return s.get("code") == block["code"]
    if kind == "output":
        return s.get("output") == block["output"]
    if kind == "data":
        if s.get("source", {}).get("kind") == "csv":
            return csv_head is not None and [s.get("headers"), s.get("rows")] == [csv_head[0], csv_head[1]]
        return s.get("headers") == block["headers"] and s.get("rows") == block["rows"] and s.get("caption", "") == block["caption"]
    if kind == "cheat":
        return s.get("headers") == block["headers"] and all(r in block["rows"] for r in s.get("rows", []))
    if kind == "compare":
        return all(s[side].get(f, "") == block[side][f] for side in ("bad", "good") for f in SIDE_FIELDS)
    return False


def source_errors(items: list[dict], blocks_by_lesson: dict, workdir: Path | None = None) -> list[str]:
    """Every table, code and output a post draws must equal its source block (or CSV) field for field."""
    import teach
    out = []
    for it in items:
        parts = [(f"slide {n}", s) for n, s in enumerate(it.get("slides") or [], 1)]
        if it.get("card"):
            parts.append(("card", it["card"]))
        for where, s in parts:
            ref = s.get("source")
            teaching = s.get("kind") in TEACH_SLIDES or (where == "card" and s.get("kind") in ("cheat", "compare"))
            if not ref:
                if teaching:
                    out.append(f"{it['id']}: {where}: teaching {'card' if where == 'card' else 'slide'} has no source")
                continue
            if ref.get("kind") == "csv":
                head = teach.csv_head(Path(workdir), ref["index"]) if workdir else None
                ok = _matches(s, {}, head)
            else:
                ok = _matches(s, _block(blocks_by_lesson, ref), None)
            if not ok:
                out.append(f"{it['id']}: {where}: text not found in {ref.get('lessonId')} {ref.get('kind')} {ref.get('index')}")
    return out


def _file_problems(it: dict, packdir: Path) -> list[str]:
    import reel
    iid, fmt = it["id"], it["format"]
    out = []
    names = [(n, fmt) for n in it.get("media") or []] + ([(it["cover"], "cover")] if it.get("cover") else [])
    for name, kind in names:
        path = packdir / name
        if not path.is_file():
            out.append(f"{iid}: missing {name}")
            continue
        if kind == "reel":
            if path.suffix.lower() != ".mp4":
                out.append(f"{iid}: {name} must be .mp4")
                continue
            info = reel.probe(path)
            if info["size"] != (1080, 1920):
                out.append(f"{iid}: {name} is {info['size'][0]}x{info['size'][1]}; expected 1080x1920")
            if info["seconds"] > source.MAX_REEL:
                out.append(f"{iid}: {name} is {info['seconds']:.1f} s; at most {source.MAX_REEL:.0f}")
            if not info["audio"]:
                out.append(f"{iid}: {name} has no audio")
            continue
        if path.suffix.lower() not in IMAGE_EXT:
            out.append(f"{iid}: {name} must be JPEG or PNG")
            continue
        with Image.open(path) as im:
            size = im.size
        want = SIZES[kind]
        if size != want:
            out.append(f"{iid}: {name} is {size[0]}x{size[1]}; expected {want[0]}x{want[1]}")
    return out
