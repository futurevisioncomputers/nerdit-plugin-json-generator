# Trend Reels: a presenter Reel on today's news, made on command — design

Date: 2026-11-24. Skill to build: `skills/nerdit-trend-reels` (this plugin).
Spike that proved the look: `../trend-reel-spike/` (sibling folder, throwaway; `compose.py`, `reel-pwc-test.mp4`).

## Intent

The owner says NERDIT's current posts are "very generic" and "didn't catch new audience". Every post today is
about a course (the 09:00 daily course card, the course packs' Reels cut from lesson videos), so it only works on
people already looking for a course. The owner wants Reels that stop people who are not looking: a real-looking
human presenter who explains a fresh trend or news story and ties it to a NERDIT course at the end. Reels are the
preferred format. The owner wants it fast to run ("click button or command to generate and post"), with trends and
the latest data collected fresh before every creation.

## Decided with the owner (2026-11-24)

- **Trigger:** ~~the owner starts a run with a command; no timer.~~ Changed 2026-11-25, see below. The command
  ("make trend reel", "weekly trend reel") still works for the pilot and for extra runs.
- **Trend collection: approach A**, a feed script plus a Claude check (see Approaches). Every run collects fresh.
- **Audience:** global, not only Surat. Working professionals; the hook is the worry "will AI take my job?" and its
  neighbours (layoffs, the new tool my boss wants, falling behind).
- **Language:** English narration ("try with this English"). Screen text English, as everywhere else.
- **Presenter: B, a made-up AI presenter**, made in Google Flow. The owner already has Google AI Pro (Flow shows
  PRO, 1,050 credits a month, reset on the 8th). The owner signed in to Flow for the spike and said YES to the
  result as good enough to post (apart from the presenter's wrong words, see Spike results).
- **No "AI-generated presenter" text on the video** (owner asked to remove it). Disclosure is done with each
  platform's own AI label instead (see Constraints).
- **Captions** are centred in their white pill, same pill height for every caption (owner flagged the first
  version's low text; fixed in the spike).
- **Cadence (owner picked option a, 2026-11-24):** the owner first asked for one post a day plus a weekly trend
  post, but daily presenter Reels need 1,800–3,300 credits a month against 1,050. So: **Dev Reels on 4 days a
  week, one 15 s clip each (60 credits)**, about 17 a month; the other days keep the existing course posts (daily
  course card, course packs), which are unchanged. Proposed days (my call): Monday, Wednesday, Friday a daily trend
  Reel; Sunday the weekly round-up. ~~The owner starts each run.~~ A timer starts them (2026-11-25).

## Changed with the owner (2026-11-25)

The owner asked to "schedule daily one or two videos on different topics and schedule for post on all medias",
then chose, when told the credits cannot cover daily presenter Reels:

- **Trend Reels only, at the pace the credits allow.** No mix with Chirp-voiced course Shorts.
- **A timer, not a command:** Monday, Wednesday, Friday a daily trend Reel; Sunday the weekly round-up (owner: "ok"
  to "a timer on Mon, Wed, Fri and Sunday … about 17 Reels a month").
- **The bot picks the idea itself** (it still writes 3 ideas and why it chose one).
- **Review gate: post right away** (owner first said "ok" to a 3-hour cancel window, then minutes later "post
  right away"): when every check passes, the bot posts the Reel at once ("Approve & post now") and then notifies the
  owner with the file and the post links. No window to stop it; the checks are the only gate.
- **Pilot first, still:** the first Reel is a command run the owner watches before posting; the timer is registered
  only after the owner's OK on that pilot.

Where this section and the text below differ, this section wins; the steps below are updated to match.

## Spike results (facts, 2026-11-24)

- Flow (flow.google.com, new 2026 UI) has **Characters**: a saved face plus a saved voice. Created character
  **"Dev - NERDIT presenter"** (South Asian man, early 30s, light-blue shirt, navy blazer, bright light office) with
  custom voice **"Dev voice"** built on **Achird** (the male voice the owner chose on 2026-11-04), performance
  "warm, confident, energetic social-media presenter, clear English with a light Indian accent, natural
  conversational pace, friendly not salesy". Both live in the Flow project "Nov 24 - 18:15".
- Video settings used: Video, Ingredients (character attached), 9:16, model **Omni 1.2 Flash** (current; Veo 3.1
  Fast/Quality and Omni 1.1 leave on 5 Dec; Veo 3.1 Lite stays), 720p, x1. Cost: 15 s = 60 credits, 12 s = 42,
  8 s = 24 (about 3.5–4 credits a second). Download "1080p Upscaled" costs 2–5 credits more; "720p Original" is free.
- Two clips (15 s + 12 s) gave a 27 s Reel for 109 credits. Face and setting stayed the same across clips.
- **The presenter does not always say the script.** faster-whisper heard "85,000 in cream" (an extra phrase) in
  clip 1, and clip 2 came out reordered: "…in plain English on nerdit.in. Start Machine Learning Fundamentals on
  Bio. Link in bio." instead of "…in plain English. Start Machine Learning Fundamentals free on nerdit dot in. Link
  in bio." So a transcript check is required (see step 6).
- Flow says visible watermarking is required in the owner's region: a small sparkle stays bottom-right.
- Flow has no public API; the spike drove the owner's Chrome with Claude in Chrome (about 15 minutes for one Reel).
  The Chrome extension connection dropped once afterwards; the run must survive that (resume from files).
- The composer (`trend-reel-spike/compose.py`) needs faster-whisper fed by ffmpeg-decoded 16 kHz PCM: the installed
  `av` package is too new for faster-whisper's own decoder. Model `faster-whisper-small` is already cached.

## Goals

1. On the timer (Mon/Wed/Fri) or "make trend reel": collect fresh trends, pick safe ones that touch a work worry,
   map each to a live course, write 3 Reel ideas and pick the best one.
2. Make the Reel with Dev in Flow, check what Dev said against the script, add the news card, captions and course
   end card.
3. Post it at once from Social posts to every account that can take a Reel today, with captions per platform,
   and notify the owner with the file and the post links. (Pilot: the owner watches first.)
4. On the Sunday timer or "weekly trend reel": the same, as "This week in AI & jobs", the top 3 stories of 7 days.
5. Keep a record per Reel (sources, script, transcript, captions, links to the posts) so nothing is posted without
   a traceable source.

## Non-goals

- More than 4 Reels a week, or catching up a missed day (a locked or switched-off PC skips that run).
- Trending audio. The posting APIs cannot attach Instagram/YouTube library sounds.
- Instagram's own trend data (trending Reels/sounds): no API without Meta app review. The owner may paste a trend
  into the command as one line.
- Changing the course packs, the daily course card or their times.
- The free local presenter (B1: InfiniteTalk on the PC's RTX 3060s). Not tested; parked unless credits force it.
- Hinglish versions.

## Anti-goals (a failure even if it runs)

- A Reel that states something the sources do not say, or uses a number nobody can trace to a link.
- A Reel on a sensitive story: deaths, disasters, crime, politics, religion, war, health scares, a named private
  person, or mocking a real company's staff.
- Dev resembling or naming a real person, or posing as a news anchor of a real channel.
- A post the owner does not hear about: every post is followed by a desktop notification carrying that exact file
  and the post links (the pilot: no post before the owner has watched it).
- A post when any check failed (script, transcript, captions, credits), or a second re-roll on a timer run.
- Captions that show a word Dev did not say, or a course name that is not live.
- Spending Flow credits on re-rolls without the owner knowing the count.

## Constraints

- **Credits:** 1,050 a month on AI Pro (resets on the 8th). One 15 s clip = 60 credits; 4 Reels a week ≈ 17 a
  month ≈ 1,020 credits, so there is almost no room for re-rolls. Download "720p Original" (free), never the paid
  1080p upscale; the composer scales to 1080×1920 itself.
- **Flow is browser-only.** Steps that touch Flow are skill instructions for Claude in Chrome, not scripts. Flow's
  screens can change; the skill must describe what to look for (Characters, Video, Ingredients, 9:16, model,
  length slider, credits line, download menu) rather than coordinates.
- **The PC and Chrome must be on**, unlocked, signed in to Flow, during a run (the bot's key presses fail while
  Windows is locked, learned 2026-11-24). A locked or switched-off PC skips that day; Sunday may skip often.
- **Platforms that take a Reel today:** Instagram (ig-reel), Facebook (fb-video), YouTube Shorts (yt-short,
  Access = Reviewed). LinkedIn: the posting code has no video path (`PACK_CALLS.reel.linkedin = null`); LinkedIn
  feed posts are image/multi-image only, and only to the owner's personal profile (Company Page API was denied).
  Pinterest: video pins need Standard access (requested 2026-11-23, pending; code already refuses video on Trial).
- **AI disclosure:** Meta and YouTube require realistic AI people to be disclosed. YouTube Data API has
  `status.containsSyntheticMedia`; our upload (`nerdit/functions/src/youtube.ts`, the `status` object near line 144)
  does not set it yet. Meta: Flow embeds Google's invisible watermark (SynthID / content credentials), which Meta
  may read and label "AI info" by itself; whether the Instagram/Facebook API offers an explicit flag is for the
  builder to verify.
- **Server cost:** no new scheduled jobs (each costs ~₹5/month); posting rides the existing
  `runScheduledSocialPosts` / post-now path. Reel files are small (6–9 MB each).
- **Content through the plugin only:** generation lives in this plugin's skill, with its checker; no one-off
  generator scripts outside it. Light pages; the banned phrase list in `brand-studio-plugin/brands/nerdit/brand.json`
  ("free certificate") applies to captions too. Certificate wording: "free to learn, optional certificate".
- **Pilot first:** this design's first build ends with one full run the owner approves before anything is posted.

## Approaches considered

Trend collection (owner picked A):

| | How | Trade-off |
|---|---|---|
| **A. Feed script + Claude check** | Script pulls free dated feeds into a sheet; Claude verifies and filters | Free feeds, traceable sources, repeatable; one script to maintain |
| B. Claude web search only | Claude searches freely each run | No script; different every run, no record, misses "what is being searched today" |
| C. Admin button + server function | Function reads feeds + LLM, ideas in admin | Click from phone; Reel still made on the PC, so two halves, plus deploys and server cost |

Look of the Reel (owner rejected all three non-human looks: "no nothing is work in this faction, we need real human
like face and voice"): cartoon story, animated graphics, news-style stock footage.

Presenter (owner picked B, then the free Flow route of it):

| | How | Trade-off |
|---|---|---|
| A. Owner's AI twin (HeyGen) | Owner's photo + cloned voice | ~₹100–130 per Reel; the owner's face |
| **B. Made-up presenter in Flow** | Flow Characters + Omni 1.2 Flash, owner's AI Pro credits | No extra money; ~9–17 Reels/month; watermark; browser-only |
| B1. Local InfiniteTalk | Free model on the PC's GPUs | ₹0 and scriptable; 480p on 12 GB cards, quality unknown, 30–40 GB setup |
| C. Owner on camera | Owner records from a script | ₹0, most trusted; the owner rejected a selfie intro on 2026-11-04 |

Getting the finished Reel into the scheduler (my call, see Design step 8):

| | How | Trade-off |
|---|---|---|
| **Admin page in Chrome** | Claude uses fv.nerdit.in → Social posts → new post with Reel upload, as the owner would | Reuses the existing manual-Reel path (`isOurReelUrl`, captions, platforms, post now/schedule); no new server endpoint |
| Social pack import | Build a one-item pack folder | The pack queue starts a pack after every planned pack (`firstFreeDay`), so news would post days late |
| New write API for scripts | A token-protected endpoint the skill calls | Fully scripted; new security surface and a deploy |

## Design

One skill, `nerdit-trend-reels`, with scripts for everything that is not Flow or the admin page. Each run works in
`~/.nerdit-social/trend-reels/<YYYY-MM-DD>-<slug>/` and writes a file per step, so a run can resume after a
dropped Chrome connection or a closed session.

1. **Collect** — `scripts/collect.py [--days 2|7] --out trends.json`
   - Google News RSS in English, worldwide (`hl=en-US&gl=US&ceid=US:en`) and India (`hl=en-IN&gl=IN&ceid=IN:en`),
     one query per phrase in `references/queries.txt` (start: AI jobs, AI layoffs, AI skills workers, AI at work,
     new AI model, automation jobs, plus the topic words of live courses), with `when:2d` (daily) or `when:7d`
     (weekly).
   - Google Trends daily RSS (`https://trends.google.com/trending/rss?geo=US|GB|IN`) for what people search today.
   - Hacker News top stories (Firebase API) for tech news.
   - Each row: headline, outlet, link, published time, feed, query. Dedupe by normalised headline.
     All feeds were checked working on 2026-11-24.
2. **Check (Claude)** — keep a story only if all hold: published inside the window; at least two different outlets
   report the same fact (Claude opens the links); not on the sensitive list (Anti-goals); it touches a work worry.
   "Two outlets" means two different domains with their own reporting: wire or syndicated copies of the same text
   count as one, and a Hacker News item counts as the domain it links to. On a low-news day offer fewer ideas;
   never relax the rule. (My call.)
   Map each kept story to one **live** course from the catalogue (`nerdit` MCP `catalogue_status`, `state: live`;
   the `mcp__nerdit__*` tools are configured in this Claude Code). No live course fits → drop the story; never fall
   back to a generic course. (My call.)
   Write `checked.json` with the reason for every kept and dropped story.
3. **Ideas** — 3 concepts in `ideas.json`, each: hook line (first 2 s), 2–3 beats, the course and why it fits,
   the facts used with their links. The bot picks one and writes why in `ideas.json` (`chosen`, `reason`): the
   strongest work worry, the most sources, a course that fits best, and not the same course or story as the last
   3 Reels (read from earlier run folders). Formats can vary
   (straight explainer, "3 things this means for you", myth vs fact), always Dev talking to camera.
   No story passes the check → no Reel that day; notify the owner ("no safe story today"), spend no credits.
4. **Script** — `script.json`: **one Flow clip of up to 15 s** per Reel (the owner's cadence choice). Rules
   learned in the spike:
   - at most 15 s and about 35 words; sentences of 12 words or fewer; the last sentence is the call to action
     ("…link in bio");
   - numbers spelled as said ("eighty-five thousand"); no URLs spoken except "link in bio";
   - the course name is shown on the end card, not spoken (Dev garbled it);
   - plus the screen data: news card (chip, the fact in our own words, source outlets by name), course title and
     lesson count. The card paraphrases; it never copies an outlet's headline word for word. (My call.)
   `scripts/script_check.py` enforces the rules and that every number in the script and on the card appears in a
   kept source.
5. **Make clips in Flow (Claude in Chrome)** — the Flow project "Nov 24 - 18:15" (owner's account) holds the
   character; the first real run renames it "NERDIT trend reels" and it stays the home. Video → Ingredients →
   attach character "Dev - NERDIT presenter" → 9:16 → model (a setting in the skill, default Omni 1.2 Flash; see
   Open question 1) → 720p → length to fit the line → x1. Prompt = `references/flow-prompt.md`, which holds the
   spike's framing text verbatim:
   > Vertical 9:16 talking-head video for Instagram Reels. Dev, the presenter, stands chest-up in a bright modern
   > office with soft daylight, looking straight into the camera, slight natural handheld movement, simple hand
   > gestures, natural blinking. He speaks in English with a light Indian accent, warm and confident: "<LINE>"
   > No captions, no on-screen text, no music.

   If the character is missing, recreate it from the facts in Spike results and tell the owner. Read the credits
   line before each Generate and record it. Download "720p Original" (free). Save as `clips/clip1.mp4`.
   **Credit rule (my call, owner may change):** a Reel spends 60 credits. Before a re-roll, the skill compares the
   credits left (account menu) with 60 × the Reels still planned until the reset date (4 a week); if a re-roll
   would eat into a planned Reel, it stops and asks instead (a timer run never re-rolls more than once and never
   asks: it stops and notifies). Fewer than 60 credits left → no Reel; notify "credits run out until <reset
   date>". Every run tells the owner "credits left: N, enough
   for M more Reels before <reset date>". `run.log` records credits before and after.
6. **Transcript check** — `scripts/transcript_check.py`: faster-whisper small (PCM through ffmpeg), word
   timestamps; compare normalised words with the script line. Pass when every content word of the line is present
   in order and no extra content words appear (brand fixes allowed: PwC, nerdit). On fail: one automatic re-roll of
   the clip (only if the credit rule allows), with the credit count shown; on a second fail, stop, post nothing,
   and notify the owner with both takes.
7. **Compose** — `scripts/compose.py` (the spike's composer, cleaned up; one clip now, so no concat needed, but
   keep it working for several): scale to 1080×1920 30 fps; news
   card over the chest (y≈1020) for the first ~5 s; captions of up to 3 words from the transcript, pill centred by
   a fixed ink box, numbers and key words in orange; end card for the last ~4.5 s (logo, "Start learning", course
   title, lesson count, "free to learn", "nerdit.in · link in bio" button). No AI label on screen. Then captions per
   platform in `captions.json`, checked with the social-posts caption rules (`skills/nerdit-social-posts/scripts/
   captions.py`) where they fit, including source credit ("Source: Business Insider, Inc.") and the course link.
   **Pilot only:** show the owner the Reel. When the owner says OK in chat, the skill writes `OWNER_OK` in the run
   folder: date, the owner's words, and the sha256 of `reel.mp4` (same idea as the pack pilots' `pilot/OWNER_OK`).
   Timer and command runs after the pilot instead need `checks.json` from `scripts/ready_check.py`: script, transcript and caption checks all
   passed for this `reel.mp4` (sha256), and `ideas.json` names a chosen idea.
8. **Post (Claude in Chrome)** — only when `ready_check.py` passes (and, for the pilot, `OWNER_OK` matches the
   sha256 of `reel.mp4`; posting runs in Chrome, so the shell hooks cannot guard it; the skill checks first).
   **Post now:** "Approve & post now" (owner's choice 2026-11-25), then read the post links back. Then a desktop
   notification: "Trend Reel '<hook>' posted to <platforms>."; clicking it opens `reel.mp4`. On fv.nerdit.in →
   Social posts → new post:
   the form already takes a Reel (`nerdit-admin/src/pages/AdminSocialPosts.tsx` ~line 319: `<input type="file"
   accept="video/mp4">`, 9:16, 5–90 s, under 200 MB, uploaded to `social/videos/`, checked by `isOurReelUrl`).
   The server posts a manual Reel to Instagram (ig-reel), Facebook (fb-video) and YouTube (yt-short) — see
   `publishCall` in `nerdit/functions/src/socialPosts.ts`; the form's "(Instagram only)" label is out of date and
   should be corrected. Paste the captions, tick Instagram, Facebook, YouTube (Pinterest once Standard access is
   live), post now or at a time the owner names, and read the post links back into `posted.json`.
   If Claude in Chrome cannot set the file input, the owner picks `reel.mp4` (one click) and Claude does the rest.
   The builder checks whether the manual form gives YouTube its own title/description and adds them if not. (My
   calls.)
   **Disclosure order (my call):** the YouTube flag ships before any trend Reel goes to YouTube; until then a run
   posts to Instagram and Facebook only. The change: a post-row flag set by an admin checkbox "Contains
   AI-generated person", sent as `status.containsSyntheticMedia: true` in `youtube.ts`, with tests; deploy with
   the owner's OK. Meta: if its API has an AI flag, set it the same way; if not, the run checks the live post for
   Meta's "AI info" tag and tells the owner when it is missing.
9. **Weekly** — "weekly trend reel" (Sunday): `collect.py --days 7`, Claude picks the top 3 kept stories, one
   15 s clip ("This week in AI and jobs. One… Two… Three… Link in bio."), the news card lists the three facts in
   turn, same steps 4–8.
10. **Timer (Task Scheduler, like the article poster)** — `scripts/scheduled_run.ps1` + `scripts/schedule_task.ps1`
    in this skill, copied from the article poster's pattern: task "NerdIT trend reel", weekly Monday, Wednesday,
    Friday, Sunday at **11:30** (the owner's PC is on and idle at 11:00 for the article run; 11:30 lets that run go
    first), no catch-up. The script passes "daily" or, on Sunday, "weekly". It skips the day when the PC is locked
    (LogonUI), wakes the Claude extension (opens its options page), and waits up to 2 hours while the article run's
    lock is fresh (both drive the same Chrome and clipboard); the article script waits for this lock the same way.
    `claude -p` runs with `--chrome --setting-sources project --plugin-dir <installed plugin> --permission-mode
    dontAsk` and only these tools: Claude in Chrome, Skill, `Bash(python <this skill's scripts> *)`, Read of the
    plugin, Write/Edit inside `~/.nerdit-social/trend-reels/`, WebFetch (the two-outlet check) and
    `mcp__nerdit__catalogue_status` (the builder checks it loads under `--setting-sources project`; if not, the
    scheduled run gets the catalogue another way, never a generic course). Start, done and skipped notifications
    like the article poster. Registered only after the pilot and the owner's OK.

Files per run: `trends.json`, `checked.json`, `ideas.json`, `script.json`, `clips/`, `transcript.json`,
`reel.mp4`, `captions.json`, `checks.json`, `OWNER_OK` (pilot only), `posted.json`, `run.log` (credits
before/after, re-rolls).

## Left to the builder

- Exact feed queries beyond the starting list, dedupe rules, and the course-topic words.
- The transcript-match rule's details (normalisation, stop words), as long as the spike's two failures fail it.
- Composer details: fonts (Segoe UI per brand.json), card sizes, timing, as long as cards stay clear of the face
  and captions stay centred.
- Caption wording rules per platform, reusing the social-posts checker where it fits.
- How the skill resumes a half-finished run.
- Whether Meta's API offers an AI-disclosure flag; if yes, set it like YouTube's.
- Tests for every script (collect parsing on saved feed samples, script_check, transcript_check on the spike's
  transcripts, compose layout).

## Open questions for the owner

None. (Cadence was settled as option a: 4 Dev Reels a week at 15 s. Upgrading the Google plan or testing the
cheaper Veo 3.1 Lite model stays possible later; the model is a setting in the skill.)
