from verify_course import Report, verify_structure


def lesson(svg_width: int, inside_output: bool = False) -> dict:
    svg = (f'<svg viewBox="0 0 {svg_width} 200" role="img" aria-label="A figure">'
           '<text fill="var(--nb)">label</text></svg>')
    if inside_output:
        body = (f'<div class="nerdit-run"><div class="nerdit-out"><div class="nerdit-figure">{svg}'
                '<div class="nerdit-figure-caption">Chart output.</div></div></div></div>')
    else:
        body = f'<div class="nerdit-figure">{svg}<div class="nerdit-figure-caption">Cap.</div></div>'
    return {"lessons": [{"id": "x", "content": f'<div class="nerdit-wrapper nerdit-simple">{body}</div>'}]}


def failures(out: dict, contract: str = "v10") -> list[str]:
    rep = Report()
    verify_structure(rep, out, contract)
    return rep.failures


def test_v10_refuses_a_figure_too_wide_to_read_on_a_phone():
    assert any("svg 1 viewBox is 640 wide" in f for f in failures(lesson(640)))
    assert not any("viewBox is" in f for f in failures(lesson(360)))


def test_phone_width_rule_skips_v9_and_run_output_charts():
    assert not any("viewBox is" in f for f in failures(lesson(640), "v9"))
    assert not any("viewBox is" in f for f in failures(lesson(640, inside_output=True)))


def test_v11_checks_code_accuracy_across_the_course():
    from verify_course import Report, verify_code_accuracy
    spec = ('<script type="application/json" class="nerdit-files-spec">'
            '{"python": "3.12", "files": [{"name": "%s", "from": {"json": []}}]}</script>')
    lessons = [
        {"id": "a-01", "content": spec % "L01-S1-x.csv" + '<p>Run <code>go_now()</code>.</p>'
                                  '<pre data-lang="python"><code>go_now()</code></pre>'},
        {"id": "a-02", "content": spec % "L01-S1-x.csv" + '<p>Call <code>missing_fn()</code>.</p>'
                                  '<pre data-lang="python"><code>t = datetime.utcnow()</code></pre>'},
    ]
    rep = Report()
    verify_code_accuracy(rep, {"lessons": lessons})
    text = "\n".join(rep.failures)
    assert "a-02" in text and "missing_fn()" in text and "utcnow" in text
    assert "must start with L02-" in text and "used twice" in text
    assert not any(f.startswith("a-01") for f in rep.failures), rep.failures
