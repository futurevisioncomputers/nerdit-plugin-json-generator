"""Topic briefs for Veo video prompts: one brief per numbered lesson section of a course JSON.

    python topic_briefs.py --course <course_output.json> --out <dir> [--lesson <id> ...]
                           [--world <course_world.json | world name>]          # writes <dir>/briefs.json

With a world (references/worlds, e.g. fvc-institute) the briefs also carry its fixed setting
and cast: every character's name, role and visual description, so the same people appear in
every topic and every course built on that world.

Each brief carries what the topic clip must teach, taken from the page: the section heading
(Title Case), its prose, its key terms, its worked examples (code and the output the lesson
prints) and tables, and every number the section uses. The prompt writer reads only this
file, so the clip cannot drift from the lesson. The clip's slot key matches the story video's
(<lessonId>-t<N>-video), so the admin maps each Veo clip like any topic clip.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "nerdit-story-video" / "scripts"))
sys.path.insert(0, str(HERE.parents[1] / "nerdit-chapter-generator" / "scripts"))
import lessonparts  # noqa: E402  (the story video's reader of a section's tables, code and terms)
from titlecase import title_case  # noqa: E402

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Practice blocks restate the section; the clip explains it, so they are left out of the prose.
PRACTICE = re.compile(r'<div class="nerdit-(?:predict|tryit|fillblank)\b.*', re.S)
CODE_AND_TABLES = re.compile(r"<pre\b.*?</pre>|<table\b.*?</table>|<script\b.*?</script>", re.S)
MAX_PROSE = 1600
WORLDS = HERE.parents[1] / "nerdit-chapter-generator" / "references" / "worlds"


def load_course(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return data.get("course", data)


def brief(lesson: dict, topic: int) -> dict | None:
    content = lesson.get("content") or ""
    found = lessonparts.section_html(content, topic)
    if not found:
        return None
    heading, markup = found
    parts = lessonparts.section_parts(content, topic)
    prose = lessonparts.text(CODE_AND_TABLES.sub(" ", PRACTICE.sub("", markup)))
    runs = [{"id": f"code{i}", "code": r["code"], "output": r["output"], "outLabel": r["outLabel"]} for i, r in enumerate(parts["runs"], 1)]
    tables = [{"id": f"table{i}", **t} for i, t in enumerate(parts["tables"], 1)]
    facts = " ".join([lessonparts.text(PRACTICE.sub("", markup))] + [r["code"] + " " + r["output"] for r in runs])
    return {
        "key": f"{lesson['id']}-t{topic}-video",
        "lessonId": lesson["id"],
        "lessonTitle": title_case(lesson.get("title", "")),
        "topic": topic,
        "heading": title_case(heading),
        "prose": prose[:MAX_PROSE],
        "terms": parts["terms"],
        "runs": runs,
        "tables": tables,
        "numbers": sorted(set(NUMBER.findall(facts)), key=lambda n: (len(n), n)),
    }


def load_world(ref: str) -> dict:
    """A world file, a course_world.json ({"use": name} allowed) or a bundled world's name."""
    path = Path(ref)
    if not path.is_file():
        path = WORLDS / f"{ref}.world.json"
    world = json.loads(path.read_text(encoding="utf-8-sig"))
    if "use" in world:
        world = json.loads((WORLDS / f"{world['use']}.world.json").read_text(encoding="utf-8-sig"))
    return world


TEACHER = re.compile(r"trainer|teacher|professor|faculty|instructor|mentor", re.I)


def presenter_of(world: dict | None) -> dict | None:
    """The world's own trainer explains its topics on camera; None means the skill's default professor."""
    for c in (world or {}).get("cast", []):
        if TEACHER.search(c.get("role", "")):
            return {"name": c["name"], "role": c["role"], "visual": c["visual"]}
    return None


def world_brief(world: dict) -> dict:
    business = world.get("business", {})
    missing = [c["name"] for c in world.get("cast", []) if not c.get("visual")]
    if missing or not business.get("setting"):
        raise SystemExit(f"world needs business.setting and a visual for every cast member (missing: "
                         f"{', '.join(missing) or 'setting'})")
    return {"business": business.get("name", ""), "setting": business["setting"],
            "owner": (business.get("owner") or {}).get("name", ""),
            "cast": [{"name": c["name"], "role": c["role"], "visual": c["visual"]} for c in world["cast"]]}


def briefs(course: dict, only: list[str] | None = None) -> list[dict]:
    out = []
    for lesson in course.get("lessons", []):
        if only and lesson.get("id") not in only:
            continue
        for topic in lessonparts.numbered_topics(lesson.get("content") or ""):
            b = brief(lesson, topic)
            if b:
                out.append(b)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--lesson", action="append", help="only this lesson id (repeatable); default: every lesson")
    ap.add_argument("--world", help="course world file or bundled world name, for a fixed cast and setting")
    a = ap.parse_args(argv)
    course = load_course(a.course)
    items = briefs(course, a.lesson)
    a.out.mkdir(parents=True, exist_ok=True)
    doc = {"course": title_case(course.get("title", "")), "source": str(a.course.resolve()), "topics": items}
    if a.world:
        doc["world"] = world_brief(load_world(a.world))
        if presenter_of(doc["world"]):
            doc["presenter"] = presenter_of(doc["world"])
    (a.out / "briefs.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(items)} topic brief(s) from {len(course.get('lessons', []))} lesson(s) -> {a.out / 'briefs.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
