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

from lessonhtml import IMG, SRC, text

TARGET = 150_000
HARD = 250_000
JSON_LIMIT = 1_048_576
ALLOWED_HOSTS = ("firebasestorage.googleapis.com", "storage.googleapis.com", "nerdit.in",
                 "future-vision-skill-learning.web.app")
VERIFY = Path(__file__).resolve().parents[2] / "nerdit-chapter-generator" / "scripts" / "verify_course.py"
BLOCK = re.compile(r'<div class="nerdit-figure nerdit-illustration" data-nerdit-img="([^"]+)">'
                   r'(.*?)<div class="nerdit-figure-caption">(.*?)</div>\s*</div>', re.S)


def json_bytes(course: dict) -> bytes:
    return (json.dumps(course, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _host(src: str) -> str:
    return urlparse("https:" + src if src.startswith("//") else src).hostname or ""


def _host_ok(src: str) -> bool:
    host = _host(src)
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


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
