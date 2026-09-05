"""Does the viewer reproduce our shaping?

inklet measures with HarfBuzz and then emits <text> with the raw string, leaving
the viewer to shape it again. Everything about auto-sizing rests on those two
shapers agreeing. This renders the same string both ways -- one run, and one
tspan per glyph at HarfBuzz's own advances -- so the rasters can be differenced.
"""
import sys
from inklet.typeset.shaping import shape_buffer, feature_key
from inklet.typeset.fonts import find_font
from inklet.typeset import shape
from inklet import pt

SAMPLES = [
    ("kerning", "AVATAR Wave To. Yo,"),
    ("ligature", "efficient office fjord"),
    ("mixed",    "ΔF/F₀ = 0.42 — n=17"),
    ("numerals", "1,234.56 × 10⁻³"),
]
SIZE = pt(11)
FAM = "sans"

def glyph_run(text, face, size):
    """x positions in mm of each glyph, from HarfBuzz."""
    buf = shape_buffer(text, face, feature_key(None))
    scale = size / face.units_per_em
    out, x = [], 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        out.append((x + pos.x_offset * scale, info.cluster))
        x += pos.x_advance * scale
    return out, x

def svg(text, face, size, mode, w, h):
    y = h / 2
    if mode == "run":
        body = f'<text x="2" y="{y}" font-family="{face.family}" font-size="{size}" xml:space="preserve">{text}</text>'
    else:
        run, _ = glyph_run(text, face, size)
        spans = "".join(
            f'<tspan x="{2 + x:.5f}" y="{y}">{_esc(text[c])}</tspan>'
            for x, c in run if c < len(text))
        body = f'<text font-family="{face.family}" font-size="{size}" xml:space="preserve">{spans}</text>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" '
            f'viewBox="0 0 {w} {h}"><rect width="{w}" height="{h}" fill="#fff"/>'
            f'{body}</svg>')

def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

face = find_font(FAM)
print(f"face: {face.family}  upem={face.units_per_em}  {face.path}")
for name, text in SAMPLES:
    prim = shape(text, font=FAM, size=SIZE)
    _, advance = glyph_run(text, face, SIZE)
    w, h = advance + 8, SIZE * 3
    for mode in ("run", "glyphs"):
        open(f"/tmp/fid_{name}_{mode}.svg", "w").write(svg(text, face, SIZE, mode, w, h))
    print(f"{name:10s} advance={advance:8.4f}mm  prim.width={prim.width:8.4f}mm  "
          f"delta={advance-prim.width:+.6f}")
