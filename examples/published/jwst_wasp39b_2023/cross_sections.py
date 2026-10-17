"""Molecular cross-sections for the bottom panel of Figure 3, computed.

The authors did not release the curves behind the bottom panel of Fig. 3 (the
absorption cross-section of each gas in the best-fit model), so this script
derives them from the HITRAN line lists instead. It is run once, by hand, and
writes `data/fig3_cross_sections.csv`; `fig3.py` only reads that file.

What is computed: the cross-section averaged over each 0.025 um wavelength bin
(about the data's resolution) from 3.0 to 5.55 um, at T = 1,170 K (WASP-39b's
equilibrium temperature, from the paper). Each line's HITRAN intensity is
scaled from 296 K to T, and the intensities that fall in a bin are summed and
divided by the bin's width in wavenumber. That is the bin mean of sigma
exactly (cm^2 per molecule), with no line profile: at the millibar pressures
the figure shows, lines are far narrower than a bin. Only line wings that cross a bin edge are ignored.

Differences from the paper's curves, which come from ScCHIMERA's own opacity
tables (ExoMol and HITEMP line lists at the model's temperatures): HITRAN is a
296 K database, so hot bands that only HITEMP or ExoMol contain are missing,
which lowers the cross-sections in the windows between bands, most for H2O and
CH4. The shapes and band positions are the same; the values are ours.

Needs `hitran-api` (pip install hitran-api) and a network connection on the
first run, which downloads about 20 MB of HITRAN lines to a cache directory
outside the repository (the system temp directory unless one is given):

    python cross_sections.py [directory for the HITRAN tables]

Line data: I. E. Gordon et al., "The HITRAN2020 molecular spectroscopic
database", J. Quant. Spectrosc. Radiat. Transf. 277, 107949 (2022).
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

import hapi

HERE = Path(__file__).resolve().parent
TABLES = Path(sys.argv[1] if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "inklet-hitran")
OUT = HERE / "data" / "fig3_cross_sections.csv"

T, T_REF = 1170.0, 296.0
C2 = 1.4387769          # second radiation constant, cm K
GASES = [("H2O", 1), ("CO2", 2), ("CO", 5), ("CH4", 6), ("H2S", 31)]   # HITRAN ids
EDGES_UM = np.round(np.arange(3.0, 5.55 + 1e-9, 0.025), 4)


def intensity_at(nu, sw, elower, molecule):
    """HITRAN line intensities, scaled from 296 K to T (main isotopologue)."""
    q = hapi.partitionSum(molecule, 1, [T_REF, T])
    boltzmann = np.exp(-C2 * elower / T) / np.exp(-C2 * elower / T_REF)
    stimulated = (1 - np.exp(-C2 * nu / T)) / (1 - np.exp(-C2 * nu / T_REF))
    return sw * q[0] / q[1] * boltzmann * stimulated


TABLES.mkdir(parents=True, exist_ok=True)
hapi.db_begin(str(TABLES))
low, high = 1e4 / EDGES_UM[-1] - 50, 1e4 / EDGES_UM[0] + 50      # cm^-1, with margin
columns = {"wavelength_um": (EDGES_UM[:-1] + EDGES_UM[1:]) / 2}
for name, molecule in GASES:
    if name not in hapi.tableList():
        hapi.fetch(name, molecule, 1, low, high)
    nu, sw, elower = (np.asarray(c, float) for c in hapi.getColumns(name, ["nu", "sw", "elower"]))
    strength = intensity_at(nu, sw, elower, molecule)
    wavelength = 1e4 / nu
    sums, _ = np.histogram(wavelength, bins=EDGES_UM, weights=strength)
    width = 1e4 / EDGES_UM[:-1] - 1e4 / EDGES_UM[1:]                # bin width, cm^-1
    sigma = sums / width                                            # cm^2 per molecule
    columns[f"log10_sigma_{name}"] = np.where(sigma > 0, np.log10(np.maximum(sigma, 1e-300)), np.nan)

header = ",".join(columns)
rows = np.column_stack(list(columns.values()))
np.savetxt(OUT, rows, delimiter=",", header=header, comments="", fmt="%.6g")
print(f"wrote {OUT} ({len(rows)} bins)")
