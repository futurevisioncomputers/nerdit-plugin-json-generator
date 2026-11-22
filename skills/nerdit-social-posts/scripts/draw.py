"""The Reel overlays as HTML pages, shot to PNG/JPEG with headless Chromium (the story-video way).

Reel layers (1080x1920): `back` (gradient), `front` (transparent: logo, hook, rounded video corners), one
transparent page per cue, the closing button and the cover. All on-screen text is English. Carousel slides and
Story/feed cards are drawn by brand-studio (studio.py) since part 2b.
"""
import base64
import html
import json
import re
from pathlib import Path

import source  # noqa: F401  puts story-video's scripts on sys.path
from dayplan import THEMES

ASSETS = Path(__file__).resolve().parents[1] / "assets"
STYLE_DIR = Path(__file__).resolve().parents[1] / "styles"
FALLBACK_FONTS = {"head": "Segoe UI", "body": "Segoe UI", "code": "Consolas"}
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


# ---- Looks: a style (../styles/<name>.json) in one of the layout families ----

def style_from_theme(name: str) -> dict:
    """A library style by name; an old theme name without a style file is converted."""
    path = STYLE_DIR / f"{name}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    t = THEMES[name]
    palette = {k: t[k] for k in ("bg", "bg2", "panel", "ink", "muted", "accent", "chip", "chipInk")}
    return {"name": name, "inspiration": "", "palette": {**palette, "codeBg": "#0b1220", "codeInk": "#e2e8f0"},
            "fonts": dict(FALLBACK_FONTS), "background": "gradient", "motif": "none"}


def look_for(item: dict) -> dict:
    """The look an item is drawn in: its style (or, for packs planned before styles, its theme) and layout."""
    return {**style_from_theme(item.get("style") or item.get("theme") or "navy"), "layout": item.get("layout") or "stack"}


def resolve(look) -> tuple[dict, dict, str]:
    """(colours, style, layout) for a look dict or an old theme name."""
    st = style_from_theme(look) if isinstance(look, str) else look
    layout = "stack" if isinstance(look, str) else look.get("layout") or "stack"
    return {**st["palette"], "stroke": st["palette"].get("muted", "#ffffff")}, st, layout


def reel_frame(layout: str | None) -> str:
    """Reels keep their fixed safe areas: every layout family maps to one of the two frame layouts."""
    return "split" if layout in ("split", "editorial") else "stack"


def _font(name: str) -> str:
    return f'"{name}","Segoe UI","Nirmala UI",sans-serif'


def layout_css(layout: str, t: dict) -> str:
    """Moves the slide's content box for each layout family (the box has class 'wrap')."""
    return {
        "split": ".layout-split .wrap{left:150px!important;width:850px!important}",
        "bleed": (".layout-bleed .wrap{left:40px!important;width:1000px!important;top:160px!important;"
                  f"height:1120px!important;padding:48px;background:{t['panel']}}}"),
        "editorial": ".layout-editorial .wrap{justify-content:flex-start!important;top:250px!important}"
                     ".layout-editorial .h{letter-spacing:-0.02em}",
        "bignumber": ".layout-bignumber .wrap{top:330px!important;height:940px!important}",
    }.get(layout, "")


def motif_css(motif: str, t: dict) -> str:
    return {
        "highlight": (f".motif-highlight .h{{text-decoration:underline;text-decoration-thickness:.38em;"
                      f"text-decoration-color:{t['accent']}66;text-underline-offset:-.28em;text-decoration-skip-ink:none}}"),
        "underline": (f".motif-underline .h{{text-decoration:underline;text-decoration-thickness:7px;"
                      f"text-decoration-color:{t['accent']};text-underline-offset:14px}}"),
    }.get(motif, "")


def _motif(t: dict, st: dict, w: int, h: int) -> str:
    """Drawn decorations for the sticker and arrow motifs (highlight and underline are CSS)."""
    motif = st.get("motif", "none")
    if motif == "stickers":
        return (f"<div class='abs' style='right:64px;top:132px;transform:rotate(8deg);background:{t['chip']};"
                f"color:{t['chipInk']};font-size:30px;font-weight:800;padding:8px 20px;border-radius:14px'>&lt;/&gt;</div>"
                f"<div class='abs' style='right:150px;top:150px;transform:rotate(-10deg);color:{t['accent']};"
                f"font-size:44px'>&#9733;</div>")
    if motif == "arrows":
        return (f"<svg class='abs' style='left:52px;bottom:118px' width='190' height='120' viewBox='0 0 190 120'>"
                f"<path d='M12 104 C 60 22, 124 18, 172 58' stroke='{t['accent']}' stroke-width='8' fill='none' stroke-linecap='round'/>"
                f"<path d='M150 36 L174 60 L144 70' stroke='{t['accent']}' stroke-width='8' fill='none' stroke-linecap='round' "
                f"stroke-linejoin='round'/></svg>")
    return ""


def _background(t: dict, st: dict, w: int, h: int, inner: str = "") -> str:
    kind = st.get("background", "gradient")
    base = f"<rect width='{w}' height='{h}' fill='{t['bg'] if kind == 'flat' else 'url(#g)'}'/>"
    extra = ""
    if kind == "grain":
        extra = ("<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/>"
                 "<feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.09 0'/></filter>"
                 f"<rect width='{w}' height='{h}' filter='url(#n)'/>")
    elif kind == "grid":
        extra = (f"<pattern id='grid' width='60' height='60' patternUnits='userSpaceOnUse'><path d='M60 0H0V60' fill='none' "
                 f"stroke='{t['ink']}' stroke-opacity='0.08' stroke-width='2'/></pattern><rect width='{w}' height='{h}' fill='url(#grid)'/>")
    elif kind == "shapes":
        extra = (f"<circle cx='{w * 0.9:.0f}' cy='{h * 0.1:.0f}' r='{w * 0.3:.0f}' fill='{t['accent']}' fill-opacity='0.13'/>"
                 f"<circle cx='{w * 0.06:.0f}' cy='{h * 0.92:.0f}' r='{w * 0.24:.0f}' fill='{t['chip']}' fill-opacity='0.11'/>")
    return _gradient_svg(t, w, h, base + extra + inner, cls=f"bg-{kind}")


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


def _page(body: str, w: int, h: int, transparent: bool = False, extra_css: str = "", st: dict | None = None,
          layout: str | None = None) -> str:
    bg = "background:transparent" if transparent else "background:#000"
    fonts = (st or {}).get("fonts") or FALLBACK_FONTS
    t = {**(st or style_from_theme("navy"))["palette"]}
    classes = f"layout-{layout} motif-{(st or {}).get('motif', 'none')}" if layout else ""
    look_css = (layout_css(layout, t) + motif_css((st or {}).get("motif", "none"), t)) if layout else ""
    return ("<!doctype html><html><head><meta charset='utf-8'><style>"
            f"html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;{bg}}}"
            f":root{{--head:{_font(fonts['head'])};--body:{_font(fonts['body'])};--code:{_font(fonts['code'])}}}"
            "*{box-sizing:border-box}body{font-family:var(--body);position:relative}"
            ".h{font-family:var(--head)}.mono{font-family:var(--code)}"
            ".tk-kw{color:#c792ea}.tk-str{color:#c3e88d}.tk-num{color:#f78c6c}.tk-com{color:#8b98b0;font-style:italic}"
            ".abs{position:absolute}.fit{overflow:hidden}"
            f"{look_css}{extra_css}</style></head><body class='{classes}'>{body}{FIT_JS}</body></html>")


def _gradient_svg(t: dict, w: int, h: int, inner: str = "", cls: str = "", flat: bool = False) -> str:
    end = t["bg"] if flat else t["bg2"]
    return (f"<svg class='abs {cls}' style='left:0;top:0' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>"
            f"<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='{h}' gradientUnits='userSpaceOnUse'>"
            f"<stop offset='0' stop-color='{t['bg']}'/><stop offset='1' stop-color='{end}'/></linearGradient></defs>"
            f"{inner}</svg>")


def _logo(box: tuple, plate: str = "#ffffff") -> str:
    x, y, w, h = box
    return (f"<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{plate};"
            f"border-radius:18px;display:flex;align-items:center;justify-content:center;padding:12px 18px'>"
            f"<img src='{logo_uri()}' style='max-width:100%;max-height:100%'></div>")


def reel_layers(hook: str, look, layout: str | None = None) -> dict[str, str]:
    t, st, own = resolve(look)
    layout = reel_frame(layout or own)
    flat = st.get("background") == "flat"
    text = _fit(hook, "hook", HOOK_CHARS, HOOK_LINES)
    vx, vy, vw, vh = VIDEO_BOX
    glow = (f"<rect x='{vx - 16}' y='{vy - 16}' width='{vw + 32}' height='{vh + 32}' rx='{RADIUS + 12}' "
            f"fill='{t['panel']}' opacity='0.55'/>")
    back = _page(_background(t, st, REEL_W, REEL_H, glow), REEL_W, REEL_H, st=st)
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
                     f"<div class='fit h' style='color:{t['ink']};font-size:54px;font-weight:800;line-height:1.15;"
                     f"max-height:{hh}px;text-align:left'>{text}</div></div></div>")
    else:
        outline = ""
        hook_html = (f"<div class='abs' style='left:{hx}px;top:{hy}px;width:{hw}px;height:{hh}px;display:flex;"
                     f"align-items:center;justify-content:center'><div class='fit h' style='color:{t['ink']};"
                     f"font-size:54px;font-weight:800;line-height:1.15;max-height:{hh}px;text-align:center'>{text}</div></div>")
    front = _page(_gradient_svg(t, REEL_W, REEL_H, corners + outline, flat=flat) + _logo(LOGO_BOX) + hook_html,
                  REEL_W, REEL_H, transparent=True, st=st)
    return {"back": back, "front": front}


def cue_html(cue: dict, look) -> str:
    t, st, _ = resolve(look)
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
    return _page(body, REEL_W, REEL_H, transparent=True, st=st)


def cta_html(look) -> str:
    t, st, _ = resolve(look)
    x, y, w, h = CTA_BOX
    return _page(f"<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{t['chip']};"
                 f"color:{t['chipInk']};border-radius:999px;display:flex;align-items:center;justify-content:center;"
                 f"font-size:46px;font-weight:800;box-shadow:0 10px 30px rgba(0,0,0,.35)'>{CTA_TEXT}</div>",
                 REEL_W, REEL_H, transparent=True, st=st)


def cover_html(hook: str, frame: Path, look) -> str:
    """The Reel's cover: kept inside the grid's centre crop (y 240-1680)."""
    t, st, _ = resolve(look)
    text = _fit(hook, "hook", HOOK_CHARS, HOOK_LINES)
    vx, _, vw, vh = VIDEO_BOX
    vy = 760
    body = (_background(t, st, REEL_W, REEL_H)
            + _logo((440, 300, 200, 72))
            + f"<div class='abs fit h' style='left:90px;top:410px;width:900px;height:300px;display:flex;align-items:center;"
              f"justify-content:center;text-align:center;color:{t['ink']};font-size:68px;font-weight:800;line-height:1.12'>"
              f"{text}</div>"
            + f"<img class='abs' src='{data_uri(frame)}' style='left:{vx}px;top:{vy}px;width:{vw}px;height:{vh}px;"
              f"object-fit:cover;border-radius:{RADIUS}px;border:6px solid {t['accent']}'>"
            + f"<div class='abs' style='left:0;top:1420px;width:{REEL_W}px;text-align:center'><span style='background:"
              f"{t['chip']};color:{t['chipInk']};font-size:40px;font-weight:800;padding:14px 34px;border-radius:999px'>"
              f"Free lesson &middot; nerdit.in</span></div>")
    return _page(body, REEL_W, REEL_H, st=st)


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
