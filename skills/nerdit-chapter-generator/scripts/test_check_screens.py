import re
from check_screens import check_lesson
from render_screens import figure_block, render_lesson
from test_screens import ADS, ADS_TEXT, DEDUPE, DEDUPE_TEXT, XL, XL_TEXT, block, lesson


def rendered(*blocks, text=XL_TEXT + " " + ADS_TEXT):
    html, problems = render_lesson(lesson(text, *blocks))
    assert problems == []
    return html


def two():
    return rendered(block(XL, grid="xl-staff"), block(ADS))


def test_clean_rendered_lesson_passes():
    assert check_lesson(two()) == ([], [])


def test_missing_figure_fails():
    fails, _ = check_lesson(lesson(XL_TEXT, block(XL, grid="xl-staff")))
    assert "xlookup-city: no drawn screen; run render_screens.py" in fails


def test_stale_figure_fails():
    html = two().replace('"Isha", "Marketing", "Chennai"', '"Isha", "Marketing", "Kochi"')
    fails, _ = check_lesson(html)
    assert "xlookup-city: drawn screen is out of date; run render_screens.py" in fails


def test_removed_word_fails():
    html = two().replace("and the Daily budget to", "and the spend to")
    fails, _ = check_lesson(html)
    assert "ads-new: 'Daily budget' is not in the lesson" in fails


def test_formula_error_fails():
    spec = dict(XL, steps=[{"do": "type", "target": "H3", "text": "=FOO(1)"}, {"do": "result", "target": "H3"}])
    fails, _ = check_lesson(lesson("Type =FOO(1) in H3.", block(spec, grid="xl-staff")))
    assert any("H3: =FOO(1) gives #NAME?" in f for f in fails)


def test_override_warns():
    html = rendered(block(dict(XL, image="A", why="the result needs the grid"), grid="xl-staff"))
    fails, warns = check_lesson(html)
    assert fails == [] and "xlookup-city: image forced to A: the result needs the grid" in warns


def test_unthemed_app_warns():
    html = rendered(block(dict(ADS, app="New App")))
    fails, warns = check_lesson(html)
    assert fails == []
    assert any("no colour theme for 'New App'" in w for w in warns)


def test_b_spec_with_a_drawing_fails():
    stale = figure_block(DEDUPE, "<svg></svg>", ["Click OK."])
    fails, _ = check_lesson(lesson(DEDUPE_TEXT, block(DEDUPE, grid="xl-staff") + stale))
    assert any(f.startswith("dedupe:") and "B screen" in f for f in fails)


def test_drawing_without_a_spec_fails():
    orphan = figure_block(dict(XL, id="gone"), "<svg></svg>", ["Click cell H3."])
    fails, _ = check_lesson(lesson(XL_TEXT, orphan))
    assert any(f.startswith("gone:") and "no spec" in f for f in fails)


CLICKS = "<ol><li>Click the Data tab.</li><li>Click Remove Duplicates.</li></ol>"


def test_click_path_without_screen_warns():
    _, warns = check_lesson(lesson("Remove repeated rows." + CLICKS, grid=None))
    assert "section 1: click-path with no screen (figures.md template 16)" in warns


def test_click_path_with_a_screen_is_quiet():
    html = rendered(block(DEDUPE, grid="xl-staff"), text=DEDUPE_TEXT + CLICKS)
    assert check_lesson(html) == ([], [])


def test_reading_list_and_answers_are_not_click_paths():
    read = CLICKS.replace("<ol>", '<ol class="nerdit-visual-read">')
    answer = f"<details><summary>Show answer</summary>{CLICKS}</details>"
    assert check_lesson(lesson("Steps." + read + answer, grid=None)) == ([], [])


def test_lesson_without_specs_is_untouched():
    assert check_lesson(lesson("No screens here.", grid=None)) == ([], [])


# ---- final review fixes ----

def test_a_screen_drawn_twice_fails():
    html = two()
    block_html = re.search(r'<div class="nerdit-figure" data-visual="screen" data-screen="ads-new".*?</ol>', html, re.S).group(0)
    fails, _ = check_lesson(html + block_html)
    assert any(f.startswith("ads-new:") and "twice" in f for f in fails)


def test_cli_checks_every_lesson_in_a_course(tmp_path):
    import json as _json
    from check_screens import main as check_main
    stale = two().replace('"Isha", "Marketing", "Chennai"', '"Isha", "Marketing", "Kochi"')
    course = {"lessons": [{"id": "ok", "content": two()}, {"id": "bad", "content": stale}]}
    path = tmp_path / "course.json"
    path.write_text(_json.dumps(course), encoding="utf-8")
    assert check_main(["--course", str(path)]) == 1
    course["lessons"] = course["lessons"][:1]
    path.write_text(_json.dumps(course), encoding="utf-8")
    assert check_main(["--course", str(path)]) == 0
