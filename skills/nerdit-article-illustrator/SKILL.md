---
name: nerdit-article-illustrator
description: >
  Adds 2-3 teaching images to a NerdIT blog article (nerdit.in/blog): a figure reused from the
  related NerdIT course when one fits, otherwise a diagram drawn from the article's own content.
  Use when the owner wants images for an article ("add images to this article", "illustrate the
  blog post", "make the article image pack"). Two runs: `plan` picks the places and writes the
  SVGs and plan.json; `apply` checks everything and renders a pack (1600 px PNGs on a light page
  + placements.json) for the admin's Articles -> Edit -> "Import images". Never calls an image API.
---

# NerdIT Article Illustrator

**Any model** (Claude, OpenAI/Codex or another agent) can run this skill: it is these steps plus
Python scripts. Do the steps in order; `scripts/…` paths are relative to this skill's folder.

Scripts live in `scripts/`; run them with `python <script>` and absolute paths. Read every output:
a `PROBLEM` line or a non-zero exit means stop and fix it, never skip it. House style:
`references/style.md` (read it before planning).

Inputs, in one work folder (for example `~/.nerdit-social/articles/<slug>/`):
- `article.json`: Articles -> Edit -> **Download JSON** in the admin.
- For each id in its `relatedCourseIds`, that course's JSON: admin course editor -> **Export output JSON**
  (or the chapter generator's `course-<chapter>_output.json`).

## Run 1 - plan

1. `python scripts/article_outline.py --article <work>/article.json`: the sections (§) and anchor lines (¶).
2. Pick 2 or 3 places where a picture teaches what the text says: a relationship, a sequence, a
   comparison, a before/after or a result. Not the intro, not a list of tips. Spread them out.
3. For each place, look for a course figure first:
   `python scripts/course_figures.py --course <course.json>` lists every figure (lesson:n, title,
   caption, labels). A figure fits only when its labels and caption say the same thing as the
   paragraph. Extract it: `--extract <lesson>:<n> --out <work>/<name>.svg`.
4. No fitting figure: draw a diagram as `<work>/<name>.svg`, following
   `../nerdit-chapter-generator/references/figures.md` (tokens only, `viewBox` at most 400 wide,
   `role="img"`, `aria-label`, no width/height). Every label and every number or name drawn must be
   in the article word for word.
5. Write `<work>/plan.json`:
   `{"items": [{"file": "<name>.png", "source": "diagram"|"course", "svg": "<name>.svg",
   "anchor": "<a ¶ line, copied exactly>", "labels": [...], "alt": "...", "caption": "...",
   "steps": 0, "courseId": "...", "courseSlug": "...", "courseTitle": "..."}]}`
   (`course*` only for course figures; `steps` = numbered markers ① ② ③ drawn, else 0).

## Run 2 - apply

1. `python scripts/build_pack.py --article <work>/article.json --plan <work>/plan.json --out <work>/pack`
2. Open every PNG in the pack and check it against its paragraph: right idea, labels readable, nothing
   drawn that the article does not say. Fix the SVG and re-run on any doubt.
3. Tell the owner: Articles -> Edit -> **Import images** -> pick `placements.json` and the PNGs together
   -> Preview -> Save. Course figures get a caption link to their course.
4. Cover: `brand-studio article-cover <work>/article.json [--course <course.json>] --out <work>` (see the
   brand-studio skill), uploaded in the article's "Cover image" field.

Tests: `cd skills/nerdit-article-illustrator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
