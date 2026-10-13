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
