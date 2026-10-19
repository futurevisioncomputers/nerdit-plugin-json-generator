# Lesson visuals for every course — design

Date: 2026-10-19. Status: approved to plan. The owner skipped questions and widened the scope on
the same day: "all courses include some images where it need … python based or sql or other
marketing and ai learning courses also".

## Why

NerdIT runs about 75 courses: Excel and Power BI, SQL and Python, web development, design
tools (WordPress, Bootstrap), machine learning, Generative AI and Digital Marketing. A learner
understands a process faster with a picture of it, but today only some lessons get one.

What exists today (plugin 3.4.0):

- **Concept figures (vector).** The v11 writer draws one main figure per concept section from
  15 SVG templates (CORE.md §7 Visual Map, figures.md). This works for every subject, but
  only v11 courses have it.
- **Illustrations (AI images).** The illustrator plans scene and analogy images. It runs as a
  separate, manual step after the course is built, so most courses never get them.
- **Screens (pictures of an app).** There is nothing for these. The owner hand-made 17 Excel
  screen images for the Excel course, lessons 01–04. Checking the live course on 2026-10-19
  found three problems:
  - One image shows an "Operations" department the lesson never mentions.
  - Text is about 4 px tall on a 390 px phone.
  - There are no captions, and the alt texts are file names.

The owner wants the plugin to make these visuals **together with the lesson content**, in sync
with it, for **every course where a visual helps**, using one rule:

> If the process is complex to explain, use image A. If it is simple, use image B.

- **A — drawn (vector SVG):**
  - Made by the plugin from the lesson's own data.
  - Exact, readable on a phone, and checked by script.
- **B — image (raster):**
  - A realistic AI-generated image, built from a brief the plugin writes from the same lesson.
  - Generated outside the plugin, then checked against that brief.

## Goals

1. **Every course, every preset.** The same rule and checks work for all five presets:
   Code, Spreadsheet, Visual, Quantitative and Conversational (CORE.md §2b).
2. **Where it is needed, not everywhere.** A lesson gets a visual where it teaches:
   - a click-path in an app (a **screen**);
   - a process or structure (a **concept figure**);
   - an idea best grasped through a familiar scene (a **scene**).

   A check warns when a section teaches a click-path with no screen. The existing v11 check
   already warns when a concept section has no main visual.
3. **Made together.** The writer describes each visual once, at the place it goes, inside the
   lesson. A visuals are drawn during the generation run. B briefs reach the illustrator in the
   same run, with no hand-written plan.
4. **Kept in sync.** A gate fails a lesson whose drawn screen no longer matches its spec or data.
   Every word in a screen must come from the lesson. Editing a lesson marks its B images for
   regeneration.
5. **The owner's rule in one place.** One function decides A or B for screens. The Visual Map
   states the same rule for concepts. A writer override needs a reason, which QA reviews.

## Non-goals

- Refreshing all ~75 live courses in this plan. The pilot proves the process on four courses.
  The rollout is lesson updates, scheduled by the owner course by course afterwards.
- Fixing the third-party `claude-image-generation` plugin, which fails on Windows paths. B works
  with any image tool that saves into `<images>/incoming/`.
- New formula functions in the Excel engine, or new result engines for other apps.
- Animated or interactive walkthroughs.
- Publishing. The pilot ends with a local preview; import is a separate, approved step.

## Anti-goals (failure even if it "works")

- A picture that shows a value, name, button or step the lesson does not contain.
- Text a learner cannot read on a 390 px phone.
- The same facts shown twice. A screen must not repeat a run line or figure next to it
  (figures.md R13).
- Real logos or brand marks. App and button names as plain text are fine; logos are not.
- Decorative pictures. The caption-first test (CORE.md §7) still decides whether a visual earns
  its place.

## Three kinds of visual, one rule

| Kind | What it shows | A (complex) | B (simple) |
|---|---|---|---|
| **Screen** | A click-path in an app: Excel, Power BI, VS Code, a terminal, WordPress, an ads manager, an AI chat tool | Drawn by `render_screens.py` from a screen spec | AI image from a brief written from the same spec |
| **Concept** | A process, structure or relationship | Writer-drawn figure template (figures.md §1–15, unchanged) | — |
| **Scene** | One simple idea through a familiar real-world scene or analogy | — | AI image from a scene spec |

### What counts as complex

**Screens** use a script rule, `screen_kind(spec)`. A screen is **A** when any of these hold:

- it has more than 3 steps;
- it fills 2 or more fields (a dialog or form);
- it shows a computed result.

Otherwise it is **B**: up to 3 clicks or keys on one screen.

**Concepts and scenes** follow the Visual Map, which states the same rule:

- **A concept figure**, when the idea has parts, an order or exact values (complex).
- **A scene**, when one idea becomes obvious from a familiar situation (simple). A section's
  main visual may be a scene.
- Never both for the same fact (R13).

## The screen spec

One JSON block per walkthrough, written by the writer at the place the picture goes:

```html
<script type="application/json" class="nerdit-screen" data-grid="xl-staff">
{"id": "xlookup-city", "app": "Excel", "layout": "sheet",
 "goal": "Find Isha's city with XLOOKUP",
 "view": {"columns": ["B", "D", "H"], "rows": [1, 7], "active": "H3"},
 "steps": [{"do": "select", "target": "H3"},
           {"do": "type", "target": "H3", "text": "=XLOOKUP(\"Isha\",B2:B7,D2:D7)"},
           {"do": "result", "target": "H3"}],
 "image": "auto"}
</script>
```

- **`app`:** the app's plain name, as the lesson writes it ("Excel", "VS Code", "Meta Ads
  Manager").
- **`layout`:** one of three drawing kits.
  - **`sheet`:** a spreadsheet window. Cells come from the lesson's demo-data block
    (`data-grid`). Computed results come from the plugin's Excel engine, the same one the Try It
    uses.
  - **`editor`:** a code editor, notebook or terminal. It shows `lines` (code or commands) and
    `output` lines.
  - **`app`:** any other app window. It shows a menu path and a panel of items: `field` (label
    and value), `button`, `message` (who and text, for chat tools) and `item` (a list row).
- **`steps`** become the numbered markers ①②③ and the reading list. Kinds:

  | Kind | What it does |
  |---|---|
  | `select` | pick a cell or a panel item |
  | `click` | `path`: a menu, tab or button path |
  | `type` | text or a formula into a target |
  | `set` | a field to a value |
  | `key` | a shortcut |
  | `result` | `sheet` only: the engine's value for a typed formula |

- **`dialog`** (optional, any layout): `{"title", "fields": [{"label", "value"}]}`.
- **`image`:** `"auto"`, or `"A"` / `"B"` with a `why`.
- **B specs** also carry the teaching text the illustrator needs: `alt`, `takeaway`,
  `misconception` and `check` (`question`, `answer`, `reasoning`).

### The sync rule

Every word drawn in a screen must come from the lesson. Grid cells and engine results come from
the lesson's data. Everything else must appear in the lesson's visible text:

- menu paths;
- labels, values and code lines;
- messages.

The only exceptions are a short known-label list per app (Excel's ribbon tabs at first). This
makes "a value the lesson never mentions" impossible.

## The scene spec

One JSON block per scene image, written by the writer where the image goes:

```html
<script type="application/json" class="nerdit-scene">
{"id": "shop-bill", "subject": "A shopkeeper copying one bill into two notebooks, one per customer",
 "alt": "...", "caption": "...", "takeaway": "...", "misconception": "...",
 "check": {"question": "...", "answer": "...", "reasoning": "..."}}
</script>
```

The subject must name the scene or analogy the section's text already uses. House style is
unchanged: no text and no app screens inside a scene.

## How A is made

- **Screens.** `render_screens.py` writes inline SVG straight after each A spec, in a
  `div.nerdit-figure` with `data-visual="screen"`, a caption (the goal) and the reading steps.
  - Phone first:
    - a viewBox at most 400 wide;
    - at most 4 grid columns and 7 rows;
    - at most 8 code lines;
    - at most 6 panel items;
    - each value short enough to stay readable.
  - Colour tokens only; markers on the parts the steps name.
  - The render is deterministic, so the gate can re-render it and compare.
- **Concepts.** The writer draws them from the figure templates, unchanged.

## How B is made

- `visual_briefs.py` turns every B screen spec and every scene spec into illustrator v2 plan
  items: kinds `screen` and `illustration`, with the anchor taken from the paragraph before the
  spec.
- The illustrator writes prompts:
  - **`screen`** uses a new screen style block: a realistic, logo-free window of the named app,
    cropped to the working area, showing only the listed labels.
  - **`illustration`** keeps the house style.
- The owner (or a working image tool) saves images into `<images>/incoming/`. The apply step
  converts them, checks each against its brief (every listed label present, nothing extra,
  readable on the phone preview), and inserts them.

## Generated together

1. The writer writes each lesson with its screen and scene specs in one pass (writer rules,
   figures.md template 16, Visual Map rows).
2. The orchestrator runs `render_screens.py` after each writer and before the one-lesson gate.
   The gate runs `check_screens.py`.
3. After assembly, the orchestrator runs `visual_briefs.py` and the illustrator's plan step in
   the same run. The owner receives the course JSON and `PROMPTS.md` together.
4. The illustrator's section fingerprint already marks a brief stale when its section changes.

## Checks

| Check | Script | When |
|---|---|---|
| Spec schema, layout limits, the sync rule, A/B rule, formula results | `check_screens.py` | gate, course verify |
| A figure equals a fresh render | `check_screens.py` | gate |
| Click-path with no screen (warning) | `check_screens.py` | gate |
| Concept section with no main visual (warning, exists) | `verify_course.py` v11 | verify |
| `data-visual="screen"` is a known visual | `verify_course.py` (VISUALS) | verify |
| B image matches brief, readable on a phone | illustrator check step | apply |

## Pilot (one course per kind of subject)

| Course | Preset | What it proves |
|---|---|---|
| Business Intelligence and Data Analysis Using Excel, lessons 01–04 | Spreadsheet | Replace the 17 hand-made images with A/B screens (`sheet`) |
| Digital Marketing for Business Growth, one lesson | Conversational | `app` screens for a marketing tool, plus a scene |
| Agentic AI for Data Analysis, one lesson (local workdir) | Code | `app` (chat) or `editor` screen, plus a scene |
| Data Modelling v11, lesson 01 | Code | A scene added to a lesson that already has A figures (resumes the paused analogy images) |

For each pilot lesson:

- the writer works in refresh mode `figures`, so prose stays the same;
- then render, gate, briefs, illustrator, teaching QA, and a browser check at 1280 and 390;
- the owner reviews before any import.

## Left to the builder

- SVG layout maths for the three kits.
- The JSON-schema details.
- How Node is called (one batch per lesson).
- The exact screen-style wording within the anti-goals.
- The click-path detection heuristic, which must be tested and must stay a warning.

## Risks

- **Engine coverage:** only `sheet` has a result engine. Other layouts show results only when
  the lesson's text already states them (Code lessons' outputs are verified by
  `check_python_outputs.py` and `check_sql_outputs.py`).
- **B volume:** more courses means more images to generate by hand while the image tool is
  broken. The rule keeps exact values on the A side, and B is only for simple steps and scenes.
- **B drift:** AI images drift from their brief. The check step and the label list catch it; a
  fail produces a corrected prompt.
- **Rollout size:** about 70 courses predate v11. Each needs a `figures` refresh, which is
  lesson work, planned with the owner.
