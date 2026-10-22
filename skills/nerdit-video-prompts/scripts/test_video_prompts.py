"""Veo prompts per topic: briefs from the page, shot-list checks, the paste-ready sheet."""
import json

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


def veo(voice, visual="A shop owner in a small Surat store lays four paper order slips side by side "
                      "on the counter and points at each one in turn."):
    return {"type": "veo", "visual": visual, "camera": "slow push-in", "voiceover": voice}


def good_shots():
    return [veo("Every shop keeps orders. How do we look at all of them at once?"),
            veo("A DataFrame is a table with named columns and numbered rows."),
            veo("Each order slip becomes one row, and each detail becomes a column."),
            {"type": "overlay", "show": "code1", "highlight": ["line:2"],
             "voiceover": "head(2) shows only the first two rows: O1 for 400 and O2 for 900."},
            veo("Looking at a few rows first tells you what the table holds."),
            veo("Check the column names before you trust any number."),
            veo("So: build the DataFrame, then inspect its first rows.")]


def test_brief_takes_heading_terms_code_and_numbers_from_the_page():
    b = topic_briefs.briefs({"lessons": [LESSON]})
    assert len(b) == 1
    b = b[0]
    assert b["key"] == "eda-01-t1-video" and b["heading"] == "Make Your First Pandas Table"
    assert b["lessonTitle"] == "Start an EDA" and b["terms"] == ["DataFrame"]
    assert b["runs"][0]["id"] == "code1" and "O2    900" in b["runs"][0]["output"]
    assert "400" in b["numbers"] and "4" in b["numbers"] and "99" not in b["numbers"]   # Try It left out
    assert "print(99)" not in b["prose"] and "named columns" in b["prose"]


def test_good_shot_list_passes_and_sheet_is_paste_ready(tmp_path):
    briefs = {"course": "EDA", "topics": topic_briefs.briefs({"lessons": [LESSON]})}
    prompts = {"language": "english", "style": STYLE, "topics": [{"key": "eda-01-t1-video", "shots": good_shots()}]}
    assert check_prompts.check(briefs, prompts) == []
    md = check_prompts.sheet(briefs, prompts)
    assert "Slot key: `eda-01-t1-video` · 7 shots · about 56 s" in md
    assert md.count("### Shot") == 7 and "overlays/eda-01-t1-video-s04.png" in md
    assert "No on-screen text, no subtitles" in md and STYLE in md


def test_checks_catch_drift_from_the_page():
    briefs = {"course": "EDA", "topics": topic_briefs.briefs({"lessons": [LESSON]})}
    shots = good_shots()
    shots[1] = veo("Tables help with analysis.")                                      # term never spoken
    shots[2] = veo("Revenue grew 37 percent this year, which shows growth clearly.")  # invented number
    shots[4] = veo("Look closely.", visual='A screen that reads "orders table" in big letters')
    shots[3] = {"type": "overlay", "show": "code9", "voiceover": "This is code."}
    shots[6] = veo("So: build the table, then inspect its first rows.")
    errors = check_prompts.check(briefs, {"language": "english", "style": STYLE,
                                          "topics": [{"key": "eda-01-t1-video", "shots": shots}]})
    joined = "\n".join(errors)
    assert "key term 'DataFrame'" in joined and "number 37" in joined
    assert "asks Veo for written words" in joined and "'code9' is not in this section" in joined
    assert "show at least one of the section's own examples" in joined


def test_every_topic_needs_shots_or_a_reason():
    briefs = {"course": "EDA", "topics": topic_briefs.briefs({"lessons": [LESSON]})}
    base = {"language": "english", "style": STYLE, "topics": []}
    assert any("no shots" in e for e in check_prompts.check(briefs, base))
    assert check_prompts.check(briefs, {**base, "skip": [{"key": "eda-01-t1-video", "reason": "covered by the demo"}]}) == []
    one = [veo("A DataFrame is a table with named columns and numbered rows.")]
    assert check_prompts.check(briefs, {**base, "topics": [{"key": "eda-01-t1-video", "shots": one}]}) == []
    long = check_prompts.check(briefs, {**base, "topics": [{"key": "eda-01-t1-video", "shots": good_shots() * 2}]})
    assert any("14 shot(s)" in e for e in long)
    three = [veo("A DataFrame is a table with named columns."), veo("Each order is one row."), veo("Check it first.")]
    assert any("own examples" in e for e in check_prompts.check(
        briefs, {**base, "topics": [{"key": "eda-01-t1-video", "shots": three}]}))


def test_world_cast_is_fixed_and_the_owner_stays_off_screen():
    import topic_briefs as tb
    world = tb.world_brief(tb.load_world("fvc-institute"))
    assert world["owner"] == "Siddharth Parakh" and "teal cotton kurta" in world["cast"][0]["visual"]
    briefs = {"course": "EDA", "world": world, "topics": topic_briefs.briefs({"lessons": [LESSON]})}
    shot = {**veo("A DataFrame is a table with named columns and numbered rows."), "cast": ["Neha"]}
    prompts = {"language": "english", "style": STYLE, "topics": [{"key": "eda-01-t1-video", "shots": [shot]}]}
    assert check_prompts.check(briefs, prompts) == []
    md = check_prompts.sheet(briefs, prompts)
    assert "Neha (admissions counsellor): Indian woman in her early 30s" in md and "attach: cast/Neha.png" in md
    assert "### Arjun — data analyst" in md and md.count("Photorealistic waist-up portrait") == 3
    bad = [{**shot, "cast": ["Priya"]}, veo("A DataFrame is a table.", visual="Siddharth walks into the classroom and greets the batch "
                                             "warmly before the class begins today.")]
    bad[1].pop("cast", None)
    errors = "\n".join(check_prompts.check(briefs, {**prompts, "topics": [{"key": "eda-01-t1-video", "shots": bad}]}))
    assert "'Priya' is not in the world's cast" in errors and "list the cast" in errors and "never on screen" in errors
