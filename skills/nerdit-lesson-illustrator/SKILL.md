---
name: nerdit-lesson-illustrator
description: >
  Plans and inserts teaching visuals into a NERDIT course JSON after its content is final:
  SVG diagrams drawn from each lesson's own data, and concept illustrations for real scenes.
  Use when the user wants images for lessons ("add images to this course", "plan lesson images",
  "illustrate the lessons", "apply the images I generated"). Two runs: `plan` writes a visual
  brief per slot, draws the diagrams, and writes a prompt sheet and placements for illustrations
  the user generates in their own tool (Codex CLI or any other); `apply` converts the generated
  images to small WebP files, checks each visual against its brief, inserts it with an intro,
  reading steps and a check question, and produces a JSON plus image folder for the admin's
  "Import JSON + Images" page.
  Works for new courses (the chapter generator's output JSON) and existing courses (a JSON
  exported from the admin). Never calls an image API.
---

# NERDIT Lesson Illustrator

All scripts live in `scripts/` next to this file. Run them with `python <script>` from any folder,
passing absolute paths. `<images>` is the `images/` folder next to the course JSON.

House style, planning rules and visual-check criteria: `references/style.md`. Read it before
planning and before checking.

## Run 1 — plan

1. Locate the course JSON. New course: `course-<chapter>_output.json` from the chapter generator's
   workdir. Existing course: the file the user exported with "Export output JSON" in the admin.
   If neither is given, ask for it.
2. `python scripts/extract_outline.py --course <course.json>` to find candidate sections.
   Add `--hints <workdir>` when the chapter generator's workdir is available, to see each
   section's planned visual and image idea.
3. For each candidate, read the whole section and its data:
   `python scripts/extract_outline.py --course <course.json> --full <lesson-id>:<section>`.
   Inspect any existing figure in that section before deciding it already covers the idea.
4. Choose the visual by its teaching job (`references/style.md`): a **diagram** for any
   relationship, sequence, change, timeline or table; an **illustration** only for a real scene
   or analogy. Write `<images>/plan.json` as
   `{"version": 2, "cast": "<optional recurring characters>", "items": [ ... ]}` with one item per
   visual: `lessonId, section, heading, position, anchor, kind, question, objective, sourceRefs,
   knownTerms, newTerms, labels, takeaway, misconception, intro, caption, alt, explanation,
   checkQuestion {question, answer, reasoning}` and, for illustrations, `subject`.
   Labels are copied exactly from the section or fixture. `explanation` is the visible reading
   order: with two or more steps, the figure carries matching markers ① ② ③.
   `section` and `heading` come from the `§` line; `anchor` is copied exactly from a `¶` line of
   that section (leave it empty for `before-practice`). Include only lessons not yet in
   `<images>/manifest.json`; to redo one lesson use `--replan <lesson-id>` with only that lesson's items.
   (A plain JSON list is the older v1 plan format; it still works but has no teaching brief.)
5. `python scripts/manifest.py add --course <course.json> --plan <images>/plan.json --images-dir <images>`.
   On errors, fix `plan.json` and run again (nothing is saved until the plan is clean).
6. For each diagram listed under "Diagrams to draw" in `PROMPTS.md`, write the SVG to
   `<images>/diagrams/<file>` following `figures.md` (tokens only, viewBox, role, aria-label,
   labels as `<text>`, markers ① ② ③). Illustrations go to the user as before.
7. Tell the user: how many visuals per lesson and why (lessons with no visual first), the path of
   `PROMPTS.md`, and that each illustration must be saved into `<images>/incoming/` under the
   filename shown. Then stop.

## Run 2 — apply

1. `python scripts/convert_images.py --images-dir <images>`. It reports converted, waiting and
   ignored files, and checks each diagram SVG against the figure contract.
2. Check every converted visual against its brief using the criteria in `references/style.md`:
   read each raster preview at both sizes (`preview/<id>.jpg` and `preview/<id>-phone.jpg`) and
   each diagram's SVG source. Write `<images>/results.json` as before:
   `[{"id", "result": "pass"|"fail", "reason", "revisedSubject"?}]`.
   For a fail, give a one-line reason and a corrected `revisedSubject` that fixes the cause.
   For a failed diagram, also fix its SVG in `<images>/diagrams/` and run step 1 again.
3. `python scripts/manifest.py record --images-dir <images> --results <images>/results.json`.
   If the user wants to keep an image you failed: `python scripts/manifest.py accept --images-dir <images> --id <image-id>`.
4. `python scripts/insert_images.py --course <course.json> --images-dir <images>`. It also
   re-encodes heavy images already in the lessons (`--no-optimise` skips that). If it reports
   problems, nothing is written: fix them (usually `--replan <lesson-id>` for a moved paragraph)
   and run again.
5. Tell the user what was inserted, what is still waiting or failed (see "Regenerate" in
   `PROMPTS.md`), and the upload step:
   Admin → Import JSON + Images → `course-<chapter>_output.with-images.json` + folder `<images>/upload/`
   (create mode for a new course, update mode for an existing one).

Apply can run as often as needed: images arrive in batches, and re-running gives the same lessons.
A new course whose JSON the chapter generator rebuilt loses inserted images; run apply again — the
manifest and `upload/` restore them without generating anything.

When a course world is supplied, read its cast and story beats before planning.
Keep invented characters' `look` consistent across lessons. Respect the course map
and the writer's `visuals` hints. Never invent a business permission record or
replace exact world data with an illustration. Keep real business logos out of images.

## Never

- Call an image generation API, or embed images as `data:` URIs.
- Edit the input course JSON.
- Ask for text, numbers, charts or tables inside an image; exact data belongs in SVG figures.
