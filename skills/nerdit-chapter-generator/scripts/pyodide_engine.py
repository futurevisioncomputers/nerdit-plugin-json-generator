"""Driver for the pinned Pyodide engine (tools/pyodide/engine.mjs).

The website runs lesson Python on Pyodide 0.26.2. Checking outputs on the same engine means
the same library versions, the same float printing and the same error lines.

    run_job({"files": {...}, "steps": [{"id", "code", "fresh"}], "probe": [...]})

Set NERDIT_PYODIDE_DIR to use an engine installed elsewhere. Stdlib only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent / "tools" / "pyodide"
ENGINE = ENGINE_DIR / "engine.mjs"


class EngineError(Exception):
    """The engine is missing, crashed or returned something unreadable."""


class EngineTimeout(EngineError):
    """The job ran past its timeout; Node was stopped."""


def engine_dir() -> Path:
    return Path(os.environ.get("NERDIT_PYODIDE_DIR") or ENGINE_DIR)


def engine_available() -> tuple[bool, str]:
    """(True, "") when Node is on PATH and the pinned package is installed; else (False, reason)."""
    folder = engine_dir()
    if shutil.which("node") is None:
        return False, f"Node.js is not on PATH: install Node 18 or later, then run `npm ci` in {folder}"
    if not (folder / "node_modules" / "pyodide").is_dir():
        return False, f"Pyodide engine is not installed: run `npm ci` in {folder} (see tools/pyodide/README.md)"
    return True, ""


def run_job(job: dict, timeout: int = 120) -> dict:
    ok, reason = engine_available()
    if not ok:
        raise EngineError(reason)
    try:
        proc = subprocess.run([shutil.which("node"), str(ENGINE), str(engine_dir())],
                              input=json.dumps(job).encode("utf-8"), capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:  # subprocess.run has already killed Node
        raise EngineTimeout(f"timed out after {timeout} s") from exc
    err = proc.stderr.decode("utf-8", "replace").strip()
    if proc.returncode != 0:
        raise EngineError(f"engine exited {proc.returncode}: {err[-500:]}")
    try:
        result = json.loads(proc.stdout.decode("utf-8"))
    except ValueError as exc:
        raise EngineError(f"engine returned no result: {err[-500:]}") from exc
    if not isinstance(result, dict) or not isinstance(result.get("results"), list):
        raise EngineError("engine result has no results list")
    if result.get("load_errors"):
        # Usually a first run without internet: the packages were never cached.
        raise EngineError(f"packages could not be downloaded ({result['load_errors'][0][:200]}); connect to the "
                          f"internet once so the engine can cache them (tools/pyodide/README.md)")
    return result
