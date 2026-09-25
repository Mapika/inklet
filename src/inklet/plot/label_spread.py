"""Labels along one line, moved apart as little as possible.

Slope and bump charts write a name at the end of every series, and two
series that end at nearly the same value put their names on top of each
other. `spread` moves label centres along one coordinate until neighbours
clear each other by `gap`, keeping their order and minimising the squared
distance each one moves (isotonic regression by pooling adjacent
violators, the same method `inklet.layout.label_column` uses).
"""

from __future__ import annotations

from typing import Sequence

from ..core import Diagram
from ..draw.coords import active_theme
from .axis import text_node

__all__ = ["spread", "label_text", "on_fill"]


def spread(centres: Sequence[float], sizes: Sequence[float], gap: float = 0.0,
           lo: float | None = None, hi: float | None = None) -> list[float]:
    """New centres, in input order, no two of which overlap.

    `sizes` is the extent of each label along the line. `lo` and `hi`, when
    given, bound the whole run; a run longer than the bounds is centred on
    them rather than refused, since a label that overlaps its neighbour a
    little is still better than one that is missing.
    """
    count = len(centres)
    if count != len(sizes):
        raise ValueError("spread() needs one size per centre")
    if count == 0:
        return []
    order = sorted(range(count), key=lambda k: (centres[k], k))
    heights = [float(sizes[k]) for k in order]
    offsets = [0.0]
    for a, b in zip(heights, heights[1:]):
        offsets.append(offsets[-1] + (a + b) / 2 + gap)
    blocks: list[list[float]] = []
    for j, k in enumerate(order):
        blocks.append([centres[k] - offsets[j], 1.0])
        while len(blocks) > 1 and (blocks[-2][0] / blocks[-2][1]
                                   > blocks[-1][0] / blocks[-1][1]):
            total, weight = blocks.pop()
            blocks[-1][0] += total
            blocks[-1][1] += weight
    levels = [total / weight for total, weight in blocks
              for _ in range(int(weight))]
    if lo is not None and hi is not None:
        first = lo + heights[0] / 2
        last = hi - heights[-1] / 2 - offsets[-1]
        if last < first:
            levels = [(first + last) / 2] * count
        else:
            levels = [min(last, max(first, v)) for v in levels]
    out = [0.0] * count
    for j, k in enumerate(order):
        out[k] = levels[j] + offsets[j]
    return out


def label_text(content: str, size: float | None = None, **style) -> Diagram:
    """A data label in the theme's small type, set literally (no markup)."""
    theme = active_theme()
    return text_node(str(content), theme.font_size_small if size is None else size,
                     "label", markup=False, **style)


def on_fill(fill: str) -> str:
    """The theme ink or paper, whichever reads better on `fill`."""
    from ..themes import contrast_ratio
    theme = active_theme()
    return (theme.ink if contrast_ratio(theme.ink, fill) >= contrast_ratio(theme.paper, fill)
            else theme.paper)
