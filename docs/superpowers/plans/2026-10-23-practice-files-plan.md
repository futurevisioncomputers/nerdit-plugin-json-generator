# Practice Files (CSV, Excel, JSON, SQL, code) Plan

**Goal:** Every lesson that works with data or code gives the learner the exact files it uses, with names that
say which lesson and section they belong to. The plugin makes and checks the files; the admin uploads them to
the course's storage with the course JSON; the learner site shows them in one "Practice files" box and in each
section that uses them.

**Linked plans:** [admin import plan](../../../../nerdit-admin/docs/course-json-images-import-plan.md) ·
[course import contract](../../course-import-contract.md) ·
[Plan C, data science datasets](2026-10-17-plan-c-data-science-datasets.md) (browser-built CSVs, kept).

**Repos:** the plugin is done here. `nerdit` (learner site, `future-vision`, `shared`) and `nerdit-admin` were not
reachable from the planning session, so their sections below are the contract they implement.

---

## 1. What exists today, and the gaps

| Today | Gap |
|---|---|
| Python/plot lessons with a world recipe build CSVs in the browser and add `Download enquiries.csv` after the first Try It (Plan C). | Only Python with a recipe; only CSV; the link appears inside a runner, not where the learner starts. |
| SQL seeds live in `<script type="text/plain">`; Excel grids in `data-grid`. | No downloadable `.sql` or `.xlsx`, so learners cannot practise in their own SQLite, MySQL or Excel. |
| JSON payloads, request lists and starter code are typed in run lines. | Learners copy them by hand. |
| File names come from the entity (`enquiries.csv`). | Two lessons can both ship `enquiries.csv` with different rows, and a learner cannot tell which lesson a file is from. |
| Images: relative `images/<name>` links, matched by unique file name on admin import, stored under the course id. | Data files have no such path through the admin. |

## 2. File naming (the tracing rule)

```
L<lesson 2 digits>-S<section>-<what-it-holds>.<ext>     one section's file
L<lesson 2 digits>-practice-<what>.<ext>               the closing practice set
L<lesson 2 digits>-practice-files.zip                  every file of the lesson + README.txt
```

- Examples: `L02-S1-enquiry-messages.csv`, `L02-S2-provider-replies.json`, `L03-S1-seed.sql`,
  `L05-S3-monthly-sales.xlsx`, `L02-practice-starter.py`.
- Lower case `a-z`, digits and hyphens; at most 60 characters; the lesson number is its position in the input.
- **Unique across the whole course, images included**: the admin matches by file name in one upload.
- **Code uses the same name** the learner downloads: `pd.read_csv("L02-S1-enquiry-messages.csv")`. A learner
  who saves the file next to their notebook runs the lesson's code unchanged.
- A dataset recipe's file key (Plan C) uses the same name, so the browser-built file and the download match.
- The zip holds a `README.txt`: one line per file — name, what is inside (rows, columns), the section that uses it.

If the course order changes, file names are regenerated and re-uploaded; lesson ids stay unchanged.

## 3. Formats

| Format | Made from | Rules |
|---|---|---|
| `.csv` | world entity slice, a lesson table, or a dataset recipe | UTF-8, header row, comma, quoted per RFC 4180; Plan C's quoting tests apply |
| `.xlsx` | the same rows | one sheet per table, sheet named after it, bold header, no macros (`.xlsm` refused), formulas only in Excel lessons and only ones `nerdit-excel-engine.js` computes |
| `.json` / `.jsonl` | a payload or record list the lesson shows | pretty-printed, 2-space indent; `.jsonl` one object per line (log lessons) |
| `.sql` | the lesson's seed script, byte for byte | `CREATE TABLE` + `INSERT`; runs in SQLite; header comment names lesson, section and tables |
| `.py` | Try It starters and practice tasks, without solutions | runs as is; each task a commented block |
| `.ipynb` (optional) | the same tasks as notebook cells | one markdown cell per task, one starter code cell |
| `.txt` / `.md` | prompts (Conversational preset) | plain text |

Limits (to confirm, §9): 5 MiB per file, 50 MiB per course. Bytes never go into the course JSON.

## 4. Lesson markup

The writer declares files once in a spec; the plugin draws the markup from it (the same pattern as screen specs).

```html
<script type="application/json" class="nerdit-files-spec">
{"files": [
  {"name": "L02-S1-enquiry-messages.csv", "sections": [1], "about": "4 enquiry messages Neha pasted",
   "from": {"world": "enquiry_messages", "rows": ["M1", "M2", "M7", "M12"], "columns": ["message_id", "intent", "message"]}},
  {"name": "L02-S2-provider-replies.json", "sections": [2], "about": "status codes per attempt for M2 and M12",
   "from": {"json": {"M2": [503, 429, 200], "M12": [400, 200, 200]}}},
  {"name": "L02-S4-neha-requests.csv", "sections": [4], "from": {"table": "Neha's requests: capacity 3, refill 0.5 per second"}},
  {"name": "L02-practice-starter.py", "sections": ["practice"], "from": {"practice": "starters"}}
]}
</script>
```

Generated under the overview (before section 1):

```html
<div class="nerdit-files" data-nerdit-files="timeouts-retries-rate-limits-and-errors-02">
  <p class="nerdit-files-head">📂 Practice files for this lesson</p>
  <table>
    <thead><tr><th>File</th><th>What's inside</th><th>Used in</th></tr></thead>
    <tbody>
      <tr><td><a class="nerdit-file" href="files/L02-S1-enquiry-messages.csv" download="L02-S1-enquiry-messages.csv"
             data-nerdit-file="L02-S1-enquiry-messages.csv" data-format="csv" data-bytes="412">L02-S1-enquiry-messages.csv</a></td>
          <td>4 rows: message_id, intent, message</td><td>Section 1</td></tr>
    </tbody>
  </table>
  <a class="nerdit-file nerdit-file-all" href="files/L02-practice-files.zip" download="L02-practice-files.zip"
     data-nerdit-file="L02-practice-files.zip" data-format="zip">Download all files (zip)</a>
</div>
```

And at the start of each section's case study:

```html
<p class="nerdit-file-use">📎 This section uses <a class="nerdit-file" href="files/L02-S1-enquiry-messages.csv"
   download="L02-S1-enquiry-messages.csv" data-nerdit-file="L02-S1-enquiry-messages.csv">L02-S1-enquiry-messages.csv</a>.</p>
```

The new classes (`nerdit-files`, `nerdit-files-head`, `nerdit-file`, `nerdit-file-all`, `nerdit-file-use`) go into
the canonical `references/css9-simple.css` and both apps' `src/lesson-css/` copies in the same change;
`node ../nerdit/scripts/check-lesson-sync.mjs` must pass.

## 5. Plugin work (this repo)

- [ ] **Rules:** CORE.md §5 and a new §6e "Practice files"; writer agent; QA checklist; runners/python.md
      (recipe file key = practice file name); runners/sql.md and excel.md (seed → `.sql`, grid → `.xlsx`).
- [ ] **`scripts/practice_files.py`**: parses `nerdit-files-spec`, builds each file from its source (world slice via
      `make_world_data.py`, lesson table, recipe build, seed script, JSON literal, practice starters), writes
      `<workdir>/upload/files/`, the zip with README, `<workdir>/files.manifest.json`
      (`name, format, bytes, sha256, lessonId, sections, about, source`) and inserts the box and section lines.
- [ ] **`scripts/check_files.py`** (gate + verify v11):
  - names follow §2 and are unique with the course's images;
  - every `files/` link has a file and every file is linked;
  - each file parses (CSV rectangular, JSON loads, SQL runs in in-memory SQLite, xlsx opens);
  - the file holds what the page shows: shown rows are in it, a `.sql` file equals the seed, a recipe build has
    the same sha256 as the CSV;
  - every name the code opens (`read_csv`, `read_excel`, `open`, `json.load`) is a listed file;
  - size limits.
- [ ] **`check_python_outputs.py`** writes the lesson's files into Pyodide's file system by name before the run
      lines, so examples are checked against the real files.
- [ ] **Output folder** (one folder for the admin to select):
      `course-<chapter>_output.with-media.json` + `upload/images/…` + `upload/files/…`.
      The illustrator writes to `upload/images/`; the old `<images>/upload/` path stays readable.
- [ ] **Story video:** a `table` scene may name its practice file; the description lists the lesson's files.
- [ ] Tests for each script; pilot on Lesson 2 of *Building Production-Ready AI APIs* (the four files above).

## 6. Admin contract (`nerdit-admin`)

- [ ] **Import JSON + Media** (today: Import JSON + Images) takes the `upload/` folder:
      allowed `.csv .xlsx .json .jsonl .sql .py .ipynb .txt .md .zip`; refused `.xlsm .exe .html .js` and anything else.
- [ ] Matching as for images: by file name across nested folders; a missing file or a duplicate name blocks
      preparation; extra selected files enter the course library.
- [ ] Validation mirrors `check_files.py`'s cheap checks: size, extension vs content (zip signature for
      xlsx/zip, UTF-8 for text, JSON parses).
- [ ] Storage: `courses/<courseId>/files/<sha256 8 chars>/<original name>`, `Content-Type` by extension,
      `Content-Disposition: attachment; filename="<original name>"` so the learner gets the traceable name,
      one-year immutable cache (the hash changes when the file does).
- [ ] Rewrite `href` to the Storage URL; keep `download`, `data-nerdit-file`, `data-format`, `data-bytes`.
      Media records store `kind: "file"`, name, sha256 and bytes, so re-import and Export output JSON round-trip
      by original name, as images do today.
- [ ] Media library lists files with the lessons and sections that use them; replacing a file flags those lessons
      for review.
- [ ] Sanitizer allowlist: the five classes, `a[download]`, the `data-*` attributes above, `href` only to the
      course's Storage or a relative `files/` path; `script.nerdit-files-spec` kept in the JSON, never rendered.
- [ ] Tests: import → preview → export round-trip with one file of each format; duplicate-name and
      missing-file blocks.

## 7. Learner site contract (`nerdit`: `future-vision`, `shared`)

- [ ] `shared`: media record type gains `kind: "image" | "file"`, `format`, `bytes`, `sha256`; rebuild `shared`.
- [ ] Lesson CSS copies updated with the plugin (§4); `normalizeLessonHtml` keeps the box and links, adds
      `rel="noopener"`, drops links to other origins.
- [ ] Python/plot runners: when a `.nerdit-files` box exists, the runner skips its own Blob `Download` links (no
      duplicates) and writes the listed files into Pyodide's file system — from the recipe as today, or fetched
      from the uploaded URL for files without a recipe (JSON, xlsx).
- [ ] SQL runner: unchanged seed; the `.sql` download sits in the box.
- [ ] Download UX: format, size, one tap on a phone; "Download all (zip)".
- [ ] Access: same as images (public, unguessable, hashed URLs) unless §9 decides enrolled-only signed URLs.
- [ ] Tests: `normalizeLessonHtml` keeps the markup; Playwright downloads a file with the right name and bytes and
      runs a Try It that reads it.

## 8. Rollout

| Phase | Where | Done when |
|---|---|---|
| 1 | plugin | rules, `practice_files.py`, `check_files.py`, Pyodide mounting, tests; Lesson 2 pilot passes every gate |
| 2 | admin | import/upload/rewrite/round-trip and sanitizer tests pass with the pilot folder |
| 3 | learner site | CSS sync check passes; Playwright download + Try It on the pilot lesson |
| 4 | all three | end-to-end: generate → import → preview → publish → learner downloads and runs the code |
| 5 | courses | backfill published courses from their worlds, seeds and shown tables; re-import each reviewed final JSON |

Phase 1 can start now and ships nothing to learners until phases 2–3 are released.

## 9. Decisions needed

1. Downloads public with hashed URLs (like images), or only for enrolled learners (signed URLs)?
2. Limits: 5 MiB per file, 50 MiB per course?
3. Formats in phase 1: CSV, XLSX, JSON, SQL, PY — and `.ipynb`?
4. Ship a solutions file, or keep solutions only on the page (current rule: answers stay on the page)?
5. HTML-only (like images), or also a lesson-level `practiceFiles` list in the course JSON for a separate
   "Files" tab? HTML-only needs no schema change; the list needs `assemble_course.py`, `verify_course.py`,
   admin validation and `shared` types.
