"""Story-video plan (v3): scaffold from a course, then check it.

    python storyplan.py scaffold --images-dir <images> --course <course.json>   # writes <images>/video/plan.json
    python storyplan.py check --images-dir <images>

A plan is an intro card, 4-12 scenes and a recap card. The video explains with visuals, not
characters and not quizzes. A scene is one of:

  vector  - an animated SVG written for this video (process, tree, bar/line chart, comparison),
            saved as <images>/video/vectors/<file>.svg, drawn with the lesson CSS tokens and
            animated with the lesson's na-* classes in step with the narration;
  diagram - one of the lesson's own SVG figures, by its data-nerdit-img id;
  broll   - a short real-world stock clip (Pexels) found by `query`, fetched by broll.py.

Each scene has a key-idea panel, key terms that pop in when spoken, optional camera focus
points, and an optional misconception check (myth). Narration is Hinglish, written from the
lesson text; the check refuses invented numbers in narration and in drawn vectors.
"""
import argparse, html, json, re, sys
from pathlib import Path

KINDS = ("vector", "diagram", "broll")
MIN_SCENES, MAX_SCENES = 4, 12
MAX_SENTENCES, MAX_CHARS = 4, 360
MAX_KEY_IDEA, MAX_MYTH_LINE, MAX_POINT = 90, 80, 70
MAX_TERMS, MAX_FOCUS = 4, 4
MAX_BROLL_SHARE = 0.3            # B-roll sets the scene; the vectors do the explaining
MIN_VECTOR_ASPECT, MAX_VECTOR_ASPECT = 1.15, 1.55   # the picture box is 4:3
SENTENCE_END = re.compile(r"[.!?।]+(?=\s|$)")   # not the point in 0.25
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
LATIN = re.compile(r"[A-Za-z]")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
MIN_ENGLISH = 0.3   # Hinglish: natural Hindi grammar and verbs, English technical terms and key nouns
FIGURE = re.compile(r'<div[^>]*data-nerdit-img="([^"]+)"[^>]*>\s*(<svg\b.*?</svg>)', re.S)
ARIA = re.compile(r'aria-label="([^"]*)"')
SVG_TEXT = re.compile(r"<text\b[^>]*>(.*?)</text>", re.S)
FACT_TOKEN = re.compile(r"\d+(?:[.,:/-]\d+)*|\b[A-Z][A-Za-z0-9_]*")
ANIM_ROOT = re.compile(r'\bclass="[^"]*\bnerdit-anim\b')
ANIM_PART = re.compile(r'\bclass="[^"]*\bna-(?:show|slide|draw|open|pulse)\b')
OWN_MOTION = re.compile(r"<(?:style|script|animate\w*|set|image|foreignObject)\b", re.I)
HEX = re.compile(r"(?<!&)#[0-9a-fA-F]{3,8}\b")
DEFAULT_VOICE = {"engine": "google", "name": "hi-IN-Chirp3-HD-Aoede", "rate": 1.0}


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def course_lessons(course_path: Path) -> list[dict]:
    data = load_json(course_path)
    course = data.get("course", data)
    lessons = []
    for chapter in course.get("chapters", []) or [course]:
        lessons += chapter.get("lessons", [])
    return lessons


def plain(markup: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", markup or ""))


def lesson_texts(course_path: Path) -> dict:
    """Plain text of each lesson, by lesson id, for the number and fact checks."""
    return {l.get("id", ""): plain(l.get("content") or l.get("html") or "") for l in course_lessons(course_path)}


def lesson_figures(course_path: Path, images_dir: Path | None = None) -> dict:
    """Every SVG figure in the lessons (and the illustrator's diagrams), by figure id."""
    figures = {}
    for lesson in course_lessons(course_path):
        for fid, svg in FIGURE.findall(lesson.get("content") or ""):
            label = (ARIA.search(svg) or [None, ""])[1]
            figures[fid] = {"lessonId": lesson.get("id", ""), "svg": svg, "label": html.unescape(label)}
    if images_dir is not None and (images_dir / "manifest.json").is_file():
        for img in load_json(images_dir / "manifest.json").get("images", []):
            path = images_dir / "upload" / img.get("outputFile", "")
            if img.get("kind") == "diagram" and path.suffix == ".svg" and path.is_file():
                figures[img["id"]] = {"lessonId": img["lessonId"], "svg": path.read_text(encoding="utf-8-sig"),
                                      "label": img.get("alt", "")}
    return figures


def check_vector(svg: str, source: str) -> list[str]:
    """A video vector: 4:3-ish, animated with the lesson classes, tokens only, facts from the lesson."""
    m = re.match(r"\s*<svg\b([^>]*)>", svg, re.S)
    if not m:
        return ["not an <svg> element"]
    attrs, errors = m.group(1), []
    vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', attrs)
    if not vb:
        errors.append("svg has no viewBox")
    else:
        ratio = float(vb.group(1)) / float(vb.group(2))
        if not MIN_VECTOR_ASPECT <= ratio <= MAX_VECTOR_ASPECT:
            errors.append(f"viewBox is {ratio:.2f}:1; the video box is 4:3, so keep it between "
                          f"{MIN_VECTOR_ASPECT} and {MAX_VECTOR_ASPECT} (e.g. 480 x 360)")
    if not ANIM_ROOT.search(attrs):
        errors.append('svg needs class="nerdit-anim": a video vector builds up while it is explained')
    if not ANIM_PART.search(svg):
        errors.append("svg has no moving part (class na-show/na-slide/na-draw/na-open/na-pulse with --d delays)")
    if OWN_MOTION.search(svg):
        errors.append("svg carries <style>, <script>, SMIL, <image> or <foreignObject>; draw with shapes and "
                      "animate with the lesson classes")
    if not re.search(r'\brole="img"', attrs) or not re.search(r'\baria-label="[^"]+"', attrs):
        errors.append('svg needs role="img" and an aria-label')
    if re.search(r'\b(?:width|height)="', attrs):
        errors.append("svg must not set width/height (viewBox only)")
    if HEX.search(svg):
        errors.append("hex colour in svg; use var(--token)")
    drawn = " ".join(plain(t) for t in SVG_TEXT.findall(svg))
    invented = sorted({t for t in FACT_TOKEN.findall(drawn) if t not in source})
    if invented:
        errors.append(f"draws numbers or names the lesson does not contain: {', '.join(invented[:6])}")
    return errors


def scaffold(images_dir: Path, course_path: Path) -> Path:
    """One vector scene per lesson to start from, plus every lesson figure listed to choose from."""
    lessons = course_lessons(course_path)
    data = load_json(course_path)
    title = data.get("title") or data.get("course", {}).get("title", "")
    scenes = [{"kind": "vector", "vector": f"{l['id']}-v1.svg", "lessonId": l["id"], "title": l.get("title", ""),
               "narration": "", "keyIdea": "", "terms": [], "focus": [], "myth": None} for l in lessons]
    figures = [{"id": fid, "lessonId": f["lessonId"], "label": f["label"]}
               for fid, f in lesson_figures(course_path, images_dir).items()]
    plan = {"version": 3, "course": title, "source": str(Path(course_path).resolve()), "language": "hi",
            "voice": dict(DEFAULT_VOICE),
            "intro": {"title": title, "points": [], "narration": ""},
            "scenes": scenes,
            "recap": {"points": [], "narration": ""},
            "availableFigures": figures}
    out = images_dir / "video" / "plan.json"
    (out.parent / "vectors").mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise SystemExit(f"{out} already exists; edit it or delete it first")
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def narrated_parts(plan: dict):
    """(tag, lessonId or None, narration) for every narration in the plan, in speaking order."""
    yield "intro", None, (plan.get("intro") or {}).get("narration", "")
    for n, s in enumerate(plan.get("scenes") or [], 1):
        lid = s.get("lessonId")
        yield f"scene {n}", lid, s.get("narration", "")
        if s.get("myth"):
            yield f"scene {n} myth", lid, s["myth"].get("narration", "")
    yield "recap", None, (plan.get("recap") or {}).get("narration", "")


def english_share(text: str) -> float:
    """Share of words written in English (Latin script) among English and Hindi words."""
    words = text.split()
    latin = sum(1 for w in words if LATIN.search(w))
    hindi = sum(1 for w in words if DEVANAGARI.search(w) and not LATIN.search(w))
    return latin / (latin + hindi) if latin + hindi else 0.0


def _check_text(tag: str, text: str, errors: list) -> bool:
    text = (text or "").strip()
    if not text:
        errors.append(f"{tag}: narration is empty")
        return False
    sentences = [p for p in SENTENCE_END.split(text) if p.strip()]
    if len(sentences) > MAX_SENTENCES or len(text) > MAX_CHARS:
        errors.append(f"{tag}: narration too long ({len(sentences)} sentences, {len(text)} chars); "
                      f"keep to {MAX_SENTENCES} sentences and {MAX_CHARS} chars")
    share = english_share(text)
    if share < MIN_ENGLISH:
        errors.append(f"{tag}: narration is {share:.0%} English words; say the technical terms and key nouns "
                      f"in English (at least {MIN_ENGLISH:.0%})")
    return True


def _limit(tag: str, field: str, value: str, most: int, errors: list) -> None:
    value = (value or "").strip()
    if not value:
        errors.append(f"{tag}: {field} is empty")
    elif len(value) > most:
        errors.append(f"{tag}: {field} is {len(value)} chars; keep to {most} so it fits the screen")


def check_plan(plan: dict, video_dir: Path, figures: dict | None = None, texts: dict | None = None) -> list[str]:
    errors = []
    if plan.get("version") != 3:
        return ["plan.version must be 3; delete plan.json and scaffold again"]
    scenes = plan.get("scenes") or []
    if not MIN_SCENES <= len(scenes) <= MAX_SCENES:
        errors.append(f"plan has {len(scenes)} scenes; use {MIN_SCENES}-{MAX_SCENES}")
    engine = (plan.get("voice") or {}).get("engine")
    if engine not in ("google", "edge", "clone"):
        errors.append(f"voice.engine must be 'google', 'edge' or 'clone', not {engine!r}")
    for part, lo, hi in (("intro", 2, 4), ("recap", 3, 5)):
        points = (plan.get(part) or {}).get("points") or []
        if not lo <= len(points) <= hi:
            errors.append(f"{part}: give {lo}-{hi} points, not {len(points)}")
        for p in points:
            _limit(part, "point", p, MAX_POINT, errors)
    brolls = sum(1 for s in scenes if s.get("kind") == "broll")
    if scenes and brolls / len(scenes) > MAX_BROLL_SHARE:
        errors.append(f"{brolls} of {len(scenes)} scenes are B-roll; keep B-roll to {MAX_BROLL_SHARE:.0%} "
                      "and explain with vectors")
    all_text = " ".join((texts or {}).values())
    seen = set()
    for n, s in enumerate(scenes, 1):
        kind = s.get("kind")
        ref = {"vector": s.get("vector"), "diagram": s.get("figure"), "broll": s.get("query")}.get(kind)
        tag = f"scene {n} ({ref or '?'})"
        if "quiz" in s:
            errors.append(f"{tag}: the video has no quizzes; remove quiz")
        if kind == "vector":
            path = video_dir / "vectors" / (ref or "")
            if not ref or not path.is_file():
                errors.append(f"{tag}: write the vector to video/vectors/{ref}")
            else:
                source = (texts or {}).get(s.get("lessonId"), all_text) if texts is not None else None
                for e in check_vector(path.read_text(encoding="utf-8-sig"), source if source is not None else
                                      path.read_text(encoding="utf-8-sig")):
                    errors.append(f"{tag}: {e}")
        elif kind == "diagram":
            if figures is None:
                errors.append(f"{tag}: diagram scenes need the course JSON (plan.source)")
            elif ref not in figures:
                errors.append(f"{tag}: no figure with this id in the lessons or diagrams")
            elif s.get("lessonId") != figures[ref]["lessonId"]:
                errors.append(f"{tag}: lessonId should be {figures[ref]['lessonId']}")
        elif kind == "broll":
            if not (ref or "").strip():
                errors.append(f"{tag}: broll needs a search query (2-5 plain English words)")
            if s.get("focus"):
                errors.append(f"{tag}: B-roll has no camera focus points")
        else:
            errors.append(f"{tag}: kind must be one of {', '.join(KINDS)}")
        if ref in seen:
            errors.append(f"{tag}: visual used twice")
        seen.add(ref)
        if not (s.get("title") or "").strip():
            errors.append(f"{tag}: title is empty")
        _limit(tag, "keyIdea", s.get("keyIdea"), MAX_KEY_IDEA, errors)
        lowered = (s.get("narration") or "").lower()
        terms = s.get("terms") or []
        if len(terms) > MAX_TERMS:
            errors.append(f"{tag}: at most {MAX_TERMS} terms")
        for term in terms:
            if term.lower() not in lowered:
                errors.append(f"{tag}: term {term!r} is never spoken in the narration")
        focus = s.get("focus") or []
        if len(focus) > MAX_FOCUS:
            errors.append(f"{tag}: at most {MAX_FOCUS} focus points")
        for f in focus:
            if not (0 <= f.get("x", -1) <= 1 and 0 <= f.get("y", -1) <= 1):
                errors.append(f"{tag}: focus x and y must be between 0 and 1")
            if not 1 <= f.get("zoom", 1) <= 2.5:
                errors.append(f"{tag}: focus zoom must be between 1 and 2.5")
            if f.get("at") and f["at"].lower() not in lowered:
                errors.append(f"{tag}: focus 'at' {f['at']!r} is never spoken in the narration")
        myth = s.get("myth")
        if myth:
            _limit(tag, "myth.wrong", myth.get("wrong"), MAX_MYTH_LINE, errors)
            _limit(tag, "myth.right", myth.get("right"), MAX_MYTH_LINE, errors)
        say = s.get("say")
        if say is not None:
            if LATIN.search(say):
                errors.append(f"{tag}: say must be all Devanagari (write English terms as डेटा, मॉडल)")
            if NUMBER.findall(say) != NUMBER.findall(s.get("narration") or ""):
                errors.append(f"{tag}: say and narration must carry the same numbers")
    if "quiz" in json.dumps(plan.get("intro") or {}) + json.dumps(plan.get("recap") or {}):
        errors.append("intro/recap: the video has no quizzes")
    for tag, lid, text in narrated_parts(plan):
        if not _check_text(tag, text, errors) or texts is None:
            continue
        source = texts.get(lid, "") if lid else all_text
        for num in NUMBER.findall(text):
            if num not in source:
                errors.append(f"{tag}: number {num} is not in the lesson text")
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["scaffold", "check"])
    ap.add_argument("--images-dir", required=True, type=Path)
    ap.add_argument("--course", type=Path, help="course JSON (scaffold; check defaults to plan.source)")
    a = ap.parse_args(argv)
    if a.command == "scaffold":
        if not a.course:
            raise SystemExit("scaffold needs --course")
        print(f"wrote {scaffold(a.images_dir, a.course)}")
        return 0
    plan = load_json(a.images_dir / "video" / "plan.json")
    course = a.course or (Path(plan["source"]) if plan.get("source") else None)
    texts = lesson_texts(course) if course else None
    figures = lesson_figures(course, a.images_dir) if course else None
    errors = check_plan(plan, a.images_dir / "video", figures, texts)
    for e in errors:
        print("ERROR", e)
    print("plan OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
