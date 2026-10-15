import re
from pathlib import Path

import pytest

from build_preview import CSS_FILES, HLJS, REFS, SCOPE_TO_CLASS, build


def test_preview_inlines_styles_lessons_and_highlighter():
    course = {"title": "T", "lessons": [{"id": "a-01", "title": "One", "duration": "5m",
              "content": '<div class="nerdit-wrapper nerdit-simple"><script src="/nerdit-sql-runner.js"></script>'
                         '<pre data-lang="sql"><code>SELECT 1;</code></pre></div>'}]}
    page = build(course)
    for f in CSS_FILES:
        assert (REFS / f).read_text(encoding="utf-8")[:200] in page
    assert "a-01" in page and "SELECT 1;" in page
    assert "nerdit-sql-runner.js" not in page
    assert '"hljs-keyword": "kw"' in page and HLJS in page


def test_scope_table_matches_the_website():
    ts = Path(__file__).resolve().parents[4] / "nerdit" / "future-vision" / "src" / "utils" / "lessonHighlight.ts"
    if not ts.exists():
        pytest.skip("website checkout is not next to the plugin")
    body = re.search(r"NERDIT_CLASS_BY_SCOPE[^{]*\{(.*?)\};", ts.read_text(encoding="utf-8"), re.S).group(1)
    site = dict(re.findall(r"'?([\w-]+)'?\s*:\s*'([\w-]*)'", body))
    assert site == SCOPE_TO_CLASS


def test_preview_highlighter_leaves_fill_in_blank_code_alone():
    # The site skips code that holds elements (lessonHighlight.ts childElementCount > 0).
    page = build({"title": "T", "lessons": []})
    assert "code.children.length" in page


def test_preview_loads_chart_runtime_before_lesson_scripts():
    page = build({'lessons': [{'content': '<canvas id="metric"></canvas><script>new Chart(document.getElementById("metric"), {});</script>'}]})
    assert page.index('chart.umd.min.js') < page.index('new Chart(')
    assert 'chart.umd.min.js' not in build({'lessons': []})
