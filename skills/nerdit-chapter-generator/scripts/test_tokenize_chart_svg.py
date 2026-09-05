import os
import subprocess
import sys

from tokenize_chart_svg import tokenize

SCRIPT = os.path.join(os.path.dirname(__file__), "tokenize_chart_svg.py")


def test_attribute_form_is_rewritten():
    out, left = tokenize('<rect fill="#003b6c"/>')
    assert out == '<rect fill="var(--nb)"/>'
    assert left == []


def test_style_form_is_rewritten():
    # matplotlib writes ticks this way, with a space after the colon
    out, left = tokenize('<use style="stroke: #000000; stroke-width: 0.8"/>')
    assert 'stroke: var(--tx)' in out
    assert left == []


def test_case_is_ignored():
    out, _ = tokenize('<path fill="#003B6C"/>')
    assert out == '<path fill="var(--nb)"/>'


def test_unknown_colour_is_left_alone_and_reported():
    # A colour outside the palette is a content bug for CORE.md 7b to catch. Guessing the
    # nearest token would hide it.
    out, left = tokenize('<rect fill="#ff00ff"/>')
    assert out == '<rect fill="#ff00ff"/>'
    assert left == ["#ff00ff"]


def test_gradient_and_flood_colours_are_covered():
    out, left = tokenize('<stop stop-color="#e7dcc7"/><feFlood flood-color="#2b2620"/>')
    assert 'stop-color="var(--bd-soft)"' in out
    assert 'flood-color="var(--tx)"' in out
    assert left == []


def test_non_colour_hashes_are_untouched():
    # xlink references and ids also start with '#'; only colour-bearing attributes move.
    svg = '<use xlink:href="#glyph-1" fill="#003b6c"/>'
    out, _ = tokenize(svg)
    assert 'xlink:href="#glyph-1"' in out
    assert 'fill="var(--nb)"' in out


def test_a_realistic_chart_ends_with_no_literals():
    svg = (
        '<svg><g id="patch_1"><path style="fill: #fffbf3; stroke: #000000"/></g>'
        '<g id="bars"><path fill="#003b6c"/><path fill="#003b6c"/></g>'
        '<g id="grid"><path style="stroke: #e7dcc7; stroke-width: 0.8"/></g>'
        '<g id="text"><text style="fill: #2b2620">Sales by region</text></g></svg>'
    )
    out, left = tokenize(svg)
    assert left == []
    assert out.count("var(--") == 6


def test_cli_rewrites_in_place(tmp_path):
    p = tmp_path / "bar.svg"
    p.write_text('<rect fill="#003b6c"/>', encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "--in", str(p)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert p.read_text(encoding="utf-8") == '<rect fill="var(--nb)"/>'


def test_cli_check_exits_two_on_leftover(tmp_path):
    p = tmp_path / "bar.svg"
    p.write_text('<rect fill="#ff00ff"/>', encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "--in", str(p), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 2
    assert "#ff00ff" in r.stdout


def test_cli_check_exits_zero_when_clean(tmp_path):
    p = tmp_path / "bar.svg"
    p.write_text('<rect fill="#003b6c"/>', encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "--in", str(p), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0
