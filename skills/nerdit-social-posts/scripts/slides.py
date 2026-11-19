"""Carousel slides and Story/feed cards, from the course's own material.

A carousel: cover, 2-4 key ideas (the topic's scene key ideas), one diagram (the topic's scene
vector, else a lesson figure), a real quiz question and its answer, and a closing slide. 5-8 slides.
"""
import html
import re
from pathlib import Path

import draw
import storyplan

ARIA = re.compile(r'aria-label="([^"]*)"')
MAX_SLIDES, MIN_SLIDES, MAX_IDEAS = 8, 5, 4
CTA_TEXT = "Full lesson free at nerdit.in"


def question_fits(q: dict) -> bool:
    """The question in at most 4 lines and each of its 4 options in at most 2 (34 characters a line),
    with a valid answer index (else the answer slide could show a wrong option as correct)."""
    options = list(q.get("options") or [])
    index = q.get("correctOptionIndex")
    return (len(options) == 4 and isinstance(index, int) and not isinstance(index, bool) and 0 <= index < 4 and _english_fit(q.get("text", ""), 34, 4)
            and all(_english_fit(str(o), 34, 2) for o in options))


def _scenes(src: dict, lesson: str, topic: int | None = None) -> list[dict]:
    return [s for s in src["plan"]["scenes"] if s.get("lessonId") == lesson and (topic is None or s.get("topic") == topic)]


def _english_fit(text: str, per_line: int, lines: int) -> bool:
    return bool(text) and draw.fits(text, per_line, lines) and not draw.DEVANAGARI.search(text)


def topic_picture(src: dict, item: dict) -> dict | None:
    """{"svg", "label"}: the topic's first scene vector, else the lesson's first figure; None when neither exists."""
    for s in _scenes(src, item["lessonId"], item["topic"]):
        path = src["video"] / "vectors" / (s.get("vector") or "")
        if s.get("vector") and path.is_file():
            svg = path.read_text(encoding="utf-8-sig")
            label = html.unescape((ARIA.search(svg) or [None, ""])[1])
            return {"svg": svg, "label": label if _english_fit(label, 40, 2) else s.get("title", "")}
    for fig in src["figures"].values():
        if fig["lessonId"] == item["lessonId"]:
            label = fig.get("label", "")
            return {"svg": fig["svg"], "label": label if _english_fit(label, 40, 2) else src["lessons"][item["lessonId"]]["title"]}
    return None


def _hook(src: dict, item: dict) -> str:
    """The owner's hook, else the first of the topic's key ideas, its title or the lesson title that fits the cover."""
    if item.get("hook"):
        return item["hook"]
    title = next((c["title"] for c in src["clips"] if c["key"] == item.get("clipKey")), "")
    candidates = [s.get("keyIdea", "") for s in _scenes(src, item["lessonId"], item["topic"])]
    candidates += [title, src["lessons"][item["lessonId"]]["title"]]
    return next((c for c in candidates if _english_fit(c, 18, 4)), candidates[-1])


def _quiz(src: dict, item: dict) -> dict | None:
    qs = src["lessons"][item["lessonId"]]["questions"]
    if not qs:
        return None
    start = (int(item.get("topic") or 1) - 1) % len(qs)     # different topics of a lesson ask different questions
    fitting = [q for q in qs[start:] + qs[:start] if question_fits(q)]
    if not fitting:
        return None
    # Prefer the question that shares the most words with this topic (its terms, key ideas and title).
    scenes = _scenes(src, item["lessonId"], item["topic"])
    title = next((c["title"] for c in src["clips"] if c["key"] == item.get("clipKey")), "")
    topic_text = " ".join([title] + [s.get("keyIdea", "") for s in scenes] + [t for s in scenes for t in s.get("terms") or []])
    words = {w for w in re.findall(r"[a-z_]{4,}", topic_text.lower())}
    score = lambda q: len(words & set(re.findall(r"[a-z_]{4,}", " ".join([q["text"], *map(str, q["options"])]).lower())))  # noqa: E731
    best = max(fitting, key=score)    # max keeps the first of equals, so the rotation still breaks ties
    return best if score(best) else None   # a question about another topic would confuse this carousel


def default_slides(src: dict, item: dict) -> list[dict]:
    title = next((c["title"] for c in src["clips"] if c["key"] == item.get("clipKey")), "")
    ideas, seen = [], set()
    own = _scenes(src, item["lessonId"], item["topic"])
    others = [s for s in _scenes(src, item["lessonId"]) if s not in own]
    for s in own + others:
        idea = (s.get("keyIdea") or "").strip()
        if idea and idea.lower() not in seen and _english_fit(idea, 22, 6):
            seen.add(idea.lower())
            ideas.append({"kind": "idea", "text": idea, "title": title if s in own else s.get("title", "")})
    picture = topic_picture(src, item)
    quiz = _quiz(src, item)
    fixed = 2 + (1 if picture else 0) + (2 if quiz else 0)            # cover + cta, diagram, quiz + answer
    n_ideas = min(len(ideas), MAX_IDEAS, MAX_SLIDES - fixed)        # fewer than 5 slides only when ideas run out
    slides = [{"kind": "cover", "hook": _hook(src, item), "course": src["course"]["title"]}] + ideas[:n_ideas]
    if picture:
        slides.append({"kind": "diagram", **picture})
    if quiz:
        slides += [{"kind": "quiz", "question": quiz["text"], "options": list(quiz["options"])},
                   {"kind": "answer", "question": quiz["text"], "answer": quiz["options"][quiz["correctOptionIndex"]]}]
    return slides + [{"kind": "cta", "text": CTA_TEXT}]


def make_carousel(src: dict, item: dict, slides: list[dict], out_dir: Path) -> list[Path]:
    out = [Path(out_dir) / f"{item['id']}-{i:02d}.jpg" for i in range(1, len(slides) + 1)]
    draw.shoot([(draw.slide_html(s, draw.look_for(item), i, len(slides)), path, draw.SLIDE_W, draw.SLIDE_H, False)
                for i, (s, path) in enumerate(zip(slides, out), 1)])
    return out


def card_spec(src: dict, item: dict) -> dict:
    """Story card: the topic diagram. Feed card (LinkedIn): the video thumbnail when there is one."""
    lesson = src["lessons"][item["lessonId"]]
    headings = storyplan.lesson_topics(src["course_path"]).get(item["lessonId"], {})
    topics = [h for _, h in sorted(headings.items()) if _english_fit(h, 40, 2)][:4]
    thumb = src["video"] / "thumbnail.jpg"
    diagram = topic_picture(src, item)
    if item.get("format") == "feed" and thumb.is_file():
        picture = {"img": str(thumb)}
    elif diagram:
        picture = {"svg": diagram["svg"]}
    else:
        picture = {"img": str(thumb)} if thumb.is_file() else None
    return {"title": lesson["title"], "course": src["course"]["title"], "topics": topics, "picture": picture}


def make_card(src: dict, item: dict, height: int, out_dir: Path) -> Path:
    """The item's teaching card (cheat sheet or Wrong vs right) when the plan gave it one, else the picture card."""
    out = Path(out_dir) / f"{item['id']}.jpg"
    card, look = item.get("card") or {}, draw.look_for(item)
    doc = (draw.cheat_html(card, look, height) if card.get("kind") == "cheat"
           else draw.compare_card_html(card, look, height) if card.get("kind") == "compare"
           else draw.card_html(card_spec(src, item), look, height))
    draw.shoot([(doc, out, draw.SLIDE_W, height, False)])
    return out
