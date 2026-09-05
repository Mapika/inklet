"""Where a solid stands, written the way an author thinks about it.

Putting a cylinder on its side and moving it 1.4 units along the stack used to
read as four lines of matrix algebra that say nothing about the assembly:

    turn = Mat4.rotation(Vec3(0.0, 1.0, 0.0), 90.0)
    mesh = build("cylinder", radius=0.11, height=3.0).transformed(turn)
    mesh = mesh.transformed(Mat4.translation(Vec3(1.4, 0.0, 0.0)))
    rod = inklet.model(mesh, ...)

and now reads as the sentence it was always meant to be:

    rod = inklet.solid("cylinder", radius=0.11, height=3.0,
                    spin=("y", 90), at=(1.4, 0, 0))

`Mat4` is still there, and anything this cannot express is still a `transform=`.
What this owns is the *spelling* of the three placements every figure needs --
scale, then turn, then move -- and the argument forms that make each of them
one obvious thing to type.

**Scale, then spin, then move**, which is the order every scene graph uses and
the only one where the numbers mean what they look like: `scale=` is about the
solid's own centre rather than about wherever it has been carried to, and `at=`
is the point the solid's origin lands on rather than a displacement that a
later rotation will swing somewhere else.
"""

from __future__ import annotations

from typing import Any, Sequence

from .linalg import Mat4, Vec3
from .mesh import MeshError

__all__ = ["placement", "as_axis", "AXES"]

#: The named axes `spin=("z", 30)` accepts, each with an optional `-` in front.
#: Spelling an axis rather than typing `Vec3(0, 0, 1)` is worth a table because
#: three quarters of the rotations in a figure are about one of these.
AXES: dict[str, Vec3] = {
    "x": Vec3(1.0, 0.0, 0.0),
    "y": Vec3(0.0, 1.0, 0.0),
    "z": Vec3(0.0, 0.0, 1.0),
}


def as_axis(axis: str | Sequence[float] | Vec3) -> Vec3:
    """`"z"`, `"-x"`, `(0, 1, 0)` or a `Vec3`, as a unit vector."""
    if isinstance(axis, Vec3):
        return _unit(axis)
    if isinstance(axis, str):
        key = axis.strip().lower()
        sign = -1.0 if key.startswith("-") else 1.0
        key = key.lstrip("+-")
        if key not in AXES:
            raise MeshError(
                f"unknown axis {axis!r}; name one of 'x', 'y', 'z' (optionally "
                "with a leading '-') or give a vector")
        return AXES[key] * sign
    values = tuple(axis)
    if len(values) != 3:
        raise MeshError(f"an axis needs three components, got {len(values)}")
    return _unit(Vec3(float(values[0]), float(values[1]), float(values[2])))


def placement(at: Sequence[float] | Vec3 | None = None,
              spin: Any = None,
              scale: float | Sequence[float] | None = None) -> Mat4 | None:
    """The transform `at=`, `spin=` and `scale=` stand for, or None for none.

    `spin` is either three Euler angles in degrees, `(rx, ry, rz)`, applied x
    then y then z; or an `(axis, degrees)` pair, where the axis is `"z"`,
    `"-x"`, a three-vector or a `Vec3`; or a `Mat4` already worked out.
    `scale` is one number or three. `at` is where the solid's own origin ends
    up.

    Returning None rather than the identity is not an optimisation: `model()`
    passes the result straight into `transform=`, and a mesh that is not moved
    should not be walked over to move it by nothing.
    """
    steps: list[Mat4] = []
    if scale is not None:
        steps.append(_scaling(scale))
    if spin is not None:
        steps.append(_rotation(spin))
    if at is not None:
        steps.append(Mat4.translation(_point(at, "at")))
    if not steps:
        return None
    out = steps[-1]
    for step in reversed(steps[:-1]):
        out = out @ step
    return out


def _rotation(spin: Any) -> Mat4:
    """`(rx, ry, rz)`, `(axis, degrees)` or a `Mat4`, as a rotation.

    The two tuple forms are told apart by length, which is unambiguous: three
    numbers is Euler and two items is an axis with an angle. Nothing anyone
    writes is both.
    """
    if isinstance(spin, Mat4):
        return spin
    if isinstance(spin, (int, float)):
        raise MeshError(
            f"spin={spin!r} does not say which axis to turn about; write "
            f"spin=('z', {spin}) or spin=(0, 0, {spin})")
    items = list(spin)
    if len(items) == 2:
        axis, degrees = items
        if isinstance(degrees, (int, float)):
            return Mat4.rotation(as_axis(axis), float(degrees))
        raise MeshError(
            f"spin={spin!r} reads as (axis, degrees) and {degrees!r} is not an "
            "angle; three numbers instead are Euler angles in degrees")
    if len(items) == 3 and all(isinstance(v, (int, float)) for v in items):
        rx, ry, rz = (float(v) for v in items)
        out = Mat4()
        # x, then y, then z: `A @ B` applies B first, so they compose leftward.
        for axis, degrees in (("x", rx), ("y", ry), ("z", rz)):
            if degrees:
                out = Mat4.rotation(AXES[axis], degrees) @ out
        return out
    raise MeshError(
        f"spin={spin!r} is neither three Euler angles in degrees nor an "
        "(axis, degrees) pair")


def _scaling(scale: float | Sequence[float]) -> Mat4:
    if isinstance(scale, (int, float)):
        if scale == 0.0:
            raise MeshError("scale=0 flattens the solid to nothing")
        return Mat4.scaling(float(scale))
    values = tuple(float(v) for v in scale)
    if len(values) != 3:
        raise MeshError(
            f"scale needs one number or three, got {len(values)}")
    if 0.0 in values:
        raise MeshError(f"scale={scale!r} flattens the solid to nothing")
    return Mat4.scaling(*values)


def _point(value: Sequence[float] | Vec3, what: str) -> Vec3:
    if isinstance(value, Vec3):
        return value
    values = tuple(value)
    if len(values) != 3:
        raise MeshError(f"{what} needs three coordinates, got {len(values)}")
    return Vec3(float(values[0]), float(values[1]), float(values[2]))


def _unit(v: Vec3) -> Vec3:
    if v.dot(v) <= 0.0:
        raise MeshError("an axis cannot be the zero vector")
    return v.normalized()
