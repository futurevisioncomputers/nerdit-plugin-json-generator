from check_world import check_lesson
from make_world_data import generate
from test_world_data import world


def lesson(seed='', body=''):
    return ('<div class="nerdit-wrapper"><div data-visual="course-map"></div>'
            '<p class="nerdit-data-note">All records, people and amounts are synthetic, made for teaching.</p>'
            f'<script type="text/plain">{seed}</script>{body}</div>')


def test_known_slice_passes_unknown_name_and_price_fail():
    w = world()
    data = generate(w)
    amount = data['orders'][0]['amount_paise']
    assert check_lesson(lesson(f"CREATE TABLE orders(amount_paise); INSERT INTO orders VALUES ({amount});"), w, data)[0] == []
    errors, _ = check_lesson(lesson("CREATE TABLE stores(city); INSERT INTO stores VALUES ('Unknown City');"), w, data)
    assert any('Unknown City' in e for e in errors)
    errors, _ = check_lesson(lesson('CREATE TABLE orders(amount_paise); INSERT INTO orders VALUES (999999);'), w, data)
    assert any('999999' in e for e in errors)


def test_defects_are_scoped_to_entity_row_column_and_value():
    w = world()
    w['messiness'] = ['amount_paise']
    seed = '-- defect: orders row 1 amount_paise "12x"\nCREATE TABLE orders(amount_paise); INSERT INTO orders VALUES (\'12x\');'
    assert check_lesson(lesson(seed), w, generate(w))[0] == []
    assert check_lesson(lesson(seed.replace('row 1', 'row 2')), w, generate(w))[0]
    assert check_lesson(lesson(seed.replace('"12x"', '"13x"')), w, generate(w))[0]
    assert check_lesson(lesson(seed), dict(w, messiness=[]), generate(w))[0]


def test_real_business_disclosure_is_required():
    w = world()
    w['business'].update(fictional=False, realName={'approvedBy': 'owner', 'date': '2026-10-15', 'note': 'written'})
    errors, _ = check_lesson(lesson(), w, generate(w))
    assert any('permission' in e for e in errors)
    html = lesson().replace('All records', 'Business name used with permission. All records')
    assert check_lesson(html, w, generate(w))[0] == []


def test_figure_values_are_checked_against_the_named_column():
    w = world()
    fig = '<div class="nerdit-figure" data-world-entity="stores"><table><thead><tr><th data-world-column="city">City</th></tr></thead><tbody><tr><td>Unknown City</td></tr></tbody></table></div>'
    assert any('Unknown City' in e for e in check_lesson(lesson(body=fig), w, generate(w))[0])


def test_unbound_figures_fail_instead_of_silently_skipping_data():
    w = world()
    fig = '<div class="nerdit-figure" data-visual="value-table"><table><tr><td>Invented</td></tr></table></div>'
    assert any('data-world-entity' in e for e in check_lesson(lesson(body=fig), w, generate(w))[0])


def test_attach_is_rejected_and_bad_sql_is_reported():
    w = world()
    for seed in ("ATTACH DATABASE 'other.db' AS other;", 'not sql'):
        assert any('seed' in e for e in check_lesson(lesson(seed), w, generate(w))[0])


def test_stages_missing_map_is_advice():
    w = world()
    errors, warnings = check_lesson(lesson().replace('data-visual="course-map"', ''), w, generate(w))
    assert not errors and any('course-map' in e for e in warnings)


def test_disclosure_after_the_first_table_fails():
    w = world()
    assert any('disclosure' in e for e in check_lesson('<table></table>' + lesson(), w, generate(w))[0])


def test_multiple_headers_and_rows_keep_document_order():
    w = world()
    data = generate(w)
    rows = ''.join(f'<tr><td>{r["store_id"]}</td><td>{r["city"]}</td></tr>' for r in data['stores'])
    fig = ('<div class="nerdit-figure" data-world-entity="stores"><table>'
           '<thead><tr><th>store_id</th><th>city</th></tr></thead>'
           f'<tbody>{rows}</tbody></table></div>')
    assert check_lesson(lesson(body=fig), w, data)[0] == []


def test_existing_foreign_key_enable_pragma_is_allowed_but_storage_pragmas_are_not():
    w = world()
    data = generate(w)
    assert check_lesson(lesson('PRAGMA foreign_keys=ON;'), w, data)[0] == []
    assert any('seed' in e for e in check_lesson(lesson('PRAGMA journal_mode=WAL;'), w, data)[0])
