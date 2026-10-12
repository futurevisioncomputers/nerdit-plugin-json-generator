"""Check an inline SVG diagram against the lesson figure contract (CORE.md §7/§7b, figures.md)."""
from __future__ import annotations

import re

from lessonhtml import text

HEX = re.compile(r"(?<!&)#[0-9a-fA-F]{3,8}\b")
MARKER_CHARS = "①②③④⑤"


def check_svg(svg: str, labels: list[str], steps: int) -> list[str]:
    m = re.match(r"\s*<svg\b([^>]*)>", svg, re.S)
    if not m:
        return ["not an <svg> element"]
    attrs, errors = m.group(1), []
    if "viewBox=" not in attrs:
        errors.append("svg has no viewBox")
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
