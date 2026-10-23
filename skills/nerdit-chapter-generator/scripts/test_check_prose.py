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


def test_long_sentence_fails_and_long_paragraph_warns():
    long = "You " + "really " * 20 + "need this."
    fails, _ = check_lesson(lesson(f"<p>{long}</p>"), PATS)
    assert any("over 20 words" in f for f in fails)
    ok = "You " + "really " * 15 + "need this."
    assert check_lesson(lesson(f"<p>{ok}</p>"), PATS)[0] == []
    _, warns = check_lesson(lesson("<p>One. Two. Three. Four. Five.</p>"), PATS)
    assert any("more than 4 sentences" in w for w in warns)


def test_concept_section_explains_the_idea_before_the_story():
    story_first = ("<section><h2>Records</h2><p>Neha writes one line for enquiry E00012: Vesu, Python.</p>"
                   "<p>That line is a <strong>record</strong>: one stored item.</p></section>")
    fails, _ = check_lesson(lesson(story_first), PATS)
    assert any("section 1 opens with a story or example" in f for f in fails)
    defined_first = ("<section><h2>Records</h2><p>A <strong>record</strong> is one stored item.</p>"
                     "<p>Neha writes one line for enquiry E00012: Vesu, Python.</p></section>")
    assert check_lesson(lesson(defined_first), PATS)[0] == []
    question_first = ("<section><h2>Records</h2><p>What is one row of a table?</p>"
                      "<p>It is a <strong>record</strong>: one stored item.</p></section>")
    assert check_lesson(lesson(question_first), PATS)[0] == []


def test_a_thin_concept_section_warns():
    thin = "<section><h2>Records</h2><p>A <strong>record</strong> is one stored item.</p></section>"
    _, warns = check_lesson(lesson(thin), PATS)
    assert any("section 1 has 6 words of explanation" in w for w in warns)
    full = "<section><h2>Records</h2><p>A <strong>record</strong> is one item.</p>" + "<p>Rows hold data.</p>" * 110
    _, warns = check_lesson(lesson(full + "</section>"), PATS)
    assert not any("words of explanation" in w for w in warns)


def test_at_most_three_key_terms_per_section_and_labels_do_not_count():
    body = ("<section><h2>X</h2><p>A <strong>count</strong>, a <strong>total</strong> and a "
            "<strong>mean</strong> differ.</p><p><strong>Fix:</strong> add.</p></section>")
    assert check_lesson(lesson(body), PATS)[0] == []
    body = body.replace("<strong>Fix:</strong>", "<strong>median</strong>")
    fails, _ = check_lesson(lesson(body), PATS)
    assert any("introduces 4 key terms (count, total, mean, median)" in f for f in fails)


def test_hard_words_name_the_simpler_one():
    fails, _ = check_lesson(lesson("<p>Choose a bounded action.</p>"), PATS)
    assert fails == ['"bounded" is hard for a beginner; say "limited" (references/voice.md plain words)']


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
    assert not any("over 20 words" in w for w in warns)
    assert not any("more than 4 sentences" in w for w in warns)
