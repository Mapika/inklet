"""Point density on continuous axes: hexagonal bins, 2D histograms and a
scatter coloured by local density.

`histogram2d` and `point_density` do the arithmetic and draw nothing.
`Panel.hexbin`, `Panel.hist2d` and `Panel.density_scatter` call the drawing
halves here.

Hexagons are laid out on the *page*, not in data units: `gridsize` hexagons
span the width of the plot area and every hexagon is regular however the
axes are scaled, including on log axes. 2D histogram bins are laid out in
data units: equal widths on a linear axis and equal ratios on a log axis.

`point_density` is estimated on the page too: the points are binned on a
lattice in millimetres and smoothed with a separable Gaussian of `bandwidth`
millimetres, and each point reads the smoothed value at its own position.
That makes the colour a statement about crowding *as drawn*, which is what a
density-coloured scatter is for: it reveals where marks overlap. It is
linear in the number of points, so 100,000 points take about a second.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import Diagram, DiagramError
from ..draw.coords import active_theme
from ..draw.path import polygon
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND
from .metadata import declare_domain
from .scale import Band, Log, linear, log
from .statistics import _bin_edges

__all__ = ["histogram2d", "point_density", "DENSITY_RAMP"]

#: Largest lattice for `point_density`, in cells per side.
_MAX_CELLS = 400


def _density_ramp():
    """Magma from orange to near black: the default for density scatters
    and hexagons. The pale end of the matrix ramp is left out, because a
    single isolated point in pale yellow is invisible on white paper."""
    from .ramp import SEQUENTIAL, Ramp
    return Ramp(tuple(SEQUENTIAL(0.18 + 0.82 * k / 8) for k in range(9)))


DENSITY_RAMP = _density_ramp()


def _finite_pairs(points) -> list[tuple[float, float]]:
    out = []
    for p in points:
        x, y = p[0], p[1]
        if x is None or y is None:
            continue
        x, y = float(x), float(y)
        if math.isfinite(x) and math.isfinite(y):
            out.append((x, y))
    return out


def _mappable(scale, v: float) -> bool:
    return v > 0 if isinstance(scale, Log) else True


def _continuous(panel, what: str) -> None:
    if isinstance(panel.x, Band) or isinstance(panel.y, Band):
        raise DiagramError(f"{what} needs continuous x and y scales")


# -- 2D histogram -------------------------------------------------------------


def _edges_for(bins, values: list[float], scale, span) -> list[float]:
    if not isinstance(bins, int) or isinstance(bins, bool):
        edges = [float(e) for e in bins]
        if len(edges) < 2 or any(b <= a for a, b in zip(edges, edges[1:])):
            raise DiagramError("2D histogram edges need two or more increasing values")
        return edges
    if bins < 1:
        raise DiagramError(f"a 2D histogram needs at least one bin, got {bins}")
    lo, hi = (min(values), max(values)) if span is None else (float(span[0]), float(span[1]))
    if isinstance(scale, Log):
        if lo <= 0:
            raise DiagramError("log-axis bins need positive values")
        if hi <= lo:
            return [lo / 1.5, lo * 1.5]
        a, b = math.log10(lo), math.log10(hi)
        return [10 ** (a + (b - a) * k / bins) for k in range(bins + 1)]
    if span is not None:
        if hi <= lo:
            raise DiagramError("a 2D histogram range needs high > low")
        return [lo + (hi - lo) * k / bins for k in range(bins + 1)]
    return _bin_edges(bins, lo, hi)


def histogram2d(points: Sequence[Sequence[float]], bins=20, *, range=None,
                density: bool = False, x_scale=None, y_scale=None
                ) -> tuple[tuple[float, ...], tuple[float, ...], tuple[tuple[float, ...], ...]]:
    """Counts of points on a rectangular grid: `(x_edges, y_edges, counts)`.

    `counts[j][i]` is the number of points in x bin `i` and y bin `j`. `bins`
    is one count or edge list for both axes, or an `(x, y)` pair of them. A
    count gives round edges over the data (as `histogram` does) or, with
    `range=((x0, x1), (y0, y1))`, even edges over that range. Pass
    `x_scale=`/`y_scale=` a log scale for bins of equal ratio. Bins are
    half-open except the last, which includes its upper edge; points
    outside every bin are not counted. `density=True` divides by the number
    of points counted and by each bin's area, so the counts integrate to 1.
    """
    data = _finite_pairs(points)
    if x_scale is not None and isinstance(x_scale, Log):
        data = [p for p in data if p[0] > 0]
    if y_scale is not None and isinstance(y_scale, Log):
        data = [p for p in data if p[1] > 0]
    if not data:
        raise DiagramError("a 2D histogram needs at least one finite point")
    # A pair of counts or of edge lists is per axis; anything else is shared.
    if isinstance(bins, (tuple, list)) and len(bins) == 2 and all(
            (isinstance(b, int) and not isinstance(b, bool))
            or not isinstance(b, (int, float)) for b in bins):
        bx, by = bins
    else:
        bx = by = bins
    rx, ry = (None, None) if range is None else range
    xe = _edges_for(bx, [p[0] for p in data], x_scale, rx)
    ye = _edges_for(by, [p[1] for p in data], y_scale, ry)
    counts = [[0.0] * (len(xe) - 1) for _ in ye[1:]]
    from bisect import bisect_right
    total = 0
    for x, y in data:
        if not (xe[0] <= x <= xe[-1] and ye[0] <= y <= ye[-1]):
            continue
        i = min(bisect_right(xe, x) - 1, len(xe) - 2)
        j = min(bisect_right(ye, y) - 1, len(ye) - 2)
        counts[j][i] += 1.0
        total += 1
    if density and total:
        counts = [[c / (total * (xe[i + 1] - xe[i]) * (ye[j + 1] - ye[j]))
                   for i, c in enumerate(row)] for j, row in enumerate(counts)]
    return tuple(xe), tuple(ye), tuple(tuple(row) for row in counts)


def _colouring(values: list[float], ramp, scale, log_counts: bool):
    positive = [v for v in values if v > 0]
    if scale is None:
        high = max(values)
        if log_counts:
            low = min(positive) if positive else 1.0
            scale = log((low, high if high > low else low * 10))
        else:
            scale = linear((0.0, high if high > 0 else 1.0))
    ramp = DENSITY_RAMP if ramp is None else ramp
    unit = scale.with_range(0.0, 1.0)

    def paint(v: float) -> str:
        t = unit.map(v)
        return ramp(min(1.0, max(0.0, t)))
    return ramp, scale, paint


def hist2d_layer(panel, points, *, bins=20, range=None, density: bool = False,
                 min_count: float = 1, ramp=None, scale=None, log: bool = False,
                 **style) -> tuple[Diagram, object, object, dict]:
    """Rectangles of `Panel.hist2d`. Returns `(node, ramp, scale, note)`."""
    _continuous(panel, "hist2d")
    xe, ye, counts = histogram2d(points, bins, range=range, density=density,
                                 x_scale=panel.x, y_scale=panel.y)
    raw = histogram2d(points, (list(xe), list(ye)), x_scale=panel.x,
                      y_scale=panel.y)[2] if density else counts
    shown = [counts[j][i] for j in _range(len(ye) - 1) for i in _range(len(xe) - 1)
             if raw[j][i] >= min_count]
    if not shown:
        raise DiagramError("hist2d() has no bin with at least min_count points")
    ramp, scale, paint = _colouring(shown, ramp, scale, log)
    theme = active_theme()
    items = []
    for j in _range(len(ye) - 1):
        y0, y1 = panel.y.map(ye[j]), panel.y.map(ye[j + 1])
        for i in _range(len(xe) - 1):
            if raw[j][i] < min_count:
                continue
            x0, x1 = panel.x.map(xe[i]), panel.x.map(xe[i + 1])
            ink = paint(counts[j][i])
            cell = {"fill": ink, "stroke": ink, "stroke_width": theme.hairline}
            cell.update(style)
            items.append(polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
                                 kind=MARK_KIND, **cell))
    node = draw_place(items, origin=(0, 0), kind="hist2d")
    declare_domain(node, scale)
    note = {"x_edges": xe, "y_edges": ye, "cells": len(items),
            "max": max(shown), "density": density}
    node.notes["hist2d"] = note
    return node, ramp, scale, note


_range = range


# -- hexagonal bins -----------------------------------------------------------


def hexbin_layer(panel, points, *, gridsize: int = 24, min_count: int = 1,
                 ramp=None, scale=None, log: bool = False,
                 **style) -> tuple[Diagram, object, object, dict]:
    """Hexagons of `Panel.hexbin`. Returns `(node, ramp, scale, note)`."""
    _continuous(panel, "hexbin")
    if not isinstance(gridsize, int) or gridsize < 1:
        raise DiagramError(f"hexbin gridsize is a positive whole number, got {gridsize!r}")
    area = panel.area
    w = area.width / gridsize               # centre-to-centre across a row
    r = w / math.sqrt(3.0)                  # corner radius, pointy-top
    pitch = 1.5 * r                         # row spacing
    x0, y0 = area.x0, area.y1               # bottom-left corner of the area
    counts: dict[tuple[int, int], int] = {}
    for x, y in _finite_pairs(points):
        if not (_mappable(panel.x, x) and _mappable(panel.y, y)):
            continue
        px, py = panel.x.map(x), panel.y.map(y)
        if not (area.x0 <= px <= area.x1 and area.y0 <= py <= area.y1):
            continue                        # off the axes: not in any hexagon shown
        # Row index counts upward from the bottom of the area.
        fy = (y0 - py) / pitch
        fx = (px - x0) / w
        best = None
        for row in (math.floor(fy), math.floor(fy) + 1):
            shift = 0.5 if row % 2 else 0.0
            col = round(fx - shift)
            cx = x0 + (col + shift) * w
            cy = y0 - row * pitch
            d = (px - cx) ** 2 + (py - cy) ** 2
            if best is None or d < best[0] - 1e-12:
                best = (d, row, col)
        key = (best[1], best[2])
        counts[key] = counts.get(key, 0) + 1
    shown = sorted((k, c) for k, c in counts.items() if c >= min_count)
    if not shown:
        raise DiagramError("hexbin() has no hexagon with at least min_count points")
    ramp, scale, paint = _colouring([float(c) for _, c in shown], ramp, scale, log)
    theme = active_theme()
    corners = [(r * math.cos(math.radians(90 + 60 * k)),
                -r * math.sin(math.radians(90 + 60 * k))) for k in range(6)]
    items = []
    for (row, col), c in shown:
        shift = 0.5 if row % 2 else 0.0
        cx, cy = x0 + (col + shift) * w, y0 - row * pitch
        ink = paint(float(c))
        cell = {"fill": ink, "stroke": ink, "stroke_width": theme.hairline}
        cell.update(style)
        items.append(polygon([(cx + a, cy + b) for a, b in corners],
                             kind=MARK_KIND, **cell))
    node = draw_place(items, origin=(0, 0), kind="hexbin")
    declare_domain(node, scale)
    note = {"gridsize": gridsize, "cells": len(items),
            "max": max(c for _, c in shown), "diameter": 2 * r,
            "total": sum(counts.values())}
    node.notes["hexbin"] = note
    return node, ramp, scale, note


# -- density-coloured scatter ---------------------------------------------------


def point_density(panel, points, *, bandwidth: float | None = None
                  ) -> tuple[list[tuple[float, float]], list[float], float]:
    """Each drawable point's local density on the page.

    Returns `(points, density, bandwidth)`: the points that map onto this
    panel's scales (a log axis drops zero and negative values), the density
    at each as a fraction of the largest, and the Gaussian bandwidth used in
    millimetres. The default bandwidth is the normal-reference rule
    ``sd * n ** (-1/6)`` on the page coordinates, the smaller of the two
    axes, and at least 0.3 mm.
    """
    kept, xs, ys = [], [], []
    for x, y in _finite_pairs(points):
        if _mappable(panel.x, x) and _mappable(panel.y, y):
            px, py = panel.x.map(x), panel.y.map(y)
            if math.isfinite(px) and math.isfinite(py):
                kept.append((x, y))
                xs.append(px)
                ys.append(py)
    n = len(kept)
    if n == 0:
        raise DiagramError("density_scatter() has no point these axes can show")
    if n == 1:
        return kept, [1.0], 0.0
    if bandwidth is None:
        def sd(v):
            m = math.fsum(v) / n
            return math.sqrt(math.fsum((a - m) ** 2 for a in v) / (n - 1))
        spreads = [s for s in (sd(xs), sd(ys)) if s > 0]
        h = max(0.3, (min(spreads) if spreads else 1.0) * n ** (-1.0 / 6.0))
    else:
        h = float(bandwidth)
        if not h > 0:
            raise DiagramError(f"density_scatter bandwidth must be positive, got {bandwidth!r}")
    x0, x1 = min(xs) - 3 * h, max(xs) + 3 * h
    y0, y1 = min(ys) - 3 * h, max(ys) + 3 * h
    cell = max(h / 2.5, (x1 - x0) / _MAX_CELLS, (y1 - y0) / _MAX_CELLS)
    nx = int(math.ceil((x1 - x0) / cell)) + 2
    ny = int(math.ceil((y1 - y0) / cell)) + 2
    grid = [[0.0] * nx for _ in range(ny)]
    for px, py in zip(xs, ys):
        fx, fy = (px - x0) / cell, (py - y0) / cell
        i, j = int(fx), int(fy)
        u, v = fx - i, fy - j
        grid[j][i] += (1 - u) * (1 - v)
        grid[j][i + 1] += u * (1 - v)
        grid[j + 1][i] += (1 - u) * v
        grid[j + 1][i + 1] += u * v
    from .kernel_density import _convolve, _kernel
    kernel = _kernel(cell / h)
    rows = [_convolve(row, kernel) for row in grid]
    cols = [_convolve([rows[j][i] for j in range(ny)], kernel) for i in range(nx)]
    values = []
    for px, py in zip(xs, ys):
        fx, fy = (px - x0) / cell, (py - y0) / cell
        i, j = int(fx), int(fy)
        u, v = fx - i, fy - j
        values.append((1 - u) * (1 - v) * cols[i][j] + u * (1 - v) * cols[i + 1][j]
                      + (1 - u) * v * cols[i][j + 1] + u * v * cols[i + 1][j + 1])
    peak = max(values)
    return kept, [v / peak for v in values], h
