"""Which teaching format each post gets, built from the topic's own lesson blocks.

Carousels cycle Guess the output -> Wrong vs right -> Data -> code -> result, using the first block of
that kind the course's packs have not used yet. The Story card on a lesson's first pack day is the
lesson's cheat sheet; the LinkedIn feed card is Wrong vs right, else the cheat sheet if not posted
yet. Every content slide keeps a `source` so the checker can find its words in the lesson.
"""
import csv
import json
import re
from pathlib import Path

import draw
from blocks import lesson_blocks, plain

FORMAT_CYCLE = ("predict", "compare", "run")
HOOKS = {"predict": "Guess the output", "compare": "Wrong vs right", "run": "See it run"}
CSV_DIRS = ("", "lessons", "pack/files", "work/world")
TOPIC_H2 = re.compile(r"<h2[^>]*>\s*(\d+)\s*[—–-].*?</h2>", re.S)
EMPTY = {"run": [], "predict": [], "compare": [], "spot": []}
CHEAT_EXAMPLE_CHARS = 56   # a cheat-sheet example wider than this would be cut at 26 px


def _blocks(src: dict, lesson_id: str) -> dict:
    cache = src.setdefault("_blocks", {})
    if lesson_id not in cache:
        cache[lesson_id] = lesson_blocks(src["lessons"].get(lesson_id, {}).get("content", ""))
    return cache[lesson_id]


def _topic_text(src: dict, lesson_id: str, topic: int) -> str:
    html = src["lessons"].get(lesson_id, {}).get("content", "")
    for m in TOPIC_H2.finditer(html):
        if int(m.group(1)) == topic:
            nxt = re.compile(r"<h2[\s>]").search(html, m.end())     # the section ends at the next heading of any kind
            return plain(html[m.start():nxt.start() if nxt else len(html)]).lower()
    return ""


def _ref(src_item: dict, kind: str, index) -> dict:
    return {"lessonId": src_item["lessonId"], "kind": kind, "index": index}


def _workdir(src: dict) -> Path:
    return Path(src["course_path"]).parent


def used_blocks(workdir: Path, pack_id: str) -> set[tuple[str, str, int]]:
    """(lessonId, kind, index) of every block another pack of this course already uses."""
    used = set()
    for plan in sorted((Path(workdir) / "social-pack").glob("*/pack-plan.json")):
        if plan.parent.name == pack_id:
            continue
        for item in json.loads(plan.read_text(encoding="utf-8")).get("items", []):
            for s in list(item.get("slides") or []) + ([item["card"]] if item.get("card") else []):
                if s.get("source"):
                    used.add((s["source"]["lessonId"], s["source"]["kind"], s["source"]["index"]))
    return used


def csv_head(workdir: Path, name: str, rows: int = 5) -> tuple[list, list] | None:
    for sub in CSV_DIRS:
        path = Path(workdir) / sub / name
        if path.is_file():
            with path.open(encoding="utf-8-sig", newline="") as f:
                table = list(csv.reader(f))
            return (table[0], table[1:rows + 1]) if table else None
    return None


def _drawable(slides: list[dict]) -> bool:
    try:
        for i, s in enumerate(slides, 1):
            draw.slide_html(s, "navy", i, len(slides))
        return True
    except draw.DrawError:
        return False


def _content(kind: str, block: dict, src: dict, item: dict, topic: dict) -> list[dict] | None:
    ref = _ref(item, kind, block["index"])
    if kind == "predict":
        if not block["code"] or not block["output"]:
            return None
        return [{"kind": "predict-q", "question": block["question"], "code": block["code"], "lang": block["lang"], "source": ref},
                {"kind": "predict-a", "output": block["output"], "outTag": block.get("outTag") or "Output",
                 "explanation": block["explanation"], "source": ref}]
    if kind == "compare":
        if not block["bad"]["code"] or not block["good"]["code"]:
            return None
        return [{"kind": "wrong", **block["bad"], "source": ref}, {"kind": "right", **block["good"], "source": ref}]
    if not block["code"] or not block["output"]:
        return None
    reads = block["reads"]
    spot = next((sp for sp in topic["spot"] if any(name in sp["caption"] for name in reads)), None)
    if spot:     # the lesson's own "meet the data" table, when it describes the file this code reads
        data = {"kind": "data", "headers": spot["headers"], "rows": spot["rows"], "caption": spot["caption"], "sample": True,
                "source": _ref(item, "spot", spot["index"])}
    else:
        head = next((csv_head(_workdir(src), name) for name in block["reads"] if csv_head(_workdir(src), name)), None)
        if not head:
            return None
        name = next(n for n in block["reads"] if csv_head(_workdir(src), n))
        data = {"kind": "data", "headers": head[0], "rows": head[1], "caption": f"First rows of {name}", "sample": True,
                "source": _ref(item, "csv", name)}
    return [data, {"kind": "code", "code": block["code"], "lang": block["lang"], "source": ref},
            {"kind": "output", "output": block["output"], "outTag": block["outTag"] or "Output",
             "sample": bool(block["reads"]), "source": ref}]


def teaching_carousel(src: dict, item: dict, used: set, last_format: str | None) -> dict | None:
    """The next format in the cycle this topic can show with an unused block; None keeps the key-idea carousel."""
    topic = _blocks(src, item["lessonId"])["topics"].get(item["topic"], EMPTY)
    start = (FORMAT_CYCLE.index(last_format) + 1) % len(FORMAT_CYCLE) if last_format in FORMAT_CYCLE else 0
    for fmt in FORMAT_CYCLE[start:] + FORMAT_CYCLE[:start]:
        for block in topic[fmt]:
            if (item["lessonId"], fmt, block["index"]) in used:
                continue
            content = _content(fmt, block, src, item, topic)
            if not content:
                continue
            slides = [{"kind": "cover", "hook": HOOKS[fmt], "course": src["course"]["title"]}, *content,
                      {"kind": "cta", "text": "Full lesson free at nerdit.in"}]
            if _drawable(slides):
                return {"format": fmt, "slides": slides}
    return None


def _cheat(src: dict, item: dict, height: int, used: set) -> dict | None:
    cheat = _blocks(src, item["lessonId"])["cheatsheet"]
    if not cheat or not cheat["rows"] or (item["lessonId"], "cheatsheet", 0) in used:   # once per course
        return None
    text = _topic_text(src, item["lessonId"], item["topic"])
    # Only rows that fit whole at the floor sizes (never cut mid-value); a Story holds 6, a feed card 4.
    fitting = [r for r in cheat["rows"] if r and len(r) >= 1 and draw.fits(r[0], 40, 1)
               and (len(r) < 2 or draw.fits(r[1], 52, 2)) and (len(r) < 3 or len(r[2]) <= CHEAT_EXAMPLE_CHARS)]
    first = [r for r in fitting if r[0].lower() in text]
    rows = (first + [r for r in fitting if r not in first])[:6 if height == draw.REEL_H else 4]
    if not rows:
        return None
    card = {"kind": "cheat", "headers": cheat["headers"], "rows": rows, "source": _ref(item, "cheatsheet", 0)}
    try:
        draw.cheat_html(card, "navy", height)
    except draw.DrawError:
        return None
    return card


def story_card(src: dict, item: dict, first_day_of_lesson: bool, used: set = frozenset()) -> dict | None:
    return _cheat(src, item, draw.REEL_H, used) if first_day_of_lesson else None


def feed_card(src: dict, item: dict, used: set, cheat_posted: bool) -> dict | None:
    topic = _blocks(src, item["lessonId"])["topics"].get(item["topic"], EMPTY)
    for block in topic["compare"]:
        if (item["lessonId"], "compare", block["index"]) in used or not block["bad"]["code"] or not block["good"]["code"]:
            continue
        card = {"kind": "compare", "bad": block["bad"], "good": block["good"], "source": _ref(item, "compare", block["index"])}
        try:
            draw.compare_card_html(card, "navy", draw.SLIDE_H)
            return card
        except draw.DrawError:
            continue
    return None if cheat_posted else _cheat(src, item, draw.SLIDE_H, used)
