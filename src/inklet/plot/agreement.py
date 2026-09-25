"""Bland-Altman agreement between two measurement methods.

`bland_altman` computes, from paired measurements `a` and `b` of the same
subjects, the mean of each pair, the difference ``a - b`` (or the difference
as a percentage of the pair's mean), the bias (the mean difference), and the
limits of agreement ``bias +/- z * sd`` with ``z = 1.96`` by default.

With `confidence=`, it also gives confidence intervals, from Student's t on
``n - 1`` degrees of freedom: for the bias with standard error ``sd /
sqrt(n)``, and for each limit with the approximate standard error
``sqrt(3 * sd**2 / n)`` of Bland and Altman (1986, Lancet 327:307-310).

It draws nothing; `Panel.bland_altman` draws the points, the bias and the
limits, with the limits' values written at the right end of each line.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..core import Diagram, DiagramError
from .regression import t_quantile

__all__ = ["Agreement", "bland_altman", "margin_labels"]


@dataclass(frozen=True)
class Agreement:
    """What a Bland-Altman plot shows.

    `points` are `(mean, difference)` per pair; `bias`, `sd`, `lower` and
    `upper` the mean difference, its standard deviation and the limits of
    agreement. The `*_ci` fields are `(low, high)` or None.
    """

    points: tuple[tuple[float, float], ...]
    bias: float
    sd: float
    lower: float
    upper: float
    z: float
    n: int
    percent: bool
    bias_ci: tuple[float, float] | None = None
    lower_ci: tuple[float, float] | None = None
    upper_ci: tuple[float, float] | None = None


def bland_altman(a: Sequence[float], b: Sequence[float], *, z: float = 1.96,
                 percent: bool = False,
                 confidence: float | None = None) -> Agreement:
    """Bias and limits of agreement between paired measurements.

    Pairs with a missing or non-finite value are skipped. `percent=True`
    expresses each difference as a percentage of the pair's mean.
    """
    a, b = list(a), list(b)
    if len(a) != len(b):
        raise DiagramError(
            f"bland_altman needs paired measurements, got {len(a)} and {len(b)}")
    if not z > 0:
        raise DiagramError(f"bland_altman z must be positive, got {z!r}")
    pts = []
    for u, v in zip(a, b):
        if u is None or v is None:
            continue
        u, v = float(u), float(v)
        if not (math.isfinite(u) and math.isfinite(v)):
            continue
        mean = (u + v) / 2.0
        diff = u - v
        if percent:
            if mean == 0:
                raise DiagramError("a percentage difference needs nonzero pair means")
            diff = 100.0 * diff / mean
        pts.append((mean, diff))
    n = len(pts)
    if n < 2:
        raise DiagramError("bland_altman needs at least two complete pairs")
    diffs = [d for _, d in pts]
    bias = math.fsum(diffs) / n
    sd = math.sqrt(math.fsum((d - bias) ** 2 for d in diffs) / (n - 1))
    lower, upper = bias - z * sd, bias + z * sd
    cis: dict = {}
    if confidence is not None:
        if not 0 < confidence < 1:
            raise DiagramError(f"confidence is between 0 and 1, got {confidence!r}")
        t = t_quantile(0.5 + confidence / 2.0, n - 1)
        half_bias = t * sd / math.sqrt(n)
        half_limit = t * math.sqrt(3.0 * sd * sd / n)
        cis = {"bias_ci": (bias - half_bias, bias + half_bias),
               "lower_ci": (lower - half_limit, lower + half_limit),
               "upper_ci": (upper - half_limit, upper + half_limit)}
    return Agreement(points=tuple(pts), bias=bias, sd=sd, lower=lower,
                     upper=upper, z=z, n=n, percent=percent, **cis)


def margin_labels(panel, words) -> Diagram:
    """The names and values of the Bland-Altman lines, set in the right
    margin: each name just above its line and the value just below, left
    aligned a small gap past the plot area. `words` is `(y, name, value)`
    per line, top first. Labels that would collide are pushed apart, the
    upper one up and the lower one down, so their order never changes."""
    from ..core import Vec2
    from ..draw.coords import active_theme
    from ..draw.place import place as draw_place
    from .notes import TEXT_KIND, _text

    theme = active_theme()
    gap = theme.gap("xs")
    lift = 0.25 * theme.font_size_small
    area = panel.area
    blocks = []
    for y, name, value in words:
        top, bottom = _text(name, None, {}), _text(value, None, {})
        height = top.bbox.height + bottom.bbox.height + 2 * lift
        blocks.append([panel.y.map(y), top, bottom, height])
    blocks.sort(key=lambda b: b[0])
    for k in range(1, len(blocks)):
        prev, cur = blocks[k - 1], blocks[k]
        need = (prev[3] + cur[3]) / 2 + gap
        if cur[0] - prev[0] < need:
            push = (need - (cur[0] - prev[0])) / 2
            prev[0] -= push
            cur[0] += push
    items = []
    x0 = area.x1 + gap
    for at, top, bottom, _ in blocks:
        tb, bb = top.bbox, bottom.bbox
        items.append((Vec2(x0 + tb.width / 2, at - lift - tb.height / 2), top))
        items.append((Vec2(x0 + bb.width / 2, at + lift + bb.height / 2), bottom))
    return draw_place(items, origin=(0, 0), kind=TEXT_KIND)
