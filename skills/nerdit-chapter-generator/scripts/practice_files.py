#!/usr/bin/env python3
"""Build a course practice pack from each chapter's nerdit-files-spec block.

python practice_files.py --course course-x_output.json --world course-x_world.json \
    --course-short ai-apis --version 1 --requirements course-x_requirements.txt --out-dir work
Writes <out-dir>/<course-short>-practice-pack-v<n>.zip (one folder per chapter, README.txt,
requirements.txt), every file singly under <out-dir>/files/, <out-dir>/files.manifest.json, and the
course JSON again under <out-dir>/ with each chapter's files box, the first chapter's pack box and the
"This section uses" lines.
Stdlib only. Names follow the plan's tracing rule: L<nn>-S<section>-<what>.<ext>.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import hashlib
from html import escape
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
EXTENSIONS = {'csv', 'json', 'jsonl', 'sql', 'py', 'ipynb', 'txt', 'md'}  # .xlsx dropped for now (2026-10-24)
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


def row_key(rows: list[dict], wanted: list, key: str | None = None) -> str | None:
    """The column a world source's `rows` ids live in: `key` when given, else the unique-valued
    column (an `_id` one first) holding every wanted id. Generated rows are not in schema order."""
    if key or not rows:
        return key
    unique = [c for c in rows[0] if len({row[c] for row in rows}) == len(rows)]
    unique.sort(key=lambda c: not c.endswith('_id'))
    return next((c for c in unique if set(wanted) <= {row[c] for row in rows}), unique[0] if unique else None)


def _world_slice(source: dict, world: dict) -> str:
    rows = world.get(source['world'])
    if rows is None:
        raise ValueError(f'world has no entity {source["world"]}')
    if 'rows' in source:
        key = row_key(rows, source['rows'], source.get('key'))
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


BOX_START, BOX_END = '<!-- nerdit-files -->', '<!-- /nerdit-files -->'
OLD_BOXES = re.compile(re.escape(BOX_START) + '.*?' + re.escape(BOX_END), re.S)
OLD_USES = re.compile(r'<p class="nerdit-file-use">.*?</p>', re.S)
H2 = re.compile(r'<h2\b[^>]*>(.*?)</h2>', re.S | re.I)


def _size(n: int) -> str:
    return f'{max(1, round(n / 1024))} KB' if n < MIB else f'{n / MIB:.1f} MB'


def _link(name: str, n: int, fmt: str, label: str | None = None, cls: str = 'nerdit-file') -> str:
    return (f'<a class="{cls}" href="files/{escape(name)}" download="{escape(name)}" '
            f'data-nerdit-file="{escape(name)}" data-format="{escape(fmt)}" data-bytes="{n}">'
            f'{escape(label or name)}</a>')


def _used_in(sections) -> str:
    if sections == 'all':
        return 'All sections'
    labels = ['Practice' if s == 'practice' else f'Section {s}' for s in sections or []]
    return ', '.join(labels) or '—'


def mark_lesson(html: str, files: list[dict], folder: str, lesson_id: str, python: str,
                pack: dict | None = None) -> str:
    """The lesson with its files box (and, for the first chapter, the pack box) after its files spec, and a
    "This section uses" line under each numbered section heading. Re-running replaces what an earlier run added."""
    html = OLD_USES.sub('', OLD_BOXES.sub('', html))
    spec = SPEC.search(html)
    if spec is None:
        raise ValueError(f'{lesson_id}: no nerdit-files-spec block to place the files box after')
    py = f'<span class="nerdit-files-py">Python {escape(python)}</span>'
    parts = [BOX_START]
    if pack:
        parts.append(
            '<div class="nerdit-files nerdit-course-pack" data-nerdit-files="course">'
            f'<p class="nerdit-files-head">📦 Course practice pack {py}</p>'
            '<p>Download once, then practise chapter by chapter: one folder per chapter with its data, a starter '
            'notebook and the full solution code, plus the capstone project. Setup steps are in README.txt.</p>'
            + _link(pack['name'], pack['bytes'], 'zip',
                    f'⬇ Download the course practice pack (v{pack["version"]}, {_size(pack["bytes"])})',
                    'nerdit-file nerdit-file-all')
            + f'<p class="nerdit-files-note">{pack["chapters"]} chapter folders · updated {escape(pack["date"])}</p>'
            '</div>')
    rows = ''.join(f'<tr><td>{_link(f["name"], f["bytes"], f["format"])}</td><td>{escape(f.get("about", ""))}</td>'
                   f'<td>{_used_in(f.get("sections"))}</td></tr>' for f in files)
    parts.append(
        f'<div class="nerdit-files" data-nerdit-files="{escape(lesson_id)}">'
        f'<p class="nerdit-files-head">📂 Practice files for this chapter {py}</p>'
        f'<p>In your course practice pack: folder <code>{escape(folder)}</code>.</p>'
        "<details><summary>Download this chapter's files one by one</summary><table>"
        "<thead><tr><th>File</th><th>What's inside</th><th>Used in</th></tr></thead>"
        f'<tbody>{rows}</tbody></table></details></div>')
    parts.append(BOX_END)
    html = html[:spec.end()] + ''.join(parts) + html[spec.end():]

    headings = {}
    for m in H2.finditer(html):
        num = re.match(r'\s*(\d+)(?!\d)', re.sub(r'<[^>]+>', '', m.group(1)))
        if num:
            headings.setdefault(int(num.group(1)), m.end())
    uses: dict[int, list[str]] = {}
    for f in files:
        for s in f.get('sections') if isinstance(f.get('sections'), list) else []:
            if s == 'practice':
                continue
            if s not in headings:
                raise ValueError(f'{f["name"]}: the lesson has no section {s} heading')
            uses.setdefault(headings[s], []).append(
                f'<p class="nerdit-file-use">📎 This section uses {_link(f["name"], f["bytes"], f["format"])} '
                f'(folder <code>{escape(folder)}</code> in your pack).</p>')
    for at in sorted(uses, reverse=True):
        html = html[:at] + ''.join(uses[at]) + html[at:]
    return html


def _readme(pack: str, folders: list[tuple[str, list[dict]]]) -> str:
    lines = [pack, '', 'Setup (once):',
             '  1. python3.14 -m venv .venv',
             '  2. Activate it: .venv\\Scripts\\activate (Windows) or source .venv/bin/activate',
             '  3. pip install -r requirements.txt',
             '', 'Then work chapter by chapter. Open the starter first; check your work in solutions/ after you try.',
             '', 'Course map:']
    for folder, entries in folders:
        lines.append(f'  {folder}/')
        for e in entries:
            if 'capstone' in e:
                lines.append('    README.md, data/, starter/, tests/, solution/'
                             + (f'  ({e["about"]})' if e.get('about') else ''))
            else:
                lines.append(f'    {e["name"]}' + (f'  ({e["about"]})' if e.get('about') else ''))
    return '\n'.join(lines) + '\n'


DATA_SOURCES = {'world', 'json', 'table', 'sql'}


def _arcname(entry: dict, project: bool = False) -> str:
    """Solutions sit in a solutions/ subfolder, so the starter is what a learner opens first.
    In the capstone chapter, data files sit in data/ beside starter/ and solution/."""
    if project and DATA_SOURCES & set(entry['from']):
        return 'data/' + entry['name']
    return ('solutions/' if '-solutions.' in entry['name'] else '') + entry['name']


def _capstone_tree(entry: dict, workdir: Path | None) -> dict[str, bytes]:
    from capstone import build_tree
    if workdir is None:
        raise ValueError('a capstone entry needs the workdir')
    root = Path(workdir).resolve()
    src = (root / entry['capstone']).resolve()
    if not src.is_relative_to(root):
        raise ValueError(f'capstone {entry["capstone"]} is outside the workdir')
    return build_tree(src)


def build_pack(chapters: list[dict], course_short: str, version: int, world: dict | None, requirements: str,
               out_dir: Path, workdir: Path | None = None, image_names: set[str] = frozenset()) -> dict:
    """Build every declared file, the pack zip and the manifest. Raises ValueError on any rule break."""
    out_dir = Path(out_dir)
    pack = f'{course_short}-practice-pack-v{version}'
    seen, problems, folders, built, trees = set(image_names), [], [], [], []
    for position, chapter in enumerate(chapters, 1):
        spec = read_spec(chapter['html'])
        if not spec or not spec.get('files'):
            continue
        folder = chapter_folder(position, chapter['title'])
        files = [e for e in spec['files'] if 'capstone' not in e]
        capstones = [e for e in spec['files'] if 'capstone' in e]
        if len(capstones) > 1:
            problems.append(f'{chapter["id"]}: one capstone entry per chapter')
        for entry in files:
            problems += name_problems(entry['name'], position)
            if entry['name'] in seen:
                problems.append(f'{entry["name"]}: name used twice in the course (images included)')
            seen.add(entry['name'])
        folders.append((folder, spec['files']))
        for entry in files:
            built.append((chapter, folder, entry,
                          build_file(entry, world, workdir, {**chapter, 'position': position}), bool(capstones)))
        for entry in capstones:
            try:
                trees.append((folder, _capstone_tree(entry, workdir)))
            except (OSError, ValueError) as exc:
                problems.append(f'{chapter["id"]}: capstone: {exc}')
    for _, _, entry, data, _ in built:
        if len(data) > FILE_LIMIT:
            problems.append(f'{entry["name"]}: {len(data)} bytes, over the {FILE_LIMIT / MIB:g} MiB file limit')
    if problems:
        raise ValueError('\n'.join(problems))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(f'{pack}/README.txt', _readme(pack, folders))
        z.writestr(f'{pack}/requirements.txt', requirements)
        written = set()
        for _, folder, entry, data, project in built:
            arc = f'{pack}/{folder}/{_arcname(entry, project)}'
            written.add(arc)
            z.writestr(arc, data)
        for folder, tree in trees:
            for rel, data in tree.items():
                arc = f'{pack}/{folder}/{rel}'
                if arc not in written:  # the spec's world files win over a draft copy in data/
                    z.writestr(arc, data)
    if buf.tell() > PACK_LIMIT:
        raise ValueError(f'{pack}.zip: {buf.tell()} bytes, over the {PACK_LIMIT / MIB:g} MiB pack limit')

    files_dir = out_dir / 'files'
    files_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f'{pack}.zip').write_bytes(buf.getvalue())
    manifest = []
    for chapter, folder, entry, data, _ in built:
        (files_dir / entry['name']).write_bytes(data)
        manifest.append({'name': entry['name'], 'format': entry['name'].rpartition('.')[2], 'bytes': len(data),
                         'sha256': hashlib.sha256(data).hexdigest(), 'lessonId': chapter['id'], 'folder': folder,
                         'sections': entry.get('sections', []), 'about': entry.get('about', ''),
                         'source': entry['from'], 'packVersion': version})
    result = {'pack': f'{pack}.zip', 'packBytes': buf.tell(), 'files': manifest}
    (out_dir / 'files.manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                                 encoding='utf-8')
    return result


def mark_course(chapters: list[dict], result: dict, date: str, python: str | None = None) -> list[str]:
    """Every chapter's HTML with its boxes; the first chapter with files also carries the pack box.
    `python` is the version check_files.py --as-learner passed on; without it each spec's own is shown."""
    by_lesson: dict[str, list[dict]] = {}
    for f in result['files']:
        by_lesson.setdefault(f['lessonId'], []).append(f)
    version = result['files'][0]['packVersion'] if result['files'] else 1
    pack = {'name': result['pack'], 'bytes': result['packBytes'], 'version': version,
            'chapters': len(by_lesson), 'date': date}
    out = []
    for chapter in chapters:
        files = by_lesson.get(chapter['id'])
        if not files:
            out.append(chapter['html'])
            continue
        shown = python or (read_spec(chapter['html']) or {}).get('python', '3.12')
        out.append(mark_lesson(chapter['html'], files, files[0]['folder'], chapter['id'], shown, pack))
        pack = None
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--course', required=True, help='the course output JSON')
    ap.add_argument('--world', help='world data JSON (world_data.json from make_world_data.py)')
    ap.add_argument('--course-short', required=True)
    ap.add_argument('--version', type=int, default=1)
    ap.add_argument('--requirements', help='course-<chapter>_requirements.txt')
    ap.add_argument('--workdir', help='folder that file sources are read from')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--python', help='the version check_files.py --as-learner passed on (shown in every box)')
    args = ap.parse_args()
    try:
        course = json.loads(Path(args.course).read_text(encoding='utf-8'))
        lessons = course['lessons']
        chapters = [{'id': les['id'], 'title': les['title'], 'html': les.get('content', '')} for les in lessons]
        world = json.loads(Path(args.world).read_text(encoding='utf-8')) if args.world else None
        reqs = Path(args.requirements).read_text(encoding='utf-8') if args.requirements else ''
        result = build_pack(chapters, args.course_short, args.version, world, reqs, Path(args.out_dir),
                            Path(args.workdir) if args.workdir else None)
        for lesson, html in zip(lessons, mark_course(chapters, result, date.today().strftime('%d %b %Y'), args.python)):
            lesson['content'] = html
        marked = Path(args.out_dir) / Path(args.course).name
        marked.write_text(json.dumps(course, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    largest = max(result['files'], key=lambda f: f['bytes'], default=None)
    print(f'Built {result["pack"]}: {len(result["files"])} files, {result["packBytes"] / MIB:.2f} MiB zipped'
          + (f'; largest {largest["name"]} {largest["bytes"] / MIB:.2f} MiB' if largest else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
