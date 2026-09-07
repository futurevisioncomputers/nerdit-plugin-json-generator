---
name: nerdit-chapter-generator
description: >
  Generates a structured NERDIT LMS course JSON for a chapter. Use this skill whenever
  a user uploads a `course-[chaptername]_input.json` file and wants to produce a
  corresponding `course-[chaptername]_output.json` — a full course object with
  course-level metadata, a top-level assessment question bank, per-lesson HTML content,
  durations, per-lesson quiz questions, and a `lessonIds` index. Trigger on any mention
  of: generating lesson content, NERDIT LMS, course JSON, chapter JSON, input structure
  JSON, nerdit-wrapper, nerdit lessons, or any request to convert a chapter input JSON
  into a course output JSON. Even if the user simply says "generate the lesson" or
  "process my input JSON", use this skill.
---

# NERDIT Chapter Content Generator

## Overview

This skill processes an uploaded `course-[chaptername]_input.json` file — a JSON array
of `{id, title, description}` lesson entries — and produces a `course-[chaptername]_output.json`
file: a single **course object** (not a bare array). For each lesson entry in the input, it
generates complete HTML lesson content styled with NERDIT LMS classes (targeting `css8.css`),
an estimated lesson duration, and 6 multiple-choice quiz questions derived from that lesson's
generated content — 3 of which live on the lesson itself and 3 of which feed the course's
top-level `assessment.questions` bank. Course-level fields outside of `lessons`/`lessonIds`/
`assessment.questions` are fixed defaults or current system-time timestamps — never derived
from the input.

---

## Multi-Agent Architecture

This skill is the **orchestrator**. It does not write lesson HTML or quiz questions itself —
it delegates to two specialized subagents (bundled in `agents/`) and assembles their output:

| Agent | Job | Runs |
|---|---|---|
| `nerdit-lesson-writer` | Writes one lesson's HTML fragment to `<workdir>/<id>.html`, its 6 MCQs to `<workdir>/<id>.quiz.json`, **and** its concept manifest to `<workdir>/<id>.concepts.json`; returns the three paths | Once per lesson, in parallel |
| `nerdit-qa-validator` | Read-only checklist pass over the script-assembled output file | Once, after assembly |

Why: each lesson's generation is independent and reference-heavy (the two reference files
alone are ~4,000 lines), so isolating each lesson in its own subagent context keeps quality
high and keeps this orchestrator's own context light regardless of chapter size. Generating
each lesson's questions in the same turn that wrote its HTML avoids re-reading the fragment
from disk in a second agent. Running lessons in parallel also cuts wall-clock time on
multi-lesson chapters.

**Delegation flow:**

1. Pre-flight and parse the input array (Step 1) and choose the run workdir (Step 6's
   destination).
2. Spawn one `nerdit-lesson-writer` agent per lesson. Independent lessons have no dependency
   on each other — launch them together in one batch of parallel Agent calls. Pass each agent:
   the lesson's `id`/`title`/`description`, the chapter name, whether this is a multi-lesson
   chapter (so it prefixes internal HTML ids), the lesson's **curriculum context** —
   `PRIOR_TOPICS` (title + description of every earlier lesson, in input order) and
   `UPCOMING_TOPICS` (title + description of every later lesson) — `HTML_PATH =
   <workdir>/<id>.html`, `QUIZ_PATH = <workdir>/<id>.quiz.json`, and
   `CONCEPTS_PATH = <workdir>/<id>.concepts.json`. Each returns only `FILE:`, `QUIZ:` and
   `CONCEPTS:` path lines — no file content ever enters your context. The curriculum context
   is static per lesson (computed from the input array alone), so it does not break the
   parallel batch.
3. Run `scripts/assemble_course.py` (Step 4) to build the full `course-<chapter>_output.json`
   from the input, the `<id>.html` files, and the `<id>.quiz.json` files. The script owns all
   course defaults, ids, timestamps, durations, and `assets`.
4. Run `scripts/check_sequence.py --strict` (Step 4b) — deterministic, zero tokens. Exit 2
   means a lesson reaches for a construct a later lesson owns: regenerate that lesson with
   the violation lines, re-assemble, re-check, and do not proceed until it exits 0.
5. Run `scripts/verify_course.py --contract v10` (Step 4c) — deterministic, zero tokens, and
   the gate that keeps the model from regenerating good lessons. Fix everything it reports
   before spawning QA; it is authoritative on every check it makes.
6. Spawn `nerdit-qa-validator` once against the assembled output file (Step 5) for the
   judgment-only checks the scripts cannot make. On a `FAIL` that is genuinely the agent's to
   own, re-run that lesson's `nerdit-lesson-writer` with the exact lines, re-assemble,
   re-verify. **At most 2 regeneration attempts per lesson** (Step 4c) — then stop and report.
   Then deliver (Step 6).

If the chapter has exactly one lesson, the parallelism in step 2 is moot but the same
delegation still applies — do not write lesson content directly in the orchestrator.

---

## Reference Files (authoritative — consult these at every step)

These two files are **bundled with this skill** in the `references/` directory. **Read them in full
before generating any content** — they are the single source of truth for every class name, block
structure, and formatting rule.

| File | Authority for |
|------|---------------|
| `references/CORE.md` | **The lesson rules, subject-agnostic.** Fixed skeleton, language rules, example units with mandatory outputs, predict/fill-blank practice, visual decision table, banned-component list, shared script helpers |
| `references/figures.md` | **The nine figure templates.** CORE.md §7 picks the shape; this file carries the exact SVG for it. Every lesson ships at least one figure — copy a template, swap the labels, never improvise an SVG when one fits |
| `references/runners/<runner>.md` | **One runner's markup contract.** `sql`, `python`, `excel`, `plot`. Exactly one is passed per lesson — see Step 2b |
| `references/css8.css` | The base NERDIT LMS stylesheet — class names, color tokens, design variables (v9 lessons use these base classes; `css9-simple.css` is additive on top). When in doubt about exact markup a class expects, grep this file |
| `references/css9-simple.css` | Additive v9 patch loaded after `css8.css` — defines `nerdit-syntax`, `nerdit-example`, `nerdit-output`, `nerdit-demo-table`, `nerdit-figure`, `nerdit-predict`, `nerdit-fillblank`, `nerdit-tryit`, and the Excel widgets |
| `references/nerdit-excel-engine.js` | Formula evaluator, sheet renderer, and pivot builder for Excel lessons. Ship it alongside the lesson HTML (Excel has no embeddable engine like sql.js or Pyodide) |
| `references/nerdit-plot-runner.js` | Runs Matplotlib via Pyodide and renders the resulting figure. Ship it alongside data-visualization lesson HTML |

### Lesson style

Every lesson follows `CORE.md` — wrapper `nerdit-wrapper nerdit-simple`.
It is the only style.

More reference files live in the same `references/` directory and are the **authoritative
schema example** for this skill's output — study them before assembling (Step 4):

| File | Authority for |
|------|---------------|
| `references/course-introduction-to-langchain-and-llm-applications_input.json` | Exact input schema — array of `{id, title, description}` |
| `references/course-introduction-to-langchain-and-llm-applications_output.json` | Exact output schema — course-level field set and order, `assessment` shape, per-lesson field set and order, `lessonIds` |
| `references/course-sample-mixed_input.json` | The optional `runner` field in use — one chapter mixing all four runners (`sql`, `python`, `excel`, `plot`) across its lessons |
| `references/course-sample-mixed_output.json` | Proof the `runner` field never reaches the output, and the correct root-relative `assets` URL for each of the four engines |

If the user attaches their own sample input/output pair for the current chapter, prefer those
for field ordering/tone, but the bundled reference pair remains the schema source of truth.

> **The reference outputs are a schema model, not a teaching model.** The LangChain
> reference was generated before the sequencing rule existed, and its lesson 1 demonstrates
> `LLMChain` — which lesson 8 teaches. Copy its field shapes; never copy its habit of
> reaching forward for a construct. `scripts/check_sequence.py` reports that exact defect
> on it, on purpose.

**`CORE.md` is the single source of truth** for what a lesson may and may not contain.
A runner fragment adds one widget contract on top of it and overrides nothing.

---

## Converting an old course to v9 (optional — reform)

To rebuild an existing `*_output.json` in v9 (reshape the old material, not regenerate blind),
run the converter first, then the normal pipeline in reform mode:

1. `python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/input_from_output.py"
   --in <old_output.json> --workdir <workdir> [--chapter <slug>]` → writes
   `course-<chapter>_input.json` and `<workdir>/_src/<id>.html` (each old lesson's HTML).
2. Run Steps 1–6 on that input, but pass each `nerdit-lesson-writer` its
   `SOURCE_PATH = <workdir>/_src/<id>.html` so it reshapes the old material into v9.
3. A lesson whose old content was empty has no usable source — generate it fresh (omit `SOURCE_PATH`).

For a brand-new course (no old JSON), skip this section and start at Step 1.

## Step 1 — Detect and Read the Input File

1. Look for the uploaded file matching the pattern `course-[chaptername]_input.json`.
   - The `[chaptername]` token is a variable slug (e.g., `numpy-fundamentals`,
     `introduction-to-langchain-and-llm-applications`). Extract it from the filename by
     stripping the `course-` prefix and `_input.json` suffix.
   - If the user's file uses the older `input_[chaptername]_structure.json` naming, still
     process it the same way — extract `[chaptername]` and proceed; the *output* must still
     use the new `course-[chaptername]_output.json` naming and course-object schema below.
2. Parse the file as a JSON array. Each element is a lesson object with the fields:
   - `id` — unique lesson identifier string
   - `title` — lesson title string
   - `description` — short lesson description string
   - `runner` — *optional*. One of `sql`, `python`, `excel`, `plot`, `none`. Selects the
     runner fragment passed to that lesson's writer. Generation context only: it is never
     copied into the output, and the assembler ignores it.
3. Resolve the runner for every lesson before spawning anything.
   - If `runner` is absent on some or all lessons, infer it from the chapter name and the
     lesson descriptions, then **print your per-lesson choice and get the user's
     confirmation before spawning any agent.** Inference costs nothing; twelve
     wrongly-generated lessons cost a full run.
   - If a `runner` value is not one of the five listed above, stop and show the valid
     values. Do **not** fall back to `none` — that would silently produce a whole chapter
     with no practice widgets.
4. **The array order is the course order** — lesson 1 is taught first, and a learner reaching
   lesson N has seen lessons 1..N only. Everything downstream depends on this, so before
   spawning anything, read the titles in order and check the syllabus builds up: does any
   lesson's subject depend on a topic that only appears *later* (a project lesson before the
   feature it uses, conditions after loops)? If so, list the inversions and ask the user
   whether to reorder the input. Never reorder it yourself — the order is theirs, and lesson
   ids often encode it.
5. Run the input pre-flight before generating anything:

       python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/check_input.py" \
         --input <path to the input JSON>

   `ERROR` lines mean the input cannot produce good lessons — most often a `description`
   that repeats its `title` verbatim, which leaves the writer nothing to expand and leaves
   Step 4b guessing who owns each concept. Show them to the user and agree on real
   descriptions before spawning any writer. `WARN` lines are advisory.
6. Ask the user what the course assumes learners already know (e.g. "basic Python syntax",
   "SQL SELECT"). Keep the list — it becomes `--allow` in Step 4b. Without it, lesson 1 is
   checked against an empty world and legitimate prerequisite vocabulary reads as a forward
   reference. If the user has no answer, use an empty allowlist and say so.
7. If the file cannot be found or parsed, notify the user and stop.

---

## Step 2 — Generate Content for Each Lesson (delegated)

> **Timestamps + ids are the assembler script's job** (Step 4), not yours. Do not capture or
> pass `COURSE_TS` / `QID_SESSION_TS` / `QID_BATCH_TS`. `assemble_course.py` generates one
> consistent set at assembly time, so the course `id` suffix, `createdAt`/`updatedAt`, and every
> question id share the same session/batch pair by construction.

**Workdir:** decide the output directory up front (ask the user per Step 6's destination rules —
never the plugin folder). Every `<id>.html`, `<id>.quiz.json`, and the final output JSON live there.

Process every lesson object in the input array. For each lesson:

### 2a. Preserve source metadata (copy exactly — no changes, no reformatting)

```
lesson.id    = input.id
lesson.title = input.title
```

`input.description` is **not** copied into the output lesson object (the new schema has no
per-lesson `description` field) — pass it to `nerdit-lesson-writer` as generation context only,
the same way `title` is used to inform content, but it does not appear in the assembled output.

### 2b. Delegate the lesson to `nerdit-lesson-writer`

Do not generate the HTML lesson yourself. Spawn the `nerdit-lesson-writer` agent for this
lesson (in parallel with the other lessons' agents — see Multi-Agent Architecture above),
passing it: `id`, `title`, `description`, chapter name, whether this is a multi-lesson chapter,
`RUNNER` (the value resolved in Step 1), `PRIOR_TOPICS` + `UPCOMING_TOPICS` (the curriculum
context — see below), `HTML_PATH = <workdir>/<id>.html`,
`QUIZ_PATH = <workdir>/<id>.quiz.json`, and
`CONCEPTS_PATH = <workdir>/<id>.concepts.json`.

The writer returns three path lines (`FILE:`, `QUIZ:`, `CONCEPTS:`). Read none of the files
back into your context: the assembler consumes the first two in Step 4, and
`check_sequence.py` consumes the manifests in Step 4b.

**Curriculum context (mandatory — this is what keeps lesson N from using lesson N+1's
concepts):** the input array order **is** the course order. For lesson at index `i`, build:

- `PRIOR_TOPICS` — the `title` + `description` of every lesson at index `< i`, in order
  (empty for the first lesson)
- `UPCOMING_TOPICS` — the `title` + `description` of every lesson at index `> i`

Include both lists verbatim in the agent prompt. The writer treats `PRIOR_TOPICS` + its
own lesson as the learner's entire knowledge and must not put any `UPCOMING_TOPICS`-owned
construct in code — e.g. no loops inside the conditions lesson, no `LLMChain` inside the
prompt-templates lesson. Never spawn a writer without these two lists on a multi-lesson
chapter.

Before spawning, confirm `references/runners/<RUNNER>.md` exists on disk (skip this check when
`RUNNER` is `none`). If it does not, stop — an agent that proceeds without its fragment emits a
Try It block whose handler does not exist.

The agent owns
every content rule (skeleton, language, example/output, Try It, banned components, HTML hygiene)
and every question rule — see `agents/nerdit-lesson-writer.md`. It **writes the fragment to
`HTML_PATH`, the 6 questions to `QUIZ_PATH`, and the concept manifest to `CONCEPTS_PATH`**,
then returns only its three path lines. Duration is computed later by the assembler, and
question ids are assigned by it.

The quiz file holds two 3-item arrays, **without ids**:

- `lessonQuestions` — 3 questions, each `{text, options[4], correctOptionIndex}`
- `assessmentQuestions` — 3 *different* questions (not restatements of the lesson set), same shape

The concepts file holds two string arrays:

- `teaches` — the terms this lesson defines or introduces (5–20)
- `uses` — terms it leans on without defining; every one must come from this lesson or an
  earlier one

The manifest is what makes Step 4b's ownership a declared fact instead of a guess from the
title and description, and it is the only way a *prose-level* forward reference is caught —
a lesson that explains embeddings three lessons early has no telltale code to scan.

---

## Step 3 — (removed)

The `meta.json` sidecar is gone: `nerdit-lesson-writer` writes each lesson's questions
straight to `<workdir>/<id>.quiz.json`, and `id`/`title` reach the assembler from the input
file it already reads. Nothing to do here — go to Step 4.

`description` remains generation context only — it is passed to the agent but never appears in
the assembled output.

---

## Step 4 — Assemble the Output JSON (deterministic script)

Run the bundled assembler via Bash. It reads the input file, every `<workdir>/<id>.html`, and
every `<workdir>/<id>.quiz.json`, then writes the full course object — course-level fixed defaults, `id` +
`createdAt`/`updatedAt` from one timestamp, all question ids (one shared session/batch pair),
per-lesson `content` + computed `duration` + engine `assets`, the `assessment` bank (all
`assessmentQuestions` concatenated in lesson order, `passingScore` 70, `examQuestionCount` 20),
and `lessonIds`:

    python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/assemble_course.py" \
      --chapter <chaptername> \
      --input   <path to the input JSON> \
      --html-dir <workdir> \
      --out     <workdir>/course-<chaptername>_output.json

You own none of the schema details — they live in the script and are checked in Step 5. If the
script prints `WARNING missing HTML` or `WARNING missing quiz`, that lesson's agent failed to
write one of its two files: re-run that lesson's `nerdit-lesson-writer`, then re-run the script.
If it exits 2 with an `ERROR:` naming a lesson and a `.quiz.json` path, that file is malformed —
re-run that lesson's agent and re-assemble.

The script also prints the assembled **Firestore document size**. The whole course object is
stored in a single Firestore document (hard cap 1,048,576 bytes). If it prints a size `WARNING`
(over the ~1 MB budget), **surface that to the user** and recommend splitting the chapter into
fewer lessons — the report lists the heaviest lessons. Pass `--strict` to make the script fail
the run instead of warning.

---

## Step 4b — Check Concept Sequencing (deterministic script, blocking)

Run the sequencing checker on the assembled file before spawning QA:

    python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/check_sequence.py" \
      --input        <path to the input JSON> \
      --course       <workdir>/course-<chaptername>_output.json \
      --concepts-dir <workdir> \
      --allow        "<the Step 1 assumed-knowledge list, comma separated>" \
      --strict

It compares each lesson's **code blocks** and its manifest's declared `uses` against the
terms later lessons own (declared `teaches` first, then named APIs from any lesson's
title/description, then language constructs from titles) and prints one line per violation:

    lesson 07 prompt-templates-07: uses 'LLMChain' -- first taught in lesson 08 "Chains and Sequential Workflows"

**Exit 2 means the run is not deliverable.** Every violation is a learner meeting a
construct before the lesson that teaches it. For each reported lesson:

1. Re-run that lesson's `nerdit-lesson-writer` (Step 2) with a `VIOLATIONS` block holding
   that lesson's exact report lines. It regenerates all three files.
2. Re-run the assembler (Step 4).
3. Re-run this check.

Repeat until it exits 0. Do not continue to Step 5 with known violations, and never deliver
a course that has not passed this check exit-0.

Do **not** "fix" a violation by reordering the input — the order is the user's syllabus. If
a violation is genuinely a syllabus problem rather than a lesson defect (the construct
cannot be avoided at that point — an auth lesson that must raise an error before the
error-handling lesson), stop and tell the user which lesson should move, with the report
lines as evidence. Reordering is their decision, and lesson `id` values stay unchanged when
they do it: ids are referenced by learner progress records.

The check is still a floor, not a ceiling: it only names terms it can recognise
mechanically or that a writer declared. Conceptual leaks past both are the QA agent's job
in Step 5. It costs zero model tokens — always run it.

---

## Step 4c — Verify Deterministically (script, blocking, zero tokens)

Run the course verifier on the assembled file **before** spawning the QA agent:

    python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/verify_course.py"       --input    <path to the input JSON>       --output   <workdir>/course-<chaptername>_output.json       --contract v10

Exit 0 = every mechanical check passed. Exit 1 = at least one failed, one line each.

**This step exists to stop needless regeneration.** Roughly three quarters of the Step 5
checklist is decidable by reading the JSON or walking the DOM — field literals, id formats,
counts, timestamps, banned and retired components, `<pre>`/output pairing, a Try It per
section, unique element ids, cheatsheet markup, figures, the SVG contract, hex colours. A
script decides those in milliseconds and is never wrong about them. A model asked to eyeball
the same list produces confident false failures — on 2026-09-05 it invented an `assets` rule
this plugin's own reference output contradicts, and called correct cheatsheet markup broken.
Every one of those false failures used to trigger a full lesson regeneration.

So: fix what this reports first, and only then spawn QA. The agent then sees a file that
already clears the mechanical bar, and has far less surface on which to be wrong.

**The script is authoritative on everything it checks.** If Step 5's agent reports a failure
on an item listed in this script's output contract, the agent is wrong — do not regenerate.
Say so in one line and move on.

### Regeneration budget (applies to 4b, 4c and 5)

Re-running a `nerdit-lesson-writer` regenerates **all three** of that lesson's files, so a
single wrong question id rewrites content that was fine. Keep it bounded:

- **At most 2 regeneration attempts per lesson per run.** Count them.
- Pass the exact failure lines into the retry, never a paraphrase — a writer told "fix the
  quiz" rewrites the lesson; one told `qid does not match lesson-<SESSION>-<id>-qN-<BATCH>`
  fixes the ids.
- On a third failure for the same lesson, **stop**. Report the lesson, the failing lines, and
  what was tried. A writer that has missed the same check twice will miss it a third time,
  and the user would rather see the defect than pay for another round.
- Never regenerate a lesson that is not itself named in a failure line. A course-level
  failure (a bad count, a timestamp mismatch) is the assembler's business, not a writer's —
  re-run Step 4, not Step 2.

### Re-running this skill on an existing workdir

If `<workdir>/<id>.html`, `<id>.quiz.json` and `<id>.concepts.json` all already exist for a
lesson, **do not spawn a writer for it.** Re-assemble (Step 4) and re-run 4b/4c: a lesson
that passes needs nothing, and a lesson that fails will be named. Regenerating a chapter's
worth of passing lessons to fix one is the single most expensive mistake this pipeline can
make. Say which lessons were reused and which were written fresh.

---

## Step 5 — Validate What Only Judgment Can Check (delegated)

Step 4c has already decided everything mechanical. Spawn `nerdit-qa-validator` against the
assembled `<workdir>/course-<chaptername>_output.json` for the rest — the checks that need a
reader, not a parser. Always pass the input JSON path (it needs lesson order) and the
`<workdir>` (for each lesson's `<id>.concepts.json`).

What the agent owns, and nothing else:

- [ ] Each numbered `<h2>` section teaches **exactly one** concept — not two smuggled into one
- [ ] Language: sentences ≤ ~15 words, ≤3 per paragraph, second person, no undefined jargon
- [ ] **Conceptual** sequencing leaks that `check_sequence.py` cannot name mechanically — an
      idea used before the lesson that explains it, where no shared term gives it away
- [ ] The preset is respected and consistent across the chapter (CORE.md §2b)
- [ ] **(Excel)** Every documented formula output actually evaluates to the stated value
      against `nerdit-excel-engine.js` — a worked example claiming `301300` must produce it
- [ ] **(data-viz)** Every documented chart description matches what the code really renders
- [ ] Each figure teaches the thing its caption claims, and the caption is true of the picture
- [ ] Quiz questions are answerable from the lesson, and a lesson's `assessmentQuestions` test
      the same material as its `lessonQuestions` without restating them verbatim
- [ ] The concept manifest's `teaches`/`uses` honestly describe the lesson

**Do not re-check anything in Step 4c's contract.** Field literals, id formats, counts,
timestamps, banned/retired components, `<pre>`/output pairing, Try It presence, unique ids,
cheatsheet markup, figure wrappers, the SVG contract, hex colours — the script has already
decided those and is authoritative. A `FAIL` from this agent on one of them is a false
positive: note it in one line, do not regenerate.

On a genuine failure, re-run that lesson's `nerdit-lesson-writer` with the exact reported
lines, re-assemble (Step 4), and re-run 4b and 4c before validating again. Respect the
2-attempt budget in Step 4c. Then deliver (Step 6).

---

## Step 6 — Deliver Output File

One file is produced and delivered per run: the output JSON the assembler wrote in Step 4.

> **Never write output into this plugin's own folder** (the `nerdit-chapter-generator` skill
> directory, its `references/`, or anywhere under the plugin install). The plugin folder is
> read-only source — do not add generated files to it.
>
> **Decide the destination with the user — do not pick a location on your own:**
> 1. First ask the user where to save the output file (a directory path they choose), and
>    write it there.
> 2. If the user has no preference or wants a quick preview, offer to **display the output and
>    provide a download** instead of writing to disk — render the JSON as a downloadable
>    Artifact / file the user can save wherever they like.
> 3. Only fall back to a session scratch/temp directory (never the plugin folder) if the user
>    explicitly declines both — and tell them the exact path you used.

### 6a. Output JSON file

1. Determine the chapter name from the input filename
   (e.g., `course-numpy-fundamentals_input.json` → chapter name is `numpy-fundamentals`).
2. Name the output JSON file: `course-[chaptername]_output.json`
   (e.g., `course-numpy-fundamentals_output.json`).
3. Save it to the user-chosen destination from the Step 6 destination preamble above (or present it for
   download). Do not hard-code a path, and do not write it into the plugin folder.

### 6b. Deliver the file

Deliver the file by the method chosen with the user in the Step 6 destination preamble:

- **User picked a destination** → confirm the file is written there and print the full
  path so the user can locate it.
- **User wanted preview/download** → present the file for download (e.g. as a downloadable
  Artifact / attachment) without writing it to the plugin folder.

On a hosted environment that provides `present_files`, call it with the saved file path so
the user can download it. On the CLI, just report the destination path (or provide the
downloadable file).

After delivering, provide a brief summary listing:
- Number of lessons processed
- Lesson titles generated
- Total question counts (lesson-level total and `assessment.questions` total)
- Any notable decisions made (e.g., which visualization type was chosen per lesson)

---

## Multi-Lesson Handling

When the input JSON array contains multiple lesson objects, process them all in sequence.
Each lesson is independent — generate a full lesson for each one. The `lessons` array must
contain all lessons in the same order as the input, and `lessonIds` must mirror that order.

For multi-lesson inputs, assign unique `id` values to all chart canvas elements and tab
content `div`s across all generated lessons (not just within each lesson), so if the
frontend ever renders multiple lessons on one page, there are no ID collisions.
A safe pattern: prefix canvas IDs with a slug of the lesson `id` field.

---

## Content Quality Standards

- Write at the level of a skilled technical educator — clear, precise, pedagogically sound.
- Start from foundational concepts, build to advanced topics within each lesson.
- Explanations must be in real prose paragraphs, not bare bullet lists.
- Code examples must be syntactically correct and runnable where possible.
- Every lesson must feel complete — a learner should be able to study it standalone.
- The course order is a contract: a lesson may use only concepts it or an earlier lesson
  taught. Constructs owned by later lessons never appear in code; at most one prose
  "You will learn X in a later lesson" mention is allowed.
- Do not repeat the same boilerplate structure for every lesson; adapt sections to suit
  the specific lesson's natural learning flow.
- Every one of the 6 questions generated per lesson (3 lesson-level + 3 assessment-level)
  must be answerable from that lesson's own generated `content` — never from the input
  `description` alone, and never invented.
