import copy

from script_check import script_errors

LINE = ("PwC is training eighty-five thousand of its people for the AI age. "
        "That tells you what your company will expect next. Learn how AI works. Link in bio.")
KEPT = [{"headline": "PwC Is Training 85,000 Employees on AI Skills", "evidence": ["certify 85,000 workers"],
         "links": ["https://inc.com/a", "https://businessinsider.com/b"], "outlets": ["Inc.", "Business Insider"]}]


def script(line=LINE, facts=("PwC is training 85,000 staff for the AI age",), kind="daily",
           sources=("Business Insider", "Inc.")):
    return {"kind": kind, "line": line,
            "card": {"chip": "AI & JOBS  ·  25 NOV 2026", "facts": list(facts), "sources": list(sources)},
            "course": {"id": "Ncyq98jK81IVOgRygqP8", "title": "Machine Learning Fundamentals", "lessons": 12,
                       "url": "https://nerdit.in/course/machine-learning-fundamentals-1792397644108/preview"}}


def test_good_script_passes():
    assert script_errors(script(), KEPT) == []


def test_card_number_not_in_sources_is_named():
    errors = script_errors(script(facts=["PwC trains 90,000 people for AI"]), KEPT)
    assert any("90,000" in e for e in errors)


def test_85k_in_evidence_matches_85000_on_card():
    kept = copy.deepcopy(KEPT)
    kept[0]["headline"], kept[0]["evidence"] = "PwC to train staff on AI", ["about 85K workers"]
    assert script_errors(script(), kept) == []


def test_digits_in_line_fail():
    errors = script_errors(script(line=LINE.replace("eighty-five thousand", "85,000")), KEPT)
    assert any("digits" in e for e in errors)


def test_web_address_in_line_fails():
    errors = script_errors(script(line=LINE.replace("Learn how AI works.", "Visit nerdit dot in.")), KEPT)
    assert any("web address" in e for e in errors)


def test_course_title_spoken_fails():
    errors = script_errors(script(line=LINE.replace("Learn how AI works.", "Try Machine Learning Fundamentals.")), KEPT)
    assert any("course title" in e for e in errors)


def test_missing_cta_fails():
    errors = script_errors(script(line=LINE.replace(" Link in bio.", "")), KEPT)
    assert any("link in bio" in e for e in errors)


def test_thirteen_word_sentence_fails():
    errors = script_errors(script(line=LINE.replace("of its people", "of its own people")), KEPT)
    assert any("12 words" in e for e in errors)


def test_more_than_30_words_fails():
    # Pilot 2026-11-26: a 33-word line ran past the 14 s clip and Dev's "link in bio" was cut.
    long = "AI is here. " * 10 + "Link in bio."
    assert any("at most 30" in e for e in script_errors(script(line=long), KEPT))


def test_verbatim_headline_on_card_fails():
    errors = script_errors(script(facts=["PwC is training 85,000 employees on AI skills!"]), KEPT)
    assert any("word for word" in e for e in errors)


def test_non_latin_card_fails():
    errors = script_errors(script(facts=["ஊதியம் உயர்வு"]), KEPT)
    assert any("English letters" in e for e in errors)


def test_weekly_needs_three_facts():
    assert any("3 facts" in e for e in script_errors(script(kind="weekly"), KEPT))


def test_needs_two_sources():
    assert any("2 sources" in e for e in script_errors(script(sources=["Inc."]), KEPT))


def test_banned_phrase():
    errors = script_errors(script(line=LINE.replace("Learn how AI works.", "Get a free certificate.")), KEPT)
    assert any("free certificate" in e for e in errors)


def test_spoken_number_not_in_sources_fails():
    errors = script_errors(script(line=LINE.replace("eighty-five thousand", "ninety thousand")), KEPT)
    assert any("90000" in e and "spoken" in e for e in errors)


def test_small_spoken_counts_are_not_claims():
    line = "This week in AI and jobs. One, PwC trains people. Two, more. Three, done. Link in bio."
    assert not [e for e in script_errors(script(line=line), KEPT) if "spoken" in e]


def test_spoken_decimal_fails():
    # Pilot 2026-11-25: Dev said "ten points million" and skipped the line in two takes (108 credits).
    kept = copy.deepcopy(KEPT)
    kept[0]["evidence"].append("creates 10.6 million jobs")
    line = LINE.replace("eighty-five thousand of its people", "ten point six million people")
    errors = script_errors(script(line=line), kept)
    assert any("decimal" in e for e in errors)


def test_point_as_plain_word_passes():
    line = LINE.replace("Learn how AI works.", "That is the point. Learn how AI works.")
    assert not [e for e in script_errors(script(line=line), KEPT) if "decimal" in e]
