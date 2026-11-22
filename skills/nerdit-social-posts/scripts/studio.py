"""NERDIT's adapter to the brand-studio engine (part 2b, owner 2026-11-20: every post in the course's own look).

Carousel slides and Story/LinkedIn cards become brand-studio pages; brand-studio draws them in the course's one look
(shared with its intro and video thumbnail) and checks that every word fits. NERDIT adds its own rule here: on-screen
text is English. Rendering writes nothing when any rule fails.
"""
from datetime import date
from pathlib import Path

import draw
import source  # noqa: F401  puts the story-video scripts (storyplan) on sys.path
import storyplan  # noqa: E402

INSTALL_HINT = "brand-studio is not installed: python -m pip install -e <brand-studio-plugin>/engine"
BRAND = "nerdit"
COVER_ICONS = ("laptop", "brain", "rocket", "books", "bullseye")    # the cover's badge, by day
CTA_HEADLINE = "Keep learning"
CTA_BAR = "Save this post for later"
CTA_TEXT = "Read the full lesson free on nerdit.in"      # owner 2026-11-22: was "Full lesson free at nerdit.in"
CTA_KEYWORD = "free on nerdit.in"
NOT_TEXT = ("svg", "css", "img", "icon")


def studio():
    """(api, brands, content, pages) from brand-studio, or stop with the install hint."""
    try:
        from brand_studio import api, brands, content, pages
    except ImportError as e:
        raise SystemExit(INSTALL_HINT) from e
    return api, brands, content, pages


def course_key(src: dict) -> str:
    """The course's key in brand-studio's look record: the course JSON's slug, else the workdir's course name."""
    data = storyplan.load_json(src["course_path"])
    return (data.get("course", data).get("slug") or src["name"])


def day_of(plan: dict, item: dict) -> int:
    """Days from the pack's start to the item's date (the item's arrangement variant follows it)."""
    return (date.fromisoformat(item["date"]) - date.fromisoformat(plan["start"])).days


def slide_page(slide: dict, course: str, day: int) -> tuple[str, dict]:
    """A carousel slide as a brand-studio page: the cover and the closing slide carry a student photo."""
    kind = slide["kind"]
    if kind == "cover":
        return "hook", {"headline": slide["hook"], "highlight": [], "subline": course or slide.get("course", ""),
                        "icon": COVER_ICONS[day % len(COVER_ICONS)]}
    if kind == "cta":
        # the closing line is fixed, so a plan made before 2026-11-22 (its slide text is the old line) gets the new one
        return "cta", {"headline": CTA_HEADLINE, "highlight": [], "band": course, "subline": CTA_TEXT,
                       "keyword": CTA_KEYWORD, "cta": CTA_BAR}
    content = {k: v for k, v in slide.items() if k != "kind"}
    if kind == "diagram":
        content["css"] = draw.figure_css()
    return kind, content


def card_page(card: dict, fmt: str) -> tuple[str, dict]:
    """A Story (fmt "story") or LinkedIn feed card as a brand-studio page: cheat sheet, wrong vs right, or picture."""
    story = fmt == "story"
    if card.get("kind") == "cheat":
        return ("cheat-story" if story else "cheat"), {"rows": card["rows"]}
    if card.get("kind") == "compare":
        return "compare", {"bad": card["bad"], "good": card["good"]}
    picture = dict(card.get("picture") or {}) or None
    if picture and picture.get("svg"):
        picture["css"] = draw.figure_css()
    return ("picture-story" if story else "picture"), {"title": card.get("title", ""), "course": card.get("course", ""),
                                                       "topics": list(card.get("topics") or []), "picture": picture}


def _english(page_type: str, field: str, value) -> list[str]:
    if isinstance(value, dict):
        return [e for k, v in value.items() if k not in NOT_TEXT for e in _english(page_type, k, v)]
    if isinstance(value, list):
        return [e for v in value for e in _english(page_type, field, v)]
    if isinstance(value, str) and draw.DEVANAGARI.search(value):
        return [f"{page_type}: {field} must be English on screen: {value[:40]!r}"]
    return []


def fit_errors(page_list: list[tuple[str, dict]]) -> list[str]:
    """Problems found before drawing: brand-studio's slot rules, and English on screen."""
    pages = studio()[3]
    errors = []
    for page_type, content in page_list:
        errors += [f"{page_type}: {e}" for e in pages.guard(page_type, content)]
        errors += [e for k, v in content.items() if k not in NOT_TEXT for e in _english(page_type, k, v)]
    return errors


def reserve(src: dict, marker: Path) -> tuple[str | None, str | None]:
    """Hold the course's look while its pack plan (`marker`) exists: (look name, None) or (None, why not)."""
    return studio()[0].reserve_course_look(BRAND, course_key(src), Path(marker))


def reel_look(src: dict, marker: Path) -> dict:
    """The course's look as a Reel style (reserved first, so an old plan gets one too)."""
    name, problem = reserve(src, marker)
    if problem:
        raise SystemExit(f"course look: {problem}")
    return draw.reel_look(studio()[0].course_look(BRAND, course_key(src)))


def render(src: dict, item: dict, page_list: list[tuple[str, dict]], out_dir: Path, marker: Path, day: int) -> list[Path]:
    """JPEGs <id>-01.jpg ... (a one-page card: <id>.jpg) in the course's look; stops naming the item on a problem."""
    api = studio()[0]
    problems = fit_errors(page_list)
    if problems:
        raise SystemExit("\n".join(f"{item['id']}: {p}" for p in problems))
    single = len(page_list) == 1 and item.get("format") in ("story", "feed")
    names = [item["id"]] if single else [f"{item['id']}-{i:02d}" for i in range(1, len(page_list) + 1)]
    files, problems = api.render_set_to(BRAND, f"{course_key(src)}:{item['id']}", page_list, Path(out_dir), names,
                                        marker=Path(marker), offset=day, jpeg=True)
    if problems:
        raise SystemExit("\n".join(f"{item['id']}: {p}" for p in problems))
    return files
