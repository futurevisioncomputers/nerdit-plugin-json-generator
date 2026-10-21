"""Render the stage page to H.264 video frames with headless Chromium (Playwright).

Each worker process opens the page, calls renderAt(t) for its share of frames, screenshots
each one and pipes it to its own ffmpeg; the parts are then joined without re-encoding.
"""
import glob, math, os, subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

W, H = 1280, 720


def chromium() -> str | None:
    """Playwright's own browser if installed, else any Chromium build already on this machine."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        if Path(p.chromium.executable_path).is_file():
            return None
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright")
    found = sorted(glob.glob(str(root / "chromium-*" / "chrome-win*" / "chrome.exe"))
                   + glob.glob(str(root / "chromium-*" / "chrome-linux*" / "chrome")))
    if not found:
        raise SystemExit("no Chromium found: run  python -m playwright install chromium")
    return found[-1]


def frame_ranges(total: int, workers: int) -> list[tuple[int, int]]:
    """Split frames 0..total-1 into contiguous [start, end) ranges, one per worker."""
    size = math.ceil(total / workers)
    return [(i, min(i + size, total)) for i in range(0, total, size)]


def encode_command(ff: str, fps: int, out: Path) -> list[str]:
    return [ff, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg",
            "-i", "-", "-vf", "scale=out_range=tv,format=yuv420p",   # JPEG frames are full range
            "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-colorspace", "bt709",
            "-r", str(fps), str(out)]


def open_stage(p, html: str, exe: str | None):
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    page = browser.new_page(viewport={"width": W, "height": H})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(Path(html).resolve().as_uri())
    if errors or not page.evaluate("typeof renderAt === 'function'"):
        raise RuntimeError(f"stage page failed: {errors}")
    page.evaluate("window.ready")
    return browser, page


def render_part(job: tuple) -> str:
    html, start, end, fps, out, ff, exe = job
    from playwright.sync_api import sync_playwright
    proc = subprocess.Popen(encode_command(ff, fps, Path(out)), stdin=subprocess.PIPE)
    with sync_playwright() as p:
        browser, page = open_stage(p, html, exe)
        for i in range(start, end):
            page.evaluate(f"renderAt({i / fps})")
            proc.stdin.write(page.screenshot(type="jpeg", quality=92))
        browser.close()
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError(f"ffmpeg failed on {out}")
    return out


def render(html: Path, duration: float, fps: int, workers: int, out: Path, ff: str, runner=subprocess.run) -> Path:
    exe = chromium()
    total = math.ceil(duration * fps)
    parts_dir = out.parent / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(str(html), a, b, fps, str(parts_dir / f"v{n:02d}.mp4"), ff, exe)
            for n, (a, b) in enumerate(frame_ranges(total, workers))]
    with ProcessPoolExecutor(max_workers=len(jobs)) as pool:
        parts = list(pool.map(render_part, jobs))
    listing = parts_dir / "video-list.txt"
    listing.write_text("".join(f"file '{Path(p).as_posix()}'\n" for p in parts), encoding="utf-8")
    runner([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
            str(out)], check=True)
    return out


def still(html: Path, t: float, out: Path) -> Path:
    """One frame as a JPEG (thumbnail)."""
    from playwright.sync_api import sync_playwright
    exe = chromium()
    with sync_playwright() as p:
        browser, page = open_stage(p, str(html), exe)
        page.evaluate(f"renderAt({t})")
        page.screenshot(path=str(out), type="jpeg", quality=92)
        browser.close()
    return out
