#!/usr/bin/env python3
"""Guard a refresh: only what the chosen modes allow may change (writer refresh mode).

    python check_refresh.py --before-dir <dir> --after-dir <dir> --id <lesson-id>
                            --modes figures[,sql-layout][,trim]

Compares <id>.html, <id>.quiz.json and <id>.concepts.json between the two folders.
  figures    - figures, their reading steps, visual blocks, screen and scene specs and bare images
               may change; a text map may be removed
  sql-layout - code may change in whitespace only
  trim       - code, outputs, seeds, run-line headings and their leads may change; it may move
               tables and rows into the seed, never a view, trigger or computed table
Prose, the quiz and the concept manifest (except its `visuals` list) never change.
Exit 0 = only allowed changes, 1 = something else changed, 2 = bad mode or missing file. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from verify_course import Node, descends_from, parse, text_of

MODES = {"figures", "sql-layout", "trim"}
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
PUNCT = set("(),;=<>|+-*/")
KEYS = ("prose", "figures", "maps", "code", "outputs", "seeds", "runheads")
SEEDED = re.compile(r"\bCREATE\s+(?:TEMP(?:ORARY)?\s+)?(VIEW|TRIGGER)\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.I)
# Seed statements that compute rows instead of listing them.
COMPUTED = (
    re.compile(r"\bCREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+AS\b", re.I),
    re.compile(r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+(\w+)\s*(?:\([^)]*\)\s*)?(?:SELECT|WITH)\b", re.I),
)


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def dump(node: Node) -> str:
    """Tag, attributes and text of a subtree: equal dumps mean an unchanged block."""
    attrs = " ".join(f'{k}="{v}"' for k, v in sorted(node.attrs.items()))
    inner = "".join(_ws(x) if isinstance(x, str) else dump(x) for x in node.content)
    return f"<{node.tag} {attrs}>{inner}</{node.tag}>"


def _reading_steps(node: Node) -> bool:
    if node.tag not in ("ul", "ol"):
        return False
    if "nerdit-visual-read" in node.classes:
        return True
    first = next((c for c in node.children if c.tag == "li"), None)
    return first is not None and text_of(first).strip()[:1] in CIRCLED


def _visual_slot(node: Node) -> bool:
    """Screen and scene specs, and a bare image (alone or alone in a <p>): figure scope, so a
    'figures' refresh may swap a hand-made walkthrough image for a spec."""
    if node.tag == "script" and node.classes & {"nerdit-screen", "nerdit-scene"}:
        return True
    if node.tag == "img":
        return True
    return (node.tag == "p" and bool(node.children) and all(c.tag == "img" for c in node.children)
            and not text_of(node).strip())


def parts(html: str) -> dict[str, list[str]]:
    """A lesson split into comparable parts, each a list in page order."""
    out = {k: [] for k in KEYS}

    def visit(node: Node) -> None:
        prev = None
        for item in node.content:
            if isinstance(item, str):
                if item.strip():
                    out["prose"].append(_ws(item))
                continue
            cls = item.classes
            if "nerdit-figure" in cls or "data-nerdit-img" in item.attrs or _visual_slot(item):
                out["figures"].append(dump(item))
            elif prev is not None and "nerdit-figure" in prev.classes and _reading_steps(item):
                out["figures"].append(dump(item))
            elif item.tag == "pre" and "nerdit-map" in cls:
                out["maps"].append(dump(item))
            elif item.tag == "h3" and "nerdit-runhead" in cls:
                out["runheads"].append(_ws(text_of(item)))
            elif item.tag == "p" and prev is not None and "nerdit-runhead" in prev.classes:
                out["runheads"].append(_ws(text_of(item)))
            elif item.tag == "script" and item.attrs.get("type") == "text/plain":
                out["seeds"].append(text_of(item).strip())
            elif item.tag == "textarea":
                out["code"].append(text_of(item).strip("\n"))
            elif item.tag == "pre":
                out["outputs" if descends_from(item, "nerdit-out") else "code"].append(text_of(item).strip("\n"))
            else:
                visit(item)
            prev = item

    visit(parse(html).root)
    return out


def sql_key(sql: str) -> str:
    """SQL with layout removed: whitespace collapsed outside quotes and comments, and dropped
    next to punctuation. A line comment keeps its line end: code joined onto it would be
    commented out, which is not a layout change."""
    out: list[str] = []
    quote, pending, i, n = None, False, 0, len(sql)
    while i < n:
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            end = n if end == -1 else end
            out.append("--" + _ws(sql[i + 2:end]) + "\n")
            pending, i = False, end + 1
            continue
        if sql.startswith("/*", i):
            close = sql.find("*/", i + 2)
            body = sql[i + 2:] if close == -1 else sql[i + 2:close]
            out.append("/*" + _ws(body) + "*/")
            pending, i = False, (n if close == -1 else close + 2)
            continue
        if ch.isspace():
            pending, i = True, i + 1
            continue
        last = out[-1][-1] if out else ""
        if pending and last and ch not in PUNCT and last not in PUNCT and last != "\n":
            out.append(" ")
        pending = False
        if ch in "'\"":
            quote = ch
        out.append(ch)
        i += 1
    return "".join(out)


def seeded_objects(seeds: list[str]) -> set[tuple[str, str]]:
    """(kind, name) for each view, trigger and computed table the seeds create."""
    out = set()
    for seed in seeds:
        out |= {(m.group(1).lower(), m.group(2).lower()) for m in SEEDED.finditer(seed)}
        for pattern in COMPUTED:
            out |= {("computed table", m.group(1).lower()) for m in pattern.finditer(seed)}
    return out


def _hidden_logic(before: dict, after: dict) -> list[str]:
    """Trim may move repeated setup into the seed as plain tables and rows. A view, trigger or
    computed table would make shown code work through logic the learner never reads, even
    when the same query appears earlier (a CTE's name lasts one statement)."""
    problems = []
    for kind, name in sorted(seeded_objects(after["seeds"]) - seeded_objects(before["seeds"])):
        problems.append(f"trim seeded {kind} {name}; a seed holds only tables and listed rows, "
                        f"so show that logic in the code that needs it")
    return problems


def _first_diff(a: list[str], b: list[str]) -> int:
    return next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


def compare(before: dict, after: dict, modes: set[str]) -> list[str]:
    problems: list[str] = []

    def diff(key: str, why: str) -> None:
        a, b = before[key], after[key]
        if a == b:
            return
        i = _first_diff(a, b)
        was = a[i][:70] if i < len(a) else "(nothing)"
        now = b[i][:70] if i < len(b) else "(nothing)"
        problems.append(f"{key} item {i + 1} changed ({why}): was {was!r}, now {now!r}")

    diff("prose", "prose never changes in a refresh")
    if "figures" in modes:
        added = [m for m in after["maps"] if m not in before["maps"]]
        if added:
            problems.append(f"a text map was added or edited; 'figures' may only remove one: {added[0][:70]!r}")
    else:
        diff("figures", "needs the 'figures' mode")
        diff("maps", "needs the 'figures' mode")
    if "trim" not in modes:
        for key in ("outputs", "seeds", "runheads"):
            diff(key, "needs the 'trim' mode")
        if "sql-layout" in modes:
            a = [sql_key(c) for c in before["code"]]
            b = [sql_key(c) for c in after["code"]]
            if a != b:
                problems.append(f"code item {_first_diff(a, b) + 1} changed beyond layout; "
                                f"'sql-layout' only moves whitespace")
        else:
            diff("code", "needs 'sql-layout' or 'trim'")
    else:
        problems += _hidden_logic(before, after)
    return problems


def check(before_dir: Path, after_dir: Path, lid: str, modes: set[str]) -> list[str]:
    unknown = set(modes) - MODES
    if unknown:
        raise ValueError(f"unknown mode(s) {sorted(unknown)}; use {sorted(MODES)}")

    def read(d: Path, ext: str) -> str:
        return (Path(d) / f"{lid}{ext}").read_text(encoding="utf-8")

    problems = compare(parts(read(before_dir, ".html")), parts(read(after_dir, ".html")), set(modes))
    if json.loads(read(before_dir, ".quiz.json")) != json.loads(read(after_dir, ".quiz.json")):
        problems.append("quiz changed; a refresh never touches the quiz")
    bc, ac = json.loads(read(before_dir, ".concepts.json")), json.loads(read(after_dir, ".concepts.json"))
    if "figures" in modes:
        bc.pop("visuals", None)
        ac.pop("visuals", None)
    if bc != ac:
        problems.append("concept manifest changed beyond its visuals list")
    return problems


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--before-dir", required=True)
    ap.add_argument("--after-dir", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--modes", required=True, help="comma list of figures, sql-layout, trim")
    args = ap.parse_args()
    modes = {m.strip() for m in args.modes.split(",") if m.strip()}
    try:
        problems = check(Path(args.before_dir), Path(args.after_dir), args.id, modes)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if problems:
        print(f"FAIL  {args.id}: {len(problems)} change(s) outside {sorted(modes)}")
        for line in problems:
            print(f"  - {line}")
        return 1
    print(f"PASS  {args.id}: only {sorted(modes)} changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
