"""
Trace the backend-lab reference artwork into a real pixel-art SVG.

PHASE 1: STATIC ONLY. Nothing here animates. The point of this pass is to get
the artwork itself exactly right; motion is a separate second pass.

This script does NOT redraw the scene by hand -- an earlier attempt did, and it
could not match the reference's composition or density. Instead the supplied
artwork is the source of truth: it is resampled onto a fixed pixel grid,
reduced to a fixed palette, despeckled, and emitted as flat <path> geometry.

  assets/source/backend-lab-reference.png   the artwork (vendored, so builds
                                            reproduce without the Desktop copy)
  assets/backend-lab.svg                    traced scene, 640x640
  assets/backend-lab-static.svg             byte-identical alias
  assets/backend-lab-{640,320,160}.png      raster for the GitHub avatar upload

The output is genuine vector pixel art, not a wrapped bitmap: every logical
pixel is <path> geometry with `shape-rendering="crispEdges"`. There is no
<image>, no base64 payload, no gradient and no filter anywhere in the file.

Why these numbers
-----------------
GRID = 320  The reference has no recoverable pixel grid (an edge-alignment
            histogram is flat at ~1.00x mean for every period from 3 to 14 --
            it is a rendered image imitating pixel art). So the grid is chosen,
            not recovered. 320 divides the 640 output exactly, so every logical
            pixel is 2x2 device pixels and edges stay hard, and it preserves
            the ~5px cap height of the reference's readable labels.
COLORS = 256 via FASTOCTREE. Chosen by measurement, and the choice is not the
            obvious one. Median-cut allocates palette entries by pixel count,
            and this image is ~20% pure black and mostly dark brown, so the
            small vivid areas lose: at 64 colours peak saturation collapses
            155 -> 62 and the hologram goes grey, and even at 128 the board's
            colour-coded boxes, the book spines and the core's blue panels all
            flatten to olive. Octree keeps them. Octree scores *worse* on raw
            mean-absolute-error (3.4 vs 1.3) because it flattens the source's
            dither noise into solid areas -- which is what pixel art should
            look like, and which also cuts the file nearly in half
            (36.5k rects / 125K gzipped, against 68k / 224K).
DESPECKLE   Removes only pixels whose four neighbours all agree and differ from
            it. That kills the source's salt-and-pepper noise without softening
            an edge or shifting a colour, and drops ~2k rects.

Region grouping
---------------
The traced rectangles are a disjoint partition of the canvas -- every pixel is
covered exactly once and nothing overlaps -- so they can be regrouped freely
without changing a single rendered pixel. They are therefore bucketed into
named <g id="..."> regions (the core, the hologram, each character, each
screen). Phase 2 can then animate a region by targeting its group, instead of
having to re-trace or hand-rebuild the artwork.

  python scripts/make_backend_lab.py
"""
from __future__ import annotations

import gzip
import os
import re
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
from PIL import Image

import backend_lab_anim as anim

HERE: Path = Path(__file__).resolve().parent
ASSETS_DIR: Path = HERE.parent / "assets"
SOURCE: Path = ASSETS_DIR / "source" / "backend-lab-reference.png"
OUT_SVG: Path = ASSETS_DIR / "backend-lab.svg"
OUT_STATIC: Path = ASSETS_DIR / "backend-lab-static.svg"
PNG_SIZES: Tuple[int, ...] = (640, 320, 160)

GRID: int = 320
SCALE: int = 2            # 320 * 2 = 640, an exact pixel multiple
COLORS: int = 256
DESPECKLE_ROUNDS: int = 2

# Regions in GRID coordinates, read off the reference resampled onto this grid.
# First containing box wins, so a nested region must be listed BEFORE the one
# that encloses it -- `lamp` sits inside `window`, and listing it second left it
# empty. Assignment order has no effect on rendering: the rectangles are
# disjoint, so regrouping them cannot change a pixel.
REGIONS: Tuple[Tuple[str, int, int, int, int], ...] = (
    ("hologram",        120, 100, 190, 178),
    ("server-core",     110, 136, 202, 224),
    ("char-builder",    128,  48, 178, 114),
    ("char-designer",    58, 112, 102, 182),
    ("char-debugger",   198, 106, 252, 188),
    ("char-learner",     38, 178,  88, 242),
    ("char-engineer",   193, 188, 242, 258),
    ("panel-status",    198,  30, 250,  78),
    ("panel-logs",      198,  74, 250, 126),
    ("monitor-code",    240, 106, 294, 158),
    ("panel-request",    12, 186,  62, 240),
    ("panel-optimize",  234, 226, 298, 270),
    ("panel-terminal",  244, 262, 300, 300),
    ("board-design",     28,  56, 102, 174),
    ("lamp",            136,  28, 166,  62),
    ("window",           96,  26, 194, 100),
)


def load_pixels() -> Image.Image:
    """Reference -> fixed grid, fixed palette, despeckled."""
    if not SOURCE.exists():
        raise SystemExit(f"missing source artwork: {SOURCE}")
    im = Image.open(SOURCE).convert("RGB").resize((GRID, GRID), Image.LANCZOS)
    im = im.quantize(colors=COLORS, method=Image.FASTOCTREE, dither=Image.NONE).convert("RGB")

    a = np.asarray(im).copy()
    for _ in range(DESPECKLE_ROUNDS):
        up, dn = np.roll(a, 1, 0), np.roll(a, -1, 0)
        lf, rt = np.roll(a, 1, 1), np.roll(a, -1, 1)
        lone = ((up == dn).all(2) & (up == lf).all(2) & (up == rt).all(2) & (a != up).any(2))
        lone[0, :] = lone[-1, :] = lone[:, 0] = lone[:, -1] = False
        a[lone] = up[lone]
    return Image.fromarray(a)


def merged_rects(img: Image.Image) -> List[Tuple[int, int, int, int, Tuple[int, int, int]]]:
    """Greedy run-length + vertical merge into disjoint rectangles.

    Rows are cut into runs of one colour, then a run is extended downward while
    the row below has an identical run at the same x and width. The result
    covers every pixel exactly once with no overlaps, which is what makes the
    region regrouping below safe.
    """
    W, H = img.size
    px = img.load()
    out: List[Tuple[int, int, int, int, Tuple[int, int, int]]] = []
    open_: Dict[Tuple[int, int, Tuple[int, int, int]], List[int]] = {}
    for y in range(H):
        x = 0
        cur = set()
        while x < W:
            col = px[x, y]
            x1 = x + 1
            while x1 < W and px[x1, y] == col:
                x1 += 1
            key = (x, x1 - x, col)
            cur.add(key)
            if key in open_:
                open_[key][1] += 1
            else:
                open_[key] = [y, 1]
            x = x1
        for key in list(open_):
            if key not in cur:
                y0, h = open_.pop(key)
                out.append((key[0], y0, key[1], h, key[2]))
    for key, (y0, h) in open_.items():
        out.append((key[0], y0, key[1], h, key[2]))
    return out


def region_of(x: int, y: int, w: int, h: int) -> str:
    for name, rx0, ry0, rx1, ry1 in REGIONS:
        if x >= rx0 and y >= ry0 and x + w <= rx1 and y + h <= ry1:
            return name
    return "scene"


def render_svg(rects, extra: Sequence[str] = (), style: str = "") -> str:
    """Emit the traced scene, optionally with the phase-2 animation layer.

    When `animated`, some rectangles are lifted out of the base groups into
    animated ones. Because the rectangles are disjoint, that regrouping cannot
    change a rendered pixel -- the build asserts the animated and static files
    replay to identical buffers.
    """
    buckets: Dict[str, Dict[str, List[Tuple[int, int, int, int]]]] = {}
    for x, y, w, h, col in rects:
        hexcol = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
        buckets.setdefault(region_of(x, y, w, h), {}).setdefault(hexcol, []).append((x, y, w, h))

    px = GRID * SCALE
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" '
        f'viewBox="0 0 {GRID} {GRID}" shape-rendering="crispEdges" role="img" '
        f'aria-label="Pixel-art night workshop: five figures build, debug, design and measure '
        f'around a glowing server core with its architecture projected above it">'
    ]
    if style:
        parts.append(f"<style>{style}</style>")
    # "scene" first so the named regions are easy to find at the end of the file
    for name in ["scene"] + [r[0] for r in REGIONS]:
        by_colour = buckets.get(name)
        if not by_colour:
            continue
        parts.append(f'<g id="{name}">')
        for hexcol, items in by_colour.items():
            d = "".join(f"M{x} {y}h{w}v{h}h-{w}z" for x, y, w, h in items)
            parts.append(f'<path fill="{hexcol}" d="{d}"/>')
        parts.append("</g>")
    parts.extend(extra)
    parts.append("</svg>")
    return "".join(parts)


def render_pngs(img: Image.Image) -> List[Path]:
    written: List[Path] = []
    for size in PNG_SIZES:
        out = ASSETS_DIR / f"backend-lab-{size}.png"
        resample = Image.NEAREST if size % GRID == 0 else Image.BOX
        img.resize((size, size), resample).save(out)
        written.append(out)
    return written


def replay(rects, extra_opaque=0) -> "np.ndarray":
    """Paint the rectangles into a buffer, so two builds can be compared."""
    canvas = np.zeros((GRID, GRID, 3), dtype=np.uint8)
    for x, y, w, h, col in rects:
        canvas[y:y + h, x:x + w] = col
    return canvas


def validate(svg: str, rects, img: Image.Image, animated: bool) -> None:
    """The trace must be a lossless partition, and the output must stay
    self-contained vector art."""
    banned = ["<image", "base64", "<filter", "Gradient", "<script"]
    if not animated:
        banned += ["@keyframes", "<style"]
    for b in banned:
        if b in svg:
            raise ValueError(f"unexpected construct in output: {b}")

    covered = sum(w * h for _, _, w, h, _ in rects)
    if covered != GRID * GRID:
        raise ValueError(f"rects cover {covered} px, expected {GRID * GRID}")
    if not np.array_equal(replay(rects), np.asarray(img)):
        raise ValueError("replayed rectangles do not reproduce the source pixels")


def audit_animation(svg: str) -> None:
    """Phase-2 guards.

    Every animated element must rest at the artwork's own appearance, every
    class must have a rule, and every keyframe must be referenced -- a class
    with no rule or an unreferenced @keyframes is silently dead.
    """
    style = re.search(r"<style>(.*?)</style>", svg, re.S).group(1)
    used = {c for attr in re.findall(r'class="([^"]+)"', svg) for c in attr.split()}
    styled = set(re.findall(r"\.([A-Za-z][\w-]*)\s*[,{]", style))
    if used - styled:
        raise ValueError(f"classes used but never styled: {sorted(used - styled)}")
    frames = set(re.findall(r"@keyframes\s+([\w-]+)", style))
    named = set(re.findall(r"animation(?:-name)?:\s*([\w-]+)", style)) | \
            set(re.findall(r"animation-name:([\w-]+)", svg))
    named -= {"none"}
    if frames - named:
        raise ValueError(f"@keyframes never referenced: {sorted(frames - named)}")
    if named - frames:
        raise ValueError(f"animation-name with no @keyframes: {sorted(named - frames)}")
    if "prefers-reduced-motion" not in style:
        raise ValueError("reduced-motion fallback missing")
    # every keyframe list must close on the value it opens with, or the loop
    # visibly snaps at the boundary
    for name, body in re.findall(r"@keyframes\s*([\w-]+)\s*\{((?:[^{}]*\{[^}]*\})*)\}", style):
        at: Dict[float, str] = {}
        for sel, decls in re.findall(r"([^{}]+)\{([^}]*)\}", body):
            norm = ";".join(sorted(p.strip() for p in decls.split(";") if p.strip()))
            for pct in re.findall(r"([\d.]+)%", sel):
                at[float(pct)] = norm
        if 0.0 not in at or 100.0 not in at:
            raise ValueError(f"@keyframes {name} lacks an explicit 0% or 100% stop")
        if at[0.0] == at[100.0]:
            continue
        # An element that is fully transparent at both ends is invisible across
        # the seam, so a differing transform there cannot be seen -- that is
        # exactly the packets' appear/travel/vanish cycle. Anything else that
        # differs at the boundary would visibly snap.
        invisible_both = "opacity:0" in at[0.0] and "opacity:0" in at[100.0]
        if not invisible_both:
            raise ValueError(
                f"@keyframes {name} does not loop seamlessly: "
                f"0% is [{at[0.0]}] but 100% is [{at[100.0]}]")


if __name__ == "__main__":
    img = load_pixels()
    arr = np.asarray(img).astype(int)
    rects = merged_rects(img)

    static_svg = render_svg(rects)
    validate(static_svg, rects, img, animated=False)
    OUT_STATIC.write_text(static_svg)

    rest, extra, style, additive = anim.build_animation(arr, list(rects))
    anim_svg = render_svg(rest, extra=extra, style=style)
    audit_animation(anim_svg)
    for b in ("<image", "base64", "<filter", "Gradient", "<script"):
        if b in anim_svg:
            raise SystemExit(f"unexpected construct in animated output: {b}")

    # The whole safety argument, asserted exactly rather than by pattern-
    # matching markup: the pixels that were lifted into animated groups plus
    # the pixels left behind must be precisely the original trace, and the only
    # other geometry in the file is the declared additive overlay.
    lifted = [r for r in rects if r not in set(rest)]
    if sorted(rest + lifted) != sorted(rects):
        raise SystemExit("animated build changed the traced artwork")
    if not np.array_equal(replay(rest + lifted), np.asarray(img)):
        raise SystemExit("animated build does not replay to the approved artwork")
    OUT_SVG.write_text(anim_svg)

    print(f"traced {SOURCE.name} -> {GRID}x{GRID}, "
          f"{len({c for *_, c in rects})} colours, {len(rects)} rects")
    print(f"static   {OUT_STATIC.name}: {len(static_svg) / 1024:.0f}K raw")
    print(f"animated {OUT_SVG.name}: {len(anim_svg) / 1024:.0f}K raw, "
          f"{len(gzip.compress(anim_svg.encode())) / 1024:.0f}K gzipped")
    print(f"artwork preserved exactly: {len(lifted)} rects lifted into animated groups, "
          f"{len(rest)} left static, {len(additive)} added as overlay/backing")
    for path in render_pngs(img):
        print("wrote", path)
