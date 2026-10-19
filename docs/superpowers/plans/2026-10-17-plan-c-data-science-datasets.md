# Plan C — Data Science Datasets and Python Output Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the world generator to produce learnable Data Science datasets, let lessons build those datasets in the browser, and verify every Python example on the website's own Pyodide engine.

**Architecture:**
- The generation core moves to `references/nerdit_world_gen.py`: stdlib only, no file access. `make_world_data.py` keeps file I/O and re-exports the core, so existing importers keep working.
- Python checks run in Node on `pyodide@0.26.2`, the website's version, through a small JSON-over-stdio engine that a Python driver calls.
- The website runners read a `.nerdit-dataset` recipe, run the same generator file inside Pyodide, and write CSVs to its file system.

**Tech Stack:** Python 3.14 stdlib + pytest (plugin); Node 24 + `pyodide@0.26.2` (checker engine); plain browser JS (runners); vitest + Playwright (website).

**Spec:** `docs/superpowers/specs/2026-10-17-data-science-datasets-and-python-checks-design.md`

## Global Constraints

- `nerdit_world_gen.py`:
  - stdlib only; no file I/O, network, `eval`, `exec`, `format` with user templates, or imports beyond `random, math, datetime, re, csv, io, json`
  - randomness only through `random.Random(seed)` with `random()`, `gauss()`, `lognormvariate()`, `expovariate()`, `choice()`, `choices()`, `randint()`, `shuffle()`
- **Existing worlds must generate byte-identical output** after every task: `practice-retail` and any world with `records`.
- Profiles:
  - `sql` (default): at most 100 rows per entity.
  - `analytics`: at most 20,000 rows per entity and 200,000 cells per dataset.
  - 20,000 × 10 generates in at most 2 s in the checker's Pyodide.
- Dataset block: at most 40 KB, valid JSON, self-contained (no `"use"` reference).
- Engine pinned to `pyodide@0.26.2`, the same as `nerdit-python-runner.js` and `nerdit-plot-runner.js`.
- Checker exit codes: 0 = all match; 1 = mismatch or failing Try It starter; 2 = engine missing or unreadable input. A missing engine is never a pass.
- Business names:
  - Only `fvc-institute` uses a real name, with `realName` recorded as approvedBy `owner (course author)`, date `2026-10-17`, note `approved in the planning chat`.
  - The other four worlds use invented names.
- Tests: from each `scripts/` dir run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`. Engine tests skip, with the reason, when the engine is not installed.
- **Commits:** only after the user approves; stage only the files a task lists. **No deploys.** No course files under `nerdit/generated/` change.

## Review Focus

1. **Existing SQL worlds regenerate unchanged** after the core moves and dependency ordering arrives. Test: `test_existing_worlds_are_byte_identical` (Task 2).
2. **The engine is unavailable** (no Node, no `npm ci`, no network for the first package download). The checker exits 2 with a clear message, the gate fails, and unit tests skip with a reason. Test: `test_missing_engine_exits_2` (Task 10).
3. **Example code never ends** (`while True: pass`). The checker stops at the timeout and reports a failure instead of hanging. Test: `test_runaway_code_times_out` (Task 10).
4. **Text values with commas, quotes or newlines.** The CSV round-trips through `csv.reader` and `pandas.read_csv`. Tests: `test_csv_quotes_round_trip` (Task 2), `test_text_csv_reads_back_in_pandas` (Task 8).
5. **A dataset block that references the library** (`{"use": "fvc-institute"}`). The browser cannot read library files, so v11 fails the block. Test: `test_dataset_block_must_be_self_contained` (Task 9).

---

## File map

| File | Responsibility | Task |
| --- | --- | --- |
| `skills/nerdit-chapter-generator/tools/pyodide/package.json`, `engine.mjs`, `README.md`, `.gitignore` | Node engine pinned to 0.26.2 | 1 |
| `scripts/pyodide_engine.py`, `scripts/test_pyodide_engine.py` | driver: availability, `run_job` | 1 |
| `references/nerdit_world_gen.py` | shared generation core | 2–7 |
| `scripts/make_world_data.py` | file I/O, library resolution, re-exports | 2, 7 |
| `scripts/test_world_gen_analytics.py` | new generator tests | 3–7 |
| `scripts/test_world_engine.py` | CPython ↔ Pyodide hash, timing, pandas read-back | 8 |
| `scripts/verify_course.py`, `scripts/test_verify_v11.py` | dataset-block check | 9 |
| `scripts/check_python_outputs.py`, `scripts/test_check_python_outputs.py` | Python output checker | 10 |
| `scripts/gate_lesson.py`, `SKILL.md`, `references/runners/python.md`, `references/runners/plot.md`, `references/CORE.md`, `agents/*.md` | integration and rules | 11 |
| `scripts/check_runtime_bundle.py`, `scripts/test_check_runtime_bundle.py` | runner + generator copy check | 12 |
| `references/nerdit-python-runner.js`, `references/nerdit-plot-runner.js` (+ copies in `nerdit/future-vision/public/`), `nerdit/future-vision/src/utils/datasetRecipe.test.ts`, fixture lesson | browser datasets, Download CSV | 14 |
| `references/worlds/{fvc-institute,saree-wholesale,stationery-d2c,boat-cruises,wire-mesh}.world.json`, `references/worlds/ds-course-map.json`, `references/worlds/README.md`, `scripts/test_ds_worlds.py` | Data Science worlds and course map | 13 |

Paths without a prefix are under `skills/nerdit-chapter-generator/`.

---

### Task 0: Baseline

- [ ] Record the test counts of both suites. Expected: all pass. Write the numbers to the ledger.
- [ ] Record SHA-256 of `make_world_data.py --world references/worlds/practice-retail.world.json` output (`world_data.json`, `world_data.sql`) into `scripts/fixtures/practice-retail.sha256`, one line per file. Task 2 asserts against it.

---

### Task 1: Pyodide engine (probe first)

**Files:** Create `tools/pyodide/package.json` (`"pyodide": "0.26.2"`, private), `tools/pyodide/engine.mjs`, `tools/pyodide/README.md` (setup: `npm ci` in that folder; first run downloads packages), `tools/pyodide/.gitignore` (`node_modules/`, `.cache/`), `scripts/pyodide_engine.py`, `scripts/test_pyodide_engine.py`.

**Interfaces:**
- Engine protocol: stdin is one JSON job, stdout is one JSON result.
  - Job: `{"files": {name: text}, "steps": [{"id": str, "code": str, "fresh": bool}], "probe": [module]}`
  - Result: `{"versions": {module: version | null}, "results": [{"id", "stdout", "error": str | null, "figures": int}]}`
  - Non-fresh steps share one namespace; fresh steps get a new one.
  - Packages load per step through `loadPackagesFromImports`.
  - Matplotlib uses the Agg backend; `figures` = `len(plt.get_fignums())` after the step, then `plt.close('all')`.
  - `error` = the last line of the Python traceback (`Type: message`).
- Produces in `pyodide_engine.py`:
  - `ENGINE_DIR: Path` (env `NERDIT_PYODIDE_DIR` overrides; default `tools/pyodide`)
  - `engine_available() -> tuple[bool, str]` (Node on PATH and `ENGINE_DIR/node_modules/pyodide` exists; the reason otherwise)
  - `class EngineError(Exception)`, `class EngineTimeout(EngineError)`
  - `run_job(job: dict, timeout: int = 120) -> dict` (raises `EngineError` when unavailable or on a bad result, `EngineTimeout` on timeout, killing Node)

- [ ] **Step 1: Probe.** Run `npm ci` in `tools/pyodide`, then a one-off script that loads Pyodide in Node and imports `numpy, pandas, sklearn, scipy, matplotlib, statsmodels, seaborn`. Record each version, or "cannot load", in the ledger. **If Pyodide 0.26.2 cannot run in Node here, stop the plan and report** (spec "Effort"). Record the working `loadPyodide` options (package cache location) as a ruling.
- [ ] **Step 2: Failing tests** in `test_pyodide_engine.py`:
  - `test_engine_reports_unavailable_for_an_empty_dir`: env `NERDIT_PYODIDE_DIR` set to `tmp_path`; `engine_available()[0] is False` and the reason names `npm ci`. Always runs.
  - Engine-only, skipped with the reason when unavailable:
    - `test_shared_and_fresh_namespaces`: step a `x = 2`, step b `print(x)` → `"2"`; fresh step c `print(x)` → error `NameError: name 'x' is not defined`.
    - `test_files_are_readable`: files `{"t.csv": "a\n1\n"}`; `print(open('t.csv').read().strip())` → `"a\n1"`.
    - `test_probe_reports_versions`: probe `["numpy", "nosuchmod"]` → numpy version is a non-empty string; `nosuchmod` → `None`.
    - `test_figures_are_counted`: `import matplotlib.pyplot as plt; plt.plot([1, 2])` → `figures == 1`.
- [ ] **Step 3: Run.** Expected: FAIL (module missing).
- [ ] **Step 4: Implement** `engine.mjs` and `pyodide_engine.py` to the protocol above.
- [ ] **Step 5: Run.** Expected: PASS, with engine tests run, not skipped, on this machine.
- [ ] **Step 6: Commit** (if approved) — `feat(checker): pinned Pyodide 0.26.2 engine for Python output checks`.

---

### Task 2: Move the generation core; dependency order; CSV

**Files:** Create `references/nerdit_world_gen.py`. Modify `scripts/make_world_data.py` (keep `load_world`, `sql_dump`, `main`, `LIBRARY`; import and re-export `validate_world`, `generate`, `GENERATORS`, `PRIVATE`, `IDENT` from the core). Test: `scripts/test_world_gen_analytics.py`.

**Interfaces:**
- Produces in `nerdit_world_gen.py`:
  - `validate_world(world: dict) -> None`
  - `generate(world: dict, manifest: dict | None = None) -> dict[str, list[dict]]`
  - `column_order(columns: dict) -> list[str]`: topological by declared dependencies, with alphabetical tie-break. Equals `sorted(columns)` when nothing depends on anything; that is what keeps old worlds identical.
  - `to_csv(rows: list[dict], columns: list[str]) -> str`: `csv` module, `lineterminator="\n"`, `None` → empty field
  - `build_files(recipe: dict) -> dict[str, str]`: recipe `{"seed": int, "files": {name: {"entity": str, "drop": [str]}}, "world": dict}`; the recipe seed overrides the world seed; CSV columns follow the entity's declared order minus `drop`
- Importing the module from a file path (the browser does `exec` of the file text) must work: no relative imports, no `__file__`.

- [ ] **Step 1: Failing tests:**
  - `test_existing_worlds_are_byte_identical`: SHA-256 of the practice-retail outputs equals `fixtures/practice-retail.sha256`.
  - `test_column_order_is_sorted_without_dependencies`: `column_order({"b": {...}, "a": {...}}) == ["a", "b"]`.
  - `test_csv_quotes_round_trip`: rows with `'He said "hi", then left\nlater'` and `None`; `csv.reader(io.StringIO(to_csv(...)))` returns the same strings, with `''` for None.
  - `test_build_files_uses_recipe_seed_and_drop`: the same world with seeds 1 and 2 gives different CSV text; a dropped column is not in the header.
  - `test_core_runs_from_source_text`: `exec(Path(core).read_text(), ns)`; `ns["build_files"]` works without `__file__`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Move the code without changing draw order; add `column_order`, `to_csv`, `build_files`.
- [ ] **Step 4: Run** the whole suite. Expected: all old world tests still pass, plus 5 new.
- [ ] **Step 5: Commit** — `refactor(worlds): shared generation core with dependency order and CSV export`.

---

### Task 3: Analytics profile and distribution generators

**Files:** Modify `references/nerdit_world_gen.py`; test `scripts/test_world_gen_analytics.py`.

**Interfaces:**
- Produces:
  - world/entity key `profile` (`"sql"` | `"analytics"`)
  - generators `normal {mean, sd, min?, max?, round?}`, `lognormal {median, sigma, round?, max?}`, `poisson {lam}`, `bernoulli {p}`
  - `round` defaults to 2 for float generators
  - Poisson: Knuth's method for `lam <= 30`; otherwise `max(0, round(gauss(lam, sqrt(lam))))`
- Validation messages name `entity.column`.

- [ ] **Step 1: Failing tests:**
  - `test_profiles_cap_rows_and_cells`: `sql` with 101 rows fails; `analytics` with 20,000 rows passes; 20,001 fails; an analytics world above 200,000 cells fails.
  - `test_distributions_have_expected_moments`: 5,000 rows, seed 7. `normal(50, 10)` mean within ±0.6 and sd within ±0.6; `poisson(4)` mean within ±0.15; `bernoulli(0.3)` rate within ±0.02; `lognormal(median=1000)` median within ±5%; `min`/`max`/`round` respected.
  - `test_bad_distribution_params_fail`: `sd < 0`, `p > 1`, `lam <= 0`, unknown key → `ValueError` naming `entity.column`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS (whole suite). **Step 5: Commit** — `feat(worlds): analytics profile and distribution generators`.

---

### Task 4: Dependent columns — linear, logistic, binned_effect

**Files:** `references/nerdit_world_gen.py`; tests `scripts/test_world_gen_analytics.py`.

**Interfaces:**
- `linear {intercept, terms: {col: weight}, effects: {cat_col: {value: delta}}, noise_sd, round?, min?, max?}`
  - value = intercept + Σ weight × row[col] + effects[col][row[col]] (0 when unlisted) + `gauss(0, noise_sd)`, then clamped and rounded
- `logistic {intercept, terms, effects, target_rate?}`
  - p = 1 / (1 + exp(−score)); label = 1 if `random() < p`, else 0
  - With `target_rate`, the intercept is replaced before any label is drawn: bisection on [−20, 20] for 40 steps until mean(sigmoid(b + rest)) over all rows matches `target_rate`.
- `binned_effect {column, edges: [ascending numbers], deltas: [len(edges) + 1 numbers]}`: value = `deltas[bisect_right(edges, row[column])]`
- Dependencies are the columns named in `terms`, `effects` and `column`. `column_order` (Task 2) sorts them; a cycle fails with `cyclic column dependency at entity.column`.

- [ ] **Step 1: Failing tests:**
  - `test_linear_recovers_declared_weight`: 5,000 rows, `y = 3 + 2·x + noise(1)` → least-squares slope (stdlib: cov/var) within 10% of 2.
  - `test_logistic_target_rate_sets_class_balance`: `target_rate` 0.30 → positive rate within ±0.01; 0.05 → within ±0.01.
  - `test_effects_and_bins_shift_values`: group means differ by the declared deltas within ±10%.
  - `test_column_cycle_fails`: `a` uses `b`, `b` uses `a` → `ValueError` containing `cyclic column dependency`.
  - `test_existing_worlds_are_byte_identical` still passes.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** — `feat(worlds): dependent columns with known true effects`.

---

### Task 5: Segments and text

**Files:** `references/nerdit_world_gen.py`; tests `scripts/test_world_gen_analytics.py`.

**Interfaces:**
- Entity key `segments: {name: {weight: number, overrides: {col: {param: value}}}}`. Each row draws its segment with `choices` (weights) **before** its columns. Listed columns merge the override params into their spec. A `_segment` column records the name.
- `text {templates: [str], slots: {name: [str]}, tone_from?: {label_col: {value: [templates]}}}`
  - placeholders `{slot}` match `\{([a-z_]+)\}`
  - every placeholder must be a slot, or validation fails
  - filled with `str.replace`, never `format`
  - `tone_from` picks the template list by the row's label value
- Slot values and templates are checked against `PRIVATE` (no contact-like words) and must not contain digits that look like phone numbers (`\d{6,}`).

- [ ] **Step 1: Failing tests:**
  - `test_segments_create_separable_groups`: 2 segments with income means 30,000 and 90,000 → per-`_segment` means within 10%; segment shares within ±0.03 of the weights.
  - `test_text_follows_tone_and_fills_slots`: a positive rating picks from the positive templates; no `{` left in any value.
  - `test_text_rejects_unknown_placeholders_and_contact_slots`: `{phone}` placeholder, or slot value `98765 43210`/`9876543210` → `ValueError`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** — `feat(worlds): customer segments and template text`.

---

### Task 6: Series and interactions entities

**Files:** `references/nerdit_world_gen.py`; tests `scripts/test_world_gen_analytics.py`.

**Interfaces:**
- **Entity `kind: "series"`** with `start`, `end` (ISO dates), `freq` (`day` | `week` | `month`), `base`, `trend_per_period`, `weekly` (7 multipliers, Monday first; day freq only), `monthly` ({"1"…"12"}), `holidays` [{date, lift, days}], `noise_sd`, `break?` {date, shift}, `value_column` (default `value`), `date_column` (default `date`).
  - value_t = max(0, round((base + trend·t) × weekly[dow] × monthly[month] × (1 + lift if inside a holiday window) + gauss(0, noise_sd) + (shift if date ≥ break.date)))
  - `t` is the 0-based period index.
- **Entity `kind: "interactions"`** with `users` (entity), `items` (entity), `user_column`, `item_column`, `k` (1–5), `density` (0.01–0.3), `scale` [lo, hi], `noise_sd`.
  - Draw a k-vector `gauss(0, 1)` per user in id order, then per item, plus an item bias `gauss(0, 0.5)`.
  - For each (user, item) in sorted order, include the pair if `random() < density`.
  - rating = clamp(round(mid + half·tanh(dot / k + bias) + gauss(0, noise_sd)), lo, hi), where `mid` and `half` come from `scale`.
- Both kinds obey the profile caps; series row count = number of periods.

- [ ] **Step 1: Failing tests:**
  - `test_series_has_trend_season_holiday_and_break`: daily series for 2025 → December mean > July mean when `monthly["12"]=1.6`; holiday window mean > the surrounding 2 weeks; mean after the break exceeds before by `shift` ±10%; `freq=week` gives 52 or 53 rows.
  - `test_interactions_density_scale_and_signal`: density 0.1 → share within ±0.02; every rating in `scale`; with `noise_sd` 0 the user-mean ratings of two users differ (signal exists).
  - `test_series_and_interactions_are_seeded`: same seed → identical; different seed → different.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** — `feat(worlds): time series and user-item interactions`.

---

### Task 7: Planned defects and the manifest; CSV output from `make_world_data.py`

**Files:** `references/nerdit_world_gen.py`, `scripts/make_world_data.py`; tests `scripts/test_world_gen_analytics.py`, `scripts/test_world_workflow.py`.

**Interfaces:**
- Entity key `defects`: `missing` [{column, rate, when?}], `outliers` [{column, rate, factor}], `duplicates` rate, `label_noise` {column, rate}, `drift` {after, column, shift}.
- Applied after all columns, in this order: drift → outliers → label_noise → missing → duplicates. Duplicates copy final rows and give the copies new ids when the entity has an `id` column.
- `generate(world, manifest)` fills `manifest["defects"][entity][kind]` = {column: [row_index, …]}; duplicates list their new row indexes.
- `make_world_data.py` also writes `world_data.manifest.json` and, for analytics entities, `<entity>.csv`.

- [ ] **Step 1: Failing tests:**
  - `test_defects_hit_declared_rates_and_are_recorded`: 5,000 rows; missing 0.05 → None share within ±0.01 and the manifest lists exactly those rows; outliers ×10 listed; label_noise flips listed labels; duplicates 0.02 → row count grows by 100 ±1; drift shifts only rows after the date.
  - `test_make_world_data_writes_csv_and_manifest` (workflow): files exist; the CSV header matches the declared column order.
  - `test_existing_worlds_are_byte_identical` still passes.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** — `feat(worlds): recorded planned defects and CSV export`.

---

### Task 8: Determinism, speed and pandas read-back on the engine

**Files:** Test `scripts/test_world_engine.py` (engine-only; skip with the reason when unavailable).

**Interfaces:**
- Consumes: `run_job` (Task 1); `build_files` (Task 2); the core file text.

- [ ] **Step 1: Write tests:**
  - `test_cpython_and_pyodide_build_identical_files`: an analytics recipe using every generator, kind and defect. Local `build_files` vs Pyodide (`exec` core text, call `build_files`, print SHA-256 per file) → equal hashes.
  - `test_twenty_thousand_rows_build_within_two_seconds`: 20,000 × 10 in Pyodide; measured with `time.perf_counter` inside Pyodide; under 2.0 s.
  - `test_text_csv_reads_back_in_pandas`: `pd.read_csv` on a text-column CSV → the same strings as the generated rows.
- [ ] **Step 2: Run.** Expected: PASS. If the hashes differ, apply `systematic-debugging`; the usual cause is a non-allowed random call or float formatting. Fix the core, then rerun Tasks 2–7.
- [ ] **Step 3: Commit** — `test(worlds): generator is identical and fast in Pyodide`.

---

### Task 9: Dataset block check (v11)

**Files:** `scripts/verify_course.py`, `scripts/test_verify_v11.py`.

**Interfaces:**
- v11 structure check on `script.nerdit-dataset`:
  - at most one per lesson
  - at most 40 KB (`MAX_DATASET_BYTES = 40_960`)
  - valid JSON with `seed` (int), `files` (non-empty; names end with `.csv`), `world` (dict without `use`)
  - every file's `entity` exists
  - `validate_world` passes (lazy import from `references/nerdit_world_gen.py`, like the existing lazy `make_world_data` import)

- [ ] **Step 1: Failing tests:**
  - `test_valid_dataset_block_passes`
  - `test_dataset_block_must_be_self_contained` (`"world": {"use": "fvc-institute"}` fails)
  - `test_dataset_block_size_and_json_are_checked` (40,961 bytes fails; broken JSON fails; unknown entity fails; two blocks fail)
  - `test_v10_ignores_dataset_blocks`
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** — `feat(verify): v11 checks lesson dataset blocks`.

---

### Task 10: `check_python_outputs.py`

**Files:** Create `scripts/check_python_outputs.py`, `scripts/test_check_python_outputs.py`.

**Interfaces:**
- Consumes: `run_job`, `engine_available`, `EngineError`, `EngineTimeout` (Task 1); `build_files` (Task 2); `parse`, `text_of`, `descends_from`, `ancestor` (`verify_course`).
- Produces:
  - `python_parts(content: str) -> dict` with keys `dataset` (recipe or None); `runs` [{"code", "shown" (str | None when the output is a figure), "offline": bool}]; `tryits` [code]
    - Run lines: `.nerdit-run` whose `.nerdit-in pre[data-lang]` is `python`.
    - Offline: `.nerdit-run[data-run="offline"]`.
    - Try Its: `.nerdit-tryit` with `data-lang="python"` or a button calling `nerditRunPython`/`nerditRunPlot`.
  - `normalise(text: str) -> str`: CRLF → LF; rstrip each line; drop trailing blank lines
  - `check_lesson(content: str, timeout: int = 120) -> dict` with keys `examples`, `match`, `mismatch` [str], `offline` [str], `tryit_fail` [str]
  - Comparison:
    - A shown error matches when the shown text contains the engine's `error` line.
    - A figure run (`shown is None`) matches when `figures >= 1` and there is no error.
  - CLI `--course <json> [--lesson <id>] [--timeout N] [--probe mod,...]`; exit codes per Global Constraints

- [ ] **Step 1: Failing tests:**
  - Always run:
    - `test_python_parts_finds_runs_tryits_offline_and_dataset`
    - `test_normalise_trims_layout_only`
    - `test_missing_engine_exits_2`: env `NERDIT_PYODIDE_DIR=tmp_path`; the CLI on a Python lesson exits 2, and stderr names `npm ci`.
  - Engine-only:
    - `test_matching_outputs_pass`: a lesson with a dataset, `pd.read_csv` and `print(df.shape)`.
    - `test_changed_number_fails`
    - `test_shown_error_matches_last_line`
    - `test_failing_tryit_starter_fails`
    - `test_figure_run_needs_a_figure`
    - `test_offline_runs_are_reported_not_passed`
    - `test_runaway_code_times_out`: `while True: pass`, timeout 5 → `mismatch` mentions `timed out`; finishes in under 20 s.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** — `feat(checker): verify Python outputs on the site's Pyodide engine`.

---

### Task 11: Integration and writer rules

**Files:** `scripts/gate_lesson.py`, `scripts/test_gate_lesson.py`, `SKILL.md`, `references/runners/python.md`, `references/runners/plot.md`, `references/CORE.md`, `agents/nerdit-lesson-writer.md`, `agents/nerdit-qa-validator.md`, `scripts/test_docs_refs.py`.

**Interfaces:**
- `gate()` runs `check_lesson` from Task 10 when `python_parts(html)` has runs or Try Its.
  - mismatch and Try It failures → `python:` failures; offline → warnings
  - engine missing → failure `python: engine missing (tools/pyodide/README.md)`
- Docs (exact rules from spec §2.4 and §3):
  - `runners/python.md` and `runners/plot.md`: the dataset block contract (markup, 40 KB, self-contained, the file table in the opening section), Try It starters stand alone, run lines build in page order, seed every random call, no typed-in data over 8 rows, `data-run="offline"` for libraries the probe cannot load.
  - `CORE.md` §4 points to them.
  - `SKILL.md` Step 4c: run `scripts/check_python_outputs.py` next to the SQL checker, and use `--probe` before planning a course.
  - Writer: read the Python dataset rules.
  - QA validator: do not judge Python outputs (the script does).

- [ ] **Step 1: Failing tests:**
  - `test_gate_runs_python_checks` (engine-only): a Python lesson with a wrong output → a `python:` failure.
  - `test_gate_fails_when_engine_missing_for_python_lessons` (always; `NERDIT_PYODIDE_DIR` override)
  - `test_docs_name_python_checker_and_dataset_rules`: `SKILL.md` names `scripts/check_python_outputs.py`; `runners/python.md` contains `nerdit-dataset` and `40 KB`; the writer mentions `data-run="offline"`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** — `feat(generator): gate and rules for Python datasets and output checks`.

---

### Task 12: `check_runtime_bundle.py`

**Files:** Create `scripts/check_runtime_bundle.py`, `scripts/test_check_runtime_bundle.py`.

**Interfaces:**
- `FILES = ("nerdit-python-runner.js", "nerdit-plot-runner.js", "nerdit-sql-runner.js", "nerdit-excel-engine.js", "nerdit_world_gen.py")`
- CLI `<plugin_refs_dir> <site_public_dir>...` → prints `DRIFT` lines; exit 1 on any difference or missing file. It compares text with line endings normalised, like `check_css_bundle.py`.

- [ ] **Step 1: Failing tests** (`test_identical_passes`, `test_drift_fails`, `test_missing_file_fails`), modelled on `test_check_css_bundle.py`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Copy** `references/nerdit_world_gen.py` to `nerdit/future-vision/public/nerdit_world_gen.py`, then run the CLI. Expected: exit 0. If a runner already drifts, record it as a ruling and sync from `references/`.
- [ ] **Step 6: Commit** — `feat(generator): runtime bundle check for runners and world generator`.

---

### Task 13: Data Science worlds and the course map

**Files:** Create the five `references/worlds/*.world.json` files, `references/worlds/ds-course-map.json` and `scripts/test_ds_worlds.py`. Modify `references/worlds/README.md` (analytics profile, new generators, kinds, defects, dataset blocks, course map).

**Interfaces:**
- Worlds (all `profile: "analytics"`, with a cast and an `arc`; business facts from `docs/superpowers/notes/2026-10-15-world-sources.md`):
  - **`fvc-institute`** (real name, `realName` per Global Constraints):
    - entities `enquiries` (with `enrolled` logistic, `target_rate` 0.30), `learners` (segments), `daily_enquiries` (series, poisson-like noise), `batch_scores` (normal), `enquiry_messages` (text with intent)
  - **`saree-wholesale`** (invented name):
    - `retailers` (segments), `weekly_orders` (series; `monthly` lift for Oct–Nov Diwali and Nov–Feb weddings), `retailer_sku` (interactions), `order_lines` (defects: missing, duplicates, outliers)
  - **`stationery-d2c`** (invented name):
    - `customers` (segments), `orders` (coupons, discounts), `ratings` (interactions), `reviews` (text with `tone_from` rating), `daily_sales` (series with a launch spike holiday)
  - **`boat-cruises`** (invented name):
    - `bookings` (event type), `daily_bookings` (series; Christmas and NYE holidays), `quotes` (linear price from guests), `cancellations` (logistic)
  - **`wire-mesh`** (invented name):
    - `products` (gauge, mesh size, roll width), `prices` (linear plus binned_effect), `qc_measurements` (normal, defects: outliers, drift), `defects` (logistic, `target_rate` 0.05)
- `ds-course-map.json`: `[{"course": str, "world": str, "entities": [str]}]` with the 17 rows of spec §4.2. Offline-only courses use `"offline": true`.

- [ ] **Step 1: Failing tests:**
  - `test_every_world_validates_and_builds_within_caps`
  - `test_only_fvc_uses_a_real_name_and_it_is_recorded`
  - `test_target_rates_match_the_spec` (FVC 0.30 ±0.01; wire-mesh 0.05 ±0.01)
  - `test_seasons_are_present`: saree weekly orders Oct–Nov mean > Jun–Jul mean; boat December mean > July mean
  - `test_course_map_points_at_real_entities`: every world and entity exists; 17 rows
  - `test_no_contact_fields_or_numbers`
- [ ] **Step 2: Run** → FAIL. **Step 3: Write the worlds, map and README.** **Step 4: Run** → PASS. **Step 5: Commit** — `feat(worlds): five Data Science worlds and the course map`.

---

### Task 14: Browser datasets in the runners

**Files:**
- Modify `references/nerdit-python-runner.js` and `references/nerdit-plot-runner.js`; copy both to `nerdit/future-vision/public/`.
- Create `nerdit/future-vision/src/utils/datasetRecipe.test.ts`.
- Add a lesson with a dataset block and a Python Try It to the dev fixture course (`courseService.fixture.ts`, a new fixture HTML whose dataset block is built from the `fvc-institute` world, Task 13).

**Interfaces:**
- Both runners expose `window.nerditDatasetRecipe(root: Document) -> object | null`: the parsed JSON of the first `script.nerdit-dataset`, or `null` when it is absent or the JSON is invalid.
- Before the first run on a page:
  1. When a recipe exists, fetch `/nerdit_world_gen.py` once.
  2. `exec` it in a private namespace and call `build_files(recipe)`.
  3. Write each file with `py.FS.writeFile(name, text)` into the working directory.
- This is memoised per page, and the learner's code still runs in a fresh namespace. A page without a recipe behaves exactly as before.
- After generation, add one `a.nerdit-dataset-download` per file (`download` attribute, `Blob` URL, text `Download <name>`) after the first `.nerdit-tryit`.
- Failure to fetch or generate shows `Could not prepare this lesson's data. Check your internet connection and try again.` in the Try It result.

- [ ] **Step 1: Failing vitest** (load the public runner file into jsdom):
  - `parses the dataset recipe`
  - `returns null without a block`
  - `returns null for invalid JSON`
- [ ] **Step 2: Run** `npx vitest run src/utils/datasetRecipe.test.ts` → FAIL.
- [ ] **Step 3: Implement** in `references/`, copy to `public/`, and run `check_runtime_bundle.py`. Expected: exit 0.
- [ ] **Step 4: Run vitest** (the new file plus the full suite). Expected: PASS, with the full count unchanged plus 3.
- [ ] **Step 5: Browser check.** `VITE_FIXTURE_COURSE=1 npm run dev`. With Playwright at 1280 and 390:
  - Running the fixture Try It prints the first rows of `enquiries.csv`.
  - The download link's text (fetched from its Blob) equals `make_world_data.py`'s `enquiries.csv` byte for byte.
  - There is no page overflow.
- [ ] **Step 6: Commit** (plugin and nerdit repos, listed files only) — `feat(runner): build lesson datasets in the browser with a download link`.

---

### Task 15: Final verification and version

- [ ] Bump `.claude-plugin/plugin.json` to `3.4.0`, and update the version test in `test_docs_refs.py` to match.
- [ ] Run both plugin suites. Expected: all pass, with engine tests run, not skipped.
- [ ] Run `check_css_bundle.py` and `check_runtime_bundle.py`. Expected: exit 0.
- [ ] Run `check_python_outputs.py --probe numpy,pandas,sklearn,scipy,matplotlib,statsmodels,seaborn`. Record the versions in the ledger and in `runners/python.md`'s "what loads" line.
- [ ] Confirm no file under `nerdit/generated/` changed (Task 0 snapshot method from Plan A).
- [ ] Final whole-branch review per the execution skill; report rulings and deferred minors.
