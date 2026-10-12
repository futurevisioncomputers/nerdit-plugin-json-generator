"""A two-lesson course shared by every illustrator test.

load-basics-01 is a current-style lesson (numbered sections, an SVG figure, practice blocks,
a cheat sheet). old-style-02 is an older lesson (unnumbered headings, a hosted image).
"""
import copy

LESSON_NEW = """<div class="nerdit-wrapper nerdit-simple">
<h1>Load Basics</h1>
<div class="nerdit-info-box"><p>Overview paragraph inside a box.</p></div>
<section>
<h2>1 — What a load does</h2>
<p>A load copies cleaned rows into the warehouse &amp; keeps a <strong>run log</strong> of ₹ totals 📦.</p>
<p>The target table only ever receives checked rows.</p>
<div class="nerdit-figure"><svg viewBox="0 0 10 10" role="img" aria-label="Staging to warehouse"></svg><div class="nerdit-figure-caption">Rows move from staging to the warehouse.</div></div>
<div class="nerdit-predict"><div class="nerdit-predict-head">Try It</div><p>Inside practice.</p></div>
</section>
<section>
<h2>2 — Reruns are safe</h2>
<p>An idempotent load gives the same rows when you run it twice.</p>
<div class="nerdit-fillblank"><p>Fill the blank.</p></div>
</section>
<h2>📌 Quick cheat sheet</h2>
<table><tr><td>load</td></tr></table>
</div>"""

LESSON_OLD = """<h2>Introduction</h2>
<p>Old lessons start like this.</p>
<img src="https://nerdit.in/lesson-images/test/old-diagram.png" alt="Old diagram" width="1536" height="1024">
<h2>Key Takeaways</h2>
<p>Remember this.</p>"""

ANCHOR_1 = "A load copies cleaned rows into the warehouse & keeps a run"

_COURSE = {
    "id": "course-test",
    "title": "Test Course",
    "image": "",
    "lessons": [
        {"id": "load-basics-01", "title": "Load Basics", "content": LESSON_NEW, "duration": "20m", "questions": []},
        {"id": "old-style-02", "title": "Old Style", "content": LESSON_OLD, "duration": "10m", "questions": []},
    ],
    "lessonIds": ["load-basics-01", "old-style-02"],
}

PLAN = [
    {"lessonId": "load-basics-01", "section": 1, "heading": "1 — What a load does",
     "position": "after-explanation", "anchor": ANCHOR_1,
     "reason": "Makes the copy-into-warehouse step concrete.",
     "subject": "A conveyor carrying clean boxes from a sorting room into a large warehouse.",
     "labels": [], "alt": "Clean boxes ride a conveyor from a sorting room into a warehouse.",
     "caption": "A load moves only checked rows into the warehouse."},
    {"lessonId": "old-style-02", "section": 1, "heading": "Introduction",
     "position": "before-practice", "anchor": "",
     "reason": "Gives the old lesson a visual hook.",
     "subject": "A student opening a notebook beside a laptop.",
     "labels": ["Start"], "alt": "A student opens a notebook beside a laptop.",
     "caption": "Every lesson starts with one clear idea."},
]


def course() -> dict:
    return copy.deepcopy(_COURSE)
