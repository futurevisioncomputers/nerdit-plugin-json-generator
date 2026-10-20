# House style for NERDIT lesson illustrations

`manifest.py` appends the block between the `style` fences to every prompt. Edit the style here
and nowhere else. `{text_clause}` is filled in per image: the slot's exact labels and its
numbered markers, or no text at all. Diagrams never use this block; they are SVG.

```style
Style: clean flat educational illustration, simple shapes, soft shadows, plain light background, one idea per picture, plenty of empty space.
Colours: navy #0B1F3A, teal #14B8A6, light background #EEF3F9 and white, with at most one warm highlight colour.
Format: landscape 4:3 unless the scene needs another shape. Any label or marker is large, bold and readable on a phone screen.
Text: {text_clause}
No logos, screenshots, user-interface elements or watermarks.
People, if any: Indian people in Indian settings. No real brands, companies or celebrities.
```

Simple app screens (kind `screen`, briefed by the chapter generator's `visual_briefs.py` from
a lesson's screen spec) use the block between the `screen-style` fences instead. `{app}` is the
app the lesson names. A screen looks like its own app, in that app's colours, so a learner
recognises it; the house colours above do not apply to it.

```screen-style
Style: a clean, realistic {app} screen in {app}'s own usual colours and theme, cropped to the working area only: the menu, tab or panel in use and the content the steps touch. No title bar, no window controls, no taskbar, no browser chrome.
Format: 4:3 or 3:4, sized so every label is readable on a phone screen; text large and bold where it matters.
Text: {text_clause}
Markers: numbered circles ① to ⑤, one per step, next to the parts named in the steps, in order.
No logos, no brand marks, no watermarks, no extra values, names or menu items beyond the listed text.
```

## Choosing a visual

`nerdit-chapter-generator/references/CORE.md` §7 (the Visual Map) decides which visual each
place in a lesson gets. Illustrations are only for a real scene or an analogy the text already
uses. Everything with exact names, values or times is a diagram or table drawn from the
lesson's data (figures.md templates 1–15), with `data-visual` set; a plan item may name it in
`visual`. When the course workdir has concept manifests, `extract_outline.py --hints <workdir>`
shows each section's planned `visual` and suggested `illustration`; plan from those.

- **Process illustrations** (kind `process`): an AI-drawn picture of a process or data flow
  (rows being split, folds rotating, a pipeline filling gaps then predicting) when a drawn
  scene explains the flow better than boxes and arrows. It carries only the markers ① ② ③
  that match its 2–3 reading steps: no words, letters or numbers, and its subject names no
  values. It replaces the diagram for that section (`manifest.py` refuses both), so the exact
  values must already be in the section's text, run output or an existing table.
- **Teach, don't decorate.** Every prompt states the takeaway the picture must make obvious and
  the misconception it must not suggest. When the misconception is the lesson (a leaky refit,
  a wrong unit), use `"layout": "contrast"`: the mistake on the left marked ✗, the correct way
  on the right marked ✓.
- **Use the course's own objects.** Set plan-level `props` from the world file (its products,
  vessels, categories, record types), so every scene shows the things the learner's data
  describes, not generic office props.
- **Same people every time.** Set plan-level `characters` [{name, look}] from the world's cast.
  `PROMPTS.md` then lists one character sheet per person to generate first, and every prompt
  that names them says which sheet to attach in Codex.
- **Place by job.** A scene that sets up the problem goes before the concept
  (`after-explanation` on the section's first paragraph); a process picture goes
  `before-code`, just ahead of the first code block that does it.
- **Animate only a sequence or a change** (`"animated": true` on a diagram, figures.md
  template 18): a split, folds taking turns, a pipeline, records matched or removed. At most two
  per course, on the hardest step-by-step ideas. Definitions, values, comparisons and scenes
  stay still. The finished frame must teach without the motion.
- One objective per visual; split a crowded figure into two.
- Diagrams use the lesson's own names, keys, dates and amounts — never invented ones.
- No quota: add a visual only where it helps; an existing accurate figure may already do the job.
- The intro sentence, caption, reading steps and check question are written for a student
  meeting the topic for the first time.

## Visual check criteria

PASS only when all hold:

1. It answers the brief's question and shows the takeaway; the caption is true of it.
2. Every label, value and name matches the section or its fixture.
3. Markers ① ② ③ sit on the parts the reading steps describe, in the same order.
4. Labels are readable on the phone-size preview.
5. Process illustrations: the flow reads in marker order ① ② ③, each marker sits on its step,
   and nothing else is written — no words, numbers or chart values.
6. Illustrations: no extra text, numbers, logos or brands; Indian context where people appear;
   the course's recurring cast when one is set.
7. Nothing contradicts the lesson or invites the brief's stated misconception.
8. A learner who skips the text gets the takeaway from the picture and its caption alone.
9. The objects and people are the course's own: the world's products and records, and each
   character matches their sheet.

## Screen check criteria

A `screen` image passes only when all hold:

1. Every listed label and value appears exactly as written.
2. Nothing else is written: no extra rows, values, names or menu items.
3. Markers ① ② ③ sit on the parts the reading steps name, in order.
4. It looks like the named app in that app's own colours, and every label is readable on the
   phone-size preview.
5. No logo or brand mark.
