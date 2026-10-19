#!/usr/bin/env python3
"""Generate reproducible, synthetic teaching records from a declarative world.

python make_world_data.py --world course-x_world.json --out-dir work
python make_world_data.py --recipe x-01.html --out-dir work   (a lesson's dataset block, or recipe.json)
Stdlib only. No expressions, imports, network access or executable generators.
The generation rules live in references/nerdit_world_gen.py, shared with the website's
Python runners; this script adds file I/O and library references.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

LIBRARY = Path(__file__).resolve().parent.parent / 'references' / 'worlds'
CORE = Path(__file__).resolve().parent.parent / 'references' / 'nerdit_world_gen.py'
if str(CORE.parent) not in sys.path:
    sys.path.append(str(CORE.parent))
from nerdit_world_gen import (GENERATORS, IDENT, PRIVATE, build_files, entity_columns,  # noqa: E402,F401
                              generate, to_csv, validate_world)

DATASET = re.compile(r'<script\b[^>]*\bclass="[^"]*\bnerdit-dataset\b[^"]*"[^>]*>(.*?)</script>', re.S | re.I)


def load_world(path: Path, library: Path = LIBRARY) -> dict:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(data, dict) and 'use' in data:
        slug = data['use']
        if set(data) != {'use'} or not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
            raise ValueError('world reference must contain only a safe library slug in use')
        data = json.loads((library / f'{slug}.world.json').read_text(encoding='utf-8'))
    validate_world(data)
    return data


def load_recipe(path: Path) -> dict:
    """A lesson's dataset recipe: a recipe .json file, or the nerdit-dataset block of a lesson .html."""
    text = Path(path).read_text(encoding='utf-8')
    if Path(path).suffix.lower() in ('.html', '.htm'):
        blocks = DATASET.findall(text)
        if len(blocks) != 1:
            raise ValueError(f'{path}: expected one nerdit-dataset block, found {len(blocks)}')
        text = blocks[0]
    return json.loads(text)


def write_recipe(recipe: dict, out: Path) -> int:
    """The recipe's CSV files exactly as the browser builds them, plus their defect manifest."""
    manifest = {}
    files = build_files(recipe, manifest)
    out.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (out / name).write_text(text, encoding='utf-8', newline='')
    (out / 'world_data.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return sum(text.count('\n') - 1 for text in files.values())


def sql_dump(data: dict, world: dict | None = None) -> str:
    def literal(value):
        if value is None:
            return 'NULL'
        return str(value) if type(value) in (int, float) else "'" + str(value).replace("'", "''") + "'"
    lines = ['-- Synthetic teaching data. No real customer or staff records.', 'BEGIN;']
    for table, rows in data.items():
        if not rows:
            if world is None:
                raise ValueError('empty entities require their world schema for SQL export')
            entity = world['entities'][table]
            # Tables keep their historical sorted order; series and interactions have fixed columns.
            cols = sorted(entity['columns']) if 'columns' in entity else entity_columns(entity)
            lines.append(f'CREATE TABLE "{table}" (' + ', '.join(f'"{c}"' for c in cols) + ');')
            continue
        cols = list(rows[0])
        # No SQLite affinity: retain literal storage types in mixed raw-data columns.
        defs = ', '.join(f'"{c}"' for c in cols)
        lines.append(f'CREATE TABLE "{table}" ({defs});')
        for row in rows:
            lines.append(f'INSERT INTO "{table}" VALUES (' + ', '.join(literal(row[c]) for c in cols) + ');')
    return '\n'.join(lines + ['COMMIT;', ''])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument('--world')
    source.add_argument('--recipe', help="a lesson's dataset block (.html) or recipe (.json): built with the recipe's seed")
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    if args.recipe:
        try:
            rows = write_recipe(load_recipe(Path(args.recipe)), Path(args.out_dir))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'ERROR: {exc}', file=sys.stderr)
            return 2
        print(f'Built {rows} synthetic rows from the recipe')
        return 0
    try:
        world = load_world(Path(args.world))
        manifest = {}
        data = generate(world, manifest)
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / 'world_data.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (out / 'world_data.sql').write_text(sql_dump(data, world), encoding='utf-8')
        (out / 'world_data.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        for name, entity in world['entities'].items():
            if entity.get('profile', world.get('profile', 'sql')) == 'analytics':
                # newline='': LF bytes on every OS, the same file the browser builds.
                (out / f'{name}.csv').write_text(to_csv(data[name], entity_columns(entity)),
                                                 encoding='utf-8', newline='')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    print(f'Generated {sum(map(len, data.values()))} synthetic rows in {len(data)} tables')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
