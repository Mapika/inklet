"""Pair plots and joint plots: figure-level grids that share their axes.

`pairplot` draws every pair of variables in a table against each other, in
a square grid whose columns share an x scale and whose rows share a y scale,
with each variable's distribution on the diagonal. `jointplot` draws one
pair with the two marginal distributions along the top and right edges.

Both return a finished `Diagram` whose plot areas are aligned by `facets`,
so it goes into `row`, `column`, `letters` or a `document` like a panel.
Only the outer panels write numbers and variable names; inner panels keep
their ticks.

Each diagonal panel of a pair plot shows a histogram (or a kernel density)
of its variable, scaled to fill 90% of the panel's height. Its height has no
axis of its own: the numbers down the left of the first row belong to the
first variable, as in every other panel of that row.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, mm
from ..core.prims import PhantomPrim
from ..draw.coords import active_theme
from ..draw.path import path as draw_path, polygon
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND
from ..themes.color import mix
from . import marks as _marks
from .facets import facets
from .kernel_density import kde_curve
from .panel import Panel, panel as make_panel
from .scale import linear, log as log_scale, nice_bounds
from .statistics import _bin_edges

__all__ = ["pairplot", "jointplot", "PAIR_KINDS", "MARGINAL_KINDS"]

#: What an off-diagonal panel of `pairplot` or the main panel of `jointplot`
#: may draw.
PAIR_KINDS = ("scatter", "kde2d", "hexbin", "hist2d", "regression")
#: What a diagonal or marginal panel may draw.
MARGINAL_KINDS = ("hist", "kde")

#: The share of a diagonal panel's height its tallest bar or peak fills.
_DIAG_FILL = 0.9
#: The fill of a group's distribution, as an opacity.
_GROUP_OPACITY = 0.3


# -- data -------------------------------------------------------------------

def _finite(v) -> bool:
    try:
        return v is not None and math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _domain(values: Sequence[float], is_log: bool, name: str) -> tuple[float, float]:
    clean = [float(v) for v in values if _finite(v) and (not is_log or float(v) > 0)]
    if not clean:
        raise DiagramError(f"{name!r} has no values to plot")
    lo, hi = min(clean), max(clean)
    if is_log:
        return (10.0 ** math.floor(math.log10(lo)), 10.0 ** math.ceil(math.log10(hi)
                                                                      + (1e-12 if lo == hi else 0)))
    if lo == hi:
        lo, hi = lo - 0.5, hi + 0.5
    return nice_bounds(lo, hi, 6)


def _scale(domain, is_log: bool):
    return log_scale(domain) if is_log else linear(domain)


def _edges(domain, bins: int, is_log: bool, values) -> list[float]:
    if is_log:
        lo, hi = domain
        clean = [float(v) for v in values if _finite(v) and float(v) > 0]
        lo, hi = min(clean), max(clean)
        if lo == hi:
            lo, hi = lo / 1.5, hi * 1.5
        ratio = math.log(hi / lo)
        return [lo * math.exp(ratio * k / bins) for k in range(bins + 1)]
    clean = [float(v) for v in values if _finite(v)]
    return list(_bin_edges(bins, min(clean), max(clean)))


def _split(columns: Sequence[Sequence], groups) -> tuple[list, list]:
    """Observations per group: `(names, [[column values per group]])`."""
    n = len(columns[0])
    if groups is None:
        return [None], [[list(c) for c in columns]]
    groups = list(groups)
    if len(groups) != n:
        raise DiagramError(f"groups= has {len(groups)} labels for {n} observations")
    names: list = []
    for g in groups:
        if g not in names:
            names.append(g)
    out = []
    for name in names:
        keep = [k for k, g in enumerate(groups) if g == name]
        out.append([[c[k] for k in keep] for c in columns])
    return [str(n) for n in names], out


def _group_colors(names, color) -> list[str]:
    theme = active_theme()
    if names == [None]:
        return [theme.ink if color is None else _marks.series_colors(color, 1)[0]]
    if isinstance(color, Mapping):
        return [color[n] for n in names]
    if color is None:
        return [theme.ink_color(i) for i in range(len(names))]
    return list(_marks.series_colors(color, len(names)))


def _pairs(xs, ys, x_log: bool, y_log: bool) -> list[tuple[float, float]]:
    return [(float(a), float(b)) for a, b in zip(xs, ys)
            if _finite(a) and _finite(b) and (not x_log or float(a) > 0)
            and (not y_log or float(b) > 0)]


# -- the distributions -------------------------------------------------------

def _heights(kind: str, samples, domain, is_log: bool, bins: int, pooled):
    """Per-group `(positions, heights)` in data units of the variable; for
    "hist" the positions are edges, for "kde" a grid."""
    out = []
    if kind == "hist":
        edges = _edges(domain, bins, is_log, pooled)
        bins = len(edges) - 1           # round edges give about `bins`, not exactly
        for sample in samples:
            counts = [0] * bins
            for v in sample:
                if not _finite(v) or (is_log and float(v) <= 0):
                    continue
                v = float(v)
                if v < edges[0] or v > edges[-1]:
                    continue
                k = min(bins - 1, _bisect(edges, v))
                counts[k] += 1
            out.append((edges, counts))
        return out
    for sample in samples:
        clean = [float(v) for v in sample if _finite(v) and (not is_log or float(v) > 0)]
        if len(clean) < 2:
            out.append(((), ()))
            continue
        if is_log:
            grid, dens = kde_curve([math.log10(v) for v in clean],
                                   low=math.log10(domain[0]),
                                   high=math.log10(domain[1]),
                                   weights_total=len(clean))
            out.append((tuple(10.0 ** g for g in grid), dens))
        else:
            grid, dens = kde_curve(clean, low=domain[0], high=domain[1],
                                   weights_total=len(clean))
            out.append((grid, dens))
    return out


def _bisect(edges, v) -> int:
    lo, hi = 0, len(edges) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if edges[mid] <= v:
            lo = mid
        else:
            hi = mid
    return lo


def _distribution(panel: Panel, kind: str, curves, inks, *, orient: str,
                  peak: float, several: bool, **style) -> Diagram:
    """Histograms or density curves in page space, their tallest reaching
    `_DIAG_FILL` of the panel across the value axis."""
    theme = active_theme()
    position = panel.x if orient == "v" else panel.y
    value = panel.y if orient == "v" else panel.x
    r0, r1 = value.range
    base = r0

    def at(p, h):
        v = base + (r1 - r0) * _DIAG_FILL * (h / peak if peak > 0 else 0.0)
        return _marks._point(orient, position.map(p), v)

    items = []
    for (where, heights), ink in zip(curves, inks):
        if not heights:
            continue
        if kind == "hist":
            pts = [at(where[0], 0.0)]
            for i, h in enumerate(heights):
                pts.append(at(where[i], h))
                pts.append(at(where[i + 1], h))
            pts.append(at(where[-1], 0.0))
        else:
            pts = [at(where[0], 0.0)] + [at(p, h) for p, h in zip(where, heights)] \
                + [at(where[-1], 0.0)]
        if several:
            fill = {"fill": ink, "fill_opacity": _GROUP_OPACITY, "stroke": "none"}
        else:
            fill = {"fill": mix(ink, theme.paper, _marks._SINGLE_TINT), "stroke": "none"}
        items.append(polygon(pts, kind=MARK_KIND, **fill))
        line = {"stroke": ink, "stroke_width": theme.stroke,
                "stroke_linejoin": "miter" if kind == "hist" else "round"}
        line.update(style)
        items.append(draw_path(pts if kind == "hist" else pts[1:-1], closed=False,
                               filled=False, kind=MARK_LINE_KIND, **line))
    return draw_place(items, origin=(0, 0), kind="marginal")


def _peak(curves) -> float:
    return max((max(h) for _, h in curves if h), default=0.0)


# -- the joint panels --------------------------------------------------------

def _joint(panel: Panel, kind: str, groups_xy, inks, names, *, size, bins,
           several: bool, **style) -> None:
    theme = active_theme()
    if kind == "scatter":
        from .strip import _dots
        dot = {"size": _dots(theme, size)}
        for pts, ink, name in zip(groups_xy, inks, names):
            if pts:
                panel.scatter(pts, color=ink if several else mix(ink, theme.paper, 0.2),
                              name=name, **dot, **style)
    elif kind == "regression":
        dot = {} if size is None else {"size": size}
        for pts, ink, name in zip(groups_xy, inks, names):
            if len(pts) >= 3:
                panel.regression(pts, color=ink, name=name, **dot, **style)
    elif kind == "kde2d":
        for pts, ink, name in zip(groups_xy, inks, names):
            if len(pts) >= 3:
                if several:
                    panel.kde2d(pts, levels=(0.5, 0.8, 0.95), color=ink, name=name,
                                **style)
                else:
                    panel.kde2d(pts, levels=5, fill=True, **style)
    elif kind == "hexbin":
        pooled = [p for pts in groups_xy for p in pts]
        panel.hexbin(pooled, gridsize=max(8, bins), **style)
    elif kind == "hist2d":
        pooled = [p for pts in groups_xy for p in pts]
        panel.hist2d(pooled, bins=bins, **style)
    else:
        raise DiagramError(f"pair panels draw one of {', '.join(PAIR_KINDS)}, not {kind!r}")


def _blank(panel: Panel) -> Panel:
    """Hold an empty cell's place in the grid: a phantom over its plot area,
    which occupies the space and draws nothing."""
    return panel.under(Diagram(prim=PhantomPrim(panel.area), kind="blank"))


def _check(kind, allowed, what):
    if kind is not None and kind not in allowed:
        raise DiagramError(f"{what} is one of {', '.join(allowed)} or None, not {kind!r}")


# -- pairplot ----------------------------------------------------------------

def pairplot(data: Mapping[str, Sequence[float]], *, vars: Sequence[str] | None = None,
             groups: Sequence | None = None, cell: float | str = 26,
             diag: str | None = "auto", lower: str | None = "scatter",
             upper: str | None = "scatter", corner: bool = False,
             bins: int = 12, log: Sequence[str] = (),
             labels: Mapping[str, str] | None = None, color=None, size=None,
             legend: bool = True, gap: float | str | None = None,
             count: int = 4, **style) -> Diagram:
    """Every pair of variables against each other, in one aligned grid.

        inklet.pairplot({"length": length, "width": width, "mass": mass},
                        groups=species, lower="kde2d", diag="kde")

    `data` maps a variable's name to its values, one per observation, all
    the same length; `vars=` picks and orders them. Panel `(i, j)` draws
    variable `j` along x and `i` up y, so each column shares its x scale
    and each row its y scale; only the bottom row and the left column
    write numbers and names (`labels=` renames them). Domains are rounded
    out from the data; variables named in `log=` get decade-bounded log
    axes.

    The diagonal shows each variable's distribution: `diag="hist"` with
    `bins` bins, `"kde"` (Scott's rule) or `None`; the default `"auto"` is
    a histogram for one group and densities for several, which overlap
    more legibly. The panels below it
    draw `lower` and those above `upper`: `"scatter"`, `"kde2d"` (density
    contours), `"hexbin"`, `"hist2d"` or `"regression"` (a least-squares
    line with its 95% band), or `None` to leave the panel empty.
    `corner=True` drops the upper triangle.

    `groups=` is one label per observation: each group is drawn in its own
    colour (the theme's ink palette, or `color=` as a sequence or a mapping
    of label to colour) and, with `legend=True`, keyed in the top-right
    corner. Hexbin and 2D-histogram panels pool the groups. `cell` is each
    plot area's side in mm, `size` the dot diameter, `count` about how many
    ticks per axis, `gap` the space between panels. Other keywords style the
    marks of the off-diagonal panels.
    """
    if diag == "auto":
        diag = "kde" if groups is not None else "hist"
    _check(diag, MARGINAL_KINDS, "pairplot diag")
    _check(lower, PAIR_KINDS, "pairplot lower")
    _check(upper, PAIR_KINDS, "pairplot upper")
    if not isinstance(data, Mapping) or not data:
        raise DiagramError("pairplot data is a mapping of variable name to values")
    names_v = list(data) if vars is None else list(vars)
    for v in names_v:
        if v not in data:
            raise DiagramError(f"pairplot has no variable {v!r}")
    columns = [list(data[v]) for v in names_v]
    if len({len(c) for c in columns}) != 1:
        raise DiagramError("pairplot variables need one value per observation each")
    unknown = [v for v in log if v not in names_v]
    if unknown:
        raise DiagramError(f"pairplot log= names unknown variables {unknown}")
    labels = dict(labels or {})
    theme = active_theme()
    n = len(names_v)
    side = mm(cell)
    logs = [v in log for v in names_v]
    domains = [_domain(c, lg, v) for c, lg, v in zip(columns, logs, names_v)]
    group_names, split = _split(columns, groups)
    several = group_names != [None]
    inks = _group_colors(group_names, color)
    keys = [None] * len(group_names)

    panels: list[Panel] = []
    for i in range(n):
        for j in range(n):
            p = make_panel(side, side, x=_scale(domains[j], logs[j]),
                      y=_scale(domains[i], logs[i]))
            panels.append(p)
            kind = diag if i == j else (lower if i > j else upper)
            if i < j and corner:
                _blank(p)
                continue
            if i == j:
                if kind is not None:
                    curves = _heights(kind, [s[i] for s in split], domains[i],
                                      logs[i], bins, columns[i])
                    p.draw(_distribution(p, kind, curves, inks, orient="v",
                                         peak=_peak(curves), several=several),
                           clip=True)
            elif kind is not None:
                xy = [_pairs(s[j], s[i], logs[j], logs[i]) for s in split]
                _joint(p, kind, xy, inks, keys, size=size, bins=bins,
                       several=several, **style)
            bottom = i == n - 1
            left = j == 0
            hide_y = corner and i == 0 and j == 0
            p.axis("bottom", labels=bottom, count=count,
                   label=labels.get(names_v[j], names_v[j]) if bottom else None)
            p.axis("left", labels=left and not hide_y, count=count,
                   label=(labels.get(names_v[i], names_v[i])
                          if left and not hide_y else None))
    if several and legend:
        entries = list(zip(group_names, inks))
        panels[n - 1].legend(entries=entries, corner="ne" if corner else None,
                             side=None if corner else "right",
                             plate=False if corner else None)
    return facets(panels, cols=n, axes=False,
                  gap=theme.gap("s") if gap is None else gap)


# -- jointplot ---------------------------------------------------------------

def jointplot(points: Sequence[Sequence[float]], *, kind: str = "scatter",
              marginal: str = "hist", groups: Sequence | None = None,
              width: float | str = 50, ratio: float = 4.0,
              x=None, y=None, x_log: bool = False, y_log: bool = False,
              bins: int = 20, x_label: str | None = None,
              y_label: str | None = None, color=None, size=None,
              legend: bool = True, gap: float | str | None = None,
              count: int = 5, **style) -> Diagram:
    """One pair of variables with both marginal distributions.

        inklet.jointplot(points, kind="hexbin", x_label="x", y_label="y")

    The main panel is `width` mm square and draws `kind`: `"scatter"`,
    `"kde2d"`, `"hexbin"`, `"hist2d"` or `"regression"`. Along its top
    and right edges, panels `width / ratio` deep show the distribution of
    x and of y -- `marginal="hist"` with `bins` bins, or `"kde"` -- on
    exactly the main panel's scales. `x=` and `y=` fix the domains
    (default: rounded out from the data); `x_log` and `y_log` make them
    logarithmic. The margins have no count axis, since only their shape is
    read.

    `groups=` is one label per point, drawn in the ink palette or `color=`
    (a sequence or a mapping) and keyed at the top right with `legend=True`;
    hexbin and 2D-histogram panels pool the groups. `size` is the dot
    diameter; other keywords style the main panel's marks.
    """
    _check(kind, PAIR_KINDS, "jointplot kind")
    _check(marginal, MARGINAL_KINDS, "jointplot marginal")
    if not ratio > 1:
        raise DiagramError(f"jointplot ratio must exceed 1, got {ratio!r}")
    pts = [tuple(p) for p in points]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    theme = active_theme()
    x_dom = tuple(x) if x is not None else _domain(xs, x_log, "x")
    y_dom = tuple(y) if y is not None else _domain(ys, y_log, "y")
    main_side = mm(width)
    depth = main_side / ratio
    group_names, split = _split([xs, ys], groups)
    several = group_names != [None]
    inks = _group_colors(group_names, color)

    main = make_panel(main_side, main_side, x=_scale(x_dom, x_log), y=_scale(y_dom, y_log))
    xy = [_pairs(s[0], s[1], x_log, y_log) for s in split]
    _joint(main, kind, xy, inks, [None] * len(inks), size=size, bins=bins,
           several=several, **style)
    main.axis("bottom", label=x_label, count=count)
    main.axis("left", label=y_label, count=count)

    top = make_panel(main_side, depth, x=_scale(x_dom, x_log), y=linear((0.0, 1.0)))
    right = make_panel(depth, main_side, x=linear((0.0, 1.0)), y=_scale(y_dom, y_log))
    for panel, which, dom, lg, orient in ((top, 0, x_dom, x_log, "v"),
                                          (right, 1, y_dom, y_log, "h")):
        values = [s[which] for s in split]
        pooled = xs if which == 0 else ys
        curves = _heights(marginal, values, dom, lg, bins, pooled)
        panel.draw(_distribution(panel, marginal, curves, inks, orient=orient,
                                 peak=_peak(curves), several=several), clip=True)
    corner = _blank(make_panel(depth, depth, x=linear((0.0, 1.0)), y=linear((0.0, 1.0))))
    if several and legend:
        corner.legend(entries=list(zip(group_names, inks)), corner="sw", plate=False)
    return facets([top, corner, main, right], cols=2, axes=False,
                  gap=theme.gap("xs") if gap is None else gap)
