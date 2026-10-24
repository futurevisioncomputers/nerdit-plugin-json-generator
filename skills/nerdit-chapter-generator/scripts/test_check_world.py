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


def test_a_dataset_lesson_file_table_marked_derived_passes_the_world_check():
    from check_world import check_lesson
    from test_world_data import world as small_world
    w = small_world()
    note = '<div class="nerdit-data-note">All records, people and amounts are synthetic, made for teaching.</div>'
    table = ('<div class="nerdit-figure" data-visual="value-table"{attr}><table class="nerdit-vtable">'
             '<tr><th>File</th><th>Columns</th></tr><tr><td>orders.csv</td><td>order_id, units</td></tr>'
             '</table><div class="nerdit-figure-caption">One file.</div></div>')
    marked = note + table.format(attr=' data-world-derived="dataset block: files and columns"')
    fails, _ = check_lesson(marked, w, generate(w))
    assert not [f for f in fails if "figure" in f]
    fails, _ = check_lesson(note + table.format(attr=""), w, generate(w))
    assert any("data-world-derived" in f for f in fails)


# ---- SVG labels (figures that are not record tables) ----

def svg_figure(*labels, visual='diagram'):
    texts = ''.join(f'<text x="10" y="{20 * i + 20}">{label}</text>' for i, label in enumerate(labels))
    return (f'<div class="nerdit-figure" data-visual="{visual}"><svg viewBox="0 0 300 100" role="img" '
            f'aria-label="A figure">{texts}</svg><div class="nerdit-figure-caption">The figure.</div></div>')


def svg_errors(body):
    w = world()
    errors, _ = check_lesson(lesson(body=body), w, generate(w))
    return [e for e in errors if e.startswith('figure svg')]


def test_svg_numbers_must_come_from_the_lesson():
    # Found in a live lesson: a figure drew example rows (₹4,000) the lesson never states.
    errors = svg_errors('<p>Store S1 sold 450 units on 2026-01-03.</p>' + svg_figure('450 units', '3 Jan', '₹4,000'))
    assert errors == ['figure svg 1: draws 4,000, which the lesson and its seed never state']


def test_svg_numbers_allow_grouping_and_units():
    body = '<p>About 12750000 tokens, and ₹500000 in July.</p>' + svg_figure('≈12.75M tokens', '₹5,00,000')
    assert svg_errors(body) == []


def test_svg_world_name_the_lesson_never_shows_fails():
    # Aarav and Diya are both world customers; the lesson only ever shows Aarav.
    errors = svg_errors('<p>Aarav buys first.</p>' + svg_figure('Aarav', 'Diya', 'Report'))
    assert errors == ['figure svg 1: draws Diya, a world record the lesson never shows']


def test_drawn_screens_are_left_to_check_screens():
    screen = ('<div class="nerdit-figure" data-visual="screen" data-screen="x" style="max-width:440px">'
              '<svg viewBox="0 0 400 90" role="img" aria-label="A"><text>99999</text></svg>'
              '<div class="nerdit-figure-caption">c</div></div>'
              '<ol class="nerdit-visual-read" data-screen="x"><li>① Click cell B2.</li></ol>')
    assert svg_errors('<p>No numbers here.</p>' + screen) == []


def test_svg_numbers_found_in_table_cells_pass():
    # Cells sit side by side in the HTML; C9 then 8000 must not read as "C98000".
    body = '<table><tr><td>5</td><td>L4</td><td>C9</td><td>8000</td></tr></table>' + svg_figure('5 · L4 · C9 · 8000')
    assert svg_errors(body) == []


def test_a_world_value_inside_a_longer_label_is_not_a_record():
    # "Pune stores" names a stage, not the city record; a label that is just "Pune" is.
    assert svg_errors('<p>Stores report daily.</p>' + svg_figure('Pune stores')) == []
    assert svg_errors('<p>Stores report daily.</p>' + svg_figure('Pune')) == [
        'figure svg 1: draws Pune, a world record the lesson never shows']


# Check c: practice data comes from the world, never typed in.

def run(code):
    return ('<div class="nerdit-run"><div class="nerdit-in"><pre data-lang="python"><code>'
            f'{code}</code></pre></div></div>')


def files_spec(*files):
    import json
    return (f'<script type="application/json" class="nerdit-files-spec">'
            f'{json.dumps({"python": "3.12", "files": list(files)})}</script>')


def test_typed_in_rows_over_eight_fail():
    w = world()
    data = generate(w)
    nine = ', '.join(f'({i}, {i * 10})' for i in range(9))
    errors, _ = check_lesson(lesson(body=run(f'orders = [{nine}]')), w, data)
    assert any('9 rows typed in' in e for e in errors)
    cols = ', '.join(str(i) for i in range(12))
    errors, _ = check_lesson(lesson(body=run(f'df = pd.DataFrame({{"units": [{cols}]}})')), w, data)
    assert any('12 rows typed in' in e for e in errors)
    eight = ', '.join(f'({i}, {i})' for i in range(8))
    assert check_lesson(lesson(body=run(f'orders = [{eight}]')), w, data)[0] == []


def test_files_spec_world_sources_must_exist_in_the_world():
    w = world()
    data = generate(w)
    good = {'name': 'L01-S1-orders.csv', 'from': {'world': 'orders', 'rows': [data['orders'][0]['order_id']],
                                                  'columns': ['order_id', 'units']}}
    assert check_lesson(lesson(body=files_spec(good)), w, data)[0] == []
    bad_entity = {**good, 'from': {'world': 'refunds'}}
    bad_row = {**good, 'from': {'world': 'orders', 'rows': ['O999']}}
    bad_col = {**good, 'from': {'world': 'orders', 'columns': ['colour']}}
    typed = {'name': 'L01-S2-x.json', 'from': {'json': [{'a': i} for i in range(9)]}}
    errors, _ = check_lesson(lesson(body=files_spec(bad_entity, bad_row, bad_col, typed)), w, data)
    text = '\n'.join(errors)
    assert 'refunds' in text and 'O999' in text and 'colour' in text and 'L01-S2-x.json: 9 rows typed in' in text
