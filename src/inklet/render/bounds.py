"""Conservative painted bounds, separate from measured layout envelopes."""
from ..core import ImagePrim, PathPrim, PhantomPrim, Rect, TextPrim
from .brushes import PaintedPrim
from .paint import MITER_LIMIT


def painted_bounds(node, world, style):
    """Bound a subtree's ink in page coordinates, including strokes and halos.

    ``world`` and ``style`` already include the root node. Layout envelopes
    may deliberately reserve less or more space than the ink; they cannot be
    used as clipping bounds for a PDF transparency group.
    """
    box = None
    prim = node.prim
    if prim is not None and not isinstance(prim, PhantomPrim):
        shape = prim.shape if isinstance(prim, PaintedPrim) else prim
        if isinstance(shape, TextPrim):
            from .glyphs import placed_glyphs, to_path
            shape = to_path(placed_glyphs(shape))
            pad = max(0., style.halo or 0.)/2
        elif isinstance(shape, ImagePrim):
            pad = 0.
        else:
            pad = (1. if style.stroke_width is None else style.stroke_width)/2 if style.stroke not in (None, 'none') else 0.
            if style.stroke_linejoin in (None, 'miter'):
                pad *= MITER_LIMIT
            elif style.stroke_linecap == 'square':
                pad *= 2**.5
        if isinstance(shape, PathPrim):
            # A cubic lies inside its control polygon. The layout envelope
            # can use flattened samples; clipping must include the curve.
            points = [p for sub in shape.subpaths for p in sub.points]
            points.extend(p for sub in shape.subpaths for curve in sub.curves for p in curve)
            local = Rect.hull(points) if points else None
        else:
            local = shape.envelope().bbox() if shape is not None else None
        if local is not None:
            box = Rect(local.x0-pad,local.y0-pad,local.x1+pad,local.y1+pad).transform(world)
    for child in node.children:
        other = painted_bounds(child, world @ child.transform, child.style.over(style))
        if other is not None:
            box = other if box is None else box.union(other)
    return box
