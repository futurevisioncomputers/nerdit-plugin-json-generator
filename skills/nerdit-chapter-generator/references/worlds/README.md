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

The generator writes `world_data.json` and SQLite-compatible `world_data.sql`.
Money ranges are integers in `business.moneyUnit` (usually paise or cents).
Explicit invented names are mandatory for `person_name`. No generated contact fields.
Entities have 0–100 rows. Foreign keys point to a nonempty entity/column; cycles fail.
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
