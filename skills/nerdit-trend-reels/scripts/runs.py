"""Run folders, the Flow credit rule and the ready gate for Trend Reels.

Every run lives in <home>/<YYYY-MM-DD>-<kind>-<slug>/ and writes one file per step, so a run can resume.
checks.json collects each checker's verdict plus the sha256 of the reel they checked; `ready` refuses an
upload unless all of it holds for the reel on disk now.

CLI:
  runs.py new <daily|weekly> <slug>     print the new run folder
  runs.py credits <N> [--reroll]        print the credits message; exit 1 when the spend is not allowed
  runs.py ready <run>                   print what is missing; exit 1 when anything is
  runs.py recent                        print the last 3 chosen courses and links (JSON)
"""
import hashlib
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

KINDS = ("daily", "weekly")
SECTIONS = ("script", "transcript", "captions")
REEL_COST = 60
RESET_DAY = 8
REEL_DAYS = (0, 2, 4, 6)   # Monday, Wednesday, Friday, Sunday


def home() -> Path:
    base = os.environ.get("NERDIT_SOCIAL_HOME") or str(Path.home() / ".nerdit-social")
    return Path(base) / "trend-reels"


def new_run(kind: str, slug: str, today: date) -> Path:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, not {kind!r}")
    run = home() / f"{today.isoformat()}-{kind}-{slug}"
    (run / "clips").mkdir(parents=True, exist_ok=True)
    return run


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def recent_choices(n: int = 3) -> list[dict]:
    out = []
    runs = sorted((p for p in home().glob("*/ideas.json")), key=lambda p: p.parent.name, reverse=True)
    for path in runs:
        ideas = _read(path)
        chosen = ideas.get("chosen")
        items = ideas.get("ideas") or []
        if isinstance(chosen, int) and 0 <= chosen < len(items):
            out.append({"course_id": items[chosen].get("course_id"), "links": items[chosen].get("links", [])})
        if len(out) == n:
            break
    return out


def next_reset(today: date, reset_day: int = RESET_DAY) -> date:
    this_month = today.replace(day=reset_day)
    if today < this_month:
        return this_month
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return date(year, month, reset_day)


def reels_planned(today: date, reset: date) -> int:
    days = (reset - today).days
    return sum((today + timedelta(d)).weekday() in REEL_DAYS for d in range(1, days))


def may_spend(credits_left: int, today: date, reroll: bool = False, cost: int = REEL_COST) -> tuple[bool, str]:
    reset = next_reset(today)
    msg = f"credits left: {credits_left}, enough for {credits_left // cost} more Reels before {reset.day} {reset:%b}"
    ok = credits_left >= cost
    if reroll:
        ok = ok and credits_left - cost >= cost * reels_planned(today, reset)
    return ok, msg


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_checks(run: Path, key: str, value) -> None:
    checks = _read(run / "checks.json")
    checks[key] = value
    (run / "checks.json").write_text(json.dumps(checks, indent=1), encoding="utf-8")


def record_check(run: Path, section: str, errors: list[str]) -> None:
    _write_checks(Path(run), section, {"ok": not errors, "errors": errors})


def record_reel(run: Path) -> None:
    _write_checks(Path(run), "reel_sha256", sha256(Path(run) / "reel.mp4"))


def ready(run: Path) -> list[str]:
    run = Path(run)
    reel = run / "reel.mp4"
    if not reel.exists():
        return ["reel.mp4 is missing"]
    checks = _read(run / "checks.json")
    errors = []
    for section in SECTIONS:
        verdict = checks.get(section)
        if not verdict:
            errors.append(f"{section} check missing")
        elif not verdict.get("ok"):
            errors.append(f"{section} check failed: {'; '.join(verdict.get('errors', []))}")
    if not checks.get("reel_sha256"):
        errors.append("compose did not record reel.mp4")
    elif checks["reel_sha256"] != sha256(reel):
        errors.append("reel.mp4 changed after the checks")
    ideas = _read(run / "ideas.json")
    if not isinstance(ideas.get("chosen"), int):
        errors.append("ideas.json names no chosen idea")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[0] == "new":
        print(new_run(argv[1], argv[2], date.today()))
        return 0
    if len(argv) >= 2 and argv[0] == "credits":
        ok, msg = may_spend(int(argv[1]), date.today(), reroll="--reroll" in argv)
        print(msg if ok else f"NOT ALLOWED: {msg}")
        return 0 if ok else 1
    if len(argv) == 2 and argv[0] == "ready":
        errors = ready(Path(argv[1]))
        print("\n".join(errors) if errors else "ready")
        return 1 if errors else 0
    if argv[:1] == ["recent"]:
        print(json.dumps(recent_choices(3), indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
