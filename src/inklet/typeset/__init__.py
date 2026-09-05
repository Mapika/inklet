"""Text measurement: a family name and a string in, a measured TextPrim out.

Everything downstream sizes boxes from the advances produced here, so this is
deliberately the only module in inklet that touches a font file.

`onpath` is the one exception to "measurement only", and for the same reason:
setting a run along a curve is placement, but it is placement *of the shaped
advances*, and doing it anywhere else would mean a second module reading a
buffer out of HarfBuzz.
"""

from __future__ import annotations

from .fonts import FontFace, FontNotFoundError, find_font, load_face
from .markup import Mark, Styled, escape_markup, strip_markup, theme_colors
from .onpath import (Baseline, baseline, baseline_arc, text_on_arc,
                     text_on_path)
from .outline import Contour, glyph_contours, placed_contours, text_to_paths
from .shaping import measure, shape

__all__ = [
    "Baseline",
    "Contour",
    "FontFace",
    "FontNotFoundError",
    "Mark",
    "Styled",
    "baseline",
    "baseline_arc",
    "escape_markup",
    "find_font",
    "glyph_contours",
    "load_face",
    "placed_contours",
    "strip_markup",
    "theme_colors",
    "measure",
    "shape",
    "text_on_arc",
    "text_on_path",
    "text_to_paths",
]
