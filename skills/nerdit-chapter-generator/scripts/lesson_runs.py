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

# Agg's plt.show() warns that it cannot show a window; ignore only that warning under -W error.
SHOW_OK = ['-W', 'ignore:FigureCanvasAgg is non-interactive:UserWarning']


def ensure_venv(cache: Path, requirements: str, pythons: list[str]) -> tuple[Path | None, str | None]:
    """The course's venv: made on the first call, reused while the requirements are unchanged."""
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    stamp = hashlib.sha256(requirements.encode("utf-8")).hexdigest()
    venv = cache / "venv"
    vpy = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    mark = cache / "venv.stamp"

    def ready() -> bool:
        return vpy.exists() and mark.is_file() and mark.read_text(encoding="utf-8") == stamp

    if ready():
        return vpy, None
    # Parallel writers gate at once: one builds, the rest wait, then reuse (spec 2026-10-30).
    with _lock(cache / "venv.lock"):
        if ready():
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


LOCK_STALE = 30 * 60   # seconds: a lock older than this was left by a gate that died


class _lock:
    """An exclusive lock file (O_EXCL works on every OS); waits for the holder, breaks a stale one."""

    def __init__(self, path: Path):
        self.path = path

    def __enter__(self):
        import time
        while True:
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > LOCK_STALE:
                        self.path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                time.sleep(0.2)

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


# Runs page steps in one namespace, as the site does: each answer on its own copy of the names
# (a predict's `x = 5` never reaches the next answer), with top-level await allowed (the site's
# engine allows it). Prints {id: {"stdout", "error"}} as JSON.
ANSWER_DRIVER = r'''
import ast, asyncio, contextlib, inspect, io, json, sys
steps = json.load(open(sys.argv[1], encoding="utf-8"))
ns, out = {"__name__": "__nerdit_lesson__"}, {}
for s in steps:
    g = dict(ns) if s["isolated"] else ns
    buf, err = io.StringIO(), None
    try:
        code = compile(s["code"], s["id"], "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        with contextlib.redirect_stdout(buf):
            if code.co_flags & inspect.CO_COROUTINE:
                asyncio.run(eval(code, g))
            else:
                exec(code, g)
    except BaseException as exc:
        err = f"{type(exc).__name__}: {exc}"
    out[s["id"]] = {"stdout": buf.getvalue(), "error": err}
sys.stdout.write(json.dumps(out))
'''


def answer_runs(html: str, vpy: Path, folder: Path) -> list[str]:
    """Failures for the answers the browser engine cannot check because they use names from an
    offline run line (check_python_outputs.py reports those as "check locally"): every
    predict, fill-in and practice answer runs here, in real Python, after the run lines above it
    (practice answers after all of them), and must print what the page shows."""
    import json
    from check_python_outputs import normalise
    parts = python_parts(html)
    runs, answers = parts["runs"], parts["answers"]
    steps, labels, counts = [], {}, {}
    for k, ans in enumerate(answers):
        counts[ans["kind"]] = counts.get(ans["kind"], 0) + 1
        labels[f"ans{k}"] = f"{'practice task' if ans['kind'] == 'practice' else ans['kind']} {counts[ans['kind']]}"
    for i in range(len(runs) + 1):
        for k, ans in enumerate(answers):
            if ans["kind"] != "practice" and ans["after"] == i:
                steps.append({"id": f"ans{k}", "code": ans["code"], "isolated": True})
        if i < len(runs):
            steps.append({"id": f"run{i + 1}", "code": runs[i]["code"], "isolated": False})
    steps += [{"id": f"ans{k}", "code": a["code"], "isolated": False}
              for k, a in enumerate(answers) if a["kind"] == "practice"]
    if not any(s["id"].startswith("ans") for s in steps):
        return []
    (folder / "_answers.json").write_text(json.dumps(steps), encoding="utf-8")
    (folder / "_answer_driver.py").write_text(ANSWER_DRIVER, encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"}
    try:
        proc = subprocess.run([str(vpy), "_answer_driver.py", "_answers.json"], cwd=folder, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT, env=env)
        results = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        return [f"answers: still running after {TIMEOUT} s in real Python"]
    except ValueError:
        return [f"answers: could not run in real Python: {_last_line(proc)}"]
    fails = []
    for k, ans in enumerate(answers):
        got, shown = results.get(f"ans{k}"), ans["shown"]
        if got is None:
            continue
        if got["error"] is not None and ans["kind"] == "practice":
            continue                      # the solutions run below reports a practice answer that stops
        if got["error"] is not None and (shown is None or got["error"] not in normalise(shown)):
            fails.append(f"{labels[f'ans{k}']}: in real Python, after the examples above it, the answer raises "
                         f"'{got['error']}'; make it run on the page as written")
        elif got["error"] is None and shown is not None and normalise(got["stdout"]) != normalise(shown):
            fails.append(f"{labels[f'ans{k}']}: shown {normalise(shown)[:80]!r} but real Python prints "
                         f"{normalise(got['stdout'])[:80]!r}")
    return fails


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
        # The browser engine skips an answer that uses an offline line's names; check it here.
        real = workdir / "answers-real" / lesson["id"]
        shutil.rmtree(real, ignore_errors=True)
        real.mkdir(parents=True)
        dataset = python_parts(html)["dataset"]
        for name, text in (build_files(dataset) if dataset else {}).items():
            (real / name).write_text(text, encoding="utf-8", newline="")
        for path in files:
            shutil.copy(path, real / Path(path).name)
        fails += answer_runs(html, vpy, real)
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
    # Agg: plt.show() on a desktop backend opens a window and blocks until the timeout.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"}
    try:
        proc = subprocess.run([str(vpy), "-W", "error", *SHOW_OK, script.name], cwd=folder, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        return fails + [f"practice answers: still running after {TIMEOUT} s (a server started? only start one "
                        "when its settings are set)"], warns
    if proc.returncode != 0:
        fails.append("practice answers: run after every example on the page, in page order, they stop with "
                     f'"{_last_line(proc)}"; make each answer build what it needs')
    return fails, warns
