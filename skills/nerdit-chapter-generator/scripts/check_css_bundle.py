"""Fail if the three lesson-css bundles drift or css10 is missing.
Usage: python check_css_bundle.py <plugin_refs_dir> <app_lesson_css_dir>..."""
import hashlib, sys
from pathlib import Path
FILES = ("css8.css", "css9-simple.css", "css10-brand.css")

def digest(d: Path) -> dict[str, str]:
    out = {}
    for f in FILES:
        p = d / f
        if not p.exists():
            raise SystemExit(f"missing {p}")
        # Git may check out CRLF on Windows; compare CSS content, not line endings.
        out[f] = hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    return out

def main(argv: list[str]) -> int:
    ref, *apps = [Path(a) for a in argv]
    base = digest(ref)
    bad = [(a, f) for a in apps for f, h in digest(a).items() if h != base[f]]
    for a, f in bad:
        print(f"DRIFT {a / f} != {ref / f}")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
