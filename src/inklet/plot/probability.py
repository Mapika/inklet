"""Quantile-quantile and probability-probability plots against a reference
distribution.

`qq_points` pairs each order statistic of a sample with the quantile of the
reference distribution at its plotting position, and `pp_points` pairs the
reference distribution's cumulative probability at each order statistic
with the empirical one. Both draw nothing; `Panel.qq` and `Panel.pp` draw
them with a reference line.

Plotting positions are R's `ppoints(n)`: ``(i - a) / (n + 1 - 2a)`` with
``a = 3/8`` for ``n <= 10`` and ``1/2`` above. The default QQ reference line
is R's `qqline`: through the first and third quartiles of the sample
(type-7 quantiles) and of the reference distribution, so outliers in the
tails do not move it. The normal distribution comes from the standard
library's `statistics.NormalDist`.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Callable, Sequence

from ..core import DiagramError
from .statistics import _quantile_sorted

__all__ = ["QQ_LINES", "plotting_positions", "pp_points", "qq_line", "qq_points"]

#: Accepted values of `Panel.qq(line=)`.
QQ_LINES = ("quartiles", "fit", "identity", None)


def plotting_positions(n: int) -> list[float]:
    """R's `ppoints(n)`: the probabilities the order statistics stand for."""
    if n < 1:
        raise DiagramError("plotting positions need at least one value")
    a = 3.0 / 8.0 if n <= 10 else 0.5
    return [(i - a) / (n + 1 - 2 * a) for i in range(1, n + 1)]


def _sample(values) -> list[float]:
    out = sorted(float(v) for v in values
                 if v is not None and math.isfinite(float(v)))
    if len(out) < 2:
        raise DiagramError("a probability plot needs at least two finite values")
    return out


def _quantile_function(dist) -> Callable[[float], float]:
    if dist == "normal":
        return NormalDist().inv_cdf
    if isinstance(dist, NormalDist):
        return dist.inv_cdf
    if callable(dist):
        return dist
    raise DiagramError(
        'qq dist is "normal", a statistics.NormalDist, or a quantile function')


def qq_points(values: Sequence[float], dist="normal") -> list[tuple[float, float]]:
    """`(theoretical quantile, sample value)` for each sorted value.

    `dist` is `"normal"` (the standard normal), a `statistics.NormalDist`,
    or any function from a probability to a quantile.
    """
    ordered = _sample(values)
    quantile = _quantile_function(dist)
    return [(quantile(p), v) for p, v in zip(plotting_positions(len(ordered)), ordered)]


def qq_line(values: Sequence[float], dist="normal", line: str = "quartiles"
            ) -> tuple[float, float]:
    """`(intercept, slope)` of a QQ reference line.

    `"quartiles"` passes through the sample's and the distribution's first
    and third quartiles (R's `qqline`); `"fit"` is the normal with the
    sample's mean and standard deviation (intercept = mean, slope = sd);
    `"identity"` is ``y = x``.
    """
    ordered = _sample(values)
    if line == "identity":
        return 0.0, 1.0
    if line == "fit":
        n = len(ordered)
        mean = math.fsum(ordered) / n
        sd = math.sqrt(math.fsum((v - mean) ** 2 for v in ordered) / (n - 1))
        return mean, sd
    if line != "quartiles":
        raise DiagramError(f'qq line is "quartiles", "fit", "identity" or None, not {line!r}')
    quantile = _quantile_function(dist)
    y1, y3 = _quantile_sorted(ordered, 0.25), _quantile_sorted(ordered, 0.75)
    x1, x3 = quantile(0.25), quantile(0.75)
    slope = (y3 - y1) / (x3 - x1)
    return y1 - slope * x1, slope


def pp_points(values: Sequence[float], dist="normal") -> list[tuple[float, float]]:
    """`(theoretical probability, empirical probability)` per sorted value.

    With `dist="normal"` the reference is the normal with the sample's own
    mean and standard deviation; pass a `statistics.NormalDist` for fixed
    parameters, or any cumulative distribution function.
    """
    ordered = _sample(values)
    if dist == "normal":
        n = len(ordered)
        mean = math.fsum(ordered) / n
        sd = math.sqrt(math.fsum((v - mean) ** 2 for v in ordered) / (n - 1))
        if not sd > 0:
            raise DiagramError("a normal PP plot needs values that are not all equal")
        cdf = NormalDist(mean, sd).cdf
    elif isinstance(dist, NormalDist):
        cdf = dist.cdf
    elif callable(dist):
        cdf = dist
    else:
        raise DiagramError('pp dist is "normal", a statistics.NormalDist, or a CDF')
    return [(cdf(v), p) for v, p in zip(ordered, plotting_positions(len(ordered)))]
