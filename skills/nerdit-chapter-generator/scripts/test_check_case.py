import json

import check_case as cc

WORLD = {"business": {"name": "Future Vision Computer Institute", "owner": {"name": "Siddharth Parakh"},
                      "branches": ["Citylight", "Vesu", "Pal"]},
         "cast": [{"name": "Neha", "role": "admissions counsellor"}]}
NAMES = cc.world_names(WORLD)

INTRO = ('<div class="nerdit-info-box nerdit-case-intro"><p><strong>Meet the case study.</strong> '
         'Future Vision Computer Institute has three branches. Neha logs every enquiry.</p></div>')


def section(n, concept, case):
    return (f'<section><h2>{n} — Routes</h2>{concept}'
            f'<h3 class="nerdit-casehead">🌟 Case Study: Read One Enquiry</h3>{case}</section>')


GOOD = section(1, '<p>A <strong>route</strong> connects a URL to a function.</p>'
                  '<div class="nerdit-run"><div class="nerdit-in"><pre><code>@app.get("/hello")</code></pre></div></div>',
               '<p>Neha opens enquiry E2 at Citylight.</p>')
CHEAT = '<section><h2>📌 Quick Cheat Sheet</h2><table class="nerdit-cheatsheet"><tr><td>Neha</td></tr></table></section>'


def page(*parts):
    return '<div class="nerdit-wrapper nerdit-simple"><h1>Routes</h1>' + "".join(parts) + "</div>"


def test_world_names_cover_the_business_its_people_and_branches():
    assert {"Future Vision Computer Institute", "Future Vision", "Siddharth Parakh", "Neha",
            "Citylight", "Vesu", "Pal"} <= set(NAMES)


def test_a_section_that_explains_first_and_then_gives_its_case_study_passes():
    assert cc.case_problems(page(GOOD, CHEAT), NAMES, first=False) == []
    assert cc.case_problems(page(INTRO, GOOD, CHEAT), NAMES, first=True) == []


def test_a_world_name_in_the_explanation_fails():
    bad = section(1, '<p>Neha uses a <strong>route</strong> to read enquiries.</p>', "<p>E2.</p>")
    assert cc.case_problems(page(bad), NAMES, first=False) == [
        'section 1 names "Neha" before its case study; explain the idea in general terms, then put the '
        'course world after <h3 class="nerdit-casehead">']


def test_world_data_in_code_before_the_case_study_fails():
    bad = section(1, '<p>A <strong>route</strong>.</p><pre><code>branch = "Pal"</code></pre>', "<p>E2.</p>")
    assert 'section 1 names "Pal"' in cc.case_problems(page(bad), NAMES, first=False)[0]


def test_a_name_inside_a_word_is_not_a_world_name():
    ok = section(1, '<p>A <strong>route</strong> is palpable; Palette and pal-ette too? No: pale.</p>', "<p>E2.</p>")
    assert cc.case_problems(page(ok), NAMES, first=False) == []


def test_every_concept_section_needs_exactly_one_case_study_heading():
    none = '<section><h2>1 — Routes</h2><p>A <strong>route</strong>.</p></section>'
    two = section(2, "<p>x</p>", '<h3 class="nerdit-casehead">🌟 Case Study: Again</h3>')
    assert cc.case_problems(page(none, two), NAMES, first=False) == [
        'section 1 has no case study; after the explanation add <h3 class="nerdit-casehead">🌟 Case Study: …</h3> '
        "and put the course world's data and example after it",
        "section 2 has 2 case study headings; use one"]


def test_the_first_lesson_meets_the_case_study_before_its_first_section():
    assert cc.case_problems(page(GOOD), NAMES, first=True) == [
        'the first lesson needs a "Meet the case study" card (<div class="nerdit-info-box nerdit-case-intro">) '
        "before section 1: who Future Vision Computer Institute is, the people in its story, and the data the course uses"]
    thin = '<div class="nerdit-info-box nerdit-case-intro"><p>Meet the data.</p></div>'
    assert "who Future Vision Computer Institute is" in cc.case_problems(page(thin, GOOD), NAMES, first=True)[0]


def test_a_course_without_a_world_is_not_checked():
    assert cc.case_problems(page('<section><h2>1 — X</h2><p>Neha.</p></section>'), [], first=True) == []


def test_cli_checks_every_lesson_and_only_the_first_needs_the_card(tmp_path):
    course = {"lessons": [{"id": "a-01", "content": page(INTRO, GOOD)}, {"id": "b-02", "content": page(GOOD)},
                          {"id": "c-03", "content": page(section(1, "<p>Vesu.</p>", ""))}]}
    (tmp_path / "c.json").write_text(json.dumps(course), encoding="utf-8")
    (tmp_path / "w.json").write_text(json.dumps({"use": "fvc-institute"}), encoding="utf-8")
    assert cc.main(["--course", str(tmp_path / "c.json"), "--world", str(tmp_path / "w.json")]) == 1
    course["lessons"].pop()
    (tmp_path / "c.json").write_text(json.dumps(course), encoding="utf-8")
    assert cc.main(["--course", str(tmp_path / "c.json"), "--world", str(tmp_path / "w.json")]) == 0
