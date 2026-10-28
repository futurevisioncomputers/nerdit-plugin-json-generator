# Lesson readability and full programs — design

Date: 2026-10-28. Owner feedback after the Flask REST and Advanced Regression courses.

## Why

The owner read the finished courses as a learner and found three problems:

1. **Case studies everywhere.** Every concept section opens a "🌟 Case Study" before its code,
   even where the idea is clear without the course world. The rule that caused it
   (CORE.md §2 "Topic first, case study second", 2026-10-27, enforced by `check_case.py`)
   requires exactly one case study per concept section.
2. **Paragraphs are hard to skim.** Prose is correct but uniform. A learner revising before an
   exam cannot find the point of a paragraph at a glance. CORE.md §10 allows at most 3 `<strong>`
   key terms per section, so writers bold almost nothing.
3. **Code is a fragment the learner cannot run.** The 15-line block cap (CORE.md §4) and the
   2–4 step code walk push writers to fake the runtime. The Flask forms lesson shows
   `app.test_request_context(...)`, `MultiDict(...)` and `meta={"csrf": False}` instead of the
   app a learner would write: a route, a template, `validate_on_submit()` and `app.run()`.
   "The learner can't assemble or regenerate the full code" (owner). Where a concept only makes
   sense inside a running program, the lesson must show the whole program and explain it line
   by line.

Success: a learner can (a) skim any paragraph by its bold words, (b) meet the course world only
where it teaches something, and (c) copy a full program from a code-heavy lesson, run it on
their own computer, and understand every line of it from the page.

## Goals

- Case studies become **purposeful**, not structural.
- Paragraphs carry **scan highlights**, separate from key terms.
- Code-dependent lessons show **complete runnable programs** with a **full line walk**.
- Every rule keeps a checker beside it (owner rule: rule + checker together).

## Non-goals

- No change to the run-line component, tags, figures, quizzes or the course object schema.
- No new runtime on the site: full programs that need a server (Flask) stay offline run lines.
- Short examples stay: a full program is added where it is needed, not everywhere.

## Anti-goals (a failure even if checks pass)

- Bold everywhere, so nothing stands out.
- A 120-line program dumped on the page with a two-line walk.
- Courses losing the course world entirely; the case study still appears where it adds a real
  decision or real numbers.
- Programs that look complete but are never run by a checker.

## Design

### 1. Case study only where it teaches

- A concept section **may** have one case study; it no longer must.
- Use one when the course world adds something the general example cannot: a real decision,
  real numbers to read, a mistake in the data, or the payoff of the idea. Do not use one to wrap
  every code example.
- A lesson has at least 1 case study and at most one per concept section. A lesson's first
  case study keeps the one-line world reminder.
- Unchanged: no world name before a section's case study heading (topic first), and the first
  lesson's world card.
- Sections without a case study use a plain worked example: neutral names, or the lesson's
  dataset file without the story (no cast, branches or business names).
- `check_case.py`: drop "a concept section with no case study heading" as a failure; keep "two
  case studies in one section" and "world name before the heading"; add "a lesson with no case
  study" as a failure. WARN when every concept section of a lesson with 3+ sections has one
  ("case studies in every section: keep the ones that add a decision or real numbers").

### 2. Scan highlights: `<b>` in paragraphs

- New markup with a new meaning: `<b>` marks the 2–5 words that carry a paragraph's point.
  `<strong>` keeps its meaning (a key term being defined; at most 3 per section).
- Each explanation paragraph of 25+ words has 1–2 highlights; a paragraph never has more than 3.
  Highlights cover at most 20% of a paragraph's words. Never highlight a whole sentence.
- Highlights go on the claim ("a log link **keeps every prediction positive**"), not on filler.
- CSS: `<b>` in lesson prose gets the brand highlight weight (css9-simple.css), distinct enough
  from `<strong>` that a key term still reads as the term.
- `check_prose.py`: FAIL on 4+ `<b>` in one paragraph, on a highlight longer than 8 words, or on
  over 20% coverage; WARN when a lesson's explanation paragraphs of 25+ words have highlights in
  fewer than half of them. `<b>` does not count toward the 3 key terms.

### 3. Full programs with a full line walk

- New component: a **program** run line, `<div class="nerdit-run nerdit-program"
  data-file="form_app.py">` (offline when the browser cannot run it). It shows one complete file:
  imports, setup, every function, and the entry point (`if __name__ == "__main__":`).
- Use one when the section's construct only works inside a running program: web routes, forms,
  templates, request handling, CLIs, multi-part classes, a pipeline whose steps depend on each
  other. A fragment that fakes the runtime (`test_request_context`, `MultiDict`, `meta={"csrf":
  False}`, a hand-built request) is the signal that the section needs a program.
- Length: a program is exempt from the 15-line block cap; at most 80 lines. At most 2 programs
  per lesson. Programs do not count toward the lesson's shown-code cap.
- **Full line walk**: a program is followed by `<ol class="nerdit-codewalk nerdit-walk-full">`
  that covers every non-blank, non-comment line, in order. A step may cover a run of lines
  ("lines 12–18 build the HTML template") when they do one job. The 2–4 step limit applies only
  to ordinary code walks.
- The program's output block shows what the learner sees when they run it: the terminal lines
  and, for a web app, what the page shows at the URL (as text or a screen spec, figures.md §16).
- **Checked by running it.** The checker runs the file as the learner would, with a check
  harness for programs that block: a program with an entry point is imported (not run as
  `__main__`), then its `data-check` snippet runs against it (for Flask: `app.test_client()`
  posting the form). The shown output must match what the harness prints, as today.
- **In the pack.** `practice_files.py` writes each program to the chapter folder under its
  `data-file` name, so the learner can run exactly what the page shows.
- `verify_course.py`: a program must have an entry point, a `data-file`, at most 80 lines, and a
  full walk that covers every code line. `check_code_prose.py` already checks that walk lines
  are real code lines.
- WARN (new, `check_modern_code.py` or verify): a non-program block that uses
  `test_request_context`, `MultiDict` or `meta={"csrf": False}` ("show the real program").

### 4. Audit of courses generated with this plugin (2026-10-28)

The fragment problem is not only in the OpenAI-generated course. A static audit of shown Python
blocks (a block "needs earlier code" when it loads a name it neither imports nor assigns):

| Course | Blocks | Need earlier code | Fake runtime in shown code | Longest block |
|---|---|---|---|---|
| Flask REST API (11 ch) | 161 | 123 (76%) | `test_client()` in 9 lessons (correct only in the pytest lesson), `app_context()` in 4, `test_request_context` in 3 | 17 lines |
| Advanced Regression (15 ch) | 82 | 60 (73%) | none | 6 lines |

So the design covers two cases:

- **Programs** (web apps, CLIs, anything with an entry point): §3 above. In the Flask course,
  every lesson from routes onwards shows the real app file once, then the short run lines.
- **Analysis scripts** (data courses): the run lines may stay notebook-style cells, but every
  code lesson also ships its **whole script**: one program block at the end of the lesson's last
  concept section, "The whole script", holding every example of the lesson in page order as one
  runnable file (data loading included), with a full walk that groups by section. The same file
  goes in the practice pack as `Lnn-<slug>.py` for every code lesson, not only for lessons with a
  files spec. Its walk may reference the section where each step was explained instead of
  re-explaining it.
- `verify_course.py`: a code lesson (runner python/plot, focus not concept) with 3+ run lines
  that need earlier code must have a program block (FAIL for new courses, WARN in refresh).

### Rollout

1. Rules and checkers in the plugin, with tests (TDD), synced to the installed copy.
2. A `REFRESH = programs,readability` refresh mode, so finished courses can adopt the rules
   without a blind rewrite (`check_refresh.py` keeps outputs and data unchanged where code is
   unchanged).
3. Refresh the Flask REST course first (the owner's example), pilot two lessons, owner review,
   then the rest. Then the Advanced Regression course (readability and case studies; its two
   open QA findings, lesson 7 §2 and lesson 12 §5, get split during that refresh).

## Decided by the owner

- Case studies only where the concept needs them (not before every code block).
- Bold words in paragraphs for fast reading and revision.
- Full code with line-by-line explanation for chapters whose concept depends on the code.
- The content limit stays for ordinary explanation; full programs are the exception.
- A lesson program is **one file**: templates inline (`render_template_string`), as in the
  owner's forms example. Multi-file layouts (`templates/`, `forms.py`) appear only in the
  capstone project. `verify_course.py` WARNs on `render_template(` inside a lesson program.

## Builder's calls (Claude's, open to the owner)

- `<b>` for highlights, keeping `<strong>` for key terms; caps of 1–2 per paragraph, 20%.
- Program cap 80 lines and 2 per lesson; walk steps may group lines.
- The learner gets the program both on the page (with the walk) and as a file in the pack.
- Flask refresh before the regression refresh.
- Lessons keep at least one case study.

- **Harness scope (now):** plain Python scripts and Flask apps. A program with an entry point is
  imported, not run as `__main__`; its `data-check` snippet then runs (Flask: `app.test_client()`
  calls). Other runtimes (FastAPI, CLIs with `input()`, Streamlit) are later work; until then a
  program that needs them is not allowed. A missing library is exit 2 (environment), as every
  checker does today, never a skip.
- **What is compared:** only what the harness prints (terminal lines, status codes, the response
  text the `data-check` prints), exactly, through the existing offline-output path. "What the
  page shows" is a screen spec (figures.md §16), checked by `check_screens.py`, not compared to
  the response body.
- **Pack files:** `practice_files.py` extracts each program from the lesson HTML. `data-file`
  names are unique per chapter folder; a clash with another program, a dataset or a practice
  file is a hard FAIL.
- **Walk coverage:** inferred from the `<li>` code references, as `check_code_prose.py` does
  today; no new markup. A walk step names its first line in `<code>` and may say "to line N".
  Uncovered code lines FAIL for new courses.
- **Migration:** the new FAIL rules apply to new generation and to refreshed lessons. Already
  delivered courses get WARN until refreshed (`gate_lesson.py --modes programs,readability` turns
  them to FAIL for the lesson being refreshed). Verify on the delivered Flask and Regression
  outputs keeps passing.

## Left to the builder

- Exact CSS for `<b>`; the harness format for `data-check`; how the walk-coverage check counts
  multi-line statements; refresh prompts and pilot lesson choice.
