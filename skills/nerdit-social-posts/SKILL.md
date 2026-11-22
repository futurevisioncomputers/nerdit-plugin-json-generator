---
name: nerdit-social-posts
description: >
  Turns one NERDIT course folder into a ready-to-import social pack for the next days (default 10):
  Instagram/Facebook Reels cut from the course's own topic videos (the clip's Hinglish narration,
  English keyword captions timed to the voice, rotating themes), Instagram/LinkedIn carousels with a
  real quiz slide, Story and LinkedIn feed cards with a lesson diagram, and captions per platform
  checked against written rules. Everything is made on this PC; the admin's "Import social pack" page
  takes the folder. Use when the user wants posts for a course ("make a social pack", "posts for this
  course", "make Reels from the course videos", "plan social media for this course"). Never uploads
  or posts anything.
---

# NERDIT Social Posts

**Any model** (Claude, OpenAI/Codex or another agent) can run this skill: it is these steps plus
Python scripts. Do the steps in order; `scripts/…` paths are relative to this skill's folder. Run
every command shown and read its output: a non-zero exit means stop and fix what it prints, never
skip it. The scripts draw and cut everything; your job is the words: hooks, slide lines and captions,
written to the rules below. Never upload, post or schedule anything, and never put an API key in a
file or a message.

`<workdir>` is the course folder: it holds `course-<name>_output.json` and `images/video/` made by
`nerdit-story-video` (`plan.json`, `clips.json`, `audio/`, the `clip-*.mp4` topic videos). Python
needs `imageio-ffmpeg`, `playwright` (Chromium; an existing Playwright Chromium build is used) and
`Pillow`. If `images/video/` is missing, `plan` stops: ask the owner to download the original MP4
from YouTube Studio (their own upload) and re-run the story-video split, or to make the pack
without Reels.

## Steps

0. **Trend refresh** (whenever `plan` says "No fresh looks left", and at least once a month). Owner's
   rule: never the same design twice, always new inspiration. Each course takes one brand-studio look
   for all its posts (intro, carousels, Stories, LinkedIn cards, Reels, video thumbnail), and no other
   course may use it; NERDIT has 13 looks today. Look at every image in `~/.nerdit-social/inspiration/`
   (posts the owner saved because they liked them) and, if you can browse, at current design-trend
   round-ups for social posts. From the general ideas only (colour mood, type feel, motif) write a new
   look JSON for brand-studio (`name`, `inspiration`, `palette`, `fonts`, `motif`; shape and rules in
   brand-studio's SKILL.md) and add it with `brand-studio refresh nerdit <look.json>`; it prints
   `checks passed` or the problems to fix. Never copy a creator's layout, art, characters, text or
   brand. Pages are light (owner, 2026-11-20: no dark backgrounds; code panels stay dark); the checker
   refuses a dark page. New looks appear in the next pilot for the owner's OK.
1. **Plan.** `python scripts/build_pack.py plan <workdir> --url COURSE_PAGE [--course-id ID] [--start YYYY-MM-DD] [--days 10]`
   `--url` is the live course page, `https://nerdit.in/course/<slug>/preview`. The admin import gives
   a course a new id and slug, so never build it from the JSON: ask the owner, or find the course's
   `<loc>` in `https://nerdit.in/sitemap.xml` by its title. `--course-id` is the live course's id when
   the owner gives it (the server also finds the course from the URL). Default start is tomorrow
   (IST); the dates are only a draft: the admin moves the whole pack so day 1 is the first free
   day after you upload it. Packs run one after another, never on the same day as another pack
   (owner's rules: a pack is made and uploaded on different days; courses do not share a day). It writes
   `<workdir>/social-pack/<name>-<start>/pack-plan.json` (`<packdir>`) and refuses to replace an
   existing one (`--force` replaces it).
   Per day: a Reel (19:00) and a Story card (10:00) on Instagram + Facebook; Tuesday and Friday a
   carousel (13:00, Instagram + LinkedIn); Monday, Wednesday, Thursday a LinkedIn feed card (09:30).
   One topic per day, in course order, never repeated; a later pack for the same course skips the
   topics earlier packs used, so it continues the course. Times are IST. Reels carry the clip's
   narration with a soft background pad that ducks under the voice; `--no-pad` (or `"pad": false`
   in `pack-plan.json`) leaves the narration alone.
2. **Write the words** in `pack-plan.json`. Change only `hook`, `slides[].text`/`hook`, and
   `captions`. Leave ids, dates, times, formats and themes as they are. `platforms` may only change
   when the owner asks (reel and story: instagram, facebook; carousel and feed: any of instagram,
   facebook, linkedin).
   - Reel `hook`: drawn above the video. English, one idea, at most 2 lines (about 28 characters a
     line). The plan fills it with the topic's key idea; sharpen it into a claim or a named mistake.
   - Carousel `slides`: `slides[0].hook` is the cover (at most 4 lines of about 18 characters, must
     make sense alone in the feed). `idea` slides: one idea each, at most 6 lines of about 22
     characters. Keep the `diagram`, `quiz`, `answer` and `cta` slides as made: they come from the
     lesson.
   - `captions`: one per platform the item goes to (rules below). Story captions stay empty.
3. **Pilot.** `python scripts/build_pack.py pilot <packdir>` renders the first Reel and the first
   carousel into `<packdir>/pilot/` and checks them. **Stop here.** Show the owner the Reel, its
   cover and the slides, and wait for their OK. Apply what they ask and run the pilot again.
   Only then go on: write `<packdir>/pilot/OWNER_OK` holding the date and the owner's words. The
   project hook (`hooks/nerdit_hooks.py pre-shell`) refuses `build_pack.py build` without that file.
4. **Build.** `python scripts/build_pack.py build <packdir>` draws every item (about 40 s per Reel),
   writes `pack.json` and runs the checks. Numbers in hooks and slide lines are checked against the
   lesson before anything is drawn. Fix every `PROBLEM` line in `pack-plan.json` (build rewrites
   `pack.json` from it) and run build again.
5. **Hand over.** Tell the owner the folder to import: Admin → Social posts → Import social pack →
   choose `<packdir>`. Nothing is posted until they approve it there.

## Courses without a story video, and the course intro (brand-studio, owner 2026-11-20)

- **No video?** A workdir without `images/video/` still plans: topics come from the lessons' numbered sections
  (`<n> — Title`), and the pack has no Reels (stories, carousels and LinkedIn cards keep their days). Get the
  course JSON from the admin (Data manager, View all courses, Export JSON) and save it as
  `course-<name>_output.json` in the workdir.
- **Intro carousel.** A course's first pack opens with item `d01-intro` (format carousel, `"kind": "intro"`) in
  day 1's carousel slot: six slides (why learn, real questions, what you'll learn, real project, skills, call
  to action) drawn by the brand-studio plugin in the course's own look, the same look as its video thumbnail.
  Fill its `intro` words in `pack-plan.json` from the lessons only (shape and rules: brand-studio's SKILL.md):
  hook headline and subline, 3 question cards (text + keyword), project text, 4 skill cards, cta subline.
  Lesson titles and the project title come from the course JSON; numbers in headlines, the hook and the cta
  only from lesson counts, durations and titles. `pilot` and `build` stop on empty or untrue words. Write the
  intro's Instagram and LinkedIn captions like any carousel's. Needs brand-studio installed
  (`python -m pip install -e <brand-studio-plugin>/engine`).

## Teaching posts and looks

- For each topic the plan takes the lesson's own blocks, word for word: **Guess the output**
  (question + code, then the answer), **Wrong vs right** (mistake and fix), **Data → code → result**
  (the data table, the code, its output) as carousels, and the lesson's **Cheat sheet** as a Story
  card (once per course) or LinkedIn card. Do not edit their code, outputs, tables or lesson
  sentences: `pilot` and `build` check every drawn word against the lesson and stop on any change.
  You write only the cover hooks and the captions. A topic without a usable block keeps the
  key-idea carousel and the picture card.
- Every post of a course is drawn by brand-studio in the course's one look (the same as its intro
  and video thumbnail; owner 2026-11-20: the theme changes per course). `plan` reserves it and prints
  `course look: <name>`. Posts alternate two arrangements day by day, and carousel covers and closing
  slides carry a student photo picked by mood (thinking on the cover, confident on the close). The
  record is `~/.brand-studio/nerdit/history.json`; do not edit it. `~/.nerdit-social/style-history.json`
  is no longer used.
- Slide and card limits (characters a line, lines) are brand-studio's (`pages.guard`), checked when
  the plan picks a block and again before drawing; Devanagari on a page is refused.

## Caption rules (the checker enforces each)

- Instagram: at most 2200 characters and 8 hashtags. The first sentence is a claim or a named
  mistake, never a question. At least one call to action: comment (give a keyword, e.g.
  "Comment VENV"), save or share. Say "link in bio"; no URL (`http://`, `https://`, `www.`).
- Facebook: the course link with UTM (write `{link}`; build fills it in), at most 5 hashtags,
  community tone.
- LinkedIn: at most 3000 characters and 5 hashtags, the course link (`{link}`), professional and
  career-oriented, English only (no Devanagari).
- Hinglish in Roman script is fine on Instagram and Facebook. On-screen text is always English.
- Every number in a caption or slide appears in the lesson. No invented results, numbers or
  student claims; nothing that contradicts the lesson.
- Stories take no caption.
- UTM (made by build): `utm_source=<platform>&utm_medium=social&utm_campaign=pack-<item date>&utm_content=<item id>`.
- YouTube (every Reel, `captions.youtube`): the title on the first line (1-100 characters, English, no
  link), a blank line, then the description with `{link}`; at most 5000 characters and 15 hashtags; no
  `<` or `>`. YouTube is not in the item's `platforms`: the server never sees it.

## YouTube Shorts (owner 2026-11-20: Studio kit now, automatic upload after YouTube's audit)

Every Reel also goes to https://www.youtube.com/@nerditSkillLearning as a Short. YouTube Stories no
longer exist (shut down June 2023) and community Posts have no API. API uploads stay private until
the Google project passes YouTube's audit, so for now the owner uploads a kit in YouTube Studio:

1. Write `captions.youtube` for every Reel (rules above). `build` then writes `<packdir>/youtube/`:
   a copy of each Reel named after its title and `SHORTS.md` (day, date and time IST, title,
   description with the filled link, tags, and the settings to use once).
2. After the owner imports the pack, packs queue, so the admin shows the real Day 1. Run
   `python scripts/build_pack.py shorts <packdir> --start <Day 1>` to move every date in the kit.
3. Hand over `<packdir>/youtube/`: in YouTube Studio, upload up to 15 at once, paste each title and
   description, and schedule each at its date and time. `youtube/` is never uploaded by the admin.

## What the scripts do

- `source.py` reads the course; `dayplan.py` plans the days (its themes are only a fallback for
  packs planned before part 2b).
- `cues.py` rebuilds the story video's timeline from its plan and word timings, and stops if it no
  longer matches `clips.json` (rebuild the video first). Key ideas, terms and myth/fact lines appear
  when the narration reaches them.
- `reel.py` lays the frame, the clip (whole; only a clip over 90 s is cut, at a scene end) and the
  cues over each other with ffmpeg: 1080x1920, 30 fps, H.264 + AAC, the clip's own audio.
- `slides.py` builds carousels (cover, key ideas, the topic's diagram, a real quiz question that
  fits and its answer, closing slide) and Story/feed cards; `studio.py` turns them into brand-studio
  pages and renders them in the course's look; `draw.py` draws the Reel overlays (in the course's
  colours) with Chromium.
- `captions.py` and `packcheck.py` are the checkers.

Tests: `cd scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
