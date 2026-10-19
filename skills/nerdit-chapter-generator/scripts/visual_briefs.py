#!/usr/bin/env python3
"""Illustrator briefs for the visuals a course's lessons describe but the plugin cannot draw.

    python visual_briefs.py --course <course.json> --out <images>/plan.json

Every B screen spec (screens.screen_kind) becomes an illustrator v2 item of kind "screen", and
every scene spec an item of kind "illustration". The lesson already holds the teaching text
(alt, takeaway, misconception, check), the exact words the picture may show and the place it
goes, so nobody writes the plan by hand and the image cannot say what the lesson does not.
Feed the output to the illustrator: manifest.py add --plan <plan.json>.
Exit 1 when a lesson's specs are invalid or a spec has no paragraph to anchor to.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "nerdit-lesson-illustrator" / "scripts"))

from lessonhtml import remove_visual_blocks, sections, top_paragraphs  # noqa: E402
from render_screens import js_string, reading_steps, results_for  # noqa: E402
from screens import (cell_value, drawn_strings, read_grid, read_scenes, read_specs,  # noqa: E402
                     screen_kind, validate_lesson)

SCREEN_INTRO = "Here is the screen for this step."
SCENE_INTRO = "Picture it this way."


def _place(content: str, offset: int, lid: str, sid: str) -> dict:
    """Section, heading and anchor for a visual whose spec ends at `offset`."""
    sec = next((s for s in sections(content) if s.start <= offset < s.end), None)
    if sec is None:
        raise ValueError(f"{lid}: {sid} sits outside every <h2> section")
    before = [a for end, a in top_paragraphs(content, sec) if end <= offset and a]
    if before:
        return {"section": sec.number, "heading": sec.heading, "position": "after-explanation",
                "anchor": before[-1]}
    return {"section": sec.number, "heading": sec.heading, "position": "before-practice", "anchor": ""}


def _shown_cells(spec: dict, grid) -> list[str]:
    view = spec["view"]
    r0, r1 = view["rows"]
    out = []
    for r in range(r0, r1 + 1):
        for letter in view["columns"]:
            value = js_string(cell_value(grid, f"{letter}{r}"))
            if value and value not in out:
                out.append(value)
    return out


def _screen_item(lid: str, content: str, spec: dict) -> dict:
    grid = read_grid(content, spec["_grid"]) if spec.get("_grid") else None
    results, problems = results_for(spec, grid)
    if problems:
        raise ValueError(f"{lid}: " + "; ".join(problems))
    labels = drawn_strings(spec)
    if spec["layout"] == "sheet":
        # The image may show the grid's coordinates too, or "Click cell B4" points nowhere.
        view = spec["view"]
        coords = list(view["columns"]) + [str(r) for r in range(view["rows"][0], view["rows"][1] + 1)]
        labels += [v for v in _shown_cells(spec, grid) + list(results.values()) + coords + [view["active"]]
                   if v not in labels]
    return {
        "lessonId": lid, **_place(content, spec["_offset"], lid, spec["id"]), "kind": "screen",
        "question": spec["goal"], "objective": spec["goal"], "caption": spec["goal"],
        "takeaway": spec["takeaway"], "misconception": spec["misconception"], "alt": spec["alt"],
        "intro": SCREEN_INTRO, "explanation": reading_steps(spec, results),
        "checkQuestion": dict(spec["check"]), "labels": labels,
        "sourceRefs": ["#" + (spec["_grid"] if spec["layout"] == "sheet" else spec["id"])],
        "knownTerms": [], "newTerms": [], "subject": f"{spec['app']} window: {spec['goal']}",
        "app": spec["app"],
    }


def _scene_item(lid: str, content: str, scene: dict) -> dict:
    return {
        "lessonId": lid, **_place(content, scene["_offset"], lid, scene["id"]), "kind": "illustration",
        "question": scene["takeaway"], "objective": scene["takeaway"], "caption": scene["caption"],
        "takeaway": scene["takeaway"], "misconception": scene["misconception"], "alt": scene["alt"],
        "intro": SCENE_INTRO, "explanation": [scene["takeaway"]],
        "checkQuestion": dict(scene["check"]), "labels": [], "sourceRefs": ["#" + scene["id"]],
        "knownTerms": [], "newTerms": [], "subject": scene["subject"],
    }


def brief_items(course: dict) -> list[dict]:
    """One illustrator v2 plan item per B screen and per scene, in lesson and page order."""
    items, errors = [], []
    for lesson in course.get("lessons", []):
        lid = lesson["id"]
        content = remove_visual_blocks(lesson.get("content") or "")
        problems = validate_lesson(content)
        if problems:
            errors += [f"{lid}: {p}" for p in problems]
            continue
        found = [(s["_offset"], "screen", s) for s in read_specs(content) if screen_kind(s) == "B"]
        found += [(s["_offset"], "scene", s) for s in read_scenes(content)]
        for _, kind, spec in sorted(found, key=lambda f: f[0]):
            try:
                items.append(_screen_item(lid, content, spec) if kind == "screen" else _scene_item(lid, content, spec))
            except ValueError as e:
                errors.append(str(e))
    if errors:
        raise ValueError("\n".join(errors))
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--course", required=True, help="course output JSON")
    ap.add_argument("--out", required=True, help="where to write the illustrator v2 plan")
    args = ap.parse_args(argv)
    course = json.loads(Path(args.course).read_text(encoding="utf-8"))
    try:
        items = brief_items(course)
    except ValueError as e:
        print(f"FAIL:\n{e}")
        return 1
    Path(args.out).write_text(json.dumps({"version": 2, "items": items}, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    kinds = [i["kind"] for i in items]
    print(f"OK: {kinds.count('screen')} screen and {kinds.count('illustration')} scene brief(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
