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
