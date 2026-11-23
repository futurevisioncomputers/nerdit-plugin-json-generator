"""List or extract the inline SVG figures of a NerdIT course, to reuse one in an article.

    python course_figures.py --course <course.json>                       # list: lesson, n, title, caption, labels
    python course_figures.py --course <course.json> --extract <lesson>:<n> --out <file.svg>

The course JSON is the admin's "Export output JSON" (or the chapter generator's output).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

# The figure's SVG and, right after it, its caption (when it has one).
FIGURE = re.compile(r'<div class="nerdit-figure"[^>]*>\s*(<svg\b.*?</svg>)\s*(?:<div class="nerdit-figure-caption">(.*?)</div>)?', re.S)
TEXT = re.compile(r"<text\b[^>]*>(.*?)</text>", re.S)
TITLE = re.compile(r"<title>(.*?)</title>", re.S)


def _plain(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def figures(course: dict) -> list[dict]:
    out = []
    for lesson in course.get("lessons", []):
        for n, m in enumerate(FIGURE.finditer(lesson.get("content") or ""), 1):
            svg, cap = m.group(1), m.group(2) or ""
            title = TITLE.search(svg)
            out.append({"lesson": lesson["id"], "n": n, "title": _plain(title.group(1)) if title else "",
                        "caption": _plain(cap),
                        "labels": [_plain(t) for t in TEXT.findall(svg) if _plain(t)], "svg": svg})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--course", type=Path, required=True)
    ap.add_argument("--extract")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    found = figures(json.loads(a.course.read_text(encoding="utf-8")))
    if not a.extract:
        for f in found:
            print(f"{f['lesson']}:{f['n']}  {f['title']}  | caption: {f['caption']}  | labels: {', '.join(f['labels'])}")
        return 0
    lesson, _, n = a.extract.partition(":")
    match = [f for f in found if f["lesson"] == lesson and str(f["n"]) == n]
    if not match or not a.out:
        print(f"PROBLEM no figure {a.extract} (or no --out); list them without --extract")
        return 1
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(match[0]["svg"], encoding="utf-8")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
