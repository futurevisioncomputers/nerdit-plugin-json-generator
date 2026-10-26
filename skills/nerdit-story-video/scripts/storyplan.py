"""Story-video plan (v3): scaffold from a course, then check it.

    python storyplan.py scaffold --images-dir <images> --course <course.json>   # writes <images>/video/plan.json
    python storyplan.py check --images-dir <images>

A plan is an intro card, 4-12 scenes and a recap card. The video explains with visuals, not
characters and not quizzes. A scene is one of:

  vector  - an animated SVG written for this video (process, tree, bar/line chart, comparison),
            saved as <images>/video/vectors/<file>.svg, drawn with the lesson CSS tokens and
            animated with the lesson's na-* classes in step with the narration;
  diagram - one of the lesson's own SVG figures, by its data-nerdit-img id;
  broll   - a short real-world stock clip (Pexels) found by `query`, fetched by broll.py;
  table   - the section's own table (`table`: 1 = its first), redrawn row by row, with
            `highlight` ["row:E2", "col:branch"] ringed in the order the narration names them;
  code    - the section's own worked example (`code`: 1 = its first): the code typed in line by
            line (`highlight` ["line:3"]), then the output the lesson shows.

Each topic clip mirrors its section on the page: the same heading, the same table and code, all
its key terms spoken, at least MIN_TOPIC_SCENES scenes and MIN_TOPIC_WORDS words (about a
minute and a half). It explains first: its first scene after any B-roll is a concept (`vector`
or `diagram`), never the table or code. A section with no clip is listed in `skipTopics` with a reason.

Each scene belongs to one topic: `topic` is the number of the lesson section it explains (the
"2 — ..." heading). build_video.py cuts one short clip per topic, placed at the end of that section,
plus an intro clip and a recap clip; so a topic's first scene must stand on its own.

Each scene has a key-idea panel, key terms that pop in when spoken, optional camera focus
points, and an optional misconception check (myth). Narration is Hinglish, written from the
lesson text; the check refuses invented numbers in narration and in drawn vectors.
"""
import argparse, html, json, re, sys
from pathlib import Path

import lessonparts

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "nerdit-chapter-generator" / "scripts"))
from titlecase import title_case  # noqa: E402  (the same Title Case as the lesson headings)

KINDS = ("vector", "diagram", "broll", "table", "code")
MIN_SCENES, MAX_SCENES = 4, 60
MIN_TOPIC_SCENES, MIN_TOPIC_WORDS = 3, 180   # about a minute and a half of narration per topic clip
MAX_PART_SCENES = 2                          # tables / code runs the scaffold takes per section
MAX_SENTENCES, MAX_CHARS = 6, 550
MAX_KEY_IDEA, MAX_MYTH_LINE, MAX_POINT = 90, 80, 70
MAX_TERMS, MAX_FOCUS = 4, 4
MAX_BROLL_SHARE = 0.3            # B-roll sets the scene; the vectors do the explaining
MIN_VECTOR_ASPECT, MAX_VECTOR_ASPECT = 1.15, 1.55   # the picture box is 4:3
SENTENCE_END = re.compile(r"[.!?।]+(?=\s|$)")   # not the point in 0.25
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
LATIN = re.compile(r"[A-Za-z]")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
MIN_ENGLISH = 0.3   # Hinglish: natural Hindi grammar and verbs, English technical terms and key nouns
# English floor by plan language. Owner, 2026-10-26: "en-IN" (mostly English, an Indian-English
# voice, a few Hindi words at most) is the default; "hi" keeps the Hinglish rule.
ENGLISH_FLOOR = {"hi": MIN_ENGLISH, "en-IN": 0.8}
DEFAULT_LANGUAGE = "en-IN"
DEFAULT_VOICE = {"engine": "google", "name": "en-IN-Chirp3-HD-Aoede", "rate": 1.0}
FIGURE = re.compile(r'<div[^>]*data-nerdit-img="([^"]+)"[^>]*>\s*(<svg\b.*?</svg>)', re.S)
ARIA = re.compile(r'aria-label="([^"]*)"')
SVG_TEXT = re.compile(r"<text\b[^>]*>(.*?)</text>", re.S)
FACT_TOKEN = re.compile(r"\d+(?:[.,:/-]\d+)*|\b[A-Z][A-Za-z0-9_]*")
ANIM_ROOT = re.compile(r'\bclass="[^"]*\bnerdit-anim\b')
ANIM_PART = re.compile(r'\bclass="[^"]*\bna-(?:show|slide|draw|open|pulse)\b')
OWN_MOTION = re.compile(r"<(?:style|script|animate\w*|set|image|foreignObject)\b", re.I)
HEX = re.compile(r"(?<!&)#[0-9a-fA-F]{3,8}\b")
TOPIC_HEADING = re.compile(r"<h2[^>]*>\s*(\d+)\s*[—–-]\s*(.*?)</h2>", re.S)
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")
# A topic clip plays on its own, so its first scene cannot lean on another clip.
BACK_REFERENCE = re.compile(r"पिछले|पहले देखा|जैसा हमने देखा|ऊपर देखा|\b(?:earlier|previous(?:ly)?|as we saw|last part)\b", re.I)


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


def lesson_topics(course_path: Path) -> dict:
    """{lessonId: {topic number: heading text}} from each lesson's numbered sections ("2 — Title")."""
    out = {}
    for lesson in course_lessons(course_path):
        out[lesson.get("id", "")] = {int(n): " ".join(EMOJI.sub("", plain(h)).split())
                                     for n, h in TOPIC_HEADING.findall(lesson.get("content") or "")}
    return out


def lesson_parts(course_path: Path) -> dict:
    """{lessonId: {topic: {"heading", "tables", "runs", "terms"}}} from each numbered section."""
    out = {}
    for lesson in course_lessons(course_path):
        content = lesson.get("content") or ""
        out[lesson.get("id", "")] = {n: lessonparts.section_parts(content, n)
                                     for n in lessonparts.numbered_topics(content)}
    return out


TRYIT = re.compile(r'class="nerdit-(?:predict|fillblank|tryit)\b')
MAX_TRYIT = 60   # chars of the card's "Try It:" line


def lesson_practice(course_path: Path) -> dict:
    """{lessonId: {"tryits": {topic: count}, "starter": name or None, "tasks": n}} for the
    "Now practise" card: each section's Try It blocks, and the chapter's starter (the notebook
    first) with its number of practice tasks (practice files plan §5b)."""
    from practice_files import practice_tasks, read_spec
    out = {}
    for lesson in course_lessons(course_path):
        content = lesson.get("content") or ""
        tryits = {}
        for n in lessonparts.numbered_topics(content):
            found = lessonparts.section_html(content, n)
            tryits[n] = len(TRYIT.findall(found[1])) if found else 0
        try:
            spec = read_spec(content) or {}
        except ValueError:
            spec = {}
        starters = [f["name"] for f in spec.get("files", []) if "practice" in (f.get("from") or {})]
        starters.sort(key=lambda name: not name.endswith(".ipynb"))
        out[lesson.get("id", "")] = {"tryits": tryits, "starter": starters[0] if starters else None,
                                     "tasks": len(practice_tasks(content)) if starters else 0}
    return out


def check_practise(plan: dict, practice: dict, covered: set) -> list[str]:
    """Every topic clip ends with a "Now practise" card naming a Try It its section has and,
    when the chapter has a starter, a task that exists in it."""
    errors = []
    entries = {(e.get("lessonId"), e.get("topic")): e for e in plan.get("practise") or []}
    for lid, topic in sorted(covered, key=lambda k: (str(k[0]), k[1] if isinstance(k[1], int) else 0)):
        info = practice.get(lid)
        if info is None:
            continue
        entry = entries.get((lid, topic))
        if entry is None:
            errors.append(f"{lid} section {topic}: no practise card; add a practise entry naming its Try It")
            continue
        tag = f"practise {lid} section {topic}"
        _limit(tag, "tryIt", entry.get("tryIt"), MAX_TRYIT, errors)
        if not info["tryits"].get(topic):
            errors.append(f"{tag}: the section has no Try It for the card to name")
        task = entry.get("task")
        if info["starter"]:
            if not isinstance(task, int) or isinstance(task, bool) or not 1 <= task <= info["tasks"]:
                errors.append(f"{tag}: task {task} — the starter has tasks 1-{info['tasks']}; name the one this "
                              "clip leads to")
        elif task is not None:
            errors.append(f"{tag}: task {task}, but the chapter has no practice starter")
    return errors


def practise_cards(plan: dict, practice: dict) -> dict:
    """{(lessonId, topic): {"tryIt", "pack"}}: the card text, the file name taken from the spec."""
    cards = {}
    for e in plan.get("practise") or []:
        info = practice.get(e.get("lessonId")) or {}
        pack = (f"Pack: {info['starter']}, Task {e['task']}"
                if info.get("starter") and isinstance(e.get("task"), int) else None)
        cards[(e.get("lessonId"), e.get("topic"))] = {"tryIt": f"Try It: {e.get('tryIt', '')}", "pack": pack}
    return cards


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
    """One clip per numbered section, pre-filled from the page: a concept vector, then the
    section's own tables and code runs. The writer adds narration, key ideas and the vectors."""
    lessons = course_lessons(course_path)
    data = load_json(course_path)
    title = data.get("title") or data.get("course", {}).get("title", "")
    parts = lesson_parts(course_path)

    def scene(kind: str, lid: str, topic: int, heading: str, **extra) -> dict:
        return {"kind": kind, "lessonId": lid, "topic": topic, "title": heading, **extra,
                "narration": "", "keyIdea": "", "terms": [], "focus": [], "myth": None}

    scenes = []
    for l in lessons:
        lid = l["id"]
        if not parts.get(lid):
            scenes.append(scene("vector", lid, 1, l.get("title", ""), vector=f"{lid}-v1.svg"))
            continue
        for topic, part in parts[lid].items():
            scenes.append(scene("vector", lid, topic, part["heading"], vector=f"{lid}-t{topic}-concept.svg"))
            for n, _ in enumerate(part["tables"][:MAX_PART_SCENES], 1):
                scenes.append(scene("table", lid, topic, part["heading"], table=n, highlight=[]))
            for n, run in enumerate(part["runs"][:MAX_PART_SCENES], 1):   # the page's code-walk lines
                scenes.append(scene("code", lid, topic, part["heading"], code=n, highlight=list(run.get("walk", []))))
    figures = [{"id": fid, "lessonId": f["lessonId"], "label": f["label"]}
               for fid, f in lesson_figures(course_path, images_dir).items()]
    plan = {"version": 3, "course": title, "source": str(Path(course_path).resolve()), "language": DEFAULT_LANGUAGE,
            "voice": dict(DEFAULT_VOICE),
            "intro": {"title": title, "points": [], "narration": ""},
            "scenes": scenes,
            "skipTopics": [],
            "practise": [{"lessonId": lid, "topic": topic, "tryIt": "", "task": None}
                         for lid, sections in parts.items() for topic in sections],
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


def _check_text(tag: str, text: str, errors: list, floor: float = MIN_ENGLISH) -> bool:
    text = (text or "").strip()
    if not text:
        errors.append(f"{tag}: narration is empty")
        return False
    sentences = [p for p in SENTENCE_END.split(text) if p.strip()]
    if len(sentences) > MAX_SENTENCES or len(text) > MAX_CHARS:
        errors.append(f"{tag}: narration too long ({len(sentences)} sentences, {len(text)} chars); "
                      f"keep to {MAX_SENTENCES} sentences and {MAX_CHARS} chars")
    share = english_share(text)
    if share < floor:
        errors.append(f"{tag}: narration is {share:.0%} English words; say the technical terms and key nouns "
                      f"in English (at least {floor:.0%})")
    return True


def _limit(tag: str, field: str, value: str, most: int, errors: list) -> None:
    value = (value or "").strip()
    if not value:
        errors.append(f"{tag}: {field} is empty")
    elif len(value) > most:
        errors.append(f"{tag}: {field} is {len(value)} chars; keep to {most} so it fits the screen")


def check_topics(scenes: list[dict], topics: dict | None) -> list[str]:
    """Every scene names its lesson section; one topic's scenes sit together; each clip stands alone."""
    errors, done, last = [], set(), None
    for n, s in enumerate(scenes, 1):
        tag, topic = f"scene {n}", s.get("topic")
        if not isinstance(topic, int) or isinstance(topic, bool) or topic < 1:
            errors.append(f"{tag}: topic must be the number of the lesson section it explains (1, 2, ...)")
            continue
        known = (topics or {}).get(s.get("lessonId"))
        if known and topic not in known:
            errors.append(f"{tag}: lesson {s.get('lessonId')} has no section {topic} "
                          f"(sections: {', '.join(map(str, known))})")
        key = (s.get("lessonId"), topic)
        if key != last:
            if key in done:
                errors.append(f"{tag}: keep the scenes of {key[0]} topic {topic} together; it starts earlier")
            elif BACK_REFERENCE.search(s.get("narration") or ""):
                errors.append(f"{tag}: first scene of a topic clip refers back to another clip; "
                              "each clip plays on its own")
            done.add(key)
            last = key
    return errors


def part_of(s: dict, parts: dict | None) -> dict | None:
    """The lesson table or code run a table/code scene shows, or None."""
    section = ((parts or {}).get(s.get("lessonId")) or {}).get(s.get("topic"))
    n, pool = (s.get("table"), "tables") if s.get("kind") == "table" else (s.get("code"), "runs")
    if not section or not isinstance(n, int) or not 1 <= n <= len(section[pool]):
        return None
    return section[pool][n - 1]


def check_coverage(plan: dict, parts: dict) -> list[str]:
    """Each section's clip mirrors the page: every section covered (or skipped with a reason),
    enough scenes and narration, its own table or code shown, all its key terms spoken."""
    errors = []
    skipped = {(k.get("lessonId"), k.get("topic")) for k in plan.get("skipTopics") or []
               if (k.get("reason") or "").strip()}
    by_topic = {}
    for s in plan.get("scenes") or []:
        by_topic.setdefault((s.get("lessonId"), s.get("topic")), []).append(s)
    for lid, sections in parts.items():
        for topic, part in sections.items():
            tag = f"{lid} section {topic} ({part['heading']})"
            scenes = by_topic.get((lid, topic), [])
            if not scenes:
                if (lid, topic) not in skipped:
                    errors.append(f"{tag}: no clip; add scenes or list it in skipTopics with a reason")
                continue
            words = " ".join((s.get("narration") or "") + " " + ((s.get("myth") or {}).get("narration") or "")
                             for s in scenes)
            steps = len(scenes) + sum(1 for s in scenes if s.get("myth"))   # a myth is the "mistake" step
            if steps < MIN_TOPIC_SCENES:
                errors.append(f"{tag}: {len(scenes)} scene(s); explain it in at least {MIN_TOPIC_SCENES} steps "
                              "(concept, the page's table or code, the mistake or takeaway; a myth counts as one)")
            if len(words.split()) < MIN_TOPIC_WORDS:
                errors.append(f"{tag}: {len(words.split())} words of narration; give at least {MIN_TOPIC_WORDS} "
                              "(about a minute and a half) so the clip explains what the page explains")
            first = next((s for s in scenes if s.get("kind") != "broll"), None)
            if first is not None and first.get("kind") not in ("vector", "diagram"):
                errors.append(f"{tag}: opens with a {first.get('kind')} scene; explain the idea first with a "
                              "vector or diagram scene, then the case study's table or code")
            if (part["tables"] or part["runs"]) and not any(s.get("kind") in ("table", "code") for s in scenes):
                errors.append(f"{tag}: show the section's own table or code (a table or code scene)")
            for term in part["terms"]:
                if term.lower() not in words.lower():
                    errors.append(f"{tag}: key term {term!r} from the page is never spoken")
    return errors


def check_plan(plan: dict, video_dir: Path, figures: dict | None = None, texts: dict | None = None,
               topics: dict | None = None, parts: dict | None = None,
               practice: dict | None = None) -> list[str]:
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
        ref = {"vector": s.get("vector"), "diagram": s.get("figure"), "broll": s.get("query"),
               "table": f"{s.get('lessonId')} section {s.get('topic')} table {s.get('table')}",
               "code": f"{s.get('lessonId')} section {s.get('topic')} code {s.get('code')}"}.get(kind)
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
        elif kind in ("table", "code"):
            if parts is None:
                errors.append(f"{tag}: {kind} scenes need the course JSON (plan.source)")
            else:
                part = part_of(s, parts)
                if part is None:
                    errors.append(f"{tag}: the section has no {kind} {s.get(kind)!r}; count from 1 in page order")
                else:
                    errors += [f"{tag}: {e}" for e in lessonparts.highlight_problems(kind, part, s.get("highlight"))]
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
    errors += check_topics(scenes, topics)
    if parts is not None:
        errors += check_coverage(plan, parts)
    if practice is not None:
        skipped = {(k.get("lessonId"), k.get("topic")) for k in plan.get("skipTopics") or []}
        covered = {(s.get("lessonId"), s.get("topic")) for s in scenes} - skipped
        errors += check_practise(plan, practice, covered)
    if "quiz" in json.dumps(plan.get("intro") or {}) + json.dumps(plan.get("recap") or {}):
        errors.append("intro/recap: the video has no quizzes")
    floor = ENGLISH_FLOOR.get(plan.get("language") or "hi", MIN_ENGLISH)
    for tag, lid, text in narrated_parts(plan):
        if not _check_text(tag, text, errors, floor) or texts is None:
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
    topics = lesson_topics(course) if course else None
    parts = lesson_parts(course) if course else None
    practice = lesson_practice(course) if course else None
    errors = check_plan(plan, a.images_dir / "video", figures, texts, topics, parts, practice)
    for e in errors:
        print("ERROR", e)
    print("plan OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
