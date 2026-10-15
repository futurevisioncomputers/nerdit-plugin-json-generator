"""figures.md is copied by writers verbatim, so its templates must pass the checks they teach."""
import re
from pathlib import Path

from verify_course import Report, verify_structure

FIG = Path(__file__).resolve().parent.parent / "references" / "figures.md"


def template_blocks() -> dict[int, list[str]]:
    text = FIG.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^## (\d+) · .*?(?=^## |\Z)", text, re.S | re.M):
        out[int(m.group(1))] = re.findall(r"```html\n(.*?)```", m.group(0), re.S)
    return out


def test_every_template_figure_names_its_visual():
    for n, blocks in template_blocks().items():
        for b in blocks:
            if 'class="nerdit-figure' in b:
                assert "data-visual=" in b, f"template {n}"


def test_v11_templates_pass_the_v11_figure_checks():
    blocks = template_blocks()
    for n in (11, 12, 13, 14, 15):
        assert blocks.get(n), f"template {n} missing"
        for b in blocks[n]:
            rep = Report()
            verify_structure(rep, {"lessons": [{"id": f"t{n}",
                             "content": f'<div class="nerdit-wrapper nerdit-simple">{b}</div>'}]}, "v11")
            bad = [f for f in rep.failures
                   if any(k in f for k in ("data-visual", "packs a table row", "viewBox", "hex", "caption", "aria"))]
            assert not bad, (n, bad)
