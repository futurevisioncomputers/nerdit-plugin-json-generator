# Article writer (Codex first, Sonnet fallback) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A `nerdit-article-writer` skill. Codex CLI drafts a NerdIT blog article as `article.json` (the shape the
admin's Articles page already takes). `article_check.py` judges it. When Codex fails, Claude Sonnet writes or fixes
it under the same rules.

**Why (owner, 2026-11-28):** move article writing off Claude to Codex, with Sonnet as the safety net.

**Architecture:**
1. `article_brief.py` turns one live course into `brief.json`: title, URL, lesson titles from the course JSON when
   given, the type and the keyword.
2. `codex_write.py` sends brief + rules to `codex exec` once, read-only, in an empty temp folder, and keeps only the
   JSON block as `article.json`.
3. `article_check.py` enforces the rules (calibrated on the 3 existing articles). The social-craft humanizer runs on
   the prose.

**Calibration (2026-11-28, real articles):**

| Article | Title | Description | Words | H1 | H2 | nerdit.in links | Tags |
|---|---|---|---|---|---|---|---|
| Excel salary guide | 90 | 126 | 1,392 | 0 | 8 | 5 | 5 |
| ML career roadmap | 77 | 134 | 1,454 | 0 | 9 | 5 | 5 |
| Regression how-to | 89 | 137 | 631 | 5 | 7 | 4 | 5 |

The how-to is the thin one, and the rules fail it.

## Global Constraints

- **Rules:**
  - title 30-95 characters, with the keyword;
  - description 110-160 characters, with the keyword;
  - slug lowercase-hyphen, at most 90 characters;
  - 900-3,000 words of prose (code blocks not counted);
  - no `# ` H1 (the page title is the H1), at least 5 `## ` H2;
  - keyword in the first 100 words;
  - at least 3 links to `nerdit.in`, and one of them is the course URL;
  - 3-6 tags;
  - no stock words or dashes (social-craft `slop_errors`; an en dash inside a number range like `3–5` is fine);
  - any `₹`, `LPA`, `lakh` or `salary` figure needs a `## Sources` section with 2 or more outside links.
- Codex runs only through `codex_write.py`:
  - `codex exec` with `--sandbox read-only`, in a fresh empty temp folder;
  - never with `--dangerously-bypass-approvals-and-sandbox`;
  - the prompt goes on stdin.
- Never invent student results, placement numbers or salaries without a source.
- Checkers print what is wrong (ASCII-safe) and exit 1. Every rule ships with its test.
- Files go to `~/.nerdit-social/articles/<slug>/`, never into the plugin.
- Codex install and sign-in are the owner's to approve. Stop and ask.

## Tasks

1. **social-craft:** an en dash between digits is not an error. Test first.
2. **`skills/nerdit-article-writer/`:**
   - Files: `SKILL.md` (with the "Any model" paragraph), `references/article-rules.md`, `scripts/article_check.py`,
     `scripts/article_brief.py`, and tests.
   - Real data: the Excel and roadmap articles pass; the how-to fails on words and H1.
   - Codex mirror at `.agents/skills/nerdit-article-writer/SKILL.md`.
3. **`scripts/codex_write.py`** with a fake-runner test:
   - The last JSON block becomes `article.json` (`written_by: codex:<model>`).
   - Timeout, missing binary or a bad answer gives exit 1 and writes nothing.
   - The argv has read-only sandbox, `--skip-git-repo-check`, and no bypass flag.
   - The cwd is an empty temp folder.
   - `SKILL.md` step: Codex first, then `article_check.py`; on failure, Sonnet writes or fixes and re-checks.
4. **Codex CLI:** ask the owner to approve `npm i -g @openai/codex` (official OpenAI package). Check
   `codex login status` against the existing `~/.codex/auth.json`, and ask the owner to sign in only if needed. Then
   run one live article for a live course without an article, report it, and bump the plugin version.
