"""The structure the rest of the figure is about: a real kinase, a made-up drug.

Panels (a) and (b) are the same object at two magnifications, so the geometry
lives here once. A zoom that is redrawn rather than re-photographed is not a
zoom, and the reader has no way to tell.

**What is real and what is not.** The protein is the EGFR tyrosine kinase
domain from PDB entry 1M17, at 2.6 A, stripped to what the figure draws by
`tools/strip_pdb.py` and kept in `data/`. Every backbone coordinate, every
secondary-structure assignment and every side chain in the zoom is that
deposited structure and nothing else. The compound is invented -- there is no
DGM-431 -- and so is every number in panels (d) to (g). The caption says so.

The entry was chosen because it is a kinase with an inhibitor in the ATP site,
so the pocket the figure talks about is a pocket something really binds in.
That inhibitor is erlotinib. It is not drawn, not named in the figure, and its
coordinates are used for exactly two things: the centroid of its atoms defines
where the pocket is, and the principal axes of its atoms give
`tools/dock_ligand.py` its starting orientations. Drawing a real approved drug
beside invented trial results is the one thing this figure must not do.

**The pose is derived, not asserted.** `LIGAND_PLACEMENT` below is not a matrix
somebody tuned until the picture looked right: it is the minimum of the score
in `tools/dock_ligand.py` -- three hydrogen bonds at textbook length, and a
penalty for occupying the same space as the protein. `contacts()` re-measures
those bonds from this matrix and the deposited coordinates every time the
figure is built, so the numbers printed beside the dashes cannot drift away
from the geometry that produced them.
"""

from __future__ import annotations

import functools
import math
from pathlib import Path

from inklet.three import Mat4, Mesh, Vec3, merge

import cartoon
import pdbfile as pdbio
from bio3d import ball_and_stick

DATA = Path(__file__).resolve().parent / "data" / "1m17-kinase.pdb"

#: The entry runs from 672 to 995. The kinase domain proper is the beta sheet
#: and aC of the N lobe, the helical C lobe, and the cleft between them: 688 to
#: 958. Before it is a disordered arm and after it a C-terminal tail that
#: wanders off across a third of the frame, neither of which the figure is
#: about and both of which cost the fold the space it needs to be legible.
DOMAIN = (688, 958)

#: The residues panel (b) draws side chains for, and what each one is called in
#: a kinase paper. All three line the ATP site in the deposited structure.
POCKET_RESIDUES = {
    769: "hinge",          # Met769: the backbone amide every inhibitor reads
    767: "hinge",          # Gln767: its partner two residues back
    766: "gatekeeper",     # Thr766: what decides how big a substituent fits
    721: "catalytic",      # Lys721: the lysine that holds the phosphates
}


@functools.cache
def structure() -> pdbio.Structure:
    """The deposited chain, trimmed to the kinase domain. Read once."""
    whole = pdbio.load(DATA)
    kept = tuple(residue for residue in whole.residues
                 if DOMAIN[0] <= residue.number <= DOMAIN[1])
    return pdbio.Structure(whole.title, whole.entry, kept, whole.ligands,
                           {residue.number: residue for residue in kept})


def pocket() -> Vec3:
    """Where the ligand sits, and therefore what both panels are aimed at.

    The centroid of the inhibitor in the crystal. Using an occupied site rather
    than a guess at one is the difference between "the ATP pocket" and "a dent
    in the surface that photographs well".
    """
    return structure().ligands[0].centre


# --- the ligand ------------------------------------------------------------
#
# A hinge-binding inhibitor of the usual shape: a fused bicyclic head that
# reads the hinge, an amide linker, an aryl tail into the back pocket, and a
# solubilising ring hanging off the front. Laid out flat, because a small
# molecule of this kind very nearly is flat, and because panel (c) draws the
# same skeleton as a structural formula -- one layout, two uses, so the
# structure drawn and the structure bound cannot disagree.

#: Angstroms per unit of the skeleton below, which is laid out on a hexagonal
#: grid of unit edge. A carbon-carbon bond is 1.39 A in an aromatic ring and
#: 1.54 A between two sp3 carbons; one number for all of them has to sit
#: between. It is not a free parameter chosen to make the molecule fit: at this
#: scale the compound spans 14.8 A, and the inhibitor crystallised in this
#: pocket spans 15.6, which is the check that it is the right size for the
#: cleft rather than a schematic scaled to taste.
BOND = 1.45


def _hex(centre: tuple[float, float], phase: float = 0.0,
         radius: float = 1.0) -> list[tuple[float, float]]:
    """Six points on a circle, which is a ring bond length on every edge."""
    return [(centre[0] + radius * math.cos(phase + k * math.pi / 3),
             centre[1] + radius * math.sin(phase + k * math.pi / 3))
            for k in range(6)]


def skeleton() -> tuple[list[tuple[float, float]],
                        list[tuple[int, int, int, tuple[float, float] | None]],
                        dict[str, int]]:
    """The molecule in its own plane.

    Returns the atoms, the bonds as `(a, b, order, inner)`, and the index of
    every atom worth naming. `inner` is the point a second line should lean
    towards for a ring double bond, and `None` for one that should be drawn as
    two parallel lines -- a carbonyl.

    Laid out by hand on a hexagonal grid rather than generated from a rule. A
    structural formula is read as a claim about a real compound: every ring has
    to close, every bond has to be one length, and nothing may cross anything
    else. The generated version of this did none of the three -- it left rings
    open, overlapped the morpholine with the pyrimidine, and drew two bonds
    through each other -- and no rule in the library can see any of that,
    because to the linter it is one path node with a correct bounding box.

    A 2-aminopyrimidine at the hinge, an amide linker, a para-chlorophenyl in
    the back pocket and a morpholine out to solvent: the four pieces every
    written-up kinase inhibitor cartoon has, in the order they sit in the
    cleft.
    """
    atoms: list[tuple[float, float]] = []
    bonds: list[tuple[int, int, int, tuple[float, float] | None]] = []

    def place(points):
        first = len(atoms)
        atoms.extend(points)
        return list(range(first, len(atoms)))

    def close(made, centre, doubles=()):
        for k, index in enumerate(made):
            bonds.append((index, made[(k + 1) % len(made)],
                          2 if k in doubles else 1, centre))

    # Out to solvent: morpholine, N on the ring, O across from it.
    morpholine = place(_hex((-4.0, 0.0)))
    close(morpholine, (-4.0, 0.0))

    # At the hinge: the aminopyrimidine, Kekule so the ring reads aromatic.
    pyrimidine = place(_hex((-1.0, 0.0)))
    close(pyrimidine, (-1.0, 0.0), doubles=(0, 2, 4))
    bonds.append((pyrimidine[3], morpholine[0], 1, None))

    amide_n = place([(0.866, 0.5)])[0]
    carbonyl = place([(1.732, 0.0)])[0]
    carbonyl_o = place([(1.732, -1.0)])[0]
    bonds.append((pyrimidine[0], amide_n, 1, None))
    bonds.append((amide_n, carbonyl, 1, None))
    bonds.append((carbonyl, carbonyl_o, 2, None))

    # Into the back pocket: para-chlorophenyl.
    phenyl = place(_hex((3.464, 1.0), phase=math.pi * 7 / 6))
    close(phenyl, (3.464, 1.0), doubles=(0, 2, 4))
    bonds.append((carbonyl, phenyl[0], 1, None))
    halogen = place([(5.196, 2.0)])[0]
    bonds.append((phenyl[3], halogen, 1, None))

    named = {"hinge-n": pyrimidine[2], "ring-n": pyrimidine[4],
             "amide-n": amide_n, "carbonyl-o": carbonyl_o, "halogen": halogen,
             "morpholine-n": morpholine[0], "morpholine-o": morpholine[3]}
    return atoms, bonds, named


#: What every named atom of `skeleton()` is; everything else is carbon, and
#: every hydrogen is implied by what is left of the atom's valence. Panel (c)
#: letters its atoms from this and `formula` counts them from it, so the
#: drawing and the molecular formula beside it cannot come to disagree.
ELEMENTS = {"hinge-n": "N", "ring-n": "N", "amide-n": "N", "carbonyl-o": "O",
            "halogen": "Cl", "morpholine-n": "N", "morpholine-o": "O"}
VALENCE = {"C": 4, "N": 3, "O": 2, "Cl": 1}
WEIGHTS = {"C": 12.011, "H": 1.008, "N": 14.007, "O": 15.999, "Cl": 35.45}


def composition() -> dict[str, int]:
    """How many of each element the drawn skeleton adds up to.

    Hydrogens are not drawn -- a structural formula never draws them -- so
    they are counted rather than read: whatever is left of each atom's valence
    once its drawn bonds are taken off it. That makes the count a property of
    the picture, which is the only way a formula printed beside a structure
    can be checked at all.
    """
    atoms, bonds, named = skeleton()
    kind = ["C"] * len(atoms)
    for name, element in ELEMENTS.items():
        kind[named[name]] = element
    used = [0] * len(atoms)
    for a, b, order, _ in bonds:
        used[a] += order
        used[b] += order
    counted: dict[str, int] = {}
    for index, element in enumerate(kind):
        counted[element] = counted.get(element, 0) + 1
        spare = VALENCE[element] - used[index]
        if spare > 0:
            counted["H"] = counted.get("H", 0) + spare
    return counted


def formula() -> str:
    """The molecular formula in Hill order: carbon, hydrogen, then the rest,
    with the counts as `inklet.text` subscripts."""
    counted = composition()
    rest = sorted(k for k in counted if k not in ("C", "H"))
    return "".join(f"{element}_{{{counted[element]}}}" if counted[element] > 1
                   else element
                   for element in ["C", "H"] + rest if element in counted)


def mass() -> float:
    """Molecular weight, from the same count."""
    return sum(WEIGHTS[element] * n for element, n in composition().items())


def skeleton_3d() -> list[Vec3]:
    """The skeleton in angstroms, centred, lying in its own xy plane."""
    flat, _, _ = skeleton()
    mid_x = sum(p[0] for p in flat) / len(flat)
    mid_y = sum(p[1] for p in flat) / len(flat)
    return [Vec3((p[0] - mid_x) * BOND, (p[1] - mid_y) * BOND, 0.0)
            for p in flat]


#: Written by `tools/dock_ligand.py`. See the module docstring: this is the
#: minimum of a stated score, and `contacts()` re-measures what it achieved.
LIGAND_PLACEMENT = Mat4(
    ax=0.789118, bx=-0.570434, cx=0.227810, dx=22.747040,
    ay=-0.045263, by=-0.423874, cy=-0.904590, dy=-1.087598,
    az=0.612572, bz=0.703517, cz=-0.360306, dz=55.518764,
)


def ligand_atoms() -> list[Vec3]:
    """Every atom of the compound, where it ends up in the pocket."""
    return [LIGAND_PLACEMENT.apply(point) for point in skeleton_3d()]


def ligand_atom(name: str) -> Vec3:
    """One named atom, for an H-bond or a leader to point at."""
    _, _, named = skeleton()
    return ligand_atoms()[named[name]]


def ligand() -> Mesh:
    """The compound as balls and sticks, in the pocket."""
    _, bonds, _ = skeleton()
    atoms = [(v.x, v.y, v.z) for v in ligand_atoms()]
    return ball_and_stick(atoms, [(a, b) for a, b, _, _ in bonds],
                          atom_radius=0.45, bond_radius=0.22)


# --- what the zoom is about ------------------------------------------------

#: Which ligand atom should hydrogen-bond to which protein atom, and at what
#: distance. The first is the hinge bond every inhibitor of this class makes;
#: the second is its partner on the same strap two residues back, which is what
#: makes an aminopyrimidine a hinge binder rather than a ring near a hinge; the
#: third is the gatekeeper threonine at the back of the adenine pocket.
#:
#: `tools/dock_ligand.py` reads these as the objective it minimises. They are
#: what the pose was asked for; `contacts()` reports what it got.
RESTRAINTS = (
    ("Met769", "N", "hinge-n", 2.90),
    ("Gln767", "O", "amide-n", 3.00),
    ("Thr766", "OG1", "carbonyl-o", 3.00),
)


def contacts() -> list[tuple[str, Vec3, Vec3, float]]:
    """The hydrogen bonds, measured rather than quoted.

    Returns the residue's name, the protein end and the ligand end -- both in
    the frame `orientation()` draws in, so they can be handed straight to an
    anchor -- and the distance between them in angstroms, measured in the
    deposited frame where an angstrom is an angstrom. `tools/dock_ligand.py` asked for these three at 2.9,
    3.0 and 3.0 A; what it got is whatever this says, and what this says is
    what the labels print.
    """
    here = structure()
    out = []
    for name, atom, ligand_name, _ in RESTRAINTS:
        point = here[int(name[3:])].atoms[atom]
        tip = ligand_atom(ligand_name)
        out.append((name, upright(point), upright(tip), (tip - point).length))
    return out


#: What each atom of a side chain hangs off, first present parent wins. A
#: methionine's CE is on its sulphur and a lysine's is two carbons back, which
#: is why these are candidate lists and not a single name.
PARENT = {
    "CA": ("N",), "C": ("CA",), "O": ("C",),
    "CB": ("CA",), "CG": ("CB",), "CG1": ("CB",), "CG2": ("CB",),
    "OG": ("CB",), "OG1": ("CB",), "SG": ("CB",),
    "SD": ("CG",), "CD": ("CG",), "CD1": ("CG", "CG1"), "CD2": ("CG",),
    "OD1": ("CG",), "ND2": ("CG",),
    "CE": ("SD", "CD"), "NE2": ("CD",), "OE1": ("CD",),
    "NZ": ("CE",),
}

#: The order atoms are laid down in, so a parent is always already placed.
ORDER = ("N", "CA", "C", "O", "CB", "OG", "OG1", "SG", "CG", "CG1", "CG2",
         "SD", "CD", "CD1", "CD2", "OD1", "ND2", "CE", "NE2", "OE1", "NZ")


def side_chains() -> Mesh:
    """The pocket residues, drawn from their deposited coordinates.

    Real side chains rather than stubs pointing the right way. They are in the
    scene at both magnifications -- at panel (a)'s scale a few specks near the
    cleft, at panel (b)'s the contacts the caption talks about. Drawing them
    only in the zoom would make the zoom a different object from the picture it
    claims to enlarge.

    The backbone N, CA, C and O go in as well as the side chain proper, and
    not for completeness: two of the three hydrogen bonds in `RESTRAINTS` are
    made by *backbone* atoms, because that is what a hinge is. Leaving them out
    drew a dashed bond from a ligand atom to a point where nothing was drawn.
    """
    here = structure()
    made = []
    for number in POCKET_RESIDUES:
        residue = here[number]
        order = [name for name in ORDER if name in residue.atoms]
        where = {name: index for index, name in enumerate(order)}
        atoms = [(residue.atoms[name].x, residue.atoms[name].y,
                  residue.atoms[name].z) for name in order]
        bonds = []
        for name in order:
            parent = next((p for p in PARENT.get(name, ()) if p in where), None)
            if parent is not None:
                bonds.append((where[parent], where[name]))
        made.append(ball_and_stick(atoms, bonds,
                                   atom_radius=0.34, bond_radius=0.17))
    return merge(made)


#: The run of residues each label in panel (a) names, and what a kinase paper
#: calls it. Runs, not points: which residue of a run a leader should touch
#: depends on where the camera is, and `label_runs` hands the whole run over
#: so that `inklet.three.anchor3d(pick="visible")` can work it out.
FEATURES = {
    "sheet": (716, 722),            # b3, the strand carrying Lys721
    "helix-c": (728, 743),          # aC
    "p-loop": (695, 700),           # the glycine-rich loop over the cleft
    "hinge": (767, 771),
    "activation-loop": (831, 845),
    "c-lobe": (936, 954),           # aF, the long helix down the middle of it
    "n-lobe": (688, 707),
}


def label_runs() -> dict[str, list[tuple[float, float, float]]]:
    """The candidate points for each label, in the frame the figure draws.

    Every alpha carbon of the run, not one of them, because *which* one a
    leader should touch is not a property of the feature -- it depends on
    where the camera is standing and on what else the fold puts in front of
    it. That choice belongs to `inklet.three.anchor3d(pick="visible")`, which
    can see the drawing; this only says what the candidates are.

    This used to pick the nearest residue here, by hand, with the camera
    passed in. That was better than the centroid -- a centroid is *inside* the
    feature, so the feature's own front surface hides it -- and it was still
    wrong twice on this fold: the b3 strand's nearest residue is behind the
    ribbon in front of it, and helix aC's is out in mid-air, because a spline
    through alpha carbons cuts the corners the atoms sit on.
    """
    here = structure()

    def run(first: int, last: int) -> list[tuple[float, float, float]]:
        return [upright(here[n].ca)
                for n in range(first, last + 1) if here.get(n)]

    points = {name: run(*where) for name, where in FEATURES.items()}
    # The compound's own centroid, not `pocket()`. The two are close but not
    # the same -- the pocket is where the crystal's inhibitor sat, the compound
    # is where the docking put ours -- and everything that uses this point is
    # about the compound: the ring in panel (a) is drawn round it and the crop
    # in panel (b) is centred on it, so an offset of a couple of angstroms is
    # an offset of several millimetres at the magnification (b) is drawn at.
    atoms = ligand_atoms()
    points["ligand"] = [upright(sum(atoms, Vec3()) * (1.0 / len(atoms)))]
    return points


# --- which way up ----------------------------------------------------------

def orientation() -> Mat4:
    """The rotation that stands the kinase up the way a paper draws it.

    A crystal frame is whatever the crystallographer's unit cell happened to
    be, so a raw PDB entry drawn at any fixed camera angle lands in an
    arbitrary pose -- and turning the camera until it looks right is a number
    nobody can check and that changes the moment the entry does. Two facts
    about the molecule fix it instead:

    the **N lobe goes above the C lobe**, because that is how every kinase in
    every paper is drawn, and the **cleft faces the reader**, because the cleft
    is what the figure is about. The first gives the up axis, the second gives
    the axis out of the page, and the third follows.

    y is negative towards the viewer in this library's camera, which is worth
    stating because getting it backwards is invisible in the numbers and
    obvious in the picture: the ligand ends up behind the protein.
    """
    here = structure()

    def middle(first: int, last: int) -> Vec3:
        run = [here[n].ca for n in range(first, last + 1) if here.get(n)]
        return sum(run, Vec3()) * (1.0 / len(run))

    up = (middle(688, 743) - middle(773, 954)).normalized()      # N lobe up
    out = pocket() - (middle(688, 743) + middle(773, 954)) * 0.5
    out = (out - up * out.dot(up)).normalized()                  # cleft forward
    across = up.cross(out)
    turn = Mat4(ax=across.x, bx=across.y, cx=across.z,
                ay=-out.x, by=-out.y, cy=-out.z,
                az=up.x, bz=up.y, cz=up.z)
    return turn @ Mat4.translation(pocket() * -1.0)


def upright(point: Vec3) -> tuple[float, float, float]:
    """A point of the deposited structure, in the frame the figure draws."""
    moved = orientation().apply(point)
    return (moved.x, moved.y, moved.z)


# --- the mesh --------------------------------------------------------------

#: Face-group names, which is what `inklet.three.model(colors=)` is keyed on.
GROUPS = ("helix", "strand", "coil", "ligand", "side-chain")


@functools.cache
def fold(*, with_ligand: bool = True, sides: int = cartoon.SIDES) -> Mesh:
    """The whole subject as one mesh, its parts told apart by face group.

    One mesh, not one part per colour. Parts are painted whole, furthest centre
    first, and the pieces of a protein interleave in depth completely -- the
    two lobes fold past each other, a ligand sits between them, a side chain
    reaches through the gap. There is no order of whole parts that is right.
    Merged, hidden-surface removal happens a facet at a time and is exact, and
    the groups keep every piece its own colour.

    `sides` is how finely the ribbon's cross-section is sampled, and is a
    property of *how big the drawing will be* rather than of the protein --
    `cartoon.sides_for(inklet.three.page_scale(...))` is the caller's way to
    answer it. Cached per value, so a figure that draws the same fold at two
    magnifications gets two meshes, which is the point: one of them is a
    68 mm panel and the other a 132 mm close-up and they do not want the same
    ribbon.
    """
    pieces = [cartoon.cartoon(structure(), sides=sides)]
    if with_ligand:
        pieces.append(ligand().grouped("ligand"))
        pieces.append(side_chains().grouped("side-chain"))
    return merge(pieces).transformed(orientation())
