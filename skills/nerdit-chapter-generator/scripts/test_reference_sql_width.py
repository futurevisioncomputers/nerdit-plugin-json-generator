"""Writers copy the references' SQL, so the references must obey the 60-character rule."""
import html
import re
from pathlib import Path

G = Path(__file__).resolve().parent.parent
SOURCES = ["references/CORE.md", "references/figures.md", "references/runners/sql.md"]


def _visible(code: str) -> list[str]:
    # Fill-in-the-blank code carries <input> markup; only the text a learner sees counts,
    # exactly as verify_course measures it.
    return html.unescape(re.sub(r"<[^>]+>", "", code)).splitlines()


def sql_lines(md: str):
    for block in re.findall(r"```html\n(.*?)```", md, re.S):
        for m in re.finditer(r'<pre data-lang="sql"><code>(.*?)</code></pre>', block, re.S):
            yield from _visible(m.group(1))
        for m in re.finditer(r'<div class="nerdit-tryit" data-seed="[^"]*">.*?<textarea[^>]*>(.*?)</textarea>', block, re.S):
            yield from _visible(m.group(1))


def test_reference_sql_examples_obey_the_60_character_rule():
    long = [(rel, ln) for rel in SOURCES for ln in sql_lines((G / rel).read_text(encoding="utf-8"))
            if len(ln.rstrip()) > 60]
    assert not long, long[:5]


def test_sql_md_teaches_the_layout_rule():
    text = (G / "references/runners/sql.md").read_text(encoding="utf-8")
    assert "## Layout" in text and "60 characters" in text
