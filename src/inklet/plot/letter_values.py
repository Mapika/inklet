"""Letter-value (boxen) plots: nested boxes at the quartiles, eighths,
sixteenths and so on.

A box plot summarises a large sample by five numbers and then draws every
point past the whiskers, which for 10,000 observations is hundreds of
"outliers" that are simply the tails. A letter-value plot (Hofmann, Wickham
and Kafadar, 2017, J. Comput. Graph. Stat. 26:469-477) keeps going out
into the tails: box `k` spans the quantiles ``2**-(k+2)`` and
``1 - 2**-(k+2)``, so the first is the interquartile box, the second holds
the middle 75%, the third 87.5%, and so on. Each box is narrower and paler
than the one inside it. Observations beyond the outermost box are drawn as
points.

`letter_values` computes the boxes; quantiles are type 7, as `box_stats`
uses. The number of boxes is chosen by `depth`:

- `"tukey"` (default): ``floor(log2(n)) - 3``, at least 1;
- `"trustworthy"`: the deepest letter value whose 95% confidence interval
  does not overlap the next, ``floor(log2(n)) - floor(log2(2 * 1.96**2)) + 1``
  (Hofmann et al., eq. 3), at least 1;
- a whole number, used as given.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..core import Diagram, DiagramError, mm
from ..draw.coords import active_theme
from ..draw.path import polygon, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND, marker as make_marker
from ..themes.color import mix
from . import marks as _marks
from .statistics import _quantile_sorted

__all__ = ["LetterValues", "letter_values"]

#: How far the outermost box is blended towards paper.
_PALEST = 0.82
#: The narrowest box, as a fraction of the slot.
_NARROWEST = 0.3


@dataclass(frozen=True)
class LetterValues:
    """The boxes of one letter-value plot, innermost first.

    `boxes[k]` is `(low, high)` at the quantiles ``2**-(k+2)`` and
    ``1 - 2**-(k+2)``; `outliers` are the values outside the last box.
    """

    median: float
    boxes: tuple[tuple[float, float], ...]
    outliers: tuple[float, ...]
    count: int


def _depth(n: int, depth) -> int:
    if depth == "tukey":
        return max(1, int(math.floor(math.log2(n))) - 3)
    if depth == "trustworthy":
        z = 1.959963984540054
        return max(1, int(math.floor(math.log2(n)))
                   - int(math.floor(math.log2(2 * z * z))) + 1)
    if isinstance(depth, int) and not isinstance(depth, bool) and depth >= 1:
        return depth
    raise DiagramError(
        f'letter-value depth is "tukey", "trustworthy" or a whole number, not {depth!r}')


def letter_values(values: Sequence[float], *, depth="tukey") -> LetterValues:
    """The nested boxes of a letter-value plot of `values`."""
    ordered = sorted(float(v) for v in values
                     if v is not None and math.isfinite(float(v)))
    n = len(ordered)
    if n == 0:
        raise DiagramError("a letter-value plot needs at least one value")
    k = _depth(n, depth) if n > 1 else 1
    boxes = tuple((_quantile_sorted(ordered, 2.0 ** -(i + 2)),
                   _quantile_sorted(ordered, 1.0 - 2.0 ** -(i + 2)))
                  for i in range(k))
    low, high = boxes[-1]
    return LetterValues(median=_quantile_sorted(ordered, 0.5), boxes=boxes,
                        outliers=tuple(v for v in ordered if v < low or v > high),
                        count=n)


def boxen_layer(panel, groups, *, at=None, width: float = 0.8, orient: str = "v",
                depth="tukey", outliers: bool = True, color=None,
                size: float | str | None = None, **style) -> tuple[Diagram, dict]:
    """Nested boxes of `Panel.boxen`. Returns `(node, note)`."""
    places, data = _marks._groups(panel, groups, at, orient)
    position, value = _marks._axes_of(panel, orient)
    theme = active_theme()
    inks = _marks._swarm_colors(color, len(data), theme)
    dot = _marks._OUTLIER_OF_TYPE * theme.font_size if size is None else mm(size)
    items: list = []
    note = {"boxes": [], "outliers": []}
    for where, sample, ink in zip(places, data, inks):
        clean = [v for v in sample if math.isfinite(v)]
        if not clean:
            note["boxes"].append(0)
            note["outliers"].append(0)
            continue
        lv = letter_values(clean, depth=depth)
        lo, hi = _marks._slot(position, where, width)
        middle, half = (lo + hi) / 2, abs(hi - lo) / 2
        count = len(lv.boxes)
        boxes = []
        for k in range(count - 1, -1, -1):      # outermost first, so inner ones sit on top
            share = 0.0 if count == 1 else k / (count - 1)
            reach = half * (1.0 - (1.0 - _NARROWEST) * share)
            tint = mix(ink, theme.paper, 0.08 + (_PALEST - 0.08) * share)
            a, b = value.map(lv.boxes[k][0]), value.map(lv.boxes[k][1])
            paint = {"fill": tint, "stroke": theme.paper,
                     "stroke_width": theme.hairline}
            paint.update(style)
            boxes.append(polygon(
                (_marks._point(orient, middle - reach, a), _marks._point(orient, middle + reach, a),
                 _marks._point(orient, middle + reach, b), _marks._point(orient, middle - reach, b)),
                kind=MARK_KIND, **paint))
        items.extend(boxes)
        at_median = value.map(lv.median)
        items.append(polyline((_marks._point(orient, middle - half, at_median),
                               _marks._point(orient, middle + half, at_median)),
                              kind=MARK_LINE_KIND, stroke=theme.paper,
                              stroke_width=theme.thick, stroke_linecap="butt"))
        if outliers:
            for v in lv.outliers:
                items.append((_marks._point(orient, middle, value.map(v)),
                              make_marker("circle", dot, fill=mix(ink, theme.paper, 0.35))))
        note["boxes"].append(count)
        note["outliers"].append(len(lv.outliers))
    if not items:
        raise DiagramError("boxen() had nothing to draw")
    node = draw_place(items, origin=(0, 0), kind="boxen")
    node.notes["boxen"] = note
    return node, note
