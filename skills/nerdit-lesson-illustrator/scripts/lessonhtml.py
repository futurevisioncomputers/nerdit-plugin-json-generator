"""Dependency-free helpers for reading and editing NERDIT lesson HTML.

A section is the span from one <h2> to the next (or to the end of the lesson). A paragraph is
"top level" in a section when it sits at the same <div> depth as the section's <h2>, so text
inside practice boxes, info boxes and figures is never used as an image anchor.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

H2 = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.S | re.I)
P = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S | re.I)
IMG = re.compile(r"<img\b[^>]*>", re.I)
SRC = re.compile(r'\bsrc="([^"]*)"', re.I)
SVG = re.compile(r"<svg\b", re.I)
PRACTICE = re.compile(r'<div\b[^>]*\bclass="[^"]*\bnerdit-(?:predict|fillblank|tryit)\b[^"]*"', re.I)
FIG_CAPTION = re.compile(r'<div\b[^>]*\bclass="[^"]*\bnerdit-figure-caption\b[^"]*"[^>]*>(.*?)</div>', re.S | re.I)
DIV_OPEN = re.compile(r"<div\b", re.I)
DIV_CLOSE = re.compile(r"</div\s*>", re.I)
TAG = re.compile(r"<[^>]+>")
NON_TEACHING = re.compile(
    r"cheat\s*sheet|practice|quiz|summary|takeaway|recap|exercise|assignment|challenge|next steps", re.I)
ANCHOR_LEN = 60


class AnchorNotFound(Exception):
    """The placement recorded for an image no longer exists in the lesson."""


@dataclass(frozen=True)
class Section:
    number: int      # 1-based position of the <h2> in the lesson
    heading: str     # plain text of the <h2>
    start: int       # offset of the <h2> tag
    end: int         # offset of the next <h2>, or end of content
    teaching: bool   # False for cheat sheets, practice, quizzes and summaries


def text(fragment: str) -> str:
    """Plain text: tags removed, entities decoded, whitespace collapsed."""
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", fragment))).strip()


def anchor_of(fragment: str) -> str:
    return text(fragment)[:ANCHOR_LEN].rstrip()


def _depth(s: str) -> int:
    return len(DIV_OPEN.findall(s)) - len(DIV_CLOSE.findall(s))


def sections(content: str) -> list[Section]:
    heads = list(H2.finditer(content))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(content)
        heading = text(m.group(1))
        out.append(Section(i + 1, heading, m.start(), end, not NON_TEACHING.search(heading)))
    return out


def top_paragraphs(content: str, sec: Section) -> list[tuple[int, str]]:
    base = _depth(content[:sec.start])
    return [(m.end(), anchor_of(m.group(1)))
            for m in P.finditer(content, sec.start, sec.end)
            if _depth(content[:m.start()]) == base]


def find_section(content: str, number: int, heading: str) -> Section:
    for sec in sections(content):
        if sec.number == number and sec.heading == heading:
            return sec
    raise AnchorNotFound(f"section {number} '{heading}' not found")


def locate(content: str, number: int, heading: str, position: str, anchor: str | None) -> int:
    """Offset where an image block goes. Raises AnchorNotFound instead of guessing."""
    sec = find_section(content, number, heading)
    paras = top_paragraphs(content, sec)
    if position == "after-explanation":
        for end, a in paras:
            if a == anchor:
                return end
        raise AnchorNotFound(f"no paragraph starting '{anchor}' in section {number} '{heading}'")
    if position == "before-practice":
        m = PRACTICE.search(content, sec.start, sec.end)
        if m and _depth(content[:m.start()]) == _depth(content[:sec.start]):
            return m.start()
        if paras:
            return paras[-1][0]
        raise AnchorNotFound(f"section {number} '{heading}' has no practice block or paragraph")
    raise ValueError(f"unknown position {position!r}")


def img_sources(content: str) -> list[str]:
    out = []
    for tag in IMG.findall(content):
        m = SRC.search(tag)
        if m:
            out.append(html.unescape(m.group(1)))
    return out
