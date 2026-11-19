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

1. **Plan.** `python scripts/build_pack.py plan <workdir> --url COURSE_PAGE [--course-id ID] [--start YYYY-MM-DD] [--days 10]`
   `--url` is the live course page, `https://nerdit.in/course/<slug>/preview`. The admin import gives
   a course a new id and slug, so never build it from the JSON: ask the owner, or find the course's
   `<loc>` in `https://nerdit.in/sitemap.xml` by its title. `--course-id` is the live course's id when
   the owner gives it (the server also finds the course from the URL). Default start is tomorrow
   (IST); the dates are only a draft: the admin moves the whole pack so day 1 is the day after
   you upload it (owner's rule: a pack is made and uploaded on different days). It writes
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
   Only then go on.
4. **Build.** `python scripts/build_pack.py build <packdir>` draws every item (about 40 s per Reel),
   writes `pack.json` and runs the checks. Numbers in hooks and slide lines are checked against the
   lesson before anything is drawn. Fix every `PROBLEM` line in `pack-plan.json` (build rewrites
   `pack.json` from it) and run build again.
5. **Hand over.** Tell the owner the folder to import: Admin → Social posts → Import social pack →
   choose `<packdir>`. Nothing is posted until they approve it there.

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

## What the scripts do

- `source.py` reads the course; `dayplan.py` plans days and rotates five themes (navy, violet,
  light, ember, forest) and two layouts so no format repeats a look on consecutive days.
- `cues.py` rebuilds the story video's timeline from its plan and word timings, and stops if it no
  longer matches `clips.json` (rebuild the video first). Key ideas, terms and myth/fact lines appear
  when the narration reaches them.
- `reel.py` lays the frame, the clip (whole; only a clip over 90 s is cut, at a scene end) and the
  cues over each other with ffmpeg: 1080x1920, 30 fps, H.264 + AAC, the clip's own audio.
- `slides.py` builds carousels (cover, key ideas, the topic's diagram, a real quiz question that
  fits and its answer, closing slide) and Story/feed cards; `draw.py` draws them with Chromium.
- `captions.py` and `packcheck.py` are the checkers.

Tests: `cd scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
