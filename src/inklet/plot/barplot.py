"""Bars of a summary with error bars and every observation on top.

The most common figure in a biology paper: per condition, a bar at the mean,
an error bar for its spread, and each animal or replicate as a dot, so the
reader sees the n and the distribution the mean came from. With several
series the bars of one category are dodged side by side, exactly as
`Panel.bars` groups them, and the dots of each bar are swarmed inside it
(`marks.swarm_offsets`), so they keep their exact values.

`summary_stats` computes the bar heights and error extents without drawing.
Confidence intervals use the normal approximation (1.96 standard errors):
for small samples a t-based interval is wider, so pass the half-widths you
computed with `error=` as a callable.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Callable, Sequence

from ..core import Diagram, DiagramError, mm
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND, marker as make_marker
from ..themes.color import mix
from . import marks as _marks
from .statistics import quantile

__all__ = ["barplot", "summary_stats", "BARPLOT_ERRORS", "BARPLOT_ESTIMATORS"]

BARPLOT_ESTIMATORS = ("mean", "median")
BARPLOT_ERRORS = ("sem", "sd", "ci95", "iqr", None)

#: Bar fill, as a blend of the series colour towards paper. The dots stay
#: the darkest thing in the bar.
_BAR_TINT = 0.55

#: Palette entries for several series: blue, vermillion, bluish green,
#: orange, purple, sky blue.
_SERIES_ORDER = (5, 6, 3, 1, 7, 2)

#: Dot diameter as a fraction of the type size.
_DOT_OF_TYPE = 0.42


def _clean(sample, where) -> list[float]:
    out = []
    for v in sample:
        if v is None:
            continue
        number = float(v)
        if math.isnan(number):
            continue
        if not math.isfinite(number):
            raise DiagramError(f"barplot sample {where} has a non-finite value {v!r}")
        out.append(number)
    return out


def summary_stats(sample: Sequence[float], estimator: str = "mean",
                  error: str | Callable | None = "sem") -> tuple[float, float, float]:
    """`(centre, down, up)` for one sample: the bar height and the error
    bar's reach below and above it. An error needing a spread (sd, sem,
    ci95) is zero for a single observation."""
    values = _clean(sample, "")
    if not values:
        raise DiagramError("barplot needs at least one value per bar")
    n = len(values)
    if estimator == "mean":
        centre = sum(values) / n
    elif estimator == "median":
        centre = quantile(sorted(values), 0.5)
    else:
        raise DiagramError(f"barplot estimator= is one of {BARPLOT_ESTIMATORS}")
    if error is None:
        return centre, 0.0, 0.0
    if callable(error):
        reach = error(values)
        if isinstance(reach, Real):
            return centre, float(reach), float(reach)
        down, up = reach
        return centre, float(down), float(up)
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    if error == "sd":
        return centre, sd, sd
    if error == "sem":
        return centre, sd / math.sqrt(n), sd / math.sqrt(n)
    if error == "ci95":
        half = 1.959964 * sd / math.sqrt(n)
        return centre, half, half
    if error == "iqr":
        ordered = sorted(values)
        return centre, centre - quantile(ordered, 0.25), quantile(ordered, 0.75) - centre
    raise DiagramError(f"barplot error= is one of {BARPLOT_ERRORS} or a callable")


def _groups(data) -> list[list[list[float]]]:
    """Series-major samples: `out[s][c]` is the list of observations."""
    rows = list(data)
    if not rows:
        raise DiagramError("barplot() was given no data")

    def is_sample(x) -> bool:
        items = list(x)
        return all(v is None or isinstance(v, Real) for v in items)

    if all(is_sample(r) for r in rows):
        rows = [rows]
    out = [[list(sample) for sample in series] for series in rows]
    if len({len(s) for s in out}) != 1:
        raise DiagramError("every barplot series needs one sample per category")
    return out


def barplot(panel, at: Sequence, data, *, estimator: str = "mean",
            error: str | Callable | None = "sem", points: bool = True,
            width: float = 0.8, gap: float = 0.12, orient: str = "v",
            color=None, size: float | str | None = None,
            cap: float | str | None = None, baseline: float = 0.0,
            **style) -> tuple[Diagram, tuple[str, ...], list]:
    """Draw bars, error bars and points on `panel`. See `Panel.barplot`.

    Returns `(node, colour per series, stats)` where `stats[s][c]` is
    `(centre, down, up, n)`.
    """
    places = list(at)
    series = _groups(data)
    if len(series[0]) != len(places):
        raise DiagramError(
            f"barplot() got {len(places)} positions for {len(series[0])} samples")
    theme = active_theme()
    count = len(series)
    per_bar = None
    if color is None:
        inks = (theme.ink,) if count == 1 else tuple(
            theme.color(_SERIES_ORDER[i % len(_SERIES_ORDER)]) for i in range(count))
    elif (count == 1 and not isinstance(color, str) and len(places) > 1
          and len(tuple(color)) == len(places)):
        per_bar = tuple(color)
        inks = (per_bar[0],)
    else:
        inks = _marks.series_colors(color, count)
    fill_given = style.pop("fill", None)
    stroke = style.pop("stroke", None)
    stroke_width = style.pop("stroke_width", None)
    dot = _DOT_OF_TYPE * theme.font_size if size is None else mm(size)
    position, value = _marks._axes_of(panel, orient)
    base = value.map(baseline)
    bars, whiskers, dots, stats = [], [], [], []
    for s, samples in enumerate(series):
        stats.append([])
        for c, (where, sample) in enumerate(zip(places, samples)):
            ink = inks[s] if per_bar is None else per_bar[c]
            fill = fill_given or (mix(theme.ink, theme.paper, 0.8)
                                  if count == 1 and color is None
                                  else mix(ink, theme.paper, _BAR_TINT))
            values = _clean(sample, f"{s},{c}")
            if not values:
                stats[s].append(None)
                continue
            centre, down, up = summary_stats(values, estimator, error)
            stats[s].append((centre, down, up, len(values)))
            lo, hi = _marks._slot(position, where, width)
            if count > 1:
                lo, hi = _marks._sub_slots(lo, hi, count, gap)[s]
            mid, span = (lo + hi) / 2, hi - lo
            top = value.map(centre)
            if abs(top - base) > 1e-12:
                bars.append(_marks._rect(_marks._point(orient, mid, (base + top) / 2),
                                         *_marks._extent(orient, span, abs(top - base)),
                                         fill, stroke or ink,
                                         theme.stroke if stroke_width is None else stroke_width))
            if points:
                across = [value.map(v) for v in values]
                offsets, drawn = _marks._swarm_fit(across, span * 0.8, dot, dot * 0.15)
                for offset, along in zip(offsets, across):
                    dots.append((_marks._point(orient, mid + offset, along),
                                 make_marker("circle", drawn, fill=ink,
                                             stroke=theme.paper,
                                             stroke_width=theme.hairline)))
            if down > 0 or up > 0:
                a, b = value.map(centre - down), value.map(centre + up)
                reach = span * 0.22 if cap is None else mm(cap)
                line = {"stroke": theme.ink, "stroke_width": theme.stroke,
                        "stroke_linecap": "butt"}
                whiskers.append(polyline((_marks._point(orient, mid, a),
                                          _marks._point(orient, mid, b)),
                                         kind=MARK_LINE_KIND, **line))
                if reach > 0:
                    for end in (a, b):
                        whiskers.append(polyline((_marks._point(orient, mid - reach, end),
                                                  _marks._point(orient, mid + reach, end)),
                                                 kind=MARK_LINE_KIND, **line))
    if not (bars or dots):
        raise DiagramError("barplot() had nothing to draw")
    node = draw_place(bars + dots + whiskers, **style)
    node.notes["barplot"] = {"estimator": estimator,
                             "error": error if isinstance(error, (str, type(None))) else "custom",
                             "stats": tuple(tuple(row) for row in stats)}
    return node, inks, stats
