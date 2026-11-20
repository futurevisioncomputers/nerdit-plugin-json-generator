"""Claude Code hooks for NERDIT content work. Stdlib only; every handler fails open.

  python -I nerdit_hooks.py subagent-gate   SubagentStop: re-run a lesson writer's GATE; block while it fails
  python -I nerdit_hooks.py pre-shell       PreToolUse (Bash|PowerShell): handover files, stale deploys,
                                            pilot-first for social packs and story videos
  python -I nerdit_hooks.py stop-pack       Stop: check every social pack this session changed

The hook input arrives as JSON on stdin; a decision, if any, goes to stdout as JSON.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

MAX_GATE_ROUNDS = 2          # extra fix rounds the hook may force on one writer
GATE_TIMEOUT = 540           # seconds; the hook entry allows 600
CHECK_TIMEOUT = 170          # seconds; the hook entry allows 180
OUT_LIMIT = 3500             # characters of tool output passed back to Claude
WRITER = "nerdit-lesson-writer"
SEPS = {"&&", "||", ";", "|", "&"}


# ---------- small helpers ----------

def _split(cmd: str) -> list[str]:
    """Split a command on whitespace and quotes, keeping Windows backslashes as they are."""
    lex = shlex.shlex(cmd, posix=True)
    lex.whitespace_split = True
    lex.escape = ""
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:                       # unbalanced quote
        return cmd.split()


def _tail(text: str) -> str:
    text = (text or "").strip()
    return text if len(text) <= OUT_LIMIT else "...\n" + text[-OUT_LIMIT:]


def _unresolved(s: str) -> bool:
    return "$" in s or "%" in s


def _resolve(base: Path, raw: str) -> Path:
    p = Path(raw.strip("\"'")).expanduser()
    return p if p.is_absolute() else base / p


def _state_file(state_dir: Path | None, kind: str, key: str) -> Path:
    d = Path(state_dir) if state_dir else Path(tempfile.gettempdir()) / "nerdit-hooks"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{kind}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]}"


def _rows(transcript: Path):
    try:
        with open(transcript, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def _tool_uses(row: dict):
    content = (row.get("message") or {}).get("content")
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                yield b


def newest(root: Path, tests: bool = True, skip: set[str] = frozenset()) -> float:
    """Newest file mtime under root (0 when missing). tests=False ignores *.test.* / *.spec.* files."""
    skip_dirs = {"node_modules", ".git", "__pycache__", ".vite", ".cache"} | set(skip)
    if not tests:
        skip_dirs |= {"__tests__", "__mocks__"}
    best = 0.0
    if not Path(root).exists():
        return best
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for f in filenames:
            if not tests and re.search(r"\.(test|spec)\.[cm]?[jt]sx?$", f):
                continue
            try:
                best = max(best, os.stat(os.path.join(dirpath, f)).st_mtime)
            except OSError:
                pass
    return best


# ---------- SubagentStop: the lesson writer's GATE ----------

GATE_RE = re.compile(r"^\s*GATE:\s*(.+?)\s*$", re.M)
TXT_RE = re.compile(r"(?:[A-Za-z]:[\\/]|/)[^\s\"'|<>*?]+\.txt")


def find_gate_command(text: str) -> str | None:
    """The `GATE: <command>` line from the writer's prompt, or from a prompt file it names."""
    m = GATE_RE.search(text)
    if m and "gate_lesson.py" in m.group(1):
        return m.group(1)
    for p in TXT_RE.findall(text):
        try:
            body = Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = GATE_RE.search(body)
        if m and "gate_lesson.py" in m.group(1):
            return m.group(1)
    return None


def gate_argv(cmd: str) -> list[str] | None:
    """argv for the GATE, or None unless it is exactly `python ... gate_lesson.py ...` with no chaining."""
    argv = _split(cmd)
    if not argv or Path(argv[0]).name.lower() not in {"python", "python3", "python.exe", "python3.exe", "py", "py.exe"}:
        return None
    if any(a in SEPS or a.startswith((">", "<")) for a in argv):
        return None
    if not any(Path(a).name == "gate_lesson.py" for a in argv[1:]):
        return None
    return argv


def lesson_id(argv: list[str]) -> str | None:
    for i, a in enumerate(argv[:-1]):
        if a == "--id":
            return argv[i + 1]
    return None


def _subagent_transcript(data: dict) -> Path | None:
    if data.get("agent_transcript_path"):
        return Path(data["agent_transcript_path"])
    aid, main = str(data.get("agent_id") or ""), data.get("transcript_path")
    if not (aid and main):
        return None
    name = aid if aid.startswith("agent-") else f"agent-{aid}"
    return Path(main).with_suffix("") / "subagents" / f"{name}.jsonl"


def _agent_type(data: dict, sub: Path | None) -> str | None:
    t = data.get("agent_type") or data.get("subagent_type")
    if t:
        return str(t)
    if sub:
        try:
            return json.loads(sub.with_name(sub.stem + ".meta.json").read_text(encoding="utf-8")).get("agentType")
        except (OSError, ValueError):
            pass
    return None


def first_user_text(transcript: Path) -> str:
    for row in _rows(transcript):
        if row.get("type") != "user":
            continue
        content = (row.get("message") or {}).get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
        return ""
    return ""


def handle_subagent_stop(data: dict, run=subprocess.run, state_dir: Path | None = None) -> dict | None:
    sub = _subagent_transcript(data)
    kind = _agent_type(data, sub)
    if kind and WRITER not in kind:
        return None
    cmd = find_gate_command(first_user_text(sub)) if sub else None
    argv = gate_argv(cmd) if cmd else None
    if not argv:
        return None
    lid = lesson_id(argv) or "the lesson"
    state = _state_file(state_dir, "gate", f"{data.get('session_id', '')}|{data.get('agent_id') or lid}")
    try:
        res = run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                  timeout=GATE_TIMEOUT, cwd=data.get("cwd") or None,
                  env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except subprocess.TimeoutExpired:
        return {"systemMessage": f"nerdit gate hook: the GATE for {lid} ran past {GATE_TIMEOUT}s; run it by hand."}
    except OSError as e:
        return {"systemMessage": f"nerdit gate hook: could not run the GATE for {lid}: {e}"}
    out = _tail((res.stdout or "") + "\n" + (res.stderr or ""))
    if res.returncode == 0:
        state.unlink(missing_ok=True)
        return None
    if res.returncode != 1:
        return {"systemMessage": f"nerdit gate hook: could not run the GATE for {lid} (exit {res.returncode}):\n{out}"}
    try:
        rounds = int(state.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        rounds = 0
    if rounds >= MAX_GATE_ROUNDS:
        state.unlink(missing_ok=True)
        return {"systemMessage": f"nerdit gate hook: {lid} still fails the GATE after {rounds} extra rounds; "
                                 f"the writer has stopped. Fix the listed lines by hand:\n{out}"}
    state.write_text(str(rounds + 1), encoding="utf-8")
    return {"decision": "block",
            "reason": f"The GATE still fails for {lid} (hook round {rounds + 1} of {MAX_GATE_ROUNDS}). "
                      "Fix each failure below with Edit, one edit per fix; do not rewrite the lesson. "
                      "Then run the GATE command from your prompt again, and stop only when it prints PASS.\n\n"
                      + out}


# ---------- PreToolUse (Bash | PowerShell) ----------

DELETE_RE = re.compile(r"(?:^|[\s(])(?:rm|rmdir|del|erase|unlink|shred|Remove-Item)(?=\s)"
                       r"|os\.remove|os\.unlink|shutil\.rmtree|\.unlink\(", re.I)
SECRET_RE = re.compile(r"token|secret|credential|service[-_]?account|api[-_]?key|private[-_]?key"
                       r"|\.pem\b|\.p12\b|\.pfx\b|\.key\b|(?:^|[\s/\\\"'])\.env\b", re.I)


def key_file_delete(cmd: str) -> str | None:
    for seg in re.split(r"&&|\|\||[;|\n]", cmd):
        if DELETE_RE.search(seg) and SECRET_RE.search(seg):
            return ("this deletes a token / key / credential file. Files handed to the owner are never "
                    "deleted (rule: no-deleting-handover-files). Leave it and tell the owner they can delete it.")
    return None


DEPLOY_RE = re.compile(r"\bfirebase(?:\.cmd)?\s+deploy\b")


def deploy_problem(cmd: str, root: Path, cwd: Path) -> str | None:
    """Why a `firebase deploy` would ship stale code, or None."""
    if not DEPLOY_RE.search(cmd):
        return None
    m = re.search(r"--only[=\s]+(\"[^\"]+\"|'[^']+'|\S+)", cmd)
    parts = [p.strip() for p in m.group(1).strip("\"'").split(",")] if m else []
    if m and not any(p.startswith("hosting") for p in parts):
        return None                                  # functions / rules: build themselves, no shared bundle
    shared = root / "nerdit" / "shared"
    if not shared.is_dir():
        return None
    s_dist = newest(shared / "dist")
    if newest(shared / "src", tests=False) > s_dist:
        return ("nerdit/shared/src changed after nerdit/shared/dist was built, and the apps bundle dist. "
                "Run `npm run build` in nerdit/shared, then `npm run build` in the app, then deploy.")
    where = (cmd + " " + str(cwd)).replace("\\", "/")
    admin = "nerdit-admin" in where or any(p.startswith("hosting:admin") for p in parts)
    app, label = (root / "nerdit-admin", "nerdit-admin") if admin else \
                 (root / "nerdit" / "future-vision", "nerdit/future-vision")
    if not app.is_dir():
        return None
    a_dist = newest(app / "dist")
    if a_dist == 0:
        return f"{label}/dist is missing. Run `npm run build` in {label} first."
    if a_dist < s_dist:
        return (f"{label}/dist was built before nerdit/shared/dist, so it bundles old shared code. "
                f"Run `npm run build` in {label}, then deploy.")
    a_src = max(newest(app / "src", tests=False), newest(app / "public"))
    if a_src > a_dist:
        return f"{label} source changed after its last build. Run `npm run build` in {label}, then deploy."
    return None


PYTHONS = {"python", "python3", "py", "python.exe", "python3.exe", "py.exe"}


def _script_calls(cmd: str, cwd: Path, script: str):
    """(args after the script, folder it runs in) for each call of `script` by a Python interpreter in the
    same command segment, following plain `cd`. A script name in prose (a commit message, an echo) is not a call."""
    toks, base, i, python = _split(cmd), Path(cwd), 0, False
    while i < len(toks):
        t = toks[i]
        if t in SEPS:
            python = False
            i += 1
            continue
        if Path(t).name.lower() in PYTHONS:
            python = True
        if t.lower() in {"cd", "pushd", "set-location", "sl"} and i + 1 < len(toks):
            if not _unresolved(toks[i + 1]):
                base = _resolve(base, toks[i + 1])
            i += 2
            continue
        if python and Path(t).name == script:
            j = i + 1
            while j < len(toks) and toks[j] not in SEPS:
                j += 1
            yield toks[i + 1:j], base
            i = j
            continue
        i += 1


def _opt(args: list[str], name: str) -> str | None:
    for i, a in enumerate(args):
        if a == name and i + 1 < len(args):
            return args[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return None


def pack_build_problem(cmd: str, cwd: Path) -> str | None:
    """`build_pack.py build <packdir>` needs <packdir>/pilot/OWNER_OK (pilot first)."""
    for args, base in _script_calls(cmd, cwd, "build_pack.py"):
        if len(args) < 2 or args[0] != "build":
            continue
        if _unresolved(args[1]):
            return ("pilot first: write the pack folder as a literal path in `build_pack.py build <packdir>` "
                    "so the hook can see the owner's pilot OK.")
        pack = _resolve(base, args[1])
        if not (pack / "pilot" / "OWNER_OK").is_file():
            return (f"pilot first: {pack} has no pilot/OWNER_OK. Run `build_pack.py pilot <packdir>`, show the "
                    "owner the pilot Reel, its cover and the slides, and after their OK write pilot/OWNER_OK "
                    "(date and the owner's words). Then build.")
    return None


VIDEO_PILOT_FLAGS = {"--stills", "--only", "--thumbnail-only", "--list-voices", "-h", "--help"}


def video_full_run_problem(cmd: str, cwd: Path) -> str | None:
    """A full `voice.py` / `build_video.py` run needs <images>/video/pilot/OWNER_OK (pilot first)."""
    for script in ("build_video.py", "voice.py"):
        for args, base in _script_calls(cmd, cwd, script):
            if any(a.split("=", 1)[0] in VIDEO_PILOT_FLAGS for a in args):
                continue
            imgs = _opt(args, "--images-dir")
            if imgs is None:
                continue
            if _unresolved(imgs):
                return f"pilot first: write --images-dir as a literal path for {script} so the hook can see the owner's pilot OK."
            ok = _resolve(base, imgs) / "video" / "pilot" / "OWNER_OK"
            if not ok.is_file():
                return (f"pilot first: {script} without --only is the full paid run, and {ok} is missing. "
                        "Do the stills (`build_video.py --stills`), then the pilot topic (`voice.py --only L:T` and "
                        "`build_video.py --only L:T`), show the owner the clip, and after their OK write "
                        "video/pilot/OWNER_OK (date and the owner's words).")
    return None


def find_root(start: Path) -> Path:
    for p in (start, *start.parents):
        if (p / "nerdit" / "shared").is_dir():
            return p
    return start


def handle_pre_shell(data: dict, root: Path | None = None) -> dict | None:
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not isinstance(cmd, str) or not cmd.strip():
        return None
    cwd = Path(data.get("cwd") or os.getcwd())
    root = root or find_root(Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd))
    checks = (lambda: key_file_delete(cmd), lambda: deploy_problem(cmd, root, cwd),
              lambda: pack_build_problem(cmd, cwd), lambda: video_full_run_problem(cmd, cwd))
    for check in checks:
        problem = check()
        if problem:
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": "nerdit hook: " + problem}}
    return None


# ---------- Stop: social packs changed this session ----------

PACK_RE = re.compile(r"social-pack[\\/]+[^\\/\s\"'`|<>*?]+")
CHANGING_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "PowerShell"}


def pack_dirs_from_transcript(transcript: Path, cwd: Path) -> set[Path]:
    found: set[Path] = set()
    for row in _rows(transcript):
        for b in _tool_uses(row):
            if b.get("name") not in CHANGING_TOOLS:
                continue
            inp = b.get("input") or {}
            for key in ("file_path", "notebook_path", "command"):
                v = inp.get(key)
                if not isinstance(v, str):
                    continue
                for tok in re.split(r"[\s\"'`]+", v):
                    m = PACK_RE.search(tok)
                    if not m or _unresolved(tok[:m.end()]):
                        continue
                    pack = _resolve(cwd, tok[:m.end()]).resolve()
                    if (pack / "pack-plan.json").is_file() or (pack / "pack.json").is_file():
                        found.add(pack)
    return found


def session_start(transcript: Path) -> float:
    for row in _rows(transcript):
        ts = row.get("timestamp")
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass
    try:
        return transcript.stat().st_ctime
    except OSError:
        return time.time()


def handle_stop(data: dict, run=subprocess.run, state_dir: Path | None = None,
                script: Path | None = None) -> dict | None:
    if data.get("stop_hook_active") or not data.get("transcript_path"):
        return None
    transcript, cwd = Path(data["transcript_path"]), Path(data.get("cwd") or os.getcwd())
    script = script or Path(__file__).resolve().parents[1] / "skills" / "nerdit-social-posts" / "scripts" / "build_pack.py"
    start, problems = session_start(transcript), []
    for pack in sorted(pack_dirs_from_transcript(transcript, cwd)):
        if not (pack / "pack.json").is_file():
            continue                                  # plan or pilot only: the pilot checks itself
        changed = newest(pack, skip={"pilot"})
        stamp = _state_file(state_dir, "packcheck", str(pack).lower())
        if changed <= max(start, stamp.stat().st_mtime if stamp.exists() else 0.0):
            continue
        try:
            res = run([sys.executable, str(script), "check", str(pack)], capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=CHECK_TIMEOUT,
                      env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except (subprocess.TimeoutExpired, OSError):
            continue
        if res.returncode == 0:
            stamp.write_text(str(pack), encoding="utf-8")
            t = max(time.time(), changed)
            os.utime(stamp, (t, t))
        else:
            problems.append(f"{pack}:\n{_tail((res.stdout or '') + chr(10) + (res.stderr or ''))}")
    if not problems:
        return None
    return {"decision": "block",
            "reason": "The social pack check fails after this session's changes. Fix every PROBLEM "
                      "(in pack-plan.json, then `build_pack.py build` when drawn items changed), run "
                      "`build_pack.py check <packdir>` until it passes, then finish.\n\n" + "\n\n".join(problems)}


# ---------- entry point ----------

HANDLERS = {"subagent-gate": handle_subagent_stop, "pre-shell": handle_pre_shell, "stop-pack": handle_stop}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out = None
    try:
        data = json.loads(sys.stdin.read() or "{}")
        handler = HANDLERS.get(argv[0] if argv else "")
        if handler and isinstance(data, dict):
            out = handler(data)
    except Exception as e:                            # a hook must never break the session
        try:
            log = _state_file(None, "errors", "log").with_suffix(".log")
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now().isoformat()} {argv} {type(e).__name__}: {e}\n")
        except OSError:
            pass
        out = None
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
