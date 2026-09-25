"""Parallel coordinates: one vertical axis per variable, one line per record.

Every variable gets its own axis, spread evenly across the panel (the
categories of a band x scale, or the positions given), and its own linear
scale over the full height of the plot area. A record is a polyline
through its value on each axis. Crossing lines between two neighbouring
axes show a negative relation; parallel ones a positive relation.

Each axis is a real `plot.axis`, with round ticks over its range, so the
values can be read back. Ranges default to the data's extent widened to
round numbers; pass `ranges=` to fix them, and reverse a pair to flip an
axis.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, Vec2
from ..draw.coords import active_theme, as_drawn
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND
from ..themes.color import mix
from .axis import axis as make_axis
from .label_spread import label_text
from .scale import Band, linear, nice_bounds

__all__ = ["parallel", "parallel_ranges"]


def _records(rows, count: int) -> list[list[float | None]]:
    out = []
    for r, row in enumerate(rows):
        values = list(row.values()) if isinstance(row, Mapping) else list(row)
        if len(values) != count:
            raise DiagramError(
                f"parallel record {r} has {len(values)} values for {count} axes")
        clean = []
        for v in values:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                clean.append(None)
            else:
                number = float(v)
                if not math.isfinite(number):
                    raise DiagramError(f"parallel record {r} has a non-finite value {v!r}")
                clean.append(number)
        out.append(clean)
    if not out:
        raise DiagramError("parallel() was given no records")
    return out


def parallel_ranges(rows, count: int | None = None) -> list[tuple[float, float]]:
    """Each axis' default range: the data's extent, widened to round numbers."""
    rows = list(rows)
    count = len(rows[0]) if count is None else count
    records = _records(rows, count)
    out = []
    for d in range(count):
        present = [r[d] for r in records if r[d] is not None]
        if not present:
            out.append((0.0, 1.0))
            continue
        lo, hi = min(present), max(present)
        if hi == lo:
            lo, hi = lo - 0.5, hi + 0.5
        out.append(nice_bounds(lo, hi, 4))
    return out


def parallel(panel, rows, *, dimensions: Sequence | None = None, ranges=None,
             color=None, groups: Sequence | None = None, count: int = 4,
             format=None, labels: bool = True,
             **style) -> tuple[Diagram, dict]:
    """Draw parallel coordinates on `panel`. See `Panel.parallel`.

    Returns `(node, colour by group)` (empty without `groups`).
    """
    if dimensions is None:
        if not isinstance(panel.x, Band):
            raise DiagramError(
                "parallel() needs a band x scale naming the variables, or dimensions=")
        dimensions = panel.x.domain
    dimensions = list(dimensions)
    records = _records(rows, len(dimensions))
    if ranges is None:
        spans = parallel_ranges(records, len(dimensions))
    elif isinstance(ranges, Mapping):
        default = parallel_ranges(records, len(dimensions))
        spans = [tuple(ranges.get(d, default[i])) for i, d in enumerate(dimensions)]
    else:
        spans = [tuple(r) for r in ranges]
        if len(spans) != len(dimensions):
            raise DiagramError(f"parallel ranges= has {len(spans)} ranges for "
                               f"{len(dimensions)} axes")
    theme = active_theme()
    area = panel.area
    scales = [linear((float(lo), float(hi)), (area.y1, area.y0)) for lo, hi in spans]
    xs = [panel.x.map(d) for d in dimensions]
    palette: dict = {}
    if groups is not None:
        groups = list(groups)
        if len(groups) != len(records):
            raise DiagramError(f"parallel groups= has {len(groups)} labels for "
                               f"{len(records)} records")
        order = list(dict.fromkeys(groups))
        if isinstance(color, Mapping):
            palette = {g: color[g] for g in order}
        elif color is None or isinstance(color, str):
            palette = {g: theme.color(i + 1) for i, g in enumerate(order)}
        else:
            given = list(color)
            palette = {g: given[i % len(given)] for i, g in enumerate(order)}
        inks = [palette[g] for g in groups]
    elif color is None:
        inks = [mix(theme.ink, theme.paper, 0.35)] * len(records)
    elif isinstance(color, str):
        inks = [color] * len(records)
    else:
        inks = list(color)
        if len(inks) != len(records):
            raise DiagramError("parallel color= is one colour or one per record")
    line = {"stroke_width": theme.stroke, "stroke_linejoin": "round"}
    line.update({k: style.pop(k) for k in ("stroke_width", "stroke_dash", "stroke_opacity",
                                           "opacity") if k in style})
    lines = []
    for record, ink in zip(records, inks):
        run: list[Vec2] = []
        for x, scale, v in zip(xs, scales, record):
            if v is None:
                if len(run) >= 2:
                    lines.append(polyline(run, kind=MARK_LINE_KIND, stroke=ink, **line))
                run = []
                continue
            run.append(Vec2(x, scale.map(v)))
        if len(run) >= 2:
            lines.append(polyline(run, kind=MARK_LINE_KIND, stroke=ink, **line))
    axes = []
    formats = format if isinstance(format, (list, tuple)) else [format] * len(dimensions)
    for x, scale, fmt in zip(xs, scales, formats):
        node = as_drawn(make_axis(scale, side="left", count=count, format=fmt,
                                   halo=theme.stroke * 2.4))
        axes.append(node.translated(x, 0.0))
    names = []
    if labels:
        for x, d in zip(xs, dimensions):
            node = label_text(str(d), theme.font_size)
            names.append(draw_place([(Vec2(x, area.y1 + theme.gap("s")), node)],
                                    anchor="n", origin=(0, 0)))
    node = draw_place(lines + axes + names, **style)
    node.notes["parallel"] = {"dimensions": tuple(dimensions),
                              "ranges": tuple(tuple(s) for s in spans),
                              "records": len(records)}
    return node, palette
