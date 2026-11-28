import json
from pathlib import Path

import pytest

from hookscore import best_hook, hook_errors, main, score_hook

APPROVED = "Ninety-six percent of Indian employees use AI at work."   # Trend Reel pilot 2, owner-approved
VAGUE = "Movement = end minus start"                               # Maths pack hook, abstract


def test_owner_approved_trend_hook_passes():
    assert score_hook(APPROVED)["score"] == pytest.approx(50.6, abs=0.1)
    assert hook_errors(APPROVED, "hook") == []


def test_vague_hook_fails_with_weakest_named():
    assert score_hook(VAGUE)["score"] == pytest.approx(27.6, abs=0.1)
    assert hook_errors(VAGUE, "d03-reel") == ["d03-reel: hook scores 28; at least 50 (weakest: SPECIFICITY)"]


def test_number_hook_scores_ok():
    assert score_hook("2 cubed is 8, not 6")["score"] == pytest.approx(62.6, abs=0.1)


def test_greeting_is_a_dealbreaker():
    errs = hook_errors("Hey guys, today I wanted to talk about Excel", "hook")
    assert any("Greeting" in e for e in errs)


def test_two_line_hook_scores_as_one_line():
    assert score_hook("Put -2 in brackets\nbefore you square it") == score_hook("Put -2 in brackets before you square it")


def test_best_hook_picks_the_highest():
    text, r = best_hook([VAGUE, "2 cubed is 8, not 6"])
    assert text == "2 cubed is 8, not 6" and r["verdict"] == "OK"


def test_cli_output_is_ascii(tmp_path, capsys):
    f = tmp_path / "h.txt"
    f.write_text("2² is 4, not ₹4\n", encoding="utf-8")
    main([str(f)])
    assert all(ord(c) < 128 for c in capsys.readouterr().out)


def test_cli_exits_1_when_the_best_hook_is_weak(tmp_path):
    f = tmp_path / "h.txt"
    f.write_text(VAGUE + "\n", encoding="utf-8")
    assert main([str(f)]) == 1


def test_hooks_json_drops_personal_result_formulas():
    d = json.loads((Path(__file__).parents[1] / "references" / "hooks.json").read_text(encoding="utf-8"))
    ids = {h["id"] for h in d["hooks"]}
    assert not ids & {1, 6, 15, 25} and 27 in ids and not set(d["classify_order"]) - ids
    assert all({"template", "example", "on_screen", "match"} <= h.keys() for h in d["hooks"])


# --- final-review fixes ---

def test_acronyms_and_camelcase_are_specific():
    assert score_hook("FastAPI checks every request")["score"] > score_hook("It checks every request")["score"]


def test_curly_apostrophe_scores_the_same():
    assert score_hook("PwC won’t wait: it is training eighty-five thousand people for AI.") == \
        score_hook("PwC won't wait: it is training eighty-five thousand people for AI.")


def test_formulas_never_claim_a_personal_past():
    import re
    d = json.loads((Path(__file__).parents[1] / "references" / "hooks.json").read_text(encoding="utf-8"))
    first_person = re.compile(r"\b(I|my|me|I'm|I've|I'd|mine)\b")
    for h in d["hooks"]:
        text = re.sub(r'"[^"]*"', "", " ".join([h["template"], h["example"], h["on_screen"]]))   # quoted viewer words are fine
        assert not first_person.search(text), (h["id"], h["name"])
    assert 8 not in {h["id"] for h in d["hooks"]}
