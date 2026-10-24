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
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import textwrap
import zipfile

CORE = Path(__file__).resolve().parent.parent / 'references' / 'nerdit_world_gen.py'
if str(CORE.parent) not in sys.path:
    sys.path.append(str(CORE.parent))
from nerdit_world_gen import to_csv  # noqa: E402
from check_python_outputs import _code, _first, _in_order, _is_python  # noqa: E402
from verify_course import parse, text_of  # noqa: E402

SPEC = re.compile(r'<script\b[^>]*\bclass="[^"]*\bnerdit-files-spec\b[^"]*"[^>]*>(.*?)</script>', re.S | re.I)
EXTENSIONS = {'csv', 'xlsx', 'json', 'jsonl', 'sql', 'py', 'ipynb', 'txt', 'md'}
MAX_NAME = 60
# Measuring phase (owner, 2026-10-24): 50 MiB to see what real courses weigh; to be lowered later.
FILE_LIMIT = 50 * 1024 * 1024
PACK_LIMIT = 50 * 1024 * 1024
MIB = 1024 * 1024


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


def _squash(text: str) -> str:
    return ' '.join(text.split())


def _inside(node, cls: str) -> bool:
    while node is not None:
        if cls in node.classes:
            return True
        node = node.parent
    return False


def practice_tasks(html: str) -> list[dict]:
    """Each nerdit-task's prompt (its text outside the solution) and its Python solution, in page order."""
    tasks = []
    for node in parse(html).all:
        if 'nerdit-task' not in node.classes:
            continue
        prompt = ''.join(text_of(c) if not isinstance(c, str) else c
                         for c in node.content if isinstance(c, str) or c.tag != 'details')
        sol = _first(node, lambda n: n.tag == 'pre' and _is_python(n) and _inside(n, 'nerdit-solution'))
        tasks.append({'task': _squash(prompt), 'solution': _code(sol).strip('\n') if sol is not None else None})
    return tasks


def page_examples(html: str) -> list[tuple[str, str]]:
    """(section heading, code) for every Python run line, in page order: the examples learners read."""
    heading, out = '', []
    for node in parse(html).all:
        if node.tag == 'h2':
            heading = _squash(text_of(node))
        elif 'nerdit-run' in node.classes:
            half = _first(node, lambda n: 'nerdit-in' in n.classes)
            pre = half and _first(half, lambda n: n.tag == 'pre' and _is_python(n))
            if pre is not None:
                out.append((heading, _code(pre).strip('\n')))
    return out


# Downloaded .py files find their chapter's files wherever they run; solutions/ reads from its parent.
PY_PRELUDE = ('import os\nfrom pathlib import Path\n\n'
              'HERE = Path(__file__).resolve().parent\n'
              "os.chdir(HERE.parent if HERE.name == 'solutions' else HERE)  # this chapter's files\n")
# Notebooks open in their own folder; the solutions notebook steps up to the chapter folder once.
NB_PRELUDE = "import os\nif os.path.basename(os.getcwd()) == 'solutions':\n    os.chdir('..')  # this chapter's files\n"


def _comment(text: str) -> str:
    return '\n'.join('# ' + line for line in textwrap.wrap(text, 100)) or '#'


def _notebook(cells: list[tuple[str, str]]) -> bytes:
    def cell(kind, text):
        lines = text.splitlines(keepends=True)
        if kind == 'markdown':
            return {'cell_type': 'markdown', 'metadata': {}, 'source': lines}
        return {'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [], 'source': lines}
    nb = {'cells': [cell(k, t) for k, t in cells], 'nbformat': 4, 'nbformat_minor': 4,
          'metadata': {'kernelspec': {'name': 'python3', 'display_name': 'Python 3', 'language': 'python'},
                       'language_info': {'name': 'python'}}}
    return (json.dumps(nb, ensure_ascii=False, indent=1) + '\n').encode('utf-8')


def _practice_file(name: str, chapter: dict, solutions: bool) -> bytes:
    position, title, html = chapter['position'], chapter['title'], chapter['html']
    tasks = practice_tasks(html)
    tag = f'L{position:02d}'
    if solutions:
        intro = (f'{tag} solutions: {title}. Every example on the page in order, then every practice answer. '
                 'Check your work here after you try.')
        parts = [('code', f'# {s}\n{code}' if s else code) for s, code in page_examples(html)]
        parts += [('task', t) for t in tasks]
    else:
        intro = f'{tag} practice starter: {title}. Open this first; check your work in solutions/ after you try.'
        parts = [('task', t) for t in tasks]
    if name.endswith('.ipynb'):
        cells = [('markdown', f'# {intro}')]
        if solutions:
            cells.append(('code', NB_PRELUDE))
        for kind, item in parts:
            if kind == 'code':
                cells.append(('code', item))
            else:
                cells.append(('markdown', f'**{item["task"]}**'))
                cells.append(('code', (item['solution'] or '') if solutions else ''))
        return _notebook(cells)
    blocks = [_comment(intro) + '\n' + PY_PRELUDE]
    for kind, item in parts:
        if kind == 'code':
            blocks.append(item)
        else:
            body = (item['solution'] or '# (no Python solution on the page)') if solutions else '# Your code here'
            blocks.append(_comment(item['task']) + '\n' + body)
    return ('\n\n\n'.join(blocks) + '\n').encode('utf-8')


def _table_csv(label: str, html: str) -> str:
    """The lesson table whose caption or figcaption reads `label`, as CSV."""
    tree = parse(html)
    for node in tree.all:
        if node.tag not in ('caption', 'figcaption') or _squash(text_of(node)) != _squash(label):
            continue
        holder = node.parent  # <table> for a caption, the figure for a figcaption
        table = holder if holder.tag == 'table' else _first(holder, lambda n: n.tag == 'table')
        if table is None:
            break
        rows = [[_squash(text_of(c)) for c in _in_order(tr) if c.tag in ('th', 'td')]
                for tr in _in_order(table) if tr.tag == 'tr']
        buf = io.StringIO()
        csv.writer(buf, lineterminator='\n').writerows(rows)
        return buf.getvalue()
    raise ValueError(f'no table captioned {label!r} in the lesson')


def _seed_sql(seed_id: str, chapter: dict, sections) -> str:
    tree = parse(chapter['html'])
    block = next((n for n in tree.all if n.tag == 'script' and n.el_id == seed_id), None)
    if block is None:
        raise ValueError(f'no seed script with id {seed_id!r} in the lesson')
    body = ''.join(c for c in block.content if isinstance(c, str)).lstrip('\n')
    tables = ', '.join(dict.fromkeys(re.findall(r'CREATE TABLE\s+"?(\w+)', body, re.I))) or 'none'
    where = f', section {", ".join(map(str, sections))}' if isinstance(sections, list) and sections else ''
    return f'-- L{chapter["position"]:02d} {chapter["title"]}{where}: tables {tables}\n{body}'


def build_file(entry: dict, world: dict | None = None, workdir: Path | None = None,
               chapter: dict | None = None) -> bytes:
    """The bytes of one declared file, from its `from` source."""
    source, name = entry['from'], entry['name']
    lesson_sources = {'practice', 'solutions', 'table', 'sql'} & set(source)
    if lesson_sources and chapter is None:
        raise ValueError(f'{name}: a {next(iter(lesson_sources))} source needs its chapter')
    if 'practice' in source or 'solutions' in source:
        return _practice_file(name, chapter, solutions='solutions' in source)
    if 'table' in source:
        return _table_csv(source['table'], chapter['html']).encode('utf-8')
    if 'sql' in source:
        return _seed_sql(source['sql'], chapter, entry.get('sections')).encode('utf-8')
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
            built.append((chapter, folder, entry,
                          build_file(entry, world, workdir, {**chapter, 'position': position})))
    for _, _, entry, data in built:
        if len(data) > FILE_LIMIT:
            problems.append(f'{entry["name"]}: {len(data)} bytes, over the {FILE_LIMIT / MIB:g} MiB file limit')
    if problems:
        raise ValueError('\n'.join(problems))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(f'{pack}/README.txt', _readme(pack, folders))
        z.writestr(f'{pack}/requirements.txt', requirements)
        for _, folder, entry, data in built:
            z.writestr(f'{pack}/{folder}/{_arcname(entry)}', data)
    if buf.tell() > PACK_LIMIT:
        raise ValueError(f'{pack}.zip: {buf.tell()} bytes, over the {PACK_LIMIT / MIB:g} MiB pack limit')

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
    largest = max(result['files'], key=lambda f: f['bytes'], default=None)
    print(f'Built {result["pack"]}: {len(result["files"])} files, {result["packBytes"] / MIB:.2f} MiB zipped'
          + (f'; largest {largest["name"]} {largest["bytes"] / MIB:.2f} MiB' if largest else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
