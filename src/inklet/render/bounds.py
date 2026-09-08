"""Conservative painted bounds, separate from measured layout envelopes."""
from __future__ import annotations

from ..core import ImagePrim, PathPrim, PhantomPrim, Rect, TextPrim
from .brushes import PaintedPrim
from .paint import MITER_LIMIT


def painted_bounds(node, world, style):
    """Bound a subtree's ink in page coordinates, including strokes and halos.

    ``world`` and ``style`` already include the root node. Layout envelopes
    may deliberately reserve less or more space than the ink; they cannot be
    used as clipping bounds for a PDF transparency group.
    """
    box = primitive_bounds(node.prim, world, style)
    for child in node.children:
        other = painted_bounds(child, world @ child.transform, child.style.over(style))
        if other is not None:
            box = other if box is None else box.union(other)
    return clip_bounds(box, node, world)


def clip_bounds(box, node, world):
    if box is not None and node.clip_region:
        boundary = Rect.hull(world.apply(p) for p in node.clip_region)
        return box.overlap(boundary)
    return box


_UNSET = object()


def geometry_bounds(prim):
    """Conservative local geometry bounds, independent of paint and placement."""
    if prim is None or isinstance(prim, PhantomPrim):
        return None
    shape = prim.shape if isinstance(prim, PaintedPrim) else prim
    if isinstance(shape, TextPrim):
        from .glyphs import placed_glyphs, to_path
        shape = to_path(placed_glyphs(shape))
    if isinstance(shape, PathPrim):
        points = [p for sub in shape.subpaths for p in sub.points]
        points.extend(p for sub in shape.subpaths for curve in sub.curves for p in curve)
        return Rect.hull(points) if points else None
    return shape.envelope().bbox()


def primitive_bounds(prim, world, style, *, local_bounds=_UNSET):
    """Conservative ink bounds, optionally reusing measured local geometry."""
    if prim is None or isinstance(prim, PhantomPrim):
        return None
    shape = prim.shape if isinstance(prim, PaintedPrim) else prim
    if isinstance(shape, TextPrim):
        pad = max(0., style.halo or 0.)/2
    elif isinstance(shape, ImagePrim):
        pad = 0.
    else:
        pad = (1. if style.stroke_width is None else style.stroke_width)/2 if style.stroke not in (None, 'none') else 0.
        if style.stroke_linejoin in (None, 'miter'):
            pad *= MITER_LIMIT
        elif style.stroke_linecap == 'square':
            pad *= 2**.5
    local = geometry_bounds(prim) if local_bounds is _UNSET else local_bounds
    if local is None:
        return None
    return Rect(local.x0-pad,local.y0-pad,local.x1+pad,local.y1+pad).transform(world)
