"""A video complements the page, it does not mirror it (owner, 2026-11-05, supplementary video strategy):
each clip says what it adds, scenes say what they teach, the page's tables, code walks and
sentences are not repeated, and a topic the page already makes clear gets no clip."""
import json

import storyplan
import stage
import timeline
from test_story_video import LESSON_HTML, NARR, lesson_check, lesson_part, make_course, merge_setup


def complement_part(**kw):
    return lesson_part(**kw)   # its scenes carry a purpose and each topic a clips entry


def test_a_complementing_part_passes(tmp_path):
    assert lesson_check(tmp_path, complement_part()) == []


def test_each_clip_says_what_it_adds_and_how(tmp_path):
    part = complement_part()
    part["clips"] = part["clips"][:1]
    errors = lesson_check(tmp_path, part)
    assert any("section 2" in e and "clips" in e for e in errors), errors
    part = complement_part()
    part["clips"][0].update(adds="", format="slideshow")
    errors = lesson_check(tmp_path, part)
    assert any("adds" in e for e in errors) and any("format" in e for e in errors), errors


def test_each_scene_names_its_teaching_purpose(tmp_path):
    part = complement_part()
    part["scenes"][0]["purpose"] = ""
    assert any("purpose" in e for e in lesson_check(tmp_path, part))


def test_a_short_clip_is_fine_when_the_idea_is_simple(tmp_path):
    part = complement_part()
    t2 = [s for s in part["scenes"] if s["topic"] == 2]
    part["scenes"] = [s for s in part["scenes"] if s["topic"] == 1] + t2[:2]
    short = ("पहले Enquiry आती है, फिर Demo होता है. Rate का मतलब है एक fixed time window में कितने events होते हैं, जैसे एक week में admissions. "
             "Week बदलते ही count बदलता है, इसलिए हम हर week का data अलग रखते हैं. "
             "Model हर week का pattern पढ़ता है और सही trend दिखाता है.")
    for s in t2[:2]:
        s["narration"] = short
    assert lesson_check(tmp_path, part) == []


def test_narration_that_reads_the_page_aloud_fails(tmp_path):
    html = LESSON_HTML.replace("A rate is a count per week; 4 rows.",
                               "A rate tells you how many admissions arrive in one fixed week at a branch; 4 rows.")
    part = complement_part(html=html)
    part["scenes"][3]["narration"] = ("यहाँ देखें: a rate tells you how many admissions arrive in one fixed week "
                                      "at a branch, यही इसका मतलब है.")
    errors = lesson_check(tmp_path, part, html=html)
    assert any("reads the page" in e for e in errors), errors


CODE_HTML = ('<h1>Routes</h1><section><h2>1 — Routes</h2><p>A route maps a URL to a view; 2 routes. An Enquiry leads to a Demo; 12 learners.</p>'
             '<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span>'
             '<pre><code>a = 1\nb = 2\nc = 3\nprint(a + b + c)</code></pre></div>'
             '<div class="nerdit-out"><span class="nerdit-tag">Python shows</span><pre><code>6</code></pre></div></div>'
             '<ol class="nerdit-codewalk"><li><code>a = 1</code> one.</li><li><code>b = 2</code> two.</li>'
             '<li><code>c = 3</code> three.</li></ol>'
             '<div class="nerdit-tryit">Try It</div></section>')


def test_a_code_scene_points_at_the_idea_not_every_line(tmp_path):
    part = complement_part(topics=(1,), html=CODE_HTML)
    part["clips"] = part["clips"][:1]
    part["scenes"].append({"kind": "code", "lessonId": "c-01", "topic": 1, "title": "1 — part", "code": 1,
                           "highlight": ["line:1", "line:2", "line:3"],
                           "narration": "ये program तीन values जोड़कर एक total data value print करता है.",
                           "keyIdea": "Three values add to one total.", "terms": ["data"], "focus": [],
                           "myth": None, "purpose": "Shows what the program is for"})
    errors = lesson_check(tmp_path, part, html=CODE_HTML)
    assert any("highlight" in e and "2" in e for e in errors), errors
    part["scenes"][-1]["highlight"] = ["line:4"]
    assert lesson_check(tmp_path, part, html=CODE_HTML) == []
    twice = dict(part["scenes"][-1])
    part["scenes"].append(twice)
    assert any("one code scene" in e for e in lesson_check(tmp_path, part, html=CODE_HTML))


def test_a_topic_needs_no_table_or_code_scene(tmp_path):
    part = complement_part(topics=(1,), html=CODE_HTML)
    part["clips"] = part["clips"][:1]
    assert not any("table or code" in e for e in lesson_check(tmp_path, part, html=CODE_HTML))


def test_scaffold_starts_a_complementing_plan_without_copied_tables_or_code(tmp_path):
    course = tmp_path / "course.json"
    course.write_text(json.dumps({"title": "C", "lessons": [{"id": "c-01", "title": "Routes", "content": CODE_HTML}]}),
                      encoding="utf-8")
    plan = json.loads(storyplan.scaffold(tmp_path / "images", course).read_text(encoding="utf-8"))
    assert plan["complement"] is True
    assert [s["kind"] for s in plan["scenes"]] == ["vector"]
    assert plan["scenes"][0]["purpose"] == ""
    assert plan["clips"] == [{"lessonId": "c-01", "topic": 1, "objective": "", "pageHas": "", "adds": "",
                              "format": ""}]
    assert plan["practise"][0]["question"] == ""


def test_merge_carries_each_lessons_clips(tmp_path):
    images, course, work = merge_setup(tmp_path)
    for lid in ("c-01", "c-02"):
        part = complement_part(lid=lid)
        (work / f"{lid}.video.json").write_text(json.dumps(part, ensure_ascii=False), encoding="utf-8")
    plan = json.loads(storyplan.merge(images, course, work).read_text(encoding="utf-8"))
    assert plan["complement"] is True
    assert {(c["lessonId"], c["topic"]) for c in plan["clips"]} == {("c-01", 1), ("c-01", 2), ("c-02", 1), ("c-02", 2)}


def test_old_plans_keep_the_mirror_rules(tmp_path):
    # The Flask video was planned before this rule: without "complement" nothing new is asked of it.
    plan = {"scenes": [], "clips": []}
    assert storyplan.complement_errors(plan, {}, {}) == []


# Owner, 2026-11-05 (video improvement framework): keep the two-panel style, improve the teaching in it.

def test_each_clip_says_what_the_page_already_covers(tmp_path):
    part = complement_part()
    part["clips"][0]["pageHas"] = ""
    assert any("pageHas" in e for e in lesson_check(tmp_path, part))


def test_a_clip_longer_than_about_150_seconds_fails(tmp_path):
    part = complement_part()
    for s in part["scenes"]:
        if s["topic"] == 1:
            s["narration"] = NARR
    part["scenes"] += [dict(s, vector=s["vector"].replace(".svg", "b.svg")) for s in part["scenes"] if s["topic"] == 1]
    errors = lesson_check(tmp_path, part)
    assert any("section 1" in e and "words" in e and "150" in e for e in errors), errors


def test_the_key_idea_is_one_sentence(tmp_path):
    part = complement_part()
    part["scenes"][0]["keyIdea"] = "Counts come from data. Rates divide by time."
    assert any("keyIdea" in e and "one sentence" in e for e in lesson_check(tmp_path, part))


def test_a_clip_opens_with_a_question_not_in_this_video(tmp_path):
    part = complement_part()
    part["scenes"][0]["narration"] = "इस video में हम " + NARR
    assert any("opens with" in e for e in lesson_check(tmp_path, part))


def test_two_clips_with_the_same_objective_fail(tmp_path):
    part = complement_part()
    part["clips"][1]["objective"] = part["clips"][0]["objective"].upper()
    assert any("same objective" in e for e in lesson_check(tmp_path, part))


def test_now_practise_asks_a_question_that_checks_understanding(tmp_path):
    part = complement_part()
    part["practise"][0]["question"] = "Copy the code"
    assert any("question" in e and "?" in e for e in lesson_check(tmp_path, part))
    part["practise"][0]["question"] = ""
    assert any("question" in e for e in lesson_check(tmp_path, part))


def test_the_practise_card_shows_the_question_longer():
    cards = storyplan.practise_cards({"practise": [{"lessonId": "l1", "topic": 1, "tryIt": "x", "task": None,
                                                    "question": "Which part sends the response?"}]}, {})
    assert cards[("l1", 1)]["question"] == "Which part sends the response?"
    plan = {"intro": {"title": "T", "points": ["a"]}, "recap": {"points": ["b"]},
            "scenes": [{"kind": "vector", "lessonId": "l1", "topic": 1, "title": "One", "keyIdea": "k"}]}
    clips = {k: {"dur": 2.0, "words": []} for k in ("intro", "s1", "recap")}
    tl = timeline.build(plan, clips, cards)
    card = next(s for s in tl["segments"] if s["kind"] == "practise")
    assert card["end"] - card["start"] == timeline.CARD_QUESTION > timeline.CARD
    assert "Which part sends the response?" in stage.build_stage(plan, tl, ["<svg></svg>"], "")


def test_review_flags_travel_with_the_plan_and_never_change_the_video(tmp_path, capsys):
    images, course, work = merge_setup(tmp_path)
    part = complement_part(lid="c-01")
    part["reviewFlags"] = [{"topic": 1, "issue": "The page says 12 learners but its table has 11 rows"}]
    (work / "c-01.video.json").write_text(json.dumps(part, ensure_ascii=False), encoding="utf-8")
    plan = json.loads(storyplan.merge(images, course, work).read_text(encoding="utf-8"))
    assert plan["reviewFlags"] == [{"lessonId": "c-01", "topic": 1,
                                    "issue": "The page says 12 learners but its table has 11 rows"}]
    storyplan.main(["check", "--images-dir", str(images)])
    assert "REVIEW c-01 section 1: The page says 12 learners" in capsys.readouterr().out


# Owner, 2026-11-05 (improvement plan, written lesson + old video + pilot).

def test_the_practise_question_does_not_repeat_the_try_it(tmp_path):
    part = complement_part()
    part["practise"][0].update(tryIt='predict what show_file("a/b.txt") prints',
                               question="Which converter lets one variable hold a/b.txt?")
    assert any("repeats" in e and "Try It" in e for e in lesson_check(tmp_path, part))
    part["practise"][0]["question"] = "Which converter catches /files/reports/may.pdf in one variable?"
    assert not any("repeats" in e for e in lesson_check(tmp_path, part))


def revised_plan(tmp_path):
    images, course = tmp_path / "images", make_course(tmp_path, n=1)
    old = tmp_path / "old_plan.json"
    old.write_text(json.dumps({"scenes": [
        {"lessonId": "l1", "topic": 1, "kind": "vector", "keyIdea": "An enquiry is data."},
        {"lessonId": "l1", "topic": 1, "kind": "code", "keyIdea": "The view returns the count."}]}),
        encoding="utf-8")
    plan = json.loads(storyplan.scaffold(images, course, previous=old).read_text(encoding="utf-8"))
    return plan, images, course, old


def test_revising_a_video_scaffolds_what_the_old_clip_taught(tmp_path):
    plan, _, _, old = revised_plan(tmp_path)
    assert plan["previous"] == str(old.resolve())
    clip = plan["clips"][0]
    assert clip["oldKeyIdeas"] == ["An enquiry is data.", "The view returns the count."]
    assert clip["oldVideo"] == "" and clip["decision"] == ""


def test_revising_needs_the_old_clip_analysis_and_a_decision(tmp_path):
    plan, _, _, _ = revised_plan(tmp_path)
    errors = storyplan.complement_errors(plan, {}, {})
    assert any("oldVideo" in e for e in errors) and any("decision" in e for e in errors), errors
    plan["clips"][0].update(oldVideo="Showed the code line by line; never why the count changes",
                            decision="revise")
    errors = storyplan.complement_errors(plan, {}, {})
    assert not any("oldVideo" in e or "decision" in e for e in errors), errors
    plan["clips"][0]["decision"] = "maybe"
    assert any("decision" in e for e in storyplan.complement_errors(plan, {}, {}))


def test_a_new_course_needs_no_old_clip_analysis(tmp_path):
    part = complement_part()
    assert not any("oldVideo" in e for e in lesson_check(tmp_path, part))
