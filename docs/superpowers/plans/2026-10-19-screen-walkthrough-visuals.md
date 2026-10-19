# Screen Walkthrough Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The lesson writer describes each Excel click-path once as a screen spec; the plugin draws complex ones as SVG (type A) and turns simple ones into checked AI-image briefs (type B), both from the lesson's own data.

**Architecture:** A stdlib module `screens.py` parses specs, reads the lesson's demo grid and applies the complex/simple rule. `excel_eval.py` computes formula results by running the plugin's own `nerdit-excel-engine.js` in Node. `render_screens.py` writes A figures into lesson HTML; `check_screens.py` gates them; `screen_briefs.py` turns B specs into illustrator v2 plan items of a new kind, `screen`, which the illustrator prompts, converts, checks and inserts like an illustration.

**Tech Stack:** Python 3.14 stdlib + pytest; Node 24 (runs `references/nerdit-excel-engine.js`); illustrator scripts (Pillow already present).

**Spec:** `docs/superpowers/specs/2026-10-19-screen-walkthrough-visuals-design.md`

## Global Constraints

- `G` = `skills/nerdit-chapter-generator`, `GS` = `G/scripts`, `I` = `skills/nerdit-lesson-illustrator`, `IS` = `I/scripts`. Paths are relative to the plugin repo root.
- Tests: from `GS` and from `IS`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`. Baseline: generator **361 passed**, illustrator **90 passed**.
- Spec block: `<script type="application/json" class="nerdit-screen" data-grid="<grid id>">{...}</script>`; the grid is the lesson's `<script type="application/json" id="<grid id>">{"headers": [...], "rows": [...]}</script>` (`runners/excel.md`). Row 1 holds headers; data row i is sheet row i + 2.
- Spec keys: `id` (unique per lesson), `app` (`"excel"` only), `goal`, `view` `{"columns": [letters], "rows": [first, last], "active": "<cell>"}`, `steps`, `dialog` (`null` or `{"title", "fields": [{"label", "value"}]}`), `image` (`"auto"`, `"A"`, `"B"`), `why` (required when `image` is not `"auto"`). B also needs `alt` (≤150 chars), `takeaway`, `misconception`, `check` `{"question","answer","reasoning"}`.
- Step kinds: `select {target}`, `click {path: [str, ...]}`, `type {target, formula}`, `set {label, value}`, `key {keys}`, `result {target}` (target must be filled by an earlier `type`).
- Complex/simple rule (`screen_kind`): **A** when `len(steps) > 3`, or `dialog` has ≥ 2 fields, or any `result` step; otherwise **B**. An override (`"A"`/`"B"` + `why`) wins.
- Phone limits for A: view at most **4** columns and **7** rows (header row counts); SVG viewBox width ≤ **400**; a cell value longer than **14** characters fails validation ("narrow the view or shorten the value").
- Engine: `window.NerditExcel.makeGrid(headers, rows)`, `window.NerditExcel.evaluate(formula, grid)` → `{"ok": true, "value": v}`; an Excel error is `value == {"code": "#NAME?"}`; display with `window.NerditExcel.formatValue(v)`. Node shim: `globalThis.window = globalThis; globalThis.document = {readyState: "loading", addEventListener(){}}`.
- A figure markup (exact): `<div class="nerdit-figure" data-visual="screen" data-screen="<id>" style="max-width:440px"><svg …></svg><div class="nerdit-figure-caption"><goal></div></div><ol class="nerdit-visual-read" data-screen="<id>"><li>① …</li>…</ol>`, inserted straight after its spec `<script>`.
- Reading-step wording (exact): select `Click cell {target}.`; click `Click {p1}, then {p2}.` (one item: `Click {p1}.`, more: joined with `, then `); type `Type {formula} in {target}.`; set `Set {label} to {value}.`; key `Press {keys}.`; result `{target} shows {formatted value}.`
- SVG: colour tokens only (`var(--…)`, no hex), text as `<text>`, `role="img"`, `aria-label` = goal + " " + steps joined by spaces, markers ①–⑤ drawn on the parts their steps name. It must pass the illustrator's `svgcheck.check_svg`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; stage only the files a task names. No publishing or deploys in this plan.

## Review Focus

1. A number cell such as 45000 must look the same in the drawn screen as in the Try It. The renderer uses the engine's `formatValue`, never Python `str()` (Task 3 test `test_numbers_use_engine_format`).
2. A typed formula usually sits outside the data columns (data A–E, formula in H). The view may list non-adjacent columns; the renderer draws a narrow `…` gap column between them, and blank cells stay blank (Task 3 test `test_gap_column_between_non_adjacent_columns`).
3. Formulas and values containing `"`, `&`, `<` or `'` must be XML-escaped in the SVG and still evaluate (Task 3 test `test_special_characters_are_escaped`).
4. Two specs in one lesson: re-rendering replaces only each spec's own figure, by `data-screen` id; duplicate ids fail validation (Task 1 test `test_duplicate_ids_fail`, Task 3 test `test_rerender_replaces_only_its_own_block`).
5. A lesson edited after rendering (grid value changed) must fail the gate until re-rendered, instead of shipping a stale screen (Task 4 test `test_stale_figure_fails`).

---

### Task 0: Baseline

- [ ] **Step 1:** Run both suites; record `361 passed` and `90 passed`. Run `node --version`; expect `v24`.
- [ ] **Step 2:** `git status` is clean on `redesign-v2`.

### Task 1: Spec parsing, grid reading and the A/B rule

**Files:**
- Create: `GS/screens.py`, `GS/test_screens.py`

**Interfaces:**
- Produces:
  - `read_specs(html: str) -> list[dict]` — each dict is the parsed JSON plus `"_grid": <data-grid attr>` and `"_offset": <end offset of the </script>>`, in page order.
  - `read_grid(html: str, grid_id: str) -> tuple[list[str], list[list]] | None`.
  - `screen_kind(spec: dict) -> str` — `"A"` or `"B"`.
  - `validate_spec(spec: dict, grid: tuple | None, lesson_text: str = "") -> list[str]` — problem strings, empty when valid.
  - `validate_lesson(html: str) -> list[str]` — validates every spec plus duplicate ids.
  - `col_index(letter: str) -> int` (A → 0) and `cell_value(grid, ref: str)` (header row, data rows, or `None` outside the grid).

- [ ] **Step 1: Write the failing tests** in `GS/test_screens.py`, using one fixture lesson string with grid `xl-staff` (headers `ID, Name, Department, City, Salary`; rows 101 Aarav Sales Mumbai 45000 … 106 Isha Marketing Chennai 49000, as in the live Excel lesson 04):
  - `test_xlookup_with_result_is_A` — select H3, type the XLOOKUP, result H3 → `"A"`.
  - `test_two_clicks_is_B` — `click ["Data", "Remove Duplicates"]`, `click ["OK"]` → `"B"`.
  - `test_four_steps_is_A`, `test_dialog_with_two_fields_is_A`.
  - `test_override_needs_why` — `image: "B"` with no `why` → a problem containing `"why"`; with `why` → `screen_kind` returns `"B"` even with a result step.
  - `test_view_limits` — 5 columns → problem containing `"4 columns"`; rows `[1, 9]` → problem containing `"7 rows"`.
  - `test_long_value_fails` — a view cell whose value is 15+ characters → problem containing `"14"`.
  - `test_unknown_grid_and_step_kind_fail`, `test_result_needs_earlier_type`, `test_set_label_must_be_a_dialog_field`.
  - `test_b_needs_teaching_text` — a B spec without `check` → problem naming `check`.
  - `test_click_labels_must_be_known_or_in_lesson` — a `click` path item or dialog label passes when it is in `EXCEL_TABS` (`Home, Insert, Draw, Page Layout, Formulas, Data, Review, View, Help`, a module constant) or appears in the lesson's visible text; `"Magic Button"` fails. `validate_spec` gains a `lesson_text: str = ""` parameter for this.
  - `test_duplicate_ids_fail` (Review Focus 4).
  - `test_cell_value` — `B7` → `"Isha"`, `A1` → `"ID"`, `H3` → `None`.
- [ ] **Step 2:** Run `python -m pytest -q test_screens.py`; expect `ModuleNotFoundError: screens`.
- [ ] **Step 3:** Implement `GS/screens.py` with the interfaces above and the Global Constraints' rule and limits. Parse with `re` + `json` (stdlib); report bad JSON as a problem, never raise.
- [ ] **Step 4:** Run the file, then the whole generator suite; expect all pass.
- [ ] **Step 5:** Commit — `feat(screens): screen spec parsing and the complex/simple rule`.

### Task 2: Excel engine bridge

**Files:**
- Create: `GS/excel_eval.py`, `GS/test_excel_eval.py`

**Interfaces:**
- Consumes: `references/nerdit-excel-engine.js`.
- Produces: `evaluate_many(headers: list, rows: list, formulas: list[str]) -> list[dict]` — one Node process per call; each item is `{"value": <python value>, "text": <formatValue string>}` or `{"error": "#NAME?"}`; order matches `formulas`. Raises `RuntimeError("Node.js is required for Excel screens: install Node 18+")` when `node` is not on PATH.

- [ ] **Step 1: Failing tests:** `test_xlookup_returns_chennai` (grid from Task 1 → `text == "Chennai"`); `test_unknown_function_is_an_error` (`=FOO(1)` → `{"error": "#NAME?"}`); `test_batch_keeps_order` (`=SUM(E2:E3)`, `=XLOOKUP(...)` → two results in order); `test_missing_node_message` (monkeypatch `shutil.which` → `None`; `RuntimeError` mentioning `Node.js`).
- [ ] **Step 2:** Run; expect `ModuleNotFoundError`.
- [ ] **Step 3:** Implement: write a small JS program to stdin of `node -` that applies the shim, `require`s the engine by absolute path, reads `{headers, rows, formulas}` JSON from an env var or argv file, and prints one JSON array. Use `subprocess.run(..., timeout=30, check=False)`; a non-zero exit raises `RuntimeError` with stderr's last line.
- [ ] **Step 4:** Run tests; expect pass.
- [ ] **Step 5:** Commit — `feat(screens): evaluate formulas with the plugin's Excel engine`.

### Task 3: Type A renderer

**Files:**
- Create: `GS/render_screens.py`, `GS/test_render_screens.py`

**Interfaces:**
- Consumes: Task 1 (`read_specs`, `read_grid`, `screen_kind`, `validate_spec`, `cell_value`), Task 2 (`evaluate_many`), `IS/svgcheck.py` (`check_svg(svg, labels, markers) -> list[str]`, imported via `sys.path` as `gate_lesson.py` does).
- Produces:
  - `reading_steps(spec: dict, results: dict[str, str]) -> list[str]` — the exact wording in Global Constraints; `results` maps a target cell to its formatted value.
  - `render_svg(spec: dict, grid: tuple, results: dict[str, str]) -> str` — deterministic.
  - `figure_block(spec: dict, svg: str, steps: list[str]) -> str` — the exact markup in Global Constraints.
  - `render_lesson(html: str) -> tuple[str, list[str]]` — returns new HTML and problems; A specs get a fresh block (replacing any block with the same `data-screen`), B specs get none (an existing one is removed).
  - CLI: `python render_screens.py --dir <lesson dir> [--id <lesson id>]` rewrites `<id>.html` files in place; exit 1 and no write when any lesson has problems.

- [ ] **Step 1: Failing tests:**
  - `test_viewbox_fits_a_phone` (width ≤ 400), `test_tokens_only` (no `#[0-9a-fA-F]{3,8}`), `test_passes_svgcheck`.
  - `test_shows_only_the_view_window` (Aarav is visible when rows 1–7 are in view; a value from row 8 is absent).
  - `test_result_cell_shows_engine_value` ("Chennai" in H3's `<text>`), `test_numbers_use_engine_format` (Review Focus 1: the text equals `evaluate_many`'s `text` for `=E2`).
  - `test_gap_column_between_non_adjacent_columns` (Review Focus 2: columns `["B", "D", "H"]` → a `…` header between D and H).
  - `test_special_characters_are_escaped` (Review Focus 3: a formula with `"` and `&` → valid XML via `xml.dom.minidom.parseString` on the SVG).
  - `test_markers_match_steps` (3 steps → ①②③ in the SVG and three `<li>` items), `test_reading_step_wording` (exact strings for each kind).
  - `test_render_is_idempotent` and `test_rerender_replaces_only_its_own_block` (Review Focus 4).
  - `test_b_spec_gets_no_figure`.
- [ ] **Step 2:** Run; expect `ModuleNotFoundError`.
- [ ] **Step 3:** Implement. Layout, top to bottom, all inside one SVG of width 400: title line (the goal), a ribbon strip only when a `click` step exists (tabs from the path's first item with that tab underlined; the button from the path's second item, highlighted), the formula bar (`fx` and the typed formula, or the active cell's value), the grid window (header row of column letters, row numbers, cells; the active cell outlined), and the dialog panel when `dialog` is set. Each marker sits next to the part its step names (the cell, the ribbon button, the formula bar, the dialog field). Column widths come from the longest shown value at a fixed character width; values are truncated never (Task 1 already fails long values).
- [ ] **Step 4:** Run tests; then the whole generator suite.
- [ ] **Step 5:** Commit — `feat(screens): draw complex walkthroughs as phone-sized SVG`.

### Task 4: Gate check and visual type

**Files:**
- Create: `GS/check_screens.py`, `GS/test_check_screens.py`
- Modify: `GS/gate_lesson.py` (run the check; failures prefixed `screen: `), `GS/test_gate_lesson.py`, `GS/verify_course.py` (`VISUALS` gains `"screen"`), `GS/test_verify_v11.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `check_lesson(html: str) -> tuple[list[str], list[str]]` — fails: every `validate_lesson` problem; any formula error (`"H3: =FOO(1) gives #NAME?"`); an A spec with no figure (`"<id>: no drawn screen; run render_screens.py"`); an A figure that differs from a fresh render (`"<id>: drawn screen is out of date; run render_screens.py"`); a B spec with a drawn figure. Warns: every override, as `"<id>: image forced to A|B: <why>"` (for QA). Lessons with no specs return `([], [])`.

- [ ] **Step 1: Failing tests:** `test_clean_rendered_lesson_passes`; `test_missing_figure_fails`; `test_stale_figure_fails` (Review Focus 5: render, then change Isha's city in the grid → the "out of date" failure); `test_formula_error_fails`; `test_override_warns`; `test_lesson_without_specs_is_untouched`; in `test_gate_lesson.py`, `test_gate_reports_stale_screen` (prefix `screen: `); in `test_verify_v11.py`, `test_screen_is_a_known_visual`.
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Implement `check_lesson`; call it in `gate()` after the SVG checks; add `"screen"` to `VISUALS`. The SVG check loop in `gate()` already covers the drawn screen.
- [ ] **Step 4:** Run the whole generator suite; expect all pass.
- [ ] **Step 5:** Commit — `feat(screens): gate drawn screens against their spec and data`.

### Task 5: B briefs for the illustrator

**Files:**
- Create: `GS/screen_briefs.py`, `GS/test_screen_briefs.py`

**Interfaces:**
- Consumes: Task 1; Task 2 (`evaluate_many`, for an overridden B spec that has a `result` step); Task 3 (`reading_steps`); `IS/lessonhtml.py` (`sections`, `top_paragraphs`, `anchor_of`) via `sys.path`.
- Produces: `brief_items(course: dict) -> list[dict]` — one illustrator v2 plan item per B spec: `kind "screen"`, `lessonId`, `section` and `heading` (of the `<h2>` section that holds the spec), `position "after-explanation"`, `anchor` (the anchor of the last top-level paragraph before the spec), `question` = goal, `objective` = goal, `takeaway`, `misconception`, `intro` = `"Here is the screen for this step."`, `caption` = goal, `alt`, `explanation` = `reading_steps(spec, results)` (results from `evaluate_many` when the spec has a `result` step, else `{}`), `checkQuestion` = spec `check`, `labels` = the shown cell values + click-path items + dialog labels and values, `sourceRefs` = `["#" + grid id]`, `subject` = `"Spreadsheet window: " + goal`. CLI: `python screen_briefs.py --course <course.json> --out <plan.json>` writes `{"version": 2, "items": [...]}`.

- [ ] **Step 1: Failing tests:** `test_one_item_per_b_spec` (A specs skipped); `test_labels_come_from_the_grid_view` (only view cells, exact strings); `test_anchor_is_the_paragraph_before_the_spec`; `test_item_passes_illustrator_validation` (feed the output to `manifest.add_slots_v2` on a fixture course; expect no errors once Task 6 lands — mark `xfail(strict=True)` until then and remove the mark in Task 6).
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run; expect pass (the xfail stays xfail).
- [ ] **Step 5:** Commit — `feat(screens): illustrator briefs for simple walkthroughs`.

### Task 6: Illustrator kind `screen`

**Files:**
- Modify: `IS/manifest.py` (`KINDS` gains `"screen"`; `subject` required for `screen` as for `illustration`; labels allowed as image text for `screen`), `I/references/style.md` (a second fenced block ```` ```screen-style ```` and "Screen check criteria"), `IS/convert_images.py` (treat `screen` as a raster like `illustration`), `IS/insert_images.py` (`data-visual="screen"` for `screen`), tests `IS/test_manifest_v2.py`, `IS/test_insert_v2.py`, `IS/test_convert_images.py`; remove the `xfail` in `GS/test_screen_briefs.py`.

**Interfaces:**
- Consumes: Task 5 items.
- Produces: `style_block(labels, markers, kind="illustration")` — for `kind="screen"` it returns the `screen-style` block with `{text_clause}` filled with the exact labels and markers.

- [ ] **Step 1: Failing tests:** `test_screen_kind_is_accepted`; `test_screen_prompt_uses_screen_style_and_exact_labels` (prompt contains `"spreadsheet"` from the screen block and every label, and not the illustration block's `"No logos, screenshots, user-interface elements"` line); `test_screen_converts_like_an_illustration`; `test_screen_inserts_with_data_visual_screen`.
- [ ] **Step 2:** Run the illustrator suite; expect failures.
- [ ] **Step 3:** Implement. The `screen-style` block, verbatim:

```screen-style
Style: a clean, realistic spreadsheet window in the style of Microsoft Excel's light theme, cropped to the working area only: the ribbon tab and button in use, the formula bar and at most 5 columns by 6 rows. No title bar, no window controls, no taskbar.
Format: 4:3 or 3:4, sized so every label is readable on a phone screen; text large and bold where it matters.
Text: {text_clause}
Markers: numbered circles ① ② ③ next to the parts named in the steps, in order.
No logos, no brand marks, no watermarks, no extra rows, values or names beyond the listed text.
```

  "Screen check criteria" (append to style.md): every listed value appears exactly; nothing else is written; markers sit on the named parts in order; readable on the phone preview; no logo.
- [ ] **Step 4:** Run both suites; expect all pass.
- [ ] **Step 5:** Commit — `feat(illustrator): screen kind for simple walkthrough images`.

### Task 7: Rules for the writer, QA and the orchestrator

**Files:**
- Modify: `G/references/figures.md` (template 16 "Screen walkthrough": the spec, the rule, one A and one B example, "never hand-draw a screen SVG"), `G/references/runners/excel.md` (link to template 16), `agents/nerdit-lesson-writer.md` (write a spec for every click-path or formula walkthrough; B specs carry the teaching text; refresh mode `figures` may replace a hand-made walkthrough `<img>` with a spec), `agents/nerdit-qa-validator.md` (checklist: overrides justified; B briefs match the lesson), `G/SKILL.md` (orchestrator: run `render_screens.py` after each writer, before the gate; after assembly run `screen_briefs.py` and hand the plan to the illustrator), `GS/check_refresh.py` (in `figures` mode, screen specs, drawn screens and removed `<img>` walkthroughs count as figure scope), `GS/test_check_refresh.py`, `GS/test_docs_refs.py`, `.claude-plugin/plugin.json` (`3.4.0` → `3.5.0`).

- [ ] **Step 1: Failing tests:** `test_writer_knows_screen_specs` (writer mentions `nerdit-screen` and `render_screens.py`), `test_figures_has_template_16`, `test_skill_names_screen_scripts` (SKILL.md names `render_screens.py`, `check_screens.py`, `screen_briefs.py`), `test_plugin_version_is_3_5_0`; in `test_check_refresh.py`, `test_figures_mode_may_swap_an_img_for_a_screen_spec`.
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Edit the files and `check_refresh.parts()` (spec `<script class="nerdit-screen">` and `data-screen` blocks go to `figures`; a top-level `<img>` or `<p>` holding only an `<img>` goes to `figures`).
- [ ] **Step 4:** Run both suites; expect all pass.
- [ ] **Step 5:** Commit — `docs(screens): writer, QA and orchestrator rules; v3.5.0`.

### Task 8: Pilot on the Excel course

**Files (local work, committed in the nerdit repo):** `nerdit/generated/excel-data-analysis/` (new).

- [ ] **Step 1:** Fetch the published course and its lessons read-only through the Firestore REST API (`courses/course-excel-data-analysis-1785164945289` and its `lessons` subcollection); save them as one course-output JSON in that folder; run `python GS/input_from_output.py --in <that file> --workdir <folder> --chapter excel-data-analysis`. Snapshot lessons 01–04 into `_before/`.
- [ ] **Step 2:** For lessons 01–04, one writer at a time in refresh mode `figures`: replace each hand-made walkthrough image with a screen spec (17 images), keeping prose unchanged. Run `render_screens.py`, then the gate with `--before-dir _before --modes figures`. Two failed attempts per lesson → stop and report.
- [ ] **Step 3:** `screen_briefs.py` → illustrator `plan`; generate the B images with the image tool if it works, otherwise hand `PROMPTS.md` to the owner; `apply`.
- [ ] **Step 4:** Teaching QA per lesson; browser check at 1280 and 390 on the dev fixture route, side by side with the live images; record A/B counts, phone text size and every QA finding in `PROGRESS.md`.
- [ ] **Step 5:** Commit the folder (nerdit repo). Stop for the owner's review; no import or publishing.

### Task 9: Final verification

- [ ] **Step 1:** Both suites pass; record counts.
- [ ] **Step 2:** `check_css_bundle.py` and `check_runtime_bundle.py` exit 0 (no runtime file changed; the engine is only read).
- [ ] **Step 3:** The v11 gate still passes the Data Modelling lessons 08 and 10 unchanged (no specs → no screen checks).
- [ ] **Step 4:** Report test counts, pilot results and anything skipped.
