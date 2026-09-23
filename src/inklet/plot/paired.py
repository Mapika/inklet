"""Dot plots with connectors: dumbbells and lollipops.

A dumbbell compares two or more values per category: one dot per series on a
shared category position, joined by a line from the smallest to the largest
value. A lollipop is one value per category: a stem from a baseline to a dot.
Both are drawn with the categorical slot arithmetic `bars` uses, so a
dumbbell, a bar chart and a swarm over the same band scale share positions.

Missing values are `None` or NaN. A dumbbell category with one present value
draws that dot and no connector; a lollipop category with no value draws
nothing.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Sequence

from ..core import DiagramError, mm
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND, marker as make_marker
from ..themes.color import mix
from . import marks as _marks

__all__ = ["dumbbell", "lollipop"]

#: Dot diameter as a fraction of the type size: the size of a scatter marker.
_DOT_OF_TYPE = 0.62

#: Connector colour, as a mix of the ink towards paper. Light enough that the
#: dots at either end remain the marks that carry the values.
_CONNECTOR_TINT = 0.62


def _present(value) -> float | None:
    if value is None:
        return None
    number = float(value)
    return None if math.isnan(number) else number


def _rows(values, least: int, what: str) -> list[list[float | None]]:
    rows = list(values)
    if not rows:
        raise DiagramError(f"{what}() was given no values")
    if all(item is None or isinstance(item, Real) for item in rows):
        rows = [rows]
    out = [[_present(v) for v in row] for row in rows]
    if len({len(row) for row in out}) != 1:
        raise DiagramError(f"every {what} series needs the same number of values")
    if len(out) < least:
        raise DiagramError(
            f"{what}() needs at least {least} series, got {len(out)}")
    return out


def _dot_colors(colors, count: int, theme) -> tuple[str, ...]:
    """Series colours dark enough for dots about a millimetre across."""
    if colors is not None:
        return _marks.series_colors(colors, count)
    if count == 1:
        return (theme.ink,)
    return tuple(theme.color(i) for i in range(count))


def _centre(scale, where) -> float:
    lo, hi = _marks._slot(scale, where, 0.0)
    return (lo + hi) / 2


def dumbbell(panel, at: Sequence, values, *, orient: str = "v",
             size: float | str | None = None, colors=None,
             marker: str = "circle", connector: dict | None = None,
             **style):
    """Dots per series joined per category. See `Panel.dumbbell`.

    Returns `(node, colors)`: the drawing and the colour used for each series.
    """
    places = list(at)
    rows = _rows(values, 2, "dumbbell")
    if len(places) != len(rows[0]):
        raise DiagramError(
            f"dumbbell() got {len(places)} positions for {len(rows[0])} values")
    theme = active_theme()
    dot = _DOT_OF_TYPE * theme.font_size if size is None else mm(size)
    if dot <= 0:
        raise DiagramError(f"dumbbell dots need a positive size, got {size!r}")
    fills = _dot_colors(style.pop("fill", None) if colors is None else colors,
                        len(rows), theme)
    line = {"stroke": mix(theme.ink, theme.paper, _CONNECTOR_TINT),
            "stroke_width": theme.thick, "stroke_linecap": "butt"}
    line.update(connector or {})
    position, value = _marks._axes_of(panel, orient)
    lines, dots = [], []
    for index, where in enumerate(places):
        across = _centre(position, where)
        present = [(s, row[index]) for s, row in enumerate(rows)
                   if row[index] is not None]
        if len(present) >= 2:
            low = min(v for _, v in present)
            high = max(v for _, v in present)
            if high > low:
                lines.append(polyline(
                    (_marks._point(orient, across, value.map(low)),
                     _marks._point(orient, across, value.map(high))),
                    kind=MARK_LINE_KIND, **line))
        for s, v in present:
            dots.append((_marks._point(orient, across, value.map(v)),
                         make_marker(marker, dot, fill=fills[s])))
    if not dots:
        raise DiagramError("dumbbell() had nothing to draw: every value is missing")
    return draw_place(lines + dots, **style), fills


def lollipop(panel, at: Sequence, values, *, baseline: float = 0.0,
             orient: str = "v", size: float | str | None = None,
             color: str | None = None, marker: str = "circle",
             stem: dict | None = None, **style):
    """A stem from the baseline and a dot per value. See `Panel.lollipop`."""
    places = list(at)
    row = _rows(values, 1, "lollipop")
    if len(row) != 1:
        raise DiagramError("lollipop() draws one series; use dumbbell() for several")
    row = row[0]
    if len(places) != len(row):
        raise DiagramError(
            f"lollipop() got {len(places)} positions for {len(row)} values")
    theme = active_theme()
    dot = _DOT_OF_TYPE * theme.font_size if size is None else mm(size)
    if dot <= 0:
        raise DiagramError(f"lollipop dots need a positive size, got {size!r}")
    ink = style.pop("fill", None) or color or theme.ink
    line = {"stroke": ink, "stroke_width": theme.stroke,
            "stroke_linecap": "butt"}
    line.update(stem or {})
    position, value = _marks._axes_of(panel, orient)
    base = value.map(baseline)
    stems, dots = [], []
    for where, v in zip(places, row):
        if v is None:
            continue
        across = _centre(position, where)
        tip = value.map(v)
        if abs(tip - base) > 1e-9:
            stems.append(polyline((_marks._point(orient, across, base),
                                   _marks._point(orient, across, tip)),
                                  kind=MARK_LINE_KIND, **line))
        dots.append((_marks._point(orient, across, tip),
                     make_marker(marker, dot, fill=ink)))
    if not dots:
        raise DiagramError("lollipop() had nothing to draw: every value is missing")
    return draw_place(stems + dots, **style), ink
