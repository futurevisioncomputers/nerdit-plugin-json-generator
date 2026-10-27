#!/usr/bin/env python3
"""Run one lesson's offline examples and practice answers in real Python, inside the lesson gate.

The course-level checks (check_offline_outputs.py, check_files.py --as-learner) still run, but a
failure found there means resuming a writer that has already finished: it re-reads the rules,
the lesson and its history to change a few lines. Run here, the writer fixes it while the lesson
is still in hand. gate_lesson.py calls this with --run-dir <workdir>/gate-run and
--requirements <course requirements>.

- One venv per course, cached in <run-dir>/venv and rebuilt only when the requirements change.
- Offline examples (data-run="offline") run in page order and must print what the page shows.
- The solutions file the pack will ship (every page example, then every practice answer, in page
  order) runs beside the lesson's files and must finish without an error, as a learner runs it.
- The capstone's answers need the project tree; check_capstone.py runs them.
Stdlib only.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess

from check_files import _last_line, resolve_python
from check_offline_outputs import TIMEOUT, _run_lesson, _venv, is_capstone, offline_blocks
from check_python_outputs import python_parts
from nerdit_world_gen import build_files
from practice_files import _practice_file, practice_tasks


def ensure_venv(cache: Path, requirements: str, pythons: list[str]) -> tuple[Path | None, str | None]:
    """The course's venv: made on the first call, reused while the requirements are unchanged."""
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    stamp = hashlib.sha256(requirements.encode("utf-8")).hexdigest()
    venv = cache / "venv"
    vpy = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    mark = cache / "venv.stamp"
    if vpy.exists() and mark.is_file() and mark.read_text(encoding="utf-8") == stamp:
        return vpy, None
    for spec in pythons:
        exe = resolve_python(spec)
        if exe is None:
            continue
        made, err = _venv(exe, venv, requirements)
        if made is not None:
            mark.write_text(stamp, encoding="utf-8")
        return made, err
    return None, f"none of Python {', '.join(pythons)} is installed"


def lesson_runs(lesson: dict, position: int, vpy: Path | None, workdir: Path,
                files: list[Path] = (), pythonpath: Path | None = None) -> tuple[list[str], list[str]]:
    """(failures, warnings) for one lesson's offline examples and practice answers."""
    html = lesson.get("content", "")
    answers = [t for t in practice_tasks(html) if t["solution"]]
    if not offline_blocks(html) and not answers:
        return [], []
    workdir = Path(workdir).resolve()
    fails, warns = [], []
    if offline_blocks(html):
        fails += [p.split(": ", 1)[1] if p.startswith(lesson["id"] + ": ") else p
                  for p in _run_lesson(vpy, lesson, workdir / "examples", list(files), pythonpath)]
    if not answers:
        return fails, warns
    if is_capstone(html):
        return fails, warns + ["practice answers: the capstone's are run by check_capstone.py"]
    folder = workdir / "answers" / lesson["id"]
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    dataset = python_parts(html)["dataset"]
    for name, text in (build_files(dataset) if dataset else {}).items():
        (folder / name).write_text(text, encoding="utf-8", newline="")
    for path in files:
        shutil.copy(path, folder / Path(path).name)
    chapter = {"position": position, "title": lesson.get("title", ""), "html": html}
    script = folder / f"L{position:02d}-solutions.py"
    script.write_bytes(_practice_file(script.name, chapter, solutions=True))
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run([str(vpy), "-W", "error", script.name], cwd=folder, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        return fails + [f"practice answers: still running after {TIMEOUT} s (a server started? only start one "
                        "when its settings are set)"], warns
    if proc.returncode != 0:
        fails.append("practice answers: run after every example on the page, in page order, they stop with "
                     f'"{_last_line(proc)}"; make each answer build what it needs')
    return fails, warns
