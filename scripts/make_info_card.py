"""
Build the right-hand card: a macOS Terminal window showing a short shell
session, sized to sit beside the pixel-art scene in the README.

The reference is the native macOS Terminal.app window, not VS Code and not a
generic "developer terminal" component. That means the chrome is deliberately
plain -- a dark charcoal window, a flat title bar carrying the traffic lights
on the left and a centred proxy title, one hairline separator, 10px corners and
a restrained shadow. Everything else is shell output, and the shell output is
what supplies the hierarchy: no headings, no key/value widgets, no rules, no
badges, no progress bars.

The palette is not chosen, it is sampled from the supplied reference terminal
(see the palette block below for how). Each command's output carries its own
colour there -- cyan prompt, amber role, violet employer, lime status, blue
bullets -- so this card follows that scheme rather than a single foreground
grey.

Motion is CSS keyframes in an inline <style>, matching the pixel-art scene
(the previous version of this card used SMIL, which cannot answer
prefers-reduced-motion). Lines print once on a short stagger and freeze; only
the block cursor keeps blinking. Nothing retypes and nothing scrolls.

  python scripts/make_info_card.py
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import List, Tuple

# ---- content (single source of truth) --------------------------------------
NAME = "Arijit Das"
ROLE = "Backend + AI Engineer"
CURRENT = "American Chase"
STACK = [
    ["Python", "FastAPI", "Node.js", "Express.js"],
    ["REST APIs", "PostgreSQL", "Docker", "AWS"],
    ["LangChain", "OpenAI", "HuggingFace"],
]
STATUS = ["Building", "Learning", "Shipping"]

PROMPT = "arijit@github:~$ "
TITLE = "arijit@github: ~"

HERE: Path = Path(__file__).resolve().parent
OUT: Path = HERE.parent / "assets" / "info-card.svg"

# ---- geometry --------------------------------------------------------------
W, H = 480, 376
WIN_X, WIN_Y = 8, 6
WIN_W, WIN_H = 464, 356
RADIUS = 10
TITLEBAR_H = 28
PAD_X = 18
FONT = 12.5
LINE_H = 18.0
FIRST_BASELINE = WIN_Y + TITLEBAR_H + 20

# ---- palette ---------------------------------------------------------------
# Sampled from the supplied reference terminal, not chosen by eye. Thin
# antialiased glyphs have no dominant colour, so each value is the median of
# *stroke-interior* pixels only -- the foreground mask eroded by one pixel, so
# edge blending cannot pull the sample toward the background. Sampling the
# brightest pixel instead returns antialias overshoot (it reported the prompt
# as #45ffff rather than its actual #3ce6fc).
TERM_BG = "#0c1016"      # terminal background
TITLEBAR = "#1c2025"     # title bar
SEP = "#0c0f15"          # hairline under the title bar
TITLE_TXT = "#eff0f1"
PROMPT_C = "#3ce6fc"     # arijit@github:~$
CMD = "#f9f9fa"          # the typed command
NAME_C = "#bdc7d3"       # whoami output
ROLE_C = "#fdc44f"       # role output
CURRENT_C = "#a990f4"    # current output
STACK_C = "#b7c1ce"      # stack items
BULLET = "#3ba2e4"       # the separator between stack items
STATUS_C = "#a3ec67"     # status output
CURSOR = "#6e7681"
LIGHTS = ("#e54b48", "#efb344", "#64c74b")

MONO = ('"SF Mono", SFMono-Regular, ui-monospace, Menlo, Monaco, '
        '"Cascadia Mono", "Roboto Mono", "Courier New", monospace')

REVEAL_STEP = 0.055   # per-line stagger
REVEAL_LEAD = 0.10
CURSOR_START = 1.25   # after the last line has printed


def esc(s: str) -> str:
    return html.escape(s)


def rounded_top(x: float, y: float, w: float, h: float, r: float) -> str:
    """Path with only the top two corners rounded -- the title bar sits inside
    the window's rounded rect, so its bottom edge must stay square."""
    return (f"M{x} {y + h}L{x} {y + r}Q{x} {y} {x + r} {y}"
            f"L{x + w - r} {y}Q{x + w} {y} {x + w} {y + r}L{x + w} {y + h}Z")


def build_lines() -> List[Tuple[str, List[Tuple[str, str]]]]:
    """The session, as (kind, spans) where each span is (text, colour)."""
    def cmd(name: str):
        return ("cmd", [(PROMPT, PROMPT_C), (name, CMD)])

    def out(text: str, colour: str):
        return ("out", [(text, colour)])

    def joined(items: List[str], colour: str):
        spans: List[Tuple[str, str]] = []
        for i, it in enumerate(items):
            if i:
                spans.append((" \u2022 ", BULLET))
            spans.append((it, colour))
        return ("out", spans)

    rows: List[Tuple[str, List[Tuple[str, str]]]] = [
        cmd("whoami"), out(NAME, NAME_C), ("gap", []),
        cmd("role"), out(ROLE, ROLE_C), ("gap", []),
        cmd("current"), out(CURRENT, CURRENT_C), ("gap", []),
        cmd("stack"),
    ]
    rows += [joined(group, STACK_C) for group in STACK]
    rows += [("gap", []), cmd("status"), joined(STATUS, STATUS_C), ("gap", []),
             ("prompt", [(PROMPT, PROMPT_C)])]
    return rows


def css(n_lines: int) -> str:
    return f"""
@keyframes print{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes blink{{0%,49%{{opacity:1}}50%,99%{{opacity:0}}100%{{opacity:1}}}}
/* `backwards`, not `forwards`, and no resting opacity:0 -- a line's resting
   state is visible, and the keyframes only hold it hidden during its delay.
   With opacity:0 + forwards, any renderer that does not execute CSS shows an
   empty terminal; this way the session degrades to fully printed. */
.ln{{animation:print .28s ease-out backwards}}
.cur{{animation:blink 1.06s steps(1,end) {CURSOR_START}s infinite}}
@media (prefers-reduced-motion:reduce){{
  .ln{{animation:none}}
  .cur{{animation:none;opacity:1}}
}}
""".strip()


def main() -> None:
    rows = build_lines()
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" font-family=\'{MONO}\' '
        f'aria-label="macOS Terminal window: whoami {esc(NAME)}, {esc(ROLE)} at {esc(CURRENT)}">',
        f"<style>{css(len(rows))}</style>",
    ]

    # Window shadow: concentric translucent rounded rects rather than a blur
    # filter -- soft enough to read as a macOS drop shadow, and it cannot be
    # dropped or mis-rasterised the way a filter can be.
    for i in range(4):
        g = i * 2
        parts.append(
            f'<rect x="{WIN_X - g / 2:.1f}" y="{WIN_Y + 3 + i * 1.5:.1f}" '
            f'width="{WIN_W + g}" height="{WIN_H}" rx="{RADIUS + g / 2:.1f}" '
            f'fill="#000" opacity="0.055"/>')

    # window body + title bar + hairline separator
    parts.append(f'<rect x="{WIN_X}" y="{WIN_Y}" width="{WIN_W}" height="{WIN_H}" '
                 f'rx="{RADIUS}" fill="{TERM_BG}"/>')
    parts.append(f'<path d="{rounded_top(WIN_X, WIN_Y, WIN_W, TITLEBAR_H, RADIUS)}" fill="{TITLEBAR}"/>')
    parts.append(f'<line x1="{WIN_X}" y1="{WIN_Y + TITLEBAR_H}" x2="{WIN_X + WIN_W}" '
                 f'y2="{WIN_Y + TITLEBAR_H}" stroke="{SEP}"/>')

    # traffic lights: 12px, 20px apart, first centre ~19px in from the window edge
    cy = WIN_Y + TITLEBAR_H / 2
    for i, col in enumerate(LIGHTS):
        cx = WIN_X + 19 + i * 20
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="{col}"/>')
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="none" stroke="#000" stroke-opacity="0.14"/>')

    parts.append(f'<text x="{W / 2}" y="{cy + 4:.1f}" fill="{TITLE_TXT}" font-size="11.5" '
                 f'text-anchor="middle">{esc(TITLE)}</text>')

    # subtle outer hairline, the way a dark macOS window edge catches light
    parts.append(f'<rect x="{WIN_X + 0.5}" y="{WIN_Y + 0.5}" width="{WIN_W - 1}" height="{WIN_H - 1}" '
                 f'rx="{RADIUS}" fill="none" stroke="#fff" stroke-opacity="0.09"/>')

    # ---- session ----------------------------------------------------------
    x = WIN_X + PAD_X
    y = FIRST_BASELINE
    idx = 0
    for kind, spans in rows:
        if kind == "gap":
            y += LINE_H * 0.6
            continue
        delay = REVEAL_LEAD + idx * REVEAL_STEP
        tspans = "".join(
            f'<tspan fill="{col}" xml:space="preserve">{esc(t)}</tspan>' for t, col in spans)
        cursor = ""
        if kind == "prompt":
            cx = x + len(PROMPT) * FONT * 0.6
            cursor = (f'<rect class="cur" x="{cx:.1f}" y="{y - FONT + 2.5:.1f}" '
                      f'width="{FONT * 0.6:.1f}" height="{FONT:.1f}" fill="{CURSOR}"/>')
        parts.append(
            f'<g class="ln" style="animation-delay:{delay:.2f}s">'
            f'<text x="{x}" y="{y:.1f}" font-size="{FONT}">{tspans}</text>{cursor}</g>')
        idx += 1
        y += LINE_H

    parts.append("</svg>")
    svg = "".join(parts)

    bottom = WIN_Y + WIN_H
    if y > bottom - 6:
        raise SystemExit(f"session overflows the window: last baseline {y:.1f} vs {bottom}")
    for banned in ("<image", "base64", "<script"):
        if banned in svg:
            raise SystemExit(f"unexpected construct: {banned}")

    OUT.write_text(svg)
    print(f"wrote {OUT} {len(svg)} bytes; {W}x{H}")
    print(f"  {idx} printed lines, last baseline {y:.1f} (window bottom {bottom}), "
          f"reveal ends {REVEAL_LEAD + (idx - 1) * REVEAL_STEP + 0.28:.2f}s")


if __name__ == "__main__":
    main()
