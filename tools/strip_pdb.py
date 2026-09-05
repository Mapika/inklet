"""Cut a PDB entry down to what a figure draws, and say so in the file.

`figures/data/1m17-kinase.pdb` is 45 kB of a 247 kB entry. Shipping the whole
thing would be shipping mostly waters, occupancies and anisotropic temperature
factors, none of which reach the page; shipping a pickled mesh instead would
put a black box where the provenance should be. What comes out of here is still
a PDB file -- readable by any viewer, diffable against the original -- with a
REMARK 999 block saying exactly which records survived and why.

    .venv/bin/python tools/strip_pdb.py 1M17.pdb figures/data/1m17-kinase.pdb

Kept: the title records, the resolution, the secondary-structure assignments,
the backbone (N, CA, C, O) of the modelled chain, every atom of the residues
lining the ligand pocket, and the ligand itself. Dropped: waters, alternate
conformations past the first, hydrogens, and every other chain.
"""

from __future__ import annotations

import math
import sys

#: Only the first chain. A kinase domain is one chain and the figure draws one.
CHAIN = "A"
#: What the cartoon needs from a residue: the trace, and the carbonyl that says
#: which way the peptide plane faces.
BACKBONE = ("N", "CA", "C", "O")
#: A residue with any atom this close to the ligand lines the pocket, and keeps
#: its side chain. 4.2 A is a contact distance, not a shell -- it picks the
#: residues a medicinal chemist would name, and nothing else.
CONTACT = 4.2

HEADERS = ("HEADER", "TITLE ", "COMPND", "SOURCE", "EXPDTA")


def _xyz(line: str) -> tuple[float, float, float]:
    return float(line[30:38]), float(line[38:46]), float(line[46:54])


def _kept_atom(line: str) -> bool:
    """First conformation only, and no hydrogens.

    A structure with two conformations for a side chain has both in the file
    with occupancies that sum to one. A drawing can show one. Taking the first
    is what every viewer's default does.
    """
    return line[16] in " A" and line[76:78].strip() not in ("H", "D")


def strip(text: str) -> str:
    lines = text.splitlines()
    ligand = [line for line in lines
              if line.startswith("HETATM") and line[17:20] not in ("HOH", "DOD")
              and line[21] == CHAIN and _kept_atom(line)]
    sites = [_xyz(line) for line in ligand]

    protein = [line for line in lines
               if line.startswith("ATOM") and line[21] == CHAIN
               and _kept_atom(line)]
    pocket = set()
    for line in protein:
        point = _xyz(line)
        if any(math.dist(point, site) < CONTACT for site in sites):
            pocket.add(line[22:27])

    atoms = [line for line in protein
             if line[12:16].strip() in BACKBONE or line[22:27] in pocket]
    # The chain ID is in a different column in the two records -- 20 for a
    # helix, 22 for a strand, both 1-indexed. Testing one column for both is
    # how the first cut of this silently kept every helix and no strand.
    structure = [line for line in lines
                 if (line[:6] == "HELIX " and line[19] == CHAIN)
                 or (line[:6] == "SHEET " and line[21] == CHAIN)]
    residues = {line[22:27] for line in atoms}

    out = [line for line in lines if line[:6] in HEADERS]
    out += [line for line in lines if line.startswith("REMARK   2 RESOLUTION")]
    out += _provenance(len(residues), len(pocket), len(structure), len(ligand))
    out += structure + atoms + ligand
    out.append("END")
    return "\n".join(out) + "\n"


def _provenance(residues: int, pocket: int, structure: int,
                ligand: int) -> list[str]:
    say = [
        "STRIPPED FOR FIGURE USE BY tools/strip_pdb.py. THIS IS A SUBSET OF",
        "THE DEPOSITED ENTRY, NOT A RE-REFINEMENT: EVERY COORDINATE BELOW IS",
        f"VERBATIM FROM THE ORIGINAL. KEPT: CHAIN {CHAIN} BACKBONE (N CA C O)",
        f"FOR {residues} RESIDUES, ALL ATOMS OF THE {pocket} RESIDUES WITHIN",
        f"{CONTACT} A OF THE LIGAND, THE LIGAND ITSELF ({ligand} ATOMS), AND",
        f"{structure} HELIX/SHEET RECORDS. DROPPED: WATERS, HYDROGENS,",
        "ALTERNATE CONFORMATIONS PAST THE FIRST, OTHER CHAINS, AND ALL",
        "METADATA NOT NAMED ABOVE.",
    ]
    return [f"REMARK 999 {line}".ljust(80) for line in say]


if __name__ == "__main__":
    source, target = sys.argv[1], sys.argv[2]
    with open(source) as handle:
        result = strip(handle.read())
    with open(target, "w") as handle:
        handle.write(result)
    print(f"{target}: {len(result.splitlines())} lines, {len(result)} bytes")
