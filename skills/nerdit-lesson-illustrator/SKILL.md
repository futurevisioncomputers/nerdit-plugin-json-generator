---
name: nerdit-lesson-illustrator
description: >
  Plans and inserts concept illustrations into a NERDIT course JSON after its content is final.
  Use when the user wants images for lessons ("add images to this course", "plan lesson images",
  "illustrate the lessons", "apply the images I generated"). Two runs: `plan` writes a prompt
  sheet and placements for images the user generates in their own tool (Codex CLI or any other);
  `apply` converts the generated images to small WebP files, checks each one against its lesson,
  inserts them, and produces a JSON plus image folder for the admin's "Import JSON + Images" page.
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
2. `python scripts/extract_outline.py --course <course.json>` and read the outline.
3. Apply the planning rules in `references/style.md`. Write `<images>/plan.json`: a JSON list,
   one item per image:
   `{"lessonId", "section", "heading", "position", "anchor", "reason", "subject", "labels", "alt", "caption"}`.
   `section` and `heading` come from the `§` line; `anchor` is copied exactly from a `¶` line of
   that section (leave it empty for `before-practice`). Include only lessons not yet in
   `<images>/manifest.json`; to redo one lesson use `--replan <lesson-id>` with only that lesson's items.
4. `python scripts/manifest.py add --course <course.json> --plan <images>/plan.json --images-dir <images>`.
   On errors, fix `plan.json` and run again (nothing is saved until the plan is clean).
5. Tell the user: how many images per lesson and why (lessons with no visual first), the path of
   `PROMPTS.md`, and that each image must be saved into `<images>/incoming/` under the filename
   shown. Then stop.

## Run 2 — apply

1. `python scripts/convert_images.py --images-dir <images>`. It reports converted, waiting and
   ignored files.
2. Read every preview it lists in `<images>/preview/` (640 px JPEGs) and judge each against its
   slot in `manifest.json` using the visual-check criteria in `references/style.md`. Write
   `<images>/results.json`: `[{"id", "result": "pass"|"fail", "reason", "revisedSubject"?}]`.
   For a fail, give a one-line reason and a corrected `revisedSubject` that fixes the cause.
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

## Never

- Call an image generation API, or embed images as `data:` URIs.
- Edit the input course JSON.
- Ask for text, numbers, charts or tables inside an image; exact data belongs in SVG figures.
