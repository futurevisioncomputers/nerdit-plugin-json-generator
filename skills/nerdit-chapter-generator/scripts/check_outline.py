#!/usr/bin/env python3
"""Outline coverage: every subtopic the input lists is taught by the lesson.

An input lesson may carry `outline`, the subtopics its source material covers. A description
is one paragraph, so without the list the writer expanded what it named and dropped the rest
(the FastAPI notes had ~110 subtopics; a description names four or five per chapter).

The writer tags the heading that teaches item N (1-based) with `data-outline="N"` -- a numbered
`<h2>` or a `nerdit-runhead` `<h3>`; one heading may list several ("3 4"). This check fails when
an item has no tag, a tag names an item that does not exist, a tag sits on any other element,
or the tagged section never shows a `code term` the item names. Stdlib only.

    python check_outline.py --input <course_input.json> --dir <lesson dir> --id <lesson-id>
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
from pathlib import Path

TAGGED_RE = re.compile(r"<(\w+)\b([^>]*\bdata-outline\s*=\s*\"([^\"]*)\"[^>]*)>", re.I)
HEADING_RE = re.compile(r"<h[23]\b[^>]*>", re.I)
TERM_RE = re.compile(r"`([^`]+)`")


def _text(fragment: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))


def _terms(item: str) -> list[str]:
    # `Path()` is written Path(gt=0) in code, so the call parentheses are not part of the term.
    return [t[:-2] if t.endswith("()") else t for t in (m.strip() for m in TERM_RE.findall(item)) if t]


def outline_problems(html: str, outline: list[str]) -> list[str]:
    if not outline:
        return []
    probs: list[str] = []
    sections: dict[int, list[str]] = {}
    for m in TAGGED_RE.finditer(html):
        tag, attrs, value = m.group(1).lower(), m.group(2), m.group(3)
        if not (tag == "h2" or (tag == "h3" and "nerdit-runhead" in attrs)):
            probs.append(f"data-outline on <{tag}> -- tag a numbered <h2> or a nerdit-runhead <h3>")
            continue
        # An <h2> section runs to the next <h2>; a run-line heading to the next heading of any level.
        stop = re.compile(r"<h2\b", re.I) if tag == "h2" else HEADING_RE
        nxt = stop.search(html, m.end())
        body = _text(html[m.start():nxt.start() if nxt else len(html)])
        for tok in value.split():
            if not tok.isdigit() or not 1 <= int(tok) <= len(outline):
                probs.append(f"data-outline=\"{value}\" names item {tok}, but the outline has only "
                             f"{len(outline)} items")
                continue
            sections.setdefault(int(tok), []).append(body)
    for n, item in enumerate(outline, 1):
        if n not in sections:
            probs.append(f"outline item {n} \"{item}\" is not taught: no heading carries data-outline=\"{n}\"")
            continue
        text = " ".join(sections[n])
        missing = [t for t in _terms(item) if t not in text]
        if missing:
            probs.append(f"outline item {n} \"{item}\": its tagged section never shows "
                         f"{', '.join(missing)}")
    return probs


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Check a lesson teaches every outline item")
    ap.add_argument("--input", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--id", required=True)
    args = ap.parse_args()
    lessons = json.loads(Path(args.input).read_text(encoding="utf-8"))
    src = next((s for s in lessons if s.get("id") == args.id), None)
    if src is None:
        print(f"ERROR: {args.id} is not in {args.input}", file=sys.stderr)
        return 2
    html = (Path(args.dir) / f"{args.id}.html").read_text(encoding="utf-8")
    probs = outline_problems(html, src.get("outline") or [])
    print(f"{'FAIL' if probs else 'PASS'}  {args.id}: {len(probs)} outline problem(s)")
    for p in probs:
        print(f"  - {p}")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
