"""Title Case for headings, lesson titles, image labels and video titles."""
from titlecase import fix_headings, heading_problems, title_case


def test_main_words_get_capitals_and_joining_words_stay_small():
    assert title_case("1 — an observation becomes a record") == "1 — An Observation Becomes a Record"
    assert title_case("why isn't a prediction a guarantee?") == "Why Isn't a Prediction a Guarantee?"
    assert title_case("🧠 practice: training, testing and predictions") == "🧠 Practice: Training, Testing and Predictions"
    assert title_case("what to look for") == "What to Look For"            # last word always capital
    assert title_case("counting sums up what happened") == "Counting Sums Up What Happened"
    assert title_case("step-by-step guide to the data") == "Step-by-Step Guide to the Data"
    assert title_case("Joins With The Other Table") == "Joins with the Other Table"


def test_code_acronyms_brands_and_variables_are_left_alone():
    assert title_case("using df.head() and SQL") == "Using df.head() and SQL"
    assert title_case("iPhone sales vs. last year") == "iPhone Sales vs. Last Year"
    assert title_case("OR vs AND in SQL") == "OR vs AND in SQL"
    assert title_case("the value of x") == "The Value of x"
    assert title_case("डेटा क्या है") == "डेटा क्या है"


def test_headings_in_html_keep_tags_and_code():
    html = '<h2>3 — use <code>print()</code> to show it</h2><h3 class="a">what is a <strong>record</strong>?</h3><p>keep me</p>'
    assert fix_headings(html) == ('<h2>3 — Use <code>print()</code> to Show It</h2>'
                                  '<h3 class="a">What Is a <strong>Record</strong>?</h3><p>keep me</p>')
    assert heading_problems(html) == ["3 — use print() to show it", "what is a record?"]
    assert heading_problems(fix_headings(html)) == []
