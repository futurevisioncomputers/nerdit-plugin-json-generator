import json
import sqlite3

import pytest

from make_world_data import generate, load_world, sql_dump, validate_world


def world():
    return {
        'seed': 7,
        'business': {'name': 'Practice Mart', 'type': 'retailer', 'city': 'Surat',
                     'currency': 'INR', 'moneyUnit': 'paise', 'fictional': True},
        'cast': [{'name': 'Mira', 'role': 'analyst', 'trait': 'careful', 'look': 'blue shirt'}],
        'stages': ['source', 'clean', 'report'],
        'messiness': ['amount_text'], 'arc': {'lesson-01': 'Check a report total.'},
        'entities': {
            'stores': {'rows': 2, 'columns': {'store_id': {'generator': 'id', 'prefix': 'S'},
                                           'city': {'generator': 'choice', 'values': ['Surat', 'Pune']}}},
            'orders': {'rows': 5, 'columns': {
                'order_id': {'generator': 'id', 'prefix': 'O'},
                'store_id': {'generator': 'fk', 'entity': 'stores', 'column': 'store_id'},
                'amount_paise': {'generator': 'money_range', 'min': 100, 'max': 500},
                'units': {'generator': 'int_range', 'min': 1, 'max': 3},
                'sold_at': {'generator': 'date_range', 'start': '2026-01-01', 'end': '2026-02-28',
                            'monthWeights': {'1': 1, '2': 0}},
                'channel': {'generator': 'weighted_choice', 'values': ['web', 'shop'], 'weights': [1, 0]},
                'customer': {'generator': 'person_name', 'values': ['Aarav', 'Diya']},
            }},
        },
    }


def test_seeded_data_and_sql_round_trip():
    w = world()
    data = generate(w)
    assert data == generate(w)
    db = sqlite3.connect(':memory:')
    db.executescript(sql_dump(data))
    assert db.execute('select count(*) from orders').fetchone()[0] == 5
    assert all(r['channel'] == 'web' and r['sold_at'].startswith('2026-01') for r in data['orders'])
    assert {r['store_id'] for r in data['orders']} <= {r['store_id'] for r in data['stores']}


@pytest.mark.parametrize('change', [
    lambda w: w['entities']['orders'].update(rows=101),
    lambda w: w['entities']['orders']['columns'].update(email={'generator': 'person_name'}),
    lambda w: w['entities']['orders']['columns']['units'].update(min=10),
    lambda w: w['entities']['orders']['columns']['sold_at'].update(monthWeights={'1': 0, '2': 0}),
    lambda w: w['entities']['orders']['columns']['store_id'].update(entity='unknown'),
    lambda w: w['entities']['orders']['columns'].update(bad={'generator': 'execute'}),
    lambda w: w['business'].update(fictional=False),
    lambda w: w.update(entities={'bad; DROP TABLE x': {'rows': 1, 'columns': {}}}),
])
def test_invalid_worlds_fail_before_generation(change):
    w = world()
    change(w)
    with pytest.raises(ValueError):
        generate(w)


def test_real_business_requires_recorded_permission():
    w = world()
    w['business']['fictional'] = False
    w['business']['realName'] = {'approvedBy': 'owner', 'date': '2026-10-15', 'note': 'written approval'}
    validate_world(w)
    del w['business']['realName']['note']
    with pytest.raises(ValueError):
        validate_world(w)


def test_reference_resolution_cannot_escape_library(tmp_path):
    ref = tmp_path / 'course_world.json'
    ref.write_text(json.dumps({'use': '../secret'}))
    with pytest.raises(ValueError):
        load_world(ref)


def test_reversed_entity_order_still_resolves_foreign_keys():
    w = world()
    w['entities'] = dict(reversed(list(w['entities'].items())))
    assert generate(w) == generate(world())


def test_cycles_and_empty_foreign_keys_fail():
    w = world()
    w['entities']['stores']['columns']['parent'] = {'generator': 'fk', 'entity': 'orders', 'column': 'order_id'}
    with pytest.raises(ValueError):
        generate(w)
    w = world()
    w['entities']['stores']['rows'] = 0
    with pytest.raises(ValueError):
        generate(w)


def test_quotes_in_generated_values_are_sql_literals():
    w = world()
    w['entities']['stores']['columns']['city']['values'] = ["O'Brien"]
    data = generate(w)
    db = sqlite3.connect(':memory:')
    db.executescript(sql_dump(data))
    assert db.execute('select city from stores limit 1').fetchone()[0] == "O'Brien"


def test_empty_entity_still_has_a_table_in_the_sql_export():
    w = world()
    w['entities']['orders']['rows'] = 0
    data = generate(w)
    db = sqlite3.connect(':memory:')
    db.executescript(sql_dump(data, w))
    assert db.execute('select count(*) from orders').fetchone()[0] == 0


@pytest.mark.parametrize('value', [float('nan'), float('inf')])
def test_nonfinite_choice_values_are_rejected(value):
    w = world()
    w['entities']['stores']['columns']['city']['values'] = [value]
    with pytest.raises(ValueError):
        generate(w)


def test_existing_course_records_are_preserved_without_resampling():
    w = world()
    records = [{'store_id': 'S1', 'city': 'Surat'}, {'store_id': 'S2', 'city': 'Pune'}]
    w['entities']['stores']['records'] = records
    assert generate(w)['stores'] == records
    w['entities']['stores']['records'][0]['email'] = 'not allowed'
    with pytest.raises(ValueError):
        generate(w)


def test_preserved_mixed_sql_types_and_null_round_trip():
    data = {'example': [{'value': None}, {'value': 12}, {'value': '12x'}]}
    db = sqlite3.connect(':memory:')
    db.executescript(sql_dump(data))
    assert db.execute('select value, typeof(value) from example').fetchall() == [
        (None, 'null'), (12, 'integer'), ('12x', 'text')]
