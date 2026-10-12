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

## Choosing a visual

| Learner question | Kind | Must show |
|---|---|---|
| Where does a record go? | diagram (sequence) | each layer and its responsibility |
| What happens first? | diagram (two aligned flows) | the steps in their real order |
| How are tables related? | diagram (key match, template 10) | exact table/column names, the matching keys, one record |
| What changed? | diagram (before/after) | input, rule, output rows |
| Which date or period applies? | diagram (timeline) | exact timestamps, offset, boundaries |
| Why is this unsafe to sum? | diagram or small table | grain, units, the repeated value |
| Who does what? | illustration | the actors and actions, mapped to the lesson in the steps |

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
