"""Kernel density estimates: 1D curves and 2D contour levels.

The arithmetic here draws nothing. `bandwidth` applies a named rule,
`kde_curve` evaluates a 1D Gaussian kernel density on an even grid, and
`kde2d` evaluates a 2D product-kernel density on an even lattice. The
drawing halves, `kde_layer` and `kde2d_layer`, are what `Panel.kde` and
`Panel.kde2d` call.

**Bandwidth rules.** `"scott"` is R's `bw.nrd`,
``1.06 * min(sd, IQR / 1.34) * n ** -0.2``; `"silverman"` is R's `bw.nrd0`,
``0.9 * min(sd, IQR / 1.34) * n ** -0.2``. When the IQR is zero the standard
deviation is used alone, then ``|x[0]|``, then 1, as `bw.nrd0` does. SciPy's
`gaussian_kde` rules differ (its "scott" is ``sd * n ** -0.2``), so the two
libraries draw slightly different curves for the same rule name. In 2D the
rule is applied per axis with the normal-reference exponent for two
dimensions, ``sd * n ** (-1/6)``, for which Scott's and Silverman's rules
agree.

**The 2D estimate is binned.** The points are spread over the lattice by
linear binning and the counts convolved with a separable Gaussian cut off at
four bandwidths. The lattice is made fine enough that its spacing is at most a
third of the bandwidth, so the result is within about one percent of the
exact sum at the peak while costing time proportional to the lattice rather
than to the number of points. It is pure Python and deterministic.

**Contour levels are probability masses.** `levels=(0.5, 0.95)` draws the
contours of the highest-density regions holding 50% and 95% of the estimated
mass, which is a statement a reader can check against the points. A density
value in data units would change with the axis units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError
from ..draw.coords import active_theme
from ..draw.path import path as draw_path, polygon, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND
from ..themes.color import mix
from .scale import Band, Linear, Log
from .statistics import _quantile_sorted, kde

__all__ = ["BANDWIDTH_RULES", "Density2D", "bandwidth", "kde2d", "kde_curve",
           "mass_levels"]

#: Named bandwidth rules accepted wherever `bandwidth=` is.
BANDWIDTH_RULES = ("scott", "silverman")

_FACTOR = {"scott": 1.06, "silverman": 0.9}

#: The fill of a filled density curve, as an opacity of its line colour, so
#: two overlapping groups remain readable through each other.
_FILL_OPACITY = 0.25

#: The kernel is cut off this many bandwidths from its centre.
_REACH = 4.0

#: The largest 2D lattice, in points per side.
_MAX_GRID = 256


def _clean(values) -> list[float]:
    out = []
    for v in values:
        if v is None:
            continue
        f = float(v)
        if math.isfinite(f):
            out.append(f)
    return out


def bandwidth(values: Sequence[float], rule: str | float = "scott", *,
              adjust: float = 1.0) -> float:
    """The kernel bandwidth for `values` under a named rule, times `adjust`.

    `rule` is `"scott"` (R's `bw.nrd`), `"silverman"` (R's `bw.nrd0`) or a
    number, which is returned times `adjust`. Missing and non-finite values
    are ignored. At least two values are needed for a rule.
    """
    if adjust <= 0 or not math.isfinite(adjust):
        raise DiagramError(f"bandwidth adjust must be positive, got {adjust!r}")
    if isinstance(rule, Real) and not isinstance(rule, bool):
        if not rule > 0 or not math.isfinite(rule):
            raise DiagramError(f"a bandwidth must be positive, got {rule!r}")
        return float(rule) * adjust
    if rule not in _FACTOR:
        raise DiagramError(
            f'bandwidth rule is "scott", "silverman" or a number, not {rule!r}')
    data = _clean(values)
    n = len(data)
    if n < 2:
        raise DiagramError("a bandwidth rule needs at least two values")
    mean = math.fsum(data) / n
    sd = math.sqrt(math.fsum((v - mean) ** 2 for v in data) / (n - 1))
    ordered = sorted(data)
    iqr = _quantile_sorted(ordered, 0.75) - _quantile_sorted(ordered, 0.25)
    spread = min(sd, iqr / 1.34)
    if not spread > 0:
        spread = sd or abs(data[0]) or 1.0
    return _FACTOR[rule] * spread * n ** -0.2 * adjust


def kde_curve(values: Sequence[float], *, bandwidth: str | float = "scott",
              adjust: float = 1.0, cut: float = 3.0, samples: int = 200,
              low: float | None = None, high: float | None = None,
              weights_total: float | None = None
              ) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """A Gaussian kernel density on an even grid: `(grid, density)`.

    The grid runs from `cut` bandwidths below the smallest value to `cut`
    above the largest, or from `low` to `high` where given, in `samples`
    points. The density integrates to one over the whole line;
    `weights_total=n` multiplies it by `n`, which turns it into counts per
    unit of x. Call this first to find the y domain of a density panel:

        grid, density = inklet.plot.kde_curve(values)
        p = inklet.panel(50, 30, x=(grid[0], grid[-1]), y=(0, max(density) * 1.1))
    """
    data = _clean(values)
    if len(data) < 2:
        raise DiagramError("a density curve needs at least two values")
    if samples < 4:
        raise DiagramError(f"a density curve needs at least 4 samples, got {samples}")
    if cut < 0:
        raise DiagramError(f"cut cannot be negative, got {cut!r}")
    h = _bandwidth_of(data, bandwidth, adjust)
    lo = min(data) - cut * h if low is None else float(low)
    hi = max(data) + cut * h if high is None else float(high)
    if not hi > lo:
        raise DiagramError(f"a density curve needs high > low, got {lo} and {hi}")
    grid = tuple(lo + (hi - lo) * k / (samples - 1) for k in range(samples))
    density = kde(data, grid, bandwidth=h)
    if weights_total is not None:
        density = tuple(d * weights_total for d in density)
    return grid, density


def _bandwidth_of(data: list[float], rule, adjust: float) -> float:
    # One distinct value has no spread for a rule to use; bw.nrd0's
    # fallbacks still give it a width, which draws a narrow bump.
    return bandwidth(data, rule, adjust=adjust)


# -- 1D drawing -------------------------------------------------------------


def _as_groups(values) -> tuple[list[str | None], list[list[float]]]:
    if isinstance(values, Mapping):
        names = [str(k) for k in values]
        return names, [_clean(values[k]) for k in values]
    return [None], [_clean(values)]


def _colors(color, count: int, theme) -> list[str]:
    if color is None:
        if count == 1:
            return [theme.ink]
        return [theme.ink_color(i) for i in range(count)]
    if isinstance(color, str):
        return [color] * count
    given = list(color)
    if not given:
        raise DiagramError("color= was given no colours")
    return [given[i % len(given)] for i in range(count)]


def kde_layer(panel, values, *, bandwidth="scott", adjust: float = 1.0,
              cut: float = 3.0, samples: int = 200, fill: bool = False,
              stat: str = "density", orient: str = "v", color=None,
              baseline: float = 0.0, **style) -> tuple[Diagram, list, dict]:
    """The curves of `Panel.kde`. Returns `(node, [(name, color)], note)`."""
    if stat not in ("density", "count"):
        raise DiagramError(f'kde stat is "density" or "count", not {stat!r}')
    if orient not in ("v", "h"):
        raise DiagramError(f'kde orient is "v" or "h", not {orient!r}')
    value_scale, level_scale = ((panel.x, panel.y) if orient == "v"
                                else (panel.y, panel.x))
    if isinstance(value_scale, Band) or isinstance(level_scale, Band):
        raise DiagramError("kde needs continuous x and y scales")
    names, groups = _as_groups(values)
    theme = active_theme()
    inks = _colors(color, len(groups), theme)
    domain = _numeric_domain(value_scale)
    fills: list = []
    lines: list = []
    note = {"bandwidth": [], "peak": [], "stat": stat, "groups": list(names),
            "log": isinstance(value_scale, Log)}
    drawn: list = []
    on_log = isinstance(value_scale, Log)
    if on_log:
        # Estimated in log10 units, the way the axis spaces them: a
        # log-normal sample is then a symmetric bump, not a spike at zero.
        groups = [[math.log10(v) for v in g if v > 0] for g in groups]
        if domain is not None:
            domain = (math.log10(domain[0]), math.log10(domain[1]))
    for name, sample, ink in zip(names, groups, inks):
        if len(sample) < 2:
            raise DiagramError(
                f"kde group {name!r} needs at least two finite values"
                if name is not None else "kde needs at least two finite values")
        h = bandwidth_value = _bandwidth_of(sample, bandwidth, adjust)
        lo, hi = min(sample) - cut * h, max(sample) + cut * h
        if domain is not None:
            lo, hi = max(lo, domain[0]), min(hi, domain[1])
        if not hi > lo:
            continue
        grid, density = kde_curve(sample, bandwidth=bandwidth_value, cut=cut,
                                  samples=samples, low=lo, high=hi,
                                  weights_total=len(sample) if stat == "count" else None)
        if on_log:
            grid = tuple(10.0 ** g for g in grid)
        pts = [_oriented(orient, value_scale.map(g), level_scale.map(baseline + d))
               for g, d in zip(grid, density)]
        if fill:
            base = [_oriented(orient, value_scale.map(g), level_scale.map(baseline))
                    for g in (grid[-1], grid[0])]
            fills.append(polygon(pts + base, kind=MARK_KIND, fill=ink,
                                 fill_opacity=_FILL_OPACITY, stroke="none"))
        line_style = {"stroke": ink, "stroke_width": theme.stroke,
                      "stroke_linejoin": "round"}
        line_style.update(style)
        lines.append(polyline(pts, kind=MARK_LINE_KIND, **line_style))
        note["bandwidth"].append(bandwidth_value)
        note["peak"].append(max(density))
        drawn.append((name, line_style["stroke"]))
    if not lines:
        raise DiagramError("kde() had nothing to draw inside the axis domain")
    node = draw_place(fills + lines, origin=(0, 0), kind="kde")
    node.notes["kde"] = note
    return node, drawn, note


def _oriented(orient: str, along: float, level: float):
    return (along, level) if orient == "v" else (level, along)


def _numeric_domain(scale) -> tuple[float, float] | None:
    domain = getattr(scale, "domain", None)
    try:
        a, b = float(domain[0]), float(domain[1])
    except (TypeError, ValueError, IndexError):
        return None
    return min(a, b), max(a, b)


# -- 2D density -------------------------------------------------------------


@dataclass(frozen=True)
class Density2D:
    """A density on an even lattice: `values[j][i]` at `(xs[i], ys[j])`.

    `bandwidth` is the `(x, y)` kernel bandwidth in the coordinates the
    density was computed in, and `count` the number of points used.
    """

    xs: tuple[float, ...]
    ys: tuple[float, ...]
    values: tuple[tuple[float, ...], ...]
    bandwidth: tuple[float, float]
    count: int

    def at(self, x: float, y: float) -> float:
        """The density at one point, interpolated bilinearly; 0 outside."""
        xs, ys = self.xs, self.ys
        if not (xs[0] <= x <= xs[-1] and ys[0] <= y <= ys[-1]):
            return 0.0
        fx = (x - xs[0]) / (xs[1] - xs[0])
        fy = (y - ys[0]) / (ys[1] - ys[0])
        i = min(int(fx), len(xs) - 2)
        j = min(int(fy), len(ys) - 2)
        u, v = fx - i, fy - j
        g = self.values
        return ((1 - u) * (1 - v) * g[j][i] + u * (1 - v) * g[j][i + 1]
                + (1 - u) * v * g[j + 1][i] + u * v * g[j + 1][i + 1])


def _axis_bandwidth(data: list[float], rule, adjust: float) -> float:
    if isinstance(rule, Real) and not isinstance(rule, bool):
        return bandwidth(data, rule, adjust=adjust)
    if rule not in _FACTOR:
        raise DiagramError(
            f'bandwidth rule is "scott", "silverman" or a number, not {rule!r}')
    n = len(data)
    mean = math.fsum(data) / n
    sd = math.sqrt(math.fsum((v - mean) ** 2 for v in data) / (n - 1))
    if not sd > 0:
        sd = abs(data[0]) or 1.0
    return sd * n ** (-1.0 / 6.0) * adjust


def kde2d(points: Sequence[Sequence[float]], *, bandwidth="scott",
          adjust: float = 1.0, gridsize: int = 96, cut: float = 3.0,
          extent: tuple[float, float, float, float] | None = None) -> Density2D:
    """A 2D Gaussian product-kernel density on an even lattice.

    `bandwidth` is a rule name (applied per axis as ``sd * n ** (-1/6)``),
    one number for both axes or an `(x, y)` pair, in the units of the
    points; `adjust` multiplies it. The lattice spans `cut` bandwidths past
    the data, or `extent=(x0, x1, y0, y1)`, with at least `gridsize` points
    per side -- more when the bandwidth is small, up to 256. The density
    integrates to one over the plane.
    """
    xs_data, ys_data = [], []
    for p in points:
        x, y = float(p[0]), float(p[1])
        if math.isfinite(x) and math.isfinite(y):
            xs_data.append(x)
            ys_data.append(y)
    n = len(xs_data)
    if n < 2:
        raise DiagramError("a 2D density needs at least two finite points")
    if gridsize < 8:
        raise DiagramError(f"kde2d gridsize must be at least 8, got {gridsize}")
    if isinstance(bandwidth, (tuple, list)):
        if len(bandwidth) != 2:
            raise DiagramError("a bandwidth pair is (x, y)")
        hx = _axis_bandwidth(xs_data, bandwidth[0], adjust)
        hy = _axis_bandwidth(ys_data, bandwidth[1], adjust)
    else:
        hx = _axis_bandwidth(xs_data, bandwidth, adjust)
        hy = _axis_bandwidth(ys_data, bandwidth, adjust)
    if extent is None:
        x0, x1 = min(xs_data) - cut * hx, max(xs_data) + cut * hx
        y0, y1 = min(ys_data) - cut * hy, max(ys_data) + cut * hy
    else:
        x0, x1, y0, y1 = (float(v) for v in extent)
        if not (x1 > x0 and y1 > y0):
            raise DiagramError("kde2d extent is (x0, x1, y0, y1) with x1 > x0 and y1 > y0")
    nx = _lattice(x1 - x0, hx, gridsize)
    ny = _lattice(y1 - y0, hy, gridsize)
    dx, dy = (x1 - x0) / (nx - 1), (y1 - y0) / (ny - 1)
    counts = [[0.0] * nx for _ in range(ny)]
    for x, y in zip(xs_data, ys_data):
        fx, fy = (x - x0) / dx, (y - y0) / dy
        i, j = math.floor(fx), math.floor(fy)
        u, v = fx - i, fy - j
        for di, wu in ((0, 1 - u), (1, u)):
            for dj, wv in ((0, 1 - v), (1, v)):
                a, b = i + di, j + dj
                if 0 <= a < nx and 0 <= b < ny:
                    counts[b][a] += wu * wv
    kx = _kernel(dx / hx)
    ky = _kernel(dy / hy)
    rows = [_convolve(row, kx) for row in counts]
    columns = [_convolve([rows[j][i] for j in range(ny)], ky) for i in range(nx)]
    norm = 1.0 / (n * hx * hy * 2.0 * math.pi)
    values = tuple(tuple(columns[i][j] * norm for i in range(nx)) for j in range(ny))
    return Density2D(
        xs=tuple(x0 + dx * i for i in range(nx)),
        ys=tuple(y0 + dy * j for j in range(ny)),
        values=values, bandwidth=(hx, hy), count=n)


def _lattice(span: float, h: float, gridsize: int) -> int:
    """Points per side: `gridsize`, or enough for a spacing of h / 3."""
    need = int(math.ceil(3.0 * span / h)) + 1
    return max(gridsize, min(_MAX_GRID, need))


def _kernel(step: float) -> list[float]:
    """Gaussian weights at integer offsets of `step` bandwidths."""
    reach = max(1, int(math.ceil(_REACH / step)))
    return [math.exp(-0.5 * (k * step) ** 2) for k in range(-reach, reach + 1)]


def _convolve(row: Sequence[float], kernel: Sequence[float]) -> list[float]:
    n = len(row)
    reach = len(kernel) // 2
    out = [0.0] * n
    for i, value in enumerate(row):
        if value == 0.0:
            continue
        lo = max(0, i - reach)
        hi = min(n - 1, i + reach)
        for t in range(lo, hi + 1):
            out[t] += value * kernel[t - i + reach]
    return out


def mass_levels(density: Density2D, masses: Sequence[float]) -> tuple[float, ...]:
    """The density thresholds whose superlevel sets hold `masses` of the
    estimated probability, one per mass (each strictly between 0 and 1)."""
    flat = sorted((v for row in density.values for v in row), reverse=True)
    total = math.fsum(flat)
    if not total > 0:
        raise DiagramError("the density is zero everywhere")
    out = []
    for mass in masses:
        if not 0.0 < mass < 1.0:
            raise DiagramError(f"a contour mass is between 0 and 1, got {mass!r}")
        target = mass * total
        running = 0.0
        level = flat[-1]
        for value in flat:
            running += value
            if running >= target:
                level = value
                break
        out.append(level)
    return tuple(out)


def _masses(levels) -> tuple[float, ...]:
    if isinstance(levels, int) and not isinstance(levels, bool):
        if levels < 1:
            raise DiagramError(f"kde2d needs at least one level, got {levels}")
        return tuple(round(0.95 * k / levels, 12) for k in range(levels, 0, -1))
    masses = tuple(float(m) for m in levels)
    if not masses:
        raise DiagramError("kde2d needs at least one level")
    return tuple(sorted(masses, reverse=True))


def _transform(scale):
    """`(forward, backward)` between data and the space a density is
    estimated in: the data itself on a linear axis, its logarithm on a log
    axis."""
    if isinstance(scale, Log):
        base = scale.base
        return (lambda v: math.log(v, base) if v > 0 else math.nan,
                lambda t: base ** t)
    if isinstance(scale, Linear):
        return (float, float)
    raise DiagramError("2D densities need linear or log x and y scales")


def kde2d_layer(panel, points, *, levels=5, fill: bool = False,
                bandwidth="scott", adjust: float = 1.0, gridsize: int = 96,
                cut: float = 3.0, color=None, ramp=None,
                **style) -> tuple[Diagram, dict]:
    """The contours of `Panel.kde2d`. Returns `(node, note)`."""
    from ..plot.outlines import _contours

    fx, bx = _transform(panel.x)
    fy, by = _transform(panel.y)
    moved = [(fx(float(p[0])), fy(float(p[1]))) for p in points]
    density = kde2d(moved, bandwidth=bandwidth, adjust=adjust,
                    gridsize=gridsize, cut=cut)
    masses = _masses(levels)
    thresholds = mass_levels(density, masses)
    theme = active_theme()
    colors = _level_colors(len(masses), fill, color, ramp, theme)
    nx, ny = len(density.xs), len(density.ys)
    dx = density.xs[1] - density.xs[0]
    dy = density.ys[1] - density.ys[0]

    def page(ring):
        return [(panel.x.map(bx(density.xs[0] + i * dx)),
                 panel.y.map(by(density.ys[0] + j * dy))) for i, j in ring]

    items: list = []
    drawn_levels: list = []
    for mass, level, ink in zip(masses, thresholds, colors):
        grid = [[density.values[j][i] - level for i in range(nx)] for j in range(ny)]
        # A border below the level everywhere, so every ring closes.
        for i in range(nx):
            grid[0][i] = grid[ny - 1][i] = -level
        for row in grid:
            row[0] = row[nx - 1] = -level
        rings = [page(r) for r in _contours(grid)]
        rings = [r for r in rings if len(r) >= 3]
        if not rings:
            continue
        drawn_levels.append(mass)
        if fill:
            paint = {"fill": ink, "stroke": "none"}
            paint.update(style)
            items.append(polygon(rings[0], holes=rings[1:], fill_rule="evenodd",
                                 kind=MARK_KIND, **paint))
        else:
            paint = {"stroke": ink, "stroke_width": theme.stroke, "fill": "none",
                     "stroke_linejoin": "round"}
            paint.update(style)
            for ring in rings:
                items.append(draw_path(ring, closed=True, filled=False,
                                       kind=MARK_LINE_KIND, **paint))
    if not items:
        raise DiagramError("kde2d() found no contour to draw")
    node = draw_place(items, origin=(0, 0), kind="kde2d")
    note = {"masses": list(masses), "levels": list(thresholds),
            "drawn": drawn_levels, "bandwidth": density.bandwidth,
            "count": density.count, "grid": (nx, ny)}
    node.notes["kde2d"] = note
    return node, note


def _level_colors(count: int, fill: bool, color, ramp, theme) -> list[str]:
    """One colour per level, outermost (largest mass) first."""
    if color is not None and not isinstance(color, str):
        given = list(color)
        return [given[i % len(given)] for i in range(count)]
    if fill:
        if color is not None:
            # Tints of one colour, palest outside.
            if count == 1:
                return [mix(color, theme.paper, 0.45)]
            return [mix(color, theme.paper, 0.85 - 0.8 * k / (count - 1))
                    for k in range(count)]
        from .ramp import SEQUENTIAL
        chosen = SEQUENTIAL if ramp is None else ramp
        if count == 1:
            return [chosen(0.5)]
        return [chosen(0.08 + 0.8 * k / (count - 1)) for k in range(count)]
    if color is not None:
        return [color] * count
    if ramp is not None:
        if count == 1:
            return [ramp(0.7)]
        return [ramp(0.3 + 0.65 * k / (count - 1)) for k in range(count)]
    return [theme.ink] * count
