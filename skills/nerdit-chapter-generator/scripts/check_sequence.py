#!/usr/bin/env python3
"""Flag lessons whose code uses a construct a *later* lesson owns.

The chapter input array is the course order, so a learner reaching lesson N has seen
lessons 1..N only. A lesson that demonstrates `LLMChain` seven lessons before the chains
lesson, or a `for` loop before the loops lesson, teaches with vocabulary the learner does
not have yet. Each lesson is written by its own isolated agent, so nothing else in the
pipeline notices.

This is a deterministic pre-filter, not a replacement for the QA agent's judgement: it
catches the mechanical cases (a named API, a language construct owned by a later title) at
zero model cost. Anything it cannot name stays the QA agent's job.

Ownership is decided once, by first mention, in input order:
  * API-shaped identifiers (CamelCase, ALLCAPS acronyms) from a lesson's title AND
    description -- precise enough to trust from prose.
  * Language constructs from a lesson's title ONLY -- a description saying "handle error
    conditions" must not hand the `if` keyword to the exceptions lesson.

Only source code is scanned: output blocks and comments are dropped first, and each
construct is matched by a syntax-shaped pattern rather than a bare word, so English prose
inside a `<pre>` ("example code for beginners") is not read as a `for` loop. Prose forward
references such as "You will learn chains in a later lesson" are allowed by the rulebook
and are never flagged -- they live outside `<pre>` entirely.

Usage:
  python check_sequence.py --input <input.json> --course <output.json> [--strict]
"""
import argparse
import html as htmllib
import json
import os
import re
import sys

# A construct is owned by the lesson whose TITLE first matches the phrase. Phrases match at
# a word start on the lowercased title, so "loop" also covers "loops"/"looping".
#
# Each construct is (label, pattern, flavor). Patterns are syntax-shaped on purpose -- `for`
# only counts as a loop when an `in` follows it, `if` only at the start of a line. A
# bare-word search flags every English sentence that survives into a code block.
#
# flavor "sql" restricts the pattern to SQL code blocks. Without that scoping, a pandas
# course's `df.isna().sum()` reads as the SQL aggregate `SUM()` and every lesson before the
# aggregation lesson is flagged.
CONCEPT_CONSTRUCTS = {
    "loop": [("for", r"\bfor\s+[\w,\s]+?\s+in\b", None),
             ("while", r"(?m)^[ \t]*while\b", None)],
    "iterat": [("for", r"\bfor\s+[\w,\s]+?\s+in\b", None),
               ("while", r"(?m)^[ \t]*while\b", None)],
    "condition": [("if", r"(?m)^[ \t]*if\b", None), ("elif", r"(?m)^[ \t]*elif\b", None),
                  ("else", r"(?m)^[ \t]*else\b", None)],
    "if statement": [("if", r"(?m)^[ \t]*if\b", None), ("else", r"(?m)^[ \t]*else\b", None)],
    "branch": [("if", r"(?m)^[ \t]*if\b", None), ("else", r"(?m)^[ \t]*else\b", None)],
    "decision": [("if", r"(?m)^[ \t]*if\b", None), ("else", r"(?m)^[ \t]*else\b", None)],
    "function": [("def", r"(?m)^[ \t]*def\s+\w+\s*\(", None),
                 ("return", r"(?m)^[ \t]*return\b", None)],
    "class": [("class", r"(?m)^[ \t]*class\s+\w+", None)],
    "object-oriented": [("class", r"(?m)^[ \t]*class\s+\w+", None)],
    "exception": [("try", r"(?m)^[ \t]*try\s*:", None),
                  ("except", r"(?m)^[ \t]*except\b", None),
                  ("raise", r"(?m)^[ \t]*raise\s+\w", None)],
    "error handling": [("try", r"(?m)^[ \t]*try\s*:", None),
                       ("except", r"(?m)^[ \t]*except\b", None)],
    "decorator": [("@decorator", r"(?m)^[ \t]*@\w+", None)],
    "generator": [("yield", r"(?m)^[ \t]*yield\b", None)],
    "lambda": [("lambda", r"\blambda\b[\w\s,]*:", None)],
    "comprehension": [("comprehension", r"\[[^\]\n]+\bfor\s+\w+\s+in\b[^\]\n]*\]", None)],
    "file": [("open()", r"(?<![.\w])\bopen\s*\(", None),
             ("with", r"(?m)^[ \t]*with\s+\w", None)],
    "module": [("import", r"(?m)^[ \t]*(?:import|from)\s+\w", None)],
    "import": [("import", r"(?m)^[ \t]*(?:import|from)\s+\w", None)],
    "async": [("async", r"(?m)^[ \t]*async\s+def\b", None), ("await", r"\bawait\s+\w", None)],
    "asynchron": [("async", r"(?m)^[ \t]*async\s+def\b", None),
                  ("await", r"\bawait\s+\w", None)],
    "concurren": [("async", r"(?m)^[ \t]*async\s+def\b", None),
                  ("await", r"\bawait\s+\w", None)],
    "join": [("JOIN", r"(?i)\b(?:inner|left|right|full|cross)?\s*join\s+\w+\s+on\b", "sql")],
    "group by": [("GROUP BY", r"(?i)\bgroup\s+by\b", "sql")],
    "aggregat": [("COUNT()", r"(?i)(?<![.\w])\bcount\s*\(", "sql"),
                 ("SUM()", r"(?i)(?<![.\w])\bsum\s*\(", "sql"),
                 ("AVG()", r"(?i)(?<![.\w])\bavg\s*\(", "sql")],
    "subquer": [("subquery", r"(?is)\bwhere\b[^;]*\(\s*select\b", "sql")],
    "index": [("CREATE INDEX", r"(?i)\bcreate\s+(?:unique\s+)?index\b", "sql")],
    "transaction": [("COMMIT", r"(?i)\bcommit\s*;", "sql"),
                    ("ROLLBACK", r"(?i)\brollback\s*;", "sql")],
}

# A lesson whose TITLE covers a family of names owns all of them, even when the title spells
# out none of them. Without this, "HTTP Methods in FastAPI" (lesson 3) loses POST to the
# later "POST Request Body" lesson, and lesson 3 is flagged for teaching its own subject.
# First mention still wins, so a lesson naming a term outright keeps it.
CONCEPT_IDENTIFIERS = {
    "http method": ["GET", "POST", "PUT", "DELETE", "PATCH"],
    "http verb": ["GET", "POST", "PUT", "DELETE", "PATCH"],
    "rest": ["GET", "POST", "PUT", "DELETE"],
    "crud": ["GET", "POST", "PUT", "DELETE"],
}

# CamelCase with an internal capital (LLMChain, PromptTemplate, ChatOpenAI) or an all-caps
# acronym of 3+ chars (LCEL, RAG, FAISS). Single Capitalized words are skipped on purpose:
# every sentence starts with one.
_IDENT_RE = re.compile(r"\b(?:[A-Za-z][a-z0-9]*[A-Z][A-Za-z0-9]*|[A-Z]{3,})\b")

# Identifiers too generic to attribute to one lesson -- they appear in half the
# descriptions of any course and would flag every lesson before their first mention.
IDENT_STOPWORDS = {
    "API", "APIS", "JSON", "HTTP", "HTTPS", "URL", "URLS", "CSV", "PDF", "PDFS",
    "HTML", "CSS", "SQL", "CLI", "GUI", "IDE", "OS", "AI", "ML", "NLP", "LLM",
    "LLMS", "GPU", "CPU", "RAM", "YAML", "XML", "UUID", "ASCII", "UTF", "TODO",
    "NULL", "TRUE", "FALSE", "AND", "NOT", "THE", "YOU", "FOR",
    # SQL clause words. The construct layer already owns these with SQL-scoped patterns;
    # letting them through here too would double-report and would hand `GROUP` to any
    # lesson whose title happens to read "Grouping with GROUP BY".
    "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "OFFSET", "JOIN",
    "INNER", "OUTER", "FULL", "CROSS", "TABLE", "INSERT", "UPDATE", "VALUES", "INTO",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "DISTINCT", "UNION", "INDEX", "COMMIT",
    "ROLLBACK", "PRIMARY", "FOREIGN",
    # Platforms and environments. They appear in setup notes and ASCII diagrams all
    # course long; no lesson meaningfully "owns" the name of an operating system.
    "MACOS", "WINDOWS", "LINUX", "UBUNTU", "DEBIAN", "ANDROID", "IOS", "UNIX",
}

_OUTPUT_RE = re.compile(r'<div class="nerdit-output".*?</div>\s*</div>', re.S | re.I)
_PRE_RE = re.compile(r"<pre\b([^>]*)>(.*?)</pre>", re.S | re.I)
_LANG_RE = re.compile(r"""data-lang\s*=\s*["']([^"']+)["']""", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_COMMENT_RE = re.compile(r"(?m)(#|--|//).*$")
_SQLISH_RE = re.compile(r"(?is)\bselect\b.*?\bfrom\b")
# Docstrings and string literals are prose the code merely carries. A lesson whose sample
# prompt list contains "What is RAG?" is not using RAG, and a docstring reading "chunk for
# RAG" teaches nothing about it -- while `from ... import FAISS` genuinely does.
_STRING_RES = [
    re.compile(r'"""[\s\S]*?"""'),
    re.compile(r"'''[\s\S]*?'''"),
    re.compile(r'"(?:[^"\\\n]|\\.)*"'),
    re.compile(r"'(?:[^'\\\n]|\\.)*'"),
]


def code_blocks(content):
    """Each source `<pre>` block as (lang, text): output blocks dropped, tags stripped,
    entities decoded, string literals and comments removed.

    Output blocks are printed results, not code the learner writes; comments and string
    literals are English. Scanning any of them turns ordinary prose into phantom `for`
    loops and phantom API usage. Prose outside `<pre>` is skipped too: the rulebook allows
    one sentence naming a future topic, so flagging it would contradict the rule this
    script enforces."""
    body = _OUTPUT_RE.sub(" ", content or "")
    out = []
    for attrs, raw in _PRE_RE.findall(body):
        lang = (_LANG_RE.search(attrs).group(1).lower() if _LANG_RE.search(attrs) else "")
        text = htmllib.unescape(_TAG_RE.sub(" ", raw))
        for pattern in _STRING_RES:  # strings before comments: a `#` may sit inside one
            text = pattern.sub(" ", text)
        out.append((lang, _COMMENT_RE.sub("", text)))
    return out


def code_text(content, flavor=None):
    """All source code in `content`. flavor="sql" keeps only the SQL blocks -- those whose
    `data-lang` says sql, or whose body reads as a SELECT ... FROM."""
    blocks = code_blocks(content)
    if flavor == "sql":
        blocks = [b for b in blocks
                  if b[0] == "sql" or _SQLISH_RE.search(b[1])]
    return "\n".join(t for _, t in blocks)


def identifiers(text):
    """API-shaped names in `text`.

    A token with no lowercase letter must be a 3+ character acronym to count: the
    CamelCase branch also matches two-capital words like `BY`, which are grammar, not
    API names."""
    return {t for t in _IDENT_RE.findall(text or "")
            if t.upper() not in IDENT_STOPWORDS
            and (any(c.islower() for c in t) or len(t) >= 3)}


def canonical(term):
    """Fold a plural identifier onto its singular so one lesson cannot own `DataFrames`
    while a later one owns `DataFrame`. Applied to both sides, so an exact-but-odd fold
    (Series -> Serie) still matches itself."""
    if len(term) > 3 and term.endswith("s") and _IDENT_RE.fullmatch(term[:-1]):
        return term[:-1]
    return term


def _phrase_in(phrase, text):
    """Match `phrase` plus at most a short inflection: "loop" covers loops/looping,
    "iterat" covers iteration, but "class" must not swallow "classification"."""
    return re.search(r"\b" + re.escape(phrase) + r"[a-z]{0,3}\b", text) is not None


def concepts_in_title(title):
    """Constructs owned by a lesson with this title, as {label: (pattern, flavor)}."""
    low = (title or "").lower()
    owned = {}
    for phrase, constructs in CONCEPT_CONSTRUCTS.items():
        if _phrase_in(phrase, low):
            owned.update({label: (pat, flav) for label, pat, flav in constructs})
    return owned


_ALL_CONSTRUCTS = {label: (pattern, flavor)
                   for constructs in CONCEPT_CONSTRUCTS.values()
                   for label, pattern, flavor in constructs}


def constructs_declared(teaches):
    """Constructs a manifest's `teaches` claims, as {label: (pattern, flavor)}.

    Without this, a late "Advanced Loop Patterns" lesson owns `for` for the whole course
    even when an earlier lesson plainly taught loops under a title that never says "loop"
    ("Repeating Work Over a List"). A declaration beats a title guess."""
    owned = {}
    for term in teaches or []:
        term = str(term).strip()
        owned.update(concepts_in_title(term))
        for label, (pattern, flavor) in _ALL_CONSTRUCTS.items():
            if term.lower() == label.lower():
                owned[label] = (pattern, flavor)
    return owned


def identifier_families_in_title(title):
    """Identifier names a lesson claims through its title's subject, not by spelling
    them out (an "HTTP Methods" lesson owns GET/POST/PUT/DELETE)."""
    low = (title or "").lower()
    owned = set()
    for phrase, names in CONCEPT_IDENTIFIERS.items():
        if _phrase_in(phrase, low):
            owned.update(names)
    return owned


def is_applied_lesson(title):
    """Project and capstone lessons apply the course; they do not introduce it.

    Letting lesson 29 "Project -- AI Container Platform" own `OpenAI` makes every earlier
    lesson that touches OpenAI a violation, which inverts the rule: the project is late
    *because* it uses what came before."""
    return re.match(r"\s*(project|capstone|case study)\b", (title or "").lower()) is not None


def load_manifests(concepts_dir, lesson_ids):
    """Read <concepts_dir>/<id>.concepts.json for each id that has one.

    A present-but-broken manifest raises: silently ignoring it would quietly downgrade the
    check to the heuristic, which is worse than stopping and saying so."""
    out = {}
    for lid in lesson_ids:
        path = os.path.join(concepts_dir, lid + ".concepts.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"{lid}: unreadable concept manifest {path}: {e}")
        if not isinstance(data, dict):
            raise ValueError(f"{lid}: concept manifest {path} must be a JSON object")
        for key in ("teaches", "uses"):
            if key in data and not isinstance(data[key], list):
                raise ValueError(f"{lid}: concept manifest {path} field {key} "
                                 f"must be a list")
        out[lid] = data
    return out


def build_ownership(input_lessons, manifests=None):
    """First mention wins: {term: lesson index}. Two maps, because identifiers are precise
    enough to read out of a description and bare constructs are not.

    A lesson's declared `teaches` claims its terms before the heuristic reads that same
    lesson's prose -- the writer knows what it defined, the regex only guesses."""
    manifests = manifests or {}
    ident_owner, construct_owner = {}, {}
    for i, src in enumerate(input_lessons):
        title = src.get("title", "")
        blob = f"{title} {src.get('description', '')}"
        declared = manifests.get(src.get("id"), {}).get("teaches", [])
        for term in declared:
            ident_owner.setdefault(canonical(term), i)
        for label, (pattern, flavor) in constructs_declared(declared).items():
            construct_owner.setdefault(label, (i, pattern, flavor))
        if is_applied_lesson(title) and not declared:
            continue
        for term in identifiers(blob) | identifier_families_in_title(title):
            ident_owner.setdefault(canonical(term), i)
        for label, (pattern, flavor) in concepts_in_title(title).items():
            construct_owner.setdefault(label, (i, pattern, flavor))
    return ident_owner, construct_owner


def find_violations(input_lessons, lessons_by_id, manifests=None, allow=()):
    """One entry per (lesson, term) where the lesson reaches for a term a later lesson
    owns -- in its code, or in its manifest's declared `uses`.

    A term the lesson's own title/description/manifest names is never a violation, and
    neither is anything in `allow` (the course's assumed prior knowledge)."""
    manifests = manifests or {}
    allow_terms = {canonical(t) for t in allow} | set(allow)
    ident_owner, construct_owner = build_ownership(input_lessons, manifests)
    out = []
    for i, src in enumerate(input_lessons):
        lid = src["id"]
        content = lessons_by_id.get(lid, "")
        code = code_text(content)
        manifest = manifests.get(lid, {})
        if not code.strip() and not manifest:
            continue
        own_title = src.get("title", "")
        own_blob = f"{own_title} {src.get('description', '')}"
        own_idents = {canonical(t) for t in
                      identifiers(own_blob) | identifier_families_in_title(own_title)}
        own_idents |= {canonical(t) for t in manifest.get("teaches", [])}
        own_constructs = concepts_in_title(own_title)
        own_constructs.update(constructs_declared(manifest.get("teaches", [])))

        def _leak(term):
            owner = ident_owner.get(canonical(term))
            return (owner if owner is not None and owner > i
                    and canonical(term) not in own_idents
                    and canonical(term) not in allow_terms else None)

        seen = set()
        for term in sorted(identifiers(code)) + sorted(manifest.get("uses", [])):
            owner = _leak(term)
            if owner is not None and canonical(term) not in seen:
                seen.add(canonical(term))
                out.append((i, lid, term, owner, input_lessons[owner]["title"]))
        for label, (owner, pattern, flavor) in sorted(construct_owner.items()):
            if owner <= i or label in own_constructs or label in allow_terms:
                continue
            haystack = code_text(content, flavor) if flavor else code
            if haystack.strip() and re.search(pattern, haystack):
                out.append((i, lid, label, owner, input_lessons[owner]["title"]))
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Flag lessons using constructs a later lesson owns")
    ap.add_argument("--input", required=True, help="course-<chapter>_input.json")
    ap.add_argument("--course", required=True, help="assembled course-<chapter>_output.json")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero when any violation is found")
    ap.add_argument("--concepts-dir", default=None,
                    help="directory holding <id>.concepts.json manifests; declared "
                         "ownership overrides the title/description heuristic")
    ap.add_argument("--allow", default="",
                    help="comma-separated terms the course assumes as prior knowledge")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        input_lessons = json.load(f)
    with open(args.course, encoding="utf-8") as f:
        course = json.load(f)
    lessons_by_id = {l["id"]: l.get("content", "") for l in course.get("lessons", [])}

    manifests = {}
    if args.concepts_dir:
        try:
            manifests = load_manifests(args.concepts_dir,
                                       [l["id"] for l in input_lessons])
        except ValueError as e:
            print(f"ERROR: {e}")
            sys.exit(2)
    allow = {t.strip() for t in args.allow.split(",") if t.strip()}

    violations = find_violations(input_lessons, lessons_by_id, manifests, allow)
    coverage = (f"{len(manifests)}/{len(input_lessons)} lessons declared a concept manifest"
                if args.concepts_dir else "heuristic ownership only, no manifests")
    if not violations:
        print(f"SEQUENCING: clean -- {len(input_lessons)} lessons, "
              f"no lesson uses a later lesson's constructs ({coverage})")
        return

    print(f"SEQUENCING: {len(violations)} violation(s) ({coverage})")
    for i, lid, term, owner, owner_title in violations:
        print(f"  lesson {i + 1:02d} {lid}: uses {term!r} -- first taught in "
              f"lesson {owner + 1:02d} \"{owner_title}\"")
    print("Rewrite each example with constructs the learner already has, then re-assemble. "
          "A prose-only mention of a future topic is fine; code is not.")
    if args.strict:
        sys.exit(2)


if __name__ == "__main__":
    main()
