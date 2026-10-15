# NERDIT lesson explanations, layout and teaching visuals

Date: 2026-10-12
Status: approved by the user on 2026-10-12 as the design for the next implementation plan
([2026-10-12-learning-visuals-implementation.md](2026-10-12-learning-visuals-implementation.md)),
together with the additions at the end of this document. Incremental upgrade to the implemented
v3.1.0 illustrator; only the new enhancements are pending.
Audience: students encountering the subject for the first time. For the Data Modelling course,
retain the agreed prerequisites of basic SQL and Python/pandas; warehouse terminology is new.

## Purpose

Make each lesson understandable through its explanation, visual and worked example together.
A student should be able to trace the same record, term or process across all three, then solve
a small related problem. Image resolution, compression and successful upload are separate
checks; they do not establish that an image teaches correctly.

This revision coordinates three parts of the workflow:

1. The chapter generator writes and sequences the explanation, examples and practice.
2. The illustrator selects or creates a visual from that exact teaching context.
3. The admin preserves the resulting layout and supports review before publishing.

Related plans:

- [Original illustrator implementation](2026-10-10-nerdit-lesson-illustrator.md).
- [Original illustrator design](../specs/2026-10-10-nerdit-lesson-illustrator-design.md).
- [Admin JSON and images import](../../../../nerdit-admin/docs/course-json-images-import-plan.md).
- [Live Excel course sample review](../../reviews/2026-10-12-excel-data-analysis-course-review.md)
  adds fixture/result consistency, workbook-state clarity and mobile image-readability cases.

The changes below extend the existing implementation and revise selected teaching rules.
Existing scripts, validators and skills continue to use their current contracts until the
enhancement tasks are completed. This document does not claim a new UI release or a revised course.

## Implemented baseline and upgrade boundary

The user confirmed that the 2026-10-10 illustrator plan is already implemented. Repository
inspection on 2026-10-12 confirms the v3.1.0 plugin and implementation commits, including
`349f629` for skill instructions and generator hand-off.

| Existing capability | Evidence inspected | Upgrade scope |
|---|---|---|
| Outline extraction and prompt/manifest creation | `extract_outline.py`, `manifest.py`, `SKILL.md` | Add complete target-section context and a richer teaching brief. |
| WebP conversion, previews and recorded visual checks | `convert_images.py`, `manifest.py` | Add source-content agreement and legibility checks. |
| Placement anchors and idempotent insertion | `insert_images.py`, `lessonhtml.py` | Extend the inserted block with a visible interpretation while preserving old manifests. |
| Existing-image optimization and course verification | `optimise_existing.py`, `check_images.py` | Review instructional meaning separately from compression and structural checks. |
| One-year immutable caching for course uploads | Shared `courseMediaService.ts`, its admin test and `set-media-cache-control.mjs` | Reuse this delivery work. |

The local Data Modelling image manifest records 16 optimized existing assets and three planned
illustration slots. This is evidence of existing workflow use, not an outstanding requirement to
build the illustrator. Test execution and production deployment were not reverified during this
status correction.

The checklist below tracks new learning-quality enhancements. It does not reopen implementation
of the original conversion, insertion, validation or caching pipeline.

## Evidence from the current local course

Reviewed the original output JSON and the existing star-schema and date-calendar PNGs in
`nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/` and
`nerdit/future-vision/public/lesson-images/data-modelling-etl-data-warehousing-for-analysts/`.

| Observation | Effect on a first-time learner | Required change |
|---|---|---|
| The star-schema picture uses Boston/Chicago, customer keys 1001/1002 and a `revenue` column. The lesson uses Pune/Mumbai, keys 1/2 and `amount`. | A student cannot trace the lesson's records through the diagram. | Draw technical figures from the lesson's actual fixture, names and values. |
| That lesson displays six tables, including later snowflake and unsafe-join comparisons, before explaining the first concept. | Several unfamiliar structures arrive before the student knows their purpose. | Introduce a small relevant data slice with the concept that needs it; keep the full fixture available as reference. |
| A date lesson example heading says `JOIN dim_date ...` but its example performs a timestamp conversion using `datetime(...)` and `date(...)`. | The heading gives the wrong expectation about what the code teaches. | Check each example heading against its actual operation and result. |
| The first lesson asks the student to distinguish ETL from ELT while its live practice query aggregates Pune orders. | Running the query does not demonstrate the distinction being asked about. | Use a process-order prediction for that concept, or a worked pipeline that actually shows the ordering. |
| Illustrator planning uses an outline and first paragraphs; its prompts largely exclude labels and exact data. | The prompt can miss the example, misconception or technical relationship that the visual must explain. | Use the outline for discovery, then read the complete target section and relevant fixture before writing its visual brief. |

The date picture's UTC-to-Kolkata example agrees with the sampled conversion. Improve its
integration and reading order without treating every existing picture as factually wrong.
These observations concern local artifacts, not a fresh audit of every live lesson.
The sampled PNGs predate the new illustrator workflow; their problems are not evidence that
the illustrator was unimplemented or that it generated those pictures. Optimization can retain
an old picture's instructional mismatch, so the proposed upgrade includes review of reused assets.

## Lesson structure for a first-time learner

Keep a consistent reading rhythm without forcing every topic into identical boxes or examples.

### Lesson opening

- Show the actual course/chapter/lesson context where supplied. Do not invent a chapter level
  when the input only supplies a course and lesson.
- Use a short real question and one sentence explaining what the student will be able to do.
  Example: "How can a sales amount be connected to the customer who bought the product?"
- Connect to the preceding lesson and name only the prerequisites needed now.
- Avoid repeating an objectives list, section list and recap with the same content.
- Show only the small dataset needed to begin. Additional tables appear when introduced.
  Full setup SQL can remain available without dominating the opening screen.

### Each teaching section

1. **Meaning and purpose:** define the new term in plain language and explain the problem it solves.
2. **Concrete case:** use one small example from the course's running scenario.
3. **Visual when useful:** show the relationship, change, decision or sequence being taught.
4. **Read the visual:** explain where to start, what the labels/arrows mean and what to notice.
5. **Worked example:** show code or a decision, its result, and why that result follows.
6. **Practice:** ask a prediction, tracing question or small change using the same idea; reveal
   an explanation with the answer. Use a live runner only when running code serves this task.

This is a teaching sequence, not six mandatory new UI components. Use paragraphs, lists,
existing example blocks and existing practice controls. Put a before/after result beside the
operation when that placement teaches better than putting it before the worked example.

Preserve explicit code outputs, unique lesson IDs, prerequisite ordering and a single closing
reference. Do not add an artificial second example solely to meet a fixed count. Where current
validators require a count or placement, update the contract and fixtures together before
generating content with the revised structure.

## Choose a visual by its teaching job

| Topic or learner question | Appropriate visual | Information it must show |
|---|---|---|
| Warehouse layers: where does a record go? | Labelled flow | Source, raw/staging, curated layer and mart; each layer's responsibility |
| ETL versus ELT: what happens first? | Two aligned process flows | Extract/transform/load in their actual orders and where transformation occurs |
| Star schema: how are tables related? | Relationship diagram plus a highlighted record | Exact table/column names, key matches, one-to-many meaning and declared fact grain |
| Cleaning or deduplication: what changed? | Before/after rows | Input, rule, retained/changed rows and matching output |
| Dates and time series: which date or period applies? | Timeline or aligned date views | Exact timestamps, timezone/offset, interval boundaries and the reporting calendar assumption |
| Aggregation: why is a measure unsafe to sum? | Small contrasting tables or a chart from data | Grain, units and the repeated value that causes the error |
| Operational setting: who does what? | Optional generated illustration | Relevant actors and actions, accompanied by a concrete mapping to the lesson |

Technical figures should use deterministic SVG, HTML tables or charts built from the source
data so labels and calculations can be checked. Use existing NERDIT figure templates where
they fit. If the deliverable requires an `<img>` file, export a checked diagram to WebP and
retain its essential explanation as HTML. The current course upload path accepts raster files;
this proposal does not require allowing arbitrary uploaded SVG files.

Generated illustrations can support a real scenario or an analogy. A literal teaching diagram
usually fits a technical relationship better. A course title alone is never a sufficient image
prompt. Cover artwork and chapter banners do not count as explanations of lesson concepts.

### Visual rules

- One clear learning objective per figure. Split a crowded diagram into successive views.
- Use exact domain labels when needed; replace the blanket three-one-word-label limit for
  technical diagrams. Keep text short, legible and checked against the source.
- Keep names, keys, dates, amounts, units and terminology consistent with the worked example.
- Use arrows to communicate a stated relationship or direction. Explain that meaning in text.
- Use colour consistently, with labels or shapes so colour is not the only signal.
- Choose aspect ratio to fit the information; do not force every process into landscape 3:2.
- Do not add a picture solely because a lesson has no raster image. An existing useful diagram
  may already satisfy the teaching need. Remove redundant visuals.
- Check the actual compressed asset at its intended display size. If labels become unreadable,
  simplify or split the figure; do not solve file-size targets by making instruction illegible.
- Preserve the existing compression and immutable-storage work as delivery requirements.

## Required visual brief

Keep authoring metadata in a sidecar manifest, not in student-facing lesson prose. Extend the
manifest with a versioned contract before scripts depend on additional fields.

Each planned visual needs:

- Course title; chapter title if present; lesson ID/title; section ID/heading.
- One learning objective and the question the visual answers.
- The exact source passage and fixture records/columns used, plus a source-content fingerprint.
- Terms the student already knows and new terms explained in the target section.
- Visual type, reading order, exact labels and required relationships.
- The intended takeaway and the likely misconception it must avoid.
- Placement anchor, introductory sentence, caption and visible explanation of the visual.
- Concise alt text; complex figures also need the essential information in nearby accessible text.
- A related check question with its answer and reasoning.
- Asset filename, source/rendering method, revision and review state.

Use the outline to locate sections, then inspect the complete target explanation, examples,
outputs and practice. Inspect an existing diagram itself before deciding that its caption means
the concept is already covered. Recheck a visual when its source content or image bytes change.

## Worked redesign: star schema

Pilot lesson: `dw-dimensional-models-and-star-schemas-04`.

Proposed section question: **How does a sales row find its customer and product?**

Start with the existing fact row `O1`, line `1`: `customer_key=1`, `product_key=10`, `amount=200`.
Explain that one fact row represents one sold order line before presenting its connections.

The diagram should show the fact row in the centre and two labelled key matches:

| Start in `fact_sales` | Match in the dimension | Description obtained |
|---|---|---|
| `customer_key = 1` | `dim_customer.customer_key = 1` | Aarav, Pune |
| `product_key = 10` | `dim_product.product_key = 10` | Book, Reading |

Below it, guide the student through three steps:

1. Read `amount=200` from the sales row. This is the measurement for this order line.
2. Follow customer key `1` to obtain the customer's city, Pune.
3. Follow product key `10` to obtain the product name, Book.

Caption: "The sales row stores the amount; matching keys supply customer and product details."

Then run a join using those same rows and explain its output. Ask: "Does following the customer
key change the sale amount?" Answer: "No. A valid match adds the customer's description; the
sale is still 200 rupees." Introduce duplicate-key multiplication in its own later section.

Only reveal snowflake tables when comparing the star and snowflake structures. Keep the source
fixture unchanged while improving when its parts become visible.

Second pilot: the date lesson. Show `2025-03-31 20:00 UTC` and `2025-04-01 01:30 Asia/Kolkata`
as the same instant, then derive the reporting date. Explain that the April-to-March fiscal
calendar belongs to this example; it is not a universal calendar rule. Use a heading that names
the timezone conversion. Handle order date versus ship date as a separate relationship.

## Student-facing layout

- Use the existing lesson visual language, semantic headings and a readable main column.
  Aim for roughly 65-75 characters per line for ordinary prose on desktop.
- Keep the definition, relevant figure and its interpretation together. Avoid a gallery of
  chapter images detached from the explanation.
- Put short captions beneath images; use visible paragraphs or numbered steps for longer
  explanations. A caption-length or alt-length limit must not remove essential information.
- Introduce technical vocabulary before using it in a figure, code example or question.
- Make example headings describe their actual operation or answer a specific learner question.
- Use restrained emphasis and spacing. Reuse existing blocks rather than nesting more cards.
- On narrow screens, stack process steps or split figures as needed. Zoom can supplement a
  diagram, but essential labels and relationships must be understandable without it.
- Keep tables and code independently scrollable where required; avoid horizontal page overflow.
- Keep alt text, descriptions, dimensions and reading order intact after sanitization/import.

## Changes to each plan

### Chapter generator and lesson writer

- [ ] Align `references/CORE.md`, `references/figures.md` and lesson-writer instructions with
  concept-appropriate figure placement and progressive introduction of datasets.
- [ ] Update any validators that enforce the changed layout before generating a revised pilot.
- [ ] Require heading/code/output agreement and objective/practice agreement in content review.
- [ ] Build exact technical diagrams from the same fixtures used by the lesson's code.
- [ ] Retain useful existing constraints: explicit outputs, prerequisite sequencing, stable IDs,
  restrained component nesting and a single closing reference.

### Illustrator

- [ ] Update `SKILL.md`, `references/style.md` and the original design to use full target-section
  context, figure selection by purpose and the revised visual brief.
- [ ] Version the manifest and support new fields without breaking existing manifests.
- [ ] Keep technical diagram rendering and optional illustrative image generation distinct.
- [ ] Extend insertion to carry the introduction and visible interpretation with the figure,
  with stable IDs and idempotent updates.
- [ ] Recheck semantic correctness after content edits; re-encoding an old PNG is not approval
  of its instructional content.
- [ ] Replace label restrictions and image quotas with clarity and content-consistency checks.

### Admin importer and lesson renderer

- [ ] Preserve each complete teaching block, its placement, alt text, caption and explanation
  while rewriting image URLs. Include stable IDs and description associations in verification.
- [ ] Show figures inside the actual lesson preview with their neighbouring explanation.
- [ ] Verify both desktop and mobile with the public lesson renderer's styles and sanitization.
- [ ] Distinguish file readiness from a staff content review; an upload match does not certify
  instructional quality. Avoid claiming automated checks prove comprehension.
- [ ] Verify changing an image cannot silently leave a caption or explanation about an old image.
- [ ] Retain course-wise folder selection, backups, stable course URLs and atomic publishing.

## Verification and rollout

1. Revise the star-schema pilot and its visual brief first. Produce a reviewable lesson preview.
2. Trace every displayed value back to the fixture and run the example SQL to confirm outputs.
3. Review the learner's path: explain the term, follow one record, predict a result, and explain why.
   This is editorial review; feedback from a first-time student is the stronger next check.
4. Add the date lesson as a second pilot to verify timeline, timezone and reporting-period clarity.
5. Check actual desktop/mobile rendering, then import/export a pilot through local admin.
   Verify captions, descriptions, filenames, anchors and examples survive unchanged in meaning.
6. Run course-contract and prerequisite checks plus focused integration tests for the changed
   teaching blocks. Evaluate factual and teaching quality separately from structural validity.
7. Apply the agreed pattern to the remaining lessons only after pilot review. For a live course,
   start from a fresh export and preserve its IDs and current content; do not overwrite newer
   live content with an older local generated course.

The immediate deliverable is two improved local pilots and updated authoring rules. Production
publishing remains a separate release step after content review and the pending admin validation.

## Supporting guidance

The [IES practice guide](https://ies.ed.gov/ncee/wwc/PracticeGuide/1) recommends pairing graphics
with verbal explanations, connecting concrete and abstract representations, and alternating
worked examples with learner practice. These principles inform the proposed lesson sequence.

[W3C guidance on complex images](https://www.w3.org/WAI/tutorials/images/complex/) calls for a
short text alternative and access to the essential information in a longer description. Its
advice to explain complex figures in surrounding text informs the visible interpretation block.

Specific choices here, including the two pilot lessons and the authoring manifest, are NERDIT
design recommendations rather than requirements asserted by those sources.

## Additions agreed 2026-10-12

These were agreed with the user when this revision was approved. They extend the sections above.

1. **Compress admin uploads.** Images uploaded by hand in the admin (course image panel) are
   converted in the browser to WebP, at most 1200 px wide, before upload, and the upload limit
   drops from 25 MB to about 2 MB. Today those uploads are stored at full size.
2. **Data Modelling migration uses the optimised set.** Import the illustrator's output for that
   course (16 WebP files, 984 KB in total, largest 84 KB) instead of the admin's "copy
   website-hosted images" action, which copies the original PNGs (about 22.5 MB, 1.4 MB each).
3. **Numbered markers link a figure to its reading steps.** Where a figure has a reading order,
   it shows numbered markers ① ② ③ on the parts being described, and the visible "read the
   figure" steps beneath it use the same numbers in the same order.
4. **Recurring cast for generated illustrations.** A course may define its recurring characters
   and setting once (for example an analyst and a Pune clothing store); every generated scene in
   that course uses them. This applies only to generated illustrations, never to technical
   diagrams, which always come from the lesson's own data.
