"""Tests for nerdit_hooks.py: the SubagentStop gate, the PreToolUse guards and the Stop pack check."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import nerdit_hooks as nh  # noqa: E402

GATE = (r'GATE: python -s "D:\x\nerdit-plugin-json-generator\skills\nerdit-chapter-generator\scripts\gate_lesson.py"'
        r' --input "D:\x\course-a_input.json" --dir "D:\x\work" --id flask-routes-03 --new-course --video')


def _jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def _user(text: str, ts: str = "2026-11-20T06:00:00.000Z") -> dict:
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}}


def _tool(name: str, **inp) -> dict:
    return {"type": "assistant", "timestamp": "2026-11-20T06:01:00.000Z",
            "message": {"role": "assistant", "content": [{"type": "tool_use", "name": name, "input": inp}]}}


def _touch(path: Path, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("x", encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


# ---------- GATE command discovery ----------

def test_gate_line_found_inline():
    cmd = nh.find_gate_command("do the lesson\n" + GATE + "\nthanks")
    assert cmd is not None and cmd.startswith("python -s") and "gate_lesson.py" in cmd


def test_gate_line_found_in_prompt_file(tmp_path):
    prompt = tmp_path / "_prompt-flask-routes-03.txt"
    prompt.write_text("Inputs...\n" + GATE + "\nPython: use python -s\n", encoding="utf-8")
    text = f"Your task inputs are in this file - read it in full first:\n\n{prompt}\n\nNotes"
    assert "flask-routes-03" in nh.find_gate_command(text)


def test_no_gate_line_returns_none(tmp_path):
    assert nh.find_gate_command("write a poem; see C:\\nowhere\\x.txt") is None


def test_gate_argv_keeps_windows_backslashes():
    argv = nh.gate_argv(GATE.split("GATE:", 1)[1].strip())
    assert argv[0] == "python"
    assert argv[2].endswith(r"scripts\gate_lesson.py")
    assert r"D:\x\work" in argv
    assert nh.lesson_id(argv) == "flask-routes-03"


@pytest.mark.parametrize("cmd", [
    'rm -rf "D:\\x"',                                        # not python
    'python -c "import os; os.remove(1)"',                   # python, but not the gate
    'python D:\\evil\\gate_lesson.py.bak --id x',            # look-alike name
])
def test_gate_argv_refuses_anything_but_the_gate(cmd):
    assert nh.gate_argv(cmd) is None


# ---------- SubagentStop ----------

def _writer_session(tmp_path: Path, prompt_text: str, agent_type="nerdit_content_creator:nerdit-lesson-writer"):
    main = tmp_path / "proj" / "sess1.jsonl"
    _jsonl(main, [_user("hi")])
    sub = tmp_path / "proj" / "sess1" / "subagents" / "agent-abc123.jsonl"
    _jsonl(sub, [_user(prompt_text), _tool("Write", file_path="D:\\x\\work\\flask-routes-03.html", content="<p>")])
    sub.with_name("agent-abc123.meta.json").write_text(json.dumps({"agentType": agent_type}), encoding="utf-8")
    return {"hook_event_name": "SubagentStop", "session_id": "sess1", "transcript_path": str(main),
            "agent_id": "abc123", "stop_hook_active": False, "cwd": str(tmp_path)}


class FakeRun:
    def __init__(self, rc: int, out: str = ""):
        self.rc, self.out, self.calls = rc, out, []

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, self.rc, self.out, "")


def test_subagent_gate_blocks_on_failure(tmp_path):
    data = _writer_session(tmp_path, GATE)
    run = FakeRun(1, "FAIL  flask-routes-03: 2 failure(s), 0 warning(s)\n  - quiz: option repeats\n")
    out = nh.handle_subagent_stop(data, run=run, state_dir=tmp_path / "state")
    assert out["decision"] == "block"
    assert "quiz: option repeats" in out["reason"] and "flask-routes-03" in out["reason"]
    assert run.calls[0][0] == "python"


def test_subagent_gate_silent_on_pass(tmp_path):
    data = _writer_session(tmp_path, GATE)
    assert nh.handle_subagent_stop(data, run=FakeRun(0, "PASS"), state_dir=tmp_path / "state") is None


def test_subagent_gate_stops_blocking_after_max_rounds(tmp_path):
    data = _writer_session(tmp_path, GATE)
    state = tmp_path / "state"
    results = [nh.handle_subagent_stop(data, run=FakeRun(1, "FAIL x"), state_dir=state)
               for _ in range(nh.MAX_GATE_ROUNDS + 1)]
    assert all(r["decision"] == "block" for r in results[:nh.MAX_GATE_ROUNDS])
    last = results[-1]
    assert "decision" not in last and "still fails" in last["systemMessage"]


def test_subagent_gate_ignores_other_agents(tmp_path):
    data = _writer_session(tmp_path, GATE, agent_type="general-purpose")
    run = FakeRun(1, "FAIL")
    assert nh.handle_subagent_stop(data, run=run, state_dir=tmp_path / "state") is None
    assert run.calls == []


def test_subagent_gate_uses_agent_type_from_input(tmp_path):
    data = _writer_session(tmp_path, GATE, agent_type="general-purpose")
    data["agent_type"] = "nerdit_content_creator:nerdit-lesson-writer"
    out = nh.handle_subagent_stop(data, run=FakeRun(1, "FAIL y"), state_dir=tmp_path / "state")
    assert out["decision"] == "block"


def test_subagent_gate_tool_error_does_not_block(tmp_path):
    data = _writer_session(tmp_path, GATE)
    out = nh.handle_subagent_stop(data, run=FakeRun(2, "ERROR: no such file"), state_dir=tmp_path / "state")
    assert "decision" not in out and "could not run" in out["systemMessage"]


def test_subagent_without_gate_line_is_left_alone(tmp_path):
    data = _writer_session(tmp_path, "write lesson 3 please")
    run = FakeRun(1)
    assert nh.handle_subagent_stop(data, run=run, state_dir=tmp_path / "state") is None
    assert run.calls == []


# ---------- PreToolUse: handover files ----------

@pytest.mark.parametrize("cmd", [
    "rm scratch/linkedin-token.txt",
    "rm -f C:/Users/x/service-account.json",
    'Remove-Item "D:\\keys\\api-key.txt" -Force',
    "del .env",
    "cd x && rm client_secret.json",
])
def test_deleting_handover_files_is_denied(cmd):
    assert nh.key_file_delete(cmd) is not None


@pytest.mark.parametrize("cmd", [
    "rm -rf node_modules",
    "cat linkedin-token.txt",
    "python tokenize_chart_svg.py --in a.svg",
    "git rm --cached build.log",
])
def test_other_commands_pass_the_handover_guard(cmd):
    assert nh.key_file_delete(cmd) is None


# ---------- PreToolUse: deploy freshness ----------

def _repo(tmp_path: Path, shared_src: float, shared_dist: float, site_src: float, site_dist: float,
          admin_src: float = 100, admin_dist: float = 900) -> Path:
    root = tmp_path / "ws"
    _touch(root / "nerdit/shared/src/index.ts", shared_src)
    _touch(root / "nerdit/shared/src/index.test.ts", 9999)          # tests never count
    _touch(root / "nerdit/shared/dist/index.js", shared_dist)
    _touch(root / "nerdit/future-vision/src/main.tsx", site_src)
    _touch(root / "nerdit/future-vision/dist/assets/app.js", site_dist)
    _touch(root / "nerdit-admin/src/main.tsx", admin_src)
    _touch(root / "nerdit-admin/dist/assets/admin.js", admin_dist)
    return root


def test_deploy_allowed_when_everything_is_built_in_order(tmp_path):
    root = _repo(tmp_path, shared_src=100, shared_dist=200, site_src=150, site_dist=300)
    assert nh.deploy_problem("npx firebase deploy --only hosting:public", root, root / "nerdit") is None


def test_deploy_denied_when_shared_src_is_newer_than_its_dist(tmp_path):
    root = _repo(tmp_path, shared_src=500, shared_dist=200, site_src=150, site_dist=600)
    msg = nh.deploy_problem("npx firebase deploy --only hosting:public", root, root / "nerdit")
    assert "nerdit/shared" in msg and "npm run build" in msg


def test_deploy_denied_when_site_was_built_before_shared(tmp_path):
    root = _repo(tmp_path, shared_src=100, shared_dist=400, site_src=150, site_dist=300)
    assert "future-vision" in nh.deploy_problem("firebase deploy", root, root / "nerdit")


def test_deploy_denied_when_site_src_changed_after_build(tmp_path):
    root = _repo(tmp_path, shared_src=100, shared_dist=200, site_src=700, site_dist=300)
    assert "future-vision" in nh.deploy_problem("npx firebase deploy --only hosting:public", root, root / "nerdit")


def test_admin_deploy_checks_the_admin_build(tmp_path):
    root = _repo(tmp_path, shared_src=100, shared_dist=200, site_src=150, site_dist=300,
                 admin_src=800, admin_dist=250)
    msg = nh.deploy_problem("cd nerdit-admin && npx firebase deploy --only hosting:admin", root, root)
    assert "nerdit-admin" in msg


def test_functions_only_deploy_skips_app_checks(tmp_path):
    root = _repo(tmp_path, shared_src=500, shared_dist=200, site_src=700, site_dist=300)
    assert nh.deploy_problem("npx firebase deploy --only functions:articleAction", root, root / "nerdit") is None


def test_non_deploy_commands_are_ignored(tmp_path):
    root = _repo(tmp_path, shared_src=500, shared_dist=200, site_src=700, site_dist=300)
    assert nh.deploy_problem("npm run build", root, root / "nerdit") is None


# ---------- PreToolUse: pilot first ----------

def test_pack_build_denied_without_owner_ok(tmp_path):
    pack = tmp_path / "work/social-pack/p1"
    (pack / "pilot").mkdir(parents=True)
    cmd = f'python -s "{tmp_path}/scripts/build_pack.py" build "{pack}"'
    assert "OWNER_OK" in nh.pack_build_problem(cmd, tmp_path)


def test_pack_build_allowed_with_owner_ok(tmp_path):
    pack = tmp_path / "work/social-pack/p1"
    _touch(pack / "pilot/OWNER_OK", 100)
    assert nh.pack_build_problem("python build_pack.py build work/social-pack/p1", tmp_path) is None


def test_pack_build_follows_cd(tmp_path):
    _touch(tmp_path / "course/work/social-pack/p1/pilot/OWNER_OK", 100)
    cmd = "cd course && python ../build_pack.py build work/social-pack/p1"
    assert nh.pack_build_problem(cmd, tmp_path) is None


@pytest.mark.parametrize("sub", ["pilot", "check", "plan"])
def test_pack_pilot_check_and_plan_always_allowed(tmp_path, sub):
    assert nh.pack_build_problem(f"python build_pack.py {sub} work/social-pack/p1", tmp_path) is None


def test_script_names_in_prose_are_not_calls(tmp_path):
    msg = ("git commit -q -F - <<'EOF'\nrefuse build_pack.py build without pilot/OWNER_OK and a full "
           "voice.py --images-dir imgs run\nEOF")
    assert nh.pack_build_problem(msg, tmp_path) is None
    assert nh.video_full_run_problem(msg, tmp_path) is None
    assert nh.pack_build_problem("echo build_pack.py build x && python build_pack.py pilot x", tmp_path) is None


def test_python_flags_before_the_script_still_count(tmp_path):
    assert nh.pack_build_problem('python -s -X utf8 "scripts/build_pack.py" build work/p1', tmp_path) is not None
    assert nh.pack_build_problem('py -3 build_pack.py build work/p1', tmp_path) is not None


def test_pack_build_with_unresolved_variable_is_denied(tmp_path):
    msg = nh.pack_build_problem('python build_pack.py build "$PACK"', tmp_path)
    assert msg is not None and "literal" in msg


def test_full_video_build_denied_without_owner_ok(tmp_path):
    (tmp_path / "imgs/video/pilot").mkdir(parents=True)
    assert "OWNER_OK" in nh.video_full_run_problem("python build_video.py --images-dir imgs", tmp_path)


def test_full_voice_run_denied_without_owner_ok(tmp_path):
    assert "OWNER_OK" in nh.video_full_run_problem("python voice.py --images-dir imgs", tmp_path)


def test_full_video_build_allowed_with_owner_ok(tmp_path):
    _touch(tmp_path / "imgs/video/pilot/OWNER_OK", 100)
    assert nh.video_full_run_problem("python build_video.py --images-dir imgs --workers 3", tmp_path) is None


@pytest.mark.parametrize("flags", ["--stills", "--only L03:2", "--thumbnail-only", "--only L03"])
def test_video_pilot_steps_always_allowed(tmp_path, flags):
    assert nh.video_full_run_problem(f"python build_video.py --images-dir imgs {flags}", tmp_path) is None
    assert nh.video_full_run_problem(f"python voice.py --images-dir imgs {flags}", tmp_path) is None


def test_pre_shell_returns_deny_json(tmp_path):
    out = nh.handle_pre_shell({"tool_name": "Bash", "cwd": str(tmp_path),
                               "tool_input": {"command": "rm my-token.txt"}}, root=tmp_path)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse" and hso["permissionDecision"] == "deny"


def test_pre_shell_allows_plain_commands(tmp_path):
    assert nh.handle_pre_shell({"tool_name": "Bash", "cwd": str(tmp_path),
                                "tool_input": {"command": "ls -la"}}, root=tmp_path) is None


# ---------- Stop: pack check ----------

def _pack(tmp_path: Path, name="p1", mtime=2_000_000_000.0) -> Path:
    pack = tmp_path / "course/work/social-pack" / name
    _touch(pack / "pack.json", mtime)
    _touch(pack / "pack-plan.json", mtime)
    return pack


def _stop_session(tmp_path: Path, tools: list[dict], start="2026-11-20T06:00:00.000Z") -> dict:
    main = _jsonl(tmp_path / "proj" / "s.jsonl", [_user("go", ts=start)] + tools)
    return {"hook_event_name": "Stop", "transcript_path": str(main), "stop_hook_active": False,
            "cwd": str(tmp_path)}


def test_pack_dirs_found_from_edits_and_commands(tmp_path):
    p1, p2 = _pack(tmp_path, "p1"), _pack(tmp_path, "p2")
    data = _stop_session(tmp_path, [
        _tool("Edit", file_path=str(p1 / "pack-plan.json"), old_string="a", new_string="b"),
        _tool("Bash", command=f'python fix.py "{p2}"'),
        _tool("Read", file_path=str(tmp_path / "course/work/social-pack/p3/pack.json")),
    ])
    assert nh.pack_dirs_from_transcript(Path(data["transcript_path"]), tmp_path) == {p1.resolve(), p2.resolve()}


def test_stop_blocks_when_changed_pack_fails_check(tmp_path):
    pack = _pack(tmp_path)
    data = _stop_session(tmp_path, [_tool("Edit", file_path=str(pack / "pack-plan.json"))])
    run = FakeRun(1, "PROBLEM d04: caption too long")
    out = nh.handle_stop(data, run=run, state_dir=tmp_path / "state", script=tmp_path / "build_pack.py")
    assert out["decision"] == "block" and "caption too long" in out["reason"]
    assert run.calls[0][-2:] == ["check", str(pack.resolve())]


def test_stop_passes_and_remembers_clean_pack(tmp_path):
    pack = _pack(tmp_path)
    data = _stop_session(tmp_path, [_tool("Edit", file_path=str(pack / "pack-plan.json"))])
    state = tmp_path / "state"
    run = FakeRun(0, "OK")
    assert nh.handle_stop(data, run=run, state_dir=state, script=tmp_path / "b.py") is None
    assert nh.handle_stop(data, run=run, state_dir=state, script=tmp_path / "b.py") is None
    assert len(run.calls) == 1                                    # unchanged since the last pass


def test_stop_skips_pack_untouched_this_session(tmp_path):
    pack = _pack(tmp_path, mtime=1_000_000_000.0)                 # 2001: before the session began
    data = _stop_session(tmp_path, [_tool("Bash", command=f"ls {pack}")])
    run = FakeRun(1, "PROBLEM")
    assert nh.handle_stop(data, run=run, state_dir=tmp_path / "state", script=tmp_path / "b.py") is None
    assert run.calls == []


def test_stop_skips_pilot_only_pack(tmp_path):
    pack = tmp_path / "course/work/social-pack/p1"
    _touch(pack / "pack-plan.json", 2_000_000_000.0)              # no pack.json: pilot checks itself
    data = _stop_session(tmp_path, [_tool("Edit", file_path=str(pack / "pack-plan.json"))])
    run = FakeRun(1)
    assert nh.handle_stop(data, run=run, state_dir=tmp_path / "state", script=tmp_path / "b.py") is None
    assert run.calls == []


def test_stop_never_blocks_twice_in_a_row(tmp_path):
    pack = _pack(tmp_path)
    data = _stop_session(tmp_path, [_tool("Edit", file_path=str(pack / "pack-plan.json"))])
    data["stop_hook_active"] = True
    assert nh.handle_stop(data, run=FakeRun(1, "PROBLEM"), state_dir=tmp_path / "state",
                          script=tmp_path / "b.py") is None


# ---------- main: never crash the session ----------

def test_main_fails_open_on_bad_input(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(nh.tempfile, "gettempdir", lambda: str(tmp_path))     # keep the error log out of %TEMP%
    monkeypatch.setattr(sys, "stdin", type("S", (), {"read": staticmethod(lambda: "not json")})())
    assert nh.main(["pre-shell"]) == 0
    assert capsys.readouterr().out == ""
