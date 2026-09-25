"""Waffle charts: parts of a whole as a grid of equal cells.

A 10 x 10 waffle gives each category a whole number of cells out of a
hundred, so a share reads as a count ("23 in 100") instead of an angle.
Cells are allocated by the largest-remainder method: every category gets
the whole cells its share covers, and the cells left over go to the
largest remainders, so the counts always add up to the grid.

The grid fills the plot area in millimetres and ignores the panel's
scales; a waffle has no axes. `waffle_cells` returns the counts without
drawing.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import Diagram, DiagramError, RectPrim, Vec2
from ..draw.coords import active_theme
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND
from ..themes.color import mix
from . import marks as _marks

__all__ = ["waffle", "waffle_cells", "WAFFLE_ORDERS"]

WAFFLE_ORDERS = ("column", "row")

#: Unallocated cells (when `total` exceeds the values), towards paper.
_EMPTY_TINT = 0.88


def waffle_cells(values: Sequence[float], cells: int,
                 total: float | None = None) -> list[int]:
    """How many of `cells` each value gets: largest-remainder rounding.

    The shares are `value / total` (default: the sum of the values). With a
    larger `total`, the counts add up to less than `cells` and the rest of
    the grid is left empty. Ties in the remainder go to the earlier value.
    """
    numbers = [float(v) for v in values]
    if not numbers:
        raise DiagramError("waffle() was given no values")
    if any(not math.isfinite(v) or v < 0 for v in numbers):
        raise DiagramError("waffle values must be finite and 0 or more")
    whole = sum(numbers) if total is None else float(total)
    if whole <= 0:
        raise DiagramError("waffle values add up to nothing")
    if sum(numbers) > whole * (1 + 1e-9):
        raise DiagramError(f"waffle values add up to {sum(numbers):g}, more than total={whole:g}")
    exact = [cells * v / whole for v in numbers]
    counts = [math.floor(e) for e in exact]
    target = round(cells * sum(numbers) / whole)
    order = sorted(range(len(numbers)), key=lambda i: (-(exact[i] - counts[i]), i))
    for i in order[:max(0, target - sum(counts))]:
        counts[i] += 1
    return counts


def waffle(panel, values: Sequence[float], *, rows: int = 10, columns: int = 10,
           total: float | None = None, color=None, gap: float = 0.18,
           order: str = "column", **style) -> tuple[Diagram, tuple[str, ...], list[int]]:
    """Draw a waffle into `panel`'s plot area. See `Panel.waffle`.

    Returns `(node, colours, counts)`.
    """
    if rows < 1 or columns < 1:
        raise DiagramError("a waffle needs at least one row and one column")
    if order not in WAFFLE_ORDERS:
        raise DiagramError(f"waffle order= is one of {WAFFLE_ORDERS}, not {order!r}")
    if not 0 <= gap < 1:
        raise DiagramError(f"waffle gap is a fraction of a cell in 0..1, got {gap!r}")
    counts = waffle_cells(values, rows * columns, total)
    theme = active_theme()
    fills = (tuple(theme.color(i + 1) for i in range(len(counts))) if color is None
             else _marks.series_colors(color, len(counts)))
    empty = style.pop("empty", mix(theme.ink, theme.paper, _EMPTY_TINT))
    area = panel.area
    pitch = min(area.width / columns, area.height / rows)
    side = pitch * (1 - gap)
    # The grid is centred in the plot area; the spare room, if the area is
    # not the grid's shape, is shared equally at both ends.
    x0 = area.center.x - pitch * columns / 2
    y1 = area.center.y + pitch * rows / 2
    owner = [i for i, n in enumerate(counts) for _ in range(n)]
    stroke = style.pop("stroke", None)
    stroke_width = style.pop("stroke_width", None)
    items = []
    for k in range(rows * columns):
        if order == "column":
            c, r = divmod(k, rows)
        else:
            r, c = divmod(k, columns)
        centre = Vec2(x0 + pitch * (c + 0.5), y1 - pitch * (r + 0.5))
        fill = fills[owner[k]] if k < len(owner) else empty
        paint = {"fill": fill, "stroke": "none" if stroke is None else stroke}
        if stroke_width is not None:
            paint["stroke_width"] = stroke_width
        items.append((centre, Diagram(prim=RectPrim(side, side),
                                      kind=MARK_KIND).styled(**paint)))
    node = draw_place(items, **style)
    node.notes["waffle"] = {"counts": tuple(counts), "rows": rows, "columns": columns,
                            "cell": side}
    return node, fills, counts
