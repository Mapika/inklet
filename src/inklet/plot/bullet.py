"""Bullet charts: a measure against a target and qualitative bands.

Stephen Few's replacement for a gauge. Each row is a wide band divided
into qualitative ranges (poor, fair, good) in shades of grey, darkest for
the lowest range; a narrow bar for the measure along the middle of it; and
a short rule across the bar at the target. Several rows share one value
axis when they share units; otherwise draw one panel per row.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Sequence

from ..core import Diagram, DiagramError
from ..draw.coords import active_theme
from ..draw.place import place as draw_place
from ..themes.color import mix
from . import marks as _marks

__all__ = ["bullet", "bullet_shades"]

#: The measure bar as a fraction of the band width, and the target rule.
_BAR_OF_BAND = 0.34
_TARGET_OF_BAND = 0.72
#: The target rule's thickness, as a multiple of the theme's thick stroke.
_TARGET_WEIGHT = 1.4


def bullet_shades(count: int) -> tuple[str, ...]:
    """Greys for `count` qualitative ranges, darkest (lowest range) first."""
    theme = active_theme()
    if count <= 0:
        return ()
    if count == 1:
        return (mix(theme.ink, theme.paper, 0.85),)
    return tuple(mix(theme.ink, theme.paper, 0.62 + 0.30 * i / (count - 1))
                 for i in range(count))


def _optional(values, count: int, what: str) -> list:
    if values is None:
        return [None] * count
    if isinstance(values, Real):
        return [float(values)] * count
    out = list(values)
    if len(out) != count:
        raise DiagramError(f"bullet {what} has {len(out)} entries for {count} rows")
    return out


def bullet(panel, at: Sequence, values: Sequence[float], *, targets=None,
           ranges=None, baseline: float = 0.0, orient: str = "h", width: float = 0.7,
           color: str | None = None, **style) -> Diagram:
    """Draw bullet charts on `panel`. See `Panel.bullet`."""
    places = list(at)
    measures = [None if v is None else float(v) for v in values]
    if len(places) != len(measures):
        raise DiagramError(f"bullet() got {len(places)} positions for {len(measures)} values")
    goals = _optional(targets, len(places), "targets")
    if ranges is None or (ranges and all(isinstance(r, Real) for r in ranges)):
        ranges = [ranges] * len(places)
    bands = _optional(ranges, len(places), "ranges")
    theme = active_theme()
    ink = color or theme.ink
    position, scale = _marks._axes_of(panel, orient)
    base = scale.map(baseline)
    shading, bars, rules = [], [], []
    for where, measure, goal, limits in zip(places, measures, goals, bands):
        lo, hi = _marks._slot(position, where, width)
        mid, span = (lo + hi) / 2, hi - lo
        if limits:
            limits = sorted(float(v) for v in limits)
            shades = bullet_shades(len(limits))
            # Widest first, so each narrower range is painted over it.
            for limit, shade in reversed(list(zip(limits, shades))):
                end = scale.map(limit)
                shading.append(_marks._rect(
                    _marks._point(orient, mid, (base + end) / 2),
                    *_marks._extent(orient, span, abs(end - base)), shade, None, None))
        if measure is not None and math.isfinite(measure):
            end = scale.map(measure)
            if abs(end - base) > 1e-12:
                bars.append(_marks._rect(
                    _marks._point(orient, mid, (base + end) / 2),
                    *_marks._extent(orient, span * _BAR_OF_BAND, abs(end - base)),
                    ink, None, None))
        if goal is not None:
            at = scale.map(float(goal))
            half = span * _TARGET_OF_BAND / 2
            # A filled bar, not a stroke: the target is a mark, and keeping it
            # out of the stroke weights keeps the figure to three of them.
            rules.append(_marks._rect(_marks._point(orient, mid, at),
                                      *_marks._extent(orient, half * 2,
                                                      theme.thick * _TARGET_WEIGHT),
                                      ink, None, None))
    if not (shading or bars or rules):
        raise DiagramError("bullet() had nothing to draw")
    node = draw_place(shading + bars + rules, **style)
    node.notes["bullet"] = {"values": tuple(measures), "targets": tuple(goals)}
    return node
