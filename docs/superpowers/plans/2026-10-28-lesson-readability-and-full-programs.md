# Lesson Readability and Full Programs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lessons use case studies only where they teach, mark scan words with `<b>`, and show complete runnable programs with a full line walk, each rule with its checker.

**Architecture:** A new program run line (`nerdit-run nerdit-program`) is parsed once in `check_python_outputs.python_parts` and consumed by the offline runner, `verify_course`, `check_code_prose` and `practice_files`. `check_case` and `check_prose` relax and add rules in place. Rule text lives in `CORE.md` and the writer agent; `rules_pack.py` cuts it per preset as today.

**Tech Stack:** Python 3.12+ stdlib scripts, pytest (run with `advanced-regression-course/work/venv314/Scripts/python -m pytest -p no:cacheprovider`; the user-site pytest is broken by a urllib3 plugin).

**Spec:** `docs/superpowers/specs/2026-10-28-lesson-readability-and-full-programs-design.md`

All paths below are relative to `skills/nerdit-chapter-generator/` unless they start with `agents/` or `docs/`.

## Global Constraints

- Stdlib only in every script (existing rule).
- Program: at most **80** lines, at most **2** per lesson, exempt from `BLOCK_LINES = 15` and `LESSON_LINES`.
- A program with a check snippet must contain `if __name__ == "__main__":`, must be `data-run="offline"`, and is imported, never run as `__main__`, by checkers.
- Scan highlights: `<b>` in prose; FAIL at **4+** in one paragraph, a highlight over **8** words, or over **20%** of a paragraph's words; WARN when fewer than half of a lesson's explanation paragraphs of **25+** words have one. `<b>` never counts as a key term (`MAX_NEW_TERMS = 3` stays for `<strong>`).
- Full walk: a walk step covers at most **8** code lines; every non-blank, non-comment program line is covered.
- Case study: optional per concept section; at most 1 per section; at least 1 per lesson; WARN when every concept section of a lesson with 3+ sections has one.
- Fake runtime outside a program WARNs: `test_request_context`, `MultiDict`, `"csrf": False` / `'csrf': False`.
- `render_template(` inside a lesson program WARNs (lesson programs are one file).
- New FAIL rules apply with `--new-course` or `--modes programs|readability`; delivered courses (Flask REST, Advanced Regression) must still pass `verify_course.py --contract v11` without those flags.
- After each task: copy changed files to the installed plugin cache `C:/Users/siddh/.claude/plugins/cache/fv-analysis-marketplace/nerdit_content_creator/3.9.0/` at the same relative path.

## Review Focus

- A program whose check snippet starts a server (`app.run()` called outside the guard) must time out as a clear failure, not hang the gate — test in Task 2.
- A program whose file name clashes with a dataset CSV or another lesson's program in the same chapter folder — hard FAIL, test in Task 5.
- `<b>` inside a code walk `<li>`, a table cell or a figure caption is not prose and is never counted — test in Task 7.
- A whole script that reads the lesson's dataset CSV must run beside that CSV in the pack — test in Task 5.
- A program walk whose `<code>` line differs only by indentation from the program line still counts as covering it (walk lines are compared squashed, as `check_code_prose._squash` does) — test in Task 4.

---

### Task 1: Parse program run lines

**Files:**
- Modify: `scripts/check_python_outputs.py` (`python_parts`, ~line 125)
- Test: `scripts/test_check_python_outputs.py`

**Interfaces:**
- Produces: each item of `python_parts(html)["runs"]` gains `"program": str | None` (the `data-file` value when the run line has class `nerdit-program`, else `None`) and `"check": str | None` (text of the run line's `<script type="text/plain" class="nerdit-check">`, else `None`).

Markup (also goes in CORE.md in Task 8):

```html
<div class="nerdit-run nerdit-program" data-run="offline" data-file="form_app.py">
  <div class="nerdit-in"><span class="nerdit-tag">You type</span>
    <pre data-lang="python"><code>…the whole file…</code></pre></div>
  <script type="text/plain" class="nerdit-check">client = app.test_client()
print(client.post("/", data={"name": ""}).status_code)</script>
  <div class="nerdit-out"><span class="nerdit-tag">Python shows</span><pre><code>200</code></pre></div>
</div>
```

- [ ] **Step 1: Write the failing test** `test_program_run_lines_carry_file_and_check`: a lesson with one plain run line and one program run line (markup above). Assert `runs[0]["program"] is None and runs[0]["check"] is None`; `runs[1]["program"] == "form_app.py"`; `runs[1]["check"].startswith("client = app.test_client()")`; `runs[1]["offline"] is True`.
- [ ] **Step 2: Run** `... -m pytest -q test_check_python_outputs.py -k program` — expect FAIL (KeyError `program`).
- [ ] **Step 3: Implement** in `python_parts`: read `node.attrs.get("data-file")` when `"nerdit-program" in node.classes`, and the first descendant `script` with `nerdit-check` in its classes.
- [ ] **Step 4: Run** the whole `test_check_python_outputs.py` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "Programs: python_parts reads data-file and the check snippet"`

### Task 2: Run programs as imported modules in the offline checker

**Files:**
- Modify: `scripts/check_offline_outputs.py` (`DRIVER`, `_run_lesson`)
- Test: `scripts/test_check_offline_outputs.py`

**Interfaces:**
- Consumes: Task 1 `runs[i]["program"]`, `runs[i]["check"]`.
- Produces: `_blocks.json` items become `{"code": str, "program": str | None, "check": str | None}`; the driver runs a program in a **fresh** scope `{"__name__": Path(program).stem}`, then its check in that same scope; the printed text of the check is the block's output. Plain blocks keep the shared notebook scope.

- [ ] **Step 1: Write failing tests**
  - `test_a_program_is_imported_and_its_check_prints_the_output`: program `def add(a, b):\n    return a + b\nif __name__ == "__main__":\n    print("server")` with check `print(add(2, 3))`, shown `5` → `report["problems"] == []`.
  - `test_a_program_guard_never_runs`: same program, shown `server\n5` → one problem naming the lesson.
  - `test_a_check_that_starts_a_server_times_out_clearly`: check `import time\ntime.sleep(10**6)`, with `co.TIMEOUT` monkeypatched to 3 → a problem containing `still running`.
- [ ] **Step 2: Run** `-k "program or server"` — expect FAIL.
- [ ] **Step 3: Implement** the driver branch; serialise the three keys in `_run_lesson`. Also write the program to `folder / program` before running, so a check that opens the file works.
- [ ] **Step 4: Run** all of `test_check_offline_outputs.py test_lesson_runs.py test_headless_env.py` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "Programs: offline checker imports the program and runs its check"`

### Task 3: verify_course program rules

**Files:**
- Modify: `scripts/verify_course.py` (`verify_density` ~line 533; new `verify_programs(rep, out, inp, new_course: bool)` called from `main` beside `verify_density`)
- Test: `scripts/test_verify_v11.py`

**Interfaces:**
- Consumes: Task 1 `python_parts`.
- Produces: `verify_programs(rep: Report, out: dict, inp: list, new_course: bool = False) -> None`; constants `PROGRAM_LINES = 80`, `PROGRAMS_PER_LESSON = 2`, `FAKE_RUNTIME = ("test_request_context", "MultiDict", '"csrf": False', "'csrf': False")`. `shown_code_blocks` excludes program blocks so `verify_density` no longer counts them.

- [ ] **Step 1: Write failing tests** (one each, `rep.check` = FAIL, `rep.warn` = WARN):
  - program without `data-file` → FAIL; 81-line program → FAIL; 3 programs → FAIL;
  - program with check but no `if __name__ == "__main__":` → FAIL; program with check and no `data-run="offline"` → FAIL;
  - 70-line program → no `code block … shows` warning (exempt);
  - `render_template(` in a program → WARN; `test_request_context` in a plain run line → WARN; same inside a program → no warning;
  - python lesson (focus hands-on) with 3 plain run lines whose code loads a name it never assigns or imports, and no program: FAIL with `new_course=True`, WARN with `False`. Reuse the audit rule: names loaded minus names imported, assigned, defined, bound as args or comprehension targets, minus builtins.
  - The delivered course outputs still pass: `verify_course.py --contract v11` on `advanced-regression-course/work/pack/course-advanced-regression-models_output.json` and `flask-course/work/pack/course-flask-rest-api_output.json` exits 0 (run as a step, not a unit test).
- [ ] **Step 2: Run** `test_verify_v11.py -k program` — expect FAIL.
- [ ] **Step 3: Implement** `verify_programs` and the `shown_code_blocks` exclusion; wire `args.new_course`.
- [ ] **Step 4: Run** `test_verify_v11.py test_verify_course.py`, then both delivered-course verifies — expect PASS / exit 0.
- [ ] **Step 5: Commit** `git commit -m "Programs: verify_course checks size, guard, offline and fake runtime"`

### Task 4: Full walk coverage

**Files:**
- Modify: `scripts/check_code_prose.py` (`check_lesson`; add `new_course: bool = False` parameter and `--new-course` CLI flag)
- Test: `scripts/test_check_code_prose.py`

**Interfaces:**
- Produces: `check_lesson(content: str, new_course: bool = False) -> tuple[list[str], list[str]]` (failures, warnings). A program must be followed (next sibling `ol`) by `<ol class="nerdit-codewalk nerdit-walk-full">`. Each `<li>`'s first `<code>` is a program line (compared with `_squash`); steps appear in program order; a step covers from its line to the line before the next step's line; the first step starts at the first code line; no step covers more than `WALK_STEP_LINES = 8` code lines (blank and `#`-comment lines do not count). A missing or partial walk is a failure when `new_course`, else a warning. Update `main` and the `gate_lesson.py` caller for the tuple.

- [ ] **Step 1: Write failing tests**
  - `test_a_program_needs_a_full_walk`: 10-line program, no walk → one failure with `new_course=True`, zero failures and one warning with `False`.
  - `test_walk_steps_cover_every_line_in_order`: steps at lines 1, 5, 9 of a 12-line program → no problems; steps at 1 and 10 (9 lines in step 1) → failure naming `8`.
  - `test_indentation_does_not_break_a_walk_match` (Review Focus): `<code>return a + b</code>` matches `    return a + b`.
  - Existing tests updated for the tuple return.
- [ ] **Step 2: Run** `test_check_code_prose.py` — expect FAIL.
- [ ] **Step 3: Implement**; update `gate_lesson.py` to pass `new_course or bool({"programs"} & modes)` and route warnings to its warning list.
- [ ] **Step 4: Run** `test_check_code_prose.py test_gate_lesson.py` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "Programs: every program line is walked, at most 8 lines a step"`

### Task 5: Programs and whole scripts in the practice pack

**Files:**
- Modify: `scripts/practice_files.py` (`page_examples`, `build_pack`, `mark_lesson`)
- Test: `scripts/test_practice_files.py`

**Interfaces:**
- Consumes: Task 1 `python_parts(...)["runs"][i]["program"]`.
- Produces: `program_files(html: str) -> list[tuple[str, str]]` returning `(data-file, code)` in page order. `build_pack` writes each into the chapter folder for **every** chapter that has one, even without a files spec, beside that chapter's dataset CSVs (built from the lesson's dataset block, as the lesson's files spec would). The manifest lists them with `"source": {"program": "<lesson id>"}`. `page_examples` skips program run lines, so the solutions file never runs a guard. `mark_lesson` lists program files in the chapter's files box (creating the box when the chapter has no spec).

- [ ] **Step 1: Write failing tests**
  - `test_programs_go_in_the_chapter_folder_without_a_spec`: a chapter with one program and no files spec → pack has `L01-<slug>/form_app.py` with the exact code.
  - `test_a_program_name_that_clashes_fails` (Review Focus): program `enquiries.csv`-named or two programs `app.py` in one chapter → `ValueError` naming both.
  - `test_a_whole_script_runs_beside_its_dataset` (Review Focus): program reading `pd.read_csv("enquiries.csv")` and a dataset block → pack folder holds both files.
  - `test_solutions_skip_programs`: `page_examples` returns only the plain run line.
- [ ] **Step 2: Run** `test_practice_files.py -k "program or script or solutions_skip"` — expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `test_practice_files.py test_check_files.py test_lesson_runs.py` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "Programs: every program ships as a file in its chapter folder"`

### Task 6: Case studies where they teach

**Files:**
- Modify: `scripts/check_case.py` (`case_problems`, docstring)
- Test: `scripts/test_check_case.py`

**Interfaces:**
- Produces: `case_problems(html: str, names: list[str], first: bool) -> tuple[list[str], list[str]]` (problems, warnings); update `main` and `gate_lesson.py` callers.

- [ ] **Step 1: Write failing tests**
  - a concept section without a case study → no problem;
  - a lesson with zero case studies → problem `the lesson has no case study`;
  - a lesson with 3 concept sections, each with a case study → one warning containing `keep the ones that add a decision or real numbers`;
  - unchanged: two case headings in one section → problem; a world name before the heading → problem; first-lesson card rule.
- [ ] **Step 2: Run** `test_check_case.py` — expect FAIL.
- [ ] **Step 3: Implement.** A section without a heading skips the "named before" check only when the section names no world name at all; if it names one with no heading, that is the existing "names X before its case study" problem.
- [ ] **Step 4: Run** `test_check_case.py test_gate_lesson.py`; `check_case.py` on both delivered courses exits 0.
- [ ] **Step 5: Commit** `git commit -m "Case studies: optional per section, at least one per lesson"`

### Task 7: Scan highlights

**Files:**
- Modify: `scripts/check_prose.py` (`check_lesson`; constants `MAX_HIGHLIGHTS = 3`, `MAX_HIGHLIGHT_WORDS = 8`, `MAX_HIGHLIGHT_SHARE = 0.20`, `HIGHLIGHT_MIN_WORDS = 25`)
- Modify: `references/css9-simple.css` (rule for `.nerdit-simple p b`)
- Modify: `references/voice.md` (fail/warn list at the top)
- Test: `scripts/test_check_prose.py`, `scripts/test_check_css_bundle.py` if it lists selectors

**Interfaces:**
- Produces: nothing new for other tasks; `_terms` keeps counting only `strong`.

- [ ] **Step 1: Write failing tests**
  - 4 `<b>` in one `<p>` → failure mentioning `3`; a 9-word `<b>` → failure; `<b>` covering 6 of 25 words → failure (`20%`);
  - a lesson with four 30-word paragraphs and one highlight → warning `highlights`; with two highlighted → no warning;
  - `<b>` inside `ol.nerdit-codewalk li`, a `td`, or a `figcaption` is not counted (Review Focus);
  - 3 `<strong>` plus 3 `<b>` in a section → no key-term failure.
- [ ] **Step 2: Run** `test_check_prose.py` — expect FAIL.
- [ ] **Step 3: Implement**; CSS: `.nerdit-simple p b { font-weight: 700; color: var(--nerdit-ink-strong, inherit); }` — use the existing token css9 uses for emphasis if one exists (grep `--` tokens in css9-simple.css), so key terms in `<strong>` stay visually distinct.
- [ ] **Step 4: Run** `test_check_prose.py test_check_css_bundle.py`; `check_prose.py` on both delivered courses exits 0.
- [ ] **Step 5: Commit** `git commit -m "Prose: <b> scan highlights with caps, separate from key terms"`

### Task 8: Rules text, writer agent, refresh modes, sync

**Files:**
- Modify: `references/CORE.md` (§2 case study rule; §4 run lines: program component, when to use, caps, whole script for data lessons, full walk; §10 voice: `<b>` highlights vs `<strong>` terms; the code walk skeleton line ~86 "2–4 steps" becomes "2–4 steps; a program's walk covers every line")
- Modify: `references/runners/python.md` (program markup, check snippet, offline, one-file rule)
- Modify: `agents/nerdit-lesson-writer.md` (refresh modes `programs`, `readability`; the program and highlight checklist)
- Modify: `scripts/check_refresh.py` (`MODES` adds `programs`, `readability`; `readability` allows prose changes like `concise`; `programs` allows added program run lines, their walks and check snippets, and nothing else in code or outputs)
- Modify: `scripts/gate_lesson.py` docstring/`--modes` help
- Test: `scripts/test_check_refresh.py`, `scripts/test_rules_pack.py`, `scripts/test_docs_refs.py`

- [ ] **Step 1: Write failing tests** in `test_check_refresh.py`: `programs` mode — adding a program run line passes, changing an existing run line's code fails; `readability` mode — adding `<b>` and removing a case study heading's prose passes, changing code fails.
- [ ] **Step 2: Run** — expect FAIL.
- [ ] **Step 3: Implement** `check_refresh.py`; write the rule text (owner date 2026-10-28 on each changed rule, as CORE.md does).
- [ ] **Step 4: Run the full suite** `... -m pytest -q -p no:cacheprovider` in `scripts/` — expect all PASS; rebuild a pack with `rules_pack.py --preset code --out <tmp>` and check it contains the program section.
- [ ] **Step 5: Sync** every changed file to the plugin cache (Global Constraints) and run `verify_course.py`, `check_case.py`, `check_prose.py`, `check_code_prose.py` on both delivered courses — all exit 0.
- [ ] **Step 6: Commit** `git commit -m "Rules: case studies where they teach, scan highlights, full programs"`

### Task 9: Pilot on the Flask course (owner review gate)

Not code: run with the updated plugin.

- [ ] **Step 1:** Copy Flask lessons 02 and 04 into `flask-course/work/_before/`.
- [ ] **Step 2:** Refresh each with `nerdit-lesson-writer`, `REFRESH = programs,readability`, `SOURCE_PATH = _before/<id>.html`, one writer at a time.
- [ ] **Step 3:** Gate each with `gate_lesson.py ... --before-dir flask-course/work/_before --modes programs,readability`; fix until PASS (2 attempts max).
- [ ] **Step 4:** Build `build_preview.py` for the two lessons and hand them to the owner. Stop here until the owner approves; the remaining Flask lessons and the Advanced Regression refresh follow only after that.
