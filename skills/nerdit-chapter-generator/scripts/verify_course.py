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
from pathlib import Path

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

MAX_FIGURE_VIEWBOX_WIDTH = 400  # figures.md rule 9 (phone-readable figures), v10 only

# Contracts that use the flattened (v10) checks. v11 adds the teaching-visuals checks
# (spec 2026-10-15): SQL layout, run-line headings, figure data-visual and dotted labels.
FLAT = {"v10", "v11"}
# CORE.md §7 Visual Map: every nerdit-figure names the visual it is.
VISUALS = {"diagram", "value-table", "decision-grid", "time-window", "unit-tiles",
           "chart", "course-map", "illustration"}
DOT_SEP = "·"
_SHAPES = (
    ("time", re.compile(r"\d{1,2}:\d{2}(:\d{2})?")),
    ("date", re.compile(r"\d{4}-\d{2}-\d{2}( \d{1,2}:\d{2}(:\d{2})?)?")),
    ("number", re.compile(r"[-−]?[₹$]?[\d,]+(\.\d+)?[%kKmM]?")),
)
# An id like `O1` or `customer_sk 1`; its letter prefix says which column it belongs to.
_CODE = re.compile(r"([A-Za-z_]+) ?\d+")
# Reading-step markers (① …) label a figure part; they are not a field.
_MARKERS = re.compile(r"^[\s①②③④⑤⑥⑦⑧⑨⑩]+")
BLOCK_LINES = 15                                   # CORE.md §4: one shown code block
LESSON_LINES = {"concept": 40, "hands-on": 100}    # CORE.md §4: shown code per lesson
MAX_SQL_LINE = 60  # runners/sql.md: the input half wraps, so a longer line breaks mid-statement
MAX_DATASET_BYTES = 40_960  # runners/python.md: a lesson's dataset recipe; the browser builds the CSVs
# figures.md R11: `[ home ]` or `[ ]` in a figure shows spaces with brackets; a list like [1, 2] does not.
SPACE_BRACKETS = re.compile(r"\[(?:[ \t]+[^\]\n]*|[^\]\n]*[ \t]+)\]")

# Retired only under the flattened (v10) contract - see --contract.
RETIRED_V10 = [
    "nerdit-example", "nerdit-example-head", "nerdit-example-lead",
    "nerdit-example-note", "nerdit-output", "nerdit-output-label",
    "nerdit-objective", "nerdit-recap",
]

TRY_IT = {"nerdit-predict", "nerdit-fillblank", "nerdit-tryit"}

# A colour literal in fill=/stroke=/stop-color=, i.e. inside a diagram. Restricted to
# those attributes so a hex inside prose text (a lesson ABOUT hex codes) is not flagged.
HEX_IN_SVG = re.compile(
    r'(?:fill|stroke|stop-color|flood-color|lighting-color)\s*=\s*.#[0-9a-fA-F]{3,8}.'
)
DEPTH_CAP = 2
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "source", "track", "wbr"}


class Node:
    __slots__ = ("tag", "classes", "el_id", "parent", "children", "attrs", "content")

    def __init__(self, tag: str, classes, el_id, parent, attrs=None):
        self.tag, self.classes, self.el_id, self.parent = tag, set(classes), el_id, parent
        # Kept for the <svg> contract (viewBox / role / aria-label); everything else
        # still decides on tag, class and id alone.
        self.attrs: dict = attrs or {}
        self.children: list["Node"] = []
        # Children and text in page order, for checks that read labels and code.
        self.content: list = []


class Tree(HTMLParser):
    """Minimal DOM: tags, classes, ids, attributes and text in page order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", [], None, None)
        self.cur = self.root
        self.all: list[Node] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        node = Node(tag, (a.get("class") or "").split(), a.get("id"), self.cur, a)
        self.cur.children.append(node)
        self.cur.content.append(node)
        self.all.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        a = dict(attrs)
        node = Node(tag, (a.get("class") or "").split(), a.get("id"), self.cur, a)
        self.cur.children.append(node)
        self.cur.content.append(node)
        self.all.append(node)

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.content.append(data)


def parse(html: str) -> Tree:
    t = Tree()
    t.feed(html)
    return t


def text_of(node: Node) -> str:
    """All text under `node`, in page order, entities already decoded."""
    out: list[str] = []
    stack: list = list(reversed(node.content))
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            out.append(item)
        else:
            stack.extend(reversed(item.content))
    return "".join(out)


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



def ancestor(node: Node, cls: str) -> Node | None:
    n = node.parent
    while n is not None:
        if cls in n.classes:
            return n
        n = n.parent
    return None


def _norm_sentence(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s.lstrip("—–- ").rstrip(". ")


def field_shape(field: str) -> str | None:
    """The kind of value a dotted-label field holds; None when it holds no digit."""
    f = field.strip()
    if not re.search(r"\d", f):
        return None
    for name, pat in _SHAPES:
        if pat.fullmatch(f):
            return name
    code = _CODE.fullmatch(f)
    if code:
        return "code:" + code.group(1).lower()
    return "mixed"


def is_dotted_record(text: str) -> bool:
    """`row 1 · 09:00 · 10000` packs a table row into one label (figures.md R10);
    `O1 · O2 · O3` is a list of like values and is fine."""
    fields = _MARKERS.sub("", text).split(DOT_SEP)
    if len(fields) < 3:
        return False
    shapes = [s for s in (field_shape(f) for f in fields) if s]
    return len(shapes) >= 2 and len(set(shapes)) >= 2


def sql_code_blocks(tree: "Tree") -> list[tuple[str, str]]:
    """(where, code) for SQL a learner reads or edits: run-line input and SQL Try It editors."""
    out = []
    for n in tree.all:
        if n.tag == "pre" and n.attrs.get("data-lang", "").lower() == "sql" and descends_from(n, "nerdit-in"):
            out.append(("run line", text_of(n)))
        elif n.tag == "textarea" and "nerdit-tryit-editor" in n.classes:
            box = ancestor(n, "nerdit-tryit")
            if box is not None and ("data-seed" in box.attrs or box.attrs.get("data-lang", "").lower() == "sql"):
                out.append(("try-it editor", text_of(n)))
    return out

class Report:
    def __init__(self):
        self.passed = 0
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def check(self, ok: bool, msg: str):
        if ok:
            self.passed += 1
        else:
            self.failures.append(msg)

    def warn(self, ok: bool, msg: str):
        """Advisory: printed after the result, never changes the exit code."""
        if not ok:
            self.warnings.append(msg)


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
        if contract in FLAT:
            worst = max((box_depth(n) for n in tree.all), default=0)
            rep.check(worst <= DEPTH_CAP,
                      f"{lid}: box nesting depth {worst} exceeds cap {DEPTH_CAP}")

        present = {c for n in tree.all for c in n.classes}
        hits = sorted(present & set(BANNED))
        rep.check(not hits, f"{lid}: banned components present: {hits}")

        if contract in FLAT:
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

        # CORE.md section 7: every lesson ships at least one figure. A wall of prose and
        # code gives a learner nothing to anchor a concept to, and the decision table is
        # wide enough that almost every concept has an honest answer in it.
        figures = [n for n in tree.all if "nerdit-figure" in n.classes]
        rep.check(bool(figures), f"{lid}: no nerdit-figure - every lesson needs at least one")

        for i, fig in enumerate(figures, 1):
            where = f"{lid}: figure {i}"
            rep.check(any("nerdit-figure-caption" in c.classes for c in walk(fig)),
                      f"{where} has no nerdit-figure-caption")
            # A caption-less figure fails the caption-first test in CORE.md section 7:
            # if the sentence would not come, the figure should not have been drawn.

        # Inline SVG contract - section 7 rules plus section 7b colour tokens.
        for i, svg in enumerate([n for n in tree.all if n.tag == "svg"], 1):
            where = f"{lid}: svg {i}"
            # html.parser lowercases attribute names, so viewBox arrives as "viewbox".
            rep.check("viewbox" in svg.attrs, f"{where} has no viewBox")
            rep.check(svg.attrs.get("role") == "img", f'{where} needs role="img"')
            rep.check(bool(svg.attrs.get("aria-label", "").strip()),
                      f"{where} has no aria-label")
            # section 7 wants the wrapper for width control; a bare svg ignores
            # `.nerdit-figure svg { width:100% }` and renders at its intrinsic size.
            rep.check(descends_from(svg, "nerdit-figure") or descends_from(svg, "nerdit-flow-wrap"),
                      f"{where} is not wrapped in nerdit-figure / nerdit-flow-wrap")
            # figures.md rule 9: a phone column is ~314 px, so a wider viewBox shrinks figure
            # labels below ~11.5 px (640 wide gives ~7 px). Run outputs (charts) are exempt.
            vb = svg.attrs.get("viewbox", "").replace(",", " ").split()
            if contract in FLAT and len(vb) == 4 and not descends_from(svg, "nerdit-out"):
                try:
                    width = float(vb[2])
                except ValueError:
                    width = 0
                rep.check(width <= MAX_FIGURE_VIEWBOX_WIDTH,
                          f"{where} viewBox is {width:g} wide; stack it to at most "
                          f"{MAX_FIGURE_VIEWBOX_WIDTH} so labels stay readable on a phone (figures.md rule 9)")

        # section 7b: a hex literal survives the theme switch and breaks it - a navy
        # diagram stays navy on a dark ground. Tokens resolve per theme; hex does not.
        # Checked on the raw HTML because colours live in attributes the tree drops.
        for m in HEX_IN_SVG.finditer(html):
            frag = m.group(0)
            rep.check(False, f"{lid}: hex colour in lesson markup ({frag}) - use var(--token), see CORE.md 7b")

        if contract == "v11":
            for where, code in sql_code_blocks(tree):
                long = [ln.rstrip() for ln in code.splitlines() if len(ln.rstrip()) > MAX_SQL_LINE]
                rep.check(not long, f"{lid}: SQL {where} has {len(long)} line(s) over {MAX_SQL_LINE} "
                                    f"characters (runners/sql.md), first: {long[0].strip()[:40] if long else ''}")
            for h in [n for n in tree.all if n.tag == "h3" and "nerdit-runhead" in n.classes]:
                why = next((c for c in walk(h) if "why" in c.classes), None)
                sibs = h.parent.children if h.parent is not None else []
                nxt = sibs[sibs.index(h) + 1] if sibs.index(h) + 1 < len(sibs) else None
                if why is not None and nxt is not None and nxt.tag == "p":
                    rep.check(_norm_sentence(text_of(why)) != _norm_sentence(text_of(nxt)),
                              f"{lid}: run-line heading's why text is repeated as the next paragraph "
                              f"(CORE.md §4c): {text_of(why).strip()[:50]}")
            for i, fig in enumerate(figures, 1):
                rep.check(fig.attrs.get("data-visual") in VISUALS,
                          f"{lid}: figure {i} needs data-visual, one of {', '.join(sorted(VISUALS))} "
                          f"(CORE.md §7)")
            for t in tree.all:
                if t.tag == "text" and descends_from(t, "nerdit-figure"):
                    label = text_of(t).strip()
                    rep.check(not is_dotted_record(label),
                              f"{lid}: figure label packs a table row into dots ({label[:40]}); "
                              f"use a value table (figures.md R10)")
            for i, fig in enumerate(figures, 1):
                m = SPACE_BRACKETS.search(text_of(fig))
                rep.check(m is None, f"{lid}: figure {i} shows spaces with square brackets "
                                     f"({m.group(0) if m else ''}); use nerdit-val and nerdit-ws (figures.md R11)")
            mains = []
            concept = [s for s in sections if not any(
                n.classes & {"nerdit-cheatsheet", "nerdit-practical"} for n in walk(s))]
            for k, sec in enumerate(concept, 1):
                # A figure missing data-visual is already a failure above; it still counts as
                # the section's visual, so it must not also raise "no main visual".
                kinds = {n.attrs.get("data-visual") or "unnamed" for n in walk(sec) if "nerdit-figure" in n.classes}
                if any("nerdit-chart-wrap" in n.classes for n in walk(sec)):
                    kinds.add("chart")
                main = kinds - {"illustration", "course-map"}
                rep.warn(bool(main), f"{lid}: concept section {k} has no main visual (CORE.md §7 Visual Map)")
                mains.append(main - {"unnamed"})
            used = [m for m in mains if m]
            only = set().union(*used) if used else set()
            rep.warn(not (len(used) >= 3 and len(only) == 1),
                     f"{lid}: every concept section uses the same visual ({', '.join(sorted(only))}); "
                     f"pick each one from the Visual Map")
            verify_dataset(rep, lid, tree)


def verify_dataset(rep: Report, lid: str, tree: Tree) -> None:
    """runners/python.md: at most one self-contained recipe, small enough to ship in the lesson."""
    blocks = [n for n in tree.all if n.tag == "script" and "nerdit-dataset" in n.classes]
    if not blocks:
        return
    rep.check(len(blocks) == 1, f"{lid}: {len(blocks)} dataset blocks; a lesson carries at most one")
    raw = "".join(c for c in blocks[0].content if isinstance(c, str))
    size = len(raw.encode("utf-8"))
    rep.check(size <= MAX_DATASET_BYTES,
              f"{lid}: dataset block is {size} bytes; at most {MAX_DATASET_BYTES} (runners/python.md)")
    rep.check(blocks[0].attrs.get("type") == "application/json",
              f'{lid}: dataset block needs type="application/json"')
    try:
        recipe = json.loads(raw)
    except ValueError as exc:
        rep.check(False, f"{lid}: dataset block is not valid JSON ({exc})")
        return
    # Lazy import: the generator core lives in references/, shared with the website.
    refs = str(Path(__file__).resolve().parent.parent / "references")
    if refs not in sys.path:
        sys.path.append(refs)
    from nerdit_world_gen import check_recipe
    try:
        check_recipe(recipe)
        rep.check(True, f"{lid}: dataset block")
    except (ValueError, KeyError, TypeError) as exc:
        rep.check(False, f"{lid}: dataset block: {exc}")



def shown_code_blocks(tree: Tree) -> list[str]:
    return [text_of(n).strip("\n") for n in tree.all if n.tag == "pre" and descends_from(n, "nerdit-in")]


def verify_density(rep: Report, out: dict, inp: list):
    """CORE.md §4: code where the learner must produce or check a number. Advisory only."""
    focus = {s.get("id"): str(s.get("focus") or "hands-on").lower() for s in inp}
    for lesson in out.get("lessons", []):
        lid = lesson.get("id", "?")
        blocks = shown_code_blocks(parse(lesson.get("content", "")))
        for i, code in enumerate(blocks, 1):
            n = len(code.splitlines())
            rep.warn(n <= BLOCK_LINES, f"{lid}: code block {i} shows {n} lines (max {BLOCK_LINES}); "
                                       f"move repeated setup into the seed, never the step being taught")
        kind = focus.get(lid, "hands-on")
        cap = LESSON_LINES.get(kind, LESSON_LINES["hands-on"])
        total = sum(len(c.splitlines()) for c in blocks)
        rep.warn(total <= cap, f"{lid}: lesson shows {total} code lines (max {cap} for {kind})")

def walk(node: Node):
    stack = list(node.children)
    while stack:
        n = stack.pop()
        yield n
        stack.extend(n.children)


def main() -> int:
    # Messages quote lesson text (①, ·, ₹, §). A Windows pipe defaults to cp1252 and would crash.
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--contract", choices=["v9", "v10", "v11"], default="v9",
                    help="v10 rejects retired blocks; v11 adds the teaching-visuals checks")
    ap.add_argument("--quiet", action="store_true", help="print failures only")
    ap.add_argument("--world", help="optional world file; v11 checks records and course-map continuity")
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
    if args.contract == "v11":
        verify_density(rep, out, inp)
        if args.world:
            # Lazy import keeps the standalone DOM helpers usable by check_world.py.
            from pathlib import Path
            from make_world_data import generate, load_world
            from check_world import check_lesson as check_world
            try:
                world = load_world(Path(args.world))
                data = generate(world)
                for lesson in out.get("lessons", []):
                    failures, warnings = check_world(lesson.get("content", ""), world, data)
                    for failure in failures:
                        rep.check(False, f"{lesson.get('id', '?')}: world: {failure}")
                    for warning in warnings:
                        rep.warn(False, f"{lesson.get('id', '?')}: world: {warning}")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                print(f"ERROR: world: {exc}", file=sys.stderr)
                return 2

    total = rep.passed + len(rep.failures)
    if rep.failures:
        print(f"FAIL  {len(rep.failures)} of {total} checks (contract {args.contract})")
        for f in rep.failures:
            print(f"  - {f}")
    elif not args.quiet:
        print(f"PASS  {rep.passed}/{total} checks (contract {args.contract})")
    for w in rep.warnings:
        print(f"  WARN {w}")
    return 1 if rep.failures else 0


if __name__ == "__main__":
    sys.exit(main())
