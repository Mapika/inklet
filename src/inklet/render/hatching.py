"""Physical hatch lines shared by vector export backends."""
from __future__ import annotations

import math
from collections.abc import Iterator

from ..core import DiagramError, Rect, Vec2
from .brushes import Hatch


def _range(box: Rect, brush: Hatch):
    theta = math.radians(brush.angle)
    direction = Vec2(math.cos(theta),math.sin(theta))
    normal = Vec2(-direction.y,direction.x)
    along = [point.dot(direction) for point in box.corners]
    across = [point.dot(normal)/brush.spacing for point in box.corners]
    if (not all(math.isfinite(value) for value in across)
            or math.ceil(max(across))-math.floor(min(across)) > 100_000):
        raise DiagramError('Hatch would exceed 100,000 lines; increase spacing')
    start,end = direction*min(along),direction*max(along)
    return start,end,normal,math.floor(min(across)),math.ceil(max(across))


def hatch_bounds(box: Rect, brush: Hatch) -> Rect:
    """An outward-rounded reusable cover; the authored shape clips it exactly.

    Cover cells span 32 hatch periods, capped at 8 mm. Near the work limit,
    retain exact bounds rather than rejecting a previously supported shape.
    """
    _range(box,brush)
    step = min(8.,brush.spacing*32)
    values = (box.x0/step,box.y0/step,box.x1/step,box.y1/step)
    if not all(math.isfinite(value) for value in values):
        return box
    cover = Rect(math.floor(values[0])*step,math.floor(values[1])*step,
                 math.ceil(values[2])*step,math.ceil(values[3])*step).union(box)
    try:
        _range(cover,brush)
    except DiagramError:
        return box
    return cover


def hatch_segments(box: Rect, brush: Hatch) -> Iterator[tuple[Vec2, Vec2]]:
    """Exact parallel lines, with a bounded 100,000-line index span."""
    start,end,normal,first,last = _range(box,brush)
    for index in range(first,last+1):
        offset = normal*(index*brush.spacing)
        yield start+offset,end+offset
