"""Check a Trend Reel script before any Flow credit is spent.

The spoken line follows what the spike taught (Dev garbles long lines, numbers in digits, web addresses and the
course name); every number on the news card must come from a story that passed the two-outlet check.

CLI: script_check.py <run>   reads script.json + checked.json, records checks.json["script"]; exit 1 on errors
"""
import json
import re
import sys
from pathlib import Path

from numwords import DIGITS, TENS, UNITS, find, normalise, words_to_digits
from runs import record_check

# Hook scoring and the humanizer live with the social-craft skill (shared with social-posts); reuse, never copy.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "nerdit-social-craft" / "scripts"))
from hookscore import best_hook, hook_errors  # noqa: E402
from humanize import slop_errors  # noqa: E402

MAX_WORDS = 30   # Dev: ~2.4 words a second after a 1 s lead-in; 30 words fit a 15 s clip
MAX_SENTENCE = 12
BANNED = ("free certificate",)
WEB = re.compile(r"https?://|www\.|\bdot (?:com|in|org|net)\b|\b\w+\.(?:com|in|org|net)\b", re.I)
NON_LATIN = re.compile("[^\u0000-ɏ -⁯₹]")   # Latin letters, punctuation, rupee sign
FACTS = {"daily": 1, "weekly": 3}
_NUMWORD = "|".join([*UNITS, *TENS])
# Pilot 2026-11-25: Dev garbled "ten point six million" in both takes; say "over ten million" instead.
SPOKEN_DECIMAL = re.compile(rf"\b(?:{_NUMWORD})(?:-(?:{_NUMWORD}))?\s+point\s+(?:{_NUMWORD})\b", re.I)


def _same_sentence(a: str, b: str) -> bool:
    """Equal after case, curly apostrophes and the closing full stop are set aside."""
    def norm(s: str) -> str:
        return re.sub(r"[.!?\s]+$", "", s.replace("’", "'").replace("‘", "'")).strip().lower()
    return norm(a) == norm(b)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def script_errors(script: dict, kept: list[dict]) -> list[str]:
    line = script.get("line", "").strip()
    card = script.get("card", {})
    facts = card.get("facts", [])
    errors = []

    words = line.split()
    if len(words) > MAX_WORDS:
        errors.append(f"line has {len(words)} words; at most {MAX_WORDS}")
    for sentence in re.split(r"(?<=[.!?])\s+", line):
        if len(sentence.split()) > MAX_SENTENCE:
            errors.append(f"sentence over {MAX_SENTENCE} words: '{sentence}'")
    if not re.sub(r"[.!?\s]+$", "", line).lower().endswith("link in bio"):
        errors.append("line must end with 'link in bio'")
    digits = [w for w in words if re.search(r"\d", w)]
    if digits:
        errors.append(f"spoken line has digits: {', '.join(digits)} (spell numbers as said)")
    if m := SPOKEN_DECIMAL.search(line):
        errors.append(f"spoken decimal '{m.group(0)}' (Dev garbles decimals: round it, e.g. 'over ten million')")
    if WEB.search(line):
        errors.append("spoken line has a web address (say 'link in bio' only)")
    title = script.get("course", {}).get("title", "")
    if title and title.lower() in line.lower():
        errors.append(f"course title spoken in the line: '{title}' (show it on the end card only)")

    want = FACTS.get(script.get("kind"), 1)
    if len(facts) != want:
        errors.append(f"{script.get('kind')} card needs {want} fact{'s' if want > 1 else ''}, not {len(facts)}")
    if len(card.get("sources", [])) < 2:
        errors.append("card needs at least 2 sources")

    known = normalise(" ".join(k.get("headline", "") + " " + " ".join(k.get("evidence", [])) for k in kept))
    # Spoken numbers are claims too (captions show them); counts under 10 ("One… Two… Three…") are not.
    for tok in words_to_digits(re.findall(r"[a-z]+(?:-[a-z]+)*|\d+(?:\.\d+)?", line.lower())):
        if DIGITS.match(tok) and float(tok) >= 10 and tok not in known:
            errors.append(f"spoken number {tok} is not in any kept source")
    headlines = [_words(k.get("headline", "")) for k in kept]
    for fact in facts:
        if NON_LATIN.search(fact):
            errors.append(f"card fact not in English letters: '{fact}'")
        for raw, norm in find(fact):
            if norm not in known:
                errors.append(f"card number '{raw}' is not in any kept source")
        if _words(fact) in headlines:
            errors.append(f"card copies a headline word for word: '{fact}'")

    everything = " ".join([line, card.get("chip", ""), *facts]).lower()
    errors += [f"banned phrase '{p}'" for p in BANNED if p in everything]

    # Three hook options from three formulas (social-craft hooks.json); the line opens with the best, scoring 50+.
    hooks = script.get("hooks")
    if not (isinstance(hooks, list) and len(hooks) == 3 and all(isinstance(h, str) and h.strip() for h in hooks)):
        errors.append("script.json needs 3 hook options in 'hooks'")
    else:
        best, _ = best_hook(hooks)
        first = re.split(r"(?<=[.!?])\s+", line)[0]
        if not _same_sentence(first, best):
            errors.append(f"line must open with the best hook: '{best}'")
        errors += hook_errors(best, "hook")
    errors += slop_errors(line, "line") + slop_errors(card.get("chip", ""), "card")
    for fact in facts:
        errors += slop_errors(fact, "card")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    run = Path(argv[0])
    script = json.loads((run / "script.json").read_text(encoding="utf-8"))
    kept = json.loads((run / "checked.json").read_text(encoding="utf-8")).get("kept", [])
    errors = script_errors(script, kept)
    record_check(run, "script", errors, [run / "script.json", run / "checked.json"])
    for e in errors or ["script ok"]:
        print(e.encode("ascii", "replace").decode())   # the Windows console is cp1252
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
