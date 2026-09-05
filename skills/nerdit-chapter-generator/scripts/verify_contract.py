#!/usr/bin/env python3
"""Preflight: does the INSTALLED plugin match this repo's source?

Generation runs from the installed plugin cache, not from the repo checkout. When the
two diverge, lessons are written against the installed contract while being reviewed
against the repo one — every lesson "fails" review despite being correct, and the
temptation is to fix content that was never broken.

Observed 2026-09-05: repo CORE.md 861 lines, installed copy 448. Fixes to the practice
markup and the depth-cap rule existed only in the repo, so a whole 4-lesson run came out
against the superseded contract.

Run this BEFORE generating a chapter. Exit 0 = in sync, 1 = drift (details printed),
2 = could not locate one of the trees.

    python verify_contract.py --repo <repo>/nerdit-plugin-json-generator-main
    python verify_contract.py --repo ... --installed <plugin cache dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

# Files whose divergence changes what a generated lesson looks like.
TRACKED = [
    "skills/nerdit-chapter-generator/references/CORE.md",
    "skills/nerdit-chapter-generator/references/css8.css",
    "skills/nerdit-chapter-generator/references/css9-simple.css",
    "agents/nerdit-lesson-writer.md",
    "agents/nerdit-qa-validator.md",
]

# The whole plugin cache. Its layout is
#     <cache>/<marketplace>/<plugin name>/<version>/
# and NONE of those three segments is stable: the plugin was renamed at 3.0.0
# (nerdit_try_plugin -> nerdit_content_creator), and moving it to a shared catalog
# moved it from cache/nerdit-plugin/ to cache/fv-analysis-marketplace/. Assuming any
# of them means the check silently inspects the wrong install - which it did, on the
# very run that installed 3.0.0. So the tree is searched and the manifest is read.
DEFAULT_CACHE_ROOT = os.path.expanduser("~/.claude/plugins/cache")

# Matched against plugin.json `name`, so a rename inside the family still resolves.
PLUGIN_NAME_HINT = "nerdit"


def _version_key(v: str):
    return [int(c) if c.isdigit() else -1 for c in v.split(".")]


def newest_installed(cache_root: str) -> str | None:
    """Newest installed version of the nerdit generator, wherever it is cached.

    Walks <cache>/<marketplace>/<plugin>/<version>/ and keeps any directory whose
    plugin.json names a nerdit plugin. The highest version wins.
    """
    if not os.path.isdir(cache_root):
        return None

    candidates: list[tuple[list[int], str]] = []
    for marketplace in os.listdir(cache_root):
        mpath = os.path.join(cache_root, marketplace)
        if not os.path.isdir(mpath):
            continue
        for plugin in os.listdir(mpath):
            ppath = os.path.join(mpath, plugin)
            if not os.path.isdir(ppath):
                continue
            for version in os.listdir(ppath):
                vpath = os.path.join(ppath, version)
                manifest = os.path.join(vpath, ".claude-plugin", "plugin.json")
                if not os.path.isfile(manifest):
                    continue
                try:
                    name = json.load(open(manifest, encoding="utf-8")).get("name", "")
                except (OSError, ValueError):
                    continue
                if PLUGIN_NAME_HINT in name.lower():
                    candidates.append((_version_key(version), vpath))

    if not candidates:
        return None
    return sorted(candidates)[-1][1]


def digest(path: str) -> tuple[str, int] | None:
    if not os.path.isfile(path):
        return None
    data = open(path, "rb").read()
    return hashlib.sha256(data).hexdigest(), data.count(b"\n") + 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="repo copy of the plugin")
    ap.add_argument("--installed", help="installed plugin dir (default: newest in the cache)")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print(f"ERROR: repo path not found: {repo}", file=sys.stderr)
        return 2

    installed = args.installed or newest_installed(DEFAULT_CACHE_ROOT)
    if not installed or not os.path.isdir(installed):
        print(
            "ERROR: installed plugin not found. Pass --installed explicitly.\n"
            f"  looked under: {DEFAULT_CACHE_ROOT}",
            file=sys.stderr,
        )
        return 2

    print(f"repo      : {repo}")
    print(f"installed : {installed}\n")

    drift, missing = [], []
    for rel in TRACKED:
        a, b = digest(os.path.join(repo, rel)), digest(os.path.join(installed, rel))
        if a is None or b is None:
            missing.append((rel, a is None, b is None))
            continue
        if a[0] != b[0]:
            drift.append((rel, a[1], b[1]))
        else:
            print(f"  same   {rel}")

    for rel, no_repo, no_inst in missing:
        where = "repo" if no_repo else "installed"
        print(f"  MISSING in {where}: {rel}")
    for rel, repo_lines, inst_lines in drift:
        print(f"  DRIFT  {rel}  (repo {repo_lines} lines, installed {inst_lines})")

    if drift or missing:
        # Plain ASCII: this prints to a cp1252 console on Windows, where an em-dash
        # comes out as a replacement character.
        print(
            "\nCONTRACT DRIFT - the generator will follow the INSTALLED files above, not "
            "the repo.\nEither reinstall the plugin from the repo first, or state clearly "
            "that the\nchapter was generated against the installed contract and review it "
            "on those terms."
        )
        return 1

    print("\nIn sync - generated output can be reviewed against the repo contract.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
