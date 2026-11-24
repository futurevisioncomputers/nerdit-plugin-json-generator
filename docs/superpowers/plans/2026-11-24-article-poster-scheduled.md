# Article Poster Scheduled Runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily Windows Task Scheduler run that starts `claude -p --chrome` and posts every NerdIT article live 24 h or more to 8 API-less sites, inside pace caps, with a report and a desktop notification.

**Architecture:** `runlog.py` gains the deterministic parts (which articles are due, which sites today in scheduled mode, the day's report). Two PowerShell scripts own the timer and the unattended launch. `SKILL.md` gains a "Scheduled run" section that tells Claude how the run differs from the manual one. No admin, functions or Firestore change.

**Tech Stack:** Python 3 stdlib (`urllib.request`, `json`, `re`; the test file adds `import datetime as dt`), pytest; Windows PowerShell 5.1 (`Register-ScheduledTask`, WinRT toast); Claude Code CLI `claude -p --chrome`.

**Spec:** `docs/superpowers/specs/2026-11-23-article-poster-scheduled-design.md` (commit 8a5c247).

## Global Constraints

- Scheduled sites, in this order: `medium`, `hashnode`, `hackernoon`, `substack`, `vocal`, `dailydev`, `indiehackers`, `pinterest`.
- Manual-only (never in a scheduled plan): `quora`, `hackernews`, `linkedin`. API sites never posted by browser in scheduled runs: `wordpress`, `blogger`, `tumblr` (Dev.to is not in `SITES`).
- Due = live on nerdit.in **24 hours or more**, newest first. Date source: `https://nerdit.in/blog` JSON-LD `blogPost[].url` + `datePublished` (30 newest).
- Pace: at most 6 sites per article per day (unchanged); scheduled mode: **every** site at most once per day across all articles.
- Lock: a lock younger than **3 hours** means a run is in progress. Task: daily, default **09:00**, start when available after a missed start, time limit 3 h, only when the owner is logged on.
- Never type passwords/codes, solve CAPTCHAs, accept new terms; sign-in wall → `skipped` with the reason. No git, deploy, Firestore-write or Gmail tools in the run; never `--dangerously-skip-permissions`.
- State stays under `~/.nerdit-social/article-runs/` (`NERDIT_SOCIAL_HOME` overrides): logs in `logs/<date>.log`, reports in `reports/<date>.md`.
- Tests: `cd skills/nerdit-article-poster/scripts`, then `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD=1; python -m pytest -q` (PowerShell) — 10 tests today, 1 failing (fixed in Task 1).
- Work in a worktree on branch `article-scheduled` from `main` (8a5c247): `main` has another session's uncommitted chapter-generator edits and a 3.22.0 bump that must not be committed here.

## Review Focus

1. **Manual runs must not change.** A medium post for article A today must not stop the manual plan for article B from offering medium. → Task 2 test `test_manual_plan_ignores_other_articles_posts`.
2. **An article published 23 h 59 m ago is not due; exactly 24 h is.** → Task 3 test `test_due_boundary_is_24_hours`.
3. **nerdit.in/blog unreachable or changed** (no JSON-LD, no `blogPost`): `due` must print a PROBLEM line and exit 1 or list nothing, never crash or guess. → Task 3 tests `test_due_without_blogpost_is_empty` and `test_cli_due_fetch_error`.
4. **A site left `started` (Publish pressed, no outcome)** must show under "Check first" in the report, even if it was started on an earlier day. → Task 4 test `test_report_lists_unsettled_from_earlier_days`.
5. **A stale lock** (PC crashed mid-run yesterday) must not block today's run forever. → Task 5 verification step with a 4-hour-old lock.

---

### Task 1: Worktree + fix the broken recipe test

**Files:**
- Modify: `skills/nerdit-article-poster/references/sites/hashnode.md` (add the missing field line)

- [ ] **Step 1:** Create the worktree: `git worktree add .worktrees/article-scheduled -b article-scheduled main`. All later paths are inside it.
- [ ] **Step 2:** Run the tests. Expected: `1 failed, 9 passed` — `hashnode: **Canonical / original URL:**`.
- [ ] **Step 3:** In `hashnode.md`, after the `**Images:**` block, add:
  `- **Canonical / original URL:** In the Publish panel: 'Are you republishing?' -> the nerdit.in article URL (see Publish).`
- [ ] **Step 4:** Run the tests. Expected: `10 passed`.
- [ ] **Step 5:** Commit: `fix(article-poster): hashnode recipe keeps the canonical field line`.

### Task 2: Scheduled plan

**Files:**
- Modify: `skills/nerdit-article-poster/scripts/runlog.py` (`SCHEDULED_SITES`, `plan`, `mark`, CLI `plan --scheduled`, module docstring)
- Test: `skills/nerdit-article-poster/scripts/test_runlog.py`

**Interfaces:**
- Produces: `SCHEDULED_SITES: tuple[str, ...]`; `plan(slug: str, posted: set[str], today: str, scheduled: bool = False) -> list[str]`; CLI `python runlog.py plan --slug S --posted a,b [--scheduled] [--today D]`.
- `_daily.json` now counts **every** posted site per day (`{day: {site: n}}`), not only `ONCE_A_DAY`.

- [ ] **Step 1: Write the failing tests**

```python
def test_scheduled_plan_only_offers_scheduled_sites_capped_at_six():
    assert runlog.plan("a", set(), DAY, scheduled=True) == ["medium", "hashnode", "hackernoon", "substack", "vocal", "dailydev"]

def test_scheduled_every_site_once_a_day_across_articles():
    runlog.mark("a", "medium", "posted", DAY, url="https://medium.com/p/1")
    assert "medium" not in runlog.plan("b", set(), DAY, scheduled=True)
    assert runlog.plan("b", set(), NEXT, scheduled=True)[0] == "medium"

def test_manual_plan_ignores_other_articles_posts():
    runlog.mark("a", "medium", "posted", DAY, url="https://medium.com/p/1")
    assert runlog.plan("b", set(), DAY)[0] == "medium"

def test_scheduled_plan_never_offers_manual_only_or_api_sites():
    plan = runlog.plan("a", {"medium", "hashnode", "hackernoon", "substack", "vocal"}, DAY, scheduled=True)
    assert plan == ["dailydev", "indiehackers", "pinterest"]

def test_cli_plan_scheduled(capsys):
    assert runlog.main(["plan", "--slug", "a", "--scheduled", "--today", DAY]) == 0
    assert capsys.readouterr().out.split()[:2] == ["medium", "hashnode"]
```

- [ ] **Step 2:** Run the tests. Expected: the 5 new tests FAIL (`unexpected keyword argument 'scheduled'` / unknown CLI flag); the old 10 pass.
- [ ] **Step 3:** Implement. Scheduled mode: candidates are `SCHEDULED_SITES` and `full` is every candidate with `daily[site] >= 1`; manual mode keeps `full` = `ONCE_A_DAY` only. `mark` increments `_daily.json` for every `posted` site. Add the `--scheduled` flag (store_true) to the `plan` subparser and a line about it in the module docstring.
- [ ] **Step 4:** Run the tests. Expected: `15 passed`.
- [ ] **Step 5:** Commit: `feat(article-poster): runlog plan --scheduled (8 sites, each once a day)`.

### Task 3: Which articles are due

**Files:**
- Modify: `skills/nerdit-article-poster/scripts/runlog.py` (`due_slugs`, CLI `due`)
- Test: `skills/nerdit-article-poster/scripts/test_runlog.py`

**Interfaces:**
- Produces: `due_slugs(html: str, now: dt.datetime) -> list[str]` (pure; `now` is timezone-aware UTC); CLI `python runlog.py due [--now ISO]` prints one slug per line, or `nothing due`; on fetch error prints `PROBLEM could not read https://nerdit.in/blog: <error>` and exits 1.
- `BLOG_INDEX = "https://nerdit.in/blog"`.

- [ ] **Step 1: Write the failing tests.** The sample mirrors the live page: one `<script type="application/ld+json">{"@context":"https://schema.org","@type":"Blog",…,"blogPost":[{"@type":"BlogPosting","headline":"…","url":"https://nerdit.in/blog/<slug>","datePublished":"2026-11-22T11:05:42.209Z"},…]}</script>`.

```python
NOW = dt.datetime(2026, 11, 24, 12, 0, tzinfo=dt.timezone.utc)

def blog(*posts):  # posts: (slug, iso)
    items = ",".join(f'{{"@type":"BlogPosting","headline":"x","url":"https://nerdit.in/blog/{s}","datePublished":"{d}"}}' for s, d in posts)
    return f'<html><script type="application/ld+json">{{"@context":"https://schema.org","@type":"Blog","blogPost":[{items}]}}</script></html>'

def test_due_newest_first_and_skips_under_24_hours():
    html = blog(("old", "2026-11-14T09:00:00.000Z"), ("new", "2026-11-24T06:00:00.000Z"), ("mid", "2026-11-22T11:05:42.209Z"))
    assert runlog.due_slugs(html, NOW) == ["mid", "old"]

def test_due_boundary_is_24_hours():
    assert runlog.due_slugs(blog(("a", "2026-11-23T12:00:00.000Z")), NOW) == ["a"]
    assert runlog.due_slugs(blog(("b", "2026-11-23T12:00:01.000Z")), NOW) == []

def test_due_without_blogpost_is_empty():
    assert runlog.due_slugs("<html>no json-ld</html>", NOW) == []
    assert runlog.due_slugs('<script type="application/ld+json">{"@type":"Blog"}</script>', NOW) == []

def test_cli_due_fetch_error(monkeypatch, capsys):
    def boom(*a, **k): raise OSError("offline")
    monkeypatch.setattr(runlog.urllib.request, "urlopen", boom)
    assert runlog.main(["due"]) == 1
    assert capsys.readouterr().out.startswith("PROBLEM could not read https://nerdit.in/blog")
```

- [ ] **Step 2:** Run the tests. Expected: the 4 new tests FAIL (`no attribute 'due_slugs'`).
- [ ] **Step 3:** Implement. Find every `<script type="application/ld+json">…</script>` with a regex, `json.loads` each (skip ones that fail), take `blogPost` from the first that has it; slug = last path part of `url`; parse `datePublished` with `fromisoformat` after replacing a trailing `Z` with `+00:00`; keep `now - date >= 24 h`; sort by date, newest first. CLI fetches `BLOG_INDEX` with `urllib.request.urlopen(…, timeout=30)`, UTF-8.
- [ ] **Step 4:** Run the tests. Expected: `19 passed`. Then run `python runlog.py due` once against the live site; expected: a list of slugs that includes `career-roadmap-supervised-machine-learning-regression-algorithms-with-python`.
- [ ] **Step 5:** Commit: `feat(article-poster): runlog due lists articles live 24h+ from nerdit.in/blog`.

### Task 4: The day's report

**Files:**
- Modify: `skills/nerdit-article-poster/scripts/runlog.py` (`report`, CLI `report`)
- Test: `skills/nerdit-article-poster/scripts/test_runlog.py`

**Interfaces:**
- Consumes: the per-article logs `<slug>.json` (Task 2 format, unchanged); `unsettled(slug)`.
- Produces: `report(today: str) -> str` (Markdown); CLI `python runlog.py report [--today D]` prints it. **First line is fixed copy** the notification reads: `Posted: N · Skipped: N · Failed: N · Check first: N`. Then sections `## Posted` (`- <slug> · <site> · <url>`), `## Skipped` (`- <slug> · <site> · <error or "skipped">`), `## Failed` (`- <slug> · <site> · <error>`), `## Check first` (`- <slug> · <site> · Publish was pressed; is it live?`); empty sections are left out; with no steps today and nothing unsettled, the body is `Nothing ran today.`

- [ ] **Step 1: Write the failing tests**

```python
def test_report_groups_the_day_across_articles():
    runlog.mark("a", "medium", "posted", DAY, url="https://medium.com/p/1")
    runlog.mark("b", "vocal", "skipped", DAY, error="sign in needed")
    runlog.mark("b", "substack", "failed", DAY, error="editor changed")
    runlog.mark("a", "hashnode", "posted", "2026-11-20", url="https://x.hashnode.dev/a")
    text = runlog.report(DAY)
    assert text.splitlines()[0] == "Posted: 1 · Skipped: 1 · Failed: 1 · Check first: 0"
    assert "- a · medium · https://medium.com/p/1" in text and "- b · vocal · sign in needed" in text
    assert "- b · substack · editor changed" in text and "hashnode" not in text

def test_report_lists_unsettled_from_earlier_days():
    runlog.mark("a", "medium", "started", "2026-11-20")
    text = runlog.report(DAY)
    assert text.splitlines()[0].endswith("Check first: 1") and "- a · medium ·" in text

def test_report_with_nothing_today():
    assert runlog.report(DAY) == "Posted: 0 · Skipped: 0 · Failed: 0 · Check first: 0\n\nNothing ran today."
```

- [ ] **Step 2:** Run the tests. Expected: the 3 new tests FAIL.
- [ ] **Step 3:** Implement. Read every `*.json` in `_dir()` except `_daily.json`; per (slug, site), the latest step of `today` decides the section; "Check first" comes from `unsettled(slug)` (any day). A site that failed and then posted on the same day counts as Posted only.
- [ ] **Step 4:** Run the tests. Expected: `22 passed`.
- [ ] **Step 5:** Commit: `feat(article-poster): runlog report for the day across articles`.

### Task 5: Launcher, timer and the skill's "Scheduled run" section

**Files:**
- Create: `skills/nerdit-article-poster/scripts/scheduled_run.ps1`
- Create: `skills/nerdit-article-poster/scripts/schedule_task.ps1`
- Modify: `skills/nerdit-article-poster/SKILL.md` (frontmatter description + new `## Scheduled run` section after `## Run`)
- Test: `skills/nerdit-article-poster/scripts/test_runlog.py` (one doc check)

**Interfaces:**
- Consumes: CLI `due`, `plan --scheduled`, `mark`, `report` (Tasks 2–4).
- `scheduled_run.ps1 [-DryRun] [-Prompt <string>]`. Default prompt (exact): `Use the nerdit-article-poster skill: scheduled run.` Exit 0 when done or when another run holds the lock.
- `schedule_task.ps1 [-Time "09:00"] [-Remove]`. Task name (exact): `NerdIT article poster`.

- [ ] **Step 1: Write the failing doc test**

```python
def test_skill_has_a_scheduled_run_section_naming_every_scheduled_site():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    section = text.split("## Scheduled run", 1)[1]
    for needle in ("runlog.py due", "plan --scheduled", "runlog.py report", "24 hours", "sign in needed", *runlog.SCHEDULED_SITES):
        assert needle in section, needle
```

- [ ] **Step 2:** Run the tests. Expected: the new test FAILS (`IndexError`/missing section).
- [ ] **Step 3: SKILL.md.** Add `## Scheduled run` (when the prompt says "scheduled run"; never ask anything). Content = spec "How a scheduled run works" steps 2–5 as instructions: `runlog.py due` → Articles page saved links per due article → `plan --scheduled` per article newest first → per-site steps of the manual run with the scheduled differences (an article live 24 hours or more is the owner's yes, including where a recipe says "get the owner's yes"; sign-in wall / CAPTCHA / phone or email check / new terms → `mark --status skipped --error "sign in needed"` or the reason, close the tab, next site; `check first` sites untouched) → `runlog.py report --today <date>` saved to `~/.nerdit-social/article-runs/reports/<date>.md`, plus a line per due article whose WordPress.com/Blogger/Tumblr link is missing: "press Post copy on the Articles page". Name the 8 scheduled sites and the manual-only ones. Admin signed out → report `admin sign-in needed` and stop. Add "and runs by itself once a day (scheduled run)" to the frontmatter description.
- [ ] **Step 4:** Run the tests. Expected: `23 passed`.
- [ ] **Step 5: `scheduled_run.ps1`.** Order: resolve home (`$env:NERDIT_SOCIAL_HOME` or `~\.nerdit-social`) and create `article-runs\logs` + `article-runs\reports`; lock `article-runs\scheduled.lock` (holds the start time; younger than 3 h → log "run in progress" and exit 0; older → take it over); remove the lock in `finally`. If no `chrome` process, start Chrome (path from `HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe`) and wait 20 s. Run `claude -p --chrome --allowedTools <list> $Prompt`, output appended to `logs\<yyyy-MM-dd>.log`. Allowlist (spike in Rollout step 1 confirms the exact strings): the claude-in-chrome server's tools, `Skill`, `Bash(python *runlog.py*)`, `Read`/`Write` under `~/.nerdit-social/`, and the image download the recipes use. Then read the first line of `reports\<date>.md` (or "No report written" if missing) and show a Windows toast "NerdIT article poster" with that line (WinRT `ToastNotificationManager`, PowerShell's own AppId; no new module). `-DryRun`: do the lock and print the claude command line and paths; start nothing.
- [ ] **Step 6: `schedule_task.ps1`.** `Register-ScheduledTask` for the current user, "Run only when user is logged on", daily at `-Time`, action `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<full path of scheduled_run.ps1>"`, settings `-StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew`. `-Remove` unregisters it (no prompt). Re-running replaces the existing task.
- [ ] **Step 7: Verify the launcher.** With `$env:NERDIT_SOCIAL_HOME` set to a scratch folder:
  1. `scheduled_run.ps1 -DryRun` → prints a command starting `claude -p --chrome --allowedTools`; lock removed afterwards.
  2. Write a lock with the current time, run `-DryRun` again → log says "run in progress", exit 0.
  3. Write a lock dated 4 hours ago, run `-DryRun` → it takes the lock over and prints the command.
- [ ] **Step 8: Verify the timer.** `schedule_task.ps1 -Time 09:00` → `Get-ScheduledTask "NerdIT article poster"` shows a daily 09:00 trigger and StartWhenAvailable; then `schedule_task.ps1 -Remove` → `Get-ScheduledTask` finds nothing. (The owner turns it on for real in Rollout step 4.)
- [ ] **Step 9:** Commit: `feat(article-poster): scheduled daily run (launcher, timer, skill section)`.

---

## Rollout (owner present; not part of the build tasks)

1. **Spike** (spec Rollout 1): from a one-off Task Scheduler "Run" of `scheduled_run.ps1 -Prompt "List my Chrome tabs and take one screenshot of fv.nerdit.in/articles. Do nothing else."`, check the log shows the tab list. Then on the Articles page press one Copy button and paste into a scratch text box with Chrome in the background, and again with the PC locked. Record the exact allowlist strings that worked in `scheduled_run.ps1`. Any failure: stop and report to the owner.
2. **Manual pilot** (spec Rollout 2): the existing "post article" run on the Regression article for the scheduled sites it is not on yet; fix recipes, set each `Verified:`.
3. **Release:** bump `.claude-plugin/plugin.json` to the next minor above every version on `main` and open branches (3.22.0 is taken by uncommitted work on `main`), merge, then push and update the installed plugin. Push needs the owner's OK.
4. **One scheduled run by hand** while the owner watches; read `reports/<date>.md`.
5. **Turn on daily:** `schedule_task.ps1 -Time 09:00`, only after the owner's OK.
