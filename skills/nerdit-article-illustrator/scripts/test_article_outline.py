from article_outline import outline
from fixtures import ARTICLE


def test_headings_and_paragraph_anchors_in_order_skipping_code():
    rows = outline(ARTICLE["markdown"])
    kinds = [(r["kind"], r["text"]) for r in rows]
    assert kinds[0] == ("heading", "What is regression?")
    assert ("anchor", "Regression predicts a number, like a house price, from features.") in kinds
    assert all("not a heading" not in t and "model.fit" not in t for _, t in kinds)
    assert ("heading", "Train and test") in kinds
    assert ("anchor", "- Fit on the Training set") in kinds


def test_each_anchor_knows_its_section():
    rows = [r for r in outline(ARTICLE["markdown"]) if r["kind"] == "anchor"]
    assert rows[-1] == {"kind": "anchor", "text": "Lower MAE means better predictions.", "section": "Evaluate"}
