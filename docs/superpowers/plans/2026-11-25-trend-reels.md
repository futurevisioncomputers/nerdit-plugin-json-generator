# Trend Reels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A timer (Mon/Wed/Fri daily, Sun weekly) or the command "make trend reel" collects fresh AI-and-jobs news, makes a 15 s Reel with the Flow presenter "Dev", checks it, and uploads it to Social posts as a **pending** post; the server emails the owner, whose Approve tap posts it.

**Architecture:** Part A is a new plugin skill `nerdit-trend-reels`: Python scripts for everything checkable (collect, script check, transcript check, compose, caption check, run folders and credits), SKILL.md instructions for the browser steps (Flow, admin upload) done by Claude in Chrome, and a Task Scheduler wrapper copied from the article poster. Part B is a small server/admin change: manual Reel rows carry YouTube words, an AI-person flag and spoken language; YouTube uploads send `containsSyntheticMedia`; creating such a row emails the owner.

**Tech Stack:** Python 3 (pytest, Pillow, imageio-ffmpeg, faster-whisper `small` — all installed), PowerShell 5.1, TypeScript Cloud Functions (vitest in `nerdit/future-vision`), React admin (vitest in `nerdit-admin`), shared package `nerdit/shared`.

**Spec:** `docs/superpowers/specs/2026-11-24-trend-reels-design.md` (read the "Changed with the owner (2026-11-25)" section first; it wins over older text).

## Global Constraints

- English narration and screen text; global working-professional audience.
- One Flow clip per Reel, at most 15 s, about 35 words; sentences of 12 words or fewer; last sentence ends "link in bio".
- Numbers spoken as words; no digits, no URLs and no course name in the spoken line.
- No "AI-generated presenter" text on the video; disclosure only through platform flags.
- Light cards (white on the video), Segoe UI fonts (`C:/Windows/Fonts/segoeui.ttf`, `segoeuib.ttf`), ink `#0B1F3A`, teal `#0e7490`, orange `#f97316`.
- Banned phrase in any text: "free certificate". Certificate wording: "free to learn, optional certificate".
- Credits: 60 per Reel; reset on the 8th of each month; download "720p Original" only.
- The bot never presses Approve. Every Reel waits as pending until the owner's tap.
- A timer run re-rolls at most once and never asks; on any failed check it uploads nothing and notifies.
- No new Cloud Scheduler jobs; no new server endpoint for the skill.
- Run folders: `$NERDIT_SOCIAL_HOME/trend-reels/` (default `~/.nerdit-social/trend-reels/`).
- Deploys and pushes need the owner's explicit OK. Build `nerdit/shared` before the admin. Work on branch `trend-reels` in each repo.

## Review Focus

1. A feed that is down, blocked or returns HTML → that feed is recorded in `errors`, the other feeds still give rows; only all feeds failing stops the run (Task A2 test).
2. One number written several ways ("85,000", "85000", "85K", "eighty-five thousand") → treated as the same number by the script and transcript checks (Tasks A3, A4 tests).
3. Credits near the reset day and across a year end (Dec 31 → Jan 8) → the planned-Reels count and the re-roll rule stay right (Task A1 tests).
4. `reel.mp4` changed after the checks ran, or `checks.json` from an older render → `ready` refuses (Task A1 test).
5. A clip with no speech, or shorter than the 4.5 s end-card window → the transcript check fails with "no speech heard"; compose still renders (Tasks A4, A5 tests).

---

## Part A — plugin skill (repo `nerdit-plugin-json-generator`)

All files under `skills/nerdit-trend-reels/`. Tests sit next to the scripts (as in `skills/nerdit-social-posts/scripts/`); run them with `python -m pytest skills/nerdit-trend-reels/scripts -q` from the repo root.

### Task A1: Run folders, credits and the ready gate

**Files:**
- Create: `skills/nerdit-trend-reels/scripts/runs.py`
- Create: `skills/nerdit-trend-reels/scripts/conftest.py` (autouse fixture: `NERDIT_SOCIAL_HOME` → `tmp_path / "social-home"`, as in `nerdit-social-posts/scripts/conftest.py`)
- Test: `skills/nerdit-trend-reels/scripts/test_runs.py`

**Interfaces:**
- Produces:
  - `home() -> Path`: `$NERDIT_SOCIAL_HOME` or `~/.nerdit-social`, plus `trend-reels`.
  - `new_run(kind: str, slug: str, today: date) -> Path`: makes `<home>/<YYYY-MM-DD>-<kind>-<slug>/clips/`. `kind` is `"daily"` or `"weekly"`; anything else raises `ValueError`.
  - `recent_choices(n: int = 3) -> list[dict]`: `{"course_id", "links"}` from the `chosen` idea of the newest n run folders that have `ideas.json`.
  - `next_reset(today: date, reset_day: int = 8) -> date`: the next reset strictly after today.
  - `reels_planned(today: date, reset: date) -> int`: Mondays, Wednesdays, Fridays and Sundays strictly after today and before reset.
  - `may_spend(credits_left: int, today: date, reroll: bool = False, cost: int = 60) -> tuple[bool, str]`. A first take needs `credits_left >= cost`; a re-roll also needs `credits_left - cost >= cost * reels_planned(...)`. The message is always `"credits left: N, enough for M more Reels before <D Mon>"` with M = credits_left // cost.
  - `sha256(path: Path) -> str`.
  - `record_check(run: Path, section: str, errors: list[str]) -> None`: writes `checks.json[section] = {"ok": not errors, "errors": errors}`. Sections: `script`, `transcript`, `captions`.
  - `record_reel(run: Path) -> None`: writes `checks.json["reel_sha256"] = sha256(run / "reel.mp4")` (compose calls it).
  - `ready(run: Path) -> list[str]`: errors when `reel.mp4` is missing, any of the three sections is missing or not ok, `reel_sha256` differs from the file, or `ideas.json` has no `chosen`.
  - CLI: `runs.py new <kind> <slug>` prints the path; `runs.py credits <N> [--reroll]` prints the message, exit 1 when not allowed; `runs.py ready <run>` prints errors, exit 1 when any; `runs.py recent`.

- [ ] **Step 1: Write the failing tests**

```python
def test_next_reset_rolls_month_and_year():
    assert next_reset(date(2026, 11, 25)) == date(2026, 12, 8)
    assert next_reset(date(2026, 12, 8)) == date(2027, 1, 8)
    assert next_reset(date(2026, 12, 31)) == date(2027, 1, 8)

def test_reels_planned_counts_mon_wed_fri_sun_between():
    # Wed 25 Nov 2026 -> 8 Dec: Fri 27, Sun 29, Mon 1, Wed 3, Fri 5, Sun 7
    assert reels_planned(date(2026, 11, 25), date(2026, 12, 8)) == 6

def test_may_spend_first_take_and_reroll():
    assert may_spend(60, date(2026, 11, 25))[0] is True
    assert may_spend(59, date(2026, 11, 25))[0] is False
    ok, msg = may_spend(400, date(2026, 11, 25), reroll=True)   # 340 left < 6 * 60
    assert ok is False and msg == "credits left: 400, enough for 6 more Reels before 8 Dec"

def test_ready_refuses_changed_reel(tmp_path): ...   # all sections ok, then overwrite reel.mp4 -> "reel.mp4 changed after the checks"
def test_ready_needs_every_section_and_a_chosen_idea(tmp_path): ...   # missing "captions" -> error names captions; no "chosen" -> error
def test_new_run_rejects_unknown_kind(): ...
```

- [ ] **Step 2: Run them; expect FAIL (`ModuleNotFoundError: runs`)**

Run: `python -m pytest skills/nerdit-trend-reels/scripts/test_runs.py -q`

- [ ] **Step 3: Implement `runs.py` with the interfaces above**

- [ ] **Step 4: Run; expect PASS**

- [ ] **Step 5: Commit** — `git add skills/nerdit-trend-reels/scripts/{runs.py,conftest.py,test_runs.py}` then `git commit -m "feat(trend-reels): run folders, credit rule and ready gate"`

### Task A2: Collect feeds

**Files:**
- Create: `skills/nerdit-trend-reels/scripts/collect.py`
- Create: `skills/nerdit-trend-reels/references/queries.txt` (one query per line, `#` comments): `AI jobs`, `AI layoffs`, `AI skills workers`, `AI at work`, `new AI model`, `automation jobs`, plus topic words of live courses (`machine learning jobs`, `data analyst AI`, `Python jobs AI`, `generative AI work`)
- Create: `skills/nerdit-trend-reels/scripts/fixtures/` — one real Google News RSS, one Google Trends RSS and two Hacker News item JSONs, saved once with the URLs below (trim to 3 items each)
- Test: `skills/nerdit-trend-reels/scripts/test_collect.py`

**Interfaces:**
- Consumes: `runs.home()` only for the CLI default.
- Produces:
  - Row dict: `{"headline", "outlet", "link", "published", "feed", "query"}`; `published` is ISO UTC (`...Z`); `feed` is one of `gnews-us`, `gnews-in`, `trends-us`, `trends-gb`, `trends-in`, `hn`.
  - `parse_gnews(xml: str, feed: str, query: str) -> list[dict]`: title "Headline - Outlet" split at the last " - "; outlet from `<source>` when present; HTML entities decoded.
  - `parse_trends(xml: str, feed: str) -> list[dict]`: headline = the search term; link/outlet from the first `ht:news_item` when present, else the trends page and "Google Trends".
  - `parse_hn(items: list[dict]) -> list[dict]`: outlet = the link's domain; items without `url` dropped.
  - `dedupe(rows) -> list[dict]` by lower-case alphanumeric words of the headline, keeping the first.
  - `collect(days: int, get: Callable[[str], str], now: datetime, queries: list[str]) -> dict`: `{"collected_at", "days", "rows", "errors": [{"feed", "url", "error"}]}`; rows older than `days` dropped; raises `SystemExit(1)` only when every request failed.
  - URLs: `https://news.google.com/rss/search?q=<query>+when:<days>d&hl=en-US&gl=US&ceid=US:en` (and `hl=en-IN&gl=IN&ceid=IN:en`), `https://trends.google.com/trending/rss?geo=US|GB|IN`, `https://hacker-news.firebaseio.com/v0/topstories.json` (first 30 ids) and `.../v0/item/<id>.json`.
  - User-Agent: `Mozilla/5.0 (compatible; trend-reels)`. No personal data in any request.
  - CLI: `collect.py --days 2|7 --out <run>/trends.json`.

- [ ] **Step 1: Write the failing tests** — on the fixtures: entities decoded (`&amp;` → `&`), outlet split ("AI is making it hard for young people to find work, report says - NPR" → outlet `NPR`), `published` ISO UTC, Trends term kept as headline, HN domain as outlet, dedupe across `gnews-us`/`gnews-in`, and:

```python
def test_one_failing_feed_is_recorded_and_others_kept():
    out = collect(2, get=fake_get(fail={"trends.google.com"}), now=NOW, queries=["AI jobs"])
    assert out["rows"] and {e["feed"] for e in out["errors"]} == {"trends-us", "trends-gb", "trends-in"}

def test_html_instead_of_rss_counts_as_a_failed_feed(): ...   # "<html>blocked</html>" -> error, no crash
def test_all_feeds_failing_exits(): ...                         # pytest.raises(SystemExit)
def test_rows_outside_the_window_are_dropped(): ...
```

- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement `collect.py`** with `urllib.request` and `xml.etree.ElementTree` (no new dependency).
- [ ] **Step 4: Run; expect PASS. Then one live run:** `python skills/nerdit-trend-reels/scripts/collect.py --days 2 --out %TEMP%/trends.json` prints a row count above 0.
- [ ] **Step 5: Commit** — `feat(trend-reels): collect news, trends and HN into a dated sheet`

### Task A3: Script check

**Files:**
- Create: `skills/nerdit-trend-reels/scripts/script_check.py`
- Create: `skills/nerdit-trend-reels/scripts/numbers.py` (shared by A3 and A4)
- Test: `skills/nerdit-trend-reels/scripts/test_script_check.py`, `test_numbers.py`

**Interfaces:**
- Consumes: `runs.record_check`.
- Produces:
  - `script.json`: `{"kind": "daily"|"weekly", "line": str, "card": {"chip": str, "facts": [str, ...1-3], "sources": [outlet, ...]}, "course": {"id", "title", "lessons": int, "url"}}`; `url` is `https://nerdit.in/course/<slug>/preview` (slug from `catalogue_status`).
  - `checked.json` (written by Claude in step 2 of the skill): `{"kept": [{"headline", "links": [..2+], "outlets": [..2+], "evidence": [quoted sentences], "course_id"}], "dropped": [{"headline", "reason"}]}`.
  - `numbers.normalise(text: str) -> set[str]`: every number in the text as plain digits: `"85,000"`, `"85000"`, `"85K"`, `"85k"` → `"85000"`; `"72%"` → `"72"`; years 20xx ignored.
  - `numbers.words_to_digits(tokens: list[str]) -> list[str]`: runs of English number words (zero–nineteen, tens, hundred, thousand, million, hyphenated) become one digit token: `["eighty-five", "thousand"]` → `["85000"]`.
  - `script_errors(script: dict, kept: list[dict]) -> list[str]`.
  - CLI: `script_check.py <run>` → `record_check(run, "script", errors)`; exit 1 on errors.

Rules `script_errors` enforces (one error string each, naming the offending text):
line over 35 words; a sentence over 12 words; line not ending "link in bio" (before final punctuation); a digit or URL or "dot com"/"dot in" in the line; the course title spoken in the line; a card fact with characters outside Latin script; a number on the card not in the normalised numbers of the kept stories' headlines + evidence; a card fact equal (lower-case, punctuation-free) to a kept headline; "free certificate" anywhere; `card.facts` count not 1 for daily or 3 for weekly; fewer than 2 `card.sources`.

- [ ] **Step 1: Write the failing tests**

```python
LINE = ("PwC is training eighty-five thousand of its own people for the AI age. "
        "That tells you what your company will expect next. Learn how AI works. Link in bio.")
KEPT = [{"headline": "PwC Is Training 85,000 Employees on AI Skills", "evidence": ["certify 85,000 workers"],
         "links": ["https://inc.com/a", "https://businessinsider.com/b"], "outlets": ["Inc.", "Business Insider"]}]

def test_good_script_passes(): assert script_errors(script(LINE, facts=["PwC is training 85,000 staff for the AI age"]), KEPT) == []
def test_card_number_not_in_sources_is_named(): assert any("90,000" in e for e in script_errors(script(LINE, facts=["PwC trains 90,000"]), KEPT))
def test_85k_in_evidence_matches_85000_on_card(): ...
def test_digits_in_line_fail(): ...           # "85,000" spoken line
def test_course_title_spoken_fails(): ...     # "Machine Learning Fundamentals" in line
def test_missing_cta_fails(): ...
def test_thirteen_word_sentence_fails(): ...
def test_verbatim_headline_on_card_fails(): ...
def test_non_latin_card_fails(): ...          # Tamil text from a Trends row
def test_weekly_needs_three_facts(): ...

# test_numbers.py
def test_normalise_forms(): assert normalise("85,000 / 85000 / 85K / 72% in 2026") == {"85000", "72"}
def test_words_to_digits(): assert words_to_digits(["eighty-five", "thousand", "people"]) == ["85000", "people"]
```

- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement `numbers.py` and `script_check.py`**
- [ ] **Step 4: Run; expect PASS**
- [ ] **Step 5: Commit** — `feat(trend-reels): script check (spoken rules, traceable card numbers)`

### Task A4: Transcript and transcript check

**Files:**
- Create: `skills/nerdit-trend-reels/scripts/transcript.py`
- Test: `skills/nerdit-trend-reels/scripts/test_transcript.py`

**Interfaces:**
- Consumes: `numbers.words_to_digits`, `runs.record_check`.
- Produces:
  - `merge_tokens(raw: list[tuple[str, float, float]]) -> list[dict]`: `{"w", "s", "e"}`; a token starting with "," or "." and longer than 1 joins the previous one ("85" ",000" → "85,000"; "nerdid" ".in" → "nerdit.in"); fixes `{"PWC": "PwC", "nerdid": "nerdit", "Nerdid": "nerdit"}`.
  - `transcribe(clip: Path, model: str = "small") -> list[dict]`: ffmpeg (`imageio_ffmpeg.get_ffmpeg_exe()`) decodes to 16 kHz mono float32 PCM on stdout, `np.frombuffer` into `WhisperModel(model, device="cpu", compute_type="int8").transcribe(..., language="en", word_timestamps=True)` (the installed `av` is too new for faster-whisper's own decoder — keep this one-line comment), then `merge_tokens`.
  - `match_errors(heard: list[str], line: str) -> list[str]`: lower-case, strip punctuation, number words → digits on both sides, drop stop words (`a an the of its to in on and so is are for it that this be`). Errors: `"no speech heard"` when nothing is heard; `"missing: <words>"` for line content words not found in order; `"extra: <words>"` for heard content words not in the line.
  - `transcript.json`: list of `{"w", "s", "e"}` with times from the start of the Reel (clips in name order, offset by each clip's duration).
  - CLI: `transcript.py <run>` → writes `transcript.json`, `record_check(run, "transcript", match_errors(...))`; exit 1 on errors.

- [ ] **Step 1: Write the failing tests** — the spike's real transcripts as fixtures:

```python
LINE1 = ("PwC is training eighty-five thousand of its own people for the AI age. Not a small tech team. "
         "Eighty-five thousand. That's a clear signal of what your company will expect from you next.")
HEARD1 = ("PwC is training 85,000 of its own people for the AI age. Not a small tech team. 85,000 in cream. "
          "That's a clear signal of what your company will expect from you next.").split()
LINE2 = "So don't wait to be asked. Learn how AI actually works, in plain English. Start Machine Learning Fundamentals free on nerdit dot in. Link in bio."
HEARD2 = "So, don't wait to be asked, learn how AI actually works in plain English on nerdit.in. Start Machine Learning Fundamentals on Bio. Link in bio.".split()

def test_spike_clip1_fails_on_extra_words(): assert any("cream" in e for e in match_errors(HEARD1, LINE1))
def test_spike_clip2_fails_on_missing_free(): assert any("free" in e for e in match_errors(HEARD2, LINE2))
def test_exact_take_passes(): assert match_errors(HEARD1[:12] + HEARD1[15:], LINE1) == []   # without "85,000 in cream."
def test_no_speech(): assert match_errors([], LINE1) == ["no speech heard"]
def test_merge_tokens_joins_and_fixes(): assert [t["w"] for t in merge_tokens([("PWC", 0, .3), ("85", .4, .6), (",000", .6, .8)])] == ["PwC", "85,000"]
```

- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement `transcript.py`**
- [ ] **Step 4: Run; expect PASS. Then on the spike clip:** `python skills/nerdit-trend-reels/scripts/transcript.py <tmp run with ../trend-reel-spike/clips/clip1.mp4 + script.json of LINE1>` exits 1 and prints an "extra" error with "cream".
- [ ] **Step 5: Commit** — `feat(trend-reels): transcript with word times and the said-vs-script check`

### Task A5: Compose

**Files:**
- Create: `skills/nerdit-trend-reels/scripts/compose.py` (port of `../trend-reel-spike/compose.py`; transcription moves out to A4)
- Test: `skills/nerdit-trend-reels/scripts/test_compose.py`

**Interfaces:**
- Consumes: `transcript.json`, `script.json`, `clips/*.mp4`, `runs.record_reel`.
- Produces:
  - `caption_groups(words: list[dict], max_words: int = 3) -> list[list[dict]]`: break after 3 words or a word ending `.?!`.
  - `caption_png(path: Path, words: list[str]) -> dict`: returns `{"pill": (x0, y0, x1, y1)}`. Pill height from the fixed ink box of `"Hgjy"`, `pad_y = 24`, `y0 = 1920 - 300`; numbers and words in `{"pwc", "ai", "free", "nerdit"}` plus any word with a digit in orange.
  - `card_png(path: Path, chip: str, fact: str, sources: list[str]) -> dict`: card at `y0 = 1020`, returns `{"card": box}`; source line `"Source: " + ", ".join(sources)`.
  - `endcard_png(path: Path, course: dict) -> dict`: card at `y0 = 960`; logo `skills/nerdit-social-posts/assets/nerdit-logo.png` (inside the plugin; the spike's brand-studio path is not in the installed plugin); "Start learning", title (wrapped), `"<lessons> lessons  ·  free to learn"`, orange button `"nerdit.in  ·  link in bio"`; height follows the title's line count; returns `{"meta_bottom": int, "button_top": int}`.
  - `compose(run: Path) -> Path`: 1080×1920, 30 fps, AAC 160k, libx264 crf 20, `+faststart`. Daily: the card shows facts[0] from 0.3 s to 5.5 s. Weekly: each of the 3 facts for 4 s in turn from 0.3 s. End card from `max(0, total - 4.5)` to the end. Captions from `transcript.json`. Writes `reel.mp4`, then `record_reel(run)`.
  - CLI: `compose.py <run>`.

- [ ] **Step 1: Write the failing tests**

```python
def test_caption_text_is_centred_in_the_pill(tmp_path):
    for words in (["your", "company", "will"], ["signal", "of", "what"]):
        info = caption_png(tmp_path / "c.png", words)
        top_gap, bottom_gap = ink_gaps(tmp_path / "c.png", info["pill"])   # dark-pixel rows inside the pill
        assert abs(top_gap - bottom_gap) <= 4
def test_every_pill_has_the_same_height(tmp_path): ...
def test_news_card_sits_below_the_face(tmp_path): assert card_png(...)["card"][1] >= 1000
def test_end_card_button_is_below_the_meta_line(tmp_path):
    info = endcard_png(tmp_path / "e.png", {"title": "Machine Learning Fundamentals", "lessons": 12})
    assert info["button_top"] > info["meta_bottom"]
def test_compose_short_clip_renders(tmp_path):
    # 3 s lavfi clip (testsrc2 720x1280 + sine), transcript of 3 words, daily script -> reel.mp4 exists,
    # ffmpeg -i reports 1080x1920 and ~3 s, checks.json has reel_sha256
```

- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement `compose.py`**
- [ ] **Step 4: Run; expect PASS. Then render the spike clips** through a temp run and look at 4 frames (2, 6, 10, 13 s): captions centred, card clear of the face, no AI label.
- [ ] **Step 5: Commit** — `feat(trend-reels): compose Reel with news card, captions and end card`

### Task A6: Caption check

**Files:**
- Create: `skills/nerdit-trend-reels/scripts/trend_captions.py`
- Modify: `skills/nerdit-social-posts/scripts/captions.py` (`utm_link`: campaign `item.get("campaign", "pack")` instead of the fixed `pack`; packs unchanged)
- Test: `skills/nerdit-trend-reels/scripts/test_trend_captions.py`, `skills/nerdit-social-posts/scripts/test_captions.py` (one test: `campaign: "trend"` gives `utm_campaign=trend-<date>`; the existing pack test still passes)

**Interfaces:**
- Consumes: `caption_errors`, `fill_links` from `skills/nerdit-social-posts/scripts/captions.py` (import by inserting that folder into `sys.path`; one-line comment why), `runs.record_check`.
- Produces:
  - `captions.json` (written by Claude): `{"instagram", "facebook", "youtube", "pinterest"}`; `{link}` marks the course link; YouTube = title line, blank line, description.
  - `trend_caption_errors(captions: dict, script: dict, kept: list[dict], item: dict) -> list[str]`: `caption_errors(p, "reel", text, evidence_text, item, script["course"]["url"])` per platform (evidence_text = card facts + kept headlines + evidence, so traceable numbers pass), plus: each caption contains `"Source:"` and every `card.sources` outlet; "free certificate" nowhere; YouTube title has no `{link}`.
  - `item = {"id": <run folder name>, "date": <YYYY-MM-DD>, "campaign": "trend"}` → `utm_campaign=trend-<date>`.
  - CLI: `trend_captions.py <run>` → writes `captions_filled.json` (links filled per platform) and `record_check(run, "captions", errors)`; exit 1 on errors.

- [ ] **Step 1: Write the failing tests** — good captions pass; a caption without "Source:" fails naming the platform; "free certificate" fails; a number not in the evidence fails; filled Instagram text contains `utm_source=instagram`.
- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run; expect PASS**
- [ ] **Step 5: Commit** — `feat(trend-reels): caption check reusing the social-posts rules`

### Task A7: SKILL.md and references

**Files:**
- Create: `skills/nerdit-trend-reels/SKILL.md`
- Create: `skills/nerdit-trend-reels/references/flow-prompt.md` (the spike's framing text verbatim, from the spec step 5, with `<LINE>`)
- Create: `skills/nerdit-trend-reels/references/editorial.md` (sensitive list and work-worry list from the spec's Anti-goals and Intent; the two-outlet rule; the idea-choice rule)

**Interfaces:**
- Consumes: every CLI from A1–A6; the admin form labels from Task B2 ("Or a Reel", "YouTube title", "YouTube description", "Contains AI-generated person", "Spoken language").
- Produces: the skill the timer prompt names: `Use the nerdit-trend-reels skill: scheduled run, kind <daily|weekly>.` and the command triggers "make trend reel", "weekly trend reel".

SKILL.md content, in order (frontmatter `name: nerdit-trend-reels`, description naming both triggers and "never presses Approve"):
1. Start: `runs.py new <kind> <slug>`; read the credits line from Flow's account menu; `runs.py credits <N>`; below 60 → stop and write the report line "credits run out until <reset>".
2. Collect: `collect.py --days 2` (weekly 7).
3. Check: open the links, apply `references/editorial.md`, map to a live course with `mcp__nerdit__catalogue_status`, write `checked.json`. Nothing kept → report "no safe story today", stop.
4. Ideas: 3 ideas into `ideas.json` with `chosen` and `reason`; avoid `runs.py recent` choices.
5. Script: write `script.json`, run `script_check.py` until it passes (rewrite the script; never edit the check).
6. Flow: what to look for (project "NERDIT trend reels" — rename "Nov 24 - 18:15" on first run; Video, Ingredients, character "Dev - NERDIT presenter", 9:16, model setting `Omni 1.2 Flash`, 720p, length slider to fit, x1, credits line), prompt from `flow-prompt.md`; download "720p Original" to `clips/clip1.mp4` (copy from Downloads by the newest `*.mp4`).
7. `transcript.py`; on fail one re-roll only if `runs.py credits <N> --reroll` allows; second fail → report and stop.
8. `compose.py`; write `captions.json`; `trend_captions.py` until it passes.
9. `runs.py ready <run>` must exit 0, then the admin: fv.nerdit.in → Social posts → new post; Name = hook; captions; Reel file; YouTube title/description from `captions_filled.json`; tick "Contains AI-generated person"; Spoken language English; Create. **Never press Approve.** Chrome's file upload refused files under `~/.nerdit-social` from an interactive session (2026-11-25) but accepts files in the session's working directory: the timer runs with that folder as its working directory (Task A8); in a command run, copy `reel.mp4` into the session's scratchpad first. If the file input still cannot be set, stop and report the file path. Save the new row id in `posted.json` (`status: pending`).
10. Report: first line of `<home>/last-report.md` is the notification text: "Trend Reel '<hook>' is waiting for your Approve in Social posts. credits left: N, enough for M more Reels before <D Mon>." Mention any earlier run still pending (read its row status in the admin into its `posted.json`). For an earlier row that is now posted, open its Instagram link once and record whether Meta shows "AI info"; say so in the report when it is missing (spec: Meta disclosure).
11. Until Task B3 is deployed, step 9 leaves "Contains AI-generated person" off and unticks YouTube (spec: disclosure order).

- [ ] **Step 1: Write the three files**
- [ ] **Step 2: Check** — `python -m pytest skills/nerdit-trend-reels/scripts -q` still passes; `grep -c "Approve" skills/nerdit-trend-reels/SKILL.md` shows the never-press rule; every script named in SKILL.md exists.
- [ ] **Step 3: Commit** — `feat(trend-reels): skill instructions, Flow prompt and editorial rules`

### Task A8: Timer wrapper

**Files:**
- Create: `skills/nerdit-trend-reels/scripts/nerdit-mcp.json` (content below; no secret in it)
- Create: `skills/nerdit-trend-reels/scripts/scheduled_run.ps1` (from `skills/nerdit-article-poster/scripts/scheduled_run.ps1`)
- Create: `skills/nerdit-trend-reels/scripts/schedule_task.ps1` (from the article poster's)
- Modify: `skills/nerdit-article-poster/scripts/scheduled_run.ps1` (wait for the trend lock)

**Interfaces:**
- Consumes: SKILL.md trigger text (A7); `runs.home()` layout.
- Produces:
  - `scheduled_run.ps1 [-DryRun] [-Kind daily|weekly]`: Kind defaults to `weekly` on Sunday, else `daily`. Lock `<home>/trend-reels/scheduled.lock` (3 h staleness, as the article poster). Skips when `LogonUI` runs (toast "Skipped today: the PC was locked."). Waits up to 2 h, checking every 2 min, while `<home>/article-runs/scheduled.lock` is younger than 3 h. Prompt: `Use the nerdit-trend-reels skill: scheduled run, kind <Kind>.` plus the pinned script paths (forward slashes), as the article poster pins `runlog.py`. Claude args: `-p <prompt> --chrome --setting-sources project --plugin-dir <installed plugin> --permission-mode dontAsk --disallowedTools PowerShell --allowedTools` then: `mcp__claude-in-chrome`, `Skill`, `Bash(python <scripts>/runs.py *)`, the same for `collect.py`, `script_check.py`, `transcript.py`, `compose.py`, `trend_captions.py`, `Read(~/.claude/plugins/**)`, `Read(~/.nerdit-social/trend-reels/**)`, `Write(~/.nerdit-social/trend-reels/**)`, `Edit(~/.nerdit-social/trend-reels/**)`, `Read(~/Downloads/**)`, `Bash(cp ~/Downloads/* *)`, `WebFetch`, `mcp__nerdit__catalogue_status`. After the run, toast the first line of `last-report.md`; clicking opens the run's `reel.mp4` when it exists, else the log.
  - `--setting-sources project` drops the user-scoped nerdit MCP (verified 2026-11-25), so the runner always adds `--mcp-config <scripts>/nerdit-mcp.json` (a file; PowerShell 5.1 strips quotes from inline JSON). The file, committed in the skill, holds `{"mcpServers":{"nerdit":{"type":"http","url":"https://us-central1-future-vision-skill-learning.cloudfunctions.net/nerditMcp","headers":{"X-Nerdit-Token":"${NERDIT_MCP_TOKEN}"}}}}`; right before `claude`, the runner sets `$env:NERDIT_MCP_TOKEN` from `~/.claude.json` (`mcpServers.nerdit.headers.X-Nerdit-Token`). The token is never written to a file, the log or the command line.
  - Before `claude`, wake the Claude extension: open `chrome-extension://fcoeoabgfenejglbffodgkkbkcdhcgfn/options.html` and wait 10 s (copy from the article runner, plugin commit c0f5753).
  - `Set-Location` to the new run's parent `<home>/trend-reels` before `claude`, so Chrome's file upload accepts `reel.mp4` (pilot verifies).
  - `schedule_task.ps1 [-Time 11:30] [-Remove]`: task "NerdIT trend reel", weekly Monday, Wednesday, Friday, Sunday at `-Time`, same settings as the article task (3 h limit, IgnoreNew, interactive, no catch-up).
  - Article `scheduled_run.ps1`: before its own run, wait (same 2 h / 2 min rule) while the trend lock is younger than 3 h.

- [ ] **Step 1: Write both scripts and the article change**
- [ ] **Step 2: Dry run** — `powershell -NoProfile -File skills/nerdit-trend-reels/scripts/scheduled_run.ps1 -DryRun -Kind weekly` prints the lock path, the prompt with `kind weekly`, `--mcp-config` with the file path and every allowed tool above, and no token; the lock is removed afterwards. The article script's `-DryRun` still prints its own args.
- [ ] **Step 2b: MCP check** — `claude -p "Call mcp__nerdit__catalogue_status and reply with the number of live courses only." --setting-sources project --mcp-config <file> --allowedTools mcp__nerdit__catalogue_status` (with the env var set as the runner does) answers a number (78 on 2026-11-25), not MISSING.
- [ ] **Step 3: Commit** — `feat(trend-reels): Task Scheduler wrapper, shared-Chrome lock with the article run`

---

## Part B — server and admin (repos `nerdit`, `nerdit-admin`)

### Task B1: Post fields, YouTube flags and the approval email (functions)

**Files:**
- Modify: `nerdit/functions/src/socialPosts.ts` (`SocialPost` type ~line 79-130; `manualSocialPost` ~line 655)
- Modify: `nerdit/functions/src/youtube.ts:140-145` (`uploadShort`)
- Modify: `nerdit/functions/src/youtubePublish.ts:49` (`postYoutube` call)
- Modify: `nerdit/functions/src/socialFunctions.ts:339-343` (create handler)
- Test: `nerdit/future-vision/src/__tests__/youtube.test.ts`, `youtubePublish.test.ts`, `socialPosts.test.ts`

**Interfaces:**
- Produces:
  - `SocialPost` gains `syntheticMedia?: boolean; spokenLanguage?: 'en' | 'hi';` (comment: YouTube disclosure and audio language; trend Reels set both).
  - `manualSocialPost(id, input: { ...existing; youtubeTitle?: string; youtubeText?: string; syntheticMedia?: boolean; spokenLanguage?: 'en' | 'hi' }, nowIso)`: copies `youtubeTitle` (clipped to `YOUTUBE_TITLE_MAX` = 100) and `youtubeText` (5000) when non-empty; `syntheticMedia` only when `=== true`; `spokenLanguage` only `'en'` or `'hi'`; a row with `videoUrl` gets `platforms: ['instagram', 'facebook', 'youtube', 'pinterest']` (Pinterest is dropped later by `pinnable` while Trial).
  - `uploadShort(tok, meta: { title; description; tags; syntheticMedia?: boolean; audioLanguage?: 'en' | 'hi' }, ...)`: `status.containsSyntheticMedia = meta.syntheticMedia === true`; `snippet.defaultAudioLanguage = meta.audioLanguage ?? 'hi'`.
  - `postYoutube` passes `syntheticMedia: post.syntheticMedia === true, audioLanguage: post.spokenLanguage`.
  - `pendingReelMail(row: SocialPost): { subject: string; text: string }` in `socialPosts.ts`: subject `Trend Reel waiting for your Approve: <title>`; text names the title, says nothing is posted until Approve, and links `https://fv.nerdit.in/social-posts`.
  - Create handler: passes `youtubeTitle`, `youtubeText`, `syntheticMedia === true`, `spokenLanguage` from `body`; after saving a row with `videoUrl && syntheticMedia`, `sendLoggedMail("admin-alert", { from: getSenderInfo() sender, to: ADMIN_ALERT_EMAIL, ...pendingReelMail(row) })` in try/catch → `logSystemError("socialPostAction", error, "pending Reel mail")`; a mail failure never fails the create.

- [ ] **Step 1: Write the failing tests**

```ts
it('marks AI-person Shorts as synthetic and English when asked', async () => {
  await uploadShort('tok', { title: 'T', description: 'D', tags: [], syntheticMedia: true, audioLanguage: 'en' }, video, f);
  const meta = JSON.parse(String(calls[0].init.body));
  expect(meta.status.containsSyntheticMedia).toBe(true);
  expect(meta.snippet.defaultAudioLanguage).toBe('en');
});
// existing 'uploads a Short in two steps' expectation gains containsSyntheticMedia: false (default unchanged otherwise)
it('postYoutube sends the row flags', ...)                         // youtubePublish.test.ts: uploadShort meta has syntheticMedia true, audioLanguage 'en'
it('manual Reel keeps YouTube words, flag, language and platforms', ...)   // socialPosts.test.ts
it('manual post ignores a non-boolean flag and an unknown language', ...)  // syntheticMedia: 'yes' -> absent; spokenLanguage: 'fr' -> absent
it('pendingReelMail names the title and links Social posts', ...)
```

- [ ] **Step 2: Run; expect FAIL** — `cd nerdit/future-vision && npx vitest run src/__tests__/youtube.test.ts src/__tests__/youtubePublish.test.ts src/__tests__/socialPosts.test.ts`
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run; expect PASS; then the whole suite** `npx vitest run` (all pass) and `cd ../functions && npm run build` (no errors)
- [ ] **Step 5: Commit** (branch `trend-reels` in `nerdit`) — `feat(social): AI-person flag, spoken language and YouTube words on manual Reels; approval email`

### Task B2: Admin new-post form (shared + admin)

**Files:**
- Modify: `nerdit/shared/src/services/socialClient.ts:199-208` (`NewSocialPost`; the `SocialPost` type there gains the two fields too)
- Modify: `nerdit-admin/src/pages/AdminSocialPosts.tsx:285-335` (`NewPostForm`; export it for the test)
- Test: `nerdit-admin/tests/newPostForm.test.tsx` (follow `tests/AdminMenu.test.tsx` for rendering and mocking)

**Interfaces:**
- Consumes: B1 field names.
- Produces:
  - `NewSocialPost` gains `youtubeTitle?: string; youtubeText?: string; syntheticMedia?: boolean; spokenLanguage?: 'en' | 'hi';` (passed through by `...rest`); the `video` comment says "an MP4 Reel (Instagram, Facebook, YouTube)".
  - The row editor already edits `youtubeTitle`/`youtubeText` for video rows (`AdminSocialPosts.tsx` ~434-439, ~640): reuse its limits and counters for the new fields.
  - When a video is chosen, the form shows, each as a `<label>` wrapping its control so the label text is the accessible name: "YouTube title" (input, maxLength 100), "YouTube description" (textarea), "Contains AI-generated person" (checkbox, off by default), "Spoken language" (select: Hindi `hi` default, English `en`).
  - Label "Or a Reel: … (Instagram only)" → "Or a Reel: MP4 video, 9:16, 5–90 seconds, under 200 MB (Instagram, Facebook and YouTube)". Success message → "Reel uploaded. Approve or schedule it to post it."

- [ ] **Step 1: Write the failing test** — choosing an MP4 shows the four fields; filling them and pressing Create calls `createSocialPost` with `youtubeTitle`, `youtubeText`, `syntheticMedia: true`, `spokenLanguage: 'en'`; without a video the four fields are absent.
- [ ] **Step 2: Run; expect FAIL** — `cd nerdit-admin && npx vitest run tests/newPostForm.test.tsx`
- [ ] **Step 3: Implement** (shared first, then the admin)
- [ ] **Step 4: Verify** — `cd nerdit/shared && npm run build`; `cd nerdit-admin && npx vitest run` (all pass) and `npm run build`; `grep -l "Contains AI-generated person" nerdit-admin/dist/assets/*.js` finds the bundle.
- [ ] **Step 5: Commit** (branch `trend-reels` in `nerdit` for shared, `nerdit-admin` for the form) — `feat(admin): YouTube words, AI-person flag and language for Reel posts`

### Task B3: Deploy (owner's OK required)

- [ ] **Step 1: Ask the owner** to deploy functions `socialPostAction`, `runScheduledSocialPosts` and admin hosting. Check other worktrees for undeployed admin work first (memory: article-email lists) and that `nerdit/shared` was built before the admin.
- [ ] **Step 2: Deploy on OK** — `cd nerdit && FUNCTIONS_DISCOVERY_TIMEOUT=120 firebase deploy --only functions:socialPostAction,functions:runScheduledSocialPosts`, then the admin hosting target as in earlier deploys.
- [ ] **Step 3: Verify live** — on fv.nerdit.in Social posts → new post, choosing an MP4 shows the four fields (owner's browser; create nothing).

---

## Part C — pilot and release

### Task C1: Pilot run (owner-gated)

- [ ] **Step 1:** Run "make trend reel" in a normal session (not the timer), end to end. Expected: a pending post in Social posts with the Reel, captions, YouTube words; the owner gets the email; `runs.py ready <run>` exited 0; credits line recorded in `run.log`.
- [ ] **Step 2:** The owner watches the pending Reel and taps Approve (or rejects). Record the owner's words in the run's `run.log`.
- [ ] **Step 3:** Only after the owner's OK: `powershell -NoProfile -File skills/nerdit-trend-reels/scripts/schedule_task.ps1 -Time 11:30` (prints `registered: NerdIT trend reel …`).

### Task C2: Plugin release (push needs the owner's OK)

- [ ] **Step 1:** `.claude-plugin/plugin.json` version `3.24.0` and a description sentence for nerdit-trend-reels; README skill list gains the skill.
- [ ] **Step 2:** `python -m pytest skills -q` all pass.
- [ ] **Step 3:** Commit `release: nerdit_content_creator 3.24.0 (trend reels)`; merge `trend-reels` into `main`; push and reinstall the plugin only on the owner's OK (the timer uses the installed copy).
