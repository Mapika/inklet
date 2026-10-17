"""Contour lines of a field sampled on a grid: a histogram's counts, a surface.

`Panel.contour` draws the lines where a gridded field reaches each level. The
levels are values of the field, or, with `hdr=`, the highest-density regions
holding the given shares of its total: `hdr=(0.683, 0.954)` draws the one- and
two-sigma regions of a 2D histogram. `inklet.plot.mass_levels` returns the z
values behind those regions, for a grid or a `Density2D`.

The field is the value at each node of the grid, with node `z[j][i]` at
`(x[i], y[j])`. Between two nodes the contour is found by linear interpolation
along the edge, using the same marching squares as `Panel.kde2d`. The rings are
drawn in page millimetres, so a log axis bends them the way it bends the axis.
A missing value (None or NaN) counts as lying below every level, so a contour
closes round a gap instead of running through it.
"""

from __future__ import annotations

import math
from numbers import Real

from ..core import DiagramError
from ..draw.coords import active_theme
from ..draw.path import path as draw_path
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND
from .kernel_density import _level_colors, mass_levels
from .outlines import _contours

__all__ = ["grid_contour_layer"]


def _axis(values, name: str) -> list[float]:
    out = [float(v) for v in values]
    if len(out) < 2:
        raise DiagramError(f"contour needs at least two {name} positions, got {len(out)}")
    steps = [b - a for a, b in zip(out, out[1:])]
    if not all(math.isfinite(s) for s in steps):
        raise DiagramError(f"contour {name} positions must be finite")
    if not (all(s > 0 for s in steps) or all(s < 0 for s in steps)):
        raise DiagramError(f"contour {name} positions must strictly increase or decrease")
    return out


def _value(v) -> float | None:
    """A grid value as a float, or None for a missing one."""
    if v is None:
        return None
    f = float(v)
    if math.isnan(f):
        return None
    if math.isinf(f):
        raise DiagramError(f"contour values must be finite or missing (None), not {v!r}")
    return f


def _levels(levels) -> tuple[float, ...]:
    if isinstance(levels, Real) and not isinstance(levels, bool):
        raise DiagramError(
            "contour levels= is a list of z values; for highest-density regions "
            "pass hdr=, for example hdr=(0.683, 0.954)")
    out = []
    for level in levels:
        f = float(level)
        if not math.isfinite(f):
            raise DiagramError(f"contour levels must be finite, not {level!r}")
        out.append(f)
    if not out:
        raise DiagramError("contour needs at least one level")
    return tuple(out)


def _fractions(hdr) -> tuple[float, ...]:
    if isinstance(hdr, Real) and not isinstance(hdr, bool):
        raise DiagramError(
            "contour hdr= is a list of enclosed fractions, for example hdr=(0.683, 0.954)")
    out = tuple(sorted((float(f) for f in hdr), reverse=True))
    if not out:
        raise DiagramError("contour hdr= needs at least one fraction")
    return out


def _padded(mm: list[float]) -> list[float]:
    """Page positions of the grid nodes, with one step beyond each end.

    The padding nodes are where the border of the grid sits, so a contour
    through an edge node can close outside the data rather than at it.
    """
    return [2 * mm[0] - mm[1]] + mm + [2 * mm[-1] - mm[-2]]


def _at(positions: list[float], t: float) -> float:
    """The page position at fractional padded index `t`."""
    k = min(max(int(math.floor(t)), 0), len(positions) - 2)
    return positions[k] + (t - k) * (positions[k + 1] - positions[k])


#: Names people reach for from `kde2d` or a plain contour call, and the keyword
#: that does the job here.
_HINTS = {"mass": "hdr", "masses": "hdr", "shares": "hdr", "fractions": "hdr",
          "level": "levels", "thresholds": "levels", "contours": "levels"}


def grid_contour_layer(panel, x, y, z, *, levels=None, hdr=None, color=None,
                       ramp=None, **style):
    """The contours of `Panel.contour`. Returns `(node, note)`."""
    for key in style:
        if key in _HINTS:
            raise TypeError(f"contour() got unknown keyword {key}= (did you mean "
                            f"{_HINTS[key]}=?)")
    xs, ys = _axis(x, "x"), _axis(y, "y")
    nx, ny = len(xs), len(ys)
    rows = [list(row) for row in z]
    if len(rows) != ny or any(len(row) != nx for row in rows):
        raise DiagramError(
            f"contour z needs {ny} rows of {nx} values, one row per y position")
    values = [[_value(v) for v in row] for row in rows]
    finite = [v for row in values for v in row if v is not None]
    if not finite:
        raise DiagramError("contour has no finite values to draw")
    if levels is None and hdr is None:
        raise DiagramError(
            "contour needs levels= (z values to draw) or hdr= (shares of the total)")
    if levels is not None and hdr is not None:
        raise DiagramError("contour takes levels= or hdr=, not both")
    if hdr is not None:
        masses = _fractions(hdr)
        thresholds = mass_levels(values, masses)
    else:
        masses = None
        thresholds = _levels(levels)

    low, high = min(finite), max(finite)
    span = (high - low) or abs(high) or 1.0
    # Below every value, so the border of the padded grid is below every level.
    floor = low - span
    px = _padded([panel.x.map(v) for v in xs])
    py = _padded([panel.y.map(v) for v in ys])
    theme = active_theme()
    colors = _level_colors(len(thresholds), False, color, ramp, theme)

    items: list = []
    drawn: list[float] = []
    for level, ink in zip(thresholds, colors):
        # A level at or below the lowest value encloses the whole field, which
        # has no line to draw; one above the highest value encloses nothing.
        if not low < level <= high:
            continue
        grid = [[floor - level] * (nx + 2) for _ in range(ny + 2)]
        for j in range(ny):
            for i in range(nx):
                v = values[j][i]
                grid[j + 1][i + 1] = (floor if v is None else v) - level
        rings = []
        for ring in _contours(grid):
            if len(ring) < 3:
                continue
            rings.append([(_at(px, u), _at(py, v)) for u, v in ring])
        if not rings:
            continue
        drawn.append(level)
        paint = {"stroke": ink, "stroke_width": theme.stroke, "fill": "none",
                 "stroke_linejoin": "round"}
        paint.update(style)
        for ring in rings:
            items.append(draw_path(ring, closed=True, filled=False,
                                   kind=MARK_LINE_KIND, **paint))
    if not items:
        raise DiagramError(
            "contour() found no contour to draw: no level lies inside the range of the field")
    node = draw_place(items, origin=(0, 0), kind="contour")
    note = {"levels": list(thresholds), "drawn": drawn, "grid": (nx, ny)}
    if masses is not None:
        note["masses"] = list(masses)
    node.notes["contour"] = note
    return node, note
