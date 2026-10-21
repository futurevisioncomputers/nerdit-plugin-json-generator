"""Fetch B-roll clips from Pexels for every `broll` scene in plan.json.

    python broll.py --images-dir <images> [--refresh]

Writes <images>/video/broll/s<n>.mp4 and broll/credits.json (videographer and Pexels page per clip,
for the YouTube description). Key in the PEXELS_API_KEY environment variable, never in the plan.
Pexels videos are free to use, commercial use included; credit is courteous, not required.
"""
import argparse, json, os, sys, urllib.parse, urllib.request
from pathlib import Path

SEARCH = "https://api.pexels.com/videos/search?{q}"
MIN_WIDTH, MAX_WIDTH = 1280, 1920
MIN_SECONDS = 5


def pexels_key() -> str:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        raise SystemExit("set PEXELS_API_KEY in your user environment, then restart the terminal")
    return key


def search(query: str, key: str, opener=urllib.request.urlopen) -> list[dict]:
    q = urllib.parse.urlencode({"query": query, "orientation": "landscape", "size": "medium", "per_page": 10})
    req = urllib.request.Request(SEARCH.format(q=q), headers={"Authorization": key, "User-Agent": "nerdit-story-video"})
    with opener(req, timeout=60) as r:
        return json.loads(r.read()).get("videos", [])


def pick(videos: list[dict]) -> tuple[dict, dict] | None:
    """First video at least MIN_SECONDS long with an mp4 file 1280-1920 px wide (smallest such file)."""
    for v in videos:
        if v.get("duration", 0) < MIN_SECONDS:
            continue
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"
                 and MIN_WIDTH <= (f.get("width") or 0) <= MAX_WIDTH]
        if files:
            return v, min(files, key=lambda f: f["width"])
    return None


def fetch(images_dir: Path, refresh: bool = False, opener=urllib.request.urlopen, key: str | None = None) -> list[str]:
    plan = json.loads((images_dir / "video" / "plan.json").read_text(encoding="utf-8-sig"))
    out_dir = images_dir / "video" / "broll"
    out_dir.mkdir(parents=True, exist_ok=True)
    credits_path = out_dir / "credits.json"
    credits = json.loads(credits_path.read_text(encoding="utf-8")) if credits_path.is_file() else {}
    done = []
    for n, s in enumerate(plan["scenes"], 1):
        if s.get("kind") != "broll":
            continue
        clip = out_dir / f"s{n}.mp4"
        if clip.is_file() and not refresh and credits.get(f"s{n}", {}).get("query") == s["query"]:
            continue
        found = pick(search(s["query"], key or pexels_key(), opener))
        if not found:
            raise SystemExit(f"scene {n}: no landscape Pexels clip for {s['query']!r}; try other words")
        video, file = found
        with opener(urllib.request.Request(file["link"], headers={"User-Agent": "nerdit-story-video"}), timeout=120) as r:
            clip.write_bytes(r.read())
        credits[f"s{n}"] = {"query": s["query"], "by": video.get("user", {}).get("name", ""),
                            "page": video.get("url", ""), "seconds": video.get("duration")}
        done.append(f"s{n}")
    credits_path.write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding="utf-8")
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images-dir", required=True, type=Path)
    ap.add_argument("--refresh", action="store_true", help="download again even if a clip exists")
    a = ap.parse_args(argv)
    done = fetch(a.images_dir, a.refresh)
    print(f"fetched {len(done)} clip(s): {', '.join(done) or 'none needed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
