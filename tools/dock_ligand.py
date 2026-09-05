"""Find a pose for the invented compound in the real kinase pocket.

`figures/target.py` draws a compound that does not exist inside a protein that
does. Putting the two together by hand and then printing hydrogen-bond
distances beside them would be asserting a result rather than showing one, so
the pose is not hand-placed: it is the minimum of a score written down here,
and the score is three hydrogen bonds at textbook length plus a penalty for
sitting inside the protein.

    .venv/bin/python tools/dock_ligand.py

It prints a 4x4 matrix to paste into `target.LIGAND_PLACEMENT` and the contact
distances it achieved. `target.contacts()` re-measures those distances from the
checked-in matrix and the real coordinates every time the figure is built, so
a matrix that drifts from the numbers beside it fails a test rather than
quietly mislabelling the picture.

This is a search over six degrees of freedom, not a docking program. It has no
force field, no conformational freedom, and no solvation -- the ligand is a
rigid planar sketch. What it buys is that the pose is *reproducible from a
stated objective*, which is the only claim the figure makes about it.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "figures"))

import pdbfile as pdbio                                          # noqa: E402
import target                                                # noqa: E402
from inklet.three.linalg import Mat4, Vec3                      # noqa: E402

#: The objective lives beside the compound it is about, in `target`, so that
#: what the pose was asked for and what the figure prints beside it cannot end
#: up in two files saying two things.
RESTRAINTS = target.RESTRAINTS

#: No heavy atom of the ligand closer than this to a heavy atom of the protein,
#: except the hydrogen-bond partners themselves. Two carbons at 3.4 A are in
#: van der Waals contact, which is what a bound ligand is; the penalty is soft
#: below it because the compound here is a flat sketch with no rotatable bonds,
#: and a rigid sketch that has to clear a real pocket everywhere would have to
#: sit outside it.
CLEARANCE = 3.25
#: Protein atoms further than this from the pocket cannot be reached and are
#: not worth measuring against.
NEIGHBOURHOOD = 14.0

WEIGHT_BOND, WEIGHT_CLASH, WEIGHT_HOME = 8.0, 5.0, 0.02


def _neighbourhood(structure: pdbio.Structure, centre: Vec3
                   ) -> list[tuple[Vec3, bool]]:
    """Protein heavy atoms near the pocket, flagged if they are a partner."""
    partners = {(name, atom) for name, atom, _, _ in RESTRAINTS}
    out = []
    for residue in structure.residues:
        for atom, point in residue.atoms.items():
            if (point - centre).length <= NEIGHBOURHOOD:
                out.append((point, (residue.label, atom) in partners))
    return out


def _score(world: list[Vec3], named: dict[str, int], targets: list[Vec3],
           near: list[tuple[Vec3, bool]], home: Vec3) -> float:
    total = 0.0
    for (_, _, atom, ideal), point in zip(RESTRAINTS, targets):
        gap = (world[named[atom]] - point).length - ideal
        total += WEIGHT_BOND * gap * gap
    for point in world:
        for other, partner in near:
            if partner:
                continue
            over = CLEARANCE - (point - other).length
            if over > 0.0:
                total += WEIGHT_CLASH * over * over
    middle = sum(world, Vec3()) * (1.0 / len(world))
    return total + WEIGHT_HOME * (middle - home).length ** 2


def _pose(base: Mat4, shift: Vec3, spin: tuple[float, float, float],
          home: Vec3) -> Mat4:
    """A rigid move, applied about the pocket rather than about the origin."""
    turn = (Mat4.rotation(Vec3(0.0, 0.0, 1.0), spin[2])
            @ Mat4.rotation(Vec3(0.0, 1.0, 0.0), spin[1])
            @ Mat4.rotation(Vec3(1.0, 0.0, 0.0), spin[0]))
    return (Mat4.translation(home + shift) @ turn
            @ Mat4.translation(home * -1.0) @ base)


def _ideal_points(structure: pdbio.Structure, home: Vec3) -> list[Vec3]:
    """Where each restrained ligand atom would sit if its bond were perfect.

    On the line from its protein partner towards the middle of the pocket, at
    the distance the restraint asks for. Three of them define the pose the
    chemistry wants, before anything is asked about whether the rest of the
    molecule fits around it.
    """
    out = []
    for name, atom, _, ideal in RESTRAINTS:
        point = structure[int(name[3:])].atoms[atom]
        out.append(point + (home - point).normalized() * ideal)
    return out


def _frame(a: Vec3, b: Vec3, c: Vec3, flip: bool) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    """An orthonormal frame on three points, and their centroid."""
    u = (b - a).normalized()
    v = c - a
    v = (v - u * v.dot(u))
    v = v.normalized() if v.length > 1e-9 else u.cross(Vec3(0.0, 0.0, 1.0))
    w = u.cross(v)
    return u, v, (w * -1.0 if flip else w), (a + b + c) * (1.0 / 3.0)


def _seed(local: list[Vec3], named: dict[str, int], targets: list[Vec3],
          flip: bool) -> Mat4:
    """The rigid move taking the three restrained atoms onto their ideal spots.

    Frame to frame rather than a least-squares fit: with exactly three
    correspondences the two constructions agree to within the difference
    between the triangles, and this one needs no eigen-decomposition. `flip`
    turns the flat molecule over, which is a second pose the restraints cannot
    tell apart and the pocket very much can.
    """
    here = [local[named[name]] for _, _, name, _ in RESTRAINTS]
    lu, lv, lw, lc = _frame(*here, flip)
    tu, tv, tw, tc = _frame(*targets, False)
    turn = Mat4(ax=tu.x, bx=tv.x, cx=tw.x,
                ay=tu.y, by=tv.y, cy=tw.y,
                az=tu.z, bz=tv.z, cz=tw.z) @ Mat4(
        ax=lu.x, bx=lu.y, cx=lu.z,
        ay=lv.x, by=lv.y, cy=lv.z,
        az=lw.x, bz=lw.y, cz=lw.z)
    return Mat4.translation(tc) @ turn @ Mat4.translation(lc * -1.0)


def dock(structure: pdbio.Structure) -> tuple[Mat4, float]:
    """Refine the pose the restraints imply until the molecule also fits.

    Two kinds of starting point. The restraints alone determine a pose up to
    turning the flat molecule over, and that pose is where the chemistry says
    the compound goes; the principal axes of the inhibitor that was really in
    this pocket say which way round something flat sits in it. Both are tried,
    because the first ignores the walls and the second ignores the bonds, and
    the answer has to satisfy both.

    The refinement is a shrinking random walk with a fixed seed -- crude, but
    six degrees of freedom starting from a good guess is a small enough problem
    that crude converges, and a fixed seed means the figure is the same every
    time it is built.
    """
    home = structure.ligands[0].centre
    near = _neighbourhood(structure, home)
    targets = [structure[int(name[3:])].atoms[atom]
               for name, atom, _, _ in RESTRAINTS]
    local = target.skeleton_3d()
    _, _, named = target.skeleton()
    ideal = _ideal_points(structure, home)

    starts = [_seed(local, named, ideal, flip) for flip in (False, True)]
    starts += _starts(structure, home)

    best: tuple[float, Mat4] | None = None
    for index, base in enumerate(starts):
        for attempt in range(3):
            rng = random.Random(20260823 + 101 * index + attempt)
            shift = Vec3(*(rng.gauss(0, 0.6 * attempt) for _ in range(3)))
            spin = tuple(rng.gauss(0, 9.0 * attempt) for _ in range(3))
            placed = _pose(base, shift, spin, home)
            score = _score([placed.apply(q) for q in local], named, targets,
                           near, home)
            step = 1.5
            while step > 0.01:
                improved = False
                for _ in range(90):
                    move = Vec3(rng.gauss(0, step), rng.gauss(0, step),
                                rng.gauss(0, step)) * 0.5
                    turn = tuple(rng.gauss(0, step * 10.0) for _ in range(3))
                    trial = _pose(base, shift + move,
                                  tuple(a + b for a, b in zip(spin, turn)),
                                  home)
                    value = _score([trial.apply(q) for q in local], named,
                                   targets, near, home)
                    if value < score:
                        score, placed = value, trial
                        shift = shift + move
                        spin = tuple(a + b for a, b in zip(spin, turn))
                        improved = True
                if not improved:
                    step *= 0.55
            if best is None or score < best[0]:
                best = (score, placed)
                print(f"# start {index} attempt {attempt}: {score:.3f}",
                      file=sys.stderr)
    return best[1], best[0]


def _starts(structure: pdbio.Structure, home: Vec3) -> list[Mat4]:
    """The four right-handed frames built on the crystal ligand's own axes."""
    points = list(structure.ligands[0].atoms.values())

    def spread(direction: Vec3) -> Vec3:
        out = Vec3()
        for point in points:
            offset = point - home
            out = out + offset * offset.dot(direction)
        return out * (1.0 / len(points))

    def principal(*without: Vec3) -> Vec3:
        axis = Vec3(0.31, 0.57, 0.76).normalized()
        for _ in range(300):
            found = spread(axis)
            for taken in without:
                found = found - taken * found.dot(taken)
            if found.length < 1e-12:
                break
            axis = found.normalized()
        return axis

    long_axis = principal()
    mid_axis = principal(long_axis)
    out = []
    for sx in (1.0, -1.0):
        for sy in (1.0, -1.0):
            u, v = long_axis * sx, mid_axis * sy
            w = u.cross(v)
            out.append(Mat4.translation(home) @ Mat4(
                ax=u.x, bx=v.x, cx=w.x,
                ay=u.y, by=v.y, cy=w.y,
                az=u.z, bz=v.z, cz=w.z))
    return out


if __name__ == "__main__":
    structure = target.structure()
    matrix, score = dock(structure)
    print(f"# score {score:.3f}")
    print("LIGAND_PLACEMENT = Mat4(")
    for row in "xyz":
        print("    " + ", ".join(
            f"{axis}{row}={getattr(matrix, axis + row):.6f}"
            for axis in "abcd") + ",")
    print(")")
    world = [matrix.apply(q) for q in target.skeleton_3d()]
    _, _, named = target.skeleton()
    print("\n# contacts")
    for name, atom, ligand_atom, ideal in RESTRAINTS:
        point = structure[int(name[3:])].atoms[atom]
        got = (world[named[ligand_atom]] - point).length
        print(f"#   {name} {atom:4s} - {ligand_atom:12s} {got:.2f} A "
              f"(asked {ideal:.2f})")
    worst = min(((point - other).length, other)
                for point in world
                for other, partner in _neighbourhood(structure,
                                                     structure.ligands[0].centre)
                if not partner)
    print(f"# closest non-partner approach {worst[0]:.2f} A "
          f"(clearance {CLEARANCE:.2f})")
