"""Fail if the website's copies of the lesson runners or the world generator drift.

The plugin's references/ folder is the source of truth; the website serves copies from
nerdit/future-vision/public/. A runner that differs runs lessons the checkers never saw, and a
generator that differs builds a lesson's CSV files with other rows than make_world_data.py.

Usage: python check_runtime_bundle.py <plugin_refs_dir> <site_public_dir>...
Exit 0 = identical (line endings aside), 1 = a copy differs or is missing.
"""
import hashlib
import sys
from pathlib import Path

FILES = ("nerdit-python-runner.js", "nerdit-plot-runner.js", "nerdit-sql-runner.js",
         "nerdit-excel-engine.js", "nerdit_world_gen.py")


def digest(d: Path) -> dict:
    """{file: sha256 of its text with LF line ends, or None when missing}."""
    out = {}
    for f in FILES:
        p = d / f
        # Git may check out CRLF on Windows; compare content, not line endings.
        out[f] = (hashlib.sha256(p.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest()
                  if p.is_file() else None)
    return out


def main(argv: list) -> int:
    ref, *sites = [Path(a) for a in argv]
    base = digest(ref)
    bad = 0
    for f, h in base.items():
        if h is None:
            print(f"MISSING {ref / f}")
            bad += 1
    for site in sites:
        for f, h in digest(site).items():
            if h is None:
                print(f"MISSING {site / f}")
                bad += 1
            elif base[f] is not None and h != base[f]:
                print(f"DRIFT {site / f} != {ref / f}")
                bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
