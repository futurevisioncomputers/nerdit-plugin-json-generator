#!/usr/bin/env python3
"""Turn a matplotlib SVG into one that re-themes with the page.

Matplotlib writes every colour into the SVG as a literal -- `fill="#003b6c"`,
`style="stroke: #000000"`. A literal survives a theme switch, so a navy chart stays navy
on a dark ground and black axis text disappears into it. This rewrites those literals as
`var(--token)` references, which resolve against whichever theme is active when the page
renders. One file then works on light, dark and high contrast alike.

Why SVG and not PNG at all: measured on the same bar chart, the SVG is 10.4 KB against a
140-dpi PNG's 14.6 KB, and it is the only one of the two that can re-theme. A per-theme
PNG set would be three files per chart -- one per theme -- and would push theme-switching
logic into lesson HTML, which CORE.md §7b forbids. PNG stays correct for dense chart types
where SVG element count explodes: see DENSE_CHART_TYPES below.

Usage:
  python tokenize_chart_svg.py --in bar.svg [--out bar.svg] [--check]

  --check  exit 2 if any colour literal survives, printing what is left. Use in CI.

Producing the input, in the lesson pipeline:

    import matplotlib
    matplotlib.rcParams["svg.fonttype"] = "none"   # keep <text> as text, not outlines
    fig.savefig(path, format="svg", transparent=True)

`svg.fonttype = "none"` matters: the default outlines glyphs into paths, and outlined text
cannot be recoloured by CSS, so the axis labels would stay black on a dark ground.
"""
import argparse
import re
import sys

# Palette literal -> token. Values mirror the :root block of css8.css; see CORE.md §7b for
# what each role means. Keys are lowercase -- input is normalised before lookup.
PALETTE = {
    "#003b6c": "var(--nb)",          # brand navy: bars, primary series
    "#163c6b": "var(--nb)",          # pre-v10 navy, still present in older figures
    "#b4560f": "var(--orange)",      # clay: the "what you do" series
    "#1f7a3f": "var(--green)",       # leaf: the "what you get" series
    "#8a5a00": "var(--amber)",       # amber: warnings, thresholds
    "#2b2620": "var(--tx)",          # ink: titles, axis labels
    "#6d6459": "var(--tx-m)",        # muted ink: tick labels
    "#e7dcc7": "var(--bd-soft)",     # hairline: gridlines
    "#d9cbb2": "var(--bd)",          # stronger rule: axis spines
    "#fffbf3": "var(--white)",       # paper, when a figure is not transparent
    "#000000": "var(--tx)",          # matplotlib's default black
    "#000": "var(--tx)",
}

# SVG grows one element per drawn mark, so these explode. Render them as a transparent PNG
# with mid-tone axis colours instead, and accept that neither theme gets ideal contrast --
# it is the right trade only where SVG is genuinely unworkable.
DENSE_CHART_TYPES = ("scatter over ~2000 points", "heatmap", "imshow", "hexbin", "contourf")

_ATTR = re.compile(r'\b(fill|stroke|stop-color|flood-color)="(#[0-9a-fA-F]{3,6})"')
_STYLE = re.compile(r'\b(fill|stroke|stop-color|flood-color):\s*(#[0-9a-fA-F]{3,6})')
_ANY_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def tokenize(svg, palette=None):
    """Return (svg_with_tokens, [literals_left_over]).

    Unknown colours are left untouched rather than guessed at -- a chart using a colour
    outside the palette is a content bug for §7b to catch, and silently rewriting it to
    the nearest token would hide that.
    """
    table = {k.lower(): v for k, v in (palette or PALETTE).items()}

    def attr(m):
        token = table.get(m.group(2).lower())
        return f'{m.group(1)}="{token}"' if token else m.group(0)

    def style(m):
        token = table.get(m.group(2).lower())
        return f"{m.group(1)}: {token}" if token else m.group(0)

    out = _STYLE.sub(style, _ATTR.sub(attr, svg))
    return out, sorted(set(_ANY_HEX.findall(out)))


def main():
    ap = argparse.ArgumentParser(description="Rewrite matplotlib SVG colours as theme tokens")
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", help="defaults to rewriting the input in place")
    ap.add_argument("--check", action="store_true",
                    help="exit 2 if any colour literal survives")
    args = ap.parse_args()

    with open(args.src, encoding="utf-8") as fh:
        svg = fh.read()

    if 'svg.fonttype' not in svg and '<use xlink:href="#DejaVu' in svg:
        print("WARN: text is outlined into paths -- CSS cannot recolour it. "
              "Set matplotlib.rcParams['svg.fonttype'] = 'none' before savefig.",
              file=sys.stderr)

    out, leftover = tokenize(svg)

    with open(args.dst or args.src, "w", encoding="utf-8") as fh:
        fh.write(out)

    swapped = out.count("var(--")
    print(f"{args.src}: {swapped} token reference(s), {len(leftover)} literal(s) remaining")
    if leftover:
        print("  remaining:", ", ".join(leftover))
        if args.check:
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
