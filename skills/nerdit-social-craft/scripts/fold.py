"""Check what the feed shows before "... more": the first sentence must end inside it, with something concrete.

Adapted from https://github.com/Jakeschincariol/instagram-agent-skill (MIT, Copyright (c) 2026 Jake Schincariol),
skills/ig-caption/caption.py (the 125-character Instagram window). NERDIT adds LinkedIn (about 140 characters on a
phone; no official number, checked 2026-11-28, see docs/superpowers/specs/2026-11-28-phase0-facts.md) and a
stricter "concrete" test that does not count a word just because it starts a sentence.

CLI: fold.py <platform> <file>   exit 1 when the first sentence is cut or nothing concrete shows before the cut
"""
import re
import sys
from pathlib import Path

from textio import say

FOLD = {"instagram": 125, "linkedin": 140}
URL_RE = re.compile(r"https?://\S+|www\.\S+")
CONCRETE = re.compile(r"\d|(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}\b", re.MULTILINE)


def _visible(text: str) -> str:
    """The caption as the feed starts it: links masked, leading blank lines dropped."""
    return URL_RE.sub("", text).lstrip()


def feed_window(text: str, platform: str) -> str:
    return _visible(text)[:FOLD[platform]]


def fold_errors(text: str, platform: str, label: str) -> list[str]:
    if platform not in FOLD:
        return []
    shown = _visible(text)
    cut = FOLD[platform]
    errors = []
    first = re.split(r"(?<=[.!?])\s|\n", shown, maxsplit=1)[0].strip()
    if len(first) > cut:
        errors.append(f"{label}: first sentence is {len(first)} characters; the feed cuts at {cut}")
    if not CONCRETE.search(shown[:cut]):
        errors.append(f"{label}: nothing concrete before the cut (a number or a name like Python or Excel)")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in FOLD:
        say(__doc__)
        return 2
    platform, text = argv[0], Path(argv[1]).read_text(encoding="utf-8")
    say("feed shows: " + feed_window(text, platform).replace("\n", " / ") + " ... more")
    errors = fold_errors(text, platform, platform)
    for e in errors or [f"{platform}: fold ok"]:
        say(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
