# Runner: Python (Pyodide)

Load the engine once per lesson, after the wrapper:

<script src="/nerdit-python-runner.js"></script>


**Python variant.** Each Try It runs its starter program alone, in a fresh namespace. Keep
the starter short and directly tied to the concept just taught.
```html
<div class="nerdit-tryit" data-lang="python">
  <div class="nerdit-tryit-head">▶ Try It Yourself — edit the code and run it</div>
  <textarea class="nerdit-tryit-editor" rows="6" spellcheck="false">marks = 72
if marks >= 40:
    print("Pass")
else:
    print("Fail")</textarea>
  <div class="nerdit-tryit-bar">
    <button class="nerdit-run-btn" onclick="nerditRunPython(this)">Run Python ▶</button>
    <span class="nerdit-tryit-status" aria-live="polite"></span>
  </div>
  <div class="nerdit-tryit-result"></div>
</div>
```
Python output (including tracebacks) renders into `.nerdit-tryit-result` as plain text
inside `.nerdit-tryit-output`. Warn the learner in one sentence that the first run takes a
few seconds while Python loads.

## Lesson data: the dataset block

A lesson that works with a table carries a **recipe**, not a file. The runner builds the CSV
files in the browser before the learner's first run, so `pd.read_csv("enquiries.csv")` works
the way it does on a real computer, and a **Download** link under the first Try It gives the
learner the same file for Excel or Jupyter.

```html
<script type="application/json" class="nerdit-dataset">
{"seed": 7,
 "files": {"enquiries.csv": {"entity": "enquiries", "drop": ["_segment"]}},
 "world": { ...the business, cast and only the entities these files need... }}
</script>
```

- **One block per lesson, before the first Python example.** At most **40 KB**, valid JSON.
  `verify_course.py --contract v11` fails a bigger block, broken JSON or a second block.
- **Self-contained.** Copy the entities from the course world into `world`. A library
  reference (`{"use": "fvc-institute"}`) cannot load in the browser and fails v11.
  The rows depend on every entity in the recipe's world and on its seed, so a world cut down
  to one entity draws different rows from the full world. Quote numbers and dirty rows from
  the recipe's own build: `make_world_data.py --recipe <lesson>.html --out-dir work` writes
  the same CSV files the browser builds (recipe seed included) and their
  `world_data.manifest.json`.
- `seed` replaces the world's seed, so each lesson can draw its own rows. `drop` removes
  columns from the CSV (always drop `_segment`, the hidden cluster label, unless the lesson
  is about checking clusters).
- The world format, generators and planned defects are in `references/worlds/README.md`.
- **Say what the learner is loading.** The lesson's opening section names each file and its
  columns in one small value table (figures.md template 11).
- **Mark tables that come from the recipe.** The file table and any table of CSV rows carry
  `data-world-derived="dataset block: <file or files and columns>"` on their `nerdit-figure`.
  Their values come from the recipe's build, not the course world, so `check_world.py` must not
  match them against the world (it fails a figure table with neither marker). Check the values
  with `make_world_data.py --recipe` and `check_python_outputs.py` instead.

## Rules for Python examples

- **Every Try It starter runs on its own** in a fresh namespace: it imports what it needs and
  reads its data file itself. It never relies on a run line or another Try It.
- **Run lines build on each other in page order**, like notebook cells: a later run line may
  use a variable an earlier one made.
- **A run line prints what it shows.** Write `print(df.head())`, never a bare `df.head()`:
  the runner does not display a last expression, so the shown output must come from `print`.
- **Shown code is download code** (CORE.md §6e): Python 3.12 features only, nothing in
  `references/deprecated.md`. With a files box in the lesson, the runner skips its own Download
  link: the pack carries the file.
- **Seed every random call** in shown code: `random_state=7`, `np.random.default_rng(7)`,
  `random.seed(7)`. An unseeded example shows numbers no learner can reproduce.
- **Data comes from the dataset block.** Never type in a list of more than 8 rows.
- **Libraries the browser cannot load** (TensorFlow/Keras, PyTorch, PySpark, Flask/FastAPI,
  Docker, seaborn) go in an offline run line: `<div class="nerdit-run" data-run="offline">`.
  Show the code and the output captured on a real machine, and give it no Try It. Ask the
  checker before planning, never memory:
  `check_python_outputs.py --probe numpy,pandas,sklearn,seaborn`.

## The checker

`scripts/check_python_outputs.py` runs every Python example on the website's own engine
(Pyodide 0.26.2, set up once with `npm ci` in `tools/pyodide/`):

- run lines in page order in one namespace; the printed output must equal the shown output
  (line ends and trailing spaces aside);
- a shown error must contain Python's last error line (`ZeroDivisionError: division by zero`);
- a run whose output half has no `<pre>` is a chart: it must draw a figure without an error;
- each Try It starter alone: it must not raise;
- offline run lines are reported as offline, never as a pass.

What loads in the engine: numpy 1.26.4, pandas 2.2.0, scikit-learn 1.4.2, scipy 1.12.0,
matplotlib 3.5.2, statsmodels 0.14.2 (Python 3.12.1). seaborn does not load.
