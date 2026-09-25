"""Slope charts and bump charts: series compared across a few time points.

A slope chart joins each series' values at two (or a few) time points with
a straight line, and writes the series name and its value at the ends, so
the reader compares slopes and reads the numbers off the labels instead of
an axis. A bump chart draws the *rank* of each series at each time point,
rank 1 at the top, joined by S-shaped curves, which shows reordering over
time and hides the size of the differences.

End labels are moved apart along the value axis just enough not to overlap
(`plot.label_spread.spread`); the line keeps its exact end point.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, Vec2, mm, pt
from ..draw.coords import active_theme
from ..draw.path import path as draw_path, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND, marker as make_marker
from ..themes.color import mix
from .label_spread import label_text, on_fill, spread
from .scale import Band

__all__ = ["slope", "bump", "ranks", "SLOPE_LABELS"]

SLOPE_LABELS = ("both", "left", "right", "none")

#: Series not named in `highlight=`, as a blend of the ink towards paper.
_BACKGROUND_TINT = 0.72

#: Dot diameter on a slope chart, as a fraction of the type size.
_DOT_OF_TYPE = 0.55

#: Bump-chart dots are larger: each carries a rank, and the eye follows dots.
_BUMP_DOT_OF_TYPE = 0.75


def _series(values, what: str) -> tuple[list[str], list[list[float | None]]]:
    if not isinstance(values, Mapping):
        raise DiagramError(f"{what}() takes a mapping of series name to values")
    if not values:
        raise DiagramError(f"{what}() was given no series")
    names = [str(k) for k in values]
    rows = []
    for name, row in values.items():
        out = []
        for v in row:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                out.append(None)
            else:
                out.append(float(v))
        rows.append(out)
    if len({len(r) for r in rows}) != 1:
        raise DiagramError(f"every {what} series needs the same number of values")
    if len(rows[0]) < 2:
        raise DiagramError(f"{what}() needs at least two time points")
    return names, rows


def _positions(panel, at, count: int, what: str) -> list[float]:
    if at is None:
        if not isinstance(panel.x, Band):
            raise DiagramError(
                f"{what}() needs at= positions, or a band x scale naming the time points")
        at = panel.x.domain
    at = list(at)
    if len(at) != count:
        raise DiagramError(f"{what}() has {count} time points but {len(at)} positions")
    return [panel.x.map(a) for a in at]


def _colors(names: Sequence[str], color, highlight, theme) -> list[str]:
    """One colour per series. Highlighting greys out every other series and
    gives the highlighted ones the palette in order."""
    count = len(names)
    chosen = None
    if highlight is not None:
        chosen = {str(h) for h in ([highlight] if isinstance(highlight, str) else highlight)}
        unknown = chosen - set(names)
        if unknown:
            raise DiagramError(f"highlight names unknown series {sorted(unknown)}")
    if color is None:
        # Palette entry 0 is the ink in most themes; series start at 1.
        if chosen is not None:
            order = iter(range(1, count + 1))
            return [theme.color(next(order)) if n in chosen
                    else mix(theme.ink, theme.paper, _BACKGROUND_TINT) for n in names]
        return [theme.color(i + 1) for i in range(count)]
    if isinstance(color, str):
        colors = [color] * count
    elif isinstance(color, Mapping):
        colors = [color.get(n, theme.ink) for n in names]
    else:
        given = list(color)
        if not given:
            raise DiagramError("color= was given no colours")
        colors = [given[i % len(given)] for i in range(count)]
    if chosen is not None:
        grey = mix(theme.ink, theme.paper, _BACKGROUND_TINT)
        colors = [c if n in chosen else grey for n, c in zip(names, colors)]
    return colors


def _written(value: float, format) -> str:
    if format is None:
        return f"{value:g}"
    if callable(format):
        return str(format(value))
    return format.format(value)


def _end_labels(panel, items, side: str, gap: float) -> list:
    """Labels beside line ends, spread apart along y. `items` is a list of
    `(x, y, text, colour)` in panel millimetres."""
    if not items:
        return []
    theme = active_theme()
    from ..themes import readable
    nodes = [label_text(text, text_fill=readable(color, theme.paper, 4.5))
             for _, _, text, color in items]
    heights = [n.bbox.height for n in nodes]
    ys = spread([y for _, y, _, _ in items], heights, gap=0.15,
                lo=panel.area.y0 - heights[0], hi=panel.area.y1 + heights[0])
    out = []
    for (x, _, _, _), y, node in zip(items, ys, nodes):
        anchor = "e" if side == "left" else "w"
        out.append((Vec2(x - gap if side == "left" else x + gap, y), node, anchor))
    return out


def slope(panel, values, *, at=None, labels: str = "both", format=None,
          color=None, highlight=None, size: float | str | None = None,
          names: bool = True, **style) -> tuple[Diagram, list[str]]:
    """Draw a slope chart on `panel`. See `Panel.slope`.

    Returns `(node, colours)`, one colour per series.
    """
    if labels not in SLOPE_LABELS:
        raise DiagramError(f"slope labels= is one of {SLOPE_LABELS}, not {labels!r}")
    series, rows = _series(values, "slope")
    xs = _positions(panel, at, len(rows[0]), "slope")
    theme = active_theme()
    colors = _colors(series, color, highlight, theme)
    dot = _DOT_OF_TYPE * theme.font_size if size is None else mm(size)
    width = style.pop("stroke_width", theme.stroke * 2)
    lines, dots, left, right = [], [], [], []
    # Highlighted (coloured) series are drawn last, over the grey ones.
    grey = mix(theme.ink, theme.paper, _BACKGROUND_TINT)
    order = sorted(range(len(series)),
                   key=lambda s: (highlight is not None and colors[s] != grey, s))
    for s in order:
        row = rows[s]
        pts = [Vec2(x, panel.y.map(v)) for x, v in zip(xs, row) if v is not None]
        if len(pts) >= 2:
            lines.append(polyline(pts, kind=MARK_LINE_KIND, stroke=colors[s],
                                  stroke_width=width, **style))
        for p in pts:
            dots.append((p, make_marker("circle", dot, fill=colors[s],
                                        stroke=theme.paper,
                                        stroke_width=theme.hairline)))
        first = next((i for i, v in enumerate(row) if v is not None), None)
        last = next((i for i in range(len(row) - 1, -1, -1) if row[i] is not None), None)
        if first is None:
            continue
        name = series[s]
        if labels in ("both", "left"):
            text = _written(row[first], format)
            left.append((xs[first], panel.y.map(row[first]),
                         f"{name}  {text}" if names else text, colors[s]))
        if labels in ("both", "right"):
            text = _written(row[last], format)
            right.append((xs[last], panel.y.map(row[last]),
                          f"{text}  {name}" if names else text, colors[s]))
    if not dots:
        raise DiagramError("slope() had nothing to draw: every value is missing")
    gap = dot / 2 + theme.gap("xs")
    written = []
    for side, items in (("left", left), ("right", right)):
        for point, node, anchor in _end_labels(panel, items, side, gap):
            written.append(draw_place([(point, node)], anchor=anchor, origin=(0, 0)))
    node = draw_place(lines + dots + written)
    node.notes["slope"] = {"series": tuple(series), "colors": tuple(colors)}
    return node, colors


def ranks(values, *, descending: bool = True) -> dict[str, list[int | None]]:
    """Rank the series at each time point: 1 for the largest value (or the
    smallest with `descending=False`). Ties keep the input order; a missing
    value has no rank."""
    names, rows = _series(values, "ranks")
    out: dict[str, list[int | None]] = {n: [] for n in names}
    for t in range(len(rows[0])):
        present = [(rows[s][t], s) for s in range(len(names)) if rows[s][t] is not None]
        present.sort(key=lambda p: ((-p[0] if descending else p[0]), p[1]))
        placed = {s: r + 1 for r, (_, s) in enumerate(present)}
        for s, name in enumerate(names):
            out[name].append(placed.get(s))
    return out


def _s_curve(points: Sequence[Vec2]) -> list[tuple[Vec2, Vec2, Vec2, Vec2]]:
    """Cubics with horizontal tangents at every point: the bump-chart S."""
    chain = []
    for a, b in zip(points, points[1:]):
        half = (b.x - a.x) / 2
        chain.append((a, Vec2(a.x + half, a.y), Vec2(b.x - half, b.y), b))
    return chain


def bump(panel, values, *, at=None, ranked: bool = False, labels: str = "both",
         color=None, highlight=None, size: float | str | None = None,
         numbers: bool = False, **style) -> tuple[Diagram, list[str], dict]:
    """Draw a bump chart on `panel`. See `Panel.bump`.

    Returns `(node, colours, ranks)`.
    """
    if labels not in SLOPE_LABELS:
        raise DiagramError(f"bump labels= is one of {SLOPE_LABELS}, not {labels!r}")
    table = values if ranked else ranks(values)
    series, rows = _series(table, "bump")
    xs = _positions(panel, at, len(rows[0]), "bump")
    theme = active_theme()
    colors = _colors(series, color, highlight, theme)
    dot = _BUMP_DOT_OF_TYPE * theme.font_size if size is None else mm(size)
    # A rank written in a dot is set no smaller than 5 pt, and the dot grows
    # to hold it.
    number_size = max(pt(5.5), 0.6 * dot)
    if numbers and size is None:
        dot = max(dot, 1.45 * number_size)
    width = style.pop("stroke_width", theme.thick * 1.6)
    grey = mix(theme.ink, theme.paper, _BACKGROUND_TINT)
    order = sorted(range(len(series)),
                   key=lambda s: (highlight is not None and colors[s] != grey, s))
    lines, dots, left, right = [], [], [], []
    for s in order:
        row = rows[s]
        # Break the curve where a rank is missing.
        run: list[tuple[Vec2, float]] = []
        runs = []
        for x, v in zip(xs, row):
            if v is None:
                if run:
                    runs.append(run)
                run = []
            else:
                run.append((Vec2(x, panel.y.map(v)), v))
        if run:
            runs.append(run)
        for items in runs:
            pts = [p for p, _ in items]
            if len(pts) >= 2:
                lines.append(draw_path(curves=_s_curve(pts), kind=MARK_LINE_KIND,
                                       stroke=colors[s], stroke_width=width,
                                       stroke_linecap="round", **style))
            for p, v in items:
                dots.append((p, make_marker("circle", dot, fill=colors[s],
                                            stroke=theme.paper,
                                            stroke_width=theme.hairline)))
                if numbers:
                    dots.append((p, label_text(f"{v:g}", number_size,
                                               text_fill=on_fill(colors[s]))))
        present = [i for i, v in enumerate(row) if v is not None]
        if not present:
            continue
        if labels in ("both", "left"):
            left.append((xs[present[0]], panel.y.map(row[present[0]]), series[s], colors[s]))
        if labels in ("both", "right"):
            right.append((xs[present[-1]], panel.y.map(row[present[-1]]), series[s], colors[s]))
    if not dots:
        raise DiagramError("bump() had nothing to draw: every rank is missing")
    gap = dot / 2 + theme.gap("xs")
    written = []
    for side, items in (("left", left), ("right", right)):
        for point, node, anchor in _end_labels(panel, items, side, gap):
            written.append(draw_place([(point, node)], anchor=anchor, origin=(0, 0)))
    node = draw_place(lines + dots + written)
    table = {n: list(r) for n, r in zip(series, rows)}
    node.notes["bump"] = {"series": tuple(series), "ranks": table,
                          "colors": tuple(colors)}
    return node, colors, table
