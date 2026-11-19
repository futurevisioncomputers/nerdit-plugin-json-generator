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
    """Every number in a hook or a written slide line must be in the lesson (lesson-made slides are not checked)."""
    out = []
    for it in items:
        lesson = texts.get(it.get("lessonId", ""), "")
        if it.get("hook"):
            out += [f"{it['id']}: hook: {n} is not in the lesson" for n in unknown_numbers(it["hook"], lesson)]
        for i, s in enumerate(it.get("slides") or [], 1):
            for field in ("hook", "text"):
                if s.get("kind") in ("cover", "idea", "cta") and s.get(field):
                    out += [f"{it['id']}: slide {i}: {n} is not in the lesson" for n in unknown_numbers(s[field], lesson)]
    return out


def _norm(text) -> str:
    return " ".join(str(text).split())


def _block(blocks: dict, ref: dict):
    lesson = blocks.get(ref.get("lessonId"), {})
    if ref.get("kind") == "cheatsheet":
        return lesson.get("cheatsheet")
    for topic in lesson.get("topics", {}).values():
        for b in topic.get(ref.get("kind"), []):
            if b.get("index") == ref.get("index"):
                return b
    return None


def _corpus(block) -> str:
    """Every string in a block, joined: what a drawn line may be taken from."""
    if isinstance(block, dict):
        return " ".join(_corpus(v) for k, v in block.items() if k not in ("kind", "index", "reads", "lang"))
    if isinstance(block, list):
        return " ".join(_corpus(v) for v in block)
    return _norm(block) if isinstance(block, str) else ""


def _drawn(s: dict) -> list[str]:
    """The lesson words a slide or card draws (cover, closing slide and generated captions excluded)."""
    kind = s.get("kind")
    fields = {"predict-q": ("question", "code"), "predict-a": ("output", "explanation"), "wrong": ("head", "code", "reason"),
              "right": ("head", "code", "reason"), "code": ("code",), "output": ("output",)}.get(kind, ())
    texts = [s.get(f, "") for f in fields]
    if kind in ("data", "cheat"):
        texts += list(s.get("headers", [])) + [c for r in s.get("rows", []) for c in r]
        if kind == "data" and s.get("source", {}).get("kind") == "spot":
            texts.append(s.get("caption", ""))
    if kind == "compare":
        texts += [s[side].get(f, "") for side in ("bad", "good") for f in ("head", "code", "reason")]
    return [t for t in texts if _norm(t)]


def source_errors(items: list[dict], blocks_by_lesson: dict, workdir: Path | None = None) -> list[str]:
    """Every table, code and output a post draws must be word for word in its source block (or CSV)."""
    import teach
    out = []
    for it in items:
        parts = [(f"slide {n}", s) for n, s in enumerate(it.get("slides") or [], 1)]
        if it.get("card"):
            parts.append(("card", it["card"]))
        for where, s in parts:
            ref = s.get("source")
            if not ref:
                continue
            if ref.get("kind") == "csv":
                head = teach.csv_head(Path(workdir), ref["index"]) if workdir else None
                corpus = _corpus(list(head)) if head else ""
            else:
                corpus = _corpus(_block(blocks_by_lesson, ref))
            if not corpus or any(_norm(t) not in corpus for t in _drawn(s)):
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
