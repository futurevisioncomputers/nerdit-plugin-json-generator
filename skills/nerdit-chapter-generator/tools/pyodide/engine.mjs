// Pyodide engine for check_python_outputs.py: the website's Python, run in Node.
//
//   node engine.mjs [install_dir] < job.json > result.json
//
// install_dir holds node_modules/pyodide and the .cache package folder (default: this folder;
// pyodide_engine.py passes NERDIT_PYODIDE_DIR). Same version as nerdit-python-runner.js: 0.26.2.
//
// Job:    {"files": {name: text}, "steps": [{"id", "code", "fresh"}], "probe": [module]}
// Result: {"versions": {module: version | null}, "results": [{"id", "stdout", "error", "figures"}]}
//
// Non-fresh steps share one namespace, like notebook cells; a fresh step gets its own, like a
// Try It. Output is collected the way the runners collect it: batched lines joined by "\n",
// stderr included. stdout carries only the result JSON, so Pyodide's console messages go to stderr.
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const installDir = resolve(process.argv[2] || here);
const toStderr = (...a) => process.stderr.write(a.join(" ") + "\n");
console.log = toStderr;
console.info = toStderr;
console.warn = toStderr;

// The runners' friendlyError keeps the last line that names an error type.
const ERROR_LINE = /^[A-Za-z_][A-Za-z_.]*(Error|Exception|Interrupt)\b/;
function lastErrorLine(message) {
  const lines = String(message).replace(/\s+$/, "").split("\n");
  for (let i = lines.length - 1; i >= 0; i--) {
    if (ERROR_LINE.test(lines[i].trim())) return lines[i].trim();
  }
  return lines[lines.length - 1].trim();
}

const SETUP = [
  "import os, warnings",
  "os.environ['MPLBACKEND'] = 'Agg'",
  "warnings.filterwarnings('ignore', message='.*non-GUI backend.*')",
].join("\n");

const FIGURES = [
  "import sys as _s",
  "_n = 0",
  "if 'matplotlib.pyplot' in _s.modules:",
  "    _p = _s.modules['matplotlib.pyplot']",
  "    _n = len(_p.get_fignums())",
  "    _p.close('all')",
  "_n",
].join("\n");

const VERSION = [
  "import importlib",
  "def _nerdit_version(name):",
  "    try:",
  "        return str(getattr(importlib.import_module(name), '__version__', 'unknown'))",
  "    except Exception:",
  "        return None",
].join("\n");

// NERDIT_PYODIDE_NO_NETWORK=1 blocks package downloads, as on a machine without internet
// (Pyodide downloads through the global fetch). Packages already in .cache still load.
if (process.env.NERDIT_PYODIDE_NO_NETWORK === "1") {
  globalThis.fetch = () => Promise.reject(new TypeError("network disabled by NERDIT_PYODIDE_NO_NETWORK"));
}

const job = JSON.parse(readFileSync(0, "utf8"));
const { loadPyodide } = await import(pathToFileURL(join(installDir, "node_modules", "pyodide", "pyodide.mjs")).href);
const py = await loadPyodide({ packageCacheDir: join(installDir, ".cache"), stdout: toStderr, stderr: toStderr });
// A failed download is reported here, not thrown. Collect it: the job's results are then an
// engine problem (exit 2), never a lesson mismatch.
const loadErrors = [];
const quiet = { messageCallback: () => {}, errorCallback: (m) => { loadErrors.push(String(m)); toStderr(m); } };
py.runPython(SETUP);

for (const [name, text] of Object.entries(job.files || {})) py.FS.writeFile(name, text);

const versions = {};
if ((job.probe || []).length) {
  await py.loadPackagesFromImports((job.probe || []).map((m) => `import ${m}`).join("\n"), quiet);
  py.runPython(VERSION);
  const version = py.globals.get("_nerdit_version");
  for (const m of job.probe) versions[m] = version(m) ?? null;
  version.destroy();
}

const results = [];
let shared = py.toPy({});
for (const step of job.steps || []) {
  const buf = [];
  const collect = { batched: (s) => buf.push(s) };
  const ns = step.fresh ? py.toPy({}) : shared;
  let error = null;
  try {
    await py.loadPackagesFromImports(step.code, quiet);
    py.setStdout(collect);
    py.setStderr(collect);
    py.runPython(step.code, { globals: ns });
  } catch (err) {
    error = lastErrorLine(err.message || err);
  } finally {
    py.setStdout({ batched: toStderr });
    py.setStderr({ batched: toStderr });
  }
  const figures = py.runPython(FIGURES);
  if (step.fresh) ns.destroy();
  results.push({ id: step.id, stdout: buf.join("\n"), error, figures });
}
shared.destroy();

process.stdout.write(JSON.stringify({ versions, results, load_errors: loadErrors }));
