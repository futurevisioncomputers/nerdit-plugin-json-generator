# Practice Files (CSV, Excel, JSON, SQL, Python, notebooks) Plan

**Goal:** Every lesson that works with data or code gives enrolled learners the exact files it uses, with names
that say which lesson and section they belong to, plus the complete runnable code. The page keeps short,
explained code; the download holds the full code. The plugin makes and checks every file; the admin uploads
them with the course JSON; the learner site shows them to enrolled learners only. A lesson ships only when all
its code, answers and files run on current Python with no deprecated code.

**Linked plans:** [admin import plan](../../../../nerdit-admin/docs/course-json-images-import-plan.md) ·
[course import contract](../../course-import-contract.md) ·
[Plan C, data science datasets](2026-10-17-plan-c-data-science-datasets.md) (browser-built CSVs, kept).

**Repos:** the plugin is done here. `nerdit` (learner site: `future-vision`, `shared`) and `nerdit-admin` were not
reachable from the planning session; their sections are the contract they implement. Phases 2–3 need the
Claude GitHub App to have access to both repos.

## Decisions (owner, 2026-10-23)

| # | Question | Decision |
|---|---|---|
| 1 | Who can download | **Enrolled learners only** (and admins) |
| 2 | Size | **5 MiB per file**; a lesson's zip also stays under 5 MiB (§3) |
| 3 | Formats | **CSV, Excel, JSON, SQL, Python, notebooks** |
| 4 | Solutions | **Downloadable full code.** The page shows short code with explanations; the download holds the complete, runnable code |
| 5 | Where file details live | **Lesson HTML only** (like images); no course-JSON schema change |
| 6 | Python version | **Latest Python, no deprecated code** (§4) |
| 7 | Worlds | **`fvc-institute`** for tech and AI courses, **`practice-retail`** for business courses |

---

## 1. What exists today, and the gaps

| Today | Gap |
|---|---|
| Python/plot lessons with a world recipe build CSVs in the browser and add `Download enquiries.csv` after the first Try It (Plan C). | Only Python with a recipe; only CSV; inside a runner, not where the learner starts. |
| SQL seeds in `<script type="text/plain">`; Excel grids in `data-grid`. | No `.sql` or `.xlsx` to practise in the learner's own SQLite, MySQL or Excel. |
| Payloads, request lists and code typed in run lines, at most 15 lines each. | No complete program to download and run. |
| File names from the entity (`enquiries.csv`). | Not traceable to a lesson; two lessons can clash. |
| Website Python is 3.12 (Pyodide 0.26.2). | Not the current Python; deprecated APIs are not checked anywhere. |
| Checks cover run lines, Try It starters, SQL results, Excel formulas, world values. | Solutions, predict and fill-in answers, offline code (FastAPI, httpx …) and quiz answers are not run. |

## 2. File naming (the tracing rule)

```
L<nn>-S<section>-<what-it-holds>.<ext>     a section's data file       L02-S1-enquiry-messages.csv
L<nn>-practice-starter.py | .ipynb        practice tasks, no answers   L02-practice-starter.ipynb
L<nn>-solutions.py | .ipynb               complete code, every example and task, with answers
L<nn>-full-app.py                         the lesson's pieces in one runnable program (project lessons)
L<nn>-requirements.txt                    pinned libraries for the downloads (code lessons)
L<nn>-practice-files.zip                  all of the above + README.txt
```

- Lower case `a-z`, digits and hyphens; at most 60 characters; `<nn>` is the lesson's position in the input.
- Unique across the whole course, images included: the admin matches by file name in one upload.
- Code opens files by the downloaded name: `pd.read_csv("L02-S1-enquiry-messages.csv")`. Saved next to the
  notebook, the code runs unchanged. A dataset recipe's file key (Plan C) uses the same name.
- `README.txt` in the zip: one line per file (what is inside, rows and columns, the section that uses it), the
  Python version, and `pip install -r L<nn>-requirements.txt`.
- If the course order changes, names are regenerated and re-uploaded; lesson ids stay unchanged.

## 3. Formats and the solutions split

| Format | Made from | Rules |
|---|---|---|
| `.csv` | world entity slice, lesson table, or dataset recipe | UTF-8, header row, RFC 4180 quoting |
| `.xlsx` | the same rows | one sheet per table named after it, bold header, no macros (`.xlsm` refused), formulas only in Excel lessons and only ones `nerdit-excel-engine.js` computes |
| `.json` / `.jsonl` | payloads or records the lesson shows | 2-space indent; `.jsonl` one object per line |
| `.sql` | the lesson's seed script, byte for byte | runs in SQLite; header comment names lesson, section and tables |
| `.py` | starters, solutions, full app | runs as is on the pinned Python; sections in page order, each with a one-line comment |
| `.ipynb` | the same as `.py`, as cells | starter: a markdown cell per task + an empty code cell; solutions: filled and run, outputs saved |

**Page vs download.** The page keeps each shown block within the CORE.md limits (15 lines, explained in 2–3
sentences). `L<nn>-solutions.*` holds the complete code: imports, setup, every example in order, every practice
task answered, short comments. Project lessons (an API, an app) add `L<nn>-full-app.py`, which combines the
lesson's pieces (for Lesson 2: one endpoint with timeouts, retries with backoff, a token bucket and clear HTTP
errors). The page still shows each answer in its `<details>`; the download adds, it never replaces.

**Size.** At most 5 MiB per file. A data file over 5 MiB is cut to a smaller sample. If the zip would pass
5 MiB, it holds the code, notebooks and README, and the large data files stay separate downloads.

## 4. Python version and modern code

- **Download and offline code: Python 3.14.** It is stable, a year old, and every library the courses use
  ships wheels for it.
- **Website runner: move from Pyodide 0.26.2 (Python 3.12) to Pyodide 314.x (Python 3.14),** so the page and
  the downloads run the same Python. This changes `nerdit-python-runner.js` and `nerdit-plot-runner.js`
  (plugin references + the learner site's copies) and the checker's `tools/pyodide` pin. Before switching,
  `check_python_outputs.py --probe numpy,pandas,sklearn,scipy,matplotlib,statsmodels` must pass on the new
  engine, and every published Python lesson is re-checked on it.
- **Python 3.15** (released 2026-10-09): used now only for lessons about 3.15's new features. Those examples are
  offline run lines checked on CPython 3.15, and their downloads say "needs Python 3.15". 3.15 becomes the
  default when Pyodide ships a 3.15 build and the course libraries publish 3.15 wheels.
- **Each course records its versions** in `course-<chapter>_requirements.txt`: Python version and the latest
  stable release of each library at generation time (for example `fastapi`, `httpx`, `pydantic`, `pandas`).
  The downloads copy it as `L<nn>-requirements.txt`.
- **No deprecated code**, enforced by `check_modern_code.py` (§6 g) and a banned list in
  `references/deprecated.md`, read like `voice.md`. Starting entries:

  | Instead of (deprecated) | Write |
  |---|---|
  | `typing.List`, `Dict`, `Optional[X]`, `Union[X, Y]` | `list`, `dict`, `X \| None`, `X \| Y` |
  | `datetime.utcnow()`, `utcfromtimestamp()` | `datetime.now(UTC)`, `datetime.fromtimestamp(ts, UTC)` |
  | `asyncio.get_event_loop()` to run code | `asyncio.run()` |
  | FastAPI `@app.on_event("startup")` | `lifespan=` context manager |
  | Pydantic v1 `.dict()`, `.json()`, `class Config`, `@validator` | `.model_dump()`, `.model_dump_json()`, `model_config`, `@field_validator` |
  | pandas `DataFrame.append`, chained assignment with `inplace=True` | `pd.concat`, assign the result |
  | scikit-learn `OneHotEncoder(sparse=…)` | `sparse_output=…` |
  | `os.popen`, `distutils`, `imp` | `subprocess.run`, `setuptools`/`sysconfig`, `importlib` |

## 5. Lesson markup

The writer declares the files once; the plugin draws the markup from it, as with screen specs.

```html
<script type="application/json" class="nerdit-files-spec">
{"python": "3.14",
 "files": [
  {"name": "L02-S1-enquiry-messages.csv", "sections": [1], "about": "4 enquiry messages Neha pasted",
   "from": {"world": "enquiry_messages", "rows": ["M1", "M2", "M7", "M12"], "columns": ["message_id", "intent", "message"]}},
  {"name": "L02-S2-provider-replies.json", "sections": [2], "from": {"json": {"M2": [503, 429, 200], "M12": [400, 200, 200]}}},
  {"name": "L02-S4-neha-requests.csv", "sections": [4], "from": {"table": "Neha's requests: capacity 3, refill 0.5 per second"}},
  {"name": "L02-practice-starter.ipynb", "sections": ["practice"], "from": {"practice": "starters"}},
  {"name": "L02-solutions.ipynb", "sections": "all", "from": {"solutions": "all"}},
  {"name": "L02-full-app.py", "sections": "all", "from": {"file": "full-app.py"}}
 ]}
</script>
```

Generated under the overview (before section 1):

```html
<div class="nerdit-files" data-nerdit-files="timeouts-retries-rate-limits-and-errors-02">
  <p class="nerdit-files-head">📂 Practice files for this lesson <span class="nerdit-files-py">Python 3.14</span></p>
  <table>
    <thead><tr><th>File</th><th>What's inside</th><th>Used in</th></tr></thead>
    <tbody>
      <tr><td><a class="nerdit-file" href="files/L02-S1-enquiry-messages.csv" download="L02-S1-enquiry-messages.csv"
             data-nerdit-file="L02-S1-enquiry-messages.csv" data-format="csv" data-bytes="412">L02-S1-enquiry-messages.csv</a></td>
          <td>4 rows: message_id, intent, message</td><td>Section 1</td></tr>
      <tr><td><a class="nerdit-file" href="files/L02-solutions.ipynb" … >L02-solutions.ipynb</a></td>
          <td>Full code: every example and practice answer</td><td>Whole lesson</td></tr>
    </tbody>
  </table>
  <a class="nerdit-file nerdit-file-all" href="files/L02-practice-files.zip" download="L02-practice-files.zip"
     data-nerdit-file="L02-practice-files.zip" data-format="zip">Download all files (zip)</a>
</div>
```

Each section's case study starts with `<p class="nerdit-file-use">📎 This section uses <a class="nerdit-file" …>…</a>.</p>`.
New classes (`nerdit-files`, `nerdit-files-head`, `nerdit-files-py`, `nerdit-file`, `nerdit-file-all`,
`nerdit-file-use`) go into the canonical `references/css9-simple.css` and both apps' `src/lesson-css/` copies in
the same change; `node ../nerdit/scripts/check-lesson-sync.mjs` must pass.

## 6. Verification: no broken or outdated code reaches a learner

| # | Check | Script | Fails when |
|---|---|---|---|
| a | **Every answer runs**: practice solutions, predict answers (in the run lines' namespace), fill-in code with `data-answer` filled in | `check_python_outputs.py`, `check_sql_outputs.py` (extended) | output differs from the page, or code raises / does not compile |
| b | **Offline code runs for real**: `data-run="offline"` examples and `L<nn>-full-app.py` in a venv built from the course requirements | new `check_offline_outputs.py` | output differs, a library is not pinned, or the app does not start and answer its test request |
| c | **All practice data is generated**: data and code courses declare a world (decision 7) | `check_input.py --strict`, `check_world.py` | no world; typed-in data over 8 rows; a value outside the world (declared defects aside) |
| d | **Learner-eye test**: unzip the lesson zip into an empty folder, `pip install -r` its requirements in a fresh venv, run the starter and solutions `.py`, execute both notebooks, run the `.sql` in SQLite | `check_files.py --as-learner` | any error, a missing file, a file the code opens that is not in the zip, a zip over 5 MiB |
| e | **One source, three copies agree**: page tables, downloads and the browser runner's files | `check_files.py` | sha256 of the browser build ≠ the download; shown rows not in the file; a solution's output differs from the page's |
| f | **Computable quiz answers are computed** | `check_quiz.py` (new) | the marked option is not the computed result |
| g | **No deprecated code**: every run with `-W error::DeprecationWarning -W error::PendingDeprecationWarning -W error::FutureWarning`; a static scan against `references/deprecated.md` and ruff's `UP` rules targeting the course's Python | `check_modern_code.py` (new), and the warning flags in a, b, d | any warning, or a banned API in shown code, starters, solutions or the full app |
| h | **Names and limits**: §2 names, unique with images; every `files/` link has a file and every file is linked; each file parses; at most 5 MiB | `check_files.py` | any of these |

Exit codes as the existing checks (2 = environment missing, never a pass). A failure regenerates the lesson
within the 2-attempt budget, then stops and reports. **Freshness:** a quarterly re-run of b, d and g on the
newest library releases reports lessons whose code has become deprecated, before learners hit the warning.

## 7. Plugin work (phase 1)

- [ ] Rules: CORE.md §5 and a new §6e "Practice files", the page/download split, `references/deprecated.md`;
      writer agent, QA checklist, runners/python.md, sql.md, excel.md.
- [ ] `scripts/practice_files.py`: reads the spec, builds every file (world slices via `make_world_data.py`, lesson
      tables, recipe builds, seed scripts, JSON, starters, solutions as `.py` and `.ipynb`, full app), the zip
      with README, `<workdir>/files.manifest.json` (`name, format, bytes, sha256, lessonId, sections, about, source`),
      and inserts the box and section lines.
- [ ] The checks a–h, with tests; `gate_lesson.py` and `verify_course.py` run them.
- [ ] Pyodide 314.x engine for the checker; probe; re-check existing Python lessons; runner JS updated.
- [ ] Output folder for the admin: `course-<chapter>_output.with-media.json` + `upload/images/…` + `upload/files/…`
      (the illustrator writes `upload/images/`; the old `<images>/upload/` path stays readable).
- [ ] Story video: a `table` scene may name its practice file; the description lists the lesson's files.
- [ ] Pilot: Lesson 2 of *Building Production-Ready AI APIs* with all its files and the full app; every check passes.

## 8. Admin contract (`nerdit-admin`)

- [ ] **Import JSON + Media** takes the `upload/` folder. Allowed: `.csv .xlsx .json .jsonl .sql .py .ipynb .txt .md .zip`;
      refused: `.xlsm .exe .html .js` and anything else; at most 5 MiB each.
- [ ] Matching as for images: by file name across nested folders; a missing or duplicate name blocks
      preparation; extra files enter the course library.
- [ ] Validation: extension vs content (zip signature for xlsx/zip, UTF-8 text, JSON parses, notebook JSON valid).
- [ ] **Private storage:** `courses/<courseId>/files/<sha256 8 chars>/<original name>`, `Content-Type` by extension,
      `Content-Disposition: attachment; filename="<original name>"`. Not public: no download tokens are created,
      and the HTML keeps the relative `files/<name>` link plus `data-nerdit-file`; the learner site resolves it.
- [ ] **Storage security rules:** read allowed for admins, and for a signed-in user whose enrolment record for
      that course exists (rules read Firestore, one read per download); write for admins only. Rules tests cover
      enrolled, not enrolled, signed out and admin.
- [ ] Media records hold `kind: "file"`, name, sha256, bytes and storage path, so re-import and Export output JSON
      round-trip by original name, as images do.
- [ ] Media library lists files with the lessons and sections that use them; replacing one flags those lessons
      for review. Admin preview downloads work for admins.
- [ ] Sanitizer allowlist: the new classes, `a[download]`, the `data-*` attributes above, `href` only to a relative
      `files/` path; `script.nerdit-files-spec` kept in the JSON, never rendered.
- [ ] Tests: import → preview → export round-trip with one file of each format; duplicate and missing-file blocks.

## 9. Learner site contract (`nerdit`: `future-vision`, `shared`)

- [ ] `shared`: media record gains `kind: "image" | "file"`, `format`, `bytes`, `sha256`, `storagePath`; rebuild.
- [ ] Lesson CSS copies updated with the plugin (§5); `normalizeLessonHtml` keeps the box and links, drops links to
      other origins.
- [ ] **Enrolled-only downloads:** a click on `a.nerdit-file` fetches the file with the Firebase SDK (`getBlob` on the
      storage path, which the security rules check) and saves it under `data-nerdit-file`. Not enrolled: the box
      shows the file list with an "Enrol to download" button instead of links. Signed out: "Sign in to download".
- [ ] Runners: with a `.nerdit-files` box, the Python/plot runners skip their own Blob links and write the listed
      files into Pyodide's file system — built from the recipe as today, or fetched with `getBlob` for files without
      a recipe (JSON, xlsx). Runners move to Pyodide 314.x (§4). Fetched files are kept in the browser's Cache
      Storage keyed by their sha256, so repeated runs and page visits do not download them again (private
      downloads skip the shared HTTP cache that public images get).
- [ ] Download UX: format, size and "Python 3.14" shown; one tap on a phone; "Download all (zip)".
- [ ] Tests: `normalizeLessonHtml` keeps the markup; Playwright as enrolled, not enrolled and signed out; an enrolled
      download has the right name and bytes; a Try It that reads the file runs.

## 10. Rollout

| Phase | Where | Done when |
|---|---|---|
| 1 | plugin | §7 complete; Lesson 2 pilot passes checks a–h |
| 2 | admin | import, private upload, rules tests and round-trip pass with the pilot folder |
| 3 | learner site | CSS sync check passes; Pyodide 314 runners; Playwright access tests pass |
| 4 | all three | end-to-end: generate → import → preview → publish → enrolled learner downloads and runs everything |
| 5 | courses | backfill published courses: worlds per decision 7, files, solutions, re-check on Python 3.14; re-import each reviewed final JSON |

Phase 1 ships nothing to learners until phases 2–3 are released.

## 11. Cost (Google)

About 6 GB of files for 500 courses (about ₹3 a month to store); downloads are free up to 100 GB a month, then about
$0.12 per GB. Private files cost the same per GB as public ones. The only extra is the enrolment check: one
Firestore read per download (50,000 reads a day free, then a few cents per 100,000). No server or Cloud Function
streams the files; the SDK reads Storage directly under the security rules. Videos stay on YouTube. Set a budget alert.
