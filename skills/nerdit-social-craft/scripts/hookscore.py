"""Score a hook (the first spoken line or the first on-screen line) from 0 to 100 on five properties.

Adapted from https://github.com/Jakeschincariol/instagram-agent-skill (MIT, Copyright (c) 2026 Jake Schincariol),
skills/ig-reel/hookscore.py: the five checks, the dealbreakers and the overall formula are unchanged. NERDIT adds
the pass mark (50, calibrated 2026-11-28: the owner-approved Trend Reel hook scores 50.6) and the error lines the
other skills' checkers print.

CLI: hookscore.py <file>   one hook per line; prints the ranking; exit 1 when the best hook scores under 50
"""
import re
import statistics
import sys
from pathlib import Path

from textio import say

PASS_MARK = 50.0

WORD_RE = re.compile(r"[A-Za-z0-9$%'’-]+")
NUMBER_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?"                       # money, whole
    r"|\b\d[\d,]*(?:\.\d+)?\s?"                      # a figure, with or
    r"(?:%|k\b|x\b|hrs?\b|hours?\b|mins?\b|minutes?\b"  # without a unit
    r"|days?\b|weeks?\b|months?\b|years?\b)?",
    re.IGNORECASE)
PROPER_RE = re.compile(r"(?<!^)\b[A-Z][a-z]{2,}\b")
# NERDIT: tech names are acronyms (SQL, AI) or CamelCase (FastAPI, NumPy); upstream counted neither.
NAME_RE = re.compile(r"\b[A-Z]{2,}\b|\b[A-Z][a-z]+[A-Z]\w*")
HASHTAG_RE = re.compile(r"(?:^|\s)#\w+")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")

# Spoken numbers count as concrete; "one" and "first" are left out (filler far more often than a quantity).
SPOKEN_NUMBERS = {
    "zero", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "fifteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million",
    "billion", "dozen", "half", "twice", "triple",
}
MONEY_WORDS = {
    "dollars", "dollar", "bucks", "grand", "percent", "cents",
    "millionaire", "billionaire", "revenue", "profit", "salary", "rent",
}
# Words that put something on the line.
STAKES = {
    "stop", "never", "wrong", "mistake", "mistakes", "lost", "lose", "losing",
    "cost", "costs", "broke", "broken", "failed", "failure", "fail", "nobody",
    "no", "not", "don't", "dont", "doesn't", "didn't", "can't", "won't",
    "quit", "quitting", "fired", "deleted", "delete", "killed", "kills", "kill",
    "replaced", "replaces", "cut", "beat", "free", "paid", "charged", "hired",
    "saved", "first",
    "banned", "illegal", "worst", "hate", "hated", "wasted", "waste", "scam",
    "lie", "lied", "lying", "truth", "secret", "hidden", "stole", "stolen",
    "before", "until", "instead", "but", "except", "unless", "problem",
    "risk", "danger", "warning", "regret", "wish", "should", "shouldn't",
    "still", "already", "only", "without", "versus", "vs", "actually",
}
# Openers that spend the first second saying nothing.
WEAK_OPENERS = [
    "so", "ok", "okay", "hey", "hi", "hello", "guys", "yo", "alright",
    "welcome", "today", "basically", "honestly", "look", "listen", "um",
    "just", "let", "lets", "let's", "i wanted", "i want", "one of",
    "have you", "did you", "do you", "are you", "in this", "in today",
    "the thing", "a lot", "there is", "there are", "this is", "it is",
    "as a", "when it", "if you've", "you know",
]
# Imperatives that earn the front position.
IMPERATIVES = {
    "stop", "steal", "copy", "delete", "try", "watch", "read", "save",
    "use", "build", "make", "write", "send", "take", "start", "quit",
    "never", "always", "don't", "dont", "do", "put", "run", "check",
}
DEALBREAKERS = [
    (re.compile(r"(?i)^\s*(?:stop scrolling|don'?t scroll)"),
     "Opens with \"stop scrolling\". Asking for attention proves you have not earned it."),
    (re.compile(r"(?i)\b(?:in (?:this|today'?s) (?:video|reel)|i'?m going to show you|i'?ll show you how)\b"),
     "Video preamble. Delete it and open on the payoff."),
    (re.compile(r"(?i)^\s*(?:hey |hi |what'?s up |welcome )"),
     "Greeting. Nobody came to the feed to be greeted."),
    (HASHTAG_RE,
     "Hashtag in the hook. Hashtags belong at the bottom of the caption, if anywhere."),
    (EMOJI_RE,
     "Emoji in the hook. On-screen text at hook size has room for words or for an emoji, not both."),
]
CHECKS = ["LENGTH", "SPECIFICITY", "STAKES", "FRONTLOAD", "ADDRESS"]


def _clamp(n: float) -> float:
    return max(0.0, min(100.0, n))


def _words(text: str) -> list[str]:
    # "$18,000" is one word when it is spoken, so it is one word here too.
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text))


def _check_length(text: str) -> tuple[float, str]:
    w = _words(text)
    n = len(w)
    chars = len(text.strip())
    if 5 <= n <= 12:
        score = 100.0
    elif n < 5:
        score = _clamp(100 - (5 - n) * 20)
    else:
        score = _clamp(100 - (n - 12) * 11)
    if chars > 60:                       # two lines of big on-screen text
        score -= 12
    return _clamp(score), f"{n} words, {chars} chars (want 5-12 words)"


def _check_specificity(text: str) -> tuple[float, str]:
    nums = [n.strip() for n in NUMBER_RE.findall(text) if n.strip()]
    propers = set(PROPER_RE.findall(text)) | set(NAME_RE.findall(text))
    low = [w.lower().strip("'’") for w in _words(text)]
    spoken = [w for w in low if w in SPOKEN_NUMBERS or w in MONEY_WORDS]
    hits = len(nums) + len(propers) + len(spoken)
    score = 15.0 if hits == 0 else _clamp(45 + hits * 30)
    return score, f"{hits} concrete marker(s)"


def _check_stakes(text: str) -> tuple[float, str]:
    w = [x.lower().strip("'’") for x in _words(text)]
    markers = sorted({x for x in w if x in STAKES})
    if re.search(r"\$\s?\d", text):
        markers.append("a price")
    score = {0: 20.0, 1: 70.0}.get(len(markers), 100.0)
    return _clamp(score), f"{len(markers)} tension marker(s)"


def _check_frontload(text: str) -> tuple[float, str]:
    w = _words(text)
    if not w:
        return 0.0, "empty"
    low = [x.lower().strip("'’") for x in w]
    opener = " ".join(low[:2])
    penalty = 0
    for weak in WEAK_OPENERS:
        if opener.startswith(weak) or low[0] == weak:
            penalty = 30
            break
    payload = None
    for i, token in enumerate(low):
        if (token in STAKES or token in SPOKEN_NUMBERS or token in MONEY_WORDS
                or NUMBER_RE.match(w[i]) or (i and PROPER_RE.match(w[i])) or NAME_RE.fullmatch(w[i])):
            payload = i
            break
    if payload is None:
        base = 30.0
    elif payload <= 3:
        base = 100.0
    elif payload <= 6:
        base = 70.0
    else:
        base = 40.0
    return _clamp(base - penalty), f"payload at word {payload + 1 if payload is not None else '-'}"


def _check_address(text: str) -> tuple[float, str]:
    low = text.lower()
    w = [x.lower().strip("'’") for x in _words(text)]
    if re.search(r"\b(you|your|you're|youre|yourself)\b", low):
        return 100.0, "speaks to the viewer"
    if w and w[0] in IMPERATIVES:
        return 90.0, "imperative opener"
    if re.search(r"\b(i|my|me|we|our)\b", low):
        return 70.0, "first person"
    return 35.0, "third person"


def score_hook(text: str) -> dict:
    text = " ".join(text.split())          # a two-line on-screen hook reads as one line
    text = text.replace("’", "'").replace("‘", "'")   # curly apostrophes: the word sets are ASCII
    results = {
        "LENGTH": _check_length(text),
        "SPECIFICITY": _check_specificity(text),
        "STAKES": _check_stakes(text),
        "FRONTLOAD": _check_frontload(text),
        "ADDRESS": _check_address(text),
    }
    flags = [msg for pattern, msg in DEALBREAKERS if pattern.search(text)]
    scores = [results[c][0] for c in CHECKS]
    # The weakest property caps the hook: one bad property is enough for the thumb to keep moving.
    overall = _clamp(statistics.mean(scores) * 0.6 + min(scores) * 0.4 - len(flags) * 15)
    verdict = "STRONG" if overall >= 70 and min(scores) >= 55 and not flags else ("OK" if overall >= 50 else "WEAK")
    weakest = min(CHECKS, key=lambda c: results[c][0])
    return {"score": round(overall, 1), "verdict": verdict, "weakest": weakest, "flags": flags}


def hook_errors(text: str, label: str, minimum: float = PASS_MARK) -> list[str]:
    r = score_hook(text)
    errors = []
    if r["score"] < minimum:
        errors.append(f"{label}: hook scores {r['score']:.0f}; at least {minimum:.0f} (weakest: {r['weakest']})")
    return errors + [f"{label}: {flag}" for flag in r["flags"]]


def best_hook(options: list[str]) -> tuple[str, dict]:
    scored = [(text, score_hook(text)) for text in options]
    return max(scored, key=lambda pair: pair[1]["score"])   # max keeps the first of equal scores


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        say(__doc__)
        return 2
    hooks = [h.strip() for h in Path(argv[0]).read_text(encoding="utf-8").splitlines() if h.strip()]
    ranked = sorted(((score_hook(h), h) for h in hooks), key=lambda pair: -pair[0]["score"])
    for r, h in ranked:
        say(f"{r['score']:5.1f} {r['verdict']:<6} {h}   (weakest: {r['weakest']})")
        for flag in r["flags"]:
            say(f"             dealbreaker: {flag}")
    return 0 if ranked and ranked[0][0]["score"] >= PASS_MARK else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
