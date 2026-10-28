# Video Plan in the Lesson Writer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each lesson writer also writes its lesson's part of the story-video plan, so the video pass no longer re-reads every lesson.

**Architecture:** The writer writes `<workdir>/<id>.video.json` (that lesson's scenes, practise cards and skipped topics, in the existing `plan.json` v3 scene format) and its vector SVGs to `<workdir>/video-vectors/`. `storyplan.py` gains `check-lesson` (one lesson, run by the lesson gate) and `merge` (scaffold, then fill every lesson from its file). The story-video skill starts from the merged plan and only writes the intro and recap.

**Tech Stack:** Python 3.12+ stdlib, pytest (course venv pytest, `-p no:cacheprovider`).

**Spec:** this plan's Intent section. Decided by the owner on 2026-10-27/28 (memory `video-in-writer-plan`); the narration rules stay those of `skills/nerdit-story-video/SKILL.md` §1.

## Intent

- **Why:** the video pass re-reads all lessons to write their scenes; the writer already holds the lesson in context. Estimated saving about 300k tokens for a 15-lesson course; writer context grows about 20–30k.
- **Goals:** same video quality and the same `storyplan.py check`; a regenerated lesson regenerates its video part, so the two never drift; video stays optional per course.
- **Non-goals:** no change to voice, B-roll, rendering, `build_video.py` or clip placement.
- **Anti-goals:** scenes that mirror a different version of the page than the one delivered; a writer that skips its own lesson's fixes to save room for video.

## Global Constraints

- `plan.json` stays `"version": 3`; scene keys exactly as `scaffold()` writes them: `kind, lessonId, topic, title, narration, keyIdea, terms, focus, myth` plus `vector | table | code | figure | query` and `highlight`.
- Default `language` is `hi` (Hinglish, Devanagari Hindi words, at least 30% English); `en-IN` only on request (memory `video-voice-hinglish`).
- Vector file names: `<lessonId>-t<topic>-<name>.svg`, unique per course.
- A lesson's `video.json` is valid only for the lesson HTML it was written with: it stores `"htmlSha256"` of `<id>.html`; `merge` and `check-lesson` fail on a mismatch ("the lesson changed after its video part was written; rewrite it").
- Video is opt-in per run: the orchestrator passes `VIDEO_PATH` only when the owner says the course gets a video (default yes for code courses, asked once at Step 1).
- After each task: sync changed files to the installed plugin cache `C:/Users/siddh/.claude/plugins/cache/fv-analysis-marketplace/nerdit_content_creator/3.9.0/` at the same relative path.

## Review Focus

- A lesson refreshed after its video part was written (HTML hash changed) must fail `merge`, not merge stale scenes — test in Task 2.
- A topic number in `video.json` that the lesson no longer has (sections renumbered) must fail `check-lesson` with the topic named — test in Task 1.
- Two lessons using the same vector file name must fail `merge` — test in Task 2.
- A lesson with no `video.json` when others have one: `merge` must fail and list it (never a silent gap in the video) — test in Task 2.
- `skipTopics` for a section with no Try It must still pass the practise-card check — test in Task 1.

---

### Task 1: `check-lesson` — validate one lesson's video part

**Files:**
- Modify: `skills/nerdit-story-video/scripts/storyplan.py`
- Test: `skills/nerdit-story-video/scripts/test_story_video.py`

**Interfaces:**
- Consumes: existing `check_plan(plan, video_dir, figures, texts, topics, parts, practice)`, `lesson_parts`, `lesson_topics`, `lesson_texts`, `lesson_figures`, `lesson_practice`, `check_vector`.
- Produces:
  - `lesson_video_problems(video: dict, html: str, lesson_id: str, title: str, vectors_dir: Path) -> list[str]`: wraps `html` as a one-lesson course in memory, builds a v3 plan with that lesson's scenes, practise and skipTopics plus placeholder intro and recap that pass, runs `check_plan`, and drops course-level-only errors (minimum scene count for the whole course, intro, recap). Also checks `htmlSha256`.
  - CLI: `storyplan.py check-lesson --video <id>.video.json --html <id>.html --lesson-id <id> --title "<title>" --vectors <dir>`; exit 0 ok, 1 problems.
  - `video.json` shape: `{"lessonId": str, "htmlSha256": str, "language": "hi", "scenes": [scene…], "practise": [{"topic": int, "tryIt": str, "task": str | None}], "skipTopics": [{"topic": int, "reason": str}]}`.

- [ ] **Step 1: Write failing tests**
  - `test_a_good_lesson_video_part_passes`: fixture lesson (2 sections, a table and a code run in section 1) and a hand-written valid `video.json` + vector SVG → `[]`.
  - `test_a_topic_the_lesson_does_not_have_fails` (Review Focus): scene with `topic: 3` → error naming `3`.
  - `test_a_number_not_in_the_lesson_fails`: narration speaks `9999` → the existing "number not in the lesson" error.
  - `test_a_stale_html_hash_fails`: wrong `htmlSha256` → error containing `rewrite it`.
  - `test_skip_topic_without_try_it_passes` (Review Focus).
- [ ] **Step 2: Run** `... -m pytest -q test_story_video.py -k lesson_video` — expect FAIL.
- [ ] **Step 3: Implement** `lesson_video_problems` and the CLI branch.
- [ ] **Step 4: Run** the whole `test_story_video.py test_lessonparts.py` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "Video: check one lesson's video part (storyplan check-lesson)"`

### Task 2: `merge` — build plan.json from the lessons' parts

**Files:**
- Modify: `skills/nerdit-story-video/scripts/storyplan.py`
- Test: `skills/nerdit-story-video/scripts/test_story_video.py`

**Interfaces:**
- Consumes: `scaffold`'s plan layout (refactor `scaffold` into `scaffold_plan(images_dir, course_path) -> dict` plus the writing step, so `merge` reuses it); Task 1 `lesson_video_problems`.
- Produces: `merge(images_dir: Path, course_path: Path, lessons_dir: Path) -> Path` writing `images/video/plan.json`: for each lesson, replaces its scaffolded scenes with the scenes of `lessons_dir/<id>.video.json`, fills its `practise` entries' `tryIt`/`task`, appends its `skipTopics`, copies `lessons_dir/video-vectors/<id>-*.svg` to `images/video/vectors/`. Intro and recap stay empty for the skill to write. CLI: `storyplan.py merge --images-dir <images> --course <course.json> --lessons-dir <workdir>`.

- [ ] **Step 1: Write failing tests**
  - `test_merge_fills_every_lesson_from_its_part`: two-lesson course, two valid parts → plan scenes equal the parts' scenes in lesson order; vectors copied; then `check_plan` errors are only intro/recap.
  - `test_merge_fails_on_a_missing_part` (Review Focus): error lists the lesson id.
  - `test_merge_fails_on_a_stale_part` (Review Focus): HTML hash in the course JSON content differs → error, no plan written.
  - `test_merge_fails_on_duplicate_vector_names` (Review Focus).
  - `test_merge_refuses_to_overwrite_an_existing_plan` (same rule as `scaffold`).
- [ ] **Step 2: Run** `-k merge` — expect FAIL.
- [ ] **Step 3: Implement.** Hash the lesson `content` from the course JSON, i.e. the same bytes as `<id>.html` the assembler reads (confirm `assemble_course.py` copies the file unchanged; if it normalises, hash after the same normalisation and say so in the docstring).
- [ ] **Step 4: Run** `test_story_video.py` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "Video: storyplan merge builds plan.json from lesson parts"`

### Task 3: Lesson gate runs the video check

**Files:**
- Modify: `skills/nerdit-chapter-generator/scripts/gate_lesson.py` (`gate(...)`: new parameter `video: bool = False`; CLI `--video`)
- Test: `skills/nerdit-chapter-generator/scripts/test_gate_lesson.py`

**Interfaces:**
- Consumes: Task 1 `lesson_video_problems` (import from `../../nerdit-story-video/scripts/storyplan.py` via `sys.path`, as other cross-skill imports in the repo do; check how `rules_pack.py` or `make_bundle.py` locates sibling skills and copy that).
- Produces: with `video=True`, a missing `<id>.video.json` is a failure `video: <id>.video.json missing`; its problems are failures prefixed `video: `. Without `--video` nothing changes.

- [ ] **Step 1: Write failing tests**: gate with `video=True` and no part → failure; with a valid part → no `video:` lines; with `video=False` → no `video:` lines either way.
- [ ] **Step 2: Run** `test_gate_lesson.py -k video` — expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `test_gate_lesson.py` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "Video: the lesson gate checks the lesson's video part"`

### Task 4: Rule pack carries the video rules

**Files:**
- Modify: `skills/nerdit-chapter-generator/scripts/rules_pack.py` (flag `--video`: appends `skills/nerdit-story-video/SKILL.md` §1 "Plan" items 2's scene rules, from "One topic per clip" through "practise", to the pack as `## Video part (only when VIDEO_PATH is given)`; output `rules-<preset>[-project][-video].md`)
- Modify: `skills/nerdit-story-video/SKILL.md` (mark that section with `<!-- pack: video -->` boundary comments so the cut is stable)
- Test: `skills/nerdit-chapter-generator/scripts/test_rules_pack.py`

**Interfaces:**
- Produces: `rules_pack.py --preset code --video --out <dir>` writes `<dir>/_rules/rules-code-video.md`, containing the scene rules and none of §2–§4 (voice, build, placement).

- [ ] **Step 1: Write failing test** `test_video_flag_appends_only_the_scene_rules`: pack contains "One topic per clip" and "practise", not "Voice and B-roll".
- [ ] **Step 2: Run** — expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `test_rules_pack.py test_docs_refs.py` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "Video: rule pack --video adds the scene rules for writers"`

### Task 5: Writer, orchestrator and video skill docs

**Files:**
- Modify: `agents/nerdit-lesson-writer.md` (new optional input `VIDEO_PATH`; when given, after the lesson passes its gate, write `<id>.video.json` and `video-vectors/<id>-t<n>-*.svg` from the lesson in context, set `htmlSha256`, run the gate with `--video`, return a fourth line `VIDEO: <path>`. Never write the video part before the lesson's own gate passes)
- Modify: `skills/nerdit-chapter-generator/SKILL.md` (Step 1: ask once "Make a story video for this course?"; Step 2b: pass `VIDEO_PATH` and the `-video` rule pack and `--video` in GATE; Step 5d note: run `storyplan.py merge` before the video skill)
- Modify: `skills/nerdit-story-video/SKILL.md` (§1: "If the lessons dir has `<id>.video.json` for every lesson, run `merge` instead of `scaffold`, then write only `intro` and `recap`, then `check`")
- Test: `skills/nerdit-chapter-generator/scripts/test_docs_refs.py` (existing doc-reference test must pass; add the new script names if it lists them)

- [ ] **Step 1:** Edit the three docs.
- [ ] **Step 2: Run** the full suites in both `scripts/` folders — expect PASS.
- [ ] **Step 3: Sync** to the plugin cache.
- [ ] **Step 4: Commit** `git commit -m "Video: writers write their lesson's video part when asked"`

### Task 6: Pilot on one existing lesson (measure the saving)

Not code.

- [ ] **Step 1:** Add `video-only` to `check_refresh.MODES` (it allows no change to the lesson's three files), with a test in `test_check_refresh.py` that any lesson change fails under it; commit.
- [ ] **Step 2:** Pick Advanced Regression `reg-adv-02`. Run one `nerdit-lesson-writer` with `SOURCE_PATH` = the delivered lesson, `REFRESH = video-only` and `VIDEO_PATH`.
- [ ] **Step 3:** Gate with `--video --before-dir … --modes video-only`; record the writer's token use against a full video pass for one lesson (from the Flask run's video session, or by running the old path once on the same lesson).
- [ ] **Step 4:** Report tokens and the check result to the owner. Stop for approval before enabling it by default.

## Order with the readability plan

Run `2026-10-28-lesson-readability-and-full-programs.md` first: both plans edit `agents/nerdit-lesson-writer.md`, `gate_lesson.py` and the orchestrator SKILL.md, and the video scenes must mirror the new page layout (programs, fewer case studies). This plan's Task 6 then pilots on a lesson already refreshed with the new rules.
