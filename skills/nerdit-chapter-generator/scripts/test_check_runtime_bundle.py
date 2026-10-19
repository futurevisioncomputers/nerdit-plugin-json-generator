from pathlib import Path

import check_runtime_bundle as c


def _mk(d: Path, content: dict[str, str], skip=()):
    d.mkdir()
    for f in c.FILES:
        if f not in skip:
            (d / f).write_text(content.get(f, f"// {f}\n"), encoding="utf-8")


def test_identical_passes(tmp_path):
    _mk(tmp_path / "ref", {})
    _mk(tmp_path / "app", {})
    assert c.main([str(tmp_path / "ref"), str(tmp_path / "app")]) == 0


def test_drift_fails(tmp_path, capsys):
    _mk(tmp_path / "ref", {})
    _mk(tmp_path / "app", {"nerdit_world_gen.py": "# changed\n"})
    assert c.main([str(tmp_path / "ref"), str(tmp_path / "app")]) == 1
    assert "DRIFT" in capsys.readouterr().out


def test_missing_file_fails(tmp_path, capsys):
    _mk(tmp_path / "ref", {})
    _mk(tmp_path / "app", {}, skip=("nerdit-plot-runner.js",))
    assert c.main([str(tmp_path / "ref"), str(tmp_path / "app")]) == 1
    out = capsys.readouterr().out
    assert "MISSING" in out and "nerdit-plot-runner.js" in out


def test_windows_line_endings_pass(tmp_path):
    _mk(tmp_path / "ref", {})
    _mk(tmp_path / "app", {})
    for f in c.FILES:
        (tmp_path / "ref" / f).write_bytes(b"a = 1\nb = 2\n")
        (tmp_path / "app" / f).write_bytes(b"a = 1\r\nb = 2\r\n")
    assert c.main([str(tmp_path / "ref"), str(tmp_path / "app")]) == 0


def test_the_bundle_lists_the_runners_and_the_generator():
    assert c.FILES == ("nerdit-python-runner.js", "nerdit-plot-runner.js", "nerdit-sql-runner.js",
                       "nerdit-excel-engine.js", "nerdit_world_gen.py")
