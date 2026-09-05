"""Shared scaffolding for the electrolyser figure: the width contract, a few
theme shorthands, and the deterministic RNG every panel draws its data from.

Nothing here draws a panel. The point of the module is that twelve panels
written independently agree on what a hairline is, what "column" means, and
which seed produced the numbers -- so the page reads as one figure rather than
as twelve drawings that happen to share a font.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

import inklet

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).resolve().parent / "assets"

#: The page. 183mm is the double-column width every journal in this family
#: uses; the height is one printed page with the caption under it.
PAGE_WIDTH = 183.0
PAGE_HEIGHT = 252.0
FULL = 178.0
COLUMN = 87.0
NARROW = 57.0

#: Semantic colour roles, so a species drawn in panel (e) is the same colour in
#: (f), (i) and (l). Indices into the theme palette, which stays CVD-safe.
#:
#: Chosen for what they look like *after* `ink_color(..., min_ratio=4.5)`, not
#: as swatches: the panels darken every species colour to text contrast so one
#: slot can serve a bar, a 0.25mm fit line and the words quoting its slope.
#: That darkening is not hue-preserving. Palette 1 (#e69f00) and 4 (#f0e442)
#: both land on a dark olive-gold, and 2 (#56b4e9) darkens onto 5 (#0072b2),
#: so the obvious CVD-safe picks collapse into three hues once drawn. These
#: five stay apart: #c25703 / #0072b2 / #058461 / #a06184 / #000000.
SPECIES = {
    "C2H4": 6,      # the product the cell is for -- vermillion, the hero
    "CO": 5,        # blue
    "HCOO": 3,      # green
    "CH4": 7,       # rose
    "H2": 0,        # the parasitic one -- black
}
SPECIES_LABEL = {
    "C2H4": "C_{2}H_{4}",
    "CO": "CO",
    "HCOO": "HCOO^{-}",
    "CH4": "CH_{4}",
    "H2": "H_{2}",
}


def hair(theme) -> inklet.Style:
    """The weight leaders, ticks and construction lines are drawn at."""
    return inklet.Style(stroke=theme.muted, stroke_width=theme.hairline)


def model_stroke(theme) -> float:
    """Line-art weight for a projected mesh: a hairline, and no thinner.

    A mesh puts hundreds of lines on the page and the instinct is to drop the
    weight so the mass of them does not read as grey. Two things say no. An
    offset press stops holding a line below 0.088mm, which is what the
    HAIRLINE rule enforces; and a fourth stroke weight on a sheet that already
    runs hairline / data / emphasis buys nothing a reader can name, which is
    what INCONSISTENT_STROKE is complaining about when it counts four. So the
    mesh is lightened by *colour* -- see the greys in `cell.py` -- and the
    sheet keeps three weights.
    """
    return theme.hairline


def fit(builder: Callable[[float], inklet.Diagram], target: float,
        passes: int = 4, tol: float = 0.05) -> inklet.Diagram:
    """A panel exactly `target` millimetres wide.

    The same contract `stress/panels` works to, and for the same reason: a
    panel 8% over pushes its neighbour off the paper. Solve first, which
    *widens the content*; pad what the solve cannot reach, which can only add
    paper. See `stress/panels/apparatus._fit` for the full argument.
    """
    drive = target
    node = builder(drive)
    for _ in range(passes - 1):
        residual = target - node.bbox.width
        if abs(residual) <= tol:
            break
        drive += residual
        node = builder(drive)
    for _ in range(3):
        slack = target - node.bbox.width
        if slack >= 0.0:
            break
        node = builder(drive + slack - tol)
        drive += slack - tol
    slack = target - node.bbox.width
    if slack < 0.0:
        return node.scaled(target / node.bbox.width)
    if slack <= 1e-9:
        return node
    return inklet.pad(node, 0.0, slack / 2.0, 0.0, slack / 2.0)


def titled(letter: str, body: inklet.Diagram, *, gap: float | None = None,
           caption: inklet.Diagram | None = None) -> inklet.Diagram:
    """A panel under its letter, left-aligned, with an optional caption line."""
    theme = inklet.current_theme()
    parts = [inklet.title(letter), body]
    if caption is not None:
        parts.append(caption)
    return inklet.vstack(parts, gap=theme.gap("xs") if gap is None else gap,
                      align="left")


def rng(seed: int):
    """A generator whose stream is fixed for the life of the figure.

    Panels are built in whatever order the page composes them, and one that
    drew from a shared stream would change every other panel's data the moment
    it was reordered. Each panel takes its own seed.
    """
    import numpy as np
    return np.random.default_rng(seed)


def smooth_series(values, window: int = 5):
    """A centred moving average, for a trace that should read as a measurement
    rather than as noise."""
    out = []
    half = window // 2
    for index in range(len(values)):
        low = max(0, index - half)
        high = min(len(values), index + half + 1)
        out.append(sum(values[low:high]) / (high - low))
    return out


def nice_angle(degrees: float) -> float:
    return degrees * math.pi / 180.0
