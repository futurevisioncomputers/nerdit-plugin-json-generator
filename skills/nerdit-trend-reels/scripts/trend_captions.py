"""Check a Trend Reel's captions with the social-posts rules, plus source credit, and fill in the links.

captions.json (written by Claude): {"instagram", "facebook", "youtube", "pinterest"(optional)}; `{link}` marks the
course link; YouTube is the title line, a blank line, then the description.

CLI: trend_captions.py <run>   writes captions_filled.json, records checks.json["captions"]; exit 1 on errors
"""
import json
import sys
from pathlib import Path

# The caption rules live with the social-posts skill (one checker for every post type); reuse, never copy.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "nerdit-social-posts" / "scripts"))
from captions import caption_errors, fill_links  # noqa: E402

from runs import record_check  # noqa: E402

REQUIRED = ("instagram", "facebook", "youtube")
OPTIONAL = ("pinterest",)
BANNED = ("free certificate",)


def fill(captions: dict, script: dict, item: dict) -> dict:
    url = script["course"]["url"]
    return {p: fill_links(text, url, p, item) for p, text in captions.items() if p in REQUIRED + OPTIONAL}


def trend_caption_errors(captions: dict, script: dict, kept: list[dict], item: dict) -> list[str]:
    errors = [f"{p}: caption is missing" for p in REQUIRED if not captions.get(p, "").strip()]
    card = script["card"]
    evidence = " ".join([*card["facts"], *(k.get("headline", "") + " " + " ".join(k.get("evidence", [])) for k in kept)])
    for p, text in fill(captions, script, item).items():
        if not text.strip():
            continue
        errors += caption_errors(p, "reel", text, evidence, item, script["course"]["url"])
        if "Source:" not in text:
            errors.append(f"{p}: credit the sources ('Source: ...')")
        errors += [f"{p}: name the source {s}" for s in card["sources"] if s not in text]
        errors += [f"{p}: banned phrase '{b}'" for b in BANNED if b in text.lower()]
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    run = Path(argv[0])
    read = lambda name: json.loads((run / name).read_text(encoding="utf-8"))  # noqa: E731
    captions, script, kept = read("captions.json"), read("script.json"), read("checked.json").get("kept", [])
    item = {"id": run.name, "date": run.name[:10], "campaign": "trend"}
    errors = trend_caption_errors(captions, script, kept, item)
    (run / "captions_filled.json").write_text(json.dumps(fill(captions, script, item), indent=1, ensure_ascii=False),
                                              encoding="utf-8")
    record_check(run, "captions", errors)
    for e in errors or ["captions ok"]:
        print(e.encode("ascii", "replace").decode())   # the Windows console is cp1252
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
