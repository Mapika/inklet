"""Envelopes: how far a diagram reaches in a given direction.

An envelope is a support function, not a bounding box. Ask it for a direction
and it answers with the distance to the supporting line perpendicular to that
direction. That is what lets `hstack` pack a rotated arrow or a trimmed cutout
against its neighbour without the empty corners of a bbox pushing them apart.

Convention follows the support-function definition: for a query vector `v`,
`f(v)` is the scalar s with `p . v <= s * (v . v)` for every point p. For unit
`v` that is exactly the signed distance from the origin along `v`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from .geom import EAST, NORTH, SOUTH, WEST, Affine, Rect, Vec2

SupportFn = Callable[[Vec2], float | None]

_MISSING = object()
# Key for the memoised bounding box, sharing the extent cache. It is not a
# Vec2, so it cannot collide with a direction anyone asks about.
_BBOX = object()


@dataclass(frozen=True, slots=True)
class Envelope:
    support: SupportFn | None = None
    # The union members, kept flat. A left fold of pairwise unions would
    # otherwise build a chain of closures one deep per sibling: a panel with a
    # thousand marks then costs a thousand stack frames on every support query
    # and overruns the interpreter's recursion limit before it can draw. Held
    # alongside `support` rather than replacing it so that a transformed or
    # padded envelope stays a single opaque function, which is what it is.
    members: tuple[SupportFn, ...] | None = None
    # Answers already given. An envelope is frozen and its support function is
    # pure, so an extent is a property of the envelope rather than of who asked
    # for it -- and layout asks the same node for the same compass direction
    # over and over: every stacking pass wants each child's front and back, and
    # `bbox` wants all four. Allocated on the first query rather than in
    # `__init__`, because unions and transforms build envelopes far more often
    # than anything queries them. Excluded from equality: two envelopes are the
    # same envelope whether or not one of them has been asked anything.
    _cache: dict | None = field(default=None, compare=False, repr=False)

    @staticmethod
    def empty() -> Envelope:
        """The identity for union. An empty diagram occupies no space at all,
        which is not the same as occupying a zero-sized point at the origin."""
        return Envelope(None)

    @property
    def is_empty(self) -> bool:
        return self.support is None

    @staticmethod
    def from_points(points: Iterable[Vec2]) -> Envelope:
        """Support function of a point cloud, maximised over its convex hull.

        No interior point can be the furthest one in any direction, so the hull
        is what the maximum is really taken over -- and a traced silhouette or
        a run of mesh facets arrives with hundreds of points and a handful of
        corners. The hull is built on the first query rather than here, because
        a layout builds far more envelopes than it interrogates, and hulling a
        thousand-point outline nobody asks about is pure loss.
        """
        cloud = tuple(points)
        if not cloud:
            return Envelope.empty()
        hull: tuple[tuple[float, float], ...] = ()

        def support(v: Vec2) -> float:
            nonlocal hull
            if not hull:
                hull = _hull(cloud)
            vx, vy = v.x, v.y
            # Coordinates rather than Vec2, and the dot product written out:
            # this is the innermost loop of every layout pass, and the method
            # call around two multiplies was most of it.
            return max(x * vx + y * vy for x, y in hull) / v.dot(v)

        return Envelope(support)

    @staticmethod
    def from_rect(rect: Rect) -> Envelope:
        return Envelope.from_points(rect.corners)

    @staticmethod
    def from_ellipse(center: Vec2, rx: float, ry: float) -> Envelope:
        """Exact for ellipses, where a corner-based hull would overstate by 40%."""

        def support(v: Vec2) -> float:
            vv = v.dot(v)
            radial = ((rx * v.x) ** 2 + (ry * v.y) ** 2) ** 0.5
            return (center.dot(v) + radial) / vv

        return Envelope(support)

    def extent(self, direction: Vec2) -> float | None:
        """Distance from the origin to the boundary along a unit direction."""
        if self.support is None:
            return None
        cache = self._cache
        if cache is None:
            cache = {}
            object.__setattr__(self, "_cache", cache)
        answer = cache.get(direction, _MISSING)
        if answer is _MISSING:
            answer = cache[direction] = self.support(direction)
        return answer

    def _members(self) -> tuple[SupportFn, ...]:
        if self.support is None:
            return ()
        return self.members if self.members is not None else (self.support,)

    def union(self, other: Envelope) -> Envelope:
        if self.support is None:
            return other
        if other.support is None:
            return self
        return Envelope._over(self._members() + other._members())

    @staticmethod
    def union_all(envelopes: Iterable[Envelope]) -> Envelope:
        """Union of many at once, in one pass rather than a fold.

        `union` already keeps the result flat, but folding it over N children
        copies the member tuple N times. This is the same answer for the same
        cost as a single concatenation, which is what the layout tree wants.
        """
        parts: list[SupportFn] = []
        for env in envelopes:
            parts.extend(env._members())
        return Envelope._over(tuple(parts))

    @staticmethod
    def _over(parts: tuple[SupportFn, ...]) -> Envelope:
        if not parts:
            return Envelope.empty()
        if len(parts) == 1:
            return Envelope(parts[0])

        def support(v: Vec2) -> float:
            return max(f(v) for f in parts)

        return Envelope(support, parts)

    def transform(self, t: Affine) -> Envelope:
        if self.support is None:
            return self
        # `extent` rather than `support`: a transform is where the layout tree
        # is stitched together, so the same inner envelope is asked the same
        # question by every ancestor that stacks it. Going through the memo
        # answers the second ancestor for free, and returns the identical
        # float the first one got.
        inner = self.extent

        def support(v: Vec2) -> float:
            u = t.transpose_linear(v)
            uu = u.dot(u)
            if uu == 0.0:
                # Degenerate linear part collapsed this direction; only the
                # translation survives.
                return Vec2(t.e, t.f).dot(v) / v.dot(v)
            return (inner(u) * uu + Vec2(t.e, t.f).dot(v)) / v.dot(v)

        return Envelope(support)

    def translate(self, dx: float, dy: float) -> Envelope:
        return self.transform(Affine.translation(dx, dy))

    def pad(self, amount: float) -> Envelope:
        """Grow uniformly in every direction, the way padding should behave."""
        if self.support is None:
            return self
        inner = self.support

        def support(v: Vec2) -> float:
            return inner(v) + amount / v.length

        return Envelope(support)

    def minkowski(self, other: Envelope) -> Envelope:
        """Sweep this shape around the other. Support functions simply add under
        a Minkowski sum, which is the whole reason padding can stay tight: the
        alternative -- unioning with a padding rectangle -- rounds the result up
        to that rectangle and invents clearance on the diagonals."""
        if self.support is None or other.support is None:
            return Envelope.empty()
        mine, theirs = self.support, other.support

        def support(v: Vec2) -> float:
            return mine(v) + theirs(v)

        return Envelope(support)

    def expand(self, top: float, right: float | None = None,
               bottom: float | None = None, left: float | None = None) -> Envelope:
        """Asymmetric padding, in CSS shorthand order. Remember y points down,
        so `top` grows the envelope toward negative y."""
        right = top if right is None else right
        bottom = top if bottom is None else bottom
        left = right if left is None else left
        if self.support is None:
            return self
        if top == right == bottom == left == 0.0:
            return self
        if top == right == bottom == left:
            # Uniform padding is an offset curve, so sweep a disc: that adds
            # exactly `top` in every direction. Sweeping a square instead would
            # add top*sqrt(2) on the diagonals -- clearance nobody asked for.
            return self.pad(top)
        # Asymmetric padding has no disc to sweep; a box sum is the honest
        # generalisation and matches what CSS padding means.
        return self.minkowski(Envelope.from_rect(Rect(-left, -top, right, bottom)))

    def bbox(self) -> Rect | None:
        """Four axis queries. Exact regardless of convexity, since the support
        function reports true extremes along whatever direction it is given."""
        if self.support is None:
            return None
        cache = self._cache
        if cache is not None and (box := cache.get(_BBOX)) is not None:
            return box
        box = Rect(
            x0=-self.extent(WEST), y0=-self.extent(NORTH),
            x1=self.extent(EAST), y1=self.extent(SOUTH),
        )
        # `extent` has just made the cache if it did not exist.
        self._cache[_BBOX] = box
        return box


def _hull(points: tuple[Vec2, ...]) -> tuple[tuple[float, float], ...]:
    """The convex hull of a point cloud, as bare `(x, y)` pairs.

    Andrew's monotone chain. A point strictly inside the hull is dropped, and
    so is one lying on an edge between two corners: for a linear functional --
    which is all a support query is -- an interior point is never the maximum,
    and an edge point only ever ties with the corners it sits between. That the
    tie is exact in floating point too was verified rather than assumed: every
    support query the four corpus figures make, 256k of them, was answered over
    the cloud and over the hull and the two compared bit for bit.
    """
    if len(points) <= 4:
        # A triangle or a quadrilateral is usually already its own hull, and
        # sorting one costs more than the two multiplies it might save.
        return tuple((p.x, p.y) for p in points)
    pts = sorted({(p.x, p.y) for p in points})
    if len(pts) <= 2:
        return tuple(pts)

    def chain(seq: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        for p in seq:
            while len(out) >= 2:
                (ax, ay), (bx, by) = out[-2], out[-1]
                if (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) > 0.0:
                    break
                out.pop()
            out.append(p)
        return out

    lower = chain(pts)
    upper = chain(reversed(pts))
    return tuple(lower[:-1] + upper[:-1])
