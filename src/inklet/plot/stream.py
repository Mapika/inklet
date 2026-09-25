"""Streamgraphs: stacked areas around a moving baseline.

`Panel.stackarea` stacks series up from a fixed baseline, which makes the
total easy to read and every layer above the first hard to follow, because
each inherits the wobble of all the layers beneath it. A streamgraph moves
the baseline instead:

* `"silhouette"` centres the stack on zero, so the outline is symmetric;
* `"wiggle"` chooses the baseline that minimises the weighted change in
  slope of all the layers (Byron & Wattenberg 2008, the offset d3 calls
  `stackOffsetWiggle`), which keeps each layer as flat as it can be;
* `"zero"` is an ordinary stacked area, and `"expand"` normalises every x
  to a total of 1.

`order="inside-out"` puts the series that peak earliest in the middle and
the later ones alternately above and below, which with `"wiggle"` is the
classic streamgraph. `stream_layers` returns the layer boundaries without
drawing, which is how to choose the y domain first.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import Diagram, DiagramError
from ..draw.coords import active_theme
from ..draw.path import catmull_rom, path as draw_path, straight_cubic
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND
from . import marks as _marks

__all__ = ["STREAM_OFFSETS", "STREAM_ORDERS", "stream_layers", "stream_order",
           "streamgraph"]

STREAM_OFFSETS = ("wiggle", "silhouette", "zero", "expand")
STREAM_ORDERS = ("input", "inside-out")


def stream_order(values, order: str = "input") -> list[int]:
    """The stacking order of the series, bottom first."""
    rows = _marks._series(values)
    if order not in STREAM_ORDERS:
        raise DiagramError(f"stream order= is one of {STREAM_ORDERS}, not {order!r}")
    if order == "input":
        return list(range(len(rows)))
    # d3.stackOrderInsideOut: by the index of each series' peak, then placed
    # alternately on whichever side currently has the smaller total.
    peaks = sorted(range(len(rows)),
                   key=lambda s: (max(range(len(rows[s])), key=lambda i: rows[s][i]), s))
    top, bottom, tops, bottoms = 0.0, 0.0, [], []
    for s in peaks:
        total = sum(rows[s])
        if top < bottom:
            top += total
            tops.append(s)
        else:
            bottom += total
            bottoms.append(s)
    return bottoms[::-1] + tops


def stream_layers(values, *, offset: str = "wiggle",
                  order: str = "input") -> list[tuple[tuple[float, ...], tuple[float, ...]]]:
    """`(lower, upper)` for every series, in input order.

    `values` is series-major, one value per x in each series, all 0 or
    more. The wiggle offset assumes evenly spaced x.
    """
    if offset not in STREAM_OFFSETS:
        raise DiagramError(f"stream offset= is one of {STREAM_OFFSETS}, not {offset!r}")
    rows = _marks._series(values)
    if any(not math.isfinite(v) or v < 0 for row in rows for v in row):
        raise DiagramError("streamgraph values must be finite and 0 or more")
    stacking = stream_order(rows, order)
    n = len(rows[0])
    totals = [sum(rows[s][i] for s in range(len(rows))) for i in range(n)]
    if offset == "expand":
        rows = tuple(tuple(v / totals[i] if totals[i] > 0 else 0.0
                           for i, v in enumerate(row)) for row in rows)
        base = [0.0] * n
    elif offset == "zero":
        base = [0.0] * n
    elif offset == "silhouette":
        base = [-t / 2 for t in totals]
    else:
        base = _wiggle([rows[s] for s in stacking])
    out: list = [None] * len(rows)
    lower = list(base)
    for s in stacking:
        upper = [a + b for a, b in zip(lower, rows[s])]
        out[s] = (tuple(lower), tuple(upper))
        lower = upper
    return out


def _wiggle(rows: Sequence[Sequence[float]]) -> list[float]:
    """d3's stackOffsetWiggle, then shifted so the stack is centred on zero
    on average (the published offset starts at zero at the first x)."""
    n = len(rows[0])
    y = 0.0
    base = [0.0]
    for j in range(1, n):
        s1 = s2 = 0.0
        for i, row in enumerate(rows):
            sij0, sij1 = row[j], row[j - 1]
            s3 = (sij0 - sij1) / 2
            for k in range(i):
                s3 += rows[k][j] - rows[k][j - 1]
            s1 += sij0
            s2 += s3 * sij0
        y -= s2 / s1 if s1 else 0.0
        base.append(y)
    totals = [sum(row[j] for row in rows) for j in range(n)]
    shift = sum(b + t / 2 for b, t in zip(base, totals)) / n
    return [b - shift for b in base]


def streamgraph(panel, x: Sequence, values, *, offset: str = "wiggle",
                order: str = "input", color=None, smooth: float = 0.5,
                **style) -> tuple[Diagram, tuple[str, ...], list]:
    """Draw a streamgraph on `panel`. See `Panel.streamgraph`.

    Returns `(node, colours, layers)`.
    """
    xs = list(x)
    layers = stream_layers(values, offset=offset, order=order)
    if len(layers[0][0]) != len(xs):
        raise DiagramError("streamgraph needs one value per x in every series")
    if len(xs) < 2:
        raise DiagramError("streamgraph needs at least two x values")
    theme = active_theme()
    count = len(layers)
    fills = (tuple(theme.color(i + 1) for i in range(count)) if color is None
             else _marks.series_colors(color, count))
    stroke = style.pop("stroke", theme.paper)
    stroke_width = style.pop("stroke_width", theme.hairline)
    shapes = []
    for s, (lower, upper) in enumerate(layers):
        top = [panel.point(a, b) for a, b in zip(xs, upper)]
        bottom = [panel.point(a, b) for a, b in reversed(list(zip(xs, lower)))]
        if smooth > 0:
            chain = (list(catmull_rom(top, smooth)) + [straight_cubic(top[-1], bottom[0])]
                     + list(catmull_rom(bottom, smooth)) + [straight_cubic(bottom[-1], top[0])])
            shapes.append(draw_path(curves=chain, closed=True, filled=True, kind=MARK_KIND,
                                    fill=fills[s], stroke=stroke,
                                    stroke_width=stroke_width))
        else:
            shapes.append(draw_path(top + bottom, closed=True, filled=True, kind=MARK_KIND,
                                    fill=fills[s], stroke=stroke,
                                    stroke_width=stroke_width))
    node = draw_place(shapes, **style)
    node.notes["streamgraph"] = {"offset": offset, "order": order,
                                 "extent": (min(min(lo) for lo, _ in layers),
                                            max(max(hi) for _, hi in layers))}
    return node, fills, layers
