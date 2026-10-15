"""Validate inserted lesson images, and compare verifier results before and after insertion."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from lessonhtml import (IMG, SRC, AnchorNotFound, find_section, fixture_text, remove_visual_blocks,
                        section_fingerprint, section_text, text, visual_elements)
from svgcheck import check_svg, foreign_tokens

TARGET = 150_000
HARD = 250_000
JSON_LIMIT = 1_048_576
ALLOWED_HOSTS = ("firebasestorage.googleapis.com", "storage.googleapis.com", "nerdit.in",
                 "future-vision-skill-learning.web.app")
VERIFY = Path(__file__).resolve().parents[2] / "nerdit-chapter-generator" / "scripts" / "verify_course.py"
BLOCK = re.compile(r'<div class="nerdit-figure nerdit-illustration" data-nerdit-img="([^"]+)"[^>]*>'
                   r'(.*?)<div class="nerdit-figure-caption">(.*?)</div>\s*</div>', re.S)


def json_bytes(course: dict) -> bytes:
    return (json.dumps(course, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _host(src: str) -> str:
    return urlparse("https:" + src if src.startswith("//") else src).hostname or ""


def _host_ok(src: str) -> bool:
    host = _host(src)
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def _check_v2(lesson_content: str, slot: dict, upload_dir: Path) -> list[str]:
    where, errors = f"{slot['lessonId']}: {slot['id']}", []
    parts = visual_elements(lesson_content, slot["id"])
    by = {}
    for tag, el in parts:
        cls = re.search(r'\bclass="([^"]*)"', el)
        by[(cls.group(1) if cls else tag)] = el
    intro = by.get("nerdit-visual-intro")
    figure = by.get("nerdit-figure")
    steps = by.get("nerdit-visual-read")
    if intro is None or not text(intro):
        errors.append(f"{where}: missing intro paragraph")
    if figure is None:
        return errors + [f"{where}: missing figure"]
    if "nerdit-predict" not in by:
        errors.append(f"{where}: missing check question")
    cap = re.search(r'<div class="nerdit-figure-caption">(.*?)</div>', figure, re.S)
    if not cap or not text(cap.group(1)):
        errors.append(f"{where}: empty caption")
    shown = len(re.findall(r"<li\b", steps or ""))
    if shown != len(slot["explanation"]):
        errors.append(f"{where}: {shown} reading steps shown, {len(slot['explanation'])} expected")
    if slot["kind"] == "diagram":
        svg = re.search(r"<svg\b.*?</svg>", figure, re.S)
        errors += [f"{where}: {p}" for p in check_svg(svg.group(0) if svg else "", slot["labels"],
                                                      len(slot["explanation"]))]
    else:
        tm = IMG.search(figure)
        tag = tm.group(0) if tm else ""
        for need in ('loading="lazy"', 'decoding="async"'):
            if need not in tag:
                errors.append(f"{where}: missing {need}")
        for attr in ("alt", "width", "height"):
            if not re.search(rf'\b{attr}="[^"]+"', tag):
                errors.append(f"{where}: missing {attr}")
        f = upload_dir / slot["outputFile"]
        if not f.is_file():
            errors.append(f"{where}: {slot['outputFile']} not in upload/")
        elif f.stat().st_size > HARD:
            errors.append(f"{where}: {f.stat().st_size // 1000} KB, over 250 KB")
    try:
        fp = section_fingerprint(lesson_content, slot["section"]["number"], slot["section"]["heading"])
    except AnchorNotFound:
        return errors + [f"{where}: its section no longer exists; re-plan with --replan {slot['lessonId']}"]
    if fp != slot["sourceFingerprint"]:
        errors.append(f"{where}: section changed since planning; re-review the visual "
                      f"(--replan {slot['lessonId']})")
    if slot["kind"] == "diagram":
        clean = remove_visual_blocks(lesson_content)
        source = section_text(clean, find_section(clean, slot["section"]["number"], slot["section"]["heading"])) \
            + "\n" + fixture_text(clean)
        absent = [l for l in slot["labels"] if l not in source]
        if absent:
            errors.append(f"{where}: labels no longer in the lesson: {absent}")
        svg = re.search(r"<svg\b.*?</svg>", figure, re.S)
        foreign = foreign_tokens(svg.group(0) if svg else "", source)
        if foreign:
            errors.append(f"{where}: drawn text not in the lesson: {foreign}")
    return errors


def check(course: dict, m: dict, upload_dir: Path) -> tuple[list[str], list[str]]:
    upload_dir = Path(upload_dir)
    errors, warnings, seen = [], [], set()
    slots = {s["id"]: s for s in m.get("images", [])}
    for lesson in course.get("lessons", []):
        content = lesson.get("content") or ""
        lid = lesson["id"]
        for tag in IMG.findall(content):
            sm = SRC.search(tag)
            src = sm.group(1) if sm else ""
            if src.startswith("data:"):
                errors.append(f"{lid}: embedded data: image")
            elif re.match(r"^(https?:)?//", src) and not _host_ok(src):
                errors.append(f"{lid}: image from outside host {_host(src)}")
        for bm in BLOCK.finditer(content):
            image_id, body, caption = bm.groups()
            where = f"{lid}: {image_id}"
            if image_id in seen:
                errors.append(f"{where}: inserted twice")
                continue
            seen.add(image_id)
            slot = slots.get(image_id)
            if slot is not None and slot.get("version") == 2:
                continue
            if slot is None or slot["status"] != "inserted":
                errors.append(f"{where}: not an inserted manifest slot")
                continue
            tm = IMG.search(body)
            tag = tm.group(0) if tm else ""
            for need in ('loading="lazy"', 'decoding="async"'):
                if need not in tag:
                    errors.append(f"{where}: missing {need}")
            for attr in ("alt", "width", "height"):
                if not re.search(rf'\b{attr}="[^"]+"', tag):
                    errors.append(f"{where}: missing {attr}")
            if not text(caption):
                errors.append(f"{where}: empty caption")
            f = upload_dir / slot["outputFile"]
            if not f.is_file():
                errors.append(f"{where}: {slot['outputFile']} not in upload/")
            elif f.stat().st_size > HARD:
                errors.append(f"{where}: {f.stat().st_size // 1000} KB, over 250 KB")
            elif f.stat().st_size > TARGET:
                warnings.append(f"{where}: {f.stat().st_size // 1000} KB, above 150 KB target")
        for s in m.get("images", []):
            if s.get("version") == 2 and s["lessonId"] == lid and s["status"] == "inserted":
                seen.add(s["id"])
                errors += _check_v2(content, s, upload_dir)
    for s in m.get("images", []):
        if s["status"] == "inserted" and s["id"] not in seen:
            errors.append(f"{s['id']}: marked inserted but not found in any lesson")
    for e in m.get("existingOptimised", []):
        if not (upload_dir / e["to"]).is_file():
            errors.append(f"{e['to']}: optimised file missing from upload/")
    size = len(json_bytes(course))
    if size >= JSON_LIMIT:
        errors.append(f"course JSON is {size} bytes; the admin import limit is {JSON_LIMIT}")
    return errors, warnings


def verifier_failures(course: dict, contract: str = "v10") -> Counter:
    inp = [{"id": l["id"], "title": l.get("title", ""), "description": l.get("title", "")}
           for l in course.get("lessons", [])]
    with tempfile.TemporaryDirectory() as d:
        ip, op = Path(d) / "input.json", Path(d) / "output.json"
        ip.write_text(json.dumps(inp, ensure_ascii=False), encoding="utf-8")
        op.write_bytes(json_bytes(course))
        r = subprocess.run([sys.executable, str(VERIFY), "--input", str(ip), "--output", str(op),
                            "--contract", contract], capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode == 2 or not re.search(r"^(PASS|FAIL) ", r.stdout, re.M):
        # A crash prints a traceback and no summary line; never read that as "no failures".
        raise RuntimeError(f"verify_course.py could not run: {(r.stderr or r.stdout).strip()[-500:]}")
    lines = [ln.strip()[2:] for ln in r.stdout.splitlines() if ln.strip().startswith("- ")]
    # Inserting a figure renumbers later figures and SVGs; compare without the numbers.
    return Counter(re.sub(r"\b(figure|svg) \d+\b", r"\1 N", ln) for ln in lines)


def new_verifier_failures(before: dict, after: dict, contract: str = "v10") -> list[str]:
    return sorted((verifier_failures(after, contract) - verifier_failures(before, contract)).elements())
