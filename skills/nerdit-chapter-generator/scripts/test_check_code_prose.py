import json

import check_code_prose as cp


def section(title, prose, code, output=''):
    return (f'<section><h2>{title}</h2>{prose}<div class="nerdit-run"><div class="nerdit-in">'
            f'<pre data-lang="python"><code>{code}</code></pre></div><div class="nerdit-out">'
            f'<pre><code>{output}</code></pre></div></div></section>')


def test_prose_matching_its_code_passes():
    html = section('1 — Read rows', '<p>Call <code>df.head(3)</code> to see three rows; <code>head()</code> '
                   'shows five by default. Python prints 42 below.</p>', 'df = load()\nprint(df.head(3))\nprint(42)',
                   'a\n42')
    assert cp.check_lesson(html) == []


def test_code_named_in_prose_but_not_on_the_page_fails():
    html = section('1 — Read rows', '<p>Use <code>df.tail(2)</code> to see the last rows.</p>',
                   'print(df.head(2))', 'x')
    fails = cp.check_lesson(html)
    assert len(fails) == 1 and 'df.tail(2)' in fails[0] and '1 — Read rows' in fails[0]


def test_a_number_the_prose_says_is_printed_must_be_in_the_output():
    html = section('2 — Count', '<p>The loop prints 12 for Surat.</p>', 'print(11)', '11')
    fails = cp.check_lesson(html)
    assert len(fails) == 1 and '12' in fails[0]
    ok = section('2 — Count', '<p>It returns 1,250 rows.</p>', 'print(n)', '1250')
    assert cp.check_lesson(ok) == []


def test_plain_words_keywords_and_placeholders_are_not_judged():
    html = section('1 — If', '<p>Use <code>if</code>, <code>None</code>, <code>TypeError</code> and '
                   '<code>list.append(&lt;item&gt;)</code> or <code>name = ...</code> in your own code.</p>',
                   'x = 1', '')
    assert cp.check_lesson(html) == []


def test_sql_and_seed_count_as_code():
    html = ('<section><h2>1 — Filter</h2><p>The clause <code>WHERE city = \'Surat\'</code> keeps two rows.</p>'
            '<pre data-lang="sql"><code>SELECT name FROM customers\nWHERE city = \'Surat\';</code></pre></section>')
    assert cp.check_lesson(html) == []


def test_cli(tmp_path):
    course = {'lessons': [{'id': 'a-01', 'content': section('1 — X', '<p><code>run_it()</code> starts.</p>',
                                                            'go()', '')}]}
    path = tmp_path / 'c.json'
    path.write_text(json.dumps(course), encoding='utf-8')
    assert cp.main(['--course', str(path)]) == 1


# A code walk explains a run block line by line. Each step quotes one whole line of that
# section's code, so the walk can never describe code the learner cannot see.
def test_a_code_walk_quotes_whole_lines_of_its_sections_code():
    code = 'app = Flask(__name__)\n@app.get("/products/1")\ndef product():\n    return {"id": 1}'
    walk = ('<ol class="nerdit-codewalk"><li><code>@app.get("/products/1")</code> registers the function.</li>'
            '<li><code>return {"id": 1}</code> becomes the JSON body.</li></ol>')
    html = section('1 — Routes', '<p>A route.</p>', code, '200') .replace('</section>', walk + '</section>')
    assert cp.check_lesson(html) == []
    bad = html.replace('<code>return {"id": 1}</code>', '<code>return {"id": 2}</code>')
    fails = cp.check_lesson(bad)
    assert any('code walk' in f and 'return {"id": 2}' in f and '1 — Routes' in f for f in fails), fails
    part = html.replace('<code>@app.get("/products/1")</code>', '<code>@app.get</code>')
    assert any('code walk' in f and '`@app.get`' in f for f in cp.check_lesson(part))
