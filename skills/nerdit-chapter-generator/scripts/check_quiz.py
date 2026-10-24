#!/usr/bin/env python3
"""Compute the quiz answers that can be computed (plan check f).

    python check_quiz.py --course <course_output.json>

An applied question shows its snippet in backticks (or a fenced block) in its text. When the
snippet is Python (it prints), it runs on the website's engine after the lesson's run lines,
in their namespace, with the lesson's dataset files. When it is a SQL SELECT, it runs on the
lesson's seed scripts and is judged only when it returns one value. The result must be the
marked option whenever exactly one option equals it (an error matches the option that names
its class, such as IndexError). A snippet whose result no option equals is a warning: the
question may ask something else about the code. Assessment questions are checked in the
lesson their id names. Other questions (definitions, Excel) are left to QA.

Exit 0 = no wrong answer; 1 = a marked option is not the computed result; 2 = the Python
engine is missing for a lesson that needs it, or an unreadable file.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re
import sys

from check_python_outputs import build_files, normalise, python_parts
from check_sql_outputs import SEED, _run, _same_cell
from pyodide_engine import EngineError, EngineTimeout, run_job

TICKS = re.compile(r'```[a-z]*\n?(.*?)```|`([^`\n]+)`', re.S)
ERROR = re.compile(r'\b([A-Z]\w*(?:Error|Exception))\b')


def snippets(text: str) -> list[str]:
    return [(fenced or inline).strip() for fenced, inline in TICKS.findall(html.unescape(text or ''))]


def kind(parts: list[str]) -> str | None:
    if any('print(' in p for p in parts):
        return 'python'
    if any(re.match(r'\s*(WITH|SELECT)\b', p, re.I) for p in parts):
        return 'sql'
    return None


def _option(text: str) -> str:
    text = str(text).strip()
    return text[1:-1].strip() if len(text) > 1 and text[0] == text[-1] == '`' else text


def matching(options: list[str], value: str, numeric: bool = True) -> list[int]:
    """Options equal to `value`. `numeric` (SQL cells): 20 and 20.0 are the same number. Python
    prints exact text, so its 250 and 250.0 differ."""
    value = normalise(value)
    return [i for i, opt in enumerate(options)
            if normalise(_option(opt)) == value or (numeric and _same_cell(normalise(_option(opt)), value))]


def _error_options(options: list[str], error: str) -> list[int]:
    found = ERROR.search(error)
    return [i for i, opt in enumerate(options) if found and found.group(1) in opt] if found else []


def _judge(label: str, question: dict, value: str, matches: list[int], fails: list, warns: list):
    correct = question.get('correctOptionIndex')
    options = question.get('options', [])
    if not matches:
        warns.append(f'{label}: no option equals what the snippet gives ({_short(value)!r})')
    elif correct not in matches:
        m = matches[0]
        fails.append(f'{label}: the snippet gives {_short(value)!r} = option {m + 1} ({options[m]!r}), '
                     f'but the quiz marks option {correct + 1 if isinstance(correct, int) else correct}')
    elif len(matches) > 1:
        warns.append(f'{label}: options {", ".join(str(i + 1) for i in matches)} all equal the result')


def _short(text: str, n: int = 60) -> str:
    text = normalise(text)
    return text if len(text) <= n else text[:n] + '…'


def check_questions(content: str, labelled: list[tuple[str, dict]], timeout: int = 120) -> tuple[list, list]:
    """(fails, warns) for one lesson's questions. Raises EngineError when Python questions need
    the engine and it is missing."""
    fails, warns = [], []
    python_qs, sql_qs = [], []
    for label, question in labelled:
        parts = snippets(question.get('text', ''))
        k = kind(parts)
        if k == 'python':
            python_qs.append((label, question, '\n'.join(parts)))
        elif k == 'sql':
            sql_qs.append((label, question, next(p for p in parts if re.match(r'\s*(WITH|SELECT)\b', p, re.I))))
    seed = '\n'.join(html.unescape(s) for s in SEED.findall(content))
    for label, question, sql in sql_qs:
        rows, error = _run(seed, [], sql) if seed else (None, 'no seed')
        if error is None and rows and len(rows) == 2 and len(rows[1]) == 1:
            value = rows[1][0]
            _judge(label, question, value, matching(question.get('options', []), value), fails, warns)
    if python_qs:
        parts = python_parts(content)
        files = build_files(parts['dataset']) if parts['dataset'] is not None else {}
        steps = [{'id': f'run{i}', 'code': r['code'], 'fresh': False}
                 for i, r in enumerate(parts['runs'], 1) if not r['offline']]
        steps += [{'id': f'quiz{j}', 'code': code, 'fresh': False} for j, (_, _, code) in enumerate(python_qs)]
        try:
            results = {r['id']: r for r in run_job({'files': files, 'steps': steps, 'probe': []}, timeout)['results']}
        except EngineTimeout:
            return fails + [f'quiz snippets timed out after {timeout} s'], warns
        for j, (label, question, _) in enumerate(python_qs):
            got = results[f'quiz{j}']
            options = question.get('options', [])
            if got['error'] is not None:
                _judge(label, question, got['error'], _error_options(options, got['error']), fails, warns)
            else:
                _judge(label, question, got['stdout'], matching(options, got['stdout'], numeric=False), fails, warns)
    return fails, warns


def _lesson_for(question_id: str, lesson_ids: list[str]) -> str | None:
    hits = [lid for lid in lesson_ids if f'-{lid}-q' in question_id]
    return max(hits, key=len) if hits else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--course', required=True)
    ap.add_argument('--timeout', type=int, default=120)
    args = ap.parse_args(argv)
    try:
        course = json.loads(Path(args.course).read_text(encoding='utf-8'))
        lessons = course['lessons']
        ids = [ls['id'] for ls in lessons]
        assessment = (course.get('assessment') or {}).get('questions', [])
        total_fails = 0
        for ls in lessons:
            labelled = [(f'{ls["id"]} question {i}', q) for i, q in enumerate(ls.get('questions', []), 1)]
            labelled += [(f'{ls["id"]} assessment {q.get("id", i)}', q) for i, q in enumerate(assessment, 1)
                         if _lesson_for(q.get('id', ''), ids) == ls['id']]
            fails, warns = check_questions(ls.get('content', ''), labelled, args.timeout)
            total_fails += len(fails)
            for line in fails:
                print(f'FAIL {line}')
            for line in warns:
                print(f'WARN {line}')
    except (EngineError, OSError, ValueError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    print(f'QUIZ: {total_fails} wrong answer(s)')
    return 1 if total_fails else 0


if __name__ == '__main__':
    raise SystemExit(main())
