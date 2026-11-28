import json
from datetime import date

import pytest

from runs import (home, may_spend, new_run, next_reset, ready, recent_choices, record_check, record_reel, reels_planned,
                  take_download)


def test_next_reset_rolls_month_and_year():
    assert next_reset(date(2026, 11, 25)) == date(2026, 12, 8)
    assert next_reset(date(2026, 12, 8)) == date(2027, 1, 8)
    assert next_reset(date(2026, 12, 31)) == date(2027, 1, 8)
    assert next_reset(date(2026, 12, 7)) == date(2026, 12, 8)


def test_reels_planned_counts_mon_wed_fri_sun_between():
    # Wed 25 Nov 2026 -> 8 Dec: Fri 27, Sun 29, Mon 30, Wed 2, Fri 4, Sun 6, Mon 7
    assert reels_planned(date(2026, 11, 25), date(2026, 12, 8)) == 7


def test_reels_planned_across_year_end():
    # Thu 31 Dec 2026 -> 8 Jan 2027: Fri 1, Sun 3, Mon 4, Wed 6, Fri 8 is the reset day (excluded)
    assert reels_planned(date(2026, 12, 31), date(2027, 1, 8)) == 4


def test_may_spend_first_take_and_reroll():
    assert may_spend(60, date(2026, 11, 25))[0] is True
    assert may_spend(59, date(2026, 11, 25))[0] is False
    ok, msg = may_spend(400, date(2026, 11, 25), reroll=True)   # 340 left < 7 * 60
    assert ok is False
    assert msg == "credits left: 400, enough for 6 more Reels before 8 Dec"
    assert may_spend(500, date(2026, 11, 25), reroll=True)[0] is True   # 440 >= 420


def test_new_run_makes_the_folder_with_clips(monkeypatch):
    run = new_run("daily", "pwc-ai-training", date(2026, 11, 25))
    assert run == home() / "2026-11-25-daily-pwc-ai-training"
    assert (run / "clips").is_dir()


def test_new_run_rejects_unknown_kind():
    with pytest.raises(ValueError):
        new_run("hourly", "x", date(2026, 11, 25))


def _good_run(tmp_path):
    run = new_run("daily", "x", date(2026, 11, 25))
    (run / "reel.mp4").write_bytes(b"reel")
    (run / "ideas.json").write_text(json.dumps({"ideas": [{"hook": "h"}], "chosen": 0, "reason": "r"}))
    for section in ("checked", "script", "transcript", "captions"):
        record_check(run, section, [])
    record_reel(run)
    return run


def test_ready_passes_a_checked_run(tmp_path):
    assert ready(_good_run(tmp_path)) == []


def test_ready_refuses_changed_reel(tmp_path):
    run = _good_run(tmp_path)
    (run / "reel.mp4").write_bytes(b"re-rendered")
    assert ready(run) == ["reel.mp4 changed after the checks"]


def test_ready_needs_every_section_and_a_chosen_idea(tmp_path):
    run = _good_run(tmp_path)
    checks = json.loads((run / "checks.json").read_text())
    del checks["captions"]
    checks["transcript"] = {"ok": False, "errors": ["extra: cream"]}
    (run / "checks.json").write_text(json.dumps(checks))
    (run / "ideas.json").write_text(json.dumps({"ideas": []}))
    errors = ready(run)
    assert any("captions" in e for e in errors)
    assert any("transcript" in e for e in errors)
    assert any("chosen" in e for e in errors)


def test_ready_without_reel(tmp_path):
    run = new_run("daily", "x", date(2026, 11, 25))
    assert "reel.mp4 is missing" in ready(run)


def test_take_download_copies_the_newest_recent_mp4(tmp_path):
    import os, time
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    old, new = downloads / "old.mp4", downloads / "Presenter_speaking_720p.mp4"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    os.utime(old, (time.time() - 600, time.time() - 600))
    run = new_run("daily", "x", date(2026, 11, 25))
    clip = take_download(run, downloads)
    assert clip == run / "clips" / "clip1.mp4" and clip.read_bytes() == b"new"


def test_take_download_refuses_an_old_file(tmp_path):
    import os, time
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    stale = downloads / "stale.mp4"
    stale.write_bytes(b"x")
    os.utime(stale, (time.time() - 7200, time.time() - 7200))
    with pytest.raises(FileNotFoundError):
        take_download(new_run("daily", "x", date(2026, 11, 25)), downloads)


def test_recent_choices_newest_first(tmp_path):
    for day, course in (("2026-11-23", "c1"), ("2026-11-25", "c3"), ("2026-11-24", "c2")):
        run = new_run("daily", course, date.fromisoformat(day))
        (run / "ideas.json").write_text(json.dumps(
            {"ideas": [{"course_id": course, "links": [f"https://a/{course}"]}], "chosen": 0}))
    assert [c["course_id"] for c in recent_choices(2)] == ["c3", "c2"]
    assert recent_choices(1)[0]["links"] == ["https://a/c3"]


def test_ready_refuses_a_stale_check(tmp_path):
    run = new_run("daily", "x", date(2026, 11, 25))
    (run / "script.json").write_text("{}")
    (run / "checked.json").write_text("{}")
    (run / "clips" / "clip1.mp4").write_bytes(b"take1")
    (run / "captions_filled.json").write_text("{}")
    (run / "reel.mp4").write_bytes(b"reel")
    (run / "ideas.json").write_text(json.dumps({"ideas": [{}], "chosen": 0}))
    record_check(run, "checked", [], [run / "checked.json"])
    record_check(run, "script", [], [run / "script.json", run / "checked.json"])
    record_check(run, "transcript", [], [run / "clips" / "clip1.mp4", run / "script.json"])
    record_check(run, "captions", [], [run / "captions_filled.json"])
    record_reel(run)
    assert ready(run) == []
    (run / "script.json").write_text('{"line": "edited"}')
    record_reel(run)   # a recompose refreshes the reel hash, but not the stale verdicts
    errors = ready(run)
    assert any("script check is stale" in e for e in errors)
    assert any("transcript check is stale" in e for e in errors)


def test_credits_cli_accepts_a_comma():
    from runs import main
    assert main(["credits", "1,050"]) == 0


def test_take_download_refuses_the_same_take_again(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "take1.mp4").write_bytes(b"first take")
    run = new_run("daily", "x", date(2026, 11, 25))
    take_download(run, downloads)
    with pytest.raises(FileNotFoundError):
        take_download(run, downloads)   # the re-roll is still downloading: newest finished file is take 1


def test_ready_needs_the_checked_verdict(tmp_path):
    run = _good_run(tmp_path)
    checks = json.loads((run / "checks.json").read_text())
    del checks["checked"]
    (run / "checks.json").write_text(json.dumps(checks))
    assert "checked check missing" in ready(run)


def test_ready_refuses_a_checked_verdict_made_without_fetching(tmp_path):
    run = _good_run(tmp_path)
    record_check(run, "checked", [], fetched=False)
    assert ("checked check ran without fetching the pages; run checked_check.py <run> without --no-fetch"
            in ready(run))
