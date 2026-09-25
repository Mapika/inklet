"""Bars that grow both ways from zero: Likert scales, two-sided comparisons.

`likert` draws one stacked bar per question from the counts of each
response level, *centred on the neutral level*: the disagreeing levels
extend left of zero, the agreeing ones right, and the neutral level
straddles zero. Reading the two sides against one zero line is the point;
a stacked bar starting at the left edge hides it.

`diverging_bars` draws two quantities per category back to back: the left
one as a bar running left from zero and the right one running right, each
side optionally a stack of several series. It is the "female left / male
right" comparison, and with touching bars the population pyramid
(`Panel.pyramid`). Values on both sides are positive; the axis should
write magnitudes, which is what `unsigned` is for:

    p.axis("bottom", format=inklet.plot.unsigned)

`likert_spans` returns the segment extents without drawing.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Sequence

from ..core import Diagram, DiagramError, Vec2
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND
from ..themes.color import mix
from . import marks as _marks
from .label_spread import label_text, on_fill
from .scale import format_number

__all__ = ["likert", "likert_spans", "likert_colors", "diverging_bars",
           "unsigned"]

#: The neutral level of a Likert bar, as a blend of the ink towards paper.
_NEUTRAL_TINT = 0.8


def unsigned(value) -> str:
    """An axis format writing the magnitude: `-40` is written `40`."""
    return format_number(abs(float(value)))


def _row(counts, index: int) -> list[float]:
    out = []
    for v in counts:
        number = 0.0 if v is None else float(v)
        if math.isnan(number):
            number = 0.0
        if not math.isfinite(number) or number < 0:
            raise DiagramError(
                f"likert counts must be finite and 0 or more, got {v!r} in row {index}")
        out.append(number)
    return out


def likert_spans(counts: Sequence[Sequence[float]], *, neutral: int | None = None,
                 normalize: bool = True) -> list[list[tuple[float, float]]]:
    """Each level's `(start, end)` per row, centred on the neutral level.

    `counts[r][k]` is the count of level `k` (ordered from the most negative
    to the most positive) for row `r`. `neutral` is the index of the
    neutral level; the default is the middle level when there is an odd
    number and none when even. With `normalize=True` each row is scaled to
    percentages summing to 100. The negative levels end at the neutral
    level's left edge and the neutral level is centred on zero.
    """
    rows = [_row(r, i) for i, r in enumerate(counts)]
    if not rows:
        raise DiagramError("likert() was given no rows")
    levels = len(rows[0])
    if levels < 2 or any(len(r) != levels for r in rows):
        raise DiagramError("likert rows need the same number (2 or more) of levels")
    if neutral is None and levels % 2 == 1:
        neutral = levels // 2
    if neutral is not None and not 0 <= neutral < levels:
        raise DiagramError(f"likert neutral={neutral} is outside the {levels} levels")
    out = []
    for row in rows:
        total = sum(row)
        if normalize:
            row = [100.0 * v / total if total > 0 else 0.0 for v in row]
        if neutral is None:
            left = sum(row[:levels // 2])
        else:
            left = sum(row[:neutral]) + row[neutral] / 2
        x = -left
        spans = []
        for v in row:
            spans.append((x, x + v))
            x += v
        out.append(spans)
    return out


def likert_colors(levels: int, neutral: int | None = None) -> tuple[str, ...]:
    """Default Likert colours: vermillion-to-blue from Tol's BuRd ramp,
    strongest at the ends, with a light grey neutral level."""
    from .ramp import DIVERGING
    theme = active_theme()
    if neutral is None and levels % 2 == 1:
        neutral = levels // 2
    below = neutral if neutral is not None else levels // 2
    above = levels - below - (1 if neutral is not None else 0)

    def side(count: int) -> list[float]:
        if count == 1:
            return [0.85]
        return [0.97 - j * 0.27 / (count - 1) for j in range(count)]

    reds = [DIVERGING(t) for t in side(below)]
    blues = [DIVERGING(1 - t) for t in side(above)][::-1]
    middle = [mix(theme.ink, theme.paper, _NEUTRAL_TINT)] if neutral is not None else []
    return tuple(reds + middle + blues)


def likert(panel, at: Sequence, counts, *, neutral: int | None = None,
           normalize: bool = True, orient: str = "h", width: float = 0.7,
           color=None, labels=None, zero: bool = True,
           **style) -> tuple[Diagram, tuple[str, ...], list]:
    """Draw centred Likert bars on `panel`. See `Panel.likert`.

    Returns `(node, colours per level, spans)`.
    """
    places = list(at)
    spans = likert_spans(counts, neutral=neutral, normalize=normalize)
    if len(places) != len(spans):
        raise DiagramError(f"likert() got {len(places)} positions for {len(spans)} rows")
    levels = len(spans[0])
    fills = (likert_colors(levels, neutral) if color is None
             else _marks.series_colors(color, levels))
    stroke = style.pop("stroke", None)
    stroke_width = style.pop("stroke_width", None)
    position, value = _marks._axes_of(panel, orient)
    cells, written = [], []
    theme = active_theme()
    for where, row in zip(places, spans):
        lo, hi = _marks._slot(position, where, width)
        for level, (a, b) in enumerate(row):
            p0, p1 = value.map(a), value.map(b)
            if abs(p1 - p0) < 1e-12:
                continue
            centre = _marks._point(orient, (lo + hi) / 2, (p0 + p1) / 2)
            cells.append(_marks._rect(centre, *_marks._extent(orient, hi - lo, abs(p1 - p0)),
                                      fills[level], stroke, stroke_width))
            if labels is not None and labels is not False:
                text = _label(labels, b - a)
                node = label_text(text, text_fill=on_fill(fills[level]))
                box = node.bbox
                room = abs(p1 - p0) if orient == "h" else hi - lo
                depth = hi - lo if orient == "h" else abs(p1 - p0)
                if box.width + theme.gap("xs") <= room and box.height <= depth:
                    written.append((centre, node))
    rules = []
    if zero:
        z = value.map(0.0)
        a, b = ((panel.area.y0, panel.area.y1) if orient == "h"
                else (panel.area.x0, panel.area.x1))
        rules.append(polyline((_marks._point(orient, a, z), _marks._point(orient, b, z)),
                              kind=MARK_LINE_KIND, stroke=theme.ink,
                              stroke_width=theme.stroke, stroke_linecap="butt"))
    if not cells:
        raise DiagramError("likert() had nothing to draw: every count is zero")
    node = draw_place(cells + rules + written, **style)
    node.notes["likert"] = {"spans": tuple(tuple(r) for r in spans),
                            "colors": tuple(fills)}
    return node, fills, spans


def _label(labels, value: float) -> str:
    if labels is True:
        return f"{value:.0f}"
    if callable(labels):
        return str(labels(value))
    return str(labels).format(value)


def _side(values, what: str) -> list[list[float]]:
    rows = list(values)
    if not rows:
        raise DiagramError(f"diverging_bars {what} was given no values")
    if all(v is None or isinstance(v, Real) for v in rows):
        rows = [rows]
    out = []
    for row in rows:
        series = []
        for v in row:
            number = 0.0 if v is None else float(v)
            if math.isnan(number):
                number = 0.0
            if not math.isfinite(number) or number < 0:
                raise DiagramError(
                    f"diverging_bars {what} values must be 0 or more, got {v!r}; "
                    "the side says the direction")
            series.append(number)
        out.append(series)
    if len({len(r) for r in out}) != 1:
        raise DiagramError(f"every {what} series needs the same number of values")
    return out


def diverging_bars(panel, at: Sequence, left, right, *, orient: str = "h",
                   width: float = 0.7, color=None, reference=None,
                   titles: Sequence[str] | None = None, zero: bool = True,
                   **style) -> tuple[Diagram, tuple[str, ...], tuple[str, ...]]:
    """Draw back-to-back bars on `panel`. See `Panel.diverging_bars`.

    Returns `(node, left colours, right colours)`, one colour per series.
    """
    places = list(at)
    lefts, rights = _side(left, "left"), _side(right, "right")
    for rows, what in ((lefts, "left"), (rights, "right")):
        if len(rows[0]) != len(places):
            raise DiagramError(
                f"diverging_bars {what} has {len(rows[0])} values for {len(places)} positions")
    theme = active_theme()
    if len(lefts) == 1 and len(rights) == 1:
        pair = ((_marks.fill_color(theme, 1), _marks.fill_color(theme, 0)) if color is None
                else _marks.series_colors(color, 2))
        left_fills, right_fills = (pair[0],), (pair[1],)
    else:
        if len(lefts) != len(rights):
            raise DiagramError(
                "stacked diverging bars need the same series on both sides; "
                f"got {len(lefts)} left and {len(rights)} right")
        fills = (tuple(_marks.fill_color(theme, i) for i in range(len(lefts)))
                 if color is None
                 else _marks.series_colors(color, len(lefts)))
        left_fills = right_fills = fills
    stroke = style.pop("stroke", None)
    stroke_width = style.pop("stroke_width", None)
    position, value = _marks._axes_of(panel, orient)
    cells = []
    for index, where in enumerate(places):
        lo, hi = _marks._slot(position, where, width)
        for rows, fills, sign in ((lefts, left_fills, -1.0), (rights, right_fills, 1.0)):
            reach = 0.0
            for s, row in enumerate(rows):
                v = row[index]
                if v <= 0:
                    continue
                a, b = value.map(sign * reach), value.map(sign * (reach + v))
                reach += v
                cells.append(_marks._rect(
                    _marks._point(orient, (lo + hi) / 2, (a + b) / 2),
                    *_marks._extent(orient, hi - lo, abs(b - a)),
                    fills[s], stroke, stroke_width))
    if not cells:
        raise DiagramError("diverging_bars() had nothing to draw: every value is zero")
    a, b = ((panel.area.y0, panel.area.y1) if orient == "h"
            else (panel.area.x0, panel.area.x1))
    rules = []
    if zero:
        z = value.map(0.0)
        rules.append(polyline((_marks._point(orient, a, z), _marks._point(orient, b, z)),
                              kind=MARK_LINE_KIND, stroke=theme.ink,
                              stroke_width=theme.stroke, stroke_linecap="butt"))
    if reference is not None:
        pair = (reference, reference) if isinstance(reference, Real) else tuple(reference)
        if len(pair) != 2:
            raise DiagramError("diverging_bars reference= is one value or (left, right)")
        for sign, level in zip((-1.0, 1.0), pair):
            if level is None:
                continue
            z = value.map(sign * float(level))
            rules.append(polyline((_marks._point(orient, a, z), _marks._point(orient, b, z)),
                                  kind=MARK_LINE_KIND, stroke=theme.ink,
                                  stroke_width=theme.stroke, stroke_dash=(1.0, 0.7),
                                  stroke_linecap="butt"))
    heads = []
    if titles is not None:
        if len(titles) != 2:
            raise DiagramError("diverging_bars titles= is two strings: (left, right)")
        z = value.map(0.0)
        gap = theme.gap("s")
        for title, sign in zip(titles, (-1.0, 1.0)):
            if title is None:
                continue
            node = label_text(title, theme.font_size)
            if orient == "h":
                point = Vec2(z + sign * gap, panel.area.y0 - theme.gap("xs"))
                anchor = "se" if sign < 0 else "sw"
            else:
                point = Vec2(panel.area.x1 + theme.gap("xs"), z - sign * gap)
                anchor = "nw" if sign < 0 else "sw"
            heads.append(draw_place([(point, node)], anchor=anchor, origin=(0, 0)))
    node = draw_place(cells + rules + heads, **style)
    node.notes["diverging_bars"] = {
        "left": tuple(tuple(r) for r in lefts), "right": tuple(tuple(r) for r in rights)}
    return node, left_fills, right_fills
