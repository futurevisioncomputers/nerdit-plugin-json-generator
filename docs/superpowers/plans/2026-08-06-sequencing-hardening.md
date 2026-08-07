# Sequencing Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the plugin from generating lessons that teach with constructs a later lesson owns, so a learner never meets a `for` loop in the conditions lesson or `LLMChain` before the chains lesson.

**Architecture:** Three layers, cheapest first. (1) *Prevention* — every lesson writer receives the curriculum around it and a rule that its lesson's vocabulary is bounded by what came before. (2) *Declaration* — each writer records the terms it taught and the terms it merely used, turning a heuristic guess about who owns a concept into a fact. (3) *Enforcement* — a deterministic script fails the run on any forward reference, and the orchestrator feeds the exact violations back into a regeneration pass. Layer 1 shipped earlier in this session; this plan builds 2 and 3, plus an input pre-flight so bad syllabus data cannot silently degrade all three.

**Tech Stack:** Python 3 standard library only (no third-party imports in `scripts/`), pytest for tests, Markdown agent/skill definitions.

## Global Constraints

- `scripts/*.py` must import only the Python standard library — the plugin ships no dependency manifest.
- Every script keeps its existing CLI contract; new flags are optional with backward-compatible defaults.
- Tests live beside the script as `scripts/test_<name>.py` and run with `python -m pytest` from `scripts/`.
- Agent files (`agents/*.md`) are prompts, not code: keep them terse, imperative, and free of examples longer than 3 lines.
- No generated artifact may be written into the plugin folder — workdir paths only.
- Lesson `id` values are opaque keys referenced by learner progress records; never renumber or rewrite them.
- Current baseline: `scripts/` has 61 passing tests. No task may reduce that count.

---

## Already shipped (context, not tasks)

Completed earlier in this session; later tasks build directly on these:

- `SKILL.md` passes `PRIOR_TOPICS` / `UPCOMING_TOPICS` to every `nerdit-lesson-writer`, runs `check_sequence.py` as Step 4b, and checks input order in Step 1.
- `references/CORE.md` teaching constitution principle 9 forbids untaught constructs.
- `agents/nerdit-lesson-writer.md` has a **Sequencing** section; quiz rules and reform mode inherit it.
- `agents/nerdit-qa-validator.md` has a per-lesson sequencing checklist item.
- `scripts/check_sequence.py` + `scripts/test_check_sequence.py` — heuristic ownership (identifier families, plural folding, SQL-flavored construct scoping).

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/check_input.py` (create) | Pre-flight on the input array: weak descriptions, duplicate ids, suspected order inversions. Runs before any generation. |
| `scripts/test_check_input.py` (create) | Tests for the above. |
| `scripts/check_sequence.py` (modify) | Gains `--concepts-dir` (declared ownership overrides the heuristic) and `--allow` (course-level assumed knowledge). |
| `scripts/test_check_sequence.py` (modify) | Tests for the two new inputs. |
| `agents/nerdit-lesson-writer.md` (modify) | Writes a third artifact `<id>.concepts.json`; accepts a `VIOLATIONS` block on regeneration; foundations-lesson rule; backward-callback rule. |
| `agents/nerdit-qa-validator.md` (modify) | Checks the manifest exists and is consistent with the lesson. |
| `skills/nerdit-chapter-generator/SKILL.md` (modify) | Step 1 runs the pre-flight; Step 2b passes `CONCEPTS_PATH`; Step 4b runs `--strict` with `--concepts-dir`; adds the mandatory repair loop. |
| `references/CORE.md` (modify) | Within-lesson ordering rule; backward-callback guidance. |
| `README.md` (modify) | Document the manifest in the sequencing section. |

---

### Task 1: Input pre-flight script

Catches the garbage-in case observed in two live courses, where every `description` was a verbatim copy of its `title`. Ownership detection reads descriptions, so this silently weakens every downstream check.

**Files:**
- Create: `skills/nerdit-chapter-generator/scripts/check_input.py`
- Test: `skills/nerdit-chapter-generator/scripts/test_check_input.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `audit(input_lessons) -> list[tuple[str, str, str]]` of `(severity, lesson_id, message)` where severity is `"ERROR"` or `"WARN"`. CLI: `python check_input.py --input <path> [--strict]`, exit 2 when `--strict` and any `ERROR`.

- [ ] **Step 1: Write the failing tests**

```python
import json
import subprocess
import sys
import os

from check_input import audit

SCRIPT = os.path.join(os.path.dirname(__file__), "check_input.py")

GOOD = [
    {"id": "a-01", "title": "Variables and Values",
     "description": "Store a value in a name you choose, then read it back later."},
    {"id": "a-02", "title": "Conditions with if",
     "description": "Run a block of code only when a test turns out true."},
]


def test_clean_input_has_no_findings():
    assert audit(GOOD) == []


def test_description_identical_to_title_is_an_error():
    bad = [dict(GOOD[0], description=GOOD[0]["title"])] + GOOD[1:]
    sev, lid, msg = audit(bad)[0]
    assert (sev, lid) == ("ERROR", "a-01")
    assert "description repeats the title" in msg


def test_short_description_is_a_warning():
    bad = [dict(GOOD[0], description="Learn variables.")] + GOOD[1:]
    assert [(s, i) for s, i, _ in audit(bad)] == [("WARN", "a-01")]


def test_missing_description_is_an_error():
    bad = [{"id": "a-01", "title": "Variables and Values"}] + GOOD[1:]
    assert audit(bad)[0][0] == "ERROR"


def test_duplicate_id_is_an_error():
    bad = GOOD + [dict(GOOD[0])]
    assert any(s == "ERROR" and "duplicate id" in m for s, _, m in audit(bad))


def test_suspected_inversion_is_a_warning():
    lessons = [
        {"id": "x-01", "title": "Building a REST API with Chains",
         "description": "Use LLMChain to serve a route that answers questions."},
        {"id": "x-02", "title": "Chains and Sequential Workflows",
         "description": "Introduce LLMChain and compose steps."},
    ]
    findings = audit(lessons)
    assert any(s == "WARN" and "LLMChain" in m and "x-01" in i for s, i, m in findings)


def test_cli_strict_exits_two_on_error(tmp_path):
    p = tmp_path / "in.json"
    p.write_text(json.dumps([dict(GOOD[0], description=GOOD[0]["title"])] + GOOD[1:]),
                 encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "--input", str(p), "--strict"],
                       capture_output=True, text=True)
    assert r.returncode == 2
    assert "ERROR" in r.stdout


def test_cli_clean_exits_zero(tmp_path):
    p = tmp_path / "in.json"
    p.write_text(json.dumps(GOOD), encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, "--input", str(p), "--strict"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "clean" in r.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/nerdit-chapter-generator/scripts && python -m pytest test_check_input.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'check_input'`

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Pre-flight the chapter input array before any lesson is generated.

Two live courses shipped with every `description` set to a verbatim copy of its
`title`. Descriptions are what the writers expand into a lesson and what
`check_sequence.py` reads to decide which lesson owns a concept, so a title-echo
description degrades generation and validation at once -- silently, because the
run still completes.

Usage:
  python check_input.py --input <course-<chapter>_input.json> [--strict]
"""
import argparse
import json
import re
import sys

MIN_DESCRIPTION_WORDS = 12

_IDENT_RE = re.compile(r"\b(?:[A-Za-z][a-z0-9]*[A-Z][A-Za-z0-9]*|[A-Z]{3,})\b")
_STOPWORDS = {
    "API", "APIS", "JSON", "HTTP", "HTTPS", "URL", "CSV", "PDF", "HTML", "CSS",
    "SQL", "CLI", "GUI", "IDE", "AI", "ML", "NLP", "LLM", "LLMS", "XML", "YAML",
}


def _idents(text):
    return {t for t in _IDENT_RE.findall(text or "") if t.upper() not in _STOPWORDS}


def _norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def audit(input_lessons):
    """Return [(severity, lesson_id, message)] -- ERROR blocks a --strict run."""
    out, seen = [], {}
    for i, src in enumerate(input_lessons):
        lid = src.get("id") or f"<index {i}>"
        title, desc = src.get("title", ""), src.get("description")
        if lid in seen:
            out.append(("ERROR", lid, f"duplicate id (also at index {seen[lid]})"))
        seen.setdefault(lid, i)
        if not title:
            out.append(("ERROR", lid, "missing title"))
        if desc is None or not str(desc).strip():
            out.append(("ERROR", lid, "missing description -- the writer has nothing "
                                      "to expand beyond the title"))
        elif _norm(desc) == _norm(title):
            out.append(("ERROR", lid, "description repeats the title verbatim -- write "
                                      "what the lesson teaches, in a sentence or two"))
        elif len(str(desc).split()) < MIN_DESCRIPTION_WORDS:
            out.append(("WARN", lid, f"description is {len(str(desc).split())} words; "
                                     f"under {MIN_DESCRIPTION_WORDS} gives the writer "
                                     f"little to work from"))

    # Suspected order inversion: an earlier lesson names something a later lesson
    # introduces. Reported, never auto-fixed -- the order is the author's call.
    first_seen = {}
    for i, src in enumerate(input_lessons):
        for term in _idents(f"{src.get('title', '')} {src.get('description', '')}"):
            first_seen.setdefault(term, i)
    for i, src in enumerate(input_lessons):
        blob = f"{src.get('title', '')} {src.get('description', '')}".lower()
        for term, owner in sorted(first_seen.items()):
            if owner <= i:
                continue
            if re.search(r"\b" + re.escape(term.lower()) + r"\b", blob):
                out.append(("WARN", src.get("id", f"<index {i}>"),
                            f"names {term!r}, which lesson {owner + 1} introduces -- "
                            f"check the order"))
    return out


def main():
    ap = argparse.ArgumentParser(description="Pre-flight a chapter input array")
    ap.add_argument("--input", required=True)
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero when any ERROR is found")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        lessons = json.load(f)

    findings = audit(lessons)
    if not findings:
        print(f"INPUT: clean -- {len(lessons)} lessons")
        return
    errors = sum(1 for s, _, _ in findings if s == "ERROR")
    print(f"INPUT: {errors} error(s), {len(findings) - errors} warning(s)")
    for sev, lid, msg in findings:
        print(f"  {sev} {lid}: {msg}")
    if args.strict and errors:
        sys.exit(2)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_check_input.py -q`
Expected: PASS, 8 tests.

- [ ] **Step 5: Run the whole suite for regressions**

Run: `python -m pytest -q`
Expected: PASS, 69 tests (61 baseline + 8 new).

- [ ] **Step 6: Commit**

```bash
git add skills/nerdit-chapter-generator/scripts/check_input.py \
        skills/nerdit-chapter-generator/scripts/test_check_input.py
git commit -m "feat: pre-flight chapter input for weak descriptions and order inversions"
```

---

### Task 2: Concept manifest — writer contract

Ownership is currently inferred from titles and descriptions. The writer knows exactly which terms it defined; recording that turns a guess into a fact and lets the checker see prose-level leaks, not only code.

**Files:**
- Modify: `agents/nerdit-lesson-writer.md`
- Modify: `skills/nerdit-chapter-generator/SKILL.md`

**Interfaces:**
- Consumes: `PRIOR_TOPICS` / `UPCOMING_TOPICS` (already passed).
- Produces: `<workdir>/<id>.concepts.json` shaped
  `{"teaches": ["term", ...], "uses": ["term", ...]}` — `teaches` = terms this lesson
  defines in plain words at first use; `uses` = terms it relies on without defining
  (must all come from this lesson or an earlier one). Writer's reply gains a third
  line `CONCEPTS: <path>`.

- [ ] **Step 1: Add the manifest to the writer's job statement**

In `agents/nerdit-lesson-writer.md`, replace the two-file job with three:

```markdown
1. `HTML_PATH` — the complete self-contained NERDIT LMS HTML lesson fragment.
2. `QUIZ_PATH` — 6 multiple-choice questions derived from the fragment you just wrote.
3. `CONCEPTS_PATH` — the concept manifest for the fragment you just wrote.
```

- [ ] **Step 2: Add the manifest contract section**

Insert after the Quiz rules section:

```markdown
## Concept manifest

After `HTML_PATH` is written, record what it actually taught. Read your own fragment
back if you need to — the manifest describes the file on disk, not your plan for it.

Write `CONCEPTS_PATH` as:

```json
{
  "teaches": ["variable", "assignment", "print()"],
  "uses": ["number", "text"]
}
```

- `teaches` — every term this lesson defines in plain words at first use, plus every
  function, keyword, or class it introduces. Lowercase prose terms as written;
  code names exactly as spelled (`LLMChain`, not `llmchain`).
- `uses` — terms the lesson leans on without defining. Every one must come from this
  lesson or a `PRIOR_TOPICS` lesson. If a term belongs to `UPCOMING_TOPICS`, you have
  a sequencing bug: fix the lesson, do not list it here.
- 5–20 entries in `teaches`. A lesson teaching two things is under-built; one teaching
  forty is really five lessons.
```

- [ ] **Step 3: Update the writer's output contract**

Replace the two-line reply with:

```text
FILE: <HTML_PATH>
QUIZ: <QUIZ_PATH>
CONCEPTS: <CONCEPTS_PATH>
```

- [ ] **Step 4: Pass the path from the orchestrator**

In `SKILL.md` Step 2b, add `CONCEPTS_PATH = <workdir>/<id>.concepts.json` to the list of
values passed to each writer, and note that the orchestrator never reads the file back —
`check_sequence.py` consumes it in Step 4b.

- [ ] **Step 5: Verify the docs are internally consistent**

Run: `grep -rn "CONCEPTS_PATH\|concepts.json" agents/ skills/nerdit-chapter-generator/SKILL.md`
Expected: the path appears in the writer's job list, its manifest section, its output
contract, and SKILL.md Step 2b — four places, same spelling.

- [ ] **Step 6: Commit**

```bash
git add agents/nerdit-lesson-writer.md skills/nerdit-chapter-generator/SKILL.md
git commit -m "feat: lesson writers declare a concept manifest per lesson"
```

---

### Task 3: Concept manifest — checker consumption

**Files:**
- Modify: `skills/nerdit-chapter-generator/scripts/check_sequence.py`
- Modify: `skills/nerdit-chapter-generator/scripts/test_check_sequence.py`

**Interfaces:**
- Consumes: `<id>.concepts.json` from Task 2.
- Produces: `load_manifests(concepts_dir, lesson_ids) -> dict[str, dict]`;
  `find_violations(input_lessons, lessons_by_id, manifests=None, allow=())` — `manifests`
  overrides heuristic ownership and adds declared-`uses` checking; `allow` is a set of
  terms the course assumes as prior knowledge. CLI gains `--concepts-dir` and `--allow`.

- [ ] **Step 1: Write the failing tests**

```python
def test_declared_teaches_overrides_heuristic_ownership():
    # The heuristic gives DataFrame to lesson 2 by title; lesson 1 declares it teaches it.
    course = [
        {"id": "a", "title": "Introduction to Pandas", "description": "Why Pandas."},
        {"id": "b", "title": "Understanding DataFrames", "description": "The core object."},
    ]
    manifests = {"a": {"teaches": ["DataFrame"], "uses": []}}
    content = {"a": _pre('df = pd.DataFrame({"x": [1]})')}
    assert find_violations(course, content, manifests=manifests) == []


def test_declared_use_of_a_later_term_is_flagged_without_any_code():
    course = [
        {"id": "a", "title": "Prompt Templates", "description": "Design prompts."},
        {"id": "b", "title": "Chains", "description": "Compose steps with LLMChain."},
    ]
    manifests = {"a": {"teaches": ["prompt"], "uses": ["LLMChain"]}}
    v = find_violations(course, {"a": "<p>prose only</p>"}, manifests=manifests)
    assert [(x[1], x[2], x[3]) for x in v] == [("a", "LLMChain", 1)]


def test_allowlisted_term_is_never_flagged():
    course = [
        {"id": "a", "title": "Setup", "description": "Install the tools."},
        {"id": "b", "title": "Functions and Reuse", "description": "Write a def."},
    ]
    content = {"a": _pre("def main():\n    return 1")}
    assert find_violations(course, content) != []
    assert find_violations(course, content, allow={"def", "return"}) == []


def test_load_manifests_reads_only_requested_ids(tmp_path):
    (tmp_path / "a.concepts.json").write_text(
        json.dumps({"teaches": ["x"], "uses": []}), encoding="utf-8")
    (tmp_path / "z.concepts.json").write_text(
        json.dumps({"teaches": ["q"], "uses": []}), encoding="utf-8")
    got = load_manifests(str(tmp_path), ["a", "b"])
    assert set(got) == {"a"}
    assert got["a"]["teaches"] == ["x"]


def test_load_manifests_raises_on_malformed_file(tmp_path):
    (tmp_path / "a.concepts.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifests(str(tmp_path), ["a"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test_check_sequence.py -q -k "manifest or allow or declared"`
Expected: FAIL — `ImportError: cannot import name 'load_manifests'`

- [ ] **Step 3: Implement `load_manifests` and wire the two new inputs**

```python
def load_manifests(concepts_dir, lesson_ids):
    """Read <concepts_dir>/<id>.concepts.json for each id that has one.

    A present-but-broken manifest raises: silently ignoring it would downgrade the
    check to the heuristic without saying so, which is worse than stopping."""
    out = {}
    for lid in lesson_ids:
        path = os.path.join(concepts_dir, lid + ".concepts.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"{lid}: unreadable concept manifest {path}: {e}")
        if not isinstance(data, dict):
            raise ValueError(f"{lid}: concept manifest {path} must be a JSON object")
        for key in ("teaches", "uses"):
            if key in data and not isinstance(data[key], list):
                raise ValueError(f"{lid}: concept manifest {path} field {key} "
                                 f"must be a list")
        out[lid] = data
    return out
```

In `build_ownership`, accept `manifests=None` and let a declared `teaches` claim a term
before the heuristic does, walking lessons in order so first mention still wins:

```python
def build_ownership(input_lessons, manifests=None):
    manifests = manifests or {}
    ident_owner, construct_owner = {}, {}
    for i, src in enumerate(input_lessons):
        title = src.get("title", "")
        blob = f"{title} {src.get('description', '')}"
        declared = manifests.get(src.get("id"), {}).get("teaches", [])
        for term in declared:
            ident_owner.setdefault(canonical(term), i)
        for term in identifiers(blob) | identifier_families_in_title(title):
            ident_owner.setdefault(canonical(term), i)
        for label, (pattern, flavor) in concepts_in_title(title).items():
            construct_owner.setdefault(label, (i, pattern, flavor))
    return ident_owner, construct_owner
```

In `find_violations(input_lessons, lessons_by_id, manifests=None, allow=())`:
- build `allow_canon = {canonical(t) for t in allow}` and skip any term whose canonical
  form is in it, and any construct label in `allow`;
- treat a lesson's declared `teaches` as its own terms (never a violation);
- after the code scan, check declared `uses` against `ident_owner` so a prose-only
  forward reference is caught even when no code names it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_check_sequence.py -q`
Expected: PASS.

- [ ] **Step 5: Add the CLI flags**

```python
    ap.add_argument("--concepts-dir", default=None,
                    help="directory holding <id>.concepts.json manifests; declared "
                         "ownership overrides the title/description heuristic")
    ap.add_argument("--allow", default="",
                    help="comma-separated terms the course assumes as prior knowledge")
```

Wire them into the `find_violations` call, and print which mode ran:

```python
    manifests = (load_manifests(args.concepts_dir, [l["id"] for l in input_lessons])
                 if args.concepts_dir else {})
    allow = {t.strip() for t in args.allow.split(",") if t.strip()}
    ...
    print(f"  ({len(manifests)}/{len(input_lessons)} lessons declared a concept manifest)")
```

- [ ] **Step 6: Verify against the bundled reference course**

Run: `python check_sequence.py --input ../references/course-introduction-to-langchain-and-llm-applications_input.json --course ../references/course-introduction-to-langchain-and-llm-applications_output.json`
Expected: still reports `LLMChain` in lesson 01 — no manifests exist for that course, so
the heuristic path must be unchanged.

- [ ] **Step 7: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS, 74 tests.

- [ ] **Step 8: Commit**

```bash
git add skills/nerdit-chapter-generator/scripts/check_sequence.py \
        skills/nerdit-chapter-generator/scripts/test_check_sequence.py
git commit -m "feat: check_sequence consumes concept manifests and an allowlist"
```

---

### Task 4: Mandatory repair loop

Today Step 4b prints violations and the orchestrator is trusted to act. Trust is not a
gate: make the script fail the run and give the writer the exact lines to fix.

**Files:**
- Modify: `skills/nerdit-chapter-generator/SKILL.md`
- Modify: `agents/nerdit-lesson-writer.md`

**Interfaces:**
- Consumes: `check_sequence.py --strict` exit code 2 and its stdout lines.
- Produces: a `VIOLATIONS` input block on the writer; Step 4b becomes blocking.

- [ ] **Step 1: Make Step 4b blocking in `SKILL.md`**

Replace the Step 4b command with the strict, manifest-aware form and state the loop:

```markdown
    python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/check_sequence.py" \
      --input        <path to the input JSON> \
      --course       <workdir>/course-<chaptername>_output.json \
      --concepts-dir <workdir> \
      --allow        "<course-level assumed knowledge, comma separated>" \
      --strict

Exit 2 means the run is not deliverable. For every reported lesson, re-run its
`nerdit-lesson-writer` with a `VIOLATIONS` block containing that lesson's exact report
lines, re-assemble (Step 4), and re-run this check. Repeat until it exits 0. Do not
proceed to Step 5 with known violations, and never deliver a course that has not passed
this check exit-0.

If a violation is genuinely a syllabus-order problem rather than a lesson defect (the
construct cannot be avoided at that point in the course — an auth lesson that must raise
an error), stop and tell the user which lesson should move, with the evidence. Reordering
the input is the user's decision, never yours, and lesson ids stay unchanged when they
reorder.
```

- [ ] **Step 2: Teach the writer to consume `VIOLATIONS`**

Add to `agents/nerdit-lesson-writer.md`, in the Sequencing section:

```markdown
### Regenerating after a failed check

The orchestrator may pass a `VIOLATIONS` block — the exact lines a previous attempt
failed on:

```text
lesson 07 prompt-templates-07: code uses 'LLMChain' -- first taught in lesson 08 "Chains and Sequential Workflows"
```

Every listed term must be gone from your new fragment's code, and gone from the manifest's
`uses`. Do not delete the example to satisfy the check — rewrite it so it still teaches
the same concept using constructs the learner already has. If a listed term is genuinely
unavoidable for this topic, say so in one line in your reply after the path lines, and
still emit your best untainted version.
```

- [ ] **Step 3: Record the assumed-knowledge question in Step 1**

Add to `SKILL.md` Step 1:

```markdown
7. Ask the user what the course assumes learners already know (e.g. "basic Python
   syntax", "SQL SELECT"). Pass those terms to `check_sequence.py --allow` in Step 4b.
   Without them, lesson 1 is checked against an empty world and legitimate prerequisite
   vocabulary reads as a forward reference. If the user has no answer, use an empty
   allowlist and say so.
```

- [ ] **Step 4: Verify the loop is described consistently**

Run: `grep -n "strict\|VIOLATIONS\|allow" skills/nerdit-chapter-generator/SKILL.md agents/nerdit-lesson-writer.md`
Expected: Step 1 asks for the allowlist, Step 4b passes `--strict` + `--allow` +
`--concepts-dir`, and the writer documents `VIOLATIONS`.

- [ ] **Step 5: Commit**

```bash
git add skills/nerdit-chapter-generator/SKILL.md agents/nerdit-lesson-writer.md
git commit -m "feat: make the sequencing check blocking with a writer repair loop"
```

---

### Task 5: Within-lesson ordering and the foundations rule

Both observed genuine defects were a *foundations* lesson reaching for the course's
headline tool: "Python Foundations for Pandas" building DataFrames, "Python Syntax"
defining a function eight lessons early. The same mistake also happens between sections
of one lesson.

**Files:**
- Modify: `skills/nerdit-chapter-generator/references/CORE.md`
- Modify: `agents/nerdit-lesson-writer.md`
- Modify: `agents/nerdit-qa-validator.md`

**Interfaces:**
- Consumes: nothing.
- Produces: prose rules only — enforced by the QA agent, not by a script.

- [ ] **Step 1: Add the within-lesson rule to `CORE.md` §1**

```markdown
10. **Order holds inside the lesson too.** Concept 2 may use concept 1's material;
    concept 1 may not use concept 3's. Introduce each construct in the section that
    teaches it, never earlier in the same lesson.
```

- [ ] **Step 2: Add the foundations rule to the writer's Sequencing section**

```markdown
- **A foundations lesson teaches the foundation, not the destination.** When the title
  says foundations, prerequisites, setup, installing, or introduction, its examples use
  the *prerequisite* material. A "Python Foundations for Pandas" lesson teaches lists and
  dictionaries — it does not build a DataFrame. One motivating snippet of the destination
  is allowed in the overview only, never as a worked example with a Try It.
```

- [ ] **Step 3: Add the backward-callback rule to the writer's Sequencing section**

```markdown
- **Look back once.** If this lesson builds on an earlier one, say so in the overview in
  one sentence, naming the lesson: "You used `WHERE` in Lesson 3; now you group those
  rows." Continuity is why the course order exists. At most one such callback.
```

- [ ] **Step 4: Add the matching QA checks**

In `agents/nerdit-qa-validator.md`, under the per-lesson checklist:

```markdown
- Within-lesson order: no concept section uses a construct a *later* section of the same lesson introduces
- Foundations lessons (title says foundations/prerequisites/setup/installing/introduction) do not use the course's headline library in a worked example
- `<workdir>/<id>.concepts.json` exists, has 5–20 `teaches` entries, and no `uses` entry belongs to a later lesson
```

- [ ] **Step 5: Verify no rule contradicts an existing one**

Run: `grep -n "forward\|later lesson\|UPCOMING" skills/nerdit-chapter-generator/references/CORE.md agents/nerdit-lesson-writer.md agents/nerdit-qa-validator.md`
Expected: every hit says the same thing — later-owned constructs never appear in code,
one prose forward reference allowed.

- [ ] **Step 6: Commit**

```bash
git add skills/nerdit-chapter-generator/references/CORE.md agents/nerdit-lesson-writer.md \
        agents/nerdit-qa-validator.md
git commit -m "feat: within-lesson ordering, foundations-lesson, and callback rules"
```

---

### Task 6: Document the hardened pipeline

**Files:**
- Modify: `README.md`
- Modify: `skills/nerdit-chapter-generator/SKILL.md`

- [ ] **Step 1: Extend the README sequencing section**

Add the manifest and the pre-flight to the existing "Concept sequencing" section, and
state that the check is blocking.

- [ ] **Step 2: Add the pre-flight to `SKILL.md` Step 1**

```markdown
6. Run the input pre-flight before generating anything:

       python "${CLAUDE_PLUGIN_ROOT}/skills/nerdit-chapter-generator/scripts/check_input.py" \
         --input <path to the input JSON>

   `ERROR` lines mean the input cannot produce good lessons — show them to the user and
   agree on fixed descriptions before spawning any writer. `WARN` lines about suspected
   order inversions are for the user to accept or reorder.
```

- [ ] **Step 3: Verify every script the docs mention exists**

Run: `for s in assemble_course input_from_output check_sequence check_input; do test -f skills/nerdit-chapter-generator/scripts/$s.py && echo "ok $s" || echo "MISSING $s"; done`
Expected: four `ok` lines.

- [ ] **Step 4: Run the whole suite one final time**

Run: `cd skills/nerdit-chapter-generator/scripts && python -m pytest -q`
Expected: PASS, 74 tests.

- [ ] **Step 5: Commit**

```bash
git add README.md skills/nerdit-chapter-generator/SKILL.md
git commit -m "docs: document the input pre-flight, concept manifest, and blocking gate"
```

---

## Deviations taken during implementation

- **Task 1's order-inversion warning was dropped, not built.** The planned rule (flag a
  lesson naming a term a later lesson "introduces") used first-mention ownership, which
  makes the `owner > i` branch unreachable — it could never fire. Every mechanical
  substitute tried (title-word overlap, description-vs-title ownership) instead flagged the
  course's own subject in every lesson. Order inversions are judged twice with better
  evidence anyway: by the orchestrator reading the titles in Step 1, and by
  `check_sequence.py` against generated lessons in Step 4b. `check_input.py` is now purely
  a description/id/title quality gate, which is the part real course data proved was needed.
- Test count landed at 85, not the 74 the plan projected, from extra edge-case coverage
  (manifest-and-code duplicate reporting, allowlist plural folding, broken-manifest CLI exit).
- The violation line reads `uses 'X'` rather than `code uses 'X'`, since a manifest-declared
  leak has no code behind it.

## Verification

The plan is complete when a fresh chapter run:

1. refuses to start on an input whose descriptions echo their titles (Task 1);
2. produces `<id>.concepts.json` beside every `<id>.html` (Task 2);
3. checks declared concepts, not just guessed ones, and honours the course allowlist (Task 3);
4. exits non-zero and regenerates the offending lessons rather than delivering them (Task 4);
5. carries the foundations, within-lesson, and callback rules into every writer (Task 5).

Regression floor: `python -m pytest -q` in `scripts/` stays green at 74 tests.
