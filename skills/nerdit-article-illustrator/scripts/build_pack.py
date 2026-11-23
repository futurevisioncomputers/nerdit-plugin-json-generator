"""Check an article image plan and build the image pack the admin imports.

    python build_pack.py --article <article.json> --plan <plan.json> --out <pack-folder>

plan.json: {"items": [{"file": "x.png", "source": "diagram"|"course", "svg": "x.svg" (beside plan.json),
"anchor": "<a ¶ line from article_outline.py>", "labels": [...], "alt": "...", "caption": "...",
"steps": 0, "courseId"?, "courseSlug"?, "courseTitle"? (course figures)}]}

Every rule failure prints `PROBLEM ...` and nothing is written. On success the folder holds one 1600 px PNG
per item (light page, lesson stylesheet) and placements.json for Articles → Edit → Import images.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageStat

from article_outline import outline

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "nerdit-lesson-illustrator" / "scripts"))
from svgcheck import check_svg, foreign_tokens  # noqa: E402

CSS_DIR = SKILLS / "nerdit-chapter-generator" / "references"
LESSON_CSS = ("css8.css", "css9-simple.css", "css10-brand.css")
WIDTH = 1600
PAD = 40
MIN_LUMINANCE = 0.6
SITE = "https://nerdit.in"


def plan_errors(article: dict, plan: dict, base: Path) -> list[str]:
    items = plan.get("items") or []
    errors = [] if 2 <= len(items) <= 3 else [f"plan has {len(items)} images; an article gets 2 or 3 images"]
    anchors = {r["text"] for r in outline(article["markdown"]) if r["kind"] == "anchor"}
    source_text = f"{article['title']}\n{article['markdown']}"
    files = [str(i.get("file", "")) for i in items]
    errors += [f"{f}: file name used twice" for f in sorted({f for f in files if files.count(f) > 1})]
    for item in items:
        f = str(item.get("file", ""))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.png", f):
            errors.append(f"{f or '(no file)'}: file must be a lowercase name ending .png")
        if item.get("anchor") not in anchors:
            errors.append(f"{f}: anchor is not a line of the article word for word: {item.get('anchor')!r}")
        for key in ("alt", "caption"):
            if not str(item.get(key, "")).strip():
                errors.append(f"{f}: {key} is empty")
        svg_path = base / str(item.get("svg", ""))
        if not item.get("svg") or not svg_path.is_file():
            errors.append(f"{f}: svg file not found: {item.get('svg')}")
            continue
        svg = svg_path.read_text(encoding="utf-8")
        labels = list(item.get("labels") or [])
        errors += [f"{f}: {e}" for e in check_svg(svg, labels, int(item.get("steps", 0)))]
        if item.get("source") == "diagram":
            errors += [f"{f}: label '{lb}' is not in the article" for lb in labels if lb.lower() not in source_text.lower()]
            errors += [f"{f}: drawn '{t}' is not in the article" for t in foreign_tokens(svg, source_text)]
        elif item.get("source") == "course":
            if not item.get("courseTitle") or not (item.get("courseSlug") or item.get("courseId")):
                errors.append(f"{f}: a course figure needs courseTitle and courseSlug or courseId")
        else:
            errors.append(f"{f}: source must be diagram or course")
    return errors


def lesson_css() -> str:
    return "\n".join((CSS_DIR / n).read_text(encoding="utf-8") for n in LESSON_CSS if (CSS_DIR / n).is_file())


def page(svg: str, css: str) -> tuple[str, int]:
    """The figure on a white page, WIDTH px wide; returns (html, height)."""
    vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg)
    w, h = (float(vb.group(1)), float(vb.group(2))) if vb else (4.0, 3.0)
    height = round((WIDTH - 2 * PAD) * h / w) + 2 * PAD
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}\n'
           ".nerdit-anim .na-open{transform:none!important}.nerdit-anim *{animation:none!important}"
           "html,body{margin:0!important;background:#fff!important}"
           f".nerdit-wrapper{{background:#fff!important;margin:0!important;padding:{PAD}px!important;"
           f"width:{WIDTH}px!important;max-width:none!important;box-sizing:border-box!important;border:0!important}}"
           ".nerdit-figure{max-width:none!important;width:100%!important;margin:0!important;padding:0!important;"
           "border:0!important;box-shadow:none!important;background:transparent!important}"
           ".nerdit-figure svg{width:100%!important;height:auto!important;display:block}"
           f'</style></head><body><div class="nerdit-wrapper"><div class="nerdit-figure">{svg}</div></div></body></html>')
    return doc, height


def placement(item: dict) -> dict:
    out = {k: item[k] for k in ("file", "anchor", "alt", "caption")}
    if item.get("source") == "course":
        # No UTM: the caption link sits inside the nerdit.in article (an internal link).
        out["courseLink"] = f"{SITE}/course/{item.get('courseSlug') or item['courseId']}/preview"
        out["courseTitle"] = item["courseTitle"]
    return out


def mean_luminance(png: Path) -> float:
    return ImageStat.Stat(Image.open(png).convert("L")).mean[0] / 255


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--article", type=Path, required=True)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    article = json.loads(a.article.read_text(encoding="utf-8"))
    plan = json.loads(a.plan.read_text(encoding="utf-8"))
    errors = plan_errors(article, plan, a.plan.parent)
    if errors:
        for e in errors:
            print(f"PROBLEM {e}")
        return 1

    from brand_studio.render import shoot
    css = lesson_css()
    tmp = a.out.parent / f".{a.out.name}.building"
    shutil.rmtree(tmp, ignore_errors=True)
    jobs = []
    for item in plan["items"]:
        doc, height = page((a.plan.parent / item["svg"]).read_text(encoding="utf-8"), css)
        jobs.append((doc, tmp / item["file"], WIDTH, height))
    shoot(jobs)
    dark = [f"{p.name}: page is too dark ({mean_luminance(p):.2f}; at least {MIN_LUMINANCE})"
            for _, p, _, _ in jobs if mean_luminance(p) < MIN_LUMINANCE]
    if dark:
        shutil.rmtree(tmp, ignore_errors=True)
        for e in dark:
            print(f"PROBLEM {e}")
        return 1
    (tmp / "placements.json").write_text(json.dumps([placement(i) for i in plan["items"]], indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    shutil.rmtree(a.out, ignore_errors=True)
    tmp.rename(a.out)
    print(f"wrote {len(jobs)} image(s) and placements.json to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
