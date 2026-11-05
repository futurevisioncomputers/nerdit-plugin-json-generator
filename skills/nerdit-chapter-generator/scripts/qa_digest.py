#!/usr/bin/env python3
"""Write one plain-text digest per lesson for nerdit-qa-validator to read instead of the raw JSON.

    python qa_digest.py --course <course-[chapter]_output.json> --out <workdir>/_digest

Writes <out>/<lesson id>.md and prints each file's size beside the lesson's raw size.

The validator judges teaching: one concept per section, prose against code, figures against
captions, quiz answers against the lesson. All of that survives here; only what it never judges
leaves. Kept in full: every heading, paragraph, list, table, code block, every word drawn in a
figure (labels, markers ① ② ③, aria-label), captions, <details> answers, nerdit-dataset and
nerdit-files-spec contents, and the lesson's and assessment questions with the marked answer.
Dropped: tag attributes, inline styles, SVG geometry, <style>, and other <script> bodies
(runner helpers and gate cases: scripts check those). Each nerdit-* component is named on its
own line ([nerdit-run], [nerdit-tryit] ...), so structure and order stay visible.

When a check needs the exact markup, the validator opens that lesson's HTML in the course JSON.
Exit 0 = written, 2 = unreadable course file. Stdlib only, zero model tokens.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

BLOCK = {"p", "div", "section", "figure", "ul", "ol", "table", "tr", "blockquote", "details", "br"}
KEEP_SCRIPT = ("nerdit-dataset", "nerdit-files-spec")
VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr"}


class _Digest(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.line: list[str] = []
        self.pre = 0          # inside <pre> or a nerdit-terminal
        self.pre_stack: list[bool] = []   # open tags inside it: True = a label span
        self.href: str | None = None
        self.svg_label = ""
        self.svg = 0          # inside <svg>
        self.svg_words: list[str] = []
        self.skip = 0         # inside <style> or a dropped <script>
        self.script: str | None = None   # kept script kind
        self.cell = False

    # -- helpers ---------------------------------------------------------
    def _flush(self) -> None:
        text = re.sub(r"[ \t]+", " ", "".join(self.line)).strip()
        if text:
            self.out.append(text)
        self.line = []

    def _emit(self, text: str) -> None:
        self._flush()
        self.out.append(text)

    # -- parser hooks ----------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        cls = a.get("class") or ""
        if self.skip:
            if tag in ("style", "script"):
                self.skip += 1
            return
        if self.svg:
            if tag == "svg":
                self.svg += 1
            return
        if tag == "style":
            self.skip = 1
            return
        if tag == "script":
            kind = next((k for k in KEEP_SCRIPT if k in cls), None)
            if kind:
                self._flush()
                self.script = kind
                self.out.append(f"[{kind}]\n```")
            else:
                self.skip = 1
            return
        if tag == "svg":
            self._flush()
            self.svg, self.svg_words = 1, []
            label = a.get("aria-label")
            self.svg_label = label or ""
            return
        if self.pre:                  # inside a code or terminal block: keep text, mark labels
            if tag == "br":
                self.line.append("\n")
            elif tag not in VOID:
                self.pre_stack.append("-label" in cls)
            return
        if tag == "pre" or "nerdit-terminal" in cls.split():
            self._flush()
            names = [c for c in cls.split() if c.startswith("nerdit-")]
            if names:
                self.out.append(f"[{' '.join(names)}]")
            self.pre, self.pre_stack = 1, []
            self.out.append(f"```{a.get('data-lang') or ''}")
            return
        names = [c for c in cls.split() if c.startswith("nerdit-") and c != "nerdit-simple"]
        if tag in BLOCK or re.fullmatch(r"h[1-6]", tag) or tag in ("li", "summary", "figcaption"):
            self._flush()
        if names and tag not in ("span", "code", "strong", "em", "b", "i", "a"):
            extra = f" {a['data-run']}" if a.get("data-run") else ""
            self.out.append(f"[{' '.join(names)}{extra}]")
        if re.fullmatch(r"h[1-6]", tag):
            self.line.append("#" * int(tag[1]) + " ")
        elif tag == "li":
            self.line.append("- ")
        elif tag == "summary":
            self.line.append("<details> ")
        elif tag == "figcaption":
            self.line.append("Caption: ")
        elif tag in ("td", "th"):
            self.line.append("| ")
        elif tag == "code":
            self.line.append("`")
        elif tag == "img":
            self._emit(f"[img alt=\"{a.get('alt') or ''}\" src={a.get('src') or ''}]")
        elif tag == "a" and a.get("href"):
            self.href = a["href"]

    def handle_endtag(self, tag: str) -> None:
        if self.skip:
            if tag in ("style", "script"):
                self.skip -= 1
            return
        if self.svg:
            if tag == "svg":
                self.svg -= 1
                if not self.svg:
                    words = " | ".join(w for w in self.svg_words if w)
                    self.out.append(f"[figure svg] aria-label: {self.svg_label}\n  labels: {words}")
            return
        if tag == "script" and self.script:
            self._flush()
            self.out.append("```")
            self.script = None
            return
        if self.pre:
            if self.pre_stack:
                if self.pre_stack.pop():
                    self.line.append("\n")       # a map label sits on its own line
                return
            self.pre = 0
            text = "".join(self.line).strip("\n")
            self.line = []
            self.out.append(text)
            self.out.append("```")
            return
        if tag == "code":
            self.line.append("`")
        elif tag in ("td", "th"):
            self.line.append(" ")
        elif tag == "tr":
            self.line.append("|")
            self._flush()
        elif tag == "a" and self.href:
            self.line.append(f" ({self.href})")
            self.href = None
        elif tag in BLOCK or re.fullmatch(r"h[1-6]", tag) or tag in ("li", "summary", "figcaption"):
            self._flush()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.svg:
            word = " ".join(data.split())
            if word:
                self.svg_words.append(word)
            return
        if self.script:
            self.out.append(data.strip("\n"))
            return
        if self.pre:
            self.line.append(data)
            return
        self.line.append(data.replace("\n", " "))

    def text(self) -> str:
        self._flush()
        return "\n".join(self.out).strip() + "\n"


def html_to_text(html: str) -> str:
    parser = _Digest()
    parser.feed(html)
    parser.close()
    return parser.text()


def _questions(title: str, qs: list[dict]) -> str:
    lines = [f"## {title}"]
    for n, q in enumerate(qs, 1):
        lines.append(f"{n}. {q.get('text', '')}")
        for i, opt in enumerate(q.get("options", [])):
            mark = " (marked correct)" if i == q.get("correctOptionIndex") else ""
            lines.append(f"   {chr(65 + i)}. {opt}{mark}")
    return "\n".join(lines) + "\n"


def lesson_digest(lesson: dict, assessment: list[dict]) -> str:
    lid = lesson["id"]
    mine = [q for q in assessment if f"-{lid}-q" in q.get("id", "")]
    return (f"# DIGEST {lid} — {lesson.get('title', '')}\n"
            f"duration: {lesson.get('duration', '')}\n\n"
            + html_to_text(lesson.get("content") or "")
            + "\n" + _questions("Lesson questions", lesson.get("questions") or [])
            + "\n" + _questions("Assessment questions from this lesson", mine))


def build(course: dict, out: Path) -> list[tuple[str, int, int]]:
    out.mkdir(parents=True, exist_ok=True)
    assessment = (course.get("assessment") or {}).get("questions") or []
    sizes = []
    for lesson in course.get("lessons") or []:
        text = lesson_digest(lesson, assessment)
        (out / f"{lesson['id']}.md").write_text(text, encoding="utf-8")
        raw = len(json.dumps(lesson, ensure_ascii=False))
        sizes.append((lesson["id"], raw, len(text)))
    return sizes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--course", required=True, help="the assembled course-[chapter]_output.json")
    ap.add_argument("--out", required=True, help="folder for the per-lesson digests")
    args = ap.parse_args(argv)
    try:
        course = json.loads(Path(args.course).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    sizes = build(course, Path(args.out))
    raw = sum(r for _, r, _ in sizes)
    small = sum(d for _, _, d in sizes)
    for lid, r, d in sizes:
        print(f"  {lid}: {d:,} chars (raw lesson {r:,})")
    print(f"wrote {len(sizes)} digests to {args.out}: {small:,} chars vs {raw:,} raw "
          f"({100 - round(100 * small / max(raw, 1))}% smaller)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
