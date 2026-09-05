"""Three-dimensional points and the affine maps that move them.

`core.geom` stops at two dimensions on purpose -- the diagram tree is flat, and
nothing downstream of a projection has any business knowing about depth. So the
3D half needs its own small vocabulary, and this is it: a `Vec3` that mirrors
`Vec2`'s surface so the two read alike, and a `Mat4` that is affine only.

Affine only is a deliberate restriction. A perspective divide is not a matrix
multiply you want hidden inside an operator: it has a singularity at the eye
plane, and burying it in `Mat4.apply` would let a vertex behind the camera come
back as a plausible-looking finite point. `camera.py` does the divide in the
open, where it can guard the denominator. What lives here is the part that is
always safe -- translation, rotation, scale, and composition of those.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["Vec3", "Mat4", "ORIGIN3", "X_AXIS", "Y_AXIS", "Z_AXIS"]


@dataclass(frozen=True, slots=True)
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other: Vec3) -> Vec3:
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vec3) -> Vec3:
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, k: float) -> Vec3:
        return Vec3(self.x * k, self.y * k, self.z * k)

    __rmul__ = __mul__

    def __neg__(self) -> Vec3:
        return Vec3(-self.x, -self.y, -self.z)

    def dot(self, other: Vec3) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vec3) -> Vec3:
        return Vec3(self.y * other.z - self.z * other.y,
                    self.z * other.x - self.x * other.z,
                    self.x * other.y - self.y * other.x)

    @property
    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalized(self) -> Vec3:
        n = self.length
        if n == 0.0:
            raise ValueError("cannot normalize the zero vector")
        return Vec3(self.x / n, self.y / n, self.z / n)

    def lerp(self, other: Vec3, t: float) -> Vec3:
        return Vec3(self.x + (other.x - self.x) * t,
                    self.y + (other.y - self.y) * t,
                    self.z + (other.z - self.z) * t)

    def min(self, other: Vec3) -> Vec3:
        return Vec3(min(self.x, other.x), min(self.y, other.y), min(self.z, other.z))

    def max(self, other: Vec3) -> Vec3:
        return Vec3(max(self.x, other.x), max(self.y, other.y), max(self.z, other.z))

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


ORIGIN3 = Vec3(0.0, 0.0, 0.0)
X_AXIS = Vec3(1.0, 0.0, 0.0)
Y_AXIS = Vec3(0.0, 1.0, 0.0)
Z_AXIS = Vec3(0.0, 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class Mat4:
    """A 3x4 affine map, written as three rows of four.

    Stored row-major and named after what each number does rather than after a
    matrix index, because the one bug this class exists to prevent is a
    transposed rotation, and `m10` tells you nothing about which way it went.
    """

    ax: float = 1.0
    bx: float = 0.0
    cx: float = 0.0
    dx: float = 0.0
    ay: float = 0.0
    by: float = 1.0
    cy: float = 0.0
    dy: float = 0.0
    az: float = 0.0
    bz: float = 0.0
    cz: float = 1.0
    dz: float = 0.0

    # -- constructors -----------------------------------------------------

    @staticmethod
    def translation(v: Vec3) -> Mat4:
        return Mat4(dx=v.x, dy=v.y, dz=v.z)

    @staticmethod
    def scaling(sx: float, sy: float | None = None, sz: float | None = None) -> Mat4:
        sy = sx if sy is None else sy
        sz = sx if sz is None else sz
        return Mat4(ax=sx, by=sy, cz=sz)

    @staticmethod
    def rotation(axis: Vec3, degrees: float) -> Mat4:
        """Right-handed rotation about an arbitrary axis (Rodrigues)."""
        u = axis.normalized()
        r = math.radians(degrees)
        c, s = math.cos(r), math.sin(r)
        k = 1.0 - c
        return Mat4(
            ax=c + u.x * u.x * k, bx=u.x * u.y * k - u.z * s, cx=u.x * u.z * k + u.y * s,
            ay=u.y * u.x * k + u.z * s, by=c + u.y * u.y * k, cy=u.y * u.z * k - u.x * s,
            az=u.z * u.x * k - u.y * s, bz=u.z * u.y * k + u.x * s, cz=c + u.z * u.z * k,
        )

    @staticmethod
    def basis(x: Vec3, y: Vec3, z: Vec3, origin: Vec3 = ORIGIN3) -> Mat4:
        """The map that sends the unit axes onto these three vectors."""
        return Mat4(ax=x.x, bx=y.x, cx=z.x, dx=origin.x,
                    ay=x.y, by=y.y, cy=z.y, dy=origin.y,
                    az=x.z, bz=y.z, cz=z.z, dz=origin.z)

    # -- use --------------------------------------------------------------

    def apply(self, p: Vec3) -> Vec3:
        return Vec3(self.ax * p.x + self.bx * p.y + self.cx * p.z + self.dx,
                    self.ay * p.x + self.by * p.y + self.cy * p.z + self.dy,
                    self.az * p.x + self.bz * p.y + self.cz * p.z + self.dz)

    def apply_vector(self, v: Vec3) -> Vec3:
        """Directions ignore translation."""
        return Vec3(self.ax * v.x + self.bx * v.y + self.cx * v.z,
                    self.ay * v.x + self.by * v.y + self.cy * v.z,
                    self.az * v.x + self.bz * v.y + self.cz * v.z)

    def __matmul__(self, other: Mat4) -> Mat4:
        """`self @ other` applies `other` first, matching `core.geom.Affine`."""
        x = self.apply_vector(Vec3(other.ax, other.ay, other.az))
        y = self.apply_vector(Vec3(other.bx, other.by, other.bz))
        z = self.apply_vector(Vec3(other.cx, other.cy, other.cz))
        o = self.apply(Vec3(other.dx, other.dy, other.dz))
        return Mat4.basis(x, y, z, o)

    @property
    def determinant(self) -> float:
        return (self.ax * (self.by * self.cz - self.cy * self.bz)
                - self.bx * (self.ay * self.cz - self.cy * self.az)
                + self.cx * (self.ay * self.bz - self.by * self.az))

    @property
    def is_identity(self) -> bool:
        return self == IDENTITY4

    def normal_matrix_apply(self, n: Vec3) -> Vec3:
        """Transform a surface normal.

        Normals ride the inverse transpose, not the matrix itself: under a
        non-uniform scale the plain map tilts them off the surface. Uniform
        scales and rotations make this identical to `apply_vector`, so the cost
        is only paid where it is needed.
        """
        det = self.determinant
        if abs(det) < 1e-15:
            raise ValueError("a singular transform has no normal matrix")
        # Adjugate divided by the determinant, then transposed -- written out
        # rather than composed from two helpers because this is a hot loop.
        c00 = self.by * self.cz - self.cy * self.bz
        c01 = self.cy * self.az - self.ay * self.cz
        c02 = self.ay * self.bz - self.by * self.az
        c10 = self.cx * self.bz - self.bx * self.cz
        c11 = self.ax * self.cz - self.cx * self.az
        c12 = self.bx * self.az - self.ax * self.bz
        c20 = self.bx * self.cy - self.cx * self.by
        c21 = self.cx * self.ay - self.ax * self.cy
        c22 = self.ax * self.by - self.bx * self.ay
        return Vec3((c00 * n.x + c10 * n.y + c20 * n.z) / det,
                    (c01 * n.x + c11 * n.y + c21 * n.z) / det,
                    (c02 * n.x + c12 * n.y + c22 * n.z) / det)


IDENTITY4 = Mat4()
