"""Put one empty video slot per lesson clip into the course JSON, for the admin to fill.

    python place_video.py --images-dir <images> --course <course.json> [--out <file>]

Reads <images>/video/clips.json (written by build_video.py) and writes <course>.with-video.json
unless --out is given. Each slot is
    <div class="nerdit-video" data-nerdit-video="<lessonId>-video" data-title="<lesson title>"></div>
placed before the lesson's cheat sheet (📌 section), else at the end of the lesson wrapper. On the
admin's Import JSON + Images page each slot gets a box for its YouTube link; an empty slot stays
hidden from learners. Running it again never adds a second slot for the same clip.
"""
import argparse, html, json, re, sys
from pathlib import Path

CHEATSHEET = re.compile(r'<(?:section|div)[^>]*class="[^"]*nerdit-cheatsheet|<h2[^>]*>\s*📌')


def slot_html(key: str, title: str) -> str:
    return f'<div class="nerdit-video" data-nerdit-video="{key}" data-title="{html.escape(title, quote=True)}"></div>'


def place(content: str, block: str) -> str:
    m = CHEATSHEET.search(content)
    if m:
        at = m.start()
        if m.group(0).startswith("<h2"):   # a heading: go back to the section that holds it
            section = content.rfind("<section", 0, at)
            at = section if section != -1 else at
        return content[:at] + block + "\n" + content[at:]
    end = content.rstrip()
    if end.endswith("</div>"):
        at = end.rfind("</div>")
        return end[:at] + block + "\n" + end[at:]
    return content + "\n" + block


def add_slots(course: dict, clips: list[dict]) -> tuple[dict, list[str]]:
    lessons = {l["id"]: l for l in course.get("lessons", [])}
    added = []
    for c in clips:
        lesson = lessons.get(c["lessonId"])
        if lesson is None:
            raise SystemExit(f"clip {c['key']}: lesson {c['lessonId']} is not in the course JSON")
        if f'data-nerdit-video="{c["key"]}"' in lesson.get("content", ""):
            continue
        lesson["content"] = place(lesson.get("content", ""), slot_html(c["key"], c["title"]))
        added.append(c["key"])
    return course, added


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images-dir", required=True, type=Path)
    ap.add_argument("--course", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    clips = json.loads((a.images_dir / "video" / "clips.json").read_text(encoding="utf-8"))
    course = json.loads(a.course.read_text(encoding="utf-8-sig"))
    course, added = add_slots(course, clips)
    out = a.out or a.course.with_name(a.course.stem + ".with-video.json")
    out.write_text(json.dumps(course, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(added)} video slot(s) added: {', '.join(added) or 'none (already placed)'}\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
