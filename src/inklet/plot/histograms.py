"""Histogram variants: outlines, filled outlines, cumulative counts and
several groups over shared bins.

`Panel.hist` draws touching bars by default and keeps doing so byte for byte.
It hands off to `hist_layer` here when asked for anything else:

- `histtype="step"` draws the outline of the bars as one unfilled line;
  `"stepfilled"` fills that outline and draws no edges between bins. Both
  are what overlaid histograms need, since touching bars of two groups hide
  each other.
- `cumulative=True` draws the running total of the bins: counts up to each
  bin's upper edge, or with `density=True` the fraction of observations.
- a mapping of group name to values draws one histogram per group over the
  *same* bin edges, taken from all the groups together, each in its own
  colour and named for `legend()`.
"""

from __future__ import annotations

from typing import Mapping

from ..core import Diagram, DiagramError
from ..draw.coords import active_theme
from ..draw.path import path as draw_path, polygon
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND
from ..themes.color import mix
from . import marks as _marks
from .statistics import _bin_edges, histogram

__all__ = ["HISTTYPES", "hist_layer", "cumulate"]

#: Accepted values of `Panel.hist(histtype=)`.
HISTTYPES = ("bar", "step", "stepfilled")

#: The fill of an overlaid group's filled outline, as an opacity.
_GROUP_FILL_OPACITY = 0.3


def cumulate(edges, heights, density: bool) -> tuple[float, ...]:
    """Running totals of bin heights; for densities, of heights times widths."""
    out, total = [], 0.0
    for i, h in enumerate(heights):
        total += h * (edges[i + 1] - edges[i]) if density else h
        out.append(total)
    return tuple(out)


def _groups(values) -> tuple[list, list[list[float]]]:
    if isinstance(values, Mapping):
        return ([str(k) for k in values],
                [[float(v) for v in values[k]] for k in values])
    return [None], [[float(v) for v in values]]


def _outline(panel, edges, heights, baseline: float, orient: str,
             closed: bool) -> list:
    position, value = _marks._axes_of(panel, orient)
    base = value.map(baseline)
    pts = [_marks._point(orient, position.map(edges[0]), base)]
    for i, h in enumerate(heights):
        top = value.map(baseline + h)
        pts.append(_marks._point(orient, position.map(edges[i]), top))
        pts.append(_marks._point(orient, position.map(edges[i + 1]), top))
    pts.append(_marks._point(orient, position.map(edges[-1]), base))
    return pts


def hist_layer(panel, values, bins=10, *, range=None, density: bool = False,
               cumulative: bool = False, histtype: str | None = None,
               baseline: float = 0.0, orient: str = "v", colors=None,
               **style) -> tuple[Diagram, list]:
    """The histograms `Panel.hist` hands off. Returns `(node, [(name, key)])`
    where each key is `(form, color, fill)` for the legend."""
    names, groups = _groups(values)
    several = len(groups) > 1 or names[0] is not None
    if histtype is None:
        histtype = "stepfilled" if several else "bar"
    if histtype not in HISTTYPES:
        raise DiagramError(
            f'hist histtype is "bar", "step" or "stepfilled", not {histtype!r}')
    pooled = [v for g in groups for v in g]
    if not pooled:
        raise DiagramError("a histogram needs at least one value")
    if isinstance(bins, int):
        if range is not None:
            lo, hi = float(range[0]), float(range[1])
        else:
            lo, hi = min(pooled), max(pooled)
        edges = _bin_edges(bins, lo, hi)
    else:
        edges = [float(e) for e in bins]
    theme = active_theme()
    if colors is None:
        inks = ([theme.ink] if len(groups) == 1
                else [theme.ink_color(i) for i in _range(len(groups))])
    else:
        inks = list(_marks.series_colors(colors, len(groups)))
    items: list = []
    keys: list = []
    for name, sample, ink in zip(names, groups, inks):
        if not sample:
            continue
        _, heights = histogram(sample, edges, range=range, density=density)
        if cumulative:
            heights = cumulate(edges, heights, density)
        if histtype == "bar":
            fill = ink if several else _marks.series_colors(None, 1)[0]
            paint = dict(style)
            if several:
                paint.setdefault("fill_opacity", 0.5)
                paint.setdefault("stroke", "none")
            items.append(_marks.bins_node(panel, edges, heights, baseline=baseline,
                                          orient=orient, colors=paint.pop("fill", fill),
                                          **paint))
            keys.append((name, ("area", None, fill)))
            continue
        pts = _outline(panel, edges, heights, baseline, orient, histtype == "stepfilled")
        line = {"stroke": ink, "stroke_width": theme.stroke,
                "stroke_linejoin": "miter"}
        if histtype == "stepfilled":
            fill = (mix(ink, theme.paper, _marks._SINGLE_TINT) if not several
                    else ink)
            paint = {"fill": fill, "stroke": "none"}
            if several:
                paint["fill_opacity"] = _GROUP_FILL_OPACITY
            if "fill" in style:
                paint["fill"] = style["fill"]
            items.append(polygon(pts, kind=MARK_KIND, **paint))
            keys.append((name, ("area", ink, paint["fill"] if not several
                                else mix(ink, theme.paper, 1 - _GROUP_FILL_OPACITY))))
        else:
            keys.append((name, ("line", ink, None)))
        line.update({k: v for k, v in style.items() if k != "fill"})
        if cumulative:
            pts = pts[:-1]      # a running total ends at its top, not back at zero
        items.append(draw_path(pts, closed=False, filled=False,
                               kind=MARK_LINE_KIND, **line))
    if not items:
        raise DiagramError("hist() had nothing to draw")
    node = draw_place(items, origin=(0, 0), kind="hist")
    node.notes["hist"] = {"edges": tuple(edges), "histtype": histtype,
                          "cumulative": cumulative, "density": density,
                          "groups": names if several else None}
    return node, keys


_range = range
