"""Veo prompts per topic: briefs from the page, a teacher explaining with objects, the paste-ready sheet."""
import check_prompts
import topic_briefs

LESSON = {"id": "eda-01", "title": "start an EDA", "content": '''<div class="nerdit-wrapper">
<section><h2>1 — make your first pandas table</h2>
<p>A <strong>DataFrame</strong> is a table with named columns. It holds 4 orders.</p>
<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span>
<pre><code>orders = pd.DataFrame(records)
print(orders.head(2))</code></pre></div>
<div class="nerdit-out"><span class="nerdit-tag">Python shows</span><pre><code>  order amount
0    O1    400
1    O2    900</code></pre></div></div>
<div class="nerdit-predict"><pre><code>print(99)</code></pre></div>
</section><section><h2>📌 Quick cheat sheet</h2></section></div>'''}

STYLE = ("Realistic modern Indian training institute, soft daylight, navy and teal accents, "
         "clean desks, calm documentary feel.")


def teach(line, prop="four paper order slips",
          action="The teacher lays the slips side by side in a neat row and points at each one in turn."):
    return {"type": "teach", "prop": prop, "action": action, "camera": "slow push-in", "voiceover": line}


def veo(line, visual="A shop owner in a small Surat store lays four paper order slips side by side "
                     "on the counter and points at each one in turn."):
    return {"type": "veo", "visual": visual, "camera": "slow push-in", "voiceover": line}


def good_shots():
    return [teach("Every shop keeps orders. How do we look at all of them at once?"),
            teach("A DataFrame is a table with named columns and numbered rows.",
                  prop="a wooden tray with four slips", action="The teacher slides each slip into its own row of "
                  "the tray and runs a finger along the rows."),
            veo("Each order slip becomes one row, and each detail becomes a column."),
            {"type": "overlay", "show": "code1", "highlight": ["line:2"],
             "voiceover": "head(2) shows only the first two rows: O1 for 400 and O2 for 900."},
            teach("Look at a few rows first, and check the column names before trusting any number.")]


def briefs_for(world=None):
    doc = {"course": "EDA", "topics": topic_briefs.briefs({"lessons": [LESSON]})}
    if world:
        doc["world"] = world
        if topic_briefs.presenter_of(world):
            doc["presenter"] = topic_briefs.presenter_of(world)
    return doc


def test_brief_takes_heading_terms_code_and_numbers_from_the_page():
    b = topic_briefs.briefs({"lessons": [LESSON]})
    assert len(b) == 1
    b = b[0]
    assert b["key"] == "eda-01-t1-video" and b["heading"] == "Make Your First Pandas Table"
    assert b["lessonTitle"] == "Start an EDA" and b["terms"] == ["DataFrame"]
    assert b["runs"][0]["id"] == "code1" and "O2    900" in b["runs"][0]["output"]
    assert "400" in b["numbers"] and "4" in b["numbers"] and "99" not in b["numbers"]   # Try It left out
    assert "print(99)" not in b["prose"] and "named columns" in b["prose"]


def test_teacher_explains_on_camera_and_sheet_is_paste_ready():
    prompts = {"language": "english", "style": STYLE, "topics": [{"key": "eda-01-t1-video", "shots": good_shots()}]}
    assert check_prompts.check(briefs_for(), prompts) == []
    md = check_prompts.sheet(briefs_for(), prompts)
    assert "Slot key: `eda-01-t1-video` · 5 shot(s) · about 40 s" in md
    assert "### Shot 1 · Teach · attach: cast/Professor Mehta.png" in md
    assert "Object on the table: four paper order slips." in md and "says, lip-synced" in md
    assert "Professor Mehta (professor): Indian man in his early 50s" in md and "### Professor Mehta — professor" in md
    assert "overlays/eda-01-t1-video-s04.png" in md and "No on-screen text, no subtitles" in md


def test_checks_catch_drift_from_the_page_and_missing_teaching():
    shots = good_shots()
    shots[1] = teach("Tables help with analysis.")                                     # term never spoken
    shots[2] = veo("Revenue grew 37 percent this year, which shows growth clearly.")  # invented number
    shots[4] = teach("Look closely.", action='The teacher holds a card that reads "orders table" up high.')
    shots[3] = {"type": "overlay", "show": "code9", "voiceover": "This is code."}
    joined = "\n".join(check_prompts.check(briefs_for(), {"language": "english", "style": STYLE,
                                                          "topics": [{"key": "eda-01-t1-video", "shots": shots}]}))
    assert "key term 'DataFrame'" in joined and "number 37" in joined
    assert "asks Veo for written words" in joined and "'code9' is not in this section" in joined
    assert "show at least one of the section's own examples" in joined
    plain = [veo("A DataFrame is a table."), veo("Rows are orders."), teach("Columns are details.")]
    joined = "\n".join(check_prompts.check(briefs_for(), {"language": "english", "style": STYLE,
                                                          "topics": [{"key": "eda-01-t1-video", "shots": plain}]}))
    assert "open with a teach shot" in joined and "1 of 3 shots are teach shots" in joined
    no_prop = [{**teach("A DataFrame is a table."), "prop": ""}]
    assert any("prop" in e for e in check_prompts.check(briefs_for(), {"language": "english", "style": STYLE,
               "topics": [{"key": "eda-01-t1-video", "shots": no_prop}]}))


def test_short_clips_and_every_topic_needs_shots_or_a_reason():
    briefs = briefs_for()
    base = {"language": "english", "style": STYLE, "topics": []}
    assert any("no shots" in e for e in check_prompts.check(briefs, base))
    assert check_prompts.check(briefs, {**base, "skip": [{"key": "eda-01-t1-video", "reason": "covered by the demo"}]}) == []
    one = [teach("A DataFrame is a table with named columns and numbered rows.")]
    assert check_prompts.check(briefs, {**base, "topics": [{"key": "eda-01-t1-video", "shots": one}]}) == []
    long = check_prompts.check(briefs, {**base, "topics": [{"key": "eda-01-t1-video", "shots": good_shots() * 3}]})
    assert any("15 shot(s)" in e for e in long)


def test_world_trainer_teaches_cast_is_fixed_and_the_owner_stays_off_screen():
    world = topic_briefs.world_brief(topic_briefs.load_world("fvc-institute"))
    assert world["owner"] == "Siddharth Parakh" and "teal cotton kurta" in world["cast"][0]["visual"]
    assert topic_briefs.presenter_of(world)["name"] == "Fatima"           # the world's trainer teaches
    briefs = briefs_for(world)
    shot = {**teach("A DataFrame is a table with named columns and numbered rows."), "cast": ["Neha"]}
    prompts = {"language": "english", "style": STYLE, "topics": [{"key": "eda-01-t1-video", "shots": [shot]}]}
    assert check_prompts.check(briefs, prompts) == []
    md = check_prompts.sheet(briefs, prompts)
    assert "attach: cast/Fatima.png, cast/Neha.png" in md and "Fatima looks at the students and says" in md
    assert "Neha (admissions counsellor): Indian woman in her early 30s" in md
    assert md.count("Photorealistic waist-up portrait") == 3                 # Neha, Arjun, Fatima once each
    bad = [{**shot, "cast": ["Priya"]},
           teach("A DataFrame is a table.", action="Siddharth walks in and hands the teacher a tray of slips "
                                                   "while the students watch.")]
    errors = "\n".join(check_prompts.check(briefs, {**prompts, "topics": [{"key": "eda-01-t1-video", "shots": bad}]}))
    assert "'Priya' is not in the cast" in errors and "never on screen" in errors
