# brand-studio engine Implementation Plan (part 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new `brand-studio` plugin whose engine renders, from a course JSON (or a Future Vision brief), the 6-slide intro series, a 16:9 thumbnail/course image and a Future Vision course-showcase set, in per-course looks that never repeat, for the pilot.

**Architecture:** A Python package `brand_studio` (pip install -e) inside a new plugin folder. Brand kits and looks are JSON files; parts are functions returning HTML with CSS variables from the look; page types compose parts in fixed text/photo regions; Playwright shoots PNGs and measures overflow; checks enforce every rule. Part 2 (separate plan, after the owner OKs the pilot) wires NERDIT's social packs and video thumbnail onto this engine.

**Tech Stack:** Python 3.14 (system), Playwright Chromium (already installed for nerdit-social-posts), Pillow, pytest (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`).

**Spec:** `nerdit-plugin-json-generator/docs/superpowers/specs/2026-11-20-brand-studio-design.md`

## Global Constraints

- Plugin root: `D:\siddharth\nerdit-backup\nerdit-mainAndPlugin\nerdit-mainAndPlugin\brand-studio-plugin\`, its own local git repo; nothing pushed.
- Runtime data: `$BRAND_STUDIO_HOME` (default `~/.brand-studio`)`/<brand>/` holds `history.json` and `assets/`; tests set `BRAND_STUDIO_HOME` to a tmp dir (autouse fixture) and never touch the real home.
- Light pages: page background relative luminance >= 0.6 (also for a photo's sampled background). Contrast >= 4.5 for text on its background.
- Fonts allowed: Segoe UI, Segoe UI Variable Display, Segoe UI Semibold, Segoe UI Black, Bahnschrift, Bahnschrift Condensed, Bahnschrift SemiBold Condensed, Bahnschrift Bold Condensed, Georgia, Georgia Pro, Cambria, Corbel, Consolas.
- Banned phrases (both brands): "free certificate" (case-insensitive). Handle on both brands' pages: `Nerdit.in`.
- Sizes: carousel 1080x1350, Story 1080x1920, thumbnail 1280x720.
- Lesson titles are shown word for word (after stripping outer spaces); every number in agent-written text must appear in the course JSON text.
- Icons: Fluent Emoji 3D from `~/.nerdit-social/assets/icons/fluent-3d/` (copied into the brand's assets at intake, with `LICENSE-MIT.txt`). The Gemini sparkle mark is left alone.

## Review Focus

- A lesson or course title longer than its slot (for example "Cleaning Capstone: Reconcile a Messy Orders Batch"): the text shrinks down to the slot's minimum size, then fails with the slot named; never cut off (Task 7 test).
- A course with an empty description and trailing spaces in its title (Supervised Learning Classification): pages render from the agent's words and the stripped title (Task 8 test).
- A photo whose background is darker than the light-page limit: refused at intake with its file name (Task 5 test).
- `&`, `<`, quotes in any text: escaped, never breaking the page (Task 6 test).
- A course with fewer lessons than a slot list wants (for example 3 lessons for 4 checklist rows): the page shows what exists, no empty rows (Task 7 test).

---

### Task 1: Plugin scaffold, package and brand kits

**Files:**
- Create: `brand-studio-plugin/.claude-plugin/plugin.json` (name `brand-studio`, version `0.1.0`, author Future Vision Computers, MIT)
- Create: `brand-studio-plugin/engine/pyproject.toml` (package `brand_studio`, deps `pillow`, `playwright`)
- Create: `brand-studio-plugin/engine/brand_studio/__init__.py`, `brand_studio/brands.py`
- Create: `brand-studio-plugin/brands/nerdit/brand.json`, `brands/nerdit/logo.png` (copy of the NERDIT logo the social skill uses), `brands/futurevision/brand.json`, `brands/futurevision/logo.png` (copy of `D:\siddharth\logo\fv logo2024.png`)
- Create: `brand-studio-plugin/engine/tests/conftest.py` (autouse `BRAND_STUDIO_HOME` tmp fixture), `tests/test_brands.py`
- Create: `brand-studio-plugin/skills/brand-studio/SKILL.md` (stub: what the plugin is; filled in Task 8)

**Interfaces:**
- Produces: `brands.load_brand(name: str) -> dict` (keys: `name`, `handle`, `logo` (absolute Path str), `ink`, `accents` (list of hex), `fonts` (list), `rules` (`{"light_pages": true, "banned": [...]}`), `cta`, `website`); `brands.brand_errors(brand: dict) -> list[str]`; `brands.home(brand_name: str) -> Path` (`$BRAND_STUDIO_HOME/<brand>`, created); `brands.PLUGIN_ROOT: Path`.

- [ ] **Step 1: Write failing tests** `test_nerdit_kit_loads`, `test_futurevision_kit_uses_nerdit_handle_and_its_logo_colours`, `test_kit_missing_a_key_is_reported`, `test_home_uses_env_dir`:
  - `load_brand("nerdit")["handle"] == "Nerdit.in"`, `"free certificate" in [b.lower() for b in ...["rules"]["banned"]]`, `Path(logo).is_file()`.
  - futurevision: `handle == "Nerdit.in"`, accents contain an indigo and a red (`"#2e2a86"`, `"#b91c1c"` exactly), logo file exists.
  - `brand_errors({**kit, "handle": ""}) == ["brand: handle is empty"]`.
  - `home("nerdit") == tmp/"nerdit"` and exists.
- [ ] **Step 2:** `cd brand-studio-plugin/engine && pip install -e . && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` → FAIL (module/functions missing).
- [ ] **Step 3:** Implement `brands.py` and the two kits (NERDIT ink `#0B1F3A`, accents teal `#14B8A6` first; Future Vision ink `#1F1B5C`, accents `#2e2a86`, `#b91c1c`; both `cta` "Start the course on NerdIT", website `https://nerdit.in`).
- [ ] **Step 4:** Tests pass.
- [ ] **Step 5:** `git init` in `brand-studio-plugin`, commit "feat: brand-studio scaffold and brand kits".

### Task 2: Looks and the per-brand "never repeat" history

**Files:**
- Create: `engine/brand_studio/looks.py`, `brand-studio-plugin/brands/nerdit/looks/*.json` (the 13 light styles from `nerdit-social-posts/styles/*.json` converted), `brands/futurevision/looks/*.json` (4 new light looks: indigo or red accents on light grey/cream pages)
- Test: `engine/tests/test_looks.py`

**Interfaces:**
- Consumes: `brands.home`, `checks.look_errors` (Task 3; write Task 3 first if executing out of order — or keep `looks.py` free of checks and let Task 3's test load every shipped look).
- Produces: look JSON shape `{name, inspiration, palette: {bg, bg2, panel, ink, muted, accent, highlight, chip, chipInk, codeBg, codeInk, wave1, wave2}, fonts: {display, body, condensed, code}, motif: "wave"|"blob"|"none"}`; `VARIANTS = ("a", "b")`; `looks.load_looks(brand: str) -> list[dict]`; `looks.history_path(brand) -> Path`; `load_history(path) -> dict`; `save_history(path, history) -> None` (write to a temp file then replace); `pick_looks(items: list[dict], looks: list[dict], history: dict, key: str) -> list[tuple[str, str]]` returning `(look_name, variant)` per item; `reserve_looks(history, key, picks: list[tuple[str, str, str]], folder: str | None = None) -> dict`; `mark_built(history, key) -> dict`; `prune_history(history) -> dict`; `class NoFreshLooks(Exception)`.
  Same semantics as `nerdit-social-posts/scripts/stylebook.py` (least-used look first, then least-used variant; a look never repeats within `RECENT = 3` items; history entries carry `folder` and `built`; prune drops unbuilt entries whose folder no longer has its plan file), with variant in place of layout. Conversion of old styles: `head` -> `display`, `condensed` = "Bahnschrift Bold Condensed", `highlight` = a light tint of `accent` that keeps ink contrast >= 4.5, `wave1` = `accent`, `wave2` = `ink`, motif `highlight`/`underline` -> `wave`, `stickers`/`arrows` -> `blob`, `none` -> `none`.

- [ ] **Step 1: Failing tests** `test_nerdit_has_13_looks_and_futurevision_4`, `test_pick_gives_each_item_an_unused_look_and_variant`, `test_no_look_repeats_within_three_items`, `test_history_is_per_brand_and_survives_reload`, `test_exhausted_pool_raises_no_fresh_looks`, `test_prune_returns_looks_of_abandoned_plans`. Use the stylebook tests in `nerdit-social-posts/scripts/test_stylebook.py` as the model for the last four.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `looks.py`; write the conversion as a one-off script in the scratchpad (not shipped), run it, commit its output JSON.
- [ ] **Step 4:** Tests pass.
- [ ] **Step 5:** Commit "feat: looks with per-brand never-repeat history".

### Task 3: Checks

**Files:**
- Create: `engine/brand_studio/checks.py`
- Test: `engine/tests/test_checks.py`

**Interfaces:**
- Produces: `LIGHT_PAGE = 0.6`; `FONTS` (Global Constraints list); `luminance(hex) -> float`; `contrast(a, b) -> float`; `look_errors(look: dict) -> list[str]` (missing keys, bad hex, dark bg/bg2, ink-on-bg and ink-on-highlight and chipInk-on-chip contrast < 4.5, font not allowed); `banned_errors(text: str, brand: dict) -> list[str]`; `overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool` (x, y, w, h); `unknown_numbers(text: str, source_text: str) -> list[str]` (same rule as `nerdit-social-posts/scripts/captions.py:unknown_numbers`).

- [ ] **Step 1: Failing tests** `test_every_shipped_look_passes`, `test_dark_page_is_refused`, `test_low_contrast_highlight_is_refused`, `test_unknown_font_is_refused`, `test_banned_phrase_any_case`, `test_overlap`, `test_numbers_must_come_from_the_source`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit "feat: checks".

### Task 4: Render and overflow measurement

**Files:**
- Create: `engine/brand_studio/render.py`
- Test: `engine/tests/test_render.py`

**Interfaces:**
- Produces: `render.shoot(pages: list[tuple[str, Path, int, int]]) -> None` (one Chromium, PNG or JPEG by suffix; port of `draw.shoot`); `render.overflows(html: str, width: int, height: int) -> list[str]` returns `data-slot` names of elements with class `fit` whose text still overflows after shrinking. Shrinking: elements with class `fit` shrink their font size in steps down to `data-min` px (port of `FIT_JS`, which already lives in `draw.py:171`), and are marked `data-over="1"` when still too big.

- [ ] **Step 1: Failing tests** `test_shoot_writes_image_at_size` (1080x1350 PNG; Pillow reads that size), `test_long_text_shrinks_to_fit`, `test_text_too_long_even_at_min_is_reported` (returns `["title"]`).
- [ ] **Step 2–5:** FAIL, implement, PASS, commit "feat: render and overflow".

### Task 5: Asset library and prompt sheet

**Files:**
- Create: `engine/brand_studio/assets.py`
- Test: `engine/tests/test_assets.py`

**Interfaces:**
- Consumes: `brands.home`, `checks.luminance`.
- Produces: `add_photos(brand: str, folder: Path, meta: dict[str, dict]) -> list[str]` (meta per file stem: `facing` in {left, right, front}, `pose`, `outfit`, `kind` in {cutout, scene}); stores a JPEG copy (long side 1600 px) in `home/assets/photos/`, appends to `index.json` `{file, kind, aspect, bg, facing, pose, outfit, source: "gemini", used_by: []}`; returns problems (`"st09.png: background #6b6b6b is too dark for a light page"`, missing meta). `add_icons(brand, folder) -> int` copies PNGs and the licence. `pick_photo(brand, *, kind, facing=None, course: str) -> dict | None` (never a photo already used by `course`; else least-used; ties by file name). `mark_used(brand, file, course) -> None`. `icon(brand, name) -> Path`. `prompt_sheet(brand, missing: list[dict]) -> str` (markdown, one prompt per entry, same wording rules as `C:\Users\siddh\.nerdit-social\assets\gemini-test\PROMPTS.md`: plain light grey seamless background #EDEDED, waist-up, no text/logos, vertical 4:5 or 16:9).

- [ ] **Step 1: Failing tests** `test_add_photo_samples_background_and_indexes`, `test_dark_background_photo_is_refused`, `test_pick_never_reuses_within_a_course_and_prefers_least_used`, `test_missing_meta_is_reported`, `test_prompt_sheet_asks_for_light_grey_and_no_text`.
- [ ] **Step 2–5:** FAIL, implement, PASS, commit "feat: asset library".

### Task 6: Parts

**Files:**
- Create: `engine/brand_studio/parts.py`
- Test: `engine/tests/test_parts.py`

**Interfaces:**
- Consumes: look dict (Task 2), `assets.icon`.
- Produces (all return HTML strings; colours only via CSS variables `--bg --bg2 --panel --ink --muted --accent --highlight --chip --chipInk --codeBg --codeInk --wave1 --wave2`; all text HTML-escaped): `css_vars(look) -> str`; `brand_mark(handle)`; `page_number(n: int)`; `headline(text: str, highlight: list[str], slot: str = "headline")` (wraps each exact highlighted phrase in `<mark>`; class `fit`, `data-slot`, `data-min`); `subline(text)`; `icon_card(icon_uri, text, keyword="")`; `check_card(text)`; `tile(icon_uri, text)`; `photo(uri, bg_hex, box: tuple, facing)` (absolutely placed in `box`, edge fade on the side facing the text); `badge(icon_uri, box)`; `wave(corner: str)` ("br" or "tl"); `blob(box)`; `title_band(text)`; `cta_bar(text)`; `glass_panel(kind: str, lines: list[str], box)` (kind in {code, list, response}); `logo_chip(logo_uri)`.

- [ ] **Step 1: Failing tests** `test_parts_use_variables_not_hex` (regex `#[0-9a-fA-F]{3,6}` absent from every part's output except inside `url(data:` URIs), `test_headline_marks_exact_phrases`, `test_text_is_escaped` (`"R&D <b>"` appears as `R&amp;D &lt;b&gt;`), `test_fit_slots_carry_name_and_min`.
- [ ] **Step 2–5:** FAIL, implement, PASS, commit "feat: parts".

### Task 7: Page types

**Files:**
- Create: `engine/brand_studio/pages.py`
- Test: `engine/tests/test_pages.py`

**Interfaces:**
- Consumes: parts, `render.overflows`, `checks.overlap`, `checks.banned_errors`.
- Produces: `PAGE_TYPES = ("hook", "questions", "learn", "project", "skills", "cta", "thumbnail")`; each type has `SLOTS[type]` (slot -> max characters, max lines) and `REGIONS[type][variant]` with `"text"` and `"photo"` boxes for variants `a` (photo right), `b` (photo left), and `"none"` (no photo: a large 3D icon fills the photo box with a blob and badge). `build(page_type: str, content: dict, look: dict, brand: dict, variant: str, photo: dict | None, n: int, total: int) -> str` returns full HTML at the type's size (thumbnail 1280x720, others 1080x1350); `class PageError(Exception)` naming the slot or rule; `page_errors(html, page_type, variant, content, brand) -> list[str]` = overflow slots + text/photo region overlap + banned phrases.
  Content keys: hook `{headline, highlight, subline, icon}`; questions `{headline, highlight, cards: [{icon, text, keyword}] x3}`; learn `{headline, highlight, items: [str] (1-4)}`; project `{headline, highlight, title, text, icon}`; skills `{headline, highlight, cards: [{icon, text}] (2-4)}`; cta `{headline, band, subline, cta}`; thumbnail `{title, panels: [{kind, lines}] (1-3)}`.
  Layout per the owner's references: `Nerdit.in` top left (80 px margin), page number top right in `--accent`, headline display font 84-104 px weight 800 with `<mark>` highlights, cards on `--panel` with radius 28 px and soft shadow, wave or blob per look motif, photo blended per Task 6. Thumbnail: rounded title band with the condensed font in capitals, photo on the opposite side of the panels.

- [ ] **Step 1: Failing tests** `test_every_type_and_variant_renders_clean` (sample content; `page_errors == []`; image size right), `test_photo_less_variant_has_no_photo_and_a_big_icon`, `test_long_title_shrinks_or_names_the_slot` (`"Cleaning Capstone: Reconcile a Messy Orders Batch"` in `project.title` passes; a 140-character title raises `PageError` mentioning `title`), `test_three_lessons_give_three_rows` (learn with 3 items renders 3 `check_card`s, no empty row), `test_banned_phrase_in_any_slot_fails`.
- [ ] **Step 2–5:** FAIL, implement, PASS, commit "feat: page types".

### Task 8: Course content, Future Vision brief and CLI

**Files:**
- Create: `engine/brand_studio/content.py`, `engine/brand_studio/cli.py` (console script `brand-studio`)
- Modify: `skills/brand-studio/SKILL.md` (how to: add photos and icons, write the words file, render intro / thumbnail / brief, read problems)
- Test: `engine/tests/test_content.py`, `engine/tests/test_cli.py`, fixture `engine/tests/fixtures/course.json` (5 lessons, one with a `<pre class="nerdit-in">` run block, empty description, title with a trailing space)

**Interfaces:**
- Consumes: everything above.
- Produces: `content.course_facts(course: dict) -> dict` (`title` (stripped), `lessons: [title...]`, `project` (last lesson title), `lesson_count`, `text` (all lesson text, tags stripped), `first_code` (first run block of the first lesson, or None)); `content.intro_pages(facts, words: dict) -> list[tuple[str, dict]]` six `(page_type, content)` pairs, where `words` = `{hook: {headline, highlight, subline}, questions: [{text, keyword}] x3, project_text, skills: [str] x4, icons: {slot: icon_name}}`; `content.truth_errors(facts, words, brand) -> list[str]` (agent text numbers must be in `facts.text`; lesson titles on `learn`/`project` come only from facts; banned phrases); `content.thumbnail_page(facts, key_idea: str) -> tuple[str, dict]` (panels: `first_code` if it has <= 7 lines, else the first 3 lesson titles; plus the key idea); `content.brief_pages(brief: dict, courses: list[dict]) -> list[tuple[str, dict]]` for Future Vision: hook (brief headline), questions-style cards of the featured courses (title, `N lessons`, duration from the course JSON), learn (first lessons of the first course), cta.
  `content.refresh(brand: str, look: dict) -> list[str]` (the learn step: the agent describes a new look from reference images as JSON; it is checked with `checks.look_errors`, refused if its name exists, else written to `brands/<brand>/looks/<name>.json`); when `pick_photo` returns None a page uses variant `"none"`.
  CLI: `brand-studio refresh <brand> <look.json>`; `brand-studio add-photos <brand> <folder> --meta meta.json`; `brand-studio add-icons <brand> <folder>`; `brand-studio prompts <brand> --needs needs.json`; `brand-studio intro <course.json> <words.json> --brand nerdit --out <dir>`; `brand-studio thumbnail <course.json> --key-idea "..." --brand nerdit --out <dir>`; `brand-studio brief <brief.json> --out <dir>`. Each render command: picks a look+variant per page from the brand history (key = course slug or brief name), picks photos (cutouts for slides, scene or cutout for thumbnail), runs `truth_errors` and `page_errors`, prints `PROBLEM ...` lines and exits 1 without writing images when any exist, else writes `01-hook.png` ... and a `contact.jpg`, reserves and marks the looks, marks the photos used.

- [ ] **Step 1: Failing tests** `test_facts_strip_title_and_take_last_lesson_as_project`, `test_empty_description_is_fine`, `test_invented_number_is_refused`, `test_changed_lesson_title_is_impossible` (learn items equal facts lessons), `test_thumbnail_uses_short_code_else_titles`, `test_brief_cards_come_from_course_json`, `test_cli_intro_writes_six_pages_and_contact_sheet` (fixture course + words, tmp home with 2 photos indexed), `test_cli_refuses_and_writes_nothing_on_problems`, `test_refresh_adds_a_valid_look_and_refuses_a_dark_or_duplicate_one`, `test_no_photo_falls_back_to_variant_none`.
- [ ] **Step 2–5:** FAIL, implement, PASS (whole suite), commit "feat: course content, brief and CLI".

### Task 9: Pilot

Not code. Needs the owner's exports in `D:\siddharth\nerdit-backup\nerdit-mainAndPlugin\nerdit-mainAndPlugin\design-pilot\`.

- [ ] Intake: `brand-studio add-photos nerdit C:\Users\siddh\.nerdit-social\assets\gemini-test --meta <meta for st01-st04>`, `add-icons nerdit ~/.nerdit-social/assets/icons/fluent-3d`, same for futurevision.
- [ ] For each pilot course: write `words.json` from its lessons (hook, 3 real questions, project text, 4 skills; English; numbers only from the lessons), run `intro` and `thumbnail`; fix every PROBLEM in the words, never in the checker.
- [ ] Future Vision: `brief.json` (headline; courses: the two pilot courses, Flask Web Development, the FastAPI course), run `brief`.
- [ ] Show the owner the contact sheets and stop (pilot-first). Part 2 plan starts after their OK.
