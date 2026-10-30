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

W, H = 164, 40
BG, BG2, FRAME = "#0d1117", "#111722", "#30363d"
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


def build(label: str, colour: str, icon) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" font-family="{MONO}" aria-label="{html.escape(label)}">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient></defs>'
        f'<rect width="{W}" height="{H}" rx="10" fill="url(#g)"/>'
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="none" stroke="{FRAME}"/>'
        f'<g transform="translate(18,10)">{icon(colour)}</g>'
        f'<text x="48" y="25" font-size="13" font-weight="700" fill="{TEXT}">{html.escape(label)}</text>'
        f'</svg>'
    )


def main() -> None:
    for slug, label, colour, icon in LINKS:
        path = OUT / f"link-{slug}.svg"
        path.write_text(build(label, colour, icon))
        print("wrote", path)


if __name__ == "__main__":
    main()
