"""Turn Dev's Flow clip(s) into the finished 1080x1920 Reel: news card, word captions and the course end card.

Layout from the spike the owner approved (2026-11-24): cards sit over the chest, clear of the face; captions are
centred in a white pill of one fixed height; no AI label on screen (disclosure goes through platform flags).

CLI: compose.py <run>   reads clips/*.mp4, transcript.json, script.json; writes reel.mp4 and its sha256
"""
import json
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from runs import record_reel

FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1080, 1920
INK, TEAL, ORANGE, MUTED = "#0B1F3A", "#0e7490", "#f97316", "#33585f"
FONTS = "C:/Windows/Fonts/"
LOGO = Path(__file__).resolve().parents[2] / "nerdit-social-posts" / "assets" / "nerdit-logo.png"
HIGHLIGHT = {"pwc", "ai", "free", "nerdit"}
CARD_Y, END_Y, CAPTION_Y = 1020, 960, H - 300
END_SECONDS = 4.5
CAPTION_SIZE, CAPTION_MAX_W = 76, 960   # pill = text + 80 px, so at most 1040 of the 1080 px width


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTS + name, size)


def _wrap(dr: ImageDraw.ImageDraw, text: str, font, width: float) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if dr.textlength(trial, font=font) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur]


def _canvas():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def caption_width(words: list[str]) -> float:
    return ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(" ".join(words), font=_font("segoeuib.ttf", CAPTION_SIZE))


def caption_groups(words: list[dict], max_words: int = 3, max_width: float = CAPTION_MAX_W) -> list[list[dict]]:
    """Up to 3 words a caption, broken at sentence ends and before a word that would run past the screen."""
    groups, cur = [], []
    for w in words:
        if cur and caption_width([x["w"] for x in cur] + [w["w"]]) > max_width:
            groups.append(cur)
            cur = []
        cur.append(w)
        if len(cur) == max_words or w["w"].endswith((".", "?", "!")):
            groups.append(cur)
            cur = []
    return groups + ([cur] if cur else [])


def overlay_plan(script: dict, words: list[dict], total: float) -> list[tuple[str, int, float, float]]:
    """(kind, index, start, end) for every overlay. Weekly facts share the time before the end card."""
    facts = script["card"]["facts"]
    end_start = max(0.0, total - END_SECONDS)
    if len(facts) == 1:
        plan = [("card", 0, 0.3, min(5.5, total))]
    else:
        slot = max(0.0, end_start - 0.3) / len(facts)
        plan = [("card", i, 0.3 + i * slot, 0.3 + (i + 1) * slot) for i in range(len(facts))]
    plan.append(("end", 0, end_start, total))
    groups = caption_groups(words)
    for i, g in enumerate(groups):
        nxt = groups[i + 1][0]["s"] if i + 1 < len(groups) else g[-1]["e"] + 0.3
        plan.append(("cap", i, g[0]["s"], min(nxt, g[-1]["e"] + 0.6)))
    return plan


def caption_png(path: Path, words: list[str]) -> dict:
    img, dr = _canvas()
    f = _font("segoeuib.ttf", CAPTION_SIZE)
    text = " ".join(words)
    tw = dr.textlength(text, font=f)
    _, top, _, bottom = dr.textbbox((0, 0), "Hgjy", font=f)   # fixed ink box: same pill height for every caption
    pad_x, pad_y = 40, 24
    x = (W - tw) / 2
    pill = (x - pad_x, CAPTION_Y, x + tw + pad_x, CAPTION_Y + (bottom - top) + 2 * pad_y)
    dr.rounded_rectangle(pill, 30, fill=(255, 255, 255, 235))
    ty = CAPTION_Y + pad_y - top   # Segoe's top bearing would otherwise push the ink low
    for w in words:
        key = w.lower().strip(".,!?\"'")
        orange = key in HIGHLIGHT or any(c.isdigit() for c in w)
        dr.text((x, ty), w, font=f, fill=ORANGE if orange else INK)
        x += dr.textlength(w + " ", font=f)
    img.save(path)
    return {"pill": pill}


def card_png(path: Path, chip: str, fact: str, sources: list[str]) -> dict:
    img, dr = _canvas()
    x0, x1 = 60, W - 60
    fc, fh, fs = _font("segoeuib.ttf", 32), _font("segoeuib.ttf", 64), _font("segoeui.ttf", 34)
    lines = _wrap(dr, fact, fh, x1 - x0 - 80)
    y1 = CARD_Y + 115 + len(lines) * 78 + 70
    dr.rounded_rectangle((x0, CARD_Y, x1, y1), 36, fill="white")
    chip_w = dr.textlength(chip, font=fc) + 44
    dr.rounded_rectangle((x0 + 40, CARD_Y + 36, x0 + 40 + chip_w, CARD_Y + 90), 27, fill=TEAL)
    dr.text((x0 + 62, CARD_Y + 42), chip, font=fc, fill="white")
    y = CARD_Y + 115
    for ln in lines:
        dr.text((x0 + 40, y), ln, font=fh, fill=INK)
        y += 78
    dr.text((x0 + 40, y + 10), "Source: " + ", ".join(sources), font=fs, fill=MUTED)
    img.save(path)
    return {"card": (x0, CARD_Y, x1, y1)}


def endcard_png(path: Path, course: dict) -> dict:
    img, dr = _canvas()
    x0, x1 = 60, W - 60
    ft, fm = _font("segoeuib.ttf", 66), _font("segoeui.ttf", 38)
    lines = _wrap(dr, course["title"], ft, x1 - x0 - 100)
    y1 = END_Y + 200 + len(lines) * 80 + 60 + 140   # height follows the title's line count
    dr.rounded_rectangle((x0, END_Y, x1, y1), 40, fill="white")
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA")
        logo.thumbnail((260, 90))
        img.alpha_composite(logo, (x0 + 50, END_Y + 45))
    dr.text((x0 + 50, END_Y + 145), "Start learning", font=_font("segoeui.ttf", 40), fill=MUTED)
    y = END_Y + 200
    for ln in lines:
        dr.text((x0 + 50, y), ln, font=ft, fill=TEAL)
        y += 80
    meta = f"{course['lessons']} lessons  ·  free to learn"
    dr.text((x0 + 50, y + 5), meta, font=fm, fill=INK)
    meta_bottom = dr.textbbox((x0 + 50, y + 5), meta, font=fm)[3]
    button_top = y1 - 120
    dr.rounded_rectangle((x0 + 50, button_top, x1 - 50, y1 - 40), 40, fill=ORANGE)
    fb = _font("segoeuib.ttf", 44)
    label = "nerdit.in  ·  link in bio"
    dr.text(((W - dr.textlength(label, font=fb)) / 2, y1 - 110), label, font=fb, fill="white")
    img.save(path)
    return {"meta_bottom": meta_bottom, "button_top": button_top}


def duration(clip: Path) -> float:
    out = subprocess.run([FF, "-i", str(clip)], capture_output=True, text=True).stderr
    hh, mm, ss = out.split("Duration: ")[1].split(",")[0].split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(ss)


def compose(run: Path) -> Path:
    run = Path(run)
    clips = sorted((run / "clips").glob("*.mp4"))
    script = json.loads((run / "script.json").read_text(encoding="utf-8"))
    words = json.loads((run / "transcript.json").read_text(encoding="utf-8"))
    work = run / "overlays"
    work.mkdir(exist_ok=True)
    total = sum(duration(c) for c in clips)
    card = script["card"]
    groups = caption_groups(words)

    overlays = []   # (png, start, end)
    for kind, i, start, end in overlay_plan(script, words, total):
        if kind == "card":
            png = work / f"card{i}.png"
            card_png(png, card["chip"], card["facts"][i], card["sources"])
        elif kind == "end":
            png = work / "end.png"
            endcard_png(png, script["course"])
        else:
            png = work / f"cap{i:02d}.png"
            caption_png(png, [x["w"] for x in groups[i]])
        overlays.append((png, start, end))

    args = [FF, "-y", "-loglevel", "error"]
    for c in clips:
        args += ["-i", str(c)]
    for png, _, _ in overlays:
        args += ["-i", str(png)]
    norm = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1"
    fc = [f"[{i}:v]{norm}[v{i}]" for i in range(len(clips))]
    fc += [f"[{i}:a]aresample=48000[a{i}]" for i in range(len(clips))]
    fc.append("".join(f"[v{i}][a{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=1[base][aout]")
    last = "base"
    for j, (_, start, end) in enumerate(overlays):
        fc.append(f"[{last}][{len(clips) + j}:v]overlay=0:0:enable='between(t,{start:.2f},{end:.2f})'[o{j}]")
        last = f"o{j}"
    reel = run / "reel.mp4"
    args += ["-filter_complex", ";".join(fc), "-map", f"[{last}]", "-map", "[aout]", "-c:v", "libx264",
             "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
             "-movflags", "+faststart", str(reel)]
    subprocess.run(args, check=True, capture_output=True)
    record_reel(run)
    return reel


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    reel = compose(Path(argv[0]))
    print(f"wrote {reel} ({duration(reel):.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
