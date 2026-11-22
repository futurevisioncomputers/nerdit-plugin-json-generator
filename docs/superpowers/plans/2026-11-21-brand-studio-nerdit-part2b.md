# brand-studio × NERDIT, part 2b: every post in the course's look — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teaching carousels, Story cards and LinkedIn cards are drawn by brand-studio pages in the course's one look, Reel overlays take that look's colours, the old per-post style record is retired, and photos are picked by mood.

**Architecture:** brand-studio gains teaching page types (`teaching.py`: code, output, table, quiz, cheat sheet, wrong vs right, picture card) next to the intro types, plus two pack helpers in `api.py` (reserve the course look at plan time, read it back for Reels). NERDIT gets one adapter module (`studio.py`) that maps its slide and card dicts to brand-studio pages and renders them through `api.render_set_to`; `draw.py` keeps only the Reel overlays. The course look replaces `stylebook`'s per-post looks: one look per course, posts vary by arrangement variant.

**Tech Stack:** Python 3.14, Playwright Chromium (HTML → JPEG/PNG), Pillow, pytest (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`).

**Spec:** `docs/superpowers/specs/2026-11-20-brand-studio-design.md` (sections "Page types", "Checks", "NERDIT integration", decisions 2, 3, 4, 8). Previous plan: `docs/superpowers/plans/2026-11-20-brand-studio-nerdit-part2a.md`.

## Global Constraints

- Pages are light (owner, 2026-11-20); code panels may be dark (`codeBg`). Every colour and font comes from the look's CSS variables (`parts.css_vars`); no hex value in a page builder.
- On-screen text is English; Devanagari on a page is refused (NERDIT rule, enforced in `studio.py`, not in brand-studio).
- Teaching words are drawn word for word from the lesson; `packcheck.source_errors` and `plan_text_errors` stay unchanged.
- Never claim a free certificate (`checks.banned_errors` runs on every page).
- Code is drawn at 30 px and output at 26 px and never shrunk (today's `CODE_PX, OUT_PX = 30, 26`); code at most 12 lines of 46 characters; output lines at most 46 characters, more than 14 lines keep the first 13 plus "…"; tables at most 5 columns and 6 rows, cut whole and marked "…".
- Story pages (1080x1920) keep all text and logos inside y 250–1590 (Instagram's top bar and reply bar).
- A render that breaks a rule writes nothing and records nothing (`render_set_to` contract).
- Tests never touch the real `~/.nerdit-social` or `~/.brand-studio` (`BRAND_STUDIO_HOME`, `NERDIT_SOCIAL_HOME` fixtures).
- Nothing is pushed or deployed. Branches: brand-studio `teach-2b` off `master`; plugin `brand-studio-2b` off `main`. Stage only files this plan names (the owner has uncommitted work in the plugin repo).
- Contract tests stay unchanged (spec decision 2): word-for-word, captions, dayplan, cues, reel command, pack checks.

## Decisions (mine unless marked owner)

1. **One look per course for every post** (owner, 2026-11-20: "changing theme per course"). The intro, thumbnail, carousels, Stories, LinkedIn cards and Reel overlays of a course share its brand-studio look; variety inside a course comes from the a/b arrangement variants. Across courses a look never repeats (`pick_course_look`).
2. **stylebook is retired.** `build_pack.py` no longer reads or writes `~/.nerdit-social/style-history.json` (left on disk, never deleted). Its records are not migrated: they belong to per-post looks of the old system. `stylebook.py` and `test_stylebook.py` are removed; `styles/` stays only for `draw.look_for`'s fallback on old plan items.
3. **History keys.** Each NERDIT item renders under key `"<course key>:<item id>"`; the plan reserves under `"<course key>:reserved"`. `looks.family()` makes all of them one course.
4. **Variant per post.** `render_set_to(offset=…)`; NERDIT passes the item's day number (days since `plan["start"]`), so pilot and build draw the same variant and single-page Stories alternate a/b day by day.
5. **Carousel cover and closing slide** become the intro's `hook` and `cta` page types (with a student photo). Cover: headline = the cover hook, subline = course title, badge icon by day from `("laptop", "brain", "rocket", "books", "bullseye")`. Closing: headline `"Keep learning"`, band = course title, subline = the slide's text (default `"Full lesson free at nerdit.in"`), cta bar `"Save this post for later"`.
6. **Mood** (my reading of the owner's "ok" to question 3). Pose words in `index.json` already describe mood; no re-tagging. Pinned tables in Task 1.
7. **Pilot keys.** Picture cards join the pilot (every card is new now).

## Review Focus

1. Text that passes the character guard but overflows in the browser (wide letters, long identifiers) → the build stops with `<item id>: <page>: text does not fit: <slot>` and writes nothing for that item. Test: Task 5 `test_render_problem_names_the_item_and_slot`.
2. No free look left at plan time (every look held by another course) → `plan` prints "No fresh looks left … run the trend refresh" and writes no `pack-plan.json`. Test: Task 6 `test_no_fresh_course_look_stops_plan_and_writes_nothing`.
3. Rebuilding an old pack plan (items carry `style`/`layout`/`theme`, no reservation) → it draws in the course look without error. Test: Task 6 `test_old_plan_items_render_in_the_course_look`.
4. No photo matches the mood, or the course has used every cutout → the mood is dropped, then the page falls back to the 3D icon; never a failure. Test: Task 1 `test_mood_is_dropped_before_the_photo_is` and `test_no_photo_left_gives_none`.
5. Code that would be clipped (too many lines for the box at 30 px) → reported as `text does not fit: code`, never clipped silently. Test: Task 3 `test_code_panel_never_shrinks_and_reports_overflow`.

---

### Task 1: Mood-based photo picking (brand-studio)

**Files:**
- Modify: `brand-studio-plugin/engine/brand_studio/assets.py` (`pick_photo`)
- Modify: `brand-studio-plugin/engine/brand_studio/pages.py` (add `MOOD`)
- Modify: `brand-studio-plugin/engine/brand_studio/api.py` (`photo_for`)
- Test: `brand-studio-plugin/engine/tests/test_assets.py`, `brand-studio-plugin/engine/tests/test_api.py`

**Interfaces:**
- Produces: `pick_photo(brand, *, kind, facing=None, course, exclude=(), mood: tuple[str, ...] = (), avoid: tuple[str, ...] = ()) -> dict | None`; `pages.MOOD: dict[str, tuple[tuple[str, ...], tuple[str, ...]]]` (page type → (mood words, avoid words)).

Pinned values (`pages.py`):

```python
UPBEAT = ("confident", "thumbs up", "fist pump", "smiling", "waving", "presenting", "laughing", "holding", "pointing")
DOWNBEAT = ("puzzled", "scratching", "facepalm", "shrug", "surprised")
MOOD = {"hook": (("thinking", "idea", "looking up", "weighing", "puzzled", "chin"), ()),
        "cta": (UPBEAT, DOWNBEAT), "thumbnail": (UPBEAT, DOWNBEAT)}
```

A word matches when it is a substring of the photo's `pose`, lower-cased.

- [ ] **Step 1: Write the failing tests** (`test_assets.py`; photos added with `add_photos` as the existing tests do)

```python
def test_avoid_drops_a_pose_and_mood_keeps_only_matching_poses(tmp_path):
    _add(tmp_path, {"st10": "puzzled, scratching head", "st25": "calm confident", "st14": "reading a book"})
    assert pick_photo("nerdit", kind="cutout", course="c", avoid=("puzzled",), mood=("confident",))["file"] == "st25.jpg"
    assert pick_photo("nerdit", kind="cutout", course="c", mood=("dancing",)) is None
    assert pick_photo("nerdit", kind="cutout", course="c", avoid=("puzzled", "confident", "reading")) is None

def test_no_photo_left_gives_none(tmp_path):
    _add(tmp_path, {"st25": "calm confident"})
    mark_used("nerdit", "st25.jpg", "c")
    assert pick_photo("nerdit", kind="cutout", course="c") is None
```

(`test_api.py`)

```python
def test_cta_never_picks_a_puzzled_student_and_hook_prefers_thinking(tmp_path):
    # library: st10 puzzled (left), st01 thinking (left), st25 confident (front)
    assert api.photo_for("nerdit", "c", "cta", "a", [])["file"] == "st25.jpg"
    assert api.photo_for("nerdit", "c", "hook", "a", [])["file"] == "st01.jpg"

def test_mood_is_dropped_before_the_photo_is(tmp_path):
    # library: only st14 "reading a book" (left)
    assert api.photo_for("nerdit", "c", "hook", "a", [])["file"] == "st14.jpg"
```

- [ ] **Step 2: Run them; expect FAIL** (`TypeError: pick_photo() got an unexpected keyword argument 'avoid'`)

Run: `cd brand-studio-plugin/engine && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_assets.py tests/test_api.py`

- [ ] **Step 3: Implement.** `pick_photo` filters out `avoid` matches always, and keeps only `mood` matches when `mood` is non-empty; ranking unchanged (least used, then file name). `photo_for` tries `for words in (mood, ()): for facing in (want, "front", None)`, always passing the page type's `avoid`; page types without a `MOOD` entry pass `()`.

- [ ] **Step 4: Run the whole brand-studio suite; expect all pass** (97 + 4)

Run: `cd brand-studio-plugin/engine && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`

- [ ] **Step 5: Commit** (`git checkout -b teach-2b` first)

```bash
git add engine/brand_studio/assets.py engine/brand_studio/pages.py engine/brand_studio/api.py engine/tests/test_assets.py engine/tests/test_api.py
git commit -m "feat: photos picked by mood (the hook a thinking student, the call to action never a puzzled one)"
```

---

### Task 2: Pack helpers in the API (brand-studio)

**Files:**
- Modify: `brand-studio-plugin/engine/brand_studio/api.py`
- Test: `brand-studio-plugin/engine/tests/test_api.py`

**Interfaces:**
- Consumes: `looks.pick_course_look`, `reserve_looks`, `prune_history`, `family`.
- Produces:
  - `render_set_to(..., offset: int = 0)`: page i uses `VARIANTS[(i - 1 + offset) % 2]`.
  - `reserve_course_look(brand_id: str, key: str, marker: Path) -> tuple[str | None, str | None]`: `(look name, None)` or `(None, problem)`. Writes two unbuilt entries (one per variant) under key `f"{family(key)}:reserved"`, item id `"reserved"`, with `marker`. Calling again for the same course returns the same look.
  - `course_look(brand_id: str, key: str) -> dict | None`: the look dict the course's history entries hold (most used), `None` when the course has none.
  - Private `_course_look_name(history, looks, key) -> str` (raises `NoFreshLooks`), shared by `render_set_to` and `reserve_course_look` (today's inline `own`/`pick_course_look` logic).

- [ ] **Step 1: Write the failing tests**

```python
QUESTIONS = intro_pages(facts(), WORDS, load_brand("nerdit"))[1]      # ("questions", {...}): one photo-less page
variants = lambda key: [e["variant"] for e in load_history(history_path("nerdit"))["looks"] if e["key"] == key]

def test_offset_shifts_the_variant(tmp_path):
    icons(tmp_path)
    api.render_set_to("nerdit", "c:x", [QUESTIONS], tmp_path / "x", ["p"])
    api.render_set_to("nerdit", "c:y", [QUESTIONS], tmp_path / "y", ["p"], offset=1)
    assert variants("c:x") == ["a"] and variants("c:y") == ["b"]

def test_reserve_course_look_is_stable_and_shared_with_renders(tmp_path):
    icons(tmp_path)
    marker = tmp_path / "pack-plan.json"
    marker.write_text("{}")
    name, problem = api.reserve_course_look("nerdit", "c", marker)
    assert problem is None and api.reserve_course_look("nerdit", "c", marker) == (name, None)
    assert variants("c:reserved") == ["a", "b"]
    api.render_set_to("nerdit", "c:d03-carousel", [QUESTIONS], tmp_path / "o", ["p1"])
    assert {e["look"] for e in load_history(history_path("nerdit"))["looks"]} == {name}
    assert api.course_look("nerdit", "c")["name"] == name

def test_reserve_course_look_reports_no_fresh_looks(tmp_path):
    held = [{"look": l["name"], "variant": v, "key": f"o{i}", "itemId": "x", "built": True}
            for i, l in enumerate(load_looks("nerdit")) for v in ("a", "b")]
    save_history(history_path("nerdit"), {"looks": held})
    name, problem = api.reserve_course_look("nerdit", "c", tmp_path / "m")
    assert name is None and "fresh" in problem

def test_course_look_is_none_for_an_unknown_course():
    assert api.course_look("nerdit", "nobody") is None
```

- [ ] **Step 2: Run; expect FAIL** (`AttributeError: module 'brand_studio.api' has no attribute 'reserve_course_look'`)

- [ ] **Step 3: Implement** the three functions in `api.py`; `render_set_to` uses `_course_look_name`.

- [ ] **Step 4: Run the whole brand-studio suite; expect all pass**

- [ ] **Step 5: Commit**

```bash
git add engine/brand_studio/api.py engine/tests/test_api.py
git commit -m "feat: reserve a course's look at plan time, read it back, and shift variants per post"
```

---

### Task 3: Teaching slide pages (brand-studio)

**Files:**
- Create: `brand-studio-plugin/engine/brand_studio/teaching.py`
- Modify: `brand-studio-plugin/engine/brand_studio/parts.py` (add `document`, `wave(corner, height=1350)`)
- Modify: `brand-studio-plugin/engine/brand_studio/pages.py` (register types, public `guard`, dispatch, `_strings` skips `svg`/`css`/`img`)
- Modify: `brand-studio-plugin/engine/brand_studio/checks.py` (add `fits`)
- Test: `brand-studio-plugin/engine/tests/test_teaching.py`

**Interfaces:**
- Produces:
  - `checks.fits(text: str, per_line: int, lines: int) -> bool`: greedy word wrap, a word longer than `per_line` fails (port of NERDIT `draw.fits`, same behaviour).
  - `parts.document(look: dict, size: tuple[int, int], body: str, extra_css: str = "", bg: str | None = None, bg2: str | None = None) -> str`: the full page (css vars, base css, gradient background, `FIT_JS`); `pages.build` uses it too.
  - `teaching.TYPES = ("idea", "diagram", "quiz", "answer", "predict-q", "predict-a", "wrong", "right", "data", "code", "output")`, all 1080x1350.
  - `teaching.SLOTS[type]`: field → `int` (most characters) or `(per_line, lines)` (word wrap), pinned below.
  - `teaching.build(page_type, content, look, brand, variant, n, total) -> str`; `teaching.highlight(code, lang) -> str` (port of `draw.highlight`, same token classes `tk-kw`, `tk-str`, `tk-num`, `tk-com`, coloured from look variables); `teaching.code_panel(code: str, lang: str, edge: str | None = None) -> str` and `teaching.output_panel(text: str) -> str` (the `.fit` panels described below).
  - `pages.guard(page_type: str, content: dict) -> list[str]`: every pre-render problem as `"slot <name>: …"` (code, output and table rules included); `pages.build` raises `PageError` with the first.
  - `pages.PAGE_TYPES`, `SIZE`, `REGIONS` include the teaching types (`REGIONS[t][v] = {"text": [content box], "photo": None}` for v in a, b, none).

Content shapes (NERDIT's slide dict without `kind`) and pinned slot rules:

| type | content | rules |
|---|---|---|
| idea | `text`, `title` | text (22, 6); title 60 |
| diagram | `label`, `svg`, `css` | label (40, 2) |
| quiz | `question`, `options` (4) | question (34, 4); each option (34, 2) |
| answer | `question`, `answer` | question (34, 4); answer (34, 2) |
| predict-q | `question` (may be empty: shows "What does this print?"), `code`, `lang` | question (34, 4); code rule |
| predict-a | `output`, `outTag` (default "Output"), `explanation` | output rule; explanation (40, 5) |
| wrong / right | `head`, `code`, `lang`, `reason` | head (34, 2); code rule; reason (40, 4) |
| data | `headers`, `rows`, `caption`, `sample` | table rule; caption (46, 3) |
| code | `code`, `lang` | code rule |
| output | `output`, `outTag`, `sample` | output rule |

Labels stay today's copy: "Guess the output", "Answer", "&#10007; Wrong", "&#10003; Right", "Meet the data", "You type", "Quick check", "Answer on the next slide &rarr;", "Comment your answer, then swipe &rarr;", and `"Sample data from the course"` only when `sample` is true. Wrong/right marks use fixed red `#ef4444` / green `#22c55e` (meaning colours, the one exception to tokens). Code and output panels are `.fit` elements with `data-min` equal to their font size (30 / 26) and `data-slot="code"` / `"output"`, so they never shrink and an overflow is reported by `page_errors`. Variant b mirrors the decoration (wave corner, accent bar side) of a; the text box does not move.

- [ ] **Step 1: Write the failing tests** (`test_teaching.py`, look = `load_looks("nerdit")[0]`, render with `render.overflows` / `pages.page_errors`)

```python
def test_fits_wraps_on_words():
    assert checks.fits("one two three", 7, 2) and not checks.fits("one two three", 7, 1) and not checks.fits("x" * 8, 7, 3)

@pytest.mark.parametrize("page_type", teaching.TYPES)
def test_every_teaching_type_renders_without_overflow_in_both_variants(page_type, studio):
    for v in ("a", "b"):
        html = pages.build(page_type, SAMPLES[page_type], studio["look"], studio["brand"], v, None, 2, 8)
        assert pages.page_errors(html, page_type, v, SAMPLES[page_type], studio["brand"]) == []

def test_variants_differ(studio):
    build = lambda v: pages.build("idea", SAMPLES["idea"], studio["look"], studio["brand"], v, None, 2, 8)
    assert build("a") != build("b")

def test_builders_use_no_hex_but_the_meaning_colours():
    assert set(re.findall(r"#[0-9a-fA-F]{6}\b", Path(teaching.__file__).read_text(encoding="utf-8"))) <= {"#ef4444", "#22c55e"}

def test_teaching_text_is_on_the_page_word_for_word(studio):
    html = pages.build("wrong", SAMPLES["wrong"], studio["look"], studio["brand"], "a", None, 2, 8)
    text = html_lib.unescape(re.sub(r"<[^>]+>", "", html))
    assert text.count(SAMPLES["wrong"]["head"]) == 1 and SAMPLES["wrong"]["code"].split("\n")[0] in text

def test_guard_pins_todays_limits():
    assert pages.guard("idea", {"text": "w " * 70, "title": ""}) and pages.guard("idea", {"text": "Short idea.", "title": ""}) == []
    assert any("code" in e for e in pages.guard("code", {"code": "\n".join(["x"] * 13), "lang": "python"}))
    assert any("code" in e for e in pages.guard("code", {"code": "x" * 47, "lang": "python"}))
    assert any("output" in e for e in pages.guard("output", {"output": "y" * 47, "outTag": "", "sample": False}))

def test_long_output_and_big_tables_are_cut_and_marked(studio):
    html = pages.build("output", {"output": "\n".join(str(i) for i in range(20)), "outTag": "", "sample": False}, ...)
    assert "…" in html_text(html) and "19" not in html_text(html)
    html = pages.build("data", {"headers": list("ABCDEFG"), "rows": [list("1234567")] * 9, "caption": "", "sample": True}, ...)
    assert html.count("<th") == 6 and "Sample data from the course" in html

def test_code_panel_never_shrinks_and_reports_overflow(studio):
    panel = teaching.code_panel("\n".join(["a = 1"] * 12), "python")
    assert 'data-min="30"' in panel and 'data-slot="code"' in panel
    squeezed = parts.document(studio["look"], (1080, 1350), f'<div class="abs" style="left:0;top:0;width:900px;height:200px">{panel}</div>')
    assert render.overflows(squeezed, 1080, 1350) == ["code"]
```

`SAMPLES` holds one realistic content dict per type, each at its slot limits (longest legal text), including a 12x46 code block for `wrong` and `predict-q`.

- [ ] **Step 2: Run; expect FAIL** (`ModuleNotFoundError: No module named 'brand_studio.teaching'`)

- [ ] **Step 3: Implement** `checks.fits`, `parts.document`, `parts.wave(corner, height=1350)` (the bottom-right wave follows the page height), `teaching.py`, and the `pages.py` registration, `guard` and dispatch (`if page_type in teaching.TYPES: return teaching.build(...)` after `_guard`). The diagram page puts `content["css"]` into the page's `<style>` and the SVG on a white panel.

- [ ] **Step 4: Run the whole brand-studio suite; expect all pass.** Then look at one contact sheet of all 11 types, both variants (`cli._contact`), and fix anything clipped or crowded by eye before committing (tests passed before on clipped pages in part 1).

- [ ] **Step 5: Commit**

```bash
git add engine/brand_studio/teaching.py engine/brand_studio/parts.py engine/brand_studio/pages.py engine/brand_studio/checks.py engine/tests/test_teaching.py
git commit -m "feat: teaching slide pages (guess the output, wrong vs right, data, code, output, idea, diagram, quiz) in the course look"
```

---

### Task 4: Story and LinkedIn card pages (brand-studio)

**Files:**
- Modify: `brand-studio-plugin/engine/brand_studio/teaching.py`
- Test: `brand-studio-plugin/engine/tests/test_teaching.py`

**Interfaces:**
- Produces: card types `"cheat"`, `"compare"`, `"picture"` (1080x1350) and `"cheat-story"`, `"picture-story"` (1080x1920), added to `teaching.TYPES` and `SIZE`.

| type | content | rules |
|---|---|---|
| cheat, cheat-story | `rows`: list of `[term, what, example]` (example may be missing) | at most 6 rows (story) / 4 (card); term (40, 1); what (52, 2); example at most 56 characters, drawn at 26 px, never shrunk |
| compare | `bad`, `good`: each `head`, `code`, `lang`, `reason` | head (40, 2); code rule; reason (44, 3); both code blocks together at most 12 lines |
| picture, picture-story | `title`, `course`, `topics` (up to 4), `picture`: `{"svg", "css"}` or `{"img": path}` or `None` | title (26, 3); each topic (40, 2) |

Card copy stays today's: titles "Cheat sheet" and "Wrong vs right", "What you'll learn", "Save this · nerdit.in" chip, and the brand logo (`brand["logo"]`) on every card.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("page_type", ["cheat", "compare", "picture", "cheat-story", "picture-story"])
def test_cards_render_without_overflow_in_both_variants(page_type, studio):
    for v in ("a", "b"):
        html = pages.build(page_type, SAMPLES[page_type], studio["look"], studio["brand"], v, None, 1, 1)
        assert pages.page_errors(html, page_type, v, SAMPLES[page_type], studio["brand"]) == []

def test_story_cards_keep_text_inside_the_safe_area(studio):
    for t in ("cheat-story", "picture-story"):
        assert all(250 <= y and y + h <= 1590 for _, y, _, h in pages.REGIONS[t]["a"]["text"])

def test_compare_refuses_more_than_12_code_lines_in_all():
    six = "\n".join(["x = 1"] * 7)
    assert any("12" in e for e in pages.guard("compare", {"bad": {"head": "h", "code": six, "lang": "", "reason": ""},
                                                          "good": {"head": "h", "code": six, "lang": "", "reason": ""}}))

def test_cheat_story_takes_6_rows_and_card_4():
    rows = [["term", "what it does", "x()"]] * 7
    assert pages.guard("cheat-story", {"rows": rows}) and pages.guard("cheat-story", {"rows": rows[:6]}) == []
    assert pages.guard("cheat", {"rows": rows[:5]}) and pages.guard("cheat", {"rows": rows[:4]}) == []
```

- [ ] **Step 2: Run; expect FAIL** (`KeyError: 'cheat'`)

- [ ] **Step 3: Implement** the five card builders in `teaching.py` (the picture card without a picture moves its text up, as today).

- [ ] **Step 4: Run the whole suite; expect all pass; check one contact sheet by eye** (both sizes, both variants).

- [ ] **Step 5: Commit**

```bash
git add engine/brand_studio/teaching.py engine/tests/test_teaching.py
git commit -m "feat: cheat sheet, wrong vs right and picture cards for Stories and LinkedIn in the course look"
```

Also update `brand-studio-plugin/skills/brand-studio/SKILL.md` in this commit: the teaching page types, their content shapes, `guard`, mood picking, `reserve_course_look` / `course_look` / `offset`.

---

### Task 5: NERDIT draws carousels and cards through brand-studio

**Files:**
- Create: `nerdit-plugin-json-generator/skills/nerdit-social-posts/scripts/studio.py`
- Modify: `…/scripts/slides.py` (`make_carousel`, `make_card`), `…/scripts/teach.py` (probes), `…/scripts/intro.py` (uses `studio.py`), `…/scripts/build_pack.py` (`render_items`, `_pilot_key`), `…/scripts/draw.py` (slide and card code removed)
- Modify tests: `…/scripts/test_draw.py` (slide/card tests removed: they now live in brand-studio's `test_teaching.py`), `…/scripts/test_slides.py`, `…/scripts/test_teach.py`, `…/scripts/test_pack.py`, `…/scripts/conftest.py` (icon fixture)
- Create test: `…/scripts/test_studio.py`

**Interfaces:**
- Consumes: Task 2 (`render_set_to(offset=)`), Tasks 3–4 (page types, `pages.guard`).
- Produces (`studio.py`):
  - `BRAND = "nerdit"`, `INSTALL_HINT` (moved from `intro.py`), `studio() -> (api, brands, content, pages)` (SystemExit with the hint when brand-studio is missing).
  - `course_key(src: dict) -> str`: the course JSON's `slug`, else `src["name"]` (today's intro key).
  - `slide_page(slide: dict, course: str, day: int) -> tuple[str, dict]`: `cover` → `("hook", {"headline": hook, "highlight": [], "subline": course, "icon": COVER_ICONS[day % 5]})`; `cta` → `("cta", {"headline": "Keep learning", "highlight": [], "band": course, "subline": slide text or "Full lesson free at nerdit.in", "cta": "Save this post for later"})`; `diagram` adds `"css": draw.figure_css()`; any other kind → `(kind, slide without "kind")`.
  - `card_page(card: dict, fmt: str) -> tuple[str, dict]`: `cheat` → `"cheat-story"` when `fmt == "story"` else `"cheat"`; `compare` → `"compare"`; a picture card spec → `"picture-story"` / `"picture"` (picture `svg` gets `css`).
  - `fit_errors(page_list: list[tuple[str, dict]]) -> list[str]`: `pages.guard` problems plus Devanagari on any drawn string (`"<page>: <field> must be English on screen"`).
  - `render(src, item, page_list, out_dir, marker, day) -> list[Path]`: `api.render_set_to(BRAND, f"{course_key(src)}:{item['id']}", page_list, out_dir, [f"{item['id']}-{i:02d}" …], marker=marker, offset=day, jpeg=True)`; a single-page card is named `f"{item['id']}"`; problems → `SystemExit("\n".join(f"{item['id']}: {p}" …))`.
  - `day_of(plan: dict, item: dict) -> int`: days from `plan["start"]` to `item["date"]`.
- Changed signatures: `slides.make_carousel(src, item, slides, out_dir, marker: Path, day: int = 0) -> list[Path]`; `slides.make_card(src, item, height, out_dir, marker: Path, day: int = 0) -> Path`. `teach._drawable(slides)` returns `not studio.fit_errors([studio.slide_page(s, "", 0) for s in slides])`; the cheat and compare probes use `studio.fit_errors([studio.card_page(card, fmt)])`.
- `draw.py` keeps: Reel boxes and constants (`REEL_W`, `REEL_H`, `SLIDE_W`, `SLIDE_H`, `HOOK_CHARS`, `HOOK_LINES`, `STYLE_DIR`), `DrawError`, `fits`, `DEVANAGARI`, `_english`, `_fit`, `style_from_theme`, `look_for`, `resolve`, `reel_frame`, `reel_layers`, `cue_html`, `cta_html`, `cover_html`, `figure_css`, page helpers they use, `shoot`. Everything else goes.

- [ ] **Step 1: Write the failing tests** (`test_studio.py`; conftest gains an autouse-free `studio_icons` fixture that adds the seven test icons, as `brand-studio`'s `test_api.icons` does)

```python
def test_cover_and_cta_become_photo_pages():
    assert studio.slide_page({"kind": "cover", "hook": "Split before you fit", "course": "C"}, "C", 7)[0] == "hook"
    t, c = studio.slide_page({"kind": "cta", "text": "Full lesson free at nerdit.in"}, "C", 0)
    assert t == "cta" and c["band"] == "C" and c["subline"] == "Full lesson free at nerdit.in"

def test_card_types_follow_the_format():
    assert studio.card_page({"kind": "cheat", "rows": []}, "story")[0] == "cheat-story"
    assert studio.card_page({"kind": "cheat", "rows": []}, "feed")[0] == "cheat"

def test_devanagari_is_refused_before_drawing():
    assert any("English" in e for e in studio.fit_errors([("idea", {"text": "यह गलत है", "title": ""})]))

def test_carousel_renders_named_jpegs_in_the_course_look(workdir, studio_icons, tmp_path):
    files = slides.make_carousel(src, item, item["slides"], tmp_path, tmp_path / "pack-plan.json", 2)
    assert [f.name for f in files] == [f"{item['id']}-{i:02d}.jpg" for i in range(1, len(item["slides"]) + 1)]
    entries = load_history(history_path("nerdit"))["looks"]
    assert {e["key"] for e in entries} == {f"{studio.course_key(src)}:{item['id']}"} and len({e["look"] for e in entries}) == 1
    assert entries[0]["variant"] == "a" and entries[1]["variant"] == "b"     # day 2: slide 1 starts at variant a

def test_render_problem_names_the_item_and_slot(monkeypatch, workdir, tmp_path):
    monkeypatch.setattr(api, "render_set_to", lambda *a, **k: ([], ["03-idea: text does not fit: text"]))
    with pytest.raises(SystemExit, match="d03-carousel: 03-idea: text does not fit: text"):
        slides.make_carousel(src, item, item["slides"], tmp_path, tmp_path / "pack-plan.json", 2)
```

In `test_pack.py`: `pilot_items` now includes the first picture Story and the first picture feed card (`test_pilot_takes_one_of_each_kind` updated: picture cards appear as `("story", "picture")` / `("feed", "picture")`).

- [ ] **Step 2: Run; expect FAIL** (`ModuleNotFoundError: No module named 'studio'`)

Run: `cd nerdit-plugin-json-generator/skills/nerdit-social-posts/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_studio.py`

- [ ] **Step 3: Implement** `studio.py`, then switch `slides.py`, `teach.py`, `intro.py` (`render_intro` uses `studio.course_key`, `studio.studio()`), `render_items` (passes `marker` and `studio.day_of(plan, it)`), `_pilot_key` (`(fmt, card kind or "picture")`), and strip `draw.py`. Remove the `test_draw.py` tests of removed functions; keep its Reel tests.

- [ ] **Step 4: Run all three NERDIT suites; expect all pass** (social count changes by the moved tests; story-video 108 unchanged)

Run: `cd …/nerdit-social-posts/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` and the same in `…/nerdit-story-video/scripts`.

- [ ] **Step 5: Commit** (`git checkout -b brand-studio-2b` first; stage only these files)

```bash
git add skills/nerdit-social-posts/scripts/{studio,slides,teach,intro,build_pack,draw,conftest,test_studio,test_draw,test_slides,test_teach,test_pack}.py
git commit -m "feat(social-posts): carousels, Stories and LinkedIn cards drawn by brand-studio in the course look"
```

---

### Task 6: Course look at plan time, Reels in the course look, stylebook retired

**Files:**
- Modify: `…/scripts/build_pack.py` (`plan_pack`, `main` plan and build, `render_items`), `…/scripts/reel.py` (`make_reel`), `…/scripts/draw.py` (`reel_look`), `…/scripts/studio.py` (`reserve`, `reel_look`)
- Delete: `…/scripts/stylebook.py`, `…/scripts/test_stylebook.py`
- Modify: `…/skills/nerdit-social-posts/SKILL.md` (step 0, "Teaching posts and looks", "What the scripts do")
- Test: `…/scripts/test_pack.py`, `…/scripts/test_reel.py`, `…/scripts/test_studio.py`

**Interfaces:**
- Consumes: Task 2 `reserve_course_look`, `course_look`.
- Produces:
  - `draw.reel_look(look: dict) -> dict`: a brand-studio look as a draw style: `{"name", "inspiration": "", "palette": <bg, bg2, panel, ink, muted, accent, chip, chipInk, codeBg, codeInk>, "fonts": {"head": display, "body": body, "code": code}, "background": "gradient", "motif": "none", "layout": "stack"}`.
  - `studio.reserve(src: dict, marker: Path) -> tuple[str | None, str | None]` → `api.reserve_course_look(BRAND, course_key(src), marker)`.
  - `studio.reel_look(src: dict, marker: Path) -> dict`: `reserve` then `draw.reel_look(api.course_look(...))`; a problem → SystemExit.
  - `reel.make_reel(src, item, hook, out_dir, tl=None, pad=True, look: dict | None = None)`: `look or draw.look_for(item)`.
  - `plan_pack(workdir, start, days, url, course_id=None, pad=True) -> dict` (the `history` parameter and `assign_looks` are gone; items keep dayplan's fields).
- `main` plan order: build the plan → refuse an existing `pack-plan.json` without `--force` → `studio.reserve(src, target)`; on a problem print `No fresh looks left ({problem}): run the trend refresh (SKILL.md step 0) to add a brand-studio look.` and return 1 without writing → write the plan → print `course look: <name>`.
- Build: no stylebook calls; `render_items` gets `look = studio.reel_look(src, marker)` once when the items include a Reel and passes it to `make_reel`.

- [ ] **Step 1: Write the failing tests**

```python
def test_plan_reserves_one_course_look_and_items_carry_no_style(tmp_path, workdir):
    run_plan(workdir)
    entries = studio_history()["looks"]
    assert {e["key"] for e in entries} == {f"{SLUG}:reserved"} and len({e["look"] for e in entries}) == 1
    assert not any("style" in i for i in read_plan(workdir)["items"])

def test_no_fresh_course_look_stops_plan_and_writes_nothing(tmp_path, workdir, capsys):
    hold_every_look_for_other_courses()
    assert build_pack.main(["plan", str(workdir), "--url", URL]) == 1
    assert "No fresh looks left" in capsys.readouterr().out and not list(workdir.glob("social-pack/*/pack-plan.json"))

def test_two_courses_never_share_a_look(tmp_path, workdir, second_workdir):
    run_plan(workdir)
    run_plan(second_workdir)                       # a copy of the demo course with another slug
    looks = {e["key"]: e["look"] for e in studio_history()["looks"]}
    assert len(set(looks.values())) == 2

def test_old_plan_items_render_in_the_course_look(workdir, studio_icons, tmp_path):
    item = {**carousel_item, "style": "navy", "layout": "bignumber", "theme": "navy"}
    slides.make_carousel(src, item, item["slides"], tmp_path, marker, 0)
    assert len({e["look"] for e in studio_history()["looks"]}) == 1

def test_reel_look_takes_the_course_palette_and_stays_light():
    bs = load_looks("nerdit")[0]
    rl = draw.reel_look(bs)
    assert rl["palette"]["bg"] == bs["palette"]["bg"] and rl["fonts"]["head"] == bs["fonts"]["display"]
    assert "front" in draw.reel_layers("Split before you fit", rl)          # the Reel frame draws with it
```

Rewrite the four stylebook look tests in `test_pack.py` (lines 196–232 today) as the first three above; drop `"stylebook"` from the module list at line 248; remove `history=` from the `plan_pack` calls in `test_pack.py` and `test_intro.py`.

- [ ] **Step 2: Run; expect FAIL** (`AttributeError: module 'draw' has no attribute 'reel_look'`, and the plan tests fail on `style` fields)

- [ ] **Step 3: Implement**; delete `stylebook.py` and `test_stylebook.py` with `git rm`.

- [ ] **Step 4: Run all three NERDIT suites and brand-studio's; expect all pass**

- [ ] **Step 5: Update SKILL.md** (nerdit-social-posts):
  - Step 0 becomes: when `plan` says "No fresh looks left" (each course takes one look; 13 looks today), write new looks for brand-studio from `~/.nerdit-social/inspiration/` and trend round-ups (general ideas only; light pages) and add each with `brand-studio refresh nerdit <look.json>`; it prints `checks passed` or the problems.
  - "Teaching posts and looks": every post of a course is drawn in the course's one brand-studio look (the same as its intro and thumbnail); posts alternate the a/b arrangements; carousel covers and closing slides carry a student photo picked by mood. The record is `~/.brand-studio/nerdit/history.json` (do not edit). `~/.nerdit-social/style-history.json` is no longer used.
  - "What the scripts do": `draw.py` draws the Reel overlays; `studio.py` maps slides and cards to brand-studio pages.

- [ ] **Step 6: Commit**

```bash
git rm skills/nerdit-social-posts/scripts/stylebook.py skills/nerdit-social-posts/scripts/test_stylebook.py
git add skills/nerdit-social-posts/scripts/{build_pack,reel,draw,studio,test_pack,test_reel,test_studio,test_intro}.py skills/nerdit-social-posts/SKILL.md
git commit -m "feat(social-posts): one course look from plan to Reel; the per-post style record is retired"
```

---

### Task 7: Pilot

Not code.

- [ ] Rename `classification-course/work/social-pack/supervised-learning-classification-2026-11-22/pilot/OWNER_OK` to `OWNER_OK-2a` (the new look needs a fresh OK; nothing is deleted).
- [ ] `python scripts/build_pack.py plan … --force` for the Classification workdir (live URL as before), refill the intro words and the pilot items' captions from the old plan, then `build_pack.py pilot <packdir>`; checks pass.
- [ ] Contact sheet: intro (6), one teaching carousel, the Story, one LinkedIn card. Look at every page at full size for clipping, crowding and photo mood before showing it.
- [ ] Show the owner; stop for their OK (pilot-first). Then merge both branches locally (no push) as in part 2a.

Known and deferred (from part 2a, unchanged here): a pilot render marks its course look and photos used, so a rejected pilot's photos do not come back for that course.
