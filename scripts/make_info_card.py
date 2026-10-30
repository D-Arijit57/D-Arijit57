"""
Build the right-hand card: a stats card in the same window frame as the other
two assets in the README (contrib-heatmap.svg and arijit-ascii.svg) -- same
12px-radius dark window, traffic lights and centred title, same
muted/green/cyan/gold colours, same monospace stack.

The top half is the profile and headline numbers, set out under small section
labels. The bottom half is the "3D" part: the monthly bar chart and the stack blocks are oblique boxes -- a front
face, a lighter top face and a darker right face -- drawn by hand because CSS
`perspective` does not apply inside an SVG shown through <img>. Bars use the
contribution-graph ramp from render_heatmap_svg.py.

Numbers come from data/contributions.json (written daily by
fetch_contributions.py), so the card refreshes with the contribution graph.

Motion is CSS keyframes in an inline <style>, like the heatmap: lines print on
a stagger, bars grow up from the slab and stack blocks rise. Resting state is fully visible (`backwards` fill, no resting
opacity:0), and prefers-reduced-motion turns every animation off.

  python scripts/make_info_card.py
"""
from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

# ---- content ---------------------------------------------------------------
NAME = "Arijit Das"
ROLE = "Software Engineer"
CURRENT = "American Chase"
STACK = ["Python", "Django", "Node.js", "DRF",
         "PostgreSQL", "AWS", "Docker", "React"]

TITLE = "arijit@github: ~"

HERE: Path = Path(__file__).resolve().parent
DATA: Path = HERE.parent / "data" / "contributions.json"
OUT: Path = HERE.parent / "assets" / "info-card.svg"

# ---- geometry --------------------------------------------------------------
W, H = 490, 692
PAD = 20
TITLEBAR_H = 30
FONT = 12.5

# ---- palette (same values as the heatmap / ascii assets) -------------------
BG, BG2 = "#0d1117", "#111722"
FRAME = "#30363d"
MUTED = "#7d8590"
TEXT = "#e6edf3"
INK = "#c9d1d9"
ACCENT = "#22d3ee"
GREEN = "#39d353"
GOLD = "#f2cc60"
RAMP = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

# (metric, what it was, where) -- picked from the resume, engineering results only
HIGHLIGHTS = [
    ("150x", "faster list queries, 46 \u2192 0.3 ms", "Lattice", GREEN),
    ("8h outage", "customer API restored", "American Chase", ACCENT),
    ("3.5s\u2192140ms", "p50 latency, 27 \u2192 101 req/s", "RakshaChakra", GOLD),
]

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def esc(s: str) -> str:
    return html.escape(s)


def mix(a: str, b: str, t: float) -> str:
    """Blend hex colour a toward b by t (0..1)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def box(x: float, y: float, w: float, h: float, d: float, front: str,
        top: str, side: str, edge: Optional[str] = None) -> str:
    """Oblique box. (x, y) is the front face's top-left; depth runs up-right."""
    dx, dy = d, -d * 0.6
    out = (
        f'<polygon points="{x + w},{y} {x + w + dx},{y + dy} {x + w + dx},{y + h + dy} {x + w},{y + h}" fill="{side}"/>'
        f'<polygon points="{x},{y} {x + dx},{y + dy} {x + w + dx},{y + dy} {x + w},{y}" fill="{top}"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{front}"/>'
    )
    if edge:
        out += f'<line x1="{x}" y1="{y}" x2="{x + w}" y2="{y}" stroke="{edge}" stroke-opacity="0.6"/>'
    return out


def solid(x: float, y: float, w: float, h: float, d: float, colour: str) -> str:
    return box(x, y, w, h, d, colour, mix(colour, "#ffffff", 0.3), mix(colour, "#000000", 0.35))


CSS = """
@keyframes print{from{opacity:0}to{opacity:1}}
@keyframes grow{from{transform:scaleY(.02)}to{transform:scaleY(1)}}
@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes glow{from{opacity:.6}to{opacity:1}}
.ln{animation:print .3s ease-out backwards}
.bar{animation:grow .9s cubic-bezier(.2,.8,.2,1) backwards}
.rise{animation:rise .5s cubic-bezier(.2,.8,.2,1) backwards}
.peak{animation:glow 1.4s ease-in-out 1.6s infinite alternate}
@media (prefers-reduced-motion:reduce){
  .ln,.bar,.rise,.peak{animation:none}
}
""".strip()


def load_stats() -> dict:
    return json.loads(DATA.read_text())


def month_label(ym: str) -> str:
    y, m = ym.split("-")
    return date(int(y), int(m), 1).strftime("%b")


def level(v: int, peak: int) -> int:
    if v == 0:
        return 0
    r = v / peak
    return 1 if r <= .25 else 2 if r <= .5 else 3 if r <= .75 else 4 if r < 1 else 5


def main() -> None:
    s = load_stats()
    monthly: List[Tuple[str, int]] = [(m["month"], m["total"]) for m in s["monthly"]]
    synced = s["generated_at"][:10]
    streak = s["current_streak"]["length"]
    peak = max(v for _, v in monthly) or 1
    p: List[str] = []

    # ---- window chrome, identical to the other two assets -------------------
    p.append(f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
             f'</linearGradient></defs>')
    p.append(f'<rect width="{W}" height="{H}" rx="12" fill="url(#bg)"/>')
    p.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="none" stroke="{FRAME}"/>')
    p.append(f'<line x1="0" y1="{TITLEBAR_H}" x2="{W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>')
    for i, col in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        p.append(f'<circle cx="{PAD + i * 16}" cy="{TITLEBAR_H / 2}" r="5" fill="{col}"/>')
    p.append(f'<text x="{W / 2}" y="{TITLEBAR_H / 2 + 4}" fill="{MUTED}" font-size="12" '
             f'text-anchor="middle">{esc(TITLE)}</text>')

    n = 0

    def line(y: float, inner: str) -> None:
        nonlocal n
        p.append(f'<g class="ln" style="animation-delay:{0.1 + n * 0.12:.2f}s">'
                 f'<text x="{PAD}" y="{y}" font-size="{FONT}" xml:space="preserve">{inner}</text></g>')
        n += 1

    def section(y: float, label: str, right: str = "") -> None:
        """Small muted label with a hairline running to the right edge."""
        nonlocal n
        end = PAD + len(label) * 7.4 + 10
        rule_end = W - PAD - (len(right) * 6.2 + 10 if right else 0)
        p.append(f'<g class="ln" style="animation-delay:{0.1 + n * 0.12:.2f}s">'
                 f'<text x="{PAD}" y="{y}" font-size="10.5" letter-spacing="1.2" fill="{MUTED}">{esc(label.upper())}</text>'
                 f'<line x1="{end:.1f}" y1="{y - 3.5}" x2="{rule_end:.1f}" y2="{y - 3.5}" stroke="{FRAME}"/>'
                 + (f'<text x="{W - PAD}" y="{y}" font-size="10" fill="{MUTED}" text-anchor="end">{esc(right)}</text>' if right else "")
                 + '</g>')
        n += 1

    # ---- profile ------------------------------------------------------------
    line(76, f'<tspan fill="{TEXT}" font-size="21" font-weight="700">{esc(NAME)}</tspan>')
    line(102, f'<tspan fill="{GOLD}">{esc(ROLE)}</tspan><tspan fill="{MUTED}"> @ </tspan>'
              f'<tspan fill="{ACCENT}">{esc(CURRENT)}</tspan>')

    # ---- stats --------------------------------------------------------------
    section(152, "stats")
    stats = [
        (f'{s["total_contributions"]:,}', "contributions", GREEN),
        (str(s["active_days"]), "active days", ACCENT),
        (f'{streak}d', "current streak", ACCENT),
        (str(s["best_day"]["count"]), "best day", GOLD),
    ]
    for i, (num, label, col) in enumerate(stats):
        x = PAD + i * 113
        p.append(f'<g class="ln" style="animation-delay:{0.1 + n * 0.12 + i * 0.08:.2f}s">'
                 f'<text x="{x}" y="190" font-size="22" font-weight="700" fill="{col}">{esc(num)}</text>'
                 f'<text x="{x}" y="209" font-size="10" fill="{MUTED}">{esc(label)}</text></g>')
    n += 1

    # ---- highlights ---------------------------------------------------------
    section(262, "highlights")
    for i, (metric, what, where, col) in enumerate(HIGHLIGHTS):
        y = 288 + i * 24
        line(y, f'<tspan fill="{col}" font-weight="700">{esc(metric)}</tspan>')
        p.append(f'<g class="ln" style="animation-delay:{0.1 + (n - 1) * 0.12:.2f}s">'
                 f'<text x="{PAD + 112}" y="{y}" font-size="11.5" xml:space="preserve">'
                 f'<tspan fill="{INK}">{esc(what)}</tspan><tspan fill="{MUTED}"> \u00b7 {esc(where)}</tspan></text></g>')

    # ---- monthly 3D bars ----------------------------------------------------
    section(380, "contributions / month", f"synced {synced}")
    base, max_h = 518, 104
    p.append(f'<g class="ln" style="animation-delay:.9s">'
             f'{box(PAD - 2, base, W - PAD * 2 + 2, 7, 7, "#21262d", "#30363d", "#161b22")}</g>')
    slot = (W - PAD * 2 - 14) / len(monthly)
    bw, bd = 18, 7
    for i, (ym, v) in enumerate(monthly):
        bx = PAD + 3 + i * slot
        h = max(2.0, v / peak * max_h)
        col = RAMP[level(v, peak)]
        glow = ' class="peak"' if v == peak else ""
        delay = 1.0 + i * 0.07
        p.append(
            f'<g transform="translate({bx:.1f},{base})">'
            f'<g class="bar" style="animation-delay:{delay:.2f}s"><g{glow}>'
            f'{solid(0, -h, bw, h, bd, col)}</g></g></g>'
            f'<g class="ln" style="animation-delay:{delay + 0.7:.2f}s">'
            f'<text x="{bx + bw / 2:.1f}" y="{base - h - bd * 0.6 - 5:.1f}" font-size="8.5" '
            f'fill="{INK}" text-anchor="middle">{v}</text></g>'
            f'<text x="{bx + bw / 2 + 2:.1f}" y="{base + 24}" font-size="8.5" fill="{MUTED}" '
            f'text-anchor="middle">{month_label(ym)}</text>')

    # ---- stack blocks -------------------------------------------------------
    section(582, "stack")
    bw2, bh, bd2 = 96, 24, 6
    g2 = (W - PAD * 2 - bd2 - 4 * bw2) / 3
    for i, name in enumerate(STACK):
        col, row = i % 4, i // 4
        bx = PAD + col * (bw2 + g2)
        by = 608 + row * 40
        p.append(
            f'<g class="rise" style="animation-delay:{1.9 + i * 0.07:.2f}s">'
            f'{box(bx, by, bw2, bh, bd2, "#161b22", mix("#161b22", GREEN, 0.28), "#0a0d12", GREEN)}'
            f'<text x="{bx + bw2 / 2}" y="{by + 16}" font-size="10.5" fill="{INK}" '
            f'text-anchor="middle">{esc(name)}</text></g>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" role="img" font-family="{MONO}" '
           f'aria-label="{esc(NAME)}, {esc(ROLE)} at {esc(CURRENT)}: '
           f'{s["total_contributions"]} contributions, {streak} day streak">'
           f"<style>{CSS}</style>" + "".join(p) + "</svg>")

    for banned in ("<image", "base64", "<script"):
        if banned in svg:
            raise SystemExit(f"unexpected construct: {banned}")
    last_block = 608 + 40 + bh
    if last_block > H - 14:
        raise SystemExit(f"stack overflows the window: {last_block} vs {H}")

    OUT.write_text(svg)
    print(f"wrote {OUT} {len(svg)} bytes; {W}x{H}")


if __name__ == "__main__":
    main()
