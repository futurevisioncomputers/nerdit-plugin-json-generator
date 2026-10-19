from check_prose import banned_patterns, check_lesson

PATS = banned_patterns()


def lesson(body):
    return f'<div class="nerdit-wrapper nerdit-simple">{body}</div>'


def test_banned_phrase_fails_but_not_inside_code():
    fails, _ = check_lesson(lesson("<p>Let's delve into joins.</p>"), PATS)
    assert any("delve" in f for f in fails)
    fails, _ = check_lesson(lesson("<p>Run it.</p><pre><code>-- delve</code></pre>"), PATS)
    assert fails == []


def test_regex_entry_and_whole_words():
    fails, _ = check_lesson(lesson("<p>It is not only fast but also safe.</p>"), PATS)
    assert fails
    fails, _ = check_lesson(lesson("<p>Add one additional column.</p>"), PATS)
    assert fails == []


def test_long_sentence_and_long_paragraph_warn():
    long = "You " + "really " * 15 + "need this."
    _, warns = check_lesson(lesson(f"<p>{long}</p>"), PATS)
    assert any("over 15 words" in w for w in warns)
    _, warns = check_lesson(lesson("<p>One. Two. Three. Four.</p>"), PATS)
    assert any("more than 3 sentences" in w for w in warns)


def test_same_opening_in_every_section_warns():
    secs = "".join(f"<section><h2>{i}</h2><p>A table is thing {i}.</p></section>" for i in range(3))
    _, warns = check_lesson(lesson(secs), PATS)
    assert any("opens with the same words" in w for w in warns)


def test_contractions_emoji_and_indian_scripts_are_fine():
    fails, warns = check_lesson(lesson("<h2>🤔 Why?</h2><p>नमस्ते. You'll see ₹499 here.</p>"), PATS)
    assert fails == [] and warns == []


def test_a_line_break_ends_a_legend_line():
    # Lesson 08 (2026-10-17): legend lines split by <br> were read as one 20-word sentence.
    html = ('<section><h2>1 — Clean</h2><p>Legend:<br>① TRIM removes spaces at the start and end.'
            '<br>② UPPER changes every letter of the code to capitals<br>③ NULLIF turns blanks into NULL</p>'
            '</section>')
    _, warns = check_lesson(html, [])
    assert not any("over 15 words" in w for w in warns)
    assert not any("more than 3 sentences" in w for w in warns)
