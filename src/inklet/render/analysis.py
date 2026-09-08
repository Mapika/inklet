"""Page-scoped compositing analysis; no persistent drawing or font cache."""
from __future__ import annotations

from ..core import Affine, Diagram, ImagePrim, PathPrim, PhantomPrim, Rect, Style, TextPrim
from .bounds import clip_bounds, primitive_bounds
from .brushes import PaintedPrim


class CompositingAnalysis:
    """Reuse subtree bounds and paint counts within one complete page export.

    Keys include inherited style and world transform where relevant, allowing
    low-level exports of a subtree in different contexts. The owning page keeps
    nodes alive; caches are discarded after that export. Counts stop at two:
    a single primitive can itself perform overlapping paints.
    """

    def __init__(self) -> None:
        self._bounds: dict[tuple[int, Affine, Style], Rect | None] = {}
        self._counts: dict[tuple[int, Style], int] = {}

    def bounds(self, node: Diagram, world: Affine, style: Style) -> Rect | None:
        key = (id(node), world, style)
        if key in self._bounds:
            return self._bounds[key]
        box = primitive_bounds(node.prim, world, style)
        for child in node.children:
            other = self.bounds(child, world @ child.transform, child.style.over(style))
            if other is not None:
                box = other if box is None else box.union(other)
        box = clip_bounds(box, node, world)
        self._bounds[key] = box
        return box

    def paint_count(self, node: Diagram, style: Style) -> int:
        key = (id(node), style)
        if key in self._counts:
            return self._counts[key]
        prim = node.prim
        if prim is None or isinstance(prim, PhantomPrim):
            count = 0
        elif isinstance(prim, ImagePrim):
            count = 1
        elif isinstance(prim, (TextPrim, PaintedPrim)):
            # Glyph runs, halos, hatch backgrounds and gradient outlines can
            # overlap inside one primitive. Conservatively isolate these.
            count = 2
        else:
            filling = style.fill != 'none' and not (isinstance(prim, PathPrim) and not prim.filled)
            stroking = style.stroke not in (None, 'none')
            count = int(filling) + int(stroking)
        for child in node.children:
            if count >= 2:
                break
            count += self.paint_count(child, child.style.over(style))
        count = min(count, 2)
        self._counts[key] = count
        return count
