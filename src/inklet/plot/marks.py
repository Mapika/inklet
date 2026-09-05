"""The shapes a dataset turns into: bars, bins, whiskers, areas, boxes.

Everything here speaks data. A caller hands over numbers in the units of the
panel's scales and gets back a diagram already in panel millimetres, so the
only place a coordinate is computed is `Scale.map` -- the same call the axis
made, which is why a bar's top edge lands on the tick that names it.

Three decisions are worth defending.

**Statistics are separated from geometry.** `histogram`, `box_stats` and `kde`
are plain functions over plain numbers, and the drawing functions call them.
That is not tidiness: a panel's y scale has to be built *before* anything is
drawn into it, so an author needs the counts before they need the bars. A
histogram helper that could only draw would force them to guess the ceiling.

**Bins and boxes are quantised the way ticks are.** `histogram` puts its edges
on the same 1/2/5 lattice `nice_ticks` uses, so a bin boundary falls on a
labelled tick instead of a millimetre away from one. Ten bins over data
spanning 0.7 to 9.4 are eleven bins from 0 to 11, and every edge is a number
the reader can read off the axis.

**Colour comes from the theme, and only when nobody else supplied it.** One
series is a tint of the ink -- it survives greyscale, and a solid black bar
chart at 89mm is more ink than a journal wants. Two or more are the
categorical palette in order. Pass `fill=` or `colors=` and none of that
happens.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, RectPrim, Vec2, mm
from ..draw.coords import active_theme
from ..draw.path import polygon, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND, marker as make_marker
from ..themes.color import mix
from .scale import Band, Scale, nice_bounds, nice_step

__all__ = [
    "BoxStats", "box_stats", "histogram", "kde", "quantile",
]

#: A single series against paper: 14% ink. Dark enough to read as a solid
#: shape at 89mm, light enough that twenty bars are not a black wall.
_SINGLE_TINT = 0.86
#: A filled area under a line is read *through*, so it goes paler still.
_AREA_TINT = 0.88

#: Error-bar caps, as a fraction of the type size. Just under a marker's
#: diameter (0.62 of type), so a cap never outweighs the point it belongs to.
_CAP_OF_TYPE = 0.30

#: ...but never more than this fraction of the gap to the next whisker. Twenty
#: points on a 40mm panel sit 1.9mm apart, and a cap sized off the type alone
#: leaves 0.4mm of paper between neighbours: a picket fence, in which the eye
#: reads the row of caps as a band and stops reading the individual intervals.
#: At 0.30 the paper between two caps is 40% of the spacing.
_CAP_OF_GAP = 0.30

#: And below this, in stroke widths, a cap is a smudge on the end of a line
#: rather than a mark, so the whisker ends bare instead.
_CAP_FLOOR = 1.5

#: Outliers on a box plot, as a fraction of the type size. Half a normal
#: marker: they are individuals, not a series.
_OUTLIER_OF_TYPE = 0.34

_ORIENTS = ("v", "h")


# -- statistics -----------------------------------------------------------


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
    ordered = sorted(values)
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
    q1 = quantile(numbers, 0.25)
    median = quantile(numbers, 0.5)
    q3 = quantile(numbers, 0.75)
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
    for value in numbers:
        index = _bin_of(value, edges)
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
    iqr = quantile(values, 0.75) - quantile(values, 0.25)
    if iqr > 0:
        spread = min(spread, iqr / 1.349)
    return 1.06 * spread * n ** -0.2


# -- shared drawing helpers -----------------------------------------------


def _axes_of(panel, orient: str) -> tuple[Scale, Scale]:
    """`(position scale, value scale)` for an orientation.

    "v" means the bars stand up: they are positioned along x and measured along
    y. "h" lays them down and swaps the two. Every helper here that has a
    baseline takes the same argument and asks this once.
    """
    if orient not in _ORIENTS:
        raise DiagramError(
            f'unknown orientation {orient!r}; expected "v" (bars stand up) '
            'or "h" (bars lie down)'
        )
    return (panel.x, panel.y) if orient == "v" else (panel.y, panel.x)


def _point(orient: str, along: float, across: float) -> Vec2:
    return Vec2(along, across) if orient == "v" else Vec2(across, along)


def _series(heights) -> tuple[tuple[float, ...], ...]:
    """Normalise a flat sequence or a sequence of series into series-major."""
    rows = list(heights)
    if not rows:
        raise DiagramError("no heights to draw")
    if all(isinstance(row, (int, float)) for row in rows):
        return (tuple(float(v) for v in rows),)
    out = []
    for row in rows:
        out.append(tuple(float(v) for v in row))
    if len({len(row) for row in out}) != 1:
        raise DiagramError(
            f"every series needs the same number of values, got "
            f"{sorted({len(row) for row in out})}"
        )
    return tuple(out)


def series_count(heights) -> int:
    """How many series a `heights` argument holds.

    `Panel.bars(names=)` has to know before the bars are drawn -- one swatch
    per series -- and asking the same function the drawing asks is what keeps
    the key's colours and the bars' colours the same colours.
    """
    return len(_series(heights))


def default_area_fill() -> str:
    """The pale tint an unstyled area is filled with.

    Public because `Panel.fill(name=)` puts it in a swatch, and a swatch that
    computed the tint a second time would be a second place to change it.
    """
    theme = active_theme()
    return mix(theme.ink, theme.paper, _AREA_TINT)


def series_colors(colors, count: int) -> tuple[str, ...]:
    """One colour per series: what was asked for, or the theme's answer.

    A lone series is a tint of the ink rather than palette colour 0, which in
    the print theme is pure black. Twenty black bars at 89mm is a wall; the
    tint reads as one shape, survives greyscale, and leaves the palette free to
    mean "these are different things".
    """
    theme = active_theme()
    if colors is None:
        if count == 1:
            return (mix(theme.ink, theme.paper, _SINGLE_TINT),)
        return tuple(theme.color(i) for i in range(count))
    if isinstance(colors, str):
        return (colors,) * count
    given = tuple(colors)
    if not given:
        raise DiagramError("colors= was given no colours")
    return tuple(given[i % len(given)] for i in range(count))


def _rect(centre: Vec2, width: float, height: float,
          fill: str, stroke: str | None, stroke_width: float | None):
    style = {"fill": fill, "stroke": "none" if stroke is None else stroke}
    if stroke is not None and stroke_width is not None:
        style["stroke_width"] = stroke_width
    return (centre, Diagram(prim=RectPrim(abs(width), abs(height)),
                            kind=MARK_KIND).styled(**style))


def _outlined(single: bool):
    """Whether a filled mark gets a hairline outline of its own.

    One tinted series does: without an edge, two bars that touch are one shape.
    Several coloured ones do not -- the hues already separate them, and an
    outline round every segment of a stacked bar is a cage.
    """
    theme = active_theme()
    return (theme.ink, theme.hairline) if single else (None, None)


def _values(value, count: int, name: str) -> tuple[float, ...]:
    if value is None:
        return (0.0,) * count
    if isinstance(value, (int, float)):
        return (float(value),) * count
    out = tuple(float(v) for v in value)
    if len(out) != count:
        raise DiagramError(
            f"{name} has {len(out)} values for {count} points"
        )
    return out


# -- bars -----------------------------------------------------------------


def bars(panel, at: Sequence, heights, *, width: float = 0.8,
         baseline: float = 0.0, orient: str = "v",
         stacked: bool | None = None, grouped: bool | None = None,
         gap: float = 0.12, colors=None, bar_colors=None, **style) -> Diagram:
    """Rectangles from a baseline, one per value. See `Panel.bars`."""
    places = list(at)
    series = _series(heights)
    if len(places) != len(series[0]):
        raise DiagramError(
            f"bars() got {len(places)} positions for {len(series[0])} values"
        )
    if stacked and grouped:
        raise DiagramError("bars() is either stacked or grouped, not both")
    # Several series and no instruction: grouped. Stacking implies the parts
    # sum to something the reader is meant to compare, which is a claim about
    # the data that a default has no business making.
    if len(series) > 1 and not stacked:
        grouped = True
    fills = series_colors(style.pop("fill", None) if colors is None else colors,
                          len(series))
    stroke, stroke_width = _outlined(len(series) == 1)
    stroke = style.pop("stroke", stroke)
    stroke_width = style.pop("stroke_width", stroke_width)
    per_bar = None
    if bar_colors is not None:
        if len(series) != 1:
            raise DiagramError("bar_colors requires a single series; use colors for multiple series")
        if colors is not None:
            raise DiagramError("choose bar_colors or series colors, not both")
        try:
            per_bar = ([bar_colors[p] for p in places] if isinstance(bar_colors, Mapping)
                       else _per_point(bar_colors, len(places), "bar_colors"))
        except KeyError as error:
            raise DiagramError(f"bar_colors has no colour for category {error.args[0]!r}") from None
    position, value = _axes_of(panel, orient)

    cells = []
    for index, where in enumerate(places):
        lo, hi = _slot(position, where, width)
        slots = (_sub_slots(lo, hi, len(series), gap) if grouped
                 else [(lo, hi)] * len(series))
        spans = (_stacked_spans(series, index, baseline) if stacked
                 else [(baseline, row[index]) for row in series])
        for s, (bottom, top) in enumerate(spans):
            a, b = value.map(bottom), value.map(top)
            if abs(b - a) < 1e-12:
                continue                    # a zero bar is not a flat rectangle
            p0, p1 = slots[s]
            cells.append(_rect(_point(orient, (p0 + p1) / 2, (a + b) / 2),
                               *_extent(orient, abs(p1 - p0), abs(b - a)),
                               fills[s] if per_bar is None else per_bar[index], stroke, stroke_width))
    if not cells:
        raise DiagramError("bars() had nothing to draw: every value was zero")
    return draw_place(cells, **style)


def _extent(orient: str, along: float, across: float) -> tuple[float, float]:
    return (along, across) if orient == "v" else (across, along)


def _slot(scale: Scale, where, width: float) -> tuple[float, float]:
    """The two edges of one bar's slot, in millimetres.

    On a band scale `width` is a fraction of the step, so the default 0.8
    leaves a fifth of the pitch as air whatever padding the scale itself was
    built with. On a continuous scale it is a width in data units, mapped
    through the scale like any other pair of values -- which is what keeps a
    bar on a log axis the shape a log axis says it is.
    """
    if isinstance(scale, Band):
        half = abs(scale.step) * width / 2
        centre = scale.map(where)
        return (centre - half, centre + half)
    edges = (scale.map(where - width / 2), scale.map(where + width / 2))
    return (min(edges), max(edges))


def _sub_slots(lo: float, hi: float, count: int,
               gap: float) -> list[tuple[float, float]]:
    """Divide one slot between grouped series, leaving `gap` of each sub-slot
    as air between neighbours."""
    step = (hi - lo) / count
    inset = step * gap / 2
    return [(lo + step * i + inset, lo + step * (i + 1) - inset)
            for i in range(count)]


def _stacked_spans(series: Sequence[Sequence[float]], index: int,
                   baseline: float) -> list[tuple[float, float]]:
    """Where each series' segment starts and ends at one position.

    Positives stack up from the baseline and negatives stack down, each with
    its own running total. Accumulating them together would let a negative
    value pull a later positive one back through the bar it should sit on.
    """
    up = down = baseline
    spans = []
    for values in series:
        height = values[index]
        if height >= 0:
            spans.append((up, up + height))
            up += height
        else:
            spans.append((down + height, down))
            down += height
    return spans


def hist(panel, values: Sequence[float], bins: int | Sequence[float] = 10, *,
         range: tuple[float, float] | None = None, density: bool = False,
         baseline: float = 0.0, orient: str = "v", colors=None,
         **style) -> Diagram:
    """Binned counts as touching rectangles. See `Panel.hist`."""
    edges, counts = histogram(values, bins, range=range, density=density)
    return bins_node(panel, edges, counts, baseline=baseline, orient=orient,
                     colors=colors, **style)


def bins_node(panel, edges: Sequence[float], heights: Sequence[float], *,
              baseline: float = 0.0, orient: str = "v", colors=None,
              **style) -> Diagram:
    """Rectangles spanning given edges: the drawing half of `hist`."""
    if len(edges) != len(heights) + 1:
        raise DiagramError(
            f"{len(edges)} edges do not bound {len(heights)} bins"
        )
    color = series_colors(style.pop("fill", None) if colors is None else colors, 1)[0]
    stroke, stroke_width = _outlined(True)
    stroke = style.pop("stroke", stroke)
    stroke_width = style.pop("stroke_width", stroke_width)
    position, value = _axes_of(panel, orient)
    base = value.map(baseline)
    cells = []
    for index, height in enumerate(heights):
        top = value.map(baseline + height)
        if abs(top - base) < 1e-12:
            continue
        p0, p1 = position.map(edges[index]), position.map(edges[index + 1])
        cells.append(_rect(_point(orient, (p0 + p1) / 2, (base + top) / 2),
                           *_extent(orient, abs(p1 - p0), abs(top - base)),
                           color, stroke, stroke_width))
    if not cells:
        raise DiagramError("hist() had nothing to draw: every bin was empty")
    return draw_place(cells, **style)


# -- error bars -----------------------------------------------------------


def errorbars(panel, points: Sequence[Sequence], *, yerr=None, xerr=None,
              cap: float | None = None, **style) -> Diagram:
    """Whiskers through each point. See `Panel.errorbars`."""
    data = [tuple(p) for p in points]
    if yerr is None and xerr is None:
        raise DiagramError("errorbars() needs yerr=, xerr= or both")
    items: list[Diagram] = []
    for axis, spread in (("y", yerr), ("x", xerr)):
        if spread is None:
            continue
        reach = _cap_reach(panel, data, axis) if cap is None else float(cap)
        for (x, y), (low, high) in zip(data, error_pairs(spread, len(data), axis)):
            items.extend(_whisker(panel, x, y, low, high, axis, reach))
    if not items:
        raise DiagramError("errorbars() had nothing to draw")
    return draw_place(items, **style)


def error_pairs(spread, count: int, name: str) -> list[tuple[float, float]]:
    """`yerr=` in any of its three spellings, as `(down, up)` pairs.

    A number is symmetric, a sequence of numbers is one symmetric bar per
    point, and a sequence of pairs is asymmetric -- the shape a confidence
    interval actually has, and the one every plotting library makes you look up.
    """
    if isinstance(spread, (int, float)):
        return [(float(spread), float(spread))] * count
    given = list(spread)
    if len(given) != count:
        raise DiagramError(f"{name}err has {len(given)} values for {count} points")
    out = []
    for item in given:
        if isinstance(item, (int, float)):
            out.append((float(item), float(item)))
        else:
            low, high = item
            out.append((float(low), float(high)))
    return out


def _cap_reach(panel, data: Sequence[Sequence], axis: str) -> float:
    """Half the width of an error bar's end caps, in millimetres.

    A cap is sized off the type, like every other small mark in the theme --
    until the whiskers crowd, and then it is sized off the crowding, because
    a cap whose job is to say "the interval ends here" cannot do that while
    it is touching its neighbour.
    """
    theme = active_theme()
    reach = min(_CAP_OF_TYPE * theme.font_size,
                _CAP_OF_GAP * _packing(panel, data, axis))
    return reach if reach >= _CAP_FLOOR * theme.stroke else 0.0


def _packing(panel, data: Sequence[Sequence], axis: str) -> float:
    """The smallest gap on paper between two whiskers, across their own axis."""
    across = sorted({(panel.point(x, y).x if axis == "y" else panel.point(x, y).y)
                     for x, y in data})
    gaps = [b - a for a, b in zip(across, across[1:]) if b - a > 1e-9]
    return min(gaps) if gaps else math.inf


def _whisker(panel, x, y, low: float, high: float, axis: str,
             cap: float) -> list[Diagram]:
    if axis == "y":
        ends = (panel.point(x, y - low), panel.point(x, y + high))
        across = Vec2(cap, 0.0)
    else:
        ends = (panel.point(x - low, y), panel.point(x + high, y))
        across = Vec2(0.0, cap)
    out = [polyline(ends, kind=MARK_LINE_KIND)]
    if cap > 0:
        out.extend(polyline((end - across, end + across), kind=MARK_LINE_KIND)
                   for end in ends)
    return out


# -- areas and steps ------------------------------------------------------


def area(panel, points: Sequence[Sequence], *, baseline: float = 0.0,
         orient: str = "v", **style) -> Diagram:
    """A filled region between a series and a baseline. See `Panel.area`."""
    data = [tuple(p) for p in points]
    if len(data) < 2:
        raise DiagramError("an area needs at least two points")
    if orient == "v":
        pairs = [(x, baseline) for x, _ in reversed(data)]
    else:
        pairs = [(baseline, y) for _, y in reversed(data)]
    return _filled(panel, data + pairs, style)


def fill_between(panel, x: Sequence, y0, y1, **style) -> Diagram:
    """The region between two curves over shared x. See `Panel.fill_between`."""
    xs = list(x)
    if len(xs) < 2:
        raise DiagramError("fill_between needs at least two x values")
    lower = _values(y0, len(xs), "y0")
    upper = _values(y1, len(xs), "y1")
    outline = ([(a, b) for a, b in zip(xs, lower)]
               + [(a, b) for a, b in reversed(list(zip(xs, upper)))])
    return _filled(panel, outline, style)


def _filled(panel, outline: Sequence[Sequence], style: dict) -> Diagram:
    style.setdefault("fill", default_area_fill())
    style.setdefault("stroke", "none")
    style.setdefault("kind", MARK_KIND)
    return polygon(panel.map(outline), **style)


def step(panel, points: Sequence[Sequence], *, where: str = "post",
         **style) -> Diagram:
    """A staircase through the points. See `Panel.step`."""
    data = [tuple(p) for p in points]
    if len(data) < 2:
        raise DiagramError("a step plot needs at least two points")
    if where not in ("post", "pre", "mid"):
        raise DiagramError(
            f'unknown step position {where!r}; expected "post", "pre" or "mid"'
        )
    out = [data[0]]
    for (x0, y0), (x1, y1) in zip(data, data[1:]):
        if where == "post":
            out.append((x1, y0))
        elif where == "pre":
            out.append((x0, y1))
        else:
            middle = (x0 + x1) / 2
            out.extend(((middle, y0), (middle, y1)))
        out.append((x1, y1))
    style.setdefault("kind", MARK_LINE_KIND)
    return polyline(panel.map(out), **style)


# -- distributions --------------------------------------------------------


def _groups(panel, groups, at, orient: str) -> tuple[list, list[list[float]]]:
    """`(positions, samples)` for a box or violin plot.

    A mapping names its own positions, which is the spelling that cannot get
    the labels out of order. A bare sequence takes them from the band scale it
    is being drawn against, and only falls back to 0, 1, 2... when there is no
    band scale to ask.
    """
    position, _ = _axes_of(panel, orient)
    if isinstance(groups, Mapping):
        keys = list(groups.keys())
        samples = [[float(v) for v in groups[k]] for k in keys]
        return (list(at) if at is not None else keys), samples
    samples = [[float(v) for v in group] for group in groups]
    if at is not None:
        places = list(at)
    elif isinstance(position, Band):
        places = list(position.categories)
    else:
        places = list(range(len(samples)))
    if len(places) != len(samples):
        raise DiagramError(
            f"{len(places)} positions for {len(samples)} groups"
        )
    return places, samples


def boxplot(panel, groups, *, at=None, width: float = 0.6, orient: str = "v",
            whisker: float = 1.5, outliers: bool = True, colors=None,
            **style) -> Diagram:
    """Quartile boxes with Tukey whiskers. See `Panel.boxplot`."""
    places, samples = _groups(panel, groups, at, orient)
    position, value = _axes_of(panel, orient)
    theme = active_theme()
    # A box is read by its edges, not by its area: an unfilled box over paper
    # keeps the median line and the whiskers the only ink in it. Ask for a
    # fill and you get the palette instead.
    given = style.pop("fill", None) if colors is None else colors
    fills = (series_colors(given, len(samples)) if given is not None
             else (theme.paper,) * len(samples))
    items: list = []
    for index, (where, sample) in enumerate(zip(places, samples)):
        stats = box_stats(sample, whisker=whisker)
        lo, hi = _slot(position, where, width)
        middle = (lo + hi) / 2
        a, b = value.map(stats.q1), value.map(stats.q3)
        items.append(_rect(_point(orient, middle, (a + b) / 2),
                           *_extent(orient, abs(hi - lo), abs(b - a)),
                           fills[index], theme.ink, theme.stroke))
        # The median is the number the reader takes away, so it is the one
        # heavy line on the box rather than another hairline among four.
        at_median = value.map(stats.median)
        items.append(polyline((_point(orient, lo, at_median),
                               _point(orient, hi, at_median)),
                              kind=MARK_LINE_KIND, stroke=theme.ink,
                              stroke_width=theme.thick, stroke_linecap="butt"))
        quarter = abs(hi - lo) / 4
        for end, box_edge in ((stats.low, stats.q1), (stats.high, stats.q3)):
            tip, root = value.map(end), value.map(box_edge)
            items.append(polyline((_point(orient, middle, root),
                                   _point(orient, middle, tip)),
                                  kind=MARK_LINE_KIND, stroke=theme.ink,
                                  stroke_width=theme.stroke))
            items.append(polyline((_point(orient, middle - quarter, tip),
                                   _point(orient, middle + quarter, tip)),
                                  kind=MARK_LINE_KIND, stroke=theme.ink,
                                  stroke_width=theme.stroke))
        if outliers:
            size = _OUTLIER_OF_TYPE * theme.font_size
            for value_out in stats.outliers:
                items.append((_point(orient, middle, value.map(value_out)),
                              make_marker("circle", size, fill=theme.muted)))
    return draw_place(items, **style)


def violin(panel, groups, *, at=None, width: float = 0.8, orient: str = "v",
           bandwidth: float | None = None, samples: int = 64,
           cut: float = 2.0, median: bool = True, colors=None,
           **style) -> Diagram:
    """Mirrored kernel densities. See `Panel.violin`."""
    places, data = _groups(panel, groups, at, orient)
    position, value = _axes_of(panel, orient)
    theme = active_theme()
    given = style.pop("fill", None) if colors is None else colors
    fills = (series_colors(given, len(data)) if given is not None
             else (mix(theme.ink, theme.paper, _SINGLE_TINT),) * len(data))
    if samples < 4:
        raise DiagramError(f"a violin needs at least 4 samples, got {samples}")
    items: list = []
    for index, (where, sample) in enumerate(zip(places, data)):
        lo, hi = _slot(position, where, width)
        middle = (lo + hi) / 2
        reach = abs(hi - lo) / 2
        spread = _bandwidth(sample) if bandwidth is None else float(bandwidth)
        pad = cut * spread
        low, high = _within(value, min(sample) - pad, max(sample) + pad)
        if high <= low:
            continue                    # the whole sample is off this axis
        grid = [low + (high - low) * i / (samples - 1)
                for i in range(samples)]
        density = kde(sample, grid, bandwidth=bandwidth)
        peak = max(density)
        if peak <= 0:
            continue                    # every value identical: nothing to shape
        left = [_point(orient, middle - reach * d / peak, value.map(g))
                for g, d in zip(grid, density)]
        right = [_point(orient, middle + reach * d / peak, value.map(g))
                 for g, d in reversed(list(zip(grid, density)))]
        items.append(polygon(left + right, kind=MARK_KIND, fill=fills[index],
                             stroke=theme.ink, stroke_width=theme.hairline))
        if median:
            at_median = quantile(sample, 0.5)
            span = reach * _at(grid, density, at_median) / peak
            items.append(polyline(
                (_point(orient, middle - span, value.map(at_median)),
                 _point(orient, middle + span, value.map(at_median))),
                kind=MARK_LINE_KIND, stroke=theme.ink, stroke_width=theme.stroke))
    if not items:
        raise DiagramError("violin() had nothing to draw")
    return draw_place(items, **style)


def _within(scale: Scale, low: float, high: float) -> tuple[float, float]:
    """Keep a kernel inside the axis it is drawn against.

    The kernel reaches `cut` bandwidths past the most extreme observation,
    which is right for the shape of the density and wrong for the page: a
    violin whose tail runs out through the spine is not showing data, it is
    showing where the kernel happened to stop. So the grid ends at the domain.
    """
    domain = getattr(scale, "domain", None)
    if not isinstance(domain, tuple) or len(domain) != 2:
        return low, high
    try:
        first, second = float(domain[0]), float(domain[1])
    except (TypeError, ValueError):
        return low, high                # a Band, or anything else not numeric
    bottom, top = min(first, second), max(first, second)
    return max(low, bottom), min(high, top)


def _at(grid: Sequence[float], density: Sequence[float], value: float) -> float:
    """The density at one value, interpolated between grid points, so the
    median line stops exactly on the outline rather than crossing it."""
    for (a, da), (b, db) in zip(zip(grid, density), zip(grid[1:], density[1:])):
        if a <= value <= b:
            t = 0.0 if b == a else (value - a) / (b - a)
            return da + (db - da) * t
    return 0.0


# -- scatter --------------------------------------------------------------


def scatter(panel, points: Sequence[Sequence], *, size=None, color=None,
            marker: str = "circle", **style) -> Diagram:
    """Markers whose size and colour may themselves be data. See
    `Panel.scatter`."""
    data = [tuple(p) for p in points]
    if not data:
        raise DiagramError("scatter() was given no points")
    sizes = _per_point(size, len(data), "size")
    fills = _per_point(color, len(data), "color")
    placed = []
    for index, point in enumerate(data):
        node = make_marker(marker, sizes[index])
        if fills[index] is not None:
            node = node.styled(fill=fills[index])
        placed.append((panel.point(*point), node))
    return draw_place(placed, **style)


def _per_point(value, count: int, name: str) -> list:
    if value is None or isinstance(value, (str, int, float)):
        return [value] * count
    given = list(value)
    if len(given) != count:
        raise DiagramError(f"{name}= has {len(given)} values for {count} points")
    return given


# -- reference lines and bands --------------------------------------------


def rule(panel, *, x=None, y=None, span=None, **style) -> Diagram:
    """One reference line across the area. See `Panel.hline` / `Panel.vline`."""
    theme = active_theme()
    box = panel.area
    if (x is None) == (y is None):
        raise DiagramError("a rule is at one x or one y, not both or neither")
    if y is not None:
        at = panel.y.map(y)
        a, b = ((box.x0, box.x1) if span is None
                else (panel.x.map(span[0]), panel.x.map(span[1])))
        ends = ((a, at), (b, at))
    else:
        at = panel.x.map(x)
        a, b = ((box.y0, box.y1) if span is None
                else (panel.y.map(span[0]), panel.y.map(span[1])))
        ends = ((at, a), (at, b))
    style.setdefault("stroke", theme.muted)
    style.setdefault("stroke_width", theme.hairline)
    style.setdefault("kind", MARK_LINE_KIND)
    return polyline(ends, **style)


def span_node(panel, *, x=None, y=None, **style) -> Diagram:
    """A shaded band across the area, in data coordinates."""
    theme = active_theme()
    box = panel.area
    if (x is None) == (y is None):
        raise DiagramError("a span covers a range of x or of y, not both")
    if x is not None:
        a, b = panel.x.map(x[0]), panel.x.map(x[1])
        corners = ((a, box.y0), (b, box.y0), (b, box.y1), (a, box.y1))
    else:
        a, b = panel.y.map(y[0]), panel.y.map(y[1])
        corners = ((box.x0, a), (box.x1, a), (box.x1, b), (box.x0, b))
    style.setdefault("fill", mix(theme.ink, theme.paper, _SINGLE_TINT))
    style.setdefault("stroke", "none")
    style.setdefault("kind", MARK_KIND)
    return polygon(corners, **style)


def rect_node(panel, x0, y0, x1, y1, **style) -> Diagram:
    """A rectangle whose four sides are data values."""
    theme = active_theme()
    corners = panel.map(((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
    style.setdefault("fill", mix(theme.ink, theme.paper, _SINGLE_TINT))
    style.setdefault("stroke", "none")
    style.setdefault("kind", MARK_KIND)
    return polygon(corners, **style)


# -- swarm ----------------------------------------------------------------

#: A swarm dot, as a fraction of the type size. Deliberately the same fraction
#: a box plot's outlier gets: both stand for one observation, and a swarm
#: drawn beside a box has to read as the same kind of mark.
_SWARM_OF_TYPE = _OUTLIER_OF_TYPE

#: Air between two neighbouring dots, as a fraction of a dot's diameter. Below
#: about a fifth a touching pair reads as one figure-of-eight; above a half the
#: swarm is wider than the band it sits in before it is interesting.
_SWARM_GAP = 0.3

#: A dot smaller than this, in millimetres, is a full stop rather than a mark
#: -- at 300dpi it is five pixels across -- so the width policy stops shrinking
#: here and lets the swarm run wide instead.
_SWARM_MIN_DOT = 0.4

#: Bisection steps used to fit a swarm to its width. Ten halvings of the gap
#: land within a thousandth of a millimetre of the widest layout that fits,
#: which is finer than the renderer's own rounding.
_SWARM_STEPS = 10

#: Offsets this close together in millimetres are the same offset. The free
#: candidates are the *edges* of the blocked intervals, so a dot placed exactly
#: on one would otherwise fail its own containment test -- and two intervals
#: that only touch have to stay two, or the point they touch at stops counting
#: as free.
_SWARM_EPS = 1e-9


def swarm_offsets(across: Sequence[float], pitch: float) -> list[float]:
    """Sideways offsets in millimetres that keep every dot clear of every other.

    `across` is where each observation lands on its value axis, already in
    millimetres, and `pitch` is the closest two dot centres may come -- a
    diameter plus whatever air the caller wants. The result is one offset per
    observation, in the order they were given, and the same numbers on every
    run: the only ordering is by value with the input index as the tie-break,
    so two identical samples swarm identically and nothing here consults a
    hash, a clock or a random number.

    The placement is greedy and nearest-first, the algorithm a beeswarm
    normally uses. Observations are laid down in ascending value; each one
    takes the smallest offset that no already-placed dot forbids. A placed dot
    at `(x, y)` forbids the interval `x ± sqrt(pitch² - dy²)` for a new dot
    `dy` away, so the candidates worth testing are that interval's two edges,
    and the centre line. A tie between the two sides goes to the emptier one,
    which is what keeps a symmetric sample from drifting off to the left.

    Greedy placement alone leans, because the first dot of a colliding pair
    keeps the centre line and the second one moves the whole way aside. So a
    second pass centres each *run* -- a maximal chain of observations whose
    neighbouring values are less than `pitch` apart -- on the category line.
    That cannot create an overlap: everything in a run shifts by one amount, so
    distances inside it are unchanged, and two dots in different runs are at
    least `pitch` apart along the value axis whatever their offsets.

    Values are never moved. A swarm that quantised them onto rows would be a
    dot histogram, and the dot would no longer sit at the number the axis says
    it does -- which matters most in exactly the figure that wants a swarm, the
    one with a mean and an interval drawn over the points.
    """
    if pitch <= 0:
        raise DiagramError(f"a swarm needs a positive pitch, got {pitch!r}")
    order = sorted(range(len(across)), key=lambda i: (across[i], i))
    offsets = [0.0] * len(across)
    placed: list[tuple[float, float]] = []      # (value, offset), value order
    bias = 0
    for index in order:
        here = across[index]
        blocked = []
        for value, offset in reversed(placed):
            gap = here - value
            if gap >= pitch:
                break                   # and everything below it is further
            half = math.sqrt(max(pitch * pitch - gap * gap, 0.0))
            blocked.append((offset - half, offset + half))
        x = _free_offset(blocked, bias)
        offsets[index] = x
        bias += (x > 0) - (x < 0)
        placed.append((here, x))
    _centre_runs(across, offsets, pitch, order)
    return offsets


def _free_offset(blocked: Sequence[tuple[float, float]], bias: int) -> float:
    """The offset nearest the centre line that no blocked interval covers.

    Merging the intervals first is what keeps a crowded swarm cheap. If the
    centre line is free the answer is the centre line; if it is not, it sits
    inside exactly one merged interval, and the two ends of *that* interval are
    the nearest free offsets there are -- everything between them is blocked
    and everything beyond them is further away. So a dot costs one sort of the
    dots within a pitch of it rather than a scan of every edge against every
    interval, which at two thousand crowded points is the difference between
    0.68 s and 0.05 s.

    Intervals that merely touch are left unmerged: their shared endpoint is a
    free offset, and it is often the best one on the page.

    `bias` is how many dots have already gone right minus how many went left;
    when the two ends are equally near, the emptier side wins.
    """
    merged: list[list[float]] = []
    for lo, hi in sorted(blocked):
        if merged and lo < merged[-1][1] - _SWARM_EPS:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    for lo, hi in merged:
        if lo + _SWARM_EPS < 0.0 < hi - _SWARM_EPS:
            if abs(lo) < abs(hi) or (abs(lo) == abs(hi) and bias >= 0):
                return lo
            return hi
    return 0.0


def _centre_runs(across: Sequence[float], offsets: list[float], pitch: float,
                 order: Sequence[int]) -> None:
    """Slide each run of touching observations back onto the category line."""
    run = [order[0]]
    for previous, index in zip(order, order[1:]):
        if across[index] - across[previous] < pitch:
            run.append(index)
        else:
            _centre_run(offsets, run)
            run = [index]
    _centre_run(offsets, run)


def _centre_run(offsets: list[float], run: Sequence[int]) -> None:
    shift = (min(offsets[i] for i in run) + max(offsets[i] for i in run)) / 2
    if shift:
        for index in run:
            offsets[index] -= shift


def _swarm_width(offsets: Sequence[float], dot: float) -> float:
    """How much paper the dots occupy across the category, edge to edge."""
    return (max(offsets) - min(offsets)) + dot if offsets else 0.0


def _swarm_fit(across: Sequence[float], cap: float, dot: float,
               gap: float) -> tuple[list[float], float]:
    """`(offsets, diameter)` for the widest swarm that fits `cap` millimetres.

    The policy, in the order a reader would want it: **air goes first, then
    size**. A swarm that overruns its width has the gap between its dots
    bisected away, down to dots that touch -- the dots stay the size they were
    asked for and only the offsets shrink, because a dot's size is data (it is
    what makes an observation visible) and the air between two of them is not.
    Only when touching dots still overrun does the diameter itself come down,
    and it stops at `_SWARM_MIN_DOT`: past that the swarm would fit by becoming
    unreadable, which is not fitting. A swarm that cannot fit even then is
    returned too wide, for the panel to clip and the linter to report.
    """
    offsets = swarm_offsets(across, dot + gap)
    if _swarm_width(offsets, dot) <= cap or len(across) < 2:
        return offsets, dot
    low, high, best = 0.0, gap, swarm_offsets(across, dot)
    for _ in range(_SWARM_STEPS):
        middle = (low + high) / 2
        trial = swarm_offsets(across, dot + middle)
        if _swarm_width(trial, dot) <= cap:
            low, best = middle, trial
        else:
            high = middle
    if _swarm_width(best, dot) <= cap:
        return best, dot
    low, high = _SWARM_MIN_DOT, dot
    best, size = swarm_offsets(across, low), low
    for _ in range(_SWARM_STEPS):
        middle = (low + high) / 2
        trial = swarm_offsets(across, middle)
        if _swarm_width(trial, middle) <= cap:
            low, best, size = middle, trial, middle
        else:
            high = middle
    return best, size


def _swarm_colors(colors, count: int, theme) -> tuple[str, ...]:
    """One colour per group, dark enough to survive being a millimetre across.

    `series_colors` answers with a pale tint for a lone series, which is right
    for a bar and wrong here: 14% ink at 0.8mm is a smudge. A single swarm is
    therefore the ink itself, and several groups take the *ink* palette -- the
    darker variant meant for strokes and hairlines -- for the same reason.
    """
    if colors is not None:
        return series_colors(colors, count)
    if count == 1:
        return (theme.ink,)
    return tuple(theme.ink_color(i) for i in range(count))


def swarm(panel, groups, *, at=None, width: float = 0.8,
          max_width: float | str | None = None, orient: str = "v",
          size: float | str | None = None, gap: float | str | None = None,
          marker: str = "circle", hollow: bool = False, colors=None,
          **style) -> Diagram:
    """One dot per observation, packed so that none hides another. See
    `Panel.swarm`."""
    places, samples = _groups(panel, groups, at, orient)
    position, value = _axes_of(panel, orient)
    theme = active_theme()
    dot = _SWARM_OF_TYPE * theme.font_size if size is None else mm(size)
    if dot <= 0:
        raise DiagramError(f"a swarm needs a positive dot size, got {size!r}")
    air = dot * _SWARM_GAP if gap is None else mm(gap)
    if air < 0:
        raise DiagramError(f"a swarm's gap cannot be negative, got {gap!r}")
    given = style.pop("fill", None) if colors is None else colors
    fills = _swarm_colors(given, len(samples), theme)
    caps, rows = [], []
    for where, sample in zip(places, samples):
        low, high = _slot(position, where, width)
        cap = abs(high - low)
        if max_width is not None:
            cap = min(cap, mm(max_width))
        caps.append(cap)
        rows.append([value.map(v) for v in sample])
    # One call draws one kind of mark, so the whole swarm takes the smallest
    # dot any of its groups had to shrink to rather than letting a crowded
    # group quietly draw smaller observations than a sparse one.
    laid = [_swarm_fit(row, cap, dot, air) if row else ([], dot)
            for row, cap in zip(rows, caps)]
    for _ in range(2):
        smallest = min((size for _, size in laid), default=dot)
        if smallest >= dot:
            break
        dot = smallest
        laid = [_swarm_fit(row, cap, dot, air) if row else ([], dot)
                for row, cap in zip(rows, caps)]
    items: list = []
    for index, (where, row) in enumerate(zip(places, rows)):
        if not row:
            continue                    # a group with no data draws nothing
        low, high = _slot(position, where, width)
        centre = (low + high) / 2
        offsets, drawn = laid[index]
        ink = fills[index]
        shape = ({"fill": theme.paper, "stroke": ink,
                  "stroke_width": theme.hairline} if hollow else {"fill": ink})
        for offset, along in zip(offsets, row):
            items.append((_point(orient, centre + offset, along),
                          make_marker(marker, drawn, **shape)))
    if not items:
        raise DiagramError("swarm() had nothing to draw")
    return draw_place(items, **style)
