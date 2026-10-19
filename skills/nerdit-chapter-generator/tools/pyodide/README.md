# Pyodide engine for Python output checks

`scripts/check_python_outputs.py` runs every Python example in a lesson on this engine:
Node.js plus the `pyodide` npm package pinned to **0.26.2**, the version that
`nerdit-python-runner.js` and `nerdit-plot-runner.js` load on the website. Same library
versions, same float printing, same error lines.

## Setup (once per machine)

```bash
cd skills/nerdit-chapter-generator/tools/pyodide
npm ci
```

- Needs Node.js 18 or later on `PATH`.
- The first check downloads the packages a lesson imports (NumPy, pandas, scikit-learn,
  Matplotlib, …) from the Pyodide CDN into `.cache/`. Later runs work offline.
- `node_modules/` and `.cache/` are git-ignored.
- To use an engine installed elsewhere, set `NERDIT_PYODIDE_DIR` to the folder that holds its
  `node_modules/` (the `.cache/` folder is created next to it).
- A package that cannot be downloaded (first run without internet) is an engine problem: the
  checker exits 2, never 1. `NERDIT_PYODIDE_NO_NETWORK=1` blocks downloads to reproduce this.
- Run lines share one engine run; each Try It gets a run of its own with only the dataset
  files, as on the site.

Without the engine, `check_python_outputs.py` exits 2 and `gate_lesson.py` fails Python
lessons. A missing engine is never a pass.

## What loads (checked with `--probe`)

numpy 1.26.4, pandas 2.2.0, scikit-learn 1.4.2, scipy 1.12.0, matplotlib 3.5.2,
statsmodels 0.14.2. **seaborn does not load** (not part of Pyodide 0.26.2), so seaborn
code needs `data-run="offline"`. Python is 3.12.1.

## Protocol

`engine.mjs` reads one JSON job on stdin and writes one JSON result on stdout:

- Job: `{"files": {name: text}, "steps": [{"id", "code", "fresh"}], "probe": [module]}`
- Result: `{"versions": {module: version | null}, "results": [{"id", "stdout", "error", "figures"}]}`

Steps without `fresh` share one namespace, like notebook cells. A `fresh` step gets its own,
like a Try It. `error` is the last traceback line (`Type: message`). `figures` counts the
Matplotlib figures a step left open (Agg backend); they are closed after counting.
