"""English on-screen cues for a Reel, timed from the story video's own narration.

The story video's timeline is rebuilt exactly as nerdit-story-video's build does it (same plan, same
word timings, same practise cards and vector parts), so a term appears when the voice says it.
If the rebuilt clips do not match clips.json, the video was built from other timings: stop.
"""
import re

import source  # noqa: F401  puts story-video's scripts on sys.path
import build_video
import storyplan
import timeline
from pathlib import Path

TERM_HOLD = 2.2       # seconds a spoken term stays up
TOLERANCE = 0.05      # seconds of drift allowed between clips.json and the rebuilt timeline
DEVANAGARI = re.compile("[ऀ-ॿ]")


def course_timeline(src: dict) -> dict:
    """The story video's timeline, rebuilt from plan.json and the audio word files."""
    plan, vid = src["plan"], src["video"]
    course = Path(plan["source"]) if plan.get("source") else src.get("course_path")
    practice = storyplan.lesson_practice(course) if course and Path(course).is_file() else None
    return timeline.build(plan, build_video.clip_info(vid / "audio", plan),
                          storyplan.practise_cards(plan, practice) if practice else None,
                          build_video.vector_labels(plan, vid))


def timeline_errors(tl: dict, src: dict) -> list[str]:
    rebuilt = {c["key"]: c for c in build_video.topic_clips(src["plan"], tl, {}, {})}
    errors = []
    for c in src["clips"]:
        name = c.get("file") or c["key"]
        r = rebuilt.get(c["key"])
        if r is None:
            errors.append(f"{name}: not in the plan timings; rebuild the video first")
            continue
        for field, word in (("start", "starts"), ("end", "ends")):
            if abs(c[field] - r[field]) > TOLERANCE:
                errors.append(f"{name}: {word} {c[field]:.3f} s in clips.json, {r[field]:.3f} s in the plan timings; "
                              "rebuild the video first")
    return errors


def _in_clip(tl: dict, clip: dict) -> list[dict]:
    return [s for s in tl["segments"] if s.get("scene") and s["start"] >= clip["start"] - TOLERANCE
            and s["end"] <= clip["end"] + TOLERANCE]


def scene_ends(tl: dict, clip: dict) -> list[float]:
    """Clip-local end times of the clip's scene, myth and practise segments (safe cut points)."""
    return [round(s["end"] - clip["start"], 3) for s in _in_clip(tl, clip)]


def cues_from_timeline(tl: dict, plan: dict, clip: dict) -> list[dict]:
    c0, length = clip["start"], clip["end"] - clip["start"]
    out = []

    def add(kind: str, text: str, start: float, end: float) -> None:
        start, end = max(start - c0, 0.0), min(end - c0, length)
        if text and not DEVANAGARI.search(text) and end > start:
            out.append({"kind": kind, "text": text.strip(), "start": round(start, 3), "end": round(end, 3)})

    for seg in _in_clip(tl, clip):
        s = plan["scenes"][seg["scene"] - 1]
        if seg["kind"] == "scene":
            add("idea", s.get("keyIdea") or "", seg["start"], seg["end"])
            terms = sorted(seg.get("terms") or [], key=lambda t: t["t"])
            for i, term in enumerate(terms):
                nxt = terms[i + 1]["t"] if i + 1 < len(terms) else seg["end"]
                add("term", term["text"], term["t"], min(term["t"] + TERM_HOLD, nxt, seg["end"]))
        elif seg["kind"] == "myth" and s.get("myth"):
            add("wrong", s["myth"].get("wrong", ""), seg["start"], seg["rightAt"])
            add("right", s["myth"].get("right", ""), seg["rightAt"], seg["end"])
    return out


def clip_cues(src: dict) -> dict[str, list[dict]]:
    tl = course_timeline(src)
    errors = timeline_errors(tl, src)
    if errors:
        raise SystemExit("the story video does not match its plan:\n" + "\n".join(errors))
    return {c["key"]: cues_from_timeline(tl, src["plan"], c) for c in src["clips"]}
