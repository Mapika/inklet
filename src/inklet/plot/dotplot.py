"""Dot plots: a matrix of circles whose area and colour are two values.

The single-cell dot plot puts categories (clusters, cell types) on one band
scale and features (genes) on the other. In each cell a circle's *area*
encodes one value, typically the fraction of cells that express the gene,
and its colour another, typically the mean expression.

`AreaScale` maps a value to a circle diameter so that the area is
proportional to the value: a value of `top` gets the full `diameter`, half
of it a circle of half the area, and zero no circle at all. It is the whole
of the size encoding, so the same object sizes the dots and the reference
circles of `size_key`, and a key cannot disagree with the dots it explains.
It works for any scatter with size encoding:

    sizes = inklet.plot.area_scale(500, 3.0)
    p.scatter(points, size=[sizes(v) for v in counts])
    p.size_key(sizes, title="cells")

`dotplot` draws the matrix; `Panel.dotplot` is the usual way to call it.
Colours go through the default matrix ramps (`Panel.matrix`), so
`Panel.colorbar()` afterwards explains them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..core import Diagram, DiagramError, mm
from ..draw.coords import active_theme
from ..draw.place import place as draw_place
from ..draw.shapes import marker as make_marker
from ..layout import vstack
from . import marks as _marks
from .axis import text_node, tick_texts
from .metadata import declare_domain as _declare_domain
from .raster import is_missing
from .scale import Band, linear, nice_ticks

__all__ = ["AreaScale", "area_scale", "dotplot", "size_key", "SIZE_KEY_KIND"]

SIZE_KEY_KIND = "size-key"

#: The largest dot, as a fraction of the smaller of the column and row
#: pitch. Neighbouring full dots then keep a visible gap.
_DOT_OF_PITCH = 0.9


@dataclass(frozen=True)
class AreaScale:
    """Value to circle diameter, with the area proportional to the value.

    `top` is the value drawn at the full `diameter` (mm). Zero draws a
    circle of no size; negative values and values above `top` are errors.
    """
    top: float
    diameter: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.top) and self.top > 0):
            raise DiagramError(f"an area scale needs a positive top value, got {self.top!r}")
        if not (math.isfinite(self.diameter) and self.diameter > 0):
            raise DiagramError(
                f"an area scale needs a positive diameter, got {self.diameter!r}")

    def __call__(self, value: float) -> float:
        """The diameter, in mm, of the circle for `value`."""
        value = float(value)
        if not math.isfinite(value) or value < 0:
            raise DiagramError(f"a circle's area cannot show {value!r}")
        if value > self.top * (1 + 1e-9):
            raise DiagramError(
                f"value {value!r} is above the area scale's top of {self.top!r}; "
                "raise the top so every circle fits")
        return self.diameter * math.sqrt(value / self.top)

    def ticks(self, count: int = 3) -> tuple[float, ...]:
        """Round reference values in (0, top], at most `count + 1` of them."""
        values: list[float] = []
        for asked in range(count, count + 4):
            values = [v for v in nice_ticks(0.0, self.top, asked) if v > 0]
            if len(values) >= count:
                break
        if len(values) > count + 1:
            # Every other value, counted down from the largest.
            values = values[::-1][::2][::-1]
        return tuple(values) or (self.top,)


def area_scale(top: float, diameter: float | str) -> AreaScale:
    """An `AreaScale`: `top` is drawn `diameter` mm across."""
    return AreaScale(float(top), mm(diameter))


def size_key(sizes: AreaScale, *, values: Sequence[float] | None = None,
             count: int = 3, format=None, title: str | None = None,
             orient: str = "v", fill: str | None = None,
             stroke: str | None = None, stroke_width: float | None = None,
             font_size: float | str | None = None, markup: bool = True,
             kind: str = SIZE_KEY_KIND) -> Diagram:
    """Reference circles with their values: the key to a size encoding.

    `sizes` is the `AreaScale` the marks were sized with. `values` names the
    reference values (default: `sizes.ticks(count)`); `format` is an axis
    format, a callable or a string such as `"{:.0%}"`. With `orient="v"`
    the circles stand in a column, each with its value to the right; with
    `orient="h"` they sit in a row with the values underneath. `fill`,
    `stroke` and `stroke_width` paint the circles (default: a grey fill and
    an ink hairline, as `Panel.dotplot` draws its dots without a colour
    value). `title` goes above.
    """
    if orient not in ("v", "h"):
        raise DiagramError(f'size key orient is "v" or "h", not {orient!r}')
    theme = active_theme()
    shown = tuple(sizes.ticks(count) if values is None else values)
    if not shown:
        raise DiagramError("a size key needs at least one value")
    if any(float(v) <= 0 for v in shown):
        raise DiagramError("size key values must be positive; zero has no circle")
    size = theme.font_size_small if font_size is None else mm(font_size)
    texts = tick_texts(linear((0.0, sizes.top)), shown, format)
    paint = {"fill": _marks.series_colors(None, 1)[0] if fill is None else fill,
             "stroke": theme.ink if stroke is None else stroke,
             "stroke_width": theme.hairline if stroke_width is None else mm(stroke_width)}
    widest = sizes(max(float(v) for v in shown))
    labels = [text_node(t, size, "label", markup=markup, features={"tnum": True})
              for t in texts]
    circles = [make_marker("circle", sizes(float(v)), **paint) for v in shown]
    if orient == "v":
        rows = _left_aligned_labels(circles, labels, widest, theme.gap("xs"))
        body = vstack(rows, gap=theme.gap("xs"), align="left")
    else:
        body = _baseline_row(circles, labels, theme.gap("xs") * 0.6,
                             theme.gap("xs") * 1.5)
    if title is not None:
        body = vstack([text_node(title, size, "label", markup=markup), body],
                      gap=theme.gap("xs"), align="left")
    node = Diagram(children=(body,), kind=kind)
    node.note("size_key", {"values": tuple(float(v) for v in shown),
                           "diameters": tuple(sizes(float(v)) for v in shown),
                           "top": sizes.top, "diameter": sizes.diameter})
    return node


def _left_aligned_labels(circles, labels, widest: float, gap: float) -> list:
    """One row per circle: the circle centred in a slot `widest` across,
    then its label, so the labels share a left edge."""
    rows = []
    for circle, label in zip(circles, labels):
        lb = label.bbox
        placed_label = label.translated(widest + gap - lb.x0, -lb.center.y)
        placed_circle = circle.translated(widest / 2 - circle.bbox.center.x,
                                          -circle.bbox.center.y)
        rows.append(Diagram(children=(placed_circle, placed_label), kind="swatch"))
    return rows


def _baseline_row(circles, labels, gap: float, between: float) -> Diagram:
    """Circles in a row standing on one line, each value centred below."""
    bottom = 0.0
    x = 0.0
    parts = []
    for circle, label in zip(circles, labels):
        width = max(circle.bbox.width, label.bbox.width)
        centre = x + width / 2
        cb, lb = circle.bbox, label.bbox
        parts.append(circle.translated(centre - cb.center.x, bottom - cb.y1))
        parts.append(label.translated(centre - lb.center.x,
                                      bottom + gap - lb.y0))
        x += width + between
    return Diagram(children=tuple(parts), kind="swatch")


def _positions(scale, given, count: int, axis: str) -> list[float]:
    """Where each column (x) or row (y) sits, in panel millimetres."""
    if given is None:
        if not isinstance(scale, Band):
            raise DiagramError(
                f"dotplot needs a band {axis} scale, or {axis}= naming a value "
                f"for each of the {count} {'columns' if axis == 'x' else 'rows'}")
        given = scale.domain
    given = list(given)
    if len(given) != count:
        raise DiagramError(
            f"dotplot has {count} {'columns' if axis == 'x' else 'rows'} but "
            f"{len(given)} {axis} positions")
    return [scale.map(v) for v in given]


def _pitch(positions: Sequence[float], scale, extent: float) -> float:
    if isinstance(scale, Band):
        return abs(scale.step)
    if len(positions) < 2:
        return extent
    ordered = sorted(positions)
    return min(b - a for a, b in zip(ordered, ordered[1:]))


def dotplot(panel, sizes, colors=None, *, x: Sequence | None = None,
            y: Sequence | None = None, top: float | None = None,
            diameter: float | str | None = None, ramp=None, scale=None,
            center: float | None = None, color: str | None = None,
            **style) -> tuple[Diagram, dict]:
    """The circles of a dot plot on `panel`. See `Panel.dotplot`.

    Returns `(node, note)`; the note's `sizes` is the `AreaScale` used and
    `ramp` and `scale` the colouring (None without `colors`).
    """
    from .matrix import default_coloring

    rows = [list(r) for r in sizes]
    if not rows or not rows[0]:
        raise DiagramError("dotplot needs at least one row and one column")
    if len({len(r) for r in rows}) != 1:
        raise DiagramError("dotplot rows must all be the same length")
    shape = (len(rows), len(rows[0]))
    shades = None
    if colors is not None:
        shades = [list(r) for r in colors]
        if len(shades) != shape[0] or any(len(r) != shape[1] for r in shades):
            raise DiagramError(
                f"dotplot colors must have the same shape as sizes, {shape[0]} x {shape[1]}")
    xs = _positions(panel.x, x, shape[1], "x")
    ys = _positions(panel.y, y, shape[0], "y")
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if not is_missing(v) and (not math.isfinite(float(v)) or float(v) < 0):
                raise DiagramError(
                    f"dotplot size values must be 0 or more, got {v!r} at row {r}, column {c}")
    present = [float(v) for row in rows for v in row if not is_missing(v)]
    if not present:
        raise DiagramError("dotplot has no size values: every cell is missing")
    if top is None:
        top = max(present) or 1.0
    if diameter is None:
        pitch = min(_pitch(xs, panel.x, panel.width), _pitch(ys, panel.y, panel.height))
        diameter = _DOT_OF_PITCH * pitch
    area = area_scale(top, diameter)
    theme = active_theme()
    unit = None
    if shades is not None:
        ramp, scale = default_coloring(shades, ramp, scale, center)
        unit = None if scale is None else scale.with_range(0.0, 1.0)
    fill = _marks.series_colors(None, 1)[0] if color is None else color
    paint = {"stroke": theme.ink, "stroke_width": theme.hairline}
    paint.update(style)
    items: list = []
    missing: list[tuple[int, int]] = []
    empty: list[tuple[int, int]] = []
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            shade = None if shades is None else shades[r][c]
            if is_missing(value) or (shades is not None and is_missing(shade)):
                missing.append((r, c))
                continue
            width = area(value)
            if width <= 0:
                empty.append((r, c))
                continue
            if shades is not None:
                t = float(shade) if unit is None else unit.map(float(shade))
                dot_fill = ramp(min(1.0, max(0.0, t)))
            else:
                dot_fill = fill
            items.append(((xs[c], ys[r]),
                          make_marker("circle", width, **{"fill": dot_fill, **paint})))
    if not items:
        raise DiagramError("dotplot had nothing to draw: every cell is missing or zero")
    node = draw_place(items, origin=(0, 0), kind="dotplot")
    if shades is not None:
        _declare_domain(node, scale)
    note = {"sizes": area, "ramp": ramp if shades is not None else None,
            "scale": scale if shades is not None else None,
            "missing": missing, "empty": empty, "shape": shape}
    node.notes["dotplot"] = {"top": area.top, "diameter": area.diameter,
                             "missing": missing, "empty": empty, "shape": shape}
    return node, note
