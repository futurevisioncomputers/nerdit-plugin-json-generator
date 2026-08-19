# nerdit_plugin-jdon-generator

Claude Code plugin that generates a full NERDIT LMS course JSON — course-level metadata, a
top-level assessment question bank, per-lesson HTML body, duration estimate, and per-lesson
quiz questions — from `course-[chaptername]_input.json` files.

## Architecture

Multi-agent, **file-based**. The `nerdit-chapter-generator` skill is the orchestrator; it never
writes lesson HTML or quiz questions itself, and it never holds either in its context. It
delegates to two subagents and assembles the final JSON with a bundled Python script:

| Agent | Job |
|---|---|
| [`nerdit-lesson-writer`](agents/nerdit-lesson-writer.md) | **Writes** one lesson's HTML fragment to `<workdir>/<id>.html` and its 6 MCQs to `<workdir>/<id>.quiz.json` — split 3 (lesson's own `questions`) + 3 (course `assessment.questions`), no ids; returns only the two paths. Run in parallel across lessons |
| [`nerdit-qa-validator`](agents/nerdit-qa-validator.md) | Read-only checklist pass over the script-assembled output file before delivery |

Questions are generated in the same agent turn that wrote the lesson, from the fragment it just
wrote — no second agent re-reads the HTML off disk to derive them.

The orchestrator then runs
[`skills/nerdit-chapter-generator/scripts/assemble_course.py`](skills/nerdit-chapter-generator/scripts/assemble_course.py),
which reads the `<id>.html` and `<id>.quiz.json` files and builds the full course object — course
defaults, `id`/timestamps, all question ids (one session/batch pair), per-lesson `content` +
computed `duration` + engine `assets`, the `assessment` bank, and `lessonIds` —
**deterministically, with zero model tokens for the HTML payload**. This keeps the biggest payload
(lesson HTML) out of the model's output and context entirely; only lesson content and quiz text
still require the LLM.

### Concept sequencing

Each lesson is written by its own isolated agent, which by itself cannot know what the other
lessons teach — so a lesson would happily demonstrate a `for` loop before the loops lesson, or
`LLMChain` seven lessons before chains. Four layers prevent that, cheapest first:

- **Pre-flight.** [`scripts/check_input.py`](skills/nerdit-chapter-generator/scripts/check_input.py)
  refuses inputs that cannot produce good lessons — most importantly a `description` that just
  repeats its `title`, which leaves the writer nothing to expand and leaves ownership detection
  guessing. Observed in the wild on two live courses.
- **Curriculum context.** The orchestrator passes every writer `PRIOR_TOPICS` (all earlier
  lessons) and `UPCOMING_TOPICS` (all later ones). The writer may use only what the learner has
  already met; a later lesson's construct may be named once in prose, never in code.
- **Declaration.** Each writer also emits `<id>.concepts.json` — the terms it `teaches` and the
  terms it `uses` without defining. That turns "which lesson owns `DataFrame`?" from a regex
  guess into a recorded fact, and it is the only way a *prose-level* forward reference gets
  caught: a lesson explaining embeddings three lessons early has no code to scan.
- **Blocking gate.** [`scripts/check_sequence.py`](skills/nerdit-chapter-generator/scripts/check_sequence.py)
  re-checks the assembled JSON deterministically (zero model tokens), scanning code blocks and
  declared `uses` against the manifests, the named APIs, and the language constructs later
  lessons own. Run with `--strict` it fails the build; the orchestrator then feeds the exact
  violation lines back to the offending lesson's writer and re-assembles until it passes.
  `--allow` carries the course's assumed prior knowledge so lesson 1 is not judged against an
  empty world. The QA agent covers conceptual leaks past all of it.

See [skills/nerdit-chapter-generator/SKILL.md](skills/nerdit-chapter-generator/SKILL.md) for
the full orchestration flow, and
[skills/nerdit-chapter-generator/references/](skills/nerdit-chapter-generator/references/)
for the NERDIT component catalogue (`CORE.md`, plus one fragment per runner in `runners/`) and
stylesheets (`css8.css` + `css9-simple.css`) the agents read as their source of truth. A lesson
writer reads `CORE.md` and exactly one runner fragment, so adding a new runner costs every other
lesson nothing.

## Install

Add this repo as a marketplace, then install the plugin:

```
/plugin marketplace add futurevisioncomputers/nerdit-plugin-json-generator
/plugin install nerdit_try_plugin
```

Or point Claude Code at a local clone:

```
/plugin marketplace add /path/to/nerdit_plugin
/plugin install nerdit_try_plugin
```

## Use

Upload a `course-[chaptername]_input.json` file (array of `{id, title, description}`
lesson objects) and ask Claude to generate the lesson. The skill triggers automatically on
mentions of NERDIT LMS chapter/lesson generation. Output:

- `course-[chaptername]_output.json` — a single course object: course-level metadata,
  `assessment.questions` (3 per lesson, `3 × lessons` total), `lessons` (each with its own
  `content`, `duration`, `questions`, and optional `assets`), and a `lessonIds` index
- per lesson in the workdir, the two intermediates the assembler consumes: `<id>.html` (embedded
  as that lesson's `content`) and `<id>.quiz.json` (its 6 questions)

## Convert an old course to v9

To rebuild an existing `*_output.json` (an old v8 course) in the v9 style, run the converter,
then the normal generation in **reform** mode:

```
python skills/nerdit-chapter-generator/scripts/input_from_output.py \
  --in <old_output.json> --workdir <dir> [--chapter <slug>]
```

It writes `course-<chapter>_input.json` plus `<dir>/_src/<id>.html` (each old lesson's HTML). Then
generate as usual, passing each `nerdit-lesson-writer` its `SOURCE_PATH = <dir>/_src/<id>.html` — it
reshapes the old teaching into the v9 skeleton instead of writing from scratch. Lessons whose old
content was empty are generated fresh.

## License

MIT — see [LICENSE](LICENSE).
