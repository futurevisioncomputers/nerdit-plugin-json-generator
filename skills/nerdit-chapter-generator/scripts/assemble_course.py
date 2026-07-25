#!/usr/bin/env python3
"""Assemble a NERDIT course-[chapter]_output.json from generated HTML files and a
small meta.json sidecar. Deterministic, Python-stdlib only, zero model tokens.

The orchestrator never holds lesson HTML in context: the lesson-writer agent writes
each <id>.html to disk, and this script reads those files and injects them into the
final course object. Question ids, the course id, and timestamps are all assigned
here so they are internally consistent by construction.

Usage:
  python assemble_course.py --chapter <slug> --input <input.json> \
      --html-dir <dir> --meta <meta.json> --out <output.json>
"""
import argparse
import datetime
import json
import os
import re
import sys
import time

ASSET_URL_BASE = "/assets/js"
ENGINE_FILES = ["nerdit-plot-runner.js", "nerdit-excel-engine.js"]

# Firestore hard-caps a single document at 1,048,576 bytes. The whole course object
# is stored in one doc, so keep it under this budget (margin left for Firestore's
# per-field sizing, which this JSON-byte proxy does not model exactly).
MAX_DOC_BYTES = 1_000_000

# Verbatim course-level defaults (SKILL Step 3a). This ordered list also defines the
# output field order between `id` and `duration`.
COURSE_DEFAULTS = [
    ("title", ""), ("description", ""), ("category", "Development"),
    ("difficulty", "Beginner"), ("image", ""), ("instructor", "Future vision"),
    ("rating", 0), ("students", 0), ("price", 0), ("certificatePrice", 999),
    ("hasExam", True), ("isDraft", True), ("isPrerequisiteOnly", False),
    ("isBestSeller", False), ("isTrending", False), ("isPopular", False),
    ("isTopRated", False), ("duration", "0h 0m"),
]


def iso_from_ms(ms):
    dt = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def detect_assets(html):
    return [f"{ASSET_URL_BASE}/{e}" for e in ENGINE_FILES if e in html]


# Concept-count floor from the v9 rulebook duration scale
# (3 concepts -> 10-14m, 4 -> 14-18m, 5+ -> 18-22m).
_CONCEPT_FLOOR = {0: 8, 1: 8, 2: 9, 3: 10, 4: 14, 5: 18}


def estimate_duration(html):
    """Deterministic lesson-duration estimate from the rendered HTML: reading time
    (~160 wpm) + ~1 min per code block, floored by concept-section count and clamped
    to 8-35m. Keeps duration a Python job so no model tokens are spent judging it."""
    if not html:
        return "8m"
    text = re.sub(r"<[^>]+>", " ", html)
    words = len(text.split())
    code_blocks = html.count("<pre")
    concepts = len(re.findall(r"<h2\b", html))
    minutes = round(words / 160) + code_blocks
    floor = _CONCEPT_FLOOR.get(concepts, 18 if concepts >= 5 else 8)
    return f"{max(min(max(minutes, floor), 35), 8)}m"


def with_ids(qs, kind, session, lesson_id, batch):
    out = []
    for i, q in enumerate(qs):
        out.append({
            "id": f"{kind}-{session}-{lesson_id}-q{i + 1}-{batch}",
            "text": q["text"], "options": q["options"],
            "correctOptionIndex": q["correctOptionIndex"],
        })
    return out


def build_course(chapter, input_lessons, meta, html_dir, now_ms=None):
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    session = batch = now_ms
    iso = iso_from_ms(now_ms)
    meta_by_id = {m["id"]: m for m in meta}

    lessons, assessment_qs, lesson_ids = [], [], []
    for src in input_lessons:
        lid = src["id"]
        m = meta_by_id.get(lid, {})
        content = ""
        html_path = os.path.join(html_dir, lid + ".html")
        if os.path.exists(html_path):
            with open(html_path, encoding="utf-8") as f:
                content = f.read().strip()
        lesson = {
            "id": lid, "title": src["title"], "content": content,
            "duration": m.get("duration") or estimate_duration(content),
            "questions": with_ids(m.get("lessonQuestions", []), "lesson", session, lid, batch),
        }
        assets = detect_assets(content)
        if assets:
            lesson["assets"] = assets
        lessons.append(lesson)
        assessment_qs += with_ids(m.get("assessmentQuestions", []), "assessment", session, lid, batch)
        lesson_ids.append(lid)

    course = {"id": f"course-{chapter}-{now_ms}"}
    for k, v in COURSE_DEFAULTS:
        course[k] = v
    course["createdAt"] = iso
    course["updatedAt"] = iso
    course["prerequisiteLessons"] = None
    course["assessment"] = {"questions": assessment_qs, "passingScore": 70, "examQuestionCount": 20}
    course["finalAssignment"] = None
    course["lessons"] = lessons
    course["lessonIds"] = lesson_ids
    return course


def _json_bytes(obj):
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def doc_size_report(course):
    """Estimate the Firestore document size of the whole course object (stored as one
    doc). `lessons` is per-lesson byte size, biggest first, so an over-budget chapter
    shows exactly which lessons to trim or split out."""
    total = _json_bytes(course)
    lessons = sorted(
        ((l["id"], _json_bytes(l)) for l in course["lessons"]),
        key=lambda x: x[1], reverse=True,
    )
    return {"total": total, "lessons": lessons, "over": total >= MAX_DOC_BYTES}


def main():
    ap = argparse.ArgumentParser(description="Assemble NERDIT course output JSON")
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--html-dir", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if the course object exceeds the 1 MiB Firestore budget")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        input_lessons = json.load(f)
    with open(args.meta, encoding="utf-8") as f:
        meta = json.load(f)

    course = build_course(args.chapter, input_lessons, meta, args.html_dir)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(course, f, ensure_ascii=False, indent=2)

    missing = [l["id"] for l in course["lessons"] if not l["content"]]
    print(f"Wrote {args.out}: {len(course['lessons'])} lessons, "
          f"{len(course['assessment']['questions'])} assessment questions")
    if missing:
        print(f"WARNING missing HTML ({len(missing)}): {', '.join(missing)}")

    rep = doc_size_report(course)
    print(f"Firestore doc size (whole course object): {rep['total']:,} bytes "
          f"/ budget {MAX_DOC_BYTES:,} (hard cap 1,048,576)")
    for lid, b in rep["lessons"][:5]:
        print(f"  {lid}: {b:,} bytes")
    if rep["over"]:
        print(f"WARNING: course exceeds the {MAX_DOC_BYTES:,}-byte budget by "
              f"{rep['total'] - MAX_DOC_BYTES:,} bytes -- it will NOT fit in one Firestore "
              f"document. Split the chapter into fewer lessons, or trim the largest lesson(s) "
              f"listed above.")
        if args.strict:
            sys.exit(2)


if __name__ == "__main__":
    main()
