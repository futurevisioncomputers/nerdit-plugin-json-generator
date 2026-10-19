# Business worlds

A world is the story bible and synthetic source data for a course. Start with
`practice-retail.world.json`, an entirely fictional retailer. Source notes about
real businesses are research inputs, not permission to publish their names.

Create `course-<chapter>_world.json` next to the input with either a complete world
or `{"use": "practice-retail"}`. Run from the plugin root:

```powershell
python skills/nerdit-chapter-generator/scripts/check_input.py --input course-x_input.json --world course-x_world.json --strict
python skills/nerdit-chapter-generator/scripts/make_world_data.py --world course-x_world.json --out-dir work
python skills/nerdit-chapter-generator/scripts/gate_lesson.py --input course-x_input.json --dir work --id x-01 --world course-x_world.json
python skills/nerdit-chapter-generator/scripts/verify_course.py --input course-x_input.json --output course-x_output.json --contract v11 --world course-x_world.json
```

The generator writes `world_data.json`, SQLite-compatible `world_data.sql` and
`world_data.manifest.json` (planned defects), plus `<entity>.csv` for analytics entities.
The rules live in `../nerdit_world_gen.py`, the same file the website's Python runners use.
Money ranges are integers in `business.moneyUnit` (usually paise or cents).
Explicit invented names are mandatory for `person_name`. No generated contact fields.
Entities have 0–100 rows (`sql` profile, the default). Foreign keys point to a nonempty
entity/column; cycles fail.
Entity and column traversal is sorted, so JSON key order does not change generated data.
Month weights use string keys `"1"` through `"12"`; omitted months have weight 1.
Changing the world, seed or generator definitions changes the data: keep all three
with the reviewed output. Never regenerate an existing course's records by guessing
an equivalent seed; preserve its source records and review that migration separately.

For an existing course an entity may carry `records`, an exact list of preserved
row objects. Its length must equal `rows`, each object's keys must match `columns`,
and values must be finite scalars or NULL. This bypasses random resampling for that
entity while retaining row/column, contact-field and foreign-key validation. Record
the source file/hash and any catalogue normalization in `provenance`. A catalogue
that unions domains across repeated demo-table schemas is a vocabulary check, not
proof of row relationships; SQL checks and QA still establish those relationships.

Use canonical entity and column names in seed tables. Staging tables can use another
name only if their columns identify exactly one source entity. Each seed is checked
independently, as the runner recreates its own database. Unknown columns fail.
For figure tables put `data-world-entity="orders"` on `nerdit-figure`; each header
uses its source column name or `data-world-column="amount_paise"`. A decorated cell
may carry `data-world-value="12500"` to separate its raw value from its visible notes.
For a derived result table use `data-world-derived="SUM(amount_paise) by store_id"`.
Derived results and SVG relationship labels require SQL-output verification and QA;
domain membership alone cannot establish their arithmetic or meaning.

Declare an intentional defect in the seed on its own line:

```sql
-- defect: orders row 1 amount_paise "12x"
```

The last token is a JSON scalar. Entity, one-based row, column and value must all
match. The column must be listed in `messiness`. A declaration is not a blanket
exception for a person, price or product. Do not label normal data as defective to
silence validation. Put the disclosure before the first data table and a course map
under the overview. Each lesson chooses its current stage from the world's `stages`.

Fictional business disclosure: “All records, people and amounts are synthetic, made
for teaching.” A real business additionally requires “Business name used with
permission.” and a `business.realName` object containing `approvedBy`, ISO `date`
and `note` recording permission evidence. Invent all cast members and records;
do not use real staff, customer contacts or logos. QA reviews story beats so mistakes
belong to data entry, queries or pipelines rather than allegations about the business.

## Data Science worlds (analytics profile)

`"profile": "analytics"` on a world or one entity allows up to 20,000 rows per entity and
200,000 cells over the world's analytics entities. Analytics entities are drawn column by
column in dependency order; `sql` entities keep the original row-by-row draw.

| Generator | Parameters | Gives |
| --- | --- | --- |
| `normal` | `mean`, `sd`, optional `min`, `max`, `round` (default 2; 0 gives whole numbers) | marks, readings |
| `lognormal` | `median`, `sigma`, optional `max`, `round` | order values, incomes |
| `poisson` | `lam` | counts per day |
| `bernoulli` | `p` | 0/1 flags |
| `linear` | `intercept`, `terms` {column: weight}, `effects` {column: {value: delta}}, `noise_sd`, optional `min`, `max`, `round` | a number driven by other columns |
| `logistic` | `intercept` or `target_rate`, `terms`, `effects` | a 0/1 label; `target_rate` sets the class balance |
| `binned_effect` | `column`, ascending `edges`, `deltas` (one more than edges) | a step by range; an edge value belongs to the bin above |
| `text` | `templates`, `slots` {name: [values]}, optional `tone_from` {label column: {value: [templates]}} | reviews, messages |

- Effect keys and `tone_from` keys are strings: a label of `1` is looked up as `"1"`.
- Declared weights are the truth. Columns that only carry the truth (`delay_effect`,
  `speed_risk`, `_segment`) are dropped from lesson CSVs unless the lesson is about them.
- Text placeholders are `{slot}`; every placeholder must be a slot, and templates and slots
  may not hold contact words, `@` or phone-like numbers (ISO dates are fine).
- `segments` {name: {weight, overrides: {column: {param: value}}}}: each row draws a segment
  first; overrides change parameters, never the generator. The hidden `_segment` column
  records the segment and comes last.
- `"kind": "series"`: `start`, `end`, `freq` (`day`, `week`, `month` on the 1st), `base`,
  `trend_per_period`, `weekly` (7 multipliers, Monday first, daily only), `monthly`,
  `holidays` [{date, lift, days}], `noise_sd`, `break` {date, shift}, `value_column`,
  `date_column`. One row per period; values are whole numbers of at least 0.
- `"kind": "interactions"`: `users`, `items` (table entities), `user_column`, `item_column`
  (their id columns), `rating_column` (default `rating`), `k` 1–5, `density` 0.01–0.3,
  `scale` [low, high], `noise_sd`. Ratings come from latent user and item factors.
- `defects` per entity, applied after its columns in this order: `drift` {after, column,
  shift, optional date_column}, `outliers` [{column, rate, factor}], `label_noise` {column,
  rate} (0/1 columns), `missing` [{column, rate, optional when {column: value}}],
  `duplicates` rate (copies appended with new ids). Each hits exactly round(rate × rows)
  rows, and the manifest lists them, so a lesson can name the dirty rows.

A lesson does not ship a CSV. It ships a dataset block (`runners/python.md`) holding a
recipe: a seed, the files to build and the entities they need, copied in full from the world.

| World | Business | Entities |
| --- | --- | --- |
| `fvc-institute` | Future Vision Computers (real name, owner's permission recorded) | enquiries, learners, daily_enquiries, batch_scores, enquiry_messages |
| `saree-wholesale` | Kesar Loom Sarees (invented) | retailers, skus, weekly_orders, retailer_sku, order_lines |
| `stationery-d2c` | Paper Lantern Studio (invented) | products, customers, orders, ratings, reviews, daily_sales |
| `boat-cruises` | Harbour Lights Cruises (invented) | bookings, quotes, cancellations, daily_bookings |
| `wire-mesh` | Ironleaf Wire Works (invented) | products, prices, qc_measurements, roll_defects |

The invented businesses follow the patterns in `docs/superpowers/notes/2026-10-15-world-sources.md`
and keep invented names until each owner's permission is recorded. `ds-course-map.json` maps
each Data Science course to its world and entities.
