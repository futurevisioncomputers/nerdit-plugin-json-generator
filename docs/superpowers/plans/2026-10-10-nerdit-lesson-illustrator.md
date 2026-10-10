# NERDIT Lesson Illustrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `nerdit-lesson-illustrator` skill that plans concept illustrations for a NERDIT course JSON, emits ready-to-paste prompts and exact placements, and — once the user has generated the images — converts them to small WebP files, records a visual check, inserts them into the lessons, and produces a JSON plus image folder for the admin's "Import JSON + Images" page.

**Architecture:** Five small Python scripts sharing one HTML helper module (`lessonhtml.py`) and one manifest module (`manifest.py`). Claude does only the judgment steps (choose slots and write prompt subjects into `plan.json`; judge previews into `results.json`); scripts do everything mechanical and are unit-tested. A last task, in two other repos, adds a one-year cache header to admin image uploads.

**Tech Stack:** Python 3.14, Pillow 12.1.1 (WebP confirmed), pytest 9.1.1, standard library only otherwise. Admin task: TypeScript, Vitest, Firebase Storage SDK.

**Spec:** `docs/superpowers/specs/2026-10-10-nerdit-lesson-illustrator-design.md` (commit 099e5f9)

## Global Constraints

- Skill folder: `skills/nerdit-lesson-illustrator/` inside the `nerdit_content_creator` plugin (this repo).
- Run tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` from the skill's `scripts/` folder. A broken third-party `langsmith` pytest plugin on this machine crashes pytest otherwise; with autoload disabled the existing 120 chapter-generator tests pass.
- Every CLI calls `sys.stdout.reconfigure(encoding="utf-8")` first: lesson text contains `₹` and emoji, and the Windows console encoding (cp1252) crashes on them.
- Never modify the input course JSON. Apply writes `course-<chapter>_output.with-images.json` next to it.
- Never write `data:` image URIs into lesson HTML.
- WebP output: at most 1200 px wide, start quality 80, step down by 5 to a floor of 60 until ≤ 150,000 bytes (target); over 250,000 bytes is an error and the image is not inserted.
- Visual-check previews: 640 px wide JPEG.
- At most 3 images per lesson.
- Filenames: request `<lesson-id>-img<N>.png` (PNG, JPG, JPEG or WebP accepted, any letter case), output `<lesson-id>-img<N>.webp`.
- Admin import limit for the course JSON: under 1,048,576 bytes.
- Existing images larger than 300,000 bytes are re-encoded and re-pointed.
- Inserted markup is exactly the block in Task 6 (`nerdit-figure nerdit-illustration`, `data-nerdit-img`, `loading="lazy"`, `decoding="async"`, real width/height, caption div, no hex colours).
- Image style block lives only in `references/style.md`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Stage only the files each task names: the working trees contain unrelated uncommitted changes.

## Review Focus

1. Paragraphs containing entities, inline tags, `₹` or emoji — the anchor the outline prints must be the exact anchor `locate` matches (Task 1 test `test_anchor_normalises_entities_tags_and_symbols`).
2. Incoming files whose names differ only in letter case or extension (`.PNG`, `.jpeg`), and two files for one slot — matched case-insensitively, the second reported as a duplicate (Task 4 tests).
3. A regenerated image saved under the same filename after a failed check — re-converted and its check reset, while an unchanged file is not re-converted (Task 4 test `test_new_file_after_fail_is_reconverted_and_check_reset`).
4. Re-running apply on a JSON the chapter generator rebuilt (no inserted blocks) or on a previous apply's lessons — byte-identical lessons (Task 6 and Task 9 idempotency tests).
5. Unusual image modes — RGBA, palette with transparency, CMYK JPEG, animated GIF — convert without crashing (Task 4 test `test_unusual_image_modes_convert`).

---

### Task 1: Skill scaffold and lesson HTML helpers

**Files:**
- Create: `skills/nerdit-lesson-illustrator/scripts/lessonhtml.py`
- Create: `skills/nerdit-lesson-illustrator/scripts/fixture_course.py`
- Test: `skills/nerdit-lesson-illustrator/scripts/test_lessonhtml.py`

**Interfaces:**
- Produces:
  - `text(fragment: str) -> str`, `anchor_of(fragment: str) -> str` (first 60 chars of `text`, right-stripped)
  - `Section(number: int, heading: str, start: int, end: int, teaching: bool)` (frozen dataclass)
  - `sections(content: str) -> list[Section]`
  - `top_paragraphs(content: str, sec: Section) -> list[tuple[int, str]]` — (end offset, anchor)
  - `find_section(content: str, number: int, heading: str) -> Section`
  - `locate(content: str, number: int, heading: str, position: str, anchor: str | None) -> int`
  - `img_sources(content: str) -> list[str]`
  - `class AnchorNotFound(Exception)`
  - regexes `IMG`, `SRC`, `SVG`, `PRACTICE`, `FIG_CAPTION`
  - `fixture_course.course() -> dict`, `fixture_course.PLAN: list[dict]`, `fixture_course.ANCHOR_1: str`

- [ ] **Step 1: Write the fixture module**

Create `scripts/fixture_course.py`:

```python
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
```

- [ ] **Step 2: Write the failing tests**

Create `scripts/test_lessonhtml.py`:

```python
import pytest

from fixture_course import ANCHOR_1, course
from lessonhtml import (AnchorNotFound, anchor_of, img_sources, locate, sections, text,
                        top_paragraphs)


def lesson(i):
    return course()["lessons"][i]["content"]


def test_text_strips_tags_decodes_entities_and_collapses_space():
    assert text("<p>A <strong>bold</strong>\n  word &amp; more</p>") == "A bold word & more"


def test_anchor_normalises_entities_tags_and_symbols():
    secs = sections(lesson(0))
    anchors = [a for _, a in top_paragraphs(lesson(0), secs[0])]
    assert anchors[0] == ANCHOR_1
    assert anchor_of("<p>A load copies cleaned rows into the warehouse &amp; keeps a <strong>run log</strong> of ₹ totals 📦.</p>") == ANCHOR_1


def test_sections_numbers_headings_and_teaching_flags():
    secs = sections(lesson(0))
    assert [(s.number, s.heading, s.teaching) for s in secs] == [
        (1, "1 — What a load does", True),
        (2, "2 — Reruns are safe", True),
        (3, "📌 Quick cheat sheet", False),
    ]


def test_old_style_headings_are_sections_too():
    secs = sections(lesson(1))
    assert [(s.heading, s.teaching) for s in secs] == [("Introduction", True), ("Key Takeaways", False)]


def test_top_paragraphs_skip_paragraphs_inside_boxes():
    secs = sections(lesson(0))
    anchors = [a for _, a in top_paragraphs(lesson(0), secs[0])]
    assert anchors == [ANCHOR_1, "The target table only ever receives checked rows."]


def test_locate_after_explanation_returns_end_of_paragraph():
    content = lesson(0)
    off = locate(content, 1, "1 — What a load does", "after-explanation", ANCHOR_1)
    assert content[:off].endswith("totals 📦.</p>")


def test_locate_before_practice_returns_start_of_practice_block():
    content = lesson(0)
    assert content[locate(content, 1, "1 — What a load does", "before-practice", None):].startswith('<div class="nerdit-predict">')
    assert content[locate(content, 2, "2 — Reruns are safe", "before-practice", None):].startswith('<div class="nerdit-fillblank">')


def test_locate_before_practice_without_practice_uses_last_paragraph():
    content = lesson(1)
    off = locate(content, 1, "Introduction", "before-practice", None)
    assert content[:off].endswith("Old lessons start like this.</p>")


def test_locate_raises_instead_of_guessing():
    content = lesson(0)
    with pytest.raises(AnchorNotFound):
        locate(content, 1, "1 — What a load does", "after-explanation", "No such paragraph")
    with pytest.raises(AnchorNotFound):
        locate(content, 1, "1 — Renamed heading", "after-explanation", ANCHOR_1)


def test_img_sources():
    assert img_sources(lesson(1)) == ["https://nerdit.in/lesson-images/test/old-diagram.png"]
    assert img_sources(lesson(0)) == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd skills/nerdit-lesson-illustrator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_lessonhtml.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'lessonhtml'`

- [ ] **Step 4: Implement `lessonhtml.py`**

```python
"""Dependency-free helpers for reading and editing NERDIT lesson HTML.

A section is the span from one <h2> to the next (or to the end of the lesson). A paragraph is
"top level" in a section when it sits at the same <div> depth as the section's <h2>, so text
inside practice boxes, info boxes and figures is never used as an image anchor.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

H2 = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.S | re.I)
P = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S | re.I)
IMG = re.compile(r"<img\b[^>]*>", re.I)
SRC = re.compile(r'\bsrc="([^"]*)"', re.I)
SVG = re.compile(r"<svg\b", re.I)
PRACTICE = re.compile(r'<div\b[^>]*\bclass="[^"]*\bnerdit-(?:predict|fillblank|tryit)\b[^"]*"', re.I)
FIG_CAPTION = re.compile(r'<div\b[^>]*\bclass="[^"]*\bnerdit-figure-caption\b[^"]*"[^>]*>(.*?)</div>', re.S | re.I)
DIV_OPEN = re.compile(r"<div\b", re.I)
DIV_CLOSE = re.compile(r"</div\s*>", re.I)
TAG = re.compile(r"<[^>]+>")
NON_TEACHING = re.compile(
    r"cheat\s*sheet|practice|quiz|summary|takeaway|recap|exercise|assignment|challenge|next steps", re.I)
ANCHOR_LEN = 60


class AnchorNotFound(Exception):
    """The placement recorded for an image no longer exists in the lesson."""


@dataclass(frozen=True)
class Section:
    number: int      # 1-based position of the <h2> in the lesson
    heading: str     # plain text of the <h2>
    start: int       # offset of the <h2> tag
    end: int         # offset of the next <h2>, or end of content
    teaching: bool   # False for cheat sheets, practice, quizzes and summaries


def text(fragment: str) -> str:
    """Plain text: tags removed, entities decoded, whitespace collapsed."""
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", fragment))).strip()


def anchor_of(fragment: str) -> str:
    return text(fragment)[:ANCHOR_LEN].rstrip()


def _depth(s: str) -> int:
    return len(DIV_OPEN.findall(s)) - len(DIV_CLOSE.findall(s))


def sections(content: str) -> list[Section]:
    heads = list(H2.finditer(content))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(content)
        heading = text(m.group(1))
        out.append(Section(i + 1, heading, m.start(), end, not NON_TEACHING.search(heading)))
    return out


def top_paragraphs(content: str, sec: Section) -> list[tuple[int, str]]:
    base = _depth(content[:sec.start])
    return [(m.end(), anchor_of(m.group(1)))
            for m in P.finditer(content, sec.start, sec.end)
            if _depth(content[:m.start()]) == base]


def find_section(content: str, number: int, heading: str) -> Section:
    for sec in sections(content):
        if sec.number == number and sec.heading == heading:
            return sec
    raise AnchorNotFound(f"section {number} '{heading}' not found")


def locate(content: str, number: int, heading: str, position: str, anchor: str | None) -> int:
    """Offset where an image block goes. Raises AnchorNotFound instead of guessing."""
    sec = find_section(content, number, heading)
    paras = top_paragraphs(content, sec)
    if position == "after-explanation":
        for end, a in paras:
            if a == anchor:
                return end
        raise AnchorNotFound(f"no paragraph starting '{anchor}' in section {number} '{heading}'")
    if position == "before-practice":
        m = PRACTICE.search(content, sec.start, sec.end)
        if m and _depth(content[:m.start()]) == _depth(content[:sec.start]):
            return m.start()
        if paras:
            return paras[-1][0]
        raise AnchorNotFound(f"section {number} '{heading}' has no practice block or paragraph")
    raise ValueError(f"unknown position {position!r}")


def img_sources(content: str) -> list[str]:
    out = []
    for tag in IMG.findall(content):
        m = SRC.search(tag)
        if m:
            out.append(html.unescape(m.group(1)))
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd skills/nerdit-lesson-illustrator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_lessonhtml.py`
Expected: `10 passed`

- [ ] **Step 6: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/lessonhtml.py skills/nerdit-lesson-illustrator/scripts/fixture_course.py skills/nerdit-lesson-illustrator/scripts/test_lessonhtml.py
git commit -m "feat(illustrator): lesson HTML section, anchor and placement helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Lesson outline extractor

**Files:**
- Create: `skills/nerdit-lesson-illustrator/scripts/extract_outline.py`
- Test: `skills/nerdit-lesson-illustrator/scripts/test_extract_outline.py`

**Interfaces:**
- Consumes: `lessonhtml.sections`, `top_paragraphs`, `text`, `img_sources`, `SVG`, `PRACTICE`, `FIG_CAPTION`
- Produces:
  - `outline(course: dict) -> list[dict]` — per lesson: `{"lessonId", "title", "svgCount", "images": [src], "sections": [{"number", "heading", "teaching", "hasPractice", "figures": [caption], "anchors": [anchor]}]}`
  - `render(lessons: list[dict]) -> str`
  - CLI: `python extract_outline.py --course <course.json> [--out <outline.json>]`

- [ ] **Step 1: Write the failing tests**

```python
import json
import os
import subprocess
import sys

from extract_outline import outline, render
from fixture_course import ANCHOR_1, course

SCRIPT = os.path.join(os.path.dirname(__file__), "extract_outline.py")


def test_outline_lists_sections_figures_anchors_and_images():
    new, old = outline(course())
    assert new["lessonId"] == "load-basics-01" and new["svgCount"] == 1 and new["images"] == []
    s1 = new["sections"][0]
    assert s1["heading"] == "1 — What a load does" and s1["teaching"] and s1["hasPractice"]
    assert s1["figures"] == ["Rows move from staging to the warehouse."]
    assert s1["anchors"] == [ANCHOR_1, "The target table only ever receives checked rows."]
    assert new["sections"][2]["teaching"] is False
    assert old["images"] == ["https://nerdit.in/lesson-images/test/old-diagram.png"]


def test_render_flags_lessons_with_no_visual():
    c = course()
    c["lessons"][1]["content"] = "<h2>Introduction</h2><p>Plain text only.</p>"
    out = render(outline(c))
    assert 'L02 old-style-02 "Old Style" [NO VISUAL]' in out
    assert 'L01 load-basics-01 "Load Basics" [svg=1 img=0]' in out
    assert f"     ¶ {ANCHOR_1}" in out


def test_cli_writes_json_and_prints_outline(tmp_path):
    src = tmp_path / "course.json"
    src.write_text(json.dumps(course(), ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "outline.json"
    r = subprocess.run([sys.executable, SCRIPT, "--course", str(src), "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert "L01 load-basics-01" in r.stdout
    assert json.loads(out.read_text(encoding="utf-8"))[0]["lessonId"] == "load-basics-01"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_extract_outline.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'extract_outline'`

- [ ] **Step 3: Implement `extract_outline.py`**

```python
"""Compact lesson outline for planning images.

Usage: python extract_outline.py --course <course.json> [--out <outline.json>]

Prints one line per lesson and section, with figure captions and the top-level paragraph
anchors the planner copies into plan.json. Reading this instead of full lesson HTML keeps
planning cheap.
"""
from __future__ import annotations

import argparse
import json
import sys

from lessonhtml import FIG_CAPTION, PRACTICE, SVG, img_sources, sections, text, top_paragraphs

MAX_ANCHORS = 6


def outline(course: dict) -> list[dict]:
    lessons = []
    for lesson in course.get("lessons", []):
        content = lesson.get("content") or ""
        secs = []
        for sec in sections(content):
            span = content[sec.start:sec.end]
            secs.append({
                "number": sec.number,
                "heading": sec.heading,
                "teaching": sec.teaching,
                "hasPractice": bool(PRACTICE.search(span)),
                "figures": [text(c) for c in FIG_CAPTION.findall(span)],
                "anchors": [a for _, a in top_paragraphs(content, sec)][:MAX_ANCHORS],
            })
        lessons.append({
            "lessonId": lesson["id"],
            "title": lesson.get("title", ""),
            "svgCount": len(SVG.findall(content)),
            "images": img_sources(content),
            "sections": secs,
        })
    return lessons


def render(lessons: list[dict]) -> str:
    lines = []
    for i, l in enumerate(lessons, 1):
        visual = ("NO VISUAL" if not l["svgCount"] and not l["images"]
                  else f"svg={l['svgCount']} img={len(l['images'])}")
        lines.append(f"L{i:02d} {l['lessonId']} \"{l['title']}\" [{visual}]")
        for s in l["sections"]:
            tag = ("teach" if s["teaching"] else "skip") + (" practice" if s["hasPractice"] else "")
            lines.append(f"  §{s['number']} {s['heading']} [{tag}]")
            lines += [f"     fig: {c}" for c in s["figures"]]
            lines += [f"     ¶ {a}" for a in s["anchors"]]
    return "\n".join(lines)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    with open(args.course, encoding="utf-8") as f:
        lessons = outline(json.load(f))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(lessons, f, ensure_ascii=False, indent=2)
    print(render(lessons))
    bare = sum(1 for l in lessons if not l["svgCount"] and not l["images"])
    print(f"\n{len(lessons)} lessons · {bare} with no visual")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_extract_outline.py`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/extract_outline.py skills/nerdit-lesson-illustrator/scripts/test_extract_outline.py
git commit -m "feat(illustrator): compact lesson outline for image planning

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: House style and manifest planning

**Files:**
- Create: `skills/nerdit-lesson-illustrator/references/style.md`
- Create: `skills/nerdit-lesson-illustrator/scripts/manifest.py`
- Test: `skills/nerdit-lesson-illustrator/scripts/test_manifest.py`

**Interfaces:**
- Consumes: `lessonhtml.locate`, `AnchorNotFound`; `fixture_course.course`, `PLAN`
- Produces:
  - constants `STATUSES = ("planned", "converted", "passed", "failed", "inserted")`, `POSITIONS`, `MAX_PER_LESSON = 3`, `STYLE_FILE`
  - `style_block(labels: list[str], path: Path = STYLE_FILE) -> str`
  - `new_manifest(course: dict, source: str) -> dict`
  - `load(images_dir: Path) -> dict`, `save(images_dir: Path, m: dict) -> None`
  - `validate(m: dict) -> list[str]`
  - `add_slots(m: dict, course: dict, plan: list[dict], replan: str | None = None) -> list[str]`
  - `render_prompts(m: dict) -> str`
  - CLI `python manifest.py add --course <json> --plan <plan.json> --images-dir <dir> [--replan <lesson-id>]`
- Slot fields (all later tasks use these names): `id, lessonId, lessonTitle, section{number,heading}, position, anchor, reason, prompt, labels, alt, caption, aspect, requestFile, outputFile, status, check{result,reason}, sourceSha256, bytes, width, height`

- [ ] **Step 1: Write `references/style.md`**

````markdown
# House style for NERDIT lesson illustrations

`manifest.py` appends the block between the `style` fences to every prompt. Edit the style here
and nowhere else. `{labels_clause}` is filled in per image.

```style
Style: flat educational illustration, clean simple shapes, soft shadows, plenty of empty space.
Colours: navy #0B1F3A, teal #14B8A6, light background #EEF3F9 and white, with at most one warm highlight colour.
Format: landscape 3:2.
Do not include any text, numbers, letters, logos, screenshots, user-interface elements or watermarks{labels_clause}.
People, if any: Indian people in Indian settings. No real brands, companies or celebrities.
```

## Planning rules

- Consider numbered teaching sections only (`[teach]` in the outline). Never the opening,
  practice blocks, the cheat sheet or the quiz.
- Every slot needs a one-line teaching `reason`. A section qualifies when it introduces an
  abstract idea a concrete picture makes memorable, describes a real-world process or scene, or
  opens the lesson and benefits from a hook (section 1).
- Skip a section when a figure caption in the outline already teaches the same idea, when the
  section is pure syntax or calculation, or when the picture would need exact numbers or text.
- 0 to 3 images per lesson; a lesson marked `[NO VISUAL]` gets at least 1; project and capstone
  lessons get 1 scene. Drop any slot without a clear reason.
- `subject`: the objects or metaphor to draw from this section, the composition (left to right
  for a process) and the focal point. Never ask for text, numbers, charts or tables.
- `labels`: at most 3 one-word labels, only when the idea needs them, spelled exactly.
- `alt`: what the picture shows, 125 characters or less.
- `caption`: the teaching point in one sentence of at most 15 words, in the lesson's terms.
- `position`: `after-explanation` with an `anchor` copied exactly from a `¶` line of that section,
  or `before-practice` (anchor empty).

## Visual check criteria

Judge each preview against its slot's reason, prompt and caption. PASS only when all hold:

1. It shows what the reason says the section needs, so the caption is true of the picture.
2. No garbled or extra text; any labels match the slot's `labels` exactly.
3. No numbers, logos, real brands or watermarks.
4. Brand palette, and an Indian context where people appear.
5. Nothing contradicts the lesson's terms or facts.
````

- [ ] **Step 2: Write the failing tests**

```python
import json
import os
import subprocess
import sys

from fixture_course import PLAN, course
from manifest import (MAX_PER_LESSON, add_slots, load, new_manifest, render_prompts, save,
                      style_block, validate)

SCRIPT = os.path.join(os.path.dirname(__file__), "manifest.py")


def planned():
    m = new_manifest(course(), "course.json")
    assert add_slots(m, course(), PLAN) == []
    return m


def test_add_slots_assigns_ids_files_and_full_prompts():
    m = planned()
    a, b = m["images"]
    assert (a["id"], a["requestFile"], a["outputFile"]) == (
        "load-basics-01-img1", "load-basics-01-img1.png", "load-basics-01-img1.webp")
    assert a["status"] == "planned" and a["section"] == {"number": 1, "heading": "1 — What a load does"}
    assert a["prompt"].startswith("A conveyor carrying clean boxes")
    assert "#0B1F3A" in a["prompt"] and "{labels_clause}" not in a["prompt"]
    assert 'except these exact labels: "Start"' in b["prompt"]
    assert b["id"] == "old-style-02-img1" and b["anchor"] == ""


def test_style_block_tolerates_crlf_files(tmp_path):
    p = tmp_path / "style.md"
    p.write_bytes(b"x\r\n```style\r\nLine one{labels_clause}.\r\n```\r\n")
    assert style_block([], p) == "Line one."
    assert style_block(["A"], p) == 'Line one, except these exact labels: "A".'


def test_add_slots_rejects_bad_items_without_partial_writes():
    m = new_manifest(course(), "course.json")
    bad = [dict(PLAN[0], lessonId="nope"), dict(PLAN[0], anchor="Not in the lesson"), dict(PLAN[0], alt="")]
    errors = add_slots(m, course(), bad)
    assert any("unknown lesson nope" in e for e in errors)
    assert any("no paragraph starting 'Not in the lesson'" in e for e in errors)
    assert any("missing alt" in e for e in errors)


def test_already_planned_lesson_needs_replan_and_replan_replaces():
    m = planned()
    assert any("--replan load-basics-01" in e for e in add_slots(m, course(), [PLAN[0]]))
    m = planned()
    new = dict(PLAN[0], subject="A different picture.")
    assert add_slots(m, course(), [new], replan="load-basics-01") == []
    ids = [s["id"] for s in m["images"] if s["lessonId"] == "load-basics-01"]
    assert ids == ["load-basics-01-img1"]
    assert m["images"][-1]["prompt"].startswith("A different picture.")


def test_per_lesson_cap():
    m = new_manifest(course(), "course.json")
    errors = add_slots(m, course(), [PLAN[0]] * (MAX_PER_LESSON + 1))
    assert any(f"more than {MAX_PER_LESSON} images" in e for e in errors)


def test_validate_alt_and_caption_limits():
    m = planned()
    m["images"][0]["alt"] = "x" * 126
    m["images"][0]["caption"] = " ".join(["word"] * 16)
    errors = validate(m)
    assert any("alt is over 125 characters" in e for e in errors)
    assert any("caption is over 15 words" in e for e in errors)


def test_render_prompts_lists_files_to_generate():
    out = render_prompts(planned())
    assert "### load-basics-01-img1.png" in out and "### old-style-02-img1.png" in out
    assert "2 to generate" in out


def test_save_and_load_round_trip(tmp_path):
    m = planned()
    save(tmp_path, m)
    assert load(tmp_path) == m


def test_cli_add_creates_manifest_prompts_and_incoming(tmp_path):
    src = tmp_path / "course.json"
    src.write_text(json.dumps(course(), ensure_ascii=False), encoding="utf-8")
    plan = tmp_path / "images" / "plan.json"
    plan.parent.mkdir()
    plan.write_text(json.dumps(PLAN, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "add", "--course", str(src), "--plan", str(plan),
                        "--images-dir", str(plan.parent)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (plan.parent / "manifest.json").is_file()
    assert (plan.parent / "PROMPTS.md").is_file()
    assert (plan.parent / "incoming").is_dir()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_manifest.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'manifest'`

- [ ] **Step 4: Implement `manifest.py`**

```python
"""Image manifest: the single record of every planned image and its status.

CLI:
  python manifest.py add    --course <course.json> --plan <plan.json> --images-dir <dir> [--replan <lesson-id>]
  python manifest.py record --images-dir <dir> --results <results.json>
  python manifest.py accept --images-dir <dir> --id <image-id>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from lessonhtml import AnchorNotFound, locate

STATUSES = ("planned", "converted", "passed", "failed", "inserted")
POSITIONS = ("after-explanation", "before-practice")
MAX_PER_LESSON = 3
STYLE_FILE = Path(__file__).resolve().parent.parent / "references" / "style.md"
PLAN_KEYS = ("lessonId", "section", "heading", "position", "reason", "subject", "alt", "caption")


def style_block(labels: list[str], path: Path = STYLE_FILE) -> str:
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.search(r"```style\n(.*?)\n```", raw, re.S)
    if not m:
        raise RuntimeError(f"no ```style block in {path}")
    clause = (", except these exact labels: " + ", ".join(f'"{l}"' for l in labels)) if labels else ""
    return m.group(1).replace("{labels_clause}", clause)


def new_manifest(course: dict, source: str) -> dict:
    return {"course": {"id": course.get("id", ""), "title": course.get("title", ""), "source": source},
            "styleVersion": 1, "images": [], "existingOptimised": []}


def load(images_dir: Path) -> dict:
    with open(Path(images_dir) / "manifest.json", encoding="utf-8") as f:
        return json.load(f)


def save(images_dir: Path, m: dict) -> None:
    path = Path(images_dir) / "manifest.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


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


def add_slots(m: dict, course: dict, plan: list[dict], replan: str | None = None) -> list[str]:
    lessons = {l["id"]: l for l in course.get("lessons", [])}
    if replan:
        m["images"] = [s for s in m["images"] if s["lessonId"] != replan]
    already = {s["lessonId"] for s in m["images"]}
    errors = []
    for i, p in enumerate(plan, 1):
        where = f"plan item {i}"
        missing = [k for k in PLAN_KEYS if p.get(k) in (None, "")]
        if p.get("position") == "after-explanation" and not p.get("anchor"):
            missing.append("anchor")
        if missing:
            errors.append(f"{where}: missing {', '.join(missing)}")
            continue
        lid = p["lessonId"]
        if lid not in lessons:
            errors.append(f"{where}: unknown lesson {lid}")
            continue
        if lid in already:
            errors.append(f"{where}: {lid} is already planned; use --replan {lid}")
            continue
        if p["position"] not in POSITIONS:
            errors.append(f"{where}: unknown position {p['position']}")
            continue
        try:
            locate(lessons[lid].get("content") or "", p["section"], p["heading"], p["position"], p.get("anchor") or None)
        except AnchorNotFound as e:
            errors.append(f"{where}: {e}")
            continue
        n = 1 + sum(1 for s in m["images"] if s["lessonId"] == lid)
        if n > MAX_PER_LESSON:
            errors.append(f"{where}: {lid} would have more than {MAX_PER_LESSON} images")
            continue
        image_id = f"{lid}-img{n}"
        labels = list(p.get("labels") or [])
        m["images"].append({
            "id": image_id, "lessonId": lid, "lessonTitle": lessons[lid].get("title", ""),
            "section": {"number": p["section"], "heading": p["heading"]},
            "position": p["position"], "anchor": p.get("anchor") or "",
            "reason": p["reason"], "prompt": p["subject"].strip() + "\n\n" + style_block(labels),
            "labels": labels, "alt": p["alt"], "caption": p["caption"], "aspect": "3:2",
            "requestFile": f"{image_id}.png", "outputFile": f"{image_id}.webp",
            "status": "planned", "check": {"result": None, "reason": None},
            "sourceSha256": None, "bytes": None, "width": None, "height": None,
        })
    return errors + validate(m)


def render_prompts(m: dict) -> str:
    todo = [s for s in m["images"] if s["status"] == "planned"]
    redo = [s for s in m["images"] if s["status"] == "failed"]
    done = sum(1 for s in m["images"] if s["status"] in ("converted", "passed", "inserted"))
    out = [f"# Image prompts — {m['course']['title']}", "",
           "Generate each image, then save it into `incoming/` with the exact filename shown.",
           "PNG, JPG or WebP all work. Landscape 3:2. Deliver in any order and in batches.", ""]
    if redo:
        out += ["## Regenerate", ""]
        for s in redo:
            out += [f"### {s['requestFile']}", f"Why it failed: {s['check']['reason']}", "",
                    "```text", s["prompt"], "```", ""]
    out += ["## To generate", ""]
    for s in todo:
        out += [f"### {s['requestFile']}",
                f"Lesson: {s['lessonTitle']} · Section {s['section']['number']}: {s['section']['heading']}",
                f"Purpose: {s['reason']}", "", "```text", s["prompt"], "```", ""]
    out.append(f"_{len(todo)} to generate · {len(redo)} to regenerate · {done} received_")
    return "\n".join(out) + "\n"


def _write_prompts(images_dir: Path, m: dict) -> None:
    (Path(images_dir) / "PROMPTS.md").write_text(render_prompts(m), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--course", required=True)
    a.add_argument("--plan", required=True)
    a.add_argument("--images-dir", required=True)
    a.add_argument("--replan")
    args = ap.parse_args()
    images_dir = Path(args.images_dir)

    if args.cmd == "add":
        with open(args.course, encoding="utf-8") as f:
            course = json.load(f)
        with open(args.plan, encoding="utf-8") as f:
            plan = json.load(f)
        m = load(images_dir) if (images_dir / "manifest.json").is_file() else new_manifest(course, Path(args.course).name)
        errors = add_slots(m, course, plan, args.replan)
        if errors:
            print("Plan not saved:")
            print("\n".join(f"  - {e}" for e in errors))
            return 1
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "incoming").mkdir(exist_ok=True)
        save(images_dir, m)
        _write_prompts(images_dir, m)
        counts = {}
        for s in m["images"]:
            counts[s["lessonId"]] = counts.get(s["lessonId"], 0) + 1
        print(f"Planned {len(m['images'])} images across {len(counts)} lessons.")
        print(f"Prompt sheet: {images_dir / 'PROMPTS.md'}  ·  drop images into: {images_dir / 'incoming'}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_manifest.py`
Expected: `9 passed`

- [ ] **Step 6: Commit**

```bash
git add skills/nerdit-lesson-illustrator/references/style.md skills/nerdit-lesson-illustrator/scripts/manifest.py skills/nerdit-lesson-illustrator/scripts/test_manifest.py
git commit -m "feat(illustrator): house style, planning rules and image manifest

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Image conversion and previews

**Files:**
- Create: `skills/nerdit-lesson-illustrator/scripts/convert_images.py`
- Test: `skills/nerdit-lesson-illustrator/scripts/test_convert_images.py`

**Interfaces:**
- Consumes: `manifest.load`, `save`, `render_prompts`, slot fields from Task 3
- Produces:
  - constants `MAX_WIDTH = 1200`, `PREVIEW_WIDTH = 640`, `TARGET_BYTES = 150_000`, `HARD_LIMIT_BYTES = 250_000`, `START_QUALITY = 80`, `FLOOR_QUALITY = 60`
  - `encode_webp(source: Path | bytes) -> tuple[bytes, int, int, int]` — (data, width, height, quality)
  - `find_incoming(m: dict, incoming: Path) -> tuple[dict[str, Path], list[str], list[str]]` — (files by image id, missing ids, unexpected names)
  - `convert_all(m: dict, images_dir: Path) -> dict` — report with keys `converted, unchanged, errors, warnings, missing, unexpected`
  - CLI `python convert_images.py --images-dir <dir>`

- [ ] **Step 1: Write the failing tests**

```python
import os

from PIL import Image, ImageDraw

import convert_images as ci
from convert_images import convert_all, encode_webp, find_incoming
from fixture_course import PLAN, course
from manifest import add_slots, new_manifest


def planned():
    m = new_manifest(course(), "course.json")
    assert add_slots(m, course(), PLAN) == []
    return m


def illustration(path, size=(1536, 1024), mode="RGB", fmt=None):
    img = Image.new("RGB", size, (238, 243, 249))
    d = ImageDraw.Draw(img)
    d.rectangle([200, 200, 900, 700], fill=(11, 31, 58))
    d.ellipse([1000, 300, 1400, 700], fill=(20, 184, 166))
    if mode != "RGB":
        img = img.convert(mode)
    img.save(path, fmt)
    return path


def setup(tmp_path):
    (tmp_path / "incoming").mkdir()
    return tmp_path


def test_encode_webp_resizes_and_stays_under_target(tmp_path):
    data, w, h, q = encode_webp(illustration(tmp_path / "a.png"))
    assert (w, h) == (1200, 800) and len(data) <= ci.TARGET_BYTES and q <= ci.START_QUALITY
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def test_unusual_image_modes_convert(tmp_path):
    illustration(tmp_path / "rgba.png", mode="RGBA")
    p = Image.new("P", (300, 200)); p.info["transparency"] = 0; p.save(tmp_path / "pal.png")
    illustration(tmp_path / "cmyk.jpg", mode="CMYK", fmt="JPEG")
    frames = [Image.new("RGB", (300, 200), c) for c in ((255, 0, 0), (0, 0, 255))]
    frames[0].save(tmp_path / "anim.gif", save_all=True, append_images=frames[1:])
    for name in ("rgba.png", "pal.png", "cmyk.jpg", "anim.gif"):
        data, w, h, _ = encode_webp(tmp_path / name)
        assert data[8:12] == b"WEBP" and w > 0 and h > 0


def test_find_incoming_matches_case_and_extension_and_reports_duplicates(tmp_path):
    d = setup(tmp_path)
    illustration(d / "incoming" / "LOAD-BASICS-01-IMG1.PNG")
    illustration(d / "incoming" / "old-style-02-img1.jpeg", fmt="JPEG")
    illustration(d / "incoming" / "old-style-02-img1.png")
    (d / "incoming" / "notes.txt").write_text("x")
    files, missing, unexpected = find_incoming(planned(), d / "incoming")
    assert set(files) == {"load-basics-01-img1", "old-style-02-img1"}
    assert missing == []
    assert "notes.txt" in unexpected and any("(duplicate)" in u for u in unexpected)


def test_convert_all_writes_upload_and_preview_and_updates_slot(tmp_path):
    d = setup(tmp_path)
    illustration(d / "incoming" / "load-basics-01-img1.png")
    m = planned()
    report = convert_all(m, d)
    assert report["converted"] == ["load-basics-01-img1"]
    assert report["missing"] == ["old-style-02-img1"]
    slot = m["images"][0]
    assert slot["status"] == "converted" and (slot["width"], slot["height"]) == (1200, 800)
    assert (d / "upload" / "load-basics-01-img1.webp").stat().st_size == slot["bytes"]
    with Image.open(d / "preview" / "load-basics-01-img1.jpg") as pv:
        assert pv.width == ci.PREVIEW_WIDTH


def test_unchanged_file_is_not_reconverted(tmp_path):
    d = setup(tmp_path)
    illustration(d / "incoming" / "load-basics-01-img1.png")
    m = planned()
    convert_all(m, d)
    assert convert_all(m, d)["unchanged"] == ["load-basics-01-img1"]


def test_new_file_after_fail_is_reconverted_and_check_reset(tmp_path):
    d = setup(tmp_path)
    illustration(d / "incoming" / "load-basics-01-img1.png")
    m = planned()
    convert_all(m, d)
    m["images"][0].update(status="failed", check={"result": "fail", "reason": "garbled text"})
    assert convert_all(m, d)["unchanged"] == ["load-basics-01-img1"]
    illustration(d / "incoming" / "load-basics-01-img1.png", size=(1500, 1000))
    report = convert_all(m, d)
    assert report["converted"] == ["load-basics-01-img1"]
    assert m["images"][0]["status"] == "converted" and m["images"][0]["check"] == {"result": None, "reason": None}


def test_corrupt_file_is_reported_and_slot_unchanged(tmp_path):
    d = setup(tmp_path)
    (d / "incoming" / "load-basics-01-img1.png").write_bytes(b"not an image")
    m = planned()
    report = convert_all(m, d)
    assert any("cannot read image" in e for e in report["errors"])
    assert m["images"][0]["status"] == "planned"


def test_over_hard_limit_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ci, "HARD_LIMIT_BYTES", 1000)
    d = setup(tmp_path)
    illustration(d / "incoming" / "load-basics-01-img1.png")
    m = planned()
    report = convert_all(m, d)
    assert any("over the 250 KB limit" in e for e in report["errors"])
    assert m["images"][0]["status"] == "planned"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_convert_images.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'convert_images'`

- [ ] **Step 3: Implement `convert_images.py`**

```python
"""Match user images in incoming/ to manifest slots, convert them to WebP and write previews.

Usage: python convert_images.py --images-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

import manifest as mf

ACCEPTED = (".png", ".jpg", ".jpeg", ".webp")
MAX_WIDTH = 1200
PREVIEW_WIDTH = 640
TARGET_BYTES = 150_000
HARD_LIMIT_BYTES = 250_000
START_QUALITY = 80
FLOOR_QUALITY = 60


def _prepare(im: Image.Image) -> Image.Image:
    im.seek(0)  # first frame of an animated file
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        return im.convert("RGBA")
    return im.convert("RGB")


def _scaled(img: Image.Image, width: int) -> Image.Image:
    if img.width <= width:
        return img
    return img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)


def encode_webp(source: Path | bytes) -> tuple[bytes, int, int, int]:
    with Image.open(BytesIO(source) if isinstance(source, bytes) else source) as im:
        img = _prepare(im)
    img = _scaled(img, MAX_WIDTH)
    q = START_QUALITY
    while True:
        buf = BytesIO()
        img.save(buf, "WEBP", quality=q, method=6)
        data = buf.getvalue()
        if len(data) <= TARGET_BYTES or q <= FLOOR_QUALITY:
            return data, img.width, img.height, q
        q = max(FLOOR_QUALITY, q - 5)


def _write_preview(webp: bytes, dst: Path) -> None:
    with Image.open(BytesIO(webp)) as im:
        img = im.convert("RGBA")
    flat = Image.new("RGB", img.size, (255, 255, 255))
    flat.paste(img, mask=img.split()[3])
    _scaled(flat, PREVIEW_WIDTH).save(dst, "JPEG", quality=80)


def find_incoming(m: dict, incoming: Path) -> tuple[dict[str, Path], list[str], list[str]]:
    wanted = {Path(s["requestFile"]).stem.lower(): s["id"] for s in m["images"]}
    files, unexpected = {}, []
    if incoming.is_dir():
        for f in sorted(incoming.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            image_id = wanted.get(f.stem.lower()) if f.suffix.lower() in ACCEPTED else None
            if image_id is None:
                unexpected.append(f.name)
            elif image_id in files:
                unexpected.append(f"{f.name} (duplicate)")
            else:
                files[image_id] = f
    missing = [s["id"] for s in m["images"] if s["id"] not in files and s["status"] in ("planned", "failed")]
    return files, missing, unexpected


def convert_all(m: dict, images_dir: Path) -> dict:
    images_dir = Path(images_dir)
    files, missing, unexpected = find_incoming(m, images_dir / "incoming")
    (images_dir / "upload").mkdir(exist_ok=True)
    (images_dir / "preview").mkdir(exist_ok=True)
    report = {"converted": [], "unchanged": [], "errors": [], "warnings": [],
              "missing": missing, "unexpected": unexpected}
    slots = {s["id"]: s for s in m["images"]}
    for image_id, f in files.items():
        slot = slots[image_id]
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        if sha == slot.get("sourceSha256") and slot["status"] != "planned":
            report["unchanged"].append(image_id)
            continue
        try:
            data, w, h, q = encode_webp(f)
        except (UnidentifiedImageError, OSError) as e:
            report["errors"].append(f"{f.name}: cannot read image ({e})")
            continue
        if len(data) > HARD_LIMIT_BYTES:
            report["errors"].append(f"{f.name}: {len(data) // 1000} KB after compression, over the 250 KB limit")
            continue
        if len(data) > TARGET_BYTES:
            report["warnings"].append(f"{f.name}: {len(data) // 1000} KB at quality {q}, above the 150 KB target")
        (images_dir / "upload" / slot["outputFile"]).write_bytes(data)
        _write_preview(data, images_dir / "preview" / f"{image_id}.jpg")
        slot.update(status="converted", sourceSha256=sha, bytes=len(data), width=w, height=h)
        slot["check"] = {"result": None, "reason": None}
        report["converted"].append(image_id)
    return report


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--images-dir", required=True)
    images_dir = Path(ap.parse_args().images_dir)
    m = mf.load(images_dir)
    report = convert_all(m, images_dir)
    mf.save(images_dir, m)
    (images_dir / "PROMPTS.md").write_text(mf.render_prompts(m), encoding="utf-8")
    print(f"Converted {len(report['converted'])} · unchanged {len(report['unchanged'])} · "
          f"missing {len(report['missing'])} · errors {len(report['errors'])}")
    for key in ("errors", "warnings"):
        for line in report[key]:
            print(f"  {key[:-1]}: {line}")
    if report["missing"]:
        print("  waiting for: " + ", ".join(f"{i}.png" for i in report["missing"]))
    if report["unexpected"]:
        print("  ignored files: " + ", ".join(report["unexpected"]))
    print(f"Previews to check: {images_dir / 'preview'}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_convert_images.py`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/convert_images.py skills/nerdit-lesson-illustrator/scripts/test_convert_images.py
git commit -m "feat(illustrator): convert user images to small WebP with previews

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Record visual-check results

**Files:**
- Modify: `skills/nerdit-lesson-illustrator/scripts/manifest.py` (add `record_checks`, `accept`, and the `record` / `accept` subcommands)
- Test: `skills/nerdit-lesson-illustrator/scripts/test_manifest_checks.py`

**Interfaces:**
- Consumes: slot fields, `style_block`, `render_prompts`
- Produces:
  - `record_checks(m: dict, results: list[dict]) -> list[str]` — each result `{"id": str, "result": "pass"|"fail", "reason": str, "revisedSubject"?: str}`
  - `accept(m: dict, image_id: str) -> list[str]`
  - CLI `python manifest.py record --images-dir <dir> --results <results.json>` and `python manifest.py accept --images-dir <dir> --id <image-id>`

- [ ] **Step 1: Write the failing tests**

```python
from fixture_course import PLAN, course
from manifest import accept, add_slots, new_manifest, record_checks, render_prompts


def converted():
    m = new_manifest(course(), "course.json")
    assert add_slots(m, course(), PLAN) == []
    for s in m["images"]:
        s.update(status="converted", width=1200, height=800, bytes=90_000)
    return m


def test_pass_and_fail_update_status_and_reason():
    m = converted()
    errors = record_checks(m, [
        {"id": "load-basics-01-img1", "result": "pass", "reason": "Shows the conveyor clearly."},
        {"id": "old-style-02-img1", "result": "fail", "reason": "Label reads 'Strat'.",
         "revisedSubject": "A student opening a notebook beside a laptop, label spelled Start."},
    ])
    assert errors == []
    a, b = m["images"]
    assert a["status"] == "passed" and a["check"]["result"] == "pass"
    assert b["status"] == "failed" and b["check"]["reason"] == "Label reads 'Strat'."
    assert b["prompt"].startswith("A student opening a notebook beside a laptop, label spelled Start.")
    assert "#0B1F3A" in b["prompt"]
    out = render_prompts(m)
    assert "## Regenerate" in out and "Why it failed: Label reads 'Strat'." in out


def test_fail_needs_reason_and_unknown_ids_and_bad_status_are_errors():
    m = converted()
    m["images"][1]["status"] = "planned"
    errors = record_checks(m, [
        {"id": "load-basics-01-img1", "result": "fail"},
        {"id": "nope", "result": "pass", "reason": "x"},
        {"id": "old-style-02-img1", "result": "pass", "reason": "x"},
        {"id": "load-basics-01-img1", "result": "maybe", "reason": "x"},
    ])
    assert any("a fail needs a reason" in e for e in errors)
    assert any("unknown image id nope" in e for e in errors)
    assert any("status planned cannot be checked" in e for e in errors)
    assert any("result must be pass or fail" in e for e in errors)


def test_accept_overrides_a_fail():
    m = converted()
    record_checks(m, [{"id": "load-basics-01-img1", "result": "fail", "reason": "Too dark."}])
    assert accept(m, "load-basics-01-img1") == []
    assert m["images"][0]["status"] == "passed"
    assert m["images"][0]["check"]["reason"] == "accepted by reviewer"
    assert accept(m, "old-style-02-img1") == [] and accept(m, "nope") == ["unknown image id nope"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_manifest_checks.py`
Expected: FAIL — `ImportError: cannot import name 'accept' from 'manifest'`

- [ ] **Step 3: Add `record_checks` and `accept` to `manifest.py`**

Insert above `def _write_prompts`:

```python
def record_checks(m: dict, results: list[dict]) -> list[str]:
    slots = {s["id"]: s for s in m["images"]}
    errors = []
    for r in results:
        s = slots.get(r.get("id"))
        if s is None:
            errors.append(f"unknown image id {r.get('id')}")
            continue
        if s["status"] not in ("converted", "passed", "failed"):
            errors.append(f"{s['id']}: status {s['status']} cannot be checked")
            continue
        if r.get("result") == "pass":
            s["status"] = "passed"
            s["check"] = {"result": "pass", "reason": r.get("reason")}
        elif r.get("result") == "fail":
            if not r.get("reason"):
                errors.append(f"{s['id']}: a fail needs a reason")
                continue
            s["status"] = "failed"
            s["check"] = {"result": "fail", "reason": r["reason"]}
            if r.get("revisedSubject"):
                s["prompt"] = r["revisedSubject"].strip() + "\n\n" + style_block(s["labels"])
        else:
            errors.append(f"{s['id']}: result must be pass or fail")
    return errors


def accept(m: dict, image_id: str) -> list[str]:
    s = next((x for x in m["images"] if x["id"] == image_id), None)
    if s is None:
        return [f"unknown image id {image_id}"]
    if s["status"] not in ("converted", "failed"):
        return [f"{image_id}: only converted or failed images can be accepted"]
    s["status"] = "passed"
    s["check"] = {"result": "pass", "reason": "accepted by reviewer"}
    return []
```

Note: `accept(m, "old-style-02-img1")` in the test succeeds because that slot is `converted`.

- [ ] **Step 4: Add the `record` and `accept` subcommands**

In `main()`, after the `add` parser is defined, add:

```python
    r = sub.add_parser("record")
    r.add_argument("--images-dir", required=True)
    r.add_argument("--results", required=True)
    c = sub.add_parser("accept")
    c.add_argument("--images-dir", required=True)
    c.add_argument("--id", required=True)
```

and replace the final `return 2` with:

```python
    m = load(images_dir)
    if args.cmd == "record":
        with open(args.results, encoding="utf-8") as f:
            errors = record_checks(m, json.load(f))
    else:
        errors = accept(m, args.id)
    if errors:
        print("Not saved:")
        print("\n".join(f"  - {e}" for e in errors))
        return 1
    save(images_dir, m)
    _write_prompts(images_dir, m)
    passed = sum(1 for s in m["images"] if s["status"] == "passed")
    failed = sum(1 for s in m["images"] if s["status"] == "failed")
    print(f"Saved. passed {passed} · failed {failed} (see Regenerate in PROMPTS.md)")
    return 0
```

- [ ] **Step 5: Run the manifest tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_manifest.py test_manifest_checks.py`
Expected: `12 passed`

- [ ] **Step 6: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/manifest.py skills/nerdit-lesson-illustrator/scripts/test_manifest_checks.py
git commit -m "feat(illustrator): record visual-check results and reviewer overrides

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Insert image blocks into lessons

**Files:**
- Create: `skills/nerdit-lesson-illustrator/scripts/insert_images.py` (core functions; the CLI comes in Task 9)
- Test: `skills/nerdit-lesson-illustrator/scripts/test_insert_images.py`

**Interfaces:**
- Consumes: `lessonhtml.locate`, `AnchorNotFound`; slot fields
- Produces:
  - `MARKER` (compiled regex matching one inserted block, including its leading newline)
  - `block(slot: dict) -> str`
  - `strip_inserted(content: str) -> str`
  - `insert_lessons(course: dict, m: dict) -> list[str]` — mutates `course` lessons and slot statuses in place; returns errors

- [ ] **Step 1: Write the failing tests**

```python
import copy

from fixture_course import PLAN, course
from insert_images import block, insert_lessons, strip_inserted
from manifest import add_slots, new_manifest


def passed():
    m = new_manifest(course(), "course.json")
    assert add_slots(m, course(), PLAN) == []
    for s in m["images"]:
        s.update(status="passed", width=1200, height=800, bytes=90_000)
    return m


def test_block_markup_is_exact_and_escaped():
    s = dict(passed()["images"][0], alt='Boxes "ride" a belt', caption="Rows & checks")
    assert block(s) == (
        '\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="load-basics-01-img1">\n'
        '  <img src="load-basics-01-img1.webp" alt="Boxes &quot;ride&quot; a belt" width="1200" height="800"'
        ' loading="lazy" decoding="async" style="display:block;width:100%;height:auto">\n'
        '  <div class="nerdit-figure-caption">Rows &amp; checks</div>\n</div>')


def test_inserts_at_both_placement_kinds_and_marks_inserted():
    c, m = course(), passed()
    assert insert_lessons(c, m) == []
    new = c["lessons"][0]["content"]
    assert 'totals 📦.</p>\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="load-basics-01-img1">' in new
    old = c["lessons"][1]["content"]
    assert 'Old lessons start like this.</p>\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="old-style-02-img1">' in old
    assert all(s["status"] == "inserted" for s in m["images"])


def test_reinserting_is_idempotent_and_strip_restores_the_original():
    c, m = course(), passed()
    insert_lessons(c, m)
    once = copy.deepcopy(c)
    insert_lessons(c, m)
    assert c == once
    assert [strip_inserted(l["content"]) for l in c["lessons"]] == [l["content"] for l in course()["lessons"]]


def test_missing_anchor_fails_only_that_slot():
    c, m = course(), passed()
    c["lessons"][0]["content"] = c["lessons"][0]["content"].replace("A load copies", "A load moves")
    errors = insert_lessons(c, m)
    assert len(errors) == 1 and "load-basics-01-img1" in errors[0] and "--replan load-basics-01" in errors[0]
    assert m["images"][0]["status"] == "passed" and m["images"][1]["status"] == "inserted"


def test_planned_and_failed_slots_are_not_inserted():
    c, m = course(), passed()
    m["images"][0]["status"] = "failed"
    m["images"][1]["status"] = "planned"
    insert_lessons(c, m)
    assert c["lessons"] == course()["lessons"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_insert_images.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'insert_images'`

- [ ] **Step 3: Implement the core of `insert_images.py`**

```python
"""Insert passed images into lessons and build the with-images course JSON.

Usage: python insert_images.py --course <course.json> --images-dir <dir> [--no-optimise] [--contract v10|v9]
"""
from __future__ import annotations

import html
import re

from lessonhtml import AnchorNotFound, locate

MARKER = re.compile(
    r'\n?<div class="nerdit-figure nerdit-illustration" data-nerdit-img="[^"]+">'
    r'.*?<div class="nerdit-figure-caption">.*?</div>\s*</div>', re.S)


def block(slot: dict) -> str:
    alt = html.escape(slot["alt"], quote=True)
    caption = html.escape(slot["caption"], quote=False)
    return (f'\n<div class="nerdit-figure nerdit-illustration" data-nerdit-img="{slot["id"]}">\n'
            f'  <img src="{slot["outputFile"]}" alt="{alt}" width="{slot["width"]}" height="{slot["height"]}"'
            ' loading="lazy" decoding="async" style="display:block;width:100%;height:auto">\n'
            f'  <div class="nerdit-figure-caption">{caption}</div>\n</div>')


def strip_inserted(content: str) -> str:
    return MARKER.sub("", content)


def insert_lessons(course: dict, m: dict) -> list[str]:
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
            placed.append((off, s))
        for off, s in sorted(placed, key=lambda p: (p[0], p[1]["id"]), reverse=True):
            content = content[:off] + block(s) + content[off:]
            s["status"] = "inserted"
        lesson["content"] = content
    for lid, slots in by_lesson.items():
        if lid not in known:
            errors += [f"{s['id']}: lesson {lid} is not in this course" for s in slots]
    return errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_insert_images.py`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/insert_images.py skills/nerdit-lesson-illustrator/scripts/test_insert_images.py
git commit -m "feat(illustrator): idempotent image block insertion

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Optimise heavy existing images

**Files:**
- Create: `skills/nerdit-lesson-illustrator/scripts/optimise_existing.py`
- Test: `skills/nerdit-lesson-illustrator/scripts/test_optimise_existing.py`

**Interfaces:**
- Consumes: `lessonhtml.IMG`, `SRC`; `convert_images.encode_webp`; manifest `existingOptimised` list and slot `outputFile`
- Produces:
  - `MIN_BYTES = 300_000`, `SITE = "https://nerdit.in"`
  - `default_fetch(url: str) -> bytes`
  - `optimise_existing(course: dict, m: dict, upload_dir: Path, fetch=default_fetch, min_bytes: int = MIN_BYTES) -> dict` — report keys `optimised, kept, errors`; mutates lesson HTML and appends `{"lessonId","from","to","bytesBefore","bytesAfter","width","height"}` entries to `m["existingOptimised"]`

- [ ] **Step 1: Write the failing tests**

```python
import os
from io import BytesIO

from PIL import Image

from fixture_course import course
from manifest import new_manifest
from optimise_existing import optimise_existing

OLD_SRC = "https://nerdit.in/lesson-images/test/old-diagram.png"


def noisy_png(w=800, h=600) -> bytes:
    buf = BytesIO()
    Image.frombytes("RGB", (w, h), os.urandom(w * h * 3)).save(buf, "PNG")
    return buf.getvalue()  # random pixels: well over 300 KB as PNG


def test_heavy_image_is_converted_repointed_and_recorded(tmp_path):
    c, m = course(), new_manifest(course(), "course.json")
    big = noisy_png()
    report = optimise_existing(c, m, tmp_path, fetch=lambda url: big)
    content = c["lessons"][1]["content"]
    assert 'src="old-diagram.webp"' in content and OLD_SRC not in content
    assert 'width="800"' in content and 'height="600"' in content
    assert (tmp_path / "old-diagram.webp").is_file()
    entry = m["existingOptimised"][0]
    assert (entry["from"], entry["to"], entry["bytesBefore"]) == (OLD_SRC, "old-diagram.webp", len(big))
    assert report["optimised"] == [f"old-style-02: {OLD_SRC} -> old-diagram.webp"]


def test_small_image_is_kept(tmp_path):
    c, m = course(), new_manifest(course(), "course.json")
    report = optimise_existing(c, m, tmp_path, fetch=lambda url: b"tiny")
    assert report["kept"] == [OLD_SRC] and OLD_SRC in c["lessons"][1]["content"]


def test_download_failure_keeps_the_original(tmp_path):
    def boom(url):
        raise OSError("timed out")
    c, m = course(), new_manifest(course(), "course.json")
    report = optimise_existing(c, m, tmp_path, fetch=boom)
    assert "could not download" in report["errors"][0] and OLD_SRC in c["lessons"][1]["content"]


def test_second_run_reuses_the_manifest_entry_without_downloading(tmp_path):
    m = new_manifest(course(), "course.json")
    big = noisy_png()
    optimise_existing(course(), m, tmp_path, fetch=lambda url: big)
    def never(url):
        raise AssertionError("should not download again")
    c = course()
    optimise_existing(c, m, tmp_path, fetch=never)
    assert 'src="old-diagram.webp"' in c["lessons"][1]["content"]
    assert len(m["existingOptimised"]) == 1


def test_name_collision_gets_a_suffix(tmp_path):
    c, m = course(), new_manifest(course(), "course.json")
    m["images"].append({"outputFile": "old-diagram.webp"})
    big = noisy_png()
    optimise_existing(c, m, tmp_path, fetch=lambda url: big)
    assert m["existingOptimised"][0]["to"] == "old-diagram-2.webp"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_optimise_existing.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'optimise_existing'`

- [ ] **Step 3: Implement `optimise_existing.py`**

```python
"""Shrink heavy images already in lessons: download, convert to WebP, re-point the src.

Used by insert_images.py. The re-pointed bare filename is matched by the admin's
"Import JSON + Images" page to the file of the same name in upload/.
"""
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from pathlib import Path

from convert_images import encode_webp
from lessonhtml import IMG, SRC

MIN_BYTES = 300_000
SITE = "https://nerdit.in"


def default_fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "nerdit-lesson-illustrator"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _absolute(src: str) -> str:
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        return SITE + src
    return src


def _set_dims(tag: str, width: int, height: int) -> str:
    for attr, val in (("width", width), ("height", height)):
        if re.search(rf'\b{attr}="[^"]*"', tag):
            tag = re.sub(rf'\b{attr}="[^"]*"', f'{attr}="{val}"', tag, count=1)
        else:
            tag = tag.replace("<img", f'<img {attr}="{val}"', 1)
    return tag


def optimise_existing(course: dict, m: dict, upload_dir: Path, fetch=default_fetch,
                      min_bytes: int = MIN_BYTES) -> dict:
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    report = {"optimised": [], "kept": [], "errors": []}
    m.setdefault("existingOptimised", [])
    own = {s["outputFile"] for s in m.get("images", [])}
    done = {e["from"]: e for e in m["existingOptimised"]}
    taken = own | {e["to"] for e in m["existingOptimised"]}
    for lesson in course.get("lessons", []):
        content = lesson.get("content") or ""
        for tag in IMG.findall(content):
            sm = SRC.search(tag)
            src = html.unescape(sm.group(1)) if sm else ""
            if not re.match(r"^(https?:)?//|^/", src):
                continue  # data:, bare filenames and our own outputs are left alone
            entry = done.get(src)
            if entry is None:
                try:
                    data = fetch(_absolute(src))
                except Exception as e:
                    report["errors"].append(f"{lesson['id']}: could not download {src} ({e}); kept")
                    continue
                if len(data) < min_bytes:
                    report["kept"].append(src)
                    continue
                try:
                    webp, w, h, _ = encode_webp(data)
                except Exception as e:
                    report["errors"].append(f"{lesson['id']}: could not convert {src} ({e}); kept")
                    continue
                stem = re.sub(r"[^A-Za-z0-9._-]", "-", Path(urllib.parse.urlparse(src).path).stem) or "image"
                name, n = f"{stem}.webp", 2
                while name in taken:
                    name, n = f"{stem}-{n}.webp", n + 1
                (upload_dir / name).write_bytes(webp)
                taken.add(name)
                entry = {"lessonId": lesson["id"], "from": src, "to": name, "bytesBefore": len(data),
                         "bytesAfter": len(webp), "width": w, "height": h}
                m["existingOptimised"].append(entry)
                done[src] = entry
            new_tag = _set_dims(re.sub(r'\bsrc="[^"]*"', f'src="{entry["to"]}"', tag, count=1),
                                entry["width"], entry["height"])
            content = content.replace(tag, new_tag)
            report["optimised"].append(f"{lesson['id']}: {src} -> {entry['to']}")
        lesson["content"] = content
    return report
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_optimise_existing.py`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/optimise_existing.py skills/nerdit-lesson-illustrator/scripts/test_optimise_existing.py
git commit -m "feat(illustrator): re-encode heavy existing lesson images to WebP

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Validate images and compare verifier results

**Files:**
- Create: `skills/nerdit-lesson-illustrator/scripts/check_images.py`
- Test: `skills/nerdit-lesson-illustrator/scripts/test_check_images.py`

**Interfaces:**
- Consumes: `lessonhtml.IMG`, `SRC`, `text`; slot fields; `existingOptimised`; `skills/nerdit-chapter-generator/scripts/verify_course.py` CLI (`--input <list of {id,title,description}> --output <course> --contract v9|v10`, prints `  - <failure>` lines, exit 2 on unreadable files)
- Produces:
  - constants `TARGET = 150_000`, `HARD = 250_000`, `JSON_LIMIT = 1_048_576`, `ALLOWED_HOSTS`, `VERIFY`
  - `json_bytes(course: dict) -> bytes` — the exact bytes apply writes
  - `check(course: dict, m: dict, upload_dir: Path) -> tuple[list[str], list[str]]` — (errors, warnings)
  - `verifier_failures(course: dict, contract: str = "v10") -> collections.Counter`
  - `new_verifier_failures(before: dict, after: dict, contract: str = "v10") -> list[str]`

- [ ] **Step 1: Write the failing tests**

```python
from PIL import Image

import check_images as ck
from check_images import check, new_verifier_failures
from fixture_course import PLAN, course
from insert_images import insert_lessons
from manifest import add_slots, new_manifest


def inserted(tmp_path):
    c, m = course(), new_manifest(course(), "course.json")
    assert add_slots(m, c, PLAN) == []
    for s in m["images"]:
        s.update(status="passed", width=1200, height=800)
        Image.new("RGB", (1200, 800), (238, 243, 249)).save(tmp_path / s["outputFile"], "WEBP", quality=80)
    assert insert_lessons(c, m) == []
    return c, m


def test_valid_course_has_no_errors(tmp_path):
    c, m = inserted(tmp_path)
    assert check(c, m, tmp_path) == ([], [])


def test_missing_lazy_and_missing_file_are_errors(tmp_path):
    c, m = inserted(tmp_path)
    c["lessons"][0]["content"] = c["lessons"][0]["content"].replace(' loading="lazy"', "")
    (tmp_path / "old-style-02-img1.webp").unlink()
    errors, _ = check(c, m, tmp_path)
    assert any('load-basics-01-img1: missing loading="lazy"' in e for e in errors)
    assert any("old-style-02-img1.webp not in upload/" in e for e in errors)


def test_size_limits(tmp_path):
    c, m = inserted(tmp_path)
    (tmp_path / "load-basics-01-img1.webp").write_bytes(b"x" * 160_000)
    (tmp_path / "old-style-02-img1.webp").write_bytes(b"x" * 260_000)
    errors, warnings = check(c, m, tmp_path)
    assert any("above 150 KB target" in w for w in warnings)
    assert any("over 250 KB" in e for e in errors)


def test_data_uri_and_outside_host_are_errors(tmp_path):
    c, m = inserted(tmp_path)
    c["lessons"][1]["content"] += '<img src="data:image/png;base64,AAAA"><img src="https://example.com/x.png">'
    errors, _ = check(c, m, tmp_path)
    assert any("embedded data: image" in e for e in errors)
    assert any("outside host example.com" in e for e in errors)


def test_json_over_import_limit_is_an_error(tmp_path, monkeypatch):
    c, m = inserted(tmp_path)
    monkeypatch.setattr(ck, "JSON_LIMIT", 100)
    errors, _ = check(c, m, tmp_path)
    assert any("admin import limit" in e for e in errors)


def test_new_verifier_failures_reports_only_new_ones():
    before = course()
    after = course()
    after["lessons"][1]["content"] += '<div class="nerdit-figure"><p>no caption</p></div>'
    new = new_verifier_failures(before, after)
    assert any("has no nerdit-figure-caption" in f for f in new)
    assert new_verifier_failures(before, course()) == []


def test_figure_renumbering_is_not_a_new_failure(tmp_path):
    before = course()
    before["lessons"][1]["content"] += '<div class="nerdit-figure"><p>no caption</p></div>'
    after, m = course(), new_manifest(course(), "course.json")
    after["lessons"][1]["content"] = before["lessons"][1]["content"]
    assert add_slots(m, after, PLAN) == []
    for s in m["images"]:
        s.update(status="passed", width=1200, height=800)
    insert_lessons(after, m)  # our captioned figure now precedes the caption-less one
    assert new_verifier_failures(before, after) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_check_images.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'check_images'`

- [ ] **Step 3: Implement `check_images.py`**

```python
"""Validate inserted lesson images, and compare verifier results before and after insertion."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from lessonhtml import IMG, SRC, text

TARGET = 150_000
HARD = 250_000
JSON_LIMIT = 1_048_576
ALLOWED_HOSTS = ("firebasestorage.googleapis.com", "storage.googleapis.com", "nerdit.in",
                 "future-vision-skill-learning.web.app")
VERIFY = Path(__file__).resolve().parents[2] / "nerdit-chapter-generator" / "scripts" / "verify_course.py"
BLOCK = re.compile(r'<div class="nerdit-figure nerdit-illustration" data-nerdit-img="([^"]+)">'
                   r'(.*?)<div class="nerdit-figure-caption">(.*?)</div>\s*</div>', re.S)


def json_bytes(course: dict) -> bytes:
    return (json.dumps(course, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _host_ok(src: str) -> bool:
    host = urlparse("https:" + src if src.startswith("//") else src).hostname or ""
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def check(course: dict, m: dict, upload_dir: Path) -> tuple[list[str], list[str]]:
    upload_dir = Path(upload_dir)
    errors, warnings, seen = [], [], set()
    slots = {s["id"]: s for s in m.get("images", [])}
    for lesson in course.get("lessons", []):
        content = lesson.get("content") or ""
        lid = lesson["id"]
        for tag in IMG.findall(content):
            sm = SRC.search(tag)
            src = sm.group(1) if sm else ""
            if src.startswith("data:"):
                errors.append(f"{lid}: embedded data: image")
            elif re.match(r"^(https?:)?//", src) and not _host_ok(src):
                host = urlparse("https:" + src if src.startswith("//") else src).hostname
                errors.append(f"{lid}: image from outside host {host}")
        for bm in BLOCK.finditer(content):
            image_id, body, caption = bm.groups()
            where = f"{lid}: {image_id}"
            if image_id in seen:
                errors.append(f"{where}: inserted twice")
                continue
            seen.add(image_id)
            slot = slots.get(image_id)
            if slot is None or slot["status"] != "inserted":
                errors.append(f"{where}: not an inserted manifest slot")
                continue
            tm = IMG.search(body)
            tag = tm.group(0) if tm else ""
            for need in ('loading="lazy"', 'decoding="async"'):
                if need not in tag:
                    errors.append(f"{where}: missing {need}")
            for attr in ("alt", "width", "height"):
                if not re.search(rf'\b{attr}="[^"]+"', tag):
                    errors.append(f"{where}: missing {attr}")
            if not text(caption):
                errors.append(f"{where}: empty caption")
            f = upload_dir / slot["outputFile"]
            if not f.is_file():
                errors.append(f"{where}: {slot['outputFile']} not in upload/")
            elif f.stat().st_size > HARD:
                errors.append(f"{where}: {f.stat().st_size // 1000} KB, over 250 KB")
            elif f.stat().st_size > TARGET:
                warnings.append(f"{where}: {f.stat().st_size // 1000} KB, above 150 KB target")
    for s in m.get("images", []):
        if s["status"] == "inserted" and s["id"] not in seen:
            errors.append(f"{s['id']}: marked inserted but not found in any lesson")
    for e in m.get("existingOptimised", []):
        if not (upload_dir / e["to"]).is_file():
            errors.append(f"{e['to']}: optimised file missing from upload/")
    size = len(json_bytes(course))
    if size >= JSON_LIMIT:
        errors.append(f"course JSON is {size} bytes; the admin import limit is {JSON_LIMIT}")
    return errors, warnings


def verifier_failures(course: dict, contract: str = "v10") -> Counter:
    inp = [{"id": l["id"], "title": l.get("title", ""), "description": l.get("title", "")}
           for l in course.get("lessons", [])]
    with tempfile.TemporaryDirectory() as d:
        ip, op = Path(d) / "input.json", Path(d) / "output.json"
        ip.write_text(json.dumps(inp, ensure_ascii=False), encoding="utf-8")
        op.write_bytes(json_bytes(course))
        r = subprocess.run([sys.executable, str(VERIFY), "--input", str(ip), "--output", str(op),
                            "--contract", contract], capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode == 2 or not re.search(r"^(PASS|FAIL) ", r.stdout, re.M):
        # A crash prints a traceback and no summary line; never read that as "no failures".
        raise RuntimeError(f"verify_course.py could not run: {(r.stderr or r.stdout).strip()[-500:]}")
    lines = [ln.strip()[2:] for ln in r.stdout.splitlines() if ln.strip().startswith("- ")]
    # Inserting a figure renumbers later figures and SVGs; compare without the numbers.
    return Counter(re.sub(r"\b(figure|svg) \d+\b", r"\1 N", ln) for ln in lines)


def new_verifier_failures(before: dict, after: dict, contract: str = "v10") -> list[str]:
    return sorted((verifier_failures(after, contract) - verifier_failures(before, contract)).elements())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_check_images.py`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/check_images.py skills/nerdit-lesson-illustrator/scripts/test_check_images.py
git commit -m "feat(illustrator): image validation and before/after verifier comparison

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Apply output builder (insert_images CLI)

**Files:**
- Modify: `skills/nerdit-lesson-illustrator/scripts/insert_images.py` (append `build_output` and `main`)
- Test: `skills/nerdit-lesson-illustrator/scripts/test_build_output.py`

**Interfaces:**
- Consumes: `insert_lessons` (Task 6), `optimise_existing`, `default_fetch` (Task 7), `check`, `new_verifier_failures`, `json_bytes` (Task 8), `manifest.load`, `save`, `render_prompts`
- Produces:
  - `build_output(course_path: Path, images_dir: Path, fetch=default_fetch, optimise: bool = True, contract: str = "v10") -> int` — 0 when the with-images JSON was written, 1 otherwise; prints the report
  - `output_path(course_path: Path) -> Path` — `<stem>.with-images.json` beside the input
  - CLI `python insert_images.py --course <course.json> --images-dir <dir> [--no-optimise] [--contract v10|v9]`

- [ ] **Step 1: Write the failing tests**

```python
import json

from PIL import Image

from fixture_course import PLAN, course
from insert_images import build_output, output_path
from manifest import add_slots, load, new_manifest, save


def ready(tmp_path, statuses=("passed", "passed")):
    src = tmp_path / "course-test_output.json"
    src.write_text(json.dumps(course(), ensure_ascii=False, indent=2), encoding="utf-8")
    images = tmp_path / "images"
    (images / "upload").mkdir(parents=True)
    m = new_manifest(course(), src.name)
    assert add_slots(m, course(), PLAN) == []
    for s, st in zip(m["images"], statuses):
        s.update(status=st, width=1200, height=800)
        Image.new("RGB", (1200, 800), (238, 243, 249)).save(images / "upload" / s["outputFile"], "WEBP")
    save(images, m)
    return src, images


def tiny(url):
    return b"tiny"  # below MIN_BYTES: existing images are kept


def test_writes_with_images_json_and_marks_inserted(tmp_path):
    src, images = ready(tmp_path)
    assert build_output(src, images, fetch=tiny) == 0
    out = output_path(src)
    assert out.name == "course-test_output.with-images.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["lessons"][0]["content"].count('data-nerdit-img="') == 1
    assert [s["status"] for s in load(images)["images"]] == ["inserted", "inserted"]
    assert json.loads(src.read_text(encoding="utf-8")) == course()  # input untouched


def test_running_twice_gives_identical_output(tmp_path):
    src, images = ready(tmp_path)
    build_output(src, images, fetch=tiny)
    first = output_path(src).read_bytes()
    assert build_output(src, images, fetch=tiny) == 0
    assert output_path(src).read_bytes() == first


def test_failure_writes_nothing_and_keeps_manifest(tmp_path):
    src, images = ready(tmp_path)
    broken = course()
    broken["lessons"][0]["content"] = broken["lessons"][0]["content"].replace("A load copies", "A load moves")
    src.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    before = load(images)
    assert build_output(src, images, fetch=tiny) == 1
    assert not output_path(src).exists()
    assert load(images) == before


def test_only_planned_slots_still_writes_output_with_nothing_inserted(tmp_path):
    src, images = ready(tmp_path, statuses=("planned", "planned"))
    assert build_output(src, images, fetch=tiny) == 0
    data = json.loads(output_path(src).read_text(encoding="utf-8"))
    assert data["lessons"] == course()["lessons"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q test_build_output.py`
Expected: FAIL — `ImportError: cannot import name 'build_output' from 'insert_images'`

- [ ] **Step 3: Append `build_output` and `main` to `insert_images.py`**

Add these imports below the existing ones at the top of the file:

```python
import argparse
import copy
import json
import sys
from pathlib import Path

import manifest as mf
from check_images import check, json_bytes, new_verifier_failures
from optimise_existing import default_fetch, optimise_existing
```

Append at the end of the file:

```python
def output_path(course_path: Path) -> Path:
    course_path = Path(course_path)
    return course_path.with_name(course_path.stem + ".with-images.json")


def build_output(course_path: Path, images_dir: Path, fetch=default_fetch, optimise: bool = True,
                 contract: str = "v10") -> int:
    course_path, images_dir = Path(course_path), Path(images_dir)
    with open(course_path, encoding="utf-8") as f:
        original = json.load(f)
    work = copy.deepcopy(original)
    m = copy.deepcopy(mf.load(images_dir))
    upload = images_dir / "upload"
    lines, problems = [], []

    if optimise:
        rep = optimise_existing(work, m, upload, fetch)
        lines += [f"  optimised: {x}" for x in rep["optimised"]]
        problems += rep["errors"]
    problems += insert_lessons(work, m)
    errors, warnings = check(work, m, upload)
    problems += errors
    problems += [f"new verifier failure: {x}" for x in new_verifier_failures(original, work, contract)]

    counts = {st: sum(1 for s in m["images"] if s["status"] == st) for st in mf.STATUSES}
    print(f"inserted {counts['inserted']} · waiting for files {counts['planned']} · "
          f"to check {counts['converted']} · failed {counts['failed']}")
    print("\n".join(lines + [f"  warning: {w}" for w in warnings]))
    if problems:
        print("Not written — fix these first:")
        print("\n".join(f"  - {p}" for p in problems))
        return 1
    out = output_path(course_path)
    out.write_bytes(json_bytes(work))
    mf.save(images_dir, m)
    (images_dir / "PROMPTS.md").write_text(mf.render_prompts(m), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Admin → Import JSON + Images: choose {out.name} and the folder {upload}")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--images-dir", required=True)
    ap.add_argument("--no-optimise", action="store_true")
    ap.add_argument("--contract", choices=["v9", "v10"], default="v10")
    args = ap.parse_args()
    return build_output(Path(args.course), Path(args.images_dir), optimise=not args.no_optimise,
                        contract=args.contract)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the whole illustrator suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: `54 passed` (10 + 3 + 9 + 8 + 3 + 5 + 5 + 7 + 4 — every test file in the folder)

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-lesson-illustrator/scripts/insert_images.py skills/nerdit-lesson-illustrator/scripts/test_build_output.py
git commit -m "feat(illustrator): apply step writes the with-images course JSON

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: SKILL.md, hand-off from the chapter generator, plugin metadata

**Files:**
- Create: `skills/nerdit-lesson-illustrator/SKILL.md`
- Modify: `skills/nerdit-chapter-generator/SKILL.md:473-477` (summary list)
- Modify: `.claude-plugin/plugin.json` (version, description)
- Modify: `README.md` (one new section)

**Interfaces:**
- Consumes: every CLI from Tasks 2–9 and `references/style.md`
- Produces: the user-facing skill `nerdit-lesson-illustrator` with `plan` and `apply` runs

- [ ] **Step 1: Write `SKILL.md`**

````markdown
---
name: nerdit-lesson-illustrator
description: >
  Plans and inserts concept illustrations into a NERDIT course JSON after its content is final.
  Use when the user wants images for lessons ("add images to this course", "plan lesson images",
  "illustrate the lessons", "apply the images I generated"). Two runs: `plan` writes a prompt
  sheet and placements for images the user generates in their own tool (Codex CLI or any other);
  `apply` converts the generated images to small WebP files, checks each one against its lesson,
  inserts them, and produces a JSON plus image folder for the admin's "Import JSON + Images" page.
  Works for new courses (the chapter generator's output JSON) and existing courses (a JSON
  exported from the admin). Never calls an image API.
---

# NERDIT Lesson Illustrator

All scripts live in `scripts/` next to this file. Run them with `python <script>` from any folder,
passing absolute paths. `<images>` is the `images/` folder next to the course JSON.

House style, planning rules and visual-check criteria: `references/style.md`. Read it before
planning and before checking.

## Run 1 — plan

1. Locate the course JSON. New course: `course-<chapter>_output.json` from the chapter generator's
   workdir. Existing course: the file the user exported with "Export output JSON" in the admin.
   If neither is given, ask for it.
2. `python scripts/extract_outline.py --course <course.json>` and read the outline.
3. Apply the planning rules in `references/style.md`. Write `<images>/plan.json`: a JSON list,
   one item per image:
   `{"lessonId", "section", "heading", "position", "anchor", "reason", "subject", "labels", "alt", "caption"}`.
   `section` and `heading` come from the `§` line; `anchor` is copied exactly from a `¶` line of
   that section (leave it empty for `before-practice`). Include only lessons not yet in
   `<images>/manifest.json`; to redo one lesson use `--replan <lesson-id>` with only that lesson's items.
4. `python scripts/manifest.py add --course <course.json> --plan <images>/plan.json --images-dir <images>`.
   On errors, fix `plan.json` and run again (nothing is saved until the plan is clean).
5. Tell the user: how many images per lesson and why (lessons with no visual first), the path of
   `PROMPTS.md`, and that each image must be saved into `<images>/incoming/` under the filename
   shown. Then stop.

## Run 2 — apply

1. `python scripts/convert_images.py --images-dir <images>`. It reports converted, waiting and
   ignored files.
2. Read every preview it lists in `<images>/preview/` (640 px JPEGs) and judge each against its
   slot in `manifest.json` using the visual-check criteria in `references/style.md`. Write
   `<images>/results.json`: `[{"id", "result": "pass"|"fail", "reason", "revisedSubject"?}]`.
   For a fail, give a one-line reason and a corrected `revisedSubject` that fixes the cause.
3. `python scripts/manifest.py record --images-dir <images> --results <images>/results.json`.
   If the user wants to keep an image you failed: `python scripts/manifest.py accept --images-dir <images> --id <image-id>`.
4. `python scripts/insert_images.py --course <course.json> --images-dir <images>`. It also
   re-encodes heavy images already in the lessons (`--no-optimise` skips that). If it reports
   problems, nothing is written: fix them (usually `--replan <lesson-id>` for a moved paragraph)
   and run again.
5. Tell the user what was inserted, what is still waiting or failed (see "Regenerate" in
   `PROMPTS.md`), and the upload step:
   Admin → Import JSON + Images → `course-<chapter>_output.with-images.json` + folder `<images>/upload/`
   (create mode for a new course, update mode for an existing one).

Apply can run as often as needed: images arrive in batches, and re-running gives the same lessons.
A new course whose JSON the chapter generator rebuilt loses inserted images; run apply again — the
manifest and `upload/` restore them without generating anything.

## Never

- Call an image generation API, or embed images as `data:` URIs.
- Edit the input course JSON.
- Ask for text, numbers, charts or tables inside an image; exact data belongs in SVG figures.
````

- [ ] **Step 2: Point the chapter generator to the illustrator**

In `skills/nerdit-chapter-generator/SKILL.md`, replace:

```markdown
- Any notable decisions made (e.g., which visualization type was chosen per lesson)
```

with:

```markdown
- Any notable decisions made (e.g., which visualization type was chosen per lesson)
- Next step: once the course is final, the `nerdit-lesson-illustrator` skill can plan concept
  illustrations for it (`plan`), then insert the images the user generates (`apply`)
```

- [ ] **Step 3: Bump the plugin version and description**

In `.claude-plugin/plugin.json` set `"version": "3.1.0"` and append to `"description"`:
` Includes nerdit-lesson-illustrator, which plans concept illustrations, emits prompts for user-generated images, and inserts them as small WebP files for the admin JSON + images import.`

- [ ] **Step 4: Add a README section**

Append to `README.md`:

```markdown
## Lesson images (nerdit-lesson-illustrator)

After a course is final, run the `nerdit-lesson-illustrator` skill on its output JSON (or on a
JSON exported from the admin for an existing course).

1. `plan` — writes `images/PROMPTS.md` (one ready-to-paste prompt per image, with the filename to
   save as) and `images/manifest.json`.
2. Generate the images in any tool and save them into `images/incoming/`.
3. `apply` — converts to WebP (≤ 1200 px, ~150 KB), checks each image against its lesson, inserts
   them and writes `course-<chapter>_output.with-images.json`.
4. Admin → Import JSON + Images: the with-images JSON and the `images/upload/` folder.

Tests: `cd skills/nerdit-lesson-illustrator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
```

- [ ] **Step 5: Verify the skill files and both test suites**

Run:
```bash
python -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])"
cd skills/nerdit-lesson-illustrator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q && cd ../../nerdit-chapter-generator/scripts && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```
Expected: `3.1.0`, then `54 passed`, then `120 passed`

- [ ] **Step 6: Commit**

```bash
git add skills/nerdit-lesson-illustrator/SKILL.md skills/nerdit-chapter-generator/SKILL.md .claude-plugin/plugin.json README.md
git commit -m "feat(illustrator): skill instructions, generator hand-off, v3.1.0

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: End-to-end trial on the Data Modelling course

**Files:**
- Work folder (not committed): `../nerdit/generated/data-modelling-etl-data-warehousing-for-analysts/`
- Read: `course-data-modelling-etl-data-warehousing-for-analysts_output.json` (16 lessons; each has one PNG on `https://nerdit.in/lesson-images/…`, about 1.4 MB each)

**Interfaces:**
- Consumes: all CLIs, used exactly as `SKILL.md` describes

- [ ] **Step 1: Optimise the existing images with an empty plan**

```bash
D=../nerdit/generated/data-modelling-etl-data-warehousing-for-analysts
S=skills/nerdit-lesson-illustrator/scripts
mkdir -p "$D/images" && echo "[]" > "$D/images/plan.json"
python $S/manifest.py add --course "$D/course-data-modelling-etl-data-warehousing-for-analysts_output.json" --plan "$D/images/plan.json" --images-dir "$D/images"
python $S/insert_images.py --course "$D/course-data-modelling-etl-data-warehousing-for-analysts_output.json" --images-dir "$D/images"
```
Expected: 16 `optimised:` lines, `Wrote …with-images.json`, and 16 `.webp` files in `$D/images/upload/`. Check that each file is under 150 KB:
`python -c "import pathlib; s=[p.stat().st_size for p in pathlib.Path('$D/images/upload').glob('*.webp')]; print(len(s), max(s))"` → `16` and a maximum below `150000`.

- [ ] **Step 2: Plan two lessons**

Run `python $S/extract_outline.py --course "$D/course-data-modelling-etl-data-warehousing-for-analysts_output.json"`, follow `SKILL.md` Run 1 for the first two lessons only (write `plan.json` with their slots), then run `manifest.py add` again with `--plan` pointing at the new `plan.json`.
Expected: `PROMPTS.md` lists 1–3 images per lesson for those two lessons, each with a filename and a complete prompt containing the house style block.

- [ ] **Step 3: User generates one image**

Ask the user to generate one image from `PROMPTS.md` and save it into `$D/images/incoming/` under its filename. Wait for them.

- [ ] **Step 4: Apply**

Follow `SKILL.md` Run 2: `convert_images.py`, read the preview, write `results.json`, `manifest.py record`, `insert_images.py`.
Expected: the image is inserted after its anchor paragraph, the other slots are listed as waiting, and `Wrote …with-images.json` is printed.

- [ ] **Step 5: Import through the admin (user)**

Ask the user to open Admin → Import JSON + Images in update mode for the Data Modelling course, select the with-images JSON and `$D/images/upload/`, check that the matching table shows every image as "Ready to upload", preview one lesson, and publish.
Expected: the lesson shows the new illustration and the optimised WebP images. In the browser's network tab, the image URLs are on `firebasestorage.googleapis.com` and each is under 150 KB.

- [ ] **Step 6: Record the result**

Note any fix needed in the scripts as a new task. If none, there is nothing to commit for this task.

---

### Task 12: One-year cache header on admin image uploads (two repos — deploy needs approval)

**Files:**
- Modify: `../nerdit/shared/src/services/courseMediaService.ts:26` (nerdit repo)
- Test: `../nerdit-admin/tests/courseMediaService.test.ts` (nerdit-admin repo)
- Create: `../nerdit/scripts/set-media-cache-control.mjs` (nerdit repo)

**Interfaces:**
- Consumes: `uploadCourseImage(file: File, courseId: string): Promise<MediaItem>` (existing)
- Produces: uploads carry `cacheControl: 'public, max-age=31536000, immutable'`; a dry-run-by-default script for objects already under `media/courses/`

> **Approval gates:** building or deploying the admin and running the script with `--apply` change production. Do neither without the user's explicit yes in that session. Both working trees contain unrelated uncommitted changes: stage only the files below.

- [ ] **Step 1: Write the failing test**

Create `../nerdit-admin/tests/courseMediaService.test.ts`:

```ts
// @vitest-environment node
import { describe, it, expect, vi } from 'vitest';

const { uploadBytes } = vi.hoisted(() => ({ uploadBytes: vi.fn(async () => ({})) }));
vi.mock('firebase/storage', () => ({
  ref: vi.fn((_storage: unknown, path: string) => ({ path })),
  uploadBytes,
  getDownloadURL: vi.fn(async () => 'https://firebasestorage.googleapis.com/x'),
}));
vi.mock('firebase/firestore', () => ({
  doc: vi.fn(() => ({})),
  getDocFromServer: vi.fn(async () => ({ exists: () => false })),
  setDoc: vi.fn(async () => undefined),
}));
vi.mock('../../nerdit/shared/src/services/storageService', () => ({ firebaseDb: {}, firebaseStorage: {} }));

import { uploadCourseImage } from '../../nerdit/shared/src/services/courseMediaService';

describe('uploadCourseImage', () => {
  it('uploads with a one-year immutable cache header', async () => {
    const file = new File([new Uint8Array([1, 2, 3])], 'lesson-img1.webp', { type: 'image/webp' });
    await uploadCourseImage(file, 'course-1');
    expect(uploadBytes).toHaveBeenCalledWith(expect.anything(), file, {
      contentType: 'image/webp',
      cacheControl: 'public, max-age=31536000, immutable',
    });
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ../nerdit-admin && npx vitest run tests/courseMediaService.test.ts`
Expected: FAIL — `uploadBytes` was called with `{ contentType: 'image/webp' }` only.

- [ ] **Step 3: Add the header**

In `../nerdit/shared/src/services/courseMediaService.ts` replace:

```ts
  await uploadBytes(storageRef, file, { contentType: file.type });
```

with:

```ts
  // The path contains the file's SHA-256, so a URL never changes content: safe to cache for a year.
  await uploadBytes(storageRef, file, { contentType: file.type, cacheControl: 'public, max-age=31536000, immutable' });
```

- [ ] **Step 4: Run the test and the admin suite**

Run: `cd ../nerdit-admin && npx vitest run tests/courseMediaService.test.ts && npx vitest run`
Expected: the new test passes; the full suite shows no new failures compared with a run before Step 3.

- [ ] **Step 5: Write the metadata script (dry run by default)**

Create `../nerdit/scripts/set-media-cache-control.mjs`:

```js
/**
 * Set a one-year immutable Cache-Control on images already uploaded under media/courses/.
 * New uploads get it from uploadCourseImage; this fixes the ones uploaded before.
 *
 *   node scripts/set-media-cache-control.mjs           # dry run: lists what would change
 *   node scripts/set-media-cache-control.mjs --apply   # writes metadata (production: needs approval)
 *
 * Auth: the Firebase CLI login (`firebase login`), the same way scripts/lib/firestoreRest.mjs works.
 */
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

const BUCKET = 'future-vision-skill-learning.firebasestorage.app';
const PREFIX = 'media/courses/';
const CACHE = 'public, max-age=31536000, immutable';
const apply = process.argv.includes('--apply');

const require = createRequire(join(execSync('npm root -g').toString().trim(), 'firebase-tools', 'package.json'));
const store = JSON.parse(readFileSync(join(homedir(), '.config', 'configstore', 'firebase-tools.json'), 'utf8'));
const { access_token: token } = await require('./lib/auth.js').getAccessToken(
  store.tokens.refresh_token, store.tokens.scopes ?? ['https://www.googleapis.com/auth/cloud-platform']);
const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
const api = `https://storage.googleapis.com/storage/v1/b/${BUCKET}/o`;

let pageToken = '', seen = 0, changed = 0;
do {
  const url = `${api}?prefix=${encodeURIComponent(PREFIX)}&fields=nextPageToken,items(name,cacheControl,contentType)${pageToken ? `&pageToken=${encodeURIComponent(pageToken)}` : ''}`;
  const page = await (await fetch(url, { headers })).json();
  for (const item of page.items ?? []) {
    seen++;
    if (!item.contentType?.startsWith('image/') || item.cacheControl === CACHE) continue;
    changed++;
    if (!apply) { console.log(`would set: ${item.name} (now: ${item.cacheControl ?? 'none'})`); continue; }
    const r = await fetch(`${api}/${encodeURIComponent(item.name)}`, { method: 'PATCH', headers, body: JSON.stringify({ cacheControl: CACHE }) });
    if (!r.ok) throw new Error(`${item.name}: ${r.status} ${await r.text()}`);
    console.log(`set: ${item.name}`);
  }
  pageToken = page.nextPageToken ?? '';
} while (pageToken);
console.log(`${seen} objects under ${PREFIX}; ${changed} ${apply ? 'updated' : 'would change'}${apply ? '' : ' (dry run; add --apply to write)'}`);
```

- [ ] **Step 6: Dry-run the script (read-only)**

Run: `cd ../nerdit && node scripts/set-media-cache-control.mjs`
Expected: a list of `would set:` lines for existing course images and a final count line ending in `(dry run; add --apply to write)`. Show the count to the user. Run `--apply` only after their explicit yes.

- [ ] **Step 7: Commit in both repos (only these files)**

```bash
cd ../nerdit && git add shared/src/services/courseMediaService.ts scripts/set-media-cache-control.mjs && git commit -m "feat(media): one-year immutable cache header for course image uploads

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
cd ../nerdit-admin && git add tests/courseMediaService.test.ts && git commit -m "test(media): course image uploads set the cache header

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 8: Deploy (only with approval)**

Ask the user whether to deploy the admin now. On a yes: `cd ../nerdit-admin && npm run build && firebase deploy --only hosting:admin` (target `admin` → site `fv-admin-panel` in `nerdit-admin/.firebaserc`). Then upload one image through the admin and confirm with the browser's network tab that the response carries `cache-control: public, max-age=31536000, immutable`.
