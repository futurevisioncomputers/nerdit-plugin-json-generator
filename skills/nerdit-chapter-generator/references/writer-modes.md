# Lesson-writer modes: reform and refresh

Read this file only when the orchestrator passes `SOURCE_PATH` (an old lesson's HTML).
With `REFRESH` too, follow Refresh mode; without it, follow Reform mode. Every rule in
`agents/nerdit-lesson-writer.md` still applies.

## Reform mode (optional — converting an old lesson)

If the orchestrator passes a `SOURCE_PATH` (an old lesson's HTML), **Read it first** and reshape
its teaching into the v9 skeleton above — do not generate from the title alone:
- Keep the real material: explanations, code, examples, data, numbers.
- Drop v10-banned components (card/stat grids, dashboards, CSS/gauge/donut charts, callout bands)
  **and the retired example box** — an old lesson's `nerdit-example` blocks are rewritten as run
  lines, not carried over. Reform mode flattens; it never preserves the old nesting.
- Add what v10 requires and the source lacks: a run line per code block (`nerdit-runhead` +
  2–3 sentences + `nerdit-run`), one Try It per concept, plain-language rewrite
  (≤20-word sentences, one concept per section, the idea explained before the case study).
- Sequencing rule still applies: an old example using a construct an `UPCOMING_TOPICS`
  lesson owns → rewrite that example with taught constructs, keeping what it teaches.
- Do not invent facts the source never taught.

When no `SOURCE_PATH` is given, generate normally from `id` / `title` / `description`.

## Refresh mode (optional — improving a finished lesson)

If the orchestrator passes `SOURCE_PATH` **and** `REFRESH` (a list from `figures`, `sql-layout`,
`trim`, `concise`, `programs`, `readability`, `video-only`), you are not rewriting the lesson. Copy `SOURCE_PATH` and change only what `REFRESH` names:

- `figures` — redraw figures that break figures.md R10–R13 or have a better template, with their
  captions and reading steps. Remove a text map (`nerdit-map`) a figure now covers; never keep
  both (figures.md R13). If prose leaned on the map's wording, put that wording on the figure
  as labels, such as `&gt; 10:00 left out`, so the prose still has its referent. Reading steps
  describe only what the new figure draws, in the learner's terms, never SVG units. Add
  `data-visual` to every figure. Replace a hand-made walkthrough image (`<img>` of an app
  screen) with a `nerdit-screen` spec built from the lesson's own words and data, and add
  `nerdit-screen` or `nerdit-scene` specs where a click-path or scene needs a picture
  (figures.md §16–17). Every word a screen shows must already be in the prose: you may not add
  prose to make a spec pass, so choose what the screen shows from what the lesson says.
- `sql-layout` — re-lay out SQL in run lines and Try Its to runners/sql.md §Layout. Whitespace
  only: no token may change.
- `trim` — shorten shown code to the CORE.md §4 limits by moving repeated setup into the seed.
  The seed holds only tables and listed rows (`CREATE TABLE` with columns, `INSERT … VALUES`).
  Never seed a view, a trigger or a computed table (`CREATE TABLE … AS`, `INSERT … SELECT`): a
  CTE's name lasts one statement, so code that reuses a seeded name works through logic the
  learner never reads. Never hide the step the section teaches; if the code still runs long,
  keep it and accept the density warning. Every shown output must still be exactly what SQLite returns. A
  run-line heading and its one-sentence lead may change to match. The lead names only what the
  shown code does, and does not say "view" or "helper" before the course has taught views.
- `concise` — shorten the prose to this file's section rules: 120–220 words per concept section,
  the run line by the section's third paragraph, a code walk (`ol.nerdit-codewalk`) after each
  run line, each idea said once, the course setup said once, standards and production asides
  moved into a Go deeper box. Move the run line up instead of rewriting it. Every fact, number
  and name you keep must already be in the source; drop sentences, never invent new ones. Every
  code block, output and seed stays character for character; run-line leads and Try It
  prompts may be shortened. Keep the Try It answers true to the unchanged code. Use Edit on the
  copied file, one edit per change.
- `programs` — add the programs CORE.md §4 asks for: where a section fakes the runtime
  (`test_request_context`, `MultiDict`, `meta={"csrf": False}`) or only works inside a running
  app, add the whole file as a `nerdit-program` with its `nerdit-check` and full walk; in a data
  lesson whose examples build on each other, add "The whole script" at the end of the last
  concept section. Existing run lines, outputs and seeds stay character for character. Gate with
  `--modes programs` so the walk and program rules are strict.
- `video-only` — change nothing in the lesson's three files; only write its video part
  (`VIDEO_PATH`, below) for a lesson that was delivered without one.
- `readability` — apply CORE.md's case-study and highlight rules to the prose: keep a case study
  only where the course world adds a decision or real numbers (turn the others into plain worked
  examples with no world names), and add `<b>` scan highlights, 1–2 per explanation paragraph.
  Code, outputs and seeds stay character for character. Facts, numbers and names you keep must
  already be in the source.

Everything else stays exactly as it is: headings, prose (unless `concise` or `readability`), Try It prompts, the cheat sheet, the
quiz file and the concept manifest (except its `visuals` list). `check_refresh.py` compares your
files with the originals and rejects any other change. Write the quiz and concept files back
unchanged.
