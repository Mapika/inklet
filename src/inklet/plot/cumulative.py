"""Empirical cumulative distributions.

`ecdf(values)` returns the steps of the empirical cumulative distribution
function without drawing anything: the distinct values in ascending order and
the fraction of observations at or below each one. Tied values share one
step. `weights=` replaces the count with a sum of weights, and
`normalize=False` keeps counts (or weight sums) instead of fractions, which is
the form a cumulative count plot on a log axis needs.

`Panel.ecdf` draws the result as a post-step staircase.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import DiagramError

__all__ = ["ecdf"]


def ecdf(values: Sequence[float], *, weights: Sequence[float] | None = None,
         complementary: bool = False,
         normalize: bool = True) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """`(xs, ys)`: distinct values and the cumulative share at or below each.

    Missing values (`None` or NaN) are excluded along with their weights, and
    the denominator counts only the remaining observations. With
    `complementary=True` each `y` is the share strictly *above* `x` (the
    survival function), so the last step is 0. With `normalize=False` the
    shares are counts or weight sums.

        xs, ys = inklet.plot.ecdf([3, 1, 2, 2])
        # xs == (1.0, 2.0, 3.0); ys == (0.25, 0.75, 1.0)
    """
    data = list(values)
    if weights is None:
        pairs = [(float(v), 1.0) for v in data if _present(v)]
    else:
        given = list(weights)
        if len(given) != len(data):
            raise DiagramError(
                f"ecdf() has {len(given)} weights for {len(data)} values")
        pairs = [(float(v), float(w)) for v, w in zip(data, given)
                 if _present(v) and _present(w)]
        if any(w < 0 for _, w in pairs):
            raise DiagramError("ecdf() weights must be non-negative")
    if not pairs:
        raise DiagramError("ecdf() needs at least one value that is not missing")
    if any(math.isinf(v) for v, _ in pairs):
        raise DiagramError("ecdf() values must be finite")
    pairs.sort(key=lambda p: p[0])
    total = sum(w for _, w in pairs)
    if total <= 0:
        raise DiagramError("ecdf() weights sum to zero")
    xs: list[float] = []
    ys: list[float] = []
    running = 0.0
    for value, weight in pairs:
        running += weight
        if xs and value == xs[-1]:
            ys[-1] = running
        else:
            xs.append(value)
            ys.append(running)
    if complementary:
        ys = [total - y for y in ys]
    if normalize:
        ys = [y / total for y in ys]
    return tuple(xs), tuple(ys)


def _present(value) -> bool:
    if value is None:
        return False
    return not math.isnan(float(value))


def staircase(xs: Sequence[float], ys: Sequence[float], *, start: float,
              low: float | None, high: float | None) -> list[tuple[float, float]]:
    """Vertices of the post-step curve through `(xs, ys)`.

    `start` is the level before the first step (0 for an ECDF, the total for
    its complement). `low` and `high` extend the curve horizontally to the
    ends of the axis; None leaves that end at the first or last step.
    """
    points: list[tuple[float, float]] = []
    if low is not None and low < xs[0]:
        points.append((low, start))
    points.append((xs[0], start))
    for index, (x, y) in enumerate(zip(xs, ys)):
        points.append((x, y))
        if index + 1 < len(xs):
            points.append((xs[index + 1], y))
    if high is not None and high > xs[-1]:
        points.append((high, ys[-1]))
    return points
