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
