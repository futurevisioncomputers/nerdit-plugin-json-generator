# nerdit_plugin-jdon-generator

Claude Code plugin that generates a full NERDIT LMS course JSON — course-level metadata, a
top-level assessment question bank, per-lesson HTML body, duration estimate, and per-lesson
quiz questions — from `course-[chaptername]_input.json` files.

## Architecture

Multi-agent, **file-based**. The `nerdit-chapter-generator` skill is the orchestrator; it never
writes lesson HTML or quiz questions itself, and it never holds lesson HTML in its context. It
delegates to three subagents and assembles the final JSON with a bundled Python script:

| Agent | Job |
|---|---|
| [`nerdit-lesson-writer`](agents/nerdit-lesson-writer.md) | **Writes** one lesson's HTML fragment to `<workdir>/<id>.html`; returns only the path. Run in parallel across lessons |
| [`nerdit-quiz-writer`](agents/nerdit-quiz-writer.md) | **Reads** that lesson's `<id>.html` and derives 6 MCQs, split 3 (lesson's own `questions`) + 3 (course `assessment.questions`), no ids |
| [`nerdit-qa-validator`](agents/nerdit-qa-validator.md) | Read-only checklist pass over the script-assembled output file before delivery |

The orchestrator then writes a small `meta.json` (per-lesson id/title/questions) and runs
[`skills/nerdit-chapter-generator/scripts/assemble_course.py`](skills/nerdit-chapter-generator/scripts/assemble_course.py),
which reads the HTML files + `meta.json` and builds the full course object — course defaults,
`id`/timestamps, all question ids (one session/batch pair), per-lesson `content` + computed
`duration` + engine `assets`, the `assessment` bank, and `lessonIds` — **deterministically, with
zero model tokens for the HTML payload**. This keeps the biggest payload (lesson HTML) out of the
model's output and context entirely; only lesson content and quiz text still require the LLM.

See [skills/nerdit-chapter-generator/SKILL.md](skills/nerdit-chapter-generator/SKILL.md) for
the full orchestration flow, and
[skills/nerdit-chapter-generator/references/](skills/nerdit-chapter-generator/references/)
for the NERDIT component catalogue (`NERDIT_LESSON_PROMPT_v9_simple.md`) and stylesheets (`css8.css` + `css9-simple.css`)
the agents read as their source of truth.

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
- one `<id>.html` per lesson in the workdir (the intermediate the assembler embeds) plus a small
  `meta.json` questions sidecar

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
