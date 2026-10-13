# Course JSON, images and lesson rendering

This contract links the plugin, admin and learner site. Keep all three repositories
checked out as siblings. See the [admin release checklist](../../nerdit-admin/docs/course-json-images-import-plan.md).

## Course folder workflow

Generate one completed output JSON and one folder of raster images. Reference each
file at its intended lesson position, for example:
`<img src="images/star-schema.png" alt="Sales star schema">`.
Filenames must be unique across the course, including nested folders. Admin matches
files by name in one upload; chapter-by-chapter assignment is unnecessary.

Inline SVG diagrams stay in lesson HTML and need no separate upload. Missing files
and duplicate names block preparation. Extra selected images enter the course library.
Existing online URLs remain usable. Reimported Storage URLs still match their original
filenames through the course's media records.

PNG/JPEG sources smaller than 25 MiB are resized to at most 1200 px wide and converted
to WebP at quality 0.8. WebP, GIF and AVIF retain their format. Every stored course image
must be smaller than 2 MiB. Paths include the course ID and content hash, with one-year
immutable caching. Image bytes never belong in course JSON.

## Teaching visuals

Preserve illustrator v3.2 teaching blocks together: `p.nerdit-visual-intro`,
`div.nerdit-figure`, `ol.nerdit-visual-read` and `div.nerdit-predict`, sharing
a stable `data-nerdit-img` ID. Keep captions, alt text, SVG title/description and
ARIA associations, list styles and `max-width:440px` sizing.

File matching verifies availability. Staff still review whether the diagram explains
its heading and examples. Replacing or inserting an image flags affected lessons for
review before publication. Inspect the introduction, labels, caption, reading steps
and prediction check at desktop and phone widths.

If the illustrator will run again, make permanent teaching-text changes in its
manifest/source files too; reapplying it can overwrite admin-only edits.
Admin and public snapshot previews show sanitized teaching content. Check interactive
runners in the learner classroom.

## Compatibility checks

The plugin's references/css8.css, css9-simple.css and css10-brand.css are canonical.
Update both apps' copies together. Run `node ../nerdit/scripts/check-lesson-sync.mjs`;
both app builds enforce this check, ignoring harmless CRLF/LF differences.

Build ../nerdit/shared after shared service/type edits. Run admin import/visual
round-trip tests and public normalizeLessonHtml tests for format changes. Public
normalization must retain SVG accessible names while removing document wrappers.
Preview snapshots include full lessons and exclude private final-assessment answers.

## Plan precedence

The October 10 illustrator implementation remains the baseline. The October 12
learning-content plan improves teaching quality; the admin import plan handles storage
and publication. They work together.

For Data Modelling, use the reviewed final JSON and only its referenced raster files.
Inline SVG replacements need no upload. This supersedes older instructions to copy all
hosted PNGs or import all 16 old WebPs. See the [rollout log](../../nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/rollout/PROGRESS.md).
Releasing the importer does not publish unfinished course revisions.
