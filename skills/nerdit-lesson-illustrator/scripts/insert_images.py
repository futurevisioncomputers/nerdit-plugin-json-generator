"""Insert passed images into lessons and build the with-images course JSON.

Usage: python insert_images.py --course <course.json> --images-dir <dir> [--no-optimise] [--contract v10|v9]
"""
from __future__ import annotations

import html
import re

from lessonhtml import AnchorNotFound, locate

MARKER = re.compile(
    r'\n?<div class="nerdit-figure nerdit-illustration" data-nerdit-img="[^"]+">'
    r'.*?<div class="nerdit-figure-caption">.*?</div>\s*</div>', re.S)


def block(slot: dict) -> str:
    alt = html.escape(slot["alt"], quote=True)
    caption = html.escape(slot["caption"], quote=False)
    return (f'\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="{slot["id"]}">\n'
            f'  <img src="{slot["outputFile"]}" alt="{alt}" width="{slot["width"]}" height="{slot["height"]}"'
            ' loading="lazy" decoding="async" style="display:block;width:100%;height:auto">\n'
            f'  <div class="nerdit-figure-caption">{caption}</div>\n</div>')


def strip_inserted(content: str) -> str:
    return MARKER.sub("", content)


def insert_lessons(course: dict, m: dict) -> list[str]:
    errors = []
    by_lesson: dict[str, list[dict]] = {}
    for s in m["images"]:
        if s["status"] in ("passed", "inserted"):
            by_lesson.setdefault(s["lessonId"], []).append(s)
    known = set()
    for lesson in course.get("lessons", []):
        known.add(lesson["id"])
        content = strip_inserted(lesson.get("content") or "")
        placed = []
        for s in by_lesson.get(lesson["id"], []):
            try:
                off = locate(content, s["section"]["number"], s["section"]["heading"],
                             s["position"], s["anchor"] or None)
            except AnchorNotFound as e:
                errors.append(f"{s['id']}: {e}; re-plan with --replan {s['lessonId']}")
                s["status"] = "passed"
                continue
            placed.append((off, s))
        for off, s in sorted(placed, key=lambda p: (p[0], p[1]["id"]), reverse=True):
            content = content[:off] + block(s) + content[off:]
            s["status"] = "inserted"
        lesson["content"] = content
    for lid, slots in by_lesson.items():
        if lid not in known:
            errors += [f"{s['id']}: lesson {lid} is not in this course" for s in slots]
    return errors
