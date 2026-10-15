from check_sql_outputs import check_lesson, parse_table

SEED = ('<script type="text/plain" id="s1">CREATE TABLE t (city TEXT, amount INTEGER);'
        "INSERT INTO t VALUES ('Pune', 200), ('Mumbai', 100);</script>")


def run(sql, out):
    return ('<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span>'
            f'<pre data-lang="sql"><code>{sql}</code></pre></div><div class="nerdit-out">'
            f'<span class="nerdit-tag">SQL shows</span><pre><code>{out}</code></pre></div></div>')


TABLE = "+--------+\n| total  |\n+--------+\n| 300    |\n+--------+"


def test_parse_table():
    assert parse_table(TABLE) == [["total"], ["300"]]
    assert parse_table("UNIQUE constraint failed") is None


def test_matching_output_counts_as_match():
    r = check_lesson(SEED + run("SELECT SUM(amount) AS total FROM t;", TABLE))
    assert (r["examples"], r["match"], r["mismatch"]) == (1, 1, [])


def test_mismatching_output_is_reported():
    r = check_lesson(SEED + run("SELECT SUM(amount) AS total FROM t WHERE city='Pune';", TABLE))
    assert r["match"] == 0 and "example 1" in r["mismatch"][0] and "200" in r["mismatch"][0]


def test_error_outputs_match_by_message_and_others_are_unchecked():
    html = (SEED + run("INSERT INTO nope VALUES (1);", "Error: no such table: nope")
            + run("CREATE INDEX i ON t(city);", "Index created."))
    r = check_lesson(html)
    assert r["match"] == 1 and len(r["unchecked"]) == 1


def test_every_result_set_of_a_multi_statement_example_is_compared():
    two = ("+--------+\n| pune   |\n+--------+\n| 200    |\n+--------+\n"
           "+--------+\n| mumbai |\n+--------+\n| 100    |\n+--------+")
    sql = ("SELECT amount AS pune FROM t WHERE city='Pune';\n"
           "SELECT amount AS mumbai FROM t WHERE city='Mumbai';")
    r = check_lesson(SEED + run(sql, two))
    assert (r["match"], r["mismatch"]) == (1, [])


def test_example_that_builds_the_seed_tables_runs_on_an_empty_database():
    build = ("CREATE TABLE t (city TEXT, amount INTEGER);"
             "INSERT INTO t VALUES ('Pune', 200), ('Mumbai', 100);"
             "SELECT SUM(amount) AS total FROM t;")
    r = check_lesson(SEED + run(build, TABLE))
    assert (r["match"], r["mismatch"]) == (1, [])


def test_numbers_match_whether_shown_as_30_or_30_point_0():
    shown = "+--------+\n| avg_amt |\n+--------+\n| 150.0  |\n+--------+"
    r = check_lesson(SEED + run("SELECT AVG(amount) AS avg_amt FROM t;", shown))
    assert (r["match"], r["mismatch"]) == (1, [])


def test_query_plans_are_left_for_a_human():
    shown = "+----+--------+\n| id | detail |\n+----+--------+\n| 2  | SCAN t |\n+----+--------+"
    r = check_lesson(SEED + run("EXPLAIN QUERY PLAN SELECT * FROM t;", shown))
    assert r["mismatch"] == [] and len(r["unchecked"]) == 1


def canonical(sql, out_html):
    """The run line exactly as CORE.md §4 writes it: a copy button inside the input <pre>."""
    return ('<div class="nerdit-run">\n  <div class="nerdit-in">\n    <span class="nerdit-tag">You type</span>\n'
            '    <pre data-lang="sql"><button class="nerdit-copy-btn" onclick="copyCode(this)">Copy</button>'
            f'<code>{sql}</code></pre>\n  </div>\n  <div class="nerdit-out">\n'
            f'    <span class="nerdit-tag">SQL shows</span>\n    {out_html}\n  </div>\n</div>')


def test_canonical_run_line_with_copy_button_is_checked():
    r = check_lesson(SEED + canonical("SELECT SUM(amount) AS total FROM t WHERE city='Pune';",
                                      f"<pre><code>{TABLE}</code></pre>"))
    assert r["examples"] == 1 and len(r["mismatch"]) == 1


def test_prose_output_does_not_swallow_the_next_example():
    html = (SEED + canonical("UPDATE t SET amount = amount;", "<p>2 rows changed.</p>")
            + run("SELECT SUM(amount) AS total FROM t WHERE city='Pune';", TABLE))
    r = check_lesson(html)
    assert r["examples"] == 2 and len(r["unchecked"]) == 1 and len(r["mismatch"]) == 1
    assert "example 2" in r["mismatch"][0]
