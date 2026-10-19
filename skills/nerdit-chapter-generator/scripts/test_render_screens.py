import html as htmllib
import re
import sys
import xml.dom.minidom
from pathlib import Path

import pytest

from excel_eval import evaluate_many
from render_screens import figure_block, main, reading_steps, render_lesson, render_svg, results_for
from screens import drawn_strings
from test_screens import ADS, ADS_TEXT, DEDUPE, DEDUPE_TEXT, GRID, PIP, XL, XL_TEXT, block, lesson

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "nerdit-lesson-illustrator" / "scripts"))
from svgcheck import check_svg  # noqa: E402

G = (GRID["headers"], GRID["rows"])
TEXT = re.compile(r"<text\b[^>]*>(.*?)</text>", re.S)
MARKERS = "①②③④⑤"
SPECS = [XL, DEDUPE, ADS, PIP]


def texts(svg):
    return [htmllib.unescape(re.sub(r"<[^>]+>", "", t)) for t in TEXT.findall(svg)]


def draw(spec, grid=G):
    grid = grid if spec["layout"] == "sheet" else None
    results, problems = results_for(spec, grid)
    assert problems == []
    return render_svg(spec, grid, results), results


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s["id"])
def test_viewbox_fits_a_phone(spec):
    svg, _ = draw(spec)
    width = float(re.search(r'viewBox="0 0 ([\d.]+) ', svg).group(1))
    assert width <= 400


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s["id"])
def test_tokens_only(spec):
    svg, _ = draw(spec)
    assert not re.search(r"(?<!&)#[0-9a-fA-F]{3,8}\b", svg)
    for value in re.findall(r'\b(?:fill|stroke)="([^"]*)"', svg):
        assert value.startswith("var(--") or value == "none", value


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s["id"])
def test_passes_svgcheck(spec):
    svg, results = draw(spec)
    assert check_svg(svg, drawn_strings(spec) + list(results.values()), len(spec["steps"])) == []


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s["id"])
def test_markers_match_steps(spec):
    svg, results = draw(spec)
    drawn = "".join(texts(svg))
    assert sum(drawn.count(m) for m in MARKERS) == len(spec["steps"])
    block_html = figure_block(spec, svg, reading_steps(spec, results))
    assert block_html.count("<li>") == len(spec["steps"])


def test_reading_step_wording():
    assert reading_steps(XL, {"H3": "Chennai"}) == [
        "Click cell H3.", 'Type =XLOOKUP("Isha",B2:B7,D2:D7) in H3.', "H3 shows Chennai."]
    assert reading_steps(DEDUPE, {}) == ["Click Data, then Remove Duplicates.", "Click OK."]
    assert reading_steps(ADS, {}) == ["Click Campaigns, then Create.", "Set Objective to Sales.",
                                      "Set Daily budget to ₹500."]
    assert reading_steps(PIP, {}) == ["Type pip install pandas in line 1.", "Press Enter."]
    assert reading_steps(dict(ADS, steps=[{"do": "select", "target": "Publish"}]), {}) == ["Select Publish."]


def test_figure_block_markup():
    out = figure_block(XL, "<svg></svg>", ["Click cell H3.", "H3 shows Chennai."])
    assert out == ('<div class="nerdit-figure" data-visual="screen" data-screen="xlookup-city" '
                   'style="max-width:440px"><svg></svg><div class="nerdit-figure-caption">'
                   "Find Isha&#x27;s city with XLOOKUP</div></div>"
                   '<ol class="nerdit-visual-read" data-screen="xlookup-city">'
                   "<li>① Click cell H3.</li><li>② H3 shows Chennai.</li></ol>")


def test_markers_on_one_part_read_left_to_right():
    svg, _ = draw(XL)  # ① select H3 and ③ result H3 share the cell
    xs = {m: float(x) for x, m in re.findall(r'<text x="([\d.]+)"[^>]*>([①②③])</text>', svg)}
    assert xs["①"] < xs["③"]


def test_only_the_clicked_chip_gets_marker_room():
    svg, _ = draw(ADS)
    rects = {t: (float(x), float(w)) for x, w, t in re.findall(
        r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)"[^>]*rx="12"[^>]*/><text[^>]*>([^<]*)</text>', svg)}
    gap = rects["Create"][0] - sum(rects["Campaigns"])
    assert gap <= 12


def test_code_keeps_spaces():
    svg, _ = draw(dict(PIP, output=["   region  sales"]))
    assert re.search(r'<text[^>]*xml:space="preserve"[^>]*>   region  sales</text>', svg)


# ---- sheet ----

def test_shows_only_the_view_window():
    svg, _ = draw(dict(XL, view={"columns": ["B", "D", "H"], "rows": [1, 4], "active": "H3"}))
    shown = texts(svg)
    assert "Aarav" in shown and "Kabir" in shown
    assert "Meera" not in shown and "Sales" not in shown  # row 5; column C


def test_result_cell_shows_engine_value():
    svg, results = draw(XL)
    assert results == {"H3": "Chennai"}
    assert re.search(r'<text[^>]*data-cell="H3"[^>]*>Chennai</text>', svg)


def test_numbers_use_engine_format():
    spec = dict(XL, view={"columns": ["E", "H"], "rows": [1, 3], "active": "H3"},
                steps=[{"do": "type", "target": "H3", "text": "=E2"}, {"do": "result", "target": "H3"}])
    svg, _ = draw(spec)
    (expected,) = evaluate_many(G[0], G[1], ["=E2"])
    assert re.search(rf'<text[^>]*data-cell="H3"[^>]*>{expected["text"]}</text>', svg)
    assert re.search(r'<text[^>]*data-cell="E2"[^>]*>45000</text>', svg)


def test_gap_column_between_non_adjacent_columns():
    svg, _ = draw(XL)
    heads = re.findall(r"<text[^>]*data-head[^>]*>(.*?)</text>", svg)
    assert heads == ["B", "…", "D", "…", "H"]
    assert 'data-cell="H2"' not in svg  # blank cells stay blank


def test_too_wide_view_is_a_problem():
    wide = {"headers": ["Customer name", "Order region", "Payment mode", "Delivery city"],
            "rows": [["Aarav Sharma12", "North Zone 12", "Credit card 1", "Bengaluru 123"]]}
    spec = dict(XL, view={"columns": ["A", "B", "C", "D"], "rows": [1, 2], "active": "A2"},
                steps=[{"do": "select", "target": "A2"}], image="A", why="the learner must see the columns")
    html = lesson(XL_TEXT, block(spec, grid="xl-staff"), grid=wide)
    _, problems = render_lesson(html)
    assert any("phone" in p for p in problems)


def test_formula_error_is_a_problem():
    spec = dict(XL, steps=[{"do": "type", "target": "H3", "text": "=FOO(1)"}, {"do": "result", "target": "H3"}])
    _, problems = results_for(spec, G)
    assert any("H3: =FOO(1) gives #NAME?" in p for p in problems)


# ---- editor and app ----

def test_editor_draws_lines_and_output():
    svg, _ = draw(PIP)
    shown = texts(svg)
    assert "$" in "".join(shown)
    assert "pip install pandas" in shown and "Successfully installed pandas" in shown
    code = dict(PIP, tool="editor", lines=["import pandas as pd", "df = pd.read_csv('sales.csv')"], output=[],
                steps=[{"do": "select", "target": "line 2"}])
    shown = texts(draw(code)[0])
    assert "1" in shown and "2" in shown and "df = pd.read_csv('sales.csv')" in shown


def test_app_draws_path_and_panel():
    shown = texts(draw(ADS)[0])
    for word in ("Meta Ads Manager", "Campaigns", "Create", "Objective", "Sales", "Daily budget", "₹500", "Publish"):
        assert word in shown


def test_message_wraps_at_34():
    message = "Sales rose 12% in March because the Diwali offer brought back many old customers."
    spec = dict(ADS, panel=[{"kind": "message", "who": "model", "text": message}],
                steps=[{"do": "click", "path": ["Create"]}])
    lines = [t for t in texts(draw(spec)[0]) if t and t in message and len(t) > 3]
    assert " ".join(lines) == message
    assert all(len(line) <= 34 for line in lines) and len(lines) == 3


def test_special_characters_are_escaped():
    formula = '=IF(E2<45000,"low&ok","hi")'
    spec = dict(XL, steps=[{"do": "type", "target": "H3", "text": formula}, {"do": "result", "target": "H3"}])
    svg, results = draw(spec)
    xml.dom.minidom.parseString(svg)
    assert formula in texts(svg) and results["H3"] == "hi"
    chat = dict(ADS, panel=[{"kind": "message", "who": "you", "text": "Why <did> 'sales' & \"profit\" fall?"}],
                steps=[{"do": "click", "path": ["Create"]}])
    xml.dom.minidom.parseString(draw(chat)[0])


# ---- lessons ----

def two_screen_lesson():
    return lesson(XL_TEXT + " " + ADS_TEXT, block(XL, grid="xl-staff"), block(ADS))


def test_render_is_idempotent():
    once, problems = render_lesson(two_screen_lesson())
    assert problems == [] and once.count('data-visual="screen"') == 2
    twice, problems = render_lesson(once)
    assert problems == [] and twice == once


def test_rerender_replaces_only_its_own_block():
    once, _ = render_lesson(two_screen_lesson())
    ads_block = re.search(r'<div class="nerdit-figure" data-visual="screen" data-screen="ads-new".*?</ol>', once, re.S).group(0)
    edited = once.replace("Find Isha's city with XLOOKUP", "Look up Isha's city")
    again, problems = render_lesson(edited)
    assert problems == []
    assert '<div class="nerdit-figure-caption">Look up Isha&#x27;s city</div>' in again
    assert ads_block in again and again.count('data-visual="screen"') == 2


def test_b_spec_gets_no_figure():
    stale = figure_block(DEDUPE, "<svg></svg>", ["Click OK."])
    html = lesson(DEDUPE_TEXT, block(DEDUPE, grid="xl-staff") + stale)
    out, problems = render_lesson(html)
    assert problems == [] and 'data-screen="dedupe"' not in out


def test_cli_writes_only_clean_lessons(tmp_path):
    good = tmp_path / "l1.html"
    good.write_text(two_screen_lesson(), encoding="utf-8")
    for lid in ("l1", "l2"):
        (tmp_path / f"{lid}.quiz.json").write_text("{}", encoding="utf-8")
    assert main(["--dir", str(tmp_path), "--id", "l1"]) == 0
    assert good.read_text(encoding="utf-8").count('data-visual="screen"') == 2
    bad = tmp_path / "l2.html"
    broken = lesson(XL_TEXT, block(dict(XL, layout="canvas"), grid="xl-staff"))
    bad.write_text(broken, encoding="utf-8")
    assert main(["--dir", str(tmp_path)]) == 1
    assert bad.read_text(encoding="utf-8") == broken


# ---- app colours ----

ROLES = ("bar", "bar-ink", "accent", "accent-ink", "surface", "soft", "ink")


def test_excel_screen_uses_excel_colours():
    svg, _ = draw(XL)
    assert 'fill="var(--app-excel-bar, var(--bg-soft))"' in svg


def test_unknown_app_uses_nerdit_colours():
    svg, _ = draw(dict(ADS, app="New App"))
    assert "--app-" not in svg


def test_terminal_tool_falls_back_to_terminal_theme():
    svg, _ = draw(dict(PIP, app="My Box"))
    assert "--app-terminal-surface" in svg


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s["id"])
def test_markers_stay_nerdit_orange(spec):
    svg, _ = draw(spec)
    for fill in re.findall(r'fill="([^"]*)"[^>]*>[①②③④⑤]</text>', svg):
        assert fill == "var(--orange)"


def test_every_theme_has_all_roles_in_css():
    from screens import APP_THEMES
    css = (Path(__file__).resolve().parent.parent / "references" / "css10-brand.css").read_text(encoding="utf-8")
    for key, _ in APP_THEMES:
        for role in ROLES:
            assert re.search(rf"--app-{key}-{role}:\s*#[0-9A-Fa-f]{{6}};", css), f"--app-{key}-{role}"


def test_cell_spaces_show_as_open_box():
    grid = {"headers": GRID["headers"], "rows": [r[:] for r in GRID["rows"]]}
    grid["rows"][0][1] = "  Aarav "
    spec = dict(XL, view={"columns": ["B"], "rows": [1, 3], "active": "B2"}, steps=[{"do": "select", "target": "B2"}])
    svg, _ = draw(spec, (grid["headers"], grid["rows"]))
    assert re.search(r'<text[^>]*data-cell="B2"[^>]*>␣␣Aarav␣</text>', svg)


def test_bold_header_fits_its_column():
    from render_screens import _sheet_columns, text_width
    spec = dict(XL, view={"columns": ["A", "C"], "rows": [1, 3], "active": "C2"}, steps=[{"do": "select", "target": "A2"}])
    widths = dict(_sheet_columns(spec, G, {}))
    assert widths["C"] >= text_width("Department", 13, bold=True) + 12


def test_bold_labels_fit_their_boxes():
    from render_screens import text_width
    svg, _ = draw(dict(ADS, panel=ADS["panel"] + [{"kind": "button", "label": "Review and publish"}]))
    for w, label in re.findall(r'<rect x="[\d.]+" y="[\d.]+" width="([\d.]+)"[^>]*/><text[^>]*font-weight="700"[^>]*>([^<]+)</text>', svg):
        assert float(w) >= text_width(htmllib.unescape(label), 14, bold=True), label


def test_ribbon_click_draws_a_tab_then_a_button():
    svg, _ = draw(DEDUPE)
    tab = re.search(r'<rect[^>]*rx="12"[^>]*/><text[^>]*>Data</text>', svg)
    button = re.search(r'<rect x="[\d.]+" y="([\d.]+)"[^>]*rx="4"[^>]*/><text[^>]*>Remove Duplicates</text>', svg)
    assert tab and button
    tab_y = float(re.search(r'y="([\d.]+)"', tab.group(0)).group(1))
    assert float(button.group(1)) > tab_y  # the button sits on the ribbon below its tab


def test_range_select_outlines_the_range():
    spec = dict(XL, steps=[{"do": "select", "target": "B2:B5"}])
    svg, _ = draw(spec)
    assert reading_steps(spec, {}) == ["Select cells B2:B5."]
    assert svg.count('stroke-width="2"') >= 1 and "①" in "".join(texts(svg))


# ---- final review fixes ----

def test_long_chip_wraps_inside_the_frame():
    spec = dict(ADS, app="Google Analytics Console", path=["Data display and events"],
                steps=[{"do": "click", "path": ["Data display and events"]}])
    svg, _ = draw(spec)
    for x, w in re.findall(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)"', svg):
        assert float(x) + float(w) <= 400, (x, w)


def test_missing_engine_is_a_problem_not_a_crash(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)
    _, problems = results_for(XL, G)
    assert any("Excel engine unavailable" in p for p in problems)


def test_cli_skips_html_that_is_not_a_lesson(tmp_path):
    (tmp_path / "l1.html").write_text(two_screen_lesson(), encoding="utf-8")
    (tmp_path / "l1.quiz.json").write_text("{}", encoding="utf-8")
    preview = two_screen_lesson() + two_screen_lesson()  # a multi-lesson preview repeats ids
    (tmp_path / "preview.html").write_text(preview, encoding="utf-8")
    assert main(["--dir", str(tmp_path)]) == 0
    assert (tmp_path / "preview.html").read_text(encoding="utf-8") == preview
