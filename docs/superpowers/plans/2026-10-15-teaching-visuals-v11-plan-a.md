# Teaching Visuals v11 — Plan A (plugin rules, checks, tools, styles) Implementation Plan

## Verification record — 2026-10-15

Verified the existing implementation. Steps below were ticked on 2026-10-17 from this record; per-task commit steps were not run as written (see their notes).

- Generator: **191 passed**. Fixed `build_preview.py` to skip code containing child elements, preserving fill-in-the-blank controls.
- Illustrator: **90 passed**. Learner site: **938 passed across 100 files**.
- Admin import/image checks: **14 passed** across `courseImportService.test.ts` and `courseImages.test.ts`.
- Admin visual preservation: **5 passed** in `lessonVisuals.test.ts` (19 admin checks total).
- Both `check_css_bundle.py` and `node ../nerdit/scripts/check-lesson-sync.mjs` pass. Fixed the unreadable active course-map label with a scoped token-based CSS override, copied to both apps.
- Task 12: inspected the actual `fixture-sql` classroom at 1280px and 390px. No document horizontal overflow; bad cells have nontransparent backgrounds; time-window labels remain inside the figure. Final screenshots: workspace `output/playwright/v11-{1280,390}-{light,dark}.png`.
- **Dark-theme check remains unavailable:** no theme toggle exists in the current classroom. Emulated dark system preference at both widths, but the app retained its light palette; the `dark` screenshots document that behavior, not a validated dark theme.
- Task 16 v10: **4 failures / 1557 checks**, exactly the expected 640-wide figures in lessons 13–16.
- Task 16 v11 (read-only): **236 failures / 2597 checks, 36 warnings**: 97 SQL-width failures, 66 missing visual attributes, 35 repeated heading leads, 34 packed SVG labels, plus the 4 existing width failures. These belong to course remediation, outside Plan A. Full output: workspace `output/playwright/v11-course-verification.txt`.
- Task 16 course preservation: the existing `%TEMP%/dm-before.txt` list and current files newer than `samples/results.json` are both empty; the prescribed comparison passes. No generated course files were edited in this run.
- Local fixture console reports unavailable Firestore emulators for gamification; lesson rendering works. No publishing or deployment was exercised.
- No commits or deploys during verification. The work was committed later in one batch: plugin `5dadb55` and nerdit `70de1ef` (2026-10-15, both pushed to `redesign-v2`). Cross-project record: `../../../../nerdit-admin/docs/course-json-images-import-plan.md` (workspace sibling).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the plugin write clearer lessons, and enforce it with checks: v11 visuals (value tables, decision grids, unit tiles, time windows, course map), a single Visual Map, SQL layout, concept-first density, a human-voice check, and a refresh guard. Add a one-lesson gate, a preview that matches the site, and the matching lesson styles.

**Architecture:**
- New checks go into `verify_course.py` under a new `--contract v11`, so v9 and v10 results are unchanged.
- Standalone, stdlib-only scripts: `check_prose.py` (voice), `check_refresh.py` (refresh guard), `gate_lesson.py` (one-lesson gate, composing every check) and `build_preview.py` (site-faithful preview).
- Rules live in `CORE.md` §7 (the Visual Map) and `figures.md` (markup). Styles are added to `css9-simple.css` and copied to the website and admin.

**Tech Stack:** Python 3.14 stdlib + pytest (plugin); CSS; React/Vite fixture + vitest (website); Playwright for the visual check.

**Spec:** `docs/superpowers/specs/2026-10-15-teaching-visuals-v11-and-data-modelling-remediation-design.md`. This plan covers Part 1 §1.1–§1.10 and Part 2. **Plan B** (business worlds: §1.10.2, §1.11, `make_world_data.py`, `check_world.py`, world library, the course-map warning, the synthetic-data note check) and **Part 3** (course lessons) are out of scope.

## Global Constraints

- **Never modify course lesson files.** Nothing under `nerdit/generated/` changes (Part 3 is excluded).
- Plugin scripts use the **stdlib only** (as `verify_course.py` already does).
- **v9 and v10 behaviour is unchanged.** Every new check runs only under `--contract v11`, and all existing tests pass unmodified, except the four illustrator markup tests Task 15 updates.
- Limits:
  - SQL line: 60 characters max.
  - Shown code block: 15 lines max.
  - Shown code per lesson: 40 lines for `concept`, 100 for `hands-on`.
- Lesson styles use colour **tokens only** (`var(--…)`), never hex.
- The three copies of `css9-simple.css` stay identical: plugin `references/`, `nerdit/future-vision/src/lesson-css/` and `nerdit-admin/src/lesson-css/`. `check_css_bundle.py` must exit 0.
- **Plugin tests:** run from each `scripts/` dir with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`. A broken urllib3 plugin in the user site-packages breaks autoload. Baseline: generator **133 passed**, illustrator **89 passed**.
- **Commits:** only after the user approves committing. Stage **only** the files a task lists, because both repos carry unrelated uncommitted work. End each commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **No deploys.**
- Paths below are relative to `nerdit-plugin-json-generator/` unless they start with `nerdit/` or `nerdit-admin/`, which are relative to the workspace root `nerdit-mainAndPlugin/`.

## Review Focus

1. **A course already verified under v10 must give the same result under v10.** A lesson with a 66-character SQL line, a dotted SVG label and no `data-visual` passes v10 exactly as before. Covered by tests in Tasks 2 and 4.
2. **HTML entities count as one character.** `&lt;&gt;` in SQL is two visible characters, so a 59-character line written with entities passes the 60 limit. Covered in Task 2.
3. **Malformed lesson HTML must not crash text extraction.** Unclosed `<p>` and `<section>` still yield all their text. Covered in Task 1.
4. **Reading steps come in two forms.** The writer emits `<ul><li>①…` after a figure; the illustrator emits `<ol class="nerdit-visual-read">`. The refresh guard treats both as figure scope. Covered in Task 7.
5. **Prose with emoji, Devanagari or ₹ must not crash the voice check** or produce false banned hits. Covered in Task 6.

---

## File map

| File | Responsibility | Task |
| --- | --- | --- |
| `skills/nerdit-chapter-generator/scripts/verify_course.py` | text capture, `Report.warn`, contract v11, v11 checks, `verify_density` | 1–5 |
| `skills/nerdit-chapter-generator/scripts/test_verify_v11.py` (new) | v11 tests | 1–5 |
| `skills/nerdit-chapter-generator/scripts/check_input.py` + `test_check_input.py` | `focus` field | 5 |
| `skills/nerdit-chapter-generator/references/voice.md` (new) | banned phrases + voice guidance | 6 |
| `skills/nerdit-chapter-generator/scripts/check_prose.py` + `test_check_prose.py` (new) | voice check | 6 |
| `skills/nerdit-chapter-generator/scripts/check_refresh.py` + `test_check_refresh.py` (new) | refresh guard | 7 |
| `skills/nerdit-chapter-generator/scripts/gate_lesson.py` + `test_gate_lesson.py` (new) | one-lesson gate | 8 |
| `skills/nerdit-chapter-generator/scripts/build_preview.py` + `test_build_preview.py` (new) | preview page | 9 |
| `skills/nerdit-chapter-generator/references/css9-simple.css` (+ 2 copies), `test_check_css_bundle.py` | v11 styles | 10 |
| `skills/nerdit-chapter-generator/references/figures.md`, `test_figures_templates.py` (new) | rules R10–R15, icon set, templates 11–15 | 11 |
| `nerdit/future-vision/src/utils/__fixtures__/lesson-v11-visuals.html` (new), `nerdit/future-vision/src/services/courseService.fixture.ts` | dev fixture | 12 |
| `skills/nerdit-chapter-generator/references/CORE.md`, `references/runners/sql.md`, `test_reference_sql_width.py` (new) | Visual Map, SQL layout, focus, voice | 13 |
| `agents/nerdit-lesson-writer.md`, `agents/nerdit-qa-validator.md`, `skills/nerdit-chapter-generator/SKILL.md`, `.claude-plugin/plugin.json`, `test_docs_refs.py` (new) | writer/QA/orchestrator docs, version | 14 |
| `skills/nerdit-lesson-illustrator/scripts/insert_images.py`, `extract_outline.py`, tests, `references/style.md`, `SKILL.md` | `data-visual`, `--hints` | 15 |

Shorthand: `G = skills/nerdit-chapter-generator`, `GS = G/scripts`, `IS = skills/nerdit-lesson-illustrator/scripts`.

---

### Task 0: Baseline

**Files:** none.

- [x] **Step 1: Record test baselines**

Run:
```bash
cd skills/nerdit-chapter-generator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q | tail -1
cd ../../nerdit-lesson-illustrator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q | tail -1
```
Expected: `133 passed`, then `89 passed`.

- [x] **Step 2: Snapshot the course folder so Task 16 can prove it is untouched**

Run (from workspace root):
```bash
find nerdit/generated/data-modelling-etl-data-warehousing-for-analysts -type f -newer nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/samples/results.json | sort > "$TMP/dm-before.txt"; wc -l "$TMP/dm-before.txt"
```
Expected: a count (any). Keep the file for Task 16.

---

### Task 1: verify_course — text capture, warnings, contract v11

**Files:**
- Modify: `GS/verify_course.py` (`Node`, `Tree`, `Report`, `main`, contract checks)
- Create: `GS/test_verify_v11.py`

**Interfaces:**
- Produces:
  - `Node.content: list[str | Node]` (children and text, in page order)
  - `text_of(node: Node) -> str`
  - `Report.warnings: list[str]` and `Report.warn(ok: bool, msg: str) -> None`
  - `FLAT = {"v10", "v11"}`
  - CLI `--contract v11`
- Test helpers in `test_verify_v11.py` that later tasks append to: `wrap(body) -> dict`, `run(body, contract="v11") -> Report`, `run_line(sql) -> str`.

- [x] **Step 1: Write the failing tests**

Create `GS/test_verify_v11.py`:
```python
"""Contract v11 checks (spec 2026-10-15 §1.7, §1.9). Shared helpers first; later tasks append tests."""
from verify_course import Report, parse, text_of, verify_structure


def wrap(body: str) -> dict:
    return {"lessons": [{"id": "x", "content": f'<div class="nerdit-wrapper nerdit-simple">{body}</div>'}]}


def run(body: str, contract: str = "v11") -> Report:
    rep = Report()
    verify_structure(rep, wrap(body), contract)
    return rep


def run_line(sql: str) -> str:
    return ('<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span>'
            f'<pre data-lang="sql"><code>{sql}</code></pre></div>'
            '<div class="nerdit-out"><span class="nerdit-tag">SQL shows</span><pre><code>x</code></pre></div></div>')


def test_text_of_keeps_document_order_and_decodes_entities():
    p = next(n for n in parse("<p>a <b>b</b> c &lt;&gt; d</p>").all if n.tag == "p")
    assert text_of(p) == "a b c <> d"


def test_text_of_survives_unclosed_tags():
    tree = parse("<section><p>one<p>two</section><p>three")
    whole = text_of(tree.root)
    assert "one" in whole and "two" in whole and "three" in whole


def test_warn_records_advice_without_failing():
    rep = Report()
    rep.warn(False, "advice")
    rep.warn(True, "fine")
    rep.check(True, "ok")
    assert rep.failures == [] and rep.warnings == ["advice"] and rep.passed == 1


def test_v11_keeps_every_v10_check():
    body = ('<div class="nerdit-figure" data-visual="diagram"><svg viewBox="0 0 640 200" role="img" '
            'aria-label="A"><text fill="var(--nb)">l</text></svg>'
            '<div class="nerdit-figure-caption">C.</div></div>')
    assert any("viewBox is 640 wide" in f for f in run(body).failures)
    assert any("viewBox is 640 wide" in f for f in run(body, "v10").failures)
```

- [x] **Step 2: Run them; confirm they fail**

Run: `cd GS && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_verify_v11.py`
Expected: FAIL with `ImportError: cannot import name 'text_of'`.

- [x] **Step 3: Implement**

In `verify_course.py`:

1. Below `MAX_FIGURE_VIEWBOX_WIDTH = 400 …` add:
```python
# Contracts that use the flattened (v10) checks. v11 adds the teaching-visuals checks
# (spec 2026-10-15): SQL layout, run-line headings, figure data-visual and dotted labels.
FLAT = {"v10", "v11"}
```
2. In `class Node`, change `__slots__` to
`("tag", "classes", "el_id", "parent", "children", "attrs", "content")` and add at the end of `__init__`:
```python
        # Children and text in page order, for checks that read labels and code.
        self.content: list = []
```
3. In `class Tree`:
   - Change the docstring to `"""Minimal DOM: tags, classes, ids, attributes and text in page order."""`.
   - In both `handle_starttag` and `handle_startendtag`, after `self.cur.children.append(node)`, add `self.cur.content.append(node)`.
   - Add the method:
```python
    def handle_data(self, data):
        self.cur.content.append(data)
```
4. After `def parse(...)` add:
```python
def text_of(node: Node) -> str:
    """All text under `node`, in page order, entities already decoded."""
    out: list[str] = []
    stack: list = list(reversed(node.content))
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            out.append(item)
        else:
            stack.extend(reversed(item.content))
    return "".join(out)
```
5. Replace `class Report` with:
```python
class Report:
    def __init__(self):
        self.passed = 0
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def check(self, ok: bool, msg: str):
        if ok:
            self.passed += 1
        else:
            self.failures.append(msg)

    def warn(self, ok: bool, msg: str):
        """Advisory: printed after the result, never changes the exit code."""
        if not ok:
            self.warnings.append(msg)
```
6. Replace **every** `contract == "v10"` with `contract in FLAT`. Check with `grep -n 'contract == "v10"' verify_course.py`; expected afterwards: no output (there are 3 today: depth cap, retired, viewBox width).
7. In `main()`:
   - Change the argparse choices to `["v9", "v10", "v11"]` and the help to `"v10 rejects retired blocks; v11 adds the teaching-visuals checks"`.
   - Replace everything from `total = rep.passed + len(rep.failures)` to the end of `main` with:
```python
    total = rep.passed + len(rep.failures)
    if rep.failures:
        print(f"FAIL  {len(rep.failures)} of {total} checks (contract {args.contract})")
        for f in rep.failures:
            print(f"  - {f}")
    elif not args.quiet:
        print(f"PASS  {rep.passed}/{total} checks (contract {args.contract})")
    for w in rep.warnings:
        print(f"  WARN {w}")
    return 1 if rep.failures else 0
```

- [x] **Step 4: Run the new tests and the whole suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: `137 passed` (133 + 4).

- [x] **Step 5: Commit** (only if commits are approved) _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_
```bash
git add skills/nerdit-chapter-generator/scripts/verify_course.py skills/nerdit-chapter-generator/scripts/test_verify_v11.py
git commit -m "feat(verify): text capture, advisory warnings and contract v11"
```

---

### Task 2: v11 — SQL line width

**Files:** Modify `GS/verify_course.py`; append to `GS/test_verify_v11.py`.

**Interfaces:**
- Consumes: `text_of`, `FLAT`, `run`, `run_line`.
- Produces: `MAX_SQL_LINE = 60`, `ancestor(node, cls) -> Node | None`, `sql_code_blocks(tree) -> list[tuple[str, str]]`.

- [x] **Step 1: Append failing tests**
```python
LONG = "SELECT order_id, customer_id, amount_paise, sale_date FROM orders;"  # 66 chars


def test_v11_fails_a_long_sql_line_in_a_run_line():
    assert any("over 60 characters" in f for f in run(run_line(LONG)).failures)


def test_v11_accepts_sql_laid_out_one_clause_per_line():
    ok = "SELECT order_id, amount_paise\nFROM orders\nWHERE amount_paise &gt; 0;"
    assert not any("over 60" in f for f in run(run_line(ok)).failures)


def test_entities_count_as_one_character():
    # 59 visible characters; written with &lt;&gt; it is 65 bytes of HTML.
    line = "SELECT order_id, amount FROM orders WHERE status &lt;&gt; 'void';"
    assert not any("over 60" in f for f in run(run_line(line)).failures)


def test_v11_checks_sql_try_it_editors_but_not_python_ones():
    sql_box = f'<div class="nerdit-tryit" data-seed="s1"><textarea class="nerdit-tryit-editor">{LONG}</textarea></div>'
    py_box = ('<div class="nerdit-tryit" data-lang="python"><textarea class="nerdit-tryit-editor">'
              f'{"x = 1  # " + "a" * 70}</textarea></div>')
    assert any("try-it editor" in f for f in run(sql_box).failures)
    assert not any("try-it editor" in f for f in run(py_box).failures)


def test_v10_ignores_sql_line_width():
    assert not any("over 60" in f for f in run(run_line(LONG), "v10").failures)
```

- [x] **Step 2: Run; expect 4 failures** (the entity and v10 tests already pass).

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_verify_v11.py`

- [x] **Step 3: Implement**

Add near the constants:
```python
MAX_SQL_LINE = 60  # runners/sql.md: the input half wraps, so a longer line breaks mid-statement
```
After `descends_from`, add:
```python
def ancestor(node: Node, cls: str) -> Node | None:
    n = node.parent
    while n is not None:
        if cls in n.classes:
            return n
        n = n.parent
    return None


def sql_code_blocks(tree: "Tree") -> list[tuple[str, str]]:
    """(where, code) for SQL a learner reads or edits: run-line input and SQL Try It editors."""
    out = []
    for n in tree.all:
        if n.tag == "pre" and n.attrs.get("data-lang", "").lower() == "sql" and descends_from(n, "nerdit-in"):
            out.append(("run line", text_of(n)))
        elif n.tag == "textarea" and "nerdit-tryit-editor" in n.classes:
            box = ancestor(n, "nerdit-tryit")
            if box is not None and ("data-seed" in box.attrs or box.attrs.get("data-lang", "").lower() == "sql"):
                out.append(("try-it editor", text_of(n)))
    return out
```
In `verify_structure`, at the end of the per-lesson loop body (after the hex loop), add:
```python
        if contract == "v11":
            for where, code in sql_code_blocks(tree):
                long = [ln.rstrip() for ln in code.splitlines() if len(ln.rstrip()) > MAX_SQL_LINE]
                rep.check(not long, f"{lid}: SQL {where} has {len(long)} line(s) over {MAX_SQL_LINE} "
                                    f"characters (runners/sql.md), first: {long[0].strip()[:40] if long else ''}")
```

- [x] **Step 4: Run all tests.** Expected: `142 passed`.
- [x] **Step 5: Commit** — `feat(verify): v11 fails SQL lines over 60 characters` (same two files). _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 3: v11 — run-line "why" not repeated

**Files:** Modify `GS/verify_course.py`; append to `GS/test_verify_v11.py`.

**Interfaces:**
- Consumes: `text_of`, `walk`.
- Produces: `_norm_sentence(s) -> str`.

- [x] **Step 1: Append failing tests**
```python
def test_v11_fails_a_why_text_repeated_as_the_next_paragraph():
    body = ('<h3 class="nerdit-runhead">CASE <span class="why">— Reject bad records</span></h3>'
            '<p>Reject bad records.</p>')
    assert any("repeated as the next paragraph" in f for f in run(body).failures)


def test_v11_accepts_a_lead_that_says_what_the_code_does():
    body = ('<h3 class="nerdit-runhead">CASE <span class="why">— reject bad records</span></h3>'
            '<p>CASE gives each row one reason code.</p>')
    assert not any("repeated as the next paragraph" in f for f in run(body).failures)
```
- [x] **Step 2: Run; expect 1 failure.**
- [x] **Step 3: Implement**

After `ancestor`, add:
```python
def _norm_sentence(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s.lstrip("—–- ").rstrip(". ")
```
Inside the `if contract == "v11":` block from Task 2, add:
```python
            for h in [n for n in tree.all if n.tag == "h3" and "nerdit-runhead" in n.classes]:
                why = next((c for c in walk(h) if "why" in c.classes), None)
                sibs = h.parent.children if h.parent is not None else []
                nxt = sibs[sibs.index(h) + 1] if sibs.index(h) + 1 < len(sibs) else None
                if why is not None and nxt is not None and nxt.tag == "p":
                    rep.check(_norm_sentence(text_of(why)) != _norm_sentence(text_of(nxt)),
                              f"{lid}: run-line heading's why text is repeated as the next paragraph "
                              f"(CORE.md §4c): {text_of(why).strip()[:50]}")
```
- [x] **Step 4: Run all tests.** Expected: `144 passed`.
- [x] **Step 5: Commit** — `feat(verify): v11 fails a run-line why repeated as its lead`. _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 4: v11 — figure checks and Visual Map balance

**Files:** Modify `GS/verify_course.py`; append to `GS/test_verify_v11.py`.

**Interfaces:**
- Produces:
  - `VISUALS` (set of 8 names)
  - `field_shape(field) -> str | None`
  - `is_dotted_record(text) -> bool`
  - figure failures and balance warnings under v11
- Test helpers added: `fig(kind)`, `svg_fig(label)`, `section(inner)`.

- [x] **Step 1: Append failing tests**
```python
from verify_course import is_dotted_record


def fig(kind):
    attr = f' data-visual="{kind}"' if kind else ""
    return (f'<div class="nerdit-figure"{attr}><table class="nerdit-vtable"><tr><td>1</td></tr></table>'
            '<div class="nerdit-figure-caption">Cap.</div></div>')


def svg_fig(label):
    return ('<div class="nerdit-figure" data-visual="diagram"><svg viewBox="0 0 360 100" role="img" '
            f'aria-label="A"><text fill="var(--tx)">{label}</text></svg>'
            '<div class="nerdit-figure-caption">C.</div></div>')


def section(inner):
    return f"<section><h2>1 — X</h2>{inner}</section>"


def test_dotted_record_detects_rows_not_lists():
    assert is_dotted_record("row 1 · 09:00 · 10000")
    assert is_dotted_record("rn 1 · row 3 · 12500 · kept")
    assert is_dotted_record("O2 · 10:00 · arrived 10:20")
    for label in ("O1 · O2 · O3 · O4 · O5", "MISSING_AMOUNT · BAD_AMOUNT",
                  "O3 · 10:30", "10000 · 12000 · 12500", "watermark · left out (>)"):
        assert not is_dotted_record(label), label


def test_v11_fails_a_figure_without_data_visual():
    assert any("needs data-visual" in f for f in run(fig(None)).failures)
    assert not any("needs data-visual" in f for f in run(fig("value-table")).failures)


def test_v11_fails_a_table_row_packed_into_a_dotted_label():
    assert any("packs a table row" in f for f in run(svg_fig("row 1 · 09:00 · 10000")).failures)
    assert not any("packs a table row" in f for f in run(svg_fig("O1 · O2 · O3")).failures)


def test_v10_ignores_data_visual_and_dotted_labels():
    failures = run(fig(None) + svg_fig("row 1 · 09:00 · 10000"), "v10").failures
    assert not any("data-visual" in f or "packs a table row" in f for f in failures)


def test_v11_warns_a_concept_section_without_a_main_visual():
    assert any("has no main visual" in w for w in run(section("<p>Only prose.</p>")).warnings)
    chart = section('<div class="nerdit-chart-wrap"><canvas></canvas></div>')
    assert not any("has no main visual" in w for w in run(chart).warnings)


def test_v11_warns_when_every_section_uses_the_same_visual():
    same = "".join(section(fig("value-table")) for _ in range(3))
    assert any("same visual" in w for w in run(same).warnings)
    mixed = section(fig("value-table")) + section(fig("decision-grid")) + section(fig("unit-tiles"))
    assert not any("same visual" in w for w in run(mixed).warnings)
```
- [x] **Step 2: Run; expect an ImportError** for `is_dotted_record`.
- [x] **Step 3: Implement**

Constants:
```python
# CORE.md §7 Visual Map: every nerdit-figure names the visual it is.
VISUALS = {"diagram", "value-table", "decision-grid", "time-window", "unit-tiles",
           "chart", "course-map", "illustration"}
DOT_SEP = "·"
_SHAPES = (
    ("time", re.compile(r"\d{1,2}:\d{2}(:\d{2})?")),
    ("date", re.compile(r"\d{4}-\d{2}-\d{2}( \d{1,2}:\d{2}(:\d{2})?)?")),
    ("number", re.compile(r"[₹$]?[\d,]+(\.\d+)?%?")),
    ("code", re.compile(r"[A-Za-z_]+ ?\d+")),
)
```
Functions (after `_norm_sentence`):
```python
def field_shape(field: str) -> str | None:
    """The kind of value a dotted-label field holds; None when it holds no digit."""
    f = field.strip()
    if not re.search(r"\d", f):
        return None
    for name, pat in _SHAPES:
        if pat.fullmatch(f):
            return name
    return "mixed"


def is_dotted_record(text: str) -> bool:
    """`row 1 · 09:00 · 10000` packs a table row into one label (figures.md R10);
    `O1 · O2 · O3` is a list of like values and is fine."""
    fields = text.split(DOT_SEP)
    if len(fields) < 3:
        return False
    shapes = [s for s in (field_shape(f) for f in fields) if s]
    return len(shapes) >= 2 and len(set(shapes)) >= 2
```
Inside the `if contract == "v11":` block, add:
```python
            for i, fig in enumerate(figures, 1):
                rep.check(fig.attrs.get("data-visual") in VISUALS,
                          f"{lid}: figure {i} needs data-visual, one of {', '.join(sorted(VISUALS))} "
                          f"(CORE.md §7)")
            for t in tree.all:
                if t.tag == "text" and descends_from(t, "nerdit-figure"):
                    label = text_of(t).strip()
                    rep.check(not is_dotted_record(label),
                              f"{lid}: figure label packs a table row into dots ({label[:40]}); "
                              f"use a value table (figures.md R10)")
            mains = []
            concept = [s for s in sections if not any(
                n.classes & {"nerdit-cheatsheet", "nerdit-practical"} for n in walk(s))]
            for k, sec in enumerate(concept, 1):
                kinds = {n.attrs.get("data-visual") for n in walk(sec) if "nerdit-figure" in n.classes}
                if any("nerdit-chart-wrap" in n.classes for n in walk(sec)):
                    kinds.add("chart")
                main = kinds - {"illustration", "course-map", None}
                rep.warn(bool(main), f"{lid}: concept section {k} has no main visual (CORE.md §7 Visual Map)")
                mains.append(main)
            used = [m for m in mains if m]
            only = set().union(*used) if used else set()
            rep.warn(not (len(used) >= 3 and len(only) == 1),
                     f"{lid}: every concept section uses the same visual ({', '.join(sorted(only))}); "
                     f"pick each one from the Visual Map")
```
(`figures` and `sections` already exist in `verify_structure`. This block sits after both, at the end of the loop body.)

- [x] **Step 4: Run all tests.** Expected: `150 passed`.
- [x] **Step 5: Commit** — `feat(verify): v11 figure data-visual, dotted-label and Visual Map balance checks`. _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 5: `focus` field and code-density warnings

**Files:** Modify `GS/check_input.py`, `GS/test_check_input.py`, `GS/verify_course.py`; append to `GS/test_verify_v11.py`.

**Interfaces:**
- Produces:
  - `FOCUS = {"concept", "hands-on"}` in `check_input.py`
  - `BLOCK_LINES = 15` and `LESSON_LINES = {"concept": 40, "hands-on": 100}`
  - `shown_code_blocks(tree) -> list[str]`
  - `verify_density(rep, out, inp)` (called by `main` and by `gate_lesson.py`)

- [x] **Step 1: Failing tests**

Append to `test_check_input.py`:
```python
def test_focus_must_be_concept_or_hands_on():
    bad = [dict(GOOD[0], focus="theory")] + GOOD[1:]
    sev, lid, msg = audit(bad)[0]
    assert (sev, lid) == ("ERROR", "a-01") and "unknown focus" in msg
    assert audit([dict(GOOD[0], focus="concept"), dict(GOOD[1], focus="hands-on")]) == []
```
Append to `test_verify_v11.py`:
```python
from verify_course import verify_density


def lesson_with(blocks: list[str]) -> dict:
    return {"lessons": [{"id": "x", "content": "".join(run_line(b) for b in blocks)}]}


def test_density_warns_a_long_block_and_a_heavy_concept_lesson():
    rep = Report()
    verify_density(rep, lesson_with(["SELECT 1;\n" * 20]), [{"id": "x", "focus": "concept"}])
    assert any("code block 1 shows 20 lines" in w for w in rep.warnings)
    rep = Report()
    verify_density(rep, lesson_with(["SELECT 1;\n" * 10] * 5), [{"id": "x", "focus": "concept"}])
    assert any("max 40 for concept" in w for w in rep.warnings)


def test_density_defaults_to_hands_on():
    rep = Report()
    verify_density(rep, lesson_with(["SELECT 1;\n" * 10] * 5), [{"id": "x"}])
    assert not any("max 100" in w for w in rep.warnings)
```
- [x] **Step 2: Run; expect failures** (`unknown focus` missing; ImportError `verify_density`).
- [x] **Step 3: Implement**

In `check_input.py`, under `RUNNER_PRESET` add:
```python
# CORE.md §4: concept lessons use one run line per concept; hands-on lessons 2-3.
FOCUS = {"concept", "hands-on"}
```
In `audit`, after the preset check inside the loop:
```python
        focus = src.get("focus")
        if focus is not None and str(focus).lower() not in FOCUS:
            out.append(("ERROR", lid, f"unknown focus {focus!r} -- one of concept, hands-on (CORE.md §4)"))
```
In `verify_course.py`, constants:
```python
BLOCK_LINES = 15                                   # CORE.md §4: one shown code block
LESSON_LINES = {"concept": 40, "hands-on": 100}    # CORE.md §4: shown code per lesson
```
Functions (after `verify_structure`):
```python
def shown_code_blocks(tree: Tree) -> list[str]:
    return [text_of(n).strip("\n") for n in tree.all if n.tag == "pre" and descends_from(n, "nerdit-in")]


def verify_density(rep: Report, out: dict, inp: list):
    """CORE.md §4: code where the learner must produce or check a number. Advisory only."""
    focus = {s.get("id"): str(s.get("focus") or "hands-on").lower() for s in inp}
    for lesson in out.get("lessons", []):
        lid = lesson.get("id", "?")
        blocks = shown_code_blocks(parse(lesson.get("content", "")))
        for i, code in enumerate(blocks, 1):
            n = len(code.splitlines())
            rep.warn(n <= BLOCK_LINES, f"{lid}: code block {i} shows {n} lines (max {BLOCK_LINES}); "
                                       f"move setup into the seed or a view")
        kind = focus.get(lid, "hands-on")
        cap = LESSON_LINES.get(kind, LESSON_LINES["hands-on"])
        total = sum(len(c.splitlines()) for c in blocks)
        rep.warn(total <= cap, f"{lid}: lesson shows {total} code lines (max {cap} for {kind})")
```
In `main`, after `verify_structure(rep, out, args.contract)`:
```python
    if args.contract == "v11":
        verify_density(rep, out, inp)
```
- [x] **Step 4: Run all tests.** Expected: `153 passed`.
- [x] **Step 5: Commit** — `feat(generator): focus field and v11 code-density warnings` (stage `check_input.py`, `test_check_input.py`, `verify_course.py`, `test_verify_v11.py`). _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 6: Human-voice check

**Files:** Create `G/references/voice.md`, `GS/check_prose.py`, `GS/test_check_prose.py`.

**Interfaces:**
- Consumes: `parse`, `walk`, `Node` from `verify_course`.
- Produces:
  - `banned_patterns(path=VOICE) -> list[tuple[str, re.Pattern]]`
  - `prose(node) -> str`
  - `check_lesson(content, patterns) -> tuple[list[str], list[str]]` (failures, warnings)
  - CLI `--course [--lesson]`

- [x] **Step 1: Create `G/references/voice.md`**
````markdown
# VOICE — write like a teacher talking

`check_prose.py` reads this file. A lesson **fails** on any phrase in the `banned` block below
and gets **warnings** for long sentences (over 15 words), long paragraphs (over 3 sentences),
more than one em dash in a paragraph, and concept sections that all open with the same two
words. Code, tables and figures are not prose and are never checked.

Why: these phrases and that rhythm are what make a lesson read as machine-written. A learner
trusts a teacher who talks plainly.

- Contractions are welcome: "you'll", "it's", "don't".
- Open sections in different ways: a question, a short story beat, a surprising number, a picture.
- Name real things: the store, the person, the amount — from the course's world.

One phrase per line. A line starting `re:` is a regular expression (case-insensitive).

```banned
delve
crucial
seamless
seamlessly
leverage
robust
utilize
let's dive in
dive into
it's important to note
it is important to note
in today's world
in today's fast-paced
furthermore
moreover
additionally
in conclusion
unlock the power
harness the power
game-changer
plays a vital role
plays a crucial role
a testament to
navigate the complexities
embark on
re:\bnot only\b.{1,60}?\bbut also\b
```
````
- [x] **Step 2: Write the failing tests** — `GS/test_check_prose.py`:
```python
from check_prose import banned_patterns, check_lesson

PATS = banned_patterns()


def lesson(body):
    return f'<div class="nerdit-wrapper nerdit-simple">{body}</div>'


def test_banned_phrase_fails_but_not_inside_code():
    fails, _ = check_lesson(lesson("<p>Let's delve into joins.</p>"), PATS)
    assert any("delve" in f for f in fails)
    fails, _ = check_lesson(lesson("<p>Run it.</p><pre><code>-- delve</code></pre>"), PATS)
    assert fails == []


def test_regex_entry_and_whole_words():
    fails, _ = check_lesson(lesson("<p>It is not only fast but also safe.</p>"), PATS)
    assert fails
    fails, _ = check_lesson(lesson("<p>Add one additional column.</p>"), PATS)
    assert fails == []


def test_long_sentence_and_long_paragraph_warn():
    long = "You " + "really " * 15 + "need this."
    _, warns = check_lesson(lesson(f"<p>{long}</p>"), PATS)
    assert any("over 15 words" in w for w in warns)
    _, warns = check_lesson(lesson("<p>One. Two. Three. Four.</p>"), PATS)
    assert any("more than 3 sentences" in w for w in warns)


def test_same_opening_in_every_section_warns():
    secs = "".join(f"<section><h2>{i}</h2><p>A table is thing {i}.</p></section>" for i in range(3))
    _, warns = check_lesson(lesson(secs), PATS)
    assert any("opens with the same words" in w for w in warns)


def test_contractions_emoji_and_indian_scripts_are_fine():
    fails, warns = check_lesson(lesson("<h2>🤔 Why?</h2><p>नमस्ते. You'll see ₹499 here.</p>"), PATS)
    assert fails == [] and warns == []
```
- [x] **Step 3: Run; expect `ModuleNotFoundError: check_prose`.**
- [x] **Step 4: Implement `GS/check_prose.py`**
```python
#!/usr/bin/env python3
"""Human-voice check for lesson prose (CORE.md §10, references/voice.md).

Lessons that read as machine-written share a small set of phrases and one rhythm. This fails
a lesson on a banned phrase and warns on long sentences, long paragraphs, em-dash habits and
concept sections that all open the same way. Code, tables and figures are not prose.

    python check_prose.py --course <course_output.json> [--lesson <id>]

Exit 0 = no banned phrase, 1 = at least one, 2 = could not read a file. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from verify_course import Node, parse, walk

VOICE = Path(__file__).resolve().parent.parent / "references" / "voice.md"
SKIP = {"pre", "code", "textarea", "svg", "script", "style", "table"}
MAX_WORDS = 15
MAX_SENTENCES = 3
MAX_DASHES = 1


def banned_patterns(path: Path = VOICE) -> list[tuple[str, re.Pattern]]:
    """The ```banned block of voice.md: one phrase per line, or `re:<regex>`."""
    block = re.search(r"```banned\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
    if block is None:
        raise ValueError(f"{path} has no ```banned block")
    out = []
    for line in block.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("re:"):
            out.append((line[3:], re.compile(line[3:], re.I)))
        else:
            out.append((line, re.compile(r"(?<!\w)" + re.escape(line) + r"(?!\w)", re.I)))
    return out


def prose(node: Node) -> str:
    """Visible prose under `node`, in page order, skipping code, tables and SVG."""
    parts, stack = [], list(reversed(node.content))
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            parts.append(item)
        elif item.tag not in SKIP:
            stack.extend(reversed(item.content))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _inside(node: Node, tags: set[str]) -> bool:
    n = node.parent
    while n is not None:
        if n.tag in tags:
            return True
        n = n.parent
    return False


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _first_paragraph(sec: Node) -> Node | None:
    stack = list(reversed(sec.content))
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            continue
        if item.tag == "p":
            return item
        stack.extend(reversed(item.content))
    return None


def check_lesson(content: str, patterns) -> tuple[list[str], list[str]]:
    """(failures, warnings) for one lesson's HTML."""
    tree = parse(content)
    fails, warns = [], []

    text = prose(tree.root)
    for phrase, pat in patterns:
        m = pat.search(text)
        if m:
            fails.append(f'banned phrase "{m.group(0)}" (references/voice.md: {phrase})')

    long_s, long_p, dashy = [], 0, 0
    for para in [n for n in tree.all if n.tag in ("p", "li") and not _inside(n, SKIP)]:
        body = prose(para)
        sents = sentences(body)
        long_s += [s for s in sents if len(s.split()) > MAX_WORDS]
        long_p += len(sents) > MAX_SENTENCES
        dashy += body.count("—") > MAX_DASHES
    if long_s:
        warns.append(f'{len(long_s)} sentence(s) over {MAX_WORDS} words, e.g. "{long_s[0][:60]}"')
    if long_p:
        warns.append(f"{long_p} paragraph(s) with more than {MAX_SENTENCES} sentences")
    if dashy:
        warns.append(f"{dashy} paragraph(s) with more than {MAX_DASHES} em dash")

    openers = []
    for sec in [n for n in tree.all if n.tag == "section"]:
        if any(n.classes & {"nerdit-cheatsheet", "nerdit-practical"} for n in walk(sec)):
            continue
        p = _first_paragraph(sec)
        if p is not None:
            openers.append(" ".join(prose(p).lower().split()[:2]))
    if len(openers) >= 3 and len(set(openers)) == 1:
        warns.append(f'every concept section opens with the same words ("{openers[0]}"); vary the openings')
    return fails, warns


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--lesson")
    args = ap.parse_args()
    try:
        course = json.loads(Path(args.course).read_text(encoding="utf-8"))
        patterns = banned_patterns()
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    bad = 0
    for lesson in course.get("lessons", []):
        if args.lesson and lesson.get("id") != args.lesson:
            continue
        fails, warns = check_lesson(lesson.get("content") or "", patterns)
        if fails or warns:
            print(f"{lesson.get('id')}: {len(fails)} banned, {len(warns)} warnings")
            for f in fails:
                print(f"  - {f}")
            for w in warns:
                print(f"  WARN {w}")
        bad += len(fails)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
```
- [x] **Step 5: Run all tests.** Expected: `158 passed`.
- [x] **Step 6: Commit** — `feat(generator): human-voice check and banned-phrase list` (stage the three new files). _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 7: Refresh guard

**Files:** Create `GS/check_refresh.py`, `GS/test_check_refresh.py`.

**Interfaces:**
- Consumes: `parse`, `text_of`, `descends_from`, `Node` from `verify_course`.
- Produces:
  - `MODES = {"figures", "sql-layout", "trim"}`
  - `sql_key(sql) -> str`
  - `parts(html) -> dict[str, list[str]]` (keys `prose, figures, maps, code, outputs, seeds, runheads`)
  - `compare(before_parts, after_parts, modes) -> list[str]`
  - `check(before_dir: Path, after_dir: Path, lid: str, modes: set[str]) -> list[str]`, which raises `ValueError` on an unknown mode and `OSError` on a missing file
  - CLI `--before-dir --after-dir --id --modes`

- [x] **Step 1: Write the failing tests** — `GS/test_check_refresh.py`:
```python
import pytest

from check_refresh import check, compare, parts, sql_key

BASE = ('<div class="nerdit-wrapper nerdit-simple"><section><h2>1 — Clean text</h2>'
        '<p>Spaces hide inside text.</p>'
        '<pre class="nerdit-map">TRIM → removes outer spaces</pre>'
        '<div class="nerdit-figure" data-visual="diagram"><svg viewBox="0 0 360 80" role="img" aria-label="A">'
        '<text>row 1 · 09:00 · 10000</text></svg><div class="nerdit-figure-caption">Cap.</div></div>'
        '<ul><li>① TRIM removes the spaces.</li></ul>'
        '<h3 class="nerdit-runhead">TRIM(customer) <span class="why">— tidy names</span></h3>'
        '<p>TRIM cleans each name.</p>'
        '<div class="nerdit-run"><div class="nerdit-in"><pre data-lang="sql"><code>'
        'SELECT TRIM(customer),amount FROM staged;</code></pre></div>'
        '<div class="nerdit-out"><pre><code>| Aarav | 10 |</code></pre></div></div>'
        '<script type="text/plain" id="seed">CREATE TABLE staged(customer TEXT);</script>'
        '</section></div>')
NEW_FIG = ('<div class="nerdit-figure" data-visual="value-table"><table class="nerdit-vtable"><tr><td>1</td></tr>'
           '</table><div class="nerdit-figure-caption">Cap.</div></div>')
OLD_FIG = BASE[BASE.index('<div class="nerdit-figure"'):BASE.index("<ul>")]


def p(html):
    return parts(html)


def test_unchanged_lesson_passes_every_mode():
    for modes in ({"figures"}, {"sql-layout"}, {"trim"}, set()):
        assert compare(p(BASE), p(BASE), modes) == []


def test_figures_mode_allows_new_figure_new_steps_and_a_removed_map():
    after = (BASE.replace(OLD_FIG, NEW_FIG)
                 .replace("① TRIM removes the spaces.", "① TRIM drops the outer marks.")
                 .replace('<pre class="nerdit-map">TRIM → removes outer spaces</pre>', ""))
    assert compare(p(BASE), p(after), {"figures"}) == []
    assert compare(p(BASE), p(after), {"sql-layout"})


def test_illustrator_reading_steps_count_as_figure_scope():
    after = BASE.replace("<ul><li>① TRIM removes the spaces.</li></ul>",
                         '<ol class="nerdit-visual-read"><li>① TRIM drops the outer marks.</li></ol>')
    assert compare(p(BASE), p(after), {"figures"}) == []


def test_figures_mode_may_not_add_a_map():
    after = BASE.replace("<p>Spaces hide inside text.</p>",
                         '<p>Spaces hide inside text.</p><pre class="nerdit-map">NEW</pre>')
    assert any("text map" in x for x in compare(p(BASE), p(after), {"figures"}))


def test_prose_change_fails_in_every_mode():
    after = BASE.replace("Spaces hide inside text.", "Spaces hide.")
    for modes in ({"figures"}, {"sql-layout"}, {"trim"}, {"figures", "sql-layout", "trim"}):
        assert any(x.startswith("prose") for x in compare(p(BASE), p(after), modes))


def test_sql_layout_allows_whitespace_only():
    relaid = BASE.replace("SELECT TRIM(customer),amount FROM staged;",
                          "SELECT TRIM(customer), amount\nFROM staged;")
    assert compare(p(BASE), p(relaid), {"sql-layout"}) == []
    assert compare(p(BASE), p(relaid), {"figures"})
    changed = BASE.replace("FROM staged;", "FROM clean;")
    assert compare(p(BASE), p(changed), {"sql-layout"})
    assert compare(p(BASE), p(changed), {"trim"}) == []


def test_outputs_seeds_and_runheads_need_trim():
    for old, new in (("| Aarav | 10 |", "| Aarav | 11 |"),
                     ("TEXT);", "TEXT, amount INT);"),
                     ("TRIM cleans each name.", "TRIM tidies names.")):
        after = BASE.replace(old, new)
        assert compare(p(BASE), p(after), {"figures", "sql-layout"}), old
        assert compare(p(BASE), p(after), {"trim"}) == [], old


def test_sql_key_ignores_layout_but_not_tokens_or_literals():
    a = "SELECT r.row_id,r.line_bk FROM raw_line r WHERE x<>'a  b';"
    b = "SELECT\n  r.row_id,\n  r.line_bk\nFROM raw_line r\nWHERE x <> 'a  b';"
    assert sql_key(a) == sql_key(b)
    assert sql_key(a) != sql_key(a.replace("'a  b'", "'a b'"))
    assert sql_key("SELECT a FROM t") != sql_key("SELECT a FROM u")


def _files(d, concepts='{"teaches": ["TRIM"], "uses": []}', quiz='{"lessonQuestions": [], "assessmentQuestions": []}'):
    d.mkdir(exist_ok=True)
    (d / "x.html").write_text(BASE, encoding="utf-8")
    (d / "x.quiz.json").write_text(quiz, encoding="utf-8")
    (d / "x.concepts.json").write_text(concepts, encoding="utf-8")


def test_check_reads_quiz_and_concepts(tmp_path):
    before, after = tmp_path / "b", tmp_path / "a"
    _files(before)
    _files(after, concepts='{"teaches": ["TRIM"], "uses": [], '
                           '"visuals": [{"section": 1, "visual": "value-table", "illustration": null}]}')
    assert check(before, after, "x", {"figures"}) == []
    assert check(before, after, "x", {"sql-layout"})
    _files(after, quiz='{"lessonQuestions": [1], "assessmentQuestions": []}')
    assert any("quiz" in x for x in check(before, after, "x", {"figures"}))


def test_unknown_mode_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        check(tmp_path, tmp_path, "x", {"tidy"})
```
- [x] **Step 2: Run; expect `ModuleNotFoundError: check_refresh`.**
- [x] **Step 3: Implement `GS/check_refresh.py`**
```python
#!/usr/bin/env python3
"""Guard a refresh: only what the chosen modes allow may change (writer refresh mode).

    python check_refresh.py --before-dir <dir> --after-dir <dir> --id <lesson-id>
                            --modes figures[,sql-layout][,trim]

Compares <id>.html, <id>.quiz.json and <id>.concepts.json between the two folders.
  figures    - figures, their reading steps and visual blocks may change; a text map may be removed
  sql-layout - code may change in whitespace only
  trim       - code, outputs, seeds, run-line headings and their leads may change
Prose, the quiz and the concept manifest (except its `visuals` list) never change.
Exit 0 = only allowed changes, 1 = something else changed, 2 = bad mode or missing file. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from verify_course import Node, descends_from, parse, text_of

MODES = {"figures", "sql-layout", "trim"}
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
PUNCT = set("(),;=<>|+-*/")
KEYS = ("prose", "figures", "maps", "code", "outputs", "seeds", "runheads")


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def dump(node: Node) -> str:
    """Tag, attributes and text of a subtree: equal dumps mean an unchanged block."""
    attrs = " ".join(f'{k}="{v}"' for k, v in sorted(node.attrs.items()))
    inner = "".join(_ws(x) if isinstance(x, str) else dump(x) for x in node.content)
    return f"<{node.tag} {attrs}>{inner}</{node.tag}>"


def _reading_steps(node: Node) -> bool:
    if node.tag not in ("ul", "ol"):
        return False
    if "nerdit-visual-read" in node.classes:
        return True
    first = next((c for c in node.children if c.tag == "li"), None)
    return first is not None and text_of(first).strip()[:1] in CIRCLED


def parts(html: str) -> dict[str, list[str]]:
    """A lesson split into comparable parts, each a list in page order."""
    out = {k: [] for k in KEYS}

    def visit(node: Node) -> None:
        prev = None
        for item in node.content:
            if isinstance(item, str):
                if item.strip():
                    out["prose"].append(_ws(item))
                continue
            cls = item.classes
            if "nerdit-figure" in cls or "data-nerdit-img" in item.attrs:
                out["figures"].append(dump(item))
            elif prev is not None and "nerdit-figure" in prev.classes and _reading_steps(item):
                out["figures"].append(dump(item))
            elif item.tag == "pre" and "nerdit-map" in cls:
                out["maps"].append(dump(item))
            elif item.tag == "h3" and "nerdit-runhead" in cls:
                out["runheads"].append(_ws(text_of(item)))
            elif item.tag == "p" and prev is not None and "nerdit-runhead" in prev.classes:
                out["runheads"].append(_ws(text_of(item)))
            elif item.tag == "script" and item.attrs.get("type") == "text/plain":
                out["seeds"].append(text_of(item).strip())
            elif item.tag == "textarea":
                out["code"].append(text_of(item).strip("\n"))
            elif item.tag == "pre":
                out["outputs" if descends_from(item, "nerdit-out") else "code"].append(text_of(item).strip("\n"))
            else:
                visit(item)
            prev = item

    visit(parse(html).root)
    return out


def sql_key(sql: str) -> str:
    """SQL with layout removed: whitespace collapsed outside quotes and dropped next to punctuation."""
    out: list[str] = []
    quote, pending = None, False
    for ch in sql:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch.isspace():
            pending = True
            continue
        if pending and out and ch not in PUNCT and out[-1] not in PUNCT:
            out.append(" ")
        pending = False
        if ch in "'\"":
            quote = ch
        out.append(ch)
    return "".join(out)


def _first_diff(a: list[str], b: list[str]) -> int:
    return next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


def compare(before: dict, after: dict, modes: set[str]) -> list[str]:
    problems: list[str] = []

    def diff(key: str, why: str) -> None:
        a, b = before[key], after[key]
        if a == b:
            return
        i = _first_diff(a, b)
        was = a[i][:70] if i < len(a) else "(nothing)"
        now = b[i][:70] if i < len(b) else "(nothing)"
        problems.append(f"{key} item {i + 1} changed ({why}): was {was!r}, now {now!r}")

    diff("prose", "prose never changes in a refresh")
    if "figures" in modes:
        added = [m for m in after["maps"] if m not in before["maps"]]
        if added:
            problems.append(f"a text map was added or edited; 'figures' may only remove one: {added[0][:70]!r}")
    else:
        diff("figures", "needs the 'figures' mode")
        diff("maps", "needs the 'figures' mode")
    if "trim" not in modes:
        for key in ("outputs", "seeds", "runheads"):
            diff(key, "needs the 'trim' mode")
        if "sql-layout" in modes:
            a = [sql_key(c) for c in before["code"]]
            b = [sql_key(c) for c in after["code"]]
            if a != b:
                problems.append(f"code item {_first_diff(a, b) + 1} changed beyond layout; "
                                f"'sql-layout' only moves whitespace")
        else:
            diff("code", "needs 'sql-layout' or 'trim'")
    return problems


def check(before_dir: Path, after_dir: Path, lid: str, modes: set[str]) -> list[str]:
    unknown = set(modes) - MODES
    if unknown:
        raise ValueError(f"unknown mode(s) {sorted(unknown)}; use {sorted(MODES)}")

    def read(d: Path, ext: str) -> str:
        return (Path(d) / f"{lid}{ext}").read_text(encoding="utf-8")

    problems = compare(parts(read(before_dir, ".html")), parts(read(after_dir, ".html")), set(modes))
    if json.loads(read(before_dir, ".quiz.json")) != json.loads(read(after_dir, ".quiz.json")):
        problems.append("quiz changed; a refresh never touches the quiz")
    bc, ac = json.loads(read(before_dir, ".concepts.json")), json.loads(read(after_dir, ".concepts.json"))
    if "figures" in modes:
        bc.pop("visuals", None)
        ac.pop("visuals", None)
    if bc != ac:
        problems.append("concept manifest changed beyond its visuals list")
    return problems


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--before-dir", required=True)
    ap.add_argument("--after-dir", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--modes", required=True, help="comma list of figures, sql-layout, trim")
    args = ap.parse_args()
    modes = {m.strip() for m in args.modes.split(",") if m.strip()}
    try:
        problems = check(Path(args.before_dir), Path(args.after_dir), args.id, modes)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if problems:
        print(f"FAIL  {args.id}: {len(problems)} change(s) outside {sorted(modes)}")
        for line in problems:
            print(f"  - {line}")
        return 1
    print(f"PASS  {args.id}: only {sorted(modes)} changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
- [x] **Step 4: Run all tests.** Expected: `168 passed`.
- [x] **Step 5: Commit** — `feat(generator): refresh guard for figure, layout and trim refreshes`. _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 8: One-lesson gate

**Files:** Create `GS/gate_lesson.py`, `GS/test_gate_lesson.py`.

**Interfaces:**
- Consumes:
  - `build_course(chapter, input_lessons, meta, html_dir, now_ms)` from `assemble_course`
  - `Report`, `verify_schema`, `verify_structure`, `verify_density`
  - `check_lesson` from `check_sql_outputs` (keys `mismatch`, `unchecked`)
  - `banned_patterns` and `check_lesson` from `check_prose`
  - `check` from `check_refresh`
  - `check_svg(svg, labels, steps)` from the illustrator's `svgcheck`
- Produces: `gate(input_path: Path, lesson_dir: Path, lid: str, contract="v11", before_dir=None, modes=()) -> tuple[list[str], list[str]]`. It raises `FileNotFoundError` when a lesson file is missing and `KeyError` when the id is not in the input. CLI exit codes: 0 pass, 1 fail, 2 missing.

- [x] **Step 1: Write the failing tests** — `GS/test_gate_lesson.py`:
```python
import json

import pytest

from gate_lesson import gate

LESSON = """<div class="nerdit-wrapper nerdit-simple" style="counter-reset:practical-counter challenge-counter;">
<h1>Counting rows</h1>
<section><h2>1 — Count rows</h2>
<p>You count rows with one query.</p>
<div class="nerdit-figure" data-visual="value-table" style="max-width:440px"><table class="nerdit-vtable"><tr><td>3 rows</td><td>count 3</td></tr></table><div class="nerdit-figure-caption">Three rows give a count of 3.</div></div>
<h3 class="nerdit-runhead">SELECT 1 AS n <span class="why">— see one value come back</span></h3>
<p>The query returns the number one.</p>
<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span><pre data-lang="sql"><code>SELECT 1 AS n;</code></pre></div><div class="nerdit-out"><span class="nerdit-tag">SQL shows</span><pre><code>+---+
| n |
+---+
| 1 |
+---+</code></pre></div></div>
<div class="nerdit-predict"><div class="nerdit-predict-head">🤔 Try It</div><p>What does SELECT 2 return?</p><details class="nerdit-predict-answer"><summary>Show answer</summary><p>It returns 2.</p></details></div>
</section></div>"""


def q(text):
    return {"text": text, "options": ["A", "B", "C", "D"], "correctOptionIndex": 0}


QUIZ = {"lessonQuestions": [q("What does SELECT 1 return?"), q("Which word names a column?"), q("What ends a statement?")],
        "assessmentQuestions": [q("Which query counts rows?"), q("What does AS do?"), q("Which result shows one row?")]}
CONCEPTS = {"teaches": ["SELECT", "AS", "result table", "column alias", "statement"], "uses": []}


def setup(tmp_path, html=LESSON):
    d = tmp_path / "w"
    d.mkdir()
    (d / "c-01.html").write_text(html, encoding="utf-8")
    (d / "c-01.quiz.json").write_text(json.dumps(QUIZ), encoding="utf-8")
    (d / "c-01.concepts.json").write_text(json.dumps(CONCEPTS), encoding="utf-8")
    inp = tmp_path / "course-c_input.json"
    inp.write_text(json.dumps([{"id": "c-01", "title": "Counting rows",
                                "description": "Count the rows in a table with one short query and read the answer."}]),
                   encoding="utf-8")
    return inp, d


def test_a_clean_lesson_passes(tmp_path):
    inp, d = setup(tmp_path)
    fails, _ = gate(inp, d, "c-01")
    assert fails == []


def test_wrong_output_and_banned_phrase_fail(tmp_path):
    bad = LESSON.replace("| 1 |", "| 2 |").replace("You count rows", "You delve into rows")
    inp, d = setup(tmp_path, bad)
    fails, _ = gate(inp, d, "c-01")
    assert any(f.startswith("sql:") for f in fails)
    assert any(f.startswith("voice:") for f in fails)


def test_refresh_guard_runs_when_before_dir_is_given(tmp_path):
    inp, d = setup(tmp_path)
    before = tmp_path / "before"
    before.mkdir()
    for f in d.iterdir():
        (before / f.name).write_bytes(f.read_bytes())
    (d / "c-01.html").write_text(LESSON.replace("You count rows with one query.", "Rows get counted."),
                                 encoding="utf-8")
    fails, _ = gate(inp, d, "c-01", before_dir=before, modes={"figures"})
    assert any(f.startswith("refresh:") for f in fails)


def test_missing_lesson_file_raises(tmp_path):
    inp, d = setup(tmp_path)
    (d / "c-01.quiz.json").unlink()
    with pytest.raises(FileNotFoundError):
        gate(inp, d, "c-01")
```
- [x] **Step 2: Run; expect `ModuleNotFoundError: gate_lesson`.**
- [x] **Step 3: Implement `GS/gate_lesson.py`**
```python
#!/usr/bin/env python3
"""One-lesson gate: every check a lesson must pass before it joins its course.

    python gate_lesson.py --input <course_input.json> --dir <lesson dir> --id <lesson-id>
                          [--contract v11] [--before-dir <dir> --modes figures,sql-layout]

Builds a one-lesson course from <dir>/<id>.html, .quiz.json and .concepts.json, then runs:
verify_course (schema, structure, density) -> check_sql_outputs -> SVG checks -> check_prose
-> check_refresh (only with --before-dir). Replaces the course-specific rollout/gate.py.
Exit 0 = pass, 1 = a check failed, 2 = a file or the lesson id is missing. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "nerdit-lesson-illustrator" / "scripts"))

from assemble_course import build_course  # noqa: E402
from check_prose import banned_patterns, check_lesson as check_voice  # noqa: E402
from check_refresh import check as check_refresh  # noqa: E402
from check_sql_outputs import check_lesson as check_sql  # noqa: E402
from svgcheck import check_svg  # noqa: E402
from verify_course import Report, verify_density, verify_schema, verify_structure  # noqa: E402

SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S | re.I)


def gate(input_path: Path, lesson_dir: Path, lid: str, contract: str = "v11",
         before_dir: Path | None = None, modes=()) -> tuple[list[str], list[str]]:
    lessons = json.loads(Path(input_path).read_text(encoding="utf-8"))
    one = [s for s in lessons if s.get("id") == lid]
    if not one:
        raise KeyError(f"{lid} is not in {input_path}")
    for ext in (".html", ".quiz.json", ".concepts.json"):
        if not (Path(lesson_dir) / f"{lid}{ext}").is_file():
            raise FileNotFoundError(Path(lesson_dir) / f"{lid}{ext}")

    course = build_course("gate", one, None, str(lesson_dir), now_ms=0)
    fails: list[str] = []
    warns: list[str] = []

    rep = Report()
    verify_schema(rep, course, one)
    verify_structure(rep, course, contract)
    if contract == "v11":
        verify_density(rep, course, one)
    fails += [f"verify: {f}" for f in rep.failures]
    warns += [f"verify: {w}" for w in rep.warnings]

    html = course["lessons"][0]["content"]
    sql = check_sql(html)
    fails += [f"sql: {m}" for m in sql["mismatch"]]
    warns += [f"sql: {u}" for u in sql["unchecked"]]

    for n, svg in enumerate(SVG_RE.findall(html), 1):
        fails += [f"svg {n}: {e}" for e in check_svg(svg, [], 0)]

    v_fails, v_warns = check_voice(html, banned_patterns())
    fails += [f"voice: {f}" for f in v_fails]
    warns += [f"voice: {w}" for w in v_warns]

    if before_dir is not None:
        fails += [f"refresh: {p}" for p in check_refresh(Path(before_dir), Path(lesson_dir), lid, set(modes))]
    return fails, warns


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--contract", choices=["v10", "v11"], default="v11")
    ap.add_argument("--before-dir")
    ap.add_argument("--modes", default="", help="comma list for the refresh guard")
    args = ap.parse_args()
    modes = {m.strip() for m in args.modes.split(",") if m.strip()}
    try:
        fails, warns = gate(Path(args.input), Path(args.dir), args.id, args.contract,
                            Path(args.before_dir) if args.before_dir else None, modes)
    except (OSError, KeyError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(f"{'FAIL' if fails else 'PASS'}  {args.id}: {len(fails)} failure(s), {len(warns)} warning(s)")
    for f in fails:
        print(f"  - {f}")
    for w in warns:
        print(f"  WARN {w}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
```
- [x] **Step 4: Run all tests.** Expected: `172 passed`. If `test_a_clean_lesson_passes` reports a `verify:` failure, read the message. The fixture must satisfy every v11 rule, so fix the **fixture**, not the gate, unless the failure is a gate bug.
- [x] **Step 5: Commit** — `feat(generator): one-lesson gate composing every check`. _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 9: Site-faithful preview

**Files:** Create `GS/build_preview.py`, `GS/test_build_preview.py`.

**Interfaces:**
- Produces:
  - `REFS`, `CSS_FILES`, `HLJS`
  - `SCOPE_TO_CLASS: dict[str, str]`
  - `build(course: dict) -> str`
  - CLI `--course --out`

- [x] **Step 1: Write the failing tests** — `GS/test_build_preview.py`:
```python
import re
from pathlib import Path

import pytest

from build_preview import CSS_FILES, HLJS, REFS, SCOPE_TO_CLASS, build


def test_preview_inlines_styles_lessons_and_highlighter():
    course = {"title": "T", "lessons": [{"id": "a-01", "title": "One", "duration": "5m",
              "content": '<div class="nerdit-wrapper nerdit-simple"><script src="/nerdit-sql-runner.js"></script>'
                         '<pre data-lang="sql"><code>SELECT 1;</code></pre></div>'}]}
    page = build(course)
    for f in CSS_FILES:
        assert (REFS / f).read_text(encoding="utf-8")[:200] in page
    assert "a-01" in page and "SELECT 1;" in page
    assert "nerdit-sql-runner.js" not in page
    assert '"hljs-keyword": "kw"' in page and HLJS in page


def test_scope_table_matches_the_website():
    ts = Path(__file__).resolve().parents[4] / "nerdit" / "future-vision" / "src" / "utils" / "lessonHighlight.ts"
    if not ts.exists():
        pytest.skip("website checkout is not next to the plugin")
    body = re.search(r"NERDIT_CLASS_BY_SCOPE[^{]*\{(.*?)\};", ts.read_text(encoding="utf-8"), re.S).group(1)
    site = dict(re.findall(r"'?([\w-]+)'?\s*:\s*'([\w-]*)'", body))
    assert site == SCOPE_TO_CLASS
```
- [x] **Step 2: Run; expect `ModuleNotFoundError`.**
- [x] **Step 3: Implement `GS/build_preview.py`**
```python
#!/usr/bin/env python3
"""Preview a course the way learners will see it: one self-contained HTML page.

    python build_preview.py --course <course_output.json> --out <preview.html>

Inlines css8, css9-simple and css10-brand, and colours code with highlight.js using the
website's scope->class table (nerdit/future-vision/src/utils/lessonHighlight.ts), so the
preview and the site agree. Try It boxes run only on the site, so runner scripts are dropped.
Stdlib only.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

REFS = Path(__file__).resolve().parent.parent / "references"
CSS_FILES = ("css8.css", "css9-simple.css", "css10-brand.css")
HLJS = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"
# Keep in step with NERDIT_CLASS_BY_SCOPE in lessonHighlight.ts (test_build_preview checks it).
SCOPE_TO_CLASS = {
    "hljs-keyword": "kw", "hljs-selector-tag": "kw", "hljs-name": "kw", "hljs-literal": "kw",
    "hljs-built_in": "bltin", "hljs-type": "cls-n", "class_": "cls-n",
    "hljs-title": "fn", "function_": "fn", "hljs-section": "fn",
    "hljs-string": "str", "hljs-regexp": "str", "hljs-char": "str", "escape_": "str",
    "hljs-meta-string": "str", "hljs-number": "num", "hljs-comment": "cmt", "hljs-quote": "cmt",
    "hljs-doctag": "cmt", "hljs-operator": "op", "hljs-punctuation": "op", "hljs-meta": "dec",
    "hljs-meta-keyword": "dec", "hljs-params": "param", "hljs-attr": "param",
    "hljs-attribute": "param", "hljs-property": "param", "hljs-selector-attr": "param",
    "hljs-selector-class": "param", "hljs-selector-id": "param", "language_": "slf",
}
RUNNER_TAG = re.compile(r'<script\s+src="/nerdit-[a-z-]+\.js"\s*>\s*</script>\s*', re.I)
HIGHLIGHT = """<script src="%s"></script>
<script>
(function () {
  if (!window.hljs) return;
  var MAP = %s;
  document.querySelectorAll('pre[data-lang] > code').forEach(function (code) {
    var lang = (code.parentElement.getAttribute('data-lang') || '').toLowerCase();
    if (!hljs.getLanguage(lang)) return;
    try {
      code.innerHTML = hljs.highlight(code.textContent, { language: lang, ignoreIllegals: true }).value;
      code.querySelectorAll('span').forEach(function (s) {
        var m = []; s.classList.forEach(function (c) { if (MAP[c]) m.push(MAP[c]); });
        s.removeAttribute('class'); if (m.length) s.className = m.join(' ');
      });
    } catch (e) { /* leave plain text */ }
  });
})();
</script>"""


def build(course: dict) -> str:
    css = "\n".join((REFS / f).read_text(encoding="utf-8") for f in CSS_FILES)
    lessons = course.get("lessons", [])
    nav = "".join(f'<li><a href="#L{i:02d}">{i:02d} · {html.escape(l.get("title", ""))}</a> '
                  f'<span>{html.escape(l.get("duration", ""))}</span></li>' for i, l in enumerate(lessons, 1))
    body = "".join(f'<article class="pv-lesson" id="L{i:02d}"><p class="pv-tag">Lesson {i:02d} · '
                   f'{html.escape(l.get("id", ""))} · <a href="#top">back to list</a></p>'
                   f'{RUNNER_TAG.sub("", l.get("content", ""))}</article>' for i, l in enumerate(lessons, 1))
    title = html.escape(course.get("title") or "Course preview")
    script = HIGHLIGHT % (HLJS, json.dumps(SCOPE_TO_CLASS))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>{css}</style>
<style>
body{{background:var(--bg-soft);margin:0}} .pv-top{{max-width:860px;margin:0 auto;padding:24px 16px 8px}}
.pv-top h1{{margin:0 0 6px;font-size:1.5rem}} .pv-top ol{{list-style:none;padding:0;margin:0;display:grid;gap:4px}}
.pv-lesson{{max-width:860px;margin:24px auto;padding:0 16px}} .pv-tag{{font-size:.8rem;color:var(--tx-m);margin:0 0 6px}}
</style></head><body>
<header class="pv-top" id="top"><h1>{title}</h1>
<p>{len(lessons)} lessons · checking copy, not published. Try It boxes run only on nerdit.in.</p>
<ol>{nav}</ol></header>{body}
{script}
</body></html>"""


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    try:
        course = json.loads(Path(args.course).read_text(encoding="utf-8"))
        page = build(course)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    Path(args.out).write_text(page, encoding="utf-8")
    print(f"{args.out}: {len(course.get('lessons', []))} lessons, {round(len(page.encode()) / 1024)} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
- [x] **Step 4: Run all tests.** Expected: `174 passed`. If `test_scope_table_matches_the_website` fails, copy the site's table exactly; the site is the source of truth.
- [x] **Step 5: Commit** — `feat(generator): preview page that colours code like the site`. _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 10: v11 lesson styles

**Files:**
- Modify: `G/references/css9-simple.css` (append), `GS/test_check_css_bundle.py`
- Copy to: `nerdit/future-vision/src/lesson-css/css9-simple.css`, `nerdit-admin/src/lesson-css/css9-simple.css`

**Interfaces:**
- Produces the classes used by Tasks 11–12 and by writers: `nerdit-vtable`, `nerdit-vgroup`, `nerdit-varrow`, `nerdit-val`, `nerdit-ws`, `nerdit-null`, `nerdit-vnote`, `nerdit-cell-bad`, `nerdit-cell-good`, `nerdit-row-kept`, `nerdit-row-dropped`, `nerdit-vtitle`, `nerdit-vlegend`, `nerdit-grid`, `nerdit-chk ok|first|skip`, `nerdit-tiles`, `nerdit-tilegroup`, `nerdit-tile sup|acc|rej`, `nerdit-vsum`, `nerdit-spot`, `nerdit-data-note`.

- [x] **Step 1: Failing tests** — append to `GS/test_check_css_bundle.py` (add `import re` and `from pathlib import Path` at the top if missing):
```python
V11_CLASSES = ["nerdit-vtable", "nerdit-vgroup", "nerdit-varrow", "nerdit-val", "nerdit-ws", "nerdit-null",
               "nerdit-vnote", "nerdit-cell-bad", "nerdit-cell-good", "nerdit-row-kept", "nerdit-row-dropped",
               "nerdit-vtitle", "nerdit-vlegend", "nerdit-grid", "nerdit-chk", "nerdit-tiles",
               "nerdit-tilegroup", "nerdit-tile", "nerdit-vsum", "nerdit-spot", "nerdit-data-note"]
CSS9 = Path(__file__).resolve().parent.parent / "references" / "css9-simple.css"


def test_css9_defines_every_v11_visual_class():
    css = CSS9.read_text(encoding="utf-8")
    assert [c for c in V11_CLASSES if f".{c}" not in css] == []


def test_v11_css_block_uses_tokens_not_hex():
    css = CSS9.read_text(encoding="utf-8")
    block = css[css.index("v11 · TEACHING VISUALS"):]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)
```
- [x] **Step 2: Run; expect 2 failures.**
- [x] **Step 3: Append to `G/references/css9-simple.css`**
```css

/* ====================================================================
   v11 · TEACHING VISUALS
   ====================================================================
   figures.md templates 11-13 (value table, decision grid, unit tiles),
   visible spaces and NULL (R11), trap cells (R12), the spotlight record
   (R15) and the synthetic-data note. Tokens only: both themes resolve.
   ==================================================================== */
.nerdit-wrapper .nerdit-vtable { width: 100%; border-collapse: collapse; font-size: .95rem; background: var(--white); border-radius: 8px; overflow: hidden; margin: 0 auto; }
.nerdit-wrapper .nerdit-vtable th { text-align: left; font-size: .72rem; letter-spacing: .06em; text-transform: uppercase; color: var(--tx-m); padding: .45rem .6rem; border-bottom: 1px solid var(--bd); background: var(--bg-soft); }
.nerdit-wrapper .nerdit-vtable th code { text-transform: none; letter-spacing: 0; }
.nerdit-wrapper .nerdit-vtable td { padding: .45rem .6rem; border-bottom: 1px solid var(--bd-soft); vertical-align: middle; color: var(--tx); }
.nerdit-wrapper .nerdit-vgroup td { background: var(--bg-soft); font-weight: 700; font-size: .9rem; padding-top: .6rem; }
.nerdit-wrapper .nerdit-varrow { color: var(--tx-m); text-align: center; width: 2rem; }
.nerdit-wrapper .nerdit-val { font-family: var(--font-code); background: var(--white); border: 1px solid var(--bd); border-radius: 4px; padding: .05rem .3rem; white-space: pre; }
.nerdit-wrapper .nerdit-ws { color: var(--tx-m); background: var(--slate-bg); border-radius: 2px; padding: 0 .05rem; }
.nerdit-wrapper .nerdit-null { font-family: var(--font-code); font-style: italic; font-size: .85em; color: var(--tx-s); background: var(--slate-bg); border: 1px dashed var(--bd); border-radius: 999px; padding: .05rem .5rem; }
.nerdit-wrapper .nerdit-vnote { display: block; font-size: .72rem; font-weight: 700; margin-top: .1rem; }
.nerdit-wrapper .nerdit-cell-bad { background: var(--rose-bg); color: var(--rose); font-weight: 700; }
.nerdit-wrapper .nerdit-cell-good { background: var(--green-bg); color: var(--green); font-weight: 700; }
.nerdit-wrapper .nerdit-row-kept td { background: var(--green-bg); color: var(--green); font-weight: 700; }
.nerdit-wrapper .nerdit-row-dropped td { color: var(--tx-m); }
.nerdit-wrapper .nerdit-vtitle { font-weight: 700; font-size: .9rem; margin: 0 0 .4rem; text-align: center; }
.nerdit-wrapper .nerdit-vlegend { font-size: .78rem; color: var(--tx-s); margin: .5rem 0 0; line-height: 1.5; }
.nerdit-wrapper .nerdit-grid td, .nerdit-wrapper .nerdit-grid th { text-align: center; padding: .4rem .3rem; }
.nerdit-wrapper .nerdit-grid td:first-child, .nerdit-wrapper .nerdit-grid th:first-child,
.nerdit-wrapper .nerdit-grid td:last-child, .nerdit-wrapper .nerdit-grid th:last-child { text-align: left; }
.nerdit-wrapper .nerdit-grid td:last-child { font-family: var(--font-code); font-size: .8rem; }
.nerdit-wrapper .nerdit-chk.ok { color: var(--green); font-weight: 800; }
.nerdit-wrapper .nerdit-chk.first { color: var(--rose); font-weight: 800; background: var(--rose-bg); box-shadow: inset 0 0 0 2px var(--rose); border-radius: 6px; }
.nerdit-wrapper .nerdit-chk.skip { color: var(--tx-m); }
.nerdit-wrapper .nerdit-tiles { display: flex; flex-wrap: wrap; gap: .9rem; justify-content: center; }
.nerdit-wrapper .nerdit-tilegroup { display: flex; flex-direction: column; align-items: center; gap: .35rem; font-size: .82rem; color: var(--tx-s); }
.nerdit-wrapper .nerdit-tilegroup > div { display: flex; gap: .3rem; padding-bottom: .35rem; border-bottom: 2px solid var(--bd); }
.nerdit-wrapper .nerdit-tile { width: 2.3rem; height: 2.3rem; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; font-weight: 800; border: 1.5px solid; }
.nerdit-wrapper .nerdit-tile.sup { background: var(--slate-bg); border-color: var(--bd); color: var(--tx-m); }
.nerdit-wrapper .nerdit-tile.acc { background: var(--green-bg); border-color: var(--green); color: var(--green); }
.nerdit-wrapper .nerdit-tile.rej { background: var(--amber-bg); border-color: var(--amber); color: var(--amber); }
.nerdit-wrapper .nerdit-vsum { text-align: center; font-weight: 600; margin: .7rem 0 0; }
.nerdit-wrapper .nerdit-spot, .nerdit-wrapper tr.nerdit-spot td { background: var(--blue-bg); box-shadow: inset 3px 0 0 var(--blue); }
.nerdit-wrapper svg .nerdit-spot { fill: var(--blue-bg); stroke: var(--blue); }
.nerdit-wrapper .nerdit-data-note { font-size: .78rem; color: var(--tx-m); font-style: italic; margin: .3rem 0 1rem; }
```
- [x] **Step 4: Copy and check the bundle**

From `G`:
```bash
cp references/css9-simple.css ../../../nerdit/future-vision/src/lesson-css/css9-simple.css
cp references/css9-simple.css ../../../nerdit-admin/src/lesson-css/css9-simple.css
python scripts/check_css_bundle.py references ../../../nerdit/future-vision/src/lesson-css ../../../nerdit-admin/src/lesson-css; echo "exit $?"
```
Expected: `exit 0`, with no `DRIFT` lines.

- [x] **Step 5: Run all tests.** Expected: `176 passed`.
- [x] **Step 6: Commit** _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_
  - Plugin repo: `references/css9-simple.css` and `scripts/test_check_css_bundle.py`.
  - `nerdit` repo: `future-vision/src/lesson-css/css9-simple.css`.
  - `nerdit-admin` repo: `src/lesson-css/css9-simple.css`.
  - Message: `feat(css): v11 teaching-visual styles`.

---

### Task 11: figures.md — rules R10–R15, icon set, templates 11–15

**Files:** Modify `G/references/figures.md`; create `GS/test_figures_templates.py`.

**Interfaces:**
- Consumes: v11 checks (Tasks 1–4) and the styles (Task 10).
- Produces: template headings `## 11 ·` … `## 15 ·`, each with ` ```html ` blocks. Task 12 extracts them by those headings.

- [x] **Step 1: Write the failing doc test** — `GS/test_figures_templates.py`:
```python
"""figures.md is copied by writers verbatim, so its templates must pass the checks they teach."""
import re
from pathlib import Path

from verify_course import Report, verify_structure

FIG = Path(__file__).resolve().parent.parent / "references" / "figures.md"


def template_blocks() -> dict[int, list[str]]:
    text = FIG.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^## (\d+) · .*?(?=^## |\Z)", text, re.S | re.M):
        out[int(m.group(1))] = re.findall(r"```html\n(.*?)```", m.group(0), re.S)
    return out


def test_every_template_figure_names_its_visual():
    for n, blocks in template_blocks().items():
        for b in blocks:
            if 'class="nerdit-figure' in b:
                assert "data-visual=" in b, f"template {n}"


def test_v11_templates_pass_the_v11_figure_checks():
    blocks = template_blocks()
    for n in (11, 12, 13, 14, 15):
        assert blocks.get(n), f"template {n} missing"
        for b in blocks[n]:
            rep = Report()
            verify_structure(rep, {"lessons": [{"id": f"t{n}",
                             "content": f'<div class="nerdit-wrapper nerdit-simple">{b}</div>'}]}, "v11")
            bad = [f for f in rep.failures
                   if any(k in f for k in ("data-visual", "packs a table row", "viewBox", "hex", "caption", "aria"))]
            assert not bad, (n, bad)
```
- [x] **Step 2: Run; expect failures** (templates 11–15 missing; existing templates lack `data-visual`).

- [x] **Step 3: Add `data-visual` to the existing figures**

Run from `G/references`:
```bash
python -I - <<'PY'
import re
from pathlib import Path
p = Path("figures.md"); s = p.read_text(encoding="utf-8")
s2 = re.sub(r'<div class="nerdit-figure"(?! data-visual)', '<div class="nerdit-figure" data-visual="diagram"', s)
p.write_text(s2, encoding="utf-8"); print(s.count('<div class="nerdit-figure"'), "wrappers updated")
PY
```
Then read template 9 (Chart.js). If any `nerdit-figure` wrapper there now says `diagram`, change it to `data-visual="chart"`.

- [x] **Step 4: Insert rules 10–15 and the icon set**

Insert after rule 9, before "Two colours carry meaning…":
```markdown
10. **Columns go in a table (R10).** A record with more than one field — `row 1`, `09:00`,
    `10000` — is a row of a value table (template 11), never an SVG label joined with `·`.
    `verify_course.py --contract v11` fails a label that packs a row into dots. SVG stays for
    shapes that carry meaning: flows, overlaps, time scales, key matches.
11. **Make invisible values visible (R11).** A raw string sits in `<span class="nerdit-val">`,
    which marks where it starts and ends. Each space is `<span class="nerdit-ws">␣</span>`.
    NULL is `<span class="nerdit-null">NULL</span>`. Never use square brackets to show spaces in
    a figure (an SQL result may, because that is real output).
12. **Highlight the surprise (R12).** The cell that springs the trap gets `nerdit-cell-bad`; the
    safe result gets `nerdit-cell-good`. Each carries a 2–4 word `<span class="nerdit-vnote">`
    saying what happened. Colour one cell, not the whole row.
13. **Show each idea once (R13).** In one section, a text map (`nerdit-map`), a figure and its
    reading steps never restate the same facts. Steps add order or reasons, not the figure's
    labels again. When a figure covers it, drop the map.
14. **Every figure names its visual.** `data-visual` on each `nerdit-figure`: `diagram`,
    `value-table`, `decision-grid`, `time-window`, `unit-tiles`, `chart`, `course-map` or
    `illustration`. `CORE.md` §7 decides which; v11 fails a figure without it.
15. **Spotlight one record.** The record the lesson follows carries `nerdit-spot` (a table row,
    a cell or an SVG shape) in every figure where it appears.

**Icons in tables — closed list:** `✓` passes · `✗` fails · `–` not checked · `⚠` needs
attention · `🔑` primary key · `🔗` foreign key. A table that uses one carries a legend
(`nerdit-vlegend`) or says it in text. No other icons, the same rule as heading emoji.
```
Also change the intro sentence "Nine fixed shapes cover…" to "Fifteen fixed shapes cover…".

- [x] **Step 5: Insert templates 11–15**, before `## Choosing between them`:

````markdown
## 11 · Value table — values before and after a rule

For: TRIM, CAST, NULLIF, date parsing; any rule applied value by value. Variant A groups by
rule, variant B puts two rules side by side to expose a trap, and variant C ranks rows with a kept one.

```html
<div class="nerdit-figure" data-visual="value-table" style="max-width:440px">
  <table class="nerdit-vtable">
    <thead><tr><th>raw value <small>(␣ = space)</small></th><th></th><th>clean value</th></tr></thead>
    <tbody>
      <tr class="nerdit-vgroup"><td colspan="3">① <code>TRIM(customer)</code></td></tr>
      <tr><td><span class="nerdit-val"><span class="nerdit-ws">␣</span>Aarav<span class="nerdit-ws">␣</span></span></td><td class="nerdit-varrow">→</td><td><span class="nerdit-val">Aarav</span></td></tr>
      <tr class="nerdit-vgroup"><td colspan="3">② <code>NULLIF(TRIM(amount_text), '')</code></td></tr>
      <tr><td><span class="nerdit-val"><span class="nerdit-ws">␣</span></span></td><td class="nerdit-varrow">→</td><td><span class="nerdit-null">NULL</span><span class="nerdit-vnote">blank = missing</span></td></tr>
      <tr><td><span class="nerdit-val">0</span></td><td class="nerdit-varrow">→</td><td><span class="nerdit-val">0</span><span class="nerdit-vnote">zero is a real value</span></td></tr>
    </tbody>
  </table>
  <div class="nerdit-figure-caption">Each rule tidies text but keeps its meaning: a blank becomes NULL, and zero stays 0.</div>
</div>
```

```html
<div class="nerdit-figure" data-visual="value-table" style="max-width:440px">
  <table class="nerdit-vtable">
    <thead><tr><th>amount_text</th><th>① <code>CAST(… AS INTEGER)</code></th><th>② digit rule</th></tr></thead>
    <tbody>
      <tr><td><span class="nerdit-val">12500</span></td><td>12500</td><td>12500</td></tr>
      <tr><td><span class="nerdit-val">12x</span></td><td class="nerdit-cell-bad">12<span class="nerdit-vnote">invented, no error</span></td><td class="nerdit-cell-good"><span class="nerdit-null">NULL</span><span class="nerdit-vnote">caught</span></td></tr>
      <tr><td><span class="nerdit-val"><span class="nerdit-ws">␣</span></span></td><td class="nerdit-cell-bad">0<span class="nerdit-vnote">blank became 0</span></td><td class="nerdit-cell-good"><span class="nerdit-null">NULL</span><span class="nerdit-vnote">caught</span></td></tr>
    </tbody>
  </table>
  <div class="nerdit-figure-caption">CAST never complains: 12x becomes 12 and a blank becomes 0. The digit rule refuses both.</div>
</div>
```

```html
<div class="nerdit-figure" data-visual="value-table" style="max-width:440px">
  <p class="nerdit-vtitle">O1's three versions, newest first</p>
  <table class="nerdit-vtable">
    <thead><tr><th>rn</th><th>row_id</th><th>time</th><th>amount</th></tr></thead>
    <tbody>
      <tr class="nerdit-row-kept"><td>1 ✓</td><td>3</td><td>10:00</td><td>12500</td></tr>
      <tr class="nerdit-row-dropped"><td>2</td><td>2</td><td>10:00</td><td>12000</td></tr>
      <tr class="nerdit-row-dropped"><td>3</td><td>1</td><td>09:00</td><td>10000</td></tr>
    </tbody>
  </table>
  <p class="nerdit-vlegend">Rows 3 and 2 tie at 10:00, so the larger row_id goes first. ✓ = kept; grey = superseded.</p>
  <div class="nerdit-figure-caption">The newest version gets number 1, and only rn = 1 is kept.</div>
</div>
```

At most 4 columns and short cell text, so it fits a 280px phone column.

---

## 12 · Decision grid — rules checked per row, first failure wins

For: a CASE that assigns reasons, validation rules, eligibility checks.

```html
<div class="nerdit-figure" data-visual="decision-grid" style="max-width:440px">
  <table class="nerdit-vtable nerdit-grid">
    <thead><tr><th>order</th><th>①</th><th>②</th><th>③</th><th>④</th><th>outcome</th></tr></thead>
    <tbody>
      <tr><td><b>O1</b> <small>row 3</small></td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk ok">✓</td><td class="nerdit-cell-good">ACCEPT</td></tr>
      <tr><td><b>O3</b> <small>row 5</small></td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk first">✗</td><td class="nerdit-chk skip">–</td><td class="nerdit-chk skip">–</td><td class="nerdit-cell-bad">BAD_AMOUNT</td></tr>
      <tr><td><b>O4</b> <small>row 6</small></td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk first">✗</td><td class="nerdit-chk skip">–</td><td class="nerdit-cell-bad">BAD_DATE</td></tr>
      <tr><td><b>O5</b> <small>row 7</small></td><td class="nerdit-chk first">✗</td><td class="nerdit-chk skip">–</td><td class="nerdit-chk skip">–</td><td class="nerdit-chk skip">–</td><td class="nerdit-cell-bad">MISSING_AMOUNT</td></tr>
    </tbody>
  </table>
  <p class="nerdit-vlegend">① amount present · ② amount is digits · ③ date is real · ④ category is approved<br>✓ passes · ✗ first failed check · – not checked</p>
  <div class="nerdit-figure-caption">CASE checks in order and stops at the first ✗. O4 also has an unknown category, but its bad date is found first.</div>
</div>
```

Columns are numbered ①–④ in CASE order, and the legend names them.

---

## 13 · Unit tiles — parts that add up to a total

For: reconciliation, row counts per bin, where every unit lands in exactly one place.

```html
<div class="nerdit-figure" data-visual="unit-tiles" style="max-width:440px">
  <div class="nerdit-tiles">
    <div class="nerdit-tilegroup"><div><span class="nerdit-tile sup">1</span><span class="nerdit-tile sup">2</span></div><span>superseded <b>2</b></span></div>
    <div class="nerdit-tilegroup"><div><span class="nerdit-tile acc">3</span><span class="nerdit-tile acc">4</span></div><span>accepted <b>2</b></span></div>
    <div class="nerdit-tilegroup"><div><span class="nerdit-tile rej">5</span><span class="nerdit-tile rej">6</span><span class="nerdit-tile rej">7</span></div><span>rejected <b>3</b></span></div>
  </div>
  <p class="nerdit-vsum">2 + 2 + 3 = <b>7</b> staged rows</p>
  <div class="nerdit-figure-caption">Each staged row lands in exactly one bin, so the bins add up to the source count.</div>
</div>
```

One tile per real row, up to about 20. Above that, show counts in a value table instead.

---

## 14 · Time window — a range on a clock, drawn to scale

For: watermarks, batch bounds, late data, any `>` / `<=` window on time. ○ marks an excluded bound
and ● an included one. A second lane shows a second clock.

```html
<div class="nerdit-figure" data-visual="time-window" style="max-width:440px">
  <svg viewBox="0 0 360 176" role="img" aria-label="The batch reads changes after 10:00 up to and including 11:00: O3 and O4 load, O6 at 11:30 waits for the next batch, and O2, stamped 10:00 but arrived at 10:20, is never read.">
    <text class="nerdit-flow-text" x="8" y="18" fill="var(--tx-m)">source_updated_at</text>
    <rect x="40" y="36" width="200" height="20" fill="var(--green-bg)"/>
    <line x1="16" y1="46" x2="350" y2="46" stroke="var(--bd)" stroke-width="1.5"/>
    <circle cx="40" cy="46" r="6" fill="var(--white)" stroke="var(--nb)" stroke-width="2"/>
    <circle cx="240" cy="46" r="6" fill="var(--nb)"/>
    <circle cx="140" cy="46" r="4" fill="var(--green)"/>
    <circle cx="190" cy="46" r="4" fill="var(--green)"/>
    <circle cx="340" cy="46" r="4" fill="var(--tx-m)"/>
    <text class="nerdit-flow-text" x="140" y="30" text-anchor="middle" fill="var(--green)">O3</text>
    <text class="nerdit-flow-text" x="190" y="30" text-anchor="middle" fill="var(--green)">O4</text>
    <text class="nerdit-flow-text" x="340" y="30" text-anchor="end" fill="var(--tx-m)">O6</text>
    <text class="nerdit-flow-text" x="40" y="74" text-anchor="middle" fill="var(--tx)">10:00</text>
    <text class="nerdit-flow-text" x="140" y="74" text-anchor="middle" fill="var(--tx-m)">10:30</text>
    <text class="nerdit-flow-text" x="240" y="74" text-anchor="middle" fill="var(--tx)">11:00</text>
    <text class="nerdit-flow-text" x="340" y="74" text-anchor="end" fill="var(--tx-m)">11:30</text>
    <text class="nerdit-flow-text" x="8" y="98" fill="var(--nb)">① ○ 10:00 left out (&gt;)</text>
    <text class="nerdit-flow-text" x="200" y="98" fill="var(--nb)">② ● 11:00 kept (&lt;=)</text>
    <text class="nerdit-flow-text" x="8" y="128" fill="var(--tx-m)">arrived in staging</text>
    <line x1="16" y1="146" x2="350" y2="146" stroke="var(--bd)" stroke-width="1.5"/>
    <line x1="40" y1="136" x2="40" y2="156" stroke="var(--nb)" stroke-width="2"/>
    <circle cx="107" cy="146" r="5" fill="var(--amber)"/>
    <text class="nerdit-flow-text" x="48" y="170" fill="var(--nb)">batch 1 ran</text>
    <text class="nerdit-flow-text" x="117" y="140" fill="var(--amber)">③ O2 arrives 10:20</text>
  </svg>
  <div class="nerdit-figure-caption">A window keeps rows after the watermark up to the frozen upper bound. A row that arrives after its batch ran is never read.</div>
</div>
```

Scale: one hour = 200 units. Place every point by its real time; never space the ticks evenly
by hand.

---

## 15 · Course map — "you are here"

For: the strip under each lesson's overview showing the course's stages. It is drawn once per
course and each lesson fills its own stage. At most 5 stages per row, with names of 8
characters or fewer.

```html
<div class="nerdit-figure" data-visual="course-map" style="max-width:440px">
  <svg viewBox="0 0 360 78" role="img" aria-label="Course map: this lesson is the clean stage, third of five: source, staging, clean, load, mart.">
    <rect x="4" y="14" width="64" height="32" rx="6" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="36" y="35" text-anchor="middle" fill="var(--tx-m)">source</text>
    <rect x="76" y="14" width="64" height="32" rx="6" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="108" y="35" text-anchor="middle" fill="var(--tx-m)">staging</text>
    <rect x="148" y="14" width="64" height="32" rx="6" fill="var(--nb)" stroke="var(--nb)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="180" y="35" text-anchor="middle" fill="var(--white)">clean</text>
    <rect x="220" y="14" width="64" height="32" rx="6" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="252" y="35" text-anchor="middle" fill="var(--tx-m)">load</text>
    <rect x="292" y="14" width="64" height="32" rx="6" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="324" y="35" text-anchor="middle" fill="var(--tx-m)">mart</text>
    <text class="nerdit-flow-text" x="180" y="68" text-anchor="middle" fill="var(--nb)">▲ you are here</text>
  </svg>
  <div class="nerdit-figure-caption">You are here: cleaning staged rows, before they load into the warehouse.</div>
</div>
```

---
````

- [x] **Step 6: Replace the body of `## Choosing between them`** (the table and its fallback paragraph) with:
```markdown
`CORE.md` §7 (the Visual Map) decides which visual a place in the lesson gets; this file only
supplies the markup. Nothing in the map fits and the concept still seems to need a picture?
Write the caption first: the one sentence the figure must teach. If that sentence will not
come, there is no figure to draw. **Prose is the correct answer, and an empty figure slot is
better than a decorative one.**
```
- [x] **Step 7: Run all tests.** Expected: `178 passed`.
- [x] **Step 8: Commit** — `docs(figures): v11 rules, icon set and templates 11-15`. _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 12: Website dev fixture and visual check

**Files:**
- Create: `nerdit/future-vision/src/utils/__fixtures__/lesson-v11-visuals.html`
- Modify: `nerdit/future-vision/src/services/courseService.fixture.ts`

**Interfaces:**
- Consumes: figures.md templates 11–15 (Task 11) and the v11 styles (Task 10).

- [x] **Step 1: Generate the fixture from the templates.** This keeps it identical to what writers copy.

Run from the workspace root:
```bash
python -I - <<'PY'
import re
from pathlib import Path
fig = Path("nerdit-plugin-json-generator/skills/nerdit-chapter-generator/references/figures.md").read_text(encoding="utf-8")
blocks = {int(m.group(1)): re.findall(r"```html\n(.*?)```", m.group(0), re.S)
          for m in re.finditer(r"^## (\d+) · .*?(?=^## |\Z)", fig, re.S | re.M)}
names = {11: "Value tables", 12: "Decision grid", 13: "Unit tiles", 14: "Time window", 15: "Course map"}
secs = "".join(f'<section><h2>{n - 10} — {names[n]}</h2>' + "".join(blocks[n]) + "</section>\n" for n in names)
spot = ('<section><h2>6 — Spotlight and data note</h2>'
        '<p class="nerdit-data-note">Business name used with permission. All records, people and amounts are synthetic, made for teaching.</p>'
        '<div class="nerdit-figure" data-visual="value-table" style="max-width:440px"><table class="nerdit-vtable">'
        '<thead><tr><th>order</th><th>amount</th></tr></thead><tbody><tr><td>O1</td><td>12500</td></tr>'
        '<tr class="nerdit-spot"><td>O3</td><td>12x</td></tr></tbody></table>'
        '<div class="nerdit-figure-caption">O3 is the record this lesson follows.</div></div></section>\n')
html = ('<div class="nerdit-wrapper nerdit-simple" style="counter-reset:practical-counter challenge-counter;">\n'
        '<h1>Teaching visuals v11 (fixture)</h1>\n' + secs + spot + '</div>\n')
Path("nerdit/future-vision/src/utils/__fixtures__/lesson-v11-visuals.html").write_text(html, encoding="utf-8")
print(len(html), "bytes")
PY
```
- [x] **Step 2: Wire it into the fixture course.** In `courseService.fixture.ts`:
  - Below `import sqlLesson …` add:
```ts
import visualsLesson from '@/utils/__fixtures__/lesson-v11-visuals.html?raw';
```
  - In `FIXTURE_SQL.lessons`, replace the array with:
```ts
  lessons: [
    { ...lessons[0], id: 'fixture-sql-1', title: 'Date dimensions and fixtures', content: sqlLesson },
    // v11 teaching visuals (figures.md templates 11-15), so the new styles can be seen locally.
    { ...lessons[0], id: 'fixture-sql-2', title: 'Teaching visuals v11', content: visualsLesson },
  ],
```
- [x] **Step 3: Run the website tests**

Run: `cd nerdit/future-vision && npx vitest run`
Expected: the same pass count as before this task, with 0 failures.

- [x] **Step 4: Visual check in the browser** _(Dark theme unavailable; see verification record.)_

Run in the background:
```bash
cd nerdit/future-vision && VITE_FIXTURE_COURSE=1 npm run dev -- --port 5180
```
With Playwright, open the `fixture-sql` course and its lesson "Teaching visuals v11" in the classroom. At widths **1280** and **390**:
1. Take a screenshot and look at it.
2. Run `document.documentElement.scrollWidth <= window.innerWidth` and expect `true`.
3. Run `getComputedStyle(document.querySelector('.nerdit-cell-bad')).backgroundColor` and expect a value that is not transparent (the styles are loaded).

Switch the site to dark theme with its theme toggle and repeat step 1.

Expected:
- tables readable, with no sideways scroll at 390px
- ✓ / ✗ cells coloured
- the time-window labels not clipped
- in dark theme, text readable on every background

Stop the dev server afterwards.

- [x] **Step 5: Commit** (`nerdit` repo; stage only the two files) — `test(fixture): v11 teaching-visuals lesson`. _(No per-task commit; landed in nerdit `70de1ef`, 2026-10-15.)_

---

### Task 13: CORE.md and runners/sql.md

**Files:** Modify `G/references/CORE.md` and `G/references/runners/sql.md`; create `GS/test_reference_sql_width.py`.

- [x] **Step 1: Write the failing doc test** — `GS/test_reference_sql_width.py`:
```python
"""Writers copy the references' SQL, so the references must obey the 60-character rule."""
import html
import re
from pathlib import Path

G = Path(__file__).resolve().parent.parent
SOURCES = ["references/CORE.md", "references/figures.md", "references/runners/sql.md"]


def sql_lines(md: str):
    for block in re.findall(r"```html\n(.*?)```", md, re.S):
        for m in re.finditer(r'<pre data-lang="sql"><code>(.*?)</code></pre>', block, re.S):
            yield from html.unescape(m.group(1)).splitlines()
        for m in re.finditer(r'<div class="nerdit-tryit" data-seed="[^"]*">.*?<textarea[^>]*>(.*?)</textarea>', block, re.S):
            yield from html.unescape(m.group(1)).splitlines()


def test_reference_sql_examples_obey_the_60_character_rule():
    long = [(rel, ln) for rel in SOURCES for ln in sql_lines((G / rel).read_text(encoding="utf-8"))
            if len(ln.rstrip()) > 60]
    assert not long, long[:5]


def test_sql_md_teaches_the_layout_rule():
    text = (G / "references/runners/sql.md").read_text(encoding="utf-8")
    assert "## Layout" in text and "60 characters" in text
```
- [x] **Step 2: Run.** Expect the layout test to fail. The width test may also list long lines in CORE.md; note them.

- [x] **Step 3: Append to `runners/sql.md`**
````markdown

## Layout

The input half of a run line wraps instead of scrolling, so a long line breaks in the middle of
a statement. Lay every query out so it never needs to:

- No line longer than **60 characters**.
- `CREATE TABLE`: one column per line. A `SELECT` list of more than three expressions: one per line.
- Two-space indent per level. No alignment indent deeper than 12 spaces; break the line instead.
- `CASE`, each `WHEN`, `ELSE` and `END` on their own lines, indented under `CASE`.
- A space after every comma and around `=`, `<>`, `<=`, `>=`, `||`.

`verify_course.py --contract v11` fails a run line or SQL Try It with a longer line.

```html
<pre data-lang="sql"><code>CREATE TABLE classified (
  row_id      INTEGER PRIMARY KEY,
  amount_text TEXT,
  reason      TEXT
);

SELECT
  row_id,
  CASE
    WHEN TRIM(amount_text) = '' THEN 'MISSING_AMOUNT'
    WHEN amount_text GLOB '*[^0-9]*' THEN 'BAD_AMOUNT'
    ELSE 'ACCEPT'
  END AS reason
FROM staged
ORDER BY row_id;</code></pre>
```
````
- [x] **Step 4: Edit `CORE.md`**

(a) In §4, in the bullet "**Input code is plain text with a `data-lang`; the website colours it.**", replace the sentences from "Write SQL one clause per line" to the end of that bullet with:
```markdown
Lay SQL out by `runners/sql.md` §Layout: no line over 60 characters, one column per line,
`CASE` blocks indented. The input half wraps, so a longer line breaks mid-statement.
```

(b) Replace the bullet "**2–3 run lines per concept.** …" with:
```markdown
- **Run lines follow the lesson's `focus`.** `concept` (the input's optional `focus` field):
  one run line per concept, and the Try It may be a prediction or a decision ("Which grain is
  this table?") instead of running code. `hands-on` (the default): 2–3 run lines per concept;
  the second is a small variation of the first, changing one thing. Either way a shown block is
  at most 15 lines; move repeated setup into the seed or a view. Shown code per lesson: at most
  40 lines for `concept`, 100 for `hands-on` (`verify_course.py` v11 warns).
```

(c) At the end of §4c, add:
```markdown
### The why is not the next sentence

The run-line heading's `.why` says why the example matters. The paragraph under it says, in one
sentence, what the code does. Never repeat the why as that paragraph; v11 fails it.
```

(d) In §7:
- Replace the paragraph "**Every lesson ships at least one figure.** …" with:
```markdown
**Every concept section has one main visual** (a figure, a value table or a chart). This is a
floor, not a quota. The caption-first test below still decides, and a section that honestly
cannot earn one may ship none (`verify_course.py` v11 warns, it does not fail).
```
- Replace the paragraph "Read this table top to bottom…" and the decision table with:
```markdown
### The Visual Map — where each visual goes

This is the only table that chooses visuals. `figures.md` holds the markup, and the illustrator
reads its image slots from here.

| Where in the lesson | The content is… | Visual (`data-visual`) | Made by |
| --- | --- | --- | --- |
| Overview / hook | a real-world scene | `illustration` | illustrator; the user generates it |
| Under the overview | the course's stages | `course-map` (figures.md §15) | writer |
| Concept: meaning | an analogy | `illustration` (optional) | illustrator |
| Concept: meaning | a structure or relationship | `diagram` (figures.md §1–8, §10) | writer |
| Concept: case | records with fields, values changing | `value-table` (§11) or `decision-grid` (§12) | writer |
| Concept: case | events in time, a window | `time-window` (§14) | writer |
| Concept: case | parts that add up to a total | `unit-tiles` (§13) | writer |
| Concept: case | real measured numbers to compare | `chart` (§9, Chart.js) | writer |
| Worked example | code → result | run line with a result table | writer |
| Practice | — | Try It (predict, run or decide) | writer |
| Closing | summary | cheat-sheet table | writer |

Nothing matches after honestly trying: **no visual**. Prose is the answer.

**Balance:**
- One main visual per concept section.
- No two visuals restating the same facts (figures.md R13).
- 0–3 illustrations per lesson, only where the text has a scene or analogy.
- Charts only for real measured numbers.
- Not the same `data-visual` in every section.
- Icons in tables come from the closed list in figures.md, always with a legend.
```

(e) In §10, append:
```markdown
- Sound like a person: no phrase from `references/voice.md` (`check_prose.py` fails it);
  contractions are welcome; open sections in different ways.
- **One real mistake per lesson:** a wrong result an analyst would really get, its output, why
  it happened, the fix (`nerdit-compare`). The mistake belongs to the data work, never to a
  business.
- **Spotlight one record** with `nerdit-spot` wherever it appears (figures.md rule 15).
- **Check it by hand:** under one key result, one line of arithmetic the learner can verify
  ("12,000 + 500 = 12,500 ✓").
```

(f) Fix any CORE.md SQL lines the width test listed. Re-lay them out with whitespace only.

- [x] **Step 5: Run all tests.** Expected: `180 passed`.
- [x] **Step 6: Commit** — `docs(core): Visual Map, SQL layout, focus and voice rules`. _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 14: Writer, QA validator, orchestrator, version

**Files:** Modify `agents/nerdit-lesson-writer.md`, `agents/nerdit-qa-validator.md`, `G/SKILL.md`, `.claude-plugin/plugin.json`; create `GS/test_docs_refs.py`.

- [x] **Step 1: Write the failing test** — `GS/test_docs_refs.py`:
```python
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def test_skill_md_names_only_scripts_that_exist():
    skill = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
    names = set(re.findall(r"(?<!illustrator/)scripts/([a-z_]+\.py)", skill))
    assert {"gate_lesson.py", "build_preview.py", "check_prose.py", "check_refresh.py"} <= names
    assert [n for n in names if not (HERE / n).exists()] == []


def test_writer_knows_refresh_mode_and_voice():
    writer = (ROOT / "agents" / "nerdit-lesson-writer.md").read_text(encoding="utf-8")
    assert "## Refresh mode" in writer and "references/voice.md" in writer and "data-visual" in writer


def test_plugin_version_is_3_3_0():
    assert json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"] == "3.3.0"
```
- [x] **Step 2: Run; expect 3 failures.**

- [x] **Step 3: Edit `agents/nerdit-lesson-writer.md`**

(a) In "## Step 0 — Read the rulebook first", add `${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/references/voice.md` to the files read, labelled "the banned-phrase list `check_prose.py` enforces".

(b) Append to "## The rules that matter most":
```markdown
- **Pick each visual from the Visual Map** (CORE.md §7). Every `nerdit-figure` carries
  `data-visual`. Records with fields go in a value table (figures.md §11), never in an SVG label
  joined with `·`. Show each idea once (figures.md R13).
- **SQL layout** (runners/sql.md §Layout): no line over 60 characters, one column per line in
  `CREATE TABLE`, `CASE`/`WHEN`/`END` on their own lines, a space after every comma.
- **Focus** (CORE.md §4): `FOCUS = concept` means one run line per concept and a predict or decide
  Try It; `hands-on` means 2–3 run lines. A shown block is at most 15 lines; move setup into the seed.
- **Sound like a person** (references/voice.md): no banned phrase, contractions welcome, sections
  that open in different ways.
- **One real mistake per lesson** (its wrong output, why, the fix), **spotlight one record**
  with `nerdit-spot`, and **check one key result by hand** (CORE.md §10).
```

(c) After "## Reform mode …" add:
```markdown
## Refresh mode (optional — improving a finished lesson)

If the orchestrator passes `SOURCE_PATH` **and** `REFRESH` (a list from `figures`, `sql-layout`,
`trim`), you are not rewriting the lesson. Copy `SOURCE_PATH` and change only what `REFRESH` names:

- `figures` — redraw figures that break figures.md R10–R13 or have a better template, with their
  captions and reading steps. Remove a text map (`nerdit-map`) a figure now covers. Add
  `data-visual` to every figure.
- `sql-layout` — re-lay out SQL in run lines and Try Its to runners/sql.md §Layout. Whitespace
  only: no token may change.
- `trim` — shorten shown code to the CORE.md §4 limits by moving repeated setup into the seed or a
  view. Every shown output must still be exactly what SQLite returns. A run-line heading and its
  one-sentence lead may change to match.

Everything else stays exactly as it is: headings, prose, Try It prompts, the cheat sheet, the
quiz file and the concept manifest (except its `visuals` list). `check_refresh.py` compares your
files with the originals and rejects any other change. Write the quiz and concept files back
unchanged.
```

(d) In "## Concept manifest", add:
```markdown
- `visuals` (optional, written whenever you write the lesson): one entry per concept section,
  `{"section": 2, "visual": "value-table", "illustration": "numbering drafts of an essay, newest first"}`.
  `visual` is the section's main `data-visual` or `none`. `illustration` names the scene or analogy
  the text already uses, or is `null`. The illustrator plans image slots from it.
```

- [x] **Step 4: Edit `agents/nerdit-qa-validator.md`.** Append to "## Your checklist":
```markdown
- **One representation per idea** (figures.md R13): no section shows the same facts as a text map,
  a figure and reading steps
- **Charts only for real measured numbers**; every table icon is explained by a legend
- **One real mistake per lesson**, belonging to the data work (a report bug, a typo, a pipeline
  error); never fraud, losses or complaints about a business
- **Spotlight record**: the same record, marked `nerdit-spot`, wherever it appears
- **Check it by hand**: the arithmetic line is true
```

- [x] **Step 5: Edit `G/SKILL.md`**

(a) Step 1's lesson-field list: add `focus` (optional: `concept` | `hands-on`, default `hands-on`; CORE.md §4).

(b) Step 2b's list of what the writer receives: add `FOCUS` (the lesson's `focus`, default `hands-on`).

(c) Step 4c: change `--contract v10` to `--contract v11`, then add after the SQL output check:
```markdown
Then the voice check, which fails on any phrase in `references/voice.md`:

    python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/check_prose.py" --course <workdir>/course-<chaptername>_output.json

`WARN` lines from both scripts are advice: fix them when cheap, never loop on them.
```

(d) After the reform section, add:
```markdown
## Refreshing a finished course (optional — refresh mode)

To improve finished lessons without rewriting them (new figures, SQL layout, less code):

1. Copy each lesson's three files into `<workdir>/_before/`.
2. Run one `nerdit-lesson-writer` at a time with `SOURCE_PATH = <workdir>/_before/<id>.html`,
   `REFRESH = figures[,sql-layout][,trim]` and the usual `HTML_PATH`, `QUIZ_PATH` and `CONCEPTS_PATH`.
3. Gate the lesson:

       python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/gate_lesson.py" --input <input.json> --dir <workdir> --id <id> --before-dir <workdir>/_before --modes figures,sql-layout

   It runs verify (v11), the SQL output check, the SVG checks, `check_prose.py` and
   `scripts/check_refresh.py`. At most 2 attempts per lesson, then stop and report.
4. Assemble as in Step 4.

## Previewing a course

    python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/build_preview.py" --course <course.json> --out <preview.html>

One page with every lesson, the site's styles and the site's code colours. Open it in a browser.
```

(e) In the reference-files table, add a row: `references/voice.md` — banned phrases and voice
rules (`check_prose.py`).

- [x] **Step 6: Bump the version.** In `.claude-plugin/plugin.json`, change `"version": "3.2.0"` to `"version": "3.3.0"`.
- [x] **Step 7: Run all tests.** Expected: `183 passed`.
- [x] **Step 8: Commit** — `docs(generator): writer refresh mode, v11 rules, QA checks; v3.3.0`. _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 15: Illustrator — `data-visual` and image hints

**Files:** Modify `IS/insert_images.py`, `IS/extract_outline.py`, `IS/test_insert_images.py`, `IS/test_insert_v2.py`, `IS/test_extract_outline.py`, `skills/nerdit-lesson-illustrator/references/style.md` and `skills/nerdit-lesson-illustrator/SKILL.md`.

**Interfaces:**
- Produces:
  - Inserted blocks carry `data-visual` after `data-nerdit-img` (illustration, or the plan item's `visual`, defaulting to `diagram`).
  - `load_hints(workdir: str | None) -> dict[str, dict[int, dict]]`
  - `outline(course, hints=None)` adds `"hint"` per section
  - CLI `--hints <workdir>`

- [x] **Step 1: Update the expected strings in the tests**
  - `test_insert_images.py`: in the expected block (line ~19) and both asserts (lines ~29, ~31), insert ` data-visual="illustration"` right after each `data-nerdit-img="…"` value, before `>`.
  - `test_insert_v2.py` (line ~29): change `data-nerdit-img="load-basics-01-fig1" style=` to `data-nerdit-img="load-basics-01-fig1" data-visual="diagram" style=`.
  - Append to `test_extract_outline.py`:
```python
def test_hints_from_concept_manifests_reach_the_outline(tmp_path):
    c = course()
    lid = c["lessons"][0]["id"]
    (tmp_path / f"{lid}.concepts.json").write_text(json.dumps({
        "teaches": [], "uses": [],
        "visuals": [{"section": 1, "visual": "value-table", "illustration": "drafts of an essay"}]}),
        encoding="utf-8")
    from extract_outline import load_hints
    lessons = outline(c, load_hints(str(tmp_path)))
    assert lessons[0]["sections"][0]["hint"]["illustration"] == "drafts of an essay"
    assert "image: drafts of an essay" in render(lessons)
```
- [x] **Step 2: Run the illustrator suite; expect the updated and new tests to fail.**

- [x] **Step 3: Implement**

`insert_images.py`:
- In `block()`: `data-nerdit-img="{slot["id"]}">` becomes `data-nerdit-img="{slot["id"]}" data-visual="illustration">`.
- In `blocks_v2()`, before `out = [...]`, add:
```python
    visual = slot.get("visual") or ("diagram" if slot["kind"] == "diagram" else "illustration")
```
  and change the figure line to:
  `f'\n<div class="nerdit-figure" data-nerdit-img="{vid}" data-visual="{visual}"{width}>\n  {figure}\n'`.

`extract_outline.py`:
- Add `from pathlib import Path`.
- Add:
```python
def load_hints(workdir: str | None) -> dict[str, dict[int, dict]]:
    """`visuals` lists from <workdir>/<id>.concepts.json, by lesson id and section number."""
    if not workdir:
        return {}
    hints: dict[str, dict[int, dict]] = {}
    for p in Path(workdir).glob("*.concepts.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        hints[p.name[: -len(".concepts.json")]] = {
            int(v["section"]): v for v in data.get("visuals", []) if "section" in v}
    return hints
```
- Change `def outline(course: dict)` to `def outline(course: dict, hints: dict | None = None)`.
- In the section dict add `"hint": (hints or {}).get(lesson["id"], {}).get(sec.number),`.
- In `render`, after the anchor lines for a section, add:
```python
            h = s.get("hint")
            if h:
                lines.append(f"     hint: {h.get('visual')}"
                             + (f" · image: {h['illustration']}" if h.get("illustration") else ""))
```
- In `main`: add `ap.add_argument("--hints", help="<workdir> holding <id>.concepts.json with visuals")` and pass `load_hints(args.hints)` to `outline(...)`.

`references/style.md`: replace the "## Choosing a visual" table with:
```markdown
## Choosing a visual

`nerdit-chapter-generator/references/CORE.md` §7 (the Visual Map) decides which visual each place
in a lesson gets. Illustrations are only for a real scene or an analogy the text already uses;
everything with exact names, values or times is a diagram or table drawn from the lesson's data.
When the course workdir has concept manifests, `extract_outline.py --hints <workdir>` shows each
section's `visual` and suggested `illustration`. Plan from those.
```
Keep the bullets below the old table ("One objective per visual…").

`SKILL.md` (illustrator), Run 1 step 2: append "Add `--hints <workdir>` when the chapter generator's workdir is available, to see each section's planned visual and image idea."

- [x] **Step 4: Run both suites.** Expected: illustrator `90 passed`, generator `183 passed`.
- [x] **Step 5: Commit** — `feat(illustrator): data-visual on inserted visuals and image hints from manifests`. _(No per-task commit; landed in plugin `5dadb55`, 2026-10-15.)_

---

### Task 16: Final verification

**Files:** none.

- [x] **Step 1: Both suites**

Run:
```bash
cd skills/nerdit-chapter-generator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q | tail -1
cd ../../nerdit-lesson-illustrator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q | tail -1
```
Expected: `183 passed`, then `90 passed`.

- [x] **Step 2: CSS copies are identical.** Run the `check_css_bundle.py` command from Task 10 Step 4. Expected: `exit 0`.

- [x] **Step 3: v10 is unchanged.** Run `verify_course.py --contract v10` on the existing course file and compare with the known result:
```bash
python skills/nerdit-chapter-generator/scripts/verify_course.py --contract v10 \
  --input ../nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/course-data-modelling-etl-data-warehousing-for-analysts_input.json \
  --output ../nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/course-data-modelling-etl-data-warehousing-for-analysts_output.v2-create.json | head -8
```
Expected: the same 4 failures as before this plan (one 640-wide figure in each of lessons 13–16), and nothing new.

- [x] **Step 4: See what v11 would say (read-only).** Run the same command with `--contract v11` and `| tail -20`. This only reports; it fixes nothing. Expected: new failures and warnings in the course. That is Part 3's work list.

- [x] **Step 5: Course files untouched.** Rerun the `find … -newer …` command from Task 0. Expected: the same list as `$TMP/dm-before.txt`.

- [x] **Step 6: Report** the test counts, the v11 findings summary from Step 4, and anything skipped.
