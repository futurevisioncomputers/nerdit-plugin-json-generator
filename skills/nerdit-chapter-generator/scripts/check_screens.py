#!/usr/bin/env python3
"""Gate check for screen and scene specs: the lesson and its pictures say the same thing.

    check_lesson(html) -> (fails, warns)

Fails: a spec that breaks screens.validate_lesson (schema, phone limits, the sync rule, ids); a
formula the Excel engine cannot compute; an A screen with no drawing, or one that differs from
a fresh render (the lesson changed after render_screens.py ran); a B screen that still has a
drawing; a drawing whose spec is gone.
Warns: an image forced to A or B (QA reads the reason); an A screen of an app with no colour
theme; a concept section that teaches a click-path with no screen spec.
Stdlib only.
"""
from __future__ import annotations

import re

from render_screens import BLOCK, render_spec, screen_theme
from screens import read_specs, screen_kind, validate_lesson
from verify_course import parse, text_of, walk

VERBS = ("Click", "Select", "Open", "Go to", "Choose", "Press", "Type", "Drag", "Set", "Tap", "Enter")
UI_PART = re.compile(r"\b(?:tab|menu|button|dialog|panel|pane|ribbon|field|box|toolbar|sidebar)s?\b|→| > ",
                     re.I)
LEAD = re.compile(r"^[\s①-⑳\d.)]+")
GAP = re.compile(r">\s+<")


def _drawn_blocks(html: str) -> dict[str, str]:
    return {m.group(1): m.group(0) for m in BLOCK.finditer(html)}


def _in_details(node) -> bool:
    while node is not None:
        if node.tag == "details":
            return True
        node = node.parent
    return False


def _is_click_path(ol) -> bool:
    if "nerdit-visual-read" in ol.classes or _in_details(ol):
        return False
    items = [LEAD.sub("", text_of(li)).strip() for li in ol.children if li.tag == "li"]
    starts = sum(1 for t in items if t.startswith(VERBS))
    return starts >= 2 and any(UI_PART.search(t) for t in items)


def click_path_warnings(html: str) -> list[str]:
    tree = parse(html)
    sections = [n for n in tree.all if n.tag == "section"]
    concept = [s for s in sections
               if not any(n.classes & {"nerdit-cheatsheet", "nerdit-practical"} for n in walk(s))]
    warns = []
    for k, sec in enumerate(concept, 1):
        nodes = list(walk(sec))
        has_screen = any(n.tag == "script" and "nerdit-screen" in n.classes for n in nodes)
        if not has_screen and any(n.tag == "ol" and _is_click_path(n) for n in nodes):
            warns.append(f"section {k}: click-path with no screen (figures.md template 16)")
    return warns


def check_lesson(html: str) -> tuple[list[str], list[str]]:
    fails = list(validate_lesson(html))
    warns: list[str] = []
    specs = read_specs(html)
    drawn = _drawn_blocks(html)
    if not fails:
        for spec in specs:
            sid, kind = spec["id"], screen_kind(spec)
            if spec.get("image", "auto") != "auto":
                warns.append(f"{sid}: image forced to {kind}: {spec.get('why', '')}")
            if kind == "B":
                if sid in drawn:
                    fails.append(f"{sid}: a B screen has a drawing; run render_screens.py to remove it")
                continue
            if screen_theme(spec) is None:
                warns.append(f"{sid}: no colour theme for '{spec['app']}'; drawn in NerdIT colours "
                             f"(add one to APP_THEMES and css10-brand.css)")
            fresh, problems = render_spec(html, spec)
            if problems:
                fails += problems
            elif sid not in drawn:
                fails.append(f"{sid}: no drawn screen; run render_screens.py")
            elif GAP.sub("><", drawn[sid]) != GAP.sub("><", fresh):
                fails.append(f"{sid}: drawn screen is out of date; run render_screens.py")
    ids = {s.get("id") for s in specs}
    fails += [f"{sid}: a drawn screen has no spec; run render_screens.py" for sid in drawn if sid not in ids]
    warns += click_path_warnings(html)
    return fails, warns
