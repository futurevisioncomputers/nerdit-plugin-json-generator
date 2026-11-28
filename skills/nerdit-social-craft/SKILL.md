---
name: nerdit-social-craft
description: >
  Shared writing checks for NERDIT social posts: scores hooks from 0 to 100 against a pass mark of 50, finds
  AI-sounding words, dashes and invisible characters, and checks what the feed shows before "more". Used by
  nerdit-social-posts and nerdit-trend-reels (their checkers call these scripts), or on its own when the owner says
  "score these hooks", "humanize this caption", "does this sound like AI" or "check this LinkedIn post". Never posts
  anything.
---

# NERDIT Social Craft

The rules come from two MIT-licensed skill packs (see `THIRD_PARTY.md`), adapted for NERDIT: every number in a hook
or caption still comes from the lesson (course posts) or a kept source (Trend Reels), and nothing is ever invented.

`<scripts>` is this skill's `scripts/` folder; run each as `python <scripts>/<name>.py`. Each one prints what is
wrong and exits 1; fix the words, never the checker.

## Write a hook

1. Read `references/hooks.json`: formulas with a template, an example, the on-screen version, what each is for,
   and its trap. Formulas 1, 6, 15 and 25 of the source pack are left out (they need a result NERDIT does not have).
2. Write **3 hooks from 3 different formulas**, one per line in a text file. On-screen hooks are English, 5 to 12
   words, with a number or a name (Python, Excel, a company in the story) near the front.
3. Run `scripts/hookscore.py <file>`. It ranks them. Use the top one; under 50, none of them is the hook yet:
   write new ones.

Other skills call `hook_errors(text, label)` and `best_hook(options)` from `scripts/hookscore.py` directly.

## Check the words

`scripts/humanize.py <file>` lists what makes a caption, slide line or script read machine-written: invisible
characters, em and en dashes, stock words and phrases from `references/slop.json` (with the plain word to use), and
stock sentence shapes ("It's not just X, it's Y"). `--fix` prints a cleaned copy (dashes and stock words replaced);
read it before using it, because a sentence shape still needs a rewrite by hand. Links and hashtags are skipped.
Roman Hinglish captions are fine; never run it on story-video narration. Words in `nerdit_keep` (normal teaching
words such as "ecosystem") are never flagged. Other skills call `slop_errors(text, label)`.

`scripts/humanscore.py <file>` scores a longer English text (a LinkedIn post) on five checks: sentence-length
variety, concrete numbers and names, stock-word density, typed-by-machine characters, and voice (contractions,
"you" and "I"). Under 50 is FLAGGED: rewrite with a real number or name from the lesson, a short sentence next to a
long one, and plain words. Social-posts runs it on LinkedIn captions only (`human_errors(text, label)`).
