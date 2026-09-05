"""Traces: where a ray leaves a shape.

This is the primitive that makes arrows touch things. Without it a connector
runs centre to centre and either stops in mid-air or buries its head inside the
box. With it, `link(a, b)` fires a ray from a's centre toward b's, clips at a's
real boundary, and does the same from the other end -- correct for rounded
rectangles, ellipses, arbitrary outlines and image cutouts alike.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from .geom import Affine, Rect, Vec2

TraceFn = Callable[[Vec2, Vec2], tuple[float, ...]]

_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class Trace:
    """Parameter values t where the ray `origin + t * direction` crosses the
    boundary. Values are sorted and may be negative (behind the origin)."""

    hits: TraceFn | None = None
    # Flattened union members -- see the note in `Envelope`. Sorting once over
    # the concatenation rather than at every level of a fold also turns the
    # cost of N siblings from O(N^2 log N) into O(N log N) per ray.
    members: tuple[TraceFn, ...] | None = None

    @staticmethod
    def empty() -> Trace:
        return Trace(None)

    @property
    def is_empty(self) -> bool:
        return self.hits is None

    @staticmethod
    def from_rect(rect: Rect) -> Trace:
        return Trace.from_polygon(rect.corners)

    @staticmethod
    def from_polygon(points: Sequence[Vec2], closed: bool = True) -> Trace:
        pts = tuple(points)
        if len(pts) < 2:
            return Trace.empty()
        edges = list(zip(pts, pts[1:]))
        if closed:
            edges.append((pts[-1], pts[0]))

        def hits(origin: Vec2, direction: Vec2) -> tuple[float, ...]:
            found = []
            for p, q in edges:
                seg = q - p
                denom = direction.cross(seg)
                if abs(denom) < _EPS:
                    continue  # parallel; a grazing hit is not a crossing
                delta = p - origin
                t = delta.cross(seg) / denom
                u = delta.cross(direction) / denom
                if -_EPS <= u <= 1.0 + _EPS:
                    found.append(t)
            return tuple(sorted(found))

        return Trace(hits)

    @staticmethod
    def from_ellipse(center: Vec2, rx: float, ry: float) -> Trace:
        if rx <= 0 or ry <= 0:
            return Trace.empty()

        def hits(origin: Vec2, direction: Vec2) -> tuple[float, ...]:
            # Squash to the unit circle so the quadratic stays simple.
            ox, oy = (origin.x - center.x) / rx, (origin.y - center.y) / ry
            dx, dy = direction.x / rx, direction.y / ry
            a = dx * dx + dy * dy
            if a < _EPS:
                return ()
            b = 2 * (ox * dx + oy * dy)
            c = ox * ox + oy * oy - 1.0
            disc = b * b - 4 * a * c
            if disc < 0:
                return ()
            root = math.sqrt(disc)
            return tuple(sorted(((-b - root) / (2 * a), (-b + root) / (2 * a))))

        return Trace(hits)

    def _members(self) -> tuple[TraceFn, ...]:
        if self.hits is None:
            return ()
        return self.members if self.members is not None else (self.hits,)

    def union(self, other: Trace) -> Trace:
        if self.hits is None:
            return other
        if other.hits is None:
            return self
        return Trace._over(self._members() + other._members())

    @staticmethod
    def union_all(traces: Iterable[Trace]) -> Trace:
        """Union of many at once, in one pass rather than a fold."""
        parts: list[TraceFn] = []
        for tr in traces:
            parts.extend(tr._members())
        return Trace._over(tuple(parts))

    @staticmethod
    def _over(parts: tuple[TraceFn, ...]) -> Trace:
        if not parts:
            return Trace.empty()
        if len(parts) == 1:
            return Trace(parts[0])

        def hits(origin: Vec2, direction: Vec2) -> tuple[float, ...]:
            found: list[float] = []
            for part in parts:
                found.extend(part(origin, direction))
            return tuple(sorted(found))

        return Trace(hits, parts)

    def transform(self, t: Affine) -> Trace:
        """Ray parameters survive an affine map untouched, so pull the ray back
        into local space and reuse the answer."""
        if self.hits is None:
            return self
        inner = self.hits
        try:
            inv = t.inverse()
        except ValueError:
            return Trace.empty()

        def hits(origin: Vec2, direction: Vec2) -> tuple[float, ...]:
            return inner(inv.apply(origin), inv.apply_vector(direction))

        return Trace(hits)

    def exit(self, origin: Vec2, direction: Vec2) -> float | None:
        """Furthest crossing ahead of the origin: where a ray fired from inside
        actually leaves the shape. Concave outlines can be crossed more than
        once and we want the last one."""
        if self.hits is None:
            return None
        ahead = [t for t in self.hits(origin, direction) if t > _EPS]
        return max(ahead) if ahead else None

    def enter(self, origin: Vec2, direction: Vec2) -> float | None:
        """First crossing ahead of the origin, for rays fired from outside."""
        if self.hits is None:
            return None
        ahead = [t for t in self.hits(origin, direction) if t > _EPS]
        return min(ahead) if ahead else None

    def boundary_point(self, origin: Vec2, direction: Vec2,
                       from_inside: bool = True) -> Vec2 | None:
        t = self.exit(origin, direction) if from_inside else self.enter(origin, direction)
        if t is None:
            return None
        return origin + direction * t
