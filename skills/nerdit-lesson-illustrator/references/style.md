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
5. Illustrations: no extra text, numbers, logos or brands; Indian context where people appear;
   the course's recurring cast when one is set.
6. Nothing contradicts the lesson or invites the brief's stated misconception.

## Screen check criteria

A `screen` image passes only when all hold:

1. Every listed label and value appears exactly as written.
2. Nothing else is written: no extra rows, values, names or menu items.
3. Markers ① ② ③ sit on the parts the reading steps name, in order.
4. It looks like the named app in that app's own colours, and every label is readable on the
   phone-size preview.
5. No logo or brand mark.
