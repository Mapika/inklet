"""Statistical helpers for plot data.

These functions operate on plain numeric sequences and do not construct
geometry.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from typing import Sequence

from ..core import DiagramError
from .scale import nice_bounds, nice_step

__all__ = [
    "BoxStats", "box_stats", "histogram", "kde", "quantile",
]


def quantile(values: Sequence[float], q: float) -> float:
    """The `q`-quantile by linear interpolation between order statistics.

    R's type 7, which is what numpy, matplotlib and every box plot a reader
    has seen use. Choosing a different estimator would move a whisker relative
    to published figures of the same data, which is a worse sin than the
    estimator's own small bias.
    """
    if not values:
        raise DiagramError("cannot take a quantile of no values")
    if not 0.0 <= q <= 1.0:
        raise DiagramError(f"a quantile is within 0..1, got {q}")
    return _quantile_sorted(sorted(values), q)


def _quantile_sorted(ordered: Sequence[float], q: float) -> float:
    """Interpolate a validated quantile in a non-empty, sorted sample."""
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    return float(ordered[low] + (ordered[high] - ordered[low]) * (position - low))


@dataclass(frozen=True, slots=True)
class BoxStats:
    """The five numbers a box plot draws, and the points it draws separately."""

    low: float                      # lower whisker end
    q1: float
    median: float
    q3: float
    high: float                     # upper whisker end
    outliers: tuple[float, ...]
    count: int

    @property
    def iqr(self) -> float:
        return self.q3 - self.q1


def box_stats(values: Sequence[float], *, whisker: float = 1.5) -> BoxStats:
    """Quartiles, whiskers and outliers, Tukey's way.

    A whisker reaches the furthest observation still within `whisker` times the
    interquartile range of its quartile -- it stops on a real datum, never on
    the multiple itself, so the end of a whisker is always something that was
    measured. `whisker=0` puts them on the quartiles; an infinite one puts them
    on the extremes and leaves no outliers.
    """
    numbers = [float(v) for v in values]
    if not numbers:
        raise DiagramError("a box plot needs at least one value")
    ordered = sorted(numbers)
    q1 = _quantile_sorted(ordered, 0.25)
    median = _quantile_sorted(ordered, 0.5)
    q3 = _quantile_sorted(ordered, 0.75)
    reach = whisker * (q3 - q1)
    inside = [v for v in numbers if q1 - reach <= v <= q3 + reach]
    if not inside:                          # every point is an outlier: keep the box
        inside = [q1, q3]
    low, high = min(inside), max(inside)
    return BoxStats(
        low=low, q1=q1, median=median, q3=q3, high=high,
        outliers=tuple(sorted(v for v in numbers if v < low or v > high)),
        count=len(numbers),
    )


def histogram(values: Sequence[float], bins: int | Sequence[float] = 10, *,
              range: tuple[float, float] | None = None,
              density: bool = False) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Bin edges and the height of each bin: `(edges, heights)`.

    `bins` is either a count -- in which case the edges land on round numbers
    and you get *about* that many -- or the edges themselves. `range` clips the
    data before binning; without it the data's own extremes are used.

    `density=True` divides by the sample size and the bin width, so the bars
    integrate to one and two histograms of different sample sizes can be
    compared. The counts are what you want for a bar chart of a survey; the
    density is what you want beside a fitted curve.

    Call this before building the panel -- the ceiling of `max(heights)` is the
    y domain you need, and it is not knowable any other way.
    """
    numbers = [float(v) for v in values]
    if not numbers:
        raise DiagramError("a histogram needs at least one value")
    if range is not None:
        lo, hi = float(range[0]), float(range[1])
        numbers = [v for v in numbers if lo <= v <= hi]
    else:
        lo, hi = min(numbers), max(numbers)

    edges = _bin_edges(bins, lo, hi)
    counts = [0.0] * (len(edges) - 1)
    # NaN edges pass the existing validation but are not ordered. Retain the
    # original scan for them; ordinary edges support binary search.
    bin_of = _bin_of if any(math.isnan(e) for e in edges) else _ordered_bin_of
    for value in numbers:
        index = bin_of(value, edges)
        if index is not None:
            counts[index] += 1.0
    if density:
        total = sum(counts)
        if total > 0:
            counts = [c / (total * (edges[i + 1] - edges[i]))
                      for i, c in enumerate(counts)]
    return tuple(edges), tuple(counts)


def _bin_edges(bins: int | Sequence[float], lo: float, hi: float) -> list[float]:
    if not isinstance(bins, int):
        edges = [float(e) for e in bins]
        if len(edges) < 2:
            raise DiagramError(f"bin edges need at least two values, got {edges}")
        if any(b <= a for a, b in zip(edges, edges[1:])):
            raise DiagramError(f"bin edges must increase, got {edges}")
        return edges
    if bins < 1:
        raise DiagramError(f"a histogram needs at least one bin, got {bins}")
    if hi <= lo:
        # One distinct value has no width to divide. A unit box around it is
        # the only answer that draws something honest.
        return [lo - 0.5, lo + 0.5]
    step = nice_step(hi - lo, bins)
    start, end = nice_bounds(lo, hi, bins)
    # Integer multiples of the step, so the lattice matches the axis ticks
    # exactly rather than drifting by an accumulated epsilon per bin.
    first = math.floor(start / step + 1e-9)
    count = max(1, int(math.ceil(end / step - 1e-9)) - first)
    return [round((first + i) * step, 12) for i in range(count + 1)]


def _ordered_bin_of(value: float, edges: Sequence[float]) -> int | None:
    """Find a half-open bin in increasing edges, including the final endpoint."""
    if value < edges[0] or value > edges[-1]:
        return None
    if math.isnan(value):
        return 0                       # retain the original scan's fallback
    return min(bisect_right(edges, value) - 1, len(edges) - 2)


def _bin_of(value: float, edges: Sequence[float]) -> int | None:
    """Which bin a value falls in, the top edge belonging to the last bin.

    Half-open bins everywhere else, closed at the very top: otherwise the
    largest observation -- the one a reader looks for -- falls out of the plot.
    """
    if value < edges[0] or value > edges[-1]:
        return None
    for index in reversed(range(len(edges) - 1)):
        if value >= edges[index]:
            return index
    return 0


def kde(values: Sequence[float], grid: Sequence[float], *,
        bandwidth: float | None = None) -> tuple[float, ...]:
    """Gaussian kernel density at each point of `grid`.

    The default bandwidth is Silverman's rule against the smaller of the
    standard deviation and the interquartile range over 1.349 -- the robust
    form, because one outlier otherwise inflates the width until the whole
    estimate is a single smooth hump with the structure smoothed out of it.
    """
    numbers = [float(v) for v in values]
    if not numbers:
        raise DiagramError("a density estimate needs at least one value")
    width = _bandwidth(numbers) if bandwidth is None else float(bandwidth)
    if width <= 0:
        # Every value identical: nothing to estimate, and no width to do it
        # over. A flat zero is the honest answer, and it draws as nothing.
        return tuple(0.0 for _ in grid)
    scale = 1.0 / (len(numbers) * width * math.sqrt(2.0 * math.pi))
    out = []
    for at in grid:
        total = 0.0
        for value in numbers:
            z = (at - value) / width
            if abs(z) < 8.0:           # past 8 sigma the term is under 1e-14
                total += math.exp(-0.5 * z * z)
        out.append(total * scale)
    return tuple(out)


def _bandwidth(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    spread = math.sqrt(variance)
    ordered = sorted(values)
    iqr = _quantile_sorted(ordered, 0.75) - _quantile_sorted(ordered, 0.25)
    if iqr > 0:
        spread = min(spread, iqr / 1.349)
    return 1.06 * spread * n ** -0.2
