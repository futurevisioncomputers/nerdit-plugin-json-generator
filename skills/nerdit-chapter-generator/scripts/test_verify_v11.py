"""Contract v11 checks (spec 2026-10-15 §1.7, §1.9). Shared helpers first; later tasks append tests."""
from verify_course import Report, parse, text_of, verify_structure


def wrap(body: str) -> dict:
    return {"lessons": [{"id": "x", "content": f'<div class="nerdit-wrapper nerdit-simple">{body}</div>'}]}


def run(body: str, contract: str = "v11") -> Report:
    rep = Report()
    verify_structure(rep, wrap(body), contract)
    return rep


def run_line(sql: str) -> str:
    return ('<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span>'
            f'<pre data-lang="sql"><code>{sql}</code></pre></div>'
            '<div class="nerdit-out"><span class="nerdit-tag">SQL shows</span><pre><code>x</code></pre></div></div>')


def test_text_of_keeps_document_order_and_decodes_entities():
    p = next(n for n in parse("<p>a <b>b</b> c &lt;&gt; d</p>").all if n.tag == "p")
    assert text_of(p) == "a b c <> d"


def test_text_of_survives_unclosed_tags():
    tree = parse("<section><p>one<p>two</section><p>three")
    whole = text_of(tree.root)
    assert "one" in whole and "two" in whole and "three" in whole


def test_warn_records_advice_without_failing():
    rep = Report()
    rep.warn(False, "advice")
    rep.warn(True, "fine")
    rep.check(True, "ok")
    assert rep.failures == [] and rep.warnings == ["advice"] and rep.passed == 1


def test_v11_keeps_every_v10_check():
    body = ('<div class="nerdit-figure" data-visual="diagram"><svg viewBox="0 0 640 200" role="img" '
            'aria-label="A"><text fill="var(--nb)">l</text></svg>'
            '<div class="nerdit-figure-caption">C.</div></div>')
    assert any("viewBox is 640 wide" in f for f in run(body).failures)
    assert any("viewBox is 640 wide" in f for f in run(body, "v10").failures)


LONG = "SELECT order_id, customer_id, amount_paise, sale_date FROM orders;"  # 66 chars


def test_v11_fails_a_long_sql_line_in_a_run_line():
    assert any("over 60 characters" in f for f in run(run_line(LONG)).failures)


def test_v11_accepts_sql_laid_out_one_clause_per_line():
    ok = "SELECT order_id, amount_paise\nFROM orders\nWHERE amount_paise &gt; 0;"
    assert not any("over 60" in f for f in run(run_line(ok)).failures)


def test_entities_count_as_one_character():
    # 59 visible characters; written with &lt;&gt; it is 65 bytes of HTML.
    line = "SELECT order_id, amount FROM orders WHERE status &lt;&gt; 'void';"
    assert not any("over 60" in f for f in run(run_line(line)).failures)


def test_v11_checks_sql_try_it_editors_but_not_python_ones():
    sql_box = f'<div class="nerdit-tryit" data-seed="s1"><textarea class="nerdit-tryit-editor">{LONG}</textarea></div>'
    py_box = ('<div class="nerdit-tryit" data-lang="python"><textarea class="nerdit-tryit-editor">'
              f'{"x = 1  # " + "a" * 70}</textarea></div>')
    assert any("try-it editor" in f for f in run(sql_box).failures)
    assert not any("try-it editor" in f for f in run(py_box).failures)


def test_v10_ignores_sql_line_width():
    assert not any("over 60" in f for f in run(run_line(LONG), "v10").failures)


def test_v11_fails_a_why_text_repeated_as_the_next_paragraph():
    body = ('<h3 class="nerdit-runhead">CASE <span class="why">— Reject bad records</span></h3>'
            '<p>Reject bad records.</p>')
    assert any("repeated as the next paragraph" in f for f in run(body).failures)


def test_v11_accepts_a_lead_that_says_what_the_code_does():
    body = ('<h3 class="nerdit-runhead">CASE <span class="why">— reject bad records</span></h3>'
            '<p>CASE gives each row one reason code.</p>')
    assert not any("repeated as the next paragraph" in f for f in run(body).failures)


from verify_course import is_dotted_record  # noqa: E402


def fig(kind):
    attr = f' data-visual="{kind}"' if kind else ""
    return (f'<div class="nerdit-figure"{attr}><table class="nerdit-vtable"><tr><td>1</td></tr></table>'
            '<div class="nerdit-figure-caption">Cap.</div></div>')


def svg_fig(label):
    return ('<div class="nerdit-figure" data-visual="diagram"><svg viewBox="0 0 360 100" role="img" '
            f'aria-label="A"><text fill="var(--tx)">{label}</text></svg>'
            '<div class="nerdit-figure-caption">C.</div></div>')


def section(inner):
    return f"<section><h2>1 — X</h2>{inner}</section>"


def test_dotted_record_detects_rows_not_lists():
    assert is_dotted_record("row 1 · 09:00 · 10000")
    assert is_dotted_record("rn 1 · row 3 · 12500 · kept")
    assert is_dotted_record("O2 · 10:00 · arrived 10:20")
    for label in ("O1 · O2 · O3 · O4 · O5", "MISSING_AMOUNT · BAD_AMOUNT",
                  "O3 · 10:30", "10000 · 12000 · 12500", "watermark · left out (>)"):
        assert not is_dotted_record(label), label


def test_v11_fails_a_figure_without_data_visual():
    assert any("needs data-visual" in f for f in run(fig(None)).failures)
    assert not any("needs data-visual" in f for f in run(fig("value-table")).failures)


def test_v11_fails_a_table_row_packed_into_a_dotted_label():
    assert any("packs a table row" in f for f in run(svg_fig("row 1 · 09:00 · 10000")).failures)
    assert not any("packs a table row" in f for f in run(svg_fig("O1 · O2 · O3")).failures)


def test_v10_ignores_data_visual_and_dotted_labels():
    failures = run(fig(None) + svg_fig("row 1 · 09:00 · 10000"), "v10").failures
    assert not any("data-visual" in f or "packs a table row" in f for f in failures)


def test_v11_warns_a_concept_section_without_a_main_visual():
    assert any("has no main visual" in w for w in run(section("<p>Only prose.</p>")).warnings)
    chart = section('<div class="nerdit-chart-wrap"><canvas></canvas></div>')
    assert not any("has no main visual" in w for w in run(chart).warnings)


def test_v11_warns_when_every_section_uses_the_same_visual():
    same = "".join(section(fig("value-table")) for _ in range(3))
    assert any("same visual" in w for w in run(same).warnings)
    mixed = section(fig("value-table")) + section(fig("decision-grid")) + section(fig("unit-tiles"))
    assert not any("same visual" in w for w in run(mixed).warnings)


from verify_course import verify_density  # noqa: E402


def lesson_with(blocks: list[str]) -> dict:
    return {"lessons": [{"id": "x", "content": "".join(run_line(b) for b in blocks)}]}


def test_density_warns_a_long_block_and_a_heavy_concept_lesson():
    rep = Report()
    verify_density(rep, lesson_with(["SELECT 1;\n" * 20]), [{"id": "x", "focus": "concept"}])
    assert any("code block 1 shows 20 lines" in w for w in rep.warnings)
    rep = Report()
    verify_density(rep, lesson_with(["SELECT 1;\n" * 10] * 5), [{"id": "x", "focus": "concept"}])
    assert any("max 40 for concept" in w for w in rep.warnings)


def test_density_defaults_to_hands_on():
    rep = Report()
    verify_density(rep, lesson_with(["SELECT 1;\n" * 10] * 5), [{"id": "x"}])
    assert not any("max 100" in w for w in rep.warnings)


def test_a_figure_without_data_visual_still_counts_as_the_main_visual():
    rep = run(section(fig(None)) * 3)
    assert not any("has no main visual" in w for w in rep.warnings)
    assert not any("same visual" in w for w in rep.warnings)
    assert any("needs data-visual" in f for f in rep.failures)


def test_cli_prints_unicode_messages_through_a_pipe(tmp_path):
    """Windows pipes default to cp1252; v11 messages carry ④ · § and must not crash the CLI."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path
    body = ('<div class="nerdit-figure"><svg viewBox="0 0 360 80" role="img" aria-label="A">'
            '<text>④ row 1 · 09:00 · 10000</text></svg><div class="nerdit-figure-caption">C</div></div>')
    out = tmp_path / "out.json"
    inp = tmp_path / "in.json"
    out.write_text(json.dumps(wrap(body)), encoding="utf-8")
    inp.write_text(json.dumps([{"id": "x", "title": "T", "description": "d"}]), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    script = Path(__file__).resolve().parent / "verify_course.py"
    r = subprocess.run([sys.executable, str(script), "--contract", "v11", "--input", str(inp),
                        "--output", str(out)], capture_output=True, env=env)
    assert b"Traceback" not in r.stderr, r.stderr.decode("utf-8", "replace")[-300:]
    assert "packs a table row" in r.stdout.decode("utf-8")


def test_dotted_record_ignores_markers_and_keys_codes_by_prefix():
    # A leading ① must not change the verdict; different id prefixes are different fields.
    assert is_dotted_record("customer_sk 1 · C1 · Surat")
    assert is_dotted_record("① customer_sk 1 · C1 · Surat")
    assert is_dotted_record("seq 5 · O4 · NULL · rn 1")
    assert not is_dotted_record("① O1 · O2 · O3")
    # Plain number lists, signed or with a k suffix, are lists, not records.
    assert not is_dotted_record("1 · 2 · -1")
    assert not is_dotted_record("0.5 · 1 · 1.5k")
