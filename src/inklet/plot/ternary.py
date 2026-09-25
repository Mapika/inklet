"""Ternary plots: three proportions that add up to one, in a triangle.

`TernaryFrame` is the geometry: an equilateral triangle fitted into a plot
area with room for its tick labels, component A at the top vertex, B bottom
left and C bottom right. `frame.point(a, b, c)` is where a composition sits
(in panel millimetres); `ternary_frame` also draws the edges, the grid and
the labels. Each component's gridlines are labelled on the edge they meet
going anticlockwise: A on the left edge, B along the bottom, C on the right.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..core import Diagram, DiagramError, Vec2, mm
from ..diagnostics.abut import abutting
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..themes.color import mix
from .axis import text_node
from .furniture import GRID_KIND

__all__ = ["TernaryFrame", "ternary_frame", "normalize"]

_ROOT3 = math.sqrt(3.0)


@dataclass(frozen=True)
class TernaryFrame:
    """The triangle's vertices `a` (top), `b` (bottom left) and `c` (bottom
    right) in panel millimetres, and its `side` length."""
    a: Vec2
    b: Vec2
    c: Vec2
    side: float

    def point(self, a: float, b: float, c: float) -> Vec2:
        """Where the composition (a, b, c) sits; the parts are normalised."""
        a, b, c = normalize(a, b, c)
        return self.a * a + self.b * b + self.c * c


def normalize(a: float, b: float, c: float) -> tuple[float, float, float]:
    """(a, b, c) as fractions of their sum."""
    parts = [float(a), float(b), float(c)]
    if any(not math.isfinite(v) or v < 0 for v in parts):
        raise DiagramError(f"ternary parts must be finite and 0 or more, got {tuple(parts)}")
    total = sum(parts)
    if total <= 0:
        raise DiagramError("a ternary composition needs a positive total")
    return parts[0] / total, parts[1] / total, parts[2] / total


def ternary_frame(panel, *, labels: Sequence[str] = ("A", "B", "C"), ticks: int = 5,
                  grid: bool = True, total: float = 100, format=None,
                  size: float | str | None = None, **style) -> tuple[Diagram, TernaryFrame]:
    """The triangle, grid and labels of a ternary plot in `panel`'s plot
    area. See `Panel.ternary`."""
    theme = active_theme()
    if len(labels) != 3:
        raise DiagramError(f"a ternary plot needs three labels, got {len(labels)}")
    if ticks < 1:
        raise DiagramError(f"ternary ticks= must be 1 or more, got {ticks}")
    font = theme.font_size_small if size is None else mm(size)
    gap = theme.gap("xs")
    # Tick labels stand further off than a gap, clear of points on the edge.
    off = gap * 1.5
    fmt = format or (lambda v: f"{v:g}")
    values = [total * k / ticks for k in range(ticks + 1)]
    tick_texts = [text_node(fmt(v), font, "label", markup=False, features={"tnum": True})
                  for v in values]
    names = [text_node(str(t), theme.font_size, "label") for t in labels]
    tw = max(t.bbox.width for t in tick_texts)
    th = max(t.bbox.height for t in tick_texts)
    area = panel.area
    # Room: tick labels stick out sideways on the slanted edges and below
    # the base; the vertex names sit above A and below B and C.
    side_room = tw + off + gap
    top_room = names[0].bbox.height + off
    bottom_room = th + off + gap + max(names[1].bbox.height, names[2].bbox.height) + gap
    side = min(area.width - 2 * side_room,
               (area.height - top_room - bottom_room) * 2 / _ROOT3)
    if side <= 0:
        raise DiagramError("the ternary plot has no room for its triangle; enlarge the panel")
    height = side * _ROOT3 / 2
    top = area.y0 + top_room + ((area.height - top_room - bottom_room) - height) / 2
    cx = area.center.x
    A = Vec2(cx, top)
    B = Vec2(cx - side / 2, top + height)
    C = Vec2(cx + side / 2, top + height)
    frame = TernaryFrame(A, B, C, side)
    items: list = []
    if grid:
        pale = {"stroke": mix(theme.muted, theme.paper, 0.6), "stroke_width": theme.hairline}
        for k in range(1, ticks):
            t = k / ticks
            for p0, p1 in (
                (A * t + B * (1 - t), A * t + C * (1 - t)),   # a = t
                (B * t + C * (1 - t), B * t + A * (1 - t)),   # b = t
                (C * t + A * (1 - t), C * t + B * (1 - t)),   # c = t
            ):
                items.append(polyline((p0, p1), kind=GRID_KIND, **pale))
    edge = {"stroke": theme.ink, "stroke_width": theme.stroke, "stroke_linejoin": "miter"}
    edge.update(style)
    items.append(polyline((A, B, C), closed=True, kind="frame", **edge))
    # Tick labels, pushed out along each edge's outward normal.
    normals = (Vec2(-_ROOT3 / 2, -0.5), Vec2(0.0, 1.0), Vec2(_ROOT3 / 2, -0.5))
    starts = ((B, A), (C, B), (A, C))       # a on the left, b along the bottom, c on the right
    for (lo, hi), n in zip(starts, normals):
        for k, text in enumerate(tick_texts):
            if k in (0, ticks):
                continue        # the vertices already say 0 and 100
            t = k / ticks
            at = lo + (hi - lo) * t
            text = text.copy()
            b = text.bbox
            push = off + abs(n.x) * b.width / 2 + abs(n.y) * b.height / 2
            items.append(draw_place([(at + n * push, text)], origin=(0, 0)))
    # Vertex names.
    na, nb, nc = names
    items.append(draw_place([(A + Vec2(0.0, -(off + na.bbox.height / 2)), na)], origin=(0, 0)))
    below = th + off + gap
    items.append(draw_place([(B + Vec2(0.0, below + nb.bbox.height / 2), nb)], origin=(0, 0)))
    items.append(draw_place([(C + Vec2(0.0, below + nc.bbox.height / 2), nc)], origin=(0, 0)))
    node = draw_place(items, origin=(0, 0), kind=abutting("ternary"))
    node.notes["ternary"] = {"a": (A.x, A.y), "b": (B.x, B.y), "c": (C.x, C.y), "side": side,
                             "labels": tuple(str(t) for t in labels), "total": total}
    return node, frame
