"""Step 3 by Gemini: the two-outlet news check through the Antigravity CLI (`agy`), written to checked.json.

One prompt (work-related candidates from trends.json, the live courses Claude saved in courses.json, the keep rules
from references/editorial.md) goes to `agy -p` once, sandboxed, in a fresh empty folder. Only the JSON block of the
answer is kept; checked_check.py then judges it like any other checked.json. On any failure nothing is written and
Claude does step 3 itself.

CLI: gemini_check.py <run> [--model M] [--timeout S]   writes gemini-raw.txt (+ checked.json on success); exit 1 on failure
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

REFERENCES = Path(__file__).resolve().parents[1] / "references"
DEFAULT_MODEL = "gemini-4-hydrogen-medium"
DEFAULT_TIMEOUT = 360
MAX_PROMPT = 30000          # one argv string; Windows caps a command line at 32,767 characters
NEWS_FEEDS = ("gnews", "hn")
WORK = re.compile(r"\b(?:work\w*|jobs?|hir\w*|layoffs?|laid off|cuts?|skills?|careers?|salar\w*|staff\w*|employ\w*|"
                  r"workforce|recruit\w*|automation|unemploy\w*|freelanc\w*|interns?\w*)\b", re.I)
JSON_BLOCK = re.compile(r"```json\s*(.*?)```", re.S)


def candidates(rows: list[dict], limit: int = 40) -> list[dict]:
    seen, out = set(), []
    for row in rows:
        headline = (row.get("headline") or "").strip()
        key = headline.lower()
        if not row.get("feed", "").startswith(NEWS_FEEDS) or not WORK.search(headline) or key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) == limit:
            break
    return out


def _keep_rules() -> str:
    text = (REFERENCES / "editorial.md").read_text(encoding="utf-8")
    start = text.index("## Keep a story only if")
    return text[start:text.index("\n## ", start + 1)].strip()


def build_prompt(run: Path) -> str:
    run = Path(run)
    trends = json.loads((run / "trends.json").read_text(encoding="utf-8"))
    courses = json.loads((run / "courses.json").read_text(encoding="utf-8"))
    window = int(trends.get("days") or 2)
    today = date.fromisoformat(run.name[:10])
    rows = candidates(trends.get("rows") or [])
    template = (REFERENCES / "gemini-check-prompt.md").read_text(encoding="utf-8")

    def fill(rows_in: list[dict]) -> str:
        lines = "\n".join(f"- {r.get('headline')} | {r.get('outlet')} | {r.get('published')} | {r.get('feed')}"
                          for r in rows_in)
        course_lines = "\n".join(f"- {c.get('id')} | {c.get('title')}" for c in courses)
        return (template.replace("{run_date}", str(today)).replace("{window_days}", str(window))
                .replace("{first_date}", str(today - timedelta(days=window))).replace("{rules}", _keep_rules())
                .replace("{candidates}", lines or "- (none)").replace("{courses}", course_lines))

    prompt = fill(rows)
    while len(prompt) >= MAX_PROMPT and rows:     # trim the weakest (latest-listed) candidates to fit one argv
        rows = rows[:-5]
        prompt = fill(rows)
    return prompt


def parse_answer(text: str) -> dict:
    blocks = JSON_BLOCK.findall(text)
    raw = blocks[-1] if blocks else text[text.find("{"):text.rfind("}") + 1]
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise ValueError(f"no JSON in the answer ({e})") from None
    if not isinstance(data, dict) or not isinstance(data.get("kept"), list):
        raise ValueError("the answer has no 'kept' list")
    return data


def run_agy(prompt: str, model: str, timeout: int, runner=subprocess.run) -> str:
    folder = tempfile.mkdtemp(prefix="nerdit-agy-")     # empty: nothing for agy to read or change
    try:
        argv = ["agy", "-p", prompt, "--model", model, "--print-timeout", f"{timeout}s", "--sandbox"]
        result = runner(argv, cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=timeout + 60)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if result.returncode != 0:
        raise RuntimeError(f"agy exited {result.returncode}: {(result.stderr or '')[-300:]}")
    return result.stdout or ""


def _say(line: str) -> None:
    print(line.encode("ascii", "replace").decode())   # the Windows console is cp1252


def main(argv: list[str], runner=subprocess.run) -> int:
    args, model, timeout = [], DEFAULT_MODEL, DEFAULT_TIMEOUT
    it = iter(argv)
    for a in it:
        if a == "--model":
            model = next(it)
        elif a == "--timeout":
            timeout = int(next(it))
        else:
            args.append(a)
    if len(args) != 1:
        _say(__doc__)
        return 2
    run = Path(args[0])
    if not (run / "courses.json").exists():
        _say("courses.json is missing: save the live courses from catalogue_status first")
        return 1
    raw = run / "gemini-raw.txt"
    try:
        answer = run_agy(build_prompt(run), model, timeout, runner)
    except FileNotFoundError:
        problem = "agy is not installed or not on PATH"
    except subprocess.TimeoutExpired:
        problem = f"agy timed out after {timeout} s"
    except RuntimeError as e:
        problem = str(e)
    else:
        raw.write_text(answer, encoding="utf-8")
        try:
            checked = parse_answer(answer)
        except ValueError as e:
            _say(f"Gemini check failed: {e}; see gemini-raw.txt. Do step 3 yourself.")
            return 1
        checked["checked_by"] = f"gemini:{model}"
        (run / "checked.json").write_text(json.dumps(checked, indent=1, ensure_ascii=False), encoding="utf-8")
        _say(f"checked.json written by gemini:{model}: {len(checked['kept'])} kept, "
             f"{len(checked.get('dropped') or [])} dropped. Run checked_check.py next.")
        return 0
    raw.write_text(problem, encoding="utf-8")
    _say(f"Gemini check failed: {problem}. Do step 3 yourself.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
