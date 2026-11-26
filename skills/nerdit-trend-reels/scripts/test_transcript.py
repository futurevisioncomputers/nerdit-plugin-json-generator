from transcript import match_errors, merge_tokens

# The spike's real takes (2026-11-24): Dev added "in cream" to clip 1 and reordered clip 2.
LINE1 = ("PwC is training eighty-five thousand of its own people for the AI age. Not a small tech team. "
         "Eighty-five thousand. That's a clear signal of what your company will expect from you next.")
HEARD1 = ("PwC is training 85,000 of its own people for the AI age. Not a small tech team. 85,000 in cream. "
          "That's a clear signal of what your company will expect from you next.").split()
LINE2 = ("So don't wait to be asked. Learn how AI actually works, in plain English. "
         "Start Machine Learning Fundamentals free on nerdit dot in. Link in bio.")
HEARD2 = ("So, don't wait to be asked, learn how AI actually works in plain English on nerdit.in. "
          "Start Machine Learning Fundamentals on Bio. Link in bio.").split()


def test_spike_clip1_fails_on_extra_words():
    errors = match_errors(HEARD1, LINE1)
    assert any(e.startswith("extra:") and "cream" in e for e in errors)


def test_spike_clip2_fails_on_missing_free():
    assert any(e.startswith("missing:") and "free" in e for e in match_errors(HEARD2, LINE2))


def test_exact_take_passes():
    assert HEARD1[18:20] == ["in", "cream."]
    assert match_errors(HEARD1[:18] + HEARD1[20:], LINE1) == []


def test_no_speech():
    assert match_errors([], LINE1) == ["no speech heard"]


def test_merge_tokens_joins_and_fixes():
    words = merge_tokens([(" PWC", 0, .3), (" 85", .4, .6), (",000", .6, .8), (" nerdid", 1.0, 1.2), (".in", 1.2, 1.4)])
    assert [w["w"] for w in words] == ["PwC", "85,000", "nerdit.in"]
    assert words[1] == {"w": "85,000", "s": .4, "e": .8}


def test_whisper_number_forms_match_spoken_words():
    assert match_errors("Pay rose 72% this year.".split(), "Pay rose seventy-two percent this year.") == []
    assert match_errors("PwC trains 85K people.".split(), "PwC trains eighty-five thousand people.") == []
    assert match_errors("PwC trains 85 thousand people.".split(), "PwC trains eighty-five thousand people.") == []
    assert match_errors("A $1 billion bet.".split(), "A one billion dollars bet.") == []
    assert match_errors("About 1.5 million jobs.".split(), "About one point five million jobs.") == []


def test_whisper_split_percent_sign_matches_spoken_percent():
    # Pilot 2026-11-26: Whisper wrote "42 %" as two words for "forty-two percent".
    assert match_errors("Only 42 % say it.".split(), "Only forty-two percent say it.") == []
