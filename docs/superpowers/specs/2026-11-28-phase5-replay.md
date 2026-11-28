# Phase 5 replay: Gemini (agy) vs Claude on the two-outlet check

Run 2026-11-28 on copies of two real Trend Reel runs. Each copy holds the same `trends.json` and today's 68 live
courses. Model: `gemini-4-hydrogen-medium`, prompt with up to 40 work-news candidates, 6-minute limit. Every result
is judged by `checked_check.py`, with quotes confirmed on the outlets' pages.

| Run | Claude (the real run) | Gemini |
|---|---|---|
| 26 Nov (pilot 2) | 1 kept (BCG: 96% of Indian employees use AI; 3 outlets). Fails today's checker on format only: no `published`, evidence lines not led by the outlet name (that file predates the rule). | 3 kept, 37 dropped. **Checker fails:** the Business Standard quote was not found on its readable page. 3 pages could not be read (Japan Today, HR Asia, CTech), so 2 of the 3 stories are unconfirmed. It did not keep the BCG story Claude used. |
| 27 Nov (scheduled) | 1 kept (SAP 10,000 job cuts; Investing.com + Calcalist). **Checker passes:** the Calcalist quote was confirmed; the Investing.com page could not be read (warning). | **Failed:** `agy` hit the 6-minute print timeout with the turn unfinished (`DEADLINE_EXCEEDED`). Nothing written; the run would fall back to Claude. |

## What it shows

- **Gemini in `agy` print mode can search but not read pages.** Its only web tool is `search_web`. Its quotes come
  from search summaries, and our checker caught one that is not on the page. Claude reads each page with WebFetch.
- **It is slow with 40 candidates.** It works through every candidate (37 drops written), so one run of two hit the
  6-minute limit.
- **Its judgement differs.** It kept the NITES story (Times of India + Business Standard). Claude dropped that story
  on 27 Nov as one syndicated copy (Rediff).
- **Score: 0 of 2 runs passed.** Under the pilot rule (keep Gemini only if it passes as often as Claude over 2 runs),
  Gemini does not keep this step yet.

## Recommendation

Claude stays first for step 3. `gemini_check.py` stays in the plugin as an optional tool, not the scheduled path.
One tuned try is cheap: `gemini-3.8-flash-medium`, 15 candidates, a 10-minute limit, and "keep at most 1". Switch
only if it passes 2 runs in a row. `checked_check.py` stays on for every run, because it caught real problems in
both writers' files.
