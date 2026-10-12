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
