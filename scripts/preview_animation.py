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
    """#rrggbb, and the #rgb shorthand the backdrop rect uses."""
    if len(c) == 4:
        return tuple(int(c[i] * 2, 16) for i in (1, 2, 3))
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _walk_count(node):
    yield node
    for c in node.children:
        yield from _walk_count(c)


class Node:
    """One <g>, <path> or <rect>, with its children (for <g>)."""
    __slots__ = ("tag", "attrs", "children", "rects", "colors")

    def __init__(self, tag: str, attrs: Dict[str, str]):
        self.tag = tag
        self.attrs = attrs
        self.children: List["Node"] = []
        self.rects: List[Tuple[int, int, int, int]] = []
        self.colors: List[Tuple[int, int, int]] = []


def parse_svg(svg: str) -> Tuple[Node, Dict]:
    """Build a real tree, not a flat element list.

    This matters as of the reveal layer: each region's base content and its
    idle-animated overlays are now nested inside one tier wrapper
    (`<g class="rv rv-core">`) so the wrapper's fade and the child's own idle
    pulse compose the way a browser actually composites nested opacity -- by
    multiplication. A flat, single-level parse (the original version of this
    script) cannot see that nesting and either double-counts or ignores one of
    the two animations; this walks the tree and multiplies alpha / adds
    translation down through however many levels are present.
    """
    style_m = re.search(r"<style>(.*?)</style>", svg, re.S)
    style = style_m.group(1) if style_m else ""
    kf, classes = parse_keyframes(style), parse_classes(style)

    def attrs_of(tag_src: str) -> Dict[str, str]:
        return {k: v for k, v in re.findall(r'([\w-]+)="([^"]*)"', tag_src)}

    root = Node("root", {})
    stack = [root]
    for m in re.finditer(r'<g\b[^>]*>|</g>|<path\b[^>]*/>|<rect\b[^>]*/>', svg):
        tok = m.group(0)
        if tok == "</g>":
            if len(stack) > 1:
                stack.pop()
            continue
        if tok.startswith("<g"):
            node = Node("g", attrs_of(tok))
            stack[-1].children.append(node)
            stack.append(node)
            continue
        # self-closing <path .../> or <rect .../>
        a = attrs_of(tok)
        node = Node("path" if tok.startswith("<path") else "rect", a)
        if node.tag == "path":
            fill = a.get("fill", "#000000")
            for r in path_rects(a.get("d", "")):
                node.rects.append(r)
                node.colors.append(hexrgb(fill))
        else:
            x, y = int(float(a.get("x", 0))), int(float(a.get("y", 0)))
            w, h = int(float(a.get("width", 0))), int(float(a.get("height", 0)))
            node.rects.append((x, y, w, h))
            node.colors.append(hexrgb(a.get("fill", "#000000")))
        stack[-1].children.append(node)
    return root, {"kf": kf, "classes": classes}


def _own_decls(node: "Node", classes: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    decls: Dict[str, str] = {}
    for c in node.attrs.get("class", "").split():
        decls.update(expand_shorthand(classes.get(c, {})))
    style_attr = node.attrs.get("style")
    if style_attr:
        for part in style_attr.split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                decls[k.strip()] = v.strip()
    return decls


def _own_state(decls: Dict[str, str], kf: Dict, t: float) -> Tuple[float, int, int]:
    """This node's OWN (alpha, dx, dy) at time t -- before composing with any
    ancestor. Same animation/keyframe evaluation as before, just factored out
    so the tree walk can call it once per node."""
    alpha, dx, dy = 1.0, 0, 0
    name = decls.get("animation-name")
    count_raw = decls.get("animation-iteration-count", "infinite")
    finite = count_raw != "infinite"
    count = float(count_raw) if finite else None
    if name and name in kf:
        dur = seconds(decls.get("animation-duration")) or 1.0
        delay = seconds(decls.get("animation-delay"))
        elapsed = t - delay
        if finite and elapsed >= count * dur:
            # Animation finished. Without 'forwards'/'both' fill-mode the
            # element reverts to its non-animated style -- opacity:1 unless
            # this node's own (non-animation) declarations say otherwise.
            if "opacity" in decls:
                alpha = float(decls["opacity"])
        else:
            p = 0.0 if elapsed < 0 else (elapsed / dur) if finite else ((elapsed / dur) % 1.0)
            p = min(1.0, p)
            fnraw = decls.get("animation-timing-function", "linear")
            sm = re.search(r"--s:\s*(\d+)", ";".join(f"{k}:{v}" for k, v in decls.items()))
            p = ease(p, fnraw, int(sm.group(1)) if sm else 1)
            vals = sample(kf[name], p)
            if "opacity" in vals:
                alpha = float(vals["opacity"])
            if "transform" in vals:
                mm = re.search(r"translate\(\s*(-?[\d.]+)px\s*,\s*(-?[\d.]+)px\s*\)", vals["transform"])
                if mm:
                    dx, dy = int(round(float(mm.group(1)))), int(round(float(mm.group(2))))
    elif "opacity" in decls:
        alpha = float(decls["opacity"])
    return alpha, dx, dy


def render(root: Node, ctx: Dict, t: float) -> np.ndarray:
    """Depth-first walk, composing opacity by multiplication and translation
    by addition through nesting -- exactly how a browser composites nested
    CSS opacity/transform, and exact (not approximate) here because every
    transform in this file is a pure translate(), which commutes."""
    kf, classes = ctx["kf"], ctx["classes"]
    buf = np.zeros((GRID, GRID, 3), float)

    def walk(node: Node, alpha: float, dx: int, dy: int) -> None:
        if node.tag != "root":
            decls = _own_decls(node, classes)
            la, ldx, ldy = _own_state(decls, kf, t)
            alpha *= la
            dx += ldx
            dy += ldy
            if alpha <= 0:
                return
        if node.rects:
            for (x, y, w, h), col in zip(node.rects, node.colors):
                x0, y0 = max(0, x + dx), max(0, y + dy)
                x1, y1 = min(GRID, x + dx + w), min(GRID, y + dy + h)
                if x1 <= x0 or y1 <= y0:
                    continue
                region = buf[y0:y1, x0:x1]
                buf[y0:y1, x0:x1] = region * (1 - alpha) + np.array(col, float) * alpha
        for child in node.children:
            walk(child, alpha, dx, dy)

    walk(root, 1.0, 0, 0)
    return buf.round().astype(np.uint8)


def main() -> None:
    svg = SVG.read_text()
    root, ctx = parse_svg(svg)
    n_nodes = sum(1 for _ in _walk_count(root))
    print(f"parsed {n_nodes} nodes, {len(ctx['kf'])} keyframe sets")

    if len(sys.argv) > 1:
        t = float(sys.argv[1])
        Image.fromarray(render(root, ctx, t)).resize((640, 640), Image.NEAREST) \
            .save(OUT / f"frame-{t:.2f}.png")
        print("wrote", OUT / f"frame-{t:.2f}.png")
        return

    times = [round(i * 15 / 12, 2) for i in range(12)]
    frames = [render(root, ctx, t) for t in times]

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
