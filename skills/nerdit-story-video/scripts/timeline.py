"""Timeline for the story video: when every card, scene, key term and camera move happens.

Pure functions, no I/O: build() takes the plan and each clip's length and word timings, and
returns segments (absolute seconds), YouTube chapters and audio placements. Word timings place
key terms and camera moves at the moment the narration says them.
"""
import re

from pronounce import spoken
from storyplan import title_case

PAD_IN, PAD_OUT = 0.5, 0.8       # silence before and after each narration clip
MOVE = 0.9                       # camera move to a focus point, seconds
CARD = 4.0                       # the silent "Now practise" card closing each topic clip


STOP = set("a an the in of to for and or is are it on at by with as be this that from into".split())
CODE_CHARS = set("@=()[]{}\"'_")
BEFORE = 0.35                    # an arrow or line appears this long before the part it leads to


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+|[ऀ-ॿ]+", text.lower()) if t not in STOP and len(t) > 1}


def part_cues(labels: list[str | None], words: list[dict], offset: float) -> list[dict] | None:
    """When each animated part of a vector scene appears: the moment the narration names it.

    labels: one entry per animated group in drawing order, its text, or None for an arrow or line.
    A labelled part appears at the first word, after the previous named part, that shares a word
    with its label; a code label (`@app.route`) must match a backtick code span, and matching then
    continues after that span. An unlabelled part appears just before the next named one. None when
    some labelled part is never named in order: the narration must name every drawn part."""
    times, i = [], 0
    for label in labels:
        if label is None:
            times.append(None)
            continue
        want, code = _tokens(label), bool(CODE_CHARS & set(label))
        j = next((k for k in range(i, len(words)) if want & _tokens(words[k]["w"])
                  and (not code or "`" in words[k]["w"])), None)
        if j is None:
            return None
        times.append(round(offset + words[j]["t"], 3))
        i = j + 1
        if words[j]["w"].count("`") == 1:          # skip the rest of this code span
            i = next((k + 1 for k in range(j + 1, len(words)) if "`" in words[k]["w"]), i)
    out = []
    for k, t in enumerate(times):
        if t is None:
            nxt = next((x for x in times[k + 1:] if x is not None), None)
            prev = next((x for x in reversed(times[:k]) if x is not None), offset)
            t = round(nxt - BEFORE, 3) if nxt is not None else round(prev + BEFORE, 3)
        out.append({"t": max(t, round(offset, 3)), "named": labels[k] is not None})
    return out


def first_spoken(words: list[dict], phrase: str, offset: float) -> float | None:
    """Absolute time the phrase's first word is spoken, or None.

    The voice says code words respelled (json.dumps as "Jason dot dumps"), so the respelled head counts too."""
    heads = {p.lower().split()[0] for p in (phrase, spoken(phrase)) if p.strip()}
    for w in words:
        word = w["w"].lower()
        if any(head in word or word in head and len(word) > 2 for head in heads):
            return round(offset + w["t"], 3)
    return None


def build(plan: dict, clips: dict, cards: dict | None = None, labels: dict | None = None) -> dict:
    """clips[id] = {"dur": seconds, "words": [{t, d, w}]}.
    cards[(lessonId, topic)] = {"tryIt", "pack"}: a "Now practise" card after that topic's last
    scene (storyplan.practise_cards); it carries that scene's number, so the topic clip keeps it.
    labels[scene number] = the vector's animated parts (svg_parts); each part then appears when
    the narration names it (part_cues) instead of on its own timer."""
    t = 0.0
    segments, audio, chapters = [], [], []

    def narrate(clip_id: str, at: float) -> tuple[float, list[dict]]:
        audio.append({"clip": clip_id, "at": round(at, 3)})
        return clips[clip_id]["dur"], clips[clip_id]["words"]

    intro = plan["intro"]
    dur, _ = narrate("intro", t + PAD_IN)
    end = t + PAD_IN + dur + PAD_OUT
    n_pts = max(len(intro["points"]), 1)
    segments.append({"kind": "intro", "start": t, "end": round(end, 3),
                     "points": [round(t + PAD_IN + dur * i / n_pts, 3) for i in range(n_pts)]})
    chapters.append((0.0, "Introduction"))
    t = end

    for n, s in enumerate(plan["scenes"], 1):
        chapters.append((round(t, 3), s["title"]))
        dur, words = narrate(f"s{n}", t + PAD_IN)
        start, end = t, t + PAD_IN + dur + PAD_OUT
        terms = [{"text": term, "t": first_spoken(words, term, t + PAD_IN) or round(start + PAD_IN, 3)}
                 for term in s.get("terms") or []]
        focus = []
        for i, f in enumerate(s.get("focus") or []):
            at = first_spoken(words, f["at"], t + PAD_IN) if f.get("at") else None
            if at is None:
                at = start + PAD_IN + dur * (i + 0.5) / (len(s["focus"]) + 0.5)
            focus.append({"x": f["x"], "y": f["y"], "zoom": f.get("zoom", 1.4), "ring": bool(f.get("ring")),
                          "t": round(max(at - MOVE / 2, start), 3)})
        focus.sort(key=lambda f: f["t"])
        parts = part_cues(labels[n], words, t + PAD_IN) if labels and labels.get(n) else None
        segments.append({"kind": "scene", "scene": n, "visual": s.get("kind", "vector"),
                         "start": round(start, 3), "end": round(end, 3), "terms": terms, "focus": focus,
                         "parts": parts})
        t = end
        if s.get("myth"):
            dur, _ = narrate(f"s{n}-myth", t + PAD_IN)
            end = t + PAD_IN + dur + PAD_OUT
            segments.append({"kind": "myth", "scene": n, "visual": s.get("kind", "vector"),
                             "start": round(t, 3), "end": round(end, 3), "rightAt": round(t + PAD_IN + dur * 0.5, 3)})
            t = end
        key = (s.get("lessonId"), s.get("topic", 1))
        following = plan["scenes"][n] if n < len(plan["scenes"]) else None
        last_of_topic = following is None or (following.get("lessonId"), following.get("topic", 1)) != key
        if cards and last_of_topic and key in cards:
            segments.append({"kind": "practise", "scene": n, "start": round(t, 3), "end": round(t + CARD, 3),
                             "card": cards[key]})
            t += CARD

    recap = plan["recap"]
    chapters.append((round(t, 3), "Recap"))
    dur, _ = narrate("recap", t + PAD_IN)
    end = t + PAD_IN + dur + PAD_OUT + 0.6
    n_pts = max(len(recap["points"]), 1)
    segments.append({"kind": "recap", "start": round(t, 3), "end": round(end, 3),
                     "points": [round(t + PAD_IN + dur * i / n_pts, 3) for i in range(n_pts)]})
    windows = []
    for n in range(1, len(plan["scenes"]) + 1):
        parts = [s for s in segments if s.get("scene") == n and s.get("visual") == "broll"]
        if parts:
            windows.append({"scene": n, "start": parts[0]["start"], "end": parts[-1]["end"]})
    return {"duration": round(end, 3), "segments": segments, "audio": audio, "chapters": chapters,
            "broll": windows}


def stamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def description(plan: dict, chapters: list) -> str:
    lines = [f"{plan.get('course', '')}: concept recap", "", "Chapters"]
    lines += [f"{stamp(t)} {title_case(title)}" for t, title in chapters]
    lines += ["", "In this video:"] + [f"- {p}" for p in plan["intro"]["points"]]
    lines += ["", "Examples use a fictional learning centre."]
    return "\n".join(lines) + "\n"
