"""Optional polyline reduction in physical plot coordinates."""
import math

from ..core import Vec2, mm


def tolerance_mm(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError('simplify needs a non-negative physical tolerance, not a boolean')
    value = mm(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError('simplify needs a finite, non-negative physical tolerance')
    return value


def simplify_points(points: tuple[Vec2, ...], tolerance: float) -> tuple[Vec2, ...]:
    """Keep a subsequence whose segments stay within the requested tolerance.

    Each removed vertex is within tolerance of its replacement segment, in
    millimetres. Endpoints and global x/y extrema are retained. Chunk boundaries
    and a linear scan budget bound work on adversarial paths; exhausting the
    budget retains remaining vertices rather than relaxing the tolerance.
    """
    count = len(points)
    if not all(math.isfinite(p.x) and math.isfinite(p.y) for p in points):
        raise ValueError('line simplification needs finite mapped coordinates')
    if count < 3 or tolerance == 0:
        return points
    cuts = {0, count-1, *range(0,count,1024)}
    for coordinate in ('x','y'):
        cuts.add(min(range(count),key=lambda j:getattr(points[j],coordinate)))
        cuts.add(max(range(count),key=lambda j:getattr(points[j],coordinate)))
    ordered = sorted(cuts)
    keep = set(cuts)
    stack = list(zip(ordered,ordered[1:]))
    budget = 16*count
    while stack:
        first,last = stack.pop()
        if last-first < 2:
            continue
        work = last-first-1
        if work > budget:
            keep.update(range(first+1,last))
            continue
        budget -= work
        a,b = points[first],points[last]
        dx,dy = b.x-a.x,b.y-a.y
        length = math.hypot(dx,dy)
        if not math.isfinite(length):
            keep.update(range(first+1,last))
            continue
        ux,uy = (dx/length,dy/length) if length else (0.0,0.0)
        farthest = tolerance
        split = None
        for index in range(first+1,last):
            p = points[index]
            px,py = p.x-a.x,p.y-a.y
            along = min(length,max(0.0,px*ux+py*uy))
            distance = math.hypot(px-along*ux,py-along*uy)
            if distance > farthest:
                farthest,split = distance,index
        if split is not None:
            keep.add(split)
            stack.extend(((first,split),(split,last)))
    return tuple(points[index] for index in sorted(keep))
