import json
import re
from pathlib import Path

import build_pack
from conftest import write_workdir
from source import load_source
from teach import FORMAT_CYCLE, csv_head, feed_card, story_card, teaching_carousel, used_blocks
from test_blocks import CSV_RUN, FLASK

ITEM_T1 = {"id": "d01-carousel", "lessonId": "demo-01", "topic": 1, "clipKey": "demo-01-t1-video", "format": "carousel"}
ITEM_T2 = {"id": "d02-carousel", "lessonId": "demo-01", "topic": 2, "clipKey": "demo-01-t2-video", "format": "carousel"}
URL = "https://nerdit.in/course/demo-course-1794042260740/preview"
EIGHT = ("<h2>Cheat Sheet</h2><div class='nerdit-cheatsheet'><table><thead><tr><th>Keyword</th><th>What it does</th>"
         "<th>Tiny example</th></tr></thead><tbody>"
         + "".join(f"<tr><td>{k}</td><td>does {k}</td><td><code>{k}()</code></td></tr>"
                   for k in ("application object", "route", "view function", "debug mode", "port", "host", "url_for", "blueprint"))
         + "</tbody></table></div>")


def src_with(tmp: Path, lesson_html: str, csv: str | None = None) -> dict:
    wd = write_workdir(tmp)
    path = wd / "course-demo_output.json"
    course = json.loads(path.read_text(encoding="utf-8"))
    course["lessons"][0]["content"] = lesson_html
    path.write_text(json.dumps(course), encoding="utf-8")
    if csv:
        (wd / "lessons").mkdir()
        (wd / "lessons" / "weekly_admissions.csv").write_text(csv, encoding="utf-8")
    return load_source(wd)


def sources(slides: list[dict]) -> set:
    return {(s["source"]["lessonId"], s["source"]["kind"], s["source"]["index"]) for s in slides if s.get("source")}


def test_cycle_starts_with_guess_the_output_and_moves_on(tmp_path):
    src = src_with(tmp_path, FLASK)
    assert FORMAT_CYCLE == ("predict", "compare", "run")
    first = teaching_carousel(src, ITEM_T1, set(), None)
    assert first["format"] == "predict" and [s["kind"] for s in first["slides"]] == ["cover", "predict-q", "predict-a", "cta"]
    assert first["slides"][0]["hook"] == "Guess the output"
    second = teaching_carousel(src, ITEM_T2, set(), "predict")
    assert second["format"] == "compare" and [s["kind"] for s in second["slides"]] == ["cover", "wrong", "right", "cta"]


def test_every_content_slide_names_its_source(tmp_path):
    slides = teaching_carousel(src_with(tmp_path, FLASK), ITEM_T1, set(), None)["slides"]
    assert all(s.get("source") for s in slides if s["kind"] not in ("cover", "cta"))
    assert sources(slides) == {("demo-01", "predict", 0)}


def test_a_used_block_is_never_reused(tmp_path):
    src = src_with(tmp_path, FLASK)
    first = teaching_carousel(src, ITEM_T1, set(), None)
    again = teaching_carousel(src, ITEM_T1, sources(first["slides"]), None)
    assert again is None or not (sources(again["slides"]) & sources(first["slides"]))


def test_run_needs_data_and_marks_sample_output(tmp_path):
    src = src_with(tmp_path, CSV_RUN, csv="branch,ad,admissions\nVesu,yes,12\nPal,no,7\n")
    run = teaching_carousel(src, ITEM_T1, set(), "compare")
    assert run["format"] == "run" and [s["kind"] for s in run["slides"]] == ["cover", "data", "code", "output", "cta"]
    data, output = run["slides"][1], run["slides"][3]
    # the lesson's table describes weekly_complaints.csv, the code reads weekly_admissions.csv: the CSV's rows are shown
    assert data["headers"] == ["branch", "ad", "admissions"] and data["sample"] is True and output["sample"] is True
    assert csv_head(Path(src["course_path"]).parent, "weekly_admissions.csv") == (["branch", "ad", "admissions"], [["Vesu", "yes", "12"], ["Pal", "no", "7"]])


def test_oversized_blocks_fall_back_to_the_key_idea_carousel(tmp_path):
    big = re.sub(r"<code>[^<]*</code>", "<code>" + "x = 1\n" * 13 + "</code>", FLASK)
    assert teaching_carousel(src_with(tmp_path, big), ITEM_T1, set(), None) is None


def test_blocks_without_code_or_output_are_skipped(tmp_path):
    no_code = FLASK.replace("<pre data-lang=\"python\"><code>site = Flask(__name__)\nprint(type(site).__name__)</code></pre>", "")
    result = teaching_carousel(src_with(tmp_path, no_code), ITEM_T1, set(), None)
    assert result is None or result["format"] != "predict"


def test_cheat_card_once_per_lesson_with_topic_rows_first(tmp_path):
    src = src_with(tmp_path, FLASK.split("<h2>📋 Cheat Sheet</h2>")[0] + EIGHT)
    card = story_card(src, ITEM_T2, True)
    assert card["kind"] == "cheat" and len(card["rows"]) == 6 and card["rows"][0][0] == "route"
    assert card["source"] == {"lessonId": "demo-01", "kind": "cheatsheet", "index": 0}
    assert story_card(src, ITEM_T2, False) is None


def test_no_cheat_sheet_means_the_picture_card(tmp_path):
    src = src_with(tmp_path, FLASK.split("<h2>📋 Cheat Sheet</h2>")[0])
    assert story_card(src, ITEM_T1, True) is None


def test_feed_card_prefers_wrong_vs_right_then_the_cheat_sheet(tmp_path):
    src = src_with(tmp_path, FLASK)
    assert feed_card(src, ITEM_T2, set(), False)["kind"] == "compare"
    assert feed_card(src, ITEM_T1, set(), False)["kind"] == "cheat"
    assert feed_card(src, ITEM_T1, set(), True) is None


def test_second_pack_never_reuses_a_block(tmp_path):
    src = src_with(tmp_path, FLASK)
    wd = Path(src["course_path"]).parent
    for start in ("2026-11-20", "2026-11-24"):           # a Friday and a Tuesday: carousel days
        assert build_pack.main(["plan", str(wd), "--start", start, "--days", "1", "--url", URL]) == 0
    plans = [json.loads((wd / "social-pack" / f"demo-{d}" / "pack-plan.json").read_text(encoding="utf-8"))
             for d in ("2026-11-20", "2026-11-24")]
    used = [set().union(*(sources(i.get("slides", []) + ([i["card"]] if i.get("card") else [])) for i in p["items"])) for p in plans]
    assert used[0] and not (used[0] & used[1])
    assert used_blocks(wd, "demo-2026-11-24") == used[0]


# ---- final review fixes ----
def test_cheat_rows_with_wide_examples_are_left_out(tmp_path):
    wide = EIGHT.replace("<code>port()</code>", "<code>app.config.from_mapping(SECRET_KEY='dev-only', START_ROWS=START_ROWS)</code>")
    card = story_card(src_with(tmp_path, FLASK.split("<h2>📋 Cheat Sheet</h2>")[0] + wide), ITEM_T2, True)
    assert "port" not in [r[0] for r in card["rows"]] and len(card["rows"]) == 6


def test_feed_cheat_card_has_at_most_four_rows(tmp_path):
    card = feed_card(src_with(tmp_path, FLASK.split("<h2>📋 Cheat Sheet</h2>")[0] + EIGHT), ITEM_T1, set(), False)
    assert card["kind"] == "cheat" and len(card["rows"]) == 4


def test_meet_the_data_must_describe_the_file_the_code_reads(tmp_path):
    # CSV_RUN's table describes weekly_complaints.csv while the code reads weekly_admissions.csv
    without_csv = teaching_carousel(src_with(tmp_path / "a", CSV_RUN), ITEM_T1, set(), "compare")
    assert without_csv is None
    with_csv = teaching_carousel(src_with(tmp_path / "b", CSV_RUN, csv="branch,ad,admissions\nVesu,yes,12\n"), ITEM_T1, set(), "compare")
    assert with_csv["slides"][1]["caption"] == "First rows of weekly_admissions.csv"
    assert with_csv["slides"][1]["source"]["kind"] == "csv"


# ---- owner 2026-11-20: a topic with no usable block borrows one from its own lesson ----
NO_BLOCKS_T3 = FLASK.replace("<h2>📋 Cheat Sheet</h2>", "<section><h2>3 — Run It</h2><p>Plain text only.</p></section>\n<h2>📋 Cheat Sheet</h2>")
ITEM_T3 = {"id": "d03-carousel", "lessonId": "demo-01", "topic": 3, "clipKey": "demo-01-t3-video", "format": "carousel"}


def test_a_topic_without_blocks_borrows_from_its_lesson(tmp_path):
    result = teaching_carousel(src_with(tmp_path, NO_BLOCKS_T3), ITEM_T3, set(), None)
    # nearest topic first: topic 2's Wrong vs right comes before topic 1's Guess the output
    assert result["format"] == "compare" and sources(result["slides"]) == {("demo-01", "compare", 0)}


def test_own_topic_first_and_used_blocks_are_not_borrowed(tmp_path):
    src = src_with(tmp_path, NO_BLOCKS_T3)
    assert sources(teaching_carousel(src, ITEM_T2, set(), None)["slides"]) == {("demo-01", "compare", 0)}
    borrowed = teaching_carousel(src, ITEM_T3, {("demo-01", "predict", 0)}, None)
    assert sources(borrowed["slides"]) == {("demo-01", "compare", 0)}
