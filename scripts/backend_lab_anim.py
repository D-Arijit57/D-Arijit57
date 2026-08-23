"""
The animation layer for the backend-lab scene. Phase 2.

The traced artwork is the source of truth and is NOT redrawn, recomposed or
duplicated here. This module only decides which of the already-traced pixels
get lifted into their own animated <g>, and what CSS drives them.

Why lifting pixels is safe
--------------------------
make_backend_lab.merged_rects() produces a *disjoint partition*: every pixel of
the 320x320 canvas is covered exactly once and no two rectangles overlap. So a
rectangle can be moved from the base group into an animated group without
changing a single rendered pixel -- there is nothing underneath it to reveal and
nothing on top of it to occlude. The build asserts this both ways: the animated
file and the static file must replay to byte-identical pixel buffers.

A rectangle is lifted only if *every* pixel it covers is inside the target mask.
A run that straddles a target boundary stays in the base layer. That costs a few
stray pixels of animation and buys a guarantee that nothing outside a target can
ever move.

Two kinds of animation
----------------------
1. BRIGHTNESS -- opacity on lifted pixels. Cheap, crisp, and because every
   element rests at opacity 1, `prefers-reduced-motion` and the static build
   both collapse to exactly the approved frame.
2. TWO-FRAME SPRITE FLIP -- for hands. The vacated pixels are refilled with the
   background colour sampled from the image itself, and the hand is redrawn one
   pixel lower; the whole patch sits at opacity 0 and flips to 1 with
   steps(1,end). That is how a pixel artist animates a sprite: two discrete
   frames, no tweening, no sub-pixel positions. Nothing is ever translated by a
   fractional pixel.

Data packets are the only new geometry in the file. They rest at opacity 0, so
the static frame is untouched, and they move with steps() over integer offsets
so they hop pixel to pixel instead of gliding.

Every keyframe list starts and ends on the same value, so each cycle is
individually seamless; the durations are mutually non-aligning so the room never
resets as a whole.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

Rect = Tuple[int, int, int, int, Tuple[int, int, int]]
Mask = np.ndarray

# Every idle animation below is offset by this many seconds, so the very first
# thing a viewer sees is the one-shot reveal (make_backend_lab.REVEAL, which
# ends at the same instant) rather than a mid-cycle LED blink racing the fade-
# in. The reveal and this offset are two names for the same number by design;
# keeping the constant here (rather than duplicated in make_backend_lab.py)
# means there is exactly one place to change it.
REVEAL_END: float = 1.60

# ---- target geometry -------------------------------------------------------
# All boxes are (x0, y0, x1, y1) in 320-grid coordinates, read off the traced
# artwork with a labelled overlay (see the build notes in the report).

HOLO_REGION = (120, 100, 190, 178)
HOLO_NODES: Tuple[Tuple[int, int, int, int], ...] = (
    (146, 110, 162, 127),   # API, top
    (146, 129, 162, 146),   # SERVICE, centre
    (132, 132, 148, 149),   # CACHE, left
    (160, 132, 176, 149),   # DB, right
    (145, 144, 162, 161),   # child of SERVICE, bottom
)
LED_REGIONS = ((112, 162, 200, 222), (244, 32, 282, 84))
CURSOR_BOX = (267, 281, 275, 283)
LAMPS = (("pendant", (136, 28, 170, 62), 6.2, REVEAL_END + 0.0),
         ("desk", (274, 108, 308, 150), 7.4, REVEAL_END + 2.1))
WINDOW_REGIONS = ((104, 36, 134, 90), (176, 36, 190, 90), (104, 36, 190, 46))
LOGS_PANEL = (198, 74, 250, 126)
LOGS_LINE = (200, 110, 248, 113)   # the last "200 OK" -- reads as a new log arriving
CODE_PANEL = (240, 106, 294, 158)
CODE_LINE = (242, 128, 292, 132)   # one line of the code listing

# hand -> (search box, cycle seconds, phase offset). Boxes were verified against
# a skin mask; the designer's is the small 6px blob of the raised pointing hand,
# deliberately tight so the tan whiteboard behind it cannot be picked up.
HANDS: Dict[str, Tuple[Tuple[int, int, int, int], float, float]] = {
    "builder":  ((155, 92, 168, 103), 2.6, REVEAL_END + 0.0),
    "debugger": ((236, 148, 250, 160), 3.1, REVEAL_END + 1.3),
    "learner":  ((72, 200, 86, 213), 4.3, REVEAL_END + 0.6),
    "engineer": ((206, 203, 222, 213), 3.8, REVEAL_END + 2.4),
    "designer": ((65, 140, 71, 146), 4.9, REVEAL_END + 3.2),
}

# packets: (class, start x, start y, dx, dy, steps, duration, delay)
PACKETS: Tuple[Tuple[str, int, int, int, int, int, float, float], ...] = (
    ("pk-stem",  152, 125,   0,  6, 6, 2.4, REVEAL_END + 0.0),
    ("pk-left",  150, 132, -12,  4, 4, 2.8, REVEAL_END + 1.6),
    ("pk-right", 156, 132,  12,  4, 4, 3.1, REVEAL_END + 3.9),
)


def _comps(mask: Mask, diag: bool = False) -> List[List[Tuple[int, int]]]:
    seen = np.zeros(mask.shape, bool)
    nbr = ((1, 0), (-1, 0), (0, 1), (0, -1))
    if diag:
        nbr += ((1, 1), (-1, -1), (1, -1), (-1, 1))
    out: List[List[Tuple[int, int]]] = []
    ys, xs = np.where(mask)
    for sy, sx in zip(ys, xs):
        if seen[sy, sx]:
            continue
        stack = [(sy, sx)]
        seen[sy, sx] = True
        pix: List[Tuple[int, int]] = []
        while stack:
            y, x = stack.pop()
            pix.append((y, x))
            for dy, dx in nbr:
                ny, nx = y + dy, x + dx
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] \
                        and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append(pix)
    return out


def _blank(a: np.ndarray) -> Mask:
    return np.zeros(a.shape[:2], bool)


def _box(mask_src: Mask, box: Tuple[int, int, int, int], a: np.ndarray) -> Mask:
    x0, y0, x1, y1 = box
    m = _blank(a)
    m[y0:y1, x0:x1] = mask_src[y0:y1, x0:x1]
    return m


# ---- target masks ----------------------------------------------------------

def holo_mask(a: np.ndarray) -> Mask:
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    return _box((G > 110) & (G > R + 30) & (G > B + 70), HOLO_REGION, a)


# LED_REGIONS[0] is the server-core drum (reveal tier rv-core); [1] is the
# wall-mounted rack (part of the room's fixtures, tier rv-fixtures). LEDs need
# to reveal with their own housing, not as one undifferentiated group, so
# led_masks tags each cluster with the tier it belongs to.
LED_REGION_TIER = ("rv-core", "rv-fixtures")


def led_masks(a: np.ndarray) -> List[Tuple[str, Mask]]:
    """Small saturated clusters only, each tagged with its reveal tier.

    The size cap is what separates a status LED from the core's glowing pool --
    the pool is one huge bright component and would otherwise be swept up and
    made to blink, which would be very wrong.
    """
    bright = (a.max(2) > 95) & ((a.max(2) - a.min(2)) > 50)
    out: List[Tuple[str, Mask]] = []
    for box, tier in zip(LED_REGIONS, LED_REGION_TIER):
        reg = _box(bright, box, a)
        for pix in _comps(reg):
            if len(pix) <= 6:
                m = _blank(a)
                for y, x in pix:
                    m[y, x] = True
                out.append((tier, m))
    return out


def window_masks(a: np.ndarray) -> List[Mask]:
    """Lit windows in the panes only -- the boxes deliberately exclude the
    column the builder's head occupies, so a character can never blink."""
    lit = (a.max(2) > 105) & (((a[:, :, 0] > a[:, :, 2] + 20)) | (a[:, :, 2] > a[:, :, 0] + 30))
    out: List[Mask] = []
    for box in WINDOW_REGIONS:
        reg = _box(lit, box, a)
        for pix in _comps(reg):
            if len(pix) <= 6:
                m = _blank(a)
                for y, x in pix:
                    m[y, x] = True
                out.append(m)
    return out


def lamp_mask(a: np.ndarray, box) -> Mask:
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    return _box((R > 150) & (G > 105) & (R > B + 55), box, a)


def panel_text_mask(a: np.ndarray, panel: Tuple[int, int, int, int],
                    band: Tuple[int, int, int, int]) -> Mask:
    """Bright text pixels inside one narrow band of a dark panel.

    The threshold is relative to the *panel's* own median brightness, not a
    fixed colour: the LOGS panel is dim green (peak G of 104) while the code
    monitor is multi-coloured syntax highlighting with almost no green, so a
    hue test finds one and misses the other. The band is given explicitly
    because the code lines sit on consecutive rows with no blank row between
    them, so they cannot be split apart automatically.
    """
    px0, py0, px1, py1 = panel
    lum_panel = a[py0:py1, px0:px1].sum(2)
    thresh = float(np.median(lum_panel)) + 60.0
    bx0, by0, bx1, by1 = band
    m = _blank(a)
    m[by0:by1, bx0:bx1] = a[by0:by1, bx0:bx1].sum(2) > thresh
    return m


def skin_mask(a: np.ndarray, box) -> Mask:
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    return _box((R > 95) & (R > G + 18) & (G > B + 8) & (R > B + 45), box, a)


# ---- lifting ---------------------------------------------------------------

def backing_rects(a: np.ndarray, mask: Mask) -> List[Rect]:
    """What sits *behind* the pixels we are about to fade.

    Lifting a rectangle into an animated group does not make a hole -- the pixel
    is still painted. But at opacity < 1 it blends with whatever is behind it,
    and behind it is nothing, so it would blend with the *page* background:
    an LED would fade toward GitHub's backdrop instead of toward its own dark
    panel, and would look wrong outright on a light background.

    So each faded pixel gets a backing painted underneath, coloured by the
    nearest pixel that is not being animated. Dimming then blends toward the
    local surroundings -- the dark rack behind an LED, the glow around a
    hologram strut -- which is both correct and independent of the page theme.
    At rest the animated copy is fully opaque and hides the backing entirely,
    so the static frame is untouched.
    """
    col = a.astype(np.uint8).copy()
    known = ~mask
    todo = mask.copy()
    while todo.any():
        filled = np.zeros_like(todo)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            src_known = np.roll(known, (dy, dx), (0, 1))
            src_col = np.roll(col, (dy, dx), (0, 1))
            take = todo & src_known & ~filled
            col[take] = src_col[take]
            filled |= take
        if not filled.any():
            break
        todo &= ~filled
        known |= filled

    out: List[Rect] = []
    ys, xs = np.where(mask)
    for y in sorted(set(int(v) for v in ys)):
        row = sorted(int(v) for v in xs[ys == y])
        start = prev = row[0]
        for x in row[1:] + [None]:
            same = x is not None and x == prev + 1 and tuple(col[y, x]) == tuple(col[y, prev])
            if same:
                prev = x
                continue
            out.append((start, y, prev - start + 1, 1, tuple(int(v) for v in col[y, start])))
            if x is None:
                break
            start = prev = x
    return out


def mark(faded: Mask, lifted: Sequence[Rect]) -> None:
    """Record exactly the pixels that were lifted, so the backing covers those
    and only those.

    Building this from the *target mask* instead is wrong and was: a mask pixel
    belonging to a rectangle that straddles the mask boundary is never lifted,
    stays in the base layer, and is drawn *before* the backing -- so the backing
    would paint over live artwork. That silently corrupted 7 pixels.
    """
    for x, y, w, h, _ in lifted:
        faded[y:y + h, x:x + w] = True


def lift(rects: List[Rect], mask: Mask) -> Tuple[List[Rect], List[Rect]]:
    """Split rects into (fully inside mask, everything else).

    Partial overlaps stay behind on purpose: a run that straddles the target
    boundary is left static, so animation can never bleed outside a target.
    """
    inside: List[Rect] = []
    rest: List[Rect] = []
    for r in rects:
        x, y, w, h, _ = r
        (inside if mask[y:y + h, x:x + w].all() else rest).append(r)
    return inside, rest


def rects_to_path(items: Sequence[Tuple[int, int, int, int]]) -> str:
    return "".join(f"M{x} {y}h{w}v{h}h-{w}z" for x, y, w, h in items)


def group_svg(rects: Sequence[Rect], gid: str, cls: str = "", style: str = "") -> str:
    by: Dict[str, List[Tuple[int, int, int, int]]] = {}
    for x, y, w, h, col in rects:
        by.setdefault(f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}", []).append((x, y, w, h))
    attrs = f' id="{gid}"'
    if cls:
        attrs += f' class="{cls}"'
    if style:
        attrs += f' style="{style}"'
    body = "".join(f'<path fill="{c}" d="{rects_to_path(v)}"/>' for c, v in by.items())
    return f"<g{attrs}>{body}</g>"


# ---- two-frame hand flip ---------------------------------------------------

def hand_frame2(a: np.ndarray, mask: Mask, dy: int = 1) -> List[Rect]:
    """Build the second frame of a hand: erase, then redraw one pixel lower.

    Vacated pixels are refilled with the colour immediately above the hand in
    the same column -- sampled from the artwork itself, so the fill matches the
    desk/device the hand rests on rather than being a guessed flat colour.
    """
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return []
    px: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
    for x in np.unique(xs):
        col = sorted(ys[xs == x])
        src_y = max(0, col[0] - 1)
        bg = tuple(int(v) for v in a[src_y, x])
        for y in col:
            px[(int(x), int(y))] = bg
    for y, x in zip(ys, xs):
        px[(int(x), int(y) + dy)] = tuple(int(v) for v in a[y, x])

    # run-merge the patch horizontally so it stays a handful of rects
    out: List[Rect] = []
    for y in sorted({p[1] for p in px}):
        row = sorted(x for (x, yy) in px if yy == y)
        run_start = prev = row[0]
        for x in row[1:] + [None]:
            if x is not None and x == prev + 1 and px[(x, y)] == px[(prev, y)]:
                prev = x
                continue
            out.append((run_start, y, prev - run_start + 1, 1, px[(run_start, y)]))
            if x is None:
                break
            run_start = prev = x
    return out


# ---- CSS -------------------------------------------------------------------

def css(led_specs: Sequence[Tuple[float, float]], win_specs: Sequence[Tuple[float, float]]) -> str:
    """Every keyframe list closes on its opening value, so each cycle is
    seamless on its own; the periods are mutually non-aligning so the scene as
    a whole never snaps back to a start frame."""
    return """
@keyframes holoBreath{0%,100%{opacity:.80}50%{opacity:1}}
@keyframes holoNode{0%,100%{opacity:.72}45%{opacity:1}}
@keyframes led{0%,38%{opacity:1}46%,86%{opacity:.22}94%,100%{opacity:1}}
@keyframes ledSoft{0%,100%{opacity:.85}50%{opacity:1}}
@keyframes cursor{0%,48%{opacity:1}50%,98%{opacity:0}100%{opacity:1}}
@keyframes lamp{0%,100%{opacity:1}18%{opacity:.97}31%{opacity:1}54%{opacity:.94}61%{opacity:.99}78%{opacity:.96}88%{opacity:1}}
@keyframes winLight{0%,44%{opacity:1}52%,72%{opacity:.25}80%,100%{opacity:1}}
@keyframes logLine{0%,10%{opacity:.25}18%,88%{opacity:1}96%,100%{opacity:.25}}
@keyframes codeLine{0%,100%{opacity:1}40%,52%{opacity:.35}}
@keyframes tap2{0%,10%{opacity:0}14%,24%{opacity:1}28%,44%{opacity:0}48%,58%{opacity:1}62%,100%{opacity:0}}
@keyframes tap1{0%,58%{opacity:0}64%,76%{opacity:1}82%,100%{opacity:0}}
@keyframes pkStem{0%,6%{opacity:0;transform:translate(0,0)}12%{opacity:1}70%{opacity:1}
  76%,100%{opacity:0;transform:translate(0,6px)}}
@keyframes pkLeft{0%,6%{opacity:0;transform:translate(0,0)}12%{opacity:1}70%{opacity:1}
  76%,100%{opacity:0;transform:translate(-12px,4px)}}
@keyframes pkRight{0%,6%{opacity:0;transform:translate(0,0)}12%{opacity:1}70%{opacity:1}
  76%,100%{opacity:0;transform:translate(12px,4px)}}

.holo{animation:holoBreath 4.5s ease-in-out infinite}
.node{animation-name:holoNode;animation-timing-function:ease-in-out;animation-iteration-count:infinite}
.led{animation-name:led;animation-timing-function:steps(1,end);animation-iteration-count:infinite}
.ledSoft{animation-name:ledSoft;animation-timing-function:ease-in-out;animation-iteration-count:infinite}
.cursor{animation:cursor 1.06s steps(1,end) infinite}
.lamp{animation-name:lamp;animation-timing-function:ease-in-out;animation-iteration-count:infinite}
.win{animation-name:winLight;animation-timing-function:steps(1,end);animation-iteration-count:infinite}
.logline{animation:logLine 6.7s ease-in-out infinite}
.codeline{animation:codeLine 5.3s ease-in-out infinite}
.tap{animation-timing-function:steps(1,end);animation-iteration-count:infinite;opacity:0}
.pk{opacity:0;animation-timing-function:steps(var(--s),end);animation-iteration-count:infinite}

@media (prefers-reduced-motion:reduce){
  .holo,.node,.led,.ledSoft,.cursor,.lamp,.win,.logline,.codeline{animation:none;opacity:1}
  .tap,.pk{animation:none;opacity:0}
}
""".strip()


def build_animation(a: np.ndarray, rects: List[Rect]):
    """Lift animated pixels out of `rects`, bucketed by reveal tier.

    Every idle-animated overlay (hologram struts and nodes, LEDs, cursor, log/
    code lines, lamps, window lights, hand frames, packets, and the backing
    behind all of them) is emitted grouped under the SAME reveal tier as the
    static artwork it sits on top of -- "rv-core" for the drum's own LEDs,
    "rv-holo" for the hologram, "rv-fixtures" for the wall rack/lamps/window/
    terminal text, "rv-chars" for hands. Without this, the reveal (built in
    make_backend_lab.py) would only fade in the STATIC leftover pixels of each
    region while every animated pixel -- which is most of what makes the core
    and hologram visually distinctive -- stayed permanently at full opacity
    from t=0, defeating the reveal entirely. This was caught by simulating the
    reveal frame-by-frame rather than by eye: the hologram was fully bright in
    the very first frame.

    Returns (static remainder, {tier: [group markup]}, stylesheet, additive)
    where `additive` is every rectangle this layer *adds* to the document --
    the backing and the hands' second frame. The build compares
    remainder + lifted against the original trace, and `additive` against this
    list, so "the artwork did not change" is asserted exactly rather than by
    pattern-matching the emitted markup.
    """
    rnd = random.Random(7)
    tier_groups: Dict[str, List[str]] = {"rv-core": [], "rv-holo": [], "rv-fixtures": [], "rv-chars": []}
    tier_faded: Dict[str, Mask] = {t: _blank(a) for t in tier_groups}
    rest = rects
    additive: List[Rect] = []

    # --- hologram: nodes first, then the connecting lines -------------------
    holo = holo_mask(a)
    node_durs = (3.2, 3.7, 4.1, 4.6, 5.0)
    node_delays = tuple(REVEAL_END + d for d in (0.0, 1.1, 2.3, 0.7, 3.1))
    claimed = _blank(a)
    for i, box in enumerate(HOLO_NODES):
        x0, y0, x1, y1 = box
        m = _blank(a)
        m[y0:y1, x0:x1] = holo[y0:y1, x0:x1] & ~claimed[y0:y1, x0:x1]
        claimed |= m
        lifted, rest = lift(rest, m)
        if lifted:
            mark(tier_faded["rv-holo"], lifted)
            tier_groups["rv-holo"].append(group_svg(
                lifted, f"anim-holo-node-{i}", "node",
                f"animation-duration:{node_durs[i]}s;animation-delay:{node_delays[i]}s"))
    lines_mask = holo & ~claimed
    lifted, rest = lift(rest, lines_mask)
    if lifted:
        mark(tier_faded["rv-holo"], lifted)
        tier_groups["rv-holo"].append(group_svg(lifted, "anim-holo-lines", "holo",
                                 f"animation-delay:{REVEAL_END}s"))

    # --- server + rack LEDs, each tagged with its own housing's tier --------
    led_bodies: Dict[str, List[str]] = {"rv-core": [], "rv-fixtures": []}
    for i, (tier, m) in enumerate(led_masks(a)):
        lifted, rest = lift(rest, m)
        if not lifted:
            continue
        mark(tier_faded[tier], lifted)
        # most LEDs breathe; a minority actually blink, so the rack reads as
        # operational rather than as a string of fairy lights
        blink = rnd.random() < 0.42
        dur = round(rnd.uniform(1.5, 4.0), 2)
        delay = round(REVEAL_END + rnd.uniform(0.0, 4.0), 2)
        led_bodies[tier].append(group_svg(
            lifted, f"anim-led-{i}", "led" if blink else "ledSoft",
            f"animation-duration:{dur}s;animation-delay:{delay}s"))
    for tier, bodies in led_bodies.items():
        if bodies:
            tier_groups[tier].append(f'<g id="anim-leds-{tier}">{"".join(bodies)}</g>')

    # --- terminal cursor, one log line, one code line -- all in the fixtures
    # tier alongside the panels they belong to -------------------------------
    cm = _blank(a)
    x0, y0, x1, y1 = CURSOR_BOX
    cm[y0:y1, x0:x1] = True
    lifted, rest = lift(rest, cm)
    if lifted:
        mark(tier_faded["rv-fixtures"], lifted)
        tier_groups["rv-fixtures"].append(group_svg(lifted, "anim-cursor", "cursor",
                                 f"animation-delay:{REVEAL_END}s"))

    lm = panel_text_mask(a, LOGS_PANEL, LOGS_LINE)
    lifted, rest = lift(rest, lm)
    if lifted:
        mark(tier_faded["rv-fixtures"], lifted)
        tier_groups["rv-fixtures"].append(group_svg(lifted, "anim-logline", "logline",
                                 f"animation-delay:{REVEAL_END}s"))
    cmm = panel_text_mask(a, CODE_PANEL, CODE_LINE)
    lifted, rest = lift(rest, cmm)
    if lifted:
        mark(tier_faded["rv-fixtures"], lifted)
        tier_groups["rv-fixtures"].append(group_svg(lifted, "anim-codeline", "codeline",
                                 f"animation-delay:{REVEAL_END}s"))

    # --- lamps ----------------------------------------------------------------
    for name, box, dur, delay in LAMPS:
        lmask = lamp_mask(a, box)
        lifted, rest = lift(rest, lmask)
        if lifted:
            mark(tier_faded["rv-fixtures"], lifted)
            tier_groups["rv-fixtures"].append(group_svg(
                lifted, f"anim-lamp-{name}", "lamp",
                f"animation-duration:{dur}s;animation-delay:{delay}s"))

    # --- window lights ----------------------------------------------------
    win_bodies: List[str] = []
    for i, m in enumerate(window_masks(a)):
        lifted, rest = lift(rest, m)
        if not lifted:
            continue
        mark(tier_faded["rv-fixtures"], lifted)
        win_bodies.append(group_svg(
            lifted, f"anim-win-{i}", "win",
            f"animation-duration:{round(rnd.uniform(5.0, 10.0), 2)}s;"
            f"animation-delay:{round(REVEAL_END + rnd.uniform(0.0, 8.0), 2)}s"))
    if win_bodies:
        tier_groups["rv-fixtures"].append(f'<g id="anim-window">{"".join(win_bodies)}</g>')

    # --- hands: additive two-frame patches (base layer untouched) -----------
    hand_bodies: List[str] = []
    for name, (box, dur, delay) in HANDS.items():
        m = skin_mask(a, box)
        frame2 = hand_frame2(a, m, dy=1)
        if not frame2:
            continue
        additive.extend(frame2)
        kind = "tap2" if name in ("builder", "debugger") else "tap1"
        hand_bodies.append(group_svg(
            frame2, f"anim-hand-{name}", "tap",
            f"animation-name:{kind};animation-duration:{dur}s;animation-delay:{delay}s"))
    if hand_bodies:
        tier_groups["rv-chars"].append(f'<g id="anim-hands">{"".join(hand_bodies)}</g>')
    # the hands' second frame is new geometry drawn only at animation time, so
    # it has nothing behind it to fade from black -- it is not part of `faded`
    # and gets no backing rect.

    # --- data packets (the only other new geometry) --------------------------
    holo_px = a[holo]
    pkt_col = "#b6f13c"
    if len(holo_px):
        brightest = holo_px[holo_px.sum(1).argmax()]
        pkt_col = f"#{brightest[0]:02x}{brightest[1]:02x}{brightest[2]:02x}"
    pk: List[str] = []
    for cls, px_, py, dx, dy, steps, dur, delay in PACKETS:
        name = {"pk-stem": "pkStem", "pk-left": "pkLeft", "pk-right": "pkRight"}[cls]
        pk.append(
            f'<rect class="pk" x="{px_}" y="{py}" width="2" height="2" fill="{pkt_col}" '
            f'style="--s:{steps};animation-name:{name};animation-duration:{dur}s;'
            f'animation-delay:{delay}s"/>')
    tier_groups["rv-holo"].append(f'<g id="anim-packets">{"".join(pk)}</g>')

    # backing, computed and inserted per tier so it reveals in lockstep with
    # the foreground pixels it sits under -- a single global backing would
    # otherwise show the core's LED backing at rv-core's earlier delay while
    # the hologram's own backing (rv-holo, later) is still fading in.
    for tier, fmask in tier_faded.items():
        back = backing_rects(a, fmask)
        if back:
            tier_groups[tier].insert(0, group_svg(back, f"anim-backing-{tier}"))
            additive.extend(back)

    return rest, tier_groups, css((), ()), additive
