"""Shrink heavy images already in lessons: download, convert to WebP, re-point the src.

Used by insert_images.py. The re-pointed bare filename is matched by the admin's
"Import JSON + Images" page to the file of the same name in upload/.
"""
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from pathlib import Path

from convert_images import encode_webp
from lessonhtml import IMG, SRC

MIN_BYTES = 300_000
SITE = "https://nerdit.in"


def default_fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "nerdit-lesson-illustrator"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _absolute(src: str) -> str:
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        return SITE + src
    return src


def _set_dims(tag: str, width: int, height: int) -> str:
    for attr, val in (("width", width), ("height", height)):
        if re.search(rf'\b{attr}="[^"]*"', tag):
            tag = re.sub(rf'\b{attr}="[^"]*"', f'{attr}="{val}"', tag, count=1)
        else:
            tag = tag.replace("<img", f'<img {attr}="{val}"', 1)
    return tag


def optimise_existing(course: dict, m: dict, upload_dir: Path, fetch=default_fetch,
                      min_bytes: int = MIN_BYTES) -> dict:
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    report = {"optimised": [], "kept": [], "errors": []}
    m.setdefault("existingOptimised", [])
    own = {s["outputFile"] for s in m.get("images", [])}
    done = {e["from"]: e for e in m["existingOptimised"]}
    taken = own | {e["to"] for e in m["existingOptimised"]}
    for lesson in course.get("lessons", []):
        content = lesson.get("content") or ""
        for tag in IMG.findall(content):
            sm = SRC.search(tag)
            src = html.unescape(sm.group(1)) if sm else ""
            if not re.match(r"^(https?:)?//|^/", src):
                continue  # data:, bare filenames and our own outputs are left alone
            entry = done.get(src)
            if entry is None:
                try:
                    data = fetch(_absolute(src))
                except Exception as e:
                    report["errors"].append(f"{lesson['id']}: could not download {src} ({e}); kept")
                    continue
                if len(data) < min_bytes:
                    report["kept"].append(src)
                    continue
                try:
                    webp, w, h, _ = encode_webp(data)
                except Exception as e:
                    report["errors"].append(f"{lesson['id']}: could not convert {src} ({e}); kept")
                    continue
                stem = re.sub(r"[^A-Za-z0-9._-]", "-", Path(urllib.parse.urlparse(src).path).stem) or "image"
                name, n = f"{stem}.webp", 2
                while name in taken:
                    name, n = f"{stem}-{n}.webp", n + 1
                (upload_dir / name).write_bytes(webp)
                taken.add(name)
                entry = {"lessonId": lesson["id"], "from": src, "to": name, "bytesBefore": len(data),
                         "bytesAfter": len(webp), "width": w, "height": h}
                m["existingOptimised"].append(entry)
                done[src] = entry
            new_tag = _set_dims(re.sub(r'\bsrc="[^"]*"', f'src="{entry["to"]}"', tag, count=1),
                                entry["width"], entry["height"])
            content = content.replace(tag, new_tag)
            report["optimised"].append(f"{lesson['id']}: {src} -> {entry['to']}")
        lesson["content"] = content
    return report
