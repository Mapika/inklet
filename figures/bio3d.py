"""Atoms and bonds as meshes: the ball-and-stick half of a structure figure.

The cartoon half -- ribbons for helices, arrows for strands, tube for coil --
is `cartoon.py`, which sweeps a real backbone. This module is what draws the
things a cartoon deliberately leaves out: a ligand, a side chain, anything
where the reader is being shown particular atoms rather than a fold.

Nothing here knows what a residue is. It takes points and pairs of indices,
which is all a bond is, and hands back one mesh. Everything is built along
`+z` and placed with a `Mat4`, matching `inklet.three.solids`.
"""

from __future__ import annotations

import math
from typing import Sequence

from inklet.three import Mat4, Mesh, Vec3, merge, solids


def orient(direction: Vec3) -> Mat4:
    """The rotation taking `+z` onto `direction`.

    Every primitive here is built along `+z`, so this is the one piece of
    trigonometry the rest of the module needs. The two degenerate cases --
    already pointing that way, or exactly backwards -- have no rotation axis to
    find, because the cross product of parallel vectors is zero.
    """
    unit = direction.normalized()
    cosine = max(-1.0, min(1.0, unit.z))
    if cosine > 1.0 - 1e-9:
        return Mat4()
    if cosine < -1.0 + 1e-9:
        return Mat4.rotation(Vec3(1.0, 0.0, 0.0), 180.0)
    return Mat4.rotation(Vec3(0.0, 0.0, 1.0).cross(unit),
                         math.degrees(math.acos(cosine)))


def segment(start: Vec3, end: Vec3, radius: float, sides: int = 8) -> Mesh:
    """One capsule-ish length of tube from `start` to `end`."""
    along = end - start
    length = along.length
    if length < 1e-9:
        return Mesh(vertices=(), faces=())
    rod = solids.build("cylinder", radius=radius, height=length, segments=sides)
    middle = (start + end) * 0.5
    return rod.transformed(Mat4.translation(middle) @ orient(along))


def stick(a: Sequence[float], b: Sequence[float], radius: float = 0.1) -> Mesh:
    """One bond, as a thin rod between two atom centres."""
    return segment(Vec3(*a), Vec3(*b), radius, sides=6)


def ball(at: Sequence[float], radius: float = 0.2,
         subdivisions: int = 1) -> Mesh:
    """One atom."""
    return solids.build("sphere", radius=radius,
                        subdivisions=subdivisions).transformed(
        Mat4.translation(Vec3(*at)))


def ball_and_stick(atoms: Sequence[Sequence[float]],
                   bonds: Sequence[tuple[int, int]], *,
                   atom_radius: float = 0.2,
                   bond_radius: float = 0.1) -> Mesh:
    """A small molecule: spheres at the atoms, rods along the bonds."""
    return merge([ball(a, atom_radius) for a in atoms]
                 + [stick(atoms[i], atoms[j], bond_radius) for i, j in bonds])
