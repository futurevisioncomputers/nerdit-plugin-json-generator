# Teaching visuals v11 — Plan B and course-remediation continuation

Source: [design](../specs/2026-10-15-teaching-visuals-v11-and-data-modelling-remediation-design.md).
Cross-project record: `../../../../nerdit-admin/docs/course-json-images-import-plan.md`.

Work in order; preserve unrelated working changes. Do not publish content or deploy
before reviewing the concrete result with the user. Real business names require
recorded permission; reusable examples start with a fictional retailer.

- [x] B1: Declarative world schema, reference resolution and validation.
- [x] B2: Seeded data generator; SQL/JSON output, row cap, safe identifiers, FK integrity.
- [x] B3: World consistency checker for SQL seeds and figure tables; declared defects and disclosure.
- [x] B4: Input, one-lesson gate, whole-course validation, writer and illustrator integration.
- [x] B5: Fictional sample world, tests and usage documentation.
- [x] C1: User identified the full v2-create file as the repair source after supplying a 12-lesson intermediate. No independently fetched live export is claimed.
- [x] C2: Preserve source IDs and snapshot all 16 lessons in `v11/_before`; catalogue 60 entities / 257 original seed records from 01–16 with source SHA-256. Exclude the old `customer_private` contact table; the access lesson must avoid generating contact fields.
- [x] C3: Rewrite lessons 13–16 through the lesson-writer workflow, one at a time. All four gates, SQL checks, browser checks and teaching QA pass (31 SQL examples, none unchecked).
- [ ] C4: Pilot-refresh 08 and 10; gates and browser preview; user review before continuing.
- [ ] C5: Refresh remaining lessons, assemble, SQL/image/sequence/world checks and QA.
- [ ] C6: Prepare image prompts and import package; user supplies generated illustrations.
- [ ] R1: Review feature diff and build results; request each required commit/deployment approval.
- [ ] R2: Deploy reviewed styles before the reviewed course update; retain rollback export.

Dark-theme verification is unavailable in the current classroom (no theme switch
or dark palette). Do not add a new app-wide theme merely to satisfy an obsolete
test instruction; retain this limitation in the release record.

## Verification — 2026-10-15

- Generator **225 passed**, illustrator **90 passed**. New tests were exercised failing before implementation.
- Shared package, learner site and admin production builds pass; existing bundle-size and mixed-import warnings remain.
- CSS synchronization passes. No real-business permission claims were invented; the sample world is fictional.
- `check_world.py` checks seed-domain membership and source figure tables, scoped defects and disclosures; computed results and SVG relationship labels remain subject to SQL-output checks and QA.
- Existing source records are retained with a `records` schema extension, rather than approximated by a new random seed. Source provenance and domain-union limits are documented.
- Course work is isolated in `nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/v11`. No original source lessons were overwritten. Rewrites 13–16 are complete; pilot refresh 08 is in progress.
- `v11/checkpoint-13-16_output.json` preserves source metadata and course/lesson/question IDs. It is a checkpoint, not a publication package. Standard v11 failures are reduced from 236 to 154, all in original lessons 01–12; 18 density warnings remain. World checks add further requirements for those older lessons.
