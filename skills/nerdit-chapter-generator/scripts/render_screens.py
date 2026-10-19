#!/usr/bin/env python3
"""Draw complex screen walkthroughs (type A) as phone-sized SVG, from the lesson's own spec.

    python render_screens.py --dir <lesson dir> [--id <lesson id>]

For every A screen spec (screens.screen_kind) the lesson gets, straight after the spec block:

    <div class="nerdit-figure" data-visual="screen" data-screen="<id>" style="max-width:440px">
      <svg …></svg><div class="nerdit-figure-caption"><goal></div></div>
    <ol class="nerdit-visual-read" data-screen="<id>"><li>① …</li>…</ol>

B specs get no drawing (the illustrator briefs them); an old drawing of one is removed. Three
kits share one frame: a bar with the app name and the clicked path, then the body ("sheet":
formula bar and grid; "editor": code lines and output; "app": panel rows), an optional dialog
and the keys pressed. Spreadsheet results come from the plugin's Excel engine (excel_eval).
The drawing is deterministic, so check_screens.py can re-render and compare.
Exit 1, writing nothing, when any lesson has a problem. Stdlib only.
"""
from __future__ import annotations

import argparse
import html as htmllib
import re
import sys
import textwrap
from pathlib import Path

from excel_eval import evaluate_many
from screens import (EXCEL_TABS, RANGE, app_theme, cell_value, col_index, read_grid, read_specs,
                     screen_kind, validate_lesson)

W, PAD = 400, 10
INNER = W - 2 * PAD
MARKERS = "①②③④⑤"
MARK_ROOM = 20  # room one marker takes beside the part it names
DIALOG_BUTTONS = ("OK", "Cancel", "Apply", "Done", "Close", "Save")
YOU = ("you", "me", "user", "learner")
WRAP = 34

BLOCK = re.compile(
    r'<div class="nerdit-figure" data-visual="screen" data-screen="([^"]*)"[^>]*>.*?</svg>\s*'
    r'<div class="nerdit-figure-caption">.*?</div>\s*</div>\s*'
    r'(?:<ol class="nerdit-visual-read" data-screen="\1">.*?</ol>)?', re.S)


def esc(s) -> str:
    return htmllib.escape(str(s), quote=True)


def text_width(s: str, size: int = 14, mono: bool = False, bold: bool = False) -> float:
    return len(s) * size * (0.6 if mono or bold else 0.54)


def js_string(v) -> str:
    """How the Try It sheet shows a raw cell: JavaScript's String(v)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def cell_text(v) -> str:
    """A cell as the drawing shows it: outer spaces become ␣ so a cleaning lesson can see them
    (figures.md R11; SVG would collapse them)."""
    s = js_string(v)
    core = s.strip(" ")
    if not core:
        return "␣" * len(s)
    lead = len(s) - len(s.lstrip(" "))
    trail = len(s) - len(s.rstrip(" "))
    return "␣" * lead + core + "␣" * trail


# ---- steps ----

def reading_steps(spec: dict, results: dict[str, str]) -> list[str]:
    out = []
    for s in spec["steps"]:
        kind = s["do"]
        if kind == "select":
            if spec["layout"] != "sheet":
                out.append(f"Select {s['target']}.")
            elif RANGE.match(s["target"]):
                out.append(f"Select cells {s['target']}.")
            else:
                out.append(f"Click cell {s['target']}.")
        elif kind == "click":
            out.append("Click " + ", then ".join(s["path"]) + ".")
        elif kind == "type":
            out.append(f"Type {s['text']} in {s['target']}.")
        elif kind == "set":
            out.append(f"Set {s['label']} to {s['value']}.")
        elif kind == "key":
            out.append(f"Press {s['keys']}.")
        elif kind == "result":
            out.append(f"{s['target']} shows {results.get(s['target'], '')}.")
    return out


def results_for(spec: dict, grid) -> tuple[dict[str, str], list[str]]:
    """Formatted engine results for every result step, by target cell, plus problems."""
    targets = [s["target"] for s in spec.get("steps", []) if s.get("do") == "result"]
    if spec.get("layout") != "sheet" or not targets:
        return {}, []
    if grid is None:
        return {}, [f"{spec['id']}: no demo grid to compute results from"]
    typed = {s["target"]: s["text"] for s in spec["steps"] if s.get("do") == "type"}
    formulas = [typed[t] for t in targets]
    results, problems = {}, []
    for target, formula, res in zip(targets, formulas, evaluate_many(grid[0], grid[1], formulas)):
        if "error" in res:
            problems.append(f"{spec['id']}: {target}: {formula} gives {res['error']}")
        else:
            results[target] = res["text"]
    return results, problems


# ---- drawing ----

def paint(theme: str | None, role: str, fallback: str) -> str:
    """An app colour role as a token, falling back to the NerdIT token when the page's CSS
    has no theme for the app (or the app has none)."""
    return f"var(--app-{theme}-{role}, var(--{fallback}))" if theme else f"var(--{fallback})"


class Canvas:
    def __init__(self, theme: str | None = None):
        self.theme = theme
        self.parts: list[str] = []
        self.anchors: dict[tuple, tuple[float, float, int]] = {}

    def paint(self, role: str, fallback: str) -> str:
        return paint(self.theme, role, fallback)

    def rect(self, x, y, w, h, fill=None, stroke="var(--bd)", rx=4, width=1):
        fill = fill or self.paint("surface", "white")
        self.parts.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx}" '
                          f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def line(self, x1, y1, x2, y2, stroke="var(--bd)"):
        self.parts.append(f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" stroke="{stroke}"/>')

    def text(self, x, y, s, size=14, fill=None, bold=False, mono=False, anchor=None,
             italic=False, attrs=""):
        fill = fill or self.paint("ink", "tx")
        extra =' font-family="var(--font-code)" xml:space="preserve"' if mono else ""
        extra += ' font-weight="700"' if bold else ""
        extra += ' font-style="italic"' if italic else ""
        extra += f' text-anchor="{anchor}"' if anchor else ""
        extra += f" {attrs}" if attrs else ""
        self.parts.append(f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}"{extra}>{esc(s)}</text>')

    def anchor(self, key: tuple, x: float, y: float, step: int = MARK_ROOM):
        """Where the first marker for `key` goes; later ones move by `step`."""
        self.anchors.setdefault(key, (x, y, step))


def _clicks(spec: dict) -> list[list[str]]:
    return [s["path"] for s in spec["steps"] if s["do"] == "click"]


def _panel_names(spec: dict) -> set:
    if spec["layout"] != "app":
        return set()
    return {i.get("label") for i in spec["panel"]} | {i.get("text") for i in spec["panel"] if i["kind"] == "item"}


def _dialog_buttons(spec: dict) -> list[str]:
    if not spec.get("dialog"):
        return []
    out = []
    for path in _clicks(spec):
        if path[-1] in DIALOG_BUTTONS and path[-1] not in out:
            out.append(path[-1])
    return out


def _chips(spec: dict) -> list[str]:
    """The bar: the page path, then every clicked name not drawn elsewhere."""
    elsewhere = _panel_names(spec) | set(_dialog_buttons(spec))
    chips = list(spec.get("path") or []) if spec["layout"] == "app" else []
    for path in _clicks(spec):
        for p in path:
            if p not in elsewhere and p not in chips:
                chips.append(p)
    return chips


def _ribbon(spec: dict) -> tuple[list[str], list[str]]:
    """(tabs, buttons) for the bar. In a sheet a click path is a ribbon: its first name is the
    tab and later names are buttons on the ribbon below it. Other apps show the path as one row."""
    chips = _chips(spec)
    if spec["layout"] != "sheet":
        return chips, []
    tabs = {path[0] for path in _clicks(spec) if len(path) >= 2 or path[0] in EXCEL_TABS}
    return [ch for ch in chips if ch in tabs], [ch for ch in chips if ch not in tabs]


def _flow(names: list[str], x0: float, marked: set) -> list[list[tuple[str, float]]]:
    rows: list[list[tuple[str, float]]] = [[]]
    x = x0
    for name in names:
        room = text_width(name, 13, bold=True) + 18 + (MARK_ROOM + 4 if name in marked else 8)
        if x + room > W - PAD and rows[-1]:
            rows.append([])
            x = PAD + 12
        rows[-1].append((name, x))
        x += room
    return rows


def _bar(c: Canvas, spec: dict, y: float) -> float:
    clicked = {p for path in _clicks(spec) for p in path}
    marked = {path[-1] for path in _clicks(spec)}  # a click's marker sits on its last name
    tabs, buttons = _ribbon(spec)
    rows = _flow(tabs, PAD + 12 + text_width(spec["app"], 14, bold=True) + 14, marked)
    h = 12 + 30 * len(rows)
    c.rect(PAD, y + 6, INNER, h - 6, fill=c.paint("bar", "bg-soft"), stroke="none", rx=6)
    c.text(PAD + 12, y + 27, spec["app"], size=14, fill=c.paint("bar-ink", "nb"), bold=True)

    def draw(rows, top, rx):
        for r, row in enumerate(rows):
            cy = top + 30 * r
            for name, cx in row:
                w = text_width(name, 13, bold=True) + 18
                on = name in clicked
                c.rect(cx, cy, w, 24, stroke=c.paint("accent", "orange") if on else "var(--bd)",
                       rx=rx, width=2 if on else 1)
                c.text(cx + w / 2, cy + 17, name, size=13, anchor="middle", bold=on)
                c.anchor(("chip", name), cx + w + 11, cy + 12)

    draw(rows, y + 9, 12)
    y += h
    if buttons:
        ribbon = _flow(buttons, PAD + 12, marked)
        rh = 8 + 30 * len(ribbon)
        c.rect(PAD, y + 2, INNER, rh, fill=c.paint("soft", "bg-soft"), stroke="var(--bd-soft)", rx=4)
        draw(ribbon, y + 6, 4)
        y += rh + 2
    return y


def _sheet_columns(spec: dict, grid, results: dict[str, str]) -> list[tuple[str | None, float]]:
    """[(letter or None for a gap, width)] for the view, sized to fit its widest value."""
    view = spec["view"]
    r0, r1 = view["rows"]
    marks: dict[str, int] = {}
    for s in spec["steps"]:
        if s["do"] in ("select", "result"):
            rng = RANGE.match(s["target"])
            ref = f"{rng.group(3)}{rng.group(2)}" if rng else s["target"]
            marks[ref] = marks.get(ref, 0) + 1
    seq: list[tuple[str | None, float]] = []
    for i, letter in enumerate(view["columns"]):
        if i and col_index(letter) - col_index(view["columns"][i - 1]) > 1:
            seq.append((None, 18))
        # Row 1 and results are drawn bold, which is wider.
        shown = [(results[f"{letter}{r}"], True) if f"{letter}{r}" in results
                 else (cell_text(cell_value(grid, f"{letter}{r}")), r == 1) for r in range(r0, r1 + 1)]
        widest = max([text_width(t, 13, bold=b) for t, b in shown] + [text_width(letter, 12)])
        room = max([marks.get(f"{letter}{r}", 0) for r in range(r0, r1 + 1)] + [0]) * MARK_ROOM
        seq.append((letter, max(40, 12 + widest) + room))
    return seq


def _sheet(c: Canvas, spec: dict, grid, results: dict[str, str], y: float) -> float:
    view = spec["view"]
    typed = [s["text"] for s in spec["steps"] if s["do"] == "type"]
    y += 8
    c.rect(PAD, y, INNER, 28)
    muted = c.paint("ink", "tx-m")
    soft = c.paint("soft", "bg-soft")
    c.text(PAD + 8, y + 19, view["active"], size=12, fill=muted, mono=True)
    c.line(PAD + 48, y + 5, PAD + 48, y + 23)
    c.text(PAD + 56, y + 19, "fx", size=12, fill=muted, italic=True)
    shown = typed[-1] if typed else cell_text(cell_value(grid, view["active"]))
    if shown:
        c.text(PAD + 76, y + 19, shown, size=12, mono=True)
    c.anchor(("fx",), W - PAD - 12, y + 14)
    y += 36
    seq = _sheet_columns(spec, grid, results)
    r0, r1 = view["rows"]
    x0 = PAD + 28
    c.rect(PAD, y, 28, 22, fill=soft, stroke="var(--bd-soft)", rx=0)
    x = x0
    at: dict[str, tuple[float, float]] = {}
    for letter, w in seq:
        if letter:
            at[letter] = (x, w)
        c.rect(x, y, w, 22, fill=soft, stroke="var(--bd-soft)", rx=0)
        c.text(x + w / 2, y + 16, letter or "…", size=12, fill=muted, anchor="middle", attrs='data-head="1"')
        x += w
    y += 22
    top = y
    for r in range(r0, r1 + 1):
        c.rect(PAD, y, 28, 24, fill=soft, stroke="var(--bd-soft)", rx=0)
        c.text(PAD + 14, y + 17, str(r), size=12, fill=muted, anchor="middle")
        x = x0
        for letter, w in seq:
            ref = f"{letter}{r}"
            c.rect(x, y, w, 24, fill=None if letter else soft, stroke="var(--bd-soft)", rx=0)
            if letter:
                value = results.get(ref)
                fill, bold = ("var(--green)", True) if value is not None else (None, r == 1)
                value = value if value is not None else cell_text(cell_value(grid, ref))
                if value:
                    c.text(x + 6, y + 17, value, size=13, fill=fill, bold=bold, attrs=f'data-cell="{ref}"')
                c.anchor(("cell", ref), x + w - 10, y + 12, -MARK_ROOM)
            x += w
        y += 24
    active = view["active"]
    m = re.match(r"([A-Z]+)(\d+)$", active)
    x = x0
    for letter, w in seq:
        if letter == m.group(1) and r0 <= int(m.group(2)) <= r1:
            c.rect(x, y - 24 * (r1 - int(m.group(2)) + 1), w, 24, fill="none",
                   stroke=c.paint("accent", "orange"), rx=0, width=2)
        x += w
    for s in spec["steps"]:
        rng = RANGE.match(s["target"]) if s["do"] == "select" else None
        if rng:  # a selected range: one outline round it, its marker on the top-right cell
            (x1, _), (x2, w2) = at[rng.group(1)], at[rng.group(3)]
            y1, y2 = top + 24 * (int(rng.group(2)) - r0), top + 24 * (int(rng.group(4)) - r0 + 1)
            c.rect(x1, y1, x2 + w2 - x1, y2 - y1, fill="none", stroke=c.paint("accent", "orange"), rx=0, width=2)
            c.anchor(("range", s["target"]), x2 + w2 - 10, y1 + 12, -MARK_ROOM)
    return y + 4


def _editor(c: Canvas, spec: dict, y: float) -> float:
    lines, output = spec["lines"], spec.get("output") or []
    term = spec["tool"] == "terminal"
    lh = 20
    h = 14 + lh * len(lines) + (10 + lh * len(output) if output else 0)
    y += 8
    ink = c.paint("ink", "white" if term else "tx")
    surface = c.paint("surface", "nb" if term else "white")
    c.rect(PAD, y, INNER, h, fill=surface, stroke=surface if term else "var(--bd)", rx=6)
    left = PAD + (26 if term else 30)
    ty = y + 20
    for n, line in enumerate(lines, 1):
        if term:
            c.text(PAD + 10, ty, "$", size=13, fill=c.paint("accent", "orange"), mono=True)
        else:
            c.text(PAD + 20, ty, str(n), size=12, fill=c.paint("ink", "tx-m"), mono=True, anchor="end")
        if line:
            c.text(left, ty, line, size=13, fill=ink, mono=True)
        c.anchor(("line", n), left + text_width(line, 13, mono=True) + 14, ty - 5)
        ty += lh
    if output:
        c.line(PAD + 8, ty - 9, W - PAD - 8, ty - 9, stroke="var(--bd-soft)")
        ty += 6
        for line in output:
            c.text(PAD + (10 if term else 30), ty, line, size=13, fill=ink if term else c.paint("ink", "green"),
                   mono=True)
            ty += lh
    return y + h + 4


def _field(c: Canvas, x: float, y: float, label: str, value, key: str) -> float:
    c.text(x, y + 13, label, size=12, fill=c.paint("ink", "tx-m"))
    value = js_string(value)
    w = max(140, text_width(value, 14) + 20)
    c.rect(x, y + 19, w, 28)
    c.text(x + 10, y + 38, value, size=14)
    c.anchor((key, label), x + w + 14, y + 33)
    return y + 54


def _panel(c: Canvas, spec: dict, y: float) -> float:
    y += 6
    for item in spec["panel"]:
        kind = item["kind"]
        if kind == "field":
            y = _field(c, PAD + 6, y, item["label"], item["value"], "field")
        elif kind == "button":
            w = text_width(item["label"], 14, bold=True) + 30
            accent = c.paint("accent", "nb")
            c.rect(PAD + 6, y + 4, w, 30, fill=accent, stroke=accent, rx=6)
            c.text(PAD + 6 + w / 2, y + 24, item["label"], size=14, fill=c.paint("accent-ink", "white"),
                   bold=True, anchor="middle")
            c.anchor(("button", item["label"]), PAD + 6 + w + 14, y + 19)
            y += 40
        elif kind == "item":
            c.rect(PAD + 6, y + 2, INNER - 12, 30, stroke="var(--bd-soft)")
            c.text(PAD + 16, y + 22, item["text"], size=14)
            c.anchor(("item", item["text"]), W - PAD - 22, y + 17)
            y += 34
        else:
            lines = textwrap.wrap(item["text"], WRAP, break_long_words=True) or [""]
            w = max(text_width(line, 14) for line in lines) + 24
            h = 14 + 18 * len(lines)
            you = item["who"].casefold() in YOU
            x = W - PAD - 6 - w if you else PAD + 6
            c.rect(x, y + 4, w, h, fill=c.paint("soft", "bg-soft"),
                   stroke=c.paint("accent", "orange") if you else "var(--bd)", rx=12)
            for k, line in enumerate(lines):
                c.text(x + 12, y + 22 + 18 * k, line, size=14)
            y += h + 10
    return y


def _dialog(c: Canvas, spec: dict, y: float) -> float:
    d = spec["dialog"]
    buttons = _dialog_buttons(spec)
    x, w = PAD + 16, INNER - 32
    h = 36 + 54 * len(d["fields"]) + (40 if buttons else 0)
    y += 10
    accent = c.paint("accent", "nb")
    c.rect(x, y, w, h, stroke=accent, rx=8, width=1.5)
    c.rect(x + 1, y + 1, w - 2, 28, fill=c.paint("soft", "bg-soft"), stroke="none", rx=7)
    c.text(x + 12, y + 20, d["title"], size=14, fill=c.paint("ink", "nb"), bold=True)
    fy = y + 32
    for f in d["fields"]:
        fy = _field(c, x + 12, fy, f["label"], f["value"], "dfield")
    bx = x + w - 12
    for b in reversed(buttons):
        bw = text_width(b, 13, bold=True) + 26
        bx -= bw
        c.rect(bx, fy + 4, bw, 26, stroke=accent, rx=5)
        c.text(bx + bw / 2, fy + 22, b, size=13, anchor="middle", bold=True)
        c.anchor(("dbutton", b), bx - 12, fy + 17, -MARK_ROOM)
        bx -= MARK_ROOM + 10
    return y + h + 4


def _keys(c: Canvas, spec: dict, y: float) -> float:
    keys: list[str] = []
    for s in spec["steps"]:
        if s["do"] == "key" and s["keys"] not in keys:
            keys.append(s["keys"])
    if not keys:
        return y
    y += 6
    x = PAD + 6
    for k in keys:
        kw = text_width(k, 13, mono=True) + 20
        if x + kw + MARK_ROOM > W - PAD:
            x, y = PAD + 6, y + 34
        c.rect(x, y, kw, 28, fill=c.paint("soft", "bg-soft"), stroke="var(--bd)", rx=5)
        c.text(x + 10, y + 19, k, size=13, mono=True)
        c.anchor(("key", k), x + kw + 12, y + 14)
        x += kw + MARK_ROOM + 12
    return y + 34


def _marker_keys(spec: dict, step: dict) -> list[tuple]:
    kind, layout = step["do"], spec["layout"]
    named = lambda t: [("field", t), ("button", t), ("item", t), ("dfield", t), ("dbutton", t), ("chip", t)]
    if kind in ("select", "type"):
        t = step["target"]
        if layout == "sheet":
            if kind == "select":
                return [("range", t)] if RANGE.match(t) else [("cell", t)]
            return [("fx",)]
        if layout == "editor":
            return [("line", int(t.split()[1]))]
        return named(t)
    if kind == "result":
        return [("cell", step["target"])]
    if kind == "set":
        return [("field", step["label"]), ("dfield", step["label"])]
    if kind == "key":
        return [("key", step["keys"])]
    return named(step["path"][-1])


def _markers(c: Canvas, spec: dict) -> None:
    keys = [next((k for k in _marker_keys(spec, s) if k in c.anchors), None) for s in spec["steps"]]
    used: dict[tuple, int] = {}
    for i, key in enumerate(keys):
        x, y, move = c.anchors[key] if key else (W - PAD - 12, PAD + 18, -MARK_ROOM)
        n = used.get(key, 0)
        used[key] = n + 1
        if move < 0:  # markers grow leftwards: hand out slots right to left so ① stays leftmost
            n = keys.count(key) - 1 - n
        x = min(max(x + move * n, PAD + 10), W - PAD - 10)
        c.parts.append(f'<circle cx="{x:g}" cy="{y:g}" r="10" fill="var(--white)" stroke="none"/>')
        c.text(x, y + 6, MARKERS[i], size=18, fill="var(--orange)", bold=True, anchor="middle")


def screen_theme(spec: dict) -> str | None:
    """The app's colour theme; a terminal with no theme of its own still looks like a terminal."""
    theme = app_theme(spec["app"])
    if theme is None and spec["layout"] == "editor" and spec.get("tool") == "terminal":
        return "terminal"
    return theme


def render_svg(spec: dict, grid, results: dict[str, str]) -> str:
    c = Canvas(screen_theme(spec))
    y = _bar(c, spec, PAD - 6)
    if spec["layout"] == "sheet":
        y = _sheet(c, spec, grid, results, y)
    elif spec["layout"] == "editor":
        y = _editor(c, spec, y)
    else:
        y = _panel(c, spec, y)
    if spec.get("dialog"):
        y = _dialog(c, spec, y)
    y = _keys(c, spec, y)
    _markers(c, spec)
    height = round(y + PAD)
    label = esc(" ".join([spec["goal"]] + reading_steps(spec, results)))
    frame = (f'<rect x="0.5" y="0.5" width="{W - 1}" height="{height - 1}" rx="8" '
             f'fill="{c.paint("surface", "white")}" stroke="var(--bd)" stroke-width="1"/>')
    return (f'<svg viewBox="0 0 {W} {height}" role="img" aria-label="{label}">'
            + frame + "".join(c.parts) + "</svg>")


def layout_problems(spec: dict, grid, results: dict[str, str]) -> list[str]:
    if spec["layout"] != "sheet" or grid is None:
        return []
    need = 28 + sum(w for _, w in _sheet_columns(spec, grid, results))
    if need > INNER:
        return [f"{spec['id']}: the view needs {need:.0f} units but a phone fits {INNER}; "
                f"show fewer columns or shorter values"]
    return []


def figure_block(spec: dict, svg: str, steps: list[str]) -> str:
    items = "".join(f"<li>{MARKERS[i]} {esc(s)}</li>" for i, s in enumerate(steps))
    sid = esc(spec["id"])
    return (f'<div class="nerdit-figure" data-visual="screen" data-screen="{sid}" style="max-width:440px">'
            f'{svg}<div class="nerdit-figure-caption">{esc(spec["goal"])}</div></div>'
            f'<ol class="nerdit-visual-read" data-screen="{sid}">{items}</ol>')


def render_spec(html: str, spec: dict) -> tuple[str | None, list[str]]:
    """The drawn block for one valid spec (None for a B spec), plus problems."""
    if screen_kind(spec) != "A":
        return None, []
    grid = read_grid(html, spec["_grid"]) if spec.get("_grid") else None
    results, problems = results_for(spec, grid)
    problems += layout_problems(spec, grid, results)
    if problems:
        return None, problems
    return figure_block(spec, render_svg(spec, grid, results), reading_steps(spec, results)), []


def render_lesson(html: str) -> tuple[str, list[str]]:
    """The lesson with a fresh drawing after every A spec and none for B; unchanged on problems."""
    problems = validate_lesson(html)
    if problems:
        return html, problems
    clean = BLOCK.sub("", html)
    inserts = []
    for spec in read_specs(clean):
        block, spec_problems = render_spec(clean, spec)
        problems += spec_problems
        if block:
            inserts.append((spec["_offset"], block))
    if problems:
        return html, problems
    for offset, block in reversed(inserts):
        clean = clean[:offset] + block + clean[offset:]
    return clean, []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", required=True, help="lesson folder holding <id>.html files")
    ap.add_argument("--id", help="render only this lesson")
    args = ap.parse_args(argv)
    folder = Path(args.dir)
    files = [folder / f"{args.id}.html"] if args.id else sorted(folder.glob("*.html"))
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        print(f"no such lesson: {', '.join(missing)}", file=sys.stderr)
        return 2
    changed, problems = {}, []
    for f in files:
        before = f.read_text(encoding="utf-8")
        after, found = render_lesson(before)
        problems += [f"{f.stem}: {p}" for p in found]
        if after != before:
            changed[f] = after
    if problems:
        print("\n".join(problems))
        print(f"FAIL: {len(problems)} problem(s); no lesson was written")
        return 1
    for f, text in changed.items():
        f.write_text(text, encoding="utf-8")
    print(f"OK: {len(files)} lesson(s) checked, {len(changed)} rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
