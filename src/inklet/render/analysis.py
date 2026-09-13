"""Primitive compositing classification used by compiled scene nodes."""
from __future__ import annotations

from ..core import MarkerBatchPrim, ImagePrim, PathPrim, PhantomPrim, TextPrim
from .brushes import PaintedPrim


def primitive_paint_count(prim, style):
    """Number of potentially overlapping primitive paints, capped at two."""
    if prim is None or isinstance(prim, PhantomPrim):
        count = 0
    elif isinstance(prim, ImagePrim):
        count = 1
    elif isinstance(prim, (TextPrim, PaintedPrim, MarkerBatchPrim)):
        # Glyph runs, halos, hatch backgrounds and gradient outlines can
        # overlap inside one primitive. Conservatively isolate these.
        count = 2
    else:
        filling = style.fill != 'none' and not (isinstance(prim, PathPrim) and not prim.filled)
        stroking = style.stroke not in (None, 'none')
        count = int(filling) + int(stroking)
    return count
