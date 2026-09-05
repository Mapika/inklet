"""Eyeball check that shaped text comes out in millimetres, not points or ems.

Run it after touching anything in inklet.typeset:

    .venv/bin/python scripts/sanity_text.py

A 7pt, 18-character label should be roughly 15-22mm wide -- about a fifth of a
single journal column. A result near 3mm means the mm/pt conversion is
inverted; a result near 200mm means it never happened.
"""

from __future__ import annotations

from inklet.core.units import COLUMN_SINGLE, pt, to_pt
from inklet.typeset import find_font, shape

SAMPLE = "Encoder (ViT-B/16)"


def main() -> None:
    face = find_font("sans")
    prim = shape(SAMPLE, size=pt(7))

    print(f"font      {face.family}  ({face.path})")
    print(f"metrics   upem {face.units_per_em}, ascent {face.ascent:g}, "
          f"descent {face.descent:g}, line gap {face.line_gap:g}")
    print(f"size      {prim.font_size:.3f} mm  ({to_pt(prim.font_size):g} pt)")
    print(f"text      {SAMPLE!r}  ({len(SAMPLE)} chars)")
    print(f"width     {prim.width:.3f} mm  ({to_pt(prim.width):.1f} pt)")
    print(f"height    {prim.height:.3f} mm  "
          f"(ascent {prim.ascent:.3f} + descent {prim.descent:.3f})")
    print(f"per char  {prim.width / len(SAMPLE):.3f} mm")
    print(f"column    {100 * prim.width / COLUMN_SINGLE:.1f}% of a {COLUMN_SINGLE:g}mm column")

    verdict = "plausible" if 15.0 <= prim.width <= 22.0 else "SUSPECT -- check unit conversion"
    print(f"verdict   {verdict}")


if __name__ == "__main__":
    main()
