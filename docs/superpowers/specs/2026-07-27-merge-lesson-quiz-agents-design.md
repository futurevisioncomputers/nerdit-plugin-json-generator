# Merge nerdit-lesson-writer and nerdit-quiz-writer

**Date:** 2026-07-27
**Status:** Approved, pending implementation plan
**Scope:** `nerdit_plugin-main/` — `agents/`, `skills/nerdit-chapter-generator/`

## Problem

The chapter generator spawns two subagents per lesson. `nerdit-lesson-writer` reads the
rulebook and writes `<id>.html`. `nerdit-quiz-writer` then reads that same `<id>.html`
back off disk and derives 6 questions from it.

The second read is duplicate spend. The lesson writer already held the full fragment in
context — it had just generated it. Re-reading it in a fresh agent pays for the same
tokens twice, plus a second agent boot, plus a second sequential round-trip per lesson.

The orchestrator pays a third time: it captures all 6 questions per lesson into its own
context solely to relay them into `meta.json`.

### Measured cost (12-lesson chapter)

Sizes from `references/`: the rulebook `NERDIT_LESSON_PROMPT_v9_simple.md` is 32.7 KB;
the reference output JSON is 341.2 KB across ~12 lessons, so a generated lesson fragment
averages ~28 KB (~7k tokens).

| | Current | Merged |
|---|---|---|
| Agent spawns | 24 | 12 |
| Duplicate HTML reads | 12 × ~7k tokens | 0 |
| Orchestrator quiz relay | ~10k tokens | 0 |
| Sequential round-trips per lesson | 2 | 1 |

Estimated saving: ~95–100k tokens per 12-lesson chapter, plus the wall-clock of one
dependent round-trip per lesson.

Merging adds only the ~700 output tokens of quiz JSON to the writer's turn. Its input
cost is zero, because the fragment is already in that agent's context.

## Approach

Fold quiz generation into `nerdit-lesson-writer`. Both artifacts are written to disk by
the agent; the assembler picks them up. The orchestrator never holds lesson HTML or
question text.

Two agents remain:

| Agent | Job | Runs |
|---|---|---|
| `nerdit-lesson-writer` | Writes `<id>.html` and `<id>.quiz.json` | Once per lesson, in parallel |
| `nerdit-qa-validator` | Read-only checklist over the assembled output | Once, after assembly |

`agents/nerdit-quiz-writer.md` is deleted. Its question-quality rules move verbatim into
the lesson writer so there is exactly one copy and no drift.

### Rejected alternative

Returning the quiz JSON inline in the agent's reply (orchestrator writes `meta.json` as
today) was considered. It needs no assembler change, but keeps ~800 tokens/lesson of
question text flowing through the orchestrator's context — the cost scales with chapter
size, which is the thing this change exists to remove. Rejected.

## Component 1 — Merged agent contract

`nerdit-lesson-writer` gains a second output file and a second return line.

Return format, exactly two lines, nothing else:

```
FILE: <workdir>/<id>.html
QUIZ: <workdir>/<id>.quiz.json
```

`<id>.quiz.json` content is the current `nerdit-quiz-writer` output shape, unchanged:

```json
{
  "lessonQuestions": [
    { "correctOptionIndex": 0, "options": ["A", "B", "C", "D"], "text": "...?" }
  ],
  "assessmentQuestions": [
    { "correctOptionIndex": 0, "options": ["A", "B", "C", "D"], "text": "...?" }
  ]
}
```

Three questions per array. No `id` fields — the assembler still assigns every question id
so one session/batch pair covers the whole file.

### Ordering rule (quality guard)

The split pipeline gave one property for free: the quiz writer read the fragment **off
disk**, so questions were provably derived from what actually landed, not from what the
writer intended to produce. Merging loses that unless the ordering is made explicit.

The merged agent must proceed in this order, stated as a hard requirement in the agent
file:

1. Read the rulebook.
2. Compose and `Write` the HTML fragment to `HTML_PATH`.
3. Derive the 6 questions **from the fragment just written** — testing content that is
   actually present in it, never a planned-but-cut example, never a fact the fragment
   does not teach.
4. `Write` the quiz JSON to `QUIZ_PATH`.

The inherited question-quality rules stay as-is: 6 total split 3/3; assessment questions
test different facts and angles than the lesson set; all four options plausible; exactly
one correct option; question text a complete sentence ending in `?`; no verbatim reuse of
heading wording.

## Component 2 — Assembler (`scripts/assemble_course.py`)

`--meta` becomes optional. `build_course()` resolves each lesson's question data in this
order:

1. `<html-dir>/<id>.quiz.json` if present
2. else the matching `meta.json` entry, if a meta file was passed
3. else `{}` — empty question arrays, existing missing-content warning path

Only the meta lookup at `build_course()` changes: `meta_by_id.get(lid, {})` gains a
file-backed fallback that returns the same dict shape. Everything downstream —
`with_ids()`, the assessment-bank concatenation, `detect_assets()`, duration estimation,
the Firestore size report — reads that dict and is untouched.

Precedence is quiz-file-first so a re-run of a single lesson's writer takes effect
without needing `meta.json` regenerated. The `meta.json` branch exists only for
back-compat with workdirs produced before this change.

`m.get("duration")` keeps working: neither source populates it today, so it continues to
fall through to `estimate_duration(content)`.

## Component 3 — Orchestrator (`SKILL.md`)

- Multi-Agent Architecture table: drop the `nerdit-quiz-writer` row; update the
  `nerdit-lesson-writer` row to state both outputs.
- Delegation flow: merge steps 2 and 3 into one spawn; renumber.
- Step 2d ("Delegate 6 split `questions`"): deleted.
- Step 3 ("Write the meta.json Sidecar"): deleted. `id` and `title` reach the assembler
  from the input file, which it already reads.
- Step 4: drop `--meta` from the documented command line.
- Step 5 QA-failure path: a failure in either content or questions re-runs the merged
  writer, which regenerates both files, then re-assembles and re-validates.
- Reform mode: unchanged — `SOURCE_PATH` still goes to the same agent, which now also
  emits that lesson's quiz.

## Data flow

```
input JSON ──> orchestrator ──> N × nerdit-lesson-writer (parallel)
                                     │
                                     ├─> <workdir>/<id>.html
                                     └─> <workdir>/<id>.quiz.json
                                              │
input JSON ──────────────────────> assemble_course.py <┘
                                     │
                                     └─> course-<chapter>_output.json ──> nerdit-qa-validator
```

The orchestrator's per-lesson context cost is two short path strings.

## Error handling

- **Quiz file missing** (agent wrote HTML but not JSON): assembler falls through to empty
  arrays and the run continues. The existing per-lesson missing report gains a
  `WARNING missing quiz` line naming the lesson ids, matching the existing
  `WARNING missing HTML` behaviour. `nerdit-qa-validator` catches the consequence anyway —
  its `questions` length check fails — but the assembler warning names the cause directly.
- **Quiz file malformed** (invalid JSON, wrong shape): fail loudly with the lesson id and
  the path. A silently-dropped question set would assemble into a passing-looking file
  with a short assessment bank.
- **Both quiz.json and meta.json present:** quiz.json wins, no warning. This is the
  normal state of a workdir being re-run after the change.

## Testing

Existing suite: 17/17 passing. Additions to the assembler tests:

- `<id>.quiz.json` present → its questions land in the lesson and the assessment bank,
  with correctly stamped ids.
- quiz.json and meta.json both present → quiz.json wins.
- meta.json only, no quiz.json → back-compat path produces the pre-change output.
- neither present → empty arrays, `WARNING missing quiz`, exit 0, no crash.
- malformed quiz.json → non-zero exit, message names the lesson id and path.
- `--meta` omitted entirely → runs clean off quiz.json files alone.

No agent-behaviour tests — agent output quality stays covered by `nerdit-qa-validator`.

## Out of scope

- `nerdit-qa-validator` and its checklist: unchanged. It validates the assembled file and
  does not care how the questions got there.
- The rulebook, the CSS references, and the lesson skeleton: untouched.
- Answerability checking (verifying each question is answerable from the fragment) stays
  an agent-instruction concern, not a validator check — same as today.
