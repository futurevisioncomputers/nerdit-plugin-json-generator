#!/usr/bin/env python3
"""Check a course's SQL seed slices and bound figure cells against its synthetic world.

python check_world.py --world course-x_world.json --course course-x_output.json
Defects: -- defect: orders row 1 amount_text "12x"
The value is JSON; row is the one-based seed/table row, not a business ID.
Derived result figures must say data-world-derived="query or arithmetic reason";
their computed values are checked by SQL output checks and QA, not domain membership.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re
import sqlite3
import sys

from make_world_data import generate, load_world
from verify_course import parse, text_of

DEFECT = re.compile(r'^\s*--\s*defect:\s+(\w+)\s+row\s+(\d+)\s+(\w+)\s+(.+?)\s*$', re.M)


def walk(node):
    """Descendants in document order (column and row positions are meaningful)."""
    stack = list(reversed(node.children))
    while stack:
        child = stack.pop()
        yield child
        stack.extend(reversed(child.children))


def _value(value):
    return 'NULL' if value is None else str(value)


def check_lesson(content: str, world: dict, data: dict) -> tuple[list[str], list[str]]:
    tree = parse(content)
    fails, warns = [], []
    first_table = next((i for i, n in enumerate(tree.all) if n.tag == 'table'), len(tree.all))
    notes = [text_of(n).casefold() for n in tree.all[:first_table] if 'nerdit-data-note' in n.classes]
    real = world['business'].get('fictional') is not True
    if not any('synthetic' in n and 'records' in n and (not real or 'permission' in n) for n in notes):
        fails.append('first data table needs a synthetic-records disclosure' + (' and business-name permission notice' if real else ''))
    if world.get('stages') and not any(n.attrs.get('data-visual') == 'course-map' for n in tree.all):
        warns.append('world defines stages but lesson has no course-map')
    domains = {}
    for entity, rows in data.items():
        for row in rows:
            for column, value in row.items():
                domains.setdefault((entity, column), set()).add(_value(value))
    allowed = {}
    seed_text = '\n'.join(text_of(n) for n in tree.all if n.tag == 'script' and n.attrs.get('type') == 'text/plain')
    for match in DEFECT.finditer(seed_text):
        entity, row, column, value = match.groups()
        try:
            value = json.loads(html.unescape(value))
            if type(value) not in (str, int, float) and value is not None:
                raise ValueError('value must be a scalar')
            if entity not in world['entities'] or column not in world['messiness'] or int(row) < 1:
                raise ValueError('entity, row or permitted defect column is invalid')
            allowed.setdefault((entity, int(row), column), set()).add(_value(value))
        except ValueError as exc:
            fails.append(f'invalid defect declaration: {exc}')

    def check_cell(entity, column, row, value, where):
        key = (entity, column)
        if key not in domains:
            fails.append(f'{where}: unknown world column {entity}.{column}')
        elif _value(value) not in domains[key] and _value(value) not in allowed.get((entity, row, column), set()):
            fails.append(f'{where}: {entity} row {row} {column}={value!r} is outside world data and has no matching defect')

    # Execute only seed scripts, never displayed examples, in a restricted memory DB.
    for index, seed in enumerate((n for n in tree.all if n.tag == 'script' and n.attrs.get('type') == 'text/plain'), 1):
        db = sqlite3.connect(':memory:')
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_000_000)
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 1_000_000)
        steps = [0]

        def progress():
            steps[0] += 1
            return steps[0] > 1000

        def authorize(action, arg1, arg2, database, trigger):
            if action in {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH}:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_PRAGMA:
                # Existing lessons enable FK enforcement in their isolated DBs.
                # Preserve that behavior without allowing file/storage pragmas.
                return sqlite3.SQLITE_OK if ((arg1 or '').lower() == 'foreign_keys' and
                    (arg2 is None or str(arg2).lower() in {'on', '1', 'true'})) else sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or '').lower() in {'load_extension', 'readfile', 'writefile'}:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(authorize)
        db.set_progress_handler(progress, 1000)
        try:
            db.executescript(html.unescape(text_of(seed)))
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for name in tables:
                quoted = '"' + name.replace('"', '""') + '"'
                cursor = db.execute(f'SELECT * FROM {quoted} LIMIT 101')
                columns = [c[0] for c in cursor.description]
                rows = cursor.fetchall()
                # Staging names may differ, but every column must map to exactly one world domain.
                entities = [name] if name in data else [e for e in data if all((e, c) in domains for c in columns)]
                if len(entities) != 1:
                    fails.append(f'seed {index}: table {name} needs an unambiguous world entity (use canonical column names)')
                    continue
                if len(rows) > 100:
                    fails.append(f'seed {index}: table {name} exceeds 100 rows')
                for row_index, row in enumerate(rows, 1):
                    for column, value in zip(columns, row):
                        check_cell(entities[0], column, row_index, value, f'seed {index}')
        except sqlite3.Error as exc:
            fails.append(f'seed {index}: {exc}')
        finally:
            db.close()

    for figure in (n for n in tree.all if 'nerdit-figure' in n.classes):
        tables = [n for n in walk(figure) if n.tag == 'table']
        if not tables:
            # SVG relationships and timelines are not record tables. QA checks their labels.
            continue
        entity = figure.attrs.get('data-world-entity')
        if not entity:
            if not figure.attrs.get('data-world-derived', '').strip():
                fails.append('figure table needs data-world-entity or a data-world-derived explanation')
            continue
        if entity not in data:
            fails.append(f'figure uses unknown world entity {entity}')
            continue
        for table in tables:
            headers = [n for n in walk(table) if n.tag == 'th']
            columns = [n.attrs.get('data-world-column') or text_of(n).strip() for n in headers]
            rows = [n for n in walk(table) if n.tag == 'tr' and any(c.tag == 'td' for c in n.children)]
            if not columns:
                fails.append(f'figure {entity}: data table needs named column headers')
            for index, row in enumerate(rows, 1):
                cells = [n for n in row.children if n.tag == 'td']
                if len(cells) != len(columns):
                    fails.append(f'figure {entity}: row {index} does not match its headers')
                for column, cell in zip(columns, cells):
                    value = cell.attrs.get('data-world-value', text_of(cell).strip())
                    check_cell(entity, column, index, value, 'figure')
    return fails, warns


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--world', required=True)
    ap.add_argument('--course', required=True)
    args = ap.parse_args()
    try:
        world = load_world(Path(args.world))
        data = generate(world)
        course = json.loads(Path(args.course).read_text(encoding='utf-8'))
        count = 0
        for lesson in course['lessons']:
            fails, warns = check_lesson(lesson['content'], world, data)
            count += len(fails)
            for message in fails:
                print(f"FAIL {lesson['id']}: {message}")
            for message in warns:
                print(f"WARN {lesson['id']}: {message}")
        print(f'WORLD: {count} failure(s)')
        return 1 if count else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
