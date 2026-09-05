"""Just enough PDB to draw a protein.

A full parser handles alternate conformations, insertion codes, anisotropic
temperature factors, multiple models, and thirty record types no drawing has
ever needed. This reads five: the two secondary-structure assignments, the two
coordinate records, and the title. Everything it returns is a plain dataclass
of floats -- nothing here knows what a diagram is, and the cartoon geometry in
`cartoon.py` is written against these types rather than against a file format.

It is called `pdbfile` and not `pdb` because `pdb` is the standard library's
debugger. Under `figures/` on `sys.path` the local file wins, but only if
nothing has imported the real one first -- and pytest has, so a test that
imported anything here got the debugger and an `AttributeError` about HELIX.

**Where secondary structure comes from.** The HELIX and SHEET records, not from
computing hydrogen bonds. Depositors assign them with DSSP or by hand and the
assignment is part of the entry; recomputing it would be a second opinion the
figure has no way to adjudicate. Residues named by neither record are coil.

Columns are fixed-width and are *not* whitespace-separated: a four-character
atom name starts one column earlier than a three-character one, and residue
9999 leaves no space before the insertion code. Every field below is sliced by
the column numbers in the format specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from inklet.three.linalg import Vec3

#: Secondary structure, one letter each, as everyone from DSSP down spells it.
HELIX, STRAND, COIL = "H", "E", "C"

#: Consecutive residues further apart than this at the alpha carbon are not
#: bonded: the chain was disordered in the crystal and the entry skips it. 4.2 A
#: is comfortably above the 3.8 A a peptide bond fixes them at and below any
#: real gap. Without the test a cartoon draws a girder straight through the
#: middle of the fold.
BREAK = 4.2


@dataclass(frozen=True)
class Residue:
    number: int
    name: str                       # three-letter code, e.g. "MET"
    chain: str
    atoms: dict[str, Vec3]
    structure: str = COIL

    @property
    def ca(self) -> Vec3 | None:
        return self.atoms.get("CA")

    @property
    def label(self) -> str:
        """What a figure calls it: "Met769", the way a paper writes it."""
        return f"{self.name.capitalize()}{self.number}"

    def side_chain(self) -> list[tuple[str, Vec3]]:
        """Everything past the backbone, in file order.

        CB is included: it is formally backbone-adjacent but it is the first
        atom of the side chain's shape, and a side chain drawn from CG onward
        floats unattached.
        """
        return [(name, point) for name, point in self.atoms.items()
                if name not in ("N", "C", "O", "OXT")]


@dataclass(frozen=True)
class Ligand:
    name: str                       # the three-character HET code
    atoms: dict[str, Vec3]

    @property
    def centre(self) -> Vec3:
        return sum(self.atoms.values(), Vec3()) * (1.0 / len(self.atoms))


@dataclass(frozen=True)
class Structure:
    title: str
    entry: str
    residues: tuple[Residue, ...]
    ligands: tuple[Ligand, ...] = ()
    _index: dict[int, Residue] = field(default_factory=dict, repr=False)

    def __getitem__(self, number: int) -> Residue:
        try:
            return self._index[number]
        except KeyError:
            raise KeyError(
                f"no residue {number} in {self.entry}; the chain runs "
                f"{self.residues[0].number}-{self.residues[-1].number}"
            ) from None

    def get(self, number: int) -> Residue | None:
        return self._index.get(number)

    def segments(self) -> list[list[Residue]]:
        """The chain split where the crystal lost it.

        One list per continuous run of residues. A cartoon is drawn per segment
        -- a spline through the whole chain would sail across the gap, and the
        line it drew would be the one thing in the picture with no evidence
        behind it.
        """
        runs: list[list[Residue]] = []
        for residue in self.residues:
            if residue.ca is None:
                continue
            if not runs or (residue.number != runs[-1][-1].number + 1
                            or (residue.ca - runs[-1][-1].ca).length > BREAK):
                runs.append([])
            runs[-1].append(residue)
        return runs

    def near(self, point: Vec3, within: float) -> list[Residue]:
        """Residues with any atom inside `within` angstroms of a point."""
        return [residue for residue in self.residues
                if any((atom - point).length <= within
                       for atom in residue.atoms.values())]


def _vec(line: str) -> Vec3:
    return Vec3(float(line[30:38]), float(line[38:46]), float(line[46:54]))


def load(path: str | Path, chain: str = "A") -> Structure:
    """Read one chain of a PDB file.

    Later duplicates of an atom name are ignored rather than overwriting, which
    is how the first alternate conformation wins without this having to know
    what an alternate conformation is.
    """
    text = Path(path).read_text()
    title: list[str] = []
    entry = ""
    ranges: list[tuple[int, int, str]] = []
    atoms: dict[int, tuple[str, dict[str, Vec3]]] = {}
    hetero: dict[str, dict[str, Vec3]] = {}

    for line in text.splitlines():
        record = line[:6]
        if record == "HEADER":
            entry = line[62:66].strip()
        elif record == "TITLE ":
            title.append(line[10:80].strip())
        elif record == "HELIX " and line[19] == chain:
            ranges.append((int(line[21:25]), int(line[33:37]), HELIX))
        elif record == "SHEET " and line[21] == chain:
            ranges.append((int(line[22:26]), int(line[33:37]), STRAND))
        elif record == "ATOM  " and line[21] == chain:
            number = int(line[22:26])
            name, place = atoms.setdefault(number, (line[17:20].strip(), {}))
            place.setdefault(line[12:16].strip(), _vec(line))
        elif record == "HETATM" and line[17:20] not in ("HOH", "DOD"):
            hetero.setdefault(line[17:20].strip(), {}).setdefault(
                line[12:16].strip(), _vec(line))

    assigned = {}
    for start, end, kind in ranges:
        for number in range(start, end + 1):
            assigned[number] = kind

    residues = tuple(
        Residue(number, name, chain, dict(place), assigned.get(number, COIL))
        for number, (name, place) in sorted(atoms.items())
    )
    if not residues:
        raise ValueError(
            f"{Path(path).name} has no ATOM records for chain {chain!r}")
    return Structure(
        title=" ".join(title).replace("- ", "-"),
        entry=entry,
        residues=residues,
        ligands=tuple(Ligand(name, place) for name, place in sorted(hetero.items())),
        _index={residue.number: residue for residue in residues},
    )
