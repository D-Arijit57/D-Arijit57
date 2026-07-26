"""
Build a neofetch-style info card SVG (Andrew6rant style) to sit to the RIGHT of
the ASCII portrait: colored key/value rows for identity, tech stack, and a
closing summary -- NOT GitHub stats (the contribution graph covers those).

Content is data-driven from the profile config below. Lines fade/slide in on a
short stagger so it feels like the panel is printing alongside the portrait.
STATIC=1 emits the frozen state for Quick Look previews.
"""
from pathlib import Path
from typing import List, Tuple
import html
import os

# ---- profile config (single source of truth -- no hardcoded personal info
# below this block) ----------------------------------------------------------
USERNAME = "D-Arijit57"
DISPLAY_NAME = "Arijit Das"
TITLE = "Software Engineer"

CURRENT_ROLE = "Software Engineer"
CURRENT_COMPANY = "American Chase"
CURRENT_LOCATION = "Indore, Madhya Pradesh"
EDUCATION = "B.Tech CS @ VIT"

SUMMARY = (
    "Software Engineer building AI-powered applications, "
    "developer tools and production-ready backend systems."
)

FRONTEND = ["React", "Next.js", "ShadCn", "TailwindCSS"]
BACKEND = ["Node.js", "Express.js", "REST APIs", "Convex"]
AI = [
    "LangChain",
    "OpenAI",
    "HuggingFace",
    "Chroma",
]
CLOUD_DEPLOY = ["Vercel", "Docker", "AWS"]

# identity block + tech stack block, each rendered as ("label", value) rows
IDENTITY: List[Tuple[str, str]] = [
    ("Role", CURRENT_ROLE),
    ("Now", CURRENT_COMPANY),
    ("Location", CURRENT_LOCATION),
    ("Edu", EDUCATION),
]
STACK: List[Tuple[str, List[str]]] = [
    ("Frontend", FRONTEND),
    ("Backend", BACKEND),
    ("AI", AI),
    ("Cloud & Deploy", CLOUD_DEPLOY),
]

HERE: Path = Path(__file__).resolve().parent
OUT: Path = HERE.parent / "assets" / "info-card.svg"
STATIC: bool = bool(os.environ.get("STATIC"))

W, H = 480, 376
PAD = 20
TITLEBAR_H = 30
KEY_X = PAD
# widened from the original 92px gap so the longer "Cloud & Deploy" label
# still clears the value column with the same visual buffer as before
VAL_X = PAD + 140
LINE_H = 20.5

BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#c9d1d9"
KEY = "#ffa657"      # orange keys (matches Andrew)
SECTION = "#58a6ff"  # blue section headers
GREEN = "#3fb950"
ACCENT = "#22d3ee"

# approx advance width (in px) of the monospace font stack, as a fraction of
# its em size -- used only to size text-wrapping, not for actual rendering
CHAR_W_RATIO = 0.6
FONT_HOST = 14
FONT_BODY = 12.5

# max characters per line for each column, derived from the available pixel
# width so wrapping adapts automatically if labels/columns ever change
KV_MAX_CHARS = int((W - PAD - VAL_X) / (FONT_BODY * CHAR_W_RATIO))
PARA_MAX_CHARS = int((W - PAD - (KEY_X + 14)) / (FONT_BODY * CHAR_W_RATIO))

# content model: tuples describing each row
# ("host",)                    -> "{USERNAME}@github" + rule
# ("kv", key, values)          -> orange key + wrapped, comma-joined values
# ("sec", title)               -> blue "— title —" rule
# ("para", text)                -> wrapped plain text, no key/heading
# ("whoami",)                  -> "{USERNAME}@github:~$ whoami" prompt (no output)
# ("gap",)                     -> vertical space
ROWS: List[tuple] = [
    ("host",),
    *[("kv", key, [val]) for key, val in IDENTITY],
    ("gap",),
    ("sec", "Tech Stack"),
    *[("kv", key, vals) for key, vals in STACK],
    ("gap",),
    ("whoami",),
    ("para", SUMMARY),
]


def esc(s: str) -> str:
    return html.escape(s)


def wrap_words(words: List[str], max_chars: int, sep: str = " ") -> List[str]:
    """Greedily pack words onto lines no wider than max_chars, never splitting a word."""
    lines: List[str] = []
    cur: List[str] = []
    for word in words:
        trial = cur + [word]
        if cur and len(sep.join(trial)) > max_chars:
            lines.append(sep.join(cur))
            cur = [word]
        else:
            cur = trial
    if cur:
        lines.append(sep.join(cur))
    return lines


def wrap_list(items: List[str], max_chars: int) -> List[str]:
    """Wrap a comma-separated list of items; continuation lines get a trailing
    comma so the list still reads correctly when it spans multiple lines."""
    lines = wrap_words(items, max_chars, sep=", ")
    return [line + ("," if i < len(lines) - 1 else "") for i, line in enumerate(lines)]


def rise(inner: str, i: int) -> str:
    """fade + slight upward slide, staggered by row index; freezes visible."""
    if STATIC:
        return f"<g>{inner}</g>"
    delay = 0.15 + i * 0.06
    return (f'<g opacity="0" transform="translate(0,5)">{inner}'
            f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.4s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 5" to="0 0" '
            f'begin="{delay:.2f}s" dur="0.4s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1"/></g>')


parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
    f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
    '<defs>'
    f'<linearGradient id="ibg" x1="0" y1="0" x2="0" y2="1">'
    f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient></defs>',
    f'<rect width="{W}" height="{H}" rx="12" fill="url(#ibg)"/>',
    f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="none" stroke="{FRAME}"/>',
    f'<line x1="0" y1="{TITLEBAR_H}" x2="{W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
]
for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
    parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
parts.append(f'<text x="{W/2}" y="{TITLEBAR_H/2 + 4}" fill="{MUTED}" font-size="12" '
             f'text-anchor="middle">{USERNAME}@github: ~$ neofetch</text>')

y = TITLEBAR_H + 30
anim_i = 0  # continuous stagger index across all emitted lines
for row in ROWS:
    kind = row[0]

    if kind == "gap":
        y += LINE_H * 0.5
        continue

    if kind == "host":
        host_text = f"{USERNAME}@github"
        # rule starts just past the host text, matching its actual rendered width
        rule_x = KEY_X + int(len(host_text) * FONT_HOST * CHAR_W_RATIO) + 12
        inner = (f'<text x="{KEY_X}" y="{y:.1f}" font-size="{FONT_HOST}" font-weight="700">'
                 f'<tspan fill="{GREEN}">{esc(USERNAME)}</tspan><tspan fill="{MUTED}">@</tspan>'
                 f'<tspan fill="{ACCENT}">github</tspan></text>'
                 f'<line x1="{rule_x}" y1="{y-4:.1f}" x2="{W-PAD}" y2="{y-4:.1f}" '
                 f'stroke="{FRAME}" stroke-opacity="0.8"/>')
        parts.append(rise(inner, anim_i))
        anim_i += 1
        y += LINE_H

    elif kind == "sec":
        title = esc(row[1])
        inner = (f'<text x="{KEY_X}" y="{y:.1f}" fill="{SECTION}" font-size="{FONT_BODY}" font-weight="700">'
                 f'&#8212; {title}</text>'
                 f'<line x1="{KEY_X + 12 + len(row[1])*8}" y1="{y-4:.1f}" x2="{W-PAD}" y2="{y-4:.1f}" '
                 f'stroke="{FRAME}" stroke-opacity="0.8"/>')
        parts.append(rise(inner, anim_i))
        anim_i += 1
        y += LINE_H

    elif kind == "kv":
        _, key, values = row
        for li, line_text in enumerate(wrap_list(values, KV_MAX_CHARS)):
            val = esc(line_text)
            if li == 0:
                inner = (f'<text x="{KEY_X}" y="{y:.1f}" fill="{KEY}" font-size="{FONT_BODY}" '
                         f'font-weight="700">{esc(key)}</text>'
                         f'<text x="{VAL_X}" y="{y:.1f}" fill="{INK}" font-size="{FONT_BODY}">{val}</text>')
            else:
                inner = f'<text x="{VAL_X}" y="{y:.1f}" fill="{INK}" font-size="{FONT_BODY}">{val}</text>'
            parts.append(rise(inner, anim_i))
            anim_i += 1
            y += LINE_H

    elif kind == "para":
        text = row[1]
        for line_text in wrap_words(text.split(), PARA_MAX_CHARS):
            inner = f'<text x="{KEY_X}" y="{y:.1f}" fill="{INK}" font-size="{FONT_BODY}">{esc(line_text)}</text>'
            parts.append(rise(inner, anim_i))
            anim_i += 1
            y += LINE_H

    elif kind == "whoami":
        inner = (f'<text x="{KEY_X}" y="{y:.1f}" fill="{MUTED}" font-size="{FONT_BODY}">'
                 f'{esc(USERNAME)}@github:~$ whoami</text>')
        parts.append(rise(inner, anim_i))
        anim_i += 1
        y += LINE_H

parts.append("</svg>")
svg = "".join(parts)
OUT.write_text(svg)
print("wrote", OUT, len(svg), "bytes;", W, "x", H, "content_bottom", round(y))
