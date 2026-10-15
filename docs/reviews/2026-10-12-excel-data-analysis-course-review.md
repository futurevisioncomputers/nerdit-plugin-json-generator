# Excel course: explanations, examples and visuals

Reviewed: 2026-10-12 (Asia/Calcutta)
Course: [Business Intelligence and Data Analysis Using Excel](https://nerdit.in/course/excel-data-analysis-test-1785164945289)
Scope: targeted review of live lessons 1, 2, 4 and 5; desktop inspection and a 390 × 844 mobile
viewport check of lesson 2. This is a sample review, not certification of all ten lessons.

## Recommendation

Keep the shared datasets, worked outputs, local practice and section navigation. Correct the
example results and data-state ambiguity before using this course as a template for new content.
Replace dense instructional posters with focused visuals whose key details remain readable on
a phone and are explained in adjacent HTML text.

## What already works

- The course progresses from fundamentals and cleaning to lookups, reporting and advanced tools.
- Sample sheets include column letters and row numbers, which can support precise formula tracing.
- Worked examples show a result immediately after their instructions or formula.
- Lessons 1 and 2 place relevant images within the teaching sections, before worked examples.
- The lookup lesson has a working formula runner: the existing
  `=XLOOKUP("Rohan", B2:B7, E2:E7)` example returned `72000`, agreeing with its displayed data.
- The PivotTable lesson includes an interactive grouping/aggregation control and a chart.
- The first lesson's displayed eight sales amounts sum to `184100`; its average of `23012.5`
  agrees with that fixture. The full PivotTable dataset totals `742300`, also matching its
  initial all-period example.

These checks establish the listed examples only. They do not establish that the browser runner
matches every feature or version of desktop Excel.

## Priority content findings

### 1. Lookup lesson: two displayed results disagree with the sheet

The employee sheet places Kabir's salary `68000` in `E4`, Meera's `41000` in `E5`, and Rohan's
`72000` in `E6`.

| Example in lesson 4 | Published output | Output from the displayed fixture | Correction |
|---|---|---|---|
| `=OFFSET(A1, 3, 4)` | `41000`, described as Meera's salary | `68000`, from `E4` | Keep the formula and correct the value/name, or change the intended reference explicitly. |
| `=INDIRECT("E5")` | `72000`, described as Rohan's salary | `41000`, from `E5` | Keep the formula and describe Meera, or use `E6` for Rohan. |

The reference semantics were checked against Microsoft's [OFFSET documentation](https://support.microsoft.com/en-us/excel/functions/offset-function)
and [INDIRECT documentation](https://support.microsoft.com/en-us/excel/functions/indirect-function?ad=us&rs=en-us&ui=en-us).
The corrected values above are derived from the course's displayed table; these two formulas
were not executed in a desktop Excel application during this review.

Another explanation says a lookup from an ID column on the left to a city column on the right
cannot be done with plain VLOOKUP. The shown arrangement is the ordinary left-to-right lookup
case. Use a genuinely reversed lookup to demonstrate the stated advantage of INDEX/MATCH, or
change that explanation.

### 2. PivotTable timeline: January-February drops a qualifying record

With the Region slicer cleared and only January-February selected, the displayed source contains:

| Region | Rows contributing | Correct total |
|---|---|---|
| West | January 5: 180000; January 12: 1300 | 181300 |
| North | February 3: 175000 | 175000 |
| South | February 20: 12000 | 12000 |
| Grand total | All four records | 368300 |

The lesson's output lists only North and West and gives `356300`. It omits Meera's February 20
sale of `12000`. These totals were recomputed from the visible rows.

Explicitly state whether a previous Region slicer selection is cleared before this example.
Otherwise students also have to guess whether both filters are active.

The dashboard diagram is titled `Q1 2024` but displays West `360300`, which includes the April
sale. For Q1, West is `181300`; the complete Q1 total is `551800`. Align the diagram's period
with its data, or label it as an all-displayed-period layout example.

### 3. Cleaning lesson: the example sheet state is ambiguous

- In the opening Contacts sheet, `C4` is Aarav's email and Kabir's is `C5`. A later
  `LOWER(C4)` example displays Kabir's email. It can agree after deleting Aarav's duplicate row,
  but the lesson does not show the resulting renumbered sheet or clearly establish that state.
- Flash Fill practice calls `C2` a City value, while the shared fixture puts City in column E.
- Text to Columns examples introduce different contents into cells already occupied in the
  shared sheet, without clearly identifying an independent example sheet or a new destination.

Choose and state one model: each example resets to the shared fixture, or examples transform a
running workbook and display the updated state. Use named helper columns and an explicit output
destination when a split could overwrite existing data.

### 4. Validation claim is too absolute

The text says unapproved city names can never enter the sheet. Specify a Stop-style alert and
the direct-entry case; copied, filled or calculated values can bypass the entry warning.
Microsoft describes these limitations in [More on data validation](https://support.microsoft.com/en-us/excel/more-on-data-validation).

The lesson also teaches case-sensitive duplicate matching, including in its checkpoint. Treat
that as a separate verification task in the stated Excel version before reusing the content.
Do not transfer Power Query's case-sensitive behaviour to worksheet commands without checking;
Microsoft documents Power Query separately in [Working with duplicates](https://learn.microsoft.com/en-us/power-query/working-with-duplicates).
This review did not execute the worksheet Remove Duplicates command.

## Image and layout findings

- Lesson 2's four PNGs are 734 × 487 pixels. At the inspected phone viewport, the loaded
  Text to Columns picture rendered about 314 pixels wide. Its ribbon, dialog labels and
  spreadsheet text were difficult to read at that size.
- Each picture combines a heading, explanatory paragraph, ribbon, dialog, worksheet and
  multiple steps. That density duplicates nearby text and leaves little space for the part
  the learner must inspect.
- The images have topic-name alt text. Their essential steps should also be expressed in
  nearby accessible text, with an explicit connection to the pictured controls or cells.
- Some inline function/tool names in the opening checklist break across lines awkwardly on
  mobile. Body text itself remains readable, and the inspected page had no document-wide
  horizontal overflow.
- Lesson 1 visibly contains a stray run of backticks after the sorting/filtering image.
- Lesson 1 shows `24m` in the classroom and `18 min` inside the content; lesson 4 similarly
  shows `26m` versus about `18 min`. Use a single duration source.
- The opening objectives, numbered sections, quick reference and closing recap repeat similar
  information. Keep a short opening outcome and one useful closing reference.

### Recommended visual treatment

For Text to Columns, show the exact input cell, the delimiter choice and the two resulting
cells in three readable steps. Put the click instructions in HTML below the figure. A genuine,
verified Excel screenshot can support a menu operation; a schematic should clearly teach the
relationship rather than imitate a full ribbon or dialog.

For lookups, highlight one search value, its matched row and the returned cell. For OFFSET,
show `A1 → three rows down → four columns right → E4`, using the displayed employee table.
For timelines, mark included/excluded dates and connect each included record to its subtotal.

Use the same cells, values, names and period labels in the visual, prose, runner and answer.
Check the final asset at phone size after compression. Enlarging or zooming can supplement a
diagram but should not be required to understand its essential teaching point.

## Implications for the learning-visuals upgrade

These are additional recommendations for the
[existing learning-content plan](../superpowers/plans/2026-10-12-nerdit-learning-content-and-visuals.md):

- [ ] Add an Excel fixture/result check alongside the planned SQL result check. Validate supported
  formulas against the same dataset; mark unsupported operations for actual Excel verification.
- [ ] Record whether examples reset data or continue from the previous workbook state.
- [ ] Check date filters and chart titles against the rows used to compute their values.
- [ ] Require menu instructions and screenshots to identify their Excel version/platform.
- [ ] Include lesson 2 as a mobile image-density reference and lesson 4 as a cell-tracing check.
- [ ] Add generated-text hygiene and metadata-consistency checks for visible backticks and durations.
- [ ] Audit affected practice answers and checkpoints when correcting explanations.

The approved Data Modelling pilots can continue. This Excel review supplies additional cases for
the common authoring rules and a separate correction backlog for the published Excel course.

## Review limits and state

The live classroom was read through the user's existing browser session. No lesson edits,
publishing, quiz submissions or completion actions were performed. The temporary viewport was
reset, and the browser was returned to lesson 2's Removing Duplicate Rows section.

Lessons 3 and 6-10, certification content, download files and a full screen-reader workflow
were not reviewed. Desktop Excel was not launched. Published course corrections remain pending.
