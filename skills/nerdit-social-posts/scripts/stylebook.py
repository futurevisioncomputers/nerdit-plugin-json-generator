"""The style library and the brand-wide record of looks already posted.

A style (one JSON file in ../styles/) is a palette, a font pairing, a background treatment and an
accent motif. A look is a style in one of the layout families. Owner's rule (2026-11-19): never
the same design twice, so every post gets a look no earlier pack used, and two posts in a row never
share a style or a layout. The record lives in the user's home folder because every course posts
to the same feed.
"""
import json
import os
import re
from pathlib import Path

LAYOUTS = ("stack", "split", "bleed", "editorial", "bignumber")
BACKGROUNDS = ("flat", "gradient", "grain", "grid", "shapes")
MOTIFS = ("none", "stickers", "arrows", "highlight", "underline")
PALETTE_KEYS = ("bg", "bg2", "panel", "ink", "muted", "accent", "chip", "chipInk", "codeBg", "codeInk")
# Families installed on this PC (C:\Windows\Fonts, checked 2026-11-19). No downloads without the owner's OK.
FONTS = {"Segoe UI", "Segoe UI Black", "Segoe UI Semibold", "Bahnschrift", "Georgia", "Georgia Pro", "Cambria",
         "Constantia", "Corbel", "Candara", "Trebuchet MS", "Verdana", "Consolas", "Arial", "Arial Black",
         "Arial Nova", "Impact", "Rockwell Nova"}
RECENT = 3          # a style does not come back within this many posts
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class NoFreshLooks(Exception):
    def __init__(self, needed: int, left: int):
        super().__init__(f"needs {needed} looks, {left} left")
        self.needed, self.left = needed, left


def load_styles(folder: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(folder).glob("*.json"))]


def _luminance(hex_colour: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def style_errors(style: dict) -> list[str]:
    errors = []
    for key in ("name", "inspiration", "palette", "fonts", "background", "motif"):
        if not style.get(key):
            errors.append(f"missing {key}")
    if errors:
        return errors
    palette = style["palette"]
    for key in PALETTE_KEYS:
        if not HEX.match(str(palette.get(key, ""))):
            errors.append(f"palette.{key} must be #rrggbb")
    for role in ("head", "body", "code"):
        font = style["fonts"].get(role, "")
        if font not in FONTS:
            errors.append(f"font {font} is not installed on this PC")
    if style["background"] not in BACKGROUNDS:
        errors.append(f"background must be one of {', '.join(BACKGROUNDS)}")
    if style["motif"] not in MOTIFS:
        errors.append(f"motif must be one of {', '.join(MOTIFS)}")
    if HEX.match(str(palette.get("codeBg", ""))) and _luminance(palette["codeBg"]) > 0.2:
        errors.append("codeBg must be dark: code colours are tuned for dark panels")
    for fg, bg in (("ink", "bg"), ("ink", "bg2"), ("codeInk", "codeBg"), ("chipInk", "chip")):
        if HEX.match(str(palette.get(fg, ""))) and HEX.match(str(palette.get(bg, ""))):
            ratio = contrast(palette[fg], palette[bg])
            if ratio < 4.5:
                errors.append(f"{fg} on {bg} contrast {ratio:.1f}; at least 4.5")
    return errors


def history_path() -> Path:
    home = os.environ.get("NERDIT_SOCIAL_HOME")
    return (Path(home) if home else Path.home() / ".nerdit-social") / "style-history.json"


def load_history(path: Path) -> dict:
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"looks": []}


def save_history(path: Path, history: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")


def pick_looks(items: list[dict], styles: list[dict], history: dict, pack_id: str) -> list[tuple[str, str]]:
    """One fresh (style, layout) per item, in posting order. Raises NoFreshLooks when they run out."""
    taken = {(h["style"], h["layout"]) for h in history.get("looks", []) if h.get("packId") != pack_id}
    names = [s["name"] for s in styles]
    fresh = [(s, l) for s in names for l in LAYOUTS if (s, l) not in taken]
    if len(fresh) < len(items):
        raise NoFreshLooks(len(items), len(fresh))
    picked: list[tuple[str, str]] = []
    uses = {s: 0 for s in names}
    for _ in items:
        recent = {s for s, _ in picked[-RECENT:]}
        last_layout = picked[-1][1] if picked else None
        options = [(s, l) for s, l in fresh if (s, l) not in picked and s not in recent and l != last_layout]
        if not options:
            raise NoFreshLooks(len(items), len(fresh))
        choice = min(options, key=lambda o: (uses[o[0]], names.index(o[0]), LAYOUTS.index(o[1])))
        picked.append(choice)
        uses[choice[0]] += 1
    return picked


def reserve_looks(history: dict, pack_id: str, picks: list[tuple[str, str, str]]) -> dict:
    """The history with this pack's earlier entries replaced by `picks` (item id, style, layout)."""
    kept = [h for h in history.get("looks", []) if h.get("packId") != pack_id]
    return {"looks": kept + [{"style": s, "layout": l, "packId": pack_id, "itemId": i} for i, s, l in picks]}
