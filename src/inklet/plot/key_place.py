"""`legend(corner="best")`: the key in the emptiest part of the plot area."""
from __future__ import annotations

from ..core import Diagram
from ..layout.label_search import emptiest, field_of

__all__ = ["best_spot"]


def best_spot(panel, node: Diagram, pad: float) -> Diagram | None:
    """`node` moved to the emptiest spot in `panel`'s plot area, or None.

    Scored against everything the panel has drawn so far in its content and
    over layers (see `layout.label_search.emptiest`). None when every spot
    would cover or cross something, so the caller can put the key outside.
    """
    area = panel.area
    b = node.bbox
    if (b is None or b.width > area.width - 2 * pad
            or b.height > area.height - 2 * pad):
        return None
    field = field_of([*panel._content, *panel._over], cell=4.0)
    box, _, clean = emptiest(b.width, b.height, area, field, pad=pad)
    if not clean:
        return None
    moved = node.translated(box.x0 - b.x0, box.y0 - b.y0)
    moved.notes["legend_place"] = {"corner": "best",
                                   "box": (box.x0, box.y0, box.x1, box.y1)}
    return moved
