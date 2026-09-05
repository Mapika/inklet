"""Points, affine maps and axis-aligned boxes.

Y grows downward, matching SVG and PDF-after-flip. Compass anchors compensate,
so "north" is -y. Picking the renderer's convention here removes a whole family
of sign bugs at the cost of one surprising constant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, k: float) -> Vec2:
        return Vec2(self.x * k, self.y * k)

    __rmul__ = __mul__

    def __neg__(self) -> Vec2:
        return Vec2(-self.x, -self.y)

    def dot(self, other: Vec2) -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: Vec2) -> float:
        return self.x * other.y - self.y * other.x

    @property
    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> Vec2:
        n = self.length
        if n == 0.0:
            raise ValueError("cannot normalize the zero vector")
        return Vec2(self.x / n, self.y / n)

    def perp(self) -> Vec2:
        """Rotated a quarter turn. Used for arrow heads and label offsets."""
        return Vec2(-self.y, self.x)

    def angle(self) -> float:
        return math.degrees(math.atan2(self.y, self.x))


ORIGIN = Vec2(0.0, 0.0)
EAST = Vec2(1.0, 0.0)
WEST = Vec2(-1.0, 0.0)
SOUTH = Vec2(0.0, 1.0)
NORTH = Vec2(0.0, -1.0)


@dataclass(frozen=True, slots=True)
class Affine:
    """SVG's matrix(a b c d e f): x' = a*x + c*y + e, y' = b*x + d*y + f."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    @staticmethod
    def translation(dx: float, dy: float) -> Affine:
        return Affine(e=dx, f=dy)

    @staticmethod
    def scaling(sx: float, sy: float | None = None) -> Affine:
        return Affine(a=sx, d=sx if sy is None else sy)

    @staticmethod
    def rotation(degrees: float) -> Affine:
        r = math.radians(degrees)
        cos, sin = math.cos(r), math.sin(r)
        return Affine(a=cos, b=sin, c=-sin, d=cos)

    def __matmul__(self, other: Affine) -> Affine:
        """self @ other applies `other` first, then `self`."""
        return Affine(
            a=self.a * other.a + self.c * other.b,
            b=self.b * other.a + self.d * other.b,
            c=self.a * other.c + self.c * other.d,
            d=self.b * other.c + self.d * other.d,
            e=self.a * other.e + self.c * other.f + self.e,
            f=self.b * other.e + self.d * other.f + self.f,
        )

    def apply(self, p: Vec2) -> Vec2:
        return Vec2(self.a * p.x + self.c * p.y + self.e,
                    self.b * p.x + self.d * p.y + self.f)

    def apply_vector(self, v: Vec2) -> Vec2:
        """Directions ignore translation."""
        return Vec2(self.a * v.x + self.c * v.y, self.b * v.x + self.d * v.y)

    def transpose_linear(self, v: Vec2) -> Vec2:
        """Apply the transpose of the linear part. This is what pulls a query
        direction back through a transform when evaluating an envelope."""
        return Vec2(self.a * v.x + self.b * v.y, self.c * v.x + self.d * v.y)

    @property
    def determinant(self) -> float:
        return self.a * self.d - self.b * self.c

    def inverse(self) -> Affine:
        det = self.determinant
        if abs(det) < 1e-12:
            raise ValueError("singular transform has no inverse")
        ia, ib = self.d / det, -self.b / det
        ic, id_ = -self.c / det, self.a / det
        return Affine(
            a=ia, b=ib, c=ic, d=id_,
            e=-(ia * self.e + ic * self.f),
            f=-(ib * self.e + id_ * self.f),
        )

    @property
    def is_identity(self) -> bool:
        return (self.a, self.b, self.c, self.d, self.e, self.f) == (1, 0, 0, 1, 0, 0)

    def uniform_scale(self) -> float:
        """Geometric mean scale factor, for keeping stroke widths honest."""
        return math.sqrt(abs(self.determinant)) or 1.0


IDENTITY = Affine()


@dataclass(frozen=True, slots=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @staticmethod
    def from_size(width: float, height: float, center: Vec2 = ORIGIN) -> Rect:
        return Rect(center.x - width / 2, center.y - height / 2,
                    center.x + width / 2, center.y + height / 2)

    @staticmethod
    def hull(points) -> Rect:
        pts = list(points)
        if not pts:
            raise ValueError("no points")
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        return Rect(min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def center(self) -> Vec2:
        return Vec2((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    @property
    def corners(self) -> tuple[Vec2, Vec2, Vec2, Vec2]:
        return (Vec2(self.x0, self.y0), Vec2(self.x1, self.y0),
                Vec2(self.x1, self.y1), Vec2(self.x0, self.y1))

    def union(self, other: Rect) -> Rect:
        return Rect(min(self.x0, other.x0), min(self.y0, other.y0),
                    max(self.x1, other.x1), max(self.y1, other.y1))

    def pad(self, top: float, right: float | None = None,
            bottom: float | None = None, left: float | None = None) -> Rect:
        """CSS shorthand order."""
        right = top if right is None else right
        bottom = top if bottom is None else bottom
        left = right if left is None else left
        return Rect(self.x0 - left, self.y0 - top, self.x1 + right, self.y1 + bottom)

    def overlap(self, other: Rect) -> Rect | None:
        r = Rect(max(self.x0, other.x0), max(self.y0, other.y0),
                 min(self.x1, other.x1), min(self.y1, other.y1))
        return r if r.width > 0 and r.height > 0 else None

    def contains(self, p: Vec2) -> bool:
        return self.x0 <= p.x <= self.x1 and self.y0 <= p.y <= self.y1

    def transform(self, t: Affine) -> Rect:
        """Bounds of the transformed corners, which is only tight for axis-aligned maps."""
        return Rect.hull(t.apply(c) for c in self.corners)
