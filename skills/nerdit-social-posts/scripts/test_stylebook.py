import json
from pathlib import Path

import pytest

from stylebook import (LAYOUTS, NoFreshLooks, history_path, load_history, load_styles, pick_looks, reserve_looks,
                       save_history, style_errors)

STYLES = Path(__file__).resolve().parents[1] / "styles"


def items(n: int) -> list[dict]:
    return [{"id": f"i{k:02d}"} for k in range(n)]


def navy() -> dict:
    return next(s for s in load_styles(STYLES) + load_styles(STYLES / "retired") if s["name"] == "navy")


def test_seed_styles_are_valid():
    styles = load_styles(STYLES)
    assert len(styles) >= 12 and all(style_errors(s) == [] for s in styles)
    assert len({s["background"] for s in styles}) == 5 and len({s["motif"] for s in styles}) == 5


def test_low_contrast_style_is_refused():
    s = navy()
    bad = {**s, "palette": {**s["palette"], "ink": "#06325a"}}
    assert "ink on bg contrast 1.1; at least 4.5" in style_errors(bad)


def test_unknown_font_and_bad_colour_are_refused():
    s = navy()
    errors = style_errors({**s, "fonts": {**s["fonts"], "head": "Comic Neue"}, "palette": {**s["palette"], "chip": "teal"}})
    assert "font Comic Neue is not installed on this PC" in errors and "palette.chip must be #rrggbb" in errors


def test_looks_are_fresh_and_consecutive_posts_differ():
    looks = pick_looks(items(10), load_styles(STYLES), {"looks": []}, "p1")
    assert len(set(looks)) == 10
    assert all(a[0] != b[0] and a[1] != b[1] for a, b in zip(looks, looks[1:]))
    assert all(looks[i][0] not in {s for s, _ in looks[max(0, i - 3):i]} for i in range(len(looks)))


def test_a_look_used_by_another_pack_is_never_picked():
    used = {"looks": [{"style": "navy", "layout": "stack", "packId": "old", "itemId": "d01-reel"}]}
    assert ("navy", "stack") not in pick_looks(items(10), load_styles(STYLES), used, "p1")


def test_running_out_of_fresh_looks_stops_with_counts():
    styles = load_styles(STYLES)
    full = {"looks": [{"style": s["name"], "layout": l, "packId": "old", "itemId": "x"} for s in styles for l in LAYOUTS[1:]]}
    with pytest.raises(NoFreshLooks, match=f"needs {len(styles) + 1} looks, {len(styles)} left"):
        pick_looks(items(len(styles) + 1), styles, full, "p1")


def test_this_packs_own_old_looks_are_free_again():
    styles = load_styles(STYLES)
    mine = {"looks": [{"style": s["name"], "layout": l, "packId": "p1", "itemId": "x"} for s in styles for l in LAYOUTS]}
    assert len(pick_looks(items(10), styles, mine, "p1")) == 10


def test_reserve_replaces_this_packs_entries_and_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("NERDIT_SOCIAL_HOME", str(tmp_path))
    h = reserve_looks({"looks": [{"style": "navy", "layout": "stack", "packId": "p1", "itemId": "old"},
                                 {"style": "ember", "layout": "split", "packId": "p0", "itemId": "a"}]},
                      "p1", [("d01-reel", "violet", "bleed")])
    assert h["looks"] == [{"style": "ember", "layout": "split", "packId": "p0", "itemId": "a"},
                          {"style": "violet", "layout": "bleed", "packId": "p1", "itemId": "d01-reel"}]
    save_history(history_path(), h)
    assert history_path() == tmp_path / "style-history.json" and load_history(history_path()) == h
    assert load_history(tmp_path / "missing.json") == {"looks": []}


def test_code_panels_must_be_dark_for_the_token_colours():
    s = navy()
    light_code = {**s, "palette": {**s["palette"], "codeBg": "#f8fafc", "codeInk": "#0b1f3a"}}
    assert "codeBg must be dark: code colours are tuned for dark panels" in style_errors(light_code)


def test_a_pack_uses_every_layout_family():
    looks = pick_looks(items(10), load_styles(STYLES), {"looks": []}, "p1")
    assert {l for _, l in looks} == set(LAYOUTS)


# ---- final review fixes ----
from stylebook import prune_history, mark_built  # noqa: E402


def test_reels_only_take_the_two_frame_layouts():
    reel_items = [{"id": f"d{k:02d}-reel", "format": "reel"} for k in range(6)]
    looks = pick_looks(reel_items, load_styles(STYLES), {"looks": []}, "p1")
    assert {l for _, l in looks} <= {"stack", "split"}


def test_an_abandoned_plan_frees_its_looks_but_a_built_pack_keeps_them(tmp_path):
    gone, built, alive = tmp_path / "gone", tmp_path / "built", tmp_path / "alive"
    alive.mkdir(); (alive / "pack-plan.json").write_text("{}")
    h = {"looks": [{"style": "navy", "layout": "stack", "packId": "a", "itemId": "x", "folder": str(gone)},
                   {"style": "ember", "layout": "split", "packId": "b", "itemId": "x", "folder": str(built)},
                   {"style": "violet", "layout": "bleed", "packId": "c", "itemId": "x", "folder": str(alive)}]}
    h = mark_built(h, "b")
    assert [e["packId"] for e in prune_history(h)["looks"]] == ["b", "c"]


def test_dark_pages_are_refused_owner_prefers_light():
    s = navy()
    dark = {**s, "palette": {**s["palette"], "bg": "#0a0a12", "bg2": "#1b1d2e"}}
    assert "bg must be light: the owner prefers light pages" in style_errors(dark)
    assert "bg2 must be light: the owner prefers light pages" in style_errors(dark)
