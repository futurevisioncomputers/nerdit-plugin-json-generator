from pathlib import Path
import check_css_bundle as c

def _mk(d: Path, content: dict[str, str]):
    d.mkdir()
    for f in c.FILES:
        (d / f).write_text(content.get(f, "x"))

def test_identical_passes(tmp_path):
    _mk(tmp_path / "ref", {}); _mk(tmp_path / "app", {})
    assert c.main([str(tmp_path / "ref"), str(tmp_path / "app")]) == 0

def test_drift_fails(tmp_path):
    _mk(tmp_path / "ref", {}); _mk(tmp_path / "app", {"css10-brand.css": "y"})
    assert c.main([str(tmp_path / "ref"), str(tmp_path / "app")]) == 1

def test_windows_line_endings_pass(tmp_path):
    _mk(tmp_path / "ref", {}); _mk(tmp_path / "app", {})
    for f in c.FILES:
        (tmp_path / "ref" / f).write_bytes(b"a {\ncolor: red;\n}\n")
        (tmp_path / "app" / f).write_bytes(b"a {\r\ncolor: red;\r\n}\r\n")
    assert c.main([str(tmp_path / "ref"), str(tmp_path / "app")]) == 0


import re  # noqa: E402

V11_CLASSES = ["nerdit-vtable", "nerdit-vgroup", "nerdit-varrow", "nerdit-val", "nerdit-ws", "nerdit-null",
               "nerdit-vnote", "nerdit-cell-bad", "nerdit-cell-good", "nerdit-row-kept", "nerdit-row-dropped",
               "nerdit-vtitle", "nerdit-vlegend", "nerdit-grid", "nerdit-chk", "nerdit-tiles",
               "nerdit-tilegroup", "nerdit-tile", "nerdit-vsum", "nerdit-spot", "nerdit-data-note"]
CSS9 = Path(__file__).resolve().parent.parent / "references" / "css9-simple.css"


def test_css9_defines_every_v11_visual_class():
    css = CSS9.read_text(encoding="utf-8")
    assert [c for c in V11_CLASSES if f".{c}" not in css] == []


def test_v11_css_block_uses_tokens_not_hex():
    css = CSS9.read_text(encoding="utf-8")
    block = css[css.index("v11 · TEACHING VISUALS"):]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)


def test_v11_emphasis_survives_the_box_shadow_reset_and_cell_colour():
    # css9's reset sets box-shadow:none at specificity 0,5,0, and `.nerdit-vtable td` sets text
    # colour at 0,2,1; the v11 emphasis must not depend on box-shadow or lose to td colour.
    css = CSS9.read_text(encoding="utf-8")
    block = css[css.index("v11 · TEACHING VISUALS"):]
    assert "box-shadow" not in block
    assert ".nerdit-vtable td.nerdit-cell-bad" in block and ".nerdit-vtable td.nerdit-cell-good" in block
    assert "outline:" in block.split(".nerdit-chk.first", 1)[1].split("}", 1)[0]
