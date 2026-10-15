#!/usr/bin/env python3
"""Preview a course the way learners will see it: one self-contained HTML page.

    python build_preview.py --course <course_output.json> --out <preview.html>

Inlines css8, css9-simple and css10-brand, and colours code with highlight.js using the
website's scope->class table (nerdit/future-vision/src/utils/lessonHighlight.ts), so the
preview and the site agree. Try It boxes run only on the site, so runner scripts are dropped.
Stdlib only.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

REFS = Path(__file__).resolve().parent.parent / "references"
CSS_FILES = ("css8.css", "css9-simple.css", "css10-brand.css")
HLJS = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"
CHARTJS = "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"
# Keep in step with NERDIT_CLASS_BY_SCOPE in lessonHighlight.ts (test_build_preview checks it).
SCOPE_TO_CLASS = {
    "hljs-keyword": "kw", "hljs-selector-tag": "kw", "hljs-name": "kw", "hljs-literal": "kw",
    "hljs-built_in": "bltin", "hljs-type": "cls-n", "class_": "cls-n",
    "hljs-title": "fn", "function_": "fn", "hljs-section": "fn",
    "hljs-string": "str", "hljs-regexp": "str", "hljs-char": "str", "escape_": "str",
    "hljs-meta-string": "str", "hljs-number": "num", "hljs-comment": "cmt", "hljs-quote": "cmt",
    "hljs-doctag": "cmt", "hljs-operator": "op", "hljs-punctuation": "op", "hljs-meta": "dec",
    "hljs-meta-keyword": "dec", "hljs-params": "param", "hljs-attr": "param",
    "hljs-attribute": "param", "hljs-property": "param", "hljs-selector-attr": "param",
    "hljs-selector-class": "param", "hljs-selector-id": "param", "language_": "slf",
}
RUNNER_TAG = re.compile(r'<script\s+src="/nerdit-[a-z-]+\.js"\s*>\s*</script>\s*', re.I)
HIGHLIGHT = """<script src="%s"></script>
<script>
(function () {
  if (!window.hljs) return;
  var MAP = %s;
  document.querySelectorAll('pre[data-lang] > code').forEach(function (code) {
    if (code.children.length) return;
    var lang = (code.parentElement.getAttribute('data-lang') || '').toLowerCase();
    if (!hljs.getLanguage(lang)) return;
    try {
      code.innerHTML = hljs.highlight(code.textContent, { language: lang, ignoreIllegals: true }).value;
      code.querySelectorAll('span').forEach(function (s) {
        var m = []; s.classList.forEach(function (c) { if (MAP[c]) m.push(MAP[c]); });
        s.removeAttribute('class'); if (m.length) s.className = m.join(' ');
      });
    } catch (e) { /* leave plain text */ }
  });
})();
</script>"""


def build(course: dict) -> str:
    css = "\n".join((REFS / f).read_text(encoding="utf-8") for f in CSS_FILES)
    lessons = course.get("lessons", [])
    nav = "".join(f'<li><a href="#L{i:02d}">{i:02d} · {html.escape(l.get("title", ""))}</a> '
                  f'<span>{html.escape(l.get("duration", ""))}</span></li>' for i, l in enumerate(lessons, 1))
    body = "".join(f'<article class="pv-lesson" id="L{i:02d}"><p class="pv-tag">Lesson {i:02d} · '
                   f'{html.escape(l.get("id", ""))} · <a href="#top">back to list</a></p>'
                   f'{RUNNER_TAG.sub("", l.get("content", ""))}</article>' for i, l in enumerate(lessons, 1))
    title = html.escape(course.get("title") or "Course preview")
    script = HIGHLIGHT % (HLJS, json.dumps(SCOPE_TO_CLASS))
    # Lesson chart initializers execute as their markup is parsed. Match the site's
    # global Chart API before those scripts run; code runners remain site-only.
    charts = f'<script src="{CHARTJS}"></script>' if re.search(r'<canvas\b', body, re.I) else ''
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{charts}
<style>{css}</style>
<style>
body{{background:var(--bg-soft);margin:0}} .pv-top{{max-width:860px;margin:0 auto;padding:24px 16px 8px}}
.pv-top h1{{margin:0 0 6px;font-size:1.5rem}} .pv-top ol{{list-style:none;padding:0;margin:0;display:grid;gap:4px}}
.pv-lesson{{max-width:860px;margin:24px auto;padding:0 16px}} .pv-tag{{font-size:.8rem;color:var(--tx-m);margin:0 0 6px}}
</style></head><body>
<header class="pv-top" id="top"><h1>{title}</h1>
<p>{len(lessons)} lessons · checking copy, not published. Try It boxes run only on nerdit.in.</p>
<ol>{nav}</ol></header>{body}
{script}
</body></html>"""


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    try:
        course = json.loads(Path(args.course).read_text(encoding="utf-8"))
        page = build(course)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    Path(args.out).write_text(page, encoding="utf-8")
    print(f"{args.out}: {len(course.get('lessons', []))} lessons, {round(len(page.encode()) / 1024)} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
