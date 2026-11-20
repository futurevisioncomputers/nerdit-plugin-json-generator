# brand-studio in NERDIT, part 2a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Social packs for courses without a story video, the course intro carousel as a pack item, and the story video's thumbnail drawn by brand-studio in the course's look.

**Architecture:** brand-studio gets a small library API (`brand_studio.api`) that renders a set of pages to named files and returns problems instead of printing. nerdit-social-posts makes the video optional (topics from the lesson headings, no Reels) and adds an `intro` carousel item rendered through that API. nerdit-story-video's thumbnail calls the API's thumbnail page. Part 2b (separate plan, later) moves every other post kind and the Reel frames onto brand-studio and unifies the never-repeat record.

**Tech Stack:** Python 3.14 (C:\Python314), Playwright, pytest (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`); brand-studio installed editable (`python -m pip install -e brand-studio-plugin/engine`).

**Spec:** `nerdit-plugin-json-generator/docs/superpowers/specs/2026-11-20-brand-studio-design.md` (section "NERDIT integration", decisions 1, 5, 9, 10). Part 1 plan: `docs/superpowers/plans/2026-11-20-brand-studio-engine.md`.

## Global Constraints

- Every existing test stays green: nerdit-social-posts (169), nerdit-story-video, brand-studio (90). Contract tests stay unchanged; tests that encode "the video is required" change because the spec makes it optional.
- A course with a story video plans and builds exactly as today (Reels, cues, covers, pad).
- Without `images/video/`: no Reel items; stories, carousels and LinkedIn cards keep their days and times; the 19:00 slot stays empty.
- The intro is a plan item of format `carousel` with `"kind": "intro"` on day 1 of a course's first pack (it takes day 1's carousel slot, adding one when day 1 has none); `pack.json`, the server and the admin import are unchanged.
- One look per course: the intro and the thumbnail share the course's brand-studio look (history key = course slug).
- When brand_studio is not installed, the NERDIT skills stop with: `brand-studio is not installed: python -m pip install -e <brand-studio-plugin>/engine`.
- Owner rules hold: light pages, lesson titles word for word, numbers only from the course, no "free certificate", pilot first.

## Review Focus

- A course with a story video still gets its Reels, cues and covers unchanged (Task 2 test).
- A course without a video and without numbered lesson sections: plan stops with a clear message instead of an empty pack (Task 2 test).
- A second pack of the same course: no second intro item (Task 3 test).
- Intro words left empty or untrue in `pack-plan.json`: build refuses before drawing, naming the field (Task 3 test).
- The owner's own photo with a dark background for the thumbnail: refused with its file name (Task 4 test).

---

### Task 1: brand-studio library API

**Files (repo `brand-studio-plugin`):**
- Create: `engine/brand_studio/api.py`
- Modify: `engine/brand_studio/cli.py` (render_set calls the API, then prints and writes the contact sheet), `engine/brand_studio/pages.py` (a photo dict may carry `"path"`: an absolute file used instead of the library copy)
- Test: `engine/tests/test_api.py`

**Interfaces:**
- Produces: `api.render_set_to(brand_id: str, key: str, page_list: list[tuple[str, dict]], out_dir: Path, names: list[str], *, marker: Path | None = None, look_from: str | None = None, photos: dict[int, dict] | None = None, jpeg: bool = False) -> tuple[list[Path], list[str]]` — same look/photo/check logic as Part 1's `cli.render_set` (one look per course, variants alternate, learn items drop when they do not fit); `names[i]` is the file stem for page i; `photos[i]` forces page i's photo; returns (files written, problems); writes and records nothing when problems is non-empty. `api.photo_from_file(path: Path, facing: str) -> tuple[dict | None, str | None]` — a photo dict `{"path", "bg", "facing", "file"}` or a problem (`"<name>: background #xxxxxx is too dark for a light page"`).
- `cli.render_set` keeps its signature and output (Part 1 tests unchanged).

- [ ] **Step 1: Failing tests** `test_render_set_to_writes_named_files_and_returns_no_problems` (fixture course + words from test_content, names `["d01-intro-01", ...]`, jpeg=True → six `.jpg` files with those stems), `test_render_set_to_returns_problems_and_writes_nothing`, `test_forced_photo_from_file_is_used_and_dark_one_refused` (`photo_from_file` on a light grey PNG gives a dict; on a dark one gives the problem; a thumbnail with `photos={0: that dict}` renders and its HTML used the file).
- [ ] **Step 2:** Run → FAIL (no `api`).
- [ ] **Step 3:** Implement; move the body of `cli.render_set` into `api.render_set_to`.
- [ ] **Step 4:** Whole brand-studio suite passes.
- [ ] **Step 5:** Commit "feat: library API for NERDIT".

### Task 2: Social packs without a story video

**Files (repo `nerdit-plugin-json-generator`, skill `nerdit-social-posts/scripts`):**
- Modify: `source.py:23-56`, `dayplan.py:45-64`, `slides.py` (`card_spec`, `topic_picture`), `build_pack.py` (plan stops when there are no topics)
- Test: `test_source.py`, `test_dayplan.py`, `test_slides.py`, `test_pack.py`

**Interfaces:**
- Produces: `load_source(workdir)` without `images/video/` returns `video: None`, `plan: {"scenes": []}`, `has_video: False`, and `clips` made from `storyplan.lesson_topics(course_path)`: `[{"key": f"{lessonId}-t{n}", "lessonId", "topic": n, "title": heading, "place": "topic", "video": False}]` in lesson order; `course.title` = the JSON title stripped (video plan fallback only when a plan exists). With the folder present but `plan.json` or `clips.json` missing it still stops as today. `day_plan` gives no `reel` item for a clip with `"video": False`. `plan_pack` stops with `"no lesson topics found (numbered '<n> — Title' sections) and no story video: nothing to plan"` when `clips` is empty.

- [ ] **Step 1: Failing tests** `test_no_video_folder_loads_topics_from_headings` (replaces `test_missing_video_folder_stops_with_youtube_studio_hint`; asserts `has_video is False`, clips keys `demo-01-t1`, `demo-01-t2`, titles from the headings), `test_video_folder_without_clips_json_still_stops`, `test_no_video_means_no_reels_but_stories_carousels_and_cards_keep_their_days` (day_plan from a no-video src: no reel items; stories every day at 10:00; carousels Tue/Fri; feed Mon/Wed/Thu), `test_card_spec_without_video_uses_a_lesson_figure`, `test_plan_without_topics_or_video_stops_with_a_clear_message`, and `test_course_with_video_plans_exactly_as_before` (existing fixture: same items as before the change).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** whole social suite passes. **Step 5:** Commit "feat(social-posts): packs for courses without a story video".

### Task 3: Intro carousel item

**Files:**
- Modify: `nerdit-social-posts/scripts/build_pack.py` (plan adds the item; build renders it), `packcheck.py` (truth and fact checks before drawing), `SKILL.md` (the intro words and the item)
- Create: `nerdit-social-posts/scripts/intro.py`
- Test: `test_intro.py`

**Interfaces:**
- Consumes: `brand_studio.api.render_set_to`, `brand_studio.content.course_facts`, `intro_pages`, `truth_errors`, `facts_errors`, `brand_studio.brands.load_brand`.
- Produces: `intro.WORDS_SKELETON` (the brand-studio words shape with empty strings: 3 question cards, 4 skill cards, icons `{"hook": "brain", "learn": "laptop"}`); `intro.add_intro(items: list[dict], src: dict, first_pack: bool) -> None` (when `first_pack`: day 1's carousel becomes, or day 1 gains, `{"id": "d01-intro", "format": "carousel", "kind": "intro", "time": "13:00", "platforms": ["instagram", "linkedin"], "lessonId": <first lesson>, "topic": 1, "intro": WORDS_SKELETON copy, "captions": {"instagram": "", "linkedin": ""}}`, keeping items sorted by date and time); `intro.intro_errors(item: dict, src: dict) -> list[str]` (empty words fields named `"d01-intro: intro.hook.headline is empty"`, plus `facts_errors` and `truth_errors` prefixed with the item id); `intro.render_intro(item: dict, src: dict, out_dir: Path) -> list[str]` (media names `d01-intro-01.jpg` … `-06.jpg`; history key = the course JSON's `slug`, else `src["name"]`; marker = `<packdir>/pack-plan.json`). `first_pack` = `used_topics(workdir, pack_id)` is empty. `plan_text_errors` runs `intro_errors` for intro items; `render_items` calls `render_intro` for them.

- [ ] **Step 1: Failing tests** `test_first_pack_gets_an_intro_on_day_one`, `test_second_pack_gets_no_intro`, `test_intro_takes_day_ones_carousel_slot_or_adds_one`, `test_empty_or_untrue_intro_words_stop_the_build_naming_the_field`, `test_intro_renders_six_slides_with_item_names` (fixture workdir, words filled, tmp `BRAND_STUDIO_HOME` with icons; media list `d01-intro-01.jpg`…`-06.jpg`).
- [ ] **Step 2:** FAIL. **Step 3:** Implement; SKILL.md: how to fill `intro` (words rules from brand-studio's SKILL.md) and that the intro uses the course's look. **Step 4:** social suite passes. **Step 5:** Commit "feat(social-posts): course intro carousel on a course's first pack".

### Task 4: Story-video thumbnail through brand-studio

**Files:**
- Modify: `nerdit-story-video/scripts/build_video.py:144-185` (`make_thumbnail`, `thumbnail_html` stays for old plans only if referenced by tests; otherwise removed), `nerdit-story-video/SKILL.md`
- Test: `nerdit-story-video/scripts/test_story_video.py` (new tests at the end)

**Interfaces:**
- Consumes: `api.render_set_to`, `api.photo_from_file`, `content.course_facts`, `content.thumbnail_page`.
- Produces: `make_thumbnail(vid: Path, plan: dict, course_path: Path) -> Path` writes `vid/thumbnail.jpg` (1280x720) with the course's look (`look_from` = course slug); key idea = `plan["thumbnail"]["key_idea"]`, else the first scene's `keyIdea`; photo = `plan["thumbnail"]["photo"]` (a file in the video folder, the owner's photo, facing from `plan["thumbnail"].get("facing", "left")`) when named, else a library cutout. Problems stop with the joined messages.

- [ ] **Step 1: Failing tests** `test_thumbnail_uses_the_course_look_and_a_library_photo`, `test_thumbnail_takes_the_owners_photo_when_named`, `test_dark_owner_photo_is_refused_with_its_name` (tmp `BRAND_STUDIO_HOME`, fixture course and plan).
- [ ] **Step 2:** FAIL. **Step 3:** Implement; update every caller of `make_thumbnail` to pass the course path; SKILL.md: thumbnail section. **Step 4:** story-video suite passes. **Step 5:** Commit "feat(story-video): thumbnail drawn by brand-studio in the course's look".

### Task 5: Pilot

Not code.

- [ ] Workdir for Supervised Learning Classification (no video): `classification-course/work/course-supervised-learning-classification_output.json` from `design-pilot\`.
- [ ] `build_pack.py plan` (live URL), fill the intro words (reuse `design-pilot\words-classification.json`), captions for the pilot items, `build_pack.py pilot`; check passes.
- [ ] Show the owner the pilot (intro + a teaching carousel + a Story + a LinkedIn card); stop for their OK (pilot-first). Part 2b plan follows.
