"""Check the Veo shot lists against the topic briefs, then write the prompt sheet and overlays.

    python check_prompts.py --dir <dir> [--overlays]

Reads <dir>/briefs.json (topic_briefs.py) and <dir>/prompts.json (written by the model).
On success writes <dir>/prompts.md: per topic, every shot in order, each Veo shot as one
self-contained prompt to paste into Veo / Flow, each overlay shot as the still to place and
the line to record over it. --overlays also renders <dir>/overlays/<key>-sNN.png (1280x720):
the lesson's exact code and output or table, which Veo cannot draw reliably.

prompts.json:
  {"language": "english" | "hinglish", "style": "<look shared by every Veo shot>",
   "skip": [{"key": "...", "reason": "..."}],
   "topics": [{"key": "<lessonId>-t<N>-video", "shots": [
       {"type": "veo", "cast": ["Neha"], "visual": "...", "camera": "...", "voiceover": "..."},
       {"type": "overlay", "show": "code1" | "table1", "highlight": ["line:2"], "voiceover": "..."}]}]}
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "nerdit-story-video" / "scripts"))
import lessonparts  # noqa: E402

SECONDS = 8                      # one Veo generation
MIN_SHOTS, MAX_SHOTS = 1, 12     # 8 s for a one-idea topic, up to about 1.5 minutes
FULL_CLIP = 3                    # from here a clip also shows the section's own example
MAX_VOICE_WORDS = 22             # what a calm narrator says in 8 seconds
MIN_VISUAL_WORDS = 15
MAX_OVERLAY_SHARE = 0.5          # Veo carries the explanation; overlays carry exact facts
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Veo garbles written words; exact text belongs on overlays.
ON_SCREEN_TEXT = re.compile(r'"[^"]{2,}"|“[^”]{2,}”|\b(?:text|caption|subtitles?|labelled|labeled|written|'
                            r'reads|spelling|code|letters|logo)\b', re.I)
VOICE = {"english": "a calm Indian English teacher's voice", "hinglish": "a calm Indian teacher speaking Hinglish"}


def load(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def part(brief: dict, ref: str) -> tuple[str, dict] | None:
    for kind, pool in (("code", brief["runs"]), ("table", brief["tables"])):
        for p in pool:
            if p["id"] == ref:
                return kind, p
    return None


def check_topic(brief: dict, shots: list[dict], world: dict | None = None) -> list[str]:
    tag = f"{brief['key']} ({brief['heading']})"
    errors = []
    if not MIN_SHOTS <= len(shots) <= MAX_SHOTS:
        errors.append(f"{tag}: {len(shots)} shot(s); give {MIN_SHOTS}-{MAX_SHOTS} (8 s each)")
    overlays = [s for s in shots if s.get("type") == "overlay"]
    if shots and len(overlays) / len(shots) > MAX_OVERLAY_SHARE:
        errors.append(f"{tag}: {len(overlays)} of {len(shots)} shots are overlays; let Veo shots explain")
    if shots and shots[0].get("type") != "veo":
        errors.append(f"{tag}: open with a Veo shot that sets up the question, not an overlay")
    shown = set()
    for n, s in enumerate(shots, 1):
        st = f"{tag} shot {n}"
        voice = (s.get("voiceover") or "").strip()
        if not voice:
            errors.append(f"{st}: voiceover is empty")
        elif len(voice.split()) > MAX_VOICE_WORDS:
            errors.append(f"{st}: voiceover is {len(voice.split())} words; keep to {MAX_VOICE_WORDS} for 8 seconds")
        for num in NUMBER.findall(voice):
            if num not in brief["numbers"]:
                errors.append(f"{st}: number {num} is not in the lesson section")
        if s.get("type") == "veo":
            visual = (s.get("visual") or "").strip()
            if len(visual.split()) < MIN_VISUAL_WORDS:
                errors.append(f"{st}: describe the scene in at least {MIN_VISUAL_WORDS} words (who, where, action)")
            m = ON_SCREEN_TEXT.search(visual)
            if m:
                errors.append(f"{st}: visual asks Veo for written words ({m.group(0)!r}); put exact text on an overlay")
            for num in NUMBER.findall(visual):
                if num not in brief["numbers"]:
                    errors.append(f"{st}: visual uses number {num}, which the lesson section does not")
            if world:
                names = {c["name"] for c in world["cast"]}
                cast = s.get("cast")
                if not isinstance(cast, list):
                    errors.append(f"{st}: list the cast in the shot (names from the world; [] for no one)")
                else:
                    for who in cast:
                        if who not in names:
                            errors.append(f"{st}: {who!r} is not in the world's cast ({', '.join(sorted(names))})")
                if world.get("owner") and world["owner"].split()[0].lower() in visual.lower():
                    errors.append(f"{st}: the owner is a real person; mention them in the voiceover, never on screen")
            if not (s.get("camera") or "").strip():
                errors.append(f"{st}: name the camera move (slow push-in, static wide, pan left ...)")
        elif s.get("type") == "overlay":
            found = part(brief, s.get("show") or "")
            if not found:
                ids = [p["id"] for p in brief["runs"] + brief["tables"]]
                errors.append(f"{st}: show {s.get('show')!r} is not in this section ({', '.join(ids) or 'none'})")
                continue
            kind, p = found
            shown.add(p["id"])
            errors += [f"{st}: {e}" for e in lessonparts.highlight_problems(kind, p, s.get("highlight"))]
        else:
            errors.append(f"{st}: type must be 'veo' or 'overlay'")
    if len(shots) >= FULL_CLIP and (brief["runs"] or brief["tables"]) and not shown:
        errors.append(f"{tag}: show at least one of the section's own examples on an overlay "
                      f"({', '.join(p['id'] for p in brief['runs'] + brief['tables'])})")
    spoken = " ".join(s.get("voiceover") or "" for s in shots).lower()
    for term in brief["terms"]:
        if term.lower() not in spoken:
            errors.append(f"{tag}: key term {term!r} from the page is never spoken")
    return errors


def check(briefs: dict, prompts: dict) -> list[str]:
    errors = []
    if prompts.get("language") not in VOICE:
        errors.append(f"language must be one of {', '.join(VOICE)}")
    if len((prompts.get("style") or "").split()) < 12:
        errors.append("style: describe the shared look in at least 12 words (setting, light, palette, realism)")
    skipped = {k.get("key") for k in prompts.get("skip") or [] if (k.get("reason") or "").strip()}
    written = {t.get("key"): t.get("shots") or [] for t in prompts.get("topics") or []}
    known = {b["key"] for b in briefs["topics"]}
    for key in written:
        if key not in known:
            errors.append(f"{key}: no such topic in briefs.json")
    for b in briefs["topics"]:
        if b["key"] in written:
            errors += check_topic(b, written[b["key"]], briefs.get("world"))
        elif b["key"] not in skipped:
            errors.append(f"{b['key']} ({b['heading']}): no shots; write them or list it in skip with a reason")
    return errors


def veo_prompt(prompts: dict, shot: dict, world: dict | None = None) -> str:
    voice = VOICE[prompts["language"]]
    people = ""
    if world:
        # The same words every time, so Veo draws the same person in every shot and course.
        cast = {c["name"]: c for c in world["cast"]}
        people = f"Setting: {world['setting']}\n" + "".join(
            f"{who} ({cast[who]['role']}): {cast[who]['visual']}.\n" for who in shot.get("cast") or [])
    return (f"{prompts['style'].strip()}\n"
            f"{people}"
            f"Scene: {shot['visual'].strip()}\n"
            f"Camera: {shot['camera'].strip()}.\n"
            f"Audio: voiceover in {voice}, unhurried and clear: \"{shot['voiceover'].strip()}\" "
            f"Soft room tone, no music.\n"
            f"No on-screen text, no subtitles, no captions, no logos, no watermarks. "
            f"{SECONDS} seconds, 16:9, 1080p.")


def sheet(briefs: dict, prompts: dict) -> str:
    by_key = {b["key"]: b for b in briefs["topics"]}
    lines = [f"# Veo prompts — {briefs['course']}", "",
             "Paste each Veo prompt into Veo / Flow as its own 8-second generation. Place overlay stills from "
             "`overlays/` where marked and record their voiceover line (or generate it with any TTS). Join the "
             "shots in order, export one MP4 per topic named by its slot key, upload it to YouTube (Unlisted) and "
             "paste the link into the admin slot with the same key.", ""]
    world = briefs.get("world")
    if world:
        lines += ["## Character references (make once, reuse in every course of this world)", "",
                  "Generate each portrait once (Flow image, Imagen or any image tool), save it as `cast/<Name>.png`, "
                  "and attach it as an ingredient to every shot that lists that character.", ""]
        for c in world["cast"]:
            lines += [f"### {c['name']} — {c['role']}", "", "```text",
                      f"Photorealistic waist-up portrait of {c['visual']}. Standing in {world['setting']} "
                      f"Facing the camera, friendly neutral expression, soft daylight, plain softly blurred background, "
                      f"16:9. No text, no logos.", "```", ""]
    for t in prompts["topics"]:
        b = by_key[t["key"]]
        lines += [f"## {b['lessonTitle']} — {b['topic']}. {b['heading']}", "",
                  f"Slot key: `{b['key']}` · {len(t['shots'])} shots · about {len(t['shots']) * SECONDS} s", ""]
        for n, s in enumerate(t["shots"], 1):
            if s["type"] == "veo":
                ref = f" · attach: {', '.join(f'cast/{w}.png' for w in s.get('cast') or [])}" if s.get("cast") else ""
                lines += [f"### Shot {n} · Veo{ref}", "", "```text", veo_prompt(prompts, s, briefs.get("world")), "```", ""]
            else:
                kind, p = part(b, s["show"])
                lines += [f"### Shot {n} · Overlay ({kind})", "",
                          f"Still: `overlays/{b['key']}-s{n:02d}.png` (the lesson's own {kind}"
                          + (f", highlight {', '.join(s['highlight'])}" if s.get("highlight") else "") + ")", "",
                          f"Voiceover ({SECONDS} s): \"{s['voiceover'].strip()}\"", ""]
    for k in prompts.get("skip") or []:
        lines += [f"Skipped `{k['key']}`: {k['reason']}", ""]
    return "\n".join(lines)


def render_overlays(briefs: dict, prompts: dict, out: Path) -> int:
    """The lesson's exact code and output, or table, as 1280x720 stills in the lesson's styles."""
    import render
    import stage
    from playwright.sync_api import sync_playwright
    by_key = {b["key"]: b for b in briefs["topics"]}
    css = stage.lesson_css()
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for t in prompts["topics"]:
        for n, s in enumerate(t["shots"], 1):
            if s["type"] == "overlay":
                kind, p = part(by_key[t["key"]], s["show"])
                svg = (lessonparts.code_svg(p, s.get("highlight")) if kind == "code"
                       else lessonparts.table_svg(p, s.get("highlight")))
                # The 4:3 drawing fits the 16:9 frame by height, centred on the video's background.
                doc = ("<!doctype html><html><head><meta charset='utf-8'><style>" + css + "</style><style>"
                       "html,body{margin:0;width:1280px;height:720px;overflow:hidden;background:#EEF3F9}"
                       # The wrapper only supplies the lesson's colour tokens, not its card.
                       ".nerdit-wrapper{background:none!important;box-shadow:none!important;border:0!important;"
                       "padding:0!important;margin:0!important;max-width:none!important}"
                       ".frame{position:absolute;left:50%;top:24px;transform:translateX(-50%);width:896px;"
                       "height:672px;background:#fff;border-radius:18px;box-shadow:0 6px 24px rgba(11,31,58,.12)}"
                       ".frame svg{display:block;width:100%;height:100%}</style></head><body>"
                       "<div class='nerdit-wrapper'><div class='frame'>" + svg + "</div></div></body></html>")
                jobs.append((out / f"{t['key']}-s{n:02d}.png", doc))
    exe = render.chromium()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        for path, doc in jobs:
            page.set_content(doc)
            page.evaluate("document.querySelector('svg').classList.add('na-play');"
                          "document.getAnimations().forEach(a => a.finish())")
            page.screenshot(path=str(path))
        browser.close()
    return len(jobs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, type=Path)
    ap.add_argument("--overlays", action="store_true", help="also render the overlay stills")
    a = ap.parse_args(argv)
    briefs, prompts = load(a.dir / "briefs.json"), load(a.dir / "prompts.json")
    errors = check(briefs, prompts)
    for e in errors:
        print("ERROR", e)
    if errors:
        print(f"{len(errors)} problem(s); nothing written")
        return 1
    (a.dir / "prompts.md").write_text(sheet(briefs, prompts), encoding="utf-8")
    shots = sum(len(t["shots"]) for t in prompts["topics"])
    print(f"prompts OK: {len(prompts['topics'])} topic(s), {shots} shot(s) -> {a.dir / 'prompts.md'}")
    if a.overlays:
        print(f"{render_overlays(briefs, prompts, a.dir / 'overlays')} overlay still(s) -> {a.dir / 'overlays'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
