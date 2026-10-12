# House style for NERDIT lesson illustrations

`manifest.py` appends the block between the `style` fences to every prompt. Edit the style here
and nowhere else. `{labels_clause}` is filled in per image.

```style
Style: clean flat educational illustration, simple shapes, soft shadows, plain light background, one idea per picture, plenty of empty space.
Colours: navy #0B1F3A, teal #14B8A6, light background #EEF3F9 and white, with at most one warm highlight colour.
Format: landscape 4:3 unless the scene needs another shape. Any label or marker is large, bold and readable on a phone screen.
Text: {text_clause}
No logos, screenshots, user-interface elements or watermarks.
People, if any: Indian people in Indian settings. No real brands, companies or celebrities.
```

## Planning rules

- Consider numbered teaching sections only (`[teach]` in the outline). Never the opening,
  practice blocks, the cheat sheet or the quiz.
- Every slot needs a one-line teaching `reason`. A section qualifies when it introduces an
  abstract idea a concrete picture makes memorable, describes a real-world process or scene, or
  opens the lesson and benefits from a hook (section 1).
- Skip a section when a figure caption in the outline already teaches the same idea, when the
  section is pure syntax or calculation, or when the picture would need exact numbers or text.
- 0 to 3 images per lesson; a lesson marked `[NO VISUAL]` gets at least 1; project and capstone
  lessons get 1 scene. Drop any slot without a clear reason.
- `subject`: the objects or metaphor to draw from this section, the composition (left to right
  for a process) and the focal point. Never ask for text, numbers, charts or tables.
- `labels`: at most 3 one-word labels, only when the idea needs them, spelled exactly.
- `alt`: what the picture shows, 125 characters or less.
- `caption`: the teaching point in one sentence of at most 15 words, in the lesson's terms.
- `position`: `after-explanation` with an `anchor` copied exactly from a `¶` line of that section,
  or `before-practice` (anchor empty).

## Visual check criteria

Judge each preview against its slot's reason, prompt and caption. PASS only when all hold:

1. It shows what the reason says the section needs, so the caption is true of the picture.
2. No garbled or extra text; any labels match the slot's `labels` exactly.
3. No numbers, logos, real brands or watermarks.
4. Brand palette, and an Indian context where people appear.
5. Nothing contradicts the lesson's terms or facts.
