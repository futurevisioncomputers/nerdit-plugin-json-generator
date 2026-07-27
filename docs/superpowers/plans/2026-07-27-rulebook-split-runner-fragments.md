# Rulebook Split into Core + Runner Fragments — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop every lesson-writer from reading every runner's documentation, and stop every lesson from carrying a copy of its runner's JavaScript.

**Architecture:** `NERDIT_LESSON_PROMPT_v9_simple.md` splits into `CORE.md` plus one small fragment per runner. The SQL and Python runner JavaScript moves out to website-served `.js` files, matching how the Excel and Matplotlib engines already work. A new optional per-lesson `runner` field in the input JSON tells the orchestrator which single fragment to hand each agent.

**Tech Stack:** Markdown (the rulebook), browser JavaScript ES5-style with `window.*` guards (the runners), Python 3 stdlib (the assembler), pytest.

**Spec:** [docs/superpowers/specs/2026-07-27-rulebook-split-runner-fragments-design.md](../specs/2026-07-27-rulebook-split-runner-fragments-design.md)

## Global Constraints

- **The split is mechanical.** Lines move between files; wording does not change. The only permitted deletions and additions are the ones enumerated in the line-accounting identity below. Improving the prose is a separate, later change.
- `scripts/*.py` stay **Python-stdlib only**.
- Runner `.js` files keep their `if (typeof window.X !== "function") { ... }` guard so multiple lessons on one page never double-define.
- Runner `.js` files stay ES5-flavoured (`var`, `function`, no arrow functions or `const`) to match `nerdit-excel-engine.js` and `nerdit-plot-runner.js`.
- All 29 existing tests must keep passing.
- The `runner` input field is generation context only — never copied into the assembled output, exactly like `description`.

## Repo note

Repository root is `d:\siddharth\nerdit-backup\nerdit_plugin-main`. Current branch: `feat/merge-lesson-quiz-agents`. **Start this work on a new branch cut from that one**, since the agent-merge work is unpushed and unmerged:

```bash
git checkout -b feat/rulebook-split
```

**Path convention:** paths below are repo-relative. Shell commands run from the repo root. The one exception is the website, which lives outside this repo at `d:\siddharth\nerdit-backup\Future Vision Online Course Website Project\future-vision\` — always written out in full.

## The line-accounting identity

The original file has **724 lines, 631 non-blank, 18 headings**. Every non-blank line has exactly one destination:

| Source lines | Non-blank | Destination |
|---|---|---|
| 1-233 | 194 | `CORE.md` |
| 234-237 | 3 | `CORE.md` (§6c heading + intro, minus the table) |
| 238-243 | 6 | **deleted** (runner routing table) |
| 244-264 | 20 | `runners/python.md` |
| 265-288 | 22 | `runners/sql.md` |
| 289-370 | 74 | `runners/excel.md` |
| 371-412 | 35 | `runners/plot.md` |
| 413-491 | 63 | `CORE.md` |
| 492-538 | 43 | `CORE.md` (§9 shared helpers) |
| 539-604 | 64 | `nerdit-python-runner.js` |
| 605-647 | 43 | `nerdit-sql-runner.js` |
| 648-655 | 5 | `CORE.md` (§9 close + Chart.js note) |
| 656-724 | 59 | `CORE.md` |

```
631 = CORE 367 + python.md 20 + sql.md 22 + excel.md 74
    + plot.md 35 + python.js 64 + sql.js 43 + deleted 6
```

Task 2 verifies this identity. Permitted **additions** on top of it, and nothing else:

- each runner `.md` gains a `<script src="/nerdit-<runner>.js">` instruction line
- each extracted `.js` gains its own IIFE wrapper (`(function(){` … `})();`)
- `CORE.md` gains the replacement paragraph for the deleted routing table
- `CORE.md` §9 intro text is adjusted to say the runner JS is external

## File Structure

| File | Change | Responsibility after |
|---|---|---|
| `skills/.../references/nerdit-sql-runner.js` | Create | `window.nerditRunSql` + sql.js CDN boot + result-table renderer |
| `skills/.../references/nerdit-python-runner.js` | Create | `window.nerditRunPython` + Pyodide boot + friendly tracebacks |
| `skills/.../references/CORE.md` | Create | Subject-agnostic lesson rules |
| `skills/.../references/runners/{sql,python,excel,plot}.md` | Create | One runner's markup contract each |
| `skills/.../references/NERDIT_LESSON_PROMPT_v9_simple.md` | Delete | — |
| `skills/.../scripts/assemble_course.py` | Modify | Correct asset URL prefix; four engines in `ENGINE_FILES` |
| `skills/.../scripts/test_assemble_course.py` | Modify (append) | Asset detection across all four engines |
| `agents/nerdit-lesson-writer.md` | Modify | Step 0 reads CORE + the named fragment |
| `skills/.../SKILL.md` | Modify | `runner` field, fragment selection, updated reference table |
| `README.md` | Modify | Reference-file sentence |
| `future-vision/public/nerdit-{sql,python}-runner.js` | Create (outside repo) | Served to learners |

Task order is driven by one constraint: **the website must serve the runner `.js` files before any lesson references them.** Task 1 creates and deploys them; Task 2 is the first thing that tells an agent to emit `<script src>`.

---

### Task 1: Extract runner JavaScript and deploy it

**Files:**
- Create: `skills/nerdit-chapter-generator/references/nerdit-sql-runner.js`
- Create: `skills/nerdit-chapter-generator/references/nerdit-python-runner.js`
- Copy to: `d:\siddharth\nerdit-backup\Future Vision Online Course Website Project\future-vision\public\`
- Source: `skills/nerdit-chapter-generator/references/NERDIT_LESSON_PROMPT_v9_simple.md:539-647`

**Interfaces:**
- Consumes: nothing.
- Produces: two browser globals, `window.nerditRunSql(btn)` and `window.nerditRunPython(btn)`, each taking the clicked `.nerdit-run-btn` element and reading `.nerdit-tryit-editor` / writing `.nerdit-tryit-result` within the enclosing `.nerdit-tryit`. Task 2's fragments reference these by name and by file path.

- [ ] **Step 1: Create `nerdit-sql-runner.js`**

Copy lines 605-647 of the rulebook verbatim (the `nerditRunSql` guarded block), wrap in an IIFE, and add a header comment. Do not alter the function body.

```javascript
/* NERDIT SQL runner — sql.js (SQLite compiled to WebAssembly).
 *
 * Lazy-loads the engine from CDN on the learner's first Run click, so a lesson
 * that is never run costs nothing at page load. Seeded per run from the
 * <script type="text/plain"> block named by the widget's data-seed, so the
 * learner always queries exactly the data shown on the page.
 *
 * Served by the website at /nerdit-sql-runner.js. Source of truth lives in the
 * nerdit plugin's references/ directory.
 */
(function () {
  if (typeof window.nerditRunSql !== "function") {
    window.nerditRunSql = function (btn) {
      var box = btn.closest('.nerdit-tryit');
      var status = box.querySelector('.nerdit-tryit-status');
      var out = box.querySelector('.nerdit-tryit-result');
      var run = function(SQL){
        try {
          var db = new SQL.Database();
          var seedEl = document.getElementById(box.getAttribute('data-seed'));
          if (seedEl) db.run(seedEl.textContent);
          var res = db.exec(box.querySelector('.nerdit-tryit-editor').value);
          status.textContent = '';
          if (!res.length) { out.innerHTML = '<div class="nerdit-tryit-empty">Query ran. No rows returned.</div>'; db.close(); return; }
          var r = res[res.length - 1], h = '<table class="nerdit-result-table"><thead><tr>';
          r.columns.forEach(function(c){ h += '<th>' + c + '</th>'; });
          h += '</tr></thead><tbody>';
          r.values.forEach(function(row){
            h += '<tr>';
            row.forEach(function(v){ h += '<td>' + (v === null ? 'NULL' : String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;')) + '</td>'; });
            h += '</tr>';
          });
          out.innerHTML = h + '</tbody></table>';
          db.close();
        } catch (e) {
          status.textContent = '';
          out.innerHTML = '<div class="nerdit-tryit-error">Error: ' + String(e.message || e).replace(/</g,'&lt;') + '</div>';
        }
      };
      if (window.__nerditSQL) return run(window.__nerditSQL);
      status.textContent = 'Loading SQL engine…';
      var boot = function(){
        window.initSqlJs({ locateFile: function(f){ return 'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.2/' + f; } })
          .then(function(SQL){ window.__nerditSQL = SQL; run(SQL); });
      };
      if (window.initSqlJs) return boot();
      var s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.2/sql-wasm.js';
      s.onload = boot;
      s.onerror = function(){ status.textContent = 'Could not load the SQL engine. Check your internet connection.'; };
      document.head.appendChild(s);
    };
  }
})();
```

- [ ] **Step 2: Create `nerdit-python-runner.js`**

Copy lines 540-603 of the rulebook verbatim (the `nerditRunPython` guarded block), wrap in an IIFE, add a header comment. Keep both existing explanatory comments — they record why the traceback is trimmed and why the namespace is recreated.

```javascript
/* NERDIT Python runner — Pyodide (CPython compiled to WebAssembly).
 *
 * Lazy-loads on the learner's first Run click; the first load takes a few
 * seconds and roughly 6 MB, so lessons warn the learner in one sentence.
 * NumPy, pandas, matplotlib and scikit-learn ship inside Pyodide and are
 * importable without extra setup.
 *
 * Served by the website at /nerdit-python-runner.js. Source of truth lives in
 * the nerdit plugin's references/ directory.
 */
(function () {
  if (typeof window.nerditRunPython !== "function") {
    window.nerditRunPython = function (btn) {
      var box = btn.closest('.nerdit-tryit');
      var status = box.querySelector('.nerdit-tryit-status');
      var out = box.querySelector('.nerdit-tryit-result');
      var show = function(text, isError){
        status.textContent = '';
        out.innerHTML = '<div class="nerdit-tryit-output' + (isError ? ' error' : '') + '"></div>';
        out.firstChild.textContent = text === '' ? '(no output — did you forget print()?)' : text;
      };
      // Pyodide tracebacks start with 5-6 frames of its own loader internals
      // (/lib/python312.zip/_pyodide/_base.py). A beginner reading that has no idea
      // which line is theirs, so reduce it to the learner's line + the error itself.
      var friendlyError = function(msg){
        var lines = String(msg).replace(/\s+$/, '').split('\n');
        var errLine = '', lineNo = '';
        for (var i = lines.length - 1; i >= 0; i--) {
          if (/^[A-Za-z_][A-Za-z_.]*(Error|Exception|Interrupt)\b/.test(lines[i].trim())) {
            errLine = lines[i].trim();
            break;
          }
        }
        for (var j = lines.length - 1; j >= 0; j--) {
          var m = lines[j].match(/File "<exec>", line (\d+)/);
          if (m) { lineNo = m[1]; break; }
        }
        if (!errLine) return String(msg);
        return (lineNo ? 'Line ' + lineNo + ' — ' : '') + errLine;
      };
      var run = function(py){
        var buf = [];
        var collect = { batched: function(s){ buf.push(s); } };
        py.setStdout(collect);
        py.setStderr(collect);
        // Fresh namespace each run, so deleting a variable in the editor really
        // removes it instead of silently surviving from the previous run.
        var ns = py.toPy({});
        try {
          py.runPython(box.querySelector('.nerdit-tryit-editor').value, { globals: ns });
          show(buf.join('\n'), false);
        } catch (err) {
          show((buf.length ? buf.join('\n') + '\n' : '') + friendlyError(err.message || err), true);
        } finally {
          py.setStdout({});
          py.setStderr({});
          if (ns && ns.destroy) ns.destroy();
        }
      };
      if (window.__nerditPy) return run(window.__nerditPy);
      status.textContent = 'Loading Python… (first run takes a few seconds)';
      var boot = function(){
        window.loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/' })
          .then(function(py){ window.__nerditPy = py; run(py); })
          .catch(function(){ status.textContent = 'Could not start Python. Check your internet connection.'; });
      };
      if (window.loadPyodide) return boot();
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js';
      s.onload = boot;
      s.onerror = function(){ status.textContent = 'Could not load Python. Check your internet connection.'; };
      document.head.appendChild(s);
    };
  }
})();
```

- [ ] **Step 3: Verify both files parse**

```bash
node --check skills/nerdit-chapter-generator/references/nerdit-sql-runner.js
node --check skills/nerdit-chapter-generator/references/nerdit-python-runner.js
```

Expected: no output, exit 0 for both. If `node` is unavailable, open each file in the browser console via a `<script>` tag and confirm `typeof nerditRunSql === 'function'`.

- [ ] **Step 4: Copy to the website's public directory**

```bash
cp skills/nerdit-chapter-generator/references/nerdit-sql-runner.js \
   "d:/siddharth/nerdit-backup/Future Vision Online Course Website Project/future-vision/public/"
cp skills/nerdit-chapter-generator/references/nerdit-python-runner.js \
   "d:/siddharth/nerdit-backup/Future Vision Online Course Website Project/future-vision/public/"
```

Confirm all four engines now sit together:

```bash
ls "d:/siddharth/nerdit-backup/Future Vision Online Course Website Project/future-vision/public/nerdit-"*.js
```

Expected: `nerdit-excel-engine.js`, `nerdit-plot-runner.js`, `nerdit-python-runner.js`, `nerdit-sql-runner.js`.

- [ ] **Step 5: Commit the plugin side**

```bash
git add skills/nerdit-chapter-generator/references/nerdit-sql-runner.js skills/nerdit-chapter-generator/references/nerdit-python-runner.js
git commit -m "feat(references): extract SQL and Python runners to standalone .js files"
```

The website copies are a separate repository — commit and deploy them there by that project's own process.

- [ ] **Step 6: STOP — deployment gate**

The website must be deployed with these two files **before** any lesson generated under the new rulebook goes to production. A lesson referencing `/nerdit-sql-runner.js` on a site that does not serve it renders perfectly and fails silently on the first Run click.

Confirm with the user that the website deploy is either done or scheduled before continuing past Task 2. Do not treat this as optional.

---

### Task 2: Split the rulebook

**Files:**
- Create: `skills/nerdit-chapter-generator/references/CORE.md`
- Create: `skills/nerdit-chapter-generator/references/runners/sql.md`
- Create: `skills/nerdit-chapter-generator/references/runners/python.md`
- Create: `skills/nerdit-chapter-generator/references/runners/excel.md`
- Create: `skills/nerdit-chapter-generator/references/runners/plot.md`
- Delete: `skills/nerdit-chapter-generator/references/NERDIT_LESSON_PROMPT_v9_simple.md`

**Interfaces:**
- Consumes: the `.js` filenames from Task 1 (`/nerdit-sql-runner.js`, `/nerdit-python-runner.js`).
- Produces: five Markdown files. Task 4's orchestrator and agent reference them by exact path: `references/CORE.md` and `references/runners/<runner>.md` where `<runner>` is one of `sql`, `python`, `excel`, `plot`.

- [ ] **Step 1: Capture the baseline before touching anything**

```bash
python - <<'PY'
import json, re
src = "skills/nerdit-chapter-generator/references/NERDIT_LESSON_PROMPT_v9_simple.md"
lines = open(src, encoding="utf-8").read().split("\n")
base = {
    "total": len(lines),
    "nonblank": sum(1 for l in lines if l.strip()),
    "headings": [l for l in lines if re.match(r"^#{1,3} ", l)],
}
json.dump(base, open("../baseline.json", "w", encoding="utf-8"), indent=2)
print(base["total"], base["nonblank"], len(base["headings"]))
PY
```

Expected output: `724 631 18`. If these three numbers differ, the file has changed since this plan was written — stop and re-derive the line map in the accounting identity above before splitting.

- [ ] **Step 2: Create the four runner fragments**

Each fragment is the corresponding source range copied verbatim, given an `# ` title, and with one added line telling the agent which script to load.

`runners/sql.md` — source lines 265-288, plus title and script line:

```markdown
# Runner: SQL (sql.js)

Load the engine once per lesson, after the demo-data block:

<script src="/nerdit-sql-runner.js"></script>

<!-- then lines 265-288 of the original rulebook, verbatim:
     the "**SQL variant**" paragraph, the fenced HTML example with its
     data-seed widget and <script type="text/plain"> seed block, and the
     closing paragraph explaining data-seed and lazy loading -->
```

`runners/python.md` — source lines 244-264, same treatment, script line `<script src="/nerdit-python-runner.js"></script>`.

`runners/excel.md` — source lines 289-370 verbatim under `# Runner: Excel`. It already carries its own `<script src="/nerdit-excel-engine.js">` instruction; do not add a second one.

`runners/plot.md` — source lines 371-412 verbatim under `# Runner: Matplotlib`. Same — it already names `/nerdit-plot-runner.js`.

Copy the source ranges with a text editor or `sed -n '265,288p'`. Do not retype them: retyping is how wording silently changes.

- [ ] **Step 3: Create `CORE.md`**

Concatenate, in this order: source lines 1-233, then 234-237, then the replacement paragraph below, then 413-491, then 492-538, then 648-655, then 656-724.

The replacement paragraph, which takes the place of deleted lines 238-243:

```markdown
At most ONE live runner per lesson, on the concept that benefits most. The orchestrator
gives you the runner fragment for this lesson — follow it exactly, and do not substitute a
different runner. If a lesson genuinely needs a different one, read that fragment from
`references/runners/` first.
```

Then adjust the §9 intro (source lines 494-496) so it no longer promises runner code. Replace:

```markdown
Emit ONE script only if the lesson uses copy buttons, tabs, fill-blanks, the SQL runner,
or Chart.js. Compose only the parts you need. All helpers are guarded so multiple lessons
on one page never double-define.
```

with:

```markdown
Emit ONE script only if the lesson uses copy buttons, tabs, fill-blanks, or Chart.js.
Compose only the parts you need. All helpers are guarded so multiple lessons on one page
never double-define.

Live code runners are NOT part of this script. Each runner ships as its own file, loaded
with a `<script src>` given in that runner's fragment.
```

Finally, remove the now-dangling `nerditRunPython` and `nerditRunSql` blocks from the fenced script (source lines 539-647) — they are already accounted for as moved to Task 1's `.js` files.

- [ ] **Step 4: Verify the line-accounting identity**

```bash
python - <<'PY'
import json, re, pathlib
base = json.load(open("../baseline.json", encoding="utf-8"))
ref = pathlib.Path("skills/nerdit-chapter-generator/references")
files = {
    "CORE.md": 367, "runners/sql.md": 22, "runners/python.md": 20,
    "runners/excel.md": 74, "runners/plot.md": 35,
}
ADDED = {  # permitted additions, enumerated in the plan
    "CORE.md": 8,          # replacement paragraph + reworded §9 intro
    "runners/sql.md": 3, "runners/python.md": 3,   # title + script line
    "runners/excel.md": 1, "runners/plot.md": 1,   # title only
}
total = 0
for name, expected in files.items():
    got = sum(1 for l in (ref / name).read_text(encoding="utf-8").split("\n") if l.strip())
    net = got - ADDED[name]
    print(f"{name:22} {got:4} lines, {net:4} after additions, expected {expected}")
    total += net
js = sum(1 for f in ("nerdit-sql-runner.js", "nerdit-python-runner.js")
         for l in (ref / f).read_text(encoding="utf-8").split("\n") if l.strip())
print(f"\nmarkdown net {total} + js {js} + deleted 6 = {total + js + 6}")
print(f"baseline nonblank                          = {base['nonblank']}")
PY
```

Expected: each file's net count matches its expected value, and the final two numbers are equal at **631**. The `.js` total will exceed 107 by the wrapper and header-comment lines those files gained — subtract those before comparing, or accept a small documented surplus and record the exact figure in the commit message.

- [ ] **Step 5: Verify every heading landed**

```bash
python - <<'PY'
import json, re, pathlib
base = json.load(open("../baseline.json", encoding="utf-8"))
ref = pathlib.Path("skills/nerdit-chapter-generator/references")
new = ""
for p in list(ref.glob("*.md")) + list((ref / "runners").glob("*.md")):
    new += p.read_text(encoding="utf-8")
REMOVED = []  # no headings are intentionally removed; only the §6c table
missing = [h for h in base["headings"]
           if h.strip() not in new and h.strip() not in REMOVED]
print("MISSING HEADINGS:", missing if missing else "none")
PY
```

Expected: `MISSING HEADINGS: none`. Any heading listed here is a dropped section — restore it before continuing.

- [ ] **Step 6: Delete the original**

```bash
git rm skills/nerdit-chapter-generator/references/NERDIT_LESSON_PROMPT_v9_simple.md
```

- [ ] **Step 7: Commit**

```bash
git add skills/nerdit-chapter-generator/references/
git commit -m "refactor(references): split rulebook into CORE.md plus per-runner fragments"
```

---

### Task 3: Assembler asset paths

**Files:**
- Modify: `skills/nerdit-chapter-generator/scripts/assemble_course.py:22-23`
- Test: `skills/nerdit-chapter-generator/scripts/test_assemble_course.py` (append)

**Interfaces:**
- Consumes: the `.js` filenames from Task 1.
- Produces: `detect_assets(html)` returning `/`-prefixed URLs for any of four engines. Nothing later depends on it.

- [ ] **Step 1: Write the failing tests**

Append to `test_assemble_course.py`:

```python
def test_detect_assets_covers_all_four_engines():
    assert detect_assets("uses nerdit-sql-runner.js") == ["/nerdit-sql-runner.js"]
    assert detect_assets("uses nerdit-python-runner.js") == ["/nerdit-python-runner.js"]
    assert detect_assets("uses nerdit-excel-engine.js") == ["/nerdit-excel-engine.js"]
    assert detect_assets("uses nerdit-plot-runner.js") == ["/nerdit-plot-runner.js"]


def test_detect_assets_url_prefix_is_site_root():
    # The website serves these from public/ at the root, not from /assets/js.
    assert all(u.startswith("/nerdit-") for u in detect_assets("nerdit-sql-runner.js"))


def test_detect_assets_multiple_engines_in_engine_files_order(tmp_path):
    html = "<div>nerdit-sql-runner.js and nerdit-plot-runner.js</div>"
    got = detect_assets(html)
    assert got == ["/nerdit-plot-runner.js", "/nerdit-sql-runner.js"]


def test_lesson_without_engine_has_no_assets_key(tmp_path):
    (tmp_path / "l1.html").write_text("<div>plain lesson</div>", encoding="utf-8")
    inp = [{"id": "l1", "title": "T", "description": "d"}]
    c = build_course("demo", inp, None, str(tmp_path), now_ms=1700000000000)
    assert "assets" not in c["lessons"][0]
```

Note `test_detect_assets_multiple_engines_in_engine_files_order` asserts `ENGINE_FILES` order, not order of appearance in the HTML — `detect_assets` iterates the constant. Set `ENGINE_FILES` in Step 3 to `["nerdit-plot-runner.js", "nerdit-excel-engine.js", "nerdit-sql-runner.js", "nerdit-python-runner.js"]` to match.

- [ ] **Step 2: Run to verify they fail**

Run from `skills/nerdit-chapter-generator/scripts`:

`python -m pytest test_assemble_course.py -k assets -v`

Expected: FAIL. `test_detect_assets_covers_all_four_engines` fails first with `assert [] == ['/nerdit-sql-runner.js']` — the SQL runner is not in `ENGINE_FILES`. The pre-existing `test_detect_assets` also fails, on the `/assets/js/` prefix.

- [ ] **Step 3: Update the constants**

Replace lines 22-23 of `assemble_course.py`:

```python
ASSET_URL_BASE = "/assets/js"
ENGINE_FILES = ["nerdit-plot-runner.js", "nerdit-excel-engine.js"]
```

with:

```python
# The website serves these from future-vision/public/, which Vite exposes at the
# site root — /nerdit-excel-engine.js, not /assets/js/nerdit-excel-engine.js.
ASSET_URL_BASE = ""
ENGINE_FILES = [
    "nerdit-plot-runner.js", "nerdit-excel-engine.js",
    "nerdit-sql-runner.js", "nerdit-python-runner.js",
]
```

`detect_assets` builds `f"{ASSET_URL_BASE}/{e}"`, so an empty base yields `/nerdit-plot-runner.js`. Leave that function body unchanged.

- [ ] **Step 4: Fix the pre-existing test's expectations**

The original `test_detect_assets` asserts the old prefix. Update those two lines:

```python
def test_detect_assets():
    assert detect_assets("uses nerdit-plot-runner.js here") == ["/nerdit-plot-runner.js"]
    assert detect_assets("uses nerdit-excel-engine.js") == ["/nerdit-excel-engine.js"]
    assert detect_assets("plain lesson, no engine") == []
```

This is the one place the plan knowingly edits an existing test. It encoded a URL that was wrong; the assertion changes because the expected value was incorrect, not because the test was inconvenient.

- [ ] **Step 5: Run the full suite**

`python -m pytest test_assemble_course.py test_input_from_output.py -q`

Expected: PASS, 33 tests (29 existing + 4 new).

- [ ] **Step 6: Commit**

```bash
git add skills/nerdit-chapter-generator/scripts/
git commit -m "fix(assembler): serve engine assets from site root, register all four runners"
```

---

### Task 4: Orchestrator, agent, and docs

**Files:**
- Modify: `agents/nerdit-lesson-writer.md` (Step 0 section)
- Modify: `skills/nerdit-chapter-generator/SKILL.md` (lines 77, 85, 99, 243, plus Step 1 and Step 2b)
- Modify: `README.md` (line 33)

**Interfaces:**
- Consumes: the file paths from Task 2 and the `runner` values `sql | python | excel | plot | none`.
- Produces: the finished pipeline. Nothing depends on this task.

- [ ] **Step 1: Update the agent's Step 0**

In `agents/nerdit-lesson-writer.md`, replace the first bullet of "Step 0 — Read the rulebook first, every time":

```markdown
- Read `${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/references/NERDIT_LESSON_PROMPT_v9_simple.md` in full — skeleton, language rules, component set, banned list, widget script contracts
```

with:

```markdown
- Read `${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/references/CORE.md` in full — skeleton, language rules, component set, banned list, shared script helpers
- If the orchestrator named a `RUNNER`, also read
  `${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/references/runners/<RUNNER>.md` — that
  is the only runner this lesson may use. Read no other runner fragment unless the lesson
  genuinely needs one, in which case read it before using it.
- `RUNNER: none` means no live runner: practice comes from `nerdit-predict` and
  `nerdit-fillblank` only.
```

- [ ] **Step 2: Update SKILL.md's reference table**

Replace the row at line 77:

```markdown
| `references/NERDIT_LESSON_PROMPT_v9_simple.md` | **The lesson rules.** Fixed skeleton, language rules, example units with mandatory outputs, Try It widgets, visual decision table, banned-component list |
```

with:

```markdown
| `references/CORE.md` | **The lesson rules, subject-agnostic.** Fixed skeleton, language rules, example units with mandatory outputs, predict/fill-blank practice, visual decision table, banned-component list, shared script helpers |
| `references/runners/<runner>.md` | **One runner's markup contract.** `sql`, `python`, `excel`, `plot`. Pass exactly one per lesson — see Step 2b |
```

- [ ] **Step 3: Update the two other SKILL.md mentions**

Line 85: `Every lesson follows NERDIT_LESSON_PROMPT_v9_simple.md` → `Every lesson follows CORE.md`.

Line 99: replace

```markdown
**Always read the active style's prompt file first** (`NERDIT_LESSON_PROMPT_v9_simple.md`
by default). It is the single source of truth for what a lesson may and may not contain.
```

with:

```markdown
**`CORE.md` is the single source of truth** for what a lesson may and may not contain.
A runner fragment adds one widget contract on top of it and overrides nothing.
```

Line 243 (QA checklist): replace `Component markup matches NERDIT_LESSON_PROMPT_v9_simple.md exactly` with `Component markup matches CORE.md and the lesson's runner fragment exactly`.

- [ ] **Step 4: Document the `runner` input field in Step 1**

In `## Step 1 — Detect and Read the Input File`, after the three bullets describing `id`, `title`, `description`, add:

```markdown
   - `runner` — *optional*. One of `sql`, `python`, `excel`, `plot`, `none`. Selects the
     runner fragment passed to that lesson's writer. Generation context only: it is never
     copied into the output, and the assembler ignores it.

   If `runner` is absent on some or all lessons, infer it from the chapter name and the
   lesson descriptions, then **print your per-lesson choice and get the user's confirmation
   before spawning any agent.** Inference costs nothing; twelve wrongly-generated lessons
   cost a full run.

   If a `runner` value is not one of the five listed above, stop and show the valid values.
   Do not fall back to `none` — that would silently produce a whole chapter with no
   practice widgets.
```

- [ ] **Step 5: Pass the runner in Step 2b**

In `### 2b. Delegate the lesson to nerdit-lesson-writer`, extend the parameter list. Replace:

```markdown
passing it: `id`, `title`, `description`, chapter name, whether this is a multi-lesson chapter,
`HTML_PATH = <workdir>/<id>.html`, and `QUIZ_PATH = <workdir>/<id>.quiz.json`.
```

with:

```markdown
passing it: `id`, `title`, `description`, chapter name, whether this is a multi-lesson chapter,
`RUNNER` (the resolved value from Step 1), `HTML_PATH = <workdir>/<id>.html`, and
`QUIZ_PATH = <workdir>/<id>.quiz.json`.

Before spawning, confirm `references/runners/<RUNNER>.md` exists on disk. If it does not,
stop — an agent that proceeds without its fragment emits a Try It block whose handler does
not exist.
```

- [ ] **Step 6: Update README.md**

Replace line 33's reference:

```markdown
for the NERDIT component catalogue (`NERDIT_LESSON_PROMPT_v9_simple.md`) and stylesheets (`css8.css` + `css9-simple.css`)
```

with:

```markdown
for the NERDIT component catalogue (`CORE.md` plus one fragment per runner in `runners/`) and
stylesheets (`css8.css` + `css9-simple.css`)
```

- [ ] **Step 7: Verify no stale references remain**

```bash
grep -rn "NERDIT_LESSON_PROMPT_v9_simple" . --exclude-dir=.git
```

Expected: hits only inside `docs/superpowers/`, which are historical records of completed and planned changes and are correct to leave. Any hit in `agents/`, `skills/`, `README.md`, or `.claude-plugin/` must be fixed now.

- [ ] **Step 8: Runtime check — four lessons, four clicks**

This is the only step that catches a broken `<script src>` or an undeployed file, and it cannot be automated here.

Generate a one-lesson chapter for each runner (`sql`, `python`, `excel`, `plot`), load each in the browser, click Run, and confirm real output appears. Confirm Task 1 Step 6's deployment actually happened first.

Expected per runner: SQL returns a result table; Python prints; Excel evaluates a formula; Matplotlib renders a figure.

- [ ] **Step 9: Commit**

```bash
git add agents/ skills/nerdit-chapter-generator/SKILL.md README.md
git commit -m "feat(skill): select one runner fragment per lesson via optional runner field"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Component 1 — file structure, five files | Task 2 Steps 2-3 |
| Component 1 — §9 seam, shared helpers stay | Task 2 Step 3 |
| Component 1 — routing table removed, replacement paragraph | Task 2 Step 3 |
| Component 2 — two `.js` files with guards | Task 1 Steps 1-2 |
| Component 2 — deployment dependency sequenced first | Task 1 Steps 4 and 6 |
| Component 3 — optional `runner` field, five values | Task 4 Step 4 |
| Component 3 — inference prints and confirms before spawning | Task 4 Step 4 |
| Component 3 — field never reaches output | Global Constraints; assembler already reads only `id`/`title` |
| Component 4 — `ASSET_URL_BASE`, `ENGINE_FILES` | Task 3 Step 3 |
| Component 5 — all six referencing sites | Task 4 Steps 1-6, verified Step 7 |
| Error handling — unknown runner value | Task 4 Step 4 |
| Error handling — fragment missing from disk | Task 4 Step 5 |
| Error handling — agent needs a second runner | Task 2 Step 3 replacement paragraph; Task 4 Step 1 |
| Testing — split integrity, headings and line count | Task 2 Steps 1, 4, 5 |
| Testing — assembler asset detection | Task 3 Step 1 |
| Testing — one browser check per runner | Task 4 Step 8 |

No gaps.

**Placeholder scan:** no TBD or TODO. Task 2 Step 2 deliberately describes source ranges rather than reproducing ~150 lines of rulebook text — the instruction is to copy those exact line ranges with `sed`, and retyping is explicitly forbidden, so this is a copy instruction rather than a placeholder.

**Type consistency:** `RUNNER` is the parameter name in Task 4 Steps 1 and 5. Fragment paths are `references/runners/<runner>.md` throughout. The four engine filenames are spelled identically in Task 1, Task 3's `ENGINE_FILES`, and Task 3's tests. `ASSET_URL_BASE = ""` yields the `/nerdit-*.js` URLs the tests assert.

**One known imprecision:** Task 2 Step 4's `.js` line count will exceed the 107 in the identity, because Task 1 adds IIFE wrappers and header comments. The step says to subtract those or record the surplus rather than pretending the number matches exactly.
