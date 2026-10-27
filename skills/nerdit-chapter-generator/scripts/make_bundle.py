#!/usr/bin/env python3
"""Write the one course bundle the admin imports (plan §10).

    python make_bundle.py --course <pack>/course-<chapter>_output.json --pack <workdir>/pack \
        --images <images folder> --slug <course-slug> --version <n> --out-dir <folder>

<slug>-bundle-v<n>.zip holds:
  course-<chapter>_output.json   the final course JSON (with its files boxes)
  media/images/                  every raster in <images>/upload/
  media/files/                   the practice pack zip and every single file from <pack>/files/
  videos/clips.json              one entry per clip, MP4 name dropped, an empty "youtube" link to fill
  videos/description.txt, videos/thumbnail.jpg   when the story video was built
  bundle.json                    course id, versions and the sha256 and size of every file
MP4s are never included: videos stay on YouTube. Every image and files/ link a lesson makes
must have its file, or nothing is written. check_bundle.py runs on the result.
Exit 0 = written and checked; 1 = the check failed; 2 = a missing file or link. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import zipfile

from check_bundle import check, entry, links


def _clips(path: Path) -> bytes:
    clips = json.loads(path.read_text(encoding='utf-8'))
    out = []
    for clip in clips:
        clip = {k: v for k, v in clip.items() if k != 'file'}
        clip.setdefault('youtube', '')
        out.append(clip)
    return (json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def make_bundle(course_path: Path, pack: Path, images: Path | None, out_dir: Path, slug: str, version: int) -> Path:
    course_path, pack = Path(course_path), Path(pack)
    course = json.loads(course_path.read_text(encoding='utf-8'))
    # A placed course (….with-images.with-video.json) goes in under its plain name.
    name = re.sub(r'(\.with-[a-z]+)+\.json$', '.json', course_path.name)
    members: dict[str, bytes] = {name: course_path.read_bytes()}
    upload = Path(images) / 'upload' if images else None
    if upload and upload.is_dir():
        for p in sorted(upload.iterdir()):
            if p.is_file():
                members[f'media/images/{p.name}'] = p.read_bytes()
    manifest = json.loads((pack / 'files.manifest.json').read_text(encoding='utf-8')) \
        if (pack / 'files.manifest.json').is_file() else {'pack': None, 'files': []}
    if manifest.get('pack'):
        members[f'media/files/{manifest["pack"]}'] = (pack / manifest['pack']).read_bytes()
    if (pack / 'files').is_dir():
        for p in sorted((pack / 'files').iterdir()):
            if p.is_file():
                members[f'media/files/{p.name}'] = p.read_bytes()
    video = Path(images) / 'video' if images else None
    if video and (video / 'clips.json').is_file():
        members['videos/clips.json'] = _clips(video / 'clips.json')
        for name in ('description.txt', 'thumbnail.jpg'):
            if (video / name).is_file():
                members[f'videos/{name}'] = (video / name).read_bytes()

    have_images = {n.rsplit('/', 1)[-1] for n in members if n.startswith('media/images/')}
    have_files = {n.rsplit('/', 1)[-1] for n in members if n.startswith('media/files/')}
    linked_images, linked_files = links(course)
    missing = sorted(linked_images - have_images) + [f'files/{n}' for n in sorted(linked_files - have_files)]
    if missing:
        raise ValueError('lessons link files the bundle would not hold: ' + ', '.join(missing))

    packs = manifest.get('files') or [{}]
    meta = {'courseId': course.get('id') or slug, 'bundleVersion': version,
            'packVersion': packs[0].get('packVersion'), 'course': course_path.name,
            'files': {name: entry(data) for name, data in sorted(members.items())}}
    out = Path(out_dir) / f'{slug}-bundle-v{version}.zip'
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(members.items()):
            z.writestr(name, data)
        z.writestr('bundle.json', json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--course', required=True)
    ap.add_argument('--pack', required=True)
    ap.add_argument('--images')
    ap.add_argument('--slug', required=True)
    ap.add_argument('--version', type=int, default=1)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args(argv)
    try:
        out = make_bundle(Path(args.course), Path(args.pack), Path(args.images) if args.images else None,
                          Path(args.out_dir), args.slug, args.version)
        fails, warns = check(out)
    except (OSError, ValueError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    for f in fails:
        print(f'FAIL {f}')
    for w in warns:
        print(f'WARN {w}')
    print(f'Wrote {out} ({out.stat().st_size} bytes)' + ('' if not fails else f'; {len(fails)} problem(s)'))
    return 1 if fails else 0


if __name__ == '__main__':
    raise SystemExit(main())
