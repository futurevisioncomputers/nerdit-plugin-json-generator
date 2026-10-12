# Learning Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make lesson figures teach: technical diagrams drawn from each lesson's own data with numbered reading steps, generated illustrations only for scenes, every figure introduced and explained in visible text, re-reviewed when its section changes — proven on two pilot lessons and one backfill before any rollout.

**Architecture:** The illustrator gains a versioned (v2) visual brief per slot. Diagram slots are inline SVG that Claude authors from the full section and its fixture; illustration slots keep the prompt/WebP path. Insertion writes four sibling elements sharing one `data-nerdit-img` id (intro paragraph, figure, read-the-figure list, check question), which keeps the verifier's two-level nesting cap. A section fingerprint detects content edits after planning. The chapter generator's rules and agents adopt the same teaching sequence, and a new SQLite checker confirms SQL example outputs.

**Tech Stack:** Python 3.14, Pillow 12.1.1, pytest 9.1.1, sqlite3 (standard library). No new dependencies.

**Spec:** `docs/superpowers/plans/2026-10-12-nerdit-learning-content-and-visuals.md` (approved 2026-10-12, commit a624771, including its "Additions agreed 2026-10-12"). Baseline: `docs/superpowers/specs/2026-10-10-nerdit-lesson-illustrator-design.md` and the v3.1.0 code.

## Global Constraints

- Run illustrator tests: `cd skills/nerdit-lesson-illustrator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`. Chapter-generator tests: same command in `skills/nerdit-chapter-generator/scripts`. Baselines: 54 and 120 passed.
- Existing v1 manifests, plan lists and inserted v1 blocks keep working unchanged. v2 is selected by a plan file that is a JSON object `{"version": 2, ...}`; a JSON list stays v1.
- Technical diagrams are inline SVG drawn from the lesson's own section text and fixture. Never generate a technical diagram as an AI image.
- SVG contract (verifier + `CORE.md` §7/§7b + `figures.md`): `viewBox`, `role="img"`, non-empty `aria-label`, no `width`/`height` on `<svg>`, colours only `var(--token)`, text as `<text>`, wrapped in `div.nerdit-figure` with a `div.nerdit-figure-caption`.
- Inserted v2 elements are siblings, each carrying `data-nerdit-img="<image-id>"`; no wrapper `div` (verifier depth cap: section > one block). No `id` attributes are added.
- Numbered markers are the literal characters `①②③④⑤`; a figure with two or more reading steps shows exactly as many markers as steps.
- Diagram labels must appear verbatim in the target section's text or the lesson fixture.
- No per-lesson image quota and no caption word limit for v2 slots; alt text at most 150 characters.
- Every CLI calls `sys.stdout.reconfigure(encoding="utf-8")`.
- Never modify an input course JSON; never write `data:` URIs; never call an image API.
- Pilots are local. Nothing is uploaded or published in this plan.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; stage only the files each task names.

## Review Focus

1. A section edited after its visual was planned (a value, a name, a sentence) — apply refuses with a re-review message instead of inserting a stale figure (Task 6 test `test_stale_section_blocks_output`).
2. A diagram label that is not in the lesson (for example `revenue` when the lesson says `amount`, or `Boston` when it says `Pune`) — plan refuses it (Task 3 test `test_v2_label_absent_from_lesson_is_refused`).
3. Markers and steps out of step (three steps, two markers drawn) — refused at convert time (Task 4 test `test_check_svg_marker_count_must_match_steps`).
4. A lesson containing both v1 and v2 inserted blocks, re-applied after the generator rebuilt its JSON — byte-identical lessons and a clean strip (Task 1 test `test_remove_visual_blocks_strips_v1_and_v2_and_keeps_the_rest`, Task 6 test `test_v2_running_twice_is_identical`).
5. SQL examples whose shown table no longer matches what the seed data produces — reported per example, not hidden (Task 7 test `test_mismatching_output_is_reported`).

---

### Task 1: Lesson HTML helpers for full sections, fixtures, fingerprints and v2 blocks

**Files:**
- Modify: `skills/nerdit-lesson-illustrator/scripts/lessonhtml.py` (append)
- Test: `skills/nerdit-lesson-illustrator/scripts/test_lessonhtml_v2.py`

**Interfaces:**
- Consumes: `sections`, `find_section`, `TAG`, `text` (Task-1 v1 module)
- Produces:
  - `remove_visual_blocks(content: str) -> str` — removes every `p`/`div`/`ol` element carrying `data-nerdit-img` (v1 and v2), plus the newline before it
  - `visual_elements(content: str, image_id: str) -> list[tuple[str, str]]` — `(tag, element_html)` in document order
  - `section_text(content: str, sec: Section) -> str` — readable plain text, code blocks kept line by line, inserted visuals excluded
  - `fixture_text(content: str) -> str` — seed `<script type="text/plain">` bodies and demo-table text
  - `section_fingerprint(content: str, number: int, heading: str) -> str` — 16 hex chars, ignores inserted visuals

- [ ] **Step 1: Write the failing tests**

```python
from fixture_course import course
from lessonhtml import (fixture_text, remove_visual_blocks, section_fingerprint, section_text,
                        sections, visual_elements)

V1 = ('\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="a-img1">\n'
      '  <img src="a.webp" alt="x">\n  <div class="nerdit-figure-caption">Cap</div>\n</div>')
V2 = ('\n<p class="nerdit-visual-intro" data-nerdit-img="a-fig1">Look at the rows.</p>'
      '\n<div class="nerdit-figure" data-nerdit-img="a-fig1">\n'
      '  <svg viewBox="0 0 10 10" role="img" aria-label="x"><text>①</text></svg>\n'
      '  <div class="nerdit-figure-caption">Cap</div>\n</div>'
      '\n<ol class="nerdit-visual-read" data-nerdit-img="a-fig1"><li>① Step.</li></ol>'
      '\n<div class="nerdit-predict" data-nerdit-img="a-fig1"><div class="nerdit-predict-head">Try</div>'
      '<p>Q?</p><details class="nerdit-predict-answer"><summary>Show answer</summary><p>A.</p></details></div>')
ANCHOR = "totals 📦.</p>"


def lesson0():
    return course()["lessons"][0]["content"]


def test_remove_visual_blocks_strips_v1_and_v2_and_keeps_the_rest():
    base = lesson0()
    assert remove_visual_blocks(base.replace(ANCHOR, ANCHOR + V1 + V2)) == base


def test_visual_elements_lists_the_siblings_of_one_visual():
    content = lesson0().replace(ANCHOR, ANCHOR + V2)
    assert [tag for tag, _ in visual_elements(content, "a-fig1")] == ["p", "div", "ol", "div"]
    assert visual_elements(content, "nope") == []


def test_section_text_keeps_code_lines_and_drops_visuals():
    content = ('<h2>1 — Q</h2><p>Intro <strong>term</strong>.</p>'
               '<pre><code>SELECT a,\n  b FROM t;</code></pre>' + V2)
    out = section_text(content, sections(content)[0])
    assert "1 — Q" in out and "Intro" in out and "term" in out
    assert "SELECT a,\n  b FROM t;" in out
    assert "Look at the rows" not in out


def test_fingerprint_ignores_inserted_visuals_but_tracks_text_edits():
    base = lesson0()
    fp = section_fingerprint(base, 1, "1 — What a load does")
    assert len(fp) == 16
    assert section_fingerprint(base.replace(ANCHOR, ANCHOR + V2), 1, "1 — What a load does") == fp
    assert section_fingerprint(base.replace("checked rows", "verified rows"), 1, "1 — What a load does") != fp


def test_fixture_text_reads_seed_scripts_and_demo_tables():
    content = ('<div class="nerdit-demo-table"><table><tr><td>Aarav</td><td>Pune</td></tr></table></div>'
               '<script type="text/plain" id="s1">INSERT INTO t VALUES (1);</script>')
    out = fixture_text(content)
    assert "Aarav" in out and "Pune" in out and "INSERT INTO t VALUES (1);" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_lessonhtml_v2.py`
Expected: FAIL — `ImportError: cannot import name 'fixture_text' from 'lessonhtml'`

- [ ] **Step 3: Append to `lessonhtml.py`**

```python
import hashlib

VISUAL_ATTR = re.compile(r'<(p|div|ol)\b[^>]*\bdata-nerdit-img="([^"]+)"[^>]*>', re.I)
_TOKENS = {
    "div": re.compile(r"<div\b|</div\s*>", re.I),
    "p": re.compile(r"<p\b|</p\s*>", re.I),
    "ol": re.compile(r"<ol\b|</ol\s*>", re.I),
}
PRE = re.compile(r"<pre\b[^>]*>(.*?)</pre>", re.S | re.I)
BLOCK_BREAK = re.compile(r"</?(?:p|div|h[1-6]|li|tr|table|section|details|summary|ol|ul|br)\b[^>]*>", re.I)
SEED = re.compile(r'<script\b[^>]*type="text/plain"[^>]*>(.*?)</script>', re.S | re.I)
DEMO = re.compile(r'<div\b[^>]*\bclass="[^"]*\bnerdit-demo-table\b[^"]*"[^>]*>', re.I)


def _element_end(content: str, start: int, tag: str) -> int:
    """End offset of the element whose start tag begins at `start`, counting nested same tags."""
    depth = 0
    for t in _TOKENS[tag].finditer(content, start):
        depth += -1 if t.group(0).startswith("</") else 1
        if depth == 0:
            return t.end()
    raise ValueError(f"unclosed <{tag}> at offset {start}")


def remove_visual_blocks(content: str) -> str:
    while True:
        m = VISUAL_ATTR.search(content)
        if not m:
            return content
        end = _element_end(content, m.start(), m.group(1).lower())
        start = m.start() - 1 if m.start() > 0 and content[m.start() - 1] == "\n" else m.start()
        content = content[:start] + content[end:]


def visual_elements(content: str, image_id: str) -> list[tuple[str, str]]:
    out, pos = [], 0
    while True:
        m = VISUAL_ATTR.search(content, pos)
        if not m:
            return out
        tag = m.group(1).lower()
        end = _element_end(content, m.start(), tag)
        if m.group(2) == image_id:
            out.append((tag, content[m.start():end]))
        pos = end


def section_text(content: str, sec: Section) -> str:
    span = remove_visual_blocks(content[sec.start:sec.end])
    kept: list[str] = []

    def stash(m: re.Match) -> str:
        kept.append(html.unescape(TAG.sub("", m.group(1))).strip("\n"))
        return f"\x00{len(kept) - 1}\x00"

    span = PRE.sub(stash, span)
    span = html.unescape(TAG.sub(" ", BLOCK_BREAK.sub("\n", span)))
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in span.split("\n")]
    joined = "\n".join(ln for ln in lines if ln)
    return re.sub(r"\x00(\d+)\x00", lambda m: "\n" + kept[int(m.group(1))] + "\n", joined).strip()


def fixture_text(content: str) -> str:
    parts = [html.unescape(s).strip() for s in SEED.findall(content)]
    for m in DEMO.finditer(content):
        block = content[m.start():_element_end(content, m.start(), "div")]
        parts.append(re.sub(r"[ \t]+", " ", html.unescape(TAG.sub(" ", BLOCK_BREAK.sub("\n", block)))).strip())
    return "\n".join(p for p in parts if p)


def section_fingerprint(content: str, number: int, heading: str) -> str:
    clean = remove_visual_blocks(content)
    sec = find_section(clean, number, heading)
    return hashlib.sha256(clean[sec.start:sec.end].encode("utf-8")).hexdigest()[:16]
```

- [ ] **Step 4: Run tests to verify they pass, then the whole suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_lessonhtml_v2.py && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: `5 passed`, then `59 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/lessonhtml.py skills/nerdit-lesson-illustrator/scripts/test_lessonhtml_v2.py
git commit -m "feat(illustrator): full-section text, fixtures, fingerprints and v2 block removal

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Full target-section dump in the outline tool

**Files:**
- Modify: `skills/nerdit-lesson-illustrator/scripts/extract_outline.py`
- Test: `skills/nerdit-lesson-illustrator/scripts/test_extract_outline_full.py`

**Interfaces:**
- Consumes: `remove_visual_blocks`, `section_text`, `fixture_text`, `section_fingerprint`, `sections` (Task 1)
- Produces: `full_section(course: dict, lesson_id: str, number: int) -> str` (raises `KeyError`); CLI flag `--full <lesson-id>:<section-number>` (exit 2 on unknown lesson/section)

- [ ] **Step 1: Write the failing tests**

```python
import json
import os
import subprocess
import sys

import pytest

from extract_outline import full_section
from fixture_course import ANCHOR_1, course
from lessonhtml import section_fingerprint

SCRIPT = os.path.join(os.path.dirname(__file__), "extract_outline.py")


def test_full_section_prints_context_text_and_fingerprint():
    out = full_section(course(), "load-basics-01", 1)
    fp = section_fingerprint(course()["lessons"][0]["content"], 1, "1 — What a load does")
    assert "COURSE Test Course" in out and "LESSON load-basics-01 Load Basics" in out
    assert "SECTION 1 1 — What a load does" in out and f"FINGERPRINT {fp}" in out
    assert ANCHOR_1 in out
    with pytest.raises(KeyError):
        full_section(course(), "load-basics-01", 9)


def test_cli_full_unknown_lesson_exits_2(tmp_path):
    src = tmp_path / "course.json"
    src.write_text(json.dumps(course(), ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "--course", str(src), "--full", "nope:1"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2 and "unknown lesson nope" in r.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_extract_outline_full.py`
Expected: FAIL — `ImportError: cannot import name 'full_section' from 'extract_outline'`

- [ ] **Step 3: Implement**

Change the import line of `extract_outline.py` to:

```python
from lessonhtml import (FIG_CAPTION, PRACTICE, SVG, fixture_text, img_sources, remove_visual_blocks,
                        section_fingerprint, section_text, sections, text, top_paragraphs)
```

Add above `def main`:

```python
def full_section(course: dict, lesson_id: str, number: int) -> str:
    lesson = next((l for l in course.get("lessons", []) if l["id"] == lesson_id), None)
    if lesson is None:
        raise KeyError(f"unknown lesson {lesson_id}")
    content = remove_visual_blocks(lesson.get("content") or "")
    sec = next((s for s in sections(content) if s.number == number), None)
    if sec is None:
        raise KeyError(f"lesson {lesson_id} has no section {number}")
    out = [f"COURSE {course.get('title', '')}",
           f"LESSON {lesson_id} {lesson.get('title', '')}",
           f"SECTION {sec.number} {sec.heading}",
           f"FINGERPRINT {section_fingerprint(content, sec.number, sec.heading)}",
           "---- SECTION TEXT ----", section_text(content, sec)]
    fixture = fixture_text(content)
    if fixture:
        out += ["---- FIXTURE ----", fixture]
    return "\n".join(out)
```

In `main()`, add `ap.add_argument("--full", help="<lesson-id>:<section-number>")` and, right after the course JSON is loaded (load it into `course` first, then compute `lessons = outline(course)`), insert:

```python
    if args.full:
        lesson_id, _, number = args.full.rpartition(":")
        try:
            print(full_section(course, lesson_id, int(number)))
        except (KeyError, ValueError) as e:
            print(f"error: {e}")
            return 2
        return 0
```

- [ ] **Step 4: Run tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_extract_outline_full.py test_extract_outline.py`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/extract_outline.py skills/nerdit-lesson-illustrator/scripts/test_extract_outline_full.py
git commit -m "feat(illustrator): --full dumps one section with its fixture and fingerprint

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Manifest v2 — the visual brief

**Files:**
- Modify: `skills/nerdit-lesson-illustrator/references/style.md` (style block only; prose is Task 9)
- Modify: `skills/nerdit-lesson-illustrator/scripts/manifest.py`
- Modify: `skills/nerdit-lesson-illustrator/scripts/fixture_course.py` (add `PLAN_V2`)
- Test: `skills/nerdit-lesson-illustrator/scripts/test_manifest_v2.py`

**Interfaces:**
- Consumes: Task 1 helpers, v1 `add_slots`/`validate`/`render_prompts`/`record_checks`
- Produces:
  - constants `KINDS = ("diagram", "illustration")`, `MARKERS = "①②③④⑤"`
  - `style_block(labels: list[str], markers: int = 0, path: Path = STYLE_FILE) -> str` (still accepts legacy `{labels_clause}` files)
  - `add_slots_v2(m: dict, course: dict, plan: dict, replan: str | None = None) -> list[str]`
  - `build_prompt(m: dict, slot: dict) -> str` (illustrations only)
  - v2 slot fields: `version` (2), `kind`, `question`, `objective`, `sourceRefs`, `knownTerms`, `newTerms`, `labels`, `takeaway`, `misconception`, `intro`, `caption`, `alt`, `explanation` (list), `checkQuestion` (`question`, `answer`, `reasoning`), `subject`, `sourceFingerprint`, plus all v1 bookkeeping fields. Diagram ids `<lesson>-fig<N>`, request `<id>.svg` in `images/diagrams/`; illustration ids `<lesson>-img<N>`, request `<id>.png` in `images/incoming/`.
  - manifest `course.cast` (Addition 4)

- [ ] **Step 1: Replace the style block in `references/style.md`**

Replace everything between the opening ```` ```style ```` fence and its closing fence with:

```text
Style: clean flat educational illustration, simple shapes, soft shadows, plain light background, one idea per picture, plenty of empty space.
Colours: navy #0B1F3A, teal #14B8A6, light background #EEF3F9 and white, with at most one warm highlight colour.
Format: landscape 4:3 unless the scene needs another shape. Any label or marker is large, bold and readable on a phone screen.
Text: {text_clause}
People, if any: Indian people in Indian settings. No real brands, companies or celebrities.
```

- [ ] **Step 2: Add `PLAN_V2` to `fixture_course.py`**

```python
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
```

- [ ] **Step 3: Write the failing tests**

```python
import copy

from fixture_course import PLAN, PLAN_V2, course
from lessonhtml import section_fingerprint
from manifest import (add_slots, add_slots_v2, new_manifest, record_checks, render_prompts,
                      style_block, validate)


def planned_v2():
    m = new_manifest(course(), "course.json")
    assert add_slots_v2(m, course(), copy.deepcopy(PLAN_V2)) == []
    return m


def test_v2_slots_get_kind_specific_ids_files_and_fingerprint():
    m = planned_v2()
    d, i = m["images"]
    assert (d["id"], d["requestFile"], d["outputFile"]) == (
        "load-basics-01-fig1", "load-basics-01-fig1.svg", "load-basics-01-fig1.svg")
    assert (i["id"], i["requestFile"], i["outputFile"]) == (
        "old-style-02-img1", "old-style-02-img1.png", "old-style-02-img1.webp")
    assert d["version"] == 2 and d["prompt"] == ""
    assert d["sourceFingerprint"] == section_fingerprint(course()["lessons"][0]["content"], 1, "1 — What a load does")
    assert m["course"]["cast"].startswith("Asha")


def test_v2_illustration_prompt_carries_context_cast_and_markers():
    p = planned_v2()["images"][1]["prompt"]
    assert "Course: Test Course" in p and "Lesson: Old Style" in p and "Section: Introduction" in p
    assert "Learning objective: Picture a student" in p and "Recurring characters and setting: Asha" in p
    assert "place ① on the part showing: The student opens the notebook." in p
    assert "no words, letters or numbers except the numbered markers ① ②." in p
    assert "{text_clause}" not in p


def test_v2_label_absent_from_lesson_is_refused():
    plan = copy.deepcopy(PLAN_V2)
    plan["items"][0]["labels"] = ["warehouse", "revenue"]
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(), plan)
    assert any("labels not found in the section or its fixture: ['revenue']" in e for e in errors)


def test_v2_incomplete_check_question_and_missing_fields_are_refused():
    plan = copy.deepcopy(PLAN_V2)
    plan["items"][0]["checkQuestion"] = {"question": "Q?", "answer": "", "reasoning": "R"}
    del plan["items"][1]["subject"]
    errors = add_slots_v2(new_manifest(course(), "c.json"), course(), plan)
    assert any("checkQuestion needs question, answer and reasoning" in e for e in errors)
    assert any("missing subject" in e for e in errors)


def test_v1_and_v2_slots_coexist_and_v2_has_no_quota():
    m = new_manifest(course(), "c.json")
    assert add_slots(m, course(), [PLAN[1]]) == []
    plan = copy.deepcopy(PLAN_V2)
    plan["items"] = [plan["items"][0]] * 4
    assert add_slots_v2(m, course(), plan) == []
    assert validate(m) == []
    assert [s["id"] for s in m["images"]][-1] == "load-basics-01-fig4"


def test_render_lists_diagrams_to_draw_and_record_rebuilds_v2_prompt():
    m = planned_v2()
    out = render_prompts(m)
    assert "## Diagrams to draw" in out and "diagrams/load-basics-01-fig1.svg" in out
    assert "### old-style-02-img1.png" in out
    m["images"][1]["status"] = "converted"
    assert record_checks(m, [{"id": "old-style-02-img1", "result": "fail", "reason": "Too busy.",
                              "revisedSubject": "One student, one notebook, nothing else."}]) == []
    assert "One student, one notebook, nothing else." in m["images"][1]["prompt"]
    assert "Course: Test Course" in m["images"][1]["prompt"]
    assert style_block(["A"], 2).endswith(
        'People, if any: Indian people in Indian settings. No real brands, companies or celebrities.')
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_manifest_v2.py`
Expected: FAIL — `ImportError: cannot import name 'PLAN_V2' from 'fixture_course'` until Step 2 is saved, then `ImportError: cannot import name 'add_slots_v2' from 'manifest'`

- [ ] **Step 5: Implement in `manifest.py`**

Change the lessonhtml import to:

```python
from lessonhtml import (AnchorNotFound, find_section, fixture_text, locate, remove_visual_blocks,
                        section_fingerprint, section_text)
```

Add constants under `PLAN_KEYS`:

```python
KINDS = ("diagram", "illustration")
MARKERS = "①②③④⑤"
V2_KEYS = ("lessonId", "section", "heading", "position", "kind", "question", "objective", "takeaway",
           "misconception", "intro", "caption", "alt", "explanation", "checkQuestion")
```

Replace `style_block` with:

```python
def style_block(labels: list[str], markers: int = 0, path: Path = STYLE_FILE) -> str:
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.search(r"```style\n(.*?)\n```", raw, re.S)
    if not m:
        raise RuntimeError(f"no ```style block in {path}")
    block = m.group(1)
    if "{labels_clause}" in block:  # legacy v1 style file
        clause = (", except these exact labels: " + ", ".join(f'"{l}"' for l in labels)) if labels else ""
        return block.replace("{labels_clause}", clause)
    allowed = []
    if labels:
        allowed.append("these exact labels: " + ", ".join(f'"{l}"' for l in labels))
    if markers:
        allowed.append("the numbered markers " + " ".join(MARKERS[:markers]))
    clause = ("no words, letters or numbers except " + "; and ".join(allowed) + ".") if allowed \
        else "no words, letters or numbers at all."
    return block.replace("{text_clause}", clause)
```

Add `build_prompt`, `_validate_v2` and `add_slots_v2` above `render_prompts`:

```python
def build_prompt(m: dict, s: dict) -> str:
    lines = ["Educational illustration for a student meeting this topic for the first time.",
             f"Course: {m['course']['title']}", f"Lesson: {s['lessonTitle']}",
             f"Section: {s['section']['heading']}", f"Learning objective: {s['objective']}",
             f"Question it answers: {s['question']}"]
    if m["course"].get("cast"):
        lines.append(f"Recurring characters and setting: {m['course']['cast']}")
    steps = s["explanation"]
    marks = MARKERS[:len(steps)] if len(steps) >= 2 else ""
    body = [s["subject"].strip()]
    if marks:
        body.append("Numbered markers: " + "; ".join(
            f"place {mk} on the part showing: {st}" for mk, st in zip(marks, steps)))
    return "\n".join(lines) + "\n\n" + "\n".join(body) + "\n\n" + style_block(s["labels"], len(marks))


def _validate_v2(s: dict) -> list[str]:
    where, errors = s["id"], []
    if s.get("kind") not in KINDS:
        errors.append(f"{where}: unknown kind {s.get('kind')}")
    for key in ("question", "objective", "takeaway", "misconception", "intro", "caption", "alt"):
        if not str(s.get(key) or "").strip():
            errors.append(f"{where}: empty {key}")
    if len(s.get("alt") or "") > 150:
        errors.append(f"{where}: alt is over 150 characters")
    if not 1 <= len(s.get("explanation") or []) <= len(MARKERS):
        errors.append(f"{where}: explanation needs 1-{len(MARKERS)} steps")
    cq = s.get("checkQuestion") or {}
    if not all(str(cq.get(k) or "").strip() for k in ("question", "answer", "reasoning")):
        errors.append(f"{where}: checkQuestion needs question, answer and reasoning")
    return errors


def add_slots_v2(m: dict, course: dict, plan: dict, replan: str | None = None) -> list[str]:
    lessons = {l["id"]: l for l in course.get("lessons", [])}
    if plan.get("cast") is not None:
        m["course"]["cast"] = plan["cast"]
    if replan:
        m["images"] = [s for s in m["images"] if s["lessonId"] != replan]
    already = {s["lessonId"] for s in m["images"]}
    m["styleVersion"] = 2
    errors, added = [], set()
    for i, p in enumerate(plan.get("items", []), 1):
        where = f"plan item {i}"
        missing = [k for k in V2_KEYS if p.get(k) in (None, "", [], {})]
        if p.get("position") == "after-explanation" and not p.get("anchor"):
            missing.append("anchor")
        if p.get("kind") == "diagram":
            missing += [k for k in ("labels", "sourceRefs") if not p.get(k)]
        if p.get("kind") == "illustration" and not p.get("subject"):
            missing.append("subject")
        if missing:
            errors.append(f"{where}: missing {', '.join(missing)}")
            continue
        lid = p["lessonId"]
        if lid not in lessons:
            errors.append(f"{where}: unknown lesson {lid}")
            continue
        if lid in already and lid not in added:
            errors.append(f"{where}: {lid} is already planned; use --replan {lid}")
            continue
        if p["position"] not in POSITIONS or p["kind"] not in KINDS:
            errors.append(f"{where}: unknown position or kind")
            continue
        content = remove_visual_blocks(lessons[lid].get("content") or "")
        try:
            locate(content, p["section"], p["heading"], p["position"], p.get("anchor") or None)
        except AnchorNotFound as e:
            errors.append(f"{where}: {e}")
            continue
        if p["kind"] == "diagram":
            source = section_text(content, find_section(content, p["section"], p["heading"])) \
                + "\n" + fixture_text(content)
            absent = [l for l in p["labels"] if l not in source]
            if absent:
                errors.append(f"{where}: labels not found in the section or its fixture: {absent}")
                continue
        diagram = p["kind"] == "diagram"
        n = 1 + sum(1 for s in m["images"] if s["lessonId"] == lid and s.get("kind", "illustration") == p["kind"])
        image_id = f"{lid}-{'fig' if diagram else 'img'}{n}"
        slot = {
            "version": 2, "id": image_id, "lessonId": lid, "lessonTitle": lessons[lid].get("title", ""),
            "section": {"number": p["section"], "heading": p["heading"]},
            "position": p["position"], "anchor": p.get("anchor") or "", "kind": p["kind"],
            "question": p["question"], "objective": p["objective"], "reason": p["objective"],
            "sourceRefs": list(p.get("sourceRefs") or []), "knownTerms": list(p.get("knownTerms") or []),
            "newTerms": list(p.get("newTerms") or []), "labels": list(p.get("labels") or []),
            "takeaway": p["takeaway"], "misconception": p["misconception"], "intro": p["intro"],
            "caption": p["caption"], "alt": p["alt"], "explanation": list(p["explanation"]),
            "checkQuestion": dict(p["checkQuestion"]), "subject": p.get("subject", ""),
            "sourceFingerprint": section_fingerprint(content, p["section"], p["heading"]),
            "requestFile": f"{image_id}.{'svg' if diagram else 'png'}",
            "outputFile": f"{image_id}.{'svg' if diagram else 'webp'}",
            "aspect": "fit" if diagram else "4:3", "prompt": "",
            "status": "planned", "check": {"result": None, "reason": None},
            "sourceSha256": None, "bytes": None, "width": None, "height": None,
        }
        if not diagram:
            slot["prompt"] = build_prompt(m, slot)
        errors += _validate_v2(slot)
        m["images"].append(slot)
        added.add(lid)
    return list(dict.fromkeys(errors + validate(m)))
```

Replace the body of `validate` so v2 slots use `_validate_v2` and only v1 slots count toward the quota:

```python
def validate(m: dict) -> list[str]:
    errors, ids, outputs, per_lesson = [], set(), set(), {}
    for s in m.get("images", []):
        where = s.get("id", "?")
        if s["id"] in ids:
            errors.append(f"{where}: duplicate id")
        ids.add(s["id"])
        if s["outputFile"] in outputs:
            errors.append(f"{where}: duplicate output file {s['outputFile']}")
        outputs.add(s["outputFile"])
        if s["status"] not in STATUSES:
            errors.append(f"{where}: unknown status {s['status']}")
        if s["position"] not in POSITIONS:
            errors.append(f"{where}: unknown position {s['position']}")
        if s.get("version") == 2:
            errors += _validate_v2(s)
            continue
        for key in ("reason", "prompt", "alt", "caption"):
            if not str(s.get(key) or "").strip():
                errors.append(f"{where}: empty {key}")
        if len(s.get("alt") or "") > 125:
            errors.append(f"{where}: alt is over 125 characters")
        if len((s.get("caption") or "").split()) > 15:
            errors.append(f"{where}: caption is over 15 words")
        per_lesson[s["lessonId"]] = per_lesson.get(s["lessonId"], 0) + 1
    for lid, n in per_lesson.items():
        if n > MAX_PER_LESSON:
            errors.append(f"{lid}: {n} images, more than {MAX_PER_LESSON}")
    return errors
```

In `render_prompts`, make `todo` exclude diagrams and add the diagrams section after the "To generate" loop:

```python
    todo = [s for s in m["images"] if s["status"] == "planned" and s.get("kind") != "diagram"]
```

```python
    draw = [s for s in m["images"] if s["status"] in ("planned", "failed") and s.get("kind") == "diagram"]
    if draw:
        out += ["## Diagrams to draw", "",
                "Claude writes each as inline SVG from the section and fixture (figures.md rules).", ""]
        for s in draw:
            out += [f"### diagrams/{s['requestFile']}", f"Objective: {s['objective']}",
                    f"Labels (exact): {', '.join(s['labels'])}",
                    f"Markers: {MARKERS[:len(s['explanation'])] if len(s['explanation']) >= 2 else 'none'}",
                    f"Source: {'; '.join(s['sourceRefs'])}", ""]
```

In `record_checks`, replace the `revisedSubject` branch with:

```python
            if r.get("revisedSubject"):
                if s.get("version") == 2:
                    s["subject"] = r["revisedSubject"].strip()
                    s["prompt"] = build_prompt(m, s) if s["kind"] == "illustration" else ""
                else:
                    s["prompt"] = r["revisedSubject"].strip() + "\n\n" + style_block(s["labels"])
```

In `main()`'s `add` branch, choose the adder by plan type and create the diagrams folder:

```python
        adder = add_slots_v2 if isinstance(plan, dict) else add_slots
        errors = adder(m, course, plan, args.replan)
```

and after `(images_dir / "incoming").mkdir(exist_ok=True)` add `(images_dir / "diagrams").mkdir(exist_ok=True)`.

- [ ] **Step 6: Run the manifest suites**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_manifest.py test_manifest_checks.py test_manifest_v2.py`
Expected: `18 passed`

- [ ] **Step 7: Commit**

```bash
git add skills/nerdit-lesson-illustrator/references/style.md skills/nerdit-lesson-illustrator/scripts/manifest.py skills/nerdit-lesson-illustrator/scripts/fixture_course.py skills/nerdit-lesson-illustrator/scripts/test_manifest_v2.py
git commit -m "feat(illustrator): v2 visual brief with diagram and illustration kinds

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: SVG diagram checks and phone previews

**Files:**
- Create: `skills/nerdit-lesson-illustrator/scripts/svgcheck.py`
- Modify: `skills/nerdit-lesson-illustrator/scripts/convert_images.py`
- Test: `skills/nerdit-lesson-illustrator/scripts/test_svgcheck.py`

**Interfaces:**
- Consumes: `lessonhtml.text`; manifest v2 slots
- Produces:
  - `check_svg(svg: str, labels: list[str], steps: int) -> list[str]`
  - `convert_all` also processes diagram slots from `images/diagrams/` (status `converted` when `check_svg` passes) and writes `preview/<id>-phone.jpg` (360 px) for raster images; constant `PHONE_WIDTH = 360`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_svgcheck.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'svgcheck'`

- [ ] **Step 3: Create `svgcheck.py`**

```python
"""Check an inline SVG diagram against the lesson figure contract (CORE.md §7/§7b, figures.md)."""
from __future__ import annotations

import re

from lessonhtml import text

HEX = re.compile(r"(?<!&)#[0-9a-fA-F]{3,8}\b")
MARKER_CHARS = "①②③④⑤"


def check_svg(svg: str, labels: list[str], steps: int) -> list[str]:
    m = re.match(r"\s*<svg\b([^>]*)>", svg, re.S)
    if not m:
        return ["not an <svg> element"]
    attrs, errors = m.group(1), []
    if "viewBox=" not in attrs:
        errors.append("svg has no viewBox")
    if not re.search(r'\brole="img"', attrs):
        errors.append('svg needs role="img"')
    if not re.search(r'\baria-label="[^"]+"', attrs):
        errors.append("svg has no aria-label")
    if re.search(r'\b(?:width|height)="', attrs):
        errors.append("svg must not set width/height (viewBox only)")
    if HEX.search(svg):
        errors.append("hex colour in svg - use var(--token)")
    drawn = " ".join(text(t) for t in re.findall(r"<text\b[^>]*>(.*?)</text>", svg, re.S))
    for label in labels:
        if label not in drawn:
            errors.append(f"label '{label}' is not drawn as <text>")
    markers = sum(drawn.count(c) for c in MARKER_CHARS)
    if steps >= 2 and markers != steps:
        errors.append(f"{markers} numbered markers drawn, {steps} reading steps written")
    return errors
```

- [ ] **Step 4: Extend `convert_images.py`**

Add `from svgcheck import check_svg` to the imports and `PHONE_WIDTH = 360` to the constants. Change `_write_preview` to take a width:

```python
def _write_preview(webp: bytes, dst: Path, width: int = PREVIEW_WIDTH) -> None:
    with Image.open(BytesIO(webp)) as im:
        img = im.convert("RGBA")
    flat = Image.new("RGB", img.size, (255, 255, 255))
    flat.paste(img, mask=img.split()[3])
    _scaled(flat, width).save(dst, "JPEG", quality=80)
```

In `find_incoming`, build `wanted` from raster slots only:

```python
    wanted = {Path(s["requestFile"]).stem.lower(): s["id"] for s in m["images"] if s.get("kind") != "diagram"}
```

and compute `missing` over raster slots only (`... if s.get("kind") != "diagram" and ...`).

In `convert_all`, after the existing raster loop writes its preview, also write the phone preview:

```python
        _write_preview(data, images_dir / "preview" / f"{image_id}-phone.jpg", PHONE_WIDTH)
```

and before `return report` add the diagram loop:

```python
    for slot in m["images"]:
        if slot.get("kind") != "diagram" or slot["status"] == "inserted":
            continue
        f = images_dir / "diagrams" / slot["requestFile"]
        if not f.is_file():
            if slot["status"] in ("planned", "failed"):
                report["missing"].append(slot["id"])
            continue
        svg = f.read_text(encoding="utf-8")
        sha = hashlib.sha256(svg.encode("utf-8")).hexdigest()
        if sha == slot.get("sourceSha256") and slot["status"] != "planned":
            report["unchanged"].append(slot["id"])
            continue
        problems = check_svg(svg, slot["labels"], len(slot["explanation"]))
        if problems:
            report["errors"] += [f"{f.name}: {p}" for p in problems]
            continue
        slot.update(status="converted", sourceSha256=sha, bytes=len(svg.encode("utf-8")))
        slot["check"] = {"result": None, "reason": None}
        report["converted"].append(slot["id"])
```

- [ ] **Step 5: Run tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_svgcheck.py test_convert_images.py`
Expected: `13 passed`

- [ ] **Step 6: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/svgcheck.py skills/nerdit-lesson-illustrator/scripts/convert_images.py skills/nerdit-lesson-illustrator/scripts/test_svgcheck.py
git commit -m "feat(illustrator): SVG diagram contract check and phone-size previews

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Insert v2 teaching blocks

**Files:**
- Modify: `skills/nerdit-lesson-illustrator/scripts/insert_images.py`
- Test: `skills/nerdit-lesson-illustrator/scripts/test_insert_v2.py`

**Interfaces:**
- Consumes: `remove_visual_blocks` (Task 1), `MARKERS` (Task 3), v2 slots
- Produces:
  - `blocks_v2(slot: dict, svg: str | None) -> str`
  - `insert_lessons(course: dict, m: dict, diagrams_dir: Path | None = None) -> list[str]` — v1 slots unchanged; v2 diagram slots read `diagrams_dir / slot["requestFile"]`
  - `strip_inserted` now delegates to `remove_visual_blocks`

- [ ] **Step 1: Write the failing tests**

```python
import copy

from fixture_course import PLAN_V2, course
from insert_images import insert_lessons, strip_inserted
from manifest import add_slots_v2, new_manifest

SVG = ('<svg viewBox="0 0 200 80" role="img" aria-label="Checked rows reach the warehouse">'
       '<text x="10" y="20" fill="var(--nb)">① warehouse</text>'
       '<text x="10" y="50" fill="var(--orange)">② run log</text></svg>')


def ready(tmp_path):
    m = new_manifest(course(), "c.json")
    assert add_slots_v2(m, course(), copy.deepcopy(PLAN_V2)) == []
    for s in m["images"]:
        s.update(status="passed", width=1200, height=900)
    (tmp_path / "load-basics-01-fig1.svg").write_text(SVG, encoding="utf-8")
    return m


def test_v2_diagram_block_has_intro_figure_steps_and_check(tmp_path):
    c, m = course(), ready(tmp_path)
    assert insert_lessons(c, m, tmp_path) == []
    html = c["lessons"][0]["content"]
    assert ('totals 📦.</p>\n<p class="nerdit-visual-intro" data-nerdit-img="load-basics-01-fig1">'
            'Follow the rows from left to right.</p>') in html
    assert '<div class="nerdit-figure" data-nerdit-img="load-basics-01-fig1">\n  <svg viewBox' in html
    assert ('<ol class="nerdit-visual-read" data-nerdit-img="load-basics-01-fig1" '
            'style="list-style:none;padding-left:0"><li>① The rows arrive in the warehouse.</li>'
            '<li>② The run log records the run.</li></ol>') in html
    assert '<div class="nerdit-predict" data-nerdit-img="load-basics-01-fig1">' in html
    assert "Does the load change the row values?" in html
    old = c["lessons"][1]["content"]
    assert '<img src="old-style-02-img1.webp" alt="A student opens a notebook beside a laptop."' in old
    assert all(s["status"] == "inserted" for s in m["images"])


def test_v2_reinsert_is_idempotent_and_strip_restores(tmp_path):
    c, m = course(), ready(tmp_path)
    insert_lessons(c, m, tmp_path)
    once = copy.deepcopy(c)
    insert_lessons(c, m, tmp_path)
    assert c == once
    assert [strip_inserted(l["content"]) for l in c["lessons"]] == [l["content"] for l in course()["lessons"]]


def test_v2_missing_diagram_file_fails_only_that_slot(tmp_path):
    c, m = course(), ready(tmp_path)
    (tmp_path / "load-basics-01-fig1.svg").unlink()
    errors = insert_lessons(c, m, tmp_path)
    assert len(errors) == 1 and "load-basics-01-fig1.svg" in errors[0]
    assert m["images"][1]["status"] == "inserted"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_insert_v2.py`
Expected: FAIL — `TypeError: insert_lessons() takes 2 positional arguments but 3 were given`

- [ ] **Step 3: Implement in `insert_images.py`**

Add to the imports: `from lessonhtml import AnchorNotFound, locate, remove_visual_blocks` (replacing the old lessonhtml import) and `from manifest import MARKERS`.

Replace `strip_inserted` with:

```python
def strip_inserted(content: str) -> str:
    return remove_visual_blocks(content)
```

Add `blocks_v2` below `block`:

```python
def blocks_v2(slot: dict, svg: str | None) -> str:
    vid, esc = slot["id"], (lambda s: html.escape(s, quote=False))
    if slot["kind"] == "diagram":
        figure = svg.strip()
    else:
        figure = (f'<img src="{slot["outputFile"]}" alt="{html.escape(slot["alt"], quote=True)}" '
                  f'width="{slot["width"]}" height="{slot["height"]}" loading="lazy" decoding="async" '
                  'style="display:block;width:100%;height:auto">')
    out = [f'\n<p class="nerdit-visual-intro" data-nerdit-img="{vid}">{esc(slot["intro"])}</p>',
           f'\n<div class="nerdit-figure" data-nerdit-img="{vid}">\n  {figure}\n'
           f'  <div class="nerdit-figure-caption">{esc(slot["caption"])}</div>\n</div>']
    steps = slot["explanation"]
    marks = MARKERS[:len(steps)] if len(steps) >= 2 else [""] * len(steps)
    items = "".join(f"<li>{(mk + ' ') if mk else ''}{esc(st)}</li>" for mk, st in zip(marks, steps))
    out.append(f'\n<ol class="nerdit-visual-read" data-nerdit-img="{vid}" '
               f'style="list-style:none;padding-left:0">{items}</ol>')
    cq = slot["checkQuestion"]
    out.append(f'\n<div class="nerdit-predict" data-nerdit-img="{vid}">'
               '<div class="nerdit-predict-head">🤔 Try It — read the figure</div>'
               f'<p>{esc(cq["question"])}</p><details class="nerdit-predict-answer"><summary>Show answer</summary>'
               f'<p>{esc(cq["answer"])} {esc(cq["reasoning"])}</p></details></div>')
    return "".join(out)
```

Change `insert_lessons` to accept `diagrams_dir` and choose the renderer per slot. Replace its signature and placement loop with:

```python
def insert_lessons(course: dict, m: dict, diagrams_dir: Path | None = None) -> list[str]:
    errors = []
    by_lesson: dict[str, list[dict]] = {}
    for s in m["images"]:
        if s["status"] in ("passed", "inserted"):
            by_lesson.setdefault(s["lessonId"], []).append(s)
    known = set()
    for lesson in course.get("lessons", []):
        known.add(lesson["id"])
        content = strip_inserted(lesson.get("content") or "")
        placed = []
        for s in by_lesson.get(lesson["id"], []):
            try:
                off = locate(content, s["section"]["number"], s["section"]["heading"],
                             s["position"], s["anchor"] or None)
            except AnchorNotFound as e:
                errors.append(f"{s['id']}: {e}; re-plan with --replan {s['lessonId']}")
                s["status"] = "passed"
                continue
            if s.get("version") == 2:
                svg = None
                if s["kind"] == "diagram":
                    f = Path(diagrams_dir or ".") / s["requestFile"]
                    if not f.is_file():
                        errors.append(f"{s['id']}: diagram file {s['requestFile']} not found")
                        s["status"] = "passed"
                        continue
                    svg = f.read_text(encoding="utf-8")
                markup = blocks_v2(s, svg)
            else:
                markup = block(s)
            placed.append((off, s, markup))
        for off, s, markup in sorted(placed, key=lambda p: (p[0], p[1]["id"]), reverse=True):
            content = content[:off] + markup + content[off:]
            s["status"] = "inserted"
        lesson["content"] = content
    for lid, slots in by_lesson.items():
        if lid not in known:
            errors += [f"{s['id']}: lesson {lid} is not in this course" for s in slots]
    return errors
```

In `build_output`, call `insert_lessons(work, m, images_dir / "diagrams")`.

- [ ] **Step 4: Run tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_insert_v2.py test_insert_images.py`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/insert_images.py skills/nerdit-lesson-illustrator/scripts/test_insert_v2.py
git commit -m "feat(illustrator): insert v2 teaching blocks as data-nerdit-img siblings

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: v2 validation, stale-section detection and the end-to-end apply

**Files:**
- Modify: `skills/nerdit-lesson-illustrator/scripts/check_images.py`
- Test: `skills/nerdit-lesson-illustrator/scripts/test_check_v2.py`

**Interfaces:**
- Consumes: `visual_elements`, `section_fingerprint`, `section_text`, `fixture_text`, `find_section`, `remove_visual_blocks` (Task 1), `check_svg` (Task 4), `build_output` (v1 Task 9)
- Produces: `check()` validates v2 inserted slots: all four siblings present, caption and intro non-empty, step count equals list items, markers agree, SVG contract, raster attributes and size, diagram labels still in the lesson, and `sourceFingerprint` unchanged (else a re-review error)

- [ ] **Step 1: Write the failing tests**

```python
import copy
import json

from PIL import Image

from check_images import check
from convert_images import convert_all
from fixture_course import PLAN_V2, course
from insert_images import build_output, insert_lessons, output_path
from manifest import add_slots_v2, load, new_manifest, record_checks, save

SVG = ('<svg viewBox="0 0 200 80" role="img" aria-label="Checked rows reach the warehouse">'
       '<text x="10" y="20" fill="var(--nb)">① warehouse</text>'
       '<text x="10" y="50" fill="var(--orange)">② run log</text></svg>')


def setup(tmp_path, content_edit=None):
    src = tmp_path / "course-test_output.json"
    src.write_text(json.dumps(course(), ensure_ascii=False, indent=2), encoding="utf-8")
    images = tmp_path / "images"
    for d in ("incoming", "diagrams", "upload"):
        (images / d).mkdir(parents=True)
    m = new_manifest(course(), src.name)
    assert add_slots_v2(m, course(), copy.deepcopy(PLAN_V2)) == []
    (images / "diagrams" / "load-basics-01-fig1.svg").write_text(SVG, encoding="utf-8")
    Image.new("RGB", (1600, 1200), (238, 243, 249)).save(images / "incoming" / "old-style-02-img1.png")
    assert convert_all(m, images)["errors"] == []
    assert record_checks(m, [{"id": s["id"], "result": "pass", "reason": "ok"} for s in m["images"]]) == []
    save(images, m)
    if content_edit:
        c = course()
        c["lessons"][0]["content"] = c["lessons"][0]["content"].replace(*content_edit)
        src.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    return src, images


def tiny(url):
    return b"tiny"


def test_v2_valid_output_is_written(tmp_path):
    src, images = setup(tmp_path)
    assert build_output(src, images, fetch=tiny) == 0
    data = json.loads(output_path(src).read_text(encoding="utf-8"))
    assert 'class="nerdit-visual-read"' in data["lessons"][0]["content"]
    assert [s["status"] for s in load(images)["images"]] == ["inserted", "inserted"]


def test_v2_running_twice_is_identical(tmp_path):
    src, images = setup(tmp_path)
    build_output(src, images, fetch=tiny)
    first = output_path(src).read_bytes()
    assert build_output(src, images, fetch=tiny) == 0
    assert output_path(src).read_bytes() == first


def test_stale_section_blocks_output(tmp_path, capsys):
    src, images = setup(tmp_path, content_edit=("only ever receives checked rows", "receives checked rows"))
    assert build_output(src, images, fetch=tiny) == 1
    assert "section changed since planning" in capsys.readouterr().out
    assert not output_path(src).exists()


def test_v2_missing_reading_step_is_an_error(tmp_path):
    src, images = setup(tmp_path)
    c, m = course(), load(images)
    insert_lessons(c, m, images / "diagrams")
    c["lessons"][0]["content"] = c["lessons"][0]["content"].replace(
        "<li>② The run log records the run.</li>", "")
    errors, _ = check(c, m, images / "upload")
    assert any("load-basics-01-fig1: 1 reading steps shown, 2 expected" in e for e in errors)


def test_v2_check_reports_missing_siblings(tmp_path):
    src, images = setup(tmp_path)
    c, m = course(), load(images)
    insert_lessons(c, m, images / "diagrams")
    content = c["lessons"][0]["content"]
    start = content.index('\n<p class="nerdit-visual-intro"')
    end = content.index("</p>", start) + 4
    c["lessons"][0]["content"] = content[:start] + content[end:]
    errors, _ = check(c, m, images / "upload")
    assert any("load-basics-01-fig1: missing intro paragraph" in e for e in errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_check_v2.py`
Expected: FAIL — `test_stale_section_blocks_output` and the two sibling tests fail (no v2 checks yet; `check` reports v2 slots as "marked inserted but not found")

- [ ] **Step 3: Implement in `check_images.py`**

Change the imports to:

```python
from lessonhtml import (IMG, SRC, AnchorNotFound, find_section, fixture_text, remove_visual_blocks,
                        section_fingerprint, section_text, text, visual_elements)
from svgcheck import check_svg
```

Add `_check_v2` above `check`:

```python
def _check_v2(lesson_content: str, slot: dict, upload_dir: Path) -> list[str]:
    where, errors = f"{slot['lessonId']}: {slot['id']}", []
    parts = visual_elements(lesson_content, slot["id"])
    by = {}
    for tag, el in parts:
        cls = re.search(r'\bclass="([^"]*)"', el)
        by[(cls.group(1) if cls else tag)] = el
    intro = by.get("nerdit-visual-intro")
    figure = by.get("nerdit-figure")
    steps = by.get("nerdit-visual-read")
    if intro is None or not text(intro):
        errors.append(f"{where}: missing intro paragraph")
    if figure is None:
        return errors + [f"{where}: missing figure"]
    if "nerdit-predict" not in by:
        errors.append(f"{where}: missing check question")
    cap = re.search(r'<div class="nerdit-figure-caption">(.*?)</div>', figure, re.S)
    if not cap or not text(cap.group(1)):
        errors.append(f"{where}: empty caption")
    shown = len(re.findall(r"<li\b", steps or ""))
    if shown != len(slot["explanation"]):
        errors.append(f"{where}: {shown} reading steps shown, {len(slot['explanation'])} expected")
    if slot["kind"] == "diagram":
        svg = re.search(r"<svg\b.*?</svg>", figure, re.S)
        errors += [f"{where}: {p}" for p in check_svg(svg.group(0) if svg else "", slot["labels"],
                                                      len(slot["explanation"]))]
    else:
        tag = (IMG.search(figure) or re.match("", "")).group(0)
        for need in ('loading="lazy"', 'decoding="async"'):
            if need not in tag:
                errors.append(f"{where}: missing {need}")
        f = upload_dir / slot["outputFile"]
        if not f.is_file():
            errors.append(f"{where}: {slot['outputFile']} not in upload/")
        elif f.stat().st_size > HARD:
            errors.append(f"{where}: {f.stat().st_size // 1000} KB, over 250 KB")
    try:
        fp = section_fingerprint(lesson_content, slot["section"]["number"], slot["section"]["heading"])
    except AnchorNotFound:
        return errors + [f"{where}: its section no longer exists; re-plan with --replan {slot['lessonId']}"]
    if fp != slot["sourceFingerprint"]:
        errors.append(f"{where}: section changed since planning; re-review the visual "
                      f"(--replan {slot['lessonId']})")
    if slot["kind"] == "diagram":
        clean = remove_visual_blocks(lesson_content)
        source = section_text(clean, find_section(clean, slot["section"]["number"], slot["section"]["heading"])) \
            + "\n" + fixture_text(clean)
        absent = [l for l in slot["labels"] if l not in source]
        if absent:
            errors.append(f"{where}: labels no longer in the lesson: {absent}")
    return errors
```

In `check`, collect v2 slots per lesson and validate them; v1 block parsing keeps its current behaviour for v1 slots only. Inside the per-lesson loop, after the existing `for bm in BLOCK.finditer(content):` block, add:

```python
        for s in m.get("images", []):
            if s.get("version") == 2 and s["lessonId"] == lid and s["status"] == "inserted":
                seen.add(s["id"])
                errors += _check_v2(content, s, upload_dir)
```

and in the v1 `BLOCK` loop, skip ids whose slot is v2 (`if slot is not None and slot.get("version") == 2: continue` right after `slot = slots.get(image_id)`).

- [ ] **Step 4: Run the whole illustrator suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: `80 passed` (54 baseline + 5 + 2 + 6 + 5 + 3 + 5)

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/check_images.py skills/nerdit-lesson-illustrator/scripts/test_check_v2.py
git commit -m "feat(illustrator): validate v2 teaching blocks and refuse stale sections

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: SQL example output checker (chapter generator)

**Files:**
- Create: `skills/nerdit-chapter-generator/scripts/check_sql_outputs.py`
- Test: `skills/nerdit-chapter-generator/scripts/test_check_sql_outputs.py`

**Interfaces:**
- Produces:
  - `parse_table(txt: str) -> list[list[str]] | None` — rows of an ASCII `+---+` table (header first), or `None`
  - `check_lesson(content: str) -> dict` — `{"examples", "match", "mismatch": [str], "unchecked": [str]}`
  - CLI `python check_sql_outputs.py --course <output.json> [--lesson <id>]`, exit 1 when any mismatch

- [ ] **Step 1: Write the failing tests**

```python
from check_sql_outputs import check_lesson, parse_table

SEED = ('<script type="text/plain" id="s1">CREATE TABLE t (city TEXT, amount INTEGER);'
        "INSERT INTO t VALUES ('Pune', 200), ('Mumbai', 100);</script>")


def run(sql, out):
    return ('<div class="nerdit-run"><div class="nerdit-in"><span class="nerdit-tag">You type</span>'
            f'<pre data-lang="sql"><code>{sql}</code></pre></div><div class="nerdit-out">'
            f'<span class="nerdit-tag">SQL shows</span><pre><code>{out}</code></pre></div></div>')


TABLE = "+--------+\n| total  |\n+--------+\n| 300    |\n+--------+"


def test_parse_table():
    assert parse_table(TABLE) == [["total"], ["300"]]
    assert parse_table("UNIQUE constraint failed") is None


def test_matching_output_counts_as_match():
    r = check_lesson(SEED + run("SELECT SUM(amount) AS total FROM t;", TABLE))
    assert (r["examples"], r["match"], r["mismatch"]) == (1, 1, [])


def test_mismatching_output_is_reported():
    r = check_lesson(SEED + run("SELECT SUM(amount) AS total FROM t WHERE city='Pune';", TABLE))
    assert r["match"] == 0 and "example 1" in r["mismatch"][0] and "200" in r["mismatch"][0]


def test_error_outputs_match_by_message_and_others_are_unchecked():
    html = (SEED + run("INSERT INTO nope VALUES (1);", "Error: no such table: nope")
            + run("CREATE INDEX i ON t(city);", "Index created."))
    r = check_lesson(html)
    assert r["match"] == 1 and len(r["unchecked"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/nerdit-chapter-generator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_check_sql_outputs.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'check_sql_outputs'`

- [ ] **Step 3: Implement**

```python
#!/usr/bin/env python3
"""Run every SQL example in a lesson against its seed data and compare with the shown output.

Usage: python check_sql_outputs.py --course <course-output.json> [--lesson <lesson-id>]

Each example runs on a fresh in-memory database built from the lesson's seed scripts; if it
fails because a table is missing, it is retried after the earlier examples. ASCII-table outputs
are compared cell by cell; an error output matches when it contains the database's message.
Anything else is listed as unchecked for a human to read.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import sys

SEED = re.compile(r'<script\b[^>]*type="text/plain"[^>]*>(.*?)</script>', re.S | re.I)
RUN = re.compile(r'<div class="nerdit-run">.*?<pre data-lang="sql"><code>(.*?)</code></pre>'
                 r'.*?<div class="nerdit-out">.*?<pre><code>(.*?)</code></pre>', re.S)


def parse_table(txt: str) -> list[list[str]] | None:
    txt = txt.strip()
    if not txt.startswith("+"):
        return None
    return [[c.strip() for c in ln.strip().strip("|").split("|")]
            for ln in txt.splitlines() if ln.strip().startswith("|")]


def _statements(sql: str) -> list[str]:
    out, buf = [], ""
    for ch in sql:
        buf += ch
        if ch == ";" and sqlite3.complete_statement(buf):
            out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def _cell(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _run(seed: str, history: list[str], sql: str):
    con = sqlite3.connect(":memory:")
    try:
        con.executescript(seed)
        for earlier in history:
            try:
                con.executescript(earlier)
            except sqlite3.Error:
                pass
        cur = None
        for stmt in _statements(sql):
            cur = con.execute(stmt)
        if cur is not None and cur.description:
            return [[d[0] for d in cur.description]] + [[_cell(v) for v in row] for row in cur.fetchall()], None
        return None, None
    except sqlite3.Error as e:
        return None, str(e)
    finally:
        con.close()


def check_lesson(content: str) -> dict:
    seed = "\n".join(html.unescape(s) for s in SEED.findall(content))
    report = {"examples": 0, "match": 0, "mismatch": [], "unchecked": []}
    history: list[str] = []
    for i, (code, shown) in enumerate(RUN.findall(content), 1):
        report["examples"] += 1
        sql, shown = html.unescape(code), html.unescape(shown)
        rows, err = _run(seed, [], sql)
        if err and "no such table" in err:
            rows, err = _run(seed, history, sql)
        history.append(sql)
        expected = parse_table(shown)
        if expected is not None and rows is not None:
            if rows == expected:
                report["match"] += 1
            else:
                report["mismatch"].append(f"example {i}: shown {expected} but the data gives {rows}")
        elif err:
            if err.lower() in shown.lower():
                report["match"] += 1
            else:
                report["mismatch"].append(f"example {i}: database error '{err}' not shown")
        else:
            report["unchecked"].append(f"example {i}: output is not a table; read it by hand")
    return report


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--lesson")
    args = ap.parse_args()
    with open(args.course, encoding="utf-8") as f:
        course = json.load(f)
    bad = 0
    for lesson in course.get("lessons", []):
        if args.lesson and lesson["id"] != args.lesson:
            continue
        r = check_lesson(lesson.get("content") or "")
        if not r["examples"]:
            continue
        print(f"{lesson['id']}: {r['examples']} examples, {r['match']} match, "
              f"{len(r['mismatch'])} mismatch, {len(r['unchecked'])} unchecked")
        for line in r["mismatch"] + r["unchecked"]:
            print(f"  - {line}")
        bad += len(r["mismatch"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests and the chapter-generator suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_check_sql_outputs.py && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: `4 passed`, then `124 passed`

- [ ] **Step 5: Run it on the current Data Modelling course (baseline, read-only)**

Run: `python check_sql_outputs.py --course ../../../../nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/course-data-modelling-etl-data-warehousing-for-analysts_output.json --lesson dw-dimensional-models-and-star-schemas-04`
Expected: one summary line for the lesson. Record the counts in the ledger as the pilot's "before" numbers; mismatches here are findings for Task 10, not failures of this task.

- [ ] **Step 6: Commit**

```bash
git add skills/nerdit-chapter-generator/scripts/check_sql_outputs.py skills/nerdit-chapter-generator/scripts/test_check_sql_outputs.py
git commit -m "feat(generator): check SQL example outputs against the lesson seed data

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Chapter-generator teaching rules

**Files:**
- Modify: `skills/nerdit-chapter-generator/references/CORE.md` (§2 concept-section shape, §4c headings, §5 demo data)
- Modify: `skills/nerdit-chapter-generator/references/figures.md` (add template 10)
- Modify: `agents/nerdit-lesson-writer.md`, `agents/nerdit-qa-validator.md`
- Modify: `skills/nerdit-chapter-generator/SKILL.md` (Step 4c gains the SQL output check)

**Interfaces:**
- Produces: the teaching sequence and figure rules the pilots (Tasks 10–11) are generated under

- [ ] **Step 1: Replace the concept-section shape in `CORE.md` §2**

Replace the lines from `[definition: 2–3 short sentences, ONE key word in <strong>]` through `[Try It block]` with:

```
    [meaning and purpose: 2–3 short sentences — what the term is and the problem it solves; ONE key word in <strong>]
    [concrete case: one small example from the running scenario, using only the rows this concept needs]
    [figure — when the concept is a relationship, sequence, change or decision (§7); drawn from those same rows]
    [read the figure: 2–4 numbered steps whose numbers ① ② ③ match markers in the figure]
    [worked example: code → output → why the output follows]
    [ONE callout max — only if there is a real gotcha]
    [Try It block — practises this concept, not a neighbouring one]
```

Below the "Hard limits" list add:

```
Teaching sequence rules (checked by the QA agent):
- Introduce a table, column or term in the section that first needs it; do not show the whole
  fixture before the first concept. The full seed can stay in the seed script.
- A worked example's heading names the operation its code actually performs.
- The Try It practises the section's own concept. If running code cannot show the concept
  (for example the order of ETL steps), use a prediction or ordering task instead.
- Do not add a second example only to reach a count.
```

- [ ] **Step 2: Add the heading rule to `CORE.md` §4c**

At the end of §4c add:

```
### The heading must match the code

An example heading names what its code does. A heading that says `JOIN dim_date` above code that
only converts a timestamp sends the learner looking for a join that is not there. Write the
heading after the code, from the code.
```

- [ ] **Step 3: Change `CORE.md` §5 opening sentence**

Replace the first paragraph of §5 with:

```
Show only the rows the first concept needs at the top of the lesson. Each later table appears
in the section that introduces it. The seed script still recreates every table, so the Try It
runner always has the full dataset.
```

- [ ] **Step 4: Add template 10 to `figures.md`**

Insert before `## Choosing between them`:

````markdown
## 10 · Key match — follow one record through its keys

For: a fact row and its dimensions, a foreign key to its parent, an order line to its product.
Use the lesson's own row and values. Number the parts the reading steps describe.

```html
<div class="nerdit-figure">
  <svg viewBox="0 0 640 250" role="img" aria-label="Sales row O1 line 1 stores amount 200; customer_key 1 finds Aarav in Pune and product_key 10 finds Book.">
    <rect x="225" y="50" width="190" height="150" rx="8" fill="var(--bg-soft)" stroke="var(--nb)"/>
    <text class="nerdit-flow-text" x="320" y="76" text-anchor="middle" fill="var(--nb)">fact_sales</text>
    <text class="nerdit-flow-text" x="240" y="104" fill="var(--tx)">order O1, line 1</text>
    <text class="nerdit-flow-text" x="240" y="130" fill="var(--green)">① amount = 200</text>
    <text class="nerdit-flow-text" x="240" y="156" fill="var(--orange)">② customer_key = 1</text>
    <text class="nerdit-flow-text" x="240" y="182" fill="var(--orange)">③ product_key = 10</text>
    <rect x="20" y="80" width="170" height="90" rx="8" fill="var(--white)" stroke="var(--nb)"/>
    <text class="nerdit-flow-text" x="105" y="104" text-anchor="middle" fill="var(--nb)">dim_customer</text>
    <text class="nerdit-flow-text" x="34" y="130" fill="var(--orange)">customer_key = 1</text>
    <text class="nerdit-flow-text" x="34" y="154" fill="var(--tx)">Aarav, Pune</text>
    <rect x="450" y="80" width="170" height="90" rx="8" fill="var(--white)" stroke="var(--nb)"/>
    <text class="nerdit-flow-text" x="535" y="104" text-anchor="middle" fill="var(--nb)">dim_product</text>
    <text class="nerdit-flow-text" x="464" y="130" fill="var(--orange)">product_key = 10</text>
    <text class="nerdit-flow-text" x="464" y="154" fill="var(--tx)">Book, Reading</text>
    <path d="M225 152 H205 V126 H190" stroke="var(--orange)" stroke-width="1.6" fill="none"/>
    <path d="M415 178 H435 V126 H450" stroke="var(--orange)" stroke-width="1.6" fill="none"/>
  </svg>
  <div class="nerdit-figure-caption">The sales row stores the amount; matching keys supply customer and product details.</div>
</div>
```

Draw one record, not a table. The reading steps under the figure follow ① ② ③ in order.
````

- [ ] **Step 5: Update the lesson-writer agent**

In `agents/nerdit-lesson-writer.md`, under "## The rules that matter most", add:

```markdown
- **Teaching sequence (CORE.md §2):** meaning → concrete case → figure → read the figure →
  worked example → practice, using only the rows the concept needs.
- **Figures come from the lesson's data.** Every label, key, name, date and amount in a figure
  appears in the section or its seed. Number the parts and write matching ① ② ③ reading steps.
- **Headings match code; practice matches the concept** (CORE.md §2 teaching rules, §4c).
- **Reform mode and old images:** keep an old raster image only when every value in it matches
  the lesson's data; otherwise drop it and draw the relationship as an SVG figure.
```

- [ ] **Step 6: Update the QA agent checklist**

In `agents/nerdit-qa-validator.md`, add to its checklist:

```markdown
- [ ] Each example heading names what its code does.
- [ ] Each Try It practises its own section's concept.
- [ ] Every value in a figure (names, keys, dates, amounts) matches the section or its seed.
- [ ] Reading steps ① ② ③ under a figure match the figure's numbered markers.
- [ ] Tables and terms appear in the section that first needs them.
```

- [ ] **Step 7: Add the SQL check to the chapter generator's Step 4c**

In `skills/nerdit-chapter-generator/SKILL.md`, at the end of "## Step 4c", add:

```markdown
For SQL lessons, also run the output checker and fix every mismatch before QA:

    python "<skill>/scripts/check_sql_outputs.py" --course <workdir>/course-<chaptername>_output.json

A mismatch means a shown result does not follow from the seed data: regenerate that lesson with
the reported lines (counts toward the 2-attempt budget).
```

- [ ] **Step 8: Verify nothing else broke**

Run: `cd skills/nerdit-chapter-generator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: `124 passed`

- [ ] **Step 9: Commit**

```bash
git add skills/nerdit-chapter-generator/references/CORE.md skills/nerdit-chapter-generator/references/figures.md agents/nerdit-lesson-writer.md agents/nerdit-qa-validator.md skills/nerdit-chapter-generator/SKILL.md
git commit -m "docs(generator): teaching sequence, data-true figures, key-match template

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Illustrator skill instructions for v2

**Files:**
- Modify: `skills/nerdit-lesson-illustrator/SKILL.md`
- Modify: `skills/nerdit-lesson-illustrator/references/style.md` (prose sections)
- Modify: `.claude-plugin/plugin.json` (version 3.2.0)

**Interfaces:**
- Consumes: every CLI from Tasks 1–6

- [ ] **Step 1: Replace "Run 1 — plan" steps 2–4 in `SKILL.md`**

```markdown
2. `python scripts/extract_outline.py --course <course.json>` to find candidate sections.
3. For each candidate, read the whole section and its data:
   `python scripts/extract_outline.py --course <course.json> --full <lesson-id>:<section>`.
   Inspect any existing figure in that section before deciding it already covers the idea.
4. Choose the visual by its teaching job (`references/style.md`): a **diagram** for any
   relationship, sequence, change, timeline or table; an **illustration** only for a real scene
   or analogy. Write `<images>/plan.json` as
   `{"version": 2, "cast": "<optional recurring characters>", "items": [ ... ]}` with one item per
   visual: `lessonId, section, heading, position, anchor, kind, question, objective, sourceRefs,
   knownTerms, newTerms, labels, takeaway, misconception, intro, caption, alt, explanation,
   checkQuestion {question, answer, reasoning}` and, for illustrations, `subject`.
   Labels are copied exactly from the section or fixture. `explanation` is the visible reading
   order: with two or more steps, the figure carries matching markers ① ② ③.
5. `python scripts/manifest.py add --course <course.json> --plan <images>/plan.json --images-dir <images>`.
6. For each diagram listed under "Diagrams to draw" in `PROMPTS.md`, write the SVG to
   `<images>/diagrams/<file>` following `figures.md` (tokens only, viewBox, role, aria-label,
   labels as `<text>`, markers ① ② ③). Illustrations go to the user as before.
```

(Renumber the following step.)

- [ ] **Step 2: Replace "Run 2 — apply" step 2 in `SKILL.md`**

```markdown
2. Check every converted visual against its brief using the criteria in `references/style.md`:
   read each raster preview at both sizes (`preview/<id>.jpg` and `preview/<id>-phone.jpg`) and
   each diagram's SVG source. Write `<images>/results.json` as before.
```

- [ ] **Step 3: Replace the prose sections of `references/style.md`**

Replace "## Planning rules" and "## Visual check criteria" with:

```markdown
## Choosing a visual

| Learner question | Kind | Must show |
|---|---|---|
| Where does a record go? | diagram (sequence) | each layer and its responsibility |
| What happens first? | diagram (two aligned flows) | the steps in their real order |
| How are tables related? | diagram (key match, template 10) | exact table/column names, the matching keys, one record |
| What changed? | diagram (before/after) | input, rule, output rows |
| Which date or period applies? | diagram (timeline) | exact timestamps, offset, boundaries |
| Why is this unsafe to sum? | diagram or small table | grain, units, the repeated value |
| Who does what? | illustration | the actors and actions, mapped to the lesson in the steps |

- One objective per visual; split a crowded figure into two.
- Diagrams use the lesson's own names, keys, dates and amounts — never invented ones.
- No quota: add a visual only where it helps; an existing accurate figure may already do the job.
- The intro sentence, caption, reading steps and check question are written for a student
  meeting the topic for the first time.

## Visual check criteria

PASS only when all hold:

1. It answers the brief's question and shows the takeaway; the caption is true of it.
2. Every label, value and name matches the section or its fixture.
3. Markers ① ② ③ sit on the parts the reading steps describe, in the same order.
4. Labels are readable on the phone-size preview.
5. Illustrations: no extra text, numbers, logos or brands; Indian context where people appear;
   the course's recurring cast when one is set.
6. Nothing contradicts the lesson or invites the brief's stated misconception.
```

- [ ] **Step 4: Bump the plugin version**

Set `"version": "3.2.0"` in `.claude-plugin/plugin.json`.

- [ ] **Step 5: Verify**

Run: `cd skills/nerdit-lesson-illustrator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: `80 passed`

- [ ] **Step 6: Commit**

```bash
git add skills/nerdit-lesson-illustrator/SKILL.md skills/nerdit-lesson-illustrator/references/style.md .claude-plugin/plugin.json
git commit -m "docs(illustrator): v2 workflow — full-section briefs, diagrams first, v3.2.0

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Pilot 1 — star schema lesson

**Files (local, not committed):** `../nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/` — a new work folder `pilot-04/` inside it.

- [ ] **Step 1: Prepare a reform source**

```bash
D=../nerdit/generated/data-modelling-etl-data-warehousing-for-analysts
mkdir -p "$D/pilot-04/_src"
cp "$D/dw-dimensional-models-and-star-schemas-04.html" "$D/pilot-04/_src/"
python - <<'EOF'
import json
d = "../nerdit/generated/data-modelling-etl-data-warehousing-for-analysts"
items = json.load(open(f"{d}/course-data-modelling-etl-data-warehousing-for-analysts_input.json", encoding="utf-8"))
json.dump([i for i in items if i["id"] == "dw-dimensional-models-and-star-schemas-04"],
          open(f"{d}/pilot-04/course-pilot-04_input.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
EOF
```

- [ ] **Step 2: Regenerate the lesson in reform mode**

Run one `nerdit-lesson-writer` agent (one agent at a time) with: the lesson's id/title/description from `pilot-04/course-pilot-04_input.json`, `RUNNER: sql`, `SOURCE_PATH = pilot-04/_src/dw-dimensional-models-and-star-schemas-04.html`, PRIOR/UPCOMING from the full course input, paths `pilot-04/<id>.html|.quiz.json|.concepts.json`, and this brief: follow the updated CORE.md teaching sequence; section 2's question is "How does a sales row find its customer and product?"; start from fact row O1 line 1 (`customer_key=1`, `product_key=10`, `amount=200`); draw template 10 from those values; steps ① amount, ② customer key → Aarav, Pune, ③ product key → Book; reveal snowflake tables only in the star-vs-snowflake section; introduce duplicate-key multiplication in its own section; drop the old Boston/Chicago PNG.

- [ ] **Step 3: Assemble and run every gate**

```bash
G=skills/nerdit-chapter-generator/scripts
python $G/assemble_course.py --chapter pilot-04 --input "$D/pilot-04/course-pilot-04_input.json" --html-dir "$D/pilot-04" --out "$D/pilot-04/course-pilot-04_output.json"
python $G/verify_course.py --input "$D/pilot-04/course-pilot-04_input.json" --output "$D/pilot-04/course-pilot-04_output.json" --contract v10
python $G/check_sql_outputs.py --course "$D/pilot-04/course-pilot-04_output.json"
```
Expected: verifier `PASS`; SQL checker `0 mismatch`. Any mismatch → regenerate with the exact lines (2-attempt budget).

- [ ] **Step 4: Trace every figure value to the fixture**

Read the lesson's key-match SVG and its seed script; confirm O1/1/200, key 1 → Aarav, Pune and key 10 → Book appear in the seed. Record the check in the ledger.

- [ ] **Step 5: Render a preview at desktop and phone width**

Write `pilot-04/preview.html` that links `skills/nerdit-chapter-generator/references/css8.css`, `css9-simple.css` and `css10-brand.css` and contains the lesson HTML. Open it with Playwright (`file://` URL), take full-page screenshots at 1280 px and 390 px widths, and read both. Fix layout problems before review.

- [ ] **Step 6: Record the pilot result in the ledger** (no commit — generated content is local)

---

### Task 11: Pilot 2 — date and reporting-calendar lesson

**Files (local, not committed):** `$D/pilot-06/`

- [ ] **Step 1:** Repeat Task 10 Steps 1–3 for `dw-date-dimensions-and-reporting-calendars-06`, with this brief: section 2 shows `2025-03-31 20:00 UTC` and `2025-04-01 01:30 Asia/Kolkata` as the same instant on a timeline figure (sequence template), then derives the reporting date; the heading names the timezone conversion; state that the April–March fiscal calendar belongs to this example; handle order date versus ship date in its own section; keep the existing date picture only if every value matches the seed, otherwise replace it with the SVG timeline.
- [ ] **Step 2:** Trace every timestamp and offset in the figure to the seed and the worked example (ledger).
- [ ] **Step 3:** Desktop and phone screenshots as in Task 10 Step 5; fix layout problems.
- [ ] **Step 4:** Record the result in the ledger.

---

### Task 12: Backfill trial — add a v2 diagram to an existing lesson without regenerating it

**Files (local):** `$D/images/` (the existing Data Modelling illustrator folder)

- [ ] **Step 1: Replace the three old v1 plans for lessons 01–02**

```bash
S=skills/nerdit-lesson-illustrator/scripts
C="$D/course-data-modelling-etl-data-warehousing-for-analysts_output.json"
python $S/extract_outline.py --course "$C" --full dw-analyst-warehouse-purpose-and-layers-01:4
```

Write `$D/images/plan.json` as a v2 object with one **diagram** item for lesson 01 section 4 ("Distinguish ETL from ELT by transformation order"): two aligned flows (sequence template) with labels copied from the section, steps ① extract ② transform ③ load in ETL order and the ELT difference stated in the explanation, and a check question "Which design transforms the data inside the warehouse?". Then run:

```bash
python $S/manifest.py add --course "$C" --plan "$D/images/plan.json" --images-dir "$D/images" --replan dw-analyst-warehouse-purpose-and-layers-01
```

Expected: `Planned …` with the diagram listed under "Diagrams to draw".

- [ ] **Step 2:** Write the SVG to `$D/images/diagrams/dw-analyst-warehouse-purpose-and-layers-01-fig1.svg` following figures.md, then run `convert_images.py`, read the SVG, write `results.json`, `manifest.py record`, and `insert_images.py`.
Expected: `Wrote …with-images.json`, the 16 optimised images still re-pointed, and no new verifier failures.

- [ ] **Step 3:** Inspect lesson 01's existing (re-encoded) warehouse-layers image against its section text and fixture; record keep or replace in the ledger. Re-encoding is not approval of its content.
- [ ] **Step 4:** Preview lesson 01 from the with-images JSON at desktop and phone width (as Task 10 Step 5) and record the result.

---

### Task 13: Admin follow-ups recorded in the admin plan

**Files:**
- Modify: `../nerdit-admin/docs/course-json-images-import-plan.md` (append; owned by the admin workstream)

- [ ] **Step 1: Append this section**

```markdown
## Integration with the lesson illustrator (added 2026-10-12)

- [ ] Preserve illustrator v2 teaching blocks on import, preview and export: sibling elements
      sharing `data-nerdit-img="<id>"` — `p.nerdit-visual-intro`, `div.nerdit-figure` (inline
      SVG or `<img>`), `ol.nerdit-visual-read`, `div.nerdit-predict`. Verify the public lesson
      renderer's sanitizer keeps `data-*` attributes, inline SVG and the `style` on the list.
- [ ] Compress hand uploads in the course image panel: convert in the browser to WebP, at most
      1200 px wide, quality about 0.8; lower the per-file limit from 25 MB to about 2 MB.
- [ ] Data Modelling migration: import the illustrator output
      (`nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/…_output.with-images.json`
      plus `images/upload/`, 16 WebP files, 984 KB) instead of "Copy website-hosted images",
      which would copy the 1.4 MB PNGs.
- [ ] Ship the one-year cache header in `shared/src/services/courseMediaService.ts` (already
      written and tested; uncommitted with the rest of this workstream's changes).
- [ ] Caption or step edits made in the admin are overwritten if the illustrator's apply runs
      again on the same JSON; edit them in the illustrator manifest, or do not re-apply.
```

- [ ] **Step 2:** Show the user the appended section; this repository is the admin workstream's, so do not commit it from this plan.

---

### Task 14: Review gate

- [ ] **Step 1:** Present to the user: both pilots' desktop and phone screenshots, the traced figure values, the SQL checker results before and after, and the backfill lesson preview.
- [ ] **Step 2:** Record the user's decision in the ledger. Rolling the pattern out to other lessons, importing anything into the admin, and publishing are separate requests after this review.
