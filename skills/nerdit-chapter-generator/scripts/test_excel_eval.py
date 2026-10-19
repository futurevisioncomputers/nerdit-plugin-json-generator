import shutil

import pytest

import excel_eval
from excel_eval import evaluate_many
from test_screens import GRID

H, R = GRID["headers"], GRID["rows"]


def test_xlookup_returns_chennai():
    (res,) = evaluate_many(H, R, ['=XLOOKUP("Isha",B2:B7,D2:D7)'])
    assert res == {"value": "Chennai", "text": "Chennai"}


def test_unknown_function_is_an_error():
    assert evaluate_many(H, R, ["=FOO(1)"]) == [{"error": "#NAME?"}]


def test_batch_keeps_order():
    first, second = evaluate_many(H, R, ["=SUM(E2:E3)", '=XLOOKUP("Isha",B2:B7,D2:D7)'])
    assert first == {"value": 97000, "text": "97000"}
    assert second["text"] == "Chennai"


def test_missing_node_message(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="Node.js"):
        excel_eval.evaluate_many(H, R, ["=SUM(E2:E3)"])
