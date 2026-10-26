import pytest

from check_refresh import check, compare, parts, sql_key

BASE = ('<div class="nerdit-wrapper nerdit-simple"><section><h2>1 — Clean text</h2>'
        '<p>Spaces hide inside text.</p>'
        '<pre class="nerdit-map">TRIM → removes outer spaces</pre>'
        '<div class="nerdit-figure" data-visual="diagram"><svg viewBox="0 0 360 80" role="img" aria-label="A">'
        '<text>row 1 · 09:00 · 10000</text></svg><div class="nerdit-figure-caption">Cap.</div></div>'
        '<ul><li>① TRIM removes the spaces.</li></ul>'
        '<h3 class="nerdit-runhead">TRIM(customer) <span class="why">— tidy names</span></h3>'
        '<p>TRIM cleans each name.</p>'
        '<div class="nerdit-run"><div class="nerdit-in"><pre data-lang="sql"><code>'
        'SELECT TRIM(customer),amount FROM staged;</code></pre></div>'
        '<div class="nerdit-out"><pre><code>| Aarav | 10 |</code></pre></div></div>'
        '<script type="text/plain" id="seed">CREATE TABLE staged(customer TEXT);</script>'
        '</section></div>')
NEW_FIG = ('<div class="nerdit-figure" data-visual="value-table"><table class="nerdit-vtable"><tr><td>1</td></tr>'
           '</table><div class="nerdit-figure-caption">Cap.</div></div>')
OLD_FIG = BASE[BASE.index('<div class="nerdit-figure"'):BASE.index("<ul>")]


def p(html):
    return parts(html)


def test_unchanged_lesson_passes_every_mode():
    for modes in ({"figures"}, {"sql-layout"}, {"trim"}, set()):
        assert compare(p(BASE), p(BASE), modes) == []


def test_figures_mode_allows_new_figure_new_steps_and_a_removed_map():
    after = (BASE.replace(OLD_FIG, NEW_FIG)
                 .replace("① TRIM removes the spaces.", "① TRIM drops the outer marks.")
                 .replace('<pre class="nerdit-map">TRIM → removes outer spaces</pre>', ""))
    assert compare(p(BASE), p(after), {"figures"}) == []
    assert compare(p(BASE), p(after), {"sql-layout"})


def test_illustrator_reading_steps_count_as_figure_scope():
    after = BASE.replace("<ul><li>① TRIM removes the spaces.</li></ul>",
                         '<ol class="nerdit-visual-read"><li>① TRIM drops the outer marks.</li></ol>')
    assert compare(p(BASE), p(after), {"figures"}) == []


def test_figures_mode_may_not_add_a_map():
    after = BASE.replace("<p>Spaces hide inside text.</p>",
                         '<p>Spaces hide inside text.</p><pre class="nerdit-map">NEW</pre>')
    assert any("text map" in x for x in compare(p(BASE), p(after), {"figures"}))


def test_prose_change_fails_in_every_mode():
    after = BASE.replace("Spaces hide inside text.", "Spaces hide.")
    for modes in ({"figures"}, {"sql-layout"}, {"trim"}, {"figures", "sql-layout", "trim"}):
        assert any(x.startswith("prose") for x in compare(p(BASE), p(after), modes))


def test_sql_layout_allows_whitespace_only():
    relaid = BASE.replace("SELECT TRIM(customer),amount FROM staged;",
                          "SELECT TRIM(customer), amount\nFROM staged;")
    assert compare(p(BASE), p(relaid), {"sql-layout"}) == []
    assert compare(p(BASE), p(relaid), {"figures"})
    changed = BASE.replace("FROM staged;", "FROM clean;")
    assert compare(p(BASE), p(changed), {"sql-layout"})
    assert compare(p(BASE), p(changed), {"trim"}) == []


def test_outputs_seeds_and_runheads_need_trim():
    for old, new in (("| Aarav | 10 |", "| Aarav | 11 |"),
                     ("TEXT);", "TEXT, amount INT);"),
                     ("TRIM cleans each name.", "TRIM tidies names.")):
        after = BASE.replace(old, new)
        assert compare(p(BASE), p(after), {"figures", "sql-layout"}), old
        assert compare(p(BASE), p(after), {"trim"}) == [], old


def test_sql_key_ignores_layout_but_not_tokens_or_literals():
    a = "SELECT r.row_id,r.line_bk FROM raw_line r WHERE x<>'a  b';"
    b = "SELECT\n  r.row_id,\n  r.line_bk\nFROM raw_line r\nWHERE x <> 'a  b';"
    assert sql_key(a) == sql_key(b)
    assert sql_key(a) != sql_key(a.replace("'a  b'", "'a b'"))
    assert sql_key("SELECT a FROM t") != sql_key("SELECT a FROM u")


def _files(d, concepts='{"teaches": ["TRIM"], "uses": []}',
           quiz='{"lessonQuestions": [], "assessmentQuestions": []}'):
    d.mkdir(exist_ok=True)
    (d / "x.html").write_text(BASE, encoding="utf-8")
    (d / "x.quiz.json").write_text(quiz, encoding="utf-8")
    (d / "x.concepts.json").write_text(concepts, encoding="utf-8")


def test_check_reads_quiz_and_concepts(tmp_path):
    before, after = tmp_path / "b", tmp_path / "a"
    _files(before)
    _files(after, concepts='{"teaches": ["TRIM"], "uses": [], '
                           '"visuals": [{"section": 1, "visual": "value-table", "illustration": null}]}')
    assert check(before, after, "x", {"figures"}) == []
    assert check(before, after, "x", {"sql-layout"})
    _files(after, quiz='{"lessonQuestions": [1], "assessmentQuestions": []}')
    assert any("quiz" in x for x in check(before, after, "x", {"figures"}))


def test_unknown_mode_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        check(tmp_path, tmp_path, "x", {"tidy"})


def test_sql_key_treats_comments_as_comments():
    a = "SELECT a -- the store's best day\nFROM t;"
    b = "SELECT a  -- the store's best day\nFROM t;"
    assert sql_key(a) == sql_key(b)
    # Joining the line after a comment onto it comments that code out: not layout.
    assert sql_key("FROM t -- paid only\nWHERE x = 1") != sql_key("FROM t -- paid only WHERE x = 1")
    assert sql_key("SELECT /* note */ a FROM t") == sql_key("SELECT /* note */\n  a\nFROM t")


SEED = '<script type="text/plain" id="seed">CREATE TABLE staged(customer TEXT);</script>'


def _with_seed(html, extra):
    return html.replace(SEED, SEED.replace("</script>", extra + "</script>"))


def test_trim_may_move_tables_and_rows_into_the_seed():
    after = _with_seed(BASE, "\nCREATE TABLE extra(x INT);\nINSERT INTO extra VALUES (1), (2);")
    assert compare(p(BASE), p(after), {"trim"}) == []


def test_trim_may_not_seed_a_view_even_over_shown_code():
    # Lesson 10 attempt 2: a view repeating an earlier shown CTE still let later blocks use
    # the name with no WITH, which works only because of a view the learner never met.
    after = _with_seed(BASE, "\nCREATE VIEW tidy AS\n  SELECT TRIM(customer), amount\n  FROM staged;")
    assert any("view tidy" in x for x in compare(p(BASE), p(after), {"trim"}))


def test_trim_may_not_seed_computed_tables():
    for extra, name in (("\nCREATE TABLE t AS SELECT TRIM(customer) FROM staged;", "t"),
                        ("\nCREATE TABLE u(c TEXT);\nINSERT INTO u SELECT TRIM(customer) FROM staged;", "u"),
                        ("\nCREATE TABLE w(c TEXT);\nINSERT INTO w (c)\nWITH x AS (SELECT 1) SELECT * FROM x;", "w")):
        after = _with_seed(BASE, extra)
        assert any(f"computed table {name}" in x for x in compare(p(BASE), p(after), {"trim"})), extra


def test_trim_may_not_hide_unshown_logic_in_a_view():
    # Lesson 10 (2026-10-17): a seeded `survivors` view held the tombstone filter the
    # section was teaching, so no shown code did what the heading promised.
    after = _with_seed(BASE, "\nCREATE VIEW tidy AS SELECT TRIM(customer) FROM staged WHERE amount > 0;")
    assert any("view tidy" in x for x in compare(p(BASE), p(after), {"trim"}))


def test_trim_may_not_add_a_trigger():
    after = _with_seed(BASE, "\nCREATE TRIGGER t AFTER INSERT ON staged BEGIN DELETE FROM staged; END;")
    assert any("trigger t" in x for x in compare(p(BASE), p(after), {"trim"}))


def test_a_view_the_original_already_seeded_is_not_rechecked():
    before = _with_seed(BASE, "\nCREATE TEMP VIEW old AS SELECT 1;")
    assert compare(p(before), p(before), {"trim"}) == []


SPEC = ('<script type="application/json" class="nerdit-screen" data-grid="xl">'
        '{"id": "trim-it", "app": "Excel", "layout": "sheet"}</script>')
DRAWN = ('<div class="nerdit-figure" data-visual="screen" data-screen="trim-it" style="max-width:440px">'
         '<svg viewBox="0 0 400 100" role="img" aria-label="A"><text>Excel</text></svg>'
         '<div class="nerdit-figure-caption">Trim names</div></div>'
         '<ol class="nerdit-visual-read" data-screen="trim-it"><li>① Click cell B2.</li></ol>')


def test_figures_mode_may_swap_an_img_for_a_screen_spec():
    with_img = BASE.replace("<p>Spaces hide inside text.</p>",
                            '<p>Spaces hide inside text.</p><p><img src="lesson1-trim.png" alt="lesson1-trim"></p>')
    swapped = BASE.replace("<p>Spaces hide inside text.</p>", "<p>Spaces hide inside text.</p>" + SPEC + DRAWN)
    assert compare(p(with_img), p(swapped), {"figures"}) == []
    assert any(x.startswith("figures") for x in compare(p(with_img), p(swapped), {"sql-layout"}))


def test_figures_mode_may_add_a_scene_spec():
    scene = '<script type="application/json" class="nerdit-scene">{"id": "shop", "subject": "A shop"}</script>'
    after = BASE.replace("<p>Spaces hide inside text.</p>", "<p>Spaces hide inside text.</p>" + scene)
    assert compare(p(BASE), p(after), {"figures"}) == []
    assert compare(p(BASE), p(after), {"trim"})


# Owner, 2026-10-26: lessons read too long. 'concise' shortens the prose and run-line leads and
# adds code walks, while every code block, output and seed stays exactly as it was.
def test_concise_mode_changes_prose_but_never_code_outputs_or_seeds():
    walk = ('<ol class="nerdit-codewalk"><li><code>SELECT TRIM(customer),amount FROM staged;</code> '
            'trims each name.</li></ol>')
    after = (BASE.replace("Spaces hide inside text.", "Spaces hide.")
                 .replace("<p>TRIM cleans each name.</p>", "<p>Notice the names.</p>")
                 .replace("</div></div><script", "</div></div>" + walk + "<script"))
    assert compare(p(BASE), p(after), {"concise"}) == []
    code = after.replace("FROM staged;</code></pre>", "FROM staged LIMIT 1;</code></pre>")
    assert any(x.startswith("code") for x in compare(p(BASE), p(code), {"concise"}))
    out = after.replace("| Aarav | 10 |", "| Aarav | 11 |")
    assert any(x.startswith("outputs") for x in compare(p(BASE), p(out), {"concise"}))
