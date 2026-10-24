#!/usr/bin/env python3
"""Check a course bundle before the admin imports it (plan §10).

    python check_bundle.py --bundle <slug>-bundle-v<n>.zip

Fails when: bundle.json is missing, lists a file the zip lacks, misses one it has, or a
sha256 / size differs; there is not exactly one course JSON at the top; a media file has a
type outside the allowed lists or content that does not match it (a .zip that is not a zip,
text that is not UTF-8, JSON that does not parse); a file or pack is over its size limit; two
media files share a name; a lesson links an image or files/ download the bundle does not
hold; a video file is inside (videos stay on YouTube); the bundle is over 100 MiB.
An image or file no lesson links is a warning: the admin adds it to the course library.
Exit 0 = pass; 1 = a problem; 2 = the bundle cannot be read. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

import practice_files as pf

BUNDLE_LIMIT = 100 * 1024 * 1024
IMAGE_TYPES = {'webp', 'png', 'jpg', 'jpeg', 'gif', 'svg'}
FILE_TYPES = pf.EXTENSIONS | {'zip'}
VIDEO_FILES = {'videos/clips.json', 'videos/description.txt', 'videos/thumbnail.jpg'}
VIDEO_TYPES = {'mp4', 'mov', 'webm', 'mkv', 'avi'}
IMG_SRC = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"', re.I)
FILE_HREF = re.compile(r'href="files/([^"]+)"')
TEXT_TYPES = {'csv', 'json', 'jsonl', 'sql', 'py', 'ipynb', 'txt', 'md'}


def entry(data: bytes) -> dict:
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def links(course: dict) -> tuple[set[str], set[str]]:
    """(image names, files/ names) the lessons link; remote and data: images are not bundle files."""
    images, files = set(), set()
    for lesson in course.get('lessons', []):
        html = lesson.get('content', '')
        for src in IMG_SRC.findall(html):
            if not re.match(r'(?i)(https?:|data:|//|/)', src):
                images.add(src.rsplit('/', 1)[-1])
        files |= set(FILE_HREF.findall(html))
    return images, files


def _content_problem(name: str, data: bytes) -> str | None:
    ext = name.rpartition('.')[2].lower()
    if ext == 'zip':
        return None if data[:4] == b'PK\x03\x04' else f'{name}: not a zip file'
    if ext in TEXT_TYPES:
        try:
            text = data.decode('utf-8')
            if ext in ('json', 'ipynb'):
                json.loads(text)
            elif ext == 'jsonl':
                [json.loads(line) for line in text.splitlines() if line.strip()]
        except (UnicodeDecodeError, ValueError) as exc:
            return f'{name}: content does not match .{ext} ({type(exc).__name__})'
    return None


def check(path: Path) -> tuple[list[str], list[str]]:
    fails, warns = [], []
    path = Path(path)
    if path.stat().st_size > BUNDLE_LIMIT:
        fails.append(f'{path.name}: {path.stat().st_size} bytes, over the 100 MiB bundle limit')
    with zipfile.ZipFile(path) as z:
        members = {n: z.read(n) for n in z.namelist() if not n.endswith('/')}
    if 'bundle.json' not in members:
        return fails + ['bundle.json is missing'], warns
    listed = json.loads(members['bundle.json']).get('files', {})
    for name, data in members.items():
        if name == 'bundle.json':
            continue
        if name not in listed:
            fails.append(f'{name}: in the bundle but not listed in bundle.json')
        elif listed[name] != entry(data):
            fails.append(f'{name}: sha256 or size differs from bundle.json')
    fails += [f'{name}: listed in bundle.json but not in the bundle' for name in listed if name not in members]

    courses = [n for n in members if '/' not in n and n.endswith('_output.json')]
    if len(courses) != 1:
        return fails + [f'expected one course JSON at the top, found {len(courses)}'], warns
    course = json.loads(members[courses[0]])
    seen: dict[str, str] = {}
    for name, data in members.items():
        ext = name.rpartition('.')[2].lower()
        if ext in VIDEO_TYPES:
            fails.append(f'{name}: videos stay on YouTube; never put a video file in the bundle')
        elif name.startswith('media/files/'):
            if ext not in FILE_TYPES:
                fails.append(f'{name}: type .{ext} not allowed (allowed: {", ".join(sorted(FILE_TYPES))})')
            limit = pf.PACK_LIMIT if re.search(r'-(practice|data)-pack-v\d+\.zip$', name) else pf.FILE_LIMIT
            if len(data) > limit:
                fails.append(f'{name}: {len(data)} bytes, over its {limit // pf.MIB} MiB limit')
            bad = _content_problem(name, data)
            if bad:
                fails.append(bad)
        elif name.startswith('media/images/'):
            if ext not in IMAGE_TYPES:
                fails.append(f'{name}: type .{ext} is not an image type')
        elif name not in VIDEO_FILES and name not in ('bundle.json', courses[0]):
            fails.append(f'{name}: not part of the bundle layout (media/images, media/files, videos)')
        if name.startswith('media/'):
            base = name.rsplit('/', 1)[-1]
            if base in seen:
                fails.append(f'{base}: two media files share this name ({seen[base]}, {name})')
            seen.setdefault(base, name)

    images = {n.rsplit('/', 1)[-1] for n in members if n.startswith('media/images/')}
    files = {n.rsplit('/', 1)[-1] for n in members if n.startswith('media/files/')}
    linked_images, linked_files = links(course)
    fails += [f'image {n}: a lesson links it but it is not in the bundle' for n in sorted(linked_images - images)]
    fails += [f'files/{n}: a lesson links it but it is not in the bundle' for n in sorted(linked_files - files)]
    warns += [f'{n}: no lesson links it (it joins the course library)' for n in sorted((images - linked_images)
                                                                                      | (files - linked_files))]
    return fails, warns


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bundle', required=True)
    args = ap.parse_args(argv)
    try:
        fails, warns = check(Path(args.bundle))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    for f in fails:
        print(f'FAIL {f}')
    for w in warns:
        print(f'WARN {w}')
    print(f'BUNDLE: {len(fails)} problem(s)')
    return 1 if fails else 0


if __name__ == '__main__':
    raise SystemExit(main())
