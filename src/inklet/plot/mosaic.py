"""Mosaic (Marimekko) charts: stacked bars whose widths are the totals.

Each category is a column as wide as its share of the grand total, divided
from bottom to top into the shares of each series within that category. The
area of every cell is then proportional to its value, and the chart shows
both the size of each category and its composition at once.

Columns run across the panel's x domain (so `x=(0, 1)` writes fractions on
the axis and `x=(0, 100)` percentages); cells run up its y domain in the
same way. `mosaic_layout` returns the geometry without drawing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..core import Diagram, DiagramError, mm
from ..draw.coords import active_theme
from ..draw.place import place as draw_place
from . import marks as _marks
from .label_spread import label_text, on_fill

__all__ = ["MosaicColumn", "mosaic", "mosaic_layout"]


@dataclass(frozen=True)
class MosaicColumn:
    """One column: its category, its x extent as fractions of the whole
    (`start`, `end`), its total, and each series' `(bottom, top)` share."""
    category: object
    start: float
    end: float
    total: float
    cells: tuple[tuple[float, float], ...]

    @property
    def centre(self) -> float:
        return (self.start + self.end) / 2


def mosaic_layout(at: Sequence, values) -> list[MosaicColumn]:
    """Column extents and cell shares, all as fractions in 0..1.

    `values` is series-major, like `Panel.bars`: `values[s][c]` is series
    `s` in category `c`. Values must be 0 or more; an all-zero category is
    a column of no width.
    """
    rows = _marks._series(values)
    places = list(at)
    if len(places) != len(rows[0]):
        raise DiagramError(f"mosaic() got {len(places)} categories for {len(rows[0])} values")
    if any(not math.isfinite(v) or v < 0 for row in rows for v in row):
        raise DiagramError("mosaic values must be finite and 0 or more")
    totals = [sum(row[c] for row in rows) for c in range(len(places))]
    grand = sum(totals)
    if grand <= 0:
        raise DiagramError("mosaic values add up to nothing")
    out = []
    start = 0.0
    for c, where in enumerate(places):
        width = totals[c] / grand
        cells = []
        bottom = 0.0
        for row in rows:
            share = row[c] / totals[c] if totals[c] > 0 else 0.0
            cells.append((bottom, bottom + share))
            bottom += share
        out.append(MosaicColumn(where, start, start + width, totals[c], tuple(cells)))
        start += width
    return out


def _between(scale, fraction: float) -> float:
    lo, hi = scale.domain[0], scale.domain[-1]
    return scale.map(lo + (hi - lo) * fraction)


def mosaic(panel, at: Sequence, values, *, color=None, gap: float | str = 0.6,
           labels=None, **style) -> tuple[Diagram, tuple[str, ...], list[MosaicColumn]]:
    """Draw a mosaic on `panel`. See `Panel.mosaic`.

    Returns `(node, colours per series, columns)`.
    """
    columns = mosaic_layout(at, values)
    count = len(columns[0].cells)
    theme = active_theme()
    fills = (tuple(theme.color(i + 1) for i in range(count)) if color is None
             else _marks.series_colors(color, count))
    space = mm(gap)
    stroke = style.pop("stroke", theme.paper)
    stroke_width = style.pop("stroke_width", theme.hairline * 2)
    cells, written = [], []
    for column in columns:
        if column.total <= 0:
            continue
        x0, x1 = sorted((_between(panel.x, column.start), _between(panel.x, column.end)))
        x0, x1 = x0 + space / 2, x1 - space / 2
        if x1 <= x0:
            continue
        for s, (bottom, top) in enumerate(column.cells):
            if top - bottom <= 0:
                continue
            y0, y1 = _between(panel.y, bottom), _between(panel.y, top)
            centre = _marks._point("v", (x0 + x1) / 2, (y0 + y1) / 2)
            cells.append(_marks._rect(centre, x1 - x0, abs(y1 - y0), fills[s],
                                      stroke, stroke_width))
            if labels is not None and labels is not False:
                share = top - bottom
                text = (f"{100 * share:.0f}%" if labels is True
                        else str(labels(share)) if callable(labels)
                        else str(labels).format(share))
                node = label_text(text, text_fill=on_fill(fills[s]))
                box = node.bbox
                if box.width + theme.gap("xs") <= x1 - x0 and box.height <= abs(y1 - y0):
                    written.append((centre, node))
    if not cells:
        raise DiagramError("mosaic() had nothing to draw")
    node = draw_place(cells + written, **style)
    node.notes["mosaic"] = {
        "columns": tuple((c.category, c.start, c.end, c.total) for c in columns)}
    return node, fills, columns
