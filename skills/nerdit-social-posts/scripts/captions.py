"""Caption rules per platform, and the checker that enforces them (owner rule: every rule has a checker).

Captions are written by the agent with `{link}` where the course link goes; fill_links puts in the
platform's UTM link. Stories take no caption.
"""
import re

LIMITS = {"instagram": 2200, "facebook": 3000, "linkedin": 3000}
MAX_TAGS = {"instagram": 8, "facebook": 5, "linkedin": 5}
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


def _first_sentence_is_question(text: str) -> bool:
    end = re.search(r"[.!?\n]", text.strip())
    return bool(end) and end.group() == "?"


def caption_errors(platform: str, fmt: str, text: str, lesson_text: str, item: dict, course_url: str) -> list[str]:
    p = platform
    if fmt == "story":
        return [f"{p}: Stories take no caption"] if text.strip() else []
    if not text.strip():
        return [f"{p}: caption is empty"]
    errors = []
    if len(text) > LIMITS[p]:
        errors.append(f"{p}: {len(text)} characters; at most {LIMITS[p]}")
    tags = HASHTAG.findall(text)
    if len(tags) > MAX_TAGS[p]:
        errors.append(f"{p}: {len(tags)} hashtags; at most {MAX_TAGS[p]}")
    if p == "instagram":
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
    plain = HASHTAG.sub(" ", URL.sub(" ", text))
    known = {n.rstrip("%") for n in NUMBER.findall(lesson_text)}
    for n in dict.fromkeys(NUMBER.findall(plain)):
        if not YEAR.match(n) and n.rstrip("%") not in known:
            errors.append(f"{p}: {n} is not in the lesson")
    return errors
