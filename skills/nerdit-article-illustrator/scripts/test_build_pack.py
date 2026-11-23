import json

from PIL import Image, ImageStat

from build_pack import main, plan_errors
from fixtures import ARTICLE, DIAGRAM, FIGURE


def course_svg() -> str:
    return FIGURE[FIGURE.index("<svg"):FIGURE.index("</svg>") + 6]


def make(tmp_path, items=None):
    (tmp_path / "split.svg").write_text(DIAGRAM, encoding="utf-8")
    (tmp_path / "fit.svg").write_text(course_svg(), encoding="utf-8")
    plan = {"items": items if items is not None else [
        {"file": "split.png", "source": "diagram", "svg": "split.svg",
         "anchor": "Split the data into a Training set and a Test set before you fit.",
         "labels": ["Training set", "Test set"], "alt": "Data split into a training set and a test set",
         "caption": "Fit on one part, test on the other"},
        {"file": "fit.png", "source": "course", "svg": "fit.svg", "anchor": "Lower MAE means better predictions.",
         "labels": ["fit", "score"], "alt": "Fit, then score", "caption": "Fit first, then score",
         "courseId": "reg-1", "courseSlug": "regression-1", "courseTitle": "Regression Basics"},
    ]}
    (tmp_path / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (tmp_path / "article.json").write_text(json.dumps(ARTICLE), encoding="utf-8")
    return plan


def test_a_good_plan_has_no_problems(tmp_path):
    plan = make(tmp_path)
    assert plan_errors(ARTICLE, plan, tmp_path) == []


def test_two_or_three_images_only(tmp_path):
    plan = make(tmp_path)
    assert any("2 or 3 images" in e for e in plan_errors(ARTICLE, {"items": plan["items"][:1]}, tmp_path))


def test_an_anchor_must_be_in_the_article_word_for_word(tmp_path):
    plan = make(tmp_path)
    plan["items"][0]["anchor"] = "Split the data before fitting."
    assert any("anchor" in e and "split.png" in e for e in plan_errors(ARTICLE, plan, tmp_path))


def test_a_diagram_label_must_come_from_the_article(tmp_path):
    plan = make(tmp_path)
    (tmp_path / "split.svg").write_text(DIAGRAM.replace("Test set", "Holdout"), encoding="utf-8")
    plan["items"][0]["labels"] = ["Training set", "Holdout"]
    errors = plan_errors(ARTICLE, plan, tmp_path)
    assert any("Holdout" in e for e in errors)


def test_the_svg_contract_is_checked(tmp_path):
    plan = make(tmp_path)
    (tmp_path / "split.svg").write_text(DIAGRAM.replace('fill="var(--nb)"', 'fill="#000000"'), encoding="utf-8")
    assert any("hex colour" in e for e in plan_errors(ARTICLE, plan, tmp_path))


def test_a_course_figure_needs_its_course(tmp_path):
    plan = make(tmp_path)
    del plan["items"][1]["courseTitle"]
    assert any("courseTitle" in e for e in plan_errors(ARTICLE, plan, tmp_path))


def test_build_renders_light_pngs_and_writes_placements(tmp_path):
    make(tmp_path)
    out = tmp_path / "pack"
    assert main(["--article", str(tmp_path / "article.json"), "--plan", str(tmp_path / "plan.json"), "--out", str(out)]) == 0
    img = Image.open(out / "split.png")
    assert img.width == 1600
    assert ImageStat.Stat(img.convert("L")).mean[0] / 255 >= 0.6
    placements = json.loads((out / "placements.json").read_text(encoding="utf-8"))
    assert placements[0] == {"file": "split.png", "anchor": "Split the data into a Training set and a Test set before you fit.",
                             "alt": "Data split into a training set and a test set", "caption": "Fit on one part, test on the other"}
    assert placements[1]["courseLink"] == "https://nerdit.in/course/regression-1/preview"
    assert placements[1]["courseTitle"] == "Regression Basics"


def test_build_refuses_a_bad_plan_and_writes_nothing(tmp_path, capsys):
    make(tmp_path, items=[])
    out = tmp_path / "pack"
    assert main(["--article", str(tmp_path / "article.json"), "--plan", str(tmp_path / "plan.json"), "--out", str(out)]) == 1
    assert "PROBLEM" in capsys.readouterr().out
    assert not out.exists()
