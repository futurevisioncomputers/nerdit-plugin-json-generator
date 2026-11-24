# Self-improving content: issue log, triage, learned rules

Date: 2026-11-19
Status: approved by the owner 2026-11-24; next: implementation plan
Repos touched: `nerdit-plugin-json-generator` (most of it), `nerdit/functions` (articles, phase 3), `nerdit-admin` (phase 3)

## Intent

The owner wants the plugin to improve itself. Each time an issue or bug is found in a lesson, quiz,
dataset, social post or article, the fix must stick, so the next course, pack or article never
repeats it.

True reinforcement learning (changing model weights from a reward) is not possible: lessons are
written by Claude agents and articles by free NVIDIA models over an API, and neither can be
fine-tuned here. "Learning" therefore means: **every issue is recorded, and recurring issues
become a rule plus a checker that run on every future generation.** The plugin already improves
this way by hand (`deprecated.md`, `voice.md`, ~30 `check_*.py` scripts, `rules_pack.py`; 39 of
272 commits are fixes). This design automates the capture and the proposal steps and keeps the
owner in charge of what becomes a rule.

## Owner decisions

1. **Fix by cost.** If fixing the current content is small, fix it now on the same data. If it is
   big (many tokens), do not touch the current content; save the improvement for the next
   generation.
2. **Exception (proposed, owner said ok):** a big issue that shows a learner something broken or
   wrong (wrong output, failing code, wrong quiz answer) gets a minimal patch of that one spot now;
   the full rewrite still waits.
3. **Both kinds teach the plugin.** A small fix also produces a rule + checker; a big one produces
   the rule + checker only.
4. **New rules wait for owner OK** before they become active.
5. **Approach A** (files in the plugin, git-tracked); see Approaches.

## Goals

- Capture every issue found, automatically wherever a script finds it.
- Triage each issue as small (fix now) or big (defer), with the learner-visible exception.
- Group recurring issues and draft a rule + checker + test for owner review.
- Cover three producers: `nerdit-chapter-generator` (lessons, quizzes, world/datasets),
  `nerdit-social-posts` (packs), and articles (`nerdit/functions`).
- Show whether learning works: issue counts per run fall over time, and issues found by a human
  with no checker that caught them approach zero.

## Non-goals

- Training or fine-tuning any model.
- A learner-facing "report a problem" button (later; the site has none today).
- An admin page for reviewing rules (Approach B; later if wanted).
- Regenerating content automatically for big fixes.

## Anti-goals (failure even if it technically works)

- A rule switches on without the owner's OK.
- Rule bloat: every run's writer prompt grows and token cost climbs. Prefer a checker with a `FIX`
  hint over prose; any prose rule is at most 3 lines and sits behind the right `<!-- pack: -->` tag.
- A new checker with false positives that forces lesson regeneration (the QA validator did exactly
  this once; see `agents/nerdit-qa-validator.md`). Every checker ships with a fail fixture from
  the real issue and a pass fixture from a known-good lesson, and is run over existing courses
  before activation.
- Bypass scripts that generate or patch content outside the plugin's skills (owner rule: content
  goes through the plugin only; a rule ships with its checker).

## Constraints

- Plugin scripts are stdlib-only Python with a `test_*.py` beside each (pytest).
- A small fix never resumes a writer agent (resuming costs ~200k tokens).
- Lesson format, CSS and schema changes follow `AGENTS.md` cross-project sync.
- No new Firestore traffic during normal generation runs (September egress bill).
- Pilot first: run on one course and one pack and get owner OK before rollout.
- Deploys and pushes need owner approval each time.

## Approaches

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | Issue log + proposals as files in the plugin; `learn.py` script; owner reviews in Claude Code; approved rules land in existing reference files and checkers | Zero running cost; git history shows each rule and its evidence; matches how the plugin already improves. Review happens in Claude Code, not admin | **Chosen** (owner handed over the how; owner said ok) |
| B | Issue log + rule queue in Firestore, admin "Learning" page, plugin pulls approved rules before each run | Review from anywhere; social skips already in Firestore. Costs Firestore reads, work in 3 repos, deploys, and generation needs network | Later, if owner wants admin review |
| C | Append "lessons learned" notes to writer prompts | Cheapest to build, but grows token cost every run and enforces nothing | Dropped |

## Design

### 1. The issue log

One git-tracked file: `nerdit-plugin-json-generator/learn/issues.jsonl` in the plugin's **source
checkout**, one JSON object per line.

*Location (builder-check answer, my call):* Claude Code runs the plugin from an installed cache
copy (`~/.claude/plugins/cache/fv-analysis-marketplace/nerdit_content_creator/<version>/`), which
is replaced on every update. So the log must never be written relative to `CLAUDE_PLUGIN_ROOT`.
`learn.py` and every `--log` writer resolve the folder from the environment variable
`NERDIT_LEARN_DIR`, set to the checkout's `learn/` folder in the owner's Claude Code user
settings (`env` block). If it is unset, they exit with an error naming the variable; they never
fall back to the cache. Claude commits `learn/` locally together with each `learn(...)` rule
commit and at the end of each generation run; pushes still need owner approval.

| Field | Meaning |
|---|---|
| `id` | `ISS-YYYYMMDD-NNN` |
| `date` | ISO date |
| `run` | run id `<ref>-<YYYYMMDD-HHMM>`, set once by the orchestrator per generation run and passed to every gate, so per-run counts work (my call) |
| `skill` | `lessons` \| `social` \| `articles` |
| `ref` | course slug, pack id or article slug |
| `item` | lesson id, slide/post id, or section |
| `stage` | `draft` (caught by a gate while the writer is still working) \| `final` (got past gates: QA, owner, admin, learner) |
| `source` | `gate` \| `qa` \| `owner` \| `admin` \| `learner` |
| `check` | name of the check that caught it, or `none` when a person found it |
| `message` | the failure line, as printed |
| `cause` | `writer` (rule existed, writer missed it) \| `rule-gap` (no rule) \| `data` (world/dataset) \| `checker-bug` \| `tool` |
| `cost` | `small` \| `big` |
| `action` | `fixed-now` \| `deferred` \| `patched-now+deferred` \| `none` (draft stage) |
| `rule` | proposal id once linked |
| `status` | `open` \| `fixed` \| `deferred` \| `ruled` \| `wontfix` |

Two signals matter most:
- `stage: final` with `check: none` means a person found it and no checker exists. That is a
  candidate for a **new checker**.
- `stage: draft` counts per check show which existing rules writers miss most. That is a
  candidate for **clearer rule wording**, not a new rule.

Duplicates are dropped by a key of (`run`, `skill`, `ref`, `item`, `check`, normalized
`message`), so re-running a gate inside one run does not flood the log, while the same failure in
a later run counts again.

*Gate-logged defaults (my call):* a `stage: draft` entry is written with `cause: writer`,
`action: none`, no `cost`, `status: fixed` once the gate passes. `cost` is required only for
`stage: final` entries. `cause` for final entries is set by Claude when logging.

### 2. Capture

- `gate_lesson.py`, `verify_course.py` and the social `packcheck.py` gain an optional
  `--log <issues.jsonl>` flag. Each failure line is appended with `source: gate`. SKILL.md passes
  the flag on every run. Gate failures during the writer's own loop are logged as `stage: draft`.
- QA validator findings: the orchestrator runs `learn.py log --from-qa <report>` after the
  validator returns.
- Owner-reported issues: a new small skill, `nerdit-learn`, triggers whenever the owner reports a
  problem in any NerdIT content ("this quiz answer is wrong", "log this", "the Reel says 5 but the
  lesson says 4"), in any session, not only inside a generation run. It logs the issue first
  (`learn.py log ...`), triages it, then fixes or defers it. It also fronts `report`, `propose`
  and `review`. Each generator's SKILL.md points to it. Without this entry point the scoreboard's
  `check: none` count would read as zero because logging was skipped (builder-check answer, my
  call). Admin and learner finds reach the log the same way until phase 3: the owner tells Claude.
- Admin skips of social posts and owner edits of AI article drafts: phase 3 (see Phases).

### 3. Triage (fix by cost)

Claude assigns `cost` when logging, from this table; `learn.py` rejects an entry without it.

| small: fix now on the same data | big: defer to next generation |
|---|---|
| Direct edit of existing files, then re-run the gate. No writer agent | Needs a writer re-run or lesson rewrite |
| Quiz answer, one code line, caption, number, typo, figure label, one dataset value in one lesson | World/dataset regenerated across lessons |
| One slide's text, one caption, re-render of that single image | Whole pack rebuild, Reel or video re-render |

Exception: if a `big` issue shows a learner something broken or wrong, patch that one spot now
(`action: patched-now+deferred`) and defer the rest.

Small fixes are followed by re-gate and, for live content, re-import through the admin's existing
"Import JSON + Images" page (social: re-import of the pack) and a check on the real site. A
re-import is a normal admin write, not a generation run; the no-Firestore constraint applies to
generation and to `learn.py`.
Deferred issues stay `deferred`; `learn.py next --ref <course>` lists them when that course or
pack is next regenerated.

### 4. Proposals

`learn.py propose` groups open issues by (`skill`, `check`, `cause`, normalized message). A group
qualifies when it has at least 2 issues across at least 2 items or courses, or holds any
`stage: final` issue with `check: none`. It does grouping only (stdlib, zero model tokens).

For each qualifying group Claude writes `learn/proposals/<RULE-id>.md`:
- evidence: the issue ids and their lines
- where the rule goes: a `CORE.md` section, a `voice.md` regex, a `deprecated.md` line, an
  existing check script, or a new `check_*.py` (articles: `aiDraftPrompt` and `articleProblems`
  in `nerdit/functions/src/articles.ts`)
- the prose rule text (if any, at most 3 lines) and its pack tag
- the checker plan, with a fail fixture taken from the real issue and a pass fixture from a
  known-good lesson or post

### 5. Review and activation

`learn.py review` lists open proposals. Per proposal the owner says OK or no.

- **OK:** Claude implements test-first: fixture tests, then the checker, then the rule text. Runs
  the full suite, then runs the new checker over every course and pack in the workspace and
  reports the hits. The workspace corpus is the course folders under
  `D:/siddharth/nerdit-backup/nerdit-mainAndPlugin/nerdit-mainAndPlugin/` (each holds a
  `course-*_output.json`, lesson files, or a `social-pack/`). This is a manual step on the
  owner's machine, not a pytest test, because the corpus is not in the plugin repo. Any hit in already-published, known-good content must be explained before the
  rule is kept. Commit as `learn(<RULE-id>): <one line>`, bump the plugin version, mark linked
  issues `ruled`.
- **No:** proposal marked `rejected` with the reason. The group is not proposed again unless its
  evidence count doubles.

### 6. Rule budget

`test_rules_pack.py` gains a size budget per assembled pack that `rules_pack.py` writes (each
preset × runner combination), measured in bytes: today's size plus 10%. A new prose rule that
breaks the budget must replace or tighten existing text; Claude drafts that tightening inside the
same proposal so the owner approves both together. This keeps writer token cost flat as rules
accumulate.

### 7. Scoreboard

`learn.py report` prints, per skill: draft-stage gate failures per lesson per run, final-stage
issues per run, final-stage issues with `check: none`, the top recurring checks, and rules added.
Learning works when final-stage issues fall and `check: none` approaches zero.

## Phases

1. **Log and capture** (lessons + social): `learn/issues.jsonl`, `learn.py log | next | report`
   (`log` validates required fields itself), `--log` and `--run` on `gate_lesson.py`,
   `verify_course.py`, `packcheck.py`, the `nerdit-learn` skill, `NERDIT_LEARN_DIR` in user
   settings, SKILL.md instructions. Pilot on the next course run and the next pack; owner reviews
   the log.
2. **Proposals and activation**: `learn.py propose | review`, proposal template, rule budget test.
3. **Articles and admin signals**: learned article rules land in `aiDraftPrompt` and
   `articleProblems` (vitest, batched to limit deploys); admin gets an optional skip reason on
   social posts and keeps the AI draft beside the published article, so `learn.py` can import
   skips and draft-vs-published edits. Needs deploy approval. Article issues use the same
   `learn/issues.jsonl` (`skill: articles`) and the same proposal files; only the activation step
   differs (vitest in `nerdit/functions` instead of pytest).

## Left to the builder

- `learn.py` internals, CLI flag spellings, the message-normalization rule for dedupe and grouping.
- Whether `--log` is a flag or an environment variable passed through SKILL.md.
- How phase 3 reads skip reasons and drafts (export file vs a small read) as long as normal
  generation runs make no Firestore calls.
