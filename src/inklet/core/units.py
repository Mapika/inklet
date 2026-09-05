"""Physical units. Millimetres are canonical; points are for type sizes.

Layout is solved in mm because the output is print. That makes "no glyph below
5pt at final size" and "this raster is 287dpi at 40mm wide" checkable facts
rather than guesses. Pixels only exist in the raster backend.
"""

from __future__ import annotations

import re

MM_PER_PT = 25.4 / 72.0
MM_PER_IN = 25.4

_LENGTH = re.compile(r"^\s*([+-]?(?:\d+\.?\d*|\.\d+))\s*(mm|cm|pt|in|px)?\s*$")

# px is CSS's 96dpi pixel, present only so browser-flavoured input parses.
_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "pt": MM_PER_PT,
    "in": MM_PER_IN,
    "px": MM_PER_IN / 96.0,
    None: 1.0,
}


class UnitError(ValueError):
    pass


def mm(value: float | int | str) -> float:
    """Coerce a length to millimetres. Bare numbers are already mm."""
    if isinstance(value, (int, float)):
        return float(value)
    match = _LENGTH.match(value)
    if match is None:
        raise UnitError(f"cannot parse length {value!r}")
    magnitude, unit = match.groups()
    return float(magnitude) * _TO_MM[unit]


def pt(value: float) -> float:
    """Points to millimetres, for font sizes and hairline strokes."""
    return value * MM_PER_PT


def to_pt(value_mm: float) -> float:
    return value_mm / MM_PER_PT


def dpi_of(pixels: int, width_mm: float) -> float:
    """Effective resolution of a raster placed at a given physical width."""
    if width_mm <= 0:
        raise UnitError("width must be positive")
    return pixels / (width_mm / MM_PER_IN)


# Journal single/double column widths, the two numbers every figure is built to.
COLUMN_SINGLE = 89.0
COLUMN_DOUBLE = 183.0
