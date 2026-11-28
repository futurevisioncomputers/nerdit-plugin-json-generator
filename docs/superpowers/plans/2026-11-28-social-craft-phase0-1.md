# Social craft, Phase 0 + 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Check the facts the visual phases depend on (Phase 0), then ship a new `nerdit-social-craft` skill whose hook,
humanizer and fold checkers run inside the existing social-posts and trend-reels checkers (Phase 1).

**Architecture:** Port four stdlib-only scripts from `Jakeschincariol/instagram-agent-skill` (MIT) into
`skills/nerdit-social-craft/scripts/`, each exposing an `*_errors(text, label) -> list[str]` function in the house
style (print what is wrong, exit 1). `captions.py`, `packcheck.plan_text_errors` and `script_check.py` import them
by path (the `trend_captions.py` pattern: reuse, never copy). No credits, no visuals, no server or admin change.

**Tech Stack:** Python 3.14 stdlib + pytest (installed). Claude in Chrome for Phase 0 only. Gemini CLI 0.64.0.

**Spec:** `docs/superpowers/specs/2026-11-28-gemini-visuals-and-social-craft-design.md` (sections 4, 7.1, 7.2 caption
wiring, 7.3 step 5, 9 phases 0-1).

## Global Constraints

- Every rule ships with its checker and tests in the same commit (owner rule). Checkers print what is wrong and exit
  1; the agent fixes the input, never the checker.
- Console output is ASCII-safe: `print(e.encode("ascii", "replace").decode())` (the Windows console is cp1252).
- No new pip dependencies. The ported scripts stay stdlib-only.
- Each adapted file starts with `Adapted from https://github.com/Jakeschincariol/instagram-agent-skill (MIT, Copyright
  (c) 2026 Jake Schincariol).` `THIRD_PARTY.md` holds the full MIT texts of instagram-agent-skill and
  `sergebulaev/linkedin-skills` (Copyright (c) 2026 Sergey Bulaev).
- Hook pass mark: **50** (owner-approved Trend hook scores 50.6; 12 of 14 Maths hooks pass).
- Human-score gate: LinkedIn captions only; error below **50** (verdict FLAGGED).
- Fold: Instagram **125** characters; LinkedIn **210** unless Task 1 records a sourced value.
- Humanizer scans English and Roman Hinglish; it never runs on story-video narration.
- Generated files never go inside the plugin folder (docs excepted).
- Tests run from the plugin root: `python -m pytest skills/<skill>/scripts -q`.
- Commit locally. Push and plugin reinstall wait for the owner's OK.

## Review Focus

- Roman Hinglish Instagram/Facebook captions ("Save karo, link in bio") must not trip stock-word errors. Test in Task 3.
- Link text and hashtags (UTM links, `#journey`) must never count as stock words or as the fold's first sentence. Tests in Tasks 3 and 5.
- A Windows console printing `₹`, `²` or Devanagari from a CLI must not crash. Test in Task 2 (the shared `say()` helper).
- `script.json` from an older run without `hooks` must give a clear error, not a `KeyError`. Test in Task 7.
- A two-line on-screen hook (`"Put -2 in brackets\nbefore you square it"`) scores the same as one line. Test in Task 2.

## Out of this plan (later phases, by design)

- `beats.py` (frame-change timing) belongs to Phases 3 and 4, when openers and scenes change the frame. Today a Dev
  Reel is one shot, so a 4 s beat rule would fail every Reel.
- `swipe.py` and `audit` belong to Phase 6.
- Carousel rules (slide numbers, recap slide, handle, alt text) belong to Phase 2, which changes brand-studio pages
  anyway.

---

### Task 1: Phase 0 facts

**Files:**
- Create: `docs/superpowers/specs/2026-11-28-phase0-facts.md`

**Interfaces:**
- Produces: `IG_CAP` (int) and `LI_FOLD` (int) for Tasks 5 and 6; the picture facts for the Phase 2 plan.

- [ ] **Step 1: Gemini CLI headless.** Run `gemini --help` and record the flags for prompt mode, output format,
  approval mode and allowed tools. Then run
  `gemini -p "Use Google Search. Give one AI-and-jobs news headline from the last 2 days as: title | outlet | URL" --output-format json`.
  Record: did it run without a prompt, did it search, and any quota line.
- [ ] **Step 2: Instagram hashtag cap.** Use WebSearch, then WebFetch on Instagram Help Center or Meta newsroom pages
  only. Record `IG_CAP` with the source URL. With no primary source, `IG_CAP = 8` (unchanged), marked "unconfirmed".
- [ ] **Step 3: LinkedIn fold.** Use WebSearch for the "see more" cut length. Record `LI_FOLD` and its source. With no
  primary source, `LI_FOLD = 210`, marked "estimate".
- [ ] **Step 4: Flow pictures.** Load the claude-in-chrome core tools (one ToolSearch). Open flow.google.com, project
  "NERDIT trend reels", and switch to picture (image) mode. Read the "will use N credits" label. Only if N is 0,
  generate one picture with "a bright, empty desk by a window, morning light, no text" and download it. Record the
  credits, any visible watermark (where), the pixel size and the ratios on offer. If N is above 0, do not generate;
  record N.
- [ ] **Step 5: Gemini app pictures.** Open gemini.google.com and make one picture with the same prompt (this uses the
  daily picture limit, not Flow credits). Download it. Record the watermark, pixel size, the download format and any
  daily limit the app or its help page states.
- [ ] **Step 6: Write `2026-11-28-phase0-facts.md`.** One row per fact: value, source or "seen in app", date checked.
- [ ] **Step 7: Commit.** `git add docs/superpowers/specs/2026-11-28-phase0-facts.md && git commit -m "docs: phase 0 facts for gemini visuals"`

### Task 2: `nerdit-social-craft` skill and `hookscore.py`

**Files:**
- Create: `skills/nerdit-social-craft/SKILL.md`, `skills/nerdit-social-craft/THIRD_PARTY.md`
- Create: `skills/nerdit-social-craft/references/hooks.json`
- Create: `skills/nerdit-social-craft/scripts/hookscore.py`, `skills/nerdit-social-craft/scripts/textio.py`
- Test: `skills/nerdit-social-craft/scripts/test_hookscore.py`, `skills/nerdit-social-craft/scripts/test_docs.py`
- Create (workspace, not the plugin repo): `../.agents/skills/nerdit-social-craft/SKILL.md`

**Interfaces:**
- Produces: `score_hook(text: str) -> dict` returning `{"score": float, "verdict": "STRONG"|"OK"|"WEAK", "weakest": str, "flags": list[str]}`
- Produces: `hook_errors(text: str, label: str, minimum: float = 50.0) -> list[str]`
- Produces: `best_hook(options: list[str]) -> tuple[str, dict]` (the highest score; ties go to the first)
- Produces: `textio.say(line: str) -> None` (prints ASCII-safe), used by every CLI in this skill
- Produces: `main(argv: list[str]) -> int` in every script of this skill (`sys.exit(main(sys.argv[1:]))`, the
  `script_check.py` pattern)

- [ ] **Step 1: Write the failing tests** in `test_hookscore.py`:

```python
import pytest
from hookscore import best_hook, hook_errors, score_hook

def test_owner_approved_trend_hook_passes():
    r = score_hook("Ninety-six percent of Indian employees use AI at work.")
    assert r["score"] == pytest.approx(50.6, abs=0.1) and hook_errors("Ninety-six percent of Indian employees use AI at work.", "hook") == []

def test_vague_hook_fails_with_weakest_named():
    assert score_hook("Movement = end minus start")["score"] == pytest.approx(27.6, abs=0.1)
    assert hook_errors("Movement = end minus start", "d03-reel") == [
        "d03-reel: hook scores 28; at least 50 (weakest: SPECIFICITY)"]

def test_number_hook_scores_ok():
    assert score_hook("2 cubed is 8, not 6")["score"] == pytest.approx(62.6, abs=0.1)

def test_greeting_is_a_dealbreaker():
    errs = hook_errors("Hey guys, today I wanted to talk about Excel", "hook")
    assert any("Greeting" in e for e in errs)

def test_two_line_hook_scores_as_one_line():
    assert score_hook("Put -2 in brackets\nbefore you square it") == score_hook("Put -2 in brackets before you square it")

def test_best_hook_picks_the_highest():
    text, r = best_hook(["Movement = end minus start", "2 cubed is 8, not 6"])
    assert text == "2 cubed is 8, not 6" and r["verdict"] == "OK"

def test_cli_output_is_ascii(tmp_path, capsys):
    from hookscore import main
    f = tmp_path / "h.txt"; f.write_text("2² is 4, not ₹4\n", encoding="utf-8")
    main([str(f)])
    assert all(ord(c) < 128 for c in capsys.readouterr().out)

def test_hooks_json_drops_personal_result_formulas():
    import json, pathlib
    d = json.loads((pathlib.Path(__file__).parents[1] / "references" / "hooks.json").read_text(encoding="utf-8"))
    ids = {h["id"] for h in d["hooks"]}
    assert not ids & {1, 6, 15, 25} and 27 in ids and not set(d["classify_order"]) - ids
    assert all({"template", "example", "on_screen", "match"} <= h.keys() for h in d["hooks"])
```

- [ ] **Step 2: Run and see them fail.** Run `python -m pytest skills/nerdit-social-craft/scripts -q`. Expected:
  `ModuleNotFoundError: No module named 'hookscore'`.
- [ ] **Step 3: Implement `hookscore.py`.** Port `check_length`, `check_specificity`, `check_stakes`,
  `check_frontload`, `check_address`, `DEALBREAKERS` and the overall formula
  (`mean*0.6 + min*0.4 - 15*flags`, STRONG ≥70 with min ≥55 and no flags, OK ≥50, else WEAK) from
  ig-reel/hookscore.py unchanged. Join newlines to spaces before scoring. Error text:
  `f"{label}: hook scores {score:.0f}; at least {minimum:.0f} (weakest: {weakest})"`, plus `f"{label}: {flag}"` per
  dealbreaker. CLI: `hookscore.py <file>` takes one hook per line, prints the ranking through `textio.say`, and exits
  1 when the best hook scores below 50. `textio.say(line)` prints `line.encode("ascii", "replace").decode()`.
- [ ] **Step 4: Write `references/hooks.json`.** Start from ig-reel/hooks.json. Drop ids 1, 6, 15 and 25 (they need a
  personal or someone else's result, and NERDIT never invents one) from `hooks` and `classify_order`. Add id 27
  "The Job Ad Says": template `"{Skill} is in {N} of {M} {role} job ads."`, `trap`: `"Only a number from a kept
  source (Trend Reels) or the lesson."` Fill in `example`, `on_screen`, `best_for` and `match`. Keep the file's
  `note` and `rules`, and add the MIT line to `note`.
- [ ] **Step 5: Write `SKILL.md`, `THIRD_PARTY.md` and the Codex mirror.**
  - `SKILL.md` frontmatter: name `nerdit-social-craft`; the description says it scores hooks, finds AI-sounding
    words, checks the feed fold, and is used by nerdit-social-posts and nerdit-trend-reels, or alone ("score these
    hooks", "humanize this caption").
  - The body lists each script with its CLI line and says: write 3 hooks from 3 different formulas in
    `references/hooks.json`, score them, use the best.
  - The Codex mirror follows `../.agents/skills/nerdit-social-posts/SKILL.md` word for word with the skill name
    swapped.
- [ ] **Step 6: Write `test_docs.py`.** `test_skill_md_names_only_scripts_that_exist`: every `scripts/<name>.py` named
  in `SKILL.md` exists. This is the `nerdit-chapter-generator/scripts/test_docs_refs.py` pattern.
- [ ] **Step 7: Run and see them pass.** `python -m pytest skills/nerdit-social-craft/scripts -q`, expect all pass.
- [ ] **Step 8: Commit.** `git add skills/nerdit-social-craft && git commit -m "feat(social-craft): hook scorer and formulas"`

### Task 3: `humanize.py` and `slop.json`

**Files:**
- Create: `skills/nerdit-social-craft/scripts/humanize.py`, `skills/nerdit-social-craft/references/slop.json`
- Test: `skills/nerdit-social-craft/scripts/test_humanize.py`

**Interfaces:**
- Consumes: `textio.say`
- Produces: `clean(text: str) -> tuple[str, dict]` (fixed text, no trailing newline; report keys `invisible`, `typographic`, `lexical`, `structures`)
- Produces: `slop_errors(text: str, label: str) -> list[str]`

- [ ] **Step 1: Write the failing tests:**

```python
from humanize import clean, slop_errors

def test_em_dash_is_an_error():
    assert slop_errors("A venv keeps packages apart — always.", "instagram") == [
        "instagram: em dash; use a comma or a full stop"]

def test_invisible_character_is_an_error():
    assert slop_errors("Save​this", "facebook") == ["facebook: invisible character ZERO WIDTH SPACE (delete it)"]

def test_stock_word_names_the_plain_word():
    assert slop_errors("Unlock your Excel skills.", "linkedin") == ["linkedin: stock word 'unlock' (say 'get')"]

def test_cut_word_says_cut_it():
    assert slop_errors("Notably, Python is free.", "linkedin") == ["linkedin: stock word 'notably' (cut it)"]

def test_structure_is_flagged_with_its_fix():
    errs = slop_errors("It's not just a tool, it's a habit.", "linkedin")
    assert len(errs) == 1 and errs[0].startswith("linkedin: \"It's not just X, it's Y\"")

def test_nerdit_keeps_tech_words():
    assert slop_errors("The Python ecosystem is robust.", "linkedin") == []

def test_links_and_hashtags_are_ignored():
    assert slop_errors("Free lesson: https://nerdit.in/journey?utm_source=x #journey", "facebook") == []

def test_roman_hinglish_caption_passes():
    assert slop_errors("Aaj venv seekho, har project ka folder alag rakho. Save karo, link in bio.", "instagram") == []

def test_clean_fixes_dash_and_word():
    assert clean("We leverage venv — always.")[0] == "We use venv, always."
```

- [ ] **Step 2: Run and see them fail.** Run `python -m pytest skills/nerdit-social-craft/scripts/test_humanize.py -q`.
  Expected: `ModuleNotFoundError`.
- [ ] **Step 3: Write `references/slop.json`.** Start from ig-human/slop.json, all keys. Add the tells from
  linkedin-skills `skills/linkedin-humanizer/references/audit-ai-tells.md` that it lacks, as `words` and `phrases`
  entries with `"family": "linkedin"`. Add `"nerdit_keep": ["ecosystem", "robust"]`: these are skipped, because they
  are teaching words in tech courses.
- [ ] **Step 4: Implement `humanize.py`.**
  - `clean` ports `protect_urls`, `pass_invisible`, `pass_typographic`, `pass_lexical`, `restore_capitals`,
    `restore_urls` and `scan_structures` from ig-human/humanize.py, and strips the result.
  - `slop_errors` masks URLs and `#hashtags` first, then reports, in this order:
    - invisible characters: `"{label}: invisible character {name} (delete it)"`
    - em dash: `"{label}: em dash; use a comma or a full stop"`
    - en dash: `"{label}: en dash; use a hyphen"`
    - each lexicon hit on whole words, case-insensitive, once per term: `"{label}: stock word '{find}' (say '{replace}')"`,
      or `(cut it)` when `replace` is empty
    - each structure: `"{label}: {name}: {fix}"`
  - Longer phrases match before the words inside them ("delve into" before "delve").
  - CLI: `humanize.py <file> [--fix]` prints the errors, or the cleaned text with `--fix`, and exits 1 on errors.
- [ ] **Step 5: Run and see them pass.** `python -m pytest skills/nerdit-social-craft/scripts -q`, expect all pass.
- [ ] **Step 6: Commit.** `git add skills/nerdit-social-craft && git commit -m "feat(social-craft): humanizer and stock-word lexicon"`

### Task 4: `humanscore.py`

**Files:**
- Create: `skills/nerdit-social-craft/scripts/humanscore.py`
- Test: `skills/nerdit-social-craft/scripts/test_humanscore.py`

**Interfaces:**
- Consumes: `references/slop.json` (same loader as Task 3)
- Produces: `human_score(text: str) -> dict` returning `{"score": float, "verdict": "PASS"|"REVIEW"|"FLAGGED", "checks": dict[str, tuple[float, str]]}`
- Produces: `human_errors(text: str, label: str, minimum: float = 50.0) -> list[str]`

- [ ] **Step 1: Write the failing tests.**
  - `test_plain_caption_passes`: the `OK_LI` text from `skills/nerdit-social-posts/scripts/test_captions.py` returns
    `[]` from `human_errors(OK_LI, "linkedin")`.
  - `test_slop_caption_is_flagged`: `"In today's fast-paced world, we leverage cutting-edge, robust, seamless tools to
    unlock a transformative journey. Moreover, it's not just a course, it's a game-changer!"` gives
    `["linkedin: reads machine-written (human score N; at least 50; weakest: X)"]`, with N below 50.
  - `test_checks_are_named`: `human_score(...)["checks"]` keys are BURSTINESS, SPECIFICITY, SLOP DENSITY,
    FINGERPRINT, VOICE.
- [ ] **Step 2: Run and see them fail.** Run `python -m pytest skills/nerdit-social-craft/scripts/test_humanscore.py -q`.
  Expected: `ModuleNotFoundError`.
- [ ] **Step 3: Implement.** Port the five checks and the `run` formula (`mean*0.6 + min*0.4`; PASS ≥70 with min ≥55,
  REVIEW ≥50, else FLAGGED) from ig-human/detect.py unchanged. Error text:
  `f"{label}: reads machine-written (human score {score:.0f}; at least {minimum:.0f}; weakest: {weakest})"`.
- [ ] **Step 4: Run and see them pass.** `python -m pytest skills/nerdit-social-craft/scripts -q`, expect all pass.
- [ ] **Step 5: Commit.** `git add skills/nerdit-social-craft && git commit -m "feat(social-craft): human score for LinkedIn text"`

### Task 5: `fold.py`

**Files:**
- Create: `skills/nerdit-social-craft/scripts/fold.py`
- Test: `skills/nerdit-social-craft/scripts/test_fold.py`

**Interfaces:**
- Consumes: `LI_FOLD` from Task 1
- Produces: `FOLD: dict[str, int] = {"instagram": 125, "linkedin": LI_FOLD}`
- Produces: `feed_window(text: str, platform: str) -> str` and `fold_errors(text: str, platform: str, label: str) -> list[str]`

- [ ] **Step 1: Write the failing tests.**
  - `test_long_first_sentence_is_cut`: a 140-character first sentence on Instagram gives
    `"instagram: first sentence is 140 characters; the feed cuts at 125"`.
  - `test_nothing_concrete_before_the_cut`: `"Most beginners install packages globally. Save this."` on Instagram gives
    `["instagram: nothing concrete before the cut (a number or a name like Python or Excel)"]`.
  - `test_name_counts_as_concrete`: `"Most beginners install Python packages globally."` returns `[]`.
  - `test_other_platforms_have_no_fold`: `fold_errors(<the 140-character text>, "facebook", "facebook") == []`.
  - `test_link_is_not_the_first_sentence`: `"https://nerdit.in/x\nSave 2 hours with Excel."` on LinkedIn returns `[]`,
    because URLs are masked before the first sentence is found.
- [ ] **Step 2: Run and see them fail.** Run `python -m pytest skills/nerdit-social-craft/scripts/test_fold.py -q`.
  Expected: `ModuleNotFoundError`.
- [ ] **Step 3: Implement.**
  - The first sentence runs to the first `.`, `!`, `?` or newline, after URLs are masked and leading whitespace and
    empty lines are dropped.
  - "Concrete" means a digit, or a capitalised word of 3 or more letters that does not start a line or a sentence:
    `re.compile(r"\d|(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}\b", re.MULTILINE)`. This is stricter than ig-caption's
    `CONCRETE_RE`, which counts "Save" after a full stop.
  - It is checked inside `feed_window` (the first `FOLD[platform]` characters).
  - Platforms not in `FOLD` return `[]`.
- [ ] **Step 4: Run and see them pass.** `python -m pytest skills/nerdit-social-craft/scripts -q`, expect all pass.
- [ ] **Step 5: Commit.** `git add skills/nerdit-social-craft && git commit -m "feat(social-craft): feed fold check"`

### Task 6: Wire into `nerdit-social-posts`

**Files:**
- Modify: `skills/nerdit-social-posts/scripts/captions.py` (the import block, `MAX_TAGS` at :13, and the end of `caption_errors` at :100-102)
- Modify: `skills/nerdit-social-posts/scripts/packcheck.py:78-93` (`plan_text_errors`)
- Modify: `skills/nerdit-social-posts/SKILL.md` (Write the words, step 2, and Caption rules)
- Test: `skills/nerdit-social-posts/scripts/test_captions.py`, `skills/nerdit-social-posts/scripts/test_pack.py`

**Interfaces:**
- Consumes: `hook_errors`, `slop_errors`, `human_errors`, `fold_errors` (Tasks 2-5); `IG_CAP` (Task 1)
- Produces: the same `caption_errors(...)` and `plan_text_errors(...)` signatures, returning the new errors

- [ ] **Step 1: Write the failing tests.** In `test_captions.py`:
  - `test_em_dash_in_caption_fails`: `OK_IG` with one `—` contains `"instagram: em dash; use a comma or a full stop"`.
  - `test_linkedin_slop_fails`: the Task 4 slop caption plus the UTM link gives an error starting
    `"linkedin: reads machine-written"`.
  - `test_instagram_fold_needs_something_concrete`: `"Most beginners install packages globally. ..."` gives the
    fold error.
  - Change the existing hashtag test to `f"instagram: 11 hashtags; at most {IG_CAP}"`.

  In `test_pack.py`:
  - `test_weak_reel_hook_fails`: `plan_text_errors([{"id": "d03-reel", "lessonId": "demo-01", "hook": "Movement = end minus start"}], {"demo-01": ""})`
    contains `"d03-reel: hook scores 28; at least 50 (weakest: SPECIFICITY)"`.
  - `test_cover_hook_is_scored`: a carousel whose `slides[0]` is `{"kind": "cover", "hook": "Movement = end minus start"}`
    gives `"<id>: cover: hook scores 28; ..."`.
- [ ] **Step 2: Run and see them fail.** `python -m pytest skills/nerdit-social-posts/scripts -q`. Expected: the new
  tests FAIL and the old ones pass.
- [ ] **Step 3: Implement.**
  - `captions.py`: add `sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "nerdit-social-craft" / "scripts"))`
    and import the four functions.
  - Set `MAX_TAGS["instagram"] = IG_CAP`.
  - In `caption_errors`, after the number check, add `slop_errors(text, p)` for every platform,
    `fold_errors(text, p, p)` (Instagram and LinkedIn are the only platforms with a fold), and, for LinkedIn only,
    `human_errors(text, p)`.
  - `plan_text_errors`: add `hook_errors(it["hook"], it["id"])` for every item with a `hook`, and
    `hook_errors(s["hook"], f"{it['id']}: cover")` for a carousel's first slide when its kind is `cover`.
  - Run `slop_errors` on the same `hook`/`text` fields the number check already reads.
- [ ] **Step 4: Fix the old fixtures that fail only because of the new rules** by sharpening their words (for example,
  add "Python" to `OK_IG`'s first sentence). Never loosen a rule. Run `python -m pytest skills/nerdit-social-posts/scripts -q`
  and expect all to pass.
- [ ] **Step 5: Update `SKILL.md`.** Step 2: write 3 hook options from `nerdit-social-craft/references/hooks.json` and
  keep the best (score at least 50, `hookscore.py`). Caption rules: the Instagram hashtag cap becomes `IG_CAP`; add a
  bullet each for the fold (125 / `LI_FOLD`, something concrete before the cut), stock words and dashes
  (`humanize.py`), and the LinkedIn human score.
- [ ] **Step 6: Commit.** `git add skills/nerdit-social-posts && git commit -m "feat(social-posts): hook, fold and humanizer checks"`

### Task 7: Wire into `nerdit-trend-reels`

**Files:**
- Modify: `skills/nerdit-trend-reels/scripts/script_check.py:31-79` (`script_errors`) and its imports
- Modify: `skills/nerdit-trend-reels/SKILL.md` (Run, step 5)
- Test: `skills/nerdit-trend-reels/scripts/test_script_check.py`

**Interfaces:**
- Consumes: `score_hook`, `best_hook`, `hook_errors`, `slop_errors`
- Produces: `script.json` gains `"hooks": [str, str, str]` (3 options for the line's first sentence). `trend_captions.py`
  gets the Task 6 caption rules through `caption_errors` with no change.

- [ ] **Step 1: Write the failing tests.**
  - `test_needs_three_hooks`: a script without `hooks` gives `"script.json needs 3 hook options in 'hooks'"`, not a
    `KeyError`.
  - `test_line_opens_with_the_best_hook`: `hooks = ["Ninety-six percent of Indian employees use AI at work.", "AI is
    changing work.", "Hey, AI news today."]` with a line that opens on the second option gives
    `"line must open with the best hook: 'Ninety-six percent of Indian employees use AI at work.'"`.
  - `test_weak_best_hook_fails`: when all 3 hooks score below 50, the result contains `"hook: hook scores ..."`.
  - `test_slop_on_card_fails`: a card fact with `—` gives `"card: em dash; use a comma or a full stop"`.
  - Add the owner-approved pilot 2 line's first sentence plus 2 weaker options to the existing good-script fixture, so
    it still passes.
- [ ] **Step 2: Run and see them fail.** `python -m pytest skills/nerdit-trend-reels/scripts -q`. Expected: the new
  tests FAIL.
- [ ] **Step 3: Implement.**
  - Insert the `nerdit-social-craft/scripts` path the same way `trend_captions.py` inserts social-posts.
  - In `script_errors`:
    - Check that `hooks` is a list of exactly 3 non-empty strings, or report the error above and skip the hook rules.
    - The first sentence of `line` (split as in the existing `MAX_SENTENCE` loop) must equal
      `best_hook(hooks)[0]`, ignoring case and surrounding spaces.
    - Add `hook_errors(best, "hook")`, then `slop_errors(line, "line")`, `slop_errors(card["chip"], "card")` and
      `slop_errors(fact, "card")` for each fact.
- [ ] **Step 4: Run and see them pass.** `python -m pytest skills/nerdit-trend-reels/scripts -q`, expect all pass.
- [ ] **Step 5: Update `SKILL.md` step 5.** Before writing `line`, write 3 hook options from 3 formulas in
  `nerdit-social-craft/references/hooks.json` into `script.json` `hooks`. `line` opens with the best one
  (`script_check.py` checks it).
- [ ] **Step 6: Commit.** `git add skills/nerdit-trend-reels && git commit -m "feat(trend-reels): three scored hooks and humanizer on the script"`

### Task 8: Real-data check and release 3.26.0

**Files:**
- Modify: `.claude-plugin/plugin.json` (`version` to `3.26.0`; add "nerdit-social-craft, which scores hooks and
  strips AI-sounding words for every post" to `description`)

- [ ] **Step 1: Full suite.** Run `python -m pytest skills -q`. Expected: all pass.
- [ ] **Step 2: Maths pack hooks.** Call `packcheck.plan_text_errors` on the items in
  `../math-ds-course/social-pack/mathematics-for-data-science-2026-12-10/pack-plan.json`, using
  `packcheck.lesson_texts(<packdir>.parents[1])`. Expected: hook errors for exactly two hooks, "Add the terms, not
  the index labels" (44) and "Movement = end minus start" (28).
- [ ] **Step 3: Maths pack captions.** Run `python skills/nerdit-social-posts/scripts/build_pack.py check ../math-ds-course/social-pack/mathematics-for-data-science-2026-12-10`.
  Expected: no hashtag, dash or stock-word errors (pre-check on 2026-11-28 found all 14 Instagram captions at 5 tags,
  0 dashes and 0 stock words). Report any fold or LinkedIn human-score error to the owner with the rule that fired;
  never loosen a rule to clear one. The pack gets rebuilt anyway after the pending maths-voice re-render, and that
  rebuild picks up the rules.
- [ ] **Step 4: Trend Reel pilot 2.** Copy `~/.nerdit-social/trend-reels/2026-11-26-daily-pilot2` to the session
  scratchpad. Add `hooks` (the line's first sentence plus 2 weaker options) to the copy's `script.json`, then run
  `script_check.py <copy>` and `trend_captions.py <copy>`. Expected: script passes, and any caption error is reported
  as in Step 3.
- [ ] **Step 5: Bump the version and commit.** Run `python -m pytest skills/nerdit-chapter-generator/scripts/test_docs_refs.py -q`
  and expect it to pass, then `git add .claude-plugin/plugin.json && git commit -m "release: 3.26.0 (social craft checks)"`.
- [ ] **Step 6: Stop and report** the commits, test counts, the Step 2-4 findings, and that push and plugin reinstall
  wait for the owner's OK. The next plan is Phase 2 (pictures), written from `phase0-facts.md`.
