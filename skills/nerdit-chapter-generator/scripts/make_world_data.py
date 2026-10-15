#!/usr/bin/env python3
"""Generate reproducible, synthetic teaching records from a declarative world.

python make_world_data.py --world course-x_world.json --out-dir work
Stdlib only. No expressions, imports, network access or executable generators.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import math
from pathlib import Path
import random
import re
import sys

LIBRARY = Path(__file__).resolve().parent.parent / 'references' / 'worlds'
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')
PRIVATE = re.compile(r'phone|mobile|email|address|postcode|postal', re.I)
GENERATORS = {'id', 'choice', 'weighted_choice', 'int_range', 'money_range', 'date_range', 'fk', 'person_name'}


def load_world(path: Path, library: Path = LIBRARY) -> dict:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(data, dict) and 'use' in data:
        slug = data['use']
        if set(data) != {'use'} or not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
            raise ValueError('world reference must contain only a safe library slug in use')
        data = json.loads((library / f'{slug}.world.json').read_text(encoding='utf-8'))
    validate_world(data)
    return data


def _dates(spec):
    start, end = date.fromisoformat(spec['start']), date.fromisoformat(spec['end'])
    if end < start or (end - start).days > 3660:
        raise ValueError('date range must be ordered and at most ten years')
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    mw = spec.get('monthWeights', {})
    if not isinstance(mw, dict) or any(str(k) not in {str(i) for i in range(1, 13)} for k in mw):
        raise ValueError('monthWeights keys must be month numbers 1 through 12')
    weights = [mw.get(str(d.month), 1) for d in days]
    _weights(weights, len(days))
    return days, weights


def _weights(weights, count):
    if (not isinstance(weights, list) or len(weights) != count or
            any(type(n) not in (int, float) or not 0 <= n < float('inf') for n in weights) or not any(weights)):
        raise ValueError('weights must match values, be finite and nonnegative, with a positive total')


def validate_world(world: dict) -> None:
    if not isinstance(world, dict):
        raise ValueError('world must be an object')
    business = world.get('business', {})
    if not isinstance(business, dict) or any(not isinstance(business.get(k), str) or not business[k].strip()
            for k in ('name', 'type', 'city', 'currency', 'moneyUnit')):
        raise ValueError('business requires name, type, city, currency and moneyUnit strings')
    if business.get('fictional') is not True:
        permission = business.get('realName', {})
        if not isinstance(permission, dict) or any(not isinstance(permission.get(k), str) or not permission[k].strip()
                for k in ('approvedBy', 'date', 'note')):
            raise ValueError('real business name requires approvedBy, date and note permission evidence')
        date.fromisoformat(permission['date'])
    if type(world.get('seed')) is not int:
        raise ValueError('world seed must be an integer')
    cast = world.get('cast')
    if not isinstance(cast, list) or any(not isinstance(p, dict) or
            any(not isinstance(p.get(k), str) or not p[k].strip() for k in ('name', 'role', 'trait', 'look')) for p in cast):
        raise ValueError('cast must list invented people with name, role, trait and look')
    stages = world.get('stages')
    if not isinstance(stages, list) or not stages or any(not isinstance(s, str) or not s.strip() for s in stages) or len(set(stages)) != len(stages):
        raise ValueError('stages must be a nonempty list of unique labels')
    if not isinstance(world.get('messiness'), list) or any(not isinstance(v, str) for v in world['messiness']):
        raise ValueError('messiness must be a list of defect column names')
    if not isinstance(world.get('arc'), dict) or any(not isinstance(v, str) for v in world['arc'].values()):
        raise ValueError('arc must map lesson IDs to story beats')
    entities = world.get('entities')
    if not isinstance(entities, dict) or not entities or len(entities) > 100:
        raise ValueError('entities must contain 1 to 100 tables')
    for name, entity in entities.items():
        if not IDENT.fullmatch(name) or not isinstance(entity, dict):
            raise ValueError(f'unsafe table name or invalid entity: {name}')
        if type(entity.get('rows')) is not int or not 0 <= entity['rows'] <= 100:
            raise ValueError(f'{name}: rows must be between 0 and 100')
        columns = entity.get('columns')
        if not isinstance(columns, dict) or not 1 <= len(columns) <= 50:
            raise ValueError(f'{name}: columns must contain 1 to 50 definitions')
        if 'records' in entity:
            records = entity['records']
            if (not isinstance(records, list) or len(records) != entity['rows'] or
                    any(not isinstance(row, dict) or set(row) != set(columns) or
                        any(v is not None and (type(v) not in (str, int, float) or
                            type(v) is float and not math.isfinite(v)) for v in row.values()) for row in records)):
                raise ValueError(f'{name}: preserved records must match rows and columns, with finite scalar values')
        for column, spec in columns.items():
            if not IDENT.fullmatch(column) or PRIVATE.search(column):
                raise ValueError(f'{name}: unsafe or private column {column}')
            if not isinstance(spec, dict) or spec.get('generator') not in GENERATORS:
                raise ValueError(f'{name}.{column}: unknown generator')
            kind = spec['generator']
            if kind in {'choice', 'weighted_choice', 'person_name'}:
                values = spec.get('values')
                if not isinstance(values, list) or not values or any(type(v) not in (str, int, float) for v in values):
                    raise ValueError(f'{name}.{column}: explicit scalar values required')
                if any(type(v) is float and not math.isfinite(v) for v in values):
                    raise ValueError(f'{name}.{column}: numeric values must be finite')
                if kind == 'person_name' and any(not isinstance(v, str) for v in values):
                    raise ValueError('person_name values must be invented name strings')
                if kind == 'weighted_choice':
                    _weights(spec.get('weights'), len(values))
            elif kind in {'int_range', 'money_range'}:
                if any(type(spec.get(k)) is not int for k in ('min', 'max')) or spec['min'] > spec['max']:
                    raise ValueError(f'{name}.{column}: ordered integer min/max required (money uses minor units)')
            elif kind == 'date_range':
                _dates(spec)
            elif kind == 'id':
                if not isinstance(spec.get('prefix', ''), str) or type(spec.get('start', 1)) is not int:
                    raise ValueError(f'{name}.{column}: id needs string prefix and integer start')
            elif kind == 'fk':
                target = entities.get(spec.get('entity'), {})
                if not target.get('rows') or spec.get('column') not in target.get('columns', {}):
                    raise ValueError(f'{name}.{column}: foreign key target is missing or empty')


def generate(world: dict) -> dict[str, list[dict]]:
    validate_world(world)
    rng = random.Random(world['seed'])
    entities, data, active = world['entities'], {}, set()

    def table(name):
        if name in data:
            return
        if name in active:
            raise ValueError(f'cyclic foreign key dependency at {name}')
        active.add(name)
        columns = entities[name]['columns']
        for col in sorted(columns):
            spec = columns[col]
            if spec['generator'] == 'fk':
                table(spec['entity'])
        if 'records' in entities[name]:
            rows = [dict(row) for row in entities[name]['records']]
            for col, spec in columns.items():
                if spec['generator'] == 'fk':
                    values = {r[spec['column']] for r in data[spec['entity']]}
                    if any(row[col] not in values for row in rows):
                        raise ValueError(f'{name}.{col}: preserved record violates foreign key')
            data[name] = rows
            active.remove(name)
            return
        rows = []
        for i in range(entities[name]['rows']):
            row = {}
            for col in sorted(columns):
                spec, value = columns[col], None
                kind = spec['generator']
                if kind == 'id':
                    number = spec.get('start', 1) + i
                    value = f"{spec['prefix']}{number}" if spec.get('prefix') else number
                elif kind in {'choice', 'person_name'}:
                    value = rng.choice(spec['values'])
                elif kind == 'weighted_choice':
                    value = rng.choices(spec['values'], weights=spec['weights'], k=1)[0]
                elif kind in {'int_range', 'money_range'}:
                    value = rng.randint(spec['min'], spec['max'])
                elif kind == 'date_range':
                    days, weights = _dates(spec)
                    value = rng.choices(days, weights=weights, k=1)[0].isoformat()
                elif kind == 'fk':
                    value = rng.choice(data[spec['entity']])[spec['column']]
                row[col] = value
            rows.append(row)
        data[name] = rows
        active.remove(name)

    for name in sorted(entities):
        table(name)
    return data


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
            cols = sorted(world['entities'][table]['columns'])
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
    ap.add_argument('--world', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    try:
        world = load_world(Path(args.world))
        data = generate(world)
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / 'world_data.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (out / 'world_data.sql').write_text(sql_dump(data, world), encoding='utf-8')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    print(f'Generated {sum(map(len, data.values()))} synthetic rows in {len(data)} tables')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
