"""From a cutout mask to the polygon `ImagePrim.outline` wants.

This is the seam the whole module exists to fill. `ImagePrim` takes an outline
in local coordinates -- origin-centred millimetres, y downward -- and uses it
for both the envelope and the trace, so once this polygon is right a photograph
packs and catches arrows exactly like a rounded rectangle does.

Two things are worth stating because getting either wrong is silent:

*Frame.* Pixel row/column indices map straight to local mm with no flip, since
image space and inklet space both grow y downward. The mask handed in here has
already been cropped to the subject's tight bounds, so index 0 and index n-1
are mapped to the two edges of the placed rectangle. That makes
`Envelope.from_points(outline).bbox()` exactly the rectangle `ImagePrim` was
sized to, rather than something a fraction of a pixel smaller.

*Simplification.* A traced contour has one vertex per boundary pixel -- tens of
thousands of them. `Trace.from_polygon` walks every edge on every ray, and
`link()` fires several rays per arrow, so an unsimplified silhouette makes
routing quadratic in the photograph's resolution for no visible gain. Douglas-
Peucker at a tolerance expressed in millimetres of *final print size* is the
right knob: 0.35 mm is under half a point, which nothing at journal scale can
resolve.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from ..core.geom import Vec2
from .deps import numpy
from .raster import shrink_mask

__all__ = [
    "Silhouette", "outline_from_mask", "trace_boundary", "simplify_ring",
    "is_simple", "DEFAULT_TOLERANCE", "DEFAULT_MAX_POINTS", "DEFAULT_RESOLUTION",
]

DEFAULT_TOLERANCE = 0.35      # mm at final size
DEFAULT_MAX_POINTS = 96
DEFAULT_RESOLUTION = 512      # px on the long side, for tracing only

# Clockwise on screen (y down), starting due west -- the order Moore-neighbour
# tracing walks when it looks for the next boundary pixel.
_MOORE = ((0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1))

_EPS = 1e-12


@dataclass(frozen=True)
class Silhouette:
    """The simplified outline plus what it cost to get there."""

    points: tuple[Vec2, ...]
    traced_points: int        # vertices before simplification
    tolerance: float          # mm actually used, after any back-off
    convex_fallback: bool = False

    def summary(self) -> str:
        how = "convex hull" if self.convex_fallback else f"{self.tolerance:.3g}mm"
        return f"{len(self.points)} pts from {self.traced_points} ({how})"


def outline_from_mask(mask: Any, width: float, height: float, *,
                      tolerance: float = DEFAULT_TOLERANCE,
                      max_points: int = DEFAULT_MAX_POINTS,
                      resolution: int = DEFAULT_RESOLUTION) -> Silhouette | None:
    """Trace `mask` -- already cropped to the subject -- into a local-mm polygon.

    Returns None when the subject is too thin to have an outline at all, which
    is the honest answer for a one-pixel sliver; the caller then falls back to
    the picture frame.
    """
    small = shrink_mask(mask, resolution)
    rows, cols = small.shape
    if rows < 2 or cols < 2:
        return None
    contour = trace_boundary(small)
    if len(contour) < 3:
        return None

    ring = tuple(
        Vec2(col / (cols - 1) * width - width / 2,
             row / (rows - 1) * height - height / 2)
        for row, col in contour
    )
    points, used, fallback = _simplify(ring, tolerance, max_points)
    if len(points) < 3:
        return None
    return Silhouette(tuple(points), len(ring), used, fallback)


# -- tracing --------------------------------------------------------------


def trace_boundary(mask: Any) -> list[tuple[int, int]]:
    """Moore-neighbour trace of the outer boundary, as ordered (row, col) pairs.

    Started at the topmost-then-leftmost foreground pixel, whose left neighbour
    is background by construction, and stopped by Jacob's criterion: re-entering
    the second boundary pixel from the same side means the walk has closed. A
    plain "am I back at the start" test loops forever on a shape that pinches to
    one pixel and is visited twice.
    """
    np = numpy()
    padded = np.pad(mask, 1)
    rows, cols = np.nonzero(padded)
    if rows.size == 0:
        return []

    start = (int(rows[0]), int(cols[0]))
    behind = (start[0], start[1] - 1)
    contour = [start]
    current, first_state = start, None

    for _ in range(4 * int(padded.size) + 8):
        offset = (behind[0] - current[0], behind[1] - current[1])
        index = _MOORE.index(offset)
        step = None
        for turn in range(1, 9):
            dy, dx = _MOORE[(index + turn) % 8]
            candidate = (current[0] + dy, current[1] + dx)
            if padded[candidate]:
                back_dy, back_dx = _MOORE[(index + turn - 1) % 8]
                behind = (current[0] + back_dy, current[1] + back_dx)
                step = candidate
                break
        if step is None:
            break  # an isolated pixel has no boundary to walk
        current = step
        state = (current, behind)
        if first_state is None:
            first_state = state
        elif state == first_state:
            break
        contour.append(current)

    if len(contour) > 1 and contour[-1] == contour[0]:
        contour.pop()
    return [(row - 1, col - 1) for row, col in contour]


# -- simplification -------------------------------------------------------


def _simplify(ring: Sequence[Vec2], tolerance: float,
              max_points: int) -> tuple[list[Vec2], float, bool]:
    """Coarsen until the polygon is small enough, then refine until it is simple."""
    used = max(tolerance, 0.0)
    points = simplify_ring(ring, used)
    for _ in range(24):
        if len(points) <= max_points:
            break
        used *= 1.5
        points = simplify_ring(ring, used)

    for _ in range(8):
        if is_simple(points):
            return points, used, False
        # Simplification cut a corner across the shape. Backing off is the only
        # repair that keeps the outline where the subject actually is; the point
        # budget loses to correctness here, because a self-crossing polygon makes
        # `Trace.exit` return a hit outside the silhouette.
        used *= 0.5
        points = simplify_ring(ring, used)
    if is_simple(points):
        return points, used, False
    return _convex_hull(ring), used, True


def simplify_ring(ring: Sequence[Vec2], tolerance: float) -> list[Vec2]:
    """Douglas-Peucker around a closed ring.

    The ring is cut at its four extreme vertices before simplifying. That both
    gives the algorithm the open polylines it is defined on and pins the
    silhouette's bounding box to the subject's: without the pins, a nearly
    straight edge with one pixel poking out of it loses that pixel and the
    asset quietly claims a few tenths of a millimetre less space than it fills.
    """
    count = len(ring)
    if count < 4:
        return list(ring)
    anchors = _extremes(ring)
    if len(anchors) < 2:
        anchors = [0, count // 2]

    kept: set[int] = set()
    for start, stop in zip(anchors, anchors[1:] + [anchors[0] + count]):
        arc = [ring[i % count] for i in range(start, stop + 1)]
        # The arc's own last vertex is the next arc's first; dropping it here
        # keeps each shared anchor in the result exactly once.
        kept.update((start + i) % count for i in _douglas_peucker(arc, tolerance)[:-1])
    return [ring[i] for i in sorted(kept)]


def _extremes(ring: Sequence[Vec2]) -> list[int]:
    """Indices of the topmost, rightmost, bottommost and leftmost vertices.

    First occurrence wins, so the answer does not depend on how NumPy breaks a
    tie or on which of two equal pixels the tracer reached first.
    """
    picks = {}
    for key, better in (
        ("top", lambda p, q: p.y < q.y), ("right", lambda p, q: p.x > q.x),
        ("bottom", lambda p, q: p.y > q.y), ("left", lambda p, q: p.x < q.x),
    ):
        best = 0
        for i, point in enumerate(ring):
            if better(point, ring[best]):
                best = i
        picks[key] = best
    return sorted(set(picks.values()))


def _douglas_peucker(points: Sequence[Vec2], tolerance: float) -> list[int]:
    """Indices to keep from an open polyline. Iterative: a 40 000-vertex contour
    would blow the recursion limit on a shape shaped like a comb."""
    count = len(points)
    if count <= 2:
        return list(range(count))
    keep = [False] * count
    keep[0] = keep[count - 1] = True
    stack = [(0, count - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        a, b = points[lo], points[hi]
        dx, dy = b.x - a.x, b.y - a.y
        span = math.hypot(dx, dy)
        worst, worst_distance = -1, tolerance
        for i in range(lo + 1, hi):
            p = points[i]
            if span < _EPS:
                distance = math.hypot(p.x - a.x, p.y - a.y)
            else:
                distance = abs(dx * (a.y - p.y) - (a.x - p.x) * dy) / span
            if distance > worst_distance:
                worst, worst_distance = i, distance
        if worst >= 0:
            keep[worst] = True
            stack.append((lo, worst))
            stack.append((worst, hi))
    return [i for i, flag in enumerate(keep) if flag]


# -- validity -------------------------------------------------------------


def is_simple(polygon: Sequence[Vec2]) -> bool:
    """Whether a closed polygon crosses itself.

    Worth the O(n^2): `Trace.exit` takes the *furthest* crossing ahead of the
    ray, so a folded outline sends an arrow to a point outside the subject and
    the failure looks like a routing bug rather than a geometry one.
    """
    count = len(polygon)
    if count < 4:
        return True
    for i in range(count):
        a, b = polygon[i], polygon[(i + 1) % count]
        for j in range(i + 1, count):
            if j == i or j == (i + 1) % count or (j + 1) % count == i:
                continue  # edges that share a vertex always "touch"
            c, d = polygon[j], polygon[(j + 1) % count]
            if _crosses(a, b, c, d):
                return False
    return True


def _crosses(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> bool:
    d1 = (b - a).cross(c - a)
    d2 = (b - a).cross(d - a)
    d3 = (d - c).cross(a - c)
    d4 = (d - c).cross(b - c)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _convex_hull(points: Sequence[Vec2]) -> list[Vec2]:
    """Andrew's monotone chain. The last-resort outline: always simple, always
    contains the subject, and honest about overstating a concave shape."""
    ordered = sorted({(p.x, p.y) for p in points})
    if len(ordered) < 3:
        return [Vec2(x, y) for x, y in ordered]

    def half(seq):
        chain: list[tuple[float, float]] = []
        for point in seq:
            while len(chain) >= 2:
                (x0, y0), (x1, y1) = chain[-2], chain[-1]
                if (x1 - x0) * (point[1] - y0) - (y1 - y0) * (point[0] - x0) > 0:
                    break
                chain.pop()
            chain.append(point)
        return chain

    lower, upper = half(ordered), half(reversed(ordered))
    return [Vec2(x, y) for x, y in lower[:-1] + upper[:-1]]
