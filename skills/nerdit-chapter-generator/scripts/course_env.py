#!/usr/bin/env python3
"""Set up a course's checking environment once, before any writer starts, and write it down.

    python course_env.py --workdir <workdir> [--requirements <requirements.txt>] [--pythons 3.14,3.12]
                         [--no-install]

1. The browser engine (tools/pyodide): runs `npm ci` there when it is not installed, so no
   writer stops on "engine missing" and installs it itself (each plugin update starts empty).
2. The gate venv (<workdir>/gate-run, the one gate_lesson.py --run-dir uses): built once from
   the course requirements, so parallel writers do not wait on it or probe pip.
3. <workdir>/_env.md: Python version and every installed package version in that venv, the
   engine state, and the course notes file. Each writer reads it instead of running
   `pip show`, `pip list`, `python -c "import x"` or `npm ci`.
4. <workdir>/_course_notes.md (created empty if missing): course-wide fixes writers report on a
   NOTE: line; the orchestrator appends them, so later writers do not rediscover them.

Exit 0 = ready, 1 = something is missing (the reason is in _env.md and printed), 2 = bad input.
Stdlib only.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lesson_runs import ensure_venv  # noqa: E402
from pyodide_engine import engine_available, engine_dir  # noqa: E402

NOTES_HEAD = ("# Course notes: fixes that hold for every lesson of this course\n\n"
              "Writers report these on a `NOTE:` line; the orchestrator appends them here. Read before\n"
              "writing; apply each one instead of rediscovering it.\n")


def install_engine(install: bool) -> tuple[bool, str]:
    ok, reason = engine_available()
    if ok or not install:
        return ok, reason
    npm = shutil.which("npm")
    if npm is None:
        return False, reason + " (npm is not on PATH)"
    proc = subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=engine_dir(),
                          capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        return False, f"`npm ci` failed in {engine_dir()}: {(proc.stderr or proc.stdout)[-400:]}"
    return engine_available()


def venv_report(vpy: Path) -> tuple[str, list[str]]:
    version = subprocess.run([str(vpy), "--version"], capture_output=True, text=True).stdout.strip()
    freeze = subprocess.run([str(vpy), "-m", "pip", "freeze", "--disable-pip-version-check"],
                            capture_output=True, text=True).stdout.split()
    return version, sorted(freeze, key=str.lower)


def write_env(workdir: Path, engine: tuple[bool, str], venv: tuple[str, list[str]] | None,
              venv_error: str | None) -> Path:
    lines = ["# Course environment (written once by course_env.py; do not probe it again)", ""]
    lines.append("## Browser engine (Pyodide, what check_python_outputs.py runs)")
    lines.append("installed" if engine[0] else f"MISSING: {engine[1]}")
    lines.append("Libraries it cannot load go in an offline run line (runners/python.md). Ask "
                 "`check_python_outputs.py --probe <modules>` before planning, never memory.")
    lines.append("")
    lines.append("## Gate venv (offline examples and practice answers; `<workdir>/gate-run/venv`)")
    if venv_error:
        lines.append(f"NOT BUILT: {venv_error}")
    elif venv is None:
        lines.append("not used (no --requirements: this course runs no local Python)")
    else:
        lines.append(venv[0])
        lines += [f"- {pkg}" for pkg in venv[1]]
    lines += ["", "## Course notes", f"`{(workdir / '_course_notes.md').as_posix()}`: read it before writing."]
    path = workdir / "_env.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    notes = workdir / "_course_notes.md"
    if not notes.exists():
        notes.write_text(NOTES_HEAD, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--requirements", help="the course requirements file (code courses with local Python)")
    ap.add_argument("--pythons", default="3.14,3.12", help="same default as gate_lesson.py")
    ap.add_argument("--no-install", action="store_true", help="report the engine state; never run npm ci")
    args = ap.parse_args(argv)
    workdir = Path(args.workdir)
    if args.requirements and not Path(args.requirements).is_file():
        print(f"ERROR: {args.requirements} not found", file=sys.stderr)
        return 2
    workdir.mkdir(parents=True, exist_ok=True)
    engine = install_engine(not args.no_install)
    venv, venv_error = None, None
    if args.requirements:
        vpy, venv_error = ensure_venv(workdir / "gate-run", Path(args.requirements).read_text(encoding="utf-8"),
                                      args.pythons.split(","))
        if vpy is not None and not venv_error:
            venv = venv_report(vpy)
    path = write_env(workdir, engine, venv, venv_error)
    ready = engine[0] and not venv_error
    print(f"wrote {path}: engine {'ready' if engine[0] else 'MISSING'}"
          + (f", venv {'ready' if venv else 'NOT BUILT'}" if args.requirements else ""))
    if not engine[0]:
        print(f"  {engine[1]}")
    if venv_error:
        print(f"  {venv_error}")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
