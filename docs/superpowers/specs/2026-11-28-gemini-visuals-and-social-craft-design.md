# Gemini visuals and social craft: design

Date: 2026-11-28. Status: draft, waiting for the owner's OK.

## 1. Why

- The owner: Google Flow (Veo) and Nano Banana make better visuals than our code-drawn cards. Gemini should do the
  graphics and creative part of social posts and news-style Reels.
- The owner shared three public repos to learn from, all MIT licensed:
  - `Jakeschincariol/instagram-agent-skill`: 13 Instagram skills and 5 local scripts (hook scorer, beat timer,
    caption fold check, humanizer, swipe file).
  - `sergebulaev/linkedin-skills`: 12 LinkedIn skills (20 hook formulas, humanizer, planner, repurposer).
  - `jdepoix/youtube-transcript-api`: a Python library that reads a YouTube video's captions.
- Use their ideas to add skills and improve ours, for nerdit.in content.
- Success: posts that stop the scroll and bring new people, the same goal as Trend Reels, with no new monthly bill.

## 2. What the owner chose

- All four visual slots:
  1. Trend Reel scenes: Veo shots cover Dev for a few seconds while his voice keeps playing.
  2. Course post pictures: a hero picture on carousel covers, Story cards and LinkedIn cards.
  3. Course Reel openers: a short Veo scene at the start of each course Reel.
  4. Thumbnails and covers: a picture behind the title on YouTube thumbnails and carousel covers.
- No API keys. Only subscriptions: Google AI Pro (Flow, 1,050 credits a month, resets on the 8th; Gemini app) and
  Claude.

## 3. Goals, non-goals, anti-goals

Goals
- The four visual slots above, made with Flow and the Gemini app on the subscription.
- The repos' best rules turned into checker scripts that every caption, hook and script must pass.
- Research from real numbers: which hook shapes work on YouTube Shorts in our niche, and which of our own posts
  worked.
- Gemini CLI does the writing steps where it is as good as Claude (news search, picture and scene prompts).

Non-goals
- No paid APIs or API keys (no Veo or Imagen API; none of the linkedin-skills paid services: Apify, Publora,
  Pixfaro).
- No bot comments, DMs or replies on other people's posts.
- No scraping of Instagram or LinkedIn.
- No change to posting: the admin's "Import social pack" and auto-post keep working as they do.
- No change to the admin or the server. Pictures end up inside rendered pages and Reels, which the pack already
  carries.

Anti-goals (a failure even if it runs)
- AI pictures replacing teaching content. Diagram, code, quiz and data slides stay drawn from the lesson.
- AI pictures or video with words, numbers, code, logos or real people in them. Code draws all text.
- Dark pages. The light-background rule stays.
- Trend Reels stopping because openers used the credits.
- A generic stock-footage look. The owner turned that down on 24 Nov.

## 4. Constraints (facts)

- Flow has no API, and neither does the Gemini app. Something must click in Chrome. Today Claude in Chrome
  already drives Flow for Trend Reels.
- Flow video costs about 4 credits a second (Omni 1.2 Flash, 720p). 1,050 credits a month. Trend Reels use about
  60 credits each, 4 a week, which is about 1,040 a month. This is the hard limit (section 8).
- Flow video carries a visible watermark in India. The picture watermark and picture cost are not known yet
  (Phase 0).
- Claude Code hooks (writer GATE, maths words, OWNER_OK, stop-pack) fire only in Claude Code. After a Gemini CLI
  step, the conductor must run the checker scripts itself.
- YouTube blocks transcript reading from cloud IPs. youtube-transcript-api runs on this PC only, never in GitHub
  Actions or Cloud Functions.
- Memory rules that apply: build through the plugin only, with each rule and its checker together; pilot first
  with owner OK; light backgrounds; one look per course; no confirmation asks after "ok", but push and deploy
  need approval.
- brand-studio is a separate plugin (its own private repo). Picture slots in its pages are a change there too.

## 5. Approaches: who makes the pictures and video

- **A. Gemini writes, Claude in Chrome clicks, scripts judge (chosen).** Gemini CLI writes the scene and picture
  prompts and does the news search. Claude (Sonnet) opens Flow or the Gemini app in the owner's Chrome, pastes
  each prompt and downloads the result. Scripts check and compose. Why: the Chrome driving is proven and already
  guarded, Gemini's built-in Google search is fresh and free on the owner's login, and Gemini CLI has no Chrome,
  so a news page it reads cannot steer the signed-in admin.
- **B. Gemini does everything, including the browser, through a Chrome DevTools MCP.** Dropped: a new, untested
  driver in the owner's signed-in Chrome, where the admin is open. Every safety rule would need copying. One bug
  could post from the wrong place.
- **C. The owner clicks.** Gemini writes a prompt sheet, the owner makes the pictures by hand, and an apply step
  picks up the files. This is the lesson-illustrator pattern. Kept as the fallback ("manual" mode) when Chrome
  automation fails. It cannot run on a timer.

## 6. Layout

```
                 Conductor: Claude session, or scheduled_run.ps1 on a timer
                 (reads the step table, runs each step, runs its checker)
                                     |
   +----------------+----------------+-------------------+-----------------+
   | Gemini CLI     | Claude Sonnet  | Claude in Chrome  | Scripts (free)  |
   | gemini -p      | claude -p      | (Sonnet)          |                 |
   | news search,   | hooks, script, | Flow: Dev, scenes,| collect, check, |
   | scene prompts, | captions, pack | openers           | compose, render,|
   | picture prompts| plan           | Gemini app or     | brand-studio    |
   |                |                | Flow: pictures    |                 |
   +----------------+----------------+-------------------+-----------------+
                                     |
                  files in the run or pack folder (the handoff)
                                     |
   checkers: hookscore, humanize/detect, fold, beats, script_check, scene_check,
   picture_check, checked_check, trend_captions, captions, packcheck
   pass = next step; fail = back to the same step once with the error list;
   fail again = that step falls back to Claude (or the run stops and reports)
```

Step table (who does what):

| Work | Step | Who | Checker |
|---|---|---|---|
| Trend Reel | Collect feeds | `collect.py` | tests |
| | Two-outlet check | Gemini CLI (pilot), Claude fallback | new `checked_check.py` |
| | Idea and 15 s script | Claude Sonnet | `script_check.py` + `hookscore.py` + `humanize.py` + `beats.py` |
| | Scene prompts | Gemini CLI | new `scene_check.py` |
| | Dev clip and scenes | Claude in Chrome, Flow | `transcript.py`, file and length checks |
| | Compose, captions | `compose.py`, Claude Sonnet | `trend_captions.py` + `fold.py` + `humanize.py` |
| Course pack | Pack plan, hooks, captions | Claude Sonnet | `packcheck.py`, `captions.py` + `hookscore.py`, `fold.py`, `humanize.py` |
| | Picture and opener prompts | Gemini CLI | new `picture_check.py`, `scene_check.py` |
| | Pictures | Claude in Chrome, Gemini app or Flow | `pictures.py apply` + one look per picture |
| | Openers | Claude in Chrome, Flow | file and length checks |
| | Render | `build_pack.py`, brand-studio | `build_pack.py check` |
| Research | YouTube hook swipe file | script + Gemini CLI search | `swipe.py` |
| | Own-post audit | `mcp__nerdit__social_post_stats` + script | none (report) |

## 7. New and changed skills

### 7.1 New skill: `nerdit-social-craft` (from the repos)

Holds the shared scripts. Other skills call them by path. The owner can also use it alone: "score these hooks",
"humanize this caption". The adapted files keep the MIT notice and name the source repo.

- `hookscore.py` + `hooks.json` (from ig-reel): score 3 hook options from 0 to 100. Below 50 fails.
  Dealbreakers include greetings, "stop scrolling" and "in today's video". NERDIT edit: keep formulas that fit
  learning and careers (time collapse, number first, the job ad says, nobody tells you); drop the ones that need
  a personal money story (never invent one).
- `beats.py` (from ig-reel): a timed beat sheet. The hook is at most 3 s, no beat runs over 4 s, and the last line
  loops back to a hook word. Trend Reels use Dev's speed (1 s lead-in, then 2.4 words a second) in place of the
  repo's 165 words a minute.
- `humanize.py` + `detect.py` + `slop.json` (from ig-human, plus the linkedin-humanizer word list): strip invisible
  characters, em dashes and curly quotes, and flag stock words and shapes ("delve", "game-changer", "follow for
  more", "it's not just X, it's Y"). English text only: captions, screen text, slide words. Never Hinglish
  narration.
- `fold.py` (from ig-caption): checks what the feed shows before "more". Instagram shows about 125 characters,
  LinkedIn about 210 (Phase 0 confirms). The hook and one number or name must sit inside it.
- Hashtag cap: Instagram goes from 8 to 5, if Phase 0 confirms the repo's claim of 5 since 18 Dec 2025.
- Carousel rules (from ig-carousel), checked against brand-studio pages: cover at most 6 words, slide numbers
  ("3/8"), a recap slide, a small @handle on each slide, alt text on the cover. The builder adds the ones that are
  missing.
- `swipe.py` (from ig-viral; research, 7.4).

Wiring: `captions.py`, `trend_captions.py`, `script_check.py` and `packcheck.py` call these, so every existing
run gets the new rules. Each rule lands with its checker and tests.

### 7.2 `nerdit-social-posts` changes

- **Picture slot.** brand-studio cover, Story card, LinkedIn card and video thumbnail pages get an optional hero
  `picture`. Teaching slides (diagram, code, quiz, data table) do not change.
- **One picture set per course.** About 4 to 8 pictures (cover, Story, LinkedIn, thumbnail, two spares), reused
  across the pack with different crops. This matches "one look per course" and keeps within the daily picture
  limit.
- **`pictures.json`.** Each entry has a slot, a prompt and a ratio (4:5, 9:16, 1:1, 16:9). `picture_check.py`
  checks the prompt rules:
  - a light, bright page, using the palette words from the course look JSON;
  - no text, letters, numbers, logos, real or famous people, or brand marks;
  - one subject, with room for the title;
  - an Indian setting where it fits.
- **Render.** Claude in Chrome makes each picture in the Gemini app or Flow (whichever Phase 0 shows is cheaper and
  cleaner). `pictures.py take <slot>` copies the newest download into `<packdir>/pictures/`. Manual mode: the
  owner drops the files there.
- **Apply.** `pictures.py apply` checks size and ratio and brightness (a mean-light floor), then crops to each page
  size. The conductor looks at each picture once: no text, no real faces, it fits the prompt. Then brand-studio
  renders.
- **Reel openers.** 2 to 3 Veo openers per course, 4 s each, 9:16, no text, a scene from the course's world.
  The opener covers the first 3 to 4 s of the clip's picture while the clip's narration plays from second 0, so
  there's no silent intro. The hook card (code-drawn) shows from frame 1. Openers rotate across the pack's Reels.
- **Thumbnails.** The story-video YouTube thumbnail and carousel covers use a picture plus the code-drawn title.
  The builder checks which skill draws the thumbnail today. The owner's suit-photo thumbnail for its one course
  stays as it is.

### 7.3 `nerdit-trend-reels` changes

- **Step 3, check.** Pilot: Gemini CLI with its Google search finds each story's original articles and writes
  `checked.json`. New `checked_check.py`: every kept story has at least 2 sources from different sites, each with
  a link, outlet and date inside the window, and every number used is in a saved source line. The two-outlet rule
  is in the skill text today, and Gemini runs outside the Claude hooks, so it needs a script.
- **Step 5, script.** Add `hookscore.py` (best of 3, at least 50), `humanize.py` on the line and card, and
  `beats.py` at Dev's speed.
- **New step 5b, scenes.** `scenes.json`: 2 scenes, 3 to 4 s each, their place in the beats, and a Veo prompt.
  `scene_check.py`: no text, no real people, logos or brands, no news-footage look (crowds, protests, disasters),
  it fits the story, 9:16, and the total credits stay inside `runs.py credits`.
- **Step 6, Flow.** After Dev's clip, make the scenes (same model, 720p, no character). Use `take-download` for
  each into `clips/scene1.mp4` and `clips/scene2.mp4`. Each scene gets at most one re-roll, under the same rule as
  Dev.
- **compose.py.** Dev's audio runs the full length. The scenes cover Dev's picture at their beats; Dev stays on
  camera for the hook and the course ask. News card and captions stay as they are today.

### 7.4 Research (in `nerdit-social-craft`)

- **`swipe`, monthly.** Find top YouTube Shorts for our topics (AI and jobs, Excel, Python, data). For each video,
  outlier multiple = views ÷ that channel's median over its last 12 Shorts. Read the top ones' captions with
  youtube-transcript-api, on this PC only. Name each hook formula with the `match` patterns in `hooks.json`, then
  write `~/.nerdit-social/swipe.md` with the channel named on every row. Copy the shape, never the words. At most
  30 videos a run. `hookscore.py` reads `swipe.md` first. Builder's call: find the Shorts with Gemini search or
  the YouTube Data API on the existing Google Cloud project (free quota).
- **`audit`, per pack.** Read `mcp__nerdit__social_post_stats` and rank our posts by outlier multiple (against our
  own median) and shares per view, not raw views. List the top 5 and bottom 5 with their hook formula. That needs
  a `hookFormula` field saved per pack item. The next pack's hooks lean toward what worked.

### 7.5 Gemini CLI setup

- Add a `GEMINI.md` at the workspace root that points to `nerdit-plugin-json-generator/skills/`, the same way
  `AGENTS.md` does for Codex.
- A headless call per step: `gemini -p "<task>" --output-format json`, with tools allowed only for search, fetch
  and read and write inside the run folder. The builder checks the flags in Gemini CLI 0.64.
- Pilot rule: Gemini keeps a step only if it passes the checkers with the same or fewer fix rounds than Claude,
  over 2 runs. Otherwise that step goes back to Claude.

### 7.6 Not taken from the repos, and why

- Comment, DM, reply, thread-monitor, engager and employee-advocacy skills: not asked for, and bot activity on
  other people's posts risks account limits.
- The Apify, Publora and Pixfaro clients: paid services with keys.
- Instagram reading at volume: against Instagram's terms.
- Profile optimizer: a one-time job. It can be done by hand on request.
- The voice.md interview: our brand voice rules already live in `captions.py` and `editorial.md`.

## 8. Credit budget (1,050 Flow credits a month)

| Use | Credits each | Per month | Credits |
|---|---|---|---|
| Trend Reel, Dev only (today) | 60 | 17 | about 1,020 |
| Trend Reel with 2 scenes | about 92 | 11 | about 1,010 |
| Course Reel openers | 16 | 3 per course × 2 courses | about 96 |
| Pictures | Phase 0 finds out | | |

With all four slots, that's about 10 Trend Reels with scenes a month (2 to 3 a week) plus openers for 2 courses.
Four Trend Reels a week with scenes needs about 1,560 credits, which means a bigger plan or a top-up. The owner
decides at Phase 4.

## 9. Phases (each one: pilot, then the owner's OK)

0. **Check the facts.** One short look in Chrome, no credits spent:
   - Flow picture cost and watermark;
   - the Gemini app's picture limit, watermark and download size;
   - today's Instagram hashtag cap;
   - whether Gemini CLI headless with Google search works on the AI Pro login;
   - the LinkedIn fold length.

   Output: `phase0-facts.md`.
1. **Craft toolkit.** `nerdit-social-craft` scripts and tests, wired into the existing checkers. No credits.
   Re-run the checks on the Maths pack and the last Trend Reel and show what they catch. Release.
2. **Pictures (slots 2 and 4).** Picture slot in brand-studio, `pictures.py`, `picture_check.py`. Pilot on one
   course: 1 cover, 1 Story, 1 LinkedIn card, 1 thumbnail.
3. **Reel openers (slot 3).** 1 opener used on 2 pilot Reels. About 16 credits.
4. **Trend Reel scenes (slot 1).** One pilot Reel, about 92 credits. Then the owner picks the credit split and the
   timer goes back on.
5. **Gemini CLI steps.** News check and prompt drafts, in a 2-run comparison with Claude. Keep or drop each step.
6. **Research.** `swipe.md` monthly and `audit` per pack.

Why this order: Phase 1 improves every post at once and costs nothing, pictures are the cheapest visual, and the
credit-heavy steps come last.

## 10. Calls made in this design (the owner can change any)

- Approach A: Claude in Chrome does the clicking and Gemini CLI does the writing.
- AI pictures and video never carry words, numbers or code. Teaching slides stay drawn from the lesson.
- One picture set and 2 to 3 openers per course, reused across the pack.
- The opener covers the clip's first 3 to 4 s; narration starts at second 0.
- The humanizer runs on English text only.
- The shared scripts live in a new skill, `nerdit-social-craft`.
- Repo code is adapted, not copied whole; the MIT notice stays in each adapted file.
- Transcripts are read only from this PC.

## 11. Open for the owner (at the pilot that needs it, not now)

- Phase 4: the credit split (fewer Trend Reels with scenes, no scenes, or more credits).
- Phase 0: if Gemini or Flow pictures carry a visible watermark, is that OK on posts?

## 12. Left to the builder

- Page geometry for the picture slot in each brand-studio page type. The pilot shows the owner.
- The exact Gemini CLI flags and tool allow-list.
- The brightness floor and human-score pass mark, tuned on the Maths pack.
- Which skill draws the video thumbnail today, and where the picture goes there.
- Whether `swipe` finds Shorts with Gemini search or the YouTube Data API.
