# Merge nerdit-quiz-writer into nerdit-lesson-writer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the two per-lesson subagents into one, so a lesson's HTML and its 6 quiz questions are produced in a single agent turn and handed to the assembler as files on disk.

**Architecture:** `nerdit-lesson-writer` writes both `<id>.html` and `<id>.quiz.json` into the run workdir and returns two path lines. `assemble_course.py` picks the quiz JSON up from `--html-dir`, making `--meta` optional and keeping the old `meta.json` path as a back-compat fallback. The orchestrator stops spawning a quiz agent and stops writing `meta.json` — it holds neither lesson HTML nor question text.

**Tech Stack:** Python 3 stdlib only (no third-party imports in `scripts/`), pytest for tests, Markdown for the agent and skill definitions.

**Spec:** [docs/superpowers/specs/2026-07-27-merge-lesson-quiz-agents-design.md](../specs/2026-07-27-merge-lesson-quiz-agents-design.md)

## Global Constraints

- `scripts/*.py` stay **Python-stdlib only**. No new dependencies.
- Quiz JSON shape is frozen and identical to today's `nerdit-quiz-writer` output: `{"lessonQuestions": [...3], "assessmentQuestions": [...3]}`, each question `{text, options[4], correctOptionIndex}`, **no `id` fields** — the assembler assigns every question id.
- All 9 existing tests in `test_assemble_course.py` must keep passing **unmodified**. They call `build_course(chapter, input_lessons, meta, html_dir, now_ms=...)` positionally; that signature does not change.
- Question ids keep the format `lesson-<session>-<lesson_id>-qN-<batch>` and `assessment-<session>-<lesson_id>-qN-<batch>`, one shared session/batch pair per file.
- Malformed `quiz.json` fails the run (exit 2). Missing `quiz.json` only warns.
- Never write generated output into the plugin folder.

## Repo note — read before Task 1

The git repository root is `d:\siddharth\nerdit-backup\nerdit_plugin-main` (remote: `futurevisioncomputers/nerdit-plugin-json-generator`). Work happens on branch `feat/merge-lesson-quiz-agents`, cut from `main`.

**Path convention:** file paths in this plan are written from `d:\siddharth\nerdit-backup` and therefore carry a `nerdit_plugin-main/` prefix. Shell commands — `git add`, `grep`, `rm` — run **from inside the repo root**, so drop that prefix when typing them. Example: the plan says `nerdit_plugin-main/agents/nerdit-quiz-writer.md`; the command is `rm agents/nerdit-quiz-writer.md`.

## File Structure

| File | Change | Responsibility after |
|---|---|---|
| `nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/assemble_course.py` | Modify | Adds `load_quiz()`; `build_course()` layers quiz-file data over meta data; `main()` makes `--meta` optional and warns on question-less lessons |
| `nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/test_assemble_course.py` | Modify (append) | Covers quiz-file loading, precedence, back-compat, and error paths |
| `nerdit_plugin-main/agents/nerdit-lesson-writer.md` | Modify | Owns both lesson-content rules and question-quality rules; documents the two-file output contract |
| `nerdit_plugin-main/agents/nerdit-quiz-writer.md` | Delete | — |
| `nerdit_plugin-main/skills/nerdit-chapter-generator/SKILL.md` | Modify | Orchestrator: one spawn per lesson, no `meta.json`, no `--meta` |

Task order matters: the assembler accepts the new file **before** the agent starts producing it, so a half-applied change never breaks a run.

---

### Task 1: Assembler reads `<id>.quiz.json`

**Files:**
- Modify: `nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/assemble_course.py:82-107` (`build_course`), plus a new `load_quiz` above it
- Test: `nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/test_assemble_course.py` (append)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `load_quiz(html_dir, lesson_id) -> dict | None` — returns the parsed quiz object, `None` if the file is absent, raises `ValueError` if present but unreadable or wrong-shaped. `build_course(chapter, input_lessons, meta, html_dir, now_ms=None)` keeps its signature but now accepts `meta=None`.

All commands run from the scripts directory:

```
d:\siddharth\nerdit-backup\nerdit_plugin-main\skills\nerdit-chapter-generator\scripts
```

- [ ] **Step 1: Write the failing tests**

Append to `test_assemble_course.py`:

```python
import os
import pytest
from assemble_course import load_quiz


def _quizfile(tmp_path, lesson_id, lesson_qs, assessment_qs):
    (tmp_path / f"{lesson_id}.quiz.json").write_text(
        json.dumps({"lessonQuestions": lesson_qs, "assessmentQuestions": assessment_qs}),
        encoding="utf-8",
    )


def test_load_quiz_absent_returns_none(tmp_path):
    assert load_quiz(str(tmp_path), "nope") is None


def test_quiz_file_questions_land_with_ids(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    _quizfile(tmp_path, "l1", [_q("lq")] * 3, [_q("aq")] * 3)
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    c = build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert len(c["lessons"][0]["questions"]) == 3
    assert c["lessons"][0]["questions"][0]["text"] == "lq"
    assert c["lessons"][0]["questions"][0]["id"] == "lesson-1700000000000-l1-q1-1700000000000"
    assert len(c["assessment"]["questions"]) == 3
    assert c["assessment"]["questions"][2]["id"] == "assessment-1700000000000-l1-q3-1700000000000"


def test_quiz_file_beats_meta(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    _quizfile(tmp_path, "l1", [_q("from-file")] * 3, [_q("af")] * 3)
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    meta = [{"id": "l1", "title": "T", "lessonQuestions": [_q("from-meta")] * 3,
             "assessmentQuestions": [_q("am")] * 3}]
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    assert c["lessons"][0]["questions"][0]["text"] == "from-file"
    assert c["assessment"]["questions"][0]["text"] == "af"


def test_meta_duration_survives_quiz_file(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    _quizfile(tmp_path, "l1", [_q("lq")] * 3, [_q("aq")] * 3)
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    meta = [{"id": "l1", "title": "T", "duration": "12m",
             "lessonQuestions": [], "assessmentQuestions": []}]
    c = build_course("demo", inp, meta, str(tmp_path), now_ms=1700000000000)
    assert c["lessons"][0]["duration"] == "12m"
    assert c["lessons"][0]["questions"][0]["text"] == "lq"


def test_no_quiz_no_meta_is_empty_not_crash(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    c = build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert c["lessons"][0]["questions"] == []
    assert c["assessment"]["questions"] == []


def test_malformed_quiz_json_raises_with_id_and_path(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    (tmp_path / "l1.quiz.json").write_text("{not json", encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    with pytest.raises(ValueError) as e:
        build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert "l1" in str(e.value) and "l1.quiz.json" in str(e.value)


def test_quiz_json_wrong_toplevel_type_raises(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    (tmp_path / "l1.quiz.json").write_text('["a", "b"]', encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    with pytest.raises(ValueError) as e:
        build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert "JSON object" in str(e.value)


def test_quiz_json_wrong_field_type_raises(tmp_path):
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    (tmp_path / "l1.quiz.json").write_text(
        '{"lessonQuestions": "oops", "assessmentQuestions": []}', encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    with pytest.raises(ValueError) as e:
        build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert "lessonQuestions" in str(e.value)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest test_assemble_course.py -v`

Expected: FAIL — `ImportError: cannot import name 'load_quiz' from 'assemble_course'`. The whole module fails to collect; that is the expected first failure.

- [ ] **Step 3: Add `load_quiz`**

Insert into `assemble_course.py` directly above `def build_course` (after `with_ids`):

```python
def load_quiz(html_dir, lesson_id):
    """Read <html_dir>/<lesson_id>.quiz.json, the question sidecar the lesson-writer
    agent writes next to its <lesson_id>.html. Returns the parsed object, or None when
    no such file exists (the lesson simply has no questions from this source).

    A present-but-broken file raises instead of being skipped: a silently dropped
    question set assembles into a file that looks fine but ships a short assessment
    bank, which QA would only catch as a confusing count mismatch."""
    path = os.path.join(html_dir, lesson_id + ".quiz.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"{lesson_id}: unreadable quiz file {path}: {e}")
    if not isinstance(data, dict):
        raise ValueError(
            f"{lesson_id}: quiz file {path} must contain a JSON object, "
            f"got {type(data).__name__}")
    for key in ("lessonQuestions", "assessmentQuestions"):
        if key in data and not isinstance(data[key], list):
            raise ValueError(
                f"{lesson_id}: quiz file {path} field {key} must be a list, "
                f"got {type(data[key]).__name__}")
    return data
```

- [ ] **Step 4: Layer the quiz file over meta in `build_course`**

In `assemble_course.py`, replace line 86:

```python
    meta_by_id = {m["id"]: m for m in meta}
```

with:

```python
    meta_by_id = {m["id"]: m for m in (meta or [])}
```

Then replace line 91:

```python
        m = meta_by_id.get(lid, {})
```

with:

```python
        # Per-lesson <id>.quiz.json is the current source; meta.json is the
        # pre-merge fallback. Layering (not replacing) keeps meta-only fields
        # such as `duration` working when both are present.
        m = dict(meta_by_id.get(lid, {}))
        quiz = load_quiz(html_dir, lid)
        if quiz is not None:
            m.update(quiz)
```

Leave lines 92-107 untouched — `duration`, `with_ids`, `detect_assets`, and the assessment concatenation all read `m` and need no change.

- [ ] **Step 5: Run the full test file to verify everything passes**

Run: `python -m pytest test_assemble_course.py -v`

Expected: PASS — 9 pre-existing tests plus 8 new ones, 17 passed. If any of the 9 original tests fail, the signature or the meta fallback broke; fix before continuing.

- [ ] **Step 6: Commit**

```bash
git add nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/assemble_course.py nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/test_assemble_course.py
git commit -m "feat(assembler): read per-lesson <id>.quiz.json, meta.json as fallback"
```

---

### Task 2: `--meta` optional, missing-quiz warning, error exit

**Files:**
- Modify: `nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/assemble_course.py:10-13` (module docstring usage), `:138-162` (`main`)
- Test: `nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/test_assemble_course.py` (append)

**Interfaces:**
- Consumes: `load_quiz` and the layered `build_course` from Task 1.
- Produces: a CLI that runs with `--meta` omitted, prints `WARNING missing quiz (N): id, id` for lessons that ended up with zero questions, and exits 2 on a malformed quiz file.

- [ ] **Step 1: Write the failing CLI tests**

Append to `test_assemble_course.py`:

```python
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assemble_course.py")


def _run_cli(tmp_path, extra=()):
    return subprocess.run(
        [sys.executable, SCRIPT, "--chapter", "demo",
         "--input", str(tmp_path / "in.json"),
         "--html-dir", str(tmp_path),
         "--out", str(tmp_path / "out.json"), *extra],
        capture_output=True, text=True,
    )


def test_cli_runs_without_meta_flag(tmp_path):
    (tmp_path / "in.json").write_text(
        json.dumps([{"id": "l1", "title": "T", "description": "d"}]), encoding="utf-8")
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    _quizfile(tmp_path, "l1", [_q("lq")] * 3, [_q("aq")] * 3)
    r = _run_cli(tmp_path)
    assert r.returncode == 0, r.stderr
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert len(out["lessons"][0]["questions"]) == 3
    assert "missing quiz" not in r.stdout


def test_cli_warns_when_quiz_missing(tmp_path):
    (tmp_path / "in.json").write_text(
        json.dumps([{"id": "l1", "title": "T", "description": "d"}]), encoding="utf-8")
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    r = _run_cli(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "WARNING missing quiz (1): l1" in r.stdout


def test_cli_exits_2_on_malformed_quiz(tmp_path):
    (tmp_path / "in.json").write_text(
        json.dumps([{"id": "l1", "title": "T", "description": "d"}]), encoding="utf-8")
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    (tmp_path / "l1.quiz.json").write_text("{broken", encoding="utf-8")
    r = _run_cli(tmp_path)
    assert r.returncode == 2
    assert "l1" in r.stderr


def test_cli_still_accepts_meta_flag(tmp_path):
    (tmp_path / "in.json").write_text(
        json.dumps([{"id": "l1", "title": "T", "description": "d"}]), encoding="utf-8")
    (tmp_path / "l1.html").write_text("<div>x</div>", encoding="utf-8")
    (tmp_path / "meta.json").write_text(json.dumps(
        [{"id": "l1", "title": "T", "lessonQuestions": [_q("m")] * 3,
          "assessmentQuestions": [_q("m2")] * 3}]), encoding="utf-8")
    r = _run_cli(tmp_path, ["--meta", str(tmp_path / "meta.json")])
    assert r.returncode == 0, r.stderr
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert out["lessons"][0]["questions"][0]["text"] == "m"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest test_assemble_course.py -k cli -v`

Expected: FAIL — `test_cli_runs_without_meta_flag` fails with returncode 2 and stderr `the following arguments are required: --meta`; `test_cli_warns_when_quiz_missing` fails for the same reason.

- [ ] **Step 3: Make `--meta` optional and load it conditionally**

In `main()`, replace:

```python
    ap.add_argument("--meta", required=True)
```

with:

```python
    ap.add_argument("--meta", default=None,
                    help="optional legacy meta.json sidecar; a per-lesson "
                         "<id>.quiz.json in --html-dir takes precedence")
```

Then replace:

```python
    with open(args.meta, encoding="utf-8") as f:
        meta = json.load(f)

    course = build_course(args.chapter, input_lessons, meta, args.html_dir)
```

with:

```python
    meta = []
    if args.meta:
        with open(args.meta, encoding="utf-8") as f:
            meta = json.load(f)

    try:
        course = build_course(args.chapter, input_lessons, meta, args.html_dir)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
```

- [ ] **Step 4: Add the missing-quiz warning**

Directly after the existing missing-HTML warning block:

```python
    if missing:
        print(f"WARNING missing HTML ({len(missing)}): {', '.join(missing)}")
```

add:

```python
    noquiz = [l["id"] for l in course["lessons"] if not l["questions"]]
    if noquiz:
        print(f"WARNING missing quiz ({len(noquiz)}): {', '.join(noquiz)}")
```

This is source-agnostic on purpose — it fires whenever a lesson ends up with no questions, whether the quiz file was never written or a stale `meta.json` had no entry.

- [ ] **Step 5: Update the module docstring usage line**

Replace the `Usage:` block at the top of `assemble_course.py`:

```
Usage:
  python assemble_course.py --chapter <slug> --input <input.json> \
      --html-dir <dir> --meta <meta.json> --out <output.json>
```

with:

```
Each lesson's questions come from <html-dir>/<id>.quiz.json, written by the
lesson-writer agent alongside that lesson's HTML. --meta is a pre-merge fallback
kept for re-assembling older workdirs.

Usage:
  python assemble_course.py --chapter <slug> --input <input.json> \
      --html-dir <dir> --out <output.json> [--meta <meta.json>]
```

- [ ] **Step 6: Run the whole suite to verify it passes**

Run: `python -m pytest test_assemble_course.py test_input_from_output.py -v`

Expected: PASS, 21 tests in `test_assemble_course.py` (9 original + 8 from Task 1 + 4 CLI) plus the `test_input_from_output.py` tests, all green.

- [ ] **Step 7: Commit**

```bash
git add nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/assemble_course.py nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/test_assemble_course.py
git commit -m "feat(assembler): make --meta optional, warn on missing quiz, exit 2 on malformed"
```

---

### Task 3: Merge the agents

**Files:**
- Modify: `nerdit_plugin-main/agents/nerdit-lesson-writer.md`
- Delete: `nerdit_plugin-main/agents/nerdit-quiz-writer.md`

**Interfaces:**
- Consumes: the `<id>.quiz.json` contract the assembler now reads (Task 1).
- Produces: an agent that returns exactly two lines, `FILE: <path>` and `QUIZ: <path>`. Task 4's orchestrator changes depend on those two line prefixes.

There are no automated tests for agent behaviour — quality stays covered by `nerdit-qa-validator`. The gate for this task is the manual read-through in Step 4.

- [ ] **Step 1: Update the frontmatter**

In `nerdit-lesson-writer.md`, replace the frontmatter block (lines 1-8):

```yaml
---
name: nerdit-lesson-writer
description: >
  Generates one complete NERDIT LMS HTML lesson (content + duration) for a single topic
  (id, title, description). Invoked by the nerdit-chapter-generator skill once per topic,
  in parallel across topics. Do not use for quiz generation or output validation.
tools: [Read, Grep, Glob, Write]
---
```

with:

```yaml
---
name: nerdit-lesson-writer
description: >
  Generates one complete NERDIT LMS HTML lesson plus its 6 multiple-choice quiz questions
  for a single topic (id, title, description). Writes both artifacts to disk. Invoked by
  the nerdit-chapter-generator skill once per topic, in parallel across topics. Do not use
  for output validation.
tools: [Read, Grep, Glob, Write]
---
```

`tools` is unchanged — `Write` already covers the second file.

- [ ] **Step 2: Restate the job as two artifacts**

Replace the `# Job` section (currently lines 12-16):

```markdown
# Job

Given one topic (`id`, `title`, `description`), a chapter theme, and a target `HTML_PATH`,
**write** the complete self-contained NERDIT LMS HTML lesson fragment to `HTML_PATH` with the
Write tool. Duration is computed downstream by the assembler script — you do not estimate it.
```

with:

```markdown
# Job

Given one topic (`id`, `title`, `description`), a chapter theme, a target `HTML_PATH`, and a
target `QUIZ_PATH`, produce **two** files with the Write tool:

1. `HTML_PATH` — the complete self-contained NERDIT LMS HTML lesson fragment.
2. `QUIZ_PATH` — 6 multiple-choice questions derived from the fragment you just wrote.

Duration is computed downstream by the assembler script — you do not estimate it. Question
ids are assigned by the assembler — you do not write any.

**Order is mandatory and not an optimisation:** read the rulebook, write the HTML, *then*
derive the questions from the fragment you actually wrote. Questions must test content that
is present in that file — never a planned example you cut, never a fact the fragment does
not teach. Do not draft questions before the HTML exists.
```

- [ ] **Step 3: Add the question rules and the new output contract**

Replace the entire `## Output format` section (currently lines 74-85, from the `## Output format` heading to the end of the file):

```markdown
## Output format

Write the full HTML fragment (starting with `<div class="nerdit-wrapper ...">`) to `HTML_PATH`
with the Write tool. Do NOT print the HTML in your reply. Then return exactly one line, nothing
else:

...
```

with:

```markdown
## Quiz rules

After `HTML_PATH` is written, derive exactly 6 multiple-choice questions from it, split into
two groups of 3:

- `lessonQuestions` — lands on the lesson object's own `questions` field
- `assessmentQuestions` — feeds the course's top-level `assessment.questions` bank

Rules:

- All 6 answerable from the fragment you wrote alone — never invent facts it does not teach
- Vary what each of the 6 tests: mix conceptual, applied/troubleshooting, and comparative angles
- `assessmentQuestions` must test **different** facts/angles than `lessonQuestions` — not
  verbatim or near-verbatim restatements of the other group's 3 questions
- All 4 options per question plausible — no throwaway distractors
- Exactly one correct option per question (`correctOptionIndex`, zero-based: 0-3)
- Question text: complete sentence, ends with `?`
- Do not reuse heading wording verbatim

## Output format

Write two files with the Write tool. Print neither of them in your reply.

**1. `HTML_PATH`** — the full HTML fragment, starting with `<div class="nerdit-wrapper ...">`.

**2. `QUIZ_PATH`** — a JSON object, exactly this shape. No `id` fields: the assembler generates
every question id so one session/batch pair covers the whole file.

```json
{
  "lessonQuestions": [
    {
      "correctOptionIndex": 0,
      "options": ["Correct answer", "Distractor B", "Distractor C", "Distractor D"],
      "text": "Question text ending with a question mark?"
    },
    { "...": "lessonQuestions[1], same shape" },
    { "...": "lessonQuestions[2], same shape" }
  ],
  "assessmentQuestions": [
    { "...": "assessmentQuestions[0], same shape" },
    { "...": "assessmentQuestions[1], same shape" },
    { "...": "assessmentQuestions[2], same shape" }
  ]
}
```

Then return exactly these two lines, nothing else:

```
FILE: <HTML_PATH>
QUIZ: <QUIZ_PATH>
```

No preamble, no explanation, no HTML echo, no JSON echo, no markdown fences. Both files written
to disk still obey every rule above.
```

Leave every other section — Step 0, "The rules that matter most", Forbidden, Hygiene, Robustness, Reform mode — exactly as it is.

- [ ] **Step 4: Read the merged file end to end and verify**

Read `nerdit-lesson-writer.md` in full. Confirm:
- The Reform-mode section still reads correctly now that the job produces two files (it should — `SOURCE_PATH` only affects how the HTML is derived, and the quiz then derives from that HTML like any other run).
- No remaining sentence claims the agent produces only one file or says "return exactly one line".
- The word "quiz" no longer appears in any exclusion clause (the old `description` said "Do not use for quiz generation").

- [ ] **Step 5: Delete the quiz agent**

```bash
rm nerdit_plugin-main/agents/nerdit-quiz-writer.md
```

- [ ] **Step 6: Verify no dangling references outside SKILL.md**

Run: `grep -rn "nerdit-quiz-writer" nerdit_plugin-main/`

Expected: hits only in `skills/nerdit-chapter-generator/SKILL.md` (fixed in Task 4). Any hit in `agents/`, `scripts/`, `README.md`, or `.claude-plugin/` must be resolved now.

- [ ] **Step 7: Commit**

```bash
git add nerdit_plugin-main/agents/
git commit -m "feat(agents): fold quiz generation into nerdit-lesson-writer, drop nerdit-quiz-writer"
```

---

### Task 4: Orchestrator (`SKILL.md`)

**Files:**
- Modify: `nerdit_plugin-main/skills/nerdit-chapter-generator/SKILL.md:30-67` (Multi-Agent Architecture), `:160-206` (Steps 2b-3), `:208-234` (Step 4), `:236-242` (Step 5 failure path)

**Interfaces:**
- Consumes: the two-line agent contract from Task 3 and the optional `--meta` CLI from Task 2.
- Produces: the final documented pipeline. Nothing depends on this task.

- [ ] **Step 1: Update the Multi-Agent Architecture table**

Replace the three-row table (lines 36-40) with:

```markdown
| Agent | Job | Runs |
|---|---|---|
| `nerdit-lesson-writer` | Writes one lesson's HTML fragment to `<workdir>/<id>.html` **and** its 6 MCQs to `<workdir>/<id>.quiz.json`; returns both paths | Once per lesson, in parallel |
| `nerdit-qa-validator` | Read-only checklist pass over the script-assembled output file | Once, after assembly |
```

- [ ] **Step 2: Rewrite the delegation flow**

Replace the numbered delegation flow (lines 47-64) with:

```markdown
1. Parse the input array (Step 1) and choose the run workdir (Step 6's destination).
2. Spawn one `nerdit-lesson-writer` agent per lesson. Independent lessons have no dependency
   on each other — launch them together in one batch of parallel Agent calls. Pass each agent:
   the lesson's `id`/`title`/`description`, the chapter name, whether this is a multi-lesson
   chapter (so it prefixes internal HTML ids), `HTML_PATH = <workdir>/<id>.html`, and
   `QUIZ_PATH = <workdir>/<id>.quiz.json`. Each returns only `FILE:` and `QUIZ:` path lines —
   neither the HTML nor the questions ever enter your context.
3. Run `scripts/assemble_course.py` (Step 4) to build the full `course-<chapter>_output.json`
   from the input, the `<id>.html` files, and the `<id>.quiz.json` files. The script owns all
   course defaults, ids, timestamps, durations, and `assets`.
4. Spawn `nerdit-qa-validator` once against the assembled output file (Step 5). On any `FAIL`,
   re-run the broken lesson's `nerdit-lesson-writer` (it regenerates both files), re-assemble,
   re-validate. Then deliver (Step 6).
```

Then update the paragraph that follows it — replace "the parallelism in steps 2/3 is moot" with "the parallelism in step 2 is moot".

Also update the "Why:" paragraph (lines 42-45): replace "Running lessons in parallel also cuts wall-clock time on multi-lesson chapters." with "Generating each lesson's questions in the same turn that wrote its HTML avoids re-reading the fragment from disk in a second agent. Running lessons in parallel also cuts wall-clock time on multi-lesson chapters."

- [ ] **Step 3: Update Step 2b/2c and delete Step 2d**

In section `### 2b/2c. Delegate the lesson HTML to nerdit-lesson-writer`, retitle it to `### 2b. Delegate the lesson to nerdit-lesson-writer` and replace its final two sentences:

```
It **writes the fragment to `HTML_PATH`** and returns only `FILE: <path>`. Do not read the HTML
back into your context; duration is computed later by the assembler.
```

with:

```
It **writes the fragment to `HTML_PATH` and the 6 questions to `QUIZ_PATH`**, then returns only
its `FILE:`/`QUIZ:` path lines. Do not read either file back into your context; duration is
computed later by the assembler, and question ids are assigned by it.
```

Then delete the whole `### 2d. Delegate 6 split questions to nerdit-quiz-writer` section (lines 170-181), including its bullet list.

- [ ] **Step 4: Delete Step 3 (the meta.json sidecar)**

Delete the entire `## Step 3 — Write the meta.json Sidecar` section (lines 185-206), heading, JSON block, and trailing paragraph included, along with its `---` separator.

Do **not** renumber Steps 4, 5, and 6 — the numbers are referenced throughout the file and in `nerdit-qa-validator`. Instead, put this line where Step 3 was:

```markdown
## Step 3 — (removed)

The `meta.json` sidecar is gone: `nerdit-lesson-writer` writes each lesson's questions
straight to `<workdir>/<id>.quiz.json`, and `id`/`title` reach the assembler from the input
file it already reads. Nothing to do here — go to Step 4.

---
```

- [ ] **Step 5: Update Step 4's command and prose**

In `## Step 4 — Assemble the Output JSON`, replace the opening sentence:

```
Run the bundled assembler via Bash. It reads the input file, every `<workdir>/<id>.html`, and
`meta.json`, then writes the full course object
```

with:

```
Run the bundled assembler via Bash. It reads the input file, every `<workdir>/<id>.html`, and
every `<workdir>/<id>.quiz.json`, then writes the full course object
```

Replace the command block with:

```
    python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/assemble_course.py" \
      --chapter <chaptername> \
      --input   <path to the input JSON> \
      --html-dir <workdir> \
      --out     <workdir>/course-<chaptername>_output.json
```

Replace the failure-handling sentence:

```
If the script prints `WARNING missing HTML`, a lesson file failed to write: re-run that lesson's
`nerdit-lesson-writer`, then re-run the script.
```

with:

```
If the script prints `WARNING missing HTML` or `WARNING missing quiz`, that lesson's agent
failed to write one of its two files: re-run that lesson's `nerdit-lesson-writer`, then re-run
the script. If it exits 2 with an `ERROR:` naming a lesson and a `.quiz.json` path, that file is
malformed — re-run that lesson's agent and re-assemble.
```

- [ ] **Step 6: Update the Step 5 failure path**

In `## Step 5 — Validate the Assembled File`, replace:

```
If it reports failures, fix the specific lesson(s) by re-running that lesson's `nerdit-lesson-writer`
and/or `nerdit-quiz-writer` (Step 2), re-run the assembler (Step 4), and spawn `nerdit-qa-validator`
again before moving to Step 6.
```

with:

```
If it reports failures, fix the specific lesson(s) by re-running that lesson's
`nerdit-lesson-writer` (Step 2) — it regenerates both the HTML and the questions — then re-run
the assembler (Step 4) and spawn `nerdit-qa-validator` again before moving to Step 6.
```

Leave the entire checklist below it unchanged. It validates the assembled file and does not care how the questions got there.

- [ ] **Step 7: Verify no stale references remain**

Run: `grep -rn "nerdit-quiz-writer\|meta.json\|--meta" nerdit_plugin-main/skills/nerdit-chapter-generator/SKILL.md`

Expected: no hits for `nerdit-quiz-writer`. Hits for `meta.json` are acceptable only inside the Step 3 removal note. No hits for `--meta`.

- [ ] **Step 8: End-to-end smoke test**

Build a two-lesson workdir by hand in a scratch directory and run the documented Step 4 command against it, with no `meta.json` present:

```bash
python nerdit_plugin-main/skills/nerdit-chapter-generator/scripts/assemble_course.py \
  --chapter smoke --input <scratch>/course-smoke_input.json \
  --html-dir <scratch> --out <scratch>/course-smoke_output.json
```

Expected: exit 0, no `WARNING` lines, and the output JSON has 3 questions on each lesson and 6 in `assessment.questions`.

- [ ] **Step 9: Commit**

```bash
git add nerdit_plugin-main/skills/nerdit-chapter-generator/SKILL.md
git commit -m "docs(skill): one agent per lesson, drop meta.json sidecar and --meta"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Component 1 — merged agent contract, two-line return, quiz JSON shape | Task 3 Steps 2-3 |
| Component 1 — ordering rule (quality guard) | Task 3 Step 2 |
| Component 1 — inherited question-quality rules | Task 3 Step 3 |
| Component 2 — `--meta` optional | Task 2 Step 3 |
| Component 2 — resolution order, quiz-file-first | Task 1 Step 4 |
| Component 2 — `duration` still falls through | Task 1 Step 1 (`test_meta_duration_survives_quiz_file`) |
| Component 3 — orchestrator edits | Task 4, all steps |
| Error handling — missing quiz warns | Task 2 Step 4 |
| Error handling — malformed quiz fails loudly | Task 1 Step 3, Task 2 Step 3 |
| Error handling — both present, quiz wins, no warning | Task 1 Step 1 (`test_quiz_file_beats_meta`) |
| Testing — all 6 listed cases | Task 1 Step 1 (5 of them) + Task 2 Step 1 (`--meta` omitted) |
| Out of scope — validator untouched | Task 4 Step 6 states it explicitly |

No gaps.

**Placeholder scan:** no TBD/TODO, no "add appropriate error handling", no "similar to Task N". Every code step carries the literal code.

**Type consistency:** `load_quiz(html_dir, lesson_id)` is defined in Task 1 Step 3 and used in Task 1 Step 4; nothing else calls it. `build_course` keeps its exact 5-parameter signature across all tasks. The `FILE:`/`QUIZ:` line prefixes are identical in Task 3 Step 3 and Task 4 Step 2. `<id>.quiz.json` is spelled the same in the assembler, the agent, and the skill.
