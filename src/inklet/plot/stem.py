"""Stem plots: a sampled signal as a stem from a baseline to each value.

The discrete-signal counterpart of a line: an impulse response, a sampled
sequence, a spectrum at discrete frequencies. Each sample is a thin stem
from the baseline to a dot at its value, and a rule marks the baseline
itself. Positions are numbers on a continuous scale; for one value per
category use `Panel.lollipop`.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import Diagram, DiagramError, mm
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND, marker as make_marker
from . import marks as _marks

__all__ = ["stem"]

#: Dot diameter as a fraction of the type size: smaller than a scatter
#: marker, because a stem plot usually has many samples close together.
_DOT_OF_TYPE = 0.45


def stem(panel, points: Sequence[Sequence], *, baseline: float = 0.0,
         orient: str = "v", color: str | None = None, marker: str = "circle",
         size: float | str | None = None, hollow: bool = False,
         rule: bool = True, **style) -> tuple[Diagram, str]:
    """Draw stems on `panel`. See `Panel.stem`. Returns `(node, colour)`."""
    data = []
    for item in points:
        x, y = item
        if y is None or (isinstance(y, float) and math.isnan(y)):
            continue
        data.append((x, float(y)))
    if not data:
        raise DiagramError("stem() was given no values")
    theme = active_theme()
    ink = color or theme.ink
    dot = _DOT_OF_TYPE * theme.font_size if size is None else mm(size)
    if dot < 0:
        raise DiagramError(f"stem dots need a size of 0 or more, got {size!r}")
    line = {"stroke": ink, "stroke_width": theme.stroke, "stroke_linecap": "butt"}
    line.update({k: style.pop(k) for k in ("stroke", "stroke_width", "stroke_dash")
                 if k in style})
    position, value = _marks._axes_of(panel, orient)
    base = value.map(baseline)
    stems, dots = [], []
    for where, v in data:
        across = position.map(where)
        tip = value.map(v)
        if abs(tip - base) > 1e-9:
            stems.append(polyline((_marks._point(orient, across, base),
                                   _marks._point(orient, across, tip)),
                                  kind=MARK_LINE_KIND, **line))
        if dot > 0:
            paint = ({"fill": theme.paper, "stroke": ink, "stroke_width": theme.stroke}
                     if hollow else {"fill": ink})
            dots.append((_marks._point(orient, across, tip),
                         make_marker(marker, dot, **paint)))
    rules = []
    if rule:
        lo, hi = ((panel.area.x0, panel.area.x1) if orient == "v"
                  else (panel.area.y0, panel.area.y1))
        rules.append(polyline((_marks._point(orient, lo, base),
                               _marks._point(orient, hi, base)),
                              kind=MARK_LINE_KIND, stroke=theme.ink,
                              stroke_width=theme.stroke, stroke_linecap="butt"))
    node = draw_place(rules + stems + dots, **style)
    node.notes["stem"] = {"count": len(data), "baseline": float(baseline)}
    return node, ink
