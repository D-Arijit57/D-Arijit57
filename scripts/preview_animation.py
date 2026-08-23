"""
Render frames of the animated SVG without a browser.

GitHub serves README images through <img>, so the animation is CSS keyframes,
and there is no headless renderer in this project that executes them. This
script is the substitute: it parses the emitted SVG, evaluates the stylesheet
at a given time, and composites the result exactly as an SVG renderer would --
static paths first, then each animated group alpha-blended at its computed
opacity and translation.

It is a verification tool, not part of the asset build. Use it to check that a
change is subtle, that the loop has no seam, and that nothing outside an
intended target ever moves.

  python scripts/preview_animation.py                 # contact sheet + motion map
  python scripts/preview_animation.py 3.25            # one frame at t=3.25s
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SVG = HERE.parent / "assets" / "backend-lab.svg"
GRID = 320
OUT = Path("/tmp")


# ---- stylesheet ------------------------------------------------------------

def parse_keyframes(style: str) -> Dict[str, List[Tuple[float, Dict[str, str]]]]:
    out: Dict[str, List[Tuple[float, Dict[str, str]]]] = {}
    for name, body in re.findall(r"@keyframes\s*([\w-]+)\s*\{((?:[^{}]*\{[^}]*\})*)\}", style):
        stops: List[Tuple[float, Dict[str, str]]] = []
        for sel, decls in re.findall(r"([^{}]+)\{([^}]*)\}", body):
            d = {}
            for part in decls.split(";"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    d[k.strip()] = v.strip()
            for pct in re.findall(r"([\d.]+)%", sel):
                stops.append((float(pct), d))
        out[name] = sorted(stops)
    return out


def parse_classes(style: str) -> Dict[str, Dict[str, str]]:
    """Class -> declarations, for the non-@keyframes rules."""
    flat = re.sub(r"@keyframes\s*[\w-]+\s*\{(?:[^{}]*\{[^}]*\})*\}", "", style)
    flat = re.sub(r"@media[^{]*\{.*?\n\}", "", flat, flags=re.S)
    out: Dict[str, Dict[str, str]] = {}
    for sel, decls in re.findall(r"([^{}]+)\{([^}]*)\}", flat):
        d = {}
        for part in decls.split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                d[k.strip()] = v.strip()
        for cls in re.findall(r"\.([A-Za-z][\w-]*)", sel):
            out.setdefault(cls, {}).update(d)
    return out


def expand_shorthand(d: Dict[str, str]) -> Dict[str, str]:
    """`animation: name 4.5s ease-in-out infinite` -> individual properties."""
    out = dict(d)
    sh = d.get("animation")
    if sh:
        for tok in sh.split():
            if re.fullmatch(r"[\d.]+m?s", tok):
                key = "animation-duration" if "animation-duration" not in out else "animation-delay"
                out[key] = tok
            elif tok in ("linear", "ease", "ease-in", "ease-out", "ease-in-out") or tok.startswith("steps"):
                out["animation-timing-function"] = tok
            elif tok not in ("infinite",):
                out["animation-name"] = tok
    return out


def seconds(v: Optional[str]) -> float:
    if not v:
        return 0.0
    v = v.strip()
    return float(v[:-2]) / 1000 if v.endswith("ms") else float(v.rstrip("s"))


def ease(p: float, fn: str, steps_n: int = 1) -> float:
    if fn.startswith("steps"):
        m = re.search(r"steps\(\s*(?:var\(--s\)|(\d+))", fn)
        n = int(m.group(1)) if m and m.group(1) else steps_n
        n = max(1, n)
        return min(1.0, np.floor(p * n) / n)
    if fn == "linear":
        return p
    # ease-in-out ~ cubic-bezier(.42,0,.58,1); smoothstep is close enough here
    return p * p * (3 - 2 * p)


def sample(stops: Sequence[Tuple[float, Dict[str, str]]], p: float) -> Dict[str, str]:
    """Interpolate opacity, snap everything else to the preceding stop."""
    pct = p * 100
    prev = stops[0]
    nxt = stops[-1]
    for i, (k, d) in enumerate(stops):
        if k <= pct:
            prev = (k, d)
        if k >= pct:
            nxt = (k, d)
            break
    out = dict(prev[1])
    if nxt[0] > prev[0] and "opacity" in prev[1] and "opacity" in nxt[1]:
        t = (pct - prev[0]) / (nxt[0] - prev[0])
        out["opacity"] = str(float(prev[1]["opacity"]) + t * (float(nxt[1]["opacity"]) - float(prev[1]["opacity"])))
    if nxt[0] > prev[0] and "transform" in prev[1] and "transform" in nxt[1]:
        def xy(s):
            m = re.search(r"translate\(\s*(-?[\d.]+)p?x?\s*,\s*(-?[\d.]+)p?x?\s*\)", s)
            return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)
        t = (pct - prev[0]) / (nxt[0] - prev[0])
        (ax, ay), (bx, by) = xy(prev[1]["transform"]), xy(nxt[1]["transform"])
        out["transform"] = f"translate({ax + t * (bx - ax)}px,{ay + t * (by - ay)}px)"
    return out


# ---- document --------------------------------------------------------------

def path_rects(d: str) -> List[Tuple[int, int, int, int]]:
    return [(int(x), int(y), int(w), int(h))
            for x, y, w, h in re.findall(r"M(-?\d+) (-?\d+)h(\d+)v(\d+)h", d)]


def hexrgb(c: str) -> Tuple[int, int, int]:
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


class Element:
    def __init__(self, rects, colors, decls):
        self.rects = rects
        self.colors = colors
        self.decls = decls


def parse_svg(svg: str):
    style = re.search(r"<style>(.*?)</style>", svg, re.S)
    style = style.group(1) if style else ""
    kf, classes = parse_keyframes(style), parse_classes(style)

    elements: List[Element] = []
    pos = 0
    # walk top-level groups in document order
    for m in re.finditer(r'<g id="([^"]+)"([^>]*)>', svg):
        gid, attrs = m.group(1), m.group(2)
        # find this group's extent (handles one level of nesting)
        start = m.end()
        depth = 1
        i = start
        while depth:
            nxt = re.search(r"<g\b[^>]*>|</g>", svg[i:])
            if not nxt:
                break
            depth += 1 if nxt.group(0).startswith("<g") else -1
            i += nxt.end()
        body = svg[start:i]
        if re.search(r'<g\b', body):
            continue  # container; its children are visited separately
        cls = re.search(r'class="([^"]+)"', attrs)
        inline = re.search(r'style="([^"]+)"', attrs)
        decls: Dict[str, str] = {}
        for c in (cls.group(1).split() if cls else []):
            decls.update(expand_shorthand(classes.get(c, {})))
        if inline:
            for part in inline.group(1).split(";"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    decls[k.strip()] = v.strip()
        rects, colors = [], []
        for pm in re.finditer(r'<path fill="(#[0-9a-f]{6})" d="([^"]+)"', body):
            for r in path_rects(pm.group(2)):
                rects.append(r)
                colors.append(hexrgb(pm.group(1)))
        if rects:
            elements.append(Element(rects, colors, decls))

    for rm in re.finditer(r'<rect class="([^"]+)"([^>]*)/>', svg):
        attrs = rm.group(2)
        g = lambda k: re.search(rf'{k}="([^"]+)"', attrs)
        decls: Dict[str, str] = {}
        for c in rm.group(1).split():
            decls.update(expand_shorthand(classes.get(c, {})))
        st = g("style")
        if st:
            for part in st.group(1).split(";"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    decls[k.strip()] = v.strip()
        x, y = int(g("x").group(1)), int(g("y").group(1))
        w, h = int(g("width").group(1)), int(g("height").group(1))
        elements.append(Element([(x, y, w, h)], [hexrgb(g("fill").group(1))], decls))
    return elements, kf


def render(elements, kf, t: float) -> np.ndarray:
    buf = np.zeros((GRID, GRID, 3), float)
    for el in elements:
        d = el.decls
        alpha, dx, dy = 1.0, 0, 0
        name = d.get("animation-name")
        if name and name in kf:
            dur = seconds(d.get("animation-duration")) or 1.0
            delay = seconds(d.get("animation-delay"))
            p = ((t - delay) / dur) % 1.0
            if t < delay:
                p = 0.0
            fnraw = d.get("animation-timing-function", "linear")
            sm = re.search(r"--s:\s*(\d+)", ";".join(f"{k}:{v}" for k, v in d.items()))
            p = ease(p, fnraw, int(sm.group(1)) if sm else 1)
            vals = sample(kf[name], p)
            if "opacity" in vals:
                alpha = float(vals["opacity"])
            if "transform" in vals:
                mm = re.search(r"translate\(\s*(-?[\d.]+)px\s*,\s*(-?[\d.]+)px\s*\)", vals["transform"])
                if mm:
                    dx, dy = int(round(float(mm.group(1)))), int(round(float(mm.group(2))))
        elif "opacity" in d:
            alpha = float(d["opacity"])
        if alpha <= 0:
            continue
        for (x, y, w, h), col in zip(el.rects, el.colors):
            x += dx
            y += dy
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(GRID, x + w), min(GRID, y + h)
            if x1 <= x0 or y1 <= y0:
                continue
            region = buf[y0:y1, x0:x1]
            buf[y0:y1, x0:x1] = region * (1 - alpha) + np.array(col, float) * alpha
    return buf.round().astype(np.uint8)


def main() -> None:
    svg = SVG.read_text()
    elements, kf = parse_svg(svg)
    print(f"parsed {len(elements)} drawable elements, {len(kf)} keyframe sets")

    if len(sys.argv) > 1:
        t = float(sys.argv[1])
        Image.fromarray(render(elements, kf, t)).resize((640, 640), Image.NEAREST) \
            .save(OUT / f"frame-{t:.2f}.png")
        print("wrote", OUT / f"frame-{t:.2f}.png")
        return

    times = [round(i * 15 / 12, 2) for i in range(12)]
    frames = [render(elements, kf, t) for t in times]

    sheet = Image.new("RGB", (4 * 320 + 15, 3 * 320 + 10), (10, 12, 16))
    for i, f in enumerate(frames):
        sheet.paste(Image.fromarray(f), ((i % 4) * 325, (i // 4) * 325))
    sheet.save(OUT / "anim-sheet.png")

    stack = np.stack(frames).astype(int)
    motion = np.abs(stack - stack[0]).sum(3).max(0)
    heat = np.zeros((GRID, GRID, 3), np.uint8)
    heat[..., 0] = np.clip(motion, 0, 255)
    heat[..., 1] = np.clip(motion // 3, 0, 255)
    base = np.asarray(Image.fromarray(frames[0]).convert("L").convert("RGB")).astype(int)
    blend = np.clip(base * 0.5 + heat * 0.9, 0, 255).astype(np.uint8)
    Image.fromarray(blend).resize((640, 640), Image.NEAREST).save(OUT / "anim-motion.png")

    moving = int((motion > 6).sum())
    print(f"pixels that ever change: {moving} of {GRID * GRID} ({100 * moving / GRID / GRID:.2f}%)")
    print(f"peak per-pixel change: {int(motion.max())} (sum over RGB, max 765)")
    print("wrote", OUT / "anim-sheet.png", "and", OUT / "anim-motion.png")


if __name__ == "__main__":
    main()
