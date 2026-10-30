"""
Build the slim link strip that sits under the contribution graph: one small
pill per link (icon + heading), each its own SVG so the README can wrap every
one in a real <a>. Links inside an SVG shown through <img> are not clickable,
so the clickability lives in the README, not here.

Same window frame, colours and monospace stack as the other assets.

  python scripts/make_link_strip.py
"""
from __future__ import annotations

import html
from pathlib import Path

N = 5
W, H = 172, 44          # five cells = 860px, the width the heatmap is shown at
R = 12                  # the heatmap window's corner radius
BG = "#0a0e14"          # the heatmap's gradient ends here, so the join is seamless
FRAME = "#1f6feb"       # the heatmap's frame colour
TEXT = "#e6edf3"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

GREEN, ACCENT, BLUE, GOLD, INK = "#39d353", "#22d3ee", "#58a6ff", "#f2cc60", "#c9d1d9"

OUT = Path(__file__).resolve().parent.parent / "assets"


# 20x20 icons drawn at (0,0); colour passed in
def resume(c):
    return (f'<path d="M4 1.5h8l4 4v13H4z" fill="none" stroke="{c}" stroke-width="1.5" stroke-linejoin="round"/>'
            f'<path d="M12 1.5v4h4" fill="none" stroke="{c}" stroke-width="1.5" stroke-linejoin="round"/>'
            f'<path d="M7 10h6M7 13h6M7 16h4" stroke="{c}" stroke-width="1.4" stroke-linecap="round"/>')


def portfolio(c):
    return (f'<circle cx="10" cy="10" r="8" fill="none" stroke="{c}" stroke-width="1.5"/>'
            f'<ellipse cx="10" cy="10" rx="3.6" ry="8" fill="none" stroke="{c}" stroke-width="1.4"/>'
            f'<path d="M2 10h16" stroke="{c}" stroke-width="1.4"/>')


def linkedin(c):
    return (f'<rect x="1.5" y="1.5" width="17" height="17" rx="3" fill="{c}"/>'
            f'<text x="10" y="14.6" font-size="11" font-weight="700" text-anchor="middle" fill="{BG}">in</text>')


def leetcode(c):
    return (f'<path d="M6.5 5.5L2 10l4.5 4.5M13.5 5.5L18 10l-4.5 4.5M11.5 3.5l-3 13" fill="none" '
            f'stroke="{c}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>')


def email(c):
    return (f'<rect x="1.5" y="4" width="17" height="12" rx="2" fill="none" stroke="{c}" stroke-width="1.5"/>'
            f'<path d="M2.5 5.5L10 11l7.5-5.5" fill="none" stroke="{c}" stroke-width="1.5" stroke-linejoin="round"/>')


LINKS = [
    ("resume", "Resume", GREEN, resume),
    ("portfolio", "Portfolio", ACCENT, portfolio),
    ("linkedin", "LinkedIn", BLUE, linkedin),
    ("leetcode", "LeetCode", GOLD, leetcode),
    ("email", "Email", INK, email),
]


def build(i: int, label: str, colour: str, icon) -> str:
    """One cell of a single footer bar docked under the heatmap window. No top
    stroke (the heatmap's bottom edge is the divider); the first and last cell
    carry the rounded bottom corners and the outer side strokes."""
    first, last = i == 0, i == N - 1
    rl = R if first else 0
    rr = R if last else 0
    bg = f'M0 0H{W}V{H - rr}' + (f'Q{W} {H} {W - R} {H}' if last else f'V{H}') \
        + f'H{rl}' + (f'Q0 {H} 0 {H - R}' if first else '') + 'Z'
    # outer frame: bottom always, left on first, right on last
    y = H - 0.5
    d = ''
    if first:
        d += f'M0.5 0V{H - R}Q0.5 {y} {R} {y}'
    else:
        d += f'M0 {y}'
    d += f'H{W - R}' if last else f'H{W}'
    if last:
        d += f'Q{W - 0.5} {y} {W - 0.5} {H - R}V0'
    divider = '' if last else (f'<line x1="{W - 0.5}" y1="10" x2="{W - 0.5}" y2="{H - 10}" '
                               f'stroke="{FRAME}" stroke-opacity="0.25"/>')
    tw = 20 + 10 + len(label) * 7.8
    x0 = (W - tw) / 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" font-family="{MONO}" aria-label="{html.escape(label)}">'
        f'<path d="{bg}" fill="{BG}"/>'
        f'<path d="{d}" fill="none" stroke="{FRAME}" stroke-opacity="0.55"/>'
        f'{divider}'
        f'<g transform="translate({x0:.1f},{(H - 20) / 2})">{icon(colour)}</g>'
        f'<text x="{x0 + 30:.1f}" y="{H / 2 + 4.5}" font-size="13" font-weight="700" fill="{TEXT}">{html.escape(label)}</text>'
        f'</svg>'
    )


def main() -> None:
    for i, (slug, label, colour, icon) in enumerate(LINKS):
        path = OUT / f"link-{slug}.svg"
        path.write_text(build(i, label, colour, icon))
        print("wrote", path)


if __name__ == "__main__":
    main()
