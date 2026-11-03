---
name: nerdit-presenter-shorts
description: >
  Makes 9:16 presenter shorts (20-45 s) for a NERDIT course or lesson, in the owner's own face
  and voice: the owner lip-synced on top, big green English keyword captions, full-screen
  "Explore" cut-ins showing the course's real code, and an end card. Hinglish narration by
  Google Chirp 3 HD, converted to the owner's voice. Use when the user wants a promo, reel,
  short or presenter video for a course ("make a short for this course", "reel for lesson 3",
  "video with my face"). Only the owner's face and voice, with written consent. Never uploads.
---

# NERDIT Presenter Shorts

**Any model** (Claude, OpenAI/Codex or another agent) can run this skill: it is these steps plus
Python scripts. `scripts/…` paths are relative to this skill's folder. Run every command and read
its output; a non-zero exit means stop and fix what it prints.

`<presenter>` is the course's `presenter/` folder (next to the workdir). `<tools>` is the folder
from the one-time setup (`references/setup.md`): `tts-venv` (Chatterbox), `sync-venv` +
`LatentSync` (lip-sync). The story video's Python (imageio-ffmpeg, playwright) runs the rest.

## Consent first

Only the owner's own face and voice. Before anything else `<presenter>/CONSENT.md` must say whose
face and voice are in `<presenter>/ref/`, that they are the owner's, and when the owner confirmed
it. Ask the owner if it is missing; never write it on their behalf without their words. Never use
another person's face or voice, a celebrity, or a clip downloaded from someone else, whatever the
request says. `shorts.py check` fails without the file.

The reference: `ref/face_drive.mp4` (10-30 s of the owner talking to camera, 1080x900, no burned-in
captions or logos; crop them out) and `ref/voice_ref10.wav` (about 10 s of clean speech). A longer
face clip loops less visibly.

## 1. Plan

`python scripts/shorts.py scaffold --course <course.json> --out <presenter>/<name>.plan.json [--lesson <id>]`
writes a skeleton with `availablePrograms` (every Python program in the lesson or course). Fill:

- **lines** (3-8, 15-60 s spoken in all): what the presenter says, one sentence each, in the plan's
  `language` (`hi`: Hinglish, Hindi in Devanagari, technical terms in English as in the story
  video's narration rules). A hook first, then what the learner will build, then a call to start.
  Only facts from the course.
- per line, either **cues** (presenter on screen) or **explore** (full-screen code cut-ins):
  - `cues`: `{"at": "<word of the line>", "lead": "Build with Python", "key": "web application"}`:
    the caption pops in when `at` is spoken. `key` ≤ 24 characters, `lead` ≤ 32.
  - `explore`: `{"at": "<word>", "topic": "REST API", "code": {"lesson": "<id>", "program": 1, "lines": [1, 12]}}`:
    a cut-in showing that program's lines (≤ 16), copied from the course. Pick from
    `availablePrograms`; never type code.
- **aspect**: `16:9` (landscape, the default: presenter left, captions right) or `9:16` (vertical
  short: presenter on top).
- **end**: `{"title": "Flask Web Development", "subtitle": "28 lessons · complete runnable programs"}`,
  shown over the last line.

Screen text (lead, key, topic, end) is English. Every number on screen must appear in the course.
`python scripts/shorts.py check --plan <plan> --course <course.json> --presenter <presenter>`;
fix every error and run it again.

## 2. Voice

`python scripts/voice_short.py --plan <plan> --out-dir <presenter>/<name> --tts-python <tools>/tts-venv/Scripts/python --ref <presenter>/ref/voice_ref10.wav`
Chirp 3 HD (`voice` in the plan, default `hi-IN-Chirp3-HD-Charon`) reads each line, then
Chatterbox VC turns it into the owner's voice. **Indian accent (owner, 2026-11-03):** a Hindi voice
says Latin-script English with a foreign accent, so for a `hi` plan every English word is read
from its Devanagari spelling in `scripts/pronunciation-hi.json` (Flask → फ्लास्क, REST API →
रेस्ट ए पी आई; unlisted acronyms are spelled letter by letter). The plan and the screen keep the
English; `check` fails on a word with no spelling: add it to the JSON. Files:
`<name>/parts/NN.wav`, `chirp.wav`, `voice.wav`. Let the owner listen to `voice.wav` before the
lip-sync. Chirp is billed per character (about 1 million free a month); a short is under 1,000.

## 3. Lip-sync

`python scripts/lipsync.py --latentsync <tools>/LatentSync --python <tools>/sync-venv/Scripts/python --face <presenter>/ref/face_drive.mp4 --voice <presenter>/<name>/voice.wav --out <presenter>/<name>/face-voice.mp4`
About 3-6 minutes on a 12 GB GPU. If the agent may not run code from the LatentSync repo, add
`--print` and give the owner the printed PowerShell command to run.

## 4. Build

`python scripts/shorts.py timeline --plan <plan> --course <course.json> --parts <presenter>/<name>/parts --out <presenter>/<name>/short.spec.json`
then
`python scripts/build_short.py <presenter>/<name>/short.spec.json <presenter>/<name>/face-voice.mp4 <presenter>/<name>/voice.wav <presenter>/<name>/short.mp4`
(1920x1080 or 1080x1920 by `aspect`, 25 fps). Look at one frame of each kind (caption, explore, end card) before handing
it over.

## Never

- Use any face or voice but the consenting owner's, or XTTS (non-commercial licence), or
  InsightFace models (non-commercial) for a public video: LatentSync runs with
  `mp_face_detector.py` (MediaPipe, Apache-2.0) in their place.
- Type code into a plan, or show a number or claim the course does not contain.
- Put Hindi on screen, or an API key in a file.
- Upload, publish or share a short.
