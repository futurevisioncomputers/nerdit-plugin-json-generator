"""The course intro carousel (brand-studio spec, owner 2026-11-20): six slides - why learn, real questions, what
you'll learn, real project, skills, call to action - on day 1 of a course's first pack, in the course's own
brand-studio look (shared with its video thumbnail).

The plan puts an empty words skeleton in the item's "intro"; the agent fills it from the lessons only. Lesson
titles and the project come from the course JSON word for word; every number written must be in the course.
"""
import copy
from pathlib import Path

import source  # noqa: F401  puts the story-video scripts (storyplan) on sys.path
import storyplan  # noqa: E402
import studio
from studio import BRAND, INSTALL_HINT  # noqa: F401  (kept importable from here)
WORDS_SKELETON = {
    "hook": {"headline": "", "highlight": [], "subline": ""},
    "questions": {"headline": "", "highlight": [], "cards": [{"text": "", "keyword": "", "icon": "memo"} for _ in range(3)]},
    "learn": {"headline": "What You'll Learn in This Course", "highlight": ["This Course"]},
    "project": {"headline": "", "highlight": [], "text": "", "icon": "rocket"},
    "skills": {"headline": "", "highlight": [], "cards": [{"text": "", "icon": "bullseye"} for _ in range(4)]},
    "cta": {"subline": "", "keyword": ""},
    "icons": {"hook": "brain", "learn": "laptop"},
}


def _studio():
    api, brands, content, _ = studio.studio()
    return api, brands, content


# The intro's six slides in order (render_intro draws them so); used to pick its Pinterest slides.
PIN_KINDS = ("hook", "questions", "learn", "project", "skills", "cta")


def add_intro(items: list[dict], src: dict, first_pack: bool) -> None:
    """On a course's first pack, day 1's carousel becomes the intro (or day 1 gains one). Items stay in order."""
    if not first_pack or not items:
        return
    day1 = min(it["date"] for it in items)
    for it in [i for i in items if i["date"] == day1 and i["format"] == "carousel"]:
        items.remove(it)
    first = src["clips"][0] if src.get("clips") else {"lessonId": items[0]["lessonId"], "topic": 1}
    items.append({"id": "d01-intro", "date": day1, "time": "13:00", "format": "carousel", "kind": "intro",
                  "title": (src.get("course") or {}).get("title") or "Course intro",
                  "platforms": ["instagram", "linkedin", "pinterest"], "lessonId": first["lessonId"], "topic": first["topic"],
                  "intro": copy.deepcopy(WORDS_SKELETON), "captions": {"instagram": "", "linkedin": "", "pinterest": ""}})
    items.sort(key=lambda it: (it["date"], it["time"]))


def _course(src: dict) -> dict:
    data = storyplan.load_json(src["course_path"])
    return data.get("course", data)


def _facts(content, src: dict) -> dict:
    """The course facts; an empty JSON title takes the pack's title (from the video plan), as the pack does."""
    course = _course(src)
    facts = content.course_facts(course)
    facts["title"] = facts["title"] or str((src.get("course") or {}).get("title") or "").strip()
    return facts


def _empty(words: dict) -> list[str]:
    paths = []
    for page in ("hook", "questions", "learn", "project", "skills", "cta"):
        for key in ("headline", "subline", "text"):
            if key in WORDS_SKELETON[page] and not str(words.get(page, {}).get(key, "")).strip():
                paths.append(f"{page}.{key}")
        want = len(WORDS_SKELETON[page].get("cards", []))
        cards = words.get(page, {}).get("cards", [])
        if want and len(cards) != want:
            paths.append(f"{page}.cards (need {want})")
        for i, card in enumerate(cards):
            if not str(card.get("text", "")).strip():
                paths.append(f"{page}.cards[{i}].text")
    return paths


def intro_errors(item: dict, src: dict) -> list[str]:
    """Problems that stop the build before anything is drawn."""
    words = item.get("intro") or {}
    empty = _empty(words)
    if empty:
        return [f"{item['id']}: intro.{p} is empty" for p in empty]
    _, brands, content = _studio()
    facts = _facts(content, src)
    brand = brands.load_brand(BRAND)
    return [f"{item['id']}: {e}" for e in content.facts_errors(facts) + content.truth_errors(facts, words, brand)]


def render_intro(item: dict, src: dict, out_dir: Path, marker: Path) -> list[Path]:
    """Six JPEGs <item id>-01.jpg ... -06.jpg in the course's look; `marker` is the pack's pack-plan.json."""
    api, brands, content = _studio()
    course = _course(src)
    facts = _facts(content, src)
    pages = content.intro_pages(facts, item["intro"], brands.load_brand(BRAND))
    names = [f"{item['id']}-{i:02d}" for i in range(1, len(pages) + 1)]
    key = studio.course_key(src)
    files, problems = api.render_set_to(BRAND, key, pages, Path(out_dir), names, marker=Path(marker), jpeg=True)
    if problems:
        raise SystemExit("\n".join(f"{item['id']}: {p}" for p in problems))
    return files
