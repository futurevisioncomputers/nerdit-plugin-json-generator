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

PLAN_V2 = {
    "version": 2,
    "cast": "Asha, a young analyst at a small Pune retailer.",
    "items": [
        {"lessonId": "load-basics-01", "section": 1, "heading": "1 — What a load does",
         "position": "after-explanation", "anchor": ANCHOR_1, "kind": "diagram",
         "question": "Where do checked rows end up?",
         "objective": "See that a load copies only checked rows into the warehouse and logs the run.",
         "sourceRefs": ["section 1, paragraphs 1-2"], "knownTerms": ["rows"], "newTerms": ["load", "run log"],
         "labels": ["warehouse", "run log"],
         "takeaway": "Only checked rows reach the warehouse, and each run is recorded.",
         "misconception": "A load does not clean data; cleaning happened earlier.",
         "intro": "Follow the rows from left to right.",
         "caption": "A load moves checked rows into the warehouse and records the run.",
         "alt": "Checked rows move into the warehouse while a run log records the load.",
         "explanation": ["The rows arrive in the warehouse.", "The run log records the run."],
         "checkQuestion": {"question": "Does the load change the row values?",
                           "answer": "No.", "reasoning": "It copies checked rows; it does not edit them."}},
        {"lessonId": "old-style-02", "section": 1, "heading": "Introduction",
         "position": "before-practice", "anchor": "", "kind": "illustration",
         "question": "What does a first lesson look like?",
         "objective": "Picture a student starting the course with one clear idea.",
         "sourceRefs": [], "knownTerms": [], "newTerms": [], "labels": [],
         "takeaway": "Each lesson starts from one idea.", "misconception": "You do not need to know everything first.",
         "intro": "Here is where every lesson starts.",
         "caption": "Every lesson starts with one clear idea.",
         "alt": "A student opens a notebook beside a laptop.",
         "explanation": ["The student opens the notebook.", "The laptop shows the first lesson."],
         "checkQuestion": {"question": "What does a lesson start from?", "answer": "One idea.",
                           "reasoning": "The picture shows a single starting point."},
         "subject": "A student opening a notebook beside a laptop."},
    ],
}


def course() -> dict:
    return copy.deepcopy(_COURSE)
