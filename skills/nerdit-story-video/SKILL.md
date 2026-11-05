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

**Lessons written with a video part.** When the chapter generator's workdir holds a
`<id>.video.json` for every lesson, run `python scripts/storyplan.py merge --images-dir <images>
--course <course.json> --lessons-dir <workdir>` instead of steps 1–2: the scenes, Try It cards
and vectors come from the writers. Write only `intro` and `recap`, then go to step 3. A missing or
stale part fails the merge: rewrite that lesson's part, never fill the gap by hand.

1. `python scripts/storyplan.py scaffold --images-dir <images> --course <course.json>` writes
   `<images>/video/plan.json` (version 3, `"complement": true`): for every numbered lesson section
   one `vector` concept scene titled with the section heading and an empty `clips` entry; plus
   `availableFigures`, every SVG figure in the lessons by id and label. It copies none of the
   page's tables or code: the video adds to the page (step 2).
   **Revising a course that already has a video** (owner, 2026-11-05): add `--previous
   <old images>/video/plan.json`. Each clip then lists the old clip's `oldKeyIdeas`; watch the old
   clip, and before writing scenes fill `oldVideo` (≤ 160 chars: what it taught, what it did well,
   what stayed unclear) and `decision`: `keep` (port its scenes, adding only the new fields),
   `revise` (fix what stayed unclear) or `create` (no old clip covered it). `check` fails a clip
   without both. Never redo a clip only to make it longer.
<!-- video-pack:start -->
2. Read each section, then write a clip that **adds what the page cannot give** (owner,
   2026-11-05, supplementary video strategy). The page already teaches the facts, steps, tables,
   code and its walk; the clip makes the hard part easy to picture and remember. The page is the
   foundation, the video a different way in. **Keep the video's look** (owner, 2026-11-05: improve
   the teaching inside it, never redesign it): the large picture on the left does the teaching,
   the KEY IDEA panel on the right holds one takeaway, diagrams build up one change at a time,
   and each clip ends on the "Now practise" card.

   | The page already has | The clip adds |
   |---|---|
   | a definition | a picture or analogy of it, and why it matters |
   | a code walk, line by line | what the program is for: the flow of a request or of the data |
   | step-by-step instructions | the whole workflow at once, and why the steps come in that order |
   | a worked example | a different scene from the course world that shows the same idea |
   | a table | what its numbers mean: the comparison drawn, the trend shown |
   | an output | what the result tells you, never the result read out |

   - **A clip only where it helps.** Give a section a clip when it has a process in several steps,
     data moving between parts, two similar ideas to compare, a decision with different outcomes,
     a hidden mechanism to make visible, a mistake the lesson itself warns about (its cause and
     its consequence), or several ideas working together. A section the page already makes clear
     (a short definition, one simple command, something a static figure already shows) goes in
     `skipTopics` with a `reason`; never stretch it into a clip. Fewer, more useful clips beat a
     clip per heading, and no two clips teach the same thing (`check` fails a repeated objective).
   - **Say what each clip is for** in `clips`, one entry per topic with scenes:
     `{"lessonId", "topic", "objective"` (≤ 120 chars: what the learner understands after it)`,
     "pageHas"` (≤ 160 chars: what the page already covers, so the clip does not repeat it)`,
     "adds"` (≤ 160 chars: what it gives beyond the page)`, "format"}`, the format one of
     `process` (a workflow or system), `comparison` (two ways side by side), `story` (an abstract
     idea through a scene), `case-study` (a decision from the course world), `whiteboard`
     (reasoning step by step), `hybrid`. Each scene's `purpose` (≤ 90 chars) says what it teaches.
   - **Never read the page aloud.** No narration repeats 8 or more words in a row from the lesson
     (`check` fails it); explain the idea another way.
   - **One topic per clip.** Every scene names `topic`: the number of the lesson section it
     explains (the `2 — …` heading). The build cuts one clip per topic and places it at the end
     of that section; the top bar always shows the page's own heading. Keep a topic's scenes
     together. A topic's first scene must stand on its own: never "पिछले part में" or "as we saw".
   - **Shape of a clip** (a guide; combine or drop a step that does not help):
     1. **Hook**: open on the learner's question, a surprising result or a small problem ("Why
        does the page load without its colours?"), never "इस video में" or "In this video" (`check`
        fails it).
     2. **Setup**: the parts involved, drawn on the left (browser and server, a form and its data).
     3. **Mechanism**: build the picture in stages: what goes in, what happens, what changes, what
        comes out. One meaningful change per step, never the finished complex diagram at once.
     4. **Compare on the same input** when the lesson has two similar ways: one example, rule A
        and its result beside rule B and its result, the exact difference marked (a slash as a
        piece boundary, a missing field), and when to use each. Never compare things the lesson
        does not set side by side.
     5. **Outcome**: the result the learner will meet: a response, an error, a missing file, a
        changed output. Label it in words as well as colour ("matched" / "not matched", "valid" /
        "invalid", before / after): colour never carries the meaning alone. When showing an error,
        show its cause; when showing success, show what made it work.
     6. **Connect to the implementation**: end the mechanism at the one code line, formula or
        action that uses it (the view receiving the captured value), highlighted alone.
     7. **Misconception** (`myth`) only when the lesson itself warns about it, never one invented
        to fill a scene.
     8. **Now practise**: the card's question (below).
     Keep stages apart that learners confuse, when the lesson has them: URL matching is not
     running the view; calling a function directly (as many lesson examples do) is not an HTTP
     request. Never draw a browser or request for code the lesson only calls.
     `storyplan.py check` fails a topic whose first scene after B-roll is not a `vector` or
     `diagram`. Length follows the idea: one simple idea 45–75 s, a process 60–100 s, a comparison
     or a multi-stage mechanism 90–150 s. `check` asks at least 2 scenes and 90 words, and fails
     over 340 words (about 150 s): cut a bigger idea to the one thing the clip adds.
   - **Pick the picture for the subject**, inside the same layout: programming and APIs: data
     flow, request and response, state changes; web pages: page structure, file paths, before and
     after; computer basics: parts and input-process-output; networks: packets and routes;
     databases: tables, relationships, a query's path; maths: step-by-step transformations, number
     lines; science: a process, cause and effect, a labelled model; business: a workflow, a
     decision tree, a customer journey; office tools: screen-area callouts and task order; theory:
     an analogy, a hierarchy, a comparison. Never force every topic into a flowchart.
   - **table** and **code** scenes are optional, at most one of each per clip: the page already
     shows them. Use one only when pointing at it explains the idea better than a drawing.
     `table: 1` / `code: 1` count from 1 in page order; `highlight` marks at most 2 rows, columns
     (`row:<first cell>`, `col:<column>`) or lines (`line:3`), in the order the narration names
     them. Say what the code is for and what one key line does, never each line in turn (the
     page's code walk does that), tie it to the picture or the output it causes, and say what the
     output means, never read it out. Never change the lesson's code, library, terms or output in
     the video; when the lesson looks wrong or unclear, add `{"topic", "issue"}` to `reviewFlags`
     (`check` prints it as `REVIEW` for the owner and does not fail) and explain the page as it is:
     "This program answers every visit to the home page; the decorator line is what connects
     the URL to the function."
     **Explain, don't read (owner, 2026-11-04):** put a line in backticks only when it is short
     (up to 30 characters, like `@app.route("/home")`); a longer line is described by what it
     does: "the last line takes only the routes whose endpoint is home and prints their paths,
     sorted", never "print sorted r dot rule for r in…". `check` fails a longer span.
     Code in backticks is spoken as a teacher reads it (`pronounce.py`: "app dot get decorator slash
     products slash one": a decorator is named as one (owner, 2026-11-04); quotes and brackets silent, `==` "is equal to", ` < ` "is less than",
     `<=` "is at most", ` * ` "times", ` - ` "minus"; a route's `<id>` stays silent); the screen keeps the
     real code. Never spell symbols out yourself.
   - Every key term the section bolds is spoken in its clip.
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
     **Explain the drawing (owner, 2026-11-04):** in a new plan (`"explain": true`), every part
     shows faintly from the start, turns solid at the moment the narration names it, and glows
     while it is explained (arrows appear just before the box they lead to). So the narration
     walks the diagram: it names each labelled part (a word of its label; a code label such as
     `@app.route` in backticks), in drawing order, inside a sentence that says what it does or
     means ("the browser sends a request"), never as a list of labels read out. `check` fails a
     scene that skips a part or names them out of order. `scaffold` and `merge` set `explain`.
   - **diagram** scenes reuse a lesson figure (`figure`: an id from `availableFigures`) when it
     already explains the idea.
   - **broll** scenes (at most 30%) set context with a real clip: `query` is 2–5 plain English
     words (`students in classroom`, `office laptop typing`); never a person's name or a brand.
     Use B-roll to open a topic, never to explain it.
   - Characters and quizzes are not used in the video.
   - **narration**: 2–6 short sentences (at most 550 characters) for a first-time learner, professional instructor tone,
     not storytelling: the concept first, then the course example. The plan's `language` sets
     the style (owner, 2026-10-27): **`hi` (default)** is Hinglish the way a good Indian teacher speaks it: correct Hindi grammar and
     Hindi verbs (खड़ी होकर, शुरू होने के बाद, check करें), English for technical terms and key
     nouns, never an English verb forced into Hindi grammar ("stand करके"); at least 30% English
     words; Hindi words in Devanagari so the Hindi voice says them right. **`en-IN`** (on request)
     is natural Indian English, the way a friendly Indian instructor talks in class: short spoken
     sentences, contractions ("you'll", "it's"), "so", "now", "notice", at most a few Hindi words;
     at least 80% English words. Only the lesson's facts; any number spoken must appear in that lesson. Say each
     `terms` entry out loud (1–3 per scene).
   - **keyIdea** (≤ 90 chars, English) is the KEY IDEA panel: one sentence a learner gets at a
     glance, the takeaway of the picture on the left; never a copy of the narration and never a
     concept the picture does not show. `check` fails more than one sentence. There are no captions.
   - **focus** (optional, up to 4, not on B-roll): `{x, y, zoom, at}` with x, y 0–1 across the
     box, zoom 1–2.5, `at` a spoken word. End with `zoom: 1` to show the whole.
   - **myth** on 1–3 scenes where the lesson itself warns about the misconception: `wrong`,
     `right` (≤ 80 chars, English) and a `narration` saying both, in the plan's language.
   - **intro** `points` (2–4) and `narration`; **recap** `points` (3–5) and `narration`.
   - **Screen text is English** (owner, 2026-11-03): titles, points, `keyIdea`, `terms`, myth lines,
     `tryIt`, the practise `question` and every word drawn in a vector. Hindi goes only in the narration; `check` fails
     Devanagari anywhere on screen.
- **practise** (one entry per topic, scaffolded): every topic clip ends with a silent
  "Now practise" card, so the learner reads, watches, then practises the same idea at once.
  `question` (≤ 90 chars, English, ends with "?") checks the clip's idea, not code copying:
  predict what happens next, identify which part is responsible, choose the right path, explain
  why an error occurs, compare two outcomes, or apply the idea to a new small case ("Which part
  sends the response back?"). Never the page's own Try It again: `check` fails a question that
  names the Try It's example (`a/b.txt`) or reuses most of its words. The card shows the question
  first and stays 7 seconds (4 without one).
  Fill `tryIt` (≤ 60 chars) with what that section's Try It asks ("fill in `should_retry`").
  When the chapter has a practice starter, set `task` to the starter task this clip leads to;
  otherwise leave it `null`. The script writes the file name from the lesson's files spec
  (`Pack: L02-practice-starter.ipynb, Task 1`); never type it. `check` fails a topic without an
  entry, a section with no Try It, or a task the starter does not have.
<!-- video-pack:end -->
3. `python scripts/storyplan.py check --images-dir <images>`. Fix every error and run again.

## Pilot first (owner, 2026-11-04): never pay for the whole course before a check

A full run costs every voice character and hours of render; a fault found afterwards is paid
again. Check in this order, and stop at the first step the owner is not happy with:

1. **Plan check** (above): free, seconds.
2. **Stills**: `python scripts/build_video.py --images-dir <images> --stills [--only <lessonId>]`
   writes `<images>/video/stills/<lessonId>.jpg`, one frame per scene at the end of its build-up,
   timed from the narration's length, before anything is recorded: free, seconds. Look at every
   sheet yourself: text touching a box edge, unreadable code, an empty panel, a wrong diagram.
3. **Pilot topic**: pick the most code-heavy topic; `python scripts/voice.py --images-dir <images>
   --only <lessonId>:<topic>` (about 1,500 characters), then `python scripts/build_video.py
   --images-dir <images> --only <lessonId>:<topic>` writes `<images>/video/pilot/pilot-*.mp4` in under
   a minute. Give the owner that clip and wait for their OK.
4. **Full run** (sections 2-3). The voice is cached: a clip whose text and voice settings are
   unchanged is not recorded again (its `.key` file matches), so a fix re-records only the scenes
   it changed, and the pilot's clips are reused.

## 2. Voice and B-roll

- `python scripts/voice.py --images-dir <images>`: Google Chirp 3 HD, `voice.name` default
  `hi-IN-Chirp3-HD-Achird` (male), `voice.rate` 0.9.
  `python scripts/voice.py --list-voices hi-IN` lists the alternatives; try two or three and
  keep the one the owner prefers. **Owner's choice (2026-11-04), after comparing it on the same
  text with `hi-IN-Chirp3-HD-Aoede` (the Flask course video's voice):** Achird at 0.9 — crisper
  consonants, the same pace as Aoede, and a male voice to match the owner's photo on the
  thumbnails. Default spelling; no presenter, lip-sync or voice conversion (all tried and
  rejected; `voice.spelling: "devanagari"` exists but is not used). Google is called once per
  sentence, so each sentence's words are timed from where it really starts.
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

**Thumbnail (owner, 2026-11-04):** the course has one story video, so one thumbnail. Copy the
owner's own photo (only theirs; the AI-styled suit photo they chose) to
`<images>/video/presenter.jpg` and set `"thumbnail": {"photo": "presenter.jpg"}` in the plan; the
build then writes `thumbnail.jpg` with the photo on the right and NERDIT, the course title and
"Full course explained" on the left. `--thumbnail-only` redoes it for an already built video.

Rendering takes about 1.5× the video's length with 3 workers (a 2-hour course took 3 hours).
Run it in the background, with its output in a log; it prints a line per worker every 5 video
minutes. Give the user that estimate before starting. Run the video scripts with the Python
that has `imageio-ffmpeg` (`python -s` hides a user-site install).

It also cuts **one clip per topic** (`clip-02-<lessonId>-t1.mp4`, …), an intro clip and a recap
clip, and lists them in `clips.json` with each clip's key, place and YouTube title.

## 4. Place the clips in the course

`python scripts/place_video.py --images-dir <images> --course <course .with-images.json>` writes
`<course>.with-images.with-video.json`: one empty slot per clip. A topic clip goes at the end of
its section, the intro clip before the first lesson's first section, the recap clip before the
last lesson's cheat sheet. Each slot carries its clip's whole seconds in `story.mp4`
(`data-start`/`data-end`); a re-run adds them to slots placed before.

Tell the user: upload `story.mp4` ONCE to YouTube (Unlisted, Allow embedding on, not made for
kids; a video over 15 minutes needs a phone-verified channel) with `title.txt`, `thumbnail.jpg`,
and a description of at most 5,000 characters; then in the admin, Import JSON + Images → the
bundle (or the `.with-video.json` and the images folder) → in the **Videos** box paste the link
once in **One video for the whole course** → Fill all slots → preview → publish. Each slot plays
only its own part; the classroom sends a seek outside it back to its start and starts with
captions off. (The per-slot boxes still take one clip upload per slot, for a course without times.)
Empty slots stay hidden from learners. Look at the thumbnail and one frame per scene kind first.
Never upload an MP4 to Firebase.

## Never

- Invent numbers, names or events that the lessons do not contain.
- Put characters, quizzes or captions in the video.
- Show code, tables or numbers that differ from the page: use `table`/`code` scenes, never redraw them.
- Read the page aloud, re-walk its code line by line or repeat its examples and exercises.
- Put an API key in a file, a plan or a message.
- Upload, publish or share the video, or use a cloned voice for anything public.
