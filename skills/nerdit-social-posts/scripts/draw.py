"""The pack's pictures as HTML pages, shot to PNG/JPEG with headless Chromium (the story-video way).

Reel layers (1080x1920): `back` (theme gradient), `front` (transparent: logo, hook, rounded video
corners), one transparent page per cue, and the closing button. Carousel slides are 1080x1350;
Story cards 1080x1920, feed cards 1080x1350. All on-screen text is English.
"""
import base64
import html
import re
from pathlib import Path

import source  # noqa: F401  puts story-video's scripts on sys.path
from dayplan import THEMES

ASSETS = Path(__file__).resolve().parents[1] / "assets"
REEL_W, REEL_H = 1080, 1920
SLIDE_W, SLIDE_H = 1080, 1350
FONT = '"Segoe UI","Nirmala UI",sans-serif'
DEVANAGARI = re.compile("[ऀ-ॿ]")

# (x, y, w, h) on the Reel. Safe area: y 90-1700, x <= 900 (Instagram's buttons and caption bar).
LOGO_BOX = (440, 90, 200, 72)
HOOK_BOX = (90, 200, 810, 260)
VIDEO_BOX = (40, 520, 1000, 562)
CAPTION_BOX = (90, 1130, 810, 300)
CTA_BOX = (180, 1500, 720, 140)
RADIUS = 28
HOOK_CHARS, HOOK_LINES = 28, 2   # about 28 characters per line at the 54 px hook font
CTA_TEXT = "Full lesson free at nerdit.in"
WRONG, RIGHT = "#ef4444", "#22c55e"


class DrawError(ValueError):
    """Text that would not fit its box, or that is not English."""


def fits(text: str, per_line: int, lines: int) -> bool:
    """Greedy word wrap: does `text` fit in `lines` lines of `per_line` characters?"""
    used, cur = 1, 0
    for word in text.split():
        if len(word) > per_line:
            return False
        if cur and cur + 1 + len(word) > per_line:
            used, cur = used + 1, len(word)
        else:
            cur = cur + 1 + len(word) if cur else len(word)
    return used <= lines


def _english(text: str, field: str) -> str:
    if DEVANAGARI.search(text or ""):
        raise DrawError(f"{field} must be English on screen: {text!r}")
    return text or ""


def _fit(text: str, field: str, per_line: int, lines: int) -> str:
    _english(text, field)
    if not fits(text, per_line, lines):
        raise DrawError(f"{field} is too long for {lines} line(s): {text!r}")
    return html.escape(text)


def data_uri(path: Path) -> str:
    mime = "image/png" if Path(path).suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


_LOGO = None


def logo_uri() -> str:
    global _LOGO
    _LOGO = _LOGO or data_uri(ASSETS / "nerdit-logo.png")
    return _LOGO


# Shrinks any .fit element's font until its text fits the box: the wrap estimate above is a guard,
# the browser has the final say. Glyphs reach past a tight line-height (about 0.2em), which
# scrollHeight counts, so a box only overflows when it is over by more than 0.35em.
FIT_JS = ("<script>for(const e of document.querySelectorAll('.fit')){let s=parseFloat(getComputedStyle(e).fontSize);"
          "while((e.scrollHeight>e.clientHeight+0.35*s||e.scrollWidth>e.clientWidth+2)&&s>18){s-=2;e.style.fontSize=s+'px';}}"
          "</script>")


def _page(body: str, w: int, h: int, transparent: bool = False, extra_css: str = "") -> str:
    bg = "background:transparent" if transparent else "background:#000"
    return ("<!doctype html><html><head><meta charset='utf-8'><style>"
            f"html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;{bg}}}"
            f"*{{box-sizing:border-box}}body{{font-family:{FONT};position:relative}}"
            ".abs{position:absolute}.fit{overflow:hidden}"
            f"{extra_css}</style></head><body>{body}{FIT_JS}</body></html>")


def _gradient_svg(t: dict, w: int, h: int, inner: str = "") -> str:
    return (f"<svg class='abs' style='left:0;top:0' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>"
            f"<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='{h}' gradientUnits='userSpaceOnUse'>"
            f"<stop offset='0' stop-color='{t['bg']}'/><stop offset='1' stop-color='{t['bg2']}'/></linearGradient></defs>"
            f"{inner}</svg>")


def _logo(box: tuple, plate: str = "#ffffff") -> str:
    x, y, w, h = box
    return (f"<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{plate};"
            f"border-radius:18px;display:flex;align-items:center;justify-content:center;padding:12px 18px'>"
            f"<img src='{logo_uri()}' style='max-width:100%;max-height:100%'></div>")


def reel_layers(hook: str, theme: str, layout: str) -> dict[str, str]:
    t = THEMES[theme]
    text = _fit(hook, "hook", HOOK_CHARS, HOOK_LINES)
    vx, vy, vw, vh = VIDEO_BOX
    glow = (f"<rect x='{vx - 16}' y='{vy - 16}' width='{vw + 32}' height='{vh + 32}' rx='{RADIUS + 12}' "
            f"fill='{t['panel']}' opacity='0.55'/>")
    back = _page(_gradient_svg(t, REEL_W, REEL_H, f"<rect width='{REEL_W}' height='{REEL_H}' fill='url(#g)'/>{glow}"),
                 REEL_W, REEL_H)
    # The four corners outside a rounded rectangle, painted with the same gradient as `back`.
    corners = (f"<path fill='url(#g)' fill-rule='evenodd' d='M{vx} {vy}h{vw}v{vh}h-{vw}z "
               f"M{vx + RADIUS} {vy}h{vw - 2 * RADIUS}a{RADIUS} {RADIUS} 0 0 1 {RADIUS} {RADIUS}v{vh - 2 * RADIUS}"
               f"a{RADIUS} {RADIUS} 0 0 1 -{RADIUS} {RADIUS}h-{vw - 2 * RADIUS}a{RADIUS} {RADIUS} 0 0 1 -{RADIUS} -{RADIUS}"
               f"v-{vh - 2 * RADIUS}a{RADIUS} {RADIUS} 0 0 1 {RADIUS} -{RADIUS}z'/>")
    hx, hy, hw, hh = HOOK_BOX
    if layout == "split":
        outline = (f"<rect x='{vx + 3}' y='{vy + 3}' width='{vw - 6}' height='{vh - 6}' rx='{RADIUS - 3}' fill='none' "
                   f"stroke='{t['accent']}' stroke-width='6'/>")
        hook_html = (f"<div class='abs' style='left:{hx}px;top:{hy}px;width:{hw}px;height:{hh}px;display:flex;"
                     f"align-items:center'><div style='border-left:10px solid {t['accent']};padding-left:26px;width:100%'>"
                     f"<div class='fit' style='color:{t['ink']};font-size:54px;font-weight:800;line-height:1.15;"
                     f"max-height:{hh}px;text-align:left'>{text}</div></div></div>")
    else:
        outline = ""
        hook_html = (f"<div class='abs' style='left:{hx}px;top:{hy}px;width:{hw}px;height:{hh}px;display:flex;"
                     f"align-items:center;justify-content:center'><div class='fit' style='color:{t['ink']};"
                     f"font-size:54px;font-weight:800;line-height:1.15;max-height:{hh}px;text-align:center'>{text}</div></div>")
    front = _page(_gradient_svg(t, REEL_W, REEL_H, corners + outline) + _logo(LOGO_BOX) + hook_html,
                  REEL_W, REEL_H, transparent=True)
    return {"back": back, "front": front}


def cue_html(cue: dict, theme: str) -> str:
    t = THEMES[theme]
    x, y, w, h = CAPTION_BOX
    kind = cue["kind"]
    if kind == "idea":
        text = _fit(cue["text"], "key idea", 38, 2)
        body = (f"<div class='abs fit' style='left:{x}px;top:{y}px;width:{w}px;height:110px;color:{t['muted']};"
                f"font-size:40px;font-weight:600;line-height:1.25;text-align:center'>{text}</div>")
    elif kind == "term":
        text = _fit(cue["text"], "term", 24, 1)
        body = (f"<div class='abs' style='left:{x}px;top:{y + 130}px;width:{w}px;display:flex;justify-content:center'>"
                f"<span style='background:{t['chip']};color:{t['chipInk']};font-size:54px;font-weight:800;"
                f"padding:14px 36px;border-radius:999px'>{text}</span></div>")
    elif kind in ("wrong", "right"):
        text = _fit(cue["text"], "myth", 32, 3)
        colour, label, mark = (WRONG, "MYTH", "&#10007;") if kind == "wrong" else (RIGHT, "FACT", "&#10003;")
        body = (f"<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{t['panel']};"
                f"border:4px solid {colour};border-radius:26px;padding:22px 30px'>"
                f"<div style='color:{colour};font-size:34px;font-weight:800;letter-spacing:2px'>{mark} {label}</div>"
                f"<div class='fit' style='color:{t['ink']};font-size:44px;font-weight:700;line-height:1.2;"
                f"height:{h - 110}px;margin-top:8px'>{text}</div></div>")
    else:
        raise DrawError(f"unknown cue kind {kind!r}")
    return _page(body, REEL_W, REEL_H, transparent=True)


def cta_html(theme: str) -> str:
    t = THEMES[theme]
    x, y, w, h = CTA_BOX
    return _page(f"<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{t['chip']};"
                 f"color:{t['chipInk']};border-radius:999px;display:flex;align-items:center;justify-content:center;"
                 f"font-size:46px;font-weight:800;box-shadow:0 10px 30px rgba(0,0,0,.35)'>{CTA_TEXT}</div>",
                 REEL_W, REEL_H, transparent=True)


def cover_html(hook: str, frame: Path, theme: str) -> str:
    """The Reel's cover: kept inside the grid's centre crop (y 240-1680)."""
    t = THEMES[theme]
    text = _fit(hook, "hook", HOOK_CHARS, HOOK_LINES)
    vx, _, vw, vh = VIDEO_BOX
    vy = 760
    body = (_gradient_svg(t, REEL_W, REEL_H, f"<rect width='{REEL_W}' height='{REEL_H}' fill='url(#g)'/>")
            + _logo((440, 300, 200, 72))
            + f"<div class='abs fit' style='left:90px;top:410px;width:900px;height:300px;display:flex;align-items:center;"
              f"justify-content:center;text-align:center;color:{t['ink']};font-size:68px;font-weight:800;line-height:1.12'>"
              f"{text}</div>"
            + f"<img class='abs' src='{data_uri(frame)}' style='left:{vx}px;top:{vy}px;width:{vw}px;height:{vh}px;"
              f"object-fit:cover;border-radius:{RADIUS}px;border:6px solid {t['accent']}'>"
            + f"<div class='abs' style='left:0;top:1420px;width:{REEL_W}px;text-align:center'><span style='background:"
              f"{t['chip']};color:{t['chipInk']};font-size:40px;font-weight:800;padding:14px 34px;border-radius:999px'>"
              f"Free lesson &middot; nerdit.in</span></div>")
    return _page(body, REEL_W, REEL_H)


_FIGURE_CSS = None


def figure_css() -> str:
    """The lesson stylesheet, with every animated part shown in its final state."""
    global _FIGURE_CSS
    if _FIGURE_CSS is None:
        import stage
        _FIGURE_CSS = (stage.lesson_css() + ".nerdit-anim .na-open{transform:none!important}"
                       ".nerdit-anim *{animation:none!important}"
                       ".pic .nerdit-wrapper{background:#fff;padding:0;margin:0;height:100%;display:flex;"
                       "align-items:center;justify-content:center}"
                       ".pic .nerdit-figure{width:100%;height:100%;max-width:none!important;margin:0!important}"
                       ".pic svg{width:100%;height:100%}")
    return _FIGURE_CSS


def _picture(picture: dict | None, x: int, y: int, w: int, h: int) -> str:
    if not picture:
        return ""
    box = f"left:{x}px;top:{y}px;width:{w}px;height:{h}px;border-radius:{RADIUS}px;overflow:hidden;background:#fff"
    if picture.get("svg"):
        return (f"<div class='abs pic' style='{box};padding:24px'><div class='nerdit-wrapper'><div class='nerdit-figure'>"
                f"{picture['svg']}</div></div></div>")
    return f"<img class='abs' src='{data_uri(Path(picture['img']))}' style='{box};object-fit:cover'>"


def _slide_frame(t: dict, n: int, total: int, inner: str) -> str:
    return (_gradient_svg(t, SLIDE_W, SLIDE_H, f"<rect width='{SLIDE_W}' height='{SLIDE_H}' fill='url(#g)'/>")
            + _logo((64, 60, 190, 66))
            + f"<div class='abs' style='right:64px;top:74px;color:{t['muted']};font-size:30px;font-weight:700'>{n}/{total}</div>"
            + inner)


def slide_html(slide: dict, theme: str, n: int, total: int) -> str:
    t = THEMES[theme]
    kind = slide["kind"]
    label = lambda s, c=None: (f"<div style='color:{c or t['accent']};font-size:34px;font-weight:800;"  # noqa: E731
                               f"letter-spacing:3px;text-transform:uppercase;margin-bottom:22px'>{s}</div>")
    wrap = "<div class='abs' style='left:80px;top:190px;width:920px;height:1060px;display:flex;flex-direction:column;"
    if kind == "cover":
        hook = _fit(slide["hook"], "cover hook", 18, 4)
        course = html.escape(_english(slide.get("course", ""), "course title"))
        inner = (wrap + "justify-content:center'>" + label("Free lesson")
                 + f"<div class='fit' style='color:{t['ink']};font-size:88px;font-weight:800;line-height:1.08;"
                   f"max-height:520px'>{hook}</div>"
                 + f"<div style='color:{t['muted']};font-size:36px;margin-top:34px'>{course}</div></div>"
                 + f"<div class='abs' style='right:64px;bottom:64px;background:{t['chip']};color:{t['chipInk']};"
                   f"font-size:34px;font-weight:800;padding:14px 30px;border-radius:999px'>Swipe &rarr;</div>")
    elif kind == "idea":
        text = _fit(slide["text"], "slide text", 22, 6)
        title = html.escape(_english(slide.get("title", ""), "slide title"))
        inner = (wrap + "justify-content:center'>" + label(f"{n - 1:02d} &middot; {title}" if title else f"{n - 1:02d}")
                 + f"<div class='fit' style='color:{t['ink']};font-size:68px;font-weight:800;line-height:1.15;"
                   f"max-height:820px'>{text}</div></div>")
    elif kind == "diagram":
        cap = _fit(slide.get("label", ""), "diagram label", 40, 2)
        inner = (f"<div class='abs fit' style='left:80px;top:180px;width:920px;height:110px;color:{t['ink']};"
                 f"font-size:40px;font-weight:700;line-height:1.2'>{cap}</div>"
                 + _picture({"svg": slide["svg"]}, 80, 310, 920, 940))
    elif kind == "quiz":
        q = _fit(slide["question"], "quiz question", 34, 3)
        opts = "".join(f"<div style='background:{t['panel']};color:{t['ink']};border:3px solid {t['stroke']}55;"
                       f"border-radius:20px;padding:16px 24px;font-size:36px;font-weight:600;margin-top:16px'>"
                       f"<b style='color:{t['accent']}'>{'ABCD'[i]}</b>&nbsp; {_fit(o, 'quiz option', 34, 2)}</div>"
                       for i, o in enumerate(slide["options"]))
        inner = (wrap + "justify-content:center'>" + label("Quick check")
                 + f"<div class='fit' style='color:{t['ink']};font-size:50px;font-weight:800;line-height:1.18;"
                   f"max-height:200px'>{q}</div>{opts}"
                 + f"<div style='color:{t['muted']};font-size:30px;margin-top:26px'>Answer on the next slide &rarr;</div></div>")
    elif kind == "answer":
        q = _fit(slide["question"], "quiz question", 34, 3)
        a = _fit(slide["answer"], "answer", 34, 2)
        inner = (wrap + "justify-content:center'>" + label("Answer", RIGHT)
                 + f"<div style='color:{t['muted']};font-size:38px;line-height:1.25'>{q}</div>"
                 + f"<div style='background:{RIGHT};color:#052e16;border-radius:24px;padding:26px 30px;font-size:52px;"
                   f"font-weight:800;margin-top:30px'>&#10003; {a}</div></div>")
    elif kind == "cta":
        text = _fit(slide.get("text") or "Full lesson free at nerdit.in", "cta", 22, 3)
        inner = (wrap + "justify-content:center;align-items:flex-start'>"
                 + f"<div class='fit' style='color:{t['ink']};font-size:80px;font-weight:800;line-height:1.1;"
                   f"max-height:420px'>{text}</div>"
                 + f"<div style='color:{t['muted']};font-size:40px;margin-top:30px'>Save this for later &middot; "
                   f"Share it with a friend who is learning</div>"
                 + f"<div style='background:{t['chip']};color:{t['chipInk']};font-size:42px;font-weight:800;"
                   f"padding:18px 40px;border-radius:999px;margin-top:44px'>nerdit.in</div></div>")
    else:
        raise DrawError(f"unknown slide kind {kind!r}")
    return _page(_slide_frame(t, n, total, inner), SLIDE_W, SLIDE_H, extra_css=figure_css() if kind == "diagram" else "")


def card_html(card: dict, theme: str, height: int) -> str:
    """Story (height 1920) or feed (1350) card: picture, title, what you'll learn, small logo."""
    t = THEMES[theme]
    top = 250 if height == REEL_H else 56          # Stories: keep clear of the top bar
    pic_h = 544
    has_pic = bool(card.get("picture"))
    title = _fit(card["title"], "card title", 26, 3)
    course = html.escape(_english(card.get("course", ""), "course title"))
    topics = "".join(f"<li style='margin-top:14px'>{_fit(x, 'topic', 40, 2)}</li>" for x in card.get("topics", [])[:4])
    text_top = top + (pic_h + 40 if has_pic else 80)
    body = (_gradient_svg(t, SLIDE_W, height, f"<rect width='{SLIDE_W}' height='{height}' fill='url(#g)'/>")
            + _picture(card.get("picture"), 56, top, 968, pic_h)
            + f"<div class='abs' style='left:72px;top:{text_top}px;width:936px'>"
              f"<div style='color:{t['accent']};font-size:30px;font-weight:800;letter-spacing:2px;"
              f"text-transform:uppercase'>{course}</div>"
              f"<div class='fit' style='color:{t['ink']};font-size:58px;font-weight:800;line-height:1.12;"
              f"max-height:200px;margin-top:10px'>{title}</div>"
            + (f"<div style='color:{t['muted']};font-size:30px;font-weight:700;margin-top:30px'>What you'll learn</div>"
               f"<ul style='color:{t['ink']};font-size:36px;line-height:1.25;margin:0;padding-left:36px'>{topics}</ul>"
               if topics else "")
            + "</div>"
            + _logo((72, height - (330 if height == REEL_H else 130), 190, 66))
            + f"<div class='abs' style='right:72px;top:{height - (318 if height == REEL_H else 118)}px;"
              f"color:{t['muted']};font-size:32px;font-weight:700'>Free lesson &middot; nerdit.in</div>")
    return _page(body, SLIDE_W, height, extra_css=figure_css() if card.get("picture", {}) and card["picture"].get("svg") else "")


def shoot(pages: list[tuple[str, Path, int, int, bool]]) -> None:
    """Shoot each (html, out, width, height, transparent) in one browser: PNG for .png, else JPEG."""
    import render
    from playwright.sync_api import sync_playwright
    exe = render.chromium()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        try:
            for doc, out, w, h, transparent in pages:
                out = Path(out)
                out.parent.mkdir(parents=True, exist_ok=True)
                page = browser.new_page(viewport={"width": w, "height": h})
                page.set_content(doc, wait_until="load")
                if out.suffix.lower() == ".png":
                    page.screenshot(path=str(out), type="png", omit_background=transparent)
                else:
                    page.screenshot(path=str(out), type="jpeg", quality=92)
                page.close()
        finally:
            browser.close()
