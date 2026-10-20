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

from lessonhtml import (AnchorNotFound, find_section, fixture_text, locate, remove_visual_blocks,
                        section_fingerprint, section_text)

STATUSES = ("planned", "converted", "passed", "failed", "inserted")
POSITIONS = ("after-explanation", "before-practice", "before-code")
# "contrast" draws the misconception (left, ✗) beside the correct way (right, ✓).
LAYOUTS = ("single", "contrast")
# Motion helps only a sequence or a change; keep it to the hardest one or two per course.
MAX_ANIMATED = 2
MAX_PER_LESSON = 3
STYLE_FILE = Path(__file__).resolve().parent.parent / "references" / "style.md"
PLAN_KEYS = ("lessonId", "section", "heading", "position", "reason", "subject", "alt", "caption")
KINDS = ("diagram", "illustration", "screen", "process")
# AI-drawn kinds whose prompt comes from build_prompt; "process" pictures a process or data flow.
PROMPTED = ("illustration", "screen", "process")
MARKERS = "①②③④⑤"
V2_KEYS = ("lessonId", "section", "heading", "position", "kind", "question", "objective", "takeaway",
           "misconception", "intro", "caption", "alt", "explanation", "checkQuestion")


def style_block(labels: list[str], markers: int = 0, path: Path = STYLE_FILE,
                kind: str = "illustration", app: str = "", contrast: bool = False) -> str:
    """The house style, or for kind "screen" the screen style: a realistic, logo-free window
    of `app` in its own colours, allowed to show only the listed labels."""
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    fence = "screen-style" if kind == "screen" else "style"
    m = re.search(rf"```{fence}\n(.*?)\n```", raw, re.S)
    if not m:
        raise RuntimeError(f"no ```{fence} block in {path}")
    block = m.group(1).replace("{app}", app)
    if "{labels_clause}" in block:  # legacy v1 style file
        clause = (", except these exact labels: " + ", ".join(f'"{l}"' for l in labels)) if labels else ""
        return block.replace("{labels_clause}", clause)
    allowed = []
    if labels:
        allowed.append("these exact labels: " + ", ".join(f'"{l}"' for l in labels))
    if markers:
        allowed.append("the numbered markers " + " ".join(MARKERS[:markers]))
    if contrast:
        allowed.append("one ✗ on the left panel and one ✓ on the right panel")
    clause = ("no words, letters or numbers except " + "; and ".join(allowed) + ".") if allowed \
        else "no words, letters or numbers at all."
    return block.replace("{text_clause}", clause)


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


def build_prompt(m: dict, s: dict) -> str:
    opener = {"screen": f"Realistic {s.get('app') or 'app'} screen",
              "process": "Educational process illustration"}.get(s.get("kind"), "Educational illustration")
    lines = [f"{opener} for a student meeting this topic for the first time.",
             f"Course: {m['course']['title']}", f"Lesson: {s['lessonTitle']}",
             f"Section: {s['section']['heading']}", f"Learning objective: {s['objective']}",
             f"Question it answers: {s['question']}"]
    if m["course"].get("cast"):
        lines.append(f"Recurring characters and setting: {m['course']['cast']}")
    if m["course"].get("props"):
        lines.append(f"Objects from this course: {m['course']['props']}")
    steps = s["explanation"]
    marks = MARKERS[:len(steps)] if len(steps) >= 2 else ""
    contrast = s.get("layout") == "contrast"
    body = [s["subject"].strip()]
    if contrast:
        body.append(f"Two panels side by side: the left panel shows the mistake ({s['misconception']}) "
                    "marked ✗; the right panel shows the correct way marked ✓.")
    if marks:
        body.append("Numbered markers: " + "; ".join(
            f"place {mk} on the part showing: {st}" for mk, st in zip(marks, steps)))
    if s.get("kind") != "screen":
        # Say what the picture must prove, so the scene teaches instead of decorating.
        body.append(f"The picture must make this obvious: {s['takeaway']}")
        body.append(f"It must not suggest: {s['misconception']}")
        for c in m["course"].get("characters") or []:
            if c["name"].lower() in s["subject"].lower():
                body.append(f"Attach {cast_file(c['name'])} as the reference for {c['name']}.")
    style = style_block(s["labels"], len(marks), kind=s.get("kind", "illustration"), app=s.get("app", ""),
                        contrast=contrast)
    return "\n".join(lines) + "\n\n" + "\n".join(body) + "\n\n" + style


def cast_file(name: str) -> str:
    return "cast/cast-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".png"


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
    if s.get("kind") == "process":
        # The picture explains the flow; exact words and values stay in the lesson text.
        if not 2 <= len(s.get("explanation") or []) <= 3:
            errors.append(f"{where}: a process needs 2-3 explanation steps")
        if s.get("labels"):
            errors.append(f"{where}: process images carry markers only, not labels")
        if re.search(r"\d", s.get("subject") or ""):
            errors.append(f"{where}: process subject contains a number; describe the flow, not values")
    cq = s.get("checkQuestion") or {}
    if not all(str(cq.get(k) or "").strip() for k in ("question", "answer", "reasoning")):
        errors.append(f"{where}: checkQuestion needs question, answer and reasoning")
    return errors


def add_slots_v2(m: dict, course: dict, plan: dict, replan: str | None = None) -> list[str]:
    lessons = {l["id"]: l for l in course.get("lessons", [])}
    if plan.get("cast") is not None:
        m["course"]["cast"] = plan["cast"]
    for key in ("props", "characters"):
        if plan.get(key) is not None:
            m["course"][key] = plan[key]
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
        if p.get("kind") in PROMPTED and not p.get("subject"):
            missing.append("subject")
        if p.get("kind") == "screen":
            missing += [k for k in ("app", "labels") if not p.get(k)]
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
        if p.get("animated") and p["kind"] != "diagram":
            errors.append(f"{where}: only a diagram can be animated")
            continue
        if p.get("animated") and sum(1 for s in m["images"] if s.get("animated")) >= MAX_ANIMATED:
            errors.append(f"{where}: a course gets at most {MAX_ANIMATED} animated diagrams")
            continue
        layout = p.get("layout") or "single"
        if layout not in LAYOUTS or (layout == "contrast" and p["kind"] not in ("illustration", "process")):
            errors.append(f"{where}: layout {layout} needs kind illustration or process")
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
        same_section = [s for s in m["images"] if s["lessonId"] == lid and s["section"]["number"] == p["section"]]
        kinds_here = {s.get("kind") for s in same_section} | {p["kind"]}
        if {"diagram", "process"} <= kinds_here:
            errors.append(f"{where}: a process illustration replaces the diagram in "
                          f"{lid} section {p['section']}; plan one or the other")
            continue
        # ids share one counter per prefix: illustration, screen and process all use "img".
        n = 1 + sum(1 for s in m["images"] if s["lessonId"] == lid and (s.get("kind") == "diagram") == diagram)
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
            "app": p.get("app", ""), "layout": layout, "animated": bool(p.get("animated")),
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


def render_prompts(m: dict) -> str:
    todo = [s for s in m["images"] if s["status"] == "planned" and s.get("kind") != "diagram"]
    redo = [s for s in m["images"] if s["status"] == "failed"]
    done = sum(1 for s in m["images"] if s["status"] in ("converted", "passed", "inserted"))
    out = [f"# Image prompts — {m['course']['title']}", "",
           "Generate each image, then save it into `incoming/` with the exact filename shown.",
           "PNG, JPG or WebP all work. Use the shape each prompt's Format line asks for. "
           "Deliver in any order and in batches.", ""]
    characters = m["course"].get("characters") or []
    if characters:
        out += ["## Character sheets", "",
                "Generate these first and save them under `cast/`. Attach each one in Codex whenever a "
                "prompt below says so, so every image draws the same person.", ""]
        for c in characters:
            out += [f"### {cast_file(c['name'])}", "", "```text",
                    f"Character reference sheet: {c['name']}, {c['look']}. Front view and three-quarter view, "
                    "full body, neutral pose, plain light background.\n\n"
                    + style_block([], 0), "```", ""]
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
    draw = [s for s in m["images"] if s["status"] in ("planned", "failed") and s.get("kind") == "diagram"]
    if draw:
        out += ["## Diagrams to draw", "",
                "Claude writes each as inline SVG from the section and fixture (figures.md rules).", ""]
        for s in draw:
            out += [f"### diagrams/{s['requestFile']}", f"Objective: {s['objective']}",
                    f"Labels (exact): {', '.join(s['labels'])}",
                    f"Markers: {MARKERS[:len(s['explanation'])] if len(s['explanation']) >= 2 else 'none'}",
                    f"Source: {'; '.join(s['sourceRefs'])}", ""]
    out.append(f"_{len(todo)} to generate · {len(redo)} to regenerate · {done} received_")
    return "\n".join(out) + "\n"


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
                if s.get("version") == 2:
                    s["subject"] = r["revisedSubject"].strip()
                    s["prompt"] = build_prompt(m, s) if s["kind"] in PROMPTED else ""
                else:
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
    r = sub.add_parser("record")
    r.add_argument("--images-dir", required=True)
    r.add_argument("--results", required=True)
    c = sub.add_parser("accept")
    c.add_argument("--images-dir", required=True)
    c.add_argument("--id", required=True)
    args = ap.parse_args()
    images_dir = Path(args.images_dir)

    if args.cmd == "add":
        with open(args.course, encoding="utf-8") as f:
            course = json.load(f)
        with open(args.plan, encoding="utf-8") as f:
            plan = json.load(f)
        m = load(images_dir) if (images_dir / "manifest.json").is_file() else new_manifest(course, Path(args.course).name)
        adder = add_slots_v2 if isinstance(plan, dict) else add_slots
        errors = adder(m, course, plan, args.replan)
        if errors:
            print("Plan not saved:")
            print("\n".join(f"  - {e}" for e in errors))
            return 1
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "incoming").mkdir(exist_ok=True)
        (images_dir / "diagrams").mkdir(exist_ok=True)
        save(images_dir, m)
        _write_prompts(images_dir, m)
        counts = {}
        for s in m["images"]:
            counts[s["lessonId"]] = counts.get(s["lessonId"], 0) + 1
        print(f"Planned {len(m['images'])} images across {len(counts)} lessons.")
        print(f"Prompt sheet: {images_dir / 'PROMPTS.md'}  ·  drop images into: {images_dir / 'incoming'}")
        return 0

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


if __name__ == "__main__":
    sys.exit(main())
