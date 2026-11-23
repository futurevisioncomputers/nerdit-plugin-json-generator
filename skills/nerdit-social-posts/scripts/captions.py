"""Caption rules per platform, and the checker that enforces them (owner rule: every rule has a checker).

Captions are written by the agent with `{link}` where the course link goes; fill_links puts in the
platform's UTM link. Stories take no caption, except on Pinterest (a pin needs searchable words).
Pinterest: the title on the first line, a blank line, the description; no link (the pin carries it).
"""
import re

PINTEREST_TITLE_MAX = 100
PINTEREST_TEXT_MAX = 800
LIMITS = {"instagram": 2200, "facebook": 3000, "linkedin": 3000, "youtube": 5000,
          "pinterest": PINTEREST_TITLE_MAX + 2 + PINTEREST_TEXT_MAX}
MAX_TAGS = {"instagram": 8, "facebook": 5, "linkedin": 5, "youtube": 15, "pinterest": 5}
YOUTUBE_TITLE_MAX = 100
HASHTAG = re.compile(r"#\w+")
URL = re.compile(r"https?://\S+|www\.\S+")
NUMBER = re.compile(r"\d+(?:\.\d+)?%?")
YEAR = re.compile(r"^20\d\d$")
CTA = re.compile(r"\b(comment|save|share)\b", re.I)
DEVANAGARI = re.compile("[ऀ-ॿ]")


def utm_link(course_url: str, platform: str, item: dict) -> str:
    joiner = "&" if "?" in course_url else "?"
    return (f"{course_url}{joiner}utm_source={platform}&utm_medium=social"
            f"&utm_campaign=pack-{item['date']}&utm_content={item['id']}")


def fill_links(text: str, course_url: str, platform: str, item: dict) -> str:
    return text.replace("{link}", utm_link(course_url, platform, item))


def unknown_numbers(text: str, lesson_text: str) -> list[str]:
    """Numbers in `text` that the lesson does not contain (years 20xx and digits in links and hashtags are not claims)."""
    plain = HASHTAG.sub(" ", URL.sub(" ", text))
    known = {n.rstrip("%") for n in NUMBER.findall(lesson_text)}
    return [n for n in dict.fromkeys(NUMBER.findall(plain)) if not YEAR.match(n) and n.rstrip("%") not in known]


def _first_sentence_is_question(text: str) -> bool:
    end = re.search(r"[.!?\n]", text.strip())
    return bool(end) and end.group() == "?"


def caption_errors(platform: str, fmt: str, text: str, lesson_text: str, item: dict, course_url: str) -> list[str]:
    p = platform
    if fmt == "story" and p != "pinterest":
        return [f"{p}: Stories take no caption"] if text.strip() else []
    if not text.strip():
        return [f"{p}: caption is empty"]
    errors = []
    if len(text) > LIMITS[p]:
        errors.append(f"{p}: {len(text)} characters; at most {LIMITS[p]}")
    tags = HASHTAG.findall(text)
    if len(tags) > MAX_TAGS[p]:
        errors.append(f"{p}: {len(tags)} hashtags; at most {MAX_TAGS[p]}")
    if p == "youtube":
        # A Short's caption: the title on the first line, then the description (YouTube's own limits).
        title = text.split("\n", 1)[0].strip()
        if not title:
            errors.append("youtube: first line is the title; it is empty")
        else:
            if len(title) > YOUTUBE_TITLE_MAX:
                errors.append(f"youtube: title is {len(title)} characters; at most {YOUTUBE_TITLE_MAX}")
            if DEVANAGARI.search(title):
                errors.append("youtube: title in English (no Devanagari)")
            if URL.search(title):
                errors.append("youtube: no link in the title")
        if "<" in text or ">" in text:
            errors.append("youtube: no < or > (YouTube rejects them)")
    if p == "pinterest":
        # A pin: searchable title, then the description (Pinterest's own limits); the link is the pin's field.
        title, _, description = text.partition("\n")
        title, description = title.strip(), description.strip()
        if not title:
            errors.append("pinterest: first line is the title; it is empty")
        elif len(title) > PINTEREST_TITLE_MAX:
            errors.append(f"pinterest: title is {len(title)} characters; at most {PINTEREST_TITLE_MAX}")
        if len(description) > PINTEREST_TEXT_MAX:
            errors.append(f"pinterest: description is {len(description)} characters; at most {PINTEREST_TEXT_MAX}")
        if URL.search(text):
            errors.append("pinterest: no link (the pin carries it)")
        if DEVANAGARI.search(text):
            errors.append("pinterest: English only (no Devanagari)")
    elif p == "instagram":
        if _first_sentence_is_question(text):
            errors.append("instagram: open with a claim or a named mistake, not a question")
        if URL.search(text):
            errors.append("instagram: no links (say 'link in bio')")
        if not CTA.search(text):
            errors.append("instagram: add a call to action (comment, save or share)")
        if "link in bio" not in text.lower():
            errors.append("instagram: say 'link in bio'")
    else:
        link = utm_link(course_url, p, item)
        if link not in text:
            errors.append(f"{p}: needs the course link {link}")
    if p == "linkedin" and DEVANAGARI.search(text):
        errors.append("linkedin: English only (no Devanagari)")
    # Every number must come from the lesson (no invented results); years and link digits are not claims.
    errors += [f"{p}: {n} is not in the lesson" for n in unknown_numbers(text, lesson_text)]
    return errors
