from blocks import lesson_blocks, plain

# Copied from Flask lesson flask-first-application-03 (2026-11-19).
FLASK = """
<section><h2>1 — Create the Application</h2>
<div class="nerdit-run" data-run="offline">
  <div class="nerdit-in"><span class="nerdit-tag">You type</span>
<pre data-lang="python"><code>from flask import Flask

app = Flask(__name__)
print(type(app).__name__)</code></pre></div>
  <div class="nerdit-out"><span class="nerdit-tag">Python shows</span>
<pre><code>Flask</code></pre></div>
</div>
<div class="nerdit-predict">
  <div class="nerdit-predict-head">🤔 Try It — Predict the output</div>
  <p>Flask is imported as above. What does this print?</p>
  <pre data-lang="python"><code>site = Flask(__name__)
print(type(site).__name__)</code></pre>
  <details class="nerdit-predict-answer">
    <summary>Show answer</summary>
    <div class="nerdit-out"><span class="nerdit-tag">Python shows</span><pre><code>Flask</code></pre></div>
    <p>The variable name does not matter. <code>site</code> holds an object made from the <code>Flask</code> class.</p>
  </details>
</div>
</section>
<section><h2>2 — Routes and View Functions</h2>
<div class="nerdit-compare">
  <div class="nerdit-compare-bad"><div class="nerdit-compare-head">Mistake: no guard, no server</div>
<pre data-lang="python"><code>@app.route("/")
def home():
    return "Welcome"
# no app.run(): python hello.py prints nothing</code></pre>
<p>The prompt returns at once. The route exists, but nothing listens for a browser.</p></div>
  <div class="nerdit-compare-good"><div class="nerdit-compare-head">Fix: end the file with the guard</div>
<pre data-lang="python"><code>if __name__ == "__main__":
    app.run()
# Running on http://127.0.0.1:5000</code></pre>
<p>Now the terminal shows the Running line and waits.</p></div>
</div>
</section>
<h2>📋 Cheat Sheet</h2>
<div class="nerdit-cheatsheet">
  <table>
    <thead><tr><th>Keyword</th><th>What it does</th><th>Tiny example</th></tr></thead>
    <tbody>
      <tr><td>application object</td><td>Holds your routes and settings</td><td><code>app = Flask(__name__)</code></td></tr>
      <tr><td>route</td><td>Links a URL to a view function</td><td><code>@app.route("/")</code></td></tr>
    </tbody>
  </table>
</div>
"""

ENTITIES = """<h2>1 — HTML</h2><div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span>
<pre data-lang="python"><button class="nerdit-copy-btn" onclick="copyCode(this)">Copy</button><code>return "&lt;h1&gt;Hi <b>&amp;</b> bye&lt;/h1&gt;"</code></pre></div>
<div class="nerdit-out"><span class="nerdit-tag">Browser shows</span><pre><code>Hi &amp; bye</code></pre></div></div>"""

# Shaped like the regression course's "meet the data" table and a run that reads a CSV.
CSV_RUN = """<h2>1 — Overdispersion</h2>
<div class="nerdit-figure" data-visual="value-table"><table class="nerdit-vtable">
<thead><tr><th>column</th><th>meaning</th></tr></thead>
<tbody><tr><td><code>branch</code></td><td>Citylight, Vesu or Pal</td></tr>
<tr class="nerdit-spot"><td><code>complaints</code></td><td>the count to predict</td></tr></tbody></table>
<div class="nerdit-figure-caption">Arjun's file <code>weekly_complaints.csv</code> has 520 rows.</div></div>
<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span>
<pre data-lang="python"><code>import pandas as pd
adm = pd.read_csv("weekly_admissions.csv")
print(adm.shape)</code></pre></div>
<div class="nerdit-out"><span class="nerdit-tag">Python shows</span><pre><code>(520, 5)</code></pre></div></div>"""


def test_run_block_keeps_code_and_output_verbatim():
    run = lesson_blocks(FLASK)["topics"][1]["run"][0]
    assert run["code"] == 'from flask import Flask\n\napp = Flask(__name__)\nprint(type(app).__name__)'
    assert run["output"] == "Flask" and run["outTag"] == "Python shows" and run["lang"] == "python"
    assert run["index"] == 0 and run["reads"] == []


def test_predict_compare_and_cheatsheet():
    b = lesson_blocks(FLASK)
    p = b["topics"][1]["predict"][0]
    assert p["question"] == "Flask is imported as above. What does this print?" and p["output"] == "Flask"
    assert p["outTag"] == "Python shows"
    assert p["code"] == "site = Flask(__name__)\nprint(type(site).__name__)"
    assert p["explanation"].startswith("The variable name does not matter.")
    c = b["topics"][2]["compare"][0]
    assert c["bad"]["head"] == "Mistake: no guard, no server" and c["good"]["code"].startswith('if __name__ == "__main__":')
    assert c["bad"]["reason"] == "The prompt returns at once. The route exists, but nothing listens for a browser."
    assert b["cheatsheet"]["headers"] == ["Keyword", "What it does", "Tiny example"]
    assert b["cheatsheet"]["rows"][0] == ["application object", "Holds your routes and settings", "app = Flask(__name__)"]


def test_entities_markup_and_copy_button_never_reach_the_code():
    run = lesson_blocks(ENTITIES)["topics"][1]["run"][0]
    assert run["code"] == 'return "<h1>Hi & bye</h1>"' and run["output"] == "Hi & bye"


def test_csv_names_read_by_the_code_and_the_data_table():
    t = lesson_blocks(CSV_RUN)["topics"][1]
    assert t["run"][0]["reads"] == ["weekly_admissions.csv"]
    spot = t["spot"][0]
    assert spot["headers"] == ["column", "meaning"] and spot["rows"][1] == ["complaints", "the count to predict"]
    assert spot["caption"] == "Arjun's file weekly_complaints.csv has 520 rows."


def test_plain_drops_tags_and_keeps_pre_newlines():
    assert plain("<p>a <code>b</code> &amp; c</p>") == "a b & c"
    assert plain('<pre><button class="nerdit-copy-btn">Copy</button><code>x = 1\ny = 2</code></pre>') == "x = 1\ny = 2"


def test_a_lesson_without_blocks():
    assert lesson_blocks("<h2>1 — Intro</h2><p>Text</p>") == {"topics": {1: {"run": [], "predict": [], "compare": [], "spot": []}}, "cheatsheet": None}
