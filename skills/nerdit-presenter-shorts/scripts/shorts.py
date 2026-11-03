"""Plan, check and time a presenter short (9:16, 20-45 s) for a NERDIT course or lesson.

    python shorts.py scaffold --course <course.json> --out <short.plan.json> [--lesson <id>]
    python shorts.py check    --plan <short.plan.json> --course <course.json> --presenter <dir>
    python shorts.py timeline --plan <short.plan.json> --course <course.json> --parts <dir> --out <short.spec.json>

The plan is what the agent writes: the lines the presenter says and, per line, the captions or
the "Explore" code cut-ins that appear while it is said. Code is never typed into the plan: a
cut-in names a lesson program ({"lesson", "program", "lines"}) and the code is copied from the
course. `timeline` turns the plan into the timed spec build_short.py draws, using the length of
each recorded line. Stdlib only.
"""
import argparse, html, json, re, sys, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "nerdit-story-video" / "scripts"))
from storyplan import course_lessons   # noqa: E402

PAUSE = 0.3                 # seconds between recorded lines (voice_short.py uses the same)
CHARS_PER_SECOND = 14.0     # Hinglish narration speed, for the length estimate before recording
MIN_SECONDS, MAX_SECONDS = 15, 60
MAX_SAY = 220               # characters in one line
MAX_KEY, MAX_LEAD, MAX_TOPIC = 24, 32, 26
MAX_CODE_LINES = 16
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
PROGRAM = re.compile(r'<pre data-lang="python"><code>(.*?)</code></pre>', re.S)
FILE_COMMENT = re.compile(r"#\s*(\S+\.py)\b")


def programs(lesson: dict) -> list[str]:
    """Every Python program block in a lesson, as plain text, in page order."""
    return [html.unescape(re.sub(r"<[^>]+>", "", m)) for m in PROGRAM.findall(lesson.get("content", ""))]


def code_ref(ref: dict, lessons: dict) -> tuple[str, str]:
    """(file name, code) for a cut-in's {"lesson", "program" (1-based), "lines" [first, last]}.
    The first line's "# name.py" comment becomes the file name and is not shown."""
    progs = programs(lessons[ref["lesson"]])
    lines = progs[ref["program"] - 1].splitlines()
    name = f"lesson {ref['lesson'].rsplit('-', 1)[-1]}"
    m = FILE_COMMENT.match(lines[0]) if lines else None
    if m:
        name, lines = m.group(1), lines[1:]
    first, last = ref.get("lines", [1, len(lines)])
    shown = lines[first - 1:last]
    while shown and not shown[0].strip():
        shown.pop(0)
    while shown and not shown[-1].strip():
        shown.pop()
    indent = min((len(l) - len(l.lstrip()) for l in shown if l.strip()), default=0)
    return name, "\n".join(l[indent:] for l in shown)


def scaffold(course: Path, lesson_id: str | None) -> dict:
    """A plan skeleton: the lines to write, and every program the cut-ins may show."""
    lessons = course_lessons(course)
    chosen = [l for l in lessons if l["id"] == lesson_id] if lesson_id else lessons
    if not chosen:
        raise SystemExit(f"no lesson {lesson_id} in {course}")
    available = []
    for l in chosen:
        for n, code in enumerate(programs(l), 1):
            first = code.splitlines()[0] if code.strip() else ""
            available.append({"lesson": l["id"], "program": n, "lines": len(code.splitlines()),
                              "file": (FILE_COMMENT.match(first) or [None, ""])[1]})
    return {"version": 1, "lesson": lesson_id, "aspect": "16:9", "language": "hi", "voice": "hi-IN-Chirp3-HD-Charon",
            "lines": [], "end": {"title": "", "subtitle": ""}, "availablePrograms": available}


def _at_ok(line: dict, cue: dict) -> bool:
    return cue.get("at", "") in line.get("say", "")


def check(plan: dict, course: Path, presenter: Path | None) -> list[str]:
    errors = []
    if presenter is not None:
        if not (presenter / "CONSENT.md").is_file():
            errors.append(f"{presenter}/CONSENT.md is missing: the face and voice must be the owner's, with consent written down")
        for ref in ("ref/face_drive.mp4", "ref/voice_ref10.wav"):
            if not (presenter / ref).is_file():
                errors.append(f"{presenter}/{ref} is missing")
    lessons = {l["id"]: l for l in course_lessons(course)}
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", l.get("content", ""))) for l in lessons.values())
    lines = plan.get("lines", [])
    if plan.get("aspect", "9:16") not in ("9:16", "16:9"):
        errors.append(f"aspect is 9:16 (vertical short) or 16:9 (landscape), not {plan.get('aspect')!r}")
    if not 3 <= len(lines) <= 8:
        errors.append(f"a short has 3-8 lines; this one has {len(lines)}")
    seconds = sum(len(l.get("say", "")) for l in lines) / CHARS_PER_SECOND + PAUSE * max(len(lines) - 1, 0)
    if lines and not MIN_SECONDS <= seconds <= MAX_SECONDS:
        errors.append(f"about {seconds:.0f}s of speech; keep a short between {MIN_SECONDS} and {MAX_SECONDS}s")
    shown = []
    for n, line in enumerate(lines, 1):
        say = line.get("say", "")
        if not say or len(say) > MAX_SAY:
            errors.append(f"line {n}: say 1-{MAX_SAY} characters")
        if line.get("cues") and line.get("explore"):
            errors.append(f"line {n}: use cues or explore, not both")
        for cue in line.get("cues", []):
            shown += [cue.get("lead", ""), cue.get("key", "")]
            if not cue.get("key") or len(cue["key"]) > MAX_KEY or len(cue.get("lead", "")) > MAX_LEAD:
                errors.append(f"line {n}: a cue needs a key (<= {MAX_KEY} chars) and a lead (<= {MAX_LEAD})")
            if not _at_ok(line, cue):
                errors.append(f"line {n}: cue at {cue.get('at')!r} is not a word of the line")
        for cut in line.get("explore", []):
            shown.append(cut.get("topic", ""))
            if not cut.get("topic") or len(cut["topic"]) > MAX_TOPIC:
                errors.append(f"line {n}: an explore topic is 1-{MAX_TOPIC} characters")
            if not _at_ok(line, cut):
                errors.append(f"line {n}: explore at {cut.get('at')!r} is not a word of the line")
            ref = cut.get("code", {})
            try:
                _, code = code_ref(ref, lessons)
            except (KeyError, IndexError, TypeError):
                errors.append(f"line {n}: explore code {ref} is not a program in the course")
                continue
            if not code.strip() or len(code.splitlines()) > MAX_CODE_LINES:
                errors.append(f"line {n}: explore code {ref} shows 1-{MAX_CODE_LINES} lines")
    end = plan.get("end", {})
    shown += [end.get("title", ""), end.get("subtitle", "")]
    if not end.get("title"):
        errors.append("end.title is missing")
    for s in shown:
        if DEVANAGARI.search(s):
            errors.append(f"screen text is English only: {s!r}")
        for num in re.findall(r"\d+", s):
            if num not in text:
                errors.append(f"{num} on screen is not in the course: {s!r}")
    return errors


def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def timeline(plan: dict, course: Path, durations: list[float], fps: int = 25) -> dict:
    """The timed spec for build_short.py. A cue or cut-in starts where its `at` word falls in the
    line (by character position) and lasts until the next one or the end of the line."""
    lessons = {l["id"]: l for l in course_lessons(course)}
    spec = {"fps": fps, "aspect": plan.get("aspect", "9:16"), "captions": [], "explore": [], "end": None}
    t = 0.0
    for n, (line, dur) in enumerate(zip(plan["lines"], durations)):
        say, start, stop = line["say"], t, t + dur + (PAUSE if n < len(durations) - 1 else 0)
        events = line.get("cues") or line.get("explore") or []
        times = [start + dur * say.index(e["at"]) / max(len(say), 1) for e in events]
        if line.get("explore"):
            times[0] = start               # the cut-in covers the whole line
        for i, e in enumerate(events):
            until = times[i + 1] if i + 1 < len(events) else stop
            at = round(times[i], 2)
            if line.get("explore"):
                name, code = code_ref(e["code"], lessons)
                spec["explore"].append([at, round(until, 2), e["topic"], name, code])
            else:
                spec["captions"].append([at, round(until, 2), e.get("lead", ""), e["key"]])
        if n == len(plan["lines"]) - 1:
            spec["end"] = [round(start, 2), plan["end"]["title"], plan["end"].get("subtitle", "")]
        t = stop
    spec["duration"] = round(t, 2)
    return spec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["scaffold", "check", "timeline"])
    ap.add_argument("--course", required=True, type=Path)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--lesson")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--presenter", type=Path)
    ap.add_argument("--parts", type=Path, help="the recorded lines: 01.wav, 02.wav, ...")
    a = ap.parse_args(argv)
    if a.command == "scaffold":
        a.out.write_text(json.dumps(scaffold(a.course, a.lesson), ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", a.out)
        return 0
    plan = json.loads(a.plan.read_text(encoding="utf-8"))
    if a.command == "check":
        errors = check(plan, a.course, a.presenter)
        print("\n".join(errors) or "plan OK")
        return 1 if errors else 0
    durations = [wav_seconds(a.parts / f"{n:02d}.wav") for n in range(1, len(plan["lines"]) + 1)]
    a.out.write_text(json.dumps(timeline(plan, a.course, durations), ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
