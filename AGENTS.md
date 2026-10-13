# Cross-project compatibility

The user requires the plugin, learner site and admin to stay synchronized.

- Check lesson-format, CSS, runner, schema and image changes against both `../nerdit/future-vision` and `../nerdit-admin`; follow the shared workflow in `../nerdit/AGENTS.md`.
- Lesson CSS in `skills/nerdit-chapter-generator/references/` is canonical. Update both apps' `src/lesson-css/` copies in the same change. Run `node ../nerdit/scripts/check-lesson-sync.mjs`; both app builds enforce it.
- Verify generated JSON can be imported, previewed, exported and published by admin and rendered by the learner site, including SVG titles/descriptions and all four teaching siblings.
- Keep raster filenames unique within a course and references relative to its upload folder. Inline SVG stays in the JSON and requires no upload.
- Link authoring plans to `../nerdit-admin/docs/course-json-images-import-plan.md`. Migrate the reviewed final JSON and its referenced raster files; do not copy superseded diagrams merely because they exist in an old export.
- Preserve unrelated generated lessons and runner work.
