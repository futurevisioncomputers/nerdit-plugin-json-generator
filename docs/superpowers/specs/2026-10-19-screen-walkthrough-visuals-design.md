# Screen walkthrough visuals — design

Date: 2026-10-19. Status: approved to plan (the user asked to skip questions and start the plan).

## Why

The owner hand-made 17 images for the Excel course (lessons 01–04): realistic Excel screens
with the lesson's own rows, a formula bar, a highlighted ribbon button and numbered steps ①–④.
They teach the click-path, which text alone cannot. But they were made outside the plugin, and
three problems showed up on the live course (checked 2026-10-19):

- **Sync:** the Text to Columns image shows an "Operations" department that the lesson never
  mentions. Nothing checks an image against its lesson.
- **Phone:** the images are about 1400 px wide with ~16 px text, so on a 390 px phone the text is
  about 4 px.
- **Access:** no captions, and alt texts are file names (`lesson4-topic1-xlookup`).

The owner wants the plugin to generate these visuals **together with the lesson content**, in
sync with it, and chose two image types by the owner's rule:

> If the process is complex to explain, use image A. If it is simple, use image B.

- **A — drawn screen (vector):** an Excel-like screen drawn as inline SVG from the lesson's own
  data. Exact, phone-readable, checked by script.
- **B — screen image (raster):** a realistic AI-generated screen image built from the same data,
  generated outside the plugin and checked against its brief.

## Goals

1. The lesson writer describes each walkthrough once, as a **screen spec** (JSON) inside the
   lesson. Both A and B come from that one spec, so the picture cannot say something the lesson
   does not.
2. A is rendered by a script during the generation run, with formula results computed by the
   plugin's own `nerdit-excel-engine.js`. A gate check fails a lesson whose drawn screen no longer
   matches its spec or its demo data.
3. B gets an automatic illustrator brief and prompt from the spec (no hand-written plan), and the
   apply step checks the generated image against that brief, including phone readability.
4. The complex/simple rule is applied by a script, with a writer override that needs a reason.
5. Pilot on the live Excel course: rebuild its workdir from the published lessons, replace the
   17 hand-made images in lessons 01–04 with A or B, and compare on a phone.

## Non-goals

- Other apps (Power BI, Google Sheets, VS Code). The spec format leaves room; build Excel only.
- Changing the Excel engine's function list, or adding new formula functions.
- Publishing. The pilot ends with a local preview and an import file; publishing is a separate,
  approved step.
- Fixing the `claude-image-generation` plugin (third-party; it fails on Windows paths). B works
  with any image tool that saves into `<images>/incoming/`.

## Anti-goals (failure even if it "works")

- A picture that shows a value, name or step the lesson does not contain.
- Text a learner cannot read on a 390 px phone.
- A second copy of the same facts as text map + figure + reading steps (figures.md R13).
- Real logos or brand marks in either type (a generic spreadsheet look with Excel's tab and
  button names is fine; no Microsoft logo).

## The screen spec

One JSON block per walkthrough, written by the lesson writer next to the place the picture goes:

```html
<script type="application/json" class="nerdit-screen" data-grid="xl-staff">
{
  "id": "xlookup-city",
  "app": "excel",
  "goal": "Find Isha's city with XLOOKUP",
  "view": {"columns": ["B", "D"], "rows": [1, 7], "active": "H3"},
  "steps": [
    {"do": "select", "target": "H3"},
    {"do": "type", "target": "H3", "formula": "=XLOOKUP(\"Isha\",B2:B7,D2:D7)"},
    {"do": "result", "target": "H3"}
  ],
  "dialog": null,
  "image": "auto"
}
</script>
```

- `data-grid` names the lesson's existing demo-data block (`runners/excel.md`). Cells shown in
  the picture are read from it, never typed into the spec.
- `steps` are the reading steps; each becomes a marker ①②③ on the picture and a line in the
  reading list. Kinds: `select` (a cell), `click` (`path`: ribbon tab then button, or a menu
  path), `type` (a formula or value into a cell), `set` (a dialog field and its value),
  `result` (the cell a `type` step filled, computed by the engine), `key` (a shortcut such as
  Ctrl+E).
- B specs also carry the teaching text the illustrator needs: `alt`, `takeaway`,
  `misconception` and `check` (`question`, `answer`, `reasoning`).
- `dialog`, when present: `{"title": ..., "fields": [{"label": ..., "value": ...}]}`. Labels must
  be real Excel dialog labels; values must appear in the lesson.
- `image`: `"auto"` (the rule decides), or `"A"` / `"B"` with `"why"` (an override the QA agent
  reviews).

## The complex/simple rule (my call on "complex", from the owner's rule)

A process is **complex → A** when any of these hold:

- more than 3 steps;
- a dialog with 2 or more settings;
- a `result` step (a computed value the learner must trust).

Otherwise it is **simple → B**: up to 3 clicks or keys on one screen, no dialog settings, no
computed value (for example, Data → Remove Duplicates → OK; Ctrl+E Flash Fill).

The rule lives in one function (`screen_kind(spec)`) so the owner can tune it in one place.

## How A is made

`render_screens.py` reads each lesson's specs and its demo data, and writes inline SVG after the
spec block, inside the usual `div.nerdit-figure` with `data-visual="screen"`, a caption and
reading steps:

- **Phone first:** viewBox at most 400 wide (figures.md rule 9). It shows only the spec's view
  window (at most 4 columns and 7 rows), a one-line formula bar, a simplified ribbon strip with
  the active tab and one highlighted button, and the dialog as a simple panel. Multi-state
  processes stack panels vertically (at most 3).
- **Exact values:** `type`/`result` cells are evaluated by running `nerdit-excel-engine.js` in
  Node (`NerditExcel.evaluate`), the same engine the Try It uses. An engine error (`#NAME?`)
  fails the lesson.
- **Style:** colour tokens only (dark-theme safe), text as `<text>`, markers ①②③ on the parts the
  steps describe, `role="img"`, `aria-label` built from the goal and steps.
- The render is deterministic, so a check can re-render and compare.

## How B is made

- `screen_briefs.py` turns each B spec into an illustrator v2 item of a new kind, `screen`:
  exact visible cells (read from the demo data), the ribbon path, the steps with markers, and a
  phone rule (cropped to the working area, at most 5 columns × 6 rows, portrait or 4:3, labels
  large).
- The illustrator writes the prompt with a **screen style block** (a realistic spreadsheet UI is
  allowed for `screen` only; text limited to the listed labels and values; no logos). The house
  style for other illustrations is unchanged.
- The image is generated outside the plugin and saved into `<images>/incoming/` (as today).
- Apply converts it, writes phone and desktop previews, and the check step compares the image
  with the brief: every listed value present, nothing extra, markers in order, readable at phone
  size. A fail produces a corrected prompt.

## Generated together, kept in sync

1. The writer writes the lesson and its screen specs in one pass (writer rules + figures.md
   template 16 "Screen walkthrough").
2. The one-lesson gate runs `check_screens.py`: every spec is valid, every shown cell exists in
   its demo grid, every formula evaluates, every label is a known Excel label or appears in the
   lesson, the kind matches the rule (or has an override reason), and every A figure equals a
   fresh render.
3. `assemble_course.py` (or the orchestrator step before it) runs `render_screens.py`, so A is in
   the lesson the moment the course JSON exists.
4. The orchestrator then writes B briefs straight into the illustrator manifest. The illustrator's
   section fingerprint already marks a brief stale when its section changes, so editing a lesson
   flags its B images for regeneration instead of silently keeping an old picture.

## Checks and where they run

| Check | Script | When |
|---|---|---|
| Spec schema, grid cells, formula results, labels, kind rule | `check_screens.py` | gate, course verify |
| A figure equals a fresh render | `check_screens.py` | gate |
| `data-visual="screen"` known | `verify_course.py` (VISUALS) | verify v11 |
| B image matches brief, readable on phone | illustrator check step | apply |

## Pilot

The Excel test course (`course-excel-data-analysis-1785164945289`, live, public read):

1. Rebuild a local workdir from the published lessons (`input_from_output.py`).
2. Lessons 01–04: replace the 17 hand-made images with specs. Expect most to be A (they show
   results or dialogs) and a few to be B.
3. Gate, QA, browser at 1280 and 390, side by side with the current images.
4. Owner reviews before any import.

## Left to the builder

SVG drawing details, panel layout maths, the spec JSON schema file, how Node is invoked (one
batch call per lesson), and the exact prompt wording within the screen style block.

## Risks

- **Engine coverage:** formulas outside the engine's function list cannot be A with results;
  such a spec must drop the `result` step or the lesson must teach a supported function.
- **B fidelity:** AI images drift. The check step and the "complex → A" rule keep exact values on
  the A side, where drift cannot happen.
- **Image tool:** in-session generation is blocked until the image plugin is fixed; B still
  works with the owner's own tool.
