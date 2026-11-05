from pathlib import Path

import course_env as ce
import gate_lesson


def test_ready_engine_and_venv_write_env_and_notes(tmp_path, monkeypatch, capsys):
    req = tmp_path / "req.txt"
    req.write_text("fastapi==0.1\n", encoding="utf-8")
    monkeypatch.setattr(ce, "engine_available", lambda: (True, ""))
    monkeypatch.setattr(ce, "ensure_venv", lambda cache, text, pys: (Path("vpy"), None))
    monkeypatch.setattr(ce, "venv_report", lambda vpy: ("Python 3.14.3", ["fastapi==0.1", "httpx2==1.0"]))
    assert ce.main(["--workdir", str(tmp_path / "w"), "--requirements", str(req)]) == 0
    env = (tmp_path / "w" / "_env.md").read_text(encoding="utf-8")
    assert "Python 3.14.3" in env and "- httpx2==1.0" in env and "installed" in env
    assert (tmp_path / "w" / "_course_notes.md").read_text(encoding="utf-8").startswith("# Course notes")
    assert "engine ready, venv ready" in capsys.readouterr().out


def test_existing_notes_are_kept_and_missing_engine_fails(tmp_path, monkeypatch):
    (tmp_path / "_course_notes.md").write_text("# Course notes\n- TestClient: use httpx2\n", encoding="utf-8")
    monkeypatch.setattr(ce, "engine_available", lambda: (False, "Pyodide engine is not installed"))
    assert ce.main(["--workdir", str(tmp_path), "--no-install"]) == 1
    assert "use httpx2" in (tmp_path / "_course_notes.md").read_text(encoding="utf-8")
    env = (tmp_path / "_env.md").read_text(encoding="utf-8")
    assert "MISSING: Pyodide engine is not installed" in env and "not used (no --requirements" in env


def test_missing_requirements_file_is_refused(tmp_path):
    assert ce.main(["--workdir", str(tmp_path), "--requirements", str(tmp_path / "none.txt")]) == 2


def test_gate_prints_one_fix_per_known_failure(tmp_path):
    fails = ["video: x: the lesson changed after its video part was written; rewrite it",
             "python: engine missing (tools/pyodide/README.md)",
             "python: practice task 1: the answer raises 'ModuleNotFoundError: No module named 'jwt''",
             "voice: 1 sentence(s) over 20 words"]
    found = gate_lesson.hints(fails, tmp_path, "l-01")
    assert len(found) == 3
    assert "storyplan.py" in found[0] and "stamp" in found[0] and "l-01.video.json" in found[0]
    assert "course_env.py" in found[1] and "_env.md" in found[2]
    assert gate_lesson.hints(["voice: 1 sentence(s) over 20 words"], tmp_path, "l-01") == []
