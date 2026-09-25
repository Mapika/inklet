"""Correlograms: a correlation matrix as a triangle of sized, coloured glyphs.

Each pair's |r| sets the glyph's area and r its colour on a diverging ramp
fixed at -1..1, so strength reads twice and sign by hue. The triangle leaves
out the mirror half and the diagonal, which carry no information.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import Diagram, DiagramError, EllipsePrim, RectPrim, Vec2, mm
from ..diagnostics.abut import abutting
from ..draw.coords import active_theme
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND
from .axis import text_node

__all__ = ["correlogram", "CORRELOGRAM_SHAPES", "CORRELOGRAM_TRIANGLES"]

CORRELOGRAM_SHAPES = ("circle", "square", "tile")
CORRELOGRAM_TRIANGLES = ("lower", "upper", "full")

#: The largest glyph's share of its cell, so |r| = 1 neighbours do not touch.
_FULL = 0.92


def _read(r) -> list[list[float | None]]:
    rows = [list(row.tolist() if hasattr(row, "tolist") else row)
            for row in (r.tolist() if hasattr(r, "tolist") else r)]
    n = len(rows)
    if n < 2 or any(len(row) != n for row in rows):
        raise DiagramError("a correlogram needs a square matrix of at least 2 x 2")
    out: list[list[float | None]] = []
    for row in rows:
        line: list[float | None] = []
        for v in row:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                line.append(None)
                continue
            v = float(v)
            if not -1.0 - 1e-9 <= v <= 1.0 + 1e-9:
                raise DiagramError(f"a correlation must be between -1 and 1, got {v!r}")
            line.append(max(-1.0, min(1.0, v)))
        out.append(line)
    return out


def correlogram(panel, r, name: Sequence[str] | None = None, *,
                triangle: str = "lower", shape: str = "circle", ramp=None,
                values=False, labels: bool = True, size: float | str | None = None,
                **style) -> tuple[Diagram, dict]:
    """A correlogram in `panel`'s plot area. See `Panel.correlogram`."""
    from .hierarchy_plots import _text_on
    from .ramp import default_ramp
    from .scale import linear
    if triangle not in CORRELOGRAM_TRIANGLES:
        raise DiagramError(f'correlogram triangle is "lower", "upper" or "full", not {triangle!r}')
    if shape not in CORRELOGRAM_SHAPES:
        raise DiagramError(f'correlogram shape is "circle", "square" or "tile", not {shape!r}')
    theme = active_theme()
    m = _read(r)
    n = len(m)
    names = [str(i + 1) for i in range(n)] if name is None else [str(v) for v in name]
    if len(names) != n:
        raise DiagramError(f"correlogram needs {n} names, got {len(names)}")
    if triangle == "lower":
        rows, cols = list(range(1, n)), list(range(n - 1))
    elif triangle == "upper":
        rows, cols = list(range(n - 1)), list(range(1, n))
    else:
        rows, cols = list(range(n)), list(range(n))
    ramp = default_ramp(True) if ramp is None else ramp
    scale = linear((-1.0, 1.0))
    unit = scale.with_range(0.0, 1.0)
    area = panel.area
    sx, sy = area.width / len(cols), area.height / len(rows)
    cell = min(sx, sy)
    font = theme.font_size_small if size is None else mm(size)
    fmt = "{:.2f}" if values is True else values
    glyphs: list = []
    words: list = []
    drawn = 0
    for a, i in enumerate(rows):
        for b, j in enumerate(cols):
            if (triangle == "lower" and j >= i) or (triangle == "upper" and j <= i):
                continue
            v = m[i][j]
            if v is None:
                continue
            centre = Vec2(area.x0 + (b + 0.5) * sx, area.y0 + (a + 0.5) * sy)
            fill = ramp(unit.map(v))
            if shape == "tile":
                prim = RectPrim(sx, sy)
            else:
                d = _FULL * cell * math.sqrt(abs(v))
                if d < 1e-6:
                    continue
                prim = (EllipsePrim(d / 2, d / 2) if shape == "circle"
                        else RectPrim(d * math.sqrt(math.pi) / 2, d * math.sqrt(math.pi) / 2))
            paint = {"fill": fill, "stroke": "none"}
            paint.update(style)
            glyphs.append((centre, Diagram(prim=prim, kind=MARK_KIND).styled(**paint)))
            drawn += 1
            if fmt:
                text = fmt.format(v) if isinstance(fmt, str) else fmt(v)
                if text.startswith("-") and not any(ch in "123456789" for ch in text):
                    text = text[1:]          # "-0.0" is a rounding artefact
                t = text_node(text.replace("-", "−"), font, "label", markup=False,
                              features={"tnum": True},
                              text_fill=_text_on(fill if shape == "tile" or abs(v) > 0.5
                                                 else theme.paper, theme))
                words.append((centre, t))
    items: list = []
    if glyphs:
        items.append(draw_place(glyphs, origin=(0, 0), kind=abutting("correlogram")))
    if words:
        items.append(draw_place(words, origin=(0, 0)))
    if labels:
        gap = theme.gap("xs")
        row_texts = [text_node(names[i], font, "label", markup=False) for i in rows]
        for a, t in enumerate(row_texts):
            b = t.bbox
            items.append(draw_place([(Vec2(area.x0 - gap - b.width / 2,
                                           area.y0 + (a + 0.5) * sy), t)], origin=(0, 0)))
        col_texts = [text_node(names[j], font, "label", markup=False) for j in cols]
        turn = max(t.bbox.width for t in col_texts) > sx * 0.9
        if turn:
            col_texts = [t.rotated(-90) for t in col_texts]
        top = triangle == "upper"
        for b, t in enumerate(col_texts):
            box = t.bbox
            y = area.y0 - gap - box.height / 2 if top else area.y1 + gap + box.height / 2
            items.append(draw_place([(Vec2(area.x0 + (b + 0.5) * sx, y), t)], origin=(0, 0)))
    node = draw_place(items, origin=(0, 0), kind="correlogram")
    note = {"triangle": triangle, "shape": shape, "cells": drawn, "cell": cell,
            "rows": [names[i] for i in rows], "columns": [names[j] for j in cols]}
    node.notes["correlogram"] = note
    return node, {"note": note, "ramp": ramp, "scale": scale}
