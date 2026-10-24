---
name: nerdit-story-video
description: >
  Turns a NERDIT course into a narrated concept-explainer video for YouTube, built from animated
  vector graphics (process flows, trees, bar and line charts, comparisons drawn from the lesson's
  own data), the lessons' SVG figures and short Pexels B-roll: intro card, key-idea panel, key
  terms that pop in when spoken, camera moves, misconception checks and a recap card. No quizzes,
  no characters, no captions. Professional instructor narration in Hinglish with a natural Google
  Chirp 3 HD voice. Use when the user wants an explainer, recap or narrated video for a course
  ("make a video for this course", "explain these lessons in a video"). Never uploads anywhere.
---

# NERDIT Story Video

**Any model** (Claude, OpenAI/Codex or another agent) can run this skill: it is these steps plus
Python scripts. Do the steps in order; `scripts/…` paths are relative to this skill's folder.
Run every command shown and read its output: a non-zero exit means stop and fix what it prints,
never skip it. The scripts build the video; your job is the plan's words, written to the rules
below. Never put an API key in a plan, a file or a message.

Scripts live in `scripts/` next to this file. `<images>` is the `images/` folder next to the
course JSON (the video lives in `<images>/video/`). Python needs `imageio-ffmpeg`, `edge-tts`
(fallback voice) and `playwright` (Chromium; an existing Playwright Chromium build is used if
present). Keys, in the user's environment only, never in a plan or a message:
`GOOGLE_TTS_API_KEY` (Cloud Text-to-Speech) and `PEXELS_API_KEY` (B-roll).

## 1. Plan

1. `python scripts/storyplan.py scaffold --images-dir <images> --course <course.json>` writes
   `<images>/video/plan.json` (version 3): for every numbered lesson section, a `vector` concept
   scene, then a `table` scene for each of the section's tables and a `code` scene for each of
   its worked examples (up to 2 each), all titled with the section heading; plus
   `availableFigures`, every SVG figure in the lessons by id and label.
2. Read each section, then write its clip so it **mirrors the page** (4–7 scenes, 90–180 s):
   - **One topic per clip.** Every scene names `topic`: the number of the lesson section it
     explains (the `2 — …` heading). The build cuts one clip per topic and places it at the end
     of that section; the top bar always shows the page's own heading. Keep a topic's scenes
     together. A topic's first scene must stand on its own: never "पिछले part में" or "as we saw".
   - **Follow the section's order, explaining first:** what the idea is and the problem it
     solves (`vector`) → how it works and when to use it (a second `vector` or the lesson's own
     `diagram`) → the case study from the course world (`table`) → the page's worked example
     (`code`) → the common mistake (`myth`) or the takeaway. Never open a topic with a story or
     with the table or code; `storyplan.py check` fails a topic whose first scene after B-roll
     is not a `vector` or `diagram`.
   - **table** scenes redraw the section's own table (`table: 1` = its first). `highlight`
     lists `row:<first cell>` / `col:<column>` in the order the narration names them; say the
     row or column out loud as it lights up, following the page's reading steps.
   - **code** scenes show the section's own code (`code: 1` = its first) typed line by line,
     then the output the lesson prints. `highlight: ["line:3"]` marks the line the narration
     explains. Read the key line and the output aloud: "print(enquiry["branch"]) Citylight
     देता है".
   - Every key term the section bolds is spoken in its clip; each clip has at least 3 scenes and
     180 words. A section that needs no video goes in `skipTopics` with a `reason`.
   - **Explain with visuals, not people.** Most scenes are `vector`: an animated SVG you write
     to `<images>/video/vectors/<file>.svg` that shows the idea's structure:
       - a **process** (boxes and arrows, one step appearing per sentence),
       - a **tree** (a question splitting into branches),
       - a **bar or line chart** built from the lesson's own table values,
       - a **comparison** (two columns: wrong way / right way, before / after),
       - a **funnel or flow** of records (enquiry → demo → enrolment).
     Draw with the figures.md templates' markup: `viewBox` about 480×360 (4:3, the video box),
     `role="img"`, an `aria-label`, `class="nerdit-anim"` on `<svg>`, parts in `<g>` with the
     lesson classes `na-show`, `na-slide`, `na-draw` (lines and arrows up to 80 units long; the lesson CSS draws only 80, so longer lines use `na-show`), `na-pulse` (only inside a `na-show` group: it pulses but never hides, so on its own it shows from the first frame)
     and `style="--d:…s"` delays in reading order, colours only as `var(--token)`, text large
     (16–22 units). Every number and capitalised name drawn must be in that lesson; chart values
     come from its tables. The build stretches the delays so the drawing finishes at 80% of the
     scene's narration: order the parts in the order the narration names them.
   - **diagram** scenes reuse a lesson figure (`figure`: an id from `availableFigures`) when it
     already explains the idea.
   - **broll** scenes (at most 30%) set context with a real clip: `query` is 2–5 plain English
     words (`students in classroom`, `office laptop typing`); never a person's name or a brand.
     Use B-roll to open a topic, never to explain it.
   - Characters and quizzes are not used in the video.
   - **narration**: 2–6 short sentences (at most 550 characters) for a first-time learner, professional instructor tone,
     not storytelling: the concept first, then the course example. Hinglish the way a good Indian
     teacher speaks it: correct Hindi grammar and Hindi verbs (खड़ी होकर, शुरू होने के बाद,
     check करें), English for technical terms and key nouns. Never force an English verb into
     Hindi grammar ("stand करके"). At least 30% English words. Only the lesson's facts; any
     number spoken must appear in that lesson. Say each `terms` entry out loud (1–3 per scene).
   - **keyIdea** (≤ 90 chars, English) is the on-screen takeaway; there are no captions.
   - **focus** (optional, up to 4, not on B-roll): `{x, y, zoom, at}` with x, y 0–1 across the
     box, zoom 1–2.5, `at` a spoken word. End with `zoom: 1` to show the whole.
   - **myth** on 1–3 scenes where the misconception is the lesson: `wrong`, `right` (≤ 80 chars)
     and a Hinglish `narration` saying both.
   - **intro** `points` (2–4) and `narration`; **recap** `points` (3–5) and `narration`.
- **practise** (one entry per topic, scaffolded): every topic clip ends with a 4-second
  "Now practise" card, so the learner reads, watches, then practises the same idea at once.
  Fill `tryIt` (≤ 60 chars) with what that section's Try It asks ("fill in `should_retry`").
  When the chapter has a practice starter, set `task` to the starter task this clip leads to;
  otherwise leave it `null`. The script writes the file name from the lesson's files spec
  (`Pack: L02-practice-starter.ipynb, Task 1`); never type it. `check` fails a topic without an
  entry, a section with no Try It, or a task the starter does not have.
3. `python scripts/storyplan.py check --images-dir <images>`. Fix every error and run again.

## 2. Voice and B-roll

- `python scripts/voice.py --images-dir <images>`: Google Chirp 3 HD, `voice.name` default
  `hi-IN-Chirp3-HD-Aoede`, `voice.rate` 1.0. `python scripts/voice.py --list-voices hi-IN` lists
  the alternatives; try two or three and keep the one the owner prefers.
  Google and edge voices speak code words respelled from `scripts/pronunciation.json` (JSON →
  Jason, dict → dictionary, json.dumps → Jason dot dumps; snake_case, dotted names, camelCase and
  acronyms are handled by `scripts/pronounce.py`). Only the audio changes; the screen keeps the real
  spelling. When the owner hears a word said wrong, add it there, and confirm any entry that
  changes the meaning (dict → dictionary) with them first.
  `--engine edge` (free, synthetic-sounding) and `--engine clone` (local XTTS test only, needs
  `say` in Devanagari and `--python`/`--ref`) remain available.
- `python scripts/broll.py --images-dir <images>` downloads one Pexels clip per B-roll scene to
  `video/broll/` and records the credit for the description.

## 3. Build

`python scripts/build_video.py --images-dir <images> [--workers 3] [--music <file>]` writes
`story.mp4` (1280×720), `thumbnail.jpg`, `title.txt` and `description.txt` (YouTube chapters and
Pexels credits) to `<images>/video/`. It re-runs the plan check first. `stage.html` draws every
frame; open it and call `renderAt(seconds)` to inspect a moment.

It also cuts **one clip per topic** (`clip-02-<lessonId>-t1.mp4`, …), an intro clip and a recap
clip, and lists them in `clips.json` with each clip's key, place and YouTube title.

## 4. Place the clips in the course

`python scripts/place_video.py --images-dir <images> --course <course .with-images.json>` writes
`<course>.with-images.with-video.json`: one empty slot per clip. A topic clip goes at the end of
its section, the intro clip before the first lesson's first section, the recap clip before the
last lesson's cheat sheet.

Tell the user: upload each clip to YouTube (Unlisted) with its title from `clips.json`; then in
the admin, Import JSON + Images → the `.with-video.json` and the images folder → in the **Videos**
box paste each clip's YouTube link next to its slot (same key as the file name) → Apply video links → preview → publish.
Empty slots stay hidden from learners. Look at the thumbnail and one frame per scene kind first.
Never upload an MP4 to Firebase.

## Never

- Invent numbers, names or events that the lessons do not contain.
- Put characters, quizzes or captions in the video.
- Show code, tables or numbers that differ from the page: use `table`/`code` scenes, never redraw them.
- Put an API key in a file, a plan or a message.
- Upload, publish or share the video, or use a cloned voice for anything public.
