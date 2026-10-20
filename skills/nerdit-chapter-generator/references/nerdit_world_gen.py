"""NERDIT world generator core: declarative worlds in, reproducible synthetic rows out.

One file, two homes. make_world_data.py imports it for offline use, and the website serves an
identical copy (/nerdit_world_gen.py) that the Python runners load into Pyodide to build a
lesson's CSV files in the browser. check_runtime_bundle.py keeps the copies identical.

Rules that keep CPython and Pyodide byte-identical:
- stdlib only: random, math, datetime, re, csv, io, json; no file access, network, eval or exec
- randomness only through random.Random(seed): random, gauss, lognormvariate, expovariate,
  choice, choices, randint, shuffle
- entities and columns are visited in a fixed order (sorted, or dependency order)
"""
import csv
from datetime import date, timedelta
import io
import math
import random
import re

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')
PRIVATE = re.compile(r'phone|mobile|email|address|postcode|postal', re.I)
GENERATORS = {'id', 'choice', 'weighted_choice', 'int_range', 'money_range', 'date_range', 'fk', 'person_name',
              'normal', 'lognormal', 'poisson', 'bernoulli', 'linear', 'logistic', 'binned_effect', 'text'}
PLACEHOLDER = re.compile(r'\{([a-z_]+)\}')  # text templates: {slot}; filled with str.replace, never format
# Row caps per profile. `sql` keeps lesson tables small enough to read; `analytics` is big
# enough to train a model on and still builds in under two seconds in the browser.
PROFILES = {'sql': 100, 'analytics': 20000}
MAX_CELLS = 200000  # rows x columns over a world's analytics entities
# Parameter keys the newer generators accept; anything else is a typo and fails.
PARAMS = {
    'normal': {'mean', 'sd', 'min', 'max', 'round'},
    'lognormal': {'median', 'sigma', 'max', 'round'},
    'poisson': {'lam'},
    'bernoulli': {'p'},
    # Dependent columns: the true effect of every input is declared, so a lesson can compare
    # what a model learned with the truth.
    'linear': {'intercept', 'terms', 'effects', 'noise_sd', 'round', 'min', 'max'},
    'logistic': {'intercept', 'terms', 'effects', 'target_rate'},
    'binned_effect': {'column', 'edges', 'deltas'},
    'text': {'templates', 'slots', 'tone_from'},
}


def _check_safe_text(where: str, text: str) -> None:
    """Template and slot text is synthetic too: no contact details, no phone-like numbers."""
    if PRIVATE.search(text) or '@' in text:
        raise ValueError(f'{where}: text may not hold contact details ({text!r})')
    if looks_like_phone(text):
        raise ValueError(f'{where}: text may not hold a phone number ({text!r})')


def looks_like_phone(text: str) -> bool:
    """Six or more digits once spaces and hyphens between digits are removed ("98765 43210").
    ISO dates (2025-01-02) are removed first: a date is not a phone number."""
    text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', ' ', text)
    return re.search(r'\d{6,}', re.sub(r'(?<=\d)[ -](?=\d)', '', text)) is not None


def _check_text(where: str, spec: dict, columns: dict) -> None:
    def strings(v, most):
        return isinstance(v, list) and 1 <= len(v) <= most and all(isinstance(t, str) and t.strip() for t in v)

    templates, slots, tone = spec.get('templates'), spec.get('slots', {}), spec.get('tone_from')
    if not strings(templates, 200):
        raise ValueError(f'{where}: text needs templates as a list of 1 to 200 strings')
    if not isinstance(slots, dict) or any(not re.fullmatch(r'[a-z_]+', k) or not strings(v, 500)
                                          for k, v in slots.items()):
        raise ValueError(f'{where}: text slots must map lower-case names to lists of strings')
    every = list(templates)
    if tone is not None:
        if not isinstance(tone, dict) or len(tone) != 1:
            raise ValueError(f'{where}: tone_from names exactly one label column')
        label, by_value = next(iter(tone.items()))
        if label not in columns or label == where.split('.')[-1]:
            raise ValueError(f'{where}: tone_from column {label} is not another column of this entity')
        if not isinstance(by_value, dict) or not by_value or any(not strings(v, 200) for v in by_value.values()):
            raise ValueError(f'{where}: tone_from must map label values to lists of templates')
        every += [t for ts in by_value.values() for t in ts]
    for t in every:
        for ph in PLACEHOLDER.findall(t):
            if ph not in slots:
                raise ValueError(f'{where}: template placeholder {{{ph}}} is not a slot')
        if '{' in PLACEHOLDER.sub('', t) or '}' in PLACEHOLDER.sub('', t):
            raise ValueError(f'{where}: stray brace in template {t!r}')
        _check_safe_text(where, t)
    for k, values in slots.items():
        _check_safe_text(where, k)
        for v in values:
            if '{' in v or '}' in v:
                raise ValueError(f'{where}: slot values may not contain a brace ({v!r})')
            _check_safe_text(where, v)


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


_DAY_CACHE = {}


def _day_table(spec):
    """(days, cumulative weights) for a date_range, built once per distinct range.

    choices(cum_weights=...) draws exactly what choices(weights=...) draws, so this only
    saves rebuilding a list of up to 3,661 days for every row.
    """
    key = (spec['start'], spec['end'], tuple(sorted((str(k), v) for k, v in spec.get('monthWeights', {}).items())))
    if key not in _DAY_CACHE:
        days, weights = _dates(spec)
        cum, total = [], 0
        for w in weights:
            total += w
            cum.append(total)
        _DAY_CACHE[key] = ([d.isoformat() for d in days], cum)
    return _DAY_CACHE[key]


def _weights(weights, count):
    if (not isinstance(weights, list) or len(weights) != count or
            any(type(n) not in (int, float) or not 0 <= n < float('inf') for n in weights) or not any(weights)):
        raise ValueError('weights must match values, be finite and nonnegative, with a positive total')


def _num(v) -> bool:
    return type(v) in (int, float) and math.isfinite(v)


def _check_inputs(where: str, spec: dict, columns: dict) -> None:
    """terms / effects of linear and logistic: other columns of the same entity."""
    terms, effects = spec.get('terms', {}), spec.get('effects', {})
    if not isinstance(terms, dict) or not isinstance(effects, dict):
        raise ValueError(f'{where}: terms and effects must be objects keyed by column')
    for c, w in terms.items():
        if c not in columns or c == where.split('.')[-1]:
            raise ValueError(f'{where}: term {c} is not another column of this entity')
        if not _num(w):
            raise ValueError(f'{where}: term {c} weight must be a number')
    for c, deltas in effects.items():
        if c not in columns or c == where.split('.')[-1]:
            raise ValueError(f'{where}: effect {c} is not another column of this entity')
        if not isinstance(deltas, dict) or any(not _num(d) for d in deltas.values()):
            raise ValueError(f'{where}: effect {c} must map values to number deltas')


def _check_params(where: str, spec: dict, columns: dict) -> None:
    """Parameters of the newer generators; `where` is entity.column for the message."""
    kind = spec['generator']
    extra = set(spec) - PARAMS[kind] - {'generator'}
    if extra:
        raise ValueError(f'{where}: unknown {kind} parameter {sorted(extra)[0]}')

    def need(key, ok, what):
        if key not in spec or not _num(spec[key]) or not ok(spec[key]):
            raise ValueError(f'{where}: {kind} needs {key} {what}')

    def optional(key, ok, what):
        if key in spec and (not _num(spec[key]) or not ok(spec[key])):
            raise ValueError(f'{where}: {kind} {key} must be {what}')

    if 'round' in spec and (type(spec['round']) is not int or not 0 <= spec['round'] <= 6):
        raise ValueError(f'{where}: round must be a whole number from 0 to 6')
    if kind == 'normal':
        need('mean', lambda v: True, 'as a number')
        need('sd', lambda v: v >= 0, 'as a number of at least 0')
        optional('min', lambda v: True, 'a number')
        optional('max', lambda v: True, 'a number')
        if 'min' in spec and 'max' in spec and spec['min'] > spec['max']:
            raise ValueError(f'{where}: normal min must not exceed max')
    elif kind == 'lognormal':
        need('median', lambda v: v > 0, 'above 0')
        need('sigma', lambda v: 0 <= v <= 5, 'from 0 to 5')
        optional('max', lambda v: v > 0, 'above 0')
    elif kind == 'poisson':
        need('lam', lambda v: 0 < v <= 1000000, 'above 0 (and at most 1000000)')
    elif kind == 'bernoulli':
        need('p', lambda v: 0 <= v <= 1, 'from 0 to 1')
    elif kind == 'linear':
        need('intercept', lambda v: True, 'as a number')
        optional('noise_sd', lambda v: v >= 0, 'a number of at least 0')
        optional('min', lambda v: True, 'a number')
        optional('max', lambda v: True, 'a number')
        _check_inputs(where, spec, columns)
    elif kind == 'logistic':
        if 'target_rate' in spec:
            need('target_rate', lambda v: 0.001 <= v <= 0.999, 'from 0.001 to 0.999')
            optional('intercept', lambda v: True, 'a number')
        else:
            need('intercept', lambda v: True, 'as a number (or a target_rate)')
        _check_inputs(where, spec, columns)
    elif kind == 'binned_effect':
        edges, deltas = spec.get('edges'), spec.get('deltas')
        if spec.get('column') not in columns or spec['column'] == where.split('.')[-1]:
            raise ValueError(f'{where}: binned_effect column must be another column of this entity')
        if (not isinstance(edges, list) or not edges or any(not _num(e) for e in edges) or
                any(a >= b for a, b in zip(edges, edges[1:]))):
            raise ValueError(f'{where}: binned_effect edges must be ascending numbers')
        if not isinstance(deltas, list) or len(deltas) != len(edges) + 1 or any(not _num(d) for d in deltas):
            raise ValueError(f'{where}: binned_effect needs len(edges) + 1 number deltas')
    elif kind == 'text':
        _check_text(where, spec, columns)


def _sigmoid(score: float) -> float:
    if score >= 0:
        return 1 / (1 + math.exp(-score))
    e = math.exp(score)  # never overflows for very negative scores
    return e / (1 + e)


def _score(spec: dict, row: dict, where: str) -> float:
    """intercept + sum(weight x value) + effects[column][value], without noise."""
    total = spec.get('intercept', 0)
    for c, w in spec.get('terms', {}).items():
        if not _num(row[c]):
            raise ValueError(f'{where}: term {c} needs numbers, got {row[c]!r}')
        total += w * row[c]
    for c, deltas in spec.get('effects', {}).items():
        total += deltas.get(str(row[c]), 0)
    return total


def _solve_intercept(rest: list, target: float) -> float:
    """Intercept b with mean(sigmoid(b + r)) == target: bisection on [-20, 20], 40 steps."""
    lo, hi = -20.0, 20.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if sum(_sigmoid(mid + r) for r in rest) / len(rest) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _round(value: float, places: int):
    value = round(value, places) if places else int(round(value))
    return 0.0 if value == 0 and places else value  # never print -0.0


def _poisson(rng, lam: float) -> int:
    if lam <= 30:  # Knuth: multiply uniforms until the product drops below e^-lam
        limit, k, prod = math.exp(-lam), 0, rng.random()
        while prod > limit:
            k += 1
            prod *= rng.random()
        return k
    return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))


def depends_on(spec: dict) -> set:
    """Columns of the same entity that this column's value is computed from."""
    if not isinstance(spec, dict):
        return set()
    deps = set()
    for key in ('terms', 'effects'):
        if isinstance(spec.get(key), dict):
            deps |= set(spec[key])
    if isinstance(spec.get('column'), str) and spec.get('generator') == 'binned_effect':
        deps.add(spec['column'])
    if isinstance(spec.get('tone_from'), dict):
        deps |= set(spec['tone_from'])
    return deps


def column_order(columns: dict, entity: str = '', segments: dict = None) -> list:
    """Dependency order, alphabetical among columns that are ready together.

    With no dependencies this is sorted(columns), the order every existing world was drawn in.
    A segment override can add inputs to a column, so its dependencies count too.
    """
    deps = {c: depends_on(spec) & set(columns) for c, spec in columns.items()}
    for seg in (segments or {}).values():
        for c, params in (seg.get('overrides', {}) if isinstance(seg, dict) else {}).items():
            if c in deps and isinstance(params, dict) and isinstance(columns[c], dict):
                deps[c] |= depends_on(dict(columns[c], **params)) & set(columns)
    order, done = [], set()
    while len(order) < len(columns):
        ready = [c for c in columns if c not in done and deps[c] <= done]
        if not ready:
            # Follow unfinished inputs from any stuck column until one repeats: that one is on the cycle.
            seen, stuck = [], min(c for c in columns if c not in done)
            while stuck not in seen:
                seen.append(stuck)
                stuck = min(deps[stuck] - done)
            raise ValueError(f'cyclic column dependency at {entity}.{stuck}' if entity else
                             f'cyclic column dependency at {stuck}')
        nxt = min(ready)
        order.append(nxt)
        done.add(nxt)
    return order


def _check_column(name, column, spec, columns, entities, profile) -> None:
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
    elif kind in PARAMS:
        _check_params(f'{name}.{column}', spec, columns)
        if 'target_rate' in spec and profile != 'analytics':
            raise ValueError(f'{name}.{column}: target_rate needs the analytics profile')


def _check_segments(name, entity, entities, profile) -> None:
    """segments: {name: {weight, overrides: {column: {param: value}}}}; each override is checked
    as the column it produces, so a segment cannot smuggle in a bad parameter."""
    segments, columns = entity['segments'], entity['columns']
    if not isinstance(segments, dict) or not 1 <= len(segments) <= 20:
        raise ValueError(f'{name}: segments must name 1 to 20 groups')
    if '_segment' in columns:
        raise ValueError(f'{name}: _segment is reserved for the segment label')
    for seg, s in segments.items():
        if not isinstance(seg, str) or not re.fullmatch(r'[A-Za-z0-9_ -]{1,40}', seg) or PRIVATE.search(seg):
            raise ValueError(f'{name}: unsafe segment name {seg!r}')
        if not isinstance(s, dict) or set(s) - {'weight', 'overrides'} or not _num(s.get('weight')) or s['weight'] <= 0:
            raise ValueError(f'{name}: segment {seg} needs a weight above 0 (and only weight and overrides)')
        overrides = s.get('overrides', {})
        if not isinstance(overrides, dict):
            raise ValueError(f'{name}: segment {seg} overrides must be an object')
        for column, params in overrides.items():
            if column not in columns:
                raise ValueError(f'{name}: segment {seg} overrides {column}, which is not a column')
            if not isinstance(params, dict) or 'generator' in params:
                raise ValueError(f'{name}.{column}: segment {seg} may change parameters, not the generator')
            # target_rate balances the whole column at once; one segment cannot have its own.
            if 'target_rate' in params or ('target_rate' in columns[column] and 'intercept' in params):
                raise ValueError(f'{name}.{column}: segment {seg} may not change target_rate or the '
                                 f'intercept it sets; the label is balanced over all rows')
            _check_column(name, column, dict(columns[column], **params), columns, entities, profile)


SERIES_KEYS = {'kind', 'profile', 'defects', 'start', 'end', 'freq', 'base', 'trend_per_period', 'weekly',
               'monthly', 'holidays', 'noise_sd', 'break', 'value_column', 'date_column'}
INTERACTION_KEYS = {'kind', 'profile', 'defects', 'users', 'items', 'user_column', 'item_column', 'rating_column',
                    'k', 'density', 'scale', 'noise_sd'}


def _iso(name: str, value, what: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name}: {what} must be an ISO date (YYYY-MM-DD)') from None


def _periods(entity: dict) -> list:
    """Period start dates of a series: every day, every 7 days, or the 1st of every month."""
    start, end, freq = date.fromisoformat(entity['start']), date.fromisoformat(entity['end']), entity['freq']
    if freq == 'day':
        return [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if freq == 'week':
        return [start + timedelta(days=7 * i) for i in range((end - start).days // 7 + 1)]
    out, y, m = [], start.year, start.month
    while date(y, m, 1) <= end:
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _out_columns(name: str, entity: dict, defaults: dict) -> list:
    cols = [entity.get(k, v) for k, v in defaults.items()]
    if any(not isinstance(c, str) or not IDENT.fullmatch(c) or PRIVATE.search(c) for c in cols) or len(set(cols)) < len(cols):
        raise ValueError(f'{name}: {", ".join(defaults)} must be distinct safe column names')
    return cols


def _check_series(name: str, e: dict, cap: int) -> list:
    extra = set(e) - SERIES_KEYS
    if extra:
        raise ValueError(f'{name}: unknown series key {sorted(extra)[0]}')
    start, end = _iso(name, e.get('start'), 'start'), _iso(name, e.get('end'), 'end')
    if end < start or (end - start).days > 3660:
        raise ValueError(f'{name}: series dates must be ordered and at most ten years apart')
    freq = e.get('freq')
    if freq not in ('day', 'week', 'month'):
        raise ValueError(f'{name}: series freq must be day, week or month')
    if freq == 'month' and start.day != 1:
        raise ValueError(f'{name}: a monthly series must start on the first day of a month')
    if not _num(e.get('base')) or any(k in e and not _num(e[k]) for k in ('trend_per_period', 'noise_sd')):
        raise ValueError(f'{name}: series needs a number base (and number trend_per_period, noise_sd)')
    if e.get('noise_sd', 0) < 0:
        raise ValueError(f'{name}: noise_sd must be at least 0')
    if 'weekly' in e:
        if freq != 'day':
            raise ValueError(f'{name}: weekly multipliers apply to daily series only')
        if not isinstance(e['weekly'], list) or len(e['weekly']) != 7 or any(not _num(v) or v < 0 for v in e['weekly']):
            raise ValueError(f'{name}: weekly needs 7 multipliers of at least 0, Monday first')
    monthly = e.get('monthly', {})
    if (not isinstance(monthly, dict) or any(k not in {str(i) for i in range(1, 13)} for k in monthly) or
            any(not _num(v) or v < 0 for v in monthly.values())):
        raise ValueError(f'{name}: monthly keys must be month numbers 1 to 12 with multipliers of at least 0')
    holidays = e.get('holidays', [])
    if not isinstance(holidays, list) or len(holidays) > 50:
        raise ValueError(f'{name}: holidays must be a list of at most 50 windows')
    for h in holidays:
        if (not isinstance(h, dict) or set(h) != {'date', 'lift', 'days'} or not _num(h['lift']) or h['lift'] <= -1 or
                type(h['days']) is not int or not 1 <= h['days'] <= 366):
            raise ValueError(f'{name}: each holiday needs date, lift (above -1) and days (1 to 366)')
        _iso(name, h['date'], 'holiday date')
    if 'break' in e:
        b = e['break']
        if not isinstance(b, dict) or set(b) != {'date', 'shift'} or not _num(b['shift']):
            raise ValueError(f'{name}: break needs a date and a number shift')
        _iso(name, b['date'], 'break date')
    _out_columns(name, e, {'date_column': 'date', 'value_column': 'value'})
    periods = _periods(e)
    if len(periods) > cap:
        raise ValueError(f'{name}: series has {len(periods)} periods; rows must be between 0 and {cap}')
    return periods


def _check_interactions(name: str, e: dict, entities: dict, cap: int) -> int:
    """Validates an interactions entity; returns the expected number of rows."""
    extra = set(e) - INTERACTION_KEYS
    if extra:
        raise ValueError(f'{name}: unknown interactions key {sorted(extra)[0]}')
    for side in ('users', 'items'):
        target = entities.get(e.get(side))
        if not isinstance(target, dict) or target.get('kind', 'table') != 'table' or not target.get('rows'):
            raise ValueError(f'{name}: {side} must name a table entity with rows')
        column = 'user_column' if side == 'users' else 'item_column'
        if e.get(column) not in target.get('columns', {}):
            raise ValueError(f'{name}: {column} must be a column of {e[side]}')
    _out_columns(name, e, {'user_column': 'user', 'item_column': 'item', 'rating_column': 'rating'})
    if type(e.get('k')) is not int or not 1 <= e['k'] <= 5:
        raise ValueError(f'{name}: k must be a whole number from 1 to 5')
    if not _num(e.get('density')) or not 0.01 <= e['density'] <= 0.3:
        raise ValueError(f'{name}: density must be from 0.01 to 0.3')
    scale = e.get('scale')
    if not isinstance(scale, list) or len(scale) != 2 or any(type(v) is not int for v in scale) or scale[0] >= scale[1]:
        raise ValueError(f'{name}: scale must be [low, high] whole numbers with low below high')
    if 'noise_sd' in e and (not _num(e['noise_sd']) or e['noise_sd'] < 0):
        raise ValueError(f'{name}: noise_sd must be a number of at least 0')
    pairs = entities[e['users']]['rows'] * entities[e['items']]['rows']
    expected = round(pairs * e['density'])
    if pairs > 1000000 or expected > cap:
        raise ValueError(f'{name}: about {expected} ratings from {pairs} pairs; rows must be between 0 and {cap}')
    return expected


NUMERIC = {'int_range', 'money_range', 'normal', 'lognormal', 'poisson', 'linear', 'binned_effect'}
DEFECTS = ('drift', 'outliers', 'label_noise', 'missing', 'duplicates')  # the order they are applied in


def _column_types(entity: dict) -> dict:
    """column -> 'binary' | 'number' | 'date' | 'other', for checking where a defect may go."""
    kind = entity.get('kind', 'table')
    if kind == 'series':
        return {entity.get('date_column', 'date'): 'date', entity.get('value_column', 'value'): 'number'}
    if kind == 'interactions':
        return {entity['user_column']: 'other', entity['item_column']: 'other',
                entity.get('rating_column', 'rating'): 'number'}
    out = {}
    for c, spec in entity['columns'].items():
        g = spec['generator']
        values = spec.get('values', [])
        if g in ('bernoulli', 'logistic') or (g in ('choice', 'weighted_choice') and
                                               all(type(v) is int and v in (0, 1) for v in values)):
            out[c] = 'binary'
        elif g in NUMERIC or (g == 'id' and not spec.get('prefix')) or (
                g in ('choice', 'weighted_choice') and all(type(v) in (int, float) for v in values)):
            out[c] = 'number'
        elif g == 'date_range':
            out[c] = 'date'
        else:
            out[c] = 'other'
    if entity.get('segments'):
        out['_segment'] = 'other'
    return out


def _drift_date_column(name: str, drift: dict, types: dict) -> str:
    if 'date_column' in drift:
        if types.get(drift['date_column']) != 'date':
            raise ValueError(f"{name}: drift date_column {drift['date_column']} is not a date column")
        return drift['date_column']
    dates = [c for c, t in types.items() if t == 'date']
    if len(dates) != 1:
        raise ValueError(f'{name}: drift needs date_column (the entity has {len(dates)} date columns)')
    return dates[0]


def _check_defects(name: str, entity: dict, cap: int) -> None:
    d = entity['defects']
    if not isinstance(d, dict):
        raise ValueError(f'{name}: defects must be an object')
    for k in d:
        if k not in DEFECTS:
            raise ValueError(f'{name}: unknown defect {k} (use {", ".join(DEFECTS)})')
    if 'records' in entity:
        raise ValueError(f'{name}: defects cannot be combined with preserved records')
    types = _column_types(entity)

    def rate(value, most, what):
        if not _num(value) or not 0 < value <= most:
            raise ValueError(f'{name}: {what} rate must be above 0 and at most {most}')

    def column(c, what, want=None):
        if c not in types:
            raise ValueError(f'{name}: {what} column {c} is not a column')
        if want == 'number' and types[c] not in ('number', 'binary'):
            raise ValueError(f'{name}: {what} needs a number column ({c})')
        if want == 'binary' and types[c] != 'binary':
            raise ValueError(f'{name}: {what} needs a 0 or 1 label column ({c})')

    for m in d.get('missing', []) if isinstance(d.get('missing', []), list) else [None]:
        if not isinstance(m, dict) or set(m) - {'column', 'rate', 'when'}:
            raise ValueError(f'{name}: missing entries need column, rate and an optional when')
        column(m.get('column'), 'missing')
        rate(m.get('rate'), 0.5, 'missing')
        when = m.get('when', {})
        if not isinstance(when, dict) or any(c not in types or type(v) not in (str, int, float) for c, v in when.items()):
            raise ValueError(f'{name}: missing when must map columns to values')
    for o in d.get('outliers', []) if isinstance(d.get('outliers', []), list) else [None]:
        if not isinstance(o, dict) or set(o) != {'column', 'rate', 'factor'}:
            raise ValueError(f'{name}: outliers entries need column, rate and factor')
        column(o['column'], 'outliers', 'number')
        rate(o['rate'], 0.2, 'outliers')
        if not _num(o['factor']) or o['factor'] <= 0:
            raise ValueError(f'{name}: outliers factor must be a number above 0')
    if 'label_noise' in d:
        n = d['label_noise']
        if not isinstance(n, dict) or set(n) != {'column', 'rate'}:
            raise ValueError(f'{name}: label_noise needs column and rate')
        column(n['column'], 'label_noise', 'binary')
        rate(n['rate'], 0.5, 'label_noise')
    if 'drift' in d:
        dr = d['drift']
        if not isinstance(dr, dict) or not {'after', 'column', 'shift'} <= set(dr) <= {'after', 'column', 'shift', 'date_column'}:
            raise ValueError(f'{name}: drift needs after, column, shift and an optional date_column')
        _iso(name, dr['after'], 'drift after')
        column(dr['column'], 'drift', 'number')
        if not _num(dr['shift']):
            raise ValueError(f'{name}: drift shift must be a number')
        _drift_date_column(name, dr, types)
    if 'duplicates' in d:
        rate(d['duplicates'], 0.2, 'duplicates')
        rows = entity.get('rows', 0)
        if rows + round(rows * d['duplicates']) > cap:
            raise ValueError(f'{name}: rows plus duplicates must stay at most {cap}')


def _pick(rng, eligible: list, rate: float) -> list:
    """Exactly round(rate * len(eligible)) of the eligible row indexes, sorted."""
    pool = list(eligible)
    rng.shuffle(pool)
    return sorted(pool[:round(rate * len(pool))])


def _apply_defects(rng, entity: dict, rows: list, name: str) -> dict:
    """Planned messiness, in a fixed order: drift, outliers, label_noise, missing, duplicates.
    Returns {defect: {column: [row index, ...]}}; duplicates give {"rows": new, "of": source}."""
    d, found = entity['defects'], {}
    types = _column_types(entity)
    rounds = {c: s.get('round', 2) for c, s in entity.get('columns', {}).items()}

    def shifted(value, new, col):
        return _round(new, 0 if type(value) is int else rounds.get(col, 2))

    def record(kind, col, idx):
        bucket = found.setdefault(kind, {})
        bucket[col] = sorted(set(bucket.get(col, [])) | set(idx))

    if 'drift' in d:
        dr = d['drift']
        dcol, col = _drift_date_column(name, dr, types), dr['column']
        idx = [i for i, r in enumerate(rows) if r[dcol] is not None and r[dcol] >= dr['after']]
        for i in idx:
            rows[i][col] = shifted(rows[i][col], rows[i][col] + dr['shift'], col)
        record('drift', col, idx)
    for o in d.get('outliers', []):
        col = o['column']
        idx = _pick(rng, range(len(rows)), o['rate'])
        for i in idx:
            rows[i][col] = shifted(rows[i][col], rows[i][col] * o['factor'], col)
        record('outliers', col, idx)
    if 'label_noise' in d:
        col = d['label_noise']['column']
        idx = _pick(rng, range(len(rows)), d['label_noise']['rate'])
        for i in idx:
            rows[i][col] = 1 - rows[i][col]
        record('label_noise', col, idx)
    for m in d.get('missing', []):
        when = m.get('when', {})
        eligible = [i for i, r in enumerate(rows) if all(r[c] == v for c, v in when.items())]
        idx = _pick(rng, eligible, m['rate'])
        for i in idx:
            rows[i][m['column']] = None
        record('missing', m['column'], idx)
    if 'duplicates' in d:
        n = len(rows)
        sources = _pick(rng, range(n), d['duplicates'])
        ids = {c: s for c, s in entity.get('columns', {}).items() if s['generator'] == 'id'}
        for j, src in enumerate(sources):
            copy = dict(rows[src])
            for c, s in ids.items():  # a copy is a new record with the same details
                number = s.get('start', 1) + n + j
                copy[c] = f"{s['prefix']}{number}" if s.get('prefix') else number
            rows.append(copy)
        found['duplicates'] = {'rows': list(range(n, n + len(sources))), 'of': sources}
    return found


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
    # A named real owner needs the same recorded permission as the real business name.
    if 'owner' in business:
        owner = business['owner']
        if business.get('fictional') is True:
            raise ValueError('owner may only be named for a real business with recorded permission')
        if not isinstance(owner, dict) or any(not isinstance(owner.get(k), str) or not owner[k].strip()
                for k in ('name', 'title')):
            raise ValueError('owner requires name and title strings')
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
    if world.get('profile', 'sql') not in PROFILES:
        raise ValueError('world profile must be sql or analytics')
    entities = world.get('entities')
    if not isinstance(entities, dict) or not entities or len(entities) > 100:
        raise ValueError('entities must contain 1 to 100 tables')
    cells = 0
    for name, entity in entities.items():
        if not IDENT.fullmatch(name) or not isinstance(entity, dict):
            raise ValueError(f'unsafe table name or invalid entity: {name}')
        profile = entity.get('profile', world.get('profile', 'sql'))
        if profile not in PROFILES:
            raise ValueError(f'{name}: profile must be sql or analytics')
        cap = PROFILES[profile]
        kind = entity.get('kind', 'table')
        if kind in ('series', 'interactions'):
            if kind == 'series':
                size = len(_check_series(name, entity, cap)) * 2
            else:
                size = _check_interactions(name, entity, entities, cap) * 3
            if profile == 'analytics':
                cells += size
            if 'defects' in entity:
                _check_defects(name, entity, cap)
            continue
        if kind != 'table':
            raise ValueError(f'{name}: kind must be table, series or interactions')
        if type(entity.get('rows')) is not int or not 0 <= entity['rows'] <= cap:
            raise ValueError(f'{name}: rows must be between 0 and {cap}')
        columns = entity.get('columns')
        if not isinstance(columns, dict) or not 1 <= len(columns) <= 50:
            raise ValueError(f'{name}: columns must contain 1 to 50 definitions')
        if profile == 'analytics':
            cells += entity['rows'] * len(entity_columns(entity))
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
            _check_column(name, column, spec, columns, entities, profile)
        if 'segments' in entity:
            _check_segments(name, entity, entities, profile)
        column_order(columns, name, entity.get('segments'))
        if 'defects' in entity:
            _check_defects(name, entity, cap)
    if cells > MAX_CELLS:
        raise ValueError(f'analytics entities hold {cells} cells; at most {MAX_CELLS} cells per dataset')


def _value(rng, spec, i, data, row=None, where=''):
    kind = spec['generator']
    if kind == 'id':
        number = spec.get('start', 1) + i
        return f"{spec['prefix']}{number}" if spec.get('prefix') else number
    if kind in {'choice', 'person_name'}:
        return rng.choice(spec['values'])
    if kind == 'weighted_choice':
        return rng.choices(spec['values'], weights=spec['weights'], k=1)[0]
    if kind in {'int_range', 'money_range'}:
        return rng.randint(spec['min'], spec['max'])
    if kind == 'date_range':
        days, cum = _day_table(spec)
        return rng.choices(days, cum_weights=cum, k=1)[0]
    if kind == 'fk':
        return rng.choice(data[spec['entity']])[spec['column']]
    if kind == 'normal':
        value = rng.gauss(spec['mean'], spec['sd'])
        value = min(max(value, spec.get('min', value)), spec.get('max', value))
        return _round(value, spec.get('round', 2))
    if kind == 'lognormal':
        value = rng.lognormvariate(math.log(spec['median']), spec['sigma'])
        return _round(min(value, spec.get('max', value)), spec.get('round', 2))
    if kind == 'poisson':
        return _poisson(rng, spec['lam'])
    if kind == 'bernoulli':
        return 1 if rng.random() < spec['p'] else 0
    if kind == 'linear':
        value = _score(spec, row, where) + rng.gauss(0, spec.get('noise_sd', 0))
        value = min(max(value, spec.get('min', value)), spec.get('max', value))
        return _round(value, spec.get('round', 2))
    if kind == 'logistic':
        return 1 if rng.random() < _sigmoid(_score(spec, row, where)) else 0
    if kind == 'binned_effect':
        x = row[spec['column']]
        if not _num(x):
            raise ValueError(f"{where}: binned_effect column {spec['column']} needs numbers, got {x!r}")
        return spec['deltas'][sum(1 for e in spec['edges'] if e <= x)]  # bisect_right
    if kind == 'text':
        templates = spec['templates']
        if 'tone_from' in spec:
            label, by_value = next(iter(spec['tone_from'].items()))
            templates = by_value.get(str(row[label]), templates)
        text = rng.choice(templates)
        for slot in PLACEHOLDER.findall(text):  # slot values hold no braces, so order is kept
            text = text.replace('{' + slot + '}', rng.choice(spec['slots'][slot]), 1)
        return text
    return None


def _fill_column(rng, specs, rows, data, where):
    """Draw one column for every row (analytics entities are drawn column by column).

    specs[i] is row i's spec: the column's own, merged with its segment's overrides.
    """
    col = where.split('.')[-1]
    if specs and specs[0]['generator'] == 'logistic' and 'target_rate' in specs[0]:
        # Class balance is set before any label is drawn: solve the intercept on all rows.
        rest = [_score(dict(spec, intercept=0), row, where) for spec, row in zip(specs, rows)]
        intercept = _solve_intercept(rest, specs[0]['target_rate'])
        for row, r in zip(rows, rest):
            row[col] = 1 if rng.random() < _sigmoid(intercept + r) else 0
        return
    for i, (spec, row) in enumerate(zip(specs, rows)):
        row[col] = _value(rng, spec, i, data, row, where)


def _series(rng, e: dict) -> list:
    """One row per period:
    max(0, round((base + trend*t) * weekly[dow] * monthly[month] * (1 + lift in a holiday)
                 + gauss(0, noise_sd) + (shift from the break date on)))"""
    dates = _periods(e)
    last = {'day': dates[-1], 'week': dates[-1] + timedelta(days=6)}.get(e['freq'])
    if last is None:  # month: up to the day before the next 1st
        y, m = dates[-1].year, dates[-1].month
        last = (date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)) - timedelta(days=1)
    ends = [d - timedelta(days=1) for d in dates[1:]] + [last]
    holidays = [(date.fromisoformat(h['date']), date.fromisoformat(h['date']) + timedelta(days=h['days'] - 1),
                 h['lift']) for h in e.get('holidays', [])]
    brk = e.get('break')
    brk_date = date.fromisoformat(brk['date']) if brk else None
    weekly, monthly = e.get('weekly'), e.get('monthly', {})
    date_col, value_col = e.get('date_column', 'date'), e.get('value_column', 'value')
    rows = []
    for t, (d, end) in enumerate(zip(dates, ends)):
        level = e['base'] + e.get('trend_per_period', 0) * t
        if weekly:
            level *= weekly[d.weekday()]
        level *= monthly.get(str(d.month), 1)
        for h_start, h_end, lift in holidays:
            if h_start <= end and h_end >= d:  # the holiday window overlaps this period
                level *= 1 + lift
        value = level + rng.gauss(0, e.get('noise_sd', 0))
        if brk and d >= brk_date:
            value += brk['shift']
        rows.append({date_col: d.isoformat(), value_col: max(0, int(round(value)))})
    return rows


def _interactions(rng, e: dict, data: dict) -> list:
    """User x item ratings from latent factors: k gauss(0, 1) per user (row order), then per
    item k gauss(0, 1) and a bias gauss(0, 0.5); each pair kept when random() < density;
    rating = clamp(round(mid + half * tanh(dot / k + bias) + gauss(0, noise_sd)), low, high)."""
    users, items, k = data[e['users']], data[e['items']], e['k']
    uc, ic, rc = e['user_column'], e['item_column'], e.get('rating_column', 'rating')
    user_f = [[rng.gauss(0, 1) for _ in range(k)] for _ in users]
    item_f, bias = [], []
    for _ in items:
        item_f.append([rng.gauss(0, 1) for _ in range(k)])
        bias.append(rng.gauss(0, 0.5))
    low, high = e['scale']
    mid, half = (low + high) / 2, (high - low) / 2
    rows = []
    for user, uf in zip(users, user_f):
        for item, itf, b in zip(items, item_f, bias):
            if rng.random() < e['density']:
                dot = sum(a * c for a, c in zip(uf, itf))
                r = round(mid + half * math.tanh(dot / k + b) + rng.gauss(0, e.get('noise_sd', 0)))
                rows.append({uc: user[uc], ic: item[ic], rc: min(high, max(low, int(r)))})
    return rows


def generate(world: dict, manifest: dict = None) -> dict:
    """{entity: rows}. Entities are drawn in sorted order, foreign-key targets first.

    With a `manifest` dict, manifest["defects"][entity] records every planned defect's rows.
    """
    validate_world(world)
    rng = random.Random(world['seed'])
    entities, data, active = world['entities'], {}, set()
    if manifest is not None:
        manifest.setdefault('defects', {})

    def finish(name, rows):
        # Defects come after an entity's own columns, so its clean draws never move.
        if 'defects' in entities[name]:
            found = _apply_defects(rng, entities[name], rows, name)
            if manifest is not None:
                manifest['defects'][name] = found
        data[name] = rows
        active.remove(name)

    def table(name):
        if name in data:
            return
        if name in active:
            raise ValueError(f'cyclic foreign key dependency at {name}')
        active.add(name)
        kind = entities[name].get('kind', 'table')
        if kind == 'series':
            return finish(name, _series(rng, entities[name]))
        if kind == 'interactions':
            table(entities[name]['users'])
            table(entities[name]['items'])
            return finish(name, _interactions(rng, entities[name], data))
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
        order = column_order(columns, name, entities[name].get('segments'))
        count = entities[name]['rows']
        segments = entities[name].get('segments', {})
        names = sorted(segments)
        merged = {seg: {c: dict(columns[c], **segments[seg].get('overrides', {}).get(c, {})) for c in columns}
                  for seg in names}
        weights = [segments[seg]['weight'] for seg in names]
        if entities[name].get('profile', world.get('profile', 'sql')) == 'analytics':
            # Segments first, then column by column, so a whole-column step (target_rate)
            # runs before the columns that depend on it.
            labels = rng.choices(names, weights=weights, k=count) if names else [None] * count
            rows = [{} for _ in range(count)]
            for col in order:
                specs = [merged[s][col] if s else columns[col] for s in labels]
                _fill_column(rng, specs, rows, data, f'{name}.{col}')
        else:
            # Row by row: the order every sql world has always been drawn in.
            rows, labels = [], []
            for i in range(count):
                seg = rng.choices(names, weights=weights, k=1)[0] if names else None
                specs = merged[seg] if seg else columns
                row = {}
                for col in order:
                    row[col] = _value(rng, specs[col], i, data, row, f'{name}.{col}')
                rows.append(row)
                labels.append(seg)
        if names:
            for row, seg in zip(rows, labels):
                row['_segment'] = seg
        finish(name, rows)

    for name in sorted(entities):
        table(name)
    return data


def to_csv(rows: list, columns: list) -> str:
    """CSV text with a header row; None becomes an empty field."""
    buf = io.StringIO()
    out = csv.writer(buf, lineterminator='\n')
    out.writerow(columns)
    for row in rows:
        out.writerow(['' if row.get(c) is None else row[c] for c in columns])
    return buf.getvalue()


def entity_columns(entity: dict) -> list:
    """The columns an entity's rows carry, in declared order; `_segment` last when segmented."""
    kind = entity.get('kind', 'table')
    if kind == 'series':
        return [entity.get('date_column', 'date'), entity.get('value_column', 'value')]
    if kind == 'interactions':
        return [entity['user_column'], entity['item_column'], entity.get('rating_column', 'rating')]
    return list(entity['columns']) + (['_segment'] if entity.get('segments') else [])


def check_recipe(recipe: dict) -> dict:
    """Validates a lesson's dataset recipe; returns the world with the recipe's seed."""
    if not isinstance(recipe, dict) or type(recipe.get('seed')) is not int:
        raise ValueError('dataset recipe needs an integer seed')
    files, world = recipe.get('files'), recipe.get('world')
    if not isinstance(files, dict) or not files:
        raise ValueError('dataset recipe needs at least one file')
    if not isinstance(world, dict) or 'use' in world:
        raise ValueError('dataset world must be written out in full; a library reference ("use") cannot load here')
    world = dict(world, seed=recipe['seed'])
    validate_world(world)
    for fname, spec in files.items():
        if not isinstance(fname, str) or not re.fullmatch(r'[A-Za-z0-9_-]+\.csv', fname):
            raise ValueError(f'dataset file name must be a plain name ending in .csv: {fname}')
        if not isinstance(spec, dict) or spec.get('entity') not in world['entities']:
            raise ValueError(f'{fname}: entity {spec.get("entity") if isinstance(spec, dict) else spec!r} '
                             f'is missing from the dataset world')
        drop = spec.get('drop', [])
        known = entity_columns(world['entities'][spec['entity']])
        if not isinstance(drop, list) or any(c not in known for c in drop):
            raise ValueError(f'{fname}: drop must list columns of {spec["entity"]}')
    return world


def build_files(recipe: dict, manifest: dict = None) -> dict:
    """{file name: CSV text} for a lesson's dataset recipe.

    recipe = {"seed": int, "files": {"x.csv": {"entity": str, "drop": [str]}}, "world": {...}}
    The recipe seed replaces the world seed, so one world can give each lesson its own draw.
    With a `manifest` dict, the planned defects' rows are recorded as in generate().
    """
    world = check_recipe(recipe)
    files = recipe['files']
    data = generate(world, manifest)
    out = {}
    for fname, spec in files.items():
        drop = set(spec.get('drop', []))
        cols = [c for c in entity_columns(world['entities'][spec['entity']]) if c not in drop]
        out[fname] = to_csv(data[spec['entity']], cols)
    return out
