---
name: nerdit-video-prompts
description: >
  Writes Google Veo / Flow video prompts for every topic of a NERDIT course: one shot list per
  numbered lesson section (7-12 shots of 8 seconds), each Veo shot a self-contained prompt with
  scene, camera and the narrator's line, plus overlay stills that carry the lesson's exact code,
  output and tables (Veo cannot draw text reliably). Built from the course output JSON, so every
  clip teaches what its section on the page teaches. Use when the user wants AI-generated video,
  Veo or Flow prompts, or video prompts per topic for a course ("generate video prompts for this
  course", "Veo prompts for each topic"). Never calls a video API.
---

# NERDIT Video Prompts (Veo)

Scripts live in `scripts/` next to this file. `<dir>` is a new folder next to the course JSON,
e.g. `<course folder>/video-prompts`. Needs the `nerdit-story-video` and `nerdit-chapter-generator`
skills beside this one (it reuses their section reader and Title Case), and Playwright Chromium
for `--overlays`.

## 1. Briefs

`python scripts/topic_briefs.py --course <course_output.json> --out <dir>` writes
`<dir>/briefs.json`: per numbered lesson section, its slot key (`<lessonId>-t<N>-video`, the same
key the admin's Videos box uses), heading, prose, key terms, worked examples (`code1`, `code2`:
code and the output the lesson prints), tables (`table1` …) and every number the section uses.

## 2. Write the shot lists

Read `briefs.json` and write `<dir>/prompts.json` (format in `scripts/check_prompts.py`). Work
one lesson at a time. For every topic:

- **7–12 shots, 8 seconds each**, in the section's own order: the question it answers → the
  idea → the section's worked example → what the output means → the common mistake → the
  takeaway.
- **`veo` shots explain.** `visual` (15+ words) is one continuous 8-second scene: who, where,
  what they do, what objects show the idea (a counsellor sorting enquiry cards into two piles,
  a shopkeeper comparing two receipts). People are generic Indian professionals and students in
  an institute, office or shop. `camera` names one move (slow push-in, static wide, gentle pan
  left). Never ask Veo for written words: no quoted text, captions, labels, code or logos —
  the check refuses them.
- **`overlay` shots carry exact facts.** `show` names the section's own `code1` / `table1`;
  `highlight` (`line:3`, `row:O2`, `col:amount`) marks what the voiceover reads out. Show at
  least one of the section's examples; keep overlays to half the shots or fewer. Open with a
  Veo shot.
- **voiceover** ≤ 22 words per shot (8 seconds), professional teacher tone, beginner-friendly.
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
1. In Veo / Flow, generate each Veo shot from `prompts.md` (8 s, 16:9). Keep the same style
   line; regenerate a shot if a face, hand or object looks wrong, or if any text appears.
2. In a video editor, place the shots in order, with each overlay still on screen for 8 s and its
   voiceover line recorded (or TTS) over it.
3. Export one MP4 per topic named by its slot key, upload to YouTube (Unlisted), then in the admin
   Import JSON + Images → Videos box paste each link next to the same key → Apply video links.
   Topic slots come from the story video's `place_video.py`, or "Add video slot" in the admin.

## Never

- Invent numbers, names, prices or results the section does not contain.
- Ask Veo to draw code, tables, numbers or any words; those go on overlays.
- Call a video API, upload, or publish anything.
