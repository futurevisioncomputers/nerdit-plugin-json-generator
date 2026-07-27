# Split the rulebook into a core plus per-runner fragments

**Date:** 2026-07-27
**Status:** Approved, pending implementation plan
**Scope:** `nerdit_plugin-main/` — `references/`, `agents/`, `skills/nerdit-chapter-generator/`, `scripts/`; plus two new files deployed to `future-vision/public/`

## Problem

`nerdit-lesson-writer` is required by Step 0 of its own definition to read
`references/NERDIT_LESSON_PROMPT_v9_simple.md` **in full, every time**. That file is
~9,040 tokens, and roughly half of it describes runners a given lesson will never use.

Measured by section:

| Section | Tokens | Needed by |
|---|---|---|
| §1-5, 6a, 6b (constitution, skeleton, examples, demo data, predict/fill-blank) | ~2,570 | every lesson |
| §6c runner shell + SQL and Python variants | ~780 | SQL or Python lessons |
| §6d Excel widgets | ~1,080 | Excel lessons |
| §6e Matplotlib widget | ~600 | data-viz lessons |
| §7-8 (visual decision table, banned list, remaining blocks) | ~1,028 | every lesson |
| §9 the lesson script (shared helpers **and** both runners' JS) | ~2,041 | split |
| §10-12 (language rules, hygiene, component set) | ~888 | every lesson |
| **Total** | **~9,040** | |

A SQL lesson today reads Excel pivot boxes, Matplotlib figure handling, and the Pyodide
boot sequence for nothing. That is ~3,500 wasted tokens per lesson, ~42k per 12-lesson
chapter.

The waste grows linearly with ambition. At nine runners the rulebook reaches ~12,600
tokens and ~11,700 of them are irrelevant to any given lesson — ~140k wasted per chapter.
Every subject added taxes every lesson of every other subject.

### The second, hidden cost

§9 is not just read — it is **copied into the output**. The agent emits the composed
`<script>` inline in each lesson's HTML. The reference output confirms it: `window.copyCode`
and `window.switchTab` each appear 64 times across 32 lessons.

So each runner's JavaScript is paid for three times per lesson: read as input, written as
output, and stored in the Firestore document.

Excel and Matplotlib already avoid this. Their engines are separate `.js` files served by
the website (`future-vision/public/nerdit-excel-engine.js`), referenced from the lesson with
a plain `<script src>`. SQL and Python are the inconsistent pair, living as copy-paste
source inside the rulebook.

## Approach

Two changes that compose:

1. **Split the document.** `CORE.md` (subject-agnostic) plus one small fragment per runner.
   The orchestrator sends `CORE.md` and exactly one fragment.
2. **Extract the remaining runner JavaScript** to `.js` files served by the website, so all
   four runners follow the pattern Excel and Matplotlib already use.

Together, per-lesson cost stops depending on how many subjects the plugin supports.

### Rejected alternatives

- **Split docs only, leave JS inline.** Saves the input tokens but keeps writing ~800 tokens
  of boilerplate into every lesson and keeps it in the Firestore doc. Half the win for
  nearly the same work.
- **Extract JS only, keep one rulebook.** Fixes output and storage, but every lesson still
  reads every runner's documentation, and the linear growth problem remains untouched.
- **A `runners.json` registry with `detect_assets()` reading it.** Real value for
  maintainability, zero token value, and premature at four runners. Revisit when a fifth
  and sixth exist. Out of scope here.

## Component 1 — File structure

`references/NERDIT_LESSON_PROMPT_v9_simple.md` is deleted and replaced by:

| File | Contents | ~tokens |
|---|---|---|
| `references/CORE.md` | §1-5, §6a, §6b, §7, §8, §9 **shared helpers only**, §10, §11, §12 | ~4,900 |
| `references/runners/sql.md` | §6c SQL variant, seed-block contract, the `<script src>` line | ~500 |
| `references/runners/python.md` | §6c Python variant, first-load warning, the `<script src>` line | ~450 |
| `references/runners/excel.md` | §6d verbatim | ~1,080 |
| `references/runners/plot.md` | §6e verbatim | ~600 |

**The split is mechanical.** Lines move; wording does not change. This is deliberate: it
makes "did we drop a rule?" answerable by line accounting rather than by re-reading and
judging. Any genuine rewording is a separate, later change.

### Where the §9 seam falls

§9 is one fenced `<script>` block containing five guarded definitions.

Stays in `CORE.md`, still emitted inline (small, shared, no runtime dependency):

- `copyCode`
- `switchTab`
- `nerditCheckBlank`

Leaves the rulebook entirely:

- `nerditRunPython` → `nerdit-python-runner.js`
- `nerditRunSql` → `nerdit-sql-runner.js`

The trailing note "Chart.js (rare in v9): reuse the v8 `withChart` lazy-load pattern inside
this same script" stays in `CORE.md`.

### What CORE.md keeps about runners

The §6c routing table (which engine for which language) is **removed** — the orchestrator
now makes that choice and hands the agent one fragment, so the table would only invite the
agent to second-guess it. `CORE.md` keeps one short paragraph in its place:

> At most ONE live runner per lesson, on the concept that benefits most. If the orchestrator
> gave you a runner fragment, follow it exactly. If a lesson genuinely needs a different
> runner, read that fragment from `references/runners/` before using it.

That last sentence is the safety valve — see Error handling.

## Component 2 — Runner JavaScript extraction

Two new files in `references/`, alongside the two engines already there:

- `references/nerdit-sql-runner.js` — `window.nerditRunSql`, the sql.js CDN boot, the result-table renderer
- `references/nerdit-python-runner.js` — `window.nerditRunPython`, the Pyodide boot, the friendly-traceback reducer, the fresh-namespace-per-run logic

Both keep their existing `if (typeof window.X !== "function")` guard so multiple lessons on
one page never double-define.

Lessons reference them exactly as Excel and Matplotlib are referenced today:

```html
<script src="/nerdit-sql-runner.js"></script>
```

### Deployment dependency — must be sequenced

These files must be copied to `future-vision/public/` and deployed **before** any lesson
generated under the new rulebook reaches production. A lesson referencing
`/nerdit-sql-runner.js` when the website does not serve it renders fine and fails silently
on the first Run click.

This dependency already exists for `nerdit-excel-engine.js` and `nerdit-plot-runner.js`;
this change widens it from two runners to four. The implementation plan must put the
website deployment before the first generation run, not after.

The mechanism is verified: `runEmbeddedLessonScripts()` in the website's `CourseView.tsx`
re-creates each `<script>` element and copies its attributes before re-inserting, so
external `src` scripts inside lesson HTML do execute.

## Component 3 — Input schema and orchestrator

The input array gains one optional per-lesson field:

```json
{
  "id": "joins-inner",
  "title": "Inner Joins",
  "description": "...",
  "runner": "sql"
}
```

Accepted values: `"sql"`, `"python"`, `"excel"`, `"plot"`, `"none"`.

Orchestrator behaviour:

- **Field present** → pass `CORE.md` + `references/runners/<runner>.md`. `"none"` passes
  `CORE.md` alone (the lesson uses only `nerdit-predict` / `nerdit-fillblank` for practice).
- **Field absent** → infer from the chapter name and the lesson descriptions, then **print
  the per-lesson choice and wait for confirmation before spawning any agent**. Inference is
  cheap; twelve wrongly-generated lessons are not.

The field is generation context only. It is not copied into the output, exactly like
`description`. The assembler ignores it — it already reads only `id` and `title` from the
input.

Per-lesson rather than per-chapter because mixed chapters are real: a data-science course
runs `python` on its pandas lessons and `plot` on its charting lessons.

## Component 4 — Assembler

Three small changes to `scripts/assemble_course.py`:

- `ASSET_URL_BASE` becomes `/` — the current `/assets/js` is wrong. The engines are served
  from the website's `public/` at root (`/nerdit-excel-engine.js`), which is what the
  rulebook tells the agent to emit and what works in production today.
- `ENGINE_FILES` gains `nerdit-sql-runner.js` and `nerdit-python-runner.js`.
- `detect_assets()` logic is unchanged — it just scans for a longer list.

**Note on impact:** `lesson.assets` is currently dead metadata. The website never reads it;
lessons work because the HTML carries its own `<script src>`. Correcting the prefix does not
fix a live bug — it stops the field from being actively misleading to the next person who
tries to use it.

## Component 5 — Referencing sites

Six places name the old file and must be updated:

| File | Line | Change |
|---|---|---|
| `agents/nerdit-lesson-writer.md` | 32 | Step 0 reads `CORE.md` plus the fragment the orchestrator named |
| `skills/.../SKILL.md` | 77 | Reference table row splits into CORE + runners |
| `skills/.../SKILL.md` | 85 | "Every lesson follows `CORE.md`" |
| `skills/.../SKILL.md` | 99 | "Always read `CORE.md` first" |
| `skills/.../SKILL.md` | 243 | QA checklist: component markup matches `CORE.md` **and the lesson's runner fragment** |
| `README.md` | 33 | Component-catalogue sentence |

The prior spec at `docs/superpowers/specs/2026-07-27-merge-lesson-quiz-agents-design.md`
also names the old file. It is a historical record of a completed change and is **not**
updated.

## Error handling

- **Unknown `runner` value** (typo, unsupported subject): the orchestrator stops and lists
  the valid values. It does not guess — silently falling back to `"none"` would produce a
  whole chapter with no practice widgets and no warning.
- **Runner fragment missing from disk:** the orchestrator stops before spawning. A lesson
  writer that silently proceeded without its fragment would emit a Try It block whose
  handler does not exist.
- **Agent needs a second runner:** it reads that fragment itself via `Read`/`Glob`. Costs
  one extra read; does not produce a broken lesson. This is the intended recovery path for
  a wrong inference, and is why the fragments stay on disk rather than being inlined into
  the agent prompt.
- **Website missing a runner `.js`:** not detectable from the plugin. Handled by sequencing
  (deploy first) and by the per-runner browser check in Testing.

## Testing

**Split integrity** — the risk that matters. A dropped rule is silent and only surfaces as
degraded lessons weeks later. Two mechanical checks:

- Every `##` and `###` heading in the original file appears in exactly one of the new files
  (or is on an explicit, listed exception — the §6c routing table is removed by design).
- Combined non-blank, non-heading line count of the new files equals the original's, minus
  the extracted JavaScript line count and the removed routing table.

**Assembler** — normal pytest, added to the existing suite:

- `detect_assets()` returns the right URL for each of the four engines
- URL prefix is `/`, not `/assets/js`
- a lesson using two engines gets both, in `ENGINE_FILES` order
- a lesson using none gets no `assets` key

**Runtime** — cannot be automated here, and is the only check that catches a broken script
tag or a missing deployed file. Generate one real lesson per runner, load each in the
browser, click Run, confirm output. Four lessons, four clicks.

## Out of scope

- `runners.json` registry and making `detect_assets()` data-driven. Revisit at 5-6 runners.
- Any new runner (TensorFlow.js, Canvas, pandas-specific). This change makes adding them
  cheap; it does not add them.
- Rewording any rule. The split is mechanical so that it stays verifiable.
- Course-level playground. That is a website feature, not a plugin feature.
- `nerdit-qa-validator`'s checklist content, beyond the one line naming the rulebook file.
