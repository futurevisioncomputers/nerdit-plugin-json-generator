#!/usr/bin/env python3
"""Human-voice check for lesson prose (CORE.md §10, references/voice.md).

Lessons that read as machine-written share a small set of phrases and one rhythm. This fails
a lesson on a banned phrase and warns on long sentences, long paragraphs, em-dash habits and
concept sections that all open the same way. Code, tables and figures are not prose.

    python check_prose.py --course <course_output.json> [--lesson <id>]

Exit 0 = no banned phrase, 1 = at least one, 2 = could not read a file. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from verify_course import Node, parse, walk

VOICE = Path(__file__).resolve().parent.parent / "references" / "voice.md"
SKIP = {"pre", "code", "textarea", "svg", "script", "style", "table"}
MAX_WORDS = 15
MAX_SENTENCES = 3
MAX_DASHES = 1
MAX_NEW_TERMS = 2   # key terms (<strong>) one concept section may introduce


def banned_patterns(path: Path = VOICE) -> list[tuple[str, re.Pattern]]:
    """The ```banned block of voice.md: one phrase per line, or `re:<regex>`."""
    block = re.search(r"```banned\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
    if block is None:
        raise ValueError(f"{path} has no ```banned block")
    out = []
    for line in block.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("re:"):
            out.append((line[3:], re.compile(line[3:], re.I)))
        else:
            out.append((line, re.compile(r"(?<!\w)" + re.escape(line) + r"(?!\w)", re.I)))
    return out


BR = " "  # stands in for <br>: a void element, so it has no text of its own


def plain_words(path: Path = VOICE) -> list[tuple[str, str]]:
    """The ```plain block of voice.md: `hard word => simpler word`, one per line."""
    block = re.search(r"```plain\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
    if block is None:
        return []
    pairs = [line.split("=>") for line in block.group(1).splitlines() if "=>" in line]
    return [(a.strip(), b.strip()) for a, b in pairs]


def prose(node: Node) -> str:
    """Visible prose under `node`, in page order, skipping code, tables and SVG.
    Each <br> becomes BR, so a legend's lines are not read as one run-on sentence."""
    parts, stack = [], list(reversed(node.content))
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            parts.append(item)
        elif item.tag == "br":
            parts.append(BR)
        elif item.tag not in SKIP:
            stack.extend(reversed(item.content))
    text = re.sub(rf"[^\S{BR}]+", " ", "".join(parts))
    return re.sub(rf" ?{BR} ?", BR, text).strip()


def _inside(node: Node, tags: set[str]) -> bool:
    n = node.parent
    while n is not None:
        if n.tag in tags:
            return True
        n = n.parent
    return False


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _first_paragraph(sec: Node) -> Node | None:
    stack = list(reversed(sec.content))
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            continue
        if item.tag == "p":
            return item
        stack.extend(reversed(item.content))
    return None


def check_lesson(content: str, patterns) -> tuple[list[str], list[str]]:
    """(failures, warnings) for one lesson's HTML."""
    tree = parse(content)
    fails, warns = [], []

    text = prose(tree.root).replace(BR, " ")
    for phrase, pat in patterns:
        m = pat.search(text)
        if m:
            fails.append(f'banned phrase "{m.group(0)}" (references/voice.md: {phrase})')

    long_s, long_p, dashy = [], 0, 0
    for para in [n for n in tree.all if n.tag in ("p", "li") and not _inside(n, SKIP)]:
        body = prose(para)
        # A line break ends a legend line for length, but lines are not extra sentences.
        long_s += [s for line in body.split(BR) for s in sentences(line) if len(s.split()) > MAX_WORDS]
        body = body.replace(BR, " ")
        long_p += len(sentences(body)) > MAX_SENTENCES
        dashy += body.count("—") > MAX_DASHES
    if long_s:
        fails.append(f'{len(long_s)} sentence(s) over {MAX_WORDS} words; split each, e.g. "{long_s[0][:60]}"')
    if long_p:
        warns.append(f"{long_p} paragraph(s) with more than {MAX_SENTENCES} sentences")
    if dashy:
        warns.append(f"{dashy} paragraph(s) with more than {MAX_DASHES} em dash")

    openers = []
    for n_sec, sec in enumerate([n for n in tree.all if n.tag == "section"], 1):
        if any(n.classes & {"nerdit-cheatsheet", "nerdit-practical"} for n in walk(sec)):
            continue
        p = _first_paragraph(sec)
        if p is not None:
            openers.append(" ".join(prose(p).lower().split()[:2]))
        fails += _simple_section(sec, p, n_sec)
    if len(openers) >= 3 and len(set(openers)) == 1:
        warns.append(f'every concept section opens with the same words ("{openers[0]}"); vary the openings')

    for word, simpler in plain_words():
        m = re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text, re.I)
        if m:
            fails.append(f'"{m.group(0)}" is hard for a beginner; say "{simpler}" (references/voice.md plain words)')
    return fails, warns


def _terms(sec: Node) -> list[Node]:
    """The section's key words: <strong> in its prose paragraphs (CORE.md §10).
    A bold label such as "Fix:" or "Task 1:" names a part of a block, not a new term."""
    return [n for n in _in_order(sec) if n.tag == "strong" and not _inside(n, SKIP)
            and any(a.tag in ("p", "li") for a in _ancestors(n)) and not prose(n).rstrip().endswith(":")]


def _in_order(node: Node):
    """Elements under `node` in reading order."""
    stack = list(reversed(node.content))
    while stack:
        item = stack.pop()
        if not isinstance(item, str):
            yield item
            stack.extend(reversed(item.content))


def _ancestors(node: Node):
    n = node.parent
    while n is not None:
        yield n
        n = n.parent


def _simple_section(sec: Node, first: Node | None, n: int) -> list[str]:
    """Simplicity rules for one concept section (CORE.md §10)."""
    out = []
    terms = _terms(sec)
    if len(terms) > MAX_NEW_TERMS:
        names = ", ".join(prose(t) for t in terms[:4])
        out.append(f"section {n} introduces {len(terms)} key terms ({names}); keep to {MAX_NEW_TERMS} so a "
                   "beginner can hold them, and move the rest to their own section")
    if first is not None and any(first in _ancestors(t) for t in terms):
        out.append(f"section {n} opens with a definition; start with an everyday example or scene the learner "
                   "knows, then name the idea")
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--lesson")
    args = ap.parse_args()
    try:
        course = json.loads(Path(args.course).read_text(encoding="utf-8"))
        patterns = banned_patterns()
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    bad = 0
    for lesson in course.get("lessons", []):
        if args.lesson and lesson.get("id") != args.lesson:
            continue
        fails, warns = check_lesson(lesson.get("content") or "", patterns)
        if fails or warns:
            print(f"{lesson.get('id')}: {len(fails)} banned, {len(warns)} warnings")
            for f in fails:
                print(f"  - {f}")
            for w in warns:
                print(f"  WARN {w}")
        bad += len(fails)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
