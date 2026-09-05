#!/usr/bin/env python3
"""Deterministic verification of an assembled course-<chapter>_output.json.

Written because the LLM QA pass produces confident false failures: on 2026-09-05 it
invented an `assets` rule the plugin's own reference output contradicts, and got the
cheatsheet markup exactly backwards (it called the correct form broken and the broken
form correct). Everything in this file is a fact that can be decided by reading the
JSON or walking the DOM, so it is decided here instead of being judged.

Two groups of checks:

  SCHEMA     - shape, ids, counts, timestamps, ordering, question dedupe
  STRUCTURE  - the lesson HTML: box nesting depth, banned/retired components,
               every <pre> paired with an output, a Try It per concept section,
               unique element ids, cheatsheet markup form

Stdlib only (html.parser) so the plugin gains no dependencies.

What it deliberately does NOT check: anything that needs real CSS - rendered widths,
contrast ratios, horizontal overflow. Those need a browser; see the harness note in
CLASSROOM_LAYOUT_REDESIGN.md / LESSON_CONTENT_SIMPLIFICATION.md.

    python verify_course.py --input course-x_input.json --output course-x_output.json
    python verify_course.py ... --contract v10     # enforce the flattened contract

Exit 0 = all checks pass, 1 = at least one failure, 2 = could not read a file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser

# Blocks that PAINT a container - border, fill, radius or shadow. Nesting these is what
# produced "four borders around one line of output".
#
# `nerdit-practical` is deliberately absent: the contract defines it as a grouping with
# no chrome (CORE.md section 8) and its CSS was stripped to match, so it costs the reader
# no nesting. Counting it would fail the contract's own worked example, which is
# section > practical > task > solution.
BOXED = {
    "nerdit-example", "nerdit-step", "nerdit-task",
    "nerdit-solution", "nerdit-output", "nerdit-tryit", "nerdit-predict",
}

# Never valid in any contract version.
BANNED = [
    "nerdit-stat-grid", "nerdit-donut", "nerdit-gauge", "nerdit-ring-grid",
    "nerdit-funnel", "nerdit-metric-compare", "nerdit-dashboard", "nerdit-cards-grid",
    "nerdit-card-grid", "nerdit-hbar-chart", "nerdit-bar-chart", "nerdit-memory-aid",
    "nerdit-step-block", "nerdit-datatable-wrap",
]

# Retired only under the flattened (v10) contract - see --contract.
RETIRED_V10 = [
    "nerdit-example", "nerdit-example-head", "nerdit-example-lead",
    "nerdit-example-note", "nerdit-output", "nerdit-output-label",
    "nerdit-objective", "nerdit-recap",
]

TRY_IT = {"nerdit-predict", "nerdit-fillblank", "nerdit-tryit"}
DEPTH_CAP = 2
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "source", "track", "wbr"}


class Node:
    __slots__ = ("tag", "classes", "el_id", "parent", "children")

    def __init__(self, tag: str, classes, el_id, parent):
        self.tag, self.classes, self.el_id, self.parent = tag, set(classes), el_id, parent
        self.children: list["Node"] = []


class Tree(HTMLParser):
    """Minimal DOM. Only tags/classes/ids matter here, so text is discarded."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", [], None, None)
        self.cur = self.root
        self.all: list[Node] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        node = Node(tag, (a.get("class") or "").split(), a.get("id"), self.cur)
        self.cur.children.append(node)
        self.all.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        a = dict(attrs)
        node = Node(tag, (a.get("class") or "").split(), a.get("id"), self.cur)
        self.cur.children.append(node)
        self.all.append(node)

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root and n.parent is not None:
            self.cur = n.parent


def parse(html: str) -> Tree:
    t = Tree()
    t.feed(html)
    return t


def box_depth(node: Node) -> int:
    d, n = 0, node
    while n is not None:
        if n.classes & BOXED:
            d += 1
        n = n.parent
    return d


def descends_from(node: Node, cls: str) -> bool:
    n = node.parent
    while n is not None:
        if cls in n.classes:
            return True
        n = n.parent
    return False


class Report:
    def __init__(self):
        self.passed = 0
        self.failures: list[str] = []

    def check(self, ok: bool, msg: str):
        if ok:
            self.passed += 1
        else:
            self.failures.append(msg)


def verify_schema(rep: Report, out: dict, inp: list):
    rep.check(isinstance(out, dict) and not isinstance(out, list),
              "output must be a single course object, not an array")
    rep.check(bool(re.fullmatch(r"course-[a-z0-9-]+-\d+", out.get("id", ""))),
              f"course id format: {out.get('id')!r}")
    created, updated = out.get("createdAt"), out.get("updatedAt")
    rep.check(created == updated, "createdAt equals updatedAt")
    suffix = out.get("id", "").rsplit("-", 1)[-1]
    rep.check(suffix.isdigit(), "course id ends in an epoch-ms suffix")

    lessons = out.get("lessons", [])
    rep.check(len(lessons) == len(inp),
              f"lesson count {len(lessons)} == input {len(inp)}")
    rep.check(out.get("lessonIds") == [l["id"] for l in inp],
              "lessonIds equal input ids in order")

    a = out.get("assessment") or {}
    rep.check(a.get("passingScore") == 70, f"passingScore 70 (got {a.get('passingScore')})")
    rep.check(a.get("examQuestionCount") == 20,
              f"examQuestionCount 20 (got {a.get('examQuestionCount')})")
    rep.check(len(a.get("questions", [])) == 3 * len(inp),
              f"assessment questions {len(a.get('questions', []))} == 3 x {len(inp)}")

    sessions, batches = set(), set()

    def q_ok(q, kind, lesson_id):
        pat = rf"^{kind}-(\d+)-{re.escape(lesson_id)}-q\d+-(\d+)$"
        m = re.fullmatch(pat, q.get("id", ""))
        rep.check(bool(m), f"{kind} question id format: {q.get('id')!r}")
        if m:
            sessions.add(m.group(1))
            batches.add(m.group(2))
        rep.check(isinstance(q.get("options"), list) and len(q["options"]) == 4,
                  f"{q.get('id')}: exactly 4 options")
        ci = q.get("correctOptionIndex")
        rep.check(isinstance(ci, int) and 0 <= ci <= 3,
                  f"{q.get('id')}: correctOptionIndex in 0..3 (got {ci!r})")
        rep.check(bool(str(q.get("text", "")).strip()), f"{q.get('id')}: non-empty text")

    for i, lesson in enumerate(lessons):
        src = inp[i] if i < len(inp) else {}
        tag = lesson.get("id", f"#{i}")
        rep.check(lesson.get("id") == src.get("id"), f"lesson {i+1}: id copied exactly")
        rep.check(lesson.get("title") == src.get("title"), f"lesson {i+1}: title copied exactly")
        rep.check("description" not in lesson, f"{tag}: no description field")
        rep.check(bool(re.fullmatch(r"\d+m", lesson.get("duration", ""))),
                  f"{tag}: duration NNm (got {lesson.get('duration')!r})")
        rep.check(len(lesson.get("questions", [])) == 3, f"{tag}: exactly 3 lesson questions")
        for q in lesson.get("questions", []):
            q_ok(q, "lesson", lesson.get("id", ""))

    for lesson in lessons:
        lid = lesson.get("id", "")
        mine = [q for q in a.get("questions", []) if f"-{lid}-" in q.get("id", "")]
        rep.check(len(mine) == 3, f"{lid}: exactly 3 assessment questions (got {len(mine)})")
        for q in mine:
            q_ok(q, "assessment", lid)
        # An assessment question that restates a lesson question tests nothing new.
        lesson_texts = {norm(q.get("text", "")) for q in lesson.get("questions", [])}
        dupes = [q["id"] for q in mine if norm(q.get("text", "")) in lesson_texts]
        rep.check(not dupes, f"{lid}: assessment questions are not restatements ({dupes})")

    rep.check(len(sessions) <= 1, f"one QID_SESSION_TS across all ids (found {sessions})")
    rep.check(len(batches) <= 1, f"one QID_BATCH_TS across all ids (found {batches})")


def norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def verify_structure(rep: Report, out: dict, contract: str):
    for lesson in out.get("lessons", []):
        lid = lesson.get("id", "?")
        html = lesson.get("content", "")
        rep.check(html.startswith('<div class="nerdit-wrapper'),
                  f"{lid}: content starts with the wrapper div")
        rep.check("nerdit-simple" in html[:200], f"{lid}: wrapper carries nerdit-simple")
        rep.check("```" not in html, f"{lid}: no markdown fences in content")

        tree = parse(html)

        ids = [n.el_id for n in tree.all if n.el_id]
        rep.check(len(ids) == len(set(ids)),
                  f"{lid}: element ids unique ({len(ids) - len(set(ids))} duplicates)")

        # The depth cap arrived with the flattened contract. Under v9 the practice block
        # is legitimately practical > task > solution > output, so enforcing it there
        # would fail every correct v9 lesson.
        if contract == "v10":
            worst = max((box_depth(n) for n in tree.all), default=0)
            rep.check(worst <= DEPTH_CAP,
                      f"{lid}: box nesting depth {worst} exceeds cap {DEPTH_CAP}")

        present = {c for n in tree.all for c in n.classes}
        hits = sorted(present & set(BANNED))
        rep.check(not hits, f"{lid}: banned components present: {hits}")

        if contract == "v10":
            retired = sorted(present & set(RETIRED_V10))
            rep.check(not retired, f"{lid}: retired v10 components present: {retired}")

        # A <pre> that is not inside a syntax box or a code-comparison must have its
        # result shown - the whole point of the run line.
        #
        # Predict and fill-blank are exempt by design: both withhold the result on
        # purpose, because supplying it is the exercise. Flagging them was this
        # script's own first false positive.
        for pre in [n for n in tree.all if n.tag == "pre"]:
            if any(descends_from(pre, c) for c in
                   ("nerdit-syntax", "nerdit-compare", "nerdit-code-tabs",
                    "nerdit-terminal", "nerdit-cheatsheet",
                    "nerdit-predict", "nerdit-fillblank")):
                continue
            # Walk up to the unit that OWNS the pair, never to the half holding the
            # input. A run line is nerdit-run > [nerdit-in, nerdit-out], so the output
            # is a SIBLING of the input; stopping at nerdit-in finds nothing and
            # reports every correct run line as missing its output.
            owner = pre
            while owner is not None and not (owner.classes & {
                    "nerdit-example", "nerdit-run", "nerdit-tryit",
                    "nerdit-predict", "nerdit-fillblank", "nerdit-solution"}):
                owner = owner.parent
            scope = owner if owner is not None else tree.root
            has_out = any(n.classes & {"nerdit-output", "nerdit-out"}
                          for n in walk(scope))
            rep.check(has_out, f"{lid}: a <pre> has no paired output block")

        # Every concept section ends with something the learner produces an answer in.
        sections = [n for n in tree.all if n.tag == "section"]
        for i, sec in enumerate(sections, 1):
            has_try = any(n.classes & TRY_IT for n in walk(sec))
            is_closing = any(n.classes & {"nerdit-cheatsheet", "nerdit-practical"}
                             for n in walk(sec))
            if is_closing:
                continue
            rep.check(has_try, f"{lid}: concept section {i} has no Try It block")

        # `.nerdit-cheatsheet table {...}` plus overflow-x on the wrapper: the class
        # belongs on a containing element, never on the table itself. With it on the
        # table the descendant rules never match - measured 245px wide instead of 1034.
        for n in tree.all:
            if "nerdit-cheatsheet" in n.classes:
                rep.check(n.tag != "table",
                          f"{lid}: nerdit-cheatsheet is on <table>; it must wrap the table")
                if n.tag != "table":
                    rep.check(any(c.tag == "table" for c in walk(n)),
                              f"{lid}: nerdit-cheatsheet wrapper contains no <table>")


def walk(node: Node):
    stack = list(node.children)
    while stack:
        n = stack.pop()
        yield n
        stack.extend(n.children)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--contract", choices=["v9", "v10"], default="v9",
                    help="v10 also rejects the retired example/output/objective/recap blocks")
    ap.add_argument("--quiet", action="store_true", help="print failures only")
    args = ap.parse_args()

    try:
        out = json.load(open(args.output, encoding="utf-8"))
        inp = json.load(open(args.input, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    rep = Report()
    verify_schema(rep, out, inp)
    verify_structure(rep, out, args.contract)

    total = rep.passed + len(rep.failures)
    if rep.failures:
        print(f"FAIL  {len(rep.failures)} of {total} checks (contract {args.contract})")
        for f in rep.failures:
            print(f"  - {f}")
        return 1

    if not args.quiet:
        print(f"PASS  {rep.passed}/{total} checks (contract {args.contract})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
