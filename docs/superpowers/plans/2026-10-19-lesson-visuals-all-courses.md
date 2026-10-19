# Lesson Visuals for Every Course Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The lesson writer describes each needed visual once, inside the lesson. The plugin then makes the visual from that description:

- **Screens** (app click-paths, every preset): the plugin draws the complex ones as SVG (A). The simple ones become checked AI-image briefs (B).
- **Scenes** (one simple idea through a familiar situation): these always become AI-image briefs (B).

Every visual comes from the lesson's own words and data.

**Architecture:**

- `screens.py` parses screen and scene specs, validates them against the lesson (the sync rule), and applies the complex/simple rule.
- `excel_eval.py` computes spreadsheet results with the plugin's own `nerdit-excel-engine.js` in Node.
- `render_screens.py` draws A screens with three kits: `sheet`, `editor` and `app`.
- `check_screens.py` gates them and warns about a click-path that has no screen.
- `visual_briefs.py` turns B screens and scenes into illustrator v2 items. The illustrator gains a `screen` kind.

**Tech Stack:** Python 3.14 stdlib + pytest; Node 24 (runs `references/nerdit-excel-engine.js`); illustrator scripts (Pillow already present).

**Spec:** `docs/superpowers/specs/2026-10-19-lesson-visuals-all-courses-design.md`

## Global Constraints

### Paths and tests

- **Paths** are relative to the plugin repo root:

  | Short name | Path |
  |---|---|
  | `G` | `skills/nerdit-chapter-generator` |
  | `GS` | `G/scripts` |
  | `I` | `skills/nerdit-lesson-illustrator` |
  | `IS` | `I/scripts` |

- **Tests:** run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` from `GS` and from `IS`.
  - Baseline: generator **361 passed**, illustrator **90 passed**.

### The screen spec

- **Block:** `<script type="application/json" class="nerdit-screen"[ data-grid="<grid id>"]>{...}</script>`. `data-grid` is required for `layout: "sheet"` only.
- **The grid** is the lesson's `<script type="application/json" id="<grid id>">{"headers": [...], "rows": [...]}</script>` (`runners/excel.md`). Row 1 holds headers; data row i is sheet row i + 2.
- **Common keys:**

  | Key | Value |
  |---|---|
  | `id` | unique across all screen and scene specs in the lesson |
  | `app` | non-empty string, the app's plain name |
  | `layout` | `"sheet"` \| `"editor"` \| `"app"` |
  | `goal` | the caption |
  | `steps` | non-empty |
  | `dialog` | `null` or `{"title", "fields": [{"label", "value"}]}` |
  | `image` | `"auto"`, `"A"` or `"B"` |
  | `why` | required when `image` is not `"auto"` |

- **B specs also need:** `alt` (≤150 chars), `takeaway`, `misconception`, and `check` `{"question", "answer", "reasoning"}`.

- **Keys per layout:**

  | Layout | Keys |
  |---|---|
  | `sheet` | `view` `{"columns": [letters], "rows": [first, last], "active": "<cell>"}` |
  | `editor` | `tool` (`"editor"`, `"notebook"` or `"terminal"`), `lines` (1–8 strings), `output` (0–4 strings) |
  | `app` | `path` (0–4 strings: the menu or page path) and `panel` (1–6 items) |

- **Panel items** (`app` layout), one of:
  - `{"kind": "field", "label", "value"}`
  - `{"kind": "button", "label"}`
  - `{"kind": "message", "who", "text"}`
  - `{"kind": "item", "text"}`

- **Step kinds:**

  | Kind | Keys | Notes |
  |---|---|---|
  | `select` | `target` | |
  | `click` | `path: [str, ...]` | |
  | `type` | `target, text` | for `sheet`, `text` is the formula or value |
  | `set` | `label, value` | the label must be a dialog field or a panel field |
  | `key` | `keys` | |
  | `result` | `target` | `sheet` only; the target must be filled by an earlier `type` |

- **Targets:**
  - `sheet`: a cell reference.
  - `editor`: `"line N"` (1-based, within `lines`).
  - `app`: a panel item's `label` (field or button).

### Limits and the A/B rule

- **Phone limits:**

  | Layout | Limit |
  |---|---|
  | `sheet` | view of at most **4** columns and **7** rows (the header row counts); each shown cell value at most **14** characters |
  | `editor` | each line or output line at most **40** characters |
  | `app` | each path item, label and value at most **24** characters; a message at most **90** characters, wrapped at word boundaries into at most 3 lines of **34** characters |
  | every SVG | viewBox width at most **400** |

  A breach fails validation and names the limit, e.g. `"4 columns"`, `"7 rows"`, `"14"`, `"40"`, `"24"`, `"90"`.

- **The complex/simple rule** (`screen_kind`). A screen is **A** when any of these hold:
  - `len(steps) > 3`;
  - 2 or more `set` steps;
  - a `dialog` with 2 or more fields;
  - any `result` step.

  Otherwise it is **B**. An override (`"A"`/`"B"` plus `why`) wins. A `sheet` B screen may not hold a `result` step unless it is an override.

### The sync rule

Every drawn string must appear in the lesson's visible text: path items, labels, values, code lines, output lines, messages, step `text`, `keys` and `path` items, and dialog titles, labels and values.

- **"Visible text"** is the lesson HTML's text, with HTML entities unescaped and whitespace collapsed. It excludes:
  - `<script>` and `<style>`;
  - every existing `data-screen` block (the figure and its reading list), so a drawn screen never vouches for itself.
- **Exempt:**
  - `id`, `app` and `goal`;
  - `sheet` grid cells, column letters and row numbers;
  - engine results;
  - the app's known labels: `KNOWN_LABELS = {"excel": EXCEL_TABS}`, keyed by `app.lower()`, where `EXCEL_TABS = ("Home", "Insert", "Draw", "Page Layout", "Formulas", "Data", "Review", "View", "Help")`.
- **Failure message:** `"<id>: '<string>' is not in the lesson"`.

### The scene spec

- **Block:** `<script type="application/json" class="nerdit-scene">{...}</script>`.
- **Keys:** `id`, `subject`, `alt` (≤150 chars), `caption`, `takeaway`, `misconception`, `check` `{"question", "answer", "reasoning"}`. All are required. A scene is always B.

### Figure output

- **Screen engine (Node):**
  - Shim: `globalThis.window = globalThis; globalThis.document = {readyState: "loading", addEventListener(){}}`.
  - `window.NerditExcel.makeGrid(headers, rows)`.
  - `window.NerditExcel.evaluate(formula, grid)` returns `{"ok": true, "value": v}`. An Excel error is `value == {"code": "#NAME?"}`.
  - Display values with `window.NerditExcel.formatValue(v)`.
- **A figure markup (exact):** inserted straight after its spec `</script>`:

  ```html
  <div class="nerdit-figure" data-visual="screen" data-screen="<id>" style="max-width:440px"><svg …></svg><div class="nerdit-figure-caption"><goal></div></div><ol class="nerdit-visual-read" data-screen="<id>"><li>① …</li>…</ol>
  ```

- **Reading-step wording (exact):**

  | Kind | Wording |
  |---|---|
  | `select` | `Click cell {target}.` for `sheet`; `Select {target}.` otherwise |
  | `click` | `Click {p1}.` for one item; more items joined with `, then ` (`Click {p1}, then {p2}.`) |
  | `type` | `Type {text} in {target}.` |
  | `set` | `Set {label} to {value}.` |
  | `key` | `Press {keys}.` |
  | `result` | `{target} shows {formatted value}.` |

- **SVG:**
  - colour tokens only (`var(--…)`, no hex);
  - text as `<text>`;
  - `role="img"`;
  - `aria-label` = goal + " " + steps joined by spaces;
  - markers ①–⑥ drawn on the parts their steps name.

  It must pass the illustrator's `svgcheck.check_svg(svg, labels, steps)`, where `steps` is the int step count.

### Commits

- End every commit with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Stage only the files a task names.
- No publishing or deploys in this plan.

## Review Focus

1. **Self-vouching.** A drawn screen's labels must not count as "lesson text" for its own sync check. Otherwise an edited lesson keeps passing (Task 1 test `test_drawn_screen_does_not_vouch_for_itself`).
2. **Number format.** A number cell such as 45000 must look the same in the drawn screen as in the Try It. The renderer uses the engine's `formatValue`, never Python `str()` (Task 3 test `test_numbers_use_engine_format`).
3. **Gap column.** A typed formula usually sits outside the data columns. For non-adjacent view columns, the renderer draws a narrow `…` gap column, and blank cells stay blank (Task 3 test `test_gap_column_between_non_adjacent_columns`).
4. **Escaping.** Strings containing `"`, `&`, `<` or `'` (formulas, code lines, chat messages) must be XML-escaped in the SVG. They must still match the lesson text, whose entities are unescaped (Task 1 test `test_entities_match_lesson_text`, Task 3 test `test_special_characters_are_escaped`).
5. **Stale screens.** A lesson edited after rendering (a grid value or a lesson word changed) must fail the gate until it is re-rendered (Task 4 tests `test_stale_figure_fails` and `test_removed_word_fails`).

---

### Task 0: Baseline

- [ ] **Step 1:** Run both suites; record `361 passed` and `90 passed`. Run `node --version`; expect `v24`.
- [ ] **Step 2:** `git status` is clean on `redesign-v2`.

### Task 1: Spec parsing, the sync rule and the A/B rule

**Files:**
- Create: `GS/screens.py`, `GS/test_screens.py`

**Interfaces:**
- Produces:
  - `read_specs(html: str) -> list[dict]`: screen specs, each the parsed JSON plus `"_grid"` (the `data-grid` attribute or `None`) and `"_offset"` (the end offset of its `</script>`), in page order.
  - `read_scenes(html: str) -> list[dict]`: scene specs, each plus `"_offset"`.
  - `read_grid(html: str, grid_id: str) -> tuple[list[str], list[list]] | None`.
  - `lesson_text(html: str) -> str`: the visible text as defined in Global Constraints.
  - `screen_kind(spec: dict) -> str`: `"A"` or `"B"`.
  - `drawn_strings(spec: dict) -> list[str]`: every string the sync rule checks.
  - `validate_spec(spec: dict, grid: tuple | None, text: str) -> list[str]`.
  - `validate_scene(scene: dict) -> list[str]`.
  - `validate_lesson(html: str) -> list[str]`: every spec, every scene, plus duplicate ids.
  - `col_index(letter: str) -> int` (A → 0).
  - `cell_value(grid, ref: str)`: the header row, data rows, or `None` outside the grid.

- [ ] **Step 1: Write the failing tests** in `GS/test_screens.py`.
  - **Fixtures:**
    - A `sheet` lesson string with grid `xl-staff`: headers `ID, Name, Department, City, Salary`; rows 101 Aarav Sales Mumbai 45000 … 106 Isha Marketing Chennai 49000, as in the live Excel lesson 04.
    - An `app` lesson: an ads-manager walkthrough whose text names `Campaigns`, `Create`, `Objective`, `Sales`, `Daily budget`, `₹500`, `Publish`.
    - An `editor` lesson: a terminal with `pip install pandas`.
  - **The A/B rule:**
    - `test_xlookup_with_result_is_A`
    - `test_two_clicks_is_B`
    - `test_four_steps_is_A`
    - `test_two_set_steps_is_A`: the ads form setting Objective and Daily budget.
    - `test_dialog_with_two_fields_is_A`
    - `test_terminal_one_command_is_B`
  - **Overrides:** `test_override_needs_why`. Without `why`, a problem names `"why"`. With `why`, `screen_kind` follows the override.
  - **Layout limits:**
    - `test_sheet_view_limits`: `"4 columns"`, `"7 rows"`.
    - `test_sheet_long_value_fails`: `"14"`.
    - `test_editor_limits`: 9 lines, or a 41-character line, fails.
    - `test_app_limits`: 7 panel items, a 25-character label, or a 91-character message fails.
  - **The sync rule:**
    - `test_sync_rule_app`: `"Magic Button"` → `"'Magic Button' is not in the lesson"`. The fixture's own words pass.
    - `test_known_excel_labels_pass`: `click ["Data", "Remove Duplicates"]` passes when the lesson text names "Remove Duplicates" but not the tab "Data".
    - `test_drawn_screen_does_not_vouch_for_itself` (Review Focus 1): a word present only inside a `data-screen` figure fails.
    - `test_entities_match_lesson_text` (Review Focus 4): lesson text `=IF(A2&lt;5,"low","ok")` matches the spec string `=IF(A2<5,"low","ok")`.
  - **Structure:**
    - `test_unknown_layout_grid_and_step_kind_fail`
    - `test_result_needs_earlier_type_and_sheet`
    - `test_set_label_must_be_a_field`
    - `test_editor_target_is_a_line`
    - `test_b_needs_teaching_text`: names `check`.
    - `test_scene_needs_all_keys`
    - `test_duplicate_ids_across_screens_and_scenes_fail`
    - `test_bad_json_is_a_problem_not_a_crash`
    - `test_cell_value`: `B7` → `"Isha"`, `A1` → `"ID"`, `H3` → `None`.
- [ ] **Step 2:** Run `python -m pytest -q test_screens.py`; expect `ModuleNotFoundError: screens`.
- [ ] **Step 3:** Implement `GS/screens.py` with the interfaces above and the Global Constraints. Use stdlib `re`, `json` and `html.parser`. Report problems; never raise.
- [ ] **Step 4:** Run the file, then the whole generator suite; expect all pass.
- [ ] **Step 5:** Commit: `feat(visuals): screen and scene specs, the sync rule and the A/B rule`.

### Task 2: Excel engine bridge

**Files:**
- Create: `GS/excel_eval.py`, `GS/test_excel_eval.py`

**Interfaces:**
- Consumes: `references/nerdit-excel-engine.js`.
- Produces: `evaluate_many(headers: list, rows: list, formulas: list[str]) -> list[dict]`.
  - It runs one Node process per call.
  - Each item is `{"value": <python value>, "text": <formatValue string>}` or `{"error": "#NAME?"}`, in the order of `formulas`.
  - It raises `RuntimeError("Node.js is required for Excel screens: install Node 18+")` when `node` is not on PATH.

- [ ] **Step 1: Failing tests:**
  - `test_xlookup_returns_chennai`: `text == "Chennai"`.
  - `test_unknown_function_is_an_error`: `=FOO(1)` → `{"error": "#NAME?"}`.
  - `test_batch_keeps_order`
  - `test_missing_node_message`: monkeypatch `shutil.which` to return `None`.
- [ ] **Step 2:** Run; expect `ModuleNotFoundError`.
- [ ] **Step 3:** Implement a small JS program passed to `node -` on stdin. It:
  - applies the shim;
  - `require`s the engine by absolute path;
  - reads `{headers, rows, formulas}` JSON from a temp file named in argv;
  - prints one JSON array.

  Call it with `subprocess.run(..., timeout=30, check=False)`. A non-zero exit raises `RuntimeError` with stderr's last line.
- [ ] **Step 4:** Run tests; expect pass.
- [ ] **Step 5:** Commit: `feat(visuals): evaluate formulas with the plugin's Excel engine`.

### Task 3: Type A renderer (three kits)

**Files:**
- Create: `GS/render_screens.py`, `GS/test_render_screens.py`

**Interfaces:**
- Consumes:
  - Task 1 and Task 2.
  - `IS/svgcheck.py` `check_svg(svg, labels, steps)`, imported via `sys.path` as `gate_lesson.py` does.
- Produces:
  - `reading_steps(spec: dict, results: dict[str, str]) -> list[str]`.
  - `render_svg(spec: dict, grid: tuple | None, results: dict[str, str]) -> str`: deterministic.
  - `figure_block(spec: dict, svg: str, steps: list[str]) -> str`.
  - `results_for(spec: dict, grid: tuple | None) -> tuple[dict[str, str], list[str]]`: formatted results by target, plus problems (`"H3: =FOO(1) gives #NAME?"`).
  - `render_lesson(html: str) -> tuple[str, list[str]]`:
    - A specs get a fresh block, replacing any block with the same `data-screen`.
    - B specs get none; an existing drawn block is removed.
  - **CLI:** `python render_screens.py --dir <lesson dir> [--id <lesson id>]` rewrites `<id>.html` in place. It exits 1 and writes nothing when any lesson has problems.

- [ ] **Step 1: Failing tests:**
  - **Every kit:**
    - `test_viewbox_fits_a_phone`
    - `test_tokens_only`
    - `test_passes_svgcheck`
    - `test_markers_match_steps`
    - `test_reading_step_wording`: exact strings for each kind and layout.
  - **`sheet`:**
    - `test_shows_only_the_view_window`
    - `test_result_cell_shows_engine_value`
    - `test_numbers_use_engine_format` (Review Focus 2)
    - `test_gap_column_between_non_adjacent_columns` (Review Focus 3)
  - **`editor`:** `test_editor_draws_lines_and_output` (each line and output line is a `<text>`; a terminal tool draws a prompt `$`).
  - **`app`:**
    - `test_app_draws_path_and_panel`: the path items, field labels and values, and button labels appear.
    - `test_message_wraps_at_34`
  - **Escaping:** `test_special_characters_are_escaped` (Review Focus 4: parse the SVG with `xml.dom.minidom.parseString`).
  - **Re-rendering:**
    - `test_render_is_idempotent`
    - `test_rerender_replaces_only_its_own_block`
    - `test_b_spec_gets_no_figure`
- [ ] **Step 2:** Run; expect `ModuleNotFoundError`.
- [ ] **Step 3:** Implement. Everything goes in one SVG, width 400, drawn top to bottom:
  1. A title line (the goal).
  2. A bar showing the app name and, when a `click` step or `path` exists, the path items. The clicked item is highlighted.
  3. The body:

     | Layout | Body |
     |---|---|
     | `sheet` | formula bar plus grid window: column letters, row numbers, cells, the active cell outlined |
     | `editor` | numbered code lines, then an output area; `terminal` uses a `$ ` prompt and no line numbers |
     | `app` | panel rows: field label and value boxes, buttons, message bubbles aligned left (model) or right (you), list items |

  4. The dialog panel, when set.

  Each marker sits next to the part its step names. Column and box widths come from the longest shown string at a fixed character width.
- [ ] **Step 4:** Run tests; then the whole generator suite.
- [ ] **Step 5:** Commit: `feat(visuals): draw complex walkthroughs as phone-sized SVG`.

### Task 4: Gate check, visual type and the "needed here" warning

**Files:**
- Create: `GS/check_screens.py`, `GS/test_check_screens.py`
- Modify:
  - `GS/gate_lesson.py`: run the check; failures are prefixed `screen: `.
  - `GS/test_gate_lesson.py`
  - `GS/verify_course.py`: `VISUALS` gains `"screen"`.
  - `GS/test_verify_v11.py`

**Interfaces:**
- Consumes:
  - Tasks 1–3.
  - `verify_course.parse`, `walk` and `text_of` for the click-path warning.
- Produces: `check_lesson(html: str) -> tuple[list[str], list[str]]`.
  - **Fails:**
    - every `validate_lesson` problem;
    - every `results_for` problem;
    - an A spec with no figure: `"<id>: no drawn screen; run render_screens.py"`;
    - an A figure that differs from a fresh render: `"<id>: drawn screen is out of date; run render_screens.py"`;
    - a B spec with a drawn figure.
  - **Warns:**
    - every override: `"<id>: image forced to A|B: <why>"`;
    - a concept section (a `<section>` without `nerdit-cheatsheet` or `nerdit-practical`) that holds a click-path and no `nerdit-screen` spec: `"section <n>: click-path with no screen (figures.md template 16)"`.
  - A click-path is an `<ol>` that is not `nerdit-visual-read` and not inside `<details>`, where both hold:
    - at least 2 items start with one of `Click, Select, Open, Go to, Choose, Press, Type, Drag, Set, Tap, Enter`;
    - at least one item names a UI part (`tab, menu, button, dialog, panel, pane, ribbon, field, box, toolbar, sidebar`) or contains `→` or ` > `.
  - A lesson with no specs and no click-path returns `([], [])`.

- [ ] **Step 1: Failing tests:**
  - `test_clean_rendered_lesson_passes`
  - `test_missing_figure_fails`
  - `test_stale_figure_fails` (Review Focus 5: Isha's city changed in the grid)
  - `test_removed_word_fails` (Review Focus 5: "Daily budget" deleted from the `app` lesson text)
  - `test_formula_error_fails`
  - `test_override_warns`
  - `test_click_path_without_screen_warns`
  - `test_reading_list_and_answers_are_not_click_paths`
  - `test_lesson_without_specs_is_untouched`
  - In `test_gate_lesson.py`: `test_gate_reports_stale_screen`.
  - In `test_verify_v11.py`: `test_screen_is_a_known_visual`.
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Implement `check_lesson`. Call it in `gate()` after the SVG checks; warnings join the gate's warnings. Add `"screen"` to `VISUALS`.
- [ ] **Step 4:** Run the whole generator suite; expect all pass.
- [ ] **Step 5:** Commit: `feat(visuals): gate drawn screens and flag click-paths with no screen`.

### Task 5: B briefs for the illustrator (screens and scenes)

**Files:**
- Create: `GS/visual_briefs.py`, `GS/test_visual_briefs.py`

**Interfaces:**
- Consumes:
  - Task 1.
  - Task 2 (`evaluate_many`, for an overridden B `sheet` spec with a `result` step).
  - Task 3 (`reading_steps`).
  - `IS/lessonhtml.py` (`sections`, `top_paragraphs`, `anchor_of`) via `sys.path`.
- Produces: `brief_items(course: dict) -> list[dict]`, one illustrator v2 plan item per B screen and per scene.
  - **Shared fields:** `lessonId`; `section` and `heading` (of the `<h2>` section that holds the spec); `position "after-explanation"`; `anchor` (the anchor of the last top-level paragraph before the spec); `takeaway`; `misconception`; `alt`; `checkQuestion` = spec `check`.
  - **Screen items:**

    | Field | Value |
    |---|---|
    | `kind` | `"screen"` |
    | `question`, `objective`, `caption` | the goal |
    | `intro` | `"Here is the screen for this step."` |
    | `explanation` | `reading_steps(spec, results)` |
    | `labels` | `drawn_strings(spec)` plus the shown grid cells |
    | `sourceRefs` | `["#" + grid id]` for `sheet`, else `["#" + spec id]` |
    | `subject` | `app + " window: " + goal` |

  - **Scene items:**

    | Field | Value |
    |---|---|
    | `kind` | `"illustration"` |
    | `question`, `objective` | the takeaway |
    | `intro` | `"Picture it this way."` |
    | `caption`, `subject` | from the spec |
    | `explanation` | `[]` |
    | `labels` | `[]` |
    | `sourceRefs` | `["#" + spec id]` |

  - **CLI:** `python visual_briefs.py --course <course.json> --out <plan.json>` writes `{"version": 2, "items": [...]}`.

- [ ] **Step 1: Failing tests:**
  - `test_one_item_per_b_screen_and_scene`: A screens are skipped.
  - `test_screen_labels_are_exact`
  - `test_anchor_is_the_paragraph_before_the_spec`
  - `test_items_pass_illustrator_validation`: feed the output to `manifest.add_slots_v2` on a fixture course and expect no errors. The scene item passes now. Mark the screen item `xfail(strict=True)` until Task 6.
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run; expect pass (the xfail stays xfail).
- [ ] **Step 5:** Commit: `feat(visuals): illustrator briefs for simple screens and scenes`.

### Task 6: Illustrator kind `screen`

**Files:**
- Modify:
  - `IS/manifest.py`: `KINDS` gains `"screen"`. `subject` is required for `screen`, as for `illustration`. Labels are allowed as image text for `screen`.
  - `I/references/style.md`: a second fenced block, ```` ```screen-style ````, and a "Screen check criteria" section.
  - `IS/convert_images.py`: treat `screen` as a raster, like `illustration`.
  - `IS/insert_images.py`: write `data-visual="screen"` for `screen`.
  - Tests: `IS/test_manifest_v2.py`, `IS/test_insert_v2.py`, `IS/test_convert_images.py`.
  - Remove the `xfail` in `GS/test_visual_briefs.py`.

**Interfaces:**
- Consumes: Task 5 items.
- Produces: `style_block(labels, markers, kind="illustration", app="")`. For `kind="screen"`, it returns the `screen-style` block with `{app}` and `{text_clause}` filled.

- [ ] **Step 1: Failing tests:**
  - `test_screen_kind_is_accepted`
  - `test_screen_prompt_uses_screen_style_and_exact_labels`: the prompt contains the app name and every label. It must not contain the illustration block's `"No logos, screenshots, user-interface elements"` line.
  - `test_screen_converts_like_an_illustration`
  - `test_screen_inserts_with_data_visual_screen`
- [ ] **Step 2:** Run the illustrator suite; expect failures.
- [ ] **Step 3:** Implement. The `screen-style` block, verbatim:

```screen-style
Style: a clean, realistic {app} screen in its light theme, cropped to the working area only: the menu, tab or panel in use and the content the steps touch. No title bar, no window controls, no taskbar, no browser chrome.
Format: 4:3 or 3:4, sized so every label is readable on a phone screen; text large and bold where it matters.
Text: {text_clause}
Markers: numbered circles ① ② ③ next to the parts named in the steps, in order.
No logos, no brand marks, no watermarks, no extra values, names or menu items beyond the listed text.
```

  Append "Screen check criteria" to style.md:
  - every listed label appears exactly;
  - nothing else is written;
  - markers sit on the named parts, in order;
  - the image is readable on the phone preview;
  - there is no logo.
- [ ] **Step 4:** Run both suites; expect all pass.
- [ ] **Step 5:** Commit: `feat(illustrator): screen kind for simple walkthrough images`.

### Task 7: Rules for the writer, QA and the orchestrator

**Files:**
- Modify:
  - `G/references/CORE.md`:
    - Visual Map: add a row `Worked example | a click-path in an app | screen (figures.md §16) | writer spec; A drawn by script, B by illustrator` and a row `Concept: meaning | one simple idea through a familiar scene | scene spec → illustration | writer spec; illustrator`.
    - Add the owner's rule in one line: complex → A (drawn), simple → B (image).
    - Balance: one visual per idea; a screen never repeats the run line beside it.
  - `G/references/figures.md`: template 16, "Screen walkthrough". It covers the three layouts, the rule, the sync rule, one A example and one B example, and "never hand-draw a screen SVG". Template 17, "Scene", covers the scene spec.
  - `G/references/runners/excel.md`: link to template 16.
  - `agents/nerdit-lesson-writer.md`:
    - write a screen spec for every click-path in any app;
    - write a scene spec where the section's analogy is the clearest way in;
    - B specs carry the teaching text;
    - refresh mode `figures` may replace a walkthrough `<img>` with a spec, and may add specs.
  - `agents/nerdit-qa-validator.md`: checklist items: overrides are justified; specs sit where the learner needs them; no screen repeats a run line.
  - `G/SKILL.md` (orchestrator):
    - run `render_screens.py` after each writer, before the gate;
    - after assembly, run `visual_briefs.py` and the illustrator plan step in the same run;
    - the final report lists A, B and scene counts and the `PROMPTS.md` path.
  - `GS/check_refresh.py`: in `figures` mode, screen and scene specs, drawn screens, and removed top-level `<img>` walkthroughs count as figure scope.
  - Tests: `GS/test_check_refresh.py`, `GS/test_docs_refs.py`.
  - `.claude-plugin/plugin.json`: `3.4.0` → `3.5.0`.

- [ ] **Step 1: Failing tests:**
  - `test_writer_knows_screen_and_scene_specs`: the writer mentions `nerdit-screen`, `nerdit-scene` and `render_screens.py`.
  - `test_figures_has_templates_16_and_17`
  - `test_visual_map_has_screen_and_scene_rows`
  - `test_skill_names_visual_scripts`: SKILL.md names `render_screens.py`, `check_screens.py` and `visual_briefs.py`.
  - `test_plugin_version_is_3_5_0`, replacing the 3.4.0 test.
  - In `test_check_refresh.py`:
    - `test_figures_mode_may_swap_an_img_for_a_screen_spec`
    - `test_figures_mode_may_add_a_scene_spec`
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Edit the files. In `check_refresh.parts()`, these go to `figures`:
  - `<script class="nerdit-screen|nerdit-scene">`;
  - `data-screen` blocks;
  - a top-level `<img>`, or a `<p>` holding only an `<img>`.
- [ ] **Step 4:** Run both suites; expect all pass.
- [ ] **Step 5:** Commit: `docs(visuals): writer, QA and orchestrator rules for screens and scenes; v3.5.0`.

### Task 8: Pilot across course types

**Files (local work, committed in the nerdit repo):** `nerdit/generated/excel-data-analysis/` and `nerdit/generated/digital-marketing/` (both new), and the existing `agentic-ai-for-data-analysis/` and `data-modelling-etl-data-warehousing-for-analysts/v11/`.

- [ ] **Step 1: Set up the workdirs.**
  - Fetch two courses and their `lessons` subcollections, read-only, through the Firestore REST API: `course-excel-data-analysis-1785164945289` and `course-1779177659694` (Digital Marketing).
  - Save each as a course-output JSON.
  - Run `python GS/input_from_output.py --in <file> --workdir <folder> --chapter <slug>`.
  - Snapshot each pilot lesson into `_before/`.
- [ ] **Step 2: Pick the lessons.**
  - Excel lessons 01–04 (17 images).
  - One Digital Marketing lesson that teaches a tool click-path.
  - One Agentic AI lesson with a tool or chat step.
  - Data Modelling lesson 01 (add the shop-counter scene).

  Record the choice and why in each `PROGRESS.md`.
- [ ] **Step 3: Refresh the lessons.** Work one writer at a time, in refresh mode `figures`, with prose unchanged.
  - Run `render_screens.py`.
  - Run the gate with `--before-dir _before --modes figures`.
  - After two failed attempts on a lesson, stop and report.
- [ ] **Step 4: Make the B images.**
  - Run `visual_briefs.py`, then the illustrator `plan` step.
  - Generate the B images with the image tool if it works. Otherwise hand `PROMPTS.md` to the owner.
  - Run `apply`.
- [ ] **Step 5: Check and record.**
  - Run teaching QA per lesson.
  - Browser-check at 1280 and 390 on the dev fixture route. Show the Excel lessons side by side with the live images.
  - In `PROGRESS.md`, record:
    - A/B/scene counts per lesson;
    - phone text size;
    - every QA finding.
- [ ] **Step 6:** Commit the folders in the nerdit repo. Stop for the owner's review; no import or publishing.

### Task 9: Final verification

- [ ] **Step 1:** Both suites pass; record counts.
- [ ] **Step 2:** `check_css_bundle.py` and `check_runtime_bundle.py` exit 0. No runtime file changed; the engine is only read.
- [ ] **Step 3:** The v11 gate still passes the Data Modelling lessons 08 and 10 unchanged (no specs, so no screen checks).
- [ ] **Step 4:** Report test counts, pilot results, the rollout list (courses still without visuals), and anything skipped.
