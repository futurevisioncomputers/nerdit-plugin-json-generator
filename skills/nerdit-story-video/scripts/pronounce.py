"""Spoken form of narration for the TTS voice: code and programming words respelled so a Hindi voice
says them the way an Indian teacher would (JSON -> Jason, dict -> dictionary, json.dumps -> Jason dot dumps).

Only the text sent to the voice changes; the plan, the screen and the key terms keep the real spelling.
Words come from pronunciation.json next to this file. A word not listed there is still spoken sensibly:
    json.dumps    -> each part, joined by "dot"
    max_tokens    -> each part, the underscores dropped (__init__ -> dunder init, CONNECT_TIMEOUT -> connect timeout)
    HTTPException -> camelCase split into words, then each word
    HTTP, SSE     -> an unlisted ALL-CAPS word of up to 3 letters, or with no vowel, is spelled letter by letter;
    PRICES        -> a longer one with a vowel is read as a word
"""
import json, re
from functools import lru_cache
from pathlib import Path

LEXICON = Path(__file__).with_name("pronunciation.json")
# A Latin-script name, optionally dotted (json.dumps, main.py) and called (print()); "steps." stays a word.
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\(\))?")
CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


@lru_cache(maxsize=None)
def lexicon(path: Path = LEXICON) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def word(w: str, lex: dict) -> str:
    """One name without dots or underscores."""
    if w in lex:
        return lex[w]
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


def spoken(text: str, lex: dict | None = None) -> str:
    """The narration as the voice should say it."""
    lex = lexicon() if lex is None else lex
    return TOKEN.sub(lambda m: name(m.group(0), lex), text)
