#!/usr/bin/env python3
"""Run every SQL example in a lesson against its seed data and compare with the shown output.

Usage: python check_sql_outputs.py --course <course-output.json> [--lesson <lesson-id>]

Each example runs on a fresh in-memory database built from the lesson's seed scripts; if it
fails because a table is missing, it is retried after the earlier examples, and if it creates a
seed table itself, it runs on an empty database. ASCII-table outputs are compared cell by cell
(every result set, in order); an error output matches when it contains the database's message.
Anything else is listed as unchecked for a human to read.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import sys

SEED = re.compile(r'<script\b[^>]*type="text/plain"[^>]*>(.*?)</script>', re.S | re.I)
EXPLAIN = re.compile(r"\bEXPLAIN\b", re.I)
RUN = re.compile(r'<div class="nerdit-run">.*?<pre data-lang="sql"><code>(.*?)</code></pre>'
                 r'.*?<div class="nerdit-out">.*?<pre><code>(.*?)</code></pre>', re.S)


def parse_table(txt: str) -> list[list[str]] | None:
    txt = txt.strip()
    if not txt.startswith("+"):
        return None
    return [[c.strip() for c in ln.strip().strip("|").split("|")]
            for ln in txt.splitlines() if ln.strip().startswith("|")]


def _statements(sql: str) -> list[str]:
    out, buf = [], ""
    for ch in sql:
        buf += ch
        if ch == ";" and sqlite3.complete_statement(buf):
            out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def _cell(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _same_cell(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return float(a) == float(b)  # 30 and 30.0 are the same number
    except ValueError:
        return False


def _same(rows: list[list[str]], expected: list[list[str]]) -> bool:
    return len(rows) == len(expected) and all(
        len(r) == len(e) and all(_same_cell(a, b) for a, b in zip(r, e)) for r, e in zip(rows, expected))


def _run(seed: str, history: list[str], sql: str):
    con = sqlite3.connect(":memory:")
    try:
        con.executescript(seed)
        for earlier in history:
            try:
                con.executescript(earlier)
            except sqlite3.Error:
                pass
        rows = []
        for stmt in _statements(sql):
            cur = con.execute(stmt)
            if cur.description:  # every result set, in order, as the shown tables stack them
                rows += [[d[0] for d in cur.description]] + [[_cell(v) for v in r] for r in cur.fetchall()]
        return rows or None, None
    except sqlite3.Error as e:
        return None, str(e)
    finally:
        con.close()


def check_lesson(content: str) -> dict:
    seed = "\n".join(html.unescape(s) for s in SEED.findall(content))
    report = {"examples": 0, "match": 0, "mismatch": [], "unchecked": []}
    history: list[str] = []
    for i, (code, shown) in enumerate(RUN.findall(content), 1):
        report["examples"] += 1
        sql, shown = html.unescape(code), html.unescape(shown)
        if EXPLAIN.search(sql):
            history.append(sql)
            report["unchecked"].append(f"example {i}: query plans differ between database versions; read it by hand")
            continue
        rows, err = _run(seed, [], sql)
        if err and "no such table" in err:
            rows, err = _run(seed, history, sql)
        elif err and "already exists" in err:  # the example builds the seed tables itself
            rows, err = _run("", [], sql)
        history.append(sql)
        expected = parse_table(shown)
        if expected is not None and rows is not None:
            if _same(rows, expected):
                report["match"] += 1
            else:
                report["mismatch"].append(f"example {i}: shown {expected} but the data gives {rows}")
        elif err:
            if err.lower() in shown.lower():
                report["match"] += 1
            else:
                report["mismatch"].append(f"example {i}: database error '{err}' not shown")
        else:
            report["unchecked"].append(f"example {i}: output is not a table; read it by hand")
    return report


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--lesson")
    args = ap.parse_args()
    with open(args.course, encoding="utf-8") as f:
        course = json.load(f)
    bad = 0
    for lesson in course.get("lessons", []):
        if args.lesson and lesson["id"] != args.lesson:
            continue
        r = check_lesson(lesson.get("content") or "")
        if not r["examples"]:
            continue
        print(f"{lesson['id']}: {r['examples']} examples, {r['match']} match, "
              f"{len(r['mismatch'])} mismatch, {len(r['unchecked'])} unchecked")
        for line in r["mismatch"] + r["unchecked"]:
            print(f"  - {line}")
        bad += len(r["mismatch"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
