"""The lesson's own parts for the video: each numbered section's tables, code runs and key terms.

A `table` scene redraws one of the section's tables and a `code` scene one of its code runs
(the code, then the output the lesson shows), as animated SVG in the lesson's tokens. They come
from the lesson HTML, so the clip shows exactly what the learner just read on the page.

    section_parts(content, topic) -> {"heading", "tables", "runs", "terms"} or None
        each run: {"code", "output", "outLabel", "walk": the page's code-walk lines as ["line:N"],
        "notes": the walk's steps as text}; a "Go deeper" box is left out
    table_svg(table, highlight)    highlight: ["row:E2", "col:branch"] in the order they are spoken
    code_svg(run, highlight)       highlight: ["line:2"]
"""
import html
import re

TOPIC = re.compile(r"<h2[^>]*>\s*(\d+)\s*[—–-]\s*(.*?)</h2>", re.S)
TABLE = re.compile(r"<table\b[^>]*>(.*?)</table>", re.S)
ROW = re.compile(r"<tr\b([^>]*)>(.*?)</tr>", re.S)
CELL = re.compile(r"<t([hd])\b[^>]*>(.*?)</t[hd]>", re.S)
RUN_START = re.compile(r'<div class="nerdit-run"')
# A worked example ends where the next block of another kind (or the next example) begins.
NEXT_BLOCK = re.compile(r'<div class="nerdit-(?:run|predict|tryit|compare|figure|fillblank|cheatsheet)\b|<h[23]\b|<p\b')
PART = re.compile(r'<div class="nerdit-(in|out)"[^>]*>\s*(?:<span class="nerdit-tag">(.*?)</span>)?.*?<code[^>]*>(.*?)</code>', re.S)
STRONG = re.compile(r"<strong>(.*?)</strong>", re.S)
WALK = re.compile(r'<ol class="nerdit-codewalk"[^>]*>(.*?)</ol>', re.S)
WALK_STEP = re.compile(r"<li\b[^>]*>\s*<code>(.*?)</code>(.*?)</li>", re.S)
DEEPER = re.compile(r'<details class="nerdit-deeper"[^>]*>.*?</details>', re.S)
VTITLE = re.compile(r'class="nerdit-vtitle"[^>]*>(.*?)<', re.S)
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")

W, H = 640, 480                 # 4:3, the video's picture box
MAX_ROWS, MAX_LINES = 9, 14


def text(markup: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", markup or "")).split())


def code_text(markup: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", markup or "")).strip("\n")


def section_html(content: str, topic: int) -> tuple[str, str] | None:
    """(heading, markup) of the lesson's numbered section, up to the next section."""
    for m in TOPIC.finditer(content or ""):
        if int(m.group(1)) == topic:
            end = content.find("</section>", m.end())
            nxt = content.find("<section", m.end())
            stops = [i for i in (end, nxt) if i != -1]
            return " ".join(EMOJI.sub("", text(m.group(2))).split()), content[m.end():min(stops) if stops else None]
    return None


def tables(markup: str) -> list[dict]:
    out = []
    for m in TABLE.finditer(markup):
        before = markup[max(0, m.start() - 400):m.start()]
        titles = VTITLE.findall(before)
        head, rows, spot = [], [], []
        for attrs, row in ROW.findall(m.group(1)):
            cells = CELL.findall(row)
            if cells and all(kind == "h" for kind, _ in cells) and not head:
                head = [text(c) for _, c in cells]
            elif cells:
                if "nerdit-spot" in attrs:
                    spot.append(len(rows))
                rows.append([text(c) for _, c in cells])
        out.append({"title": text(titles[-1]) if titles else "", "head": head, "rows": rows, "spot": spot})
    return out


def runs(markup: str) -> list[dict]:
    """Each worked example: its code and the output the lesson shows (never a Try It's answer)."""
    out = []
    starts = [m.start() for m in RUN_START.finditer(markup)]
    for a in starts:
        stop = NEXT_BLOCK.search(markup, a + 20)
        block = markup[a:stop.start() if stop else len(markup)]
        parts = {}
        for kind, tag, code in PART.findall(block):
            parts.setdefault(kind, (text(tag or ""), code_text(code)))
        if "in" in parts:
            code = parts["in"][1]
            lines = [ln.strip() for ln in code.split("\n")]
            walk, notes = [], []
            found = WALK.search(block)
            for quoted, rest in WALK_STEP.findall(found.group(1) if found else ""):
                line = code_text(quoted).strip()
                notes.append(text(f"{html.escape(line)} {rest}"))
                if line in lines:
                    walk.append(f"line:{lines.index(line) + 1}")
            out.append({"code": code, "output": parts.get("out", ("", ""))[1],
                        "outLabel": parts.get("out", ("Output", ""))[0] or "Output", "walk": walk, "notes": notes})
    return out


def terms(markup: str) -> list[str]:
    """Key terms the section bolds; labels such as "Tip:" are not terms."""
    seen = []
    for t in (text(s) for s in STRONG.findall(markup)):
        t = t.rstrip(" .")
        if t and not t.endswith(":") and t.lower() not in (s.lower() for s in seen):
            seen.append(t)
    return seen


def section_parts(content: str, topic: int) -> dict | None:
    found = section_html(content, topic)
    if not found:
        return None
    heading, markup = found
    markup = DEEPER.sub("", markup)   # optional reading; never in the video
    return {"heading": heading, "tables": tables(markup), "runs": runs(markup), "terms": terms(markup)}


def numbered_topics(content: str) -> list[int]:
    return [int(n) for n, _ in TOPIC.findall(content or "")]


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _fit(longest: int, width: float, most: float, least: float = 11, ratio: float = 0.58) -> float:
    return max(least, min(most, width / max(longest * ratio, 1)))


def _lines(cell: str, longest: int = 22) -> list[str]:
    """A long cell on two lines, broken at the space nearest its middle."""
    if len(cell) <= longest or " " not in cell:
        return [cell]
    mid = len(cell) / 2
    cut = min((i for i, ch in enumerate(cell) if ch == " "), key=lambda i: abs(i - mid))
    return [cell[:cut], cell[cut + 1:]]


def highlight_problems(kind: str, part: dict, highlight: list[str]) -> list[str]:
    errors = []
    for h in highlight or []:
        what, _, value = h.partition(":")
        if kind == "table" and what == "row" and not any(r and r[0] == value for r in part["rows"]):
            errors.append(f"highlight {h!r}: no row starts with {value!r}")
        elif kind == "table" and what == "col" and value not in part["head"]:
            errors.append(f"highlight {h!r}: no column {value!r} (columns: {', '.join(part['head'])})")
        elif kind == "code" and what == "line" and not (value.isdigit() and 1 <= int(value) <= len(part["code"].split("\n"))):
            errors.append(f"highlight {h!r}: the code has {len(part['code'].split(chr(10)))} lines")
        elif (kind, what) not in (("table", "row"), ("table", "col"), ("code", "line")):
            errors.append(f"highlight {h!r}: use " + ("row:<first cell> or col:<column>" if kind == "table" else "line:<n>"))
    return errors


def table_svg(table: dict, highlight: list[str] | None = None) -> str:
    """The table drawn row by row, then each highlight ringed in the order it is spoken."""
    head, rows = table["head"], table["rows"]
    more = len(rows) - MAX_ROWS if len(rows) > MAX_ROWS else 0
    rows = rows[:MAX_ROWS - 1] if more else rows
    cols = max(len(head), max((len(r) for r in rows), default=1))
    x0, y0, pad = 20, 70 if table["title"] else 30, 16
    cells = [[_lines(c) for c in r] for r in [head] + rows]
    # Each column as wide as its longest line, so a short id column leaves room for a long message.
    chars = [max([len(line) for r in cells if i < len(r) for line in r[i]] + [4]) for i in range(cols)]
    fs = max(11.0, min(20.0, (W - 40 - pad * cols) / (sum(chars) * 0.58)))
    base = [pad + n * 0.58 * fs for n in chars]
    cw = [b + max(0.0, W - 40 - sum(base)) / cols for b in base]
    xs = [x0 + sum(cw[:i]) for i in range(cols)]
    wrapped = any(len(c) > 1 for r in cells for c in r)
    rh = min(54 if wrapped else 46, (H - y0 - 30) / (len(rows) + 1 + bool(more)))

    def cell_text(i: int, y: float, lines: list[str], ink: str, bold: bool = False) -> str:
        weight = ' font-weight="700"' if bold else ""
        tops = [y + rh * .64] if len(lines) == 1 else [y + rh / 2 - fs * .15, y + rh / 2 + fs]
        return "".join(f'<text x="{xs[i] + 12:.1f}" y="{t:.1f}" font-size="{fs:.1f}"{weight} fill="{ink}">{_esc(line)}</text>'
                       for t, line in zip(tops, lines))
    out = [f'<svg class="nerdit-anim" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(table["title"] or "Lesson table")}" '
           f'font-family="Segoe UI, sans-serif">']
    if table["title"]:
        out.append(f'<text x="{W / 2}" y="40" text-anchor="middle" font-size="24" font-weight="700" fill="var(--tx)">'
                   f'{_esc(table["title"])}</text>')
    d = 0.0
    out.append(f'<g class="na-show" style="--d:{d:.2f}s"><rect x="{x0}" y="{y0}" width="{W - 40}" height="{rh}" rx="8" '
               f'fill="var(--nb)"/>' + "".join(
                   cell_text(i, y0, c, "var(--white)", bold=True) for i, c in enumerate(cells[0])) + "</g>")
    for r, row in enumerate(rows):
        d += 0.25
        y = y0 + rh * (r + 1)
        fill = "var(--nb-soft)" if r in table["spot"] else ("var(--bg-soft)" if r % 2 else "var(--white)")
        out.append(f'<g class="na-show" style="--d:{d:.2f}s"><rect x="{x0}" y="{y:.1f}" width="{W - 40}" height="{rh:.1f}" '
                   f'fill="{fill}" stroke="var(--bd)"/>' + "".join(
                       cell_text(i, y, c, "var(--tx)") for i, c in enumerate(cells[r + 1])) + "</g>")
    if more:
        d += 0.25
        out.append(f'<text class="na-show" style="--d:{d:.2f}s" x="{W / 2}" y="{y0 + rh * (len(rows) + 1.7):.1f}" '
                   f'text-anchor="middle" font-size="18" fill="var(--tx-s)">… {more + 1} more rows</text>')
    d += 0.6
    for h in highlight or []:
        what, _, value = h.partition(":")
        d += 1.4
        if what == "row":
            r = next((i for i, row in enumerate(rows) if row and row[0] == value), None)
            if r is None:
                continue
            box = (x0 - 6, y0 + rh * (r + 1) - 4, W - 28, rh + 8)
        else:
            if value not in head:
                continue
            i = head.index(value)
            box = (xs[i] - 2, y0 - 6, cw[i] + 4, rh * (len(rows) + 1) + 12)
        out.append(f'<rect class="na-show" style="--d:{d:.2f}s" x="{box[0]:.1f}" y="{box[1]:.1f}" width="{box[2]:.1f}" '
                   f'height="{box[3]:.1f}" rx="10" fill="none" stroke="var(--nb-vivid)" stroke-width="5"/>')
    return "".join(out) + "</svg>"


def code_svg(run: dict, highlight: list[str] | None = None) -> str:
    """The code typed in line by line, each highlighted line marked, then the lesson's output."""
    lines = run["code"].split("\n")[:MAX_LINES]
    outs = [l for l in run["output"].split("\n")][:6] if run["output"] else []
    longest = max([len(l) for l in lines + outs] or [10])
    fs = _fit(longest, W - 80, 19, ratio=0.6)
    lh = fs * 1.45
    code_h = lh * len(lines) + 56
    out_h = (lh * len(outs) + 56) if outs else 0
    scale = min(1.0, (H - 40) / (code_h + out_h + 24))
    fs, lh, code_h, out_h = fs * scale, lh * scale, code_h * scale, out_h * scale
    y = (H - code_h - out_h - (24 * scale if outs else 0)) / 2
    mono = 'font-family="Consolas, Menlo, monospace"'
    out = [f'<svg class="nerdit-anim" viewBox="0 0 {W} {H}" role="img" aria-label="Lesson code and its output" '
           f'font-family="Segoe UI, sans-serif">',
           f'<g class="na-show" style="--d:0s"><rect x="20" y="{y:.1f}" width="{W - 40}" height="{code_h:.1f}" rx="14" fill="var(--tx)"/>'
           f'<text x="40" y="{y + 30 * scale:.1f}" font-size="{15 * scale:.1f}" font-weight="700" fill="var(--nb-soft)">YOU TYPE</text></g>']
    d = 0.2
    marked = {int(h.split(":")[1]) for h in highlight or [] if h.startswith("line:") and h.split(":")[1].isdigit()}
    for i, line in enumerate(lines, 1):
        d += 0.45
        ly = y + 44 * scale + lh * i
        if i in marked:
            out.append(f'<rect class="na-show" style="--d:{d + 0.3:.2f}s" x="30" y="{ly - lh * .78:.1f}" width="{W - 60}" '
                       f'height="{lh:.1f}" rx="6" fill="var(--nb-vivid)" fill-opacity=".3"/>')
        out.append(f'<text class="na-show" style="--d:{d:.2f}s" x="40" y="{ly:.1f}" font-size="{fs:.1f}" {mono} '
                   f'fill="var(--white)" xml:space="preserve">{_esc(line)}</text>')
    if outs:
        d += 1.2
        oy = y + code_h + 24 * scale
        out.append(f'<g class="na-slide" style="--d:{d:.2f}s"><rect x="20" y="{oy:.1f}" width="{W - 40}" height="{out_h:.1f}" '
                   f'rx="14" fill="var(--bg-soft)" stroke="var(--nb)" stroke-width="2"/>'
                   f'<text x="40" y="{oy + 30 * scale:.1f}" font-size="{15 * scale:.1f}" font-weight="700" fill="var(--nb)">'
                   f'{_esc(run["outLabel"].upper())}</text>' + "".join(
                       f'<text x="40" y="{oy + 44 * scale + lh * k:.1f}" font-size="{fs:.1f}" {mono} fill="var(--tx)" '
                       f'xml:space="preserve">{_esc(l)}</text>' for k, l in enumerate(outs, 1)) + "</g>")
    return "".join(out) + "</svg>"
