"""Compact lesson outline for planning images.

Usage: python extract_outline.py --course <course.json> [--out <outline.json>]

Prints one line per lesson and section, with figure captions and the top-level paragraph
anchors the planner copies into plan.json. Reading this instead of full lesson HTML keeps
planning cheap.
"""
from __future__ import annotations

import argparse
import json
import sys

from lessonhtml import FIG_CAPTION, PRACTICE, SVG, img_sources, sections, text, top_paragraphs

MAX_ANCHORS = 6


def outline(course: dict) -> list[dict]:
    lessons = []
    for lesson in course.get("lessons", []):
        content = lesson.get("content") or ""
        secs = []
        for sec in sections(content):
            span = content[sec.start:sec.end]
            secs.append({
                "number": sec.number,
                "heading": sec.heading,
                "teaching": sec.teaching,
                "hasPractice": bool(PRACTICE.search(span)),
                "figures": [text(c) for c in FIG_CAPTION.findall(span)],
                "anchors": [a for _, a in top_paragraphs(content, sec)][:MAX_ANCHORS],
            })
        lessons.append({
            "lessonId": lesson["id"],
            "title": lesson.get("title", ""),
            "svgCount": len(SVG.findall(content)),
            "images": img_sources(content),
            "sections": secs,
        })
    return lessons


def render(lessons: list[dict]) -> str:
    lines = []
    for i, l in enumerate(lessons, 1):
        visual = ("NO VISUAL" if not l["svgCount"] and not l["images"]
                  else f"svg={l['svgCount']} img={len(l['images'])}")
        lines.append(f"L{i:02d} {l['lessonId']} \"{l['title']}\" [{visual}]")
        for s in l["sections"]:
            tag = ("teach" if s["teaching"] else "skip") + (" practice" if s["hasPractice"] else "")
            lines.append(f"  §{s['number']} {s['heading']} [{tag}]")
            lines += [f"     fig: {c}" for c in s["figures"]]
            lines += [f"     ¶ {a}" for a in s["anchors"]]
    return "\n".join(lines)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    with open(args.course, encoding="utf-8") as f:
        lessons = outline(json.load(f))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(lessons, f, ensure_ascii=False, indent=2)
    print(render(lessons))
    bare = sum(1 for l in lessons if not l["svgCount"] and not l["images"])
    print(f"\n{len(lessons)} lessons · {bare} with no visual")
    return 0


if __name__ == "__main__":
    sys.exit(main())
