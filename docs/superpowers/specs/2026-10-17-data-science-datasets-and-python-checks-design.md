# Plan C — Data Science datasets and Python output checks — design

Date: 2026-10-17. Status: draft for review.
Builds on: [teaching visuals v11 spec](2026-10-15-teaching-visuals-v11-and-data-modelling-remediation-design.md)
§1.11 (business worlds) and Plan B (`make_world_data.py`, `check_world.py`, `references/worlds/`).

## Goal

Make the plugin ready to generate the Data Science career program: Python, statistics,
machine learning, time series, recommendations and NLP courses. Three outcomes:

1. **Data a model can learn from.** The world generator produces realistic, seeded datasets
   with relationships between columns, planned messiness, time series, user × item
   interactions and short texts, at a scale of up to 20,000 rows.
2. **Datasets inside lessons without hosting.** A lesson carries a small recipe. The
   website's Python runner builds the CSV files in the browser before the learner's code runs,
   so `pd.read_csv("enquiries.csv")` works like it does on a real computer.
3. **No Python output ships unchecked.** A checker runs every Python example on the same
   engine the website uses and compares it with the output shown in the lesson.

## Why

- **The generator is built for small SQL lessons.**
  - At most 100 rows per entity (`make_world_data.py:86`).
  - Every column is drawn independently: `id`, `choice`, `weighted_choice`, `int_range`,
    `money_range`, `date_range`, `fk`, `person_name`.
  - A model trained on such data learns nothing, and no lesson can show a real relationship.
- **Python outputs are not verified.** `check_sql_outputs.py` exists for SQL; nothing checks
  Python. The Data Modelling course showed the cost: 18 wrong SQL outputs shipped in script-made
  lessons before a checker existed. A Data Science program is mostly Python.
- **The Python runner has no way to load data.**
  - Each Try It runs in a fresh namespace (`nerdit-python-runner.js:57-61`).
  - There is no seed or setup block (`runners/python.md`: "no seed block").
  - Lessons today can only use tiny lists typed into the code.
- **A lesson cannot carry a big file.** Each lesson is one Firestore document, capped at
  1,048,576 bytes. A 10,000-row CSV does not fit, and hosting CSVs would add Storage egress
  (the September Firestore bill is the warning).
- **The browser engine has limits.** Pyodide 0.26.2 (the version the site loads) runs the
  scientific Python stack. It cannot run TensorFlow/Keras, PyTorch, PySpark, Flask/FastAPI or
  Docker. The program's Deep Learning, Computer Vision, PySpark and Deployment courses need a
  different kind of lesson.
- **The program has gaps:** Unsupervised Learning, Recommendation Systems, Explainable AI,
  Deep Learning, Computer Vision, NLP, PySpark, ML Deployment, plus partial Linear Algebra &
  Calculus. Each needs suitable data before it can be generated.

## Decisions

| Question | Decision |
| --- | --- |
| How datasets reach a lesson | **Generated in the browser from a recipe.** The lesson embeds a small JSON recipe; the runner builds the CSVs into Pyodide's in-memory file system before any code runs. No hosted files. |
| One generator or two | **One.** The generation core becomes `references/nerdit_world_gen.py` (stdlib only, no file access). `make_world_data.py` imports it for offline use; the website serves an identical copy to Pyodide. |
| Randomness | **Python's stdlib `random` (Mersenne Twister) with a fixed seed**, never NumPy's generator. The same recipe and seed give byte-identical CSVs in local CPython and in Pyodide. A test proves it. |
| Python output checker engine | **The website's own engine:** Node.js running the `pyodide` npm package pinned to **0.26.2**, the version in `nerdit-python-runner.js` and `nerdit-plot-runner.js`. Same versions, same printing, same floats. |
| Libraries the browser cannot run | **Offline run lines** (`data-run="offline"`): shown code plus output captured in a pinned local environment. Plan C defines the contract and the checker reports them as offline; building the offline verifier is a separate later plan (Plan D). |
| Business names | Same safeguards as §1.11. **Future Vision Computers** uses its real name with the owner's approval recorded (the course author is the owner). The other four use invented names until each owner's permission is recorded; their business patterns come from `docs/superpowers/notes/2026-10-15-world-sources.md`. |
| Scope of course work | **None.** Plan C prepares the plugin and the website runner. Courses are generated later through the normal pipeline. |

## Non-goals

- Generating any Data Science course.
- The offline verifier for TensorFlow, PyTorch, PySpark, Flask/FastAPI and Docker lessons (Plan D).
- Image datasets for Computer Vision (needs its own design; Plan D).
- Hosting CSV files in Storage or on the website.
- Changing existing SQL lessons or the Data Modelling course.

## Part 1 — Data recipes in the generator

### 1.1 Profiles and size

- A world (or a single entity) declares `"profile": "sql"` (default) or `"analytics"`.
- `sql`: today's limits, at most 100 rows per entity.
- `analytics`: at most **20,000 rows per entity** and **200,000 cells per dataset**.
- Generation time budget in Pyodide: at most 2 seconds for 20,000 rows × 10 columns, measured
  by a test on the checker's engine.

### 1.2 New column generators (declarative; no expressions, no `eval`)

| Generator | Parameters | Use |
| --- | --- | --- |
| `normal` | `mean`, `sd`, optional `min`, `max`, `round` | marks, heights, gauge readings |
| `lognormal` | `median`, `sigma`, optional `round`, `max` | order values, incomes |
| `poisson` | `lam` | enquiries per day, defects per roll |
| `bernoulli` | `p` | yes/no flags |
| `linear` | `intercept`, `terms` {column: weight}, `effects` {category column: {value: delta}}, `noise_sd`, optional `round`, `min`, `max` | a number that depends on other columns (price from gauge and mesh) |
| `logistic` | the same `intercept`, `terms`, `effects`, plus optional `target_rate` | a 0/1 label driven by other columns; `target_rate` sets class balance by solving the intercept deterministically (bisection, 40 steps) |
| `binned_effect` | `column`, `edges`, `deltas` | a step change by range, so tree models have something linear models miss |
| `text` | `templates`, `slots` {name: [values]}, optional `tone_from` {label column: {value: [templates]}} | reviews and enquiry messages whose wording follows a label (for NLP) |

- A column may depend only on columns that come before it in a dependency order. Columns are
  sorted topologically, and a cycle is an error, the same rule as foreign keys today.
- Because the weights are declared, the **true effect of every feature is known**. Explainable
  AI lessons can compare a model's importances with the truth.

### 1.3 New entity kinds

- **`segment` mixture (any table).** `"segments": {"name": {"weight": 0.3, "overrides": {column: params}}}`.
  Each row draws a segment, and listed columns take that segment's parameters. A hidden `_segment`
  column (the underscore keeps it from clashing with a real column) is kept for checking and
  can be dropped from the CSV. This gives clustering lessons
  clusters that are really there.
- **`series`.** One row per period from `start` to `end` with `freq` `day`, `week` or `month`:
  `base`, `trend_per_period`, `weekly` (7 multipliers), `monthly` ({"1"…"12"} multipliers, like
  today's month weights), `holidays` [{date, lift, days}], `noise_sd`, optional `break`
  {date, shift}. Gives forecasting lessons trend, seasonality, festival spikes and a structural change.
- **`interactions`.** `users` (entity), `items` (entity), latent factors `k` (1–5), `density`
  (0.01–0.3), rating `scale` [min, max], `noise_sd`. Ratings come from user × item factor
  products, so collaborative filtering has a real signal to find.

### 1.4 Planned messiness (`defects`, per entity)

| Defect | Parameters |
| --- | --- |
| `missing` | [{column, rate, optional `when` {column: value}}] |
| `outliers` | [{column, rate, factor}] |
| `duplicates` | rate (copies of existing rows, new ids) |
| `label_noise` | {column, rate} |
| `drift` | {after (date), column, shift} |

Every injected defect is recorded in `world_data.json` under `defects` with the affected row
ids, so a lesson can say exactly which rows are dirty and QA can check the claim.

### 1.5 Determinism rules

- Only these stdlib calls draw randomness: `random.Random(seed)` with `random()`, `gauss()`,
  `lognormvariate()`, `expovariate()`, `choices()` and `shuffle()`. Poisson uses Knuth's method
  on `random()`. These are stable across Python 3.12 (Pyodide) and 3.14 (local).
- Entities, columns and segments are traversed in sorted order (the existing rule).
- Floats are written with `repr` rounded to the declared `round` (default 2 decimals) before CSV output.
- **Test:** the same recipe generated by local CPython and by Pyodide on the checker engine gives
  identical SHA-256 per CSV file.

### 1.6 Validation

- Unknown keys, out-of-range parameters, unknown generators and dependency cycles fail with a
  message naming the entity and column.
- Contact fields stay forbidden (the existing rule); `text` slots are checked against the same
  name/contact patterns.

## Part 2 — Datasets inside lessons

### 2.1 Lesson markup

One dataset block per lesson, before the first Python example:

```html
<script type="application/json" class="nerdit-dataset">
{"seed": 7, "files": {"enquiries.csv": {"entity": "enquiries", "drop": ["_segment"]}},
 "world": { ...only the entities those files need... }}
</script>
```

- The block must be at most **40 KB**. `verify_course.py` v11 fails a larger block or invalid JSON.
- The lesson's opening section names each file and its columns in one small value table
  (figures.md §11), so the learner knows what they are loading.

### 2.2 What the runner does

`nerdit-python-runner.js` and `nerdit-plot-runner.js`:

1. On the first run on a page, if the page has a `.nerdit-dataset` block, load
   `/nerdit_world_gen.py` once into Pyodide.
2. Generate the files and write them to Pyodide's working directory (`/home/pyodide`). They
   persist for the page session.
3. Then run the learner's code as today, in a fresh namespace. `pd.read_csv("enquiries.csv")`
   works.
4. Show a small **"Download CSV"** link under the first Try It, built in the browser (a `Blob`),
   so learners can open the same data in Excel or Jupyter.

A page without a dataset block behaves exactly as today.

### 2.3 One copy of the runtime files

- `references/nerdit_world_gen.py` and the runner JS files in `references/` are the source of
  truth, copied to `nerdit/future-vision/public/`.
- A new `check_runtime_bundle.py` (like `check_css_bundle.py`) fails when the copies differ.
  Today the runner JS files have no such check.

### 2.4 Writer rules (`runners/python.md`, `runners/plot.md`, `CORE.md`)

- Every Try It starter program runs on its own in a fresh namespace. It reads its data file itself.
- Run lines in a lesson build on each other in page order, like a notebook.
- Every random call in shown code takes a seed (`random_state=7`, `np.random.default_rng(7)`).
- Data comes from the dataset block, never typed-in lists of more than 8 rows.

## Part 3 — Python output checker

### 3.1 `check_python_outputs.py --course <course.json> [--lesson <id>]`

- **Driver:** Python stdlib. It sends each lesson's job as JSON to
  `scripts/pyodide_engine.mjs`, which runs on Node with `pyodide@0.26.2` from a plugin-local
  `tools/pyodide/package.json`. Packages are cached in `tools/pyodide/.cache`; `node_modules`
  and the cache are git-ignored.
- **Per lesson:**
  1. Build the dataset files from the lesson's block.
  2. Run every Python run line in page order in one namespace (the notebook rule).
  3. Run each Try It starter program alone in a fresh namespace.
- **Comparison:**
  - Normalise line endings and trailing spaces, and drop trailing blank lines.
  - Then the shown output must equal the printed output exactly.
  - Shown errors must match the runner's friendly last line (`ErrorType: message`).
- **Plot lessons:** the code must run without error and leave at least one Matplotlib figure.
  The image is not compared; QA checks the description.
- **Try It starters:** must run without an exception. Their output is not shown in the lesson,
  so it is not compared.
- **Offline run lines** (`data-run="offline"`): reported as `offline`, never as a pass.
- **Exit codes:** 0 = all match; 1 = any mismatch or failing starter; 2 = engine missing or
  unreadable file. A missing engine is never a silent pass.

### 3.2 `--probe <module,...>`

Loads each module in the pinned engine and prints its version, or reports that it cannot load.
Writers and the orchestrator use it before planning a course: "does seaborn load?" is answered
by the engine, not by memory.

### 3.3 Integration

- `gate_lesson.py` runs the checker for lessons whose runner is `python` or `plot`.
- `SKILL.md` Step 4c runs it next to `check_sql_outputs.py`.
- The QA validator no longer judges Python outputs it cannot run.

## Part 4 — Data Science worlds

### 4.1 World library

Five worlds in `references/worlds/`, all `profile: "analytics"`, each with a cast and an `arc`
template:

| World file | Business name in lessons | Datasets |
| --- | --- | --- |
| `fvc-institute.world.json` | Future Vision Computers (real; owner approval recorded) | enquiries → enrolment (logistic, about 30% positive), learners with segments, daily enquiry counts (series, poisson), batch scores (normal), enquiry messages (text with intent) |
| `saree-wholesale.world.json` | invented until permission | retailers with segments, weekly orders by category (series with Diwali and wedding-season lifts), retailer × SKU purchases (interactions), order lines with missing values, duplicates and outliers |
| `stationery-d2c.world.json` | invented until permission | customers, orders with coupons and discounts, customer × product ratings (interactions), reviews (text with tone from rating), a yearly launch spike (series) |
| `boat-cruises.world.json` | invented until permission | bookings by event type, daily bookings (series with Christmas and NYE peaks), price vs guests (linear), cancellations (logistic) |
| `wire-mesh.world.json` | invented until permission | product specs (gauge, mesh size, roll width), price per roll (linear with binned effects), QC measurements with outliers and drift, defect flags (logistic, about 5% positive) |

### 4.2 Course → world map (Data Science program)

| Course | World | Recipe |
| --- | --- | --- |
| Statistics & Probability | FVC | batch scores (normal), daily enquiries (poisson), conversion (bernoulli) |
| NumPy | Wire mesh | measurement arrays |
| Pandas, Data Cleaning | Saree wholesale | order lines with planned defects |
| SQL for Data Science | Saree wholesale (`sql` profile) | retailers, orders |
| EDA, Matplotlib, Seaborn | Stationery D2C; boat cruises | launch spike; seasonal bookings |
| Feature Engineering | FVC | enquiries (dates, categories, binned effects) |
| Regression | Wire mesh; boat cruises | price per roll; price vs guests |
| Classification, Model Evaluation | FVC | enrolment label with imbalance and label noise |
| Unsupervised Learning | Stationery D2C; saree wholesale | customer and retailer segments |
| Ensembles (Random Forest, boosting) | Wire mesh | defect flags with binned effects |
| Time Series | Saree wholesale; boat cruises | weekly orders; daily bookings |
| Recommendation Systems | Stationery D2C | customer × product ratings |
| Explainable AI | FVC | the enrolment model compared with the declared true weights |
| NLP | Stationery D2C; FVC | reviews with tone; enquiry intent |
| Linear Algebra & Calculus | none | numeric examples |
| Deep Learning, CV, PySpark, Deployment, MLOps | any (offline datasets from `make_world_data.py`) | offline run lines, Plan D |
| Capstone | one world end to end | all of the above |

## Success criteria

- `make_world_data.py` builds every new generator, entity kind and defect from the five worlds,
  and its output is identical in CPython and in the checker's Pyodide (hash test).
- 20,000 × 10 generates in at most 2 seconds in the checker's Pyodide.
- `check_python_outputs.py` passes a fixture lesson whose outputs are right. It fails one with a
  changed number, a missing error line, a failing Try It starter or a missing engine.
- In a dev fixture, a Python Try It reads `enquiries.csv` and prints its first rows, and the
  Download CSV link gives the same bytes as `make_world_data.py`.
- `check_runtime_bundle.py` passes; plugin and website copies are identical.
- All existing plugin tests still pass; existing SQL behaviour is unchanged.

## Testing

- **Each generator and defect:** fixed-seed tests for exact values. Statistical tests (on 5,000
  rows, the fitted weight is within 10% of the declared one; `target_rate` is within one
  percentage point).
- **Engine tests** (skipped with a clear reason when Node or the engine cache is missing, and
  required by the gate):
  - CPython vs Pyodide hash equality
  - the timing budget
  - the checker fixtures
- **Website:** vitest for the dataset-block parser in the runner. Playwright on a dev fixture
  checks the Try It output and the Download CSV link at 1280 and 390 px.

## Effort (estimate)

About 16 tasks, similar to Plan A. The engine setup (Node + Pyodide cache) is the main new risk.
A probe task comes first and stops the plan if Pyodide 0.26.2 cannot run in Node on this machine.

## Follow-ups (not in this project)

- **Plan D:** the offline verifier for TensorFlow/Keras, PyTorch, PySpark, Flask/FastAPI and
  Docker lessons, plus image datasets for Computer Vision.
- Recording permission for the four other businesses, then switching their worlds to real names.
- Generating the Data Science program's missing courses with these worlds.
- Upgrading Pyodide later means re-running `check_python_outputs.py` on every Python course,
  because printed floats and library behaviour can change.
