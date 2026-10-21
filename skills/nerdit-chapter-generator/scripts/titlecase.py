"""Title Case for headings: lesson h1-h4, lesson titles, image labels and video titles.

    title_case("why isn't a prediction a guarantee?")  -> "Why Isn't a Prediction a Guarantee?"
    fix_headings(html)                                  -> the HTML with every h1-h4 in Title Case

Every word gets a capital first letter except short joining words (a, of, the, in, vs, ...),
which stay lower case unless they open or close the heading or follow a colon or dash.
Only first letters are raised: SQL, iPhone, df.head(), pandas_ai, 0.25 and anything inside
<code> are left exactly as written. Hindi has no case and passes through unchanged.
"""
import re

SMALL = {"a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet", "as", "at", "by", "in",
         "of", "off", "on", "per", "to", "up", "via", "vs", "vs.", "v.", "with", "from", "into", "onto",
         "over", "than", "if"}
WORD = re.compile(r"[^\s]+")
# Words that look like code, file names or mixed-case brands: never touched.
CODE_LIKE = re.compile(r"[_()\[\]{}=<>/\\@#$]|\w\.\w|\d|^[a-z]+[A-Z]")
BREAK = re.compile(r"[:—–]$|^[—–-]$")   # the next word starts a new phrase
HEADING = re.compile(r"(<(h[1-4])\b[^>]*>)(.*?)(</\2>)", re.S | re.I)
TAG = re.compile(r"(<[^>]+>)")


def _cap(word: str) -> str:
    """Raise the first letter (after any opening quote or bracket); hyphen parts each get one."""
    def one(part: str) -> str:
        m = re.search(r"[A-Za-z]", part)
        if not m or CODE_LIKE.search(part):
            return part
        i = m.start()
        return part[:i] + part[i].upper() + part[i + 1:]
    if "-" in word.strip("-"):
        parts = word.split("-")
        return "-".join(one(p) if i == 0 or p.lower() not in SMALL else p for i, p in enumerate(parts))
    return one(word)


def _core(word: str) -> str:
    return re.sub(r"^[^\w]+|[^\w.]+$", "", word).lower()


def _decide(words: list[str]) -> list[str]:
    out, start = [], True
    last = max((i for i, w in enumerate(words) if re.search(r"[A-Za-z]", w)), default=-1)
    for i, w in enumerate(words):
        core = _core(w)
        if len(core) == 1 and core not in ("a", "i"):
            out.append(w)                      # a variable such as x or n
        elif start or i == last or core not in SMALL:
            out.append(_cap(w))
        elif w.isupper() and len(core) > 1:
            out.append(w)                      # an acronym that happens to be short (AS, OR)
        else:
            out.append(w.lower())
        if re.search(r"[A-Za-z]", w) or BREAK.search(w):
            start = bool(BREAK.search(w))
    return out


def title_case(text: str) -> str:
    """Title Case one plain-text heading, keeping its spacing."""
    words = WORD.findall(text or "")
    if not words:
        return text or ""
    done = iter(_decide(words))
    return WORD.sub(lambda m: next(done), text)


def _fix_inner(inner: str) -> str:
    """Title Case the text of one heading's markup, leaving tags and <code> contents alone."""
    pieces = TAG.split(inner)
    words, where, depth = [], [], 0
    for n, piece in enumerate(pieces):
        if piece.startswith("<"):
            tag = piece.lower()
            if re.match(r"<code\b", tag):
                depth += 1
            elif tag.startswith("</code"):
                depth = max(depth - 1, 0)
            continue
        for m in WORD.finditer(piece):
            words.append(m.group(0) if depth == 0 else "\0" + m.group(0))
            where.append((n, m.start(), m.end()))
    fixed = _decide([w if not w.startswith("\0") else "x_code" for w in words])
    fixed = [w[1:] if w.startswith("\0") else f for w, f in zip(words, fixed)]
    for (n, a, b), new in sorted(zip(where, fixed), key=lambda x: (x[0][0], -x[0][1])):
        pieces[n] = pieces[n][:a] + new + pieces[n][b:]
    return "".join(pieces)


def fix_headings(html: str) -> str:
    return HEADING.sub(lambda m: m.group(1) + _fix_inner(m.group(3)) + m.group(4), html or "")


def heading_problems(html: str) -> list[str]:
    """Headings that are not in Title Case, as their plain text."""
    out = []
    for m in HEADING.finditer(html or ""):
        if _fix_inner(m.group(3)) != m.group(3):
            out.append(re.sub(r"<[^>]+>", "", m.group(3)).strip())
    return out
