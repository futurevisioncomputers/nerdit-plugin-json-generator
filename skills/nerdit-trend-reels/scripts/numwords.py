"""Numbers in one form, so "85,000", "85000", "85K", "85 thousand" and "eighty-five thousand" compare equal.

(Named numwords, not numbers: a numbers.py here would shadow the standard library's `numbers` module.)
"""
import re

SCALES = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
MULT = {"k": 1_000, "m": 1_000_000, "mn": 1_000_000, "b": 1_000_000_000, "bn": 1_000_000_000}
NUM = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?:(bn|mn|[kmb])(?![a-z])|\s+(thousand|million|billion)\b)?(%)?(?!\w)", re.I)
YEAR = re.compile(r"^20\d\d$")
DIGITS = re.compile(r"^\d+(?:\.\d+)?$")
UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), start=2)}


def plain(value: float) -> str:
    value = round(value, 6)
    return str(int(value)) if value == int(value) else str(value)


def find(text: str) -> list[tuple[str, str]]:
    """(as written, normalised) for every number in the text; years 20xx are not claims."""
    out = []
    for m in NUM.finditer(text):
        digits, suffix, scale, pct = m.group(1).rstrip(","), m.group(2), m.group(3), m.group(4)
        if not (suffix or scale or pct) and YEAR.match(digits):
            continue
        mult = MULT[suffix.lower()] if suffix else SCALES[scale.lower()] if scale else 1
        out.append((m.group(0).rstrip(","), plain(float(digits.replace(",", "")) * mult)))
    return out


def normalise(text: str) -> set[str]:
    return {norm for _, norm in find(text)}


def _small(token: str) -> int | None:
    parts = token.split("-")
    if all(p in UNITS or p in TENS for p in parts):
        return sum(UNITS.get(p, TENS.get(p, 0)) for p in parts)
    return None


def words_to_digits(tokens: list[str]) -> list[str]:
    """Runs of number words (or a digit token) become one digit token: "one point five million" -> "1500000"."""
    out, total, current, in_run, i = [], 0.0, 0.0, False, 0

    def flush():
        nonlocal total, current, in_run
        if in_run:
            out.append(plain(total + current))
        total, current, in_run = 0.0, 0.0, False

    while i < len(tokens):
        tok = tokens[i]
        small = _small(tok)
        if DIGITS.match(tok):
            flush()
            current, in_run = float(tok), True
        elif small is not None:
            current += small
            in_run = True
        elif in_run and tok == "point" and i + 1 < len(tokens) and tokens[i + 1] in UNITS:
            decimals = ""
            while i + 1 < len(tokens) and tokens[i + 1] in UNITS and UNITS[tokens[i + 1]] < 10:
                i += 1
                decimals += str(UNITS[tokens[i]])
            current += float("0." + decimals)
        elif in_run and tok == "hundred":
            current *= 100
        elif in_run and tok in SCALES:
            total += current * SCALES[tok]
            current = 0.0
        else:
            flush()
            out.append(tok)
        i += 1
    flush()
    return out
