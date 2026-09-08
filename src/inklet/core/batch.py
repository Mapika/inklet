"""Immutable packed marker instances, in authored millimetres.

Records are little-endian (x, y, diameter, palette index, source index).
No point owns a Diagram, transform, style, envelope or trace object.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from functools import lru_cache

from .envelope import Envelope
from .geom import Vec2
from .prims import EllipsePrim, PathPrim, Prim, RectPrim, Subpath
from .trace import Trace

RECORD = struct.Struct('<dddIQ')


@dataclass(frozen=True, slots=True, eq=False)
class MarkerBatchPrim(Prim):
    """One unit-diameter shape and immutable instance records in paint order.

    ``palette`` entries are fill overrides; None inherits the node fill.
    ``records()`` yields original source indices even after clipping.
    Geometry identity, rather than a hash of all records, controls scene reuse.
    """
    shape: Prim
    data: bytes
    palette: tuple[str | None, ...] = (None,)

    def __post_init__(self):
        if not isinstance(self.shape, (EllipsePrim, RectPrim, PathPrim)):
            raise TypeError('marker batches require ellipse, rectangle or path geometry')
        object.__setattr__(self, 'data', bytes(self.data))
        object.__setattr__(self, 'palette', tuple(self.palette))
        if len(self.data) % RECORD.size:
            raise ValueError('incomplete marker batch record')
        for x, y, size, paint, _ in self.records():
            if not all(math.isfinite(v) for v in (x, y, size)) or size <= 0:
                raise ValueError('marker coordinates must be finite and sizes positive')
            if paint >= len(self.palette):
                raise ValueError('marker palette index is out of range')

    def __len__(self):
        return len(self.data) // RECORD.size

    def records(self):
        return RECORD.iter_unpack(self.data)

    def envelope(self):
        if not self.data:
            return Envelope.empty()
        unit = self.shape.envelope()
        if unit.is_empty:
            return unit
        def support(v):
            reach = unit.extent(v)
            vv = v.dot(v)
            return max((x*v.x+y*v.y)/vv + size*reach
                       for x, y, size, _, _ in self.records())
        return Envelope(support)

    def trace(self):
        if not self.data:
            return Trace.empty()
        unit = self.shape.trace()
        if unit.is_empty:
            return unit
        def hits(origin, direction):
            return tuple(sorted(t for x, y, size, _, _ in self.records()
                                for t in unit.hits((origin-Vec2(x,y))*(1/size),
                                                   direction*(1/size))))
        return Trace(hits)

    def instances(self):
        """Stream sized geometry; bound the temporary prototype cache to 128."""
        @lru_cache(maxsize=128)
        def sized(size):
            return scale_shape(self.shape, size)
        for x, y, size, paint, source in self.records():
            yield x, y, sized(size), self.palette[paint], source


def scale_shape(shape, size):
    if isinstance(shape, EllipsePrim):
        return EllipsePrim(shape.rx*size, shape.ry*size)
    if isinstance(shape, RectPrim):
        return RectPrim(shape.width*size, shape.height*size, shape.radius*size)
    return PathPrim(tuple(Subpath(tuple(p*size for p in sub.points), sub.closed,
                                 tuple(tuple(p*size for p in curve) for curve in sub.curves))
                          for sub in shape.subpaths), shape.filled, shape.fill_rule)
