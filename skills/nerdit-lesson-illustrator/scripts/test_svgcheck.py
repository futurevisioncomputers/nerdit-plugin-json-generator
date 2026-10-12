import copy

from PIL import Image

from convert_images import convert_all
from fixture_course import PLAN_V2, course
from manifest import add_slots_v2, new_manifest
from svgcheck import check_svg

GOOD = ('<svg viewBox="0 0 200 80" role="img" aria-label="Checked rows reach the warehouse">'
        '<text x="10" y="20" fill="var(--nb)">① warehouse</text>'
        '<text x="10" y="50" fill="var(--orange)">② run log</text></svg>')


def test_check_svg_accepts_a_contract_compliant_diagram():
    assert check_svg(GOOD, ["warehouse", "run log"], 2) == []


def test_check_svg_rejects_hex_size_and_missing_accessibility():
    bad = GOOD.replace('role="img" ', "").replace("var(--nb)", "#0B1F3A").replace("<svg ", '<svg width="200" ')
    errors = check_svg(bad, [], 0)
    assert any("role" in e for e in errors) and any("hex colour" in e for e in errors)
    assert any("width/height" in e for e in errors)


def test_check_svg_requires_every_label_as_text():
    assert any("label 'revenue'" in e for e in check_svg(GOOD, ["warehouse", "revenue"], 2))


def test_check_svg_marker_count_must_match_steps():
    assert any("2 numbered markers drawn, 3 reading steps" in e for e in check_svg(GOOD, [], 3))
    entity = GOOD.replace("① warehouse", "&#9312; warehouse")
    assert check_svg(entity, ["warehouse"], 2) == []


def test_convert_all_handles_diagrams_and_phone_previews(tmp_path):
    m = new_manifest(course(), "c.json")
    assert add_slots_v2(m, course(), copy.deepcopy(PLAN_V2)) == []
    (tmp_path / "incoming").mkdir()
    (tmp_path / "diagrams").mkdir()
    (tmp_path / "diagrams" / "load-basics-01-fig1.svg").write_text(GOOD, encoding="utf-8")
    Image.new("RGB", (1600, 1200), (238, 243, 249)).save(tmp_path / "incoming" / "old-style-02-img1.png")
    report = convert_all(m, tmp_path)
    assert set(report["converted"]) == {"load-basics-01-fig1", "old-style-02-img1"}
    assert (tmp_path / "preview" / "old-style-02-img1-phone.jpg").is_file()
    with Image.open(tmp_path / "preview" / "old-style-02-img1-phone.jpg") as pv:
        assert pv.width == 360
    (tmp_path / "diagrams" / "load-basics-01-fig1.svg").write_text(GOOD.replace("var(--nb)", "#000"), encoding="utf-8")
    report = convert_all(m, tmp_path)
    assert any("load-basics-01-fig1.svg: hex colour" in e for e in report["errors"])


def test_cli_names_each_missing_file_with_its_folder_and_extension(tmp_path, monkeypatch, capsys):
    import sys

    import convert_images
    import manifest as mf

    m = new_manifest(course(), "c.json")
    assert add_slots_v2(m, course(), copy.deepcopy(PLAN_V2)) == []
    mf.save(tmp_path, m)
    monkeypatch.setattr(sys, "argv", ["convert_images.py", "--images-dir", str(tmp_path)])
    convert_images.main()
    out = capsys.readouterr().out
    assert "diagrams/load-basics-01-fig1.svg" in out and "incoming/old-style-02-img1.png" in out
