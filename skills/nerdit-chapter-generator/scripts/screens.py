#!/usr/bin/env python3
"""Screen and scene specs: the visuals a lesson describes once, in its own words.

A screen spec (<script type="application/json" class="nerdit-screen">) describes one click-path
in an app: a spreadsheet (layout "sheet"), a code editor, notebook or terminal ("editor"), or any
other app window ("app"). A scene spec (class="nerdit-scene") describes one simple idea told
through a familiar situation; it always becomes an AI image (B).

This module reads both, checks them against the lesson and decides, for a screen, A (drawn by
render_screens.py) or B (an image the illustrator briefs). The sync rule: every word a screen
draws must appear in the lesson's visible text, except grid cells, engine results and an app's
known labels. Stdlib only.
Spec: docs/superpowers/specs/2026-10-19-lesson-visuals-all-courses-design.md
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser

LAYOUTS = ("sheet", "editor", "app")
TOOLS = ("editor", "notebook", "terminal")
STEP_KINDS = ("select", "click", "type", "set", "key", "result")
PANEL_KINDS = ("field", "button", "message", "item")

# Labels a screen may draw although the lesson never writes them: the app's own furniture.
EXCEL_TABS = ("Home", "Insert", "Draw", "Page Layout", "Formulas", "Data", "Review", "View", "Help")
KNOWN_LABELS = {"excel": EXCEL_TABS}

# Phone limits: a 400-wide drawing stays readable on a 390 px screen.
MAX_COLUMNS, MAX_ROWS, MAX_CELL = 4, 7, 14
MAX_LINES, MAX_OUTPUT, MAX_LINE = 8, 4, 40
MAX_PATH, MAX_PANEL, MAX_LABEL, MAX_ITEM, MAX_MESSAGE = 4, 6, 24, 34, 90
MAX_DIALOG_FIELDS, MAX_GOAL, MAX_ALT = 4, 60, 150

CHECK_KEYS = ("question", "answer", "reasoning")

SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)
CELL = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")
LETTERS = re.compile(r"^[A-Z]{1,3}$")
LINE = re.compile(r"^line ([1-9][0-9]*)$")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
        "source", "track", "wbr"}


def _attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'(?<![\w-]){name}\s*=\s*"([^"]*)"', attrs)
    return m.group(1) if m else None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _text(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _show(v) -> str:
    return v if isinstance(v, str) else str(v)


def _read(html: str, cls: str) -> list[dict]:
    out = []
    for m in SCRIPT.finditer(html):
        attrs = m.group(1)
        if cls not in (_attr(attrs, "class") or "").split():
            continue
        try:
            spec = json.loads(m.group(2))
            if not isinstance(spec, dict):
                raise ValueError("not a JSON object")
        except ValueError as e:
            spec = {"_error": f"a {cls} block is not valid JSON ({e})"}
        spec["_grid"] = _attr(attrs, "data-grid")
        spec["_offset"] = m.end()
        out.append(spec)
    return out


def read_specs(html: str) -> list[dict]:
    """Screen specs in page order, each with "_grid" (data-grid or None) and "_offset"."""
    return _read(html, "nerdit-screen")


def read_scenes(html: str) -> list[dict]:
    """Scene specs in page order, each with "_offset"."""
    scenes = _read(html, "nerdit-scene")
    for s in scenes:
        s.pop("_grid", None)
    return scenes


def read_grid(html: str, grid_id: str) -> tuple[list[str], list[list]] | None:
    for m in SCRIPT.finditer(html):
        if _attr(m.group(1), "id") != grid_id:
            continue
        try:
            data = json.loads(m.group(2))
        except ValueError:
            return None
        if isinstance(data, dict) and isinstance(data.get("headers"), list) and isinstance(data.get("rows"), list):
            return data["headers"], data["rows"]
        return None
    return None


def col_index(letter: str) -> int:
    n = 0
    for ch in letter:
        n = n * 26 + ord(ch) - 64
    return n - 1


def cell_value(grid, ref: str):
    """The header (row 1) or data value at ref, or None outside the grid."""
    m = CELL.match(ref)
    if not m or grid is None:
        return None
    headers, rows = grid
    col, row = col_index(m.group(1)), int(m.group(2))
    line = headers if row == 1 else rows[row - 2] if row - 2 < len(rows) else None
    if line is None or col >= len(line):
        return None
    return line[col]


class _Visible(HTMLParser):
    """Visible text: no <script>/<style>, and no drawn screen (data-screen) vouching for itself."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[str] = []
        self.skip_at: int | None = None

    def handle_starttag(self, tag, attrs):
        self.parts.append(" ")
        if tag in VOID:
            return
        self.stack.append(tag)
        if self.skip_at is None and (tag in ("script", "style") or any(k == "data-screen" for k, _ in attrs)):
            self.skip_at = len(self.stack)

    def handle_endtag(self, tag):
        self.parts.append(" ")
        if tag in VOID or tag not in self.stack:
            return
        while self.stack:
            top = self.stack.pop()
            if self.skip_at is not None and len(self.stack) < self.skip_at:
                self.skip_at = None
            if top == tag:
                break

    def handle_data(self, data):
        if self.skip_at is None:
            self.parts.append(data)


def lesson_text(html: str) -> str:
    p = _Visible()
    p.feed(html)
    p.close()
    return _norm("".join(p.parts))


def _steps(spec: dict) -> list[dict]:
    steps = spec.get("steps")
    return [s for s in steps if isinstance(s, dict)] if isinstance(steps, list) else []


def _dialog_fields(spec: dict) -> list[dict]:
    dialog = spec.get("dialog")
    fields = dialog.get("fields") if isinstance(dialog, dict) else None
    return [f for f in fields if isinstance(f, dict)] if isinstance(fields, list) else []


def _panel(spec: dict) -> list[dict]:
    panel = spec.get("panel")
    return [i for i in panel if isinstance(i, dict)] if isinstance(panel, list) else []


def screen_kind(spec: dict) -> str:
    """The owner's rule: complex to explain -> "A" (drawn), simple -> "B" (image)."""
    if spec.get("image") in ("A", "B"):
        return spec["image"]
    steps = _steps(spec)
    if len(steps) > 3:
        return "A"
    if sum(1 for s in steps if s.get("do") == "set") >= 2:
        return "A"
    if len(_dialog_fields(spec)) >= 2:
        return "A"
    if any(s.get("do") == "result" for s in steps):
        return "A"
    return "B"


def drawn_strings(spec: dict) -> list[str]:
    """Every string a screen draws that the sync rule checks (not id, app, goal or grid cells)."""
    out: list = []
    layout = spec.get("layout")
    if layout == "editor":
        out += list(spec.get("lines") or []) + list(spec.get("output") or [])
    if layout == "app":
        out += list(spec.get("path") or [])
        for item in _panel(spec):
            out += [item.get("label"), item.get("value"), item.get("text")]
    dialog = spec.get("dialog")
    if isinstance(dialog, dict):
        out.append(dialog.get("title"))
    for f in _dialog_fields(spec):
        out += [f.get("label"), f.get("value")]
    for s in _steps(spec):
        kind = s.get("do")
        if kind == "click" and isinstance(s.get("path"), list):
            out += s["path"]
        elif kind == "type":
            out.append(s.get("text"))
        elif kind == "set":
            out += [s.get("label"), s.get("value")]
        elif kind == "key":
            out.append(s.get("keys"))
    seen: list[str] = []
    for v in out:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            v = str(v)
        if isinstance(v, str) and v.strip() and v not in seen:
            seen.append(v)
    return seen


def _check_sheet(spec: dict, grid, bad) -> tuple[list[str], tuple[int, int] | None]:
    if grid is None:
        name = spec.get("_grid")
        bad(f"data-grid '{name}' names no demo grid in this lesson" if name
            else "a sheet screen needs data-grid naming the lesson's demo grid")
    view = spec.get("view") if isinstance(spec.get("view"), dict) else {}
    cols, rows = view.get("columns"), view.get("rows")
    good_cols: list[str] = []
    if not (isinstance(cols, list) and cols and all(isinstance(c, str) and LETTERS.match(c) for c in cols)):
        bad("view.columns must list column letters")
    elif len(cols) > MAX_COLUMNS:
        bad(f"view shows {len(cols)} columns; at most {MAX_COLUMNS} columns fit a phone")
    elif [col_index(c) for c in cols] != sorted({col_index(c) for c in cols}):
        bad("view.columns must be in sheet order, each once")
    else:
        good_cols = cols
    span = None
    if not (isinstance(rows, list) and len(rows) == 2 and all(isinstance(r, int) for r in rows)
            and 1 <= rows[0] <= rows[1]):
        bad("view.rows must be [first, last]")
    elif rows[1] - rows[0] + 1 > MAX_ROWS:
        bad(f"view shows {rows[1] - rows[0] + 1} rows; at most {MAX_ROWS} rows fit a phone")
    else:
        span = (rows[0], rows[1])
    if not (isinstance(view.get("active"), str) and CELL.match(view["active"])):
        bad("view.active must be a cell such as H3")
    if grid is not None and good_cols and span:
        for r in range(span[0], span[1] + 1):
            for c in good_cols:
                v = cell_value(grid, f"{c}{r}")
                if v is not None and len(_show(v)) > MAX_CELL:
                    bad(f"{c}{r} value '{v}' is longer than {MAX_CELL} characters; "
                        f"narrow the view or shorten the value")
    return good_cols, span


def _check_editor(spec: dict, bad) -> None:
    if spec.get("tool") not in TOOLS:
        bad(f"tool must be one of {', '.join(TOOLS)}")
    lines, output = spec.get("lines"), spec.get("output", [])
    if not (isinstance(lines, list) and lines and all(isinstance(x, str) for x in lines)):
        bad("lines must list the code or command lines")
    elif len(lines) > MAX_LINES:
        bad(f"shows {len(lines)} lines; at most {MAX_LINES} lines fit a phone")
    else:
        for k, line in enumerate(lines, 1):
            if len(line) > MAX_LINE:
                bad(f"line {k} is longer than {MAX_LINE} characters")
    if not (isinstance(output, list) and all(isinstance(x, str) for x in output)):
        bad("output must list text lines")
    elif len(output) > MAX_OUTPUT:
        bad(f"shows {len(output)} output lines; at most {MAX_OUTPUT} fit a phone")
    else:
        for k, line in enumerate(output, 1):
            if len(line) > MAX_LINE:
                bad(f"output line {k} is longer than {MAX_LINE} characters")


def _short(value, limit: int, what: str, bad) -> None:
    if not (_text(value) or isinstance(value, (int, float))):
        bad(f"{what} is empty")
    elif len(_show(value)) > limit:
        bad(f"'{value}' is longer than {limit} characters")


def _check_app(spec: dict, bad) -> None:
    path = spec.get("path", [])
    if not isinstance(path, list) or len(path) > MAX_PATH:
        bad(f"path must list at most {MAX_PATH} menu or page names")
    else:
        for p in path:
            _short(p, MAX_LABEL, "a path item", bad)
    panel = spec.get("panel")
    if not (isinstance(panel, list) and panel):
        bad("panel must list what the screen shows")
        return
    if len(panel) > MAX_PANEL:
        bad(f"panel has {len(panel)} items; at most {MAX_PANEL} items fit a phone")
    for item in panel:
        kind = item.get("kind") if isinstance(item, dict) else None
        if kind not in PANEL_KINDS:
            bad(f"panel item kind must be one of {', '.join(PANEL_KINDS)}")
        elif kind == "field":
            _short(item.get("label"), MAX_LABEL, "a field label", bad)
            _short(item.get("value"), MAX_LABEL, "a field value", bad)
        elif kind == "button":
            _short(item.get("label"), MAX_LABEL, "a button label", bad)
        elif kind == "item":
            _short(item.get("text"), MAX_ITEM, "a list item", bad)
        elif kind == "message":
            if not _text(item.get("who")):
                bad("a message needs who")
            if not _text(item.get("text")):
                bad("a message is empty")
            elif len(item["text"]) > MAX_MESSAGE:
                bad(f"a message is longer than {MAX_MESSAGE} characters")


def _check_dialog(spec: dict, bad) -> None:
    dialog = spec.get("dialog")
    if dialog is None:
        return
    fields = _dialog_fields(spec)
    if not (isinstance(dialog, dict) and _text(dialog.get("title")) and fields
            and len(fields) == len(dialog.get("fields") or []) <= MAX_DIALOG_FIELDS):
        bad(f"dialog needs a title and 1 to {MAX_DIALOG_FIELDS} fields with label and value")
        return
    _short(dialog["title"], MAX_LABEL, "the dialog title", bad)
    for f in fields:
        _short(f.get("label"), MAX_LABEL, "a dialog label", bad)
        _short(f.get("value"), MAX_LABEL, "a dialog value", bad)


def _check_target(spec: dict, i: int, target, cols, span, bad) -> None:
    layout = spec["layout"]
    if layout == "sheet":
        m = CELL.match(target) if isinstance(target, str) else None
        if not m:
            bad(f"step {i}: target must be a cell such as H3")
        elif cols and span and not (m.group(1) in cols and span[0] <= int(m.group(2)) <= span[1]):
            bad(f"step {i}: target {target} is outside the view")
    elif layout == "editor":
        m = LINE.match(target) if isinstance(target, str) else None
        lines = spec.get("lines") if isinstance(spec.get("lines"), list) else []
        if not m or int(m.group(1)) > len(lines):
            bad(f"step {i}: target {target} is not a line of this screen")
    else:
        names = [x.get("label") for x in _panel(spec)] + [x.get("text") for x in _panel(spec) if x.get("kind") == "item"]
        if target not in [n for n in names if n is not None]:
            bad(f"step {i}: target '{target}' is not on this panel")


def _check_steps(spec: dict, cols, span, bad) -> None:
    steps = spec.get("steps")
    if not (isinstance(steps, list) and steps):
        bad("needs at least one step")
        return
    fields = {f.get("label"): f.get("value") for f in _dialog_fields(spec)}
    if spec["layout"] == "app":
        fields.update({x.get("label"): x.get("value") for x in _panel(spec) if x.get("kind") == "field"})
    typed: set = set()
    for i, s in enumerate(steps, 1):
        kind = s.get("do") if isinstance(s, dict) else None
        if kind not in STEP_KINDS:
            shown = kind if kind is not None else s
            bad(f"step {i}: unknown kind {shown!r}; use one of {', '.join(STEP_KINDS)}")
            continue
        if kind in ("select", "type"):
            _check_target(spec, i, s.get("target"), cols, span, bad)
        if kind == "click":
            path = s.get("path")
            if not (isinstance(path, list) and path):
                bad(f"step {i}: click needs a path")
            else:
                for p in path:
                    _short(p, MAX_LABEL, f"step {i} path item", bad)
        elif kind == "type":
            text = s.get("text")
            if not _text(text):
                bad(f"step {i}: type needs text")
            elif len(text) > MAX_LINE:
                bad(f"step {i}: typed text is longer than {MAX_LINE} characters")
            typed.add(s.get("target"))
        elif kind == "set":
            label = s.get("label")
            if label not in fields:
                bad(f"step {i}: '{label}' is not a field on this screen")
            elif _show(fields[label]) != _show(s.get("value")):
                bad(f"step {i}: {label} shows {fields[label]} on the screen, not {s.get('value')}")
        elif kind == "key":
            _short(s.get("keys"), MAX_LABEL, f"step {i} keys", bad)
        elif kind == "result":
            if spec["layout"] != "sheet":
                bad(f"step {i}: result needs layout sheet, the only layout with a result engine")
            elif s.get("target") not in typed:
                bad(f"step {i}: result {s.get('target')} needs an earlier type step into that cell")


def _check_teaching(owner: str, spec: dict, bad) -> None:
    for k in ("alt", "takeaway", "misconception"):
        if not _text(spec.get(k)):
            bad(f"{owner} need {k} for the illustrator brief")
    if _text(spec.get("alt")) and len(spec["alt"]) > MAX_ALT:
        bad(f"alt is longer than {MAX_ALT} characters")
    check = spec.get("check")
    if not (isinstance(check, dict) and all(_text(check.get(k)) for k in CHECK_KEYS)):
        bad(f"{owner} need check {{question, answer, reasoning}}")


def validate_spec(spec: dict, grid: tuple | None, text: str) -> list[str]:
    """Problems with one screen spec; empty when it is ready to draw or brief."""
    if "_error" in spec:
        return [spec["_error"]]
    sid = spec.get("id") if _text(spec.get("id")) else "?"
    problems: list[str] = []

    def bad(msg: str) -> None:
        problems.append(f"{sid}: {msg}")

    if sid == "?":
        bad("a screen spec needs an id")
    if not _text(spec.get("app")):
        bad("needs app, the app's plain name")
    goal = spec.get("goal")
    if not _text(goal):
        bad("needs a goal (the caption)")
    elif len(goal) > MAX_GOAL:
        bad(f"goal is longer than {MAX_GOAL} characters")
    layout = spec.get("layout")
    if layout not in LAYOUTS:
        bad(f"layout must be one of {', '.join(LAYOUTS)}")
        return problems
    image = spec.get("image", "auto")
    if image not in ("auto", "A", "B"):
        bad("image must be auto, A or B")
    elif image != "auto" and not _text(spec.get("why")):
        bad(f"image forced to {image} needs a why")

    cols, span = _check_sheet(spec, grid, bad) if layout == "sheet" else ([], None)
    if layout == "editor":
        _check_editor(spec, bad)
    elif layout == "app":
        _check_app(spec, bad)
    _check_dialog(spec, bad)
    _check_steps(spec, cols, span, bad)
    if screen_kind(spec) == "B":
        _check_teaching("B screens", spec, bad)

    known = {k.casefold() for k in KNOWN_LABELS.get(str(spec.get("app", "")).casefold(), ())}
    hay = _norm(text).casefold()
    for s in drawn_strings(spec):
        n = _norm(s).casefold()
        if n not in known and n not in hay:
            bad(f"'{s}' is not in the lesson")
    return problems


def validate_scene(scene: dict) -> list[str]:
    if "_error" in scene:
        return [scene["_error"]]
    sid = scene.get("id") if _text(scene.get("id")) else "?"
    problems: list[str] = []

    def bad(msg: str) -> None:
        problems.append(f"{sid}: {msg}")

    if sid == "?":
        bad("a scene spec needs an id")
    for k in ("subject", "caption"):
        if not _text(scene.get(k)):
            bad(f"scenes need {k}")
    _check_teaching("scenes", scene, bad)
    return problems


def validate_lesson(html: str) -> list[str]:
    text = lesson_text(html)
    specs, scenes = read_specs(html), read_scenes(html)
    problems: list[str] = []
    for spec in specs:
        grid = read_grid(html, spec["_grid"]) if spec.get("_grid") else None
        problems += validate_spec(spec, grid, text)
    for scene in scenes:
        problems += validate_scene(scene)
    ids = [s["id"] for s in specs + scenes if _text(s.get("id"))]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"{dup}: duplicate id; every screen and scene needs its own")
    return problems
