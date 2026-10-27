#!/usr/bin/env python3
"""Write the one rule file a lesson writer reads: CORE.md and figures.md cut to the course's preset.

    python rules_pack.py --preset code [--project] --out <workdir>

Writes <workdir>/_rules/rules-<preset>[-project].md and one file per figure template in
<workdir>/_rules/figures/<nn>-<name>.md. The orchestrator names the pack on the writer prompt's
RULES: line, so every writer reads ~60% of the two files instead of all of them.

A section is cut when the line straight under its heading is a pack tag:
    <!-- pack: code, spreadsheet -->   only for these presets
    <!-- pack: project -->             only for a capstone chapter (focus: "project")
    <!-- pack: why -->                 rationale only: the rule it explains is stated elsewhere
A section runs to the next heading of the same or a higher level; headings inside ``` fences
do not count. Section numbers are kept, so "CORE.md §7" still points to the same rule.
Figure templates (## <n> · <name>) leave the pack: it lists them, and the writer reads only the
one it draws. Exit 0 = written, 2 = unknown preset or unreadable file. Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REFS = Path(__file__).resolve().parent.parent / "references"
CORE = REFS / "CORE.md"
FIGURES = REFS / "figures.md"
PRESETS = ("code", "spreadsheet", "visual", "quantitative", "conversational")
HEADING = re.compile(r"^(#{1,6}) ")
TAG = re.compile(r"^<!--\s*pack:\s*([a-z ,-]+?)\s*-->\s*$")
TEMPLATE = re.compile(r"^## (\d+) · ([^—\n]+)")


def _sections(text: str) -> list[tuple[int, list[str]]]:
    """(heading level, lines) blocks; level 0 is the text before the first heading."""
    blocks, fence = [(0, [])], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else HEADING.match(line)
        if m:
            blocks.append((len(m.group(1)), [line]))
        else:
            blocks[-1][1].append(line)
    return blocks


def _keep(tag: set[str], preset: str, project: bool) -> bool:
    if "why" in tag:
        return False
    if "project" in tag:
        return project
    return preset in tag


def core_pack(text: str, preset: str, project: bool) -> str:
    out, cut_below = [], None
    for level, lines in _sections(text):
        if cut_below is not None and level > cut_below:
            continue                                  # inside a cut section
        cut_below = None
        tag = TAG.match(lines[1]) if level and len(lines) > 1 else None
        if tag:
            if not _keep({t.strip() for t in tag.group(1).split(",")}, preset, project):
                cut_below = level
                continue
            lines = [lines[0]] + lines[2:]
        out += lines
    return "\n".join(out).rstrip() + "\n"


def split_figures(text: str) -> tuple[str, list[tuple[str, str]]]:
    """(the rules without templates, [(file stem, template text)])."""
    rules, templates = [], []
    for level, lines in _sections(text):
        m = TEMPLATE.match(lines[0]) if level == 2 else None
        if m:
            stem = f"{int(m.group(1)):02d}-" + re.sub(r"[^a-z0-9]+", "-", m.group(2).lower()).strip("-")
            templates.append((stem, "\n".join(lines).rstrip() + "\n"))
        else:
            rules += lines
    return "\n".join(rules).rstrip() + "\n", templates


def build(workdir: Path, preset: str, project: bool, core: str | None = None, figures: str | None = None) -> Path:
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; one of {', '.join(PRESETS)}")
    core = CORE.read_text(encoding="utf-8") if core is None else core
    figures = FIGURES.read_text(encoding="utf-8") if figures is None else figures
    folder = Path(workdir) / "_rules"
    (folder / "figures").mkdir(parents=True, exist_ok=True)
    rules, templates = split_figures(figures)
    for stem, body in templates:
        (folder / "figures" / f"{stem}.md").write_text(body, encoding="utf-8")
    index = "\n".join(f"- {body.splitlines()[0][3:]} → `{(folder / 'figures' / f'{stem}.md').as_posix()}`"
                      for stem, body in templates)
    head = (f"<!-- Rule pack: CORE.md + figures.md for the {preset} preset"
            f"{' (capstone chapter)' if project else ''}. Section numbers are CORE.md's and figures.md's. -->\n\n")
    text = (head + core_pack(core, preset, project) + "\n---\n\n" + rules
            + "\n## Figure templates — read only the one you draw\n\n"
              "`figures.md §N` means the template file below. Copy its markup and swap the labels.\n\n"
            + index + "\n")
    path = folder / f"rules-{preset}{'-project' if project else ''}.md"
    path.write_text(text, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", required=True)
    ap.add_argument("--project", action="store_true", help="the capstone chapter: keep CORE.md §8b")
    ap.add_argument("--out", required=True, help="the course work folder")
    args = ap.parse_args(argv)
    try:
        path = build(Path(args.out), args.preset, args.project)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    size = len(path.read_text(encoding="utf-8"))
    full = len(CORE.read_text(encoding="utf-8")) + len(FIGURES.read_text(encoding="utf-8"))
    print(f"wrote {path} ({size:,} chars; CORE.md + figures.md are {full:,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
