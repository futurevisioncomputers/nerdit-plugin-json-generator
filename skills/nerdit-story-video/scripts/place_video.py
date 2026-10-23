"""Put one empty video slot per clip into the course JSON, for the admin to fill.

    python place_video.py --images-dir <images> --course <course.json> [--out <file>]

Reads <images>/video/clips.json (written by build_video.py) and writes <course>.with-video.json
unless --out is given. Each slot is
    <div class="nerdit-video" data-nerdit-video="<key>" data-title="<title>"></div>
A topic clip (<lessonId>-t<N>-video) goes at the end of the lesson's section N, so the learner reads
the section, then watches it explained; the intro clip goes before the first lesson's first section
and the recap clip before the last lesson's cheat sheet (📌 section). A clip with no place to go
lands before the cheat sheet, else at the end of the lesson wrapper. On the
admin's Import JSON + Images page each slot gets a box for its YouTube link; an empty slot stays
hidden from learners. Running it again never adds a second slot for the same clip.
"""
import argparse, html, json, re, sys
from pathlib import Path

CHEATSHEET = re.compile(r'<(?:section|div)[^>]*class="[^"]*nerdit-cheatsheet|<h2[^>]*>\s*📌')
TOPIC_HEADING = re.compile(r"<h2[^>]*>\s*(\d+)\s*[—–-]")


def slot_html(key: str, title: str) -> str:
    return f'<div class="nerdit-video" data-nerdit-video="{key}" data-title="{html.escape(title, quote=True)}"></div>'


def topic_end(content: str, topic: int) -> int | None:
    """Index of the </section> that closes the lesson's numbered section, or None."""
    for m in TOPIC_HEADING.finditer(content):
        if int(m.group(1)) == topic:
            end = content.find("</section>", m.end())
            return end if end != -1 else None
    return None


def first_section(content: str) -> int | None:
    m = TOPIC_HEADING.search(content)
    if not m:
        return None
    at = content.rfind("<section", 0, m.start())
    return at if at != -1 else m.start()


def place_clip(content: str, block: str, clip: dict) -> str:
    where = clip.get("place")
    at = None
    if where == "topic":
        at = topic_end(content, clip.get("topic"))
    elif where == "intro":
        at = first_section(content)
    if at is None:
        return place(content, block)
    return content[:at] + block + "\n" + content[at:]


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
        lesson["content"] = place_clip(lesson.get("content", ""), slot_html(c["key"], c["title"]), c)
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
