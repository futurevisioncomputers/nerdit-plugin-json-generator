"""Compact lesson outline for planning images.

Usage: python extract_outline.py --course <course.json> [--out <outline.json>]
       python extract_outline.py --course <course.json> --full <lesson-id>:<section-number>

Prints one line per lesson and section, with figure captions and the top-level paragraph
anchors the planner copies into plan.json. Reading this instead of full lesson HTML keeps
planning cheap. --full prints one section's whole text, the lesson fixture and the section
fingerprint, which a v2 visual brief is written from.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lessonhtml import (FIG_CAPTION, PRACTICE, SVG, fixture_text, img_sources, remove_visual_blocks,
                        section_fingerprint, section_text, sections, text, top_paragraphs)

MAX_ANCHORS = 6


def load_hints(workdir: str | None) -> dict[str, dict[int, dict]]:
    """`visuals` lists from <workdir>/<id>.concepts.json, by lesson id and section number."""
    if not workdir:
        return {}
    hints: dict[str, dict[int, dict]] = {}
    for p in Path(workdir).glob("*.concepts.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        hints[p.name[: -len(".concepts.json")]] = {
            int(v["section"]): v for v in data.get("visuals", []) if "section" in v}
    return hints


def outline(course: dict, hints: dict | None = None) -> list[dict]:
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
                "hint": (hints or {}).get(lesson["id"], {}).get(sec.number),
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
            h = s.get("hint")
            if h:
                lines.append(f"     hint: {h.get('visual')}"
                             + (f" · image: {h['illustration']}" if h.get("illustration") else ""))
    return "\n".join(lines)


def full_section(course: dict, lesson_id: str, number: int) -> str:
    lesson = next((l for l in course.get("lessons", []) if l["id"] == lesson_id), None)
    if lesson is None:
        raise KeyError(f"unknown lesson {lesson_id}")
    content = remove_visual_blocks(lesson.get("content") or "")
    sec = next((s for s in sections(content) if s.number == number), None)
    if sec is None:
        raise KeyError(f"lesson {lesson_id} has no section {number}")
    out = [f"COURSE {course.get('title', '')}",
           f"LESSON {lesson_id} {lesson.get('title', '')}",
           f"SECTION {sec.number} {sec.heading}",
           f"FINGERPRINT {section_fingerprint(content, sec.number, sec.heading)}",
           "---- SECTION TEXT ----", section_text(content, sec)]
    fixture = fixture_text(content)
    if fixture:
        out += ["---- FIXTURE ----", fixture]
    return "\n".join(out)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--out")
    ap.add_argument("--full", help="<lesson-id>:<section-number>")
    ap.add_argument("--hints", help="<workdir> holding <id>.concepts.json with visuals")
    args = ap.parse_args()
    with open(args.course, encoding="utf-8") as f:
        course = json.load(f)
    if args.full:
        lesson_id, _, number = args.full.rpartition(":")
        try:
            print(full_section(course, lesson_id, int(number)))
        except (KeyError, ValueError) as e:
            print(f"error: {e}")
            return 2
        return 0
    lessons = outline(course, load_hints(args.hints))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(lessons, f, ensure_ascii=False, indent=2)
    print(render(lessons))
    bare = sum(1 for l in lessons if not l["svgCount"] and not l["images"])
    print(f"\n{len(lessons)} lessons · {bare} with no visual")
    return 0


if __name__ == "__main__":
    sys.exit(main())
