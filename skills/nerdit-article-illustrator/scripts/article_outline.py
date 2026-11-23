"""Print a NerdIT blog article as sections (§) and anchor lines (¶) for planning images.

Every ¶ line is copied word for word from the article: a plan's `anchor` must be one of them
(the admin's "Import images" puts the image after the paragraph that holds it). Code blocks are skipped.

    python article_outline.py --article <article.json>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FENCE = re.compile(r"^\s*(`{3}|~{3})")


def outline(markdown: str) -> list[dict]:
    rows: list[dict] = []
    section = ""
    in_fence = False
    for line in markdown.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip():
            continue
        heading = re.match(r"^#{2,3}\s+(.*)", line)
        if heading:
            section = heading.group(1).strip()
            rows.append({"kind": "heading", "text": section})
        elif not line.lstrip().startswith("!["):
            rows.append({"kind": "anchor", "text": line.strip(), "section": section})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--article", type=Path, required=True)
    a = ap.parse_args(argv)
    article = json.loads(a.article.read_text(encoding="utf-8"))
    print(f"# {article['title']}  ({len(article['markdown'].split())} words)")
    for row in outline(article["markdown"]):
        print(f"§ {row['text']}" if row["kind"] == "heading" else f"  ¶ {row['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
