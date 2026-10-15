# Teaching visuals v11 and Data Modelling course remediation — design

Date: 2026-10-15. Status: draft for review.

## Goal

1. Make lesson visuals and code easier for a first-time learner to read: data shown as real tables,
   invisible values (spaces, NULL) made visible, the surprising cell highlighted, each idea shown
   once, and SQL laid out so it never wraps mid-statement.
2. Write those rules into the plugin, together with checks that fail when a lesson breaks them, so
   every new course gets them without anyone remembering.
3. Repair the live course *Data Modelling, ETL & Data Warehousing for Analysts*
   (<https://nerdit.in/course/data-modelling-etl-data-warehousing-for-analysts-1791872050976>)
   through the plugin pipeline only.

## Why

Evidence gathered on 2026-10-15:

- **Lessons 13–16 never went through the plugin.** They were built on 2026-10-10 by a one-off
  script (`.nerdit_dw_last.py`) that opened `CORE.md`, `figures.md` and `runners/sql.md` but never
  used their text. Result: 18 SQL outputs that do not match what SQLite returns plus 2 unchecked
  (`rollout/PROGRESS.md`), crammed SQL (17–52 lines per lesson with no space after commas), the
  run-line "why" text repeated as the next paragraph, and one 640-wide figure per lesson (the 4
  remaining `verify_course.py --contract v10` failures).
- **Long SQL lines wrap mid-statement.** The input half of a run line wraps instead of scrolling
  (`css9-simple.css`, added 2026-10-13). Lines over 60 characters: 0–34 per lesson in 01–12,
  13–80 in 13–16.
- **Figures encode tables as dotted strings.** For example `row 1 · 09:00 · 10000` makes the
  learner work out which value belongs to which column. Spaces are shown as `[ Aarav ]`, so the
  brackets look like data. The CAST trap cells look as neutral as the correct ones. The
  reconciliation and quarantine figures state the rule but do not show which row failed which
  check.
- **The same facts are shown three times.** Lesson 10 section 1 has a text map, a figure and
  numbered steps that all restate the same three timestamps.
- **The figure set has no shape for time windows, per-row checks or parts that sum.** Writers
  force these into the sequence and before/after templates.
- **Lessons are code-heavy for an analyst audience.** Shown code lines per lesson: 24–65 in most,
  113–158 in 08, 10, 11, 12 and 16. Some of it is repetition (lesson 10 shows the same load block
  twice).
- **The static preview did not match the site.** Code colours come from `lessonHighlight.ts`
  on the website. The preview built by `rollout/build_preview.py` has no highlighter, so
  reviewers saw plain text.
- **Gate and preview scripts lived outside the plugin** (`rollout/gate.py`,
  `rollout/build_preview.py`, `rollout/merge_final.py`), untested and specific to one course.

A comparison sample built from lesson 08 (`nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/samples/compare-lesson08.html`)
shows the current figures beside the proposed ones. The user approved the proposed style.

## Decisions taken

| Question | Decision |
| --- | --- |
| Figure style | The proposed style in the lesson 08 sample: HTML value tables, visible spaces and NULL, highlighted trap cells, a decision grid, unit tiles. |
| Tool for this course | SQL only. In the career path, Python is course 9 and Pandas course 11; this course is course 6, so learners do not know Python yet. |
| Where SQL-vs-Python contrasts go | Later, as callbacks in the Pandas course (out of scope here). The sample's verified Python code and outputs (`samples/results.json`) are kept for that. |
| How much code | Concept-first. Code appears where the learner must produce or check a number. Concept lessons use one run line per concept and predict/decide Try Its. In this course it applies in full to the 13–16 rewrites; lessons 01–12 only lose code where they exceed the cap. |
| Lessons 13–16 | Full rewrite by the plugin writer (reform mode). |
| Lessons 01–12 | Refresh, not rewrite: redraw weak figures, re-lay out long SQL lines, and trim code in the heavy lessons 08, 10, 11 and 12. Teaching text, quizzes and checked results stay. |
| Images | 1–2 analogy illustrations per lesson where the lesson has an analogy, through the existing `nerdit-lesson-illustrator` flow. The user generates them. Exact data stays in tables and SVG. |
| Upload | Admin → Import JSON + Images, update mode, against the live course's own export. |
| Commits and deploys | Only after explicit approval for each one. |

## Non-goals

- Changing any other course on the site.
- Reordering the career path. Suggested to the user (Regex directly after Pandas; Web Scraping for
  Beginners before Web Data Extraction); the user does it on the admin Programs page.
- Python or `plot` lessons in this course.
- A Python output checker. It is needed before any Python content is generated anywhere, but this
  course is SQL-only (see Follow-ups).
- Step-through widgets.

## Part 1 — Plugin rules

### 1.1 New figure rules (`figures.md`, "Rules that hold for every template")

- **R10 · Columns go in a table.** Data with more than one field per record is an HTML table
  (`nerdit-vtable`) inside `nerdit-figure`, never `<text>` strings joined with `·`. SVG remains for
  shapes that carry meaning: flows, overlaps, time scales, key matches.
- **R11 · Make invisible values visible.** A raw string sits in `nerdit-val` (a thin box that marks
  where the string starts and ends). Each space is `<span class="nerdit-ws">␣</span>`. NULL is
  `<span class="nerdit-null">NULL</span>`, so it never looks like text. Square brackets are no
  longer used to show spaces in figures. (SQL outputs may still use `'[' || x || ']'`, since that
  is real query output.)
- **R12 · Highlight the surprise.** The cell that teaches the trap gets `nerdit-cell-bad`, and the
  cell that shows the safe result gets `nerdit-cell-good`. Each carries a 2–4 word
  `nerdit-vnote` saying what happened ("invented, no error", "caught"). Do not colour whole rows
  when one cell is the point.
- **R13 · Show each idea once.** Within one section, a text map (`nerdit-map`), a figure and its
  numbered reading steps must not restate the same facts. Reading steps add order or reasons; they
  do not repeat labels the figure already shows. When a figure covers it, drop the text map.

### 1.2 New templates (`figures.md`)

Each template gets markup, one worked example from lesson 08 or 10, and the phone rule: the
table fits a 280px figure column with no horizontal scroll.

- **11 · Value table**: raw value → rule → clean value, grouped by rule with ① ② ③ in the group
  row. Use for any per-value transformation (TRIM, CAST, NULLIF, date parsing). Template 4
  (before/after) stays for structural changes such as a table being split.
- **12 · Decision grid**: one row per record, one column per check in CASE order (column
  headers ① ② ③ ④ plus a legend), ✓ / ✗ / – cells, the first ✗ boxed, and an outcome column.
  Use whenever rules are checked per row and the first failure decides.
- **13 · Unit tiles**: one numbered tile per row, coloured by bin, grouped with a count under each
  group and the sum below. Use when parts must add up to a total (reconciliation, row counts).
- **14 · Time window**: SVG number line drawn to scale, ○ for an excluded bound (`>`), ● for an
  included bound (`<=`), the window shaded. An optional second lane shows a second clock (for
  example arrival time against update time). Use for watermarks, batch bounds and late data.

The "Choosing between them" table gains rows for these four, placed above the generic sequence
and before/after rows so they win when they fit.

### 1.3 SQL layout rule (`runners/sql.md`, `CORE.md` §4)

- No line longer than 60 characters.
- `CREATE TABLE`: one column per line. `SELECT` lists of more than three expressions: one per
  line.
- Two-space indent per level. No alignment indent deeper than 12 spaces; break the line instead.
- `CASE`, each `WHEN`, `ELSE` and `END` on their own lines, indented under `CASE`.
- A space after every comma and around `=`, `<>`, `<=`, `>=`, `||`.

### 1.4 Concept-first density (`CORE.md` §4, `agents/nerdit-lesson-writer.md`)

- New optional input field `focus`: `"concept"` or `"hands-on"` (default `"hands-on"`).
  `check_input.py` accepts and validates it; it never reaches the output, like `runner`.
- `concept`: one run line per concept section; the Try It may be a prediction or a decision
  ("Which grain is this table?") instead of running code.
- `hands-on`: 2–3 run lines per concept (the current rule).
- Both: a shown code block is at most 15 lines; repeated setup moves into the seed or a view.
  Shown code per lesson: at most 40 lines for `concept`, 100 for `hands-on`.
- For this course the course input JSON gets `focus` per lesson: `concept` for 01, 03, 07, 14
  and 15; `hands-on` for the rest. Lessons 01–12 keep their current density, except that the four
  over the `hands-on` cap (08: 144 lines, 10: 136, 11: 113, 12: 131) are trimmed. Concept-first
  applies in full to the 13–16 rewrites and to every new course.

### 1.5 Run-line heading rule (`CORE.md` §4c)

The `.why` text in `nerdit-runhead` must not be repeated as the paragraph that follows. The
paragraph says what the code does in one sentence; the heading says why it matters.

### 1.6 Writer: refresh mode (`agents/nerdit-lesson-writer.md`, beside reform mode)

The orchestrator passes `SOURCE_PATH` (the current lesson) and `REFRESH`, a list drawn from
`figures`, `sql-layout` and `trim`.

- `figures`: redraw the figures that break R10–R13 or have a better template in §1.2, with
  their captions and reading steps. Remove a text map that R13 makes redundant.
- `sql-layout`: re-lay out SQL in run lines and Try Its to §1.3. Whitespace only.
- `trim`: shorten code to the §1.4 limits by moving repeated setup into the seed or a view. Shown
  outputs must still match SQLite. A run line's heading and its one-sentence lead may change to
  match the shorter code.
- Everything else must stay byte-for-byte the same after whitespace normalisation: headings,
  prose, Try It prompts, cheat sheet, quiz, concept manifest.

### 1.7 Checks (each written test-first)

`verify_course.py` gains a `--contract v11`: everything v10 checks, plus the checks below. Courses already verified under v10 keep their result; new and refreshed lessons are verified under v11.

| Check | Result |
| --- | --- |
| A line over 60 characters in `.nerdit-in pre[data-lang="sql"]` or an SQL try-it textarea | fail |
| `nerdit-runhead .why` text equal to the next `<p>` (normalised) | fail |
| An SVG `<text>` with two or more `·` separators and digits in at least two fields | fail (R10) |
| A code block over 15 lines, or lesson code over the §1.4 cap for its `focus` | warning |

`Report` gains a `warnings` list that prints after the failures but does not change the exit
code.

New scripts in `skills/nerdit-chapter-generator/scripts/`, each with a `test_*.py`:

- **`check_refresh.py --before <html> --after <html> --modes figures,sql-layout[,trim]`.**
  Fails when anything outside the allowed scope changed:
  - Text outside `.nerdit-figure`, its reading steps and `pre`/`textarea` code must be equal
    after whitespace normalisation.
  - With `sql-layout` and without `trim`, every SQL block must be equal to the old one after
    whitespace is normalised outside string literals.
  - With `trim`, SQL blocks may change, and so may run-line headings and their one-sentence
    leads.
- **`gate_lesson.py`**: one-lesson gate, promoted from `rollout/gate.py`. It assembles a
  one-lesson course, then runs verify v11, `check_sql_outputs.py` and the SVG checks. With
  `--before`, it also runs `check_refresh.py`.
- **`build_preview.py`**: promoted from `rollout/build_preview.py`. It inlines `css8.css`,
  `css9-simple.css` and `css10-brand.css`, and loads highlight.js 11.9.0 from cdnjs with the
  same scope→class table as `lessonHighlight.ts`, so the preview colours code like the site does.

### 1.8 Version

Plugin 3.2.0 → 3.3.0. `SKILL.md` documents refresh mode, `gate_lesson.py` and
`build_preview.py`.

### 1.9 Visual Map: one place that decides every visual

Today three tables choose visuals and can drift apart: `CORE.md` §7, `figures.md`
"Choosing between them" and the illustrator's `references/style.md` "Choosing a visual".
`CORE.md` §7 becomes the only decision table. The other two keep their markup and checks
and point to it.

| Where in the lesson | The content is… | Visual | Made by |
| --- | --- | --- | --- |
| Overview / hook | a real-world scene | illustration | illustrator; the user generates it |
| Concept: meaning | an analogy | illustration (optional) | illustrator |
| Concept: meaning | a structure or relationship | SVG diagram (templates 1–8, 10) | writer |
| Concept: case | records with fields, or values changing | value table or decision grid (11, 12) | writer, HTML |
| Concept: case | events in time, a window | time window (14) | writer, SVG |
| Concept: case | parts that add up to a total | unit tiles (13) | writer, HTML |
| Concept: case | real measured numbers to compare | chart (Chart.js, §9) | writer |
| Worked example | code → result | run line with a result table | writer |
| Practice | — | Try It (predict, run or decide) | writer |
| Closing | summary | cheat-sheet table | writer |

**Icon set for tables (closed list):** `✓` passes, `✗` fails, `–` not checked, `⚠` needs
attention, `🔑` primary key, `🔗` foreign key. Every table that uses one carries a legend or
says it in text. No other icons, the same rule as heading emoji (`CORE.md` §4c).

**Every figure names its visual.** Each `nerdit-figure` carries
`data-visual="diagram|value-table|decision-grid|time-window|unit-tiles|chart|course-map|illustration"`,
so the balance rules below can be checked by script. `verify_course.py` v11 fails a figure
without it.

**Balance rules:**

| Rule | Checked by |
| --- | --- |
| Every concept section has one main visual (figure, value table or chart) | `verify_course.py` v11, warning |
| No two visuals in a section show the same facts (R13) | QA validator |
| 0–3 illustrations per lesson, only where the text has a scene or analogy | illustrator `manifest.py` (existing cap) |
| Charts only for real measured numbers | QA validator |
| The same template in every concept section of a lesson | `verify_course.py` v11, warning |

**Image hints written by the writer.** `<id>.concepts.json` gains an optional `visuals` list,
one entry per concept section:
`{"section": 2, "visual": "value-table", "illustration": "numbering drafts of an essay, newest first"}`.
`illustration` is `null` when the section has no scene or analogy. `visual` is one of
`diagram`, `value-table`, `decision-grid`, `time-window`, `unit-tiles`, `chart`, `none`. The
illustrator's plan run reads these hints, so it offers image slots without searching the text
again (`extract_outline.py --hints <workdir>`). `check_sequence.py` ignores the new key; a
manifest without it still works.

### 1.10 Human voice and continuity

1. **`check_prose.py`** (deterministic, run by `gate_lesson.py` and in `SKILL.md` Step 4c).
   It reads the visible prose of a lesson: text outside `pre`, `code`, `textarea`, `svg`,
   `script` and tables. It **fails** on any phrase from a banned list kept in
   `references/voice.md` ("delve", "crucial", "seamless", "leverage", "let's dive in",
   "it's important to note", "in today's world", "furthermore", "moreover", "additionally",
   "not only … but also", and others). It **warns** on:
   - sentences over 15 words
   - paragraphs over 3 sentences
   - more than one em dash per paragraph
   - every concept section opening with the same first two words

   Contractions are allowed.
2. **Story bible**: the course world in §1.11. Every writer and the illustrator receive it.
3. **"You are here" course map (template 15).** One SVG strip per course listing its stages,
   drawn once in the world file's `stages`. Each lesson shows it under the overview with its
   own stage filled. `verify_course.py` v11 warns when a course that defines `stages` has a
   lesson without the map.
4. **One real mistake per lesson.** A realistic wrong result is shown with its wrong
   output, then why it happened, then the fix. It uses the existing `nerdit-compare` block.
   Checked by the QA validator.
5. **Spotlight record.** Each lesson picks one record and marks it with `nerdit-spot`
   (a new css9 class, token colours) in every figure and table where it appears. Checked by
   the QA validator.
6. **Check it by hand.** Under a key result, one line of arithmetic the learner can verify
   ("12,000 + 500 = 12,500 ✓"). Optional; the QA validator checks that the sum is true.

### 1.11 Business worlds and generated data

A **world** is one fictional business, its people and its data. Lessons take their records
from it instead of inventing new ones.

- **Library:** `skills/nerdit-chapter-generator/references/worlds/<slug>.world.json`, reusable
  across courses. A course points at one with `course-<chapter>_world.json`, which holds either
  `{"use": "<slug>"}` or a full world.
- **World file fields:**
  - `business`: name, type, city, branches or stores, channels, currency and money unit,
    tax, fiscal year, seasons.
  - `cast`: name, role, trait, `look` (for consistent images).
  - `stages`: for the course map, §1.10.3.
  - `entities`: the tables and how to generate them.
  - `messiness`: which defects lessons may declare.
  - `arc`: a one-line story beat per lesson id.
- **Generator `make_world_data.py`.** It is declarative: each entity lists `rows` and, per
  column, a generator (`id`, `choice`, `weighted_choice`, `int_range`, `money_range`,
  `date_range`, `fk`, `person_name`), plus optional month weights for seasonality. A fixed
  `seed` makes every run identical. Output: `world_data.sql` and `world_data.json`, at most
  about 100 rows per entity. It never generates phone numbers, emails or street addresses.
- **Lessons use slices.** The writer receives the world file plus a summary of the generated
  rows. A lesson seed takes only the rows its sections need and adds defects it declares in a
  comment: `-- defect: row 5 amount_text '12x'`.
- **`check_world.py`.** Fails when a lesson seed or figure uses a person, product, store or
  price that is not in the world data and not a declared defect. `check_input.py` validates the
  world file's shape.
- **Real business names, synthetic records.** A world may use a real business's name, type,
  product mix, price bands, channels and seasons, with three safeguards:
  1. **Owner permission is recorded.** For example:
     `"realName": {"approvedBy": "owner", "date": "2026-10-15", "note": "WhatsApp"}`.
     `check_input.py` rejects a real-name world without it.
  2. **Every record is synthetic and labelled.** Customers, orders, amounts and staff are
     generated. People in the `cast` are invented, never the owner or real staff. Each lesson's
     first data table carries
     `<p class="nerdit-data-note">Business name used with permission. All records, people and
     amounts are synthetic, made for teaching.</p>`; `check_world.py` fails a lesson without it.
  3. **Mistakes belong to the data work, never to the business.** Story beats show report bugs,
     entry typos and pipeline errors. They never show fraud, losses, bad service or
     complaints about the real business. The QA validator checks the `arc` and the lessons for
     this.
  Images never show a real logo (the illustrator's existing rule).
- **This course keeps its data.** Data Modelling lessons 01–12 already share one retailer and
  its records. Its world file is written from that existing data, so the 13–16 rewrite stays
  consistent. New worlds apply to new or rewritten courses.

## Part 2 — Website styles

- Add to `css9-simple.css`, scoped under `.nerdit-wrapper`: `nerdit-vfig`, `nerdit-vtable`,
  `nerdit-vgroup`, `nerdit-varrow`, `nerdit-val`, `nerdit-ws`, `nerdit-null`, `nerdit-vnote`,
  `nerdit-cell-bad`, `nerdit-cell-good`, `nerdit-row-kept`, `nerdit-row-dropped`, `nerdit-grid`
  with `nerdit-chk ok|first|skip`, `nerdit-vlegend`, `nerdit-tiles`, `nerdit-tilegroup`,
  `nerdit-tile sup|acc|rej`, `nerdit-vsum`. Colours are tokens only (CORE.md §7b), so both
  themes work.
- Copy the file to `nerdit/future-vision/src/lesson-css/` and `nerdit-admin/src/lesson-css/`.
  `check_css_bundle.py` must report no drift.
- No JavaScript changes. All classes are new, so existing lessons render exactly as before.
- Add a dev fixture `nerdit/future-vision/src/utils/__fixtures__/lesson-v11-visuals.html` that
  uses every new class. Check it on the dev server with Playwright at 1280px and 390px, in light
  and dark themes.
- Website and admin deploy after approval, and **before** the course import. Lessons that use the
  new classes would otherwise show unstyled tables.

## Part 3 — Data Modelling course

Base file: the live course's own export (Admin → Export output JSON), not the local
`…_output.v2-create.json`, so course and lesson ids match the live course for an update import.
First diff the export against the local v2-create lessons. If any lesson differs beyond ids,
stop and report.

The writer runs one lesson at a time. A lesson that fails its gate twice stops the run and is
reported.

1. **Plugin and styles first** (Parts 1–2), so every lesson below is written to the new rules.
2. **Rewrite 13–16** in reform mode with the old lesson as `SOURCE_PATH`. Lesson 13's metric is
   shown as a Chart.js figure (figures.md §9) built from real query results. Gate: verify v11
   pass, `check_sql_outputs.py` all match with none unchecked.
3. **Pilot refresh on 08 and 10.** 08 gets `figures,sql-layout,trim`. 10 gets
   `figures,sql-layout,trim` and template 14 for the watermark. Gate plus `check_refresh.py`.
   Record the tokens used per lesson. The user reviews both on the dev site; continue only on
   their go.
4. **Refresh the rest.** 01–07 and 09 get `figures,sql-layout`; 11 and 12 also get `trim`. Each
   lesson must pass its gate.
5. **Images.** Run the illustrator's plan run with `--replan` for each lesson. Each image slot
   needs an analogy already in the lesson text (lesson 08: drafts of an essay; lesson 10: a
   letter's date, postmark and arrival, and a bookmark). The user generates the images; then
   the apply run converts, checks and inserts them.
6. **Assemble and check the whole course.** verify v11 must report 0 failures,
   `check_sql_outputs.py` all match, and `check_images.py` must pass. Build the preview with
   `build_preview.py` and get the user's review.
7. **Import.** The user imports in update mode, after the Part 2 deploy is live. The pre-import
   export is the rollback file.

## Success criteria

- `verify_course.py --contract v11`: 0 failures across all 16 lessons.
- `check_sql_outputs.py`: every example matches, none unchecked. No learner sees a wrong output.
- No SQL line over 60 characters; no dotted data strings in figures; no repeated "why" text.
- Every new figure fits a 390px phone screen with no horizontal scroll.
- The preview's code colours match the site.
- The full plugin test suite passes; `check_css_bundle.py` reports no drift.

## Testing

- Every new check has failing fixtures written first, then the code that makes them pass.
- `check_refresh.py` fixtures cover: a changed paragraph (fail), changed SQL with `sql-layout`
  only (fail), whitespace-only SQL (pass), a changed figure (pass), and a changed quiz (fail).
- `build_preview.py` test: the output contains the three stylesheets and the highlighter mapping,
  and every lesson's wrapper.
- Website: the visual fixture checked with Playwright at both widths and both themes.

## Token budget (estimate; the pilot replaces it with measured numbers)

- Lessons 13–16 rewrite: about 4 × 120k.
- Refresh: about 30k per lesson with `figures,sql-layout`, about 60k with `trim`.
- Image plan run: about 100k.
- Total: about 1.1M tokens across several sessions.

## Follow-ups (not in this project)

- Pandas course: add SQL-vs-pandas callbacks to the Data Modelling exercises, reusing
  `samples/results.json`.
- `check_python_outputs.py`: needed before any Python-runner content is generated or refreshed.
  Python lessons currently ship unchecked outputs.
- Career path reorder: the user does this in the admin.
- Retrofitting other courses with v11 visuals, one course at a time.
