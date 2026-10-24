---
name: nerdit-video-prompts
description: >
  Writes Google Veo / Flow video prompts for every topic of a NERDIT course: one shot list per
  numbered lesson section (1-12 shots of 8 seconds) in which a teacher explains the concept to
  students on camera with an everyday object, each shot a self-contained prompt with the same
  fixed people, plus overlay stills that carry the lesson's exact code,
  output and tables (Veo cannot draw text reliably). Built from the course output JSON, so every
  clip teaches what its section on the page teaches. Use when the user wants AI-generated video,
  Veo or Flow prompts, or video prompts per topic for a course ("generate video prompts for this
  course", "Veo prompts for each topic"). Never calls a video API.
---

# NERDIT Video Prompts (Veo)

**Any model** (Claude, OpenAI/Codex or another agent) can run this skill: it is these steps plus
Python scripts. Do the steps in order; `scripts/…` paths are relative to this skill's folder.
Run every command shown and read its output: a non-zero exit means stop and fix what it prints,
never skip it. Write the shot lists to the rules below; never invent names or values the
course does not have.

Scripts live in `scripts/` next to this file. `<dir>` is a new folder next to the course JSON,
e.g. `<course folder>/video-prompts`. Needs the `nerdit-story-video` and `nerdit-chapter-generator`
skills beside this one (it reuses their section reader and Title Case), and Playwright Chromium
for `--overlays`.

## 1. Briefs

`python scripts/topic_briefs.py --course <course_output.json> --out <dir>` writes
`<dir>/briefs.json`. Add `--world <course_world.json | name>` (e.g. `fvc-institute`) when the
course has a world: the briefs then carry its fixed `setting` and `cast` (name, role, `visual`),
so the same people appear in every topic and in every course on that world. The world's
trainer (a cast role such as trainer or teacher, e.g. Fatima in `fvc-institute`) becomes the
`presenter`; without one, the fixed default Professor Mehta teaches. Per numbered lesson section, its slot key (`<lessonId>-t<N>-video`, the same
key the admin's Videos box uses), heading, prose, key terms, worked examples (`code1`, `code2`:
code and the output the lesson prints), tables (`table1` …) and every number the section uses.

## 2. Write the shot lists

Read `briefs.json` and write `<dir>/prompts.json` (format in `scripts/check_prompts.py`). Work
one lesson at a time. For every topic:

- **A teacher explains, students learn.** The clip is a lesson, not a story: the presenter
  stands at the front table and explains the concept to a small group of students, using an
  everyday object that makes it obvious (slips of paper sorted into piles for a count, a
  tray with rows and compartments for a table, two jars of marbles for a rate, a weather
  forecast card for a prediction). Pick objects every Indian student knows.
- **As short as the idea allows: 1–12 shots of 8 seconds.** One clear idea (a definition, one
  rule) is one 8-second teach shot. A topic with a worked example uses 3 or more shots in the
  section's own order: the question → the idea → the section's example on an overlay → what
  the output means → the mistake or takeaway. Never pad a topic to make it longer.
- **Cast (with a world):** every Veo shot lists `cast`, names from the world only (`[]` for an
  empty room). The sheet repeats each named character's `visual` word for word, so Veo draws the
  same person every time. Never invent another named person. The business owner is a real
  person: mention them in the voiceover, never show them.
- **`teach` shots carry the explanation.** Every topic opens with one, and at least half the
  shots are teach shots. `prop` names the object; `action` (10+ words) says what the teacher
  does with it, step by step, so the idea is visible; `voiceover` is the line the teacher says
  to the students on camera (lip-synced). `camera` names one move (slow push-in, close-up on
  the object, static medium shot). `cast` may add world characters as students or helpers.
- **`veo` shots** (optional) show the idea in real life without the teacher: `visual` (15+ words),
  e.g. Neha logging an enquiry at the front desk; the teacher's voice continues over it.
- Never ask Veo for written words: no quoted text, captions, labels, code or logos in `prop`,
  `action` or `visual` — the check refuses them.
- **`overlay` shots carry exact facts.** `show` names the section's own `code1` / `table1`;
  `highlight` (`line:3`, `row:O2`, `col:amount`) marks what the voiceover reads out. A clip of 3
  or more shots shows at least one of the section's examples; keep overlays to half the shots or
  fewer.
- **voiceover** ≤ 22 words per shot (8 seconds): what the teacher says, in a professional,
  warm classroom tone for a beginner — the concept first, then what the object shows.
  `language: "english"` by default (Veo speaks English most clearly); `"hinglish"` only when the
  owner asks. Speak every key term from `terms`. Every number spoken must be in the brief's
  `numbers` — never invent one.
- **style** (one line, shared by every Veo shot so clips match): setting, light, palette,
  realism, e.g. "Realistic modern Indian training institute, soft daylight, navy and teal
  accents, clean desks, natural skin tones, shallow depth of field, calm documentary feel."
- A topic that needs no video goes in `skip` with a reason.

## 3. Check, sheet and overlays

`python scripts/check_prompts.py --dir <dir> --overlays`. Fix every `ERROR` and run again. On
success it writes `<dir>/prompts.md` (each Veo prompt ready to paste, each overlay with its still
and voiceover line) and `<dir>/overlays/<key>-sNN.png` (1280×720, the lesson's exact code and
output or table, in the lesson's styles).

Tell the user:
1. Generate each portrait (the teacher, and the world's characters) from the sheet's "Character references" once,
   save as `cast/<Name>.png`, and reuse them for every course on that world.
2. In Veo / Flow, generate each Veo shot from `prompts.md` (8 s, 16:9), attaching the portraits
   the shot lists ("Ingredients to Video"). Regenerate a shot if a face, hand or object looks
   wrong, or if any text appears.
3. In a video editor, place the shots in order, with each overlay still on screen for 8 s and its
   voiceover line recorded (or TTS) over it.
4. Export one MP4 per topic named by its slot key, upload to YouTube (Unlisted), then in the admin
   Import JSON + Images → Videos box paste each link next to the same key → Apply video links.
   Topic slots come from the story video's `place_video.py`, or "Add video slot" in the admin.

## Never

- Invent numbers, names, prices or results the section does not contain.
- Ask Veo to draw code, tables, numbers or any words; those go on overlays.
- Call a video API, upload, or publish anything.
