"""A 1080x1920 Reel from one topic clip: the clip in a themed frame with timed English cues.

No per-frame drawing: a few still layers (drawn once by draw.py) are laid over the clip with
ffmpeg, each cue only between its start and end. The clip's own narration is the audio.
"""
import re
import subprocess
from pathlib import Path

import cues as cue_mod
import draw
import source

FPS = 30
CTA_SECONDS = 2.0
# A soft generated chord under the voice (owner, 2026-11-19: music under the narration; no licensed track).
# One chord per theme, so the sound changes with the look.
PADS = {"navy": (220.0, 277.18, 329.63), "violet": (174.61, 220.0, 261.63), "light": (261.63, 329.63, 392.0),
        "ember": (164.81, 196.0, 246.94), "forest": (196.0, 246.94, 293.66)}


def _pad(freqs: tuple, length: float) -> str:
    a, b, c = freqs
    expr = (f"0.05*sin(2*PI*{a}*t)*(0.7+0.3*sin(2*PI*0.25*t))+0.035*sin(2*PI*{b}*t)*(0.7+0.3*sin(2*PI*0.21*t))"
            f"+0.03*sin(2*PI*{c}*t)")
    return (f"aevalsrc='{expr}':s=48000:d={length:.3f},lowpass=f=900,afade=t=in:d=1,"
            f"afade=t=out:st={max(length - 1.2, 0):.3f}:d=1.2,aformat=channel_layouts=stereo,volume=0.5")


def reel_command(ff: str, clip: Path, back: Path, front: Path, cues: list[tuple[Path, float, float]], cta: Path,
                 length: float, out: Path, pad: tuple | None = PADS["navy"]) -> list[str]:
    """`pad`: the chord under the voice, or None for the clip's narration alone."""
    t = f"{length:.3f}"
    still = lambda p: ["-loop", "1", "-framerate", str(FPS), "-t", t, "-i", str(p)]  # noqa: E731
    cmd = [ff, "-y", "-loglevel", "error"] + still(back) + ["-i", str(clip)] + still(front)
    for png, _, _ in cues:
        cmd += still(png)
    cmd += still(cta)
    x, y, w, h = draw.VIDEO_BOX
    graph = [f"[1:v]scale={w}:{h},setsar=1,fps={FPS}[vid]", f"[0:v][vid]overlay={x}:{y}[l0]", "[l0][2:v]overlay=0:0[l1]"]
    label = "l1"
    for i, (_, a, b) in enumerate(cues):
        graph.append(f"[{label}][{3 + i}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[c{i}]")
        label = f"c{i}"
    graph.append(f"[{label}][{3 + len(cues)}:v]overlay=0:0:enable='gte(t,{max(length - CTA_SECONDS, 0):.3f})',"
                 "format=yuv420p[v]")
    # The voice over the pad; the pad ducks while the voice speaks. 48 kHz stereo, as Reels prefer.
    voice = "[1:a]aresample=48000,aformat=channel_layouts=mono,pan=stereo|c0=c0|c1=c0"
    if pad is None:
        graph.append(voice + "[a]")
    else:
        graph += [voice + ",asplit=2[voice][key]", _pad(pad, length) + "[pad]",
                  "[pad][key]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=500[duck]",
                  "[voice][duck]amix=inputs=2:duration=first:normalize=0[a]"]
    return cmd + ["-filter_complex", ";".join(graph), "-map", "[v]", "-map", "[a]", "-t", t, "-r", str(FPS),
                  "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                  "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]


def probe(path: Path) -> dict:
    """Size, frame rate, duration and whether there is audio, from `ffmpeg -i` (no ffprobe in imageio-ffmpeg)."""
    import imageio_ffmpeg
    err = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    dur = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", err)
    video = re.search(r"Video: .*?(\d{2,5})x(\d{2,5}).*?(\d+(?:\.\d+)?) fps", err)
    return {"seconds": int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3]) if dur else 0.0,
            "size": (int(video[1]), int(video[2])) if video else (0, 0),
            "fps": float(video[3]) if video else 0.0,
            "audio": "Audio:" in err}


def _clip(src: dict, key: str) -> dict:
    for c in src["clips"]:
        if c["key"] == key:
            return c
    raise SystemExit(f"no topic clip {key} in clips.json")


def make_reel(src: dict, item: dict, hook: str, out_dir: Path, tl: dict | None = None, pad: bool = True) -> tuple[Path, Path]:
    """Write <id>.mp4 and <id>-cover.jpg into out_dir. Returns their paths. Cues that do not fit are skipped."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out_dir = Path(out_dir)
    work = out_dir / "_work" / item["id"]
    work.mkdir(parents=True, exist_ok=True)
    tl = tl or cue_mod.checked_timeline(src)
    clip = _clip(src, item["clipKey"])
    _, length = source.reel_window(clip, cue_mod.scene_ends(tl, clip))
    theme, layout = item["theme"], item["layout"]

    layers = draw.reel_layers(hook, theme, layout)
    pages = [(layers["back"], work / "back.png", 1080, 1920, False), (layers["front"], work / "front.png", 1080, 1920, True),
             (draw.cta_html(theme), work / "cta.png", 1080, 1920, True)]
    timed = []
    for i, c in enumerate(cue_mod.cues_from_timeline(tl, src["plan"], clip)):
        if c["start"] >= length:
            continue
        try:
            doc = draw.cue_html(c, theme)
        except draw.DrawError as e:
            print(f"  {item['id']}: cue skipped: {e}")
            continue
        png = work / f"cue-{i:02d}.png"
        pages.append((doc, png, 1080, 1920, True))
        timed.append((png, c["start"], min(c["end"], length)))

    # Cover: the finished drawing at the end of the clip's first scene.
    ends = cue_mod.scene_ends(tl, clip)
    at = max((ends[0] if ends else length) - 1.0, 0.0)
    frame = work / "frame.jpg"
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{at:.3f}", "-i", str(src["video"] / clip["file"]),
                    "-frames:v", "1", "-q:v", "2", str(frame)], check=True)
    cover = out_dir / f"{item['id']}-cover.jpg"
    pages.append((draw.cover_html(hook, frame, theme), cover, 1080, 1920, False))
    draw.shoot(pages)

    mp4 = out_dir / f"{item['id']}.mp4"
    subprocess.run(reel_command(ff, src["video"] / clip["file"], work / "back.png", work / "front.png", timed,
                                work / "cta.png", length, mp4, PADS[theme] if pad else None), check=True)
    return mp4, cover
