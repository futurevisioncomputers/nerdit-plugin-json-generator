"""Score how machine-written a longer English text reads, on five checks (0-100; under 50 = FLAGGED).

Adapted from https://github.com/Jakeschincariol/instagram-agent-skill (MIT, Copyright (c) 2026 Jake Schincariol),
skills/ig-human/detect.py: the five checks and the overall formula are unchanged; the lexicon is NERDIT's
references/slop.json with its keep list. Used as a gate on LinkedIn captions only: short and Hinglish captions are
judged by humanize.py's word checks instead.

CLI: humanscore.py <file>   prints the five checks; exit 1 when the text is FLAGGED (score under 50)
"""
import re
import statistics
import sys
import unicodedata
from pathlib import Path

from humanize import LEX
from textio import say

PASS_MARK = 50.0
SENT_RE = re.compile(r"[^.!?\n]+[.!?]*")
WORD_RE = re.compile(r"[A-Za-z']+")
CONTRACTIONS = re.compile(r"\b\w+'(?:s|t|re|ve|ll|d|m)\b", re.IGNORECASE)
PRONOUNS = re.compile(r"\b(i|me|my|mine|we|us|our|you|your)\b", re.IGNORECASE)
NUMBERS = re.compile(r"\b\d[\d,.]*%?\b|\$\d")
PROPER = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}\b", re.MULTILINE)
CHECKS = ["BURSTINESS", "SPECIFICITY", "SLOP DENSITY", "FINGERPRINT", "VOICE"]


def _clamp(n: float) -> float:
    return max(0.0, min(100.0, n))


def _scale(value: float, human: float, machine: float) -> float:
    """Map value onto 0-100 where `human` -> 100 and `machine` -> 0."""
    if human == machine:
        return 50.0
    return _clamp((value - machine) / (human - machine) * 100)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_RE.findall(text) if len(s.split()) > 2]


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def _check_burstiness(text: str) -> tuple[float, str]:
    lens = [len(s.split()) for s in _sentences(text)]
    if len(lens) < 4:
        return 50.0, "too short to judge"
    mean = statistics.mean(lens)
    cv = statistics.pstdev(lens) / mean if mean else 0
    return _scale(cv, human=0.70, machine=0.22), f"variation {cv:.2f} across {len(lens)} sentences"


def _check_specificity(text: str) -> tuple[float, str]:
    w = _words(text)
    if len(w) < 25:
        return 50.0, "too short to judge"
    hits = len(NUMBERS.findall(text)) + len(set(PROPER.findall(text)))
    density = hits * 100 / len(w)
    return _scale(density, human=6.0, machine=0.5), f"{hits} concrete markers"


def _check_slop(text: str) -> tuple[float, str]:
    w = _words(text)
    if not w:
        return 50.0, "empty"
    keep = {k.lower() for k in LEX.get("nerdit_keep", [])}
    hits = 0
    for entry in LEX["words"] + LEX["phrases"]:
        if entry["find"].lower() in keep:
            continue
        pattern = re.compile(r"\b" + re.escape(entry["find"]).replace(r"\ ", r"\s+") + r"\b", re.IGNORECASE)
        hits += len(pattern.findall(text))
    density = hits * 100 / len(w)
    return _scale(density, human=0.0, machine=4.0), f"{hits} stock terms"


def _check_fingerprint(text: str) -> tuple[float, str]:
    invisible = sum(1 for c in text if unicodedata.category(c) == "Cf")
    em = text.count("—")
    curly = sum(text.count(c) for c in "‘’“”")
    ellip = text.count("…")
    nbsp = sum(text.count(c) for c in "   ")
    total = invisible * 4 + em * 2 + curly + ellip + nbsp
    per1k = total * 1000 / max(len(text), 1)
    return _scale(per1k, human=0.0, machine=12.0), f"{invisible} invisible, {em} em dash, {curly} curly quote"


def _check_voice(text: str) -> tuple[float, str]:
    w = _words(text)
    if len(w) < 25:
        return 50.0, "too short to judge"
    per100 = 100 / len(w)
    contractions = len(CONTRACTIONS.findall(text)) * per100
    person = len(PRONOUNS.findall(text)) * per100
    tells = 0
    for s in LEX["structures"]:
        try:
            tells += len(re.compile(s["regex"], re.MULTILINE).findall(text))
        except re.error:
            continue
    bullets = [len(b.split()) for b in re.findall(r"(?m)^\s*[-*•]\s+(.+)$", text)]
    uniform = len(bullets) >= 3 and statistics.pstdev(bullets) < 1.6
    score = (_scale(contractions, human=3.0, machine=0.0) * 0.35
             + _scale(person, human=8.0, machine=1.0) * 0.35
             + _clamp(100 - tells * 22) * 0.30)
    if uniform:
        score -= 12
    return _clamp(score), f"{tells} structural tell(s)"


def human_score(text: str) -> dict:
    checks = {
        "BURSTINESS": _check_burstiness(text),
        "SPECIFICITY": _check_specificity(text),
        "SLOP DENSITY": _check_slop(text),
        "FINGERPRINT": _check_fingerprint(text),
        "VOICE": _check_voice(text),
    }
    scores = [checks[c][0] for c in CHECKS]
    # The weakest check drags the verdict: a detector only needs one signal.
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4
    verdict = "PASS" if overall >= 70 and min(scores) >= 55 else ("REVIEW" if overall >= 50 else "FLAGGED")
    return {"score": round(overall, 1), "verdict": verdict, "checks": checks}


def human_errors(text: str, label: str, minimum: float = PASS_MARK) -> list[str]:
    r = human_score(text)
    if r["score"] >= minimum:
        return []
    weakest = min(CHECKS, key=lambda c: r["checks"][c][0])
    return [f"{label}: reads machine-written (human score {r['score']:.0f}; at least {minimum:.0f}; weakest: {weakest})"]


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        say(__doc__)
        return 2
    r = human_score(Path(argv[0]).read_text(encoding="utf-8"))
    for name in CHECKS:
        score, detail = r["checks"][name]
        say(f"{name:<13} {score:5.1f}  {detail}")
    say(f"HUMAN SCORE   {r['score']:5.1f}  {r['verdict']}")
    return 1 if r["score"] < PASS_MARK else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
