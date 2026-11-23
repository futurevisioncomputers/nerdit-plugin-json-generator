import json

from course_figures import figures, main
from fixtures import COURSE


def test_finds_every_inline_svg_figure_with_its_caption_and_labels():
    found = figures(COURSE)
    assert [(f["lesson"], f["n"]) for f in found] == [("reg-01", 1), ("reg-02", 1)]
    assert found[0]["caption"] == "Fit on training rows, score on test rows."
    assert found[0]["title"] == "Fit, then score"
    assert found[0]["labels"] == ["fit", "score"]
    assert found[0]["svg"].startswith("<svg") and found[0]["svg"].endswith("</svg>")


def test_extract_writes_one_figure_svg(tmp_path):
    course = tmp_path / "course.json"
    course.write_text(json.dumps(COURSE), encoding="utf-8")
    out = tmp_path / "fig.svg"
    assert main(["--course", str(course), "--extract", "reg-02:1", "--out", str(out)]) == 0
    assert 'aria-label="Errors shrink"' in out.read_text(encoding="utf-8")
    assert main(["--course", str(course), "--extract", "reg-02:5", "--out", str(out)]) == 1
