"""Numbers in one form, so "85,000", "85000", "85K" and "eighty-five thousand" compare equal.

(Named numwords, not numbers: a numbers.py here would shadow the standard library's `numbers` module.)
"""
import re

NUM = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)([kKmM])?(%)?(?!\w)")
YEAR = re.compile(r"^20\d\d$")
MULT = {"k": 1_000, "m": 1_000_000}
UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), start=2)}
SCALES = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}


def _plain(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


def find(text: str) -> list[tuple[str, str]]:
    """(as written, normalised) for every number in the text; years 20xx are not claims."""
    out = []
    for m in NUM.finditer(text):
        digits = m.group(1).rstrip(",")
        if not m.group(2) and not m.group(3) and YEAR.match(digits):
            continue
        value = float(digits.replace(",", "")) * MULT.get((m.group(2) or "").lower(), 1)
        out.append((m.group(0).rstrip(","), _plain(value)))
    return out


def normalise(text: str) -> set[str]:
    return {norm for _, norm in find(text)}


def _small(token: str) -> int | None:
    parts = token.split("-")
    if all(p in UNITS or p in TENS for p in parts):
        return sum(UNITS.get(p, TENS.get(p, 0)) for p in parts)
    return None


def words_to_digits(tokens: list[str]) -> list[str]:
    out, total, current, in_run = [], 0, 0, False

    def flush():
        nonlocal total, current, in_run
        if in_run:
            out.append(str(total + current))
        total, current, in_run = 0, 0, False

    for tok in tokens:
        small = _small(tok)
        if small is not None:
            current += small
            in_run = True
        elif in_run and tok == "hundred":
            current *= 100
        elif in_run and tok in SCALES:
            total += current * SCALES[tok]
            current = 0
        else:
            flush()
            out.append(tok)
    flush()
    return out
