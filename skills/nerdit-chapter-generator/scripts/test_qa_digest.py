import json

import qa_digest as qd

HTML = """<div class="nerdit-wrapper nerdit-simple">
<h1>Routes</h1>
<style>.x{color:red}</style>
<h2>1 — One Route</h2>
<p>A <code>route</code> maps a URL to a function.</p>
<pre class="nerdit-map"><span class="nerdit-map-label">Two ways</span>a <b>→</b> b
c <b>→</b> d</pre>
<div class="nerdit-run" data-run="offline">
  <div class="nerdit-in"><span class="nerdit-tag">You type</span>
    <pre data-lang="python"><code>print(1 &lt; 2)</code></pre></div>
  <div class="nerdit-out"><span class="nerdit-tag">Python shows</span><pre><code>True</code></pre></div>
</div>
<div class="nerdit-terminal"><span class="nerdit-prompt">$ </span><span>flask run</span>
<span class="nerdit-out"> * Running</span></div>
<figure class="nerdit-figure"><svg viewBox="0 0 10 10" role="img" aria-label="Browser to app">
<rect x="0" y="0" width="5" height="5" style="fill:var(--a)"/><text x="1" y="1">Browser</text>
<text x="2" y="2">①</text></svg><figcaption>A request travels.</figcaption></figure>
<table><tr><th>name</th><th>fee</th></tr><tr><td>Asha</td><td>900</td></tr></table>
<details><summary>Show answer</summary><p>Because.</p></details>
<script>window.helper = function () { return 1; };</script>
<script type="application/json" class="nerdit-files-spec">{"python": "3.12"}</script>
</div>"""

COURSE = {
    "lessons": [{
        "id": "routes-01", "title": "Routes", "duration": "10m", "content": HTML,
        "questions": [{"id": "lesson-1-routes-01-q1-1", "text": "What prints?",
                       "options": ["1", "True", "False", "None"], "correctOptionIndex": 1}],
    }],
    "assessment": {"questions": [
        {"id": "assessment-1-routes-01-q1-1", "text": "Mine?", "options": ["a", "b", "c", "d"],
         "correctOptionIndex": 0},
        {"id": "assessment-1-other-02-q1-1", "text": "Not mine", "options": ["a", "b", "c", "d"],
         "correctOptionIndex": 0},
    ]},
}


def test_text_code_figures_and_answers_survive():
    text = qd.html_to_text(HTML)
    assert "## 1 — One Route" in text
    assert "A `route` maps a URL to a function." in text
    assert "```python\nprint(1 < 2)\n```" in text and "True" in text
    assert "[nerdit-run offline]" in text and "[nerdit-in]" in text and "[nerdit-out]" in text
    assert "aria-label: Browser to app" in text and "labels: Browser | ①" in text
    assert "Caption: A request travels." in text
    assert "| name | fee |" in text and "| Asha | 900 |" in text
    assert "<details> Show answer" in text and "Because." in text
    assert '{"python": "3.12"}' in text and "[nerdit-files-spec]" in text


def test_maps_and_terminals_keep_their_lines():
    text = qd.html_to_text(HTML)
    assert "Two ways\na → b\nc → d" in text
    assert "$ flask run\n * Running" in text


def test_markup_geometry_styles_and_helper_scripts_are_dropped():
    text = qd.html_to_text(HTML)
    for gone in ("color:red", "viewBox", "<rect", "fill:var", "window.helper", "nerdit-simple", "class="):
        assert gone not in text


def test_lesson_digest_carries_its_own_questions_with_the_marked_answer(tmp_path):
    sizes = qd.build(COURSE, tmp_path)
    assert [s[0] for s in sizes] == ["routes-01"]
    text = (tmp_path / "routes-01.md").read_text(encoding="utf-8")
    assert text.startswith("# DIGEST routes-01 — Routes")
    assert "B. True (marked correct)" in text
    assert "Mine?" in text and "Not mine" not in text


def test_cli_writes_digests_and_reports_the_saving(tmp_path, capsys):
    course = tmp_path / "course-x_output.json"
    course.write_text(json.dumps(COURSE), encoding="utf-8")
    assert qd.main(["--course", str(course), "--out", str(tmp_path / "_digest")]) == 0
    assert (tmp_path / "_digest" / "routes-01.md").is_file()
    assert "smaller" in capsys.readouterr().out
    assert qd.main(["--course", str(tmp_path / "missing.json"), "--out", str(tmp_path)]) == 2
