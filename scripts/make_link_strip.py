"""
Build the thin link strip under the contribution graph: one ruled line with
five small items (icon + lowercase label), no window chrome. It is meant
to be read as a quiet row between the graph and the portrait/card, not as a
component of its own -- so the icons and labels stay small, the
rules use the same hairline as the info card's section dividers, and there is
no fill, so it sits on the page background.

Colours are mid-greys with partial opacity so the strip reads on both GitHub's
light and dark themes (the other assets are fixed-dark windows).

It is five SVGs, one per link, stacked edge to edge, because links inside an
SVG shown through <img> are not clickable -- the README wraps each in an <a>.

  python scripts/make_link_strip.py
"""
from __future__ import annotations

import html
from pathlib import Path

N = 5
GAP = 10                # clear space above the rule, so it does not touch the graph above
W, H = 172, 30 + GAP    # five cells = 860px, the width the other assets are shown at
# each link takes one of the accents the heatmap and info card already use
GREEN, CYAN, BLUE, GOLD, VIOLET = "#39d353", "#22d3ee", "#58a6ff", "#f2cc60", "#a990f4"
RULE = "#8b949e"   # the rules stay a neutral grey
RULE_OPACITY = 0.35
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

OUT = Path(__file__).resolve().parent.parent / "assets"
S = 0.7                 # icons are drawn in a 20px box; shown at 14px


# 20x20 icons, all in the one muted colour
def resume(c):
    return (f'<path d="M4 1.5h8l4 4v13H4z" fill="none" stroke="{c}" stroke-width="1.6" stroke-linejoin="round"/>'
            f'<path d="M7 10h6M7 13h6M7 16h4" stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>')


def portfolio(c):
    return (f'<circle cx="10" cy="10" r="8" fill="none" stroke="{c}" stroke-width="1.6"/>'
            f'<ellipse cx="10" cy="10" rx="3.6" ry="8" fill="none" stroke="{c}" stroke-width="1.5"/>'
            f'<path d="M2 10h16" stroke="{c}" stroke-width="1.5"/>')


def linkedin(c):
    return (f'<rect x="1.5" y="1.5" width="17" height="17" rx="3" fill="none" stroke="{c}" stroke-width="1.6"/>'
            f'<text x="10" y="14.4" font-size="10.5" font-weight="700" text-anchor="middle" fill="{c}">in</text>')


def leetcode(c):
    return (f'<path d="M6.5 5.5L2 10l4.5 4.5M13.5 5.5L18 10l-4.5 4.5M11.5 3.5l-3 13" fill="none" '
            f'stroke="{c}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>')


def email(c):
    return (f'<rect x="1.5" y="4" width="17" height="12" rx="2" fill="none" stroke="{c}" stroke-width="1.6"/>'
            f'<path d="M2.5 5.5L10 11l7.5-5.5" fill="none" stroke="{c}" stroke-width="1.6" stroke-linejoin="round"/>')


LINKS = [
    ("resume", "resume", resume, GREEN),
    ("portfolio", "portfolio", portfolio, CYAN),
    ("linkedin", "linkedin", linkedin, BLUE),
    ("leetcode", "leetcode", leetcode, GOLD),
    ("email", "email", email, VIOLET),
]


def cell(i: int, label: str, icon, colour: str) -> str:
    last = i == N - 1
    rule = (f'<line x1="0" y1="{GAP + 0.5}" x2="{W}" y2="{GAP + 0.5}"/>'
            f'<line x1="0" y1="{H - 0.5}" x2="{W}" y2="{H - 0.5}"/>')
    divider = '' if last else f'<line x1="{W - 0.5}" y1="{GAP + 9}" x2="{W - 0.5}" y2="{H - 9}"/>'
    iw = 20 * S
    tw = iw + 8 + len(label) * 6.6
    x0 = (W - tw) / 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" font-family="{MONO}" aria-label="{html.escape(label)}">'
        f'<g stroke="{RULE}" stroke-opacity="{RULE_OPACITY}">{rule}{divider}</g>'
        f'<g transform="translate({x0:.1f},{(GAP + H - iw) / 2:.1f}) scale({S})">{icon(colour)}</g>'
        f'<text x="{x0 + iw + 8:.1f}" y="{(GAP + H) / 2 + 3.8}" font-size="11" fill="{colour}">{html.escape(label)}</text>'
        f'</svg>'
    )


def main() -> None:
    for i, (slug, label, icon, colour) in enumerate(LINKS):
        (OUT / f"link-{slug}.svg").write_text(cell(i, label, icon, colour))
    print("wrote", len(LINKS), "cells")


if __name__ == "__main__":
    main()
