"""The subject's outer outline, recovered from the strokes.

Line Art's silhouette pass returns the true occluding contour, which is exactly
right and not directly usable: it arrives as a few dozen open fragments,
because the contour is cut wherever it passes behind another part of the same
body. Rejoining them end to end recovers a closed ring for a compact subject --
a bunny, a skull -- and produces a tangle for anything with limbs, where the
outer boundary of the *drawing* runs along a different fragment from the one
the chain was following.

So there are two ways home and the good one needs numpy. With it, the strokes
are inked into a grid, the outside is flooded from the border, and what the
flood could not reach is the subject: that boundary is the outline, concavities
and all, and it comes back through the same Moore trace and Douglas-Peucker
that `inklet.asset` uses on a photograph's cutout. Without numpy, the fragments
are chained and the result is used only if it does not cross itself. Which one
ran is reported rather than hidden, because the two are not equally good.

Nothing here imports numpy at module scope: this backend is optional, and its
optional dependency has to stay optional too.
"""

from __future__ import annotations

import math
from typing import Sequence

from ...assets.deps import have
from ...assets.silhouette import (
    DEFAULT_MAX_POINTS, DEFAULT_RESOLUTION, DEFAULT_TOLERANCE, Silhouette,
    is_simple, simplify_ring,
)
from ...core.geom import Vec2

__all__ = ["outline", "chain_strokes", "TRACED", "CHAINED", "HULL", "NONE"]

TRACED = "traced"      # inked, flooded and Moore-traced: concavities survive
CHAINED = "chained"    # the contour fragments, rejoined end to end
HULL = "hull"          # a chain that crossed itself, replaced by its hull
NONE = "none"          # nothing closed; the caller should use the bounding box

# A join longer than this fraction of the drawing's larger side is not the next
# piece of the same outline, it is a jump to somewhere else. Found by widening
# it until a scanned bunny's outline joined up and no further.
_CHAIN_GAP = 0.05

# One cell of the ink grid, as a fraction of the drawing's larger side. Two
# strokes that abut are cut at the same point, so the barrier is continuous at
# any resolution; this only has to be fine enough that a thin limb does not
# close up. At 1/512 a 48 mm drawing resolves a tenth of a millimetre.
_GRID = 1.0 / DEFAULT_RESOLUTION


def outline(strokes: Sequence[Sequence[Vec2]],
            barrier: Sequence[Sequence[Vec2]] = (), *,
            width: float, height: float,
            tolerance: float = DEFAULT_TOLERANCE,
            max_points: int = DEFAULT_MAX_POINTS) -> tuple[Silhouette | None, str]:
    """The closed outline of a drawing, and how it was arrived at.

    `strokes` are the silhouette pass; `barrier` is every other stroke, added
    to the ink grid only. Interior lines cannot change where the outside stops,
    but a crease that happens to run along the boundary plugs a gap a clipped
    contour left, so they are cheap insurance.
    """
    if not strokes:
        return None, NONE
    if have("numpy"):
        traced = _trace(list(strokes) + list(barrier), width, height,
                        tolerance, max_points)
        if traced is not None:
            return traced, TRACED
    ring = chain_strokes(strokes, _CHAIN_GAP * max(width, height))
    if len(ring) < 3:
        return None, NONE
    points, used = _simplify(ring, tolerance, max_points, max(width, height))
    if len(points) < 3:
        return None, NONE
    if is_simple(points):
        return Silhouette(tuple(points), len(ring), used), CHAINED
    hull = convex_hull(points)
    if len(hull) < 3:
        return None, NONE
    return Silhouette(tuple(hull), len(ring), used, convex_fallback=True), HULL


def _trace(strokes: Sequence[Sequence[Vec2]], width: float, height: float,
           tolerance: float, max_points: int) -> Silhouette | None:
    """Ink, flood, trace. Returns None if the drawing has no interior at all."""
    from ...assets.mask import border_seeds, flood
    from ...assets.silhouette import outline_from_mask
    numpy = __import__("numpy")

    span = max(width, height)
    cell = span * _GRID
    if cell <= 0:
        return None
    # One empty cell all the way round, so the flood always starts outside even
    # when the subject runs to the very edge of its own bounding box.
    columns = int(math.ceil(width / cell)) + 3
    rows = int(math.ceil(height / cell)) + 3
    if columns < 4 or rows < 4 or columns * rows > 16_000_000:
        return None

    ink = numpy.zeros((rows, columns), dtype=bool)
    origin_x = -width / 2 - 1.5 * cell
    origin_y = -height / 2 - 1.5 * cell
    for stroke in strokes:
        _ink_polyline(ink, stroke, origin_x, origin_y, cell, rows, columns)
    if not ink.any():
        return None

    outside = flood(~ink, border_seeds(rows, columns))
    solid = ~outside
    if not solid.any():
        return None
    # `outline_from_mask` maps index 0 and index n-1 onto the two edges of the
    # placed rectangle, so hand it the grid's own extent rather than the
    # drawing's: the grid is a cell and a half wider on every side.
    return outline_from_mask(
        solid, (columns - 1) * cell, (rows - 1) * cell,
        tolerance=tolerance, max_points=max_points, resolution=DEFAULT_RESOLUTION,
    )


def _ink_polyline(ink, points: Sequence[Vec2], origin_x: float, origin_y: float,
                  cell: float, rows: int, columns: int) -> None:
    """Mark every cell the polyline passes through.

    Stepped at half a cell rather than run through Bresenham: the barrier only
    has to be watertight against a four-connected flood, and oversampling is
    both shorter and immune to the off-by-one that a hand-written line
    rasteriser invites.
    """
    for start, end in zip(points, points[1:]):
        dx = (end.x - start.x) / cell
        dy = (end.y - start.y) / cell
        steps = max(1, int(math.ceil(2.0 * math.hypot(dx, dy))))
        for step in range(steps + 1):
            t = step / steps
            column = int((start.x + (end.x - start.x) * t - origin_x) / cell)
            row = int((start.y + (end.y - start.y) * t - origin_y) / cell)
            if 0 <= row < rows and 0 <= column < columns:
                ink[row, column] = True


def chain_strokes(polylines: Sequence[Sequence[Vec2]], gap: float) -> list[Vec2]:
    """Join strokes end to end, longest first, while the gaps stay small."""
    remaining = sorted(
        ([Vec2(p.x, p.y) for p in line] for line in polylines if len(line) >= 2),
        key=lambda line: (-_length(line), line[0].x, line[0].y),
    )
    if not remaining:
        return []
    ring = remaining.pop(0)
    while remaining:
        tail = ring[-1]
        best = None
        for index, line in enumerate(remaining):
            for backwards in (False, True):
                head = line[-1] if backwards else line[0]
                distance = (head - tail).length
                if best is None or distance < best[0]:
                    best = (distance, index, backwards)
        distance, index, backwards = best
        if distance > gap:
            break
        line = remaining.pop(index)
        ring.extend(reversed(line) if backwards else line)
    return _dedupe(ring)


def convex_hull(points: Sequence[Vec2]) -> list[Vec2]:
    """Monotone chain, on a sorted-then-deduped list rather than on a set: this
    library's output may not depend on a set's iteration order even where it
    would be sorted away a line later."""
    ordered: list[tuple[float, float]] = []
    for pair in sorted((p.x, p.y) for p in points):
        if not ordered or ordered[-1] != pair:
            ordered.append(pair)
    if len(ordered) < 3:
        return [Vec2(x, y) for x, y in ordered]

    def half(sequence):
        stack: list[tuple[float, float]] = []
        for point in sequence:
            while len(stack) >= 2 and _cross(stack[-2], stack[-1], point) <= 0:
                stack.pop()
            stack.append(point)
        return stack[:-1]

    return [Vec2(x, y) for x, y in half(ordered) + half(list(reversed(ordered)))]


def _simplify(ring: Sequence[Vec2], tolerance: float, max_points: int,
              span: float) -> tuple[list[Vec2], float]:
    used = tolerance
    points = simplify_ring(ring, used)
    while len(points) > max_points and used < span:
        used *= 2.0
        points = simplify_ring(ring, used)
    return points, used


def _dedupe(points: Sequence[Vec2], epsilon: float = 1e-9) -> list[Vec2]:
    out: list[Vec2] = []
    for point in points:
        if not out or (point - out[-1]).length > epsilon:
            out.append(point)
    while len(out) > 1 and (out[0] - out[-1]).length <= epsilon:
        out.pop()
    return out


def _length(line: Sequence[Vec2]) -> float:
    return sum((b - a).length for a, b in zip(line, line[1:]))


def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
