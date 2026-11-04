from check_outline import outline_problems

OUTLINE = [
    "Create a route with `@app.get()`",
    "Path parameters",
    "Validate parameters with `Path()` and `Query()`",
]

GOOD = """
<section><h2 data-outline="1">1 — Your First Route</h2>
<p>Use <code>@app.get("/")</code> to answer a request.</p>
<h3 class="nerdit-runhead" data-outline="2">Read a value from the URL</h3>
<p>A path parameter comes from the URL.</p></section>
<section><h2 data-outline="3">2 — Check the Values</h2>
<p>Use <code>Path(gt=0)</code> and <code>Query(max_length=20)</code>.</p></section>
"""


def test_every_item_tagged_and_covered_passes():
    assert outline_problems(GOOD, OUTLINE) == []


def test_no_outline_means_nothing_to_check():
    assert outline_problems("<h2>1 — Anything</h2>", []) == []


def test_untagged_item_fails():
    html = GOOD.replace(' data-outline="2"', "")
    probs = outline_problems(html, OUTLINE)
    assert len(probs) == 1 and "item 2" in probs[0] and "Path parameters" in probs[0]


def test_one_heading_may_cover_two_items():
    html = GOOD.replace(' data-outline="2"', "").replace('data-outline="1"', 'data-outline="1 2"')
    assert outline_problems(html, OUTLINE) == []


def test_index_out_of_range_fails():
    html = GOOD.replace('data-outline="3"', 'data-outline="3 4"')
    assert any("4" in p and "only 3" in p for p in outline_problems(html, OUTLINE))


def test_tag_on_a_paragraph_fails():
    html = GOOD.replace('<p>A path', '<p data-outline="2">A path').replace(
        ' class="nerdit-runhead" data-outline="2"', ' class="nerdit-runhead"')
    probs = outline_problems(html, OUTLINE)
    assert any("<p>" in p for p in probs)


def test_tagged_section_missing_the_items_code_term_fails():
    html = GOOD.replace("<code>Query(max_length=20)</code>", "a query check")
    probs = outline_problems(html, OUTLINE)
    assert len(probs) == 1 and "Query" in probs[0] and "item 3" in probs[0]


def test_code_term_counted_only_in_its_own_section():
    # `Path()` appears in section 2 only; tagging section 1 with item 3 is not coverage.
    html = GOOD.replace('data-outline="3"', "").replace('data-outline="1"', 'data-outline="1 3"')
    probs = outline_problems(html, OUTLINE)
    assert any("item 3" in p and "Path" in p for p in probs)


def test_runhead_section_runs_to_next_heading():
    outline = ["Path parameters with `item_id`"]
    html = ('<h2>1 — A</h2><h3 class="nerdit-runhead" data-outline="1">x</h3>'
            '<p><code>item_id</code></p><h2>2 — B</h2>')
    assert outline_problems(html, outline) == []
