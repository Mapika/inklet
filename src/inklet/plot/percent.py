"""100% stacked bars: each position's series as percentages of its total.

`Panel.bars(normalize=True)` hands the heights to `percent_of_totals` before
drawing, which rescales every position so its series sum to 100, and stacks
them. Composition -- the share of each cell type per sample -- then reads
straight off a 0 to 100 axis, and `labels=True` writes each share as a
percentage.

A position whose values are all zero has no composition; its bars are left
empty (all zero) rather than divided by zero.
"""

from __future__ import annotations

import math

from ..core import DiagramError
from . import marks as _marks

__all__ = ["percent_of_totals", "PERCENT_LABEL"]

#: The label format `bars(normalize=True, labels=True)` uses.
PERCENT_LABEL = "{:.0f}%"


def percent_of_totals(heights) -> tuple[tuple[float, ...], ...]:
    """Series-major `heights` rescaled so each position sums to 100."""
    rows = _marks._series(heights)
    for row in rows:
        for v in row:
            if not math.isfinite(v) or v < 0:
                raise DiagramError(
                    f"normalized bars need finite, non-negative values, got {v!r}")
    totals = [math.fsum(col) for col in zip(*rows)]
    return tuple(tuple(100.0 * v / t if t > 0 else 0.0 for v, t in zip(row, totals))
                 for row in rows)
