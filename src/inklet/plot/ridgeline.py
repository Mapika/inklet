"""Ridgeline plots: one kernel density per category, stacked and overlapping.

Categories sit on the panel's y band scale and the values on its continuous
x scale, which every ridge shares. Each ridge's baseline is the lower edge of
its category's step, halfway to the category below, so a ridge of height one
step fills its own row and the category's tick label is level with its
middle. `overlap` is the height of the tallest ridge in steps; above 1 a
ridge rises into the rows above it.

Ridges are drawn from the top of the page down, each filled with an opaque
colour, so a lower ridge covers the one behind it. The density is evaluated
over the whole x domain and so runs flat to both ends of the axis. With
`scale="shared"` (default) all ridges use one height scale, so their areas
compare; `scale="each"` scales every ridge to the same peak height.

With `fit=True` (default) every ridge is scaled down by one common factor
when needed so that none rises above the plot area; the node's `ridgeline`
note records the overlap actually drawn under `overlap`. With `fit=False`
the top ridges can rise above the area, by the millimetres recorded under
`above`; that ink is still part of the panel's measured box.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import Diagram, DiagramError, Vec2
from ..draw.coords import active_theme
from ..draw.path import polygon, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND
from . import marks as _marks
from .scale import Band
from .statistics import _bandwidth, kde

__all__ = ["ridgeline", "RIDGE_SCALES"]

#: Accepted values of `ridgeline(scale=)`.
RIDGE_SCALES = ("shared", "each")


def _numeric_domain(scale) -> tuple[float, float]:
    domain = getattr(scale, "domain", None)
    try:
        low, high = float(domain[0]), float(domain[1])
    except (TypeError, ValueError, IndexError):
        raise DiagramError("ridgeline() needs a continuous x scale") from None
    return min(low, high), max(low, high)


def ridgeline(panel, groups, *, at=None, overlap: float = 1.5,
              bandwidth: float | None = None, samples: int = 96,
              scale: str = "shared", fit: bool = True, colors=None,
              **style) -> tuple[Diagram, tuple[str, ...], dict]:
    """Overlapping densities, one per category. See `Panel.ridgeline`.

    Returns `(node, fills, note)`.
    """
    if not isinstance(panel.y, Band):
        raise DiagramError("ridgeline() needs a band (categorical) y scale")
    if scale not in RIDGE_SCALES:
        raise DiagramError(
            f"ridgeline scale is one of {', '.join(RIDGE_SCALES)}, not {scale!r}")
    if overlap <= 0:
        raise DiagramError(f"ridgeline overlap must be positive, got {overlap}")
    if samples < 8:
        raise DiagramError(f"a ridgeline needs at least 8 samples, got {samples}")
    places, data = _marks._groups(panel, groups, at, "h")
    low, high = _numeric_domain(panel.x)
    theme = active_theme()
    given = style.pop("fill", None) if colors is None else colors
    fills = (_marks.series_colors(given, len(data)) if given is not None
             else _marks.series_colors(None, 1) * len(data))
    step = abs(panel.y.step)
    grid = [low + (high - low) * k / (samples - 1) for k in range(samples)]
    curves: list[tuple[float, ...] | None] = []
    for sample in data:
        clean = [v for v in sample if not math.isnan(v)]
        if len(clean) < 2:
            curves.append(None)
            continue
        width = _bandwidth(clean) if bandwidth is None else float(bandwidth)
        curves.append(kde(clean, grid, bandwidth=width) if width > 0 else None)
    peaks = [max(c) for c in curves if c is not None and max(c) > 0]
    if not peaks:
        raise DiagramError("ridgeline() had nothing to draw")
    tallest = max(peaks)
    line = {"stroke": theme.ink, "stroke_width": theme.stroke,
            "stroke_linejoin": "round"}
    line.update(style)
    xs = [panel.x.map(g) for g in grid]
    rows = []
    for index, (where, curve) in enumerate(zip(places, curves)):
        if curve is None or max(curve) <= 0:
            continue
        base = panel.y.map(where) + step / 2
        peak = tallest if scale == "shared" else max(curve)
        rows.append((base, index, [d * overlap * step / peak for d in curve]))
    # One factor for every ridge, so none rises above the plot area and
    # the heights keep their proportions.
    area_top = -panel.height / 2
    factor = 1.0
    if fit:
        for base, _, heights in rows:
            room = base - area_top
            if max(heights) > room > 0:
                factor = min(factor, room / max(heights))
    rows = [(base, index, [(x, base - h * factor) for x, h in zip(xs, heights)])
            for base, index, heights in rows]
    # The ridge highest on the page first, so each lower ridge covers it.
    rows.sort(key=lambda row: row[0])
    items: list = []
    drawn: list[int] = []
    for base, index, top in rows:
        outline = [Vec2(x, y) for x, y in top]
        items.append(polygon(outline + [Vec2(outline[-1].x, base),
                                        Vec2(outline[0].x, base)],
                             kind=MARK_KIND, fill=fills[index], stroke="none"))
        items.append(polyline(outline, kind=MARK_LINE_KIND, **line))
        drawn.append(index)
    node = draw_place(items, origin=(0, 0), kind="ridgeline")
    highest = min(min(y for _, y in top) for _, _, top in rows)
    note = {"drawn": sorted(drawn),
            "empty": [i for i in range(len(data)) if i not in drawn],
            "overlap": overlap * factor,
            "above": max(0.0, area_top - highest)}
    node.notes["ridgeline"] = note
    return node, tuple(fills), note
