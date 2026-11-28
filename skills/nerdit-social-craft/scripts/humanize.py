"""Find (and optionally fix) the machine fingerprint in post text: invisible characters, dashes, stock words, stock
sentence shapes.

Adapted from https://github.com/Jakeschincariol/instagram-agent-skill (MIT, Copyright (c) 2026 Jake Schincariol),
skills/ig-human/humanize.py: the clean-up passes are unchanged. NERDIT adds slop_errors (the checker other skills
call), the keep list in references/slop.json, and masking of links and hashtags before the scan. Runs on English and
Roman Hinglish text; never on story-video narration.

CLI: humanize.py <file> [--fix]   prints the errors (exit 1 if any), or with --fix prints the cleaned text (exit 0)
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

from textio import say

LEXICON = Path(__file__).resolve().parents[1] / "references" / "slop.json"
URL_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+")
HASHTAG_RE = re.compile(r"#\w+")


def load_lexicon(path: Path = LEXICON) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


LEX = load_lexicon()


def _cp(spec: str):
    """'U+200B' -> 0x200B;  'U+E0000-U+E007F' -> (start, end)."""
    if "-" in spec:
        a, b = spec.split("-")
        return (int(a[2:], 16), int(b[2:], 16))
    return int(spec[2:], 16)


def _invisible_pattern(entry: dict) -> str:
    cp = _cp(entry["cp"])
    if isinstance(cp, tuple):
        return "[" + re.escape(chr(cp[0])) + "-" + re.escape(chr(cp[1])) + "]"
    return re.escape(chr(cp))


def _term_pattern(find: str) -> re.Pattern:
    # Word boundaries only where the term starts or ends with a word character ("the result?" ends in "?").
    body = re.escape(find).replace(r"\ ", r"\s+")
    start = r"\b" if re.match(r"\w", find) else ""
    end = r"\b" if re.search(r"\w$", find) else ""
    return re.compile(start + body + end, re.IGNORECASE)


def _terms(lex: dict) -> list[dict]:
    keep = {k.lower() for k in lex.get("nerdit_keep", [])}
    entries = [e for e in lex["phrases"] + lex["words"] if e["find"].lower() not in keep]
    return sorted(entries, key=lambda e: len(e["find"]), reverse=True)   # phrases before the words inside them


# --- clean-up passes (ported) -------------------------------------------------------------------------------------

def _protect_urls(text: str) -> tuple[str, list[str]]:
    found = []

    def stash(m):
        found.append(m.group(0))
        return f"\x00URL{len(found) - 1}\x00"

    return URL_RE.sub(stash, text), found


def _restore_urls(text: str, found: list[str]) -> str:
    for i, url in enumerate(found):
        text = text.replace(f"\x00URL{i}\x00", url)
    return text


def _pass_invisible(text: str, lex: dict) -> tuple[str, list]:
    hits = []
    for entry in lex["invisible"]:
        pattern = _invisible_pattern(entry)
        n = len(re.findall(pattern, text))
        if n:
            hits.append({"name": entry["name"], "count": n})
            text = re.sub(pattern, "" if entry["action"] == "delete" else " ", text)
    stray = [c for c in text if unicodedata.category(c) == "Cf" and c != "\x00"]
    if stray:
        hits.append({"name": "other invisible format chars", "count": len(stray)})
        text = "".join(c for c in text if unicodedata.category(c) != "Cf" or c == "\x00")
    return text, hits


def _pass_typographic(text: str, lex: dict) -> tuple[str, list]:
    hits = []
    for entry in lex["typographic"]:
        ch = entry["from"]
        n = text.count(ch)
        if not n:
            continue
        hits.append({"name": entry["name"], "count": n})
        if ch == "—":
            text = re.sub(r"\s*—\s*", ", ", text)
        elif ch == "–":
            text = re.sub(r"\s*–\s*(?=\d)", "-", text)
            text = re.sub(r"\s+–\s+", ", ", text)
            text = text.replace("–", "-")
        else:
            text = text.replace(ch, entry["to"])
    text = re.sub(r",\s*([,.;:!?])", r"\1", text)
    text = re.sub(r",\s*\n", "\n", text)
    return text, hits


def _match_case(src: str, repl: str) -> str:
    if not repl:
        return repl
    if src.isupper() and len(src) > 1:
        return repl.upper()
    if src[0].isupper():
        return repl[0].upper() + repl[1:]
    return repl


def _pass_lexical(text: str, lex: dict) -> tuple[str, list]:
    hits = []
    for entry in _terms(lex):
        pattern = _term_pattern(entry["find"])
        found = pattern.findall(text)
        if not found:
            continue
        hits.append({"find": entry["find"], "replace": entry["replace"], "count": len(found)})
        text = pattern.sub(lambda m, r=entry["replace"]: _match_case(m.group(0), r), text)
    # Deleting a word or clause leaves orphaned punctuation behind; tidy it.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"(?m)^[ \t]*(?:[,.;:]+[ \t]*)+", "", text)
    text = re.sub(r"(?m)^[ \t](?=\S)", "", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r",\s*([,.;:!?])", r"\1", text)
    text = text.replace("...", "\x00ELL\x00")
    text = re.sub(r"\.\s*\.+", ".", text)
    text = re.sub(r"([!?])\s*\.", r"\1", text)
    text = text.replace("\x00ELL\x00", "...")
    text = re.sub(r"(?m)^[ \t]+$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r",\s*(also|so|still|basically|in the end)\s*,\s*",
                  lambda m: ". " + m.group(1)[0].upper() + m.group(1)[1:] + ", ", text)
    return text, hits


def _scan_structures(text: str, lex: dict) -> list[dict]:
    flags = []
    skip = set(lex.get("nerdit_skip_structures", []))
    for s in lex["structures"]:
        if s.get("id") in skip:
            continue
        try:
            pattern = re.compile(s["regex"], re.MULTILINE)
        except re.error:
            continue
        if pattern.search(text):
            flags.append({"name": s["name"], "fix": s["fix"]})
    return flags


def _restore_capitals(original: str, text: str) -> str:
    """Deleting an opener leaves the next word lower case; fix it only for writers who capitalise sentences."""
    starts = re.findall(r"(?:^|[.!?]\s+|\n)\s*([A-Za-z])", original)
    if not starts or sum(1 for c in starts if c.isupper()) * 2 < len(starts):
        return text
    return re.sub(r"(?:^|(?<=[.!?] )|(?<=[.!?]\n)|(?<=\n))\s*([a-z])",
                  lambda m: m.group(0)[:-1] + m.group(1).upper(), text)


def clean(text: str) -> tuple[str, dict]:
    original = text
    text, urls = _protect_urls(text)
    text, invisible = _pass_invisible(text, LEX)
    text, typographic = _pass_typographic(text, LEX)
    text, lexical = _pass_lexical(text, LEX)
    text = _restore_capitals(original, text)
    text = _restore_urls(text, urls)
    return text.strip(), {"invisible": invisible, "typographic": typographic, "lexical": lexical,
                          "structures": _scan_structures(text, LEX)}


# --- the checker ---------------------------------------------------------------------------------------------------

def slop_errors(text: str, label: str) -> list[str]:
    errors = []
    for entry in LEX["invisible"]:
        if re.search(_invisible_pattern(entry), text):
            errors.append(f"{label}: invisible character {entry['name']} (delete it)")
    if "—" in text:
        errors.append(f"{label}: em dash; use a comma or a full stop")
    if re.search(r"(?<!\d)–|–(?!\d)", text):   # "₹3–5 LPA" is a number range, the en dash's proper job
        errors.append(f"{label}: en dash; use a hyphen")
    # Links and hashtags are not prose: "nerdit.in/journey" and "#journey" are not stock words.
    prose = HASHTAG_RE.sub(" ", URL_RE.sub(" ", text)).replace("’", "'")
    for entry in _terms(LEX):
        pattern = _term_pattern(entry["find"])
        if pattern.search(prose):
            fix = f"say '{entry['replace']}'" if entry["replace"] else "cut it"
            errors.append(f"{label}: stock word '{entry['find']}' ({fix})")
            prose = pattern.sub(" ", prose)   # a phrase hit does not also report the word inside it
    for s in _scan_structures(prose, LEX):
        errors.append(f"{label}: {s['name']}: {s['fix']}")
    return errors


def main(argv: list[str]) -> int:
    args = [a for a in argv if a != "--fix"]
    if len(args) != 1:
        say(__doc__)
        return 2
    text = Path(args[0]).read_text(encoding="utf-8")
    if "--fix" in argv:
        # The cleaned copy is for use, so it keeps every character (UTF-8); say() is for diagnostics only.
        sys.stdout.flush()
        sys.stdout.buffer.write((clean(text)[0] + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
        return 0
    errors = slop_errors(text, "text")
    for e in errors or ["text ok"]:
        say(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
