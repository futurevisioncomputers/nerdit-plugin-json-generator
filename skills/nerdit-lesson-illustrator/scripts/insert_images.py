"""Insert passed images into lessons and build the with-images course JSON.

Usage: python insert_images.py --course <course.json> --images-dir <dir> [--no-optimise] [--contract v10|v9]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import sys
from pathlib import Path

import manifest as mf
from check_images import check, json_bytes, new_verifier_failures
from lessonhtml import AnchorNotFound, locate, remove_visual_blocks
from manifest import MARKERS
from optimise_existing import default_fetch, optimise_existing

DIAGRAM_MAX_WIDTH = 440


def block(slot: dict) -> str:
    alt = html.escape(slot["alt"], quote=True)
    caption = html.escape(slot["caption"], quote=False)
    return (f'\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="{slot["id"]}" data-visual="illustration">\n'
            f'  <img src="{slot["outputFile"]}" alt="{alt}" width="{slot["width"]}" height="{slot["height"]}"'
            ' loading="lazy" decoding="async" style="display:block;width:100%;height:auto">\n'
            f'  <div class="nerdit-figure-caption">{caption}</div>\n</div>')


def blocks_v2(slot: dict, svg: str | None) -> str:
    vid, esc = slot["id"], (lambda s: html.escape(s, quote=False))
    if slot["kind"] == "diagram":
        figure = svg.strip()
    else:
        figure = (f'<img src="{slot["outputFile"]}" alt="{html.escape(slot["alt"], quote=True)}" '
                  f'width="{slot["width"]}" height="{slot["height"]}" loading="lazy" decoding="async" '
                  'style="display:block;width:100%;height:auto">')
    # A phone-width diagram (viewBox <= 400) would blow up to 680 px on desktop; cap it.
    width = f' style="max-width:{DIAGRAM_MAX_WIDTH}px"' if slot["kind"] == "diagram" else ""
    # CORE.md §7: every figure names its visual; a plan item may say which (e.g. time-window).
    visual = slot.get("visual") or ("diagram" if slot["kind"] == "diagram" else "illustration")
    out = [f'\n<p class="nerdit-visual-intro" data-nerdit-img="{vid}">{esc(slot["intro"])}</p>',
           f'\n<div class="nerdit-figure" data-nerdit-img="{vid}" data-visual="{visual}"{width}>\n  {figure}\n'
           f'  <div class="nerdit-figure-caption">{esc(slot["caption"])}</div>\n</div>']
    steps = slot["explanation"]
    marks = MARKERS[:len(steps)] if len(steps) >= 2 else [""] * len(steps)
    items = "".join(f"<li>{(mk + ' ') if mk else ''}{esc(st)}</li>" for mk, st in zip(marks, steps))
    out.append(f'\n<ol class="nerdit-visual-read" data-nerdit-img="{vid}" '
               f'style="list-style:none;padding-left:0">{items}</ol>')
    cq = slot["checkQuestion"]
    out.append(f'\n<div class="nerdit-predict" data-nerdit-img="{vid}">'
               '<div class="nerdit-predict-head">🤔 Try It — read the figure</div>'
               f'<p>{esc(cq["question"])}</p><details class="nerdit-predict-answer"><summary>Show answer</summary>'
               f'<p>{esc(cq["answer"])} {esc(cq["reasoning"])}</p></details></div>')
    return "".join(out)


def strip_inserted(content: str) -> str:
    return remove_visual_blocks(content)


def insert_lessons(course: dict, m: dict, diagrams_dir: Path | None = None) -> list[str]:
    errors = []
    by_lesson: dict[str, list[dict]] = {}
    for s in m["images"]:
        if s["status"] in ("passed", "inserted"):
            by_lesson.setdefault(s["lessonId"], []).append(s)
    known = set()
    for lesson in course.get("lessons", []):
        known.add(lesson["id"])
        content = strip_inserted(lesson.get("content") or "")
        placed = []
        for s in by_lesson.get(lesson["id"], []):
            try:
                off = locate(content, s["section"]["number"], s["section"]["heading"],
                             s["position"], s["anchor"] or None)
            except AnchorNotFound as e:
                errors.append(f"{s['id']}: {e}; re-plan with --replan {s['lessonId']}")
                s["status"] = "passed"
                continue
            if s.get("version") == 2:
                svg = None
                if s["kind"] == "diagram":
                    f = Path(diagrams_dir or ".") / s["requestFile"]
                    if not f.is_file():
                        errors.append(f"{s['id']}: diagram file {s['requestFile']} not found")
                        s["status"] = "passed"
                        continue
                    svg = f.read_text(encoding="utf-8")
                    if hashlib.sha256(svg.encode("utf-8")).hexdigest() != s.get("sourceSha256"):
                        errors.append(f"{s['id']}: diagram file {s['requestFile']} changed since it was "
                                      "checked; run convert_images.py and review it again")
                        s["status"] = "passed"
                        continue
                markup = blocks_v2(s, svg)
            else:
                markup = block(s)
            placed.append((off, s, markup))
        for off, s, markup in sorted(placed, key=lambda p: (p[0], p[1]["id"]), reverse=True):
            content = content[:off] + markup + content[off:]
            s["status"] = "inserted"
        lesson["content"] = content
    for lid, slots in by_lesson.items():
        if lid not in known:
            errors += [f"{s['id']}: lesson {lid} is not in this course" for s in slots]
    return errors


def output_path(course_path: Path) -> Path:
    course_path = Path(course_path)
    return course_path.with_name(course_path.stem + ".with-images.json")


def build_output(course_path: Path, images_dir: Path, fetch=default_fetch, optimise: bool = True,
                 contract: str = "v10") -> int:
    course_path, images_dir = Path(course_path), Path(images_dir)
    with open(course_path, encoding="utf-8") as f:
        original = json.load(f)
    work = copy.deepcopy(original)
    m = copy.deepcopy(mf.load(images_dir))
    upload = images_dir / "upload"
    lines, problems = [], []

    if optimise:
        rep = optimise_existing(work, m, upload, fetch)
        lines += [f"  optimised: {x}" for x in rep["optimised"]]
        problems += rep["errors"]
    problems += insert_lessons(work, m, images_dir / "diagrams")
    errors, warnings = check(work, m, upload)
    problems += errors
    problems += [f"new verifier failure: {x}" for x in new_verifier_failures(original, work, contract)]

    counts = {st: sum(1 for s in m["images"] if s["status"] == st) for st in mf.STATUSES}
    print(f"inserted {counts['inserted']} · waiting for files {counts['planned']} · "
          f"to check {counts['converted']} · failed {counts['failed']}")
    print("\n".join(lines + [f"  warning: {w}" for w in warnings]))
    if problems:
        print("Not written — fix these first:")
        print("\n".join(f"  - {p}" for p in problems))
        return 1
    out = output_path(course_path)
    out.write_bytes(json_bytes(work))
    mf.save(images_dir, m)
    (images_dir / "PROMPTS.md").write_text(mf.render_prompts(m), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Admin → Import JSON + Images: choose {out.name} and the folder {upload}")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--images-dir", required=True)
    ap.add_argument("--no-optimise", action="store_true")
    ap.add_argument("--contract", choices=["v9", "v10"], default="v10")
    args = ap.parse_args()
    return build_output(Path(args.course), Path(args.images_dir), optimise=not args.no_optimise,
                        contract=args.contract)


if __name__ == "__main__":
    sys.exit(main())
