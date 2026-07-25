#!/usr/bin/env python3
"""Turn an OLD NERDIT course output JSON into inputs for a v9 REFORM run.

Reads an existing `*_output.json` (a v8/rich course) and emits, into <workdir>:
  - `course-<chapter>_input.json` — the v9 input array `[{id, title, description}]`
  - `_src/<id>.html`             — each old lesson's HTML, the reform source the
                                    lesson-writer reshapes into v9 (pass as SOURCE_PATH)

The lesson HTML is copied to files (never held in model context); only the small
input array is produced for the orchestrator. Stdlib only, no hard-coded paths.

Usage:
  python input_from_output.py --in <old_output.json> --workdir <dir> [--chapter <slug>]
"""
import argparse
import json
import os
import re


def strip_html(html):
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60] or "converted-course"


def extract_lessons(data):
    """Accept a course object, a bare lessons array, or a [course] wrapper."""
    if isinstance(data, dict) and isinstance(data.get("lessons"), list):
        return data["lessons"]
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and isinstance(data[0].get("lessons"), list):
            return data[0]["lessons"]
        return [x for x in data if isinstance(x, dict) and "id" in x]
    return []


def derive_chapter(data, override):
    if override:
        return slugify(override)
    course = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else data
    if isinstance(course, dict):
        m = re.match(r"course-(.+)-\d+$", str(course.get("id", "")))
        if m:
            return slugify(m.group(1))
        if course.get("slug"):
            return slugify(re.sub(r"-\d+$", "", course["slug"]))
        if course.get("title"):
            return slugify(course["title"])
    return "converted-course"


def derive_description(content, title):
    # Drop heading blocks first — they hold the lesson/section titles, not prose.
    body = re.sub(r"<h[1-6][^>]*>.*?</h[1-6]>", " ", content or "", flags=re.I | re.S)
    text = strip_html(body)
    if not text:
        return title
    # first sentence, capped
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return (first if len(first) <= 200 else first[:197] + "...") or title


def convert(data, workdir, chapter=None):
    """Write the v9 input array + per-lesson source HTML. Returns
    (chapter, input_list, [source_paths])."""
    chapter = derive_chapter(data, chapter)
    lessons = extract_lessons(data)
    src_dir = os.path.join(workdir, "_src")
    os.makedirs(src_dir, exist_ok=True)

    input_list, src_paths = [], []
    for les in lessons:
        lid = les["id"]
        title = les.get("title", lid)
        content = les.get("content", "") or ""
        src_path = os.path.join(src_dir, lid + ".html")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(content)
        src_paths.append(src_path)
        input_list.append({
            "id": lid,
            "title": title,
            "description": derive_description(content, title),
        })

    input_path = os.path.join(workdir, f"course-{chapter}_input.json")
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(input_list, f, ensure_ascii=False, indent=2)
    return chapter, input_list, src_paths, input_path


def main():
    ap = argparse.ArgumentParser(description="Old NERDIT output JSON -> v9 reform inputs")
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--chapter", default=None)
    args = ap.parse_args()

    with open(args.infile, encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(args.workdir, exist_ok=True)
    chapter, input_list, src_paths, input_path = convert(data, args.workdir, args.chapter)

    empty = sum(1 for les in extract_lessons(data) if not (les.get("content") or "").strip())
    print(f"chapter: {chapter}")
    print(f"wrote {input_path}: {len(input_list)} lessons")
    print(f"wrote {len(src_paths)} source files to {os.path.join(args.workdir, '_src')}")
    if empty:
        print(f"NOTE: {empty} lesson(s) had empty content -- generate those fresh (no reform source).")
    print("\nNext: run the normal pipeline on the input; pass each nerdit-lesson-writer its")
    print("SOURCE_PATH = <workdir>/_src/<id>.html so it reshapes the old material into v9.")


if __name__ == "__main__":
    main()
