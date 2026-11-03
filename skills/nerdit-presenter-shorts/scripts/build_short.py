"""Compose a 9:16 presenter short: lip-synced presenter on top, kinetic English captions,
full-screen "Explore" cut-ins showing real course code, and an end card.

    python build_short.py <short.json> <presenter.mp4 (1080x900)> <voice.wav> <out.mp4>

short.spec.json (from shorts.py timeline): {"fps": 25, "duration": s,
  "captions": [[start, end, lead, keyword]], "explore": [[start, end, topic, filename, code]],
  "end": [start, title, subtitle]}
The overlay is drawn by overlay.html (renderAt(t), transparent background) in headless
Chromium, saved as PNG frames, and laid over the presenter with ffmpeg. Needs imageio-ffmpeg
and playwright, like the story video.
"""
import json, shutil, subprocess, sys
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "nerdit-story-video" / "scripts"))
from render import chromium   # noqa: E402  existing Playwright Chromium build


def main(spec_path, presenter, voice, out):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    fps, dur = spec["fps"], spec["duration"]
    page_html = (HERE / "overlay.html").read_text(encoding="utf-8").replace("/*SPEC*/null", json.dumps(spec))
    work = Path(out).with_suffix("")
    frames = work / "frames"
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    (work / "overlay.html").write_text(page_html, encoding="utf-8")
    exe = chromium()   # opens its own Playwright, so call it before ours
    with sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto((work / "overlay.html").resolve().as_uri())
        page.wait_for_function("document.fonts.status === 'loaded'")
        for i in range(int(dur * fps)):
            page.evaluate(f"renderAt({i / fps})")
            page.screenshot(path=str(frames / f"{i:05d}.png"), omit_background=True)
        browser.close()
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    graph = (f"color=c=#0b1220:s=1080x1920:r={fps}:d={dur}[bg];"
             f"[0:v]fps={fps},scale=1080:900[pr];[bg][pr]overlay=0:0:shortest=0[base];"
             f"[base][1:v]overlay=0:0,format=yuv420p[v]")
    subprocess.run([ff, "-y", "-v", "error", "-stream_loop", "-1", "-i", str(presenter),
                    "-framerate", str(fps), "-i", str(frames / "%05d.png"), "-i", str(voice),
                    "-filter_complex", graph, "-map", "[v]", "-map", "2:a", "-t", str(dur),
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",   # 24 kHz mono is silent in some players
                    "-movflags", "+faststart", str(out)], check=True)
    print("wrote", out)


if __name__ == "__main__":
    main(*sys.argv[1:5])
