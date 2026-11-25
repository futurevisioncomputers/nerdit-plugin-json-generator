---
name: nerdit-trend-reels
description: >
  Makes a 15-second Trend Reel for NERDIT's social accounts: collects today's AI-and-jobs news, keeps only safe
  stories two outlets confirm, picks the best idea, has the Flow presenter "Dev" say a checked script (Google
  Flow in the owner's Chrome), checks what Dev actually said, adds the news card, captions and course end card,
  and uploads the Reel to the admin's Social posts as a PENDING post for the owner's one-tap Approve. Never presses
  Approve. Use when the owner says "make trend reel", "weekly trend reel" or "trend reel about <story>". Also runs
  by itself Monday, Wednesday, Friday (daily) and Sunday (weekly) ("nerdit-trend-reels: scheduled run, kind ...",
  started by Task Scheduler).
---

# NerdIT Trend Reels

Claude-only: Flow and the admin are driven with the claude-in-chrome tools (load them with ToolSearch first) in
the owner's Chrome, signed in to flow.google.com and fv.nerdit.in. Design:
`docs/superpowers/specs/2026-11-24-trend-reels-design.md` in this plugin. Rules for picking stories and writing:
`references/editorial.md`. Flow prompt: `references/flow-prompt.md`.

`<scripts>` is this skill's `scripts/` folder; run each as `python <scripts>/<name>.py`. Each one prints what is
wrong and exits 1; fix the input (rewrite the script or captions), never the checker.

## Never

- Press **Approve**, "Approve & post now", Schedule or Delete in Social posts. The owner's tap posts the Reel.
- Spend Flow credits past `runs.py credits`, buy credits, upgrade the plan, or download "1080p Upscaled" (paid).
- Put text on the video that says it is AI-generated (disclosure is the platform flag), or name a real person as Dev.
- Use a story that fails `references/editorial.md`, or a number not in a kept story.
- Re-roll a clip more than once in a run. A scheduled run never asks anyone: it stops and reports.

## Run

Kind: `daily` (Mon/Wed/Fri, or "make trend reel") or `weekly` (Sunday, or "weekly trend reel").

1. **Start.** `runs.py new <kind> <short-slug>` prints the run folder (`<run>`). In Flow, open the account menu
   (avatar, top right) and read "N Google Flow credits". `runs.py credits <N>`: exit 1 → write the report "Flow
   credits run out until <reset date>" and stop. Write `<run>/run.log` lines as you go (credits before, each step).
2. **Collect.** `collect.py --days 2 --out <run>/trends.json` (weekly: `--days 7`).
3. **Check.** Follow `references/editorial.md`: open links, keep only stories that pass, map each to a live course
   with `mcp__nerdit__catalogue_status` (course URL `https://nerdit.in/course/<slug>/preview`), write
   `<run>/checked.json`. Nothing kept → report "No safe story today; no credits spent." and stop.
4. **Ideas.** 3 ideas, `chosen` and `reason` in `<run>/ideas.json`; check `runs.py recent` first.
5. **Script.** Write `<run>/script.json` (`kind`, `line`, `card` {`chip` e.g. "AI & JOBS  ·  25 NOV 2026", `facts`,
   `sources`}, `course` {`id`, `title`, `lessons`, `url`}). Run `script_check.py <run>` until it passes.
6. **Flow.** Open the project "NERDIT trend reels" (first run: rename "Nov 24 - 18:15" to it). Turn the Flow
   Agent switch off. Settings: Video → Ingredients → 9:16 → model `Omni 1.2 Flash` (if Flow has retired it, the
   newest Omni model; say so in the report) → 720p → length slider to fit the line (about 2.5 words a second, at
   most 15 s) → x1. Read "Generating will use N credits". Attach the character "Dev - NERDIT presenter" with "+",
   paste the prompt from `references/flow-prompt.md` with the line, Generate. When done, open the clip, download
   "720p Original" (free), then `runs.py take-download <run>` (copies the newest MP4 from Downloads to
   `<run>/clips/clip1.mp4`).
7. **Transcript.** `transcript.py <run>`. On fail: read the credits again; `runs.py credits <N> --reroll` exit 0 →
   one new take (same prompt), download it, `runs.py take-download <run>` again, and run `transcript.py` again. Still failing (or the re-roll is not
   allowed) → report "Dev did not say the script: <errors>. Nothing uploaded." with both takes' paths, and stop.
8. **Compose and captions.** `compose.py <run>`. Write `<run>/captions.json` (instagram, facebook, youtube, and
   pinterest; `{link}` for the course link; each names "Source: <outlets>"; Instagram says "link in bio" and asks
   to save or share; YouTube = title line, blank line, description). `trend_captions.py <run>` until it passes.
9. **Upload as pending.** `runs.py ready <run>` must print "ready". Then fv.nerdit.in → Social posts → new post:
   Name = the hook; Instagram caption and LinkedIn & Facebook text from `<run>/captions_filled.json`; "Or a Reel" =
   `reel.mp4`; "YouTube title" and "YouTube description" from the YouTube caption; tick "Contains AI-generated
   person"; "Spoken language" English; Create. **Do not press Approve.** Chrome's file upload refuses files under
   `~/.nerdit-social` from an interactive session: copy `reel.mp4` into the session's scratchpad (or working folder)
   first; if the file input still cannot be set, report "Upload failed; the Reel is at <path>" and stop. Save the
   new post's id in `<run>/posted.json` as `{"post_id", "status": "pending"}`.
   Until the server change that sends YouTube the AI flag is live (the form shows "Contains AI-generated person"),
   untick YouTube and leave the flag off: the Reel goes to Instagram and Facebook only.
10. **Report.** Write `<home>/last-report.md` (`<home>` = the folder above `<run>`): first line is the notification,
    "Trend Reel '<hook>' is waiting for your Approve in Social posts. credits left: N, enough for M more Reels before
    <D Mon>." Then the story, outlets, course and checks. For earlier runs whose `posted.json` says pending, read the
    row in Social posts and update it (`posted` with links, or still pending: mention it). For an earlier row now
    posted, open its Instagram link once and note whether Meta shows "AI info"; say so when it is missing.

Every stop also writes `last-report.md` with the reason on the first line.

## Scheduled run

`scripts/scheduled_run.ps1` (registered by `scripts/schedule_task.ps1`, Mon/Wed/Fri/Sun 11:30) starts
`claude -p "Use the nerdit-trend-reels skill: scheduled run, kind <daily|weekly>. ..."`. Follow Run exactly with
that kind. Nobody is watching: never ask, take the steps' "stop and report" exits, and keep to the pinned script
paths the prompt gives. The runner shows the first line of `last-report.md` as a desktop notification; the
server emails the owner when the pending Reel is created.

## Files in a run folder

`trends.json`, `checked.json`, `ideas.json`, `script.json`, `clips/clip1.mp4`, `transcript.json`, `overlays/`,
`reel.mp4`, `captions.json`, `captions_filled.json`, `checks.json`, `posted.json`, `run.log`.
