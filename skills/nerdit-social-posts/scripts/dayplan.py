"""Which item goes out when: the pack's day plan, and the rotating looks.

Per day one Reel and one Story (Instagram + Facebook); Tuesday and Friday add a carousel
(Instagram + LinkedIn); Monday, Wednesday and Thursday add a LinkedIn feed card. One topic clip
per day, in course order, never repeated: a viewer meets the day's idea three ways.
"""
from datetime import date, timedelta

# Colours from the parked server Reel themes (nerdit stash "parked: server-side course Reel generator").
THEMES: dict[str, dict] = {
    "navy":   {"bg": "#003b6c", "bg2": "#001b33", "panel": "#0a2a4d", "ink": "#ffffff", "muted": "#e2e8f0",
               "accent": "#5eead4", "chip": "#14b8a6", "chipInk": "#001b33", "stroke": "#ffffff"},
    "violet": {"bg": "#4c1d95", "bg2": "#14002b", "panel": "#2e0f5c", "ink": "#ffffff", "muted": "#ede9fe",
               "accent": "#d8b4fe", "chip": "#c084fc", "chipInk": "#1e0638", "stroke": "#ffffff"},
    "light":  {"bg": "#f8fafc", "bg2": "#dbe4ef", "panel": "#ffffff", "ink": "#0b1f3a", "muted": "#1e293b",
               "accent": "#0f766e", "chip": "#0f766e", "chipInk": "#ffffff", "stroke": "#cbd5e1"},
    "ember":  {"bg": "#292524", "bg2": "#0c0a09", "panel": "#1c1917", "ink": "#ffffff", "muted": "#e7e5e4",
               "accent": "#fdba74", "chip": "#f97316", "chipInk": "#1c1917", "stroke": "#ffffff"},
    "forest": {"bg": "#065f46", "bg2": "#022c22", "panel": "#04402f", "ink": "#ffffff", "muted": "#d1fae5",
               "accent": "#6ee7b7", "chip": "#34d399", "chipInk": "#022c22", "stroke": "#ffffff"},
}
THEME_ORDER = tuple(THEMES)
LAYOUTS = ("stack", "split")

TIMES = {"story": "10:00", "carousel": "13:00", "reel": "19:00", "feed": "09:30"}   # IST
PLATFORMS = {"reel": ["instagram", "facebook", "pinterest"], "story": ["instagram", "facebook", "pinterest"],
             "carousel": ["instagram", "linkedin", "pinterest"], "feed": ["linkedin", "pinterest"]}   # every pack image pins
# What the owner may pick for each format; equals the server's PACK_FORMAT_PLATFORMS.
ALLOWED_PLATFORMS = {"reel": ["instagram", "facebook", "pinterest"], "story": ["instagram", "facebook", "pinterest"],
                     "carousel": ["instagram", "facebook", "linkedin", "pinterest"],
                     "feed": ["instagram", "facebook", "linkedin", "pinterest"]}

_OFFSET = {"reel": 0, "story": 1, "carousel": 2, "feed": 3}   # distinct offsets: a day's items never share a theme
CAROUSEL_DAYS = {1, 4}       # Tuesday, Friday
FEED_DAYS = {0, 2, 3}        # Monday, Wednesday, Thursday


def theme_for(day: int, fmt: str) -> str:
    return THEME_ORDER[(day + _OFFSET[fmt]) % len(THEME_ORDER)]


def layout_for(day: int) -> str:
    return LAYOUTS[day % len(LAYOUTS)]


def day_plan(src: dict, start: date, days: int = 10, skip: set | frozenset = frozenset()) -> list[dict]:
    """Items for up to `days` days, one topic clip each; fewer days when the course has fewer topics.
    `skip`: (lessonId, topic) pairs an earlier pack already used, so a new pack continues the course."""
    items = []
    fresh = [c for c in src["clips"] if (c["lessonId"], c["topic"]) not in skip]
    for i, clip in enumerate(fresh[:days]):
        day = start + timedelta(days=i)
        formats = ["reel", "story"] if clip.get("video", True) else ["story"]   # no story video: no Reels
        if day.weekday() in CAROUSEL_DAYS:
            formats.append("carousel")
        if day.weekday() in FEED_DAYS:
            formats.append("feed")
        for fmt in formats:
            items.append({"id": f"d{i + 1:02d}-{fmt}", "date": day.isoformat(), "time": TIMES[fmt], "format": fmt,
                          "platforms": list(PLATFORMS[fmt]), "lessonId": clip["lessonId"], "topic": clip["topic"],
                          "clipKey": clip["key"], "theme": theme_for(i, fmt), "layout": layout_for(i)})
    return sorted(items, key=lambda it: (it["date"], it["time"]))
