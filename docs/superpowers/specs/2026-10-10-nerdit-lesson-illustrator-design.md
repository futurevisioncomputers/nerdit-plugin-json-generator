# NERDIT Lesson Illustrator — design

> **Proposed revision, 2026-10-12:** the learner-focused direction is documented in
> [Lesson explanations, layout and teaching visuals](../plans/2026-10-12-nerdit-learning-content-and-visuals.md).
> It addresses consistency between source content, labelled diagrams, worked examples and
> practice. This original design records the earlier concept-illustration scope; the revised
> teaching rules still need to be implemented in the skills and scripts.

Date: 2026-10-10
Status: original implementation present in v3.1.0; incremental learning-quality revision proposed on 2026-10-12.
Plugin: `nerdit_content_creator` (implemented skill `nerdit-lesson-illustrator`)

## Goal

Add concept illustrations to NERDIT lessons — for newly generated courses and for courses already on
the site — without raising the hosting bill and without images that contradict the lesson.

The skill does the thinking and the mechanical work. People generate the pictures. The skill
decides which sections need an image (one or more per lesson, as the content needs), writes a
ready-to-paste prompt and an exact placement for each, and, once the pictures exist, converts,
checks and inserts them so the course can be imported through the admin.

## Why

- 595 of 971 published lessons have no visual at all; 372 have an inline SVG figure.
- The first generated lesson images (Data Modelling course) were 1.4 MB PNGs served from Firebase
  Hosting, whose free transfer is 10 GB a month and is shared with the site itself. At 100k lesson
  views a month that is about ₹1,650 a month. The same images as ~100 KB WebP files in Firebase
  Storage (bucket `future-vision-skill-learning.firebasestorage.app`, region US-CENTRAL1, free tier
  5 GB stored and 100 GB downloaded a month) cost nothing at that traffic.
- One sampled image showed keys and US cities that do not match the lesson's own tables. Images
  must be checked against the lesson before they ship.

## Decisions taken

| Question | Decision |
|---|---|
| What images show | Concept illustrations only: scenes, metaphors, processes. Exact data, tables and charts stay in the lesson's SVG figures. |
| Who generates images | The user, with Codex CLI or any other tool. No paid image API is used by the skill. |
| Packaging | A new skill inside the existing `nerdit_content_creator` plugin, sharing its brand references. |
| Courses covered | Both: new courses from the chapter generator and existing courses exported from the admin. |
| Upload | The admin's existing "Import JSON + Images" page, which matches image files to lesson `<img src>` filenames, uploads them to Storage and rewrites the links. |

## Non-goals

- Generating images automatically or calling any image API.
- Course cover images (the admin's update import does not change course settings; covers are a
  separate admin task).
- Data diagrams, charts or tables rendered as images.

## Workflow

The skill has two runs. Everything lives in an `images/` folder next to the course JSON.

```
<workdir>/
  course-<chapter>_output.json                 input (never modified)
  course-<chapter>_output.with-images.json     written by apply
  images/
    manifest.json      every image slot and its status
    PROMPTS.md         copy-paste prompt sheet for the user
    incoming/          the user drops generated images here
    preview/           640 px previews used for the visual check
    upload/            final WebP files, the folder given to the admin import
```

### Run 1 — plan

`/nerdit-lesson-illustrator plan <course-json>`

1. `extract_outline.py` writes a compact outline of every lesson: section number and heading,
   the first paragraph of each section, existing figure captions, whether the section is a
   teaching section, and the images already present. Planning reads this outline, not the full
   HTML, so a 16-lesson course costs about 20k tokens instead of 100k+.
2. Claude applies the planning rules (below) and writes `images/manifest.json` and
   `images/PROMPTS.md`, and creates `images/incoming/`.
3. The run reports, per lesson, how many slots were planned and why, and lists lessons that had
   no visual at all first.

Re-running plan keeps existing slots and only plans lessons not yet in the manifest.
`--replan <lesson-id>` replaces one lesson's slots.

### The user

Generates each image from `PROMPTS.md` and saves it into `images/incoming/` under the filename the
sheet gives (`<lesson-id>-img<N>.png`; PNG, JPEG or WebP accepted). Any number at a time.

### Run 2 — apply

`/nerdit-lesson-illustrator apply <course-json>`

1. Match files in `incoming/` to manifest slots; report missing and unexpected files by name.
2. `convert_images.py`: resize to at most 1200 px wide, encode WebP at quality 80, step quality
   down (to a floor of 60) until the file is 150 KB or less; strip metadata; write to `upload/`
   as `<lesson-id>-img<N>.webp`; write a 640 px preview to `preview/`.
3. Visual check: Claude reads each preview and judges it against its slot (criteria below).
   PASS marks the slot `passed`. FAIL marks it `failed`, records the reason and appends a
   corrected prompt under a "Regenerate" heading in `PROMPTS.md`. `--accept <image-id>`
   overrides a FAIL.
4. `optimise_existing.py`: any image already referenced in a lesson that is larger than 300 KB
   (for example the Data Modelling PNGs on nerdit.in) is downloaded, converted the same way,
   saved to `upload/`, and its `src` is re-pointed to the new filename. A failed download leaves
   the original reference unchanged and is reported.
5. `insert_images.py`: insert every `passed` slot into its lesson and write
   `course-<chapter>_output.with-images.json`. Re-running replaces earlier inserted blocks
   (matched by `data-nerdit-img`), so it never duplicates.
6. `check_images.py` validates the result (below) and runs the course verifier before and after.
7. Report: inserted, waiting for files, failed with reasons, and the next action.

### Upload (admin)

Admin → Import JSON + Images → choose `course-<chapter>_output.with-images.json` and the
`images/upload/` folder.

- New course: create mode.
- Existing course: update mode, which keeps lesson ids, learner progress, course settings and the
  URL.

### Where the JSON comes from

| | New course | Existing course |
|---|---|---|
| Input | The chapter generator's `course-<chapter>_output.json` in its workdir | The JSON exported from the admin ("Export output JSON") |
| Note | Illustrate only a final course. The generator rebuilds the JSON from lesson files, which drops inserted images; re-running apply restores them from the kept manifest and `upload/` in seconds. | Plan lists no-visual lessons first. Apply also optimises the heavy images already in the lessons. |

The chapter generator's final summary gains one line pointing to this skill as the next step.

## Planning rules

### Which sections may get an image

- Numbered teaching sections only. Never the opening, practice blocks, the cheat sheet or the quiz.
- Every slot carries a one-line teaching reason. A section qualifies when it:
  - introduces an abstract idea that a concrete picture makes memorable (for example an
    idempotent load drawn as a light switch pressed twice with the same result);
  - describes a real-world process or scene (a shop, a warehouse, a hand-off between teams);
  - opens the lesson and benefits from a hook (section 1).
- Skip a section when an existing SVG figure already teaches the same idea (compare captions),
  when the section is pure syntax or calculation, or when the picture would need exact numbers or
  text to be correct.

### How many

- 0 to 3 per lesson, decided by the content; hard cap 3.
- A lesson with no visual at all gets at least 1.
- Project and capstone lessons get 1 scene.
- Expected average 1 to 1.5 per lesson. A slot without a clear teaching reason is dropped.

### Placement

Each slot stores the lesson id, section number and heading, a position, and an anchor: the first
60 characters of the paragraph the image follows.

- `after-explanation` (default): after the paragraph that explains the idea, before examples.
- `before-practice`: at the end of the section, before its practice block.

If the anchor is not found at insert time, that slot fails with a hint to re-plan the lesson. The
script never guesses a position.

### Prompt house style

Each prompt in `PROMPTS.md` is complete and pasteable: the section-specific subject followed by a
fixed style block.

Subject (written per slot): the objects or metaphor to draw from this section, the composition
(left to right for a process), and the focal point.

Fixed style block:

- Flat educational illustration, clean shapes, soft shadows.
- Brand colours: navy `#0B1F3A`, teal `#14B8A6`, light background `#EEF3F9`, white; at most one
  warm highlight.
- Landscape 3:2.
- No text, numbers, letters, logos, screenshots or watermarks. At most 3 one-word labels when the
  idea truly needs them; the prompt spells each label exactly.
- Indian people and settings where people appear. No real brands, companies or celebrities.

### Alt text and caption

- Alt text describes what the picture shows, 125 characters or less.
- Caption states the teaching point in one sentence of up to 15 words, using the lesson's terms.

### Filenames

`<lesson-id>-img<N>` with N from 1 within the lesson; the user saves `.png` (or `.jpg`/`.webp`),
apply outputs `.webp`. Names are unique within a course, which the admin's filename matching
requires.

## manifest.json

```json
{
  "course": { "id": "…", "title": "…", "source": "course-<chapter>_output.json" },
  "styleVersion": 1,
  "images": [
    {
      "id": "dw-load-idempotent-09-img1",
      "lessonId": "dw-load-idempotent-09",
      "lessonTitle": "…",
      "section": { "number": 4, "heading": "…" },
      "position": "after-explanation",
      "anchor": "first 60 characters of the paragraph",
      "reason": "one line: why this image helps",
      "prompt": "full pasteable prompt including the style block",
      "labels": [],
      "alt": "…",
      "caption": "…",
      "aspect": "3:2",
      "requestFile": "dw-load-idempotent-09-img1.png",
      "outputFile": "dw-load-idempotent-09-img1.webp",
      "status": "planned",
      "check": { "result": null, "reason": null },
      "bytes": null, "width": null, "height": null
    }
  ],
  "existingOptimised": [
    { "lessonId": "…", "from": "https://nerdit.in/lesson-images/…png", "to": "…webp", "bytesBefore": 0, "bytesAfter": 0 }
  ]
}
```

Status values: `planned` → `received` → `converted` → `passed` | `failed` → `inserted`.

## Visual check criteria

Judged on the 640 px preview against the slot's reason, prompt and caption:

1. Shows what the slot's reason says the section needs, so the caption is true of the picture.
2. No garbled or extra text; any labels match the slot's `labels` exactly.
3. No numbers, logos, real brands or watermarks.
4. Brand palette and, where people appear, an Indian context.
5. Nothing that contradicts the lesson's terms or facts.

## Inserted markup

```html
<div class="nerdit-figure nerdit-illustration" data-nerdit-img="<image-id>">
  <img src="<lesson-id>-img1.webp" alt="…" width="1200" height="800"
       loading="lazy" decoding="async" style="display:block;width:100%;height:auto">
  <div class="nerdit-figure-caption">…</div>
</div>
```

- `nerdit-figure` with a `nerdit-figure-caption` satisfies the verifier's figure rule.
- No hex colours, so the theme rule passes.
- `width`/`height` are the real WebP dimensions, which prevents layout shift.

## Validation — check_images.py

- Every inserted `<img>` has its file in `upload/`, 150 KB or less (warning), never over 250 KB
  (error).
- Each has non-empty alt text, `width`, `height`, `loading="lazy"`, `decoding="async"` and a caption.
- No `data:` image sources anywhere in lesson HTML.
- No image host other than the course's own filenames, Firebase Storage or the NERDIT site.
- Every `data-nerdit-img` id is unique and matches an `inserted` manifest slot.
- The with-images JSON is under the admin import limit of 1 MiB.
- `verify_course.py` runs on the input and on the output; apply fails only on failures that are new
  in the output. Older courses already fail some newer checks for unrelated reasons, so an absolute
  pass would block them.

## Errors

| Situation | Behaviour |
|---|---|
| File missing for a slot | Slot stays `planned`; listed by filename; other slots proceed. |
| Unexpected file in `incoming/` | Listed; ignored. |
| Corrupt or unsupported file | Slot reported with the file name; not converted. |
| Over 150 KB at quality 60 | Warning; kept. Over 250 KB: error, not inserted. |
| Anchor not found | Slot fails; message suggests `--replan <lesson-id>`. |
| Visual check FAIL | Slot `failed`; corrected prompt added to `PROMPTS.md`; not inserted unless accepted. |
| Existing-image download fails | Original reference kept; reported. |
| New verifier failures after insert | Apply reports them and does not write the with-images JSON. |

## Files

```
skills/nerdit-lesson-illustrator/
  SKILL.md                    orchestration: plan and apply runs, rules, criteria
  references/style.md         house style block and planning rules (single source)
  scripts/extract_outline.py
  scripts/convert_images.py
  scripts/optimise_existing.py
  scripts/insert_images.py
  scripts/check_images.py
  scripts/manifest.py         load, validate and save the manifest (shared by the scripts)
  scripts/test_*.py           pytest, next to the scripts as in the chapter generator
  scripts/fixtures/           a small course JSON and sample images
```

Python with Pillow (WebP support confirmed with Pillow 12.1.1). No subagents are required: the
outline keeps planning small, and previews keep the visual check small. If a very large course is
planned, the skill plans lessons in batches within one session.

## Testing

Unit tests (pytest):

- `extract_outline`: sections, captions, teaching-section detection, existing images.
- `convert_images`: output is WebP, at most 1200 px wide, at most 150 KB for a typical
  illustration, quality floor respected, preview written.
- `insert_images`: correct position for both placement kinds; running twice gives byte-identical
  output; missing anchor fails that slot only.
- `optimise_existing`: re-points `src`, records sizes, leaves the reference on download failure.
- `check_images`: each rule has a failing and a passing fixture.
- `manifest`: schema validation and status transitions.

End-to-end trial on the Data Modelling course:

1. Apply optimises its 16 existing PNGs (about 1.4 MB each) to WebP.
2. Plan proposes slots for its lessons.
3. One lesson is imported through the admin to confirm filename matching and Storage upload.

## Related change outside the plugin

`uploadCourseImage` in `nerdit/shared/src/services/courseMediaService.ts` uploads files with no
cache metadata, so Storage serves them with `cache-control: private, max-age=0` and browsers
re-download them on every visit. It should pass
`cacheControl: 'public, max-age=31536000, immutable'`. This is safe because the storage path
contains the file's SHA-256. A one-off script would set the same metadata on objects already in
`media/courses/`. This touches the website/admin code and needs a separate approval and deploy.
