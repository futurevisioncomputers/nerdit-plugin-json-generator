"""Spoken form of narration for the TTS voice: code and programming words respelled so a Hindi voice
says them the way an Indian teacher would (JSON -> Jason, dict -> dictionary, json.dumps -> Jason dot dumps).

Only the text sent to the voice changes; the plan, the screen and the key terms keep the real spelling.
Words come from pronunciation.json next to this file. A word not listed there is still spoken sensibly:
    json.dumps    -> each part, joined by "dot"
    max_tokens    -> each part, the underscores dropped (__init__ -> dunder init, CONNECT_TIMEOUT -> connect timeout)
    HTTPException -> camelCase split into words, then each word
    HTTP, SSE     -> an unlisted ALL-CAPS word of up to 3 letters, or with no vowel, is spelled letter by letter;
    PRICES        -> a longer one with a vowel is read as a word
Every number is said in English words, so a Hindi voice never reads digits in Hindi:
    2,000 -> two thousand · 2.0 -> two point zero · 30% -> thirty percent · M12 -> M twelve
Code the narration writes in backticks is read the way a teacher says it, never symbol by symbol:
    `@app.get("/products/1")` -> at app dot get slash products slash one
    `response.json["name"]`   -> response dot Jason, name
    `if pid == 2:`            -> if pid is equal to two
"""
import json, re
from functools import lru_cache
from pathlib import Path

LEXICON = Path(__file__).with_name("pronunciation.json")
# A Latin-script name, optionally dotted (json.dumps, main.py) and called (print()); "steps." stays a word.
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\(\))?")
CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
# A number on its own: 2000, 2,000, 1,23,456, 2.0, 30%. Not part of a name (M12 is split in word()).
NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+|\d+)(\.\d+)?(%?)(?![\w])")
ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
        "sixteen seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
SCALES = ((10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand"))


@lru_cache(maxsize=None)
def lexicon(path: Path = LEXICON) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def cardinal(n: int) -> str:
    """English words for a whole number: 1980 -> one thousand nine hundred eighty."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return ONES[n // 100] + " hundred" + (" " + cardinal(n % 100) if n % 100 else "")
    for size, label in SCALES:
        if n >= size:
            return cardinal(n // size) + " " + label + (" " + cardinal(n % size) if n % size else "")
    return str(n)


def number(m: re.Match) -> str:
    whole, frac, pct = m.group(1), m.group(2), m.group(3)
    out = cardinal(int(whole.replace(",", "")))
    if frac:
        out += " point " + " ".join(ONES[int(d)] for d in frac[1:])
    return out + (" percent" if pct else "")


def word(w: str, lex: dict) -> str:
    """One name without dots or underscores."""
    if w in lex:
        return lex[w]
    split = re.fullmatch(r"([A-Za-z]+)(\d+)", w)                   # M12 -> M twelve
    if split:
        return word(split.group(1), lex) + " " + cardinal(int(split.group(2)))
    if w.lower() in lex:                                            # Json, Dict: the lowercase entry
        return lex[w.lower()]
    if re.search(r"[a-z][A-Z]|[A-Z]{2}[a-z]", w):                  # camelCase / PascalCase
        return " ".join(word(p, lex) for p in CAMEL.findall(w))
    if w.isupper() and w.isalpha() and len(w) >= 2:
        if len(w) <= 3 or not re.search("[AEIOU]", w):              # SSE, HTTP: letter by letter
            return " ".join(w)
        return w.lower()                                            # PRICES, DONE: a word
    return w


def name(token: str, lex: dict) -> str:
    """A whole token: dotted, snake_case, dunder or called."""
    if token in lex:
        return lex[token]
    if token.endswith("()"):
        return name(token[:-2], lex)
    if "." in token:
        return " dot ".join(name(p, lex) for p in token.split("."))
    if token.startswith("__") and token.endswith("__") and len(token) > 4:
        return "dunder " + name(token[2:-2], lex)
    if "_" in token:
        # In a CONSTANT_NAME only listed acronyms are spelled: LLM_API_KEY -> L L M A P I key
        const = token.isupper()
        return " ".join(word(p if not const or p in lex else p.lower(), lex)
                        for p in token.split("_") if p) or token
    return word(token, lex)


CODE_SPAN = re.compile(r"`([^`]+)`")
# Operators said as words; every other symbol is dropped (quotes, brackets, colons, commas).
CODE_WORDS = (("==", " is equal to "), ("!=", " is not equal to "), (">=", " is at least "), ("<=", " is at most "),
              ("->", " returns "), ("=", " equals "), ("@", " at "), ("/", " slash "), ("+", " plus "))


def code_speech(code: str) -> str:
    """One code span as a teacher reads it aloud: operators as words, other symbols silent."""
    for sym, said in CODE_WORDS:
        code = code.replace(sym, said)
    # A comparison has spaces round it; a route's <name> never does, so its brackets stay silent.
    code = re.sub(r"\s<\s", " is less than ", code)
    code = re.sub(r"\s>\s", " is greater than ", code)
    code = re.sub(r"\s\*\s", " times ", code)              # arithmetic only: COUNT(*) and *args stay silent
    code = re.sub(r"\s-\s", " minus ", code)
    code = code.replace("[", " INDEXSTEP ")                 # an index reads as a pause: json, name
    code = re.sub(r"[\"'(){}<>:;,\]]", " ", code)
    code = " ".join(code.split()).replace(" INDEXSTEP ", ", ").replace("INDEXSTEP", "")
    return code.strip(" ,")


def spoken(text: str, lex: dict | None = None) -> str:
    """The narration as the voice should say it."""
    lex = lexicon() if lex is None else lex
    text = CODE_SPAN.sub(lambda m: code_speech(m.group(1)), text)
    return NUMBER.sub(number, TOKEN.sub(lambda m: name(m.group(0), lex), text))
