"""The cheminformatics figure, and the chemistry it claims to have computed.

Two kinds of test live here and they are not the same kind of thing. The
figure tests are the usual contract -- it lints clean, it is a double column,
two builds write the same bytes. The chemistry tests are the ones that matter,
because everything on that page is a claim about thirty-eight real compounds
made by code in `figures/chem_data.py`, and a fingerprint that is subtly wrong
still draws a beautiful matrix.

So the chemistry is checked against things that were known before the code
existed: the published molecular formula of every compound, the ring counts a
chemist can recite, containments that are true by inspection and near misses
that are false by one atom, and the invariances a circular fingerprint has by
construction. Where a number could only be checked against itself -- the
Tanimoto of ampicillin and amoxicillin -- the test pins the value and says
what would have to change for it to move, so a rewrite that alters it has to
say so out loud rather than quietly redrawing the figure.
"""

from __future__ import annotations

import importlib
import math
import re
import sys
from pathlib import Path
from string import Formatter

import pytest

ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

chem = importlib.import_module("figures.chem_data")
figure_module = importlib.import_module("figures.chem_fingerprints")


@pytest.fixture(scope="module")
def figure():
    return figure_module.build()


# ---------------------------------------------------------------------------
# the parser, against what was known before it was written
# ---------------------------------------------------------------------------


def test_every_graph_reproduces_its_published_molecular_formula():
    """The one test that catches a mistyped structure.

    A SMILES string typed from memory can be a perfectly valid molecule and
    the wrong one; the formula is the independent number, and it constrains the
    element counts, the implicit-hydrogen rule and the aromaticity flags at
    once. Three typos in the compound table were found this way.
    """
    wrong = [(c.name, c.formula, mol.formula())
             for c, mol in zip(chem.COMPOUNDS, chem.molecules())
             if mol.formula() != c.formula]
    assert not wrong


def test_the_compound_set_is_what_the_caption_says_it_is():
    assert len(chem.COMPOUNDS) == 38
    assert len(chem.CLASSES) == 9
    assert sorted(chem.NAMES) == list(chem.NAMES), "kept alphabetical on purpose"
    assert {c.klass for c in chem.COMPOUNDS} == set(chem.CLASSES)


@pytest.mark.parametrize("name,rings,sizes", [
    # Ring counts and sizes a chemist can recite without a computer.
    ("diazepam", 3, [6, 6, 7]),          # benzodiazepine: fused 6-7, plus phenyl
    ("penicillin G", 3, [4, 5, 6]),      # beta-lactam, thiazolidine, phenyl
    ("naproxen", 2, [6, 6]),             # naphthalene
    ("gefitinib", 4, [6, 6, 6, 6]),      # quinazoline, aniline, morpholine
    ("aspirin", 1, [6]),
    ("sulfanilamide", 1, [6]),
    ("timolol", 2, [5, 6]),              # thiadiazole and morpholine, no arene
])
def test_ring_perception_agrees_with_the_textbook(name, rings, sizes):
    mol = chem.molecules()[chem.NAMES.index(name)]
    found = mol.rings()
    assert len(found) == rings
    assert sorted(len(ring) for ring in found) == sizes


def test_the_parser_refuses_a_string_it_cannot_read():
    with pytest.raises(chem.SmilesError):
        chem.parse("c1ccccc")            # ring bond opened and never closed


# ---------------------------------------------------------------------------
# the fingerprint
# ---------------------------------------------------------------------------


def test_a_compound_is_identical_to_itself():
    for mol in chem.molecules():
        assert chem.tanimoto(chem.fingerprint(mol),
                             chem.fingerprint(mol)) == 1.0


def test_the_fingerprint_does_not_depend_on_the_order_the_atoms_arrive_in():
    """The invariance the whole method rests on.

    A circular fingerprint is a set of hashes of neighbourhoods, and a
    neighbourhood is a property of the graph rather than of the order it was
    written down in. If this failed, two drawings of one compound would have
    different fingerprints and every coefficient on the page would depend on
    how someone chose to type a string.

    Permuted here rather than re-parsed from a different SMILES, so the test
    isolates the invariance instead of also testing the parser: the reversal is
    a genuine relabelling of the same graph.
    """
    for mol in chem.molecules():
        order = tuple(reversed(range(len(mol))))
        seat = {old: new for new, old in enumerate(order)}
        shuffled = chem.Molecule(
            name=mol.name, smiles=mol.smiles,
            atoms=tuple(mol.atoms[old] for old in order),
            bonds=tuple(chem.Bond(seat[b.a], seat[b.b], b.order, b.aromatic)
                        for b in mol.bonds))
        assert chem.fingerprint(shuffled) == chem.fingerprint(mol), mol.name


def test_the_hash_is_the_same_number_in_every_process():
    """FNV-1a on a fixed input, spelled out.

    Python's `hash()` is salted per process, so a fingerprint built on it
    would fold differently in every run and the figure would not be
    reproducible. This pins the substitute to its published constants rather
    than to whatever it happens to return today.
    """
    assert chem.FNV_OFFSET == 0xCBF29CE484222325
    assert chem.FNV_PRIME == 0x100000001B3
    assert chem.MASK64 == (1 << 64) - 1
    assert chem.fnv1a(()) == chem.FNV_OFFSET

    def reference(values):
        """FNV-1a spelled out again here, over the same big-endian bytes."""
        digest = 0xCBF29CE484222325
        for value in values:
            for byte in value.to_bytes(8, "big"):
                digest = ((digest ^ byte) * 0x100000001B3) & ((1 << 64) - 1)
        return digest

    for probe in ((0,), (0x61,), (1, 2, 3), (2 ** 63, 7)):
        assert chem.fnv1a(probe) == reference(probe), probe


@pytest.mark.parametrize("one,other,value", [
    # Pairs whose value can be argued about from the structures. Pinned to
    # three decimals: they move only if the radius, the invariants, the bit
    # count or the hash change, and any of those is a change to the figure
    # that has to be declared rather than absorbed.
    ("ampicillin", "amoxicillin", 0.857),     # one phenol OH apart
    ("lorazepam", "oxazepam", 0.755),         # one aryl chlorine apart
    ("sulfadiazine", "sulfapyridine", 0.667),  # one ring nitrogen apart
    ("ibuprofen", "diazepam", 0.076),         # nothing in common but a benzene
])
def test_a_pair_of_compounds_scores_what_their_structures_say(one, other, value):
    prints = chem.fingerprints()
    got = chem.tanimoto(prints[chem.NAMES.index(one)],
                        prints[chem.NAMES.index(other)])
    assert got == pytest.approx(value, abs=5e-4)


def test_similar_compounds_score_above_unrelated_ones_across_the_whole_set():
    """The ordering claim, not a threshold: every within-class pair of the
    penicillins beats every pair that crosses out of the class. Weaker than a
    cut-off and stronger than a single coefficient -- it is the property panel
    (d) draws, tested where the classes are cleanest."""
    sim = chem.similarity()
    inside = [i for i, c in enumerate(chem.COMPOUNDS) if c.klass == "penicillin"]
    within = [sim[a][b] for a in inside for b in inside if a < b]
    leaving = [sim[a][b] for a in inside
               for b in range(len(chem.COMPOUNDS)) if b not in inside]
    assert min(within) > max(leaving)


def test_folding_is_reported_as_a_cost_and_not_as_nothing():
    """The caption prints these; the test is that they stay small and that the
    sign is the one folding can only have -- a collision can add to an
    intersection and never take from it."""
    median, worst = chem.folding_cost()
    assert 0.0 < median < 0.02
    assert median <= worst < 0.10
    assert chem.bit_collisions() > 0


# ---------------------------------------------------------------------------
# the ordering
# ---------------------------------------------------------------------------


def test_the_ordering_is_the_same_every_time_it_is_asked_for():
    assert chem.optimal_leaf_order() == chem.seriation()
    assert chem.dendrogram() == chem.dendrogram()


def test_the_ordering_is_a_permutation_of_the_whole_set():
    assert sorted(chem.seriation()) == list(range(len(chem.COMPOUNDS)))


def test_the_ordering_beats_the_order_the_data_arrived_in():
    """The before/after the figure claims, as an inequality on both metrics.

    Two of them because they are not the same question. Adjacent-row
    similarity is what the leaf ordering maximises, so it had better rise;
    band energy is global, and an ordering can win on neighbours while leaving
    a block split across the page, so it is the one that says the picture is
    banded. Both are also compared against the tree's own leaf order, which is
    what a figure that skipped the optimisation would have drawn.
    """
    sim = chem.similarity()
    alphabetical = tuple(range(len(chem.COMPOUNDS)))
    tree = chem.dendrogram_order()
    best = chem.seriation()
    assert chem.band_energy(best, sim) < chem.band_energy(tree, sim) \
        < chem.band_energy(alphabetical, sim)
    assert chem.neighbour_similarity(best, sim) \
        > chem.neighbour_similarity(tree, sim) \
        > chem.neighbour_similarity(alphabetical, sim)
    # And well under what an ordering with no structure in it would give.
    assert chem.band_energy(best, sim) < (len(chem.COMPOUNDS) + 1) / 3.0


def test_every_class_comes_out_as_one_unbroken_run():
    """The figure's central result. `blocks()` raises rather than returning a
    broken run, so this asserts the numbers rather than the fact: nine blocks
    covering all thirty-eight rows with nothing left over."""
    blocks = chem.blocks()
    assert len(blocks) == len(chem.CLASSES)
    assert sum(block.size for block in blocks) == len(chem.COMPOUNDS)
    assert [block.first for block in blocks] == \
        [0] + [b.last + 1 for b in blocks[:-1]]
    assert chem.contiguity_odds() < 1e-20


def test_the_leaf_ordering_only_flips_the_tree_it_was_given():
    """An optimal leaf ordering is a choice of flips, not a re-clustering: it
    may reorder the leaves but every subtree of the linkage has to stay a
    contiguous run. Checked on every internal node."""
    merges = chem.linkage()
    seats = {leaf: i for i, leaf in enumerate(chem.seriation())}
    leaves = chem._subtree_leaves(merges, len(merges) + 1)
    for node, members in leaves.items():
        places = sorted(seats[leaf] for leaf in members)
        assert places == list(range(places[0], places[0] + len(places))), node


# ---------------------------------------------------------------------------
# the substructure matcher
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pattern,target,expected", [
    # Positives, true by inspection.
    ("c1ccccc1", "c1ccc2ccccc2c1", True),      # benzene in naphthalene
    ("C(=O)[OH]", "CC(=O)O", True),            # acid in acetic acid
    ("cS(=O)(=O)N", "Nc1ccc(cc1)S(N)(=O)=O", True),
    # Negatives, false by inspection.
    ("c1ccc2ccccc2c1", "c1ccccc1", False),     # naphthalene is not in benzene
    ("C1CCCCC1", "c1ccccc1", False),           # cyclohexane is not benzene
    ("c1ccccc1", "c1ccncc1", False),           # benzene is not in pyridine
    # Near misses, false by one atom or one hydrogen.
    ("c1ccc2ncncc2c1", "c1ccc2ccccc2c1", False),   # quinazoline vs naphthalene
    ("[OH]c1ccccc1[OH]", "[OH]c1ccccc1", False),   # catechol vs plain phenol
    ("C1C(=O)NC1", "C1C(=O)NCC1", False),          # 4-ring lactam vs 5-ring
])
def test_the_matcher_answers_both_directions(pattern, target, expected):
    assert chem.contains(chem.parse(pattern), chem.parse(target)) is expected


def test_a_match_is_a_real_mapping_and_not_a_count():
    """Naphthalene contains two benzenes and the matcher finds exactly two,
    each a set of six atoms of the ten. Counting is the part a fingerprint
    cannot do and the part a wrong backtracker gets wrong by orders of
    magnitude -- 12 matches for one ring is a matcher reporting automorphisms.
    """
    found = chem.match_all(chem.parse("c1ccccc1"), chem.parse("c1ccc2ccccc2c1"))
    assert len(found) == 2
    assert all(len(set(hit)) == 6 for hit in found)
    assert len({frozenset(hit) for hit in found}) == 2


def test_every_fragment_in_the_vocabulary_is_found_somewhere():
    """A query that matches nothing is a query with a typo in it: it draws an
    empty column and says something false about the whole set."""
    rows = chem.incidence()
    empty = [f.name for f, row in zip(chem.FRAGMENTS, rows) if not any(row)]
    assert not empty


@pytest.mark.parametrize("fragment,klass", [
    # Fragments that define a class, asserted as an exact set: found in every
    # member and in nothing else. These are the columns of panel (b) that make
    # its block structure an argument rather than a decoration.
    ("beta-lactam", "penicillin"),
    ("catechol", "catecholamine"),
    ("aryloxypropanolamine", "beta-blocker"),
    ("aryl sulfonamide", "sulfonamide"),
])
def test_a_defining_fragment_picks_out_exactly_its_class(fragment, klass):
    row = chem.incidence()[[f.name for f in chem.FRAGMENTS].index(fragment)]
    carriers = {chem.COMPOUNDS[i].name for i, hit in enumerate(row) if hit}
    members = {c.name for c in chem.COMPOUNDS if c.klass == klass}
    assert carriers == members


def test_the_two_descriptions_agree_without_sharing_any_code():
    """Tanimoto over hashed neighbourhoods against Jaccard over seventeen
    hand-written queries. Nothing links them but the graphs, so a correlation
    is evidence; the bound is loose on purpose, since the claim is agreement
    and not a particular coefficient."""
    sim = chem.similarity()
    n = len(sim)
    pairs = [(sim[i][j], chem.fragment_jaccard(i, j))
             for i in range(n) for j in range(i + 1, n)]
    assert len(pairs) == n * (n - 1) // 2
    rho = chem.spearman([x for x, _ in pairs], [y for _, y in pairs])
    assert 0.4 < rho < 0.9


def test_spearman_handles_the_ties_the_data_actually_has():
    assert chem.spearman([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)
    assert chem.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    # A tied run gets the mean rank, so the coefficient cannot depend on the
    # order the tied pairs were generated in.
    assert chem.spearman([1, 1, 2, 2], [3, 4, 5, 6]) \
        == pytest.approx(chem.spearman([1, 1, 2, 2], [4, 3, 6, 5]))


# ---------------------------------------------------------------------------
# the drawings
# ---------------------------------------------------------------------------


def test_no_compound_in_the_set_draws_badly():
    """The layout is under test, not just the six compounds that ship.

    Every bond one unit long, no two unbonded atoms on top of each other, no
    crossing bonds, and no atom hidden on a straight line between its two
    neighbours -- that last one is why diclofenac stopped looking like a
    benzoic acid. All thirty-eight are checked because panel (f) draws nine
    today and a different nine tomorrow.
    """
    bad = {c.name: chem.depiction_faults(mol)
           for c, mol in zip(chem.COMPOUNDS, chem.molecules())
           if chem.depiction_faults(mol)}
    assert not bad


def test_a_triple_bond_is_allowed_to_be_straight():
    """The exemption in the straightness rule is real chemistry: erlotinib's
    alkyne is linear in the molecule, and a kink drawn into it would be as
    wrong as diclofenac's missing corner."""
    mol = chem.molecules()[chem.NAMES.index("erlotinib")]
    assert any(bond.order == 3 for bond in mol.bonds)
    assert not chem.depiction_faults(mol)


def test_the_drawing_is_the_same_every_time_it_is_asked_for():
    for name in figure_module.DRAWN:
        mol = chem.molecules()[chem.NAMES.index(name)]
        assert chem.depiction(mol) == chem.depiction(mol)


def test_panel_f_draws_one_compound_from_every_block():
    """Nine structures, one per block, in block order -- which is the claim the
    numbers under them make. Read back from the seriation rather than from a
    list, so reordering the classes cannot silently mislabel them."""
    order = chem.seriation()
    blocks = chem.blocks(order)
    assert len(figure_module.DRAWN) == len(blocks)
    for block, name in zip(blocks, figure_module.DRAWN):
        index = chem.NAMES.index(name)
        assert index in order[block.first:block.last + 1]


# ---------------------------------------------------------------------------
# the eigensolver, and the two pictures built on it
# ---------------------------------------------------------------------------


def test_the_eigensolver_agrees_with_an_eigenproblem_solved_by_hand():
    """`[[2, 1], [1, 2]]` has eigenvalues 3 and 1 and eigenvectors along the
    diagonals, which is a fact about arithmetic and not about this code."""
    (first, one), (second, other) = chem.top_eigen([[2.0, 1.0], [1.0, 2.0]], 2)
    root = math.sqrt(0.5)
    assert first == pytest.approx(3.0, abs=1e-9)
    assert second == pytest.approx(1.0, abs=1e-9)
    assert one == pytest.approx((root, root), abs=1e-6)
    assert other == pytest.approx((root, -root), abs=1e-6)


def test_the_eigensolver_deflates_down_a_known_spectrum():
    """A tridiagonal matrix whose eigenvalues are 4 + sqrt(2), 4, 4 - sqrt(2).
    Deflation is the part that can silently go wrong: the first eigenpair is
    easy and the third is the one that proves the subtraction worked."""
    matrix = [[4.0, 1.0, 0.0], [1.0, 4.0, 1.0], [0.0, 1.0, 4.0]]
    values = [value for value, _ in chem.top_eigen(matrix, 3)]
    assert values == pytest.approx([4 + math.sqrt(2), 4.0, 4 - math.sqrt(2)],
                                   abs=1e-7)


def test_every_axis_comes_out_pointing_the_same_way():
    """A sign is not determined by the eigenproblem, so the module fixes it:
    the largest-magnitude entry of every eigenvector is positive. Without this
    the cloud in (h) could mirror itself between two runs of the same code."""
    matrix = [[4.0, 1.0, 0.0], [1.0, 4.0, 1.0], [0.0, 1.0, 4.0]]
    for _, vector in chem.top_eigen(matrix, 3):
        assert vector[max(range(len(vector)),
                          key=lambda i: (abs(vector[i]), -i))] > 0.0


def test_scaling_puts_a_cloud_back_where_it_found_it():
    """The test classical MDS has to pass: given the distances of a real
    3-D point set, return points with those distances. Six points, no
    symmetry, checked pair by pair -- and the kept fraction has to be 1.0,
    because three axes can carry a three-dimensional cloud exactly."""
    cloud = [(0.0, 0.0, 0.0), (1.7, 0.0, 0.0), (0.3, 2.1, 0.0),
             (-1.1, 0.4, 1.9), (0.8, -1.3, 0.7), (2.2, 1.4, -0.9)]
    want = [[math.dist(a, b) for b in cloud] for a in cloud]
    coords, kept = chem.mds(want, 3)
    for i in range(len(cloud)):
        for j in range(len(cloud)):
            assert math.dist(coords[i], coords[j]) \
                == pytest.approx(want[i][j], abs=1e-6)
    assert kept == pytest.approx(1.0, abs=1e-9)


def test_scaling_says_how_much_it_threw_away():
    """Ask the same cloud for two axes and the fraction has to fall to the
    share of the positive eigenvalue mass those two carry -- which is the
    number the caption prints, so it must not be quietly optimistic."""
    cloud = [(0.0, 0.0, 0.0), (1.7, 0.0, 0.0), (0.3, 2.1, 0.0),
             (-1.1, 0.4, 1.9), (0.8, -1.3, 0.7), (2.2, 1.4, -0.9)]
    want = [[math.dist(a, b) for b in cloud] for a in cloud]
    values = [value for value, _ in chem.top_eigen(chem.gram(want), 3)]
    _, kept = chem.mds(want, 2)
    assert kept == pytest.approx(sum(values[:2]) / sum(values), abs=1e-9)
    assert kept < 1.0


def test_the_chemical_space_is_the_same_space_every_time():
    """(h) is a picture of thirty-eight numbers that were computed, not read,
    so it has to come out identical from a cold cache."""
    first, kept = chem.chemical_space()
    chem.chemical_space.cache_clear()
    again, kept_again = chem.chemical_space()
    assert first == again
    assert kept == kept_again
    assert first == chem.mds(chem.distances(), 3)[0]


def test_the_chemical_space_keeps_what_the_caption_says_it_keeps():
    """A Tanimoto distance is not Euclidean and 2,048 bits do not flatten into
    three axes kindly. The figure prints the fraction rather than hiding it;
    this pins the order of magnitude so a change that moves it has to say so.
    """
    _, kept = chem.chemical_space()
    assert 0.30 < kept < 0.45
    assert kept == pytest.approx(0.3551, abs=0.001)


def test_the_cloud_puts_every_compound_somewhere_finite():
    coords, _ = chem.chemical_space()
    assert len(coords) == len(chem.COMPOUNDS)
    assert all(len(point) == 3 and all(math.isfinite(x) for x in point)
               for point in coords)


def test_the_blocks_are_tighter_in_the_cloud_than_the_set_is():
    """(h) claims the blocks read as clusters. That is a measurable claim:
    the mean distance within a block has to be smaller than the mean distance
    across the whole set, for every one of the nine."""
    coords, _ = chem.chemical_space()
    order = chem.seriation()
    every = [math.dist(coords[i], coords[j])
             for i in range(len(coords)) for j in range(i + 1, len(coords))]
    spread = sum(every) / len(every)
    for block in chem.blocks(order):
        members = order[block.first:block.last + 1]
        inside = [math.dist(coords[i], coords[j])
                  for x, i in enumerate(members) for j in members[x + 1:]]
        assert sum(inside) / len(inside) < spread, block.klass


# ---------------------------------------------------------------------------
# the conformer
# ---------------------------------------------------------------------------


def test_every_bond_in_the_set_has_a_tabulated_length():
    """`DEFAULT_LENGTH` exists so `conformer` cannot raise, not so the figure
    can use it. Every bond type that actually occurs in the thirty-eight has
    to be in the table -- and every key in the table has to be sorted the way
    `bond_length` sorts its lookup, which is how C-Br was found sitting in the
    table and being missed by every query for it."""
    assert all(key[:2] == tuple(sorted(key[:2])) for key in chem.LENGTHS)
    missing = set()
    for mol in chem.molecules():
        for bond in mol.bonds:
            pair = tuple(sorted((mol.atoms[bond.a].element,
                                 mol.atoms[bond.b].element)))
            code = 0 if bond.aromatic else bond.order
            if (*pair, code) not in chem.LENGTHS:
                missing.add((*pair, code))
    assert not missing


@pytest.mark.parametrize("centre,shape", [
    ("benzene", chem.TRIGONAL),          # aromatic carbon
    ("cyclopentane", 108.0),             # the ring overrides hybridisation
])
def test_the_angle_a_bond_is_asked_for_is_the_angle_its_atom_can_make(
        centre, shape):
    mol = chem.parse({"benzene": "c1ccccc1",
                      "cyclopentane": "C1CCCC1"}[centre], centre)
    a, b = mol.adjacency()[0][:2]
    assert chem.bond_angle(mol, 0, a, b) == pytest.approx(shape, abs=1e-9)


def test_a_tetrahedral_carbon_is_tetrahedral():
    mol = chem.parse("CC(C)C", "isobutane")
    a, b = mol.adjacency()[1][:2]
    assert chem.bond_angle(mol, 1, a, b) == pytest.approx(chem.TETRAHEDRAL)


def test_an_alkyne_is_straight():
    mol = chem.parse("CC#CC", "but-2-yne")
    a, b = mol.adjacency()[1][:2]
    assert chem.bond_angle(mol, 1, a, b) == pytest.approx(chem.LINEAR)


def test_the_conformer_is_the_same_shape_every_time_it_is_built():
    """Distance geometry with a relaxation in it is exactly the kind of code
    that drifts. The start vector comes from `fnv1a`, so it must not."""
    mol = chem.molecules()[chem.NAMES.index(figure_module.EMBODIED)]
    first = chem.conformer(mol)
    chem.conformer.cache_clear()
    assert chem.conformer(mol) == first


def test_the_conformer_satisfies_the_geometry_it_was_asked_for():
    """The panel's claim, measured: bond lengths within a fraction of a per
    cent of the table, angles within a degree of hybridisation, and no two
    atoms with nothing between them closer than a van der Waals contact.
    These are the three numbers the caption prints."""
    mol = chem.molecules()[chem.NAMES.index(figure_module.EMBODIED)]
    bond, angle, contact = chem.conformer_error(mol)
    assert bond < 1.0, f"worst bond off by {bond:.2f}%"
    assert angle < 2.0, f"worst angle off by {angle:.2f} degrees"
    assert contact > chem.TORSION_CONTACT - 0.01


def test_the_conformer_is_a_molecule_and_not_a_ball():
    """A degenerate embedding -- everything collapsed to a point, or flat --
    would still pass a bond-length test if the bonds were short. It has to
    have three real dimensions and be about the size of the compound."""
    mol = chem.molecules()[chem.NAMES.index(figure_module.EMBODIED)]
    points = chem.conformer(mol)
    assert len(points) == len(mol)
    extent = [max(p[k] for p in points) - min(p[k] for p in points)
              for k in range(3)]
    assert extent[0] > extent[1] > extent[2] > 1.0     # principal axes, in order
    assert 6.0 < extent[0] < 12.0        # ~7.6 A across the heavy atoms


def test_the_frame_never_mirrors_the_molecule():
    """The third principal axis is a cross product, not the third eigenvector,
    so the frame is right-handed. For a compound with a stereocentre the
    difference is the drug and the other enantiomer, which is why this is a
    test and not a comment."""
    def handedness(points):
        a, b, c, d = points[:4]
        u = [b[k] - a[k] for k in range(3)]
        v = [c[k] - a[k] for k in range(3)]
        w = [d[k] - a[k] for k in range(3)]
        return (u[0] * (v[1] * w[2] - v[2] * w[1])
                - u[1] * (v[0] * w[2] - v[2] * w[0])
                + u[2] * (v[0] * w[1] - v[1] * w[0]))

    cloud = [(0.4, 0.1, -0.2), (2.9, 0.3, 0.4), (0.2, 3.1, 0.1),
             (0.5, 0.2, 2.7), (1.4, 1.1, 1.2)]
    turned = chem._principal_frame(cloud)
    assert handedness(turned) * handedness(cloud) > 0.0


def test_the_flat_drawing_left_something_out():
    """The reason (d) is on the page at all. Diazepam's two aromatic rings
    come out planar because planarity went in as a constraint; its
    seven-membered ring comes out puckered because nothing asked it to be
    flat, and the pendant phenyl comes out well off the plane of the benzo
    ring. Both are facts about the compound that (c) cannot draw."""
    mol = chem.molecules()[chem.NAMES.index(figure_module.EMBODIED)]
    rings = mol.rings()
    for ring in rings:
        if all(mol.atoms[atom].aromatic for atom in ring):
            assert chem.ring_pucker(mol, ring) < 0.10
    seven = max(rings, key=len)
    assert len(seven) == 7
    assert chem.ring_pucker(mol, seven) > 0.15
    assert 25.0 < chem.aromatic_ring_angle(mol) < 65.0


def test_the_twist_refuses_a_molecule_it_cannot_measure():
    """One aromatic ring has no angle to another and three have three; the
    function says so rather than picking two and quoting a number."""
    with pytest.raises(ValueError):
        chem.aromatic_ring_angle(
            chem.molecules()[chem.NAMES.index("aspirin")])


def test_the_two_three_dimensional_panels_come_out_of_the_same_solver():
    """The claim the module docstring makes: (d) and (h) are one method twice,
    `chem.mds` on a distance matrix. If either grew its own embedding this
    would still draw, and the caption would be lying."""
    source = Path(chem.__file__).read_text(encoding="utf-8")
    assert source.count("def mds(") == 1
    assert "mds(distance" in source or "mds(targets" in source \
        or "mds(matrix" in source
    assert "mds(distances()" in source


# ---------------------------------------------------------------------------
# the page
# ---------------------------------------------------------------------------


def test_the_figure_lints_clean(figure):
    assert not figure.lint(), figure.report()


def test_the_page_is_a_double_column(figure):
    body, _ = figure.build()
    assert body.width == pytest.approx(figure_module.PAGE, abs=0.01)


def test_the_page_fits_the_journal(figure):
    """A figure taller than the type area is a figure that gets scaled down by
    the production department, which takes the 5 pt labels below the floor the
    linter defends."""
    body, _ = figure.build()
    assert body.height <= 247.0


def test_the_same_figure_renders_byte_identically_twice(figure):
    assert figure.to_svg() == figure.to_svg()


#: Ids come from a per-process counter, so two builds never spell them the
#: same way and every comparison has to normalise them out.
IDS = re.compile(r'(id="|data-name="|url\(#|href="#)[A-Za-z-]*\d+')


def test_two_separate_builds_agree_on_every_coordinate():
    def canonical(svg: str) -> str:
        return IDS.sub(r"\1X", svg)

    assert canonical(figure_module.build().to_svg()) \
        == canonical(figure_module.build().to_svg())


def test_the_caption_quotes_the_numbers_the_panels_drew():
    """The caption is formatted from the same functions the panels are drawn
    from, so this checks that the template still has a slot for each of them
    and that the headline numbers appear in the rendered string."""
    figure_module.RHO[0] = 0.6016
    rendered = figure_module.caption()
    text = rendered.text if hasattr(rendered, "text") else ""
    del text                      # the Diagram is opaque; format it again here
    order = chem.seriation()
    sim = chem.similarity()
    # Read the slots out of the template rather than listing them here, so a
    # panel that starts quoting a new number cannot leave this test behind.
    slots = {name for _, name, _, _ in Formatter().parse(figure_module.CAPTION)
             if name}
    filled = {name: 0.0 for name in slots}
    filled.update(legend="", odds="", radius=chem.RADIUS, bits=chem.BITS)
    assert f"{chem.BITS:,} bits" in figure_module.CAPTION.format(**filled)
    assert {"bond_error", "twist", "explained"} <= slots
    # Every class named in the gutter legend, in the order the blocks come out.
    assert [block.klass for block in chem.blocks(order)] == \
        [c.klass for c in
         [chem.COMPOUNDS[order[block.first]] for block in chem.blocks(order)]]
    assert chem.band_energy(order, sim) < 10.0


def test_the_panels_all_build_on_their_own():
    """Every entry in the preview map is callable, which is what keeps
    `python figures/chem_fingerprints.py d` working after a refactor."""
    for letter, builder in figure_module.PANELS.items():
        if builder is None:
            continue
        assert builder() is not None, letter


def test_the_row_pitch_is_big_enough_for_the_type_it_carries():
    """The compound names are the reason the matrix is the size it is. If the
    pitch ever drops below the line height, two names' boxes overlap -- which
    is an OVERLAP error, not a crowding opinion -- and the fix is the matrix,
    not the type."""
    line = math.ceil(1000 * figure_module.inklet.text(
        "Ag", size=figure_module.inklet.pt(figure_module.NAME_PT)).height) / 1000
    assert figure_module.PITCH > line
