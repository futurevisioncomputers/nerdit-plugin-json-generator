#!/usr/bin/env python3
"""Build a course practice pack from each chapter's nerdit-files-spec block.

python practice_files.py --course course-x_output.json --world course-x_world.json \
    --course-short ai-apis --version 1 --requirements course-x_requirements.txt --out-dir work
Writes <out-dir>/<course-short>-practice-pack-v<n>.zip (one folder per chapter, README.txt,
requirements.txt), every file singly under <out-dir>/files/, and <out-dir>/files.manifest.json.
Stdlib only. Names follow the plan's tracing rule: L<nn>-S<section>-<what>.<ext>.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

CORE = Path(__file__).resolve().parent.parent / 'references' / 'nerdit_world_gen.py'
if str(CORE.parent) not in sys.path:
    sys.path.append(str(CORE.parent))
from nerdit_world_gen import to_csv  # noqa: E402

SPEC = re.compile(r'<script\b[^>]*\bclass="[^"]*\bnerdit-files-spec\b[^"]*"[^>]*>(.*?)</script>', re.S | re.I)
EXTENSIONS = {'csv', 'xlsx', 'json', 'jsonl', 'sql', 'py', 'ipynb', 'txt', 'md'}
MAX_NAME = 60
FILE_LIMIT = 5 * 1024 * 1024
PACK_LIMIT = 10 * 1024 * 1024


def read_spec(html: str) -> dict | None:
    """A chapter's files spec, or None when the chapter declares no files."""
    blocks = SPEC.findall(html)
    if not blocks:
        return None
    if len(blocks) > 1:
        raise ValueError(f'expected one nerdit-files-spec block, found {len(blocks)}')
    return json.loads(blocks[0])


def name_problems(name: str, position: int) -> list[str]:
    """Why a file name breaks the tracing rule; empty when it is fine."""
    problems = []
    prefix = f'L{position:02d}-'
    if not name.startswith(prefix):
        problems.append(f'{name}: must start with {prefix} (the chapter position)')
    stem, _, ext = name.rpartition('.')
    if ext not in EXTENSIONS:
        problems.append(f'{name}: extension .{ext} not allowed')
    if not re.fullmatch(r'L\d{2}(?:-S\d+)?(?:-[a-z0-9]+)+', stem):
        problems.append(f'{name}: lower case a-z, digits and hyphens only')
    if len(name) > MAX_NAME:
        problems.append(f'{name}: longer than {MAX_NAME} characters')
    return problems


def chapter_folder(position: int, title: str) -> str:
    """L<nn>-<title slug>, at most 60 characters, cut at a hyphen."""
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    folder = f'L{position:02d}-{slug}'
    if len(folder) > MAX_NAME:
        folder = folder[:MAX_NAME].rsplit('-', 1)[0]
    return folder


def _world_slice(source: dict, world: dict) -> str:
    rows = world.get(source['world'])
    if rows is None:
        raise ValueError(f'world has no entity {source["world"]}')
    if 'rows' in source:
        key = next(iter(rows[0])) if rows else None
        by_id = {row[key]: row for row in rows}
        missing = [r for r in source['rows'] if r not in by_id]
        if missing:
            raise ValueError(f'{source["world"]}: no rows {", ".join(missing)}')
        rows = [by_id[r] for r in source['rows']]
    columns = source.get('columns') or (list(rows[0]) if rows else [])
    return to_csv(rows, columns)


def build_file(entry: dict, world: dict | None = None, workdir: Path | None = None) -> bytes:
    """The bytes of one declared file, from its `from` source."""
    source, name = entry['from'], entry['name']
    if 'world' in source:
        if world is None:
            raise ValueError(f'{name}: a world source needs the course world data')
        return _world_slice(source, world).encode('utf-8')
    if 'json' in source:
        if name.endswith('.jsonl'):
            return ''.join(json.dumps(item, ensure_ascii=False) + '\n' for item in source['json']).encode('utf-8')
        return (json.dumps(source['json'], ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if 'file' in source:
        if workdir is None:
            raise ValueError(f'{name}: a file source needs the workdir')
        root = Path(workdir).resolve()
        path = (root / source['file']).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f'{name}: {source["file"]} is outside the workdir')
        return path.read_bytes()
    raise ValueError(f'{name}: unsupported source {sorted(source)}')


def _readme(pack: str, folders: list[tuple[str, list[dict]]]) -> str:
    lines = [pack, '', 'Setup (once):',
             '  1. python3.14 -m venv .venv',
             '  2. Activate it: .venv\\Scripts\\activate (Windows) or source .venv/bin/activate',
             '  3. pip install -r requirements.txt',
             '', 'Then work chapter by chapter. Open the starter first; check your work in solutions/ after you try.',
             '', 'Course map:']
    for folder, entries in folders:
        lines.append(f'  {folder}/')
        lines += [f'    {e["name"]}' + (f'  ({e["about"]})' if e.get('about') else '') for e in entries]
    return '\n'.join(lines) + '\n'


def _arcname(entry: dict) -> str:
    """Solutions sit in a solutions/ subfolder, so the starter is what a learner opens first."""
    return ('solutions/' if '-solutions.' in entry['name'] else '') + entry['name']


def build_pack(chapters: list[dict], course_short: str, version: int, world: dict | None, requirements: str,
               out_dir: Path, workdir: Path | None = None, image_names: set[str] = frozenset()) -> dict:
    """Build every declared file, the pack zip and the manifest. Raises ValueError on any rule break."""
    out_dir = Path(out_dir)
    pack = f'{course_short}-practice-pack-v{version}'
    seen, problems, folders, built = set(image_names), [], [], []
    for position, chapter in enumerate(chapters, 1):
        spec = read_spec(chapter['html'])
        if not spec or not spec.get('files'):
            continue
        folder = chapter_folder(position, chapter['title'])
        for entry in spec['files']:
            problems += name_problems(entry['name'], position)
            if entry['name'] in seen:
                problems.append(f'{entry["name"]}: name used twice in the course (images included)')
            seen.add(entry['name'])
        folders.append((folder, spec['files']))
        for entry in spec['files']:
            built.append((chapter, folder, entry, build_file(entry, world, workdir)))
    for _, _, entry, data in built:
        if len(data) > FILE_LIMIT:
            problems.append(f'{entry["name"]}: {len(data)} bytes, over the 5 MiB file limit')
    if problems:
        raise ValueError('\n'.join(problems))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(f'{pack}/README.txt', _readme(pack, folders))
        z.writestr(f'{pack}/requirements.txt', requirements)
        for _, folder, entry, data in built:
            z.writestr(f'{pack}/{folder}/{_arcname(entry)}', data)
    if buf.tell() > PACK_LIMIT:
        raise ValueError(f'{pack}.zip: {buf.tell()} bytes, over the 10 MiB pack limit')

    files_dir = out_dir / 'files'
    files_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f'{pack}.zip').write_bytes(buf.getvalue())
    manifest = []
    for chapter, folder, entry, data in built:
        (files_dir / entry['name']).write_bytes(data)
        manifest.append({'name': entry['name'], 'format': entry['name'].rpartition('.')[2], 'bytes': len(data),
                         'sha256': hashlib.sha256(data).hexdigest(), 'lessonId': chapter['id'], 'folder': folder,
                         'sections': entry.get('sections', []), 'about': entry.get('about', ''),
                         'source': entry['from'], 'packVersion': version})
    result = {'pack': f'{pack}.zip', 'packBytes': buf.tell(), 'files': manifest}
    (out_dir / 'files.manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                                 encoding='utf-8')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--course', required=True, help='the course output JSON')
    ap.add_argument('--world', help='world data JSON (world_data.json from make_world_data.py)')
    ap.add_argument('--course-short', required=True)
    ap.add_argument('--version', type=int, default=1)
    ap.add_argument('--requirements', help='course-<chapter>_requirements.txt')
    ap.add_argument('--workdir', help='folder that file sources are read from')
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    try:
        course = json.loads(Path(args.course).read_text(encoding='utf-8'))
        lessons = course['lessons']
        chapters = [{'id': les['id'], 'title': les['title'], 'html': les.get('content', '')} for les in lessons]
        world = json.loads(Path(args.world).read_text(encoding='utf-8')) if args.world else None
        reqs = Path(args.requirements).read_text(encoding='utf-8') if args.requirements else ''
        result = build_pack(chapters, args.course_short, args.version, world, reqs, Path(args.out_dir),
                            Path(args.workdir) if args.workdir else None)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    print(f'Built {result["pack"]}: {len(result["files"])} files, {result["packBytes"]} bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
