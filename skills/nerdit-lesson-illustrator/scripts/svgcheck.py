"""Check an inline SVG diagram against the lesson figure contract (CORE.md §7/§7b, figures.md)."""
from __future__ import annotations

import re

from lessonhtml import text

HEX = re.compile(r"(?<!&)#[0-9a-fA-F]{3,8}\b")
MARKER_CHARS = "①②③④⑤"
# Lesson text in an SVG is ~14.7 user units and a phone column is ~314 px wide, so a viewBox
# wider than this shrinks labels below ~11.5 px. Stack the parts vertically instead.
MAX_VIEWBOX_WIDTH = 400


TEXT = re.compile(r"<text\b[^>]*>(.*?)</text>", re.S)
# Numbers, dates, times and capitalised names: the words a diagram can get wrong (Boston for Pune).
FACT_TOKEN = re.compile(r"\d+(?:[.,:/-]\d+)*|\b[A-Z][A-Za-z0-9_]*")


def foreign_tokens(svg: str, source: str) -> list[str]:
    """Numbers and capitalised words drawn in the SVG that do not appear in `source`."""
    drawn = " ".join(text(t) for t in TEXT.findall(svg))
    return sorted({t for t in FACT_TOKEN.findall(drawn) if t not in source})


def check_svg(svg: str, labels: list[str], steps: int) -> list[str]:
    m = re.match(r"\s*<svg\b([^>]*)>", svg, re.S)
    if not m:
        return ["not an <svg> element"]
    attrs, errors = m.group(1), []
    vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)', attrs)
    if not vb:
        errors.append("svg has no viewBox")
    elif float(vb.group(1)) > MAX_VIEWBOX_WIDTH:
        errors.append(f"viewBox is {float(vb.group(1)):g} wide; labels are unreadable on a phone above "
                      f"{MAX_VIEWBOX_WIDTH} - stack the parts vertically")
    if not re.search(r'\brole="img"', attrs):
        errors.append('svg needs role="img"')
    if not re.search(r'\baria-label="[^"]+"', attrs):
        errors.append("svg has no aria-label")
    if re.search(r'\b(?:width|height)="', attrs):
        errors.append("svg must not set width/height (viewBox only)")
    if HEX.search(svg):
        errors.append("hex colour in svg - use var(--token)")
    drawn = " ".join(text(t) for t in re.findall(r"<text\b[^>]*>(.*?)</text>", svg, re.S))
    for label in labels:
        if label not in drawn:
            errors.append(f"label '{label}' is not drawn as <text>")
    markers = sum(drawn.count(c) for c in MARKER_CHARS)
    if steps >= 2 and markers != steps:
        errors.append(f"{markers} numbered markers drawn, {steps} reading steps written")
    return errors
