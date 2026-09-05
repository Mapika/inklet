"""Thirty-eight real drugs, as graphs, and everything the figure computes on them.

The figure this feeds (`chem_fingerprints.py`) makes four claims and this
module is where all four are earned, because none of them may be a number
somebody typed.

**The compounds are real and the graphs are the compounds.** Every molecule
below is a marketed or classical drug, written as SMILES and parsed here into
an explicit atom/bond graph -- element, aromatic flag, formal charge, bond
order, and the hydrogens that are left over once the drawn bonds are taken off
each atom's valence. Nothing is loaded at build time and nothing is looked up:
`COMPOUNDS` carries each compound's published molecular formula beside its
SMILES purely so that `tests/test_chem_figure.py` can recompute the formula
from the parsed graph and compare. A SMILES string mistyped from memory is the
one failure mode a figure like this cannot survive, and a formula that has to
match is the check that catches it -- it caught three while this was written.

**RDKit is not installed and is not wanted.** The circular fingerprint, the
Tanimoto coefficient, the clustering, the leaf ordering and the substructure
matcher are all written out below in a few hundred lines of stdlib Python.
That is the point of the exercise: a reader can see exactly what "similarity"
means here rather than being told a library computed it.

**The hash is stable across processes.** Python's `hash()` is salted per
interpreter, so a fingerprint built with it changes every run and the figure
would not be byte-identical twice. `fnv1a` below is the 64-bit FNV-1a of an
explicit big-endian encoding: same bytes, same integer, every run, every
machine.

**The ordering is derived, not chosen.** `seriation()` is average-linkage
agglomerative clustering followed by Bar-Joseph optimal leaf ordering -- the
exact dynamic program, not a heuristic -- maximising the summed similarity of
neighbouring rows. `band_energy()` scores any ordering, so the figure can print
what the ordering was worth instead of asserting that it looks better.

Sources for the structures: each SMILES was written from the compound's
standard structural formula and checked against its published molecular
formula (the `formula` field). The class assignments are the ordinary
medicinal-chemistry ones -- what a pharmacology textbook puts in a chapter
together -- and are used only as labels on the picture. They are never
consulted by the clustering, which is the whole point: the blocks in panel (a)
are found by the fingerprints alone and the class colours are painted on
afterwards to say whether the chemistry agrees.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache

# ===========================================================================
# the molecular graph
# ===========================================================================


class SmilesError(ValueError):
    """A SMILES string this parser cannot read, with where it gave up."""


@dataclass(frozen=True)
class Atom:
    """One heavy atom. Hydrogens are counted, never nodes.

    `hydrogens` is what is left of the atom's valence after its drawn bonds,
    which is how a structural formula works and what makes the molecular
    formula a property of the graph rather than a second assertion about it.
    `exact_h` marks an atom whose hydrogen count was *written* -- `[OH]`,
    `[nH]` -- and is read only by the substructure matcher, where "an oxygen
    carrying one hydrogen" and "an oxygen" are different questions.
    """

    element: str
    aromatic: bool = False
    charge: int = 0
    hydrogens: int = 0
    exact_h: bool = False


@dataclass(frozen=True)
class Bond:
    """`order` is 1, 2 or 3; an aromatic bond carries `aromatic` and order 1.

    Aromatic bonds are not Kekulised. Nothing here needs a Kekule structure --
    the fingerprint hashes the aromatic flag, the matcher compares it, and the
    depiction draws an inner circle -- and Kekulising a fused heteroaromatic
    correctly is a solver nobody should write twice.
    """

    a: int
    b: int
    order: int = 1
    aromatic: bool = False

    def other(self, atom: int) -> int:
        return self.b if atom == self.a else self.a


#: Bonding capacities, smallest first. A sulfonamide sulphur uses six and a
#: sulfoxide four, so an element needs a list rather than a number: the
#: implicit hydrogen count comes from the smallest capacity that covers the
#: bonds actually drawn.
VALENCES: dict[str, tuple[int, ...]] = {
    "B": (3,), "C": (4,), "N": (3, 5), "O": (2,), "P": (3, 5),
    "S": (2, 4, 6), "F": (1,), "Cl": (1,), "Br": (1,), "I": (1,), "*": (0,),
}

#: For the molecular formula only.
MASSES = {"H": 1.008, "B": 10.81, "C": 12.011, "N": 14.007, "O": 15.999,
          "F": 18.998, "P": 30.974, "S": 32.06, "Cl": 35.45, "Br": 79.904,
          "I": 126.904}

_ORGANIC = ("Cl", "Br", "B", "C", "N", "O", "P", "S", "F", "I", "*")
_AROMATIC = {"b": "B", "c": "C", "n": "N", "o": "O", "p": "P", "s": "S"}
_BONDS = {"-": 1, "=": 2, "#": 3, "/": 1, "\\": 1, ":": 1}


@dataclass(frozen=True)
class Molecule:
    """A parsed structure: atoms, bonds, and the questions the rest asks of it."""

    name: str
    smiles: str
    atoms: tuple[Atom, ...]
    bonds: tuple[Bond, ...]

    def __len__(self) -> int:
        return len(self.atoms)

    @lru_cache(maxsize=None)
    def adjacency(self) -> tuple[tuple[int, ...], ...]:
        """Neighbours of every atom, in ascending index order."""
        near: list[list[int]] = [[] for _ in self.atoms]
        for bond in self.bonds:
            near[bond.a].append(bond.b)
            near[bond.b].append(bond.a)
        return tuple(tuple(sorted(row)) for row in near)

    @lru_cache(maxsize=None)
    def bond_index(self) -> dict[tuple[int, int], Bond]:
        """`(a, b) -> Bond` both ways round, for the matcher's inner loop."""
        found: dict[tuple[int, int], Bond] = {}
        for bond in self.bonds:
            found[(bond.a, bond.b)] = bond
            found[(bond.b, bond.a)] = bond
        return found

    def bond_between(self, a: int, b: int) -> Bond | None:
        return self.bond_index().get((a, b))

    @lru_cache(maxsize=None)
    def ring_bonds(self) -> frozenset[tuple[int, int]]:
        """Every bond that lies on a cycle, as sorted index pairs.

        A bond is in a ring exactly when it is not a bridge, so this is one
        depth-first low-link pass rather than a ring search -- and unlike a
        ring search it cannot disagree with itself about a fused system.
        """
        return frozenset(
            (bond.a, bond.b) if bond.a < bond.b else (bond.b, bond.a)
            for bond in self.bonds
            if not _is_bridge(self, bond)
        )

    def in_ring(self, atom: int) -> bool:
        return any(atom in pair for pair in self.ring_bonds())

    @lru_cache(maxsize=None)
    def rings(self) -> tuple[tuple[int, ...], ...]:
        """A smallest set of smallest rings, each as its atom cycle in order.

        For every ring bond, the shortest path between its ends that avoids
        the bond itself is the smallest ring through it. Collected smallest
        first and accepted only while it covers a bond no accepted ring has,
        which gives the right count (bonds - atoms + components) for every
        fused system a drug contains. Deterministic: candidates are sorted
        before they are filtered.
        """
        candidates: dict[frozenset[int], tuple[int, ...]] = {}
        for a, b in sorted(self.ring_bonds()):
            cycle = _shortest_cycle(self, a, b)
            if cycle is not None:
                candidates.setdefault(frozenset(cycle), cycle)
        want = len(self.ring_bonds()) - len(
            {i for pair in self.ring_bonds() for i in pair}) + len(
                _ring_systems(self))
        kept: list[tuple[int, ...]] = []
        covered: set[tuple[int, int]] = set()
        for key in sorted(candidates, key=lambda k: (len(k), sorted(k))):
            cycle = candidates[key]
            edges = {(min(u, v), max(u, v))
                     for u, v in zip(cycle, cycle[1:] + cycle[:1])}
            if len(kept) < want and not edges <= covered:
                kept.append(cycle)
                covered |= edges
        return tuple(kept)

    @lru_cache(maxsize=None)
    def formula(self) -> str:
        """The molecular formula in Hill order, counted off the graph."""
        counts: dict[str, int] = {}
        for atom in self.atoms:
            counts[atom.element] = counts.get(atom.element, 0) + 1
            if atom.hydrogens:
                counts["H"] = counts.get("H", 0) + atom.hydrogens
        rest = sorted(k for k in counts if k not in ("C", "H"))
        return "".join(
            f"{el}{counts[el]}" if counts[el] > 1 else el
            for el in (["C", "H"] if "C" in counts else []) + rest
            if el in counts)

    @lru_cache(maxsize=None)
    def mass(self) -> float:
        """Average molecular mass, from the same count."""
        total = 0.0
        for atom in self.atoms:
            total += MASSES[atom.element] + MASSES["H"] * atom.hydrogens
        return total


def _is_bridge(mol: Molecule, bond: Bond) -> bool:
    """Whether removing this bond disconnects its two ends."""
    seen = {bond.a}
    stack = [bond.a]
    near = mol.adjacency()
    while stack:
        here = stack.pop()
        for other in near[here]:
            if (here, other) in ((bond.a, bond.b), (bond.b, bond.a)):
                continue
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return bond.b not in seen


def _shortest_cycle(mol: Molecule, a: int, b: int) -> tuple[int, ...] | None:
    """The shortest ring through bond `a-b`, as a cycle of atom indices."""
    near = mol.adjacency()
    back = {a: a}
    queue = [a]
    while queue:
        nxt = []
        for here in queue:
            for other in near[here]:
                if (here, other) in ((a, b), (b, a)) or other in back:
                    continue
                back[other] = here
                nxt.append(other)
        if b in back:
            break
        queue = nxt
    if b not in back:
        return None
    path = [b]
    while path[-1] != a:
        path.append(back[path[-1]])
    return tuple(reversed(path))


def _ring_systems(mol: Molecule) -> list[tuple[int, ...]]:
    """Connected components of the ring-bond subgraph, atoms in index order."""
    near: dict[int, set[int]] = {}
    for a, b in mol.ring_bonds():
        near.setdefault(a, set()).add(b)
        near.setdefault(b, set()).add(a)
    out: list[tuple[int, ...]] = []
    seen: set[int] = set()
    for start in sorted(near):
        if start in seen:
            continue
        group, stack = {start}, [start]
        seen.add(start)
        while stack:
            here = stack.pop()
            for other in near[here] - group:
                group.add(other)
                seen.add(other)
                stack.append(other)
        out.append(tuple(sorted(group)))
    return out


# ===========================================================================
# the SMILES reader
# ===========================================================================


def parse(smiles: str, name: str = "") -> Molecule:
    """Read a SMILES string into a `Molecule`.

    The subset a drug needs and no more: the organic subset with its implicit
    hydrogens, lower-case aromatics, bracket atoms with a charge and an
    explicit hydrogen count, the four bond symbols, branches, ring-closure
    digits (and `%nn`), `.` for a second component, and `*` for "any atom" in
    a query pattern. Stereochemistry marks (`@`, `/`, `\\`) are read and
    discarded -- this figure is about connectivity, and a fingerprint that
    pretended to know the configuration of atenolol would be lying.

    Errors carry the offending index, because a SMILES typo is otherwise
    invisible: `Nc1ccc(cc1)S(N)(=O)=O` and `Nc1ccc(cc1)S(N)(=O)O` differ by one
    character and by one oxidation state.
    """
    atoms: list[Atom] = []
    bonds: list[Bond] = []
    branch: list[int] = []
    rings: dict[str, tuple[int, int | None]] = {}
    previous: int | None = None
    pending: int | None = None          # bond order written before an atom
    pending_aromatic = False
    i = 0

    def connect(a: int, b: int, order: int | None, aromatic: bool) -> None:
        if order is None:
            both = atoms[a].aromatic and atoms[b].aromatic
            bonds.append(Bond(a, b, 1, both))
        else:
            bonds.append(Bond(a, b, order, aromatic))

    while i < len(smiles):
        char = smiles[i]
        if char == "(":
            if previous is None:
                raise SmilesError(f"{name}: branch opens before an atom at {i}")
            branch.append(previous)
            i += 1
        elif char == ")":
            if not branch:
                raise SmilesError(f"{name}: unmatched ')' at {i}")
            previous = branch.pop()
            i += 1
        elif char in _BONDS:
            pending = _BONDS[char]
            pending_aromatic = char == ":"
            i += 1
        elif char == ".":
            previous = None
            i += 1
        elif char.isdigit() or char == "%":
            label, i = (smiles[i + 1:i + 3], i + 3) if char == "%" else (char, i + 1)
            if previous is None:
                raise SmilesError(f"{name}: ring bond before an atom at {i}")
            if label in rings:
                other, order = rings.pop(label)
                connect(other, previous, order if order is not None else pending,
                        pending_aromatic)
            else:
                rings[label] = (previous, pending)
            pending, pending_aromatic = None, False
        else:
            atom, i = _read_atom(smiles, i, name)
            atoms.append(atom)
            index = len(atoms) - 1
            if previous is not None:
                connect(previous, index, pending, pending_aromatic)
            previous = index
            pending, pending_aromatic = None, False
    if branch:
        raise SmilesError(f"{name}: {len(branch)} unclosed branch(es)")
    if rings:
        raise SmilesError(f"{name}: unclosed ring bond(s) {sorted(rings)}")
    filled = _fill_hydrogens(atoms, bonds)
    return Molecule(name or smiles, smiles, tuple(filled), tuple(bonds))


def _read_atom(smiles: str, i: int, name: str) -> tuple[Atom, int]:
    """One atom, bracketed or from the organic subset, and where it ends."""
    if smiles[i] == "[":
        close = smiles.find("]", i)
        if close < 0:
            raise SmilesError(f"{name}: unclosed '[' at {i}")
        return _read_bracket(smiles[i + 1:close], name, i), close + 1
    for symbol in _ORGANIC:
        if smiles.startswith(symbol, i):
            return Atom(symbol), i + len(symbol)
    if smiles[i] in _AROMATIC:
        return Atom(_AROMATIC[smiles[i]], aromatic=True), i + 1
    raise SmilesError(f"{name}: cannot read {smiles[i]!r} at {i}")


def _read_bracket(body: str, name: str, at: int) -> Atom:
    """`[nH]`, `[N+]`, `[O-]`, `[C@H]` -- symbol, hydrogens, charge.

    A bracket atom's hydrogens are exactly what is written, which is the SMILES
    rule and is also what makes `[OH]` usable as a query for "an oxygen with a
    hydrogen on it" -- a hydroxyl, and not the oxygen of an ester.
    """
    text = body.lstrip("0123456789").replace("@", "")
    if not text:
        raise SmilesError(f"{name}: empty bracket atom at {at}")
    aromatic = text[0] in _AROMATIC
    element = _AROMATIC[text[0]] if aromatic else None
    if element is None:
        element = text[:2] if text[:2] in _ORGANIC else text[:1]
    rest = text[len(text[0]) if aromatic else len(element):]
    hydrogens = 0
    if rest.startswith("H"):
        rest = rest[1:]
        digits = ""
        while rest[:1].isdigit():
            digits, rest = digits + rest[0], rest[1:]
        hydrogens = int(digits) if digits else 1
    charge = 0
    for sign, step in (("+", 1), ("-", -1)):
        while rest.startswith(sign):
            rest = rest[1:]
            digits = ""
            while rest[:1].isdigit():
                digits, rest = digits + rest[0], rest[1:]
            charge += step * (int(digits) if digits else 1)
    if rest:
        raise SmilesError(f"{name}: cannot read bracket atom {body!r} at {at}")
    if element not in VALENCES:
        raise SmilesError(f"{name}: unknown element {element!r} at {at}")
    return Atom(element, aromatic, charge, hydrogens, exact_h=True)


def _fill_hydrogens(atoms: list[Atom], bonds: list[Bond]) -> list[Atom]:
    """Implicit hydrogens for every atom whose count was not written.

    The used valence is the sum of the drawn bond orders, plus one for an
    aromatic carbon or nitrogen: an aromatic ring atom of those two elements
    carries a share of the ring's pi system worth exactly one more bond, which
    is what makes benzene C6H6 and pyridine C5H5N without anyone having to
    Kekulise anything. Aromatic oxygen and sulphur get no such share -- furan's
    oxygen is divalent and already satisfied -- which is why the rule names its
    two elements rather than testing `aromatic` alone.
    """
    used = [0] * len(atoms)
    for bond in bonds:
        used[bond.a] += bond.order
        used[bond.b] += bond.order
    out = []
    for index, atom in enumerate(atoms):
        if atom.exact_h or atom.element == "*":
            out.append(atom)
            continue
        total = used[index] + (1 if atom.aromatic
                               and atom.element in ("C", "N") else 0)
        capacity = next((v for v in VALENCES[atom.element] if v >= total),
                        VALENCES[atom.element][-1])
        out.append(Atom(atom.element, atom.aromatic, atom.charge,
                        max(0, capacity - total)))
    return out


# ===========================================================================
# the compounds
# ===========================================================================


@dataclass(frozen=True)
class Compound:
    """A drug: what it is called, what class a textbook files it under, its
    structure, and the molecular formula that structure has to reproduce."""

    name: str
    klass: str
    smiles: str
    formula: str


#: The nine classes, in the order their colours are assigned. Chosen so the
#: similarity structure is *real* rather than arranged: six of them are
#: defined by a shared scaffold (the sulfanilamide, the aryloxypropanolamine,
#: the 2-arylpropanoic acid, the 4-anilinoquinazoline, the 1,4-benzodiazepin-
#: 2-one, the penam), two by a shared pharmacophore that is not one scaffold
#: (the salicylates and the fenamates, which is why they are the loose blocks
#: in the picture), and one -- the catecholamines -- because it *bridges*: an
#: aryl-CH(OH)-CH2-NH-isopropyl is most of a beta-blocker without the ether
#: oxygen, so isoprenaline and propranolol have to come out neighbours if the
#: fingerprint is doing anything at all.
CLASSES: tuple[str, ...] = (
    "benzodiazepine",
    "fenamate / arylacetate",
    "salicylate",
    "profen",
    "penicillin",
    "catecholamine",
    "beta-blocker",
    "anilinoquinazoline",
    "sulfonamide",
)

#: In alphabetical order, which is the order a supplementary table would come
#: in and therefore the honest "before" for the seriation in panel (a). The
#: clustering never sees `klass`.
COMPOUNDS: tuple[Compound, ...] = (
    Compound("acebutolol", "beta-blocker",
             "CCCC(=O)Nc1ccc(OCC(O)CNC(C)C)c(c1)C(C)=O", "C18H28N2O4"),
    Compound("adrenaline", "catecholamine",
             "CNCC(O)c1ccc(O)c(O)c1", "C9H13NO3"),
    Compound("amoxicillin", "penicillin",
             "CC1(C)SC2C(NC(=O)C(N)c3ccc(O)cc3)C(=O)N2C1C(O)=O",
             "C16H19N3O5S"),
    Compound("ampicillin", "penicillin",
             "CC1(C)SC2C(NC(=O)C(N)c3ccccc3)C(=O)N2C1C(O)=O", "C16H19N3O4S"),
    Compound("aspirin", "salicylate",
             "CC(=O)Oc1ccccc1C(O)=O", "C9H8O4"),
    Compound("atenolol", "beta-blocker",
             "CC(C)NCC(O)COc1ccc(CC(N)=O)cc1", "C14H22N2O3"),
    Compound("diazepam", "benzodiazepine",
             "CN1c2ccc(Cl)cc2C(=NCC1=O)c1ccccc1", "C16H13ClN2O"),
    Compound("diclofenac", "fenamate / arylacetate",
             "OC(=O)Cc1ccccc1Nc1c(Cl)cccc1Cl", "C14H11Cl2NO2"),
    Compound("diflunisal", "salicylate",
             "OC(=O)c1cc(ccc1O)-c1ccc(F)cc1F", "C13H8F2O3"),
    Compound("dopamine", "catecholamine", "NCCc1ccc(O)c(O)c1", "C8H11NO2"),
    Compound("erlotinib", "anilinoquinazoline",
             "C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1", "C22H23N3O4"),
    Compound("fenoprofen", "profen",
             "CC(C(O)=O)c1cccc(Oc2ccccc2)c1", "C15H14O3"),
    Compound("flurbiprofen", "profen",
             "CC(C(O)=O)c1ccc(c(F)c1)-c1ccccc1", "C15H13FO2"),
    Compound("gefitinib", "anilinoquinazoline",
             "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1",
             "C22H24ClFN4O3"),
    Compound("ibuprofen", "profen",
             "CC(C)Cc1ccc(cc1)C(C)C(O)=O", "C13H18O2"),
    Compound("isoprenaline", "catecholamine",
             "CC(C)NCC(O)c1ccc(O)c(O)c1", "C11H17NO3"),
    Compound("ketoprofen", "profen",
             "CC(C(O)=O)c1cccc(c1)C(=O)c1ccccc1", "C16H14O3"),
    Compound("lapatinib", "anilinoquinazoline",
             "CS(=O)(=O)CCNCc1ccc(o1)-c1ccc2ncnc(Nc3ccc(OCc4cccc(F)c4)"
             "c(Cl)c3)c2c1", "C29H26ClFN4O4S"),
    Compound("lorazepam", "benzodiazepine",
             "OC1N=C(c2ccccc2Cl)c2cc(Cl)ccc2NC1=O", "C15H10Cl2N2O2"),
    Compound("mefenamic acid", "fenamate / arylacetate",
             "Cc1ccc(C)c(Nc2ccccc2C(O)=O)c1", "C15H15NO2"),
    Compound("metoprolol", "beta-blocker",
             "COCCc1ccc(OCC(O)CNC(C)C)cc1", "C15H25NO3"),
    Compound("naproxen", "profen",
             "COc1ccc2cc(ccc2c1)C(C)C(O)=O", "C14H14O3"),
    Compound("noradrenaline", "catecholamine",
             "NCC(O)c1ccc(O)c(O)c1", "C8H11NO3"),
    Compound("nordazepam", "benzodiazepine",
             "O=C1CN=C(c2ccccc2)c2cc(Cl)ccc2N1", "C15H11ClN2O"),
    Compound("oxazepam", "benzodiazepine",
             "OC1N=C(c2ccccc2)c2cc(Cl)ccc2NC1=O", "C15H11ClN2O2"),
    Compound("penicillin G", "penicillin",
             "CC1(C)SC2C(NC(=O)Cc3ccccc3)C(=O)N2C1C(O)=O", "C16H18N2O4S"),
    Compound("pindolol", "beta-blocker",
             "CC(C)NCC(O)COc1cccc2[nH]ccc12", "C14H20N2O2"),
    Compound("propranolol", "beta-blocker",
             "CC(C)NCC(O)COc1cccc2ccccc12", "C16H21NO2"),
    Compound("salicylic acid", "salicylate",
             "OC(=O)c1ccccc1O", "C7H6O3"),
    Compound("sulfadiazine", "sulfonamide",
             "Nc1ccc(cc1)S(=O)(=O)Nc1ncccn1", "C10H10N4O2S"),
    Compound("sulfamerazine", "sulfonamide",
             "Cc1ccnc(n1)NS(=O)(=O)c1ccc(N)cc1", "C11H12N4O2S"),
    Compound("sulfamethoxazole", "sulfonamide",
             "Cc1cc(no1)NS(=O)(=O)c1ccc(N)cc1", "C10H11N3O3S"),
    Compound("sulfanilamide", "sulfonamide",
             "Nc1ccc(cc1)S(N)(=O)=O", "C6H8N2O2S"),
    Compound("sulfapyridine", "sulfonamide",
             "Nc1ccc(cc1)S(=O)(=O)Nc1ccccn1", "C11H11N3O2S"),
    Compound("sulfathiazole", "sulfonamide",
             "Nc1ccc(cc1)S(=O)(=O)Nc1nccs1", "C9H9N3O2S2"),
    Compound("timolol", "beta-blocker",
             "CC(C)(C)NCC(O)COc1nsnc1N1CCOCC1", "C13H24N4O3S"),
    Compound("tolfenamic acid", "fenamate / arylacetate",
             "Cc1cccc(Cl)c1Nc1ccccc1C(O)=O", "C14H12ClNO2"),
    Compound("vandetanib", "anilinoquinazoline",
             "COc1cc2c(Nc3ccc(Br)cc3F)ncnc2cc1OCC1CCN(C)CC1",
             "C22H24BrFN4O2"),
)

NAMES: tuple[str, ...] = tuple(c.name for c in COMPOUNDS)


@lru_cache(maxsize=None)
def molecules() -> tuple[Molecule, ...]:
    """Every compound parsed, in `COMPOUNDS` order. Parsed once."""
    return tuple(parse(c.smiles, c.name) for c in COMPOUNDS)


# ===========================================================================
# the fingerprint
# ===========================================================================
#
# ECFP, written out. The idea is Morgan's: give every atom an identifier that
# summarises what it is, then repeatedly replace it by a hash of itself and of
# its neighbours' identifiers, so that after r rounds an atom's identifier is a
# summary of everything within r bonds of it. The set of every identifier that
# ever appeared is the molecule's fingerprint, and two molecules that share a
# substructure share the identifiers that substructure produced.
#
# Three properties matter and each is a test in tests/test_chem_figure.py.
# It is *invariant to atom order*, because nothing anywhere reads an index:
# neighbours enter through a sorted multiset. It is *stable across processes*,
# because the hash is FNV-1a over explicit bytes rather than `hash()`, which
# Python salts per interpreter. And folding is a plain modulo, so a bit is a
# bit and Tanimoto means what it says.

FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
MASK64 = (1 << 64) - 1

#: Two rounds of neighbourhood growth: ECFP4 in the usual naming, where the 4
#: is the diameter. Radius 2 reaches a whole benzene ring from any of its
#: carbons and a sulfonamide from its sulphur, which is the scale of the
#: features this figure is about. Radius 3 starts to hash whole scaffolds and
#: collapses the difference between two members of the same series.
RADIUS = 2

#: 2048 bits, the usual folding width. With 37 compounds of at most 40 heavy
#: atoms the raw identifier count never approaches it -- `bit_collisions()`
#: reports how close it came, and the caption prints that number rather than
#: claiming there were none.
BITS = 2048

#: Bond codes for the hash. Aromatic is its own code rather than order 1, or
#: benzene and cyclohexene would hash alike.
_BOND_CODE = {(1, False): 1, (2, False): 2, (3, False): 3, (1, True): 4}


def fnv1a(values: tuple[int, ...]) -> int:
    """FNV-1a over the big-endian bytes of each value. The stable hash.

    Deliberately not `hash()`: CPython salts string and bytes hashing per
    process, so a fingerprint built on it differs between two runs of the same
    script and the figure stops being byte-identical. Deliberately not
    `hashlib` either -- this is called about a hundred thousand times per
    build and a 64-bit multiply-xor is two orders of magnitude cheaper than a
    SHA-256 of eight bytes.
    """
    digest = FNV_OFFSET
    for value in values:
        for shift in (56, 48, 40, 32, 24, 16, 8, 0):
            digest = ((digest ^ ((value >> shift) & 0xFF)) * FNV_PRIME) & MASK64
    return digest


def initial_identifiers(mol: Molecule) -> tuple[int, ...]:
    """The radius-0 identifier of every atom: the Daylight invariants.

    Heavy-atom degree, the sum of the bond orders on it, atomic number, formal
    charge, attached hydrogens, and whether it is in a ring. Every one of the
    six is a property of the atom in the molecule and none is a property of
    where it happens to sit in the input string, which is the whole reason the
    fingerprint is invariant to atom order.
    """
    near = mol.adjacency()
    order_sum = [0] * len(mol)
    for bond in mol.bonds:
        order_sum[bond.a] += bond.order
        order_sum[bond.b] += bond.order
    return tuple(
        fnv1a((len(near[i]), order_sum[i], ATOMIC_NUMBER[atom.element],
               atom.charge + 8, atom.hydrogens, int(mol.in_ring(i)),
               int(atom.aromatic)))
        for i, atom in enumerate(mol.atoms))


ATOMIC_NUMBER = {"B": 5, "C": 6, "N": 7, "O": 8, "F": 9, "P": 15, "S": 16,
                 "Cl": 17, "Br": 35, "I": 53, "*": 0}


def identifiers(mol: Molecule, radius: int = RADIUS) -> tuple[int, ...]:
    """Every identifier the molecule generates, radius 0 to `radius`, sorted.

    Sorted and de-duplicated: two atoms in identical environments -- the two
    oxygens of a sulfonamide, the six carbons of a benzene -- produce the same
    identifier, and ECFP counts such a feature once. That is what makes the
    Tanimoto coefficient below a comparison of *which* substructures two
    molecules have rather than of how symmetric they happen to be.
    """
    near = mol.adjacency()
    codes = {(min(b.a, b.b), max(b.a, b.b)): _BOND_CODE[(b.order, b.aromatic)]
             for b in mol.bonds}
    current = list(initial_identifiers(mol))
    seen = set(current)
    for step in range(1, radius + 1):
        grown = []
        for atom in range(len(mol)):
            around = sorted(
                (codes[(min(atom, other), max(atom, other))], current[other])
                for other in near[atom])
            grown.append(fnv1a((step, current[atom],
                                *(v for pair in around for v in pair))))
        current = grown
        seen.update(current)
    return tuple(sorted(seen))


def fingerprint(mol: Molecule, radius: int = RADIUS, bits: int = BITS
                ) -> frozenset[int]:
    """The folded fingerprint: which of `bits` bits the molecule sets."""
    return frozenset(i % bits for i in identifiers(mol, radius))


def tanimoto(one: frozenset[int], other: frozenset[int]) -> float:
    """|A and B| / |A or B|. 1.0 for a molecule against itself, 0.0 for two
    that share no feature at all -- and undefined for two empty fingerprints,
    which cannot happen here because every molecule has at least one atom."""
    union = len(one | other)
    return len(one & other) / union if union else 1.0


def bit_collisions(mols: tuple[Molecule, ...] = (), bits: int = BITS) -> int:
    """How many distinct identifiers had to share a bit, over the whole set.

    Folding is lossy and a figure that quotes similarities owes the reader the
    number. Reported in the caption, not asserted to be zero.
    """
    mols = mols or molecules()
    raw: set[int] = set()
    for mol in mols:
        raw.update(identifiers(mol))
    return len(raw) - len({i % bits for i in raw})


@lru_cache(maxsize=None)
def fingerprints() -> tuple[frozenset[int], ...]:
    """Every compound's fingerprint, in `COMPOUNDS` order."""
    return tuple(fingerprint(mol) for mol in molecules())


@lru_cache(maxsize=None)
def similarity() -> tuple[tuple[float, ...], ...]:
    """The full Tanimoto matrix, in `COMPOUNDS` (alphabetical) order."""
    prints = fingerprints()
    return tuple(tuple(tanimoto(a, b) for b in prints) for a in prints)


def folding_cost(bits: int = BITS) -> tuple[float, float]:
    """What folding to `bits` did to the coefficients: median and worst shift.

    Measured against the *unfolded* feature sets -- the same Tanimoto over the
    raw identifiers, where no two features can share a slot. Folding can only
    add to an intersection, so every shift is upward and the number is the
    honest cost of a fixed-width fingerprint. It is printed in the caption
    rather than assumed away: at 2048 bits over these 37 compounds the median
    pair moves by under a hundredth and the worst by about a twentieth, and
    both of those are facts a reader is entitled to.
    """
    mols = molecules()
    raw = [frozenset(identifiers(mol)) for mol in mols]
    folded = [frozenset(i % bits for i in one) for one in raw]
    shifts = sorted(
        abs(tanimoto(folded[i], folded[j]) - tanimoto(raw[i], raw[j]))
        for i in range(len(mols)) for j in range(i + 1, len(mols)))
    return shifts[len(shifts) // 2], shifts[-1]


# ===========================================================================
# ordering the set
# ===========================================================================
#
# A similarity matrix in alphabetical order is a picture of the alphabet. The
# blocks are all there -- every one of them -- and none of them is visible,
# because the rows of a block are scattered down the axis. Reordering the rows
# and columns by the same permutation changes nothing about the data and
# everything about whether a reader can see it, so the permutation has to be
# derived rather than arranged, and its worth has to be a number.


def distances() -> tuple[tuple[float, ...], ...]:
    """1 - Tanimoto, which is a metric on binary fingerprints (Lipkus 1999)."""
    sim = similarity()
    return tuple(tuple(1.0 - value for value in row) for row in sim)


@dataclass(frozen=True)
class Merge:
    """One step of the clustering: two child nodes and the height they joined.

    Children below `len(COMPOUNDS)` are leaves; the rest index earlier merges,
    so merge `k` is node `n + k`, which is the convention `linkage` in every
    other language uses and the one `dendrogram()` reads back.
    """

    left: int
    right: int
    height: float
    size: int


def linkage(dist: tuple[tuple[float, ...], ...] | None = None
            ) -> tuple[Merge, ...]:
    """Average-linkage agglomerative clustering, exact and deterministic.

    UPGMA: the distance between two clusters is the mean distance between
    their members, maintained through the Lance-Williams update so it stays
    exact as clusters merge rather than being recomputed from a centroid that
    no molecule is at. Average linkage, and not single (which chains a whole
    figure into one smear through its nearest neighbours) or complete (which
    is dominated by the one most distant pair in each cluster and so splits
    real series).

    Ties are broken on the pair of cluster ids, smallest first, so the tree is
    a function of the distances alone. That matters more here than it sounds:
    two compounds that differ by nothing the fingerprint can see -- and there
    are none in this set, but there could be -- would otherwise merge in
    whatever order a set happened to iterate in.
    """
    dist = dist or distances()
    n = len(dist)
    between = {(i, j): dist[i][j] for i in range(n) for j in range(i + 1, n)}
    size = {i: 1 for i in range(n)}
    active = list(range(n))
    merges: list[Merge] = []

    def gap(a: int, b: int) -> float:
        return between[(a, b) if a < b else (b, a)]

    for step in range(n - 1):
        first, second = min(
            ((a, b) for i, a in enumerate(active) for b in active[i + 1:]),
            key=lambda pair: (gap(*pair), pair))
        node = n + step
        merges.append(Merge(first, second, gap(first, second),
                            size[first] + size[second]))
        for other in active:
            if other in (first, second):
                continue
            joined = (size[first] * gap(first, other)
                      + size[second] * gap(second, other))
            between[(min(node, other), max(node, other))] = (
                joined / (size[first] + size[second]))
        size[node] = size[first] + size[second]
        active = [c for c in active if c not in (first, second)] + [node]
    return tuple(merges)


def _subtree_leaves(merges: tuple[Merge, ...], n: int) -> dict[int, tuple[int, ...]]:
    """Leaves under every node, in the tree's own left-to-right order."""
    under: dict[int, tuple[int, ...]] = {i: (i,) for i in range(n)}
    for step, merge in enumerate(merges):
        under[n + step] = under[merge.left] + under[merge.right]
    return under


def optimal_leaf_order(merges: tuple[Merge, ...] | None = None,
                       sim: tuple[tuple[float, ...], ...] | None = None
                       ) -> tuple[int, ...]:
    """Bar-Joseph optimal leaf ordering: the exact dynamic program.

    A dendrogram fixes which leaves are adjacent to which *groups*, but every
    internal node may be flipped, so a tree of n leaves admits 2^(n-1)
    orderings -- 6.9e10 of them here -- all equally consistent with the
    clustering. Bar-Joseph, Gifford and Jaakkola (2001) find the best of them
    in polynomial time: for each subtree and each choice of its leftmost and
    rightmost leaf, the best interior arrangement is built from the same
    answer for its two children, so the only thing ever searched is which
    child goes first and which pair of leaves meets at the seam.

    What is maximised is the sum of Tanimoto similarity over adjacent rows --
    `neighbour_similarity()` -- which is the quantity the eye reads off the
    diagonal of panel (a).
    """
    sim = sim or similarity()
    n = len(sim)
    merges = merges or linkage()
    under = _subtree_leaves(merges, n)

    # best[(node, first, last)] -> (score, how) where `how` is what to recurse
    # into: the two child nodes in the order they are laid out, and the two
    # leaves that meet at their seam.
    best: dict[tuple[int, int, int], tuple[float, tuple]] = {
        (leaf, leaf, leaf): (0.0, ()) for leaf in range(n)}
    # The (leftmost, rightmost) pairs a node can present. A leaf has one; an
    # internal node has one for each way of taking a leaf from either child,
    # which is why the whole thing is polynomial rather than exponential.
    ends: dict[int, tuple[tuple[int, int], ...]] = {
        leaf: ((leaf, leaf),) for leaf in range(n)}
    for step, merge in enumerate(merges):
        node = n + step
        for near, far in ((merge.left, merge.right), (merge.right, merge.left)):
            for head, seam in ends[near]:
                left_score = best[(near, head, seam)][0]
                row = sim[seam]
                for start, tail in ends[far]:
                    total = (left_score + row[start]
                             + best[(far, start, tail)][0])
                    key = (node, head, tail)
                    if key not in best or total > best[key][0]:
                        best[key] = (total, (near, head, seam,
                                             far, start, tail))
        ends[node] = tuple(sorted(
            (head, tail) for head in under[merge.left]
            for tail in under[merge.right])) + tuple(sorted(
                (head, tail) for head in under[merge.right]
                for tail in under[merge.left]))

    root = n + len(merges) - 1
    head, tail = max(sorted(ends[root]),
                     key=lambda pair: best[(root, *pair)][0])

    def walk(node: int, first: int, last: int) -> list[int]:
        how = best[(node, first, last)][1]
        if not how:
            return [node]
        near, head_, seam, far, start, tail_ = how
        return walk(near, head_, seam) + walk(far, start, tail_)

    return tuple(walk(root, head, tail))


def dendrogram_order(merges: tuple[Merge, ...] | None = None) -> tuple[int, ...]:
    """The tree's leaves as the clustering happened to build them.

    The foil for `optimal_leaf_order`: the same tree, every flip left as the
    merge order left it. Any ordering read straight off a dendrogram is one of
    these, and the figure quotes what the optimisation was worth against it.
    """
    merges = merges or linkage()
    n = len(merges) + 1
    return _subtree_leaves(merges, n)[n + len(merges) - 1]


def neighbour_similarity(order: tuple[int, ...],
                         sim: tuple[tuple[float, ...], ...] | None = None
                         ) -> float:
    """Summed Tanimoto over adjacent rows: what the leaf ordering maximises."""
    sim = sim or similarity()
    return sum(sim[a][b] for a, b in zip(order, order[1:]))


def band_energy(order: tuple[int, ...],
                sim: tuple[tuple[float, ...], ...] | None = None) -> float:
    """Mean rank separation of a unit of similarity: lower is more banded.

    sum(S_ij * |i - j|) / sum(S_ij) over the off-diagonal, with i and j the
    *positions* in `order` rather than the compound indices. It answers the
    question a reader actually asks of a seriated matrix -- how far from the
    diagonal does the ink sit -- in units of rows, so 3.1 against 11.4 means
    the average unit of similarity moved eight rows closer to the diagonal.
    Unlike the objective the ordering was chosen by, it is global: an ordering
    can win on adjacent pairs and still leave a block split across the page.
    """
    sim = sim or similarity()
    weight = span = 0.0
    for i, a in enumerate(order):
        for j, b in enumerate(order):
            if i == j:
                continue
            weight += sim[a][b]
            span += sim[a][b] * abs(i - j)
    return span / weight if weight else 0.0


@lru_cache(maxsize=None)
def seriation() -> tuple[int, ...]:
    """The order the figure draws its compounds in. Computed, never typed."""
    return optimal_leaf_order()


@dataclass(frozen=True)
class Block:
    """One textbook class as it lands in the seriated order.

    `first` and `last` are positions in `seriation()`, inclusive. A block only
    exists because the class turned out to be contiguous there; `blocks()`
    raises rather than drawing a box over a class that is not, because a box
    round a discontiguous set is a lie about the picture.
    """

    klass: str
    first: int
    last: int

    @property
    def size(self) -> int:
        return self.last - self.first + 1


def blocks(order: tuple[int, ...] | None = None) -> tuple[Block, ...]:
    """Each class as one run of the seriated order, left to right.

    This is the figure's central result and it is checked rather than assumed:
    the ordering is computed from the fingerprints, which never see `klass`,
    and every one of the nine classes still comes out as an unbroken run. If
    one did not, this raises and the figure does not build -- there is no
    version of it that quietly draws a box round half a class.
    """
    order = order or seriation()
    place = {leaf: i for i, leaf in enumerate(order)}
    found: list[Block] = []
    for klass in CLASSES:
        spots = sorted(place[i] for i, c in enumerate(COMPOUNDS)
                       if c.klass == klass)
        if spots != list(range(spots[0], spots[-1] + 1)):
            raise ValueError(f"{klass} is not contiguous in this order: {spots}")
        found.append(Block(klass, spots[0], spots[-1]))
    return tuple(sorted(found, key=lambda b: b.first))


def contiguity_odds(order: tuple[int, ...] | None = None) -> float:
    """The chance that a random ordering would make every class contiguous.

    k! * prod(size!) / n!, exactly: the orderings in which each class is an
    unbroken run are the orderings of the blocks times the orderings inside
    them. With nine classes over thirty-eight compounds that is about one in
    10^25, which is the number the caption prints -- the ordering was
    computed from structure alone, and structure alone reproduced the
    pharmacology.
    """
    sizes = [b.size for b in blocks(order)]
    ways = math.factorial(len(sizes))
    for size in sizes:
        ways *= math.factorial(size)
    return ways / math.factorial(len(COMPOUNDS))


def block_similarity(order: tuple[int, ...] | None = None
                     ) -> tuple[tuple[str, tuple[float, ...], tuple[float, ...]], ...]:
    """Per class: every within-class coefficient, and every one that leaves it.

    Both as raw lists rather than means, because panel (e) draws the points
    and a mean drawn as a bar is the part of a figure a reader cannot check.
    """
    sim = similarity()
    out = []
    for block in blocks(order):
        inside = [i for i, c in enumerate(COMPOUNDS) if c.klass == block.klass]
        outside = [i for i, c in enumerate(COMPOUNDS) if c.klass != block.klass]
        within = tuple(sim[a][b] for k, a in enumerate(inside)
                       for b in inside[k + 1:])
        between = tuple(sim[a][b] for a in inside for b in outside)
        out.append((block.klass, within, between))
    return tuple(out)


def dendrogram(order: tuple[int, ...] | None = None
               ) -> tuple[tuple[float, float, float, float], ...]:
    """The tree over the seriated axis, as (x0, x1, height, child height) rungs.

    One entry per merge: the two child positions along the compound axis and
    the heights the rung joins. Positions are in compound-index units -- 0 for
    the leftmost row of panel (a) -- so the dendrogram lands on the matrix
    without the figure computing a pitch twice.
    """
    order = order or seriation()
    merges = linkage()
    n = len(merges) + 1
    place = {leaf: float(i) for i, leaf in enumerate(order)}
    height = {leaf: 0.0 for leaf in range(n)}
    rungs = []
    for step, merge in enumerate(merges):
        node = n + step
        left, right = sorted((place[merge.left], place[merge.right]))
        rungs.append((left, right, merge.height,
                      max(height[merge.left], height[merge.right])))
        place[node] = (left + right) / 2.0
        height[node] = merge.height
    return tuple(rungs)


# ===========================================================================
# named substructures
# ===========================================================================
#
# A fingerprint says two compounds are alike; it cannot say what about them is
# alike, because a folded bit is a hash and hashes do not explain themselves.
# The vocabulary below is the other half of the argument: a small set of named
# fragments, each written as a query graph in the same SMILES dialect, each
# matched against each compound by explicit subgraph isomorphism. Nothing is
# inferred from the fingerprint and nothing is inferred from the class -- if
# the picture says naproxen contains a 2-arylpropanoate, a backtracking search
# found one.


def _query_order(pattern: Molecule) -> tuple[int, ...]:
    """Pattern atoms in an order where each has an already-placed neighbour.

    A connected order turns the search from "try every injection" into "extend
    along a bond", which is the whole of VF2's feasibility rule and is what
    keeps a twelve-atom query over a forty-atom molecule instant.
    """
    near = pattern.adjacency()
    order = [0]
    seen = {0}
    while len(order) < len(pattern):
        nxt = next((other for atom in order for other in near[atom]
                    if other not in seen), None)
        if nxt is None:                       # a second component: start it
            nxt = next(i for i in range(len(pattern)) if i not in seen)
        order.append(nxt)
        seen.add(nxt)
    return tuple(order)


def _atom_fits(query: Atom, atom: Atom) -> bool:
    """Whether a target atom can stand for a query atom.

    Element and aromaticity both, because `C` and `c` are different questions
    -- cyclohexane is not benzene and a query that could not tell them apart
    would put "benzene" against every compound in the set. Charge always.
    Hydrogen count only when the query *wrote* it: `[OH]` is a hydroxyl and
    must not match the oxygen of an ester, while a plain `O` is any oxygen.
    """
    if query.element == "*":
        return True
    return (query.element == atom.element
            and query.aromatic == atom.aromatic
            and query.charge == atom.charge
            and (not query.exact_h or query.hydrogens == atom.hydrogens))


def _bond_fits(query: Bond, bond: Bond) -> bool:
    return query.aromatic == bond.aromatic and query.order == bond.order


def match_all(pattern: Molecule, target: Molecule
              ) -> tuple[tuple[int, ...], ...]:
    """Every distinct set of target atoms the pattern maps onto, sorted.

    Subgraph *monomorphism*, not induced isomorphism: every bond of the query
    must exist in the target, and the target may have bonds the query does not
    mention. That is what "contains a benzene ring" means -- toluene contains
    one -- and an induced match would answer no to almost every question a
    medicinal chemist asks.

    Distinct atom *sets*, so a benzene ring is found once and not twelve times
    over its own symmetry. Counting automorphisms as occurrences is how a
    fragment census ends up saying naphthalene has four benzene rings.
    """
    order = _query_order(pattern)
    near = pattern.adjacency()
    place = {atom: step for step, atom in enumerate(order)}
    # For each query atom, the already-placed neighbours it must join to.
    anchors = tuple(
        tuple((other, pattern.bond_between(atom, other))
              for other in near[atom] if place[other] < place[atom])
        for atom in order)
    target_near = target.adjacency()
    found: set[frozenset[int]] = set()
    mapping: dict[int, int] = {}
    used: set[int] = set()

    def extend(step: int) -> None:
        if step == len(order):
            found.add(frozenset(mapping.values()))
            return
        atom = order[step]
        query_atom = pattern.atoms[atom]
        if anchors[step]:
            first, _ = anchors[step][0]
            candidates: Iterable = target_near[mapping[first]]
        else:
            candidates = range(len(target))
        for here in candidates:
            if here in used or not _atom_fits(query_atom, target.atoms[here]):
                continue
            if all((bond := target.bond_between(mapping[other], here))
                   is not None and _bond_fits(want, bond)
                   for other, want in anchors[step]):
                mapping[atom] = here
                used.add(here)
                extend(step + 1)
                del mapping[atom]
                used.discard(here)

    extend(0)
    return tuple(sorted(tuple(sorted(hit)) for hit in found))


def contains(pattern: Molecule, target: Molecule) -> bool:
    """Whether the pattern occurs at all. Stops at the first hit."""
    return bool(match_all(pattern, target))


@dataclass(frozen=True)
class Fragment:
    """A named substructure and the query graphs that count as it.

    `patterns` is a tuple because some perfectly ordinary chemical names are
    not one graph: "aryl halide" is four, one per halogen, and writing them as
    four rows of the picture would say something about fluorine that the
    figure does not mean. `drawn` is the pattern the row label depicts, which
    is the first unless another is more recognisable.
    """

    name: str
    patterns: tuple[str, ...]
    note: str
    drawn: int = 0


#: Seventeen fragments, chosen to be the answer to "what makes this block a
#: block". Every one is a name a chemist uses out loud, every one is matched
#: rather than assigned, and between them they separate all nine classes --
#: which is the test the vocabulary has to pass and `tests/test_chem_figure.py`
#: makes it pass explicitly.
FRAGMENTS: tuple[Fragment, ...] = (
    Fragment("benzene", ("c1ccccc1",),
             "a six-carbon aromatic ring; nearly everything has one"),
    Fragment("benzo-fused ring", ("c1ccc2ccccc2c1", "c1ccc2ncncc2c1",
                                  "c1ccc2[nH]ccc2c1", "c1ccc2c(c1)C=NCC(=O)N2"),
             "a second ring sharing an edge with a benzene"),
    Fragment("pyrimidine", ("c1cncnc1",), "the 1,3-diazine ring"),
    Fragment("5-ring heteroarene", ("c1ccno1", "c1cscn1", "c1cnsn1",
                                    "c1cc[nH]c1", "c1ccoc1"),
             "isoxazole, thiazole, thiadiazole, pyrrole, furan"),
    Fragment("aryl sulfonamide", ("cS(=O)(=O)N",),
             "the sulfanilamide warhead"),
    Fragment("aryl amine", ("c[NH2]",), "a primary amine straight on a ring"),
    Fragment("diarylamine", ("c[NH]c",),
             "one nitrogen bridging two aromatic rings"),
    Fragment("carboxylic acid", ("C(=O)[OH]",), "the free acid, not an ester"),
    Fragment("2-arylpropanoate", ("cC(C)C(=O)[OH]",),
             "the profen head: an acid on a methylated benzylic carbon"),
    Fragment("amide", ("C(=O)N",), "including the lactams"),
    Fragment("beta-lactam", ("C1C(=O)NC1",), "the four-membered penam ring"),
    Fragment("phenol", ("c[OH]",), "a hydroxyl straight on a ring"),
    Fragment("catechol", ("[OH]c1ccccc1[OH]",), "two hydroxyls, ortho"),
    Fragment("aryl ether", ("cO[CH3]", "cO[CH2]", "cOc"),
             "an ether with an aryl side -- and not an aryl ester, which is "
             "why the alkyl carbon has to carry hydrogens"),
    Fragment("benzylic aminoethanol", ("cC([OH])CN",),
             "the catecholamine side chain"),
    Fragment("aryloxypropanolamine", ("cOCC([OH])C[NH]",),
             "the whole beta-blocker side chain, in one query"),
    Fragment("aryl halide", ("cCl", "cF", "cBr", "cI"),
             "a halogen straight on a ring"),
)


@lru_cache(maxsize=None)
def fragment_queries() -> tuple[tuple[Molecule, ...], ...]:
    """Every fragment's patterns, parsed once, in `FRAGMENTS` order."""
    return tuple(tuple(parse(p, f.name) for p in f.patterns)
                 for f in FRAGMENTS)


@lru_cache(maxsize=None)
def incidence() -> tuple[tuple[bool, ...], ...]:
    """`incidence()[f][c]` -- does compound `c` contain fragment `f`?

    Rows are fragments in `FRAGMENTS` order, columns compounds in `COMPOUNDS`
    order; the figure reorders columns by `seriation()` and nothing else.
    """
    mols = molecules()
    return tuple(tuple(any(contains(q, mol) for q in queries) for mol in mols)
                 for queries in fragment_queries())


def fragment_enrichment(name: str) -> tuple[tuple[str, float], ...]:
    """For one fragment, the fraction of each class that carries it."""
    row = incidence()[[f.name for f in FRAGMENTS].index(name)]
    out = []
    for klass in CLASSES:
        members = [i for i, c in enumerate(COMPOUNDS) if c.klass == klass]
        out.append((klass, sum(row[i] for i in members) / len(members)))
    return tuple(out)


def fragment_jaccard(one: int, other: int) -> float:
    """How much two compounds' *named* fragment sets overlap.

    The independent check on the fingerprint: panel (e) plots this against
    Tanimoto over all 703 pairs. The two are computed from the same graphs and
    from nothing else in common -- one is a hash of every neighbourhood, the
    other is seventeen hand-written queries -- so their agreement is
    evidence that the hashing is finding chemistry rather than noise.
    """
    rows = incidence()
    mine = {f for f, row in enumerate(rows) if row[one]}
    theirs = {f for f, row in enumerate(rows) if row[other]}
    union = mine | theirs
    return len(mine & theirs) / len(union) if union else 0.0


def spearman(one: Sequence[float], other: Sequence[float]) -> float:
    """Rank correlation, with ties given their mean rank.

    Rank and not Pearson because neither axis of panel (e) is on a scale where
    a difference of 0.1 means the same thing everywhere: a Tanimoto of 0.9 is
    a far bigger step from 0.8 than 0.2 is from 0.1, and a fragment Jaccard
    over seventeen queries takes about forty distinct values. What the panel
    claims is that the two agree on the *order* of a pair, and that is what
    this measures. Ties matter here -- 636 of the 703 pairs share a handful of
    Jaccard values -- so they get the mean of the ranks they span rather than
    an arbitrary one, which is what keeps the coefficient from depending on
    the order the pairs happened to be generated in.
    """
    if len(one) != len(other):
        raise ValueError(f"spearman needs equal lengths, "
                         f"got {len(one)} and {len(other)}")
    first, second = _ranks(one), _ranks(other)
    mean_a = sum(first) / len(first)
    mean_b = sum(second) / len(second)
    top = sum((a - mean_a) * (b - mean_b) for a, b in zip(first, second))
    left = sum((a - mean_a) ** 2 for a in first)
    right = sum((b - mean_b) ** 2 for b in second)
    return top / math.sqrt(left * right) if left and right else 0.0


def _ranks(values: Sequence[float]) -> list[float]:
    """Ranks from 1, each member of a tied run given the run's mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    start = 0
    while start < len(order):
        stop = start
        while (stop + 1 < len(order)
               and values[order[stop + 1]] == values[order[start]]):
            stop += 1
        shared = (start + stop) / 2.0 + 1.0
        for position in range(start, stop + 1):
            out[order[position]] = shared
        start = stop + 1
    return out


# ===========================================================================
# where to draw each atom
# ===========================================================================
#
# A structural formula is a claim about a real compound and it is read as one:
# every ring closes, every bond is the same length, and nothing crosses
# anything. No rule in the drawing library can see any of that -- to the linter
# a molecule is one path node with a correct bounding box -- so the geometry is
# produced here, under a test, rather than nudged until it photographs well.
#
# The layout is the standard two-stage one. Ring systems are rigid: a ring is a
# regular polygon of unit edge, and a ring fused to a placed one is reflected
# across the bond they share, which is exact and needs no search. Everything
# else grows outwards a bond at a time at 120 degrees, taking whichever of the
# two 120-degree choices leaves the most room -- which is the rule a chemist's
# hand follows and, on this set, produces no crossing and no near-miss.
#
# `depiction_faults()` is the check, and `tests/test_chem_figure.py` runs it
# over every compound the figure draws: uniform bond length, no two unbonded
# atoms closer than two-thirds of a bond, no pair of bonds crossing.

TWELFTH = math.pi / 6.0


def _unit(dx: float, dy: float) -> tuple[float, float]:
    span = math.hypot(dx, dy)
    return (dx / span, dy / span) if span > 1e-9 else (1.0, 0.0)


def _turn(vector: tuple[float, float], angle: float) -> tuple[float, float]:
    cos, sin = math.cos(angle), math.sin(angle)
    return (vector[0] * cos - vector[1] * sin,
            vector[0] * sin + vector[1] * cos)


def _ring_radius(size: int) -> float:
    """Circumradius of a regular polygon whose every edge is one bond."""
    return 0.5 / math.sin(math.pi / size)


def _place_ring_system(mol: Molecule, atoms: tuple[int, ...],
                       ) -> dict[int, tuple[float, float]]:
    """One fused ring system in its own frame, first ring on the origin."""
    rings = [r for r in mol.rings() if set(r) <= set(atoms)]
    rings.sort(key=lambda r: (-len(r), r))
    pos: dict[int, tuple[float, float]] = {}
    centres: list[tuple[float, float]] = []
    pending = list(rings)

    seed = pending.pop(0)
    radius = _ring_radius(len(seed))
    # Phase chosen so a hexagon stands on a flat edge, which is how every
    # printed benzene sits and what makes two fused rings share a vertical bond.
    phase = math.pi / 2.0 + math.pi / len(seed)
    for step, atom in enumerate(seed):
        angle = phase + 2.0 * math.pi * step / len(seed)
        pos[atom] = (radius * math.cos(angle), radius * math.sin(angle))
    centres.append((0.0, 0.0))

    while pending:
        share = next((r for r in pending
                      if len([a for a in r if a in pos]) >= 2), None)
        if share is None:                      # spiro or detached: give up here
            share = pending[0]
        pending.remove(share)
        known = [a for a in share if a in pos]
        if len(known) < 2:
            continue
        # The shared edge, as a pair adjacent in the new ring's own cycle.
        edge = next(((u, v) for u, v in zip(share, share[1:] + share[:1])
                     if u in pos and v in pos), None)
        if edge is None:
            continue
        first, second = pos[edge[0]], pos[edge[1]]
        middle = ((first[0] + second[0]) / 2.0, (first[1] + second[1]) / 2.0)
        along = _unit(second[0] - first[0], second[1] - first[1])
        normal = (-along[1], along[0])
        inward = min(centres, key=lambda c: (c[0] - middle[0]) ** 2
                     + (c[1] - middle[1]) ** 2)
        if ((inward[0] - middle[0]) * normal[0]
                + (inward[1] - middle[1]) * normal[1]) > 0:
            normal = (-normal[0], -normal[1])
        size = len(share)
        radius = _ring_radius(size)
        apothem = math.sqrt(max(radius * radius - 0.25, 0.0))
        centre = (middle[0] + normal[0] * apothem,
                  middle[1] + normal[1] * apothem)
        centres.append(centre)
        base = math.atan2(first[1] - centre[1], first[0] - centre[0])
        cycle = list(share)
        start = cycle.index(edge[0])
        cycle = cycle[start:] + cycle[:start]
        step_angle = 2.0 * math.pi / size
        # Which way round the cycle runs is fixed by where its second atom
        # already is; getting it backwards folds the new ring onto the old one.
        towards = math.atan2(second[1] - centre[1], second[0] - centre[0])
        direction = 1.0 if math.sin(towards - base) > 0 else -1.0
        for step, atom in enumerate(cycle):
            if atom in pos:
                continue
            angle = base + direction * step_angle * step
            pos[atom] = (centre[0] + radius * math.cos(angle),
                         centre[1] + radius * math.sin(angle))
    return pos


def _crosses(a: tuple[float, float], b: tuple[float, float],
             c: tuple[float, float], d: tuple[float, float]) -> bool:
    """Whether segments ab and cd properly cross. Shared ends do not count."""
    def side(p, q, r):
        return ((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]))
    if a in (c, d) or b in (c, d):
        return False
    d1, d2 = side(a, b, c), side(a, b, d)
    d3, d4 = side(c, d, a), side(c, d, b)
    return (d1 * d2 < -1e-12) and (d3 * d4 < -1e-12)


def _room(where: tuple[float, float], pos: dict[int, tuple[float, float]],
          skip: int) -> float:
    """Distance from a candidate site to the nearest atom already drawn."""
    return min((math.hypot(where[0] - p[0], where[1] - p[1])
                for atom, p in pos.items() if atom != skip),
               default=99.0)


def _drawn_bonds(mol: Molecule, pos: dict[int, tuple[float, float]]
                 ) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """The segments already on the page, for the crossing test."""
    return [(pos[b.a], pos[b.b]) for b in mol.bonds
            if b.a in pos and b.b in pos]


def _placement_cost(mol: Molecule, pos: dict[int, tuple[float, float]],
                    fresh: dict[int, tuple[float, float]]) -> tuple[int, float]:
    """How bad it would be to add `fresh` to `pos`: crossings, then crowding.

    Crossings first and clearance second, because a crossing is a different
    molecule and a tight pair is only an ugly one. Both are measured on the
    real segments rather than guessed from angles, which is what lets one rule
    serve a lone substituent and a whole fused ring system alike.
    """
    joined = mol.bond_index()
    settled = dict(pos)
    settled.update(fresh)
    old = _drawn_bonds(mol, pos)
    added = [(settled[b.a], settled[b.b]) for b in mol.bonds
             if b.a in settled and b.b in settled
             and (b.a in fresh or b.b in fresh)]
    crossings = sum(1 for one in added for other in old
                    if _crosses(*one, *other))
    crossings += sum(1 for i, one in enumerate(added)
                     for other in added[i + 1:] if _crosses(*one, *other))
    gap = 99.0
    for atom, point in fresh.items():
        for other, elsewhere in settled.items():
            if other == atom or (atom, other) in joined:
                continue
            gap = min(gap, math.hypot(point[0] - elsewhere[0],
                                      point[1] - elsewhere[1]))
    return crossings, gap


#: Clearance, in bond lengths, past which one placement is no roomier than
#: another as far as the reader is concerned: a whole bond length of air
#: between two atoms that are not bonded. Above it the tie is broken by
#: convention instead -- see `grow`.
ROOMY = 1.0


def depiction(mol: Molecule) -> tuple[tuple[float, float], ...]:
    """Coordinates for every atom, in bond lengths, y upwards.

    Deterministic: the seed ring, the order rings are fused in, the order
    atoms are grown in and the choice between two equally good directions are
    all resolved by atom index. The same molecule always draws the same way,
    which is what lets the figure be byte-identical and what lets a test
    assert that the picture has no crossing bonds.
    """
    near = mol.adjacency()
    systems = _ring_systems(mol)
    home = {atom: index for index, group in enumerate(systems) for atom in group}
    local = [_place_ring_system(mol, group) for group in systems]
    pos: dict[int, tuple[float, float]] = {}

    def settled(index: int, entry: int, at: tuple[float, float],
                facing: tuple[float, float], flip: float
                ) -> dict[int, tuple[float, float]]:
        """Ring system `index` with `entry` on `at`, its outward direction
        along `facing`, optionally mirrored. A ring hung off a chain has two
        orientations and only one of them usually keeps clear."""
        frame = local[index]
        middle = (sum(p[0] for p in frame.values()) / len(frame),
                  sum(p[1] for p in frame.values()) / len(frame))
        turned = {a: (p[0] - middle[0], flip * (p[1] - middle[1]))
                  for a, p in frame.items()}
        # The vector from the system's centroid out to its entry atom has to
        # end up pointing *back* at the parent, so that the rest of the ring
        # extends away from the chain instead of folding over it.
        out = _unit(*turned[entry])
        angle = math.atan2(-facing[1], -facing[0]) - math.atan2(out[1], out[0])
        moved = {}
        for atom, point in turned.items():
            spun = _turn((point[0] - turned[entry][0],
                          point[1] - turned[entry][1]), angle)
            moved[atom] = (at[0] + spun[0], at[1] + spun[1])
        return moved

    #: Candidate bond directions when an atom already carries two or more.
    #: Every 15 degrees, so a fourth bond on a sulfonamide sulphur has
    #: somewhere to go that is not on top of the third.
    wheel = [(math.cos(k * math.pi / 12.0), math.sin(k * math.pi / 12.0))
             for k in range(24)]

    def ways(parent: int) -> list[tuple[float, float]]:
        """Where a new bond off `parent` could point, best first."""
        taken = [_unit(pos[other][0] - pos[parent][0],
                       pos[other][1] - pos[parent][1])
                 for other in near[parent] if other in pos]
        if not taken:
            return [(1.0, 0.0)]
        if len(taken) == 1:
            # The chemist's zig-zag: 120 degrees off the bond that is there,
            # either way, and straight on only if both are blocked.
            return [_turn(taken[0], 4.0 * TWELFTH),
                    _turn(taken[0], -4.0 * TWELFTH),
                    (-taken[0][0], -taken[0][1])]
        def clearance(way: tuple[float, float]) -> float:
            return min(math.acos(max(-1.0, min(1.0, way[0] * t[0] + way[1] * t[1])))
                       for t in taken)
        return sorted(wheel, key=lambda w: (-round(clearance(w), 6),
                                            wheel.index(w)))[:8]

    def grow(parent: int, atom: int) -> None:
        """Put one new atom -- or the whole ring system it belongs to -- down."""
        best: tuple[tuple, dict] | None = None
        for rank, way in enumerate(ways(parent)):
            where = (pos[parent][0] + way[0], pos[parent][1] + way[1])
            tries = ([settled(home[atom], atom, where, way, flip)
                      for flip in (1.0, -1.0)] if atom in home
                     else [{atom: where}])
            for order, fresh in enumerate(tries):
                crossings, gap = _placement_cost(mol, pos, fresh)
                # Clamped, and the clamp is the whole point: above ROOMY a
                # placement is simply *fine*, and comparing two fine
                # placements on their millimetres is how the drawing loses its
                # chemistry. Diclofenac learned this the hard way -- the
                # straight-on direction off its CH2 left more air than either
                # 120-degree one, so the layout chose it, and the CH2 vanished
                # into a long straight line between the ring and the
                # carboxyl. A vertex a reader cannot see is a missing atom.
                # With the clamp, every roomy candidate ties here and `rank`
                # decides, which is `ways()` speaking: zig-zag first.
                key = (-crossings, round(min(gap, ROOMY), 6), -rank, -order)
                if best is None or key > best[0]:
                    best = (key, fresh)
        pos.update(best[1])

    if systems:
        biggest = max(range(len(systems)),
                      key=lambda i: (len(systems[i]), -systems[i][0]))
        pos.update(local[biggest])
    else:
        pos[0] = (0.0, 0.0)
    while len(pos) < len(mol):
        grew = False
        for parent in sorted(pos):
            for atom in near[parent]:
                if atom not in pos:
                    grow(parent, atom)
                    grew = True
        if not grew:                           # a second component: seed it
            loose = min(i for i in range(len(mol)) if i not in pos)
            aside = (max(p[0] for p in pos.values()) + 2.0, 0.0)
            pos.update(settled(home[loose], loose, aside, (1.0, 0.0), 1.0)
                       if loose in home else {loose: aside})
    middle_x = (min(p[0] for p in pos.values())
                + max(p[0] for p in pos.values())) / 2.0
    middle_y = (min(p[1] for p in pos.values())
                + max(p[1] for p in pos.values())) / 2.0
    return tuple((pos[i][0] - middle_x, pos[i][1] - middle_y)
                 for i in range(len(mol)))


def depiction_faults(mol: Molecule, *, clearance: float = 0.66
                     ) -> tuple[str, ...]:
    """Everything wrong with the drawing of `mol`, as sentences.

    Empty means the picture is safe to print: every bond one unit long, no two
    unbonded atoms within `clearance` of each other, no two bonds crossing. A
    structural formula that fails any of the three is not a worse drawing of
    the compound, it is a drawing of a different compound.
    """
    where = depiction(mol)
    faults: list[str] = []
    for bond in mol.bonds:
        length = math.dist(where[bond.a], where[bond.b])
        if abs(length - 1.0) > 0.02:
            faults.append(f"bond {bond.a}-{bond.b} is {length:.3f} bonds long")
    joined = {(min(b.a, b.b), max(b.a, b.b)) for b in mol.bonds}
    for i in range(len(mol)):
        for j in range(i + 1, len(mol)):
            if (i, j) in joined:
                continue
            gap = math.dist(where[i], where[j])
            if gap < clearance:
                faults.append(f"atoms {i} and {j} are {gap:.3f} bonds apart")
    bonds = sorted(joined)
    for index, (a, b) in enumerate(bonds):
        for c, d in bonds[index + 1:]:
            if _crosses(where[a], where[b], where[c], where[d]):
                faults.append(f"bond {a}-{b} crosses bond {c}-{d}")
    faults.extend(_straight_through(mol, where))
    return tuple(faults)


#: Two bonds this near to 180 degrees apart draw as one line through the atom
#: between them, and an atom a reader cannot see is an atom that is not there.
STRAIGHT_DEGREES = 175.0


def _straight_through(mol: Molecule,
                      where: Sequence[tuple[float, float]]) -> list[str]:
    """Atoms whose two bonds are so nearly collinear that the atom disappears.

    A skeletal formula spells a carbon as a corner, so a chain carbon drawn
    straight is a carbon the reader does not count -- diclofenac came out
    looking like a benzoic acid rather than an arylacetic acid, which is a
    different compound and a different class. Genuinely linear geometry is
    exempt: a triple bond and the two bonds either side of it are 180 degrees
    apart in the molecule, and drawing erlotinib's alkyne with a kink would be
    the same offence in the other direction.
    """
    near = mol.adjacency()
    out: list[str] = []
    for atom in range(len(mol)):
        others = list(near[atom])
        if len(others) != 2:
            continue
        bonds = [mol.bond_between(atom, other) for other in others]
        if any(bond is not None and bond.order >= 3 for bond in bonds):
            continue
        first = _unit(where[others[0]][0] - where[atom][0],
                      where[others[0]][1] - where[atom][1])
        second = _unit(where[others[1]][0] - where[atom][0],
                       where[others[1]][1] - where[atom][1])
        dot = max(-1.0, min(1.0, first[0] * second[0] + first[1] * second[1]))
        angle = math.degrees(math.acos(dot))
        if angle > STRAIGHT_DEGREES:
            out.append(f"atom {atom} sits on a straight line between "
                       f"{others[0]} and {others[1]} ({angle:.1f} degrees)")
    return out


# ===========================================================================
# two embeddings from one eigensolver
# ===========================================================================
#
# The last two panels are both a set of points in three dimensions, found the
# same way: write down the distances something ought to have, turn them into
# an inner-product matrix, and take its three leading eigenvectors. For the
# chemical space the distances are 1 - Tanimoto between compounds. For a
# conformer they are the bond lengths and bond angles of one molecule. Nothing
# below knows which of the two it is being asked for, which is the reason to
# write it once: `top_eigen` and `mds` are the whole of classical
# multidimensional scaling, in about forty lines, with no numpy and no RNG.


def _start_vector(size: int, salt: int) -> list[float]:
    """A fixed, arbitrary, non-uniform starting vector for `top_eigen`.

    Power iteration needs a start that is not orthogonal to the eigenvector it
    is hunting, and a double-centred Gram matrix annihilates the all-ones
    vector -- so the one obvious deterministic choice is exactly the wrong
    one. `fnv1a` gives an arbitrary vector that is nonetheless the same
    arbitrary vector on every machine and in every process, which is what this
    figure needs and what `random.random()` would not give.
    """
    return [(fnv1a((salt, i)) % 2_000_003) / 1_000_001.5 - 1.0
            for i in range(size)]


def top_eigen(matrix: Sequence[Sequence[float]], count: int, *,
              iterations: int = 5000, tolerance: float = 1e-13,
              stop_below: float | None = None
              ) -> tuple[tuple[float, tuple[float, ...]], ...]:
    """The `count` leading eigenpairs of a symmetric matrix, largest first.

    Power iteration with deflation: multiply, normalise, repeat until the
    Rayleigh quotient stops moving, then subtract `value * v v'` from the
    matrix and go again. Fine for a symmetric matrix whose top few eigenvalues
    are what is wanted -- 38 compounds or 20 atoms -- and worth writing out
    because the reader can then see that "the first three principal
    coordinates" means exactly this and nothing more.

    Each eigenvector's sign is fixed by making its largest-magnitude entry
    positive (ties to the lower index), because a sign is not determined by
    the eigenproblem and an unfixed one would flip the picture between runs.

    `stop_below` returns early once an eigenvalue drops to it, which is how
    `_positive_mass` asks for "all the positive ones" without paying for the
    other thirty.
    """
    size = len(matrix)
    work = [list(row) for row in matrix]
    found: list[tuple[float, tuple[float, ...]]] = []
    for step in range(count):
        vector = _start_vector(size, step)
        value = 0.0
        for _ in range(iterations):
            product = [sum(work[i][j] * vector[j] for j in range(size))
                       for i in range(size)]
            length = math.sqrt(sum(x * x for x in product))
            if length < 1e-15:
                value = 0.0
                break
            vector = [x / length for x in product]
            after = sum(vector[i] * sum(work[i][j] * vector[j]
                                        for j in range(size))
                        for i in range(size))
            if abs(after - value) < tolerance * max(1.0, abs(after)):
                value = after
                break
            value = after
        biggest = max(range(size), key=lambda i: (abs(vector[i]), -i))
        if vector[biggest] < 0.0:
            vector = [-x for x in vector]
        if stop_below is not None and value <= stop_below:
            break
        found.append((value, tuple(vector)))
        for i in range(size):
            for j in range(size):
                work[i][j] -= value * vector[i] * vector[j]
    return tuple(found)


def gram(dist: Sequence[Sequence[float]]) -> list[list[float]]:
    """Torgerson's double centring: `-0.5 * (d^2 - rowmean - colmean + mean)`.

    The matrix whose eigenvectors are the principal coordinates. Its trace is
    the total squared spread of whatever cloud of points has these distances
    -- if one exists at all, which for a Tanimoto distance it does not exactly,
    hence the negative eigenvalues `mds` reports rather than hides.
    """
    size = len(dist)
    square = [[dist[i][j] ** 2 for j in range(size)] for i in range(size)]
    rows = [sum(row) / size for row in square]
    grand = sum(rows) / size
    return [[-0.5 * (square[i][j] - rows[i] - rows[j] + grand)
             for j in range(size)] for i in range(size)]


def mds(dist: Sequence[Sequence[float]], dims: int = 3
        ) -> tuple[tuple[tuple[float, ...], ...], float]:
    """Classical multidimensional scaling: coordinates, and how much they keep.

    Returns one point per row of `dist` and the fraction of the positive
    eigenvalue mass the kept axes carry -- the honest version of "the first
    three components explain X of the variance", and the number the caption
    prints so that a reader knows how much of the picture is a projection.
    """
    matrix = gram(dist)
    pairs = top_eigen(matrix, dims)
    coords = tuple(tuple(math.sqrt(max(value, 0.0)) * vector[i]
                         for value, vector in pairs)
                   for i in range(len(dist)))
    kept = sum(max(value, 0.0) for value, _ in pairs)
    total = _positive_mass(matrix)
    return coords, (kept / total if total > 0.0 else 0.0)


def _positive_mass(matrix: Sequence[Sequence[float]]) -> float:
    """The sum of the positive eigenvalues of a Gram matrix.

    `mds`'s denominator. The trace is the sum of *all* of them, positive and
    negative, and a Tanimoto distance is not Euclidean -- the cloud of points
    with exactly these distances does not exist -- so the trace would flatter
    the answer. Only the positive part is a squared spread of anything.
    """
    return sum(value for value, _ in
               top_eigen(matrix, len(matrix), stop_below=1e-12))


@lru_cache(maxsize=None)
def chemical_space() -> tuple[tuple[tuple[float, ...], ...], float]:
    """The compounds as points in three dimensions, from Tanimoto alone.

    Classical MDS of `distances()`, which is `1 - Tanimoto`. This is the only
    place in the figure where the whole similarity matrix is asked to be a
    *shape* rather than a table, and the fraction returned beside the points
    says how much of that shape three axes could carry. It is not large --
    a 2048-bit space does not flatten kindly -- and the caption prints it.
    """
    return mds(distances(), 3)


# ===========================================================================
# the shape of one molecule
# ===========================================================================
#
# A structural formula is a graph drawn flat, and there are things it cannot
# say. Diazepam's seven-membered ring is not planar and its pendant phenyl is
# not in the plane of the rest -- both are facts about the compound that the
# 2-D drawing has to leave out, and both are what a reader who has only ever
# seen the flat formula is missing. So the figure embeds one compound properly.
#
# The method is distance geometry, the classical kind: write down every
# interatomic distance the bonding *implies* -- bond lengths from a table,
# 1-3 distances from bond angles, whole planar rings from the same planar
# layout the flat panel draws -- embed those distances with `mds` above, and
# then relax what the embedding got wrong. It is not a force field and it is
# not a minimised structure: there is no electrostatics, no torsion term and
# no experiment in it, and `conformer_error` reports exactly how well the
# geometry that comes out satisfies the geometry that went in. What it gives
# is a conformer with textbook bond lengths and angles and no atom sitting on
# top of another, which is what the panel claims and all it claims.

#: Bond lengths in angstroms, keyed by the two elements in alphabetical order
#: and a code: 0 for aromatic, otherwise the bond order. Ordinary tabulated
#: means -- an aromatic C-C is benzene's 1.39, an sp3 C-C is ethane's 1.53.
#: `tests/test_chem_figure.py` checks that every bond type that occurs in any
#: of the thirty-eight compounds is in here, so a new compound with an
#: unlisted bond fails a test rather than quietly getting the fallback.
LENGTHS: dict[tuple[str, str, int], float] = {
    ("C", "C", 0): 1.39, ("C", "C", 1): 1.53, ("C", "C", 2): 1.34,
    ("C", "C", 3): 1.20,
    ("C", "N", 0): 1.34, ("C", "N", 1): 1.47, ("C", "N", 2): 1.28,
    ("C", "N", 3): 1.16,
    ("C", "O", 0): 1.36, ("C", "O", 1): 1.43, ("C", "O", 2): 1.22,
    ("C", "S", 0): 1.71, ("C", "S", 1): 1.81, ("C", "S", 2): 1.67,
    ("Br", "C", 1): 1.94, ("C", "Cl", 1): 1.74, ("C", "F", 1): 1.35,
    ("N", "N", 0): 1.35, ("N", "N", 1): 1.45, ("N", "N", 2): 1.25,
    ("N", "O", 0): 1.36, ("N", "O", 1): 1.40, ("N", "O", 2): 1.22,
    ("N", "S", 0): 1.63, ("N", "S", 1): 1.63,
    ("O", "S", 1): 1.57, ("O", "S", 2): 1.44,
    ("O", "P", 1): 1.60, ("O", "P", 2): 1.48,
    ("S", "S", 1): 2.05,
}

#: What an unlisted bond gets, so `conformer` never raises on a compound the
#: table has not met. A test keeps the thirty-eight off this path.
DEFAULT_LENGTH = 1.50

#: Bond angles in degrees by hybridisation, read off the atom's own bonds:
#: a triple bond is linear, anything aromatic or with a double bond is
#: trigonal, and everything else is tetrahedral.
LINEAR, TRIGONAL, TETRAHEDRAL = 180.0, 120.0, 109.5

#: Below this ring size the geometry of the ring wins over hybridisation: no
#: arrangement of a four-membered ring has 109.5 degree angles, and a
#: beta-lactam is a four-membered ring. At six and up the hybridisation angles
#: are satisfiable and the ring's own pucker is what the embedding is for.
SMALL_RING = 5

#: How close two atoms with no bonding relationship may come, in angstroms:
#: roughly a carbon-carbon van der Waals contact for the far pairs, and less
#: for a 1-4 pair, which is held at a torsion angle rather than pushed apart.
CONTACT, TORSION_CONTACT = 3.05, 2.60

#: Steps of stress relaxation after the embedding, and how much of each
#: correction to apply. Both stated rather than tuned to a picture:
#: `conformer_error` says what they achieved.
RELAX_STEPS, RELAX_RATE = 5000, 1.0


def bond_length(mol: Molecule, bond: Bond) -> float:
    """The tabulated length of one bond, in angstroms."""
    first, second = sorted((mol.atoms[bond.a].element,
                            mol.atoms[bond.b].element))
    code = 0 if bond.aromatic else bond.order
    return LENGTHS.get((first, second, code), DEFAULT_LENGTH)


def bond_angle(mol: Molecule, centre: int, a: int, b: int) -> float:
    """The angle a-centre-b ought to be, in degrees.

    A ring of five atoms or fewer overrides the hybridisation, because a
    regular pentagon's 108 degrees is what the ring can actually do and the
    atom's preference is not on offer.
    """
    for ring in mol.rings():
        if len(ring) <= SMALL_RING and {centre, a, b} <= set(ring):
            return 180.0 - 360.0 / len(ring)
    bonds = [mol.bond_between(centre, other) for other in mol.adjacency()[centre]]
    if any(bond is not None and bond.order == 3 for bond in bonds):
        return LINEAR
    if mol.atoms[centre].aromatic or any(bond is not None and bond.order == 2
                                         for bond in bonds):
        return TRIGONAL
    return TETRAHEDRAL


def _flat_systems(mol: Molecule) -> list[tuple[int, ...]]:
    """Ring systems every one of whose bonds is aromatic, hence planar.

    A fused pair of aromatic rings is one flat plate, not two, so the whole
    system is taken together -- which is what makes a naphthalene come out
    flat rather than hinged along its shared bond.
    """
    out = []
    for group in _ring_systems(mol):
        inside = {(min(a, b), max(a, b)) for ring in mol.rings()
                  if set(ring) <= set(group)
                  for a, b in zip(ring, ring[1:] + ring[:1])}
        if inside and all(bond.aromatic for bond in mol.bonds
                          if (min(bond.a, bond.b), max(bond.a, bond.b)) in inside):
            out.append(group)
    return out


def distance_targets(mol: Molecule) -> dict[tuple[int, int], float]:
    """Every interatomic distance the bonding fixes, in angstroms.

    Three sources, most specific last so that it wins: a planar aromatic
    system takes all its distances from the flat depiction the other panel
    draws, scaled to the mean length of its own bonds; a 1-3 pair takes the
    law of cosines on its two bond lengths and the angle between them; a
    bonded pair takes the table. Everything else is left to `conformer`'s
    contact floor, which is another way of saying that a torsion angle is not
    something the bonding fixes -- and that is why one of these is a conformer
    and not the conformation.
    """
    near = mol.adjacency()
    targets: dict[tuple[int, int], float] = {}
    where = depiction(mol)
    for group in _flat_systems(mol):
        inside = set(group)
        lengths = [bond_length(mol, bond) for bond in mol.bonds
                   if bond.a in inside and bond.b in inside]
        scale = sum(lengths) / len(lengths)
        for i in group:
            for j in group:
                if i < j:
                    targets[(i, j)] = math.dist(where[i], where[j]) * scale
    for centre in range(len(mol)):
        others = near[centre]
        for x in range(len(others)):
            for y in range(x + 1, len(others)):
                a, b = others[x], others[y]
                first = bond_length(mol, mol.bond_between(centre, a))
                second = bond_length(mol, mol.bond_between(centre, b))
                angle = math.radians(bond_angle(mol, centre, a, b))
                targets[(min(a, b), max(a, b))] = math.sqrt(
                    first * first + second * second
                    - 2.0 * first * second * math.cos(angle))
    for bond in mol.bonds:
        targets[(min(bond.a, bond.b), max(bond.a, bond.b))] = bond_length(mol, bond)
    return targets


def _bond_steps(mol: Molecule) -> list[list[int]]:
    """How many bonds apart every pair of atoms is."""
    size = len(mol)
    near = mol.adjacency()
    out = [[size + 1] * size for _ in range(size)]
    for start in range(size):
        out[start][start] = 0
        frontier = [start]
        while frontier:
            nxt = []
            for atom in frontier:
                for other in near[atom]:
                    if out[start][other] > out[start][atom] + 1:
                        out[start][other] = out[start][atom] + 1
                        nxt.append(other)
            frontier = nxt
    return out


def _floors(mol: Molecule, targets: dict[tuple[int, int], float]
            ) -> dict[tuple[int, int], float]:
    """The closest approach allowed to pairs no target speaks for."""
    steps = _bond_steps(mol)
    out = {}
    for i in range(len(mol)):
        for j in range(i + 1, len(mol)):
            if (i, j) in targets:
                continue
            out[(i, j)] = TORSION_CONTACT if steps[i][j] == 3 else CONTACT
    return out


@lru_cache(maxsize=None)
def conformer(mol: Molecule) -> tuple[tuple[float, float, float], ...]:
    """One molecule in three dimensions, in angstroms, on its principal axes.

    Distance geometry: `distance_targets` says what the distances should be,
    the pairs it leaves out are filled in with the shortest path through the
    ones it does not, `mds` turns that matrix into points, and then the points
    are relaxed against the targets and the contact floors -- each constraint
    pulling its two atoms along the line between them, all the pulls on an
    atom averaged, `RELAX_RATE` of the result applied, `RELAX_STEPS` times.

    Then the cloud is turned onto its own principal axes, so that the longest
    dimension of the molecule runs across the page and the view the panel asks
    for is a property of the molecule rather than of the order its atoms were
    written in.
    """
    size = len(mol)
    targets = distance_targets(mol)
    floors = _floors(mol, targets)
    dist = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            if i != j:
                dist[i][j] = float(size) * 2.0
    for (i, j), value in targets.items():
        dist[i][j] = dist[j][i] = value
    for k in range(size):                      # Floyd-Warshall: an unfixed
        for i in range(size):                  # pair starts at the shortest
            for j in range(size):              # path through the fixed ones,
                through = dist[i][k] + dist[k][j]   # which is an upper bound
                if through < dist[i][j]:            # on how far apart it is.
                    dist[i][j] = through
    points = [list(p) for p in mds(dist, 3)[0]]
    for _ in range(RELAX_STEPS):
        shift = [[0.0, 0.0, 0.0] for _ in range(size)]
        count = [0] * size
        for pairs, floor in ((targets, False), (floors, True)):
            for (i, j), want in pairs.items():
                delta = [points[j][k] - points[i][k] for k in range(3)]
                span = math.sqrt(sum(d * d for d in delta)) or 1e-9
                if floor and span >= want:
                    continue
                pull = (span - want) / span * 0.5
                for k in range(3):
                    shift[i][k] += delta[k] * pull
                    shift[j][k] -= delta[k] * pull
                count[i] += 1
                count[j] += 1
        for i in range(size):
            if count[i]:
                for k in range(3):
                    points[i][k] += RELAX_RATE * shift[i][k] / count[i]
    return _principal_frame(points)


def _principal_frame(points: Sequence[Sequence[float]]
                     ) -> tuple[tuple[float, float, float], ...]:
    """The cloud centred, and turned so its widest spread is the x axis.

    The same eigensolver again, on the 3x3 covariance. The third axis is the
    cross product of the first two rather than the third eigenvector, so the
    frame is right-handed and the molecule is never mirrored -- which for a
    compound with a stereocentre would be the difference between the drug and
    the other enantiomer.
    """
    size = len(points)
    middle = [sum(p[k] for p in points) / size for k in range(3)]
    centred = [[p[k] - middle[k] for k in range(3)] for p in points]
    covariance = [[sum(p[a] * p[b] for p in centred) / size
                   for b in range(3)] for a in range(3)]
    axes = [list(vector) for _, vector in top_eigen(covariance, 2)]
    axes.append([axes[0][1] * axes[1][2] - axes[0][2] * axes[1][1],
                 axes[0][2] * axes[1][0] - axes[0][0] * axes[1][2],
                 axes[0][0] * axes[1][1] - axes[0][1] * axes[1][0]])
    return tuple(tuple(sum(p[k] * axis[k] for k in range(3)) for axis in axes)
                 for p in centred)


def conformer_error(mol: Molecule) -> tuple[float, float, float]:
    """What the embedding achieved: worst bond, worst angle, closest contact.

    The bond error is a percentage of the tabulated length, the angle error is
    in degrees against `bond_angle`, and the contact is the nearest approach
    in angstroms of two atoms with no target between them. Measured from the
    coordinates the panel draws, every build, so the caption cannot quote a
    geometry the picture does not have.
    """
    points = conformer(mol)
    worst_bond = 0.0
    for bond in mol.bonds:
        want = bond_length(mol, bond)
        got = math.dist(points[bond.a], points[bond.b])
        worst_bond = max(worst_bond, abs(got - want) / want * 100.0)
    worst_angle = 0.0
    near = mol.adjacency()
    for centre in range(len(mol)):
        others = near[centre]
        for x in range(len(others)):
            for y in range(x + 1, len(others)):
                a, b = others[x], others[y]
                first = [points[a][k] - points[centre][k] for k in range(3)]
                second = [points[b][k] - points[centre][k] for k in range(3)]
                dot = sum(first[k] * second[k] for k in range(3))
                size = (math.dist(points[a], points[centre])
                        * math.dist(points[b], points[centre]))
                got = math.degrees(math.acos(max(-1.0, min(1.0, dot / size))))
                worst_angle = max(worst_angle,
                                  abs(got - bond_angle(mol, centre, a, b)))
    targets = distance_targets(mol)
    closest = min((math.dist(points[i], points[j])
                   for i in range(len(mol)) for j in range(i + 1, len(mol))
                   if (i, j) not in targets), default=0.0)
    return worst_bond, worst_angle, closest


def _best_plane(points: Sequence[Sequence[float]]) -> tuple[float, ...]:
    """The unit normal of the plane that fits these points best.

    The smallest eigenvector of their covariance, which is the direction along
    which they vary least -- the same 3x3 eigenproblem `_principal_frame`
    solves, asked for its other end.
    """
    size = len(points)
    middle = [sum(p[k] for p in points) / size for k in range(3)]
    centred = [[p[k] - middle[k] for k in range(3)] for p in points]
    covariance = [[sum(p[a] * p[b] for p in centred) / size
                   for b in range(3)] for a in range(3)]
    return top_eigen(covariance, 3)[2][1]


def ring_pucker(mol: Molecule, ring: Sequence[int]) -> float:
    """How far, in angstroms rms, a ring departs from its own best plane.

    Small for a benzene, whose planarity went in as a constraint, and large
    for a diazepine, whose pucker is what is left over once the bond angles
    round it are satisfied -- which is the whole point of drawing one of them
    in three dimensions.
    """
    points = [conformer(mol)[atom] for atom in ring]
    normal = _best_plane(points)
    middle = [sum(p[k] for p in points) / len(points) for k in range(3)]
    return math.sqrt(sum(sum((p[k] - middle[k]) * normal[k]
                             for k in range(3)) ** 2
                         for p in points) / len(points))


def aromatic_ring_angle(mol: Molecule) -> float:
    """The angle in degrees between the planes of two aromatic rings.

    Defined only for a molecule with exactly two of them, which is what the
    figure asks it about: the twist between a benzodiazepine's fused benzo
    ring and its pendant phenyl is the second thing the flat formula cannot
    say, and quoting it means measuring it off the coordinates that were
    drawn rather than off a memory of a crystal structure.
    """
    rings = [ring for ring in mol.rings()
             if all(mol.atoms[atom].aromatic for atom in ring)]
    if len(rings) != 2:
        raise ValueError(f"{mol.name} has {len(rings)} aromatic rings, not 2")
    first, second = (_best_plane([conformer(mol)[atom] for atom in ring])
                     for ring in rings)
    dot = abs(sum(a * b for a, b in zip(first, second)))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))
