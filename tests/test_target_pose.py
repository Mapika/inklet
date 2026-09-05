"""The docked pose in `figures/target.py`, checked against what it claims.

`figures/drug_discovery.py` prints three hydrogen-bond lengths beside three
dashed lines and calls the compound a hinge binder. All three numbers come out
of `LIGAND_PLACEMENT`, a matrix written into the source by
`tools/dock_ligand.py` -- so if that matrix is ever regenerated with a
different score, a different set of restraints or a different random seed, the
figure will happily print whatever the new pose gives and still look right.

These are the assertions that would stop it: the bonds are bonds, the pose is a
rigid motion rather than a squashed one, and the compound is beside the protein
rather than inside it.
"""

import math
import sys
from pathlib import Path

import pytest

FIGURES = Path(__file__).resolve().parent.parent / "figures"
if str(FIGURES) not in sys.path:
    sys.path.insert(0, str(FIGURES))

target = pytest.importorskip("target")
cartoon = pytest.importorskip("cartoon")

#: What counts as a hydrogen bond between two heavy atoms. Below 2.6 A they
#: are on top of each other; above 3.5 there is no bond to draw.
SHORTEST, LONGEST = 2.6, 3.5

#: How close a non-bonded pair may come. Two heavy atoms neither bonded nor
#: hydrogen bonded sit at van der Waals contact, a little over 3 A; 2.4 is
#: loose enough not to fail on a tight fit and tight enough to catch a
#: compound that has been pushed through the wall of the pocket.
CLEAREST = 2.4


def test_every_restraint_is_actually_a_hydrogen_bond():
    measured = {name: distance for name, _, _, distance in target.contacts()}
    assert set(measured) == {name for name, _, _, _ in target.RESTRAINTS}
    for name, distance in measured.items():
        assert SHORTEST <= distance <= LONGEST, f"{name} at {distance:.2f} A"


def test_the_pose_asks_for_what_the_restraints_ask_for():
    """Each bond within 0.6 A of the length its restraint named.

    Not tighter, because the score the pose minimises is not the restraints
    alone: it pays for a clash as well, and the hinge bond is the one it lets
    stretch -- 3.42 A against the 2.90 asked for -- to keep the compound out of
    the wall behind it. The assertion is that the pose still answers the
    question it was set, not that it answers it perfectly.
    """
    wanted = {name: ideal for name, _, _, ideal in target.RESTRAINTS}
    for name, _, _, distance in target.contacts():
        assert abs(distance - wanted[name]) <= 0.6, f"{name} at {distance:.2f} A"


def test_the_placement_is_a_rigid_motion():
    """Orthonormal rows and a positive determinant: a turn, not a squash.

    A least-squares fit that has gone wrong comes back as a matrix that scales
    or reflects, and a reflected ligand is a different compound -- its
    stereocentres are all inverted. Nothing downstream would notice.
    """
    m = target.LIGAND_PLACEMENT
    rows = ((m.ax, m.bx, m.cx), (m.ay, m.by, m.cy), (m.az, m.bz, m.cz))
    for row in rows:
        assert math.isclose(sum(v * v for v in row), 1.0, abs_tol=1e-5)
    for one in range(3):
        for two in range(one + 1, 3):
            dot = sum(a * b for a, b in zip(rows[one], rows[two]))
            assert abs(dot) < 1e-5
    (a, b, c), (d, e, f), (g, h, i) = rows
    determinant = (a * (e * i - f * h) - b * (d * i - f * g)
                   + c * (d * h - e * g))
    assert math.isclose(determinant, 1.0, abs_tol=1e-5)


def test_the_compound_is_in_the_pocket_and_not_in_the_protein():
    here = target.structure()
    partners = {(name, atom) for name, atom, _, _ in target.RESTRAINTS}
    worst = None
    for point in target.ligand_atoms():
        for residue in here.near(point, 4.5):
            for atom, where in residue.atoms.items():
                if (residue.label, atom) in partners:
                    continue
                gap = (where - point).length
                if worst is None or gap < worst[0]:
                    worst = (gap, residue.label, atom)
    assert worst is not None, "the compound is nowhere near the protein"
    assert worst[0] >= CLEAREST, f"{worst[1]} {worst[2]} at {worst[0]:.2f} A"


def test_the_compound_spans_the_cleft_it_was_drawn_for():
    """The skeleton is laid out in units and scaled by `BOND`; this is the
    check that the scale is right, rather than a schematic sized to taste."""
    atoms = target.ligand_atoms()
    span = max((a - b).length for a in atoms for b in atoms)
    assert 12.0 <= span <= 18.0


def test_no_atom_of_the_skeleton_is_over_valent():
    """Hydrogens are counted off what is left of each valence, so a bond drawn
    one too many times would show up as a negative count and silently vanish
    from the formula printed beside the structure."""
    counted = target.composition()
    assert counted["H"] > 0
    assert target.formula().startswith(f"C_{{{counted['C']}}}H_{{{counted['H']}}}")


# -- how finely the ribbon is sampled -------------------------------------


def test_the_section_sampling_answers_to_the_page_not_to_a_constant():
    """`sides_for` is the point of `SIDES` no longer being pinned to one size:
    a drawing twice as big gets a section sampled finely enough for it."""
    assert cartoon.sides_for(20.0) > cartoon.sides_for(10.0) > cartoon.SIDES


def test_the_two_panels_of_the_figure_get_the_counts_the_docstring_claims():
    """13 points at 68 mm and 18 at 132.

    Stated as a test because it is the claim the docstring in
    `figures/drug_discovery.py` makes, and it is the kind of claim that goes
    quietly wrong when a panel is resized. Both are above the floor, so it is
    the page deciding and not `SIDES` -- which is what makes the wide panel
    carry two thirds of the geometry rather than all of it drawn smaller.
    """
    import inklet
    import drug_discovery as dd

    mesh = target.fold()
    counts = [cartoon.sides_for(
                  inklet.three.page_scale(mesh, width=width, view=dd.VIEW))
              for width in (dd.WIDE, dd.CLOSE)]
    assert counts == [13, 18]
    assert min(counts) > cartoon.SIDES


@pytest.mark.parametrize("sides", [8, 13, 20, 31])
def test_the_drawn_section_stays_inside_the_tolerance_it_reports(sides):
    """The number `sides_for` returns has to mean what it says about the
    curve, at every section type the sweep carries."""
    scale = 4.0
    tolerance = max(cartoon._departure(sides, *section) * scale
                    for section in cartoon.SECTIONS.values())
    assert cartoon.sides_for(scale, tolerance, floor=3) <= sides
    assert cartoon.sides_for(scale, tolerance * 0.99, floor=3) > sides
