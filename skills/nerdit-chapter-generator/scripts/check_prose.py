#!/usr/bin/env python3
"""Human-voice check for lesson prose (CORE.md §10, references/voice.md).

Lessons that read as machine-written share a small set of phrases and one rhythm. This fails
a lesson on a banned phrase, a long sentence or a concept section that opens with a story
instead of the idea, and warns on long paragraphs, em-dash habits, thin sections and concept
sections that all open the same way. Code, tables and figures are not prose.

    python check_prose.py --course <course_output.json> [--lesson <id>]

Exit 0 = no banned phrase, 1 = at least one, 2 = could not read a file. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from titlecase import heading_problems
from verify_course import Node, parse, walk

VOICE = Path(__file__).resolve().parent.parent / "references" / "voice.md"
SKIP = {"pre", "code", "textarea", "svg", "script", "style", "table"}
MAX_WORDS = 20
MAX_SENTENCES = 4
MAX_DASHES = 1
MAX_NEW_TERMS = 3        # key terms (<strong>) one concept section may introduce
MIN_SECTION_WORDS = 120  # prose a concept section needs: what it is, how the code shows it, the case
MAX_SECTION_WORDS = 220  # above this warns: cut, do not pad (owner, 2026-10-26: lessons read too long)
FAIL_SECTION_WORDS = 300 # above this fails
MAX_PARAS_BEFORE_CODE = 3  # a section with a run block shows its code by its third paragraph


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


def _paragraphs(sec: Node) -> list[Node]:
    """The section's prose paragraphs in reading order."""
    return [n for n in _in_order(sec) if n.tag == "p" and not _inside(n, SKIP)]


def _first_paragraph(sec: Node) -> Node | None:
    paras = _paragraphs(sec)
    return paras[0] if paras else None


def _paragraphs_before_code(sec: Node) -> int | None:
    """Prose paragraphs before the section's first run block, or None when it has no run block.
    The case study heading starts a new count: the topic's explanation is not the case's lead-in."""
    count = 0
    for n in _in_order(sec):
        if "nerdit-run" in n.classes:
            return count
        if "nerdit-casehead" in n.classes:
            count = 0
        if n.tag == "p" and not _inside(n, SKIP):
            count += 1
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
        fails += _simple_section(sec, n_sec)
        words = sum(len(prose(n).split()) for n in _in_order(sec)
                    if n.tag in ("p", "li") and not _inside(n, SKIP))
        if words < MIN_SECTION_WORDS:
            warns.append(f"section {n_sec} has {words} words of explanation; aim for "
                         f"{MIN_SECTION_WORDS}-{MAX_SECTION_WORDS}: what it is, the code, then the case")
        elif words > FAIL_SECTION_WORDS:
            fails.append(f"section {n_sec} has {words} words of explanation; at most {FAIL_SECTION_WORDS} "
                         f"(aim for {MIN_SECTION_WORDS}-{MAX_SECTION_WORDS}): show the code earlier and "
                         "explain its lines in a code walk instead of paragraphs")
        elif words > MAX_SECTION_WORDS:
            warns.append(f"section {n_sec} has {words} words of explanation; cut to {MAX_SECTION_WORDS}")
        before = _paragraphs_before_code(sec)
        if before is not None and before > MAX_PARAS_BEFORE_CODE:
            fails.append(f"section {n_sec} has {before} paragraphs before its first code block; show the code "
                         f"by paragraph {MAX_PARAS_BEFORE_CODE}, then explain it")
    if len(openers) >= 3 and len(set(openers)) == 1:
        warns.append(f'every concept section opens with the same words ("{openers[0]}"); vary the openings')

    lower = heading_problems(content)
    if lower:
        fails.append(f'{len(lower)} heading(s) not in Title Case (capital first letter on every main word), '
                     f'e.g. "{lower[0][:60]}"; assemble_course.py fixes this, or run titlecase.fix_headings')

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


def _simple_section(sec: Node, n: int) -> list[str]:
    """Simplicity rules for one concept section (CORE.md §10)."""
    out = []
    terms = _terms(sec)
    if len(terms) > MAX_NEW_TERMS:
        names = ", ".join(prose(t) for t in terms[:5])
        out.append(f"section {n} introduces {len(terms)} key terms ({names}); keep to {MAX_NEW_TERMS} so a "
                   "beginner can hold them, and move the rest to their own section")
    # Explain first: the first key word sits in the first paragraph, or in the second when the
    # first is a single question. A story or case study opening pushes it later.
    paras = _paragraphs(sec)
    if terms and paras:
        lead = paras[:2] if len(sentences(prose(paras[0]))) == 1 and prose(paras[0]).endswith("?") else paras[:1]
        if not any(p in _ancestors(terms[0]) for p in lead):
            out.append(f"section {n} opens with a story or example; explain the idea first (its key word in the "
                       "first paragraph), then give the case study")
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
