# FIGURE TEMPLATES — the deterministic SVG set

Authority for the markup of every teaching figure. `CORE.md` §7 decides **whether** a
lesson gets a figure and **which shape** it is; this file supplies the exact SVG for that
shape. Copy a template, swap the labels, ship it.

**Why templates instead of improvising an SVG per lesson.** An improvised diagram varies
in stroke weight, corner radius, font size and padding from one lesson to the next, so a
course reads as eight different hands. It also drifts off the token palette the moment a
hex feels convenient. Fifteen fixed shapes cover the concept structures a lesson actually
has; picking one is a decision, drawing one is not. Templates 16 (app screens) and 17 (scenes)
are specs, not SVG: the plugin draws or briefs them from the lesson's own words.

---

## Rules that hold for every template

1. **Tokens only, never hex.** Every `fill` and `stroke` is a `var(--token)` from
   `CORE.md` §7b. `verify_course.py` fails the build on a hex literal inside a lesson SVG.
   Tokens resolve to the brand v2 palette through `css10-brand.css`, so figures pick up
   the new palette without any hex. Figures must remain readable on white; never bake
   `#fffbf3` or use brown tints.
2. **Give every shape an explicit fill.** An unfilled shape inherits black and vanishes on
   a dark ground.
3. **Always wrapped**, always captioned:
   ```html
   <div class="nerdit-figure" data-visual="diagram">
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
9. **Readable on a phone.** A phone column is about 314 px wide and figure text is about
   14.7 units, so a 640-wide `viewBox` shrinks every label to about 7 px. New figures use a
   `viewBox` at most 400 wide — stack the parts vertically — and put
   `style="max-width:440px"` on the `nerdit-figure` wrapper so desktop does not blow them up.
   Templates 1–9 below are drawn 640 wide: restack them to fit before use. Template 10 shows a
   stacked layout.

10. **Columns go in a table (R10).** A record with more than one field — `row 1`, `09:00`,
    `10000` — is a row of a value table (template 11), never an SVG label joined with `·`.
    `verify_course.py --contract v11` fails a label that packs a row into dots. SVG stays for
    shapes that carry meaning: flows, overlaps, time scales, key matches.
11. **Make invisible values visible (R11).** A raw string sits in `<span class="nerdit-val">`,
    which marks where it starts and ends. Each space is `<span class="nerdit-ws">␣</span>`.
    NULL is `<span class="nerdit-null">NULL</span>`. Never use square brackets to show spaces in
    a figure (an SQL result may, because that is real output).
12. **Highlight the surprise (R12).** The cell that springs the trap gets `nerdit-cell-bad`; the
    safe result gets `nerdit-cell-good`. Each carries a 2–4 word `<span class="nerdit-vnote">`
    saying what happened. Colour one cell, not the whole row.
13. **Show each idea once (R13).** In one section, a text map (`nerdit-map`), a figure and its
    reading steps never restate the same facts. Steps add order or reasons, not the figure's
    labels again. When a figure covers it, drop the map.
14. **Every figure names its visual.** `data-visual` on each `nerdit-figure`: `diagram`,
    `value-table`, `decision-grid`, `time-window`, `unit-tiles`, `chart`, `course-map` or
    `illustration`. `CORE.md` §7 decides which; v11 fails a figure without it.
15. **Spotlight one record.** The record the lesson follows carries `nerdit-spot` (a table row,
    a cell or an SVG shape) in every figure where it appears.

**Icons in tables — closed list:** `✓` passes · `✗` fails · `–` not checked · `⚠` needs
attention · `🔑` primary key · `🔗` foreign key. A table that uses one carries a legend
(`nerdit-vlegend`) or says it in text. No other icons, the same rule as heading emoji.

Two colours carry meaning across every template and must not be swapped:
`var(--orange)` = **what the learner does**, `var(--green)` = **what they get back**.

---

## 1 · Sequence — a pipeline, in order

For: a query travelling app → server → DB, an ETL path, a request lifecycle.

```html
<div class="nerdit-figure" data-visual="diagram">
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
<div class="nerdit-figure" data-visual="diagram">
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
<div class="nerdit-figure" data-visual="diagram">
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
<div class="nerdit-figure" data-visual="diagram">
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
<div class="nerdit-figure" data-visual="diagram">
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
<div class="nerdit-figure" data-visual="diagram">
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
<div class="nerdit-figure" data-visual="diagram">
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
<div class="nerdit-figure" data-visual="diagram">
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

## 10 · Key match — follow one record through its keys

For: a fact row and its dimensions, a foreign key to its parent, an order line to its product.
Use the lesson's own row and values. Number the parts the reading steps describe.

```html
<div class="nerdit-figure" data-visual="diagram" style="max-width:440px">
  <svg viewBox="0 0 360 300" role="img" aria-label="Sales row O1 line 1 stores amount 200; customer_key 1 finds Aarav in Pune and product_key 10 finds Book.">
    <rect x="80" y="10" width="200" height="136" rx="8" fill="var(--bg-soft)" stroke="var(--nb)"/>
    <text class="nerdit-flow-text" x="180" y="34" text-anchor="middle" fill="var(--nb)">fact_sales</text>
    <text class="nerdit-flow-text" x="94" y="60" fill="var(--tx)">order O1, line 1</text>
    <text class="nerdit-flow-text" x="94" y="84" fill="var(--green)">① amount = 200</text>
    <text class="nerdit-flow-text" x="94" y="108" fill="var(--orange)">② customer_key = 1</text>
    <text class="nerdit-flow-text" x="94" y="132" fill="var(--orange)">③ product_key = 10</text>
    <rect x="5" y="200" width="170" height="90" rx="8" fill="var(--white)" stroke="var(--nb)"/>
    <text class="nerdit-flow-text" x="90" y="224" text-anchor="middle" fill="var(--nb)">dim_customer</text>
    <text class="nerdit-flow-text" x="17" y="250" fill="var(--orange)">customer_key = 1</text>
    <text class="nerdit-flow-text" x="17" y="274" fill="var(--tx)">Aarav, Pune</text>
    <rect x="185" y="200" width="170" height="90" rx="8" fill="var(--white)" stroke="var(--nb)"/>
    <text class="nerdit-flow-text" x="270" y="224" text-anchor="middle" fill="var(--nb)">dim_product</text>
    <text class="nerdit-flow-text" x="197" y="250" fill="var(--orange)">product_key = 10</text>
    <text class="nerdit-flow-text" x="197" y="274" fill="var(--tx)">Book, Reading</text>
    <path d="M80 103 H50 V200" stroke="var(--orange)" stroke-width="1.6" fill="none"/>
    <path d="M280 127 H310 V200" stroke="var(--orange)" stroke-width="1.6" fill="none"/>
  </svg>
  <div class="nerdit-figure-caption">The sales row stores the amount; matching keys supply customer and product details.</div>
</div>
```

Draw one record, not a table. The reading steps under the figure follow ① ② ③ in order.

---

## 11 · Value table — values before and after a rule

For: TRIM, CAST, NULLIF, date parsing; any rule applied value by value. Variant A groups by
rule, variant B puts two rules side by side to expose a trap, and variant C ranks rows with a kept one.

```html
<div class="nerdit-figure" data-visual="value-table" style="max-width:440px">
  <table class="nerdit-vtable">
    <thead><tr><th>raw value <small>(␣ = space)</small></th><th></th><th>clean value</th></tr></thead>
    <tbody>
      <tr class="nerdit-vgroup"><td colspan="3">① <code>TRIM(customer)</code></td></tr>
      <tr><td><span class="nerdit-val"><span class="nerdit-ws">␣</span>Aarav<span class="nerdit-ws">␣</span></span></td><td class="nerdit-varrow">→</td><td><span class="nerdit-val">Aarav</span></td></tr>
      <tr class="nerdit-vgroup"><td colspan="3">② <code>NULLIF(TRIM(amount_text), '')</code></td></tr>
      <tr><td><span class="nerdit-val"><span class="nerdit-ws">␣</span></span></td><td class="nerdit-varrow">→</td><td><span class="nerdit-null">NULL</span><span class="nerdit-vnote">blank = missing</span></td></tr>
      <tr><td><span class="nerdit-val">0</span></td><td class="nerdit-varrow">→</td><td><span class="nerdit-val">0</span><span class="nerdit-vnote">zero is a real value</span></td></tr>
    </tbody>
  </table>
  <div class="nerdit-figure-caption">Each rule tidies text but keeps its meaning: a blank becomes NULL, and zero stays 0.</div>
</div>
```

```html
<div class="nerdit-figure" data-visual="value-table" style="max-width:440px">
  <table class="nerdit-vtable">
    <thead><tr><th>amount_text</th><th>① <code>CAST(… AS INTEGER)</code></th><th>② digit rule</th></tr></thead>
    <tbody>
      <tr><td><span class="nerdit-val">12500</span></td><td>12500</td><td>12500</td></tr>
      <tr><td><span class="nerdit-val">12x</span></td><td class="nerdit-cell-bad">12<span class="nerdit-vnote">invented, no error</span></td><td class="nerdit-cell-good"><span class="nerdit-null">NULL</span><span class="nerdit-vnote">caught</span></td></tr>
      <tr><td><span class="nerdit-val"><span class="nerdit-ws">␣</span></span></td><td class="nerdit-cell-bad">0<span class="nerdit-vnote">blank became 0</span></td><td class="nerdit-cell-good"><span class="nerdit-null">NULL</span><span class="nerdit-vnote">caught</span></td></tr>
    </tbody>
  </table>
  <div class="nerdit-figure-caption">CAST never complains: 12x becomes 12 and a blank becomes 0. The digit rule refuses both.</div>
</div>
```

```html
<div class="nerdit-figure" data-visual="value-table" style="max-width:440px">
  <p class="nerdit-vtitle">O1's three versions, newest first</p>
  <table class="nerdit-vtable">
    <thead><tr><th>rn</th><th>row_id</th><th>time</th><th>amount</th></tr></thead>
    <tbody>
      <tr class="nerdit-row-kept"><td>1 ✓</td><td>3</td><td>10:00</td><td>12500</td></tr>
      <tr class="nerdit-row-dropped"><td>2</td><td>2</td><td>10:00</td><td>12000</td></tr>
      <tr class="nerdit-row-dropped"><td>3</td><td>1</td><td>09:00</td><td>10000</td></tr>
    </tbody>
  </table>
  <p class="nerdit-vlegend">Rows 3 and 2 tie at 10:00, so the larger row_id goes first. ✓ = kept; grey = superseded.</p>
  <div class="nerdit-figure-caption">The newest version gets number 1, and only rn = 1 is kept.</div>
</div>
```

At most 4 columns and short cell text, so it fits a 280px phone column.

---

## 12 · Decision grid — rules checked per row, first failure wins

For: a CASE that assigns reasons, validation rules, eligibility checks.

```html
<div class="nerdit-figure" data-visual="decision-grid" style="max-width:440px">
  <table class="nerdit-vtable nerdit-grid">
    <thead><tr><th>order</th><th>①</th><th>②</th><th>③</th><th>④</th><th>outcome</th></tr></thead>
    <tbody>
      <tr><td><b>O1</b> <small>row 3</small></td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk ok">✓</td><td class="nerdit-cell-good">ACCEPT</td></tr>
      <tr><td><b>O3</b> <small>row 5</small></td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk first">✗</td><td class="nerdit-chk skip">–</td><td class="nerdit-chk skip">–</td><td class="nerdit-cell-bad">BAD_AMOUNT</td></tr>
      <tr><td><b>O4</b> <small>row 6</small></td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk ok">✓</td><td class="nerdit-chk first">✗</td><td class="nerdit-chk skip">–</td><td class="nerdit-cell-bad">BAD_DATE</td></tr>
      <tr><td><b>O5</b> <small>row 7</small></td><td class="nerdit-chk first">✗</td><td class="nerdit-chk skip">–</td><td class="nerdit-chk skip">–</td><td class="nerdit-chk skip">–</td><td class="nerdit-cell-bad">MISSING_AMOUNT</td></tr>
    </tbody>
  </table>
  <p class="nerdit-vlegend">① amount present · ② amount is digits · ③ date is real · ④ category is approved<br>✓ passes · ✗ first failed check · – not checked</p>
  <div class="nerdit-figure-caption">CASE checks in order and stops at the first ✗. O4 also has an unknown category, but its bad date is found first.</div>
</div>
```

Columns are numbered ①–④ in CASE order, and the legend names them.

---

## 13 · Unit tiles — parts that add up to a total

For: reconciliation, row counts per bin, where every unit lands in exactly one place.

```html
<div class="nerdit-figure" data-visual="unit-tiles" style="max-width:440px">
  <div class="nerdit-tiles">
    <div class="nerdit-tilegroup"><div><span class="nerdit-tile sup">1</span><span class="nerdit-tile sup">2</span></div><span>superseded <b>2</b></span></div>
    <div class="nerdit-tilegroup"><div><span class="nerdit-tile acc">3</span><span class="nerdit-tile acc">4</span></div><span>accepted <b>2</b></span></div>
    <div class="nerdit-tilegroup"><div><span class="nerdit-tile rej">5</span><span class="nerdit-tile rej">6</span><span class="nerdit-tile rej">7</span></div><span>rejected <b>3</b></span></div>
  </div>
  <p class="nerdit-vsum">2 + 2 + 3 = <b>7</b> staged rows</p>
  <div class="nerdit-figure-caption">Each staged row lands in exactly one bin, so the bins add up to the source count.</div>
</div>
```

One tile per real row, up to about 20. Above that, show counts in a value table instead.

---

## 14 · Time window — a range on a clock, drawn to scale

For: watermarks, batch bounds, late data, any `>` / `<=` window on time. ○ marks an excluded bound
and ● an included one. A second lane shows a second clock.

```html
<div class="nerdit-figure" data-visual="time-window" style="max-width:440px">
  <svg viewBox="0 0 360 186" role="img" aria-label="The batch reads changes after 10:00 up to and including 11:00: O3 and O4 load, O6 at 11:30 waits for the next batch, and O2, stamped 10:00 but arrived at 10:20, is never read.">
    <text class="nerdit-flow-text" x="8" y="18" fill="var(--tx-m)">source_updated_at</text>
    <rect x="40" y="46" width="200" height="20" fill="var(--green-bg)"/>
    <line x1="16" y1="56" x2="350" y2="56" stroke="var(--bd)" stroke-width="1.5"/>
    <circle cx="40" cy="56" r="6" fill="var(--white)" stroke="var(--nb)" stroke-width="2"/>
    <circle cx="240" cy="56" r="6" fill="var(--nb)"/>
    <circle cx="140" cy="56" r="4" fill="var(--green)"/>
    <circle cx="190" cy="56" r="4" fill="var(--green)"/>
    <circle cx="340" cy="56" r="4" fill="var(--tx-m)"/>
    <text class="nerdit-flow-text" x="140" y="40" text-anchor="middle" fill="var(--green)">O3</text>
    <text class="nerdit-flow-text" x="190" y="40" text-anchor="middle" fill="var(--green)">O4</text>
    <text class="nerdit-flow-text" x="340" y="40" text-anchor="end" fill="var(--tx-m)">O6</text>
    <text class="nerdit-flow-text" x="40" y="84" text-anchor="middle" fill="var(--tx)">10:00</text>
    <text class="nerdit-flow-text" x="140" y="84" text-anchor="middle" fill="var(--tx-m)">10:30</text>
    <text class="nerdit-flow-text" x="240" y="84" text-anchor="middle" fill="var(--tx)">11:00</text>
    <text class="nerdit-flow-text" x="340" y="84" text-anchor="end" fill="var(--tx-m)">11:30</text>
    <text class="nerdit-flow-text" x="8" y="108" fill="var(--nb)">① ○ 10:00 left out (&gt;)</text>
    <text class="nerdit-flow-text" x="200" y="108" fill="var(--nb)">② ● 11:00 kept (&lt;=)</text>
    <text class="nerdit-flow-text" x="8" y="138" fill="var(--tx-m)">arrived in staging</text>
    <line x1="16" y1="156" x2="350" y2="156" stroke="var(--bd)" stroke-width="1.5"/>
    <line x1="40" y1="146" x2="40" y2="166" stroke="var(--nb)" stroke-width="2"/>
    <circle cx="107" cy="156" r="5" fill="var(--amber)"/>
    <text class="nerdit-flow-text" x="48" y="180" fill="var(--nb)">batch 1 ran</text>
    <text class="nerdit-flow-text" x="122" y="150" fill="var(--amber)">③ O2 arrives 10:20</text>
  </svg>
  <div class="nerdit-figure-caption">A window keeps rows after the watermark up to the frozen upper bound. A row that arrives after its batch ran is never read.</div>
</div>
```

Scale: one hour = 200 units. Place every point by its real time; never space the ticks evenly
by hand.

---

## 15 · Course map — "you are here"

For: the strip under each lesson's overview showing the course's stages. It is drawn once per
course and each lesson fills its own stage. At most 5 stages per row, with names of 8
characters or fewer.

```html
<div class="nerdit-figure" data-visual="course-map" style="max-width:440px">
  <svg viewBox="0 0 360 78" role="img" aria-label="Course map: this lesson is the clean stage, third of five: source, staging, clean, load, mart.">
    <rect x="4" y="14" width="64" height="32" rx="6" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="36" y="35" text-anchor="middle" fill="var(--tx-m)">source</text>
    <rect x="76" y="14" width="64" height="32" rx="6" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="108" y="35" text-anchor="middle" fill="var(--tx-m)">staging</text>
    <rect x="148" y="14" width="64" height="32" rx="6" fill="var(--nb)" stroke="var(--nb)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="180" y="35" text-anchor="middle" fill="var(--white)">clean</text>
    <rect x="220" y="14" width="64" height="32" rx="6" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="252" y="35" text-anchor="middle" fill="var(--tx-m)">load</text>
    <rect x="292" y="14" width="64" height="32" rx="6" fill="var(--white)" stroke="var(--bd)" stroke-width="1"/>
    <text class="nerdit-flow-text" x="324" y="35" text-anchor="middle" fill="var(--tx-m)">mart</text>
    <text class="nerdit-flow-text" x="180" y="68" text-anchor="middle" fill="var(--nb)">▲ you are here</text>
  </svg>
  <div class="nerdit-figure-caption">You are here: cleaning staged rows, before they load into the warehouse.</div>
</div>
```

---

## 16 · Screen walkthrough — a click-path in an app

For: any lesson that teaches the learner to do something in an app, such as Excel, Power BI,
VS Code, a terminal, WordPress, an ads manager or an AI chat tool. Every preset can use it.

**You write a spec, never the picture. Never hand-draw a screen SVG.** Write one JSON block
where the picture goes, right after the paragraph that explains the step:

```html
<script type="application/json" class="nerdit-screen" data-grid="xl-staff">
{"id": "xlookup-city", "app": "Excel", "layout": "sheet",
 "goal": "Find Isha's city with XLOOKUP",
 "view": {"columns": ["B", "D", "H"], "rows": [1, 7], "active": "H3"},
 "steps": [{"do": "select", "target": "H3"},
           {"do": "type", "target": "H3", "text": "=XLOOKUP(\"Isha\",B2:B7,D2:D7)"},
           {"do": "result", "target": "H3"}],
 "image": "auto"}
</script>
```

**Layouts:**

| Layout | Use for | Keys |
|---|---|---|
| `sheet` | spreadsheets | `data-grid` names the lesson's demo grid; `view` `{columns ≤4, rows [first, last] ≤7, active}` |
| `editor` | code editors, notebooks, terminals | `tool` (`editor`, `notebook`, `terminal`), `lines` (≤8 of ≤40 characters), `output` (≤4) |
| `app` | any other app window | `path` (≤4 menu or page names), `panel` (≤6 items: `field` {label, value}, `button` {label}, `message` {who, text ≤90}, `item` {text}) |

**Steps (≤5, one marker each):**

| Step | Keys |
|---|---|
| `select` | `target` |
| `click` | `path` [names] |
| `type` | `target`, `text` |
| `set` | `label`, `value` (a dialog or panel field) |
| `key` | `keys` |
| `result` | `target`; `sheet` only, computed by the Excel engine |

A `dialog` `{title, fields}` may be added to any layout.

**The owner's rule decides the picture** (`screens.screen_kind`):

- **Complex → A, drawn.** `render_screens.py` draws a phone-sized SVG in the app's own colours.
  A screen is complex when it has more than 3 steps, 2 or more fields to set, or a computed
  result.
- **Simple → B, an image.** Up to 3 clicks or keys on one screen. `visual_briefs.py` hands it to
  the illustrator, so a B spec also carries `alt`, `takeaway`, `misconception` and
  `check` {question, answer, reasoning}.
- **Forcing the other kind.** Set `"image": "A"` or `"B"` with a `"why"`; QA reads the reason.

**The sync rule (`check_screens.py` fails the lesson otherwise):**

- Every word the screen shows must appear in the lesson's visible text: menu names, labels,
  values, code lines and messages. Grid cells come from the demo grid, results from the engine,
  and Excel's ribbon tab names are known.
- The drawing is regenerated, never edited. Change the spec or the lesson, then run
  `render_screens.py` again.
- Do not repeat the run line beside the screen in a second form (R13). The screen shows where
  you click; the run line shows what you get.

---

## 17 · Scene — one simple idea through a familiar situation

For: a concept whose meaning becomes obvious from an everyday scene the section's text already
uses (a shop bill, a school roll number, a customs desk). A scene is always an AI image (B), in
the house style, with no text inside it.

```html
<script type="application/json" class="nerdit-scene">
{"id": "shop-bill", "subject": "A shopkeeper copying one bill into two notebooks, one per customer",
 "alt": "A shopkeeper writes the same bill into two notebooks.",
 "caption": "One bill, two copies: change one and they disagree.",
 "takeaway": "A fact stored twice can drift.", "misconception": "Copies stay equal by themselves.",
 "check": {"question": "What goes wrong when one notebook is corrected?",
           "answer": "The two copies disagree.", "reasoning": "Only one copy got the change."}}
</script>
```

The subject names the analogy the text already uses; never invent a new one for the picture.
Use a scene only when it is the clearest way in. A process, a structure or exact values get a
figure template (1–15) instead.

---

## Choosing between them

`CORE.md` §7 (the Visual Map) decides which visual a place in the lesson gets; this file only
supplies the markup. Nothing in the map fits and the concept still seems to need a picture?
Write the caption first: the one sentence the figure must teach. If that sentence will not
come, there is no figure to draw. **Prose is the correct answer, and an empty figure slot is
better than a decorative one.**
