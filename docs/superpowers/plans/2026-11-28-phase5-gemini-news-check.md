# Phase 5: Gemini news check (Trend Reels) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In Trend Reels step 3, Gemini (Antigravity CLI `agy`) finds the original articles and writes
`checked.json`. A new checker judges it, whoever wrote it. Claude does the check as before when Gemini fails. A
2-run replay measures Gemini against Claude so the owner can keep or drop the step.

**Architecture:** `gemini_check.py` builds one prompt and runs `agy -p` once:
- the work-related candidate rows of `trends.json`;
- the live courses Claude saved in `courses.json`;
- the editorial keep rules, read from `references/editorial.md`.

It runs in an empty temp folder with `--sandbox`, saves the raw answer, and writes the JSON block to `checked.json`.
`checked_check.py` enforces the two-outlet rules and confirms quotes against the fetched pages.
`runs.py ready` requires its verdict.

**Tech Stack:** Python 3.14 stdlib (subprocess, urllib, html.parser) + pytest; `agy` 1.0.13 (signed in 2026-11-28).

**Spec:** `docs/superpowers/specs/2026-11-28-gemini-visuals-and-social-craft-design.md` sections 5 (approach A),
7.3 step 3, 7.5 and 9 phase 5; `2026-11-28-phase0-facts.md` (agy row).

## Global Constraints

- `agy` runs only as a subprocess of `gemini_check.py`:
  - in a fresh empty temp folder;
  - with `--sandbox`;
  - never with `--dangerously-skip-permissions`;
  - with the prompt as one argv string under 30,000 characters.

  Its answer is data: only the parsed JSON is kept, and the checker judges it.
- Default model `gemini-4-hydrogen-medium`; `--model` overrides it.
- Every rule ships with its checker and tests. Checkers print what is wrong (ASCII-safe) and exit 1.
- Network in a checker never fails a run because a site is unreachable. An unreadable page is a warning; only a page
  that loads (2,000+ characters of text) without the quoted words is an error.
- No change to Chrome, Flow, posting, or the admin.
- Tests: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest skills/nerdit-trend-reels/scripts -q -p no:cacheprovider`.

## Review Focus

- An `agy` answer with prose around the JSON, or two JSON blocks, keeps the last one. Test in Task 2.
- `agy` timeout or missing binary means exit 1 with a clear message and no `checked.json` written. Test in Task 2.
- Links on `news.google.com` or `news.ycombinator.com` never count as an outlet, and `www.` and `m.` copies of one
  site count once. Test in Task 1.
- An empty `kept` (low-news day) passes when `dropped` explains each story. Test in Task 1.
- A Windows console printing the outlet names and quotes (curly quotes, ₹) never crashes. Test in Task 1.

---

### Task 1: `checked_check.py`

**Files:** Create `skills/nerdit-trend-reels/scripts/checked_check.py`, `test_checked_check.py`. Modify `runs.py`
(`SECTIONS` gains `"checked"`) and `test_runs.py` (fixtures record a `checked` verdict).

**Interfaces:** Produces:
- `checked_errors(checked: dict, courses: list[dict], run_date: date) -> list[str]`
- `quote_problems(kept: list[dict], fetch) -> tuple[list[str], list[str]]` (errors, warnings), where
  `fetch(url) -> str | None` returns page text or None.
- CLI `checked_check.py <run> [--no-fetch]`, which records `checks.json["checked"]`.

Rules (each one with a test):
- **kept story fields:** non-empty `headline`; `links` from 2 or more different sites; `outlets` 2 or more distinct
  names, each named in `evidence`; `published` (YYYY-MM-DD) inside `run_date - window_days .. run_date`; `course_id`
  is in `courses.json`; every number in the headline appears in its evidence.
- **Sites:** a site is the host minus `www.` and `m.`, with its last two labels (three for `co.in`, `co.uk`,
  `com.au`). Links on `news.google.com` or `news.ycombinator.com` do not count.
- **dropped:** every story has a `reason`.
- **Quotes:** for each `"…"` fragment in an evidence line starting `<Outlet>:`, its first 8 words must appear in the
  text of that outlet's fetched page (lower-cased, quotes and whitespace normalised).

Steps:
1. Write the tests: good checked passes; each rule fails with its message; google-news link not counted; www. and m.
   copies count once; empty kept passes; quote found / missing / unreadable page (warning); CLI output is ASCII.
2. Watch them fail.
3. Implement.
4. Watch them pass, with the trend suite green.
5. Commit.

### Task 2: `gemini_check.py`

**Files:** Create `skills/nerdit-trend-reels/scripts/gemini_check.py`, `test_gemini_check.py`,
`skills/nerdit-trend-reels/references/gemini-check-prompt.md`.

**Interfaces:** Consumes `courses.json` (`[{"id", "title", "slug"}]`) and `trends.json`. Produces:
- `candidates(rows: list[dict], limit: int = 40) -> list[dict]`: Google News and Hacker News rows whose headline names
  work, jobs, hiring, layoffs, skills, careers, salaries, staff or workforce; deduplicated by headline.
- `build_prompt(run: Path) -> str`
- `parse_answer(text: str) -> dict`: the last fenced `json` block, else the outermost `{...}`; raises ValueError.
- `run_agy(prompt, model, timeout, runner=subprocess.run) -> str`
- CLI `gemini_check.py <run> [--model M] [--timeout S]`. It writes `gemini-raw.txt` and, on success, `checked.json`
  with `"checked_by": "gemini:<model>"`. Exit 1 on timeout, a missing `agy`, or an unparseable answer.

Steps:
1. Write the tests, with a fake runner: prose plus 2 JSON blocks keeps the last; timeout and FileNotFoundError give
   exit 1 with no `checked.json`; the prompt contains the editorial rules text, the candidates, the courses and the
   window, and stays under 30,000 characters; the argv has `--sandbox` and not `--dangerously-skip-permissions`; the
   cwd is an empty temp folder.
2. Watch them fail.
3. Implement.
4. Watch them pass.
5. Commit.

### Task 3: Wire into the skill and the scheduled run

**Files:** Modify `skills/nerdit-trend-reels/SKILL.md` (Run, step 3; Files in a run folder),
`scripts/scheduled_run.ps1` (`$names` gains `gemini_check.py` and `checked_check.py`), and `editorial.md` (a
checker line).

Step 3 becomes:
1. Write `<run>/courses.json` from `mcp__nerdit__catalogue_status` (live courses only).
2. Run `gemini_check.py <run>`, then `checked_check.py <run>`.
3. If either fails, do the check yourself as today and run `checked_check.py` until it passes.
4. With nothing kept, the report says "No safe story today."

Test: `test_docs` (if present) or a new test asserting that SKILL.md names both scripts and the fallback.

### Task 4: Live check and 2-run replay

1. **Live smoke test:** `agy -p` with `--sandbox` can still search and fetch. If `--sandbox` blocks fetching, rule
   on dropping it and ledger the ruling.
2. **Replay:** copy the 26 Nov pilot 2 and 27 Nov scheduled runs to the scratchpad, write `courses.json` from
   `catalogue_status`, and run `gemini_check.py` then `checked_check.py` on each. Also run `checked_check.py` on the
   Claude-made `checked.json` of both runs.
3. **Write `docs/superpowers/specs/2026-11-28-phase5-replay.md`:** time, checker result, stories kept by each,
   overlap, quote confirmation. Recommend keep or drop.
4. **Bump the plugin to 3.27.0**, run every suite, commit, and report. Push and merge wait for the owner.
