"""
Render the personal artifact -- a 32x32 pixel-art token that stands in for a
portrait as the profile's visual identity: a campfire on a stone ring, beside
a backpack, its flame licks resolving into the letter A.

The artifact is authored as an explicit pixel map (ART below): one character per
pixel, one palette entry per character. That is the single source of truth --
edit the map, re-run this script, and both outputs regenerate:

  assets/ascii.svg                    animated card for the README (370x376)
  assets/artifact-{512,128,64}.png    flat raster for the GitHub avatar upload

Two outputs are needed because GitHub treats the two slots differently: README
images may be animated SVG, but the account avatar must be an uploaded raster
(no SVG, and animation is not preserved). Both are drawn from the same map, so
they cannot drift.

Animation is CSS keyframes in an inline <style>, matching render_heatmap_svg.py
-- GitHub embeds SVGs via <img>, so keyframes run but JS does not. Motion is
deliberately near-threshold: a slow flame flicker, a rare gust, and three
single-pixel sparks that blip for a quarter second every nine. Readers who set
prefers-reduced-motion get the frozen, fully-lit state. STATIC=1 emits that same
frozen state for local previews.
"""
from pathlib import Path
from typing import Dict, List, Tuple
import os

USERNAME: str = "D-Arijit57"

HERE: Path = Path(__file__).resolve().parent
ASSETS_DIR: Path = HERE.parent / "assets"
OUT_SVG: Path = ASSETS_DIR / "ascii.svg"
PNG_SIZES: Tuple[int, ...] = (512, 128, 64)

STATIC: bool = bool(os.environ.get("STATIC"))  # emit frozen state for previews

# ---- palette ---------------------------------------------------------------
# Flame (red -> orange -> cream), wood, stone, and a backpack green. The core
# flame glow ramp echoes the contribution heatmap's warmth so the assets in
# the README read as one identity.
BG: str = "#0d1117"
PALETTE: Dict[str, str] = {
    "1": "#3a0f07",  # ember / interior shadow, darkest
    "2": "#7a1f0a",  # flame, outer edge
    "3": "#e0430c",  # flame body, mid (glow)
    "4": "#f9a428",  # flame, pooled glow above the crossbar (glow)
    "A": "#ffe2a6",  # the licks that form the 'A'
    "w": "#2b1710",  # wood, shadowed
    "x": "#5c3623",  # wood, mid
    "y": "#96613c",  # wood, lit / cut ends
    "s": "#2c3136",  # stone, shadowed
    "t": "#565c62",  # stone, mid
    "u": "#8d9399",  # stone, lit
    "p": "#16241a",  # backpack, shadowed edge
    "q": "#2a4a30",  # backpack, body
    "r": "#4f8a4c",  # backpack, lit edge / flap
    "n": "#8a5a2c",  # backpack, strap & buckle
}

# pixels that flicker like fire, and the licks that form the letter
GLOW_CHARS = frozenset("34")
INK_CHARS = frozenset("A")

# ---- the artifact ----------------------------------------------------------
# 32x32. A campfire's flame tapers to a point and flares into a skirt at the
# base; its two brightest licks and their crossbar resolve into an 'A' against
# a darker interior. Below, crossed logs feed the embers, ringed by a bumpy
# stone circle. A backpack stands beside it on the right. Flame, logs and
# stones sit inside the circle inscribed in the square for the avatar crop;
# the backpack's far corner is allowed to clip there, same as the reference.
GRID: int = 32
ART: List[str] = [
    "................................",  # 0
    "................................",  # 1
    "................................",  # 2
    "................................",  # 3
    "..............2A2...............",  # 4   flame tip
    ".............23A32..............",  # 5
    ".............23A32..............",  # 6
    "............23A1A32.............",  # 7
    "............23A1A32.............",  # 8
    "...........23A111A32............",  # 9
    "...........23A111A32............",  # 10
    "..........23A11111A32...........",  # 11
    "..........23A14441A32...........",  # 12  pooled glow above the crossbar
    ".........23AAAAAAAAA32..........",  # 13  crossbar
    ".........23A1111111A32..........",  # 14
    "........23A111111111A32..rrrrrrr",  # 15  backpack flap
    ".......23A11111111111A32.rrrrrrr",  # 16
    ".......23A11111111111A32.rrrrrrr",  # 17
    "......23A1111111111111A32pqqqqqr",  # 18
    "......23A1111111111111A32pnqqqnr",  # 19  backpack straps
    ".....wwwwwwwwwwwwwwwwwww1pnqqqnr",  # 20  ember row / log
    "......yxxxxxxxxxxxxxxxy..pnqqqnr",  # 21  log
    "....wyyyyyyy.xxxxxxxx.yywpqqqqqr",  # 22  log, cut ends
    ".........................ppppppr",  # 23  backpack pocket
    "..tus...tus...tus...tus..ppppppr",  # 24  stone ring
    "..tsstustsstustsstustsstuppppppr",  # 25  stone ring
    ".....tss...tss...tss...tsppppppr",  # 26  stone ring
    ".........................pqqqqqr",  # 27
    ".........................pqqqqqr",  # 28
    ".........................sssssss",  # 29  backpack grounding shadow
    "................................",  # 30
    "................................",  # 31
]

# single-pixel sparks, SVG only -- they animate, so baking them into the flat
# avatar would just add static noise. (grid_x, grid_y, delay_seconds)
SPARKS: List[Tuple[int, int, float]] = [
    (9, 2, 0.0),
    (22, 5, 3.4),
    (16, 1, 6.1),
]

# ---- card geometry (matches info-card.svg's height so the README table lines
# up, and the shared terminal chrome of the other assets) --------------------
W, H = 370, 376
PAD = 20
TITLEBAR_H = 30
SCALE = 9
ART_W = GRID * SCALE
ART_X = (W - ART_W) // 2
ART_Y = TITLEBAR_H + 8

CARD_BG = "#0d1117"
CARD_BG2 = "#111722"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#c9d1d9"

# ---- animation timing ------------------------------------------------------
CORE_DUR = 16.0   # two slow breaths, then one rare flicker
INK_DUR = 7.0
SPARK_DUR = 9.0


def validate() -> None:
    """Fail loudly on a mis-typed pixel map rather than emitting silent garbage."""
    if len(ART) != GRID:
        raise ValueError(f"ART has {len(ART)} rows, expected {GRID}")
    for y, row in enumerate(ART):
        if len(row) != GRID:
            raise ValueError(f"ART row {y} is {len(row)} wide, expected {GRID}")
        for ch in row:
            if ch != "." and ch not in PALETTE:
                raise ValueError(f"ART row {y} uses undefined pixel {ch!r}")


def runs(row: str):
    """Merge horizontal spans of one color into (x, width, char) so the SVG is a
    few hundred rects instead of a thousand."""
    x = 0
    while x < len(row):
        ch = row[x]
        if ch == ".":
            x += 1
            continue
        run = x
        while run < len(row) and row[run] == ch:
            run += 1
        yield x, run - x, ch
        x = run


def rects(chars: frozenset = None, exclude: frozenset = frozenset()) -> str:
    """Emit unit-sized rects for the pixels matching `chars` (all, if None)."""
    out: List[str] = []
    for y, row in enumerate(ART):
        for x, w, ch in runs(row):
            if chars is not None and ch not in chars:
                continue
            if ch in exclude:
                continue
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="1" fill="{PALETTE[ch]}"/>')
    return "".join(out)


def css() -> str:
    if STATIC:
        return ".spark{opacity:0}"
    return f"""
@keyframes core {{
  0%   {{ opacity:.80 }}
  25%  {{ opacity:1 }}
  50%  {{ opacity:.80 }}
  75%  {{ opacity:1 }}
  86%  {{ opacity:.86 }}
  88%  {{ opacity:.42 }}
  89.5%{{ opacity:1 }}
  91%  {{ opacity:.55 }}
  92.5%{{ opacity:.95 }}
  100% {{ opacity:.80 }}
}}
@keyframes ink {{ 0%,100% {{ opacity:.92 }} 50% {{ opacity:1 }} }}
@keyframes spark {{ 0%,100% {{ opacity:0 }} 1.5% {{ opacity:.9 }} 3% {{ opacity:0 }} }}
.core {{ animation: core {CORE_DUR:.0f}s ease-in-out infinite }}
.ink  {{ animation: ink {INK_DUR:.0f}s ease-in-out infinite }}
.spark{{ opacity:0; animation: spark {SPARK_DUR:.0f}s linear infinite }}
@media (prefers-reduced-motion: reduce) {{
  .core, .ink {{ animation:none; opacity:1 }}
  .spark {{ animation:none; opacity:0 }}
}}
""".strip()


def render_svg() -> str:
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="Pixel-art personal artifact: a campfire on a stone ring beside a '
        f'backpack, its flame forming the letter A" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        f"<style>{css()}</style>",
        "<defs>"
        f'<linearGradient id="abg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{CARD_BG2}"/><stop offset="1" stop-color="{CARD_BG}"/>'
        f"</linearGradient></defs>",
        f'<rect width="{W}" height="{H}" rx="12" fill="url(#abg)"/>',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="none" stroke="{FRAME}"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
    ]
    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
    parts.append(f'<text x="{W/2}" y="{TITLEBAR_H/2 + 4}" fill="{MUTED}" font-size="12" '
                 f'text-anchor="middle">{USERNAME}@github: ~$ ./artifact</text>')

    # the artifact itself: unit-coordinate pixels scaled up, snapped to the pixel
    # grid so upscaling stays crisp instead of blurring at the seams
    parts.append(f'<g transform="translate({ART_X},{ART_Y}) scale({SCALE})" shape-rendering="crispEdges">')
    parts.append(rects(chars=None, exclude=GLOW_CHARS | INK_CHARS))
    parts.append(f'<g class="core">{rects(chars=GLOW_CHARS)}</g>')
    parts.append(f'<g class="ink">{rects(chars=INK_CHARS)}</g>')
    for sx, sy, delay in SPARKS:
        parts.append(f'<rect class="spark" x="{sx}" y="{sy}" width="1" height="1" '
                     f'fill="{PALETTE["4"]}" style="animation-delay:{delay:.1f}s"/>')
    parts.append("</g>")

    line_y = ART_Y + ART_W + 12
    parts.append(f'<line x1="0" y1="{line_y}" x2="{W}" y2="{line_y}" stroke="{FRAME}"/>')
    parts.append(f'<text x="{PAD}" y="{line_y + 22}" fill="{MUTED}" font-size="11">artifact '
                 f'<tspan fill="{INK}">flame &#183; foundation &#183; focus</tspan></text>')
    parts.append("</svg>")
    return "".join(parts)


def render_pngs() -> List[Path]:
    """Flat rasters for the avatar upload. Nearest-neighbour from the same map,
    so every exported size is the pixel grid exactly -- no resampling mush."""
    from PIL import Image

    base = Image.new("RGB", (GRID, GRID), BG)
    px = base.load()
    for y, row in enumerate(ART):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            px[x, y] = tuple(int(PALETTE[ch][i:i + 2], 16) for i in (1, 3, 5))

    written: List[Path] = []
    for size in PNG_SIZES:
        if size % GRID:
            raise ValueError(f"{size} is not a whole multiple of the {GRID}px grid")
        out = ASSETS_DIR / f"artifact-{size}.png"
        base.resize((size, size), Image.NEAREST).save(out)
        written.append(out)
    return written


if __name__ == "__main__":
    validate()
    svg = render_svg()
    OUT_SVG.write_text(svg)
    print("wrote", OUT_SVG, len(svg), "bytes;", W, "x", H)
    for path in render_pngs():
        print("wrote", path)
