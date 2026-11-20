# brand-studio: one design engine for many brands (NERDIT first, Future Vision second)

Date: 2026-11-20. Owner decisions in this conversation: new look from the owner's 12 references
(`C:\Users\siddh\.nerdit-social\inspiration\2026-11-20-owner-refs\`); "A. Both" (a course intro
carousel plus the new look on every post); a separate skill, then a separate plugin "so we can use
this for other business banner also"; first version covers NERDIT and Future Vision Computers
Institute ("a"); student photos from Gemini (owner generates from a prompt sheet); Fluent 3D icons
for now; pilot on two live courses that have no video.

## Why

- The owner wants banners that attract an audience, in the style of the references, and never the
  same look twice (per course, following new trends), on light pages only.
- The look must be reusable: for future NERDIT post types (Short covers, festival, launch, LinkedIn
  banners, course images), for Future Vision Computers Institute, and later for other businesses
  (a saree or kurti seller). One engine, one brand kit per brand.

## Goals

1. A new plugin, `brand-studio`, holding the design system: brand kits, looks, parts, page types,
   asset library, render engine, checks, and a learn-from-references step.
2. NERDIT uses it for every social post (intro carousel, teaching carousels, Stories, LinkedIn
   cards) and for the course video thumbnail and course card image.
3. Future Vision uses it from a small content brief (admissions, courses offered, call to action).
4. Pilot: the two NERDIT courses below, plus one Future Vision banner set.

## Non-goals (this version)

- Clothing sellers' page types (product, price, catalogue). The kit format must allow them later.
- Reels for courses without a story video (an animated-slides Reel is a later idea).
- Recolouring the 3D icons to each palette; the lesson pages on nerdit.in; the story video frames.

## Anti-goals (fails even if it works)

- Text over a face, cut-off text, a dark page, a repeated look within a brand, a lesson fact or code
  line that differs from the lesson, "free certificate" anywhere, an AI image of a product a buyer
  would receive (future clothing brands use real product photos).

## Constraints

- Renders on the owner's Windows PC with Python + Playwright Chromium (as today). Fonts: installed
  Windows fonts only in v1 (Segoe UI Variable, Bahnschrift with its condensed widths, Consolas).
- NERDIT rules stay enforced: light pages (bg/bg2 luminance >= 0.6), WCAG contrast >= 4.5, lesson
  text word for word on teaching slides, numbers only from the lesson, never claim a free
  certificate, English on screen.
- Every rule has a checker (owner rule). Existing social-posts tests (169) stay green throughout.
- Distribution: `fv-analysis-marketplace` lists plugins by git URL; `brand-studio` becomes a new
  repo there (github.com/futurevisioncomputers/brand-studio-plugin). Nothing is pushed or published
  without the owner's yes.

## Approaches considered

- A. Separate design plugin with brand kits (chosen): reusable across brands and post types; one
  look per course shared by posts and thumbnails; more work up front (draw code moves out).
- B. Grow the social skill only: faster start; a second copy of the look in the video skill drifts.
- C. Design brief for Canva by hand: not the automation the owner wants.

## Design

### Plugin layout

```
brand-studio-plugin/
  .claude-plugin/plugin.json
  skills/brand-studio/SKILL.md          how to render, add photos, refresh looks, add a brand
  engine/brand_studio/                  Python package (pip install -e engine)
    tokens.py   parts.py   pages.py   render.py   checks.py   looks.py   assets.py   cli.py
  brands/nerdit/brand.json  brands/nerdit/looks/*.json  brands/nerdit/logo.png
  brands/futurevision/brand.json  brands/futurevision/looks/*.json  brands/futurevision/logo.png
```

Per-brand runtime data lives outside the repo: `~/.brand-studio/<brand>/history.json` (used
looks) and `~/.brand-studio/<brand>/assets/` (photos, icons, `index.json`). NERDIT's
`~/.nerdit-social/style-history.json` and `~/.nerdit-social/assets/` migrate there once.

### Brand kit (`brand.json`)

Name, handle shown on pages (`Nerdit.in`; Future Vision's handle from the owner), logo file, base
ink colour, accent families the looks may use, allowed fonts, page rules (`light_pages`), banned
phrases (NERDIT: "free certificate"), default call to action and website. NERDIT: navy ink, teal
family first. Future Vision: indigo and red from its logo (split pill, white condensed letters).

### Looks (per brand)

Today's style JSON grows into a look: palette (bg, bg2, panel, ink, muted, accent, highlight,
chip, chipInk, codeBg, codeInk, wave1, wave2), fonts (display, body, condensed, code), motif
(wave, blob, none), and layout family. "Never repeat" is kept per brand, per item, as today
(`pick_looks`, `reserve_looks`, `mark_built`, prune). The learn step (`cli.py refresh <brand>
<refs-folder>`) writes new light looks from reference images (agent-described palette and fonts,
checked by `checks.py`).

### Parts (components)

Python functions returning HTML/CSS with tokens only (no hard-coded colours): brand mark, page
number, headline with highlighted words (highlight box or accent-coloured words), subline, icon
card (icon + text with a highlighted keyword), checklist card, 2x2 tile grid, photo slot (blended:
page colour sampled from the photo, faded inner edges, placed in a reserved column, facing the
text), 3D icon badge, corner wave / blob, course title band, call-to-action bar (arrow circle),
glass panel (code, route list, response, small diagram), and the teaching blocks already built
(guess the output, wrong vs right, data -> code -> result, cheat sheet), restyled.

### Page types (templates)

Each declares its size, its slots with text limits (characters and lines), and two non-overlapping
regions: text and photo. Text never enters the photo region, so a face is never covered.

- Intro series (1080x1350, 6 slides): hook ("Why learn X?"), real questions (3 icon cards),
  what you'll learn (up to 4 lesson titles, word for word), real project (capstone lesson),
  skills (4 cards), call to action (course title band, CTA bar).
- Teaching carousel slides, Story (1080x1920), LinkedIn card (1080x1350): today's kinds in the
  new look.
- Thumbnail (1280x720): condensed capitals title band, student photo, 2-3 glass panels with the
  course's real code (first lesson run block) or lesson titles. Also saved as the course card image.
- Future Vision v1: hook, card list, checklist, call to action, from a brief JSON.

### Assets

`cli.py add-photos <brand> <folder>` takes owner photos (Gemini, 1856x2304 or 16:9), stores a web
copy, and writes `index.json` entries: file, aspect, background colour (sampled), facing (agent sets
from the prompt sheet: left/right/front), pose tags, outfit colour, source, and `used_by`. A photo
is not reused within a course; across courses the least-used matching photo wins. Icons: Fluent
Emoji 3D (MIT, licence file kept) tagged by name. The Gemini sparkle mark is left as it is.

### Checks (`checks.py`)

Light page and contrast (moved from stylebook), allowed fonts, text fits its slot (measured in the
browser, as `FIT_JS` does today), text and photo regions do not overlap, banned phrases, every
page lists its source text so NERDIT's word-for-word checker keeps working.

### NERDIT integration

- `nerdit-social-posts` imports `brand_studio` (clear error if it is not installed); `draw.py`
  keeps only Reel overlays and calls pages for everything else.
- The course video is optional: without `images/video/clips.json` the plan has no Reels, and the
  source reads only the course JSON (exported from the admin: Data manager, View all courses,
  Export JSON).
- New plan item `intro` (carousel) on day 1 of a course's first pack; the agent writes the hook,
  questions and skills; lesson titles and the project come from the course JSON and are checked
  word for word; numbers only from the lessons.
- `nerdit-story-video` thumbnail uses the thumbnail page with the course's look (replaces the dark
  navy THUMB_CSS); the owner's photo stays an option for a photo slot.

### Pilot

- Supervised Learning Classification (`AIgd1ujytssUEyy58l6J`, 9 lessons, no description, no image)
  and Data Cleaning and Pre-processing (`yYKKWGgZQzusXse04p1D`, 10 lessons): owner exports both
  JSONs to `design-pilot\`. For each: the intro series, one teaching carousel, one Story, one
  LinkedIn card, the thumbnail / course image. Future Vision: one 4-slide admissions set from a
  brief the owner supplies (courses, batch times, address, phone).
- Owner checks the pilot before any full pack (pilot-first rule).

## Decisions after the builder check (my calls unless marked owner)

1. **No-video courses.** `intro` is a plan item of format `carousel` (marker `"kind": "intro"` in the
   plan only), so `pack.json`, the server and the admin import are unchanged. Without
   `clips.json` the day plan simply has no Reel items: the 19:00 slot stays empty; Stories,
   carousels and LinkedIn cards keep their days. The intro takes day 1's carousel slot.
2. **Tests.** Contract tests stay unchanged (word-for-word, fit, captions, dayplan, history, pack
   checks, cues, reel command). Render-level tests that assert today's HTML or layout names may be
   rewritten against the new parts; `draw.py` keeps its public functions as thin adapters during the
   move, so callers change one at a time.
3. **Old styles.** The 13 light styles become NERDIT looks (palettes and fonts); retired dark ones stay
   retired; looks from the references are added by `refresh`. The old layout families (stack, split,
   bleed, editorial, bignumber) become page-type variants (item 4).
4. **Variety.** A look = palette + fonts + motif + variant. Every page type ships with at least two
   arrangement variants (for example photo right or left, cards as a list or a 2x2 grid, wave corner
   bottom-right or top-left). `pick_looks` balances variants as it balances layouts today.
5. **Photo and page colour.** On a page with a photo, the page background is the colour sampled from
   that photo (which must pass the light-page check); the look's accent, ink and motif still apply.
   Photo-less pages use the look's `bg`/`bg2`. `cli.py prompts <brand>` writes the Gemini prompt sheet
   for missing pose/outfit/facing combinations, always asking for a plain light grey background (as
   `C:\Users\siddh\.nerdit-social\assets\gemini-test\PROMPTS.md` does).
6. **No photo yet.** Every page type has a photo-less variant (the photo region holds a large 3D icon
   with a blob and badge). The pilot runs with the four photos already made plus this fallback.
7. **Future Vision truth rules (owner).** The brief is the source: every number and fact on a banner
   must appear in it. Banned phrases: NERDIT's list plus whatever the owner names. The logo is shown
   as an image on a white chip, never recoloured.
8. **Reel overlays** take the course's look tokens from `brand_studio` (light only); the Reel frame
   layout stays as today. The five old themes remain only as a fallback for old plans.
9. **Development.** `brand-studio-plugin/` is a sibling folder in this workspace with its own local git
   repo; nothing is pushed until the owner says so. The engine is installed with `pip install -e`
   into the Python the tests and hooks use (system Python 3.14). The NERDIT skills state the
   dependency in SKILL.md and stop with an install hint when it is missing.
10. **Thumbnail content.** The first lesson's first run block when its code is at most 7 lines;
    otherwise the first three lesson titles as a list panel; plus one panel with the course's
    first key idea.

## Left to the builder

Exact token values per look, slot limits per page type, module boundaries inside the engine, how
the migration of existing styles and history is staged, test layout.
