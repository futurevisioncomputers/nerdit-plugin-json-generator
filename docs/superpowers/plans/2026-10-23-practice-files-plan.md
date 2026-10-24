# Practice Pack and Capstone Plan

**Goal:** Learners who buy a course's certificate get one practice pack at the start of the course: a single zip of
at most 10 MiB with one folder per chapter (data, starter, full solution code) and an end-to-end capstone project
as the last chapter. Free learners keep the whole lesson page, the in-browser runner and the on-page answers. Every
file is built from the lesson's own data, named so a learner can trace it to its chapter and section, and tested
the way a learner would use it, on current Python with no deprecated code.

**Linked plans:** [admin import plan](../../../../nerdit-admin/docs/course-json-images-import-plan.md) ·
[course import contract](../../course-import-contract.md) ·
[Plan C, data science datasets](2026-10-17-plan-c-data-science-datasets.md) (browser-built CSVs, kept) ·
[lesson writing: explain first](../../../skills/nerdit-chapter-generator/references/CORE.md) (2026-10-23 rules).

**Repos:** plugin work is done in this repo. `nerdit` (learner site: `future-vision`, `shared`) and `nerdit-admin`
were not reachable from the planning session; §10 and §11 are the contract they implement. Phases 2 and 3 need the
Claude GitHub App to have access to both repos.

## Decisions (owner, 2026-10-23)

| # | Question | Decision |
|---|---|---|
| 1 | Who downloads | **Only learners who paid for the certificate** (and admins), confirmed 2026-10-24: a paid certificate order for the course, or a paid career program that includes it. A certificate held without a paid order does not unlock the files. **A course whose certificate is free (₹0) opens its files to every signed-in learner.** A revoked certificate locks them. Courses stay free (`price: 0`); the certificate (`certificatePrice`, ₹999 today) unlocks the exam, the certificate, the practice pack and the capstone code |
| 2 | Packaging | **One course practice pack**, offered in the first chapter; **one folder per chapter**; downloaded once, then used chapter by chapter |
| 3 | Size | **Measuring phase (2026-10-24): pack and single file at most 50 MiB**, to see what real courses weigh; the target stays 10 MiB pack / 5 MiB file and is tightened once sizes are known. Samples and the separate data pack wait until then |
| 12 | HTTP client | **New AI API courses teach `httpx2`** (`import httpx2`), Pydantic's drop-in continuation of `httpx`; existing courses switch when they are regenerated |
| 11 | Admin upload | **One course bundle zip** from the plugin: the output JSON, all images and practice files, and the video list; the admin imports that one file (§10) |
| 4 | Formats | **CSV, JSON, SQL, Python, notebooks**. Excel (`.xlsx`) dropped for now (2026-10-24): CSV opens in Excel |
| 5 | Solutions | **Full code to download**; the page keeps short code with explanations |
| 6 | Where file details live | **Lesson HTML only** (like images); no course-JSON schema change |
| 7 | Python | The website runner **stays on Pyodide 0.26.2 (Python 3.12)**: the Pyodide upgrade is dropped for now (2026-10-24). Downloads use **the same code as the page, written for 3.12**: a course's pack is marked **Python 3.14** when every file runs on 3.14 with no change, otherwise **Python 3.12**; **3.15** only for lessons about its new features; **no deprecated code** |
| 8 | Worlds | **One of the six business worlds per course**, chosen by subject fit (§2b); `practice-retail` (fictional) only when none fits |
| 9 | Capstone | **A new last chapter** in every code course: one end-to-end project combining every chapter, on the world's data |
| 10 | Capstone and certificate | **Not required for the certificate.** The capstone is practice; `finalAssignment` stays unused |
| 13 | Capstone scope (2026-10-24) | **One problem statement, one complete project, on the course world's dataset only** (no other data source). **New Python libraries are welcome** (charts, images, utility tools) for learning advancement: pinned, marked `# Beyond the course:`, and explained in the project README. How much code may go beyond what the course taught: **no rule yet, decided later** |

**Still open (default used until decided):** a pack button on the course page as well as in the first chapter
(default: first chapter only).

---

## 1. Today and the gaps

| Today | Gap |
|---|---|
| Python lessons with a world recipe build CSVs in the browser and add `Download enquiries.csv` after the first Try It (Plan C). | Only Python with a recipe, only CSV, inside a runner; no course-wide download. |
| SQL seeds in `<script type="text/plain">`; Excel grids in `data-grid`. | No `.sql` for the learner's own SQLite or MySQL (Excel lessons use the CSV; `.xlsx` dropped for now). |
| Code shown in blocks of at most 15 lines. | No complete program to run at home. |
| File names from the entity (`enquiries.csv`). | Not traceable to a chapter; two chapters can clash. |
| Website Python 3.12 (Pyodide 0.26.2). | Kept for now (§4); deprecated APIs unchecked. |
| Checks: run lines, Try It starters, SQL results, Excel formulas, world values. | Solutions, predict and fill-in answers, offline code (FastAPI, httpx …) and quiz answers are not run. |
| Courses end with a cheat sheet and practice tasks. | No project that joins the chapters together. |

## 2. The course practice pack

**One zip per course, at most 10 MiB, offered under the first chapter's overview, for certificate holders.**

```
fastapi-ai-apis-practice-pack-v1/
  README.txt                course map: each chapter folder, its files and what they hold; setup in 3 steps
  requirements.txt          one set of pinned libraries for the whole course; Python 3.14
  L01-llm-api-integration-and-streaming/
    L01-S2-chat-payload.json
    L01-practice-starter.ipynb    L01-practice-starter.py
    solutions/   L01-solutions.ipynb   L01-solutions.py
  L02-timeouts-retries-rate-limits-and-error-handling/
    L02-S1-enquiry-messages.csv   L02-S2-provider-replies.json   L02-S4-neha-requests.csv
    L02-practice-starter.ipynb    L02-practice-starter.py        L02-full-app.py
    solutions/   L02-solutions.ipynb   L02-solutions.py
  L03-ai-request-validation-and-usage-tracking/   …
  L04-structured-logging-and-health-endpoints/     …
  L05-capstone-enquiry-reply-assistant/
    README.md   data/   starter/   tests/   solution/                         (§5)
```

**Names (the tracing rule):**

```
L<nn>-S<section>-<what-it-holds>.<ext>    a section's data file              L02-S1-enquiry-messages.csv
L<nn>-practice-starter.py | .ipynb       the chapter's practice tasks, no answers
L<nn>-solutions.py | .ipynb              complete code: every example and practice answer
L<nn>-full-app.py                        the chapter's pieces in one runnable program (project chapters)
<course-short>-practice-pack-v<n>.zip    the pack                           fastapi-ai-apis-practice-pack-v1.zip
```

- Folders are `L<nn>-<chapter title slug>`, so they sort in course order. Files keep their `L<nn>-` prefix, so a
  file copied out of its folder still says where it belongs. `<nn>` is the chapter's position in the input.
- Lower case `a-z`, digits and hyphens; at most 60 characters per name; unique across the course, images included
  (the admin matches by file name).
- One setup for the whole course: create a venv once, `pip install -r requirements.txt`, then work chapter by chapter.
- Solutions sit in a `solutions/` subfolder: the starter is what a learner opens first.
- **Code finds its files wherever it runs.** Notebooks open in their own folder, so `pd.read_csv("L02-S1-enquiry-messages.csv")`
  works as on the page. Downloaded `.py` files read through `HERE = Path(__file__).parent`, so they also run from the
  pack root. A dataset recipe's file key (Plan C) uses the same name.
- **Versions:** any change to a chapter's files rebuilds the pack as `v<n+1>`. The first chapter's box shows the version
  and date; `README.txt` lists what changed. Each chapter also offers its own files singly (folded away), so a learner
  with an older pack, or one who joins midway, can take just that chapter.
- **Fitting 10 MiB:** a data file over 5 MiB, or one that would push the pack over 10 MiB, is cut to a sample (the
  sample is what the lesson uses and checks). A course that still cannot fit ships a second `…-data-pack-v<n>.zip`
  (at most 10 MiB), listed beside the practice pack. This course's pack is under 1 MiB.
- If the course order changes, names are regenerated and re-uploaded; lesson ids stay unchanged.

## 2b. Which world a course uses

All practice data, case studies and the capstone come from **one world per course**. The six business worlds use real
business names with the owners' recorded permission (`business.realName`); cast and records are invented. Pick by fit:

| World | Business | Entities | Fits courses on |
|---|---|---|---|
| `fvc-institute` | Future Vision Computer Institute, Surat | enquiries, learners, daily_enquiries, batch_scores, enquiry_messages | AI and LLM apps, AI APIs, NLP, chatbots, statistics, classification, Python basics, CRM funnels |
| `saree-wholesale` | Akruti Sarees, Surat | retailers, skus, weekly_orders, retailer_sku, order_lines | SQL, pandas and data cleaning, inventory, B2B sales, weekly forecasting, Excel |
| `stationery-d2c` | Roohani Rang, Mumbai | products, customers, orders, ratings, reviews, daily_sales | e-commerce analytics, customer segmentation, review sentiment, recommendations, daily sales series, Power BI, digital marketing |
| `boat-cruises` | Australian Boat Parties, Melbourne | bookings, quotes, cancellations, daily_bookings | booking systems and APIs, cancellation prediction, seasonality, business analytics |
| `wire-mesh` | Jain Wire Netting, Visakhapatnam | products, prices, qc_measurements, roll_defects | NumPy, quality-control statistics, anomaly detection, manufacturing, price lists in Excel |
| `interior-design` | Singhvi Interiors, Mumbai | enquiries, projects | project tracking, small-business Excel, quotes and CRM, design-business courses |
| `practice-retail` | Practice Retail (fictional) | stores, products, orders | fallback when no business fits, or when the story needs a mistake that must not touch a real business |

- The choice is recorded per course (`course-<chapter>_world.json`, and `ds-course-map.json` for Data Science);
  the capstone uses the same world.
- An owner may appear as themselves (asking the question the analyst answers), never in a mistake, defect or blame
  story beat; mistakes belong to data entry, queries or pipelines (worlds README).
- A course may add entities to its world when the subject needs them (for example API request logs for an API
  course), reviewed like any world change; existing courses keep their reviewed records.

## 3. Formats, and page vs download

| Format | Made from | Rules |
|---|---|---|
| `.csv` | world entity slice, lesson table, or dataset recipe | UTF-8, header row, RFC 4180 quoting |
| `.json` / `.jsonl` | payloads or records the lesson shows | 2-space indent; `.jsonl` one object per line |
| `.sql` | the lesson's seed script, byte for byte | runs in SQLite; a header comment names chapter, section and tables |
| `.py` | starters, solutions, full app, capstone | runs as is on the pinned Python; sections in page order, a one-line comment each |
| `.ipynb` | the same as `.py`, as cells | starter: a markdown cell per task + an empty code cell; solutions: filled and run, outputs saved |

**Page vs download.** The page keeps each shown block within the CORE.md limits (15 lines, explained in 2–3
sentences, the idea explained before the case study). `L<nn>-solutions.*` holds the complete code: imports, setup,
every example in order, every practice task answered, short comments. Project chapters add `L<nn>-full-app.py`
(for Lesson 2: one endpoint with timeouts, retries with backoff, a token bucket and clear HTTP errors). The page
still shows each answer in its `<details>`; the download adds, it never replaces.

## 4. Python version and modern code

- **The website stays on Python 3.12.** The website runner and the checker's `tools/pyodide` pin **stay on
  Pyodide 0.26.2 (Python 3.12)**. The Pyodide upgrade is dropped for now (owner, 2026-10-24): newer NumPy and pandas
  print some values differently (`np.float64(3.5)`, `str` dtype), so every published lesson's shown output would have
  to be re-checked first.
- **Downloads: the page's code, no second version.** Starters, solutions, full apps and the capstone are written for
  Python 3.12 (no 3.13+ only features). The offline checks run them on Python 3.14 first: when every file passes with
  no change, the course's pack and boxes say **Python 3.14**; when any file needs a change on 3.14 (a library without a
  3.14 build, different output), nothing is changed, the course pins **Python 3.12** in its requirements and its pack
  and boxes say **Python 3.12**, and the checks run on 3.12. The spec's `"python"` holds the result.
- **Python 3.15** (released 2026-10-09): only for lessons about its new features, as offline run lines checked on
  CPython 3.15, marked "needs Python 3.15". It becomes the default when Pyodide ships a 3.15 build and the course
  libraries publish 3.15 wheels.
- **Each course pins its versions** in `course-<chapter>_requirements.txt` (Python version and the latest stable
  release of each library at generation time); the pack ships it as `requirements.txt`.
- **No deprecated code.** Every run treats **all** warnings as errors (`-W error`): libraries such as Starlette raise
  deprecations as `UserWarning`. A banned list in `references/deprecated.md`, read like `voice.md`, plus ruff's `UP`
  rules for the course's Python, scan shown code, starters, solutions, full apps and the capstone. Starting entries:

  | Instead of (deprecated) | Write |
  |---|---|
  | `typing.List`, `Dict`, `Optional[X]`, `Union[X, Y]` | `list`, `dict`, `X \| None`, `X \| Y` |
  | `datetime.utcnow()`, `utcfromtimestamp()` | `datetime.now(UTC)`, `datetime.fromtimestamp(ts, UTC)` |
  | `asyncio.get_event_loop()` to run code | `asyncio.run()` |
  | `except asyncio.TimeoutError` | `except TimeoutError` (one class since 3.11) |
  | FastAPI `@app.on_event("startup")` | `lifespan=` context manager |
  | Pydantic v1 `.dict()`, `.json()`, `class Config`, `@validator` | `.model_dump()`, `.model_dump_json()`, `model_config`, `@field_validator` |
  | pandas `DataFrame.append`, chained assignment with `inplace=True` | `pd.concat`, assign the result |
  | scikit-learn `OneHotEncoder(sparse=…)` | `sparse_output=…` |
  | `os.popen`, `distutils`, `imp` | `subprocess.run`, `setuptools`/`sysconfig`, `importlib` |

  Found by the prototype: Starlette 1.7+ wants `httpx2` (Pydantic's continuation of `httpx`, a drop-in with the same
  classes and output) for FastAPI's test client. Decision 12: new AI API courses teach `httpx2` and pin only it;
  `import httpx` in a new course is flagged. The pilot course's Lessons 1–2 and its full app switch when regenerated.
- **Freshness:** a quarterly re-run of the offline, learner-eye and modern-code checks on the newest library releases
  reports chapters whose code has become deprecated, before learners see the warning.

## 5. Capstone: the whole course, end to end (new last chapter)

**Shape.** One extra last chapter per code course, `Capstone: <project>`, with `focus: "project"`. The plugin
proposes its title and description from the earlier chapters; the owner adds it to the input (the order stays
theirs). It builds one working project that uses every chapter, on the course world's data at full size: synthetic,
never real learner records. It is practice, not a certificate requirement.

**Example for *Building Production-Ready AI APIs*: "The Enquiry Reply Assistant, end to end"** on all 2,000
synthetic `enquiry_messages` of Future Vision Computer Institute:

| Milestone | From chapter | The learner builds | Proved by |
|---|---|---|---|
| M1 | L01 LLM integration and streaming | `/draft-reply` calls the provider and streams the draft | `tests/test_m1_streaming.py` |
| M2 | L02 timeouts, retries, rate limits | both timeouts, retries with backoff and jitter, a token bucket per counsellor, clear 504/502/429 | `tests/test_m2_resilience.py` |
| M3 | L03 validation and usage tracking | a Pydantic request model, token estimates, a daily quota, cost per call | `tests/test_m3_usage.py` |
| M4 | L04 logging and health | one JSON log line per request, liveness and readiness | `tests/test_m4_ops.py` |
| Final | all | draft replies for all 2,000 messages in a batch, then a spend report by intent and branch | `tests/test_final_batch.py`, `python report.py` |

**The capstone page** follows the explain-first rules: the problem and what the finished app does, an architecture
figure, one section per milestone (goal, what to build, the short key code, the tests that prove it), "run the whole
thing", extension ideas. Free learners can read it and build it from the page.

**Its pack folder** (certificate holders):

```
L05-capstone-enquiry-reply-assistant/
  README.md      brief, milestones, how to run the tests, how to switch to a real provider
  data/          L05-enquiry-messages.csv (2,000 rows), L05-learners.csv, L05-prices.json
  starter/       the project skeleton with TODOs per milestone; imports and runs, tests fail
  tests/         pytest, one file per milestone: pytest tests/test_m2_resilience.py
  solution/      the complete app, report script and fake provider; every test passes
```

A fake provider makes the project run offline and without an API key; an environment variable switches to a real one.
**Video:** a story-video clip per milestone and a final demo of the tests and the report.

## 5b. Learning flow: read, watch, practise

Each section follows one loop, so the video and the exercise teach the same idea back to back:

1. **Read** the section (idea first, then the case study and short code).
2. **Watch** its topic clip, placed at the end of the section (story video, one clip per section).
3. **Practise** at once: the section's Try It on the page (everyone), then the matching task in the chapter's
   starter notebook (certificate holders). The clip's last scene names that task.
4. **Check** with the on-page answer, or `solutions/` in the pack.

- Every topic clip ends with a "Now practise" card naming the Try It and the starter task
  (for example "Try It: fill in `should_retry` · Pack: `L02-practice-starter.ipynb`, Task 1").
- Starter notebooks follow the section order and name the clip each task follows ("After the video on backoff").
- The capstone has one clip per milestone, then the milestone's tests: watch M2, build M2, run `test_m2_resilience.py`.
- Story-video check: each topic clip's "Now practise" card names a Try It that exists in that section and, when the
  chapter has a pack folder, a task that exists in its starter.

## 6. Lesson markup

The writer declares a chapter's files once; the plugin builds the files and draws the markup, as with screen specs.

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

**First chapter:** the course pack box under the overview.

```html
<div class="nerdit-files nerdit-course-pack" data-nerdit-files="course">
  <p class="nerdit-files-head">📦 Course practice pack <span class="nerdit-files-py">Python 3.14</span></p>
  <p>Download once, then practise chapter by chapter: one folder per chapter with its data, a starter notebook and
     the full solution code, plus the capstone project. Setup steps are in README.txt.</p>
  <a class="nerdit-file nerdit-file-all" href="files/fastapi-ai-apis-practice-pack-v1.zip"
     download="fastapi-ai-apis-practice-pack-v1.zip" data-nerdit-file="fastapi-ai-apis-practice-pack-v1.zip"
     data-format="zip" data-bytes="48213">⬇ Download the course practice pack (v1, 47 KB)</a>
  <p class="nerdit-files-note">5 chapter folders, including the capstone · updated 23 Oct 2026</p>
</div>
```

**Every chapter:** a slim box naming its folder in the pack, with its files folded away for single downloads.

```html
<div class="nerdit-files" data-nerdit-files="timeouts-retries-rate-limits-and-errors-02">
  <p class="nerdit-files-head">📂 Practice files for this chapter <span class="nerdit-files-py">Python 3.14</span></p>
  <p>In your course practice pack: folder <code>L02-timeouts-retries-rate-limits-and-error-handling</code>.</p>
  <details><summary>Download this chapter's files one by one</summary>
    <table>
      <thead><tr><th>File</th><th>What's inside</th><th>Used in</th></tr></thead>
      <tbody>
        <tr><td><a class="nerdit-file" href="files/L02-S1-enquiry-messages.csv" download="L02-S1-enquiry-messages.csv"
               data-nerdit-file="L02-S1-enquiry-messages.csv" data-format="csv" data-bytes="273">L02-S1-enquiry-messages.csv</a></td>
            <td>4 rows: message_id, intent, message</td><td>Section 1</td></tr>
      </tbody>
    </table>
  </details>
</div>
```

**Each section** that uses a file starts its case study with
`<p class="nerdit-file-use">📎 This section uses <a class="nerdit-file" …>L02-S1-enquiry-messages.csv</a> (folder <code>L02-…</code> in your pack).</p>`.

New classes (`nerdit-files`, `nerdit-course-pack`, `nerdit-files-head`, `nerdit-files-py`, `nerdit-files-note`,
`nerdit-file`, `nerdit-file-all`, `nerdit-file-use`) go into the canonical `references/css9-simple.css` and both apps'
`src/lesson-css/` copies in the same change; `node ../nerdit/scripts/check-lesson-sync.mjs` must pass. The price and
lock states are drawn by the learner site (§11), never written into the lesson HTML.

## 7. Paid access: the certificate unlocks the files

| Learner | Lesson page, runner, answers, videos, capstone brief | Practice pack, chapter files, capstone code | Files box shows |
|---|---|---|---|
| Bought the certificate | ✓ | ✓ | download buttons |
| Enrolled, not bought | ✓ | locked | the full list, locked, with **"Unlock with certificate — ₹999: exam, certificate, practice pack and capstone code"** (price from `certificatePrice`) |
| Signed out | ✓ | locked | the same list with **"Sign in"** |
| Admin | ✓ | ✓ (preview) | download buttons |

- **The browser runner never needs a paid file:** its data comes from the lesson's dataset recipe or a small block in
  the lesson (at most 40 KB). Paid files live only under `courses/<courseId>/files/`.
- **Storage rules** allow reading `courses/<courseId>/files/**` for admins and for a signed-in user whose certificate
  purchase for that course is recorded: the record the exam and certificate unlock already use (path to confirm in
  `nerdit`). One Firestore read per download; writes for admins only.

## 8. Verification: no broken or outdated code reaches a learner

| # | Check | Script | Fails when |
|---|---|---|---|
| a | **Every answer runs:** practice solutions, predict answers (in the run lines' namespace), fill-in code with `data-answer` filled in | `check_python_outputs.py`, `check_sql_outputs.py` (extended) | output differs from the page, or code raises or does not compile |
| b | **Offline code runs for real:** `data-run="offline"` examples and each `L<nn>-full-app.py` in a venv from the course requirements | `check_offline_outputs.py` (new) | output differs, a library is not pinned, the app does not start and answer its test requests |
| c | **All practice data is generated:** every data or code course declares a world (decision 8) | `check_input.py --strict`, `check_world.py` | no world; typed-in data over 8 rows; a value outside the world (declared defects aside) |
| d | **Learner-eye test:** unzip the pack into an empty folder; one fresh venv; `pip install -r requirements.txt`; in every chapter folder run the starter and solutions `.py` (from the pack root and from the folder), execute both notebooks in their folder, run each `.sql` in SQLite | `check_files.py --as-learner` | any error; a missing file; a file the code opens that is not in its folder; the pack over 10 MiB or a file over 5 MiB; a chapter's single files differing from its pack folder |
| e | **One source, three copies agree:** page tables, pack files, browser runner files | `check_files.py` | the browser build's sha256 ≠ the file; shown rows missing from the file; a solution's output differs from the page |
| f | **Computable quiz answers are computed** | `check_quiz.py` (new) | the marked option is not the computed result |
| g | **No deprecated code:** all runs with `-W error`; static scan against `references/deprecated.md` and ruff `UP` | `check_modern_code.py` (new), and the flags in a, b, d | any warning, or a banned API anywhere a learner sees or downloads |
| h | **Names and links:** §2 names, unique with images; every `files/` link has a file and every file is linked; each file parses | `check_files.py` | any of these |
| i | **Capstone:** the solution passes every test and `report.py` prints the documented report; the starter imports and runs; **each milestone's tests fail on the starter and pass on the solution**; the page's short code is part of the solution; every data file in `data/` is built from the course world (decision 13) | `check_capstone.py` (new), `check_sequence.py` | any of these |

Exit codes as the existing checks (2 = environment missing, never a pass). A failure regenerates the chapter within
the 2-attempt budget, then stops and reports.

## 9. Plugin work (phase 1)

- [ ] **Rules:** CORE.md §5, a new §6e "Practice files" and a "Capstone chapter" section (`focus: "project"`, milestone
      sections, tests); the page/download split; `references/deprecated.md`; writer agent, QA checklist,
      runners/python.md, sql.md, excel.md.
- [ ] **`scripts/practice_files.py`:** reads each chapter's spec; builds every file (world slices via
      `make_world_data.py`, lesson tables, recipe builds, seed scripts, JSON, starters and solutions as `.py` and
      `.ipynb`, full apps, the capstone folder); fits the 10 MiB pack (samples, data pack if needed); writes the pack
      with its chapter folders, course `README.txt` and `requirements.txt`, `<workdir>/files.manifest.json`
      (`name, format, bytes, sha256, lessonId, sections, about, source, packVersion`); inserts the first-chapter pack
      box, each chapter's folder box and the section lines.
- [ ] **Capstone generator:** proposes the capstone chapter's title and description from the earlier chapters; the
      writer writes the page; the plugin builds `starter/`, `tests/`, `solution/` and `data/`.
- [ ] **Checks a–i** with tests; `gate_lesson.py` and `verify_course.py` run them.
- [ ] **Output for the admin: one course bundle zip** (§10) with the output JSON, `media/images/`, `media/files/`,
      `videos/clips.json`, thumbnail, description and `bundle.json` (`scripts/make_bundle.py`, checked by
      `check_bundle.py`: every link resolves inside the bundle, sha256s match, sizes within limits). The illustrator
      and story video write into the same workdir; the old `<images>/upload/` path stays readable.
- [ ] **Story video:** each topic clip ends with a "Now practise" card (§5b) checked against the section's Try It and the starter; a `table` scene may name its practice file; the description lists the pack; one clip per capstone milestone.
- [ ] **Pilot:** *Building Production-Ready AI APIs*: Lesson 2 folder complete (prototype built and tested on Python
      3.14, 2026-10-23), the other chapters as they are regenerated, and the capstone.

## 10. Admin contract (`nerdit-admin`)

**One course bundle, one import.** The plugin writes one zip per course version; the admin uploads that single file.

```
building-production-ready-ai-apis-bundle-v1.zip
  course-building-production-ready-ai-apis_output.json   the final course JSON: lessons, quiz, media links, video slots
  media/images/…                                         raster images (public storage, as today)
  media/files/…                                          the practice pack and every chapter file (private storage)
  videos/clips.json                                      one entry per clip: key, chapter, section, title, YouTube link
  videos/thumbnail.jpg  videos/description.txt
  bundle.json                                            course id, versions, pack version, sha256 of every file
```

- **Videos stay on YouTube.** MP4s are not in the bundle: hosting video in Firebase would cost about ₹9,000 a month
  per 10,000 course views, against ₹0 on YouTube. Staff upload the clips to YouTube (Unlisted) and either paste each
  link into `videos/clips.json` before import, or paste them in the admin's Videos box after import; empty slots stay
  hidden from learners. Later option: an "Upload to YouTube" button in the admin through the YouTube Data API, which
  needs a quota increase for bulk uploads (the default daily quota allows only a few uploads).
- **Import course bundle** replaces "Import JSON + Images": it checks `bundle.json` (every file present, sha256
  matches, names unique, sizes within limits), shows a preview, then uploads images (public), files (private, §7)
  and fills video slots from `clips.json`. A newer bundle version uploads only files whose sha256 changed.
- Bundle size: at most 100 MiB (images are already WebP; the pack is at most 10 MiB).
- The separate "Import JSON + Images" stays available for old courses.

Details:

Phase 2 status (24 Oct 2026, `nerdit` 1630bae, `nerdit-admin` 73e6baf): the import screen takes the bundle; round trip
passes with the pilot bundle (`nerdit-admin/tests/fixtures/ai-apis-bundle-v1.zip`). Open items are marked below.

- [x] The bundle's `media/` folder follows these rules. Allowed: `.csv .json .jsonl .sql .py .ipynb .txt .md .zip`;
      refused: `.xlsx .xlsm .exe .html .js` and anything else (`.xlsx` dropped for now). Size limits as decision 3 (50 MiB while measuring; target 5 MiB per file and 10 MiB for a
      `*-practice-pack-v<n>.zip` or `*-data-pack-v<n>.zip`).
- [x] Matching as for images: by file name across nested folders; a missing or duplicate name blocks preparation;
      extra files enter the course library; a new pack version replaces the old one. *(A new pack has a new name, so
      the lessons link it; the old pack stays in the private library, listed "Not linked from any lesson".)*
- [x] Validation: extension vs content (zip signature for zip, UTF-8 text, JSON and notebook JSON parse).
- [x] **Private storage:** `courses/<courseId>/files/<sha256 8 chars>/<original name>`, `Content-Type` by extension,
      `Content-Disposition: attachment; filename="<original name>"`; no public download tokens. The HTML keeps the
      relative `files/<name>` link and `data-nerdit-file`; the learner site resolves it.
- [x] **Storage security rules** as §7; rules tests for certificate holder, enrolled without certificate, signed out, admin.
- [x] Media records hold `kind: "file"`, name, sha256, bytes, storage path, so re-import and Export output JSON
      round-trip by original name, as images do.
- [ ] Media library lists files with the chapters that use them *(done)*; sections, the "replaced, review these
      chapters" flag and admin preview downloads move to Phase 3, which builds the one download helper both sites use.
- [x] Sanitizer allowlist: the new classes, `a[download]`, `details`/`summary` in the box, the `data-*` attributes above;
      `script.nerdit-files-spec` kept in the JSON, never rendered. The two `<!-- nerdit-files -->` marker comments are
      kept (every other comment is removed), so an exported course re-runs through `mark_lesson` without doubling boxes.
      *(Open: `href` limited to relative `files/` on `a.nerdit-file`; today DOMPurify's own URL rules apply.)*
- [x] Tests: import → publish → export → import round trip with the pilot bundle (csv, json, py, ipynb, pack zip);
      duplicate and missing-file blocks. *(jsonl, sql, txt and md are covered by the bundle reader's own tests.)*

## 11. Learner site contract (`nerdit`: `future-vision`, `shared`)

Phase 3 status (24 Oct 2026, `nerdit` d75a056, `nerdit-admin` de1bcef, plugin 7440cb7): done except where marked.
Browser check on the emulators (`functions/scripts/practice-files-browser-seed.mjs`, sign-in at
`/tests/emulator-login.html`): the paid learner's box opens and the CSV downloads with its name and exact bytes, kept
in Cache Storage by sha256; the unpaid learner sees "Unlock with certificate — ₹999", and a click opens the
certificate step with no download. Signed out, free and revoked cases: unit tests plus `practice-files-itest.mjs`.

- [x] `shared`: media record gains `kind: "image" | "file"`, `format`, `bytes`, `sha256`, `storagePath`; rebuild.
- [x] Lesson CSS copies updated with the plugin (§6); `normalizeLessonHtml` keeps the boxes and links, drops links to
      other origins. *(A practice link to anything but `files/<name>` becomes plain text.)*
- [x] **Certificate-only downloads (§7):** a click on `a.nerdit-file` fetches the file with the Firebase SDK (`getBlob`
      on the storage path, checked by the rules) and saves it under `data-nerdit-file`. Not bought: the box shows the
      list locked with "Unlock with certificate — ₹<certificatePrice>", linking to the certificate purchase. Signed out:
      "Sign in".
- [x] **Runners:** stay on Pyodide 0.26.2 (§4). Data only from recipes or in-lesson blocks; never a paid file. With a
      files box present, the runners skip their own Blob download links.
- [x] Files fetched for download are kept in the browser's Cache Storage by sha256, so a second click does not
      download again.
- [x] Download UX: format, size and "Python 3.14" shown; one tap on a phone; the pack button is the main action in the
      first chapter; other chapters show their folder, with single files folded away. *(Busy look while a file
      downloads; locked links dimmed but readable.)*
- [ ] Tests: `normalizeLessonHtml` keeps the markup *(done)*; browser check as certificate holder and enrolled without
      certificate *(done, through the Playwright tools, not yet a committed Playwright suite)*; signed out is not
      reachable in the classroom (sign-in is required) and is unit tested; a Try It without any paid file is covered by
      the runner tests, not yet in a browser.
- [ ] Admin preview downloads *(done, moved from §10)*; per-section use and the "replaced, review" flag still open.

## 12. Rollout

| Phase | Where | Done when |
|---|---|---|
| 1 | plugin | §9 complete; the pilot course's pack (with capstone) passes checks a–i |
| 2 | admin | Import course bundle, private upload, rules tests and round-trip pass with the pilot bundle |
| 3 | learner site | CSS sync check passes; Playwright access tests pass |
| 4 | all three | end to end: generate → import → preview → publish → a certificate holder downloads the pack and runs every chapter and the capstone |
| 5 | trial | one batch of 20–30 institute students uses the pilot pack for a week: downloads, finished practice tasks, capstone milestones reached, where they got stuck |
| 6 | courses | backfill published courses: worlds per decision 8, packs, solutions, a capstone chapter each, re-check on Python 3.14; re-import each reviewed final JSON |

Phase 1 ships nothing to learners until phases 2 and 3 are released.

## 13. Cost (Google)

- **Storage:** about 12 GB for 500 courses with packs, about ₹25 a month.
- **Downloads:** free up to 100 GB a month, then about $0.12 per GB. A pack is at most 10 MiB, so 10,000 certificate
  holders downloading a full pack is at most about 100 GB a month (free to about ₹1,000); API courses are under 1 MiB.
- **Certificate check:** one Firestore read per download (50,000 reads a day free).
- **No server or Cloud Function** streams the files; videos stay on YouTube. Set a budget alert.

## 14. Risks and answers

| Risk | Answer |
|---|---|
| Too many files overwhelm beginners | one pack button in the first chapter; per-chapter files folded away; starter first, solutions in a subfolder |
| Learners copy solutions before trying | starter first; solutions labelled "check your work after you try"; capstone tests show progress |
| Local Python setup is hard for absolute beginners | the in-browser runner stays the main practice; the pack is for intermediate, data and project courses |
| Libraries change (`httpx` → `httpx2`) | pinned versions per course; quarterly freshness check |
| A data course does not fit 10 MiB | samples, then a separate data pack |
| A pack is outdated after an update | versioned packs, changelog in README, single-file downloads per chapter |
