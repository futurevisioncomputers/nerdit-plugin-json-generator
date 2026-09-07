# FIGURE TEMPLATES — the deterministic SVG set

Authority for the markup of every teaching figure. `CORE.md` §7 decides **whether** a
lesson gets a figure and **which shape** it is; this file supplies the exact SVG for that
shape. Copy a template, swap the labels, ship it.

**Why templates instead of improvising an SVG per lesson.** An improvised diagram varies
in stroke weight, corner radius, font size and padding from one lesson to the next, so a
course reads as eight different hands. It also drifts off the token palette the moment a
hex feels convenient. Nine fixed shapes cover the concept structures a lesson actually
has; picking one is a decision, drawing one is not.

---

## Rules that hold for every template

1. **Tokens only, never hex.** Every `fill` and `stroke` is a `var(--token)` from
   `CORE.md` §7b. `verify_course.py` fails the build on a hex literal inside a lesson SVG.
2. **Give every shape an explicit fill.** An unfilled shape inherits black and vanishes on
   a dark ground.
3. **Always wrapped**, always captioned:
   ```html
   <div class="nerdit-figure">
     <svg viewBox="0 0 640 200" role="img" aria-label="…">…</svg>
     <div class="nerdit-figure-caption">…</div>
   </div>
   ```
4. **`viewBox` yes, `width`/`height` no.** `.nerdit-figure svg` is already
   `width:100%; height:auto`. A fixed `width` attribute fights it.
5. **`role="img"` + `aria-label`** describing what the figure *teaches*, not what it
   depicts. "INNER JOIN keeps only rows present in both tables", not "Venn diagram".
6. **The caption carries the lesson.** A reader who skips the picture must still get the
   point from the caption alone.
7. **Text stays text.** No `<path>`-outlined glyphs — outlined text cannot re-theme.
8. Use the css8 flow classes where they fit — `nerdit-flow-rect`, `nerdit-flow-text`,
   `nerdit-flow-edge` — rather than restating their fill/stroke inline.

Two colours carry meaning across every template and must not be swapped:
`var(--orange)` = **what the learner does**, `var(--green)` = **what they get back**.

---

## 1 · Sequence — a pipeline, in order

For: a query travelling app → server → DB, an ETL path, a request lifecycle.

```html
<div class="nerdit-figure">
  <svg viewBox="0 0 640 90" role="img" aria-label="A query passes through the parser, then the planner, then the executor, before rows come back.">
    <rect class="nerdit-flow-rect" x="8"   y="22" width="130" height="46"/>
    <text class="nerdit-flow-text" x="73"  y="50" text-anchor="middle">Parser</text>
    <rect class="nerdit-flow-rect" x="178" y="22" width="130" height="46"/>
    <text class="nerdit-flow-text" x="243" y="50" text-anchor="middle">Planner</text>
    <rect class="nerdit-flow-rect" x="348" y="22" width="130" height="46"/>
    <text class="nerdit-flow-text" x="413" y="50" text-anchor="middle">Executor</text>
    <rect x="518" y="22" width="114" height="46" rx="10" fill="var(--white)" stroke="var(--green)" stroke-width="1.5"/>
    <text class="nerdit-flow-text" x="575" y="50" text-anchor="middle" fill="var(--green)">Rows</text>
    <path class="nerdit-flow-edge" d="M138 45 H178" marker-end="url(#fig-arrow)"/>
    <path class="nerdit-flow-edge" d="M308 45 H348" marker-end="url(#fig-arrow)"/>
    <path class="nerdit-flow-edge" d="M478 45 H518" marker-end="url(#fig-arrow)"/>
    <defs>
      <marker id="fig-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" fill="var(--nb-mid)"/>
      </marker>
    </defs>
  </svg>
  <div class="nerdit-figure-caption">The planner decides <em>how</em> to get the rows; the executor goes and gets them.</div>
</div>
```

> `<marker>` ids are document-global and a lesson page holds several figures. Suffix the
> id per figure — `fig-arrow-joins`, `fig-arrow-pipeline` — or `verify_course.py` reports
> a duplicate-id failure.

---

## 2 · Two sets overlapping — a Venn

For: INNER vs LEFT JOIN, union vs intersection, "which rows survive".

```html
<div class="nerdit-figure">
  <svg viewBox="0 0 420 180" role="img" aria-label="INNER JOIN returns only the customers that appear in both tables; rows unique to either side are dropped.">
    <circle cx="160" cy="90" r="70" fill="var(--bg-soft)" stroke="var(--nb)" stroke-width="1.5"/>
    <circle cx="260" cy="90" r="70" fill="var(--bg-soft)" stroke="var(--nb)" stroke-width="1.5"/>
    <path d="M210 32 A70 70 0 0 1 210 148 A70 70 0 0 1 210 32 z" fill="var(--green)" fill-opacity="0.30" stroke="var(--green)" stroke-width="1.5"/>
    <text class="nerdit-flow-text" x="118" y="95" text-anchor="middle" fill="var(--tx-m)">customers</text>
    <text class="nerdit-flow-text" x="302" y="95" text-anchor="middle" fill="var(--tx-m)">orders</text>
    <text class="nerdit-flow-text" x="210" y="95" text-anchor="middle" fill="var(--green)">both</text>
  </svg>
  <div class="nerdit-figure-caption">INNER JOIN keeps only the shaded overlap — a customer with no order disappears.</div>
</div>
```

---

## 3 · Comparison — two options on fixed criteria

For: list vs tuple, INNER vs LEFT, `.loc` vs `.iloc`, VLOOKUP vs XLOOKUP.
The single most reusable shape: most "plain concepts" are really a comparison.

```html
<div class="nerdit-figure">
  <svg viewBox="0 0 640 172" role="img" aria-label="A list can be changed after creation and is written with square brackets; a tuple cannot be changed and is written with parentheses.">
    <rect x="8"   y="8" width="304" height="156" rx="10" fill="var(--bg-soft)" stroke="var(--bd)" stroke-width="1"/>
    <rect x="328" y="8" width="304" height="156" rx="10" fill="var(--bg-soft)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="160" y="36" text-anchor="middle" fill="var(--nb)">list</text>
    <text class="nerdit-flow-text" x="480" y="36" text-anchor="middle" fill="var(--nb)">tuple</text>
    <line x1="24" y1="50" x2="296" y2="50" stroke="var(--bd-soft)" stroke-width="1"/>
    <line x1="344" y1="50" x2="616" y2="50" stroke="var(--bd-soft)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="24"  y="78"  fill="var(--tx-m)">written</text>
    <text class="nerdit-flow-text" x="24"  y="108" fill="var(--tx-m)">changeable</text>
    <text class="nerdit-flow-text" x="24"  y="138" fill="var(--tx-m)">use when</text>
    <text class="nerdit-flow-text" x="296" y="78"  text-anchor="end" fill="var(--tx)">[1, 2, 3]</text>
    <text class="nerdit-flow-text" x="296" y="108" text-anchor="end" fill="var(--green)">yes</text>
    <text class="nerdit-flow-text" x="296" y="138" text-anchor="end" fill="var(--tx)">it will grow</text>
    <text class="nerdit-flow-text" x="616" y="78"  text-anchor="end" fill="var(--tx)">(1, 2, 3)</text>
    <text class="nerdit-flow-text" x="616" y="108" text-anchor="end" fill="var(--orange)">no</text>
    <text class="nerdit-flow-text" x="616" y="138" text-anchor="end" fill="var(--tx)">it must not</text>
  </svg>
  <div class="nerdit-figure-caption">Same three questions asked of both — the answer to "changeable" is the whole difference.</div>
</div>
```

Keep the criteria rows identical on both sides. A comparison that asks different questions
of each side is not a comparison.

---

## 4 · Before / after — one transformation

For: a de-duplicate, a filter, a pivot, a sort, a rename.

```html
<div class="nerdit-figure">
  <svg viewBox="0 0 640 168" role="img" aria-label="drop_duplicates removes the second Mumbai row, taking five rows down to four.">
    <text class="nerdit-flow-text" x="120" y="22" text-anchor="middle" fill="var(--tx-m)">before — 5 rows</text>
    <rect x="30" y="34" width="180" height="112" rx="8" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <line x1="30" y1="62" x2="210" y2="62" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="120" y="54"  text-anchor="middle" fill="var(--tx-m)">city</text>
    <text class="nerdit-flow-text" x="120" y="82"  text-anchor="middle" fill="var(--tx)">Mumbai</text>
    <text class="nerdit-flow-text" x="120" y="106" text-anchor="middle" fill="var(--orange)">Mumbai</text>
    <text class="nerdit-flow-text" x="120" y="130" text-anchor="middle" fill="var(--tx)">Pune</text>

    <path class="nerdit-flow-edge" d="M232 90 H298" marker-end="url(#fig-arrow-dedupe)"/>
    <text class="nerdit-flow-text" x="265" y="78" text-anchor="middle" fill="var(--nb)">drop_duplicates()</text>

    <text class="nerdit-flow-text" x="430" y="22" text-anchor="middle" fill="var(--tx-m)">after — 4 rows</text>
    <rect x="340" y="34" width="180" height="112" rx="8" fill="var(--white)" stroke="var(--green)" stroke-width="1.5"/>
    <line x1="340" y1="62" x2="520" y2="62" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="430" y="54"  text-anchor="middle" fill="var(--tx-m)">city</text>
    <text class="nerdit-flow-text" x="430" y="82"  text-anchor="middle" fill="var(--tx)">Mumbai</text>
    <text class="nerdit-flow-text" x="430" y="106" text-anchor="middle" fill="var(--tx)">Pune</text>
    <defs>
      <marker id="fig-arrow-dedupe" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" fill="var(--nb-mid)"/>
      </marker>
    </defs>
  </svg>
  <div class="nerdit-figure-caption">Clay marks the row that goes; the operation label sits on the arrow that removes it.</div>
</div>
```

Mark the changed thing in `var(--orange)` on the left and let the right side be plain —
the eye then finds the difference without reading a word.

---

## 5 · Decision — a branch with named outcomes

For: which join to reach for, which chart type, when a formula returns `#N/A`.

```html
<div class="nerdit-figure">
  <svg viewBox="0 0 560 190" role="img" aria-label="If unmatched rows still matter, use a LEFT JOIN; if they do not, use an INNER JOIN.">
    <path d="M280 12 L392 62 L280 112 L168 62 z" fill="var(--bg-soft)" stroke="var(--nb)" stroke-width="1.5"/>
    <text class="nerdit-flow-text" x="280" y="58" text-anchor="middle">Keep unmatched</text>
    <text class="nerdit-flow-text" x="280" y="78" text-anchor="middle">rows?</text>
    <path class="nerdit-flow-edge" d="M168 62 H96 V140" marker-end="url(#fig-arrow-join)"/>
    <path class="nerdit-flow-edge" d="M392 62 H464 V140" marker-end="url(#fig-arrow-join)"/>
    <text class="nerdit-flow-text" x="126" y="52" fill="var(--green)">yes</text>
    <text class="nerdit-flow-text" x="404" y="52" fill="var(--orange)">no</text>
    <rect x="20"  y="144" width="152" height="40" rx="8" fill="var(--white)" stroke="var(--green)" stroke-width="1.5"/>
    <text class="nerdit-flow-text" x="96"  y="169" text-anchor="middle" fill="var(--green)">LEFT JOIN</text>
    <rect x="388" y="144" width="152" height="40" rx="8" fill="var(--white)" stroke="var(--orange)" stroke-width="1.5"/>
    <text class="nerdit-flow-text" x="464" y="169" text-anchor="middle" fill="var(--orange)">INNER JOIN</text>
    <defs>
      <marker id="fig-arrow-join" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" fill="var(--nb-mid)"/>
      </marker>
    </defs>
  </svg>
  <div class="nerdit-figure-caption">One question decides it — everything else about the two joins follows from the answer.</div>
</div>
```

One question, two outcomes. A third branch means the question is wrong; split it.

---

## 6 · Anatomy — the parts of one thing, labelled

For: a SELECT statement, a function signature, a formula, a file path, a URL.

```html
<div class="nerdit-figure">
  <svg viewBox="0 0 640 132" role="img" aria-label="In VLOOKUP, the first argument is the value to find, the second is the table to search, the third is which column to return.">
    <text x="24" y="52" font-family="var(--font-code)" font-size="17" fill="var(--tx)">=VLOOKUP(</text>
    <text x="126" y="52" font-family="var(--font-code)" font-size="17" fill="var(--orange)">E2</text>
    <text x="152" y="52" font-family="var(--font-code)" font-size="17" fill="var(--tx)">,</text>
    <text x="168" y="52" font-family="var(--font-code)" font-size="17" fill="var(--nb)">A:C</text>
    <text x="208" y="52" font-family="var(--font-code)" font-size="17" fill="var(--tx)">,</text>
    <text x="224" y="52" font-family="var(--font-code)" font-size="17" fill="var(--green)">3</text>
    <text x="238" y="52" font-family="var(--font-code)" font-size="17" fill="var(--tx)">)</text>
    <path d="M133 62 V88 H92" stroke="var(--orange)" stroke-width="1.4" fill="none"/>
    <text class="nerdit-flow-text" x="86" y="92" text-anchor="end" fill="var(--orange)">what to find</text>
    <path d="M186 62 V108 H236" stroke="var(--nb)" stroke-width="1.4" fill="none"/>
    <text class="nerdit-flow-text" x="242" y="112" fill="var(--nb)">where to look</text>
    <path d="M230 62 V88 H286" stroke="var(--green)" stroke-width="1.4" fill="none"/>
    <text class="nerdit-flow-text" x="292" y="92" fill="var(--green)">which column comes back</text>
  </svg>
  <div class="nerdit-figure-caption">Read it as a sentence: find <em>E2</em> inside <em>A:C</em>, return column <em>3</em>.</div>
</div>
```

Label at most four parts. A fifth leader line crosses another and the figure stops being
readable — split the anatomy across two figures instead.

---

## 7 · Part / whole — what contains what

For: a workbook holding sheets holding cells, a database → table → row, scope nesting.

```html
<div class="nerdit-figure">
  <svg viewBox="0 0 480 168" role="img" aria-label="A workbook contains worksheets, and each worksheet contains cells.">
    <rect x="12" y="12" width="456" height="144" rx="10" fill="var(--bg-soft)" stroke="var(--nb)" stroke-width="1.5"/>
    <text class="nerdit-flow-text" x="28" y="36" fill="var(--nb)">Workbook — the .xlsx file</text>
    <rect x="32" y="50" width="416" height="92" rx="8" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="48" y="74" fill="var(--tx-m)">Worksheet — one tab</text>
    <rect x="52" y="88" width="376" height="40" rx="6" fill="var(--bg-soft)" stroke="var(--bd-soft)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="68" y="113" fill="var(--tx)">Cell — one box, addressed E2</text>
  </svg>
  <div class="nerdit-figure-caption">Three levels, outermost first — every address like <em>E2</em> is read inside a sheet, inside a file.</div>
</div>
```

Three levels maximum. Deeper is a tree (§8), not a nesting.

---

## 8 · Hierarchy — a tree

For: a folder tree, a DOM, an inheritance chain, a decision tree's shape.

```html
<div class="nerdit-figure">
  <svg viewBox="0 0 520 176" role="img" aria-label="The project folder holds a data folder and a notebooks folder; the data folder holds two CSV files.">
    <rect x="188" y="8" width="144" height="36" rx="8" fill="var(--bg-soft)" stroke="var(--nb)" stroke-width="1.5"/>
    <text class="nerdit-flow-text" x="260" y="31" text-anchor="middle">project/</text>
    <path class="nerdit-flow-edge" d="M260 44 V62 H120 V78"/>
    <path class="nerdit-flow-edge" d="M260 44 V62 H400 V78"/>
    <rect x="48"  y="80" width="144" height="34" rx="8" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="120" y="102" text-anchor="middle">data/</text>
    <rect x="328" y="80" width="144" height="34" rx="8" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="400" y="102" text-anchor="middle">notebooks/</text>
    <path class="nerdit-flow-edge" d="M120 114 V130 H64 V142"/>
    <path class="nerdit-flow-edge" d="M120 114 V130 H176 V142"/>
    <rect x="8"   y="144" width="112" height="30" rx="6" fill="var(--white)" stroke="var(--bd-soft)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="64"  y="164" text-anchor="middle" fill="var(--tx-m)">sales.csv</text>
    <rect x="120" y="144" width="112" height="30" rx="6" fill="var(--white)" stroke="var(--bd-soft)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="176" y="164" text-anchor="middle" fill="var(--tx-m)">cities.csv</text>
  </svg>
  <div class="nerdit-figure-caption">A relative path is read by walking down from the folder you started in.</div>
</div>
```

---

## 9 · Real measured numbers — Chart.js

Only when the comparison itself teaches: indexed vs full-scan query time, memory by dtype.
Not for illustrating a definition. Use the v8 `nerdit-chart-wrap` markup, read colours from
tokens per §7b, and never invent the numbers — they come from a run the lesson shows.

If the numbers came out of Matplotlib inside the lesson, that is an **output**, not a
figure: it belongs in the run line, and `tokenize_chart_svg.py` handles its colours.

---

## Choosing between them

Work down this list and stop at the first match:

| The concept is… | Template |
|---|---|
| an ordered path through stages | 1 · Sequence |
| membership — what is in, what is out | 2 · Venn |
| two options a learner picks between | 3 · Comparison |
| one operation changing data | 4 · Before / after |
| a rule for choosing | 5 · Decision |
| one artifact whose parts need naming | 6 · Anatomy |
| containers inside containers, ≤3 deep | 7 · Part / whole |
| a branching structure, >3 deep | 8 · Tree |
| measured numbers worth comparing | 9 · Chart.js |

Nothing matches and the concept still needs a picture? It usually means the concept has
not been pinned down yet. Write the caption first — the one sentence the figure must
teach. If that sentence will not come, there is no figure to draw, and §7's fallback
applies: **prose is the correct answer, and an empty figure slot is better than a
decorative one.**
