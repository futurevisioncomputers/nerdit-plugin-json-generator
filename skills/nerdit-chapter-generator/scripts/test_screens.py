import json

from screens import (cell_value, col_index, drawn_strings, lesson_text, read_grid, read_scenes,
                     read_specs, screen_kind, validate_lesson, validate_scene, validate_spec)

GRID = {"headers": ["ID", "Name", "Department", "City", "Salary"],
        "rows": [[101, "Aarav", "Sales", "Mumbai", 45000],
                 [102, "Diya", "Finance", "Pune", 52000],
                 [103, "Kabir", "Sales", "Delhi", 47000],
                 [104, "Meera", "HR", "Mumbai", 43000],
                 [105, "Rohan", "Finance", "Bengaluru", 55000],
                 [106, "Isha", "Marketing", "Chennai", 49000]]}

TEACH = {"alt": "A screen with the steps marked.", "takeaway": "Two clicks do it.",
         "misconception": "You must sort first.",
         "check": {"question": "What comes first?", "answer": "The tab.", "reasoning": "The button lives there."}}

XL = {"id": "xlookup-city", "app": "Excel", "layout": "sheet", "goal": "Find Isha's city with XLOOKUP",
      "view": {"columns": ["B", "D", "H"], "rows": [1, 7], "active": "H3"},
      "steps": [{"do": "select", "target": "H3"},
                {"do": "type", "target": "H3", "text": '=XLOOKUP("Isha",B2:B7,D2:D7)'},
                {"do": "result", "target": "H3"}],
      "image": "auto"}
XL_TEXT = 'Type =XLOOKUP("Isha",B2:B7,D2:D7) in H3 to find her city.'

DEDUPE = {"id": "dedupe", "app": "Excel", "layout": "sheet", "goal": "Remove repeated rows",
          "view": {"columns": ["A", "B"], "rows": [1, 4], "active": "A1"},
          "steps": [{"do": "click", "path": ["Data", "Remove Duplicates"]}, {"do": "click", "path": ["OK"]}],
          "image": "auto", **TEACH}
DEDUPE_TEXT = "Remove Duplicates deletes repeated rows. Click OK to confirm."

ADS = {"id": "ads-new", "app": "Meta Ads Manager", "layout": "app", "goal": "Start a sales campaign",
       "path": ["Campaigns", "Create"],
       "panel": [{"kind": "field", "label": "Objective", "value": "Sales"},
                 {"kind": "field", "label": "Daily budget", "value": "₹500"},
                 {"kind": "button", "label": "Publish"}],
       "steps": [{"do": "click", "path": ["Campaigns", "Create"]},
                 {"do": "set", "label": "Objective", "value": "Sales"},
                 {"do": "set", "label": "Daily budget", "value": "₹500"}],
       "image": "auto"}
ADS_TEXT = ("Open Campaigns and click Create. Set the Objective to Sales and the Daily budget "
            "to ₹500, then click Publish.")

PIP = {"id": "pip", "app": "Terminal", "layout": "editor", "tool": "terminal", "goal": "Install pandas",
       "lines": ["pip install pandas"], "output": ["Successfully installed pandas"],
       "steps": [{"do": "type", "target": "line 1", "text": "pip install pandas"},
                 {"do": "key", "keys": "Enter"}],
       "image": "auto", **TEACH}
PIP_TEXT = "Type pip install pandas and press Enter. It prints Successfully installed pandas."

SCENE = {"id": "shop-bill", "subject": "A shopkeeper copying one bill into two notebooks",
         "alt": "A shopkeeper writes the same bill twice.", "caption": "One bill, two copies.",
         "takeaway": "A copy can drift.", "misconception": "Copies stay equal.",
         "check": {"question": "What breaks?", "answer": "The copies disagree.", "reasoning": "Edits miss one."}}


def block(spec, cls="nerdit-screen", grid=None):
    attr = f' data-grid="{grid}"' if grid else ""
    return f'<script type="application/json" class="{cls}"{attr}>{json.dumps(spec, ensure_ascii=False)}</script>'


def lesson(text, *blocks, grid=GRID):
    data = f'<script type="application/json" id="xl-staff">{json.dumps(grid)}</script>' if grid else ""
    return (f'<div class="nerdit-wrapper nerdit-simple"><section><h2>1 — Look up</h2><p>{text}</p>'
            f'{data}{"".join(blocks)}</section></div>')


def problems_for(spec, text, grid=GRID):
    g = (grid["headers"], grid["rows"]) if grid else None
    return validate_spec(spec, g if spec.get("layout") == "sheet" else None, text)


# ---- the A/B rule ----

def test_xlookup_with_result_is_A():
    assert screen_kind(XL) == "A"


def test_two_clicks_is_B():
    assert screen_kind(DEDUPE) == "B"


def test_four_steps_is_A():
    spec = dict(DEDUPE, steps=DEDUPE["steps"] + [{"do": "click", "path": ["OK"]}, {"do": "key", "keys": "Ctrl+S"}])
    assert screen_kind(spec) == "A"


def test_two_set_steps_is_A():
    assert len(ADS["steps"]) == 3
    assert screen_kind(ADS) == "A"


def test_dialog_with_two_fields_is_A():
    spec = dict(DEDUPE, dialog={"title": "Remove Duplicates",
                                "fields": [{"label": "Name", "value": "on"}, {"label": "City", "value": "on"}]})
    assert screen_kind(spec) == "A"


def test_terminal_one_command_is_B():
    assert screen_kind(PIP) == "B"


def test_override_needs_why():
    forced = dict(XL, image="B", **TEACH)
    assert any("why" in p for p in problems_for(forced, XL_TEXT))
    forced["why"] = "the learner only needs to see where the formula goes"
    assert not any("why" in p for p in problems_for(forced, XL_TEXT))
    assert screen_kind(forced) == "B"


# ---- layout limits ----

def test_sheet_view_limits():
    wide = dict(XL, view={"columns": ["A", "B", "C", "D", "E"], "rows": [1, 7], "active": "B2"})
    assert any("4 columns" in p for p in problems_for(wide, XL_TEXT))
    tall = dict(XL, view={"columns": ["B", "D"], "rows": [1, 9], "active": "B2"})
    assert any("7 rows" in p for p in problems_for(tall, XL_TEXT))


def test_sheet_long_value_fails():
    grid = {"headers": GRID["headers"], "rows": [r[:] for r in GRID["rows"]]}
    grid["rows"][0][3] = "Bengaluru Rural East Zone"  # 25 characters
    assert any("24" in p for p in problems_for(XL, XL_TEXT, grid))
    grid["rows"][0][3] = "AARAV.SHARMA@GMAIL.COM"  # 22: a cleaning lesson must show it
    assert not any("longer than" in p for p in problems_for(XL, XL_TEXT, grid))


def test_editor_limits():
    many = dict(PIP, lines=["pip install pandas"] * 9)
    assert any("8 lines" in p for p in problems_for(many, PIP_TEXT))
    long_line = "x" * 41
    wide = dict(PIP, lines=[long_line])
    assert any("40" in p for p in problems_for(wide, PIP_TEXT + " " + long_line))


def test_app_limits():
    seven = dict(ADS, panel=ADS["panel"] + [{"kind": "button", "label": "Publish"}] * 4)
    assert any("6 items" in p for p in problems_for(seven, ADS_TEXT))
    label = "Daily budget for the week"  # 25 characters
    wide = dict(ADS, panel=[{"kind": "field", "label": label, "value": "₹500"}], steps=[{"do": "click", "path": ["Create"]}])
    assert any("24" in p for p in problems_for(wide, ADS_TEXT + " " + label))
    message = "word " * 18 + "x"  # 91 characters
    assert len(message) == 91
    chat = dict(ADS, panel=[{"kind": "message", "who": "model", "text": message}], steps=[{"do": "click", "path": ["Create"]}])
    assert any("90" in p for p in problems_for(chat, ADS_TEXT + " " + message))


# ---- the sync rule ----

def test_sync_rule_app():
    assert problems_for(ADS, ADS_TEXT) == []
    magic = dict(ADS, panel=ADS["panel"] + [{"kind": "button", "label": "Magic Button"}])
    assert "ads-new: 'Magic Button' is not in the lesson" in problems_for(magic, ADS_TEXT)


def test_known_excel_labels_pass():
    assert "data" not in DEDUPE_TEXT.casefold()
    assert problems_for(DEDUPE, DEDUPE_TEXT) == []


def test_drawn_screen_does_not_vouch_for_itself():
    text_without_publish = ADS_TEXT.replace(", then click Publish", "")
    figure = ('<div class="nerdit-figure" data-visual="screen" data-screen="ads-new"><svg><text>Publish</text></svg>'
              '<div class="nerdit-figure-caption">Start a sales campaign</div></div>'
              '<ol class="nerdit-visual-read" data-screen="ads-new"><li>Click Publish.</li></ol>')
    html = lesson(text_without_publish, block(ADS), figure, grid=None)
    assert "Publish" not in lesson_text(html)
    assert "ads-new: 'Publish' is not in the lesson" in validate_lesson(html)


def test_entities_match_lesson_text():
    formula = '=IF(E2<45000,"low","ok")'
    spec = dict(XL, steps=[{"do": "type", "target": "H3", "text": formula}, {"do": "result", "target": "H3"}])
    html = lesson('Type <code>=IF(E2&lt;45000,"low","ok")</code> in H3.', block(spec, grid="xl-staff"))
    assert formula in lesson_text(html)
    assert validate_lesson(html) == []


# ---- structure ----

def test_unknown_layout_grid_and_step_kind_fail():
    assert any("layout" in p for p in problems_for(dict(ADS, layout="canvas"), ADS_TEXT))
    html = lesson(XL_TEXT, block(XL, grid="xl-missing"))
    assert any("grid" in p for p in validate_lesson(html))
    assert any("wave" in p for p in problems_for(dict(ADS, steps=[{"do": "wave"}]), ADS_TEXT))


def test_result_needs_earlier_type_and_sheet():
    early = dict(XL, steps=[{"do": "result", "target": "H3"}, XL["steps"][1]])
    assert any("result" in p for p in problems_for(early, XL_TEXT))
    in_app = dict(ADS, steps=[{"do": "result", "target": "Objective"}])
    assert any("sheet" in p for p in problems_for(in_app, ADS_TEXT))


def test_set_label_must_be_a_field():
    spec = dict(ADS, steps=[{"do": "set", "label": "Publish", "value": "Sales"}])
    assert any("'Publish' is not a field" in p for p in problems_for(spec, ADS_TEXT))


def test_at_most_five_steps():
    # svgcheck counts markers ①–⑤ only; a longer path is two screens.
    six = dict(DEDUPE, steps=[{"do": "click", "path": ["OK"]}] * 6)
    assert any("5 steps" in p for p in problems_for(six, DEDUPE_TEXT))
    assert not any("steps" in p for p in problems_for(dict(six, steps=six["steps"][:5]), DEDUPE_TEXT))


def test_editor_target_is_a_line():
    spec = dict(PIP, steps=[{"do": "type", "target": "line 3", "text": "pip install pandas"}])
    assert any("line 3" in p for p in problems_for(spec, PIP_TEXT))


def test_b_needs_teaching_text():
    spec = {k: v for k, v in DEDUPE.items() if k != "check"}
    assert any("check" in p for p in problems_for(spec, DEDUPE_TEXT))


def test_scene_needs_all_keys():
    assert validate_scene(SCENE) == []
    assert any("misconception" in p for p in validate_scene({k: v for k, v in SCENE.items() if k != "misconception"}))
    assert any("150" in p for p in validate_scene(dict(SCENE, alt="a" * 151)))


def test_duplicate_ids_across_screens_and_scenes_fail():
    html = lesson(DEDUPE_TEXT, block(DEDUPE, grid="xl-staff"), block(dict(SCENE, id="dedupe"), cls="nerdit-scene"))
    assert len(read_specs(html)) == 1 and len(read_scenes(html)) == 1
    assert any("duplicate" in p for p in validate_lesson(html))


def test_bad_json_is_a_problem_not_a_crash():
    html = lesson("Text.", '<script type="application/json" class="nerdit-screen">{bad</script>')
    assert any("JSON" in p for p in validate_lesson(html))


def test_read_specs_keeps_grid_and_offset():
    html = lesson(XL_TEXT, block(XL, grid="xl-staff"))
    (spec,) = read_specs(html)
    assert spec["_grid"] == "xl-staff" and spec["id"] == "xlookup-city"
    assert html[: spec["_offset"]].endswith("</script>")
    assert read_grid(html, "xl-staff") == (GRID["headers"], GRID["rows"])
    assert read_grid(html, "nope") is None


def test_drawn_strings_cover_every_drawn_word():
    words = drawn_strings(ADS)
    assert {"Campaigns", "Create", "Objective", "Sales", "Daily budget", "₹500", "Publish"} <= set(words)
    assert "Meta Ads Manager" not in words and "Start a sales campaign" not in words


def test_cell_value():
    grid = (GRID["headers"], GRID["rows"])
    assert col_index("A") == 0 and col_index("AA") == 26
    assert cell_value(grid, "B7") == "Isha"
    assert cell_value(grid, "A1") == "ID"
    assert cell_value(grid, "H3") is None


def test_app_theme_matches_names():
    from screens import app_theme
    assert app_theme("Excel") == app_theme("Microsoft Excel") == "excel"
    assert app_theme("VS Code") == app_theme("Visual Studio Code") == "vscode"
    assert app_theme("Meta Ads Manager") == "meta-ads"
    assert app_theme("Google Ads") == "google-ads"
    assert app_theme("Google Sheets") == "sheets"
    assert app_theme("New App") is None


def test_select_may_name_a_range_in_the_view():
    spec = dict(XL, steps=[{"do": "select", "target": "B2:B5"}, XL["steps"][1], XL["steps"][2]])
    assert not any("target" in p for p in problems_for(spec, XL_TEXT))
    outside = dict(spec, steps=[{"do": "select", "target": "B2:B9"}] + spec["steps"][1:])
    assert any("outside the view" in p for p in problems_for(outside, XL_TEXT))


def test_values_may_be_longer_than_labels():
    source = "Surat,Mumbai,Delhi,Bengaluru,Pune"  # 33 characters
    spec = dict(DEDUPE, dialog={"title": "Data Validation", "fields": [{"label": "Source", "value": source}]})
    text = DEDUPE_TEXT + " Data Validation Source " + source
    assert not any("longer than" in p for p in problems_for(spec, text))
    too_long = dict(spec, dialog={"title": "Data Validation", "fields": [{"label": "Source", "value": source + "abc"}]})
    assert any("34" in p for p in problems_for(too_long, text + "abc"))


# ---- final review fixes ----

def test_sync_rule_matches_whole_words_only():
    for drawn, text in (("₹50", "Set the budget to ₹500."), ("5", "Sales in 2025."), ("Day", "Every Monday.")):
        spec = dict(ADS, path=[], panel=[{"kind": "button", "label": drawn}], steps=[{"do": "click", "path": [drawn]}])
        assert f"ads-new: '{drawn}' is not in the lesson" in problems_for(spec, text), drawn


def test_illustrator_blocks_do_not_vouch_for_a_b_screen():
    inserted = ('<p class="nerdit-visual-intro" data-nerdit-img="l1-img1">Here is the screen.</p>'
                '<ol class="nerdit-visual-read" data-nerdit-img="l1-img1"><li>Click Data, then Remove Duplicates.</li></ol>')
    html = lesson("Click OK to confirm.", block(DEDUPE, grid="xl-staff"), inserted)
    assert "dedupe: 'Remove Duplicates' is not in the lesson" in validate_lesson(html)


def test_reversed_range_fails():
    spec = dict(XL, steps=[{"do": "select", "target": "B7:B2"}])
    assert any("top-left" in p for p in problems_for(spec, XL_TEXT))


def test_app_name_has_a_limit():
    assert any("app" in p and "24" in p for p in problems_for(dict(ADS, app="A" * 25), ADS_TEXT))


def test_numbers_where_text_belongs_are_problems_not_crashes():
    for bad in (dict(ADS, path=[2024]), dict(PIP, steps=[{"do": "key", "keys": 5}]),
                dict(ADS, panel=[{"kind": "button", "label": 7}], steps=[{"do": "click", "path": ["Create"]}])):
        assert any("text" in p for p in problems_for(bad, ADS_TEXT + " " + PIP_TEXT + " 2024 5 7"))


# ---- deferred review fixes ----

def test_ids_must_be_slugs():
    assert any("slug" in p for p in problems_for(dict(ADS, id="q&a"), ADS_TEXT))
    assert any("slug" in p for p in validate_scene(dict(SCENE, id="Shop Bill")))


def test_single_quoted_attributes_are_read():
    html = lesson(XL_TEXT, block(XL, grid="xl-staff").replace('"application/json" class="nerdit-screen" data-grid="xl-staff"',
                                                              "'application/json' class='nerdit-screen' data-grid='xl-staff'"))
    (spec,) = read_specs(html)
    assert spec["_grid"] == "xl-staff"


def test_known_labels_follow_the_app_theme():
    spec = dict(DEDUPE, app="Microsoft Excel")
    assert problems_for(spec, DEDUPE_TEXT) == []
