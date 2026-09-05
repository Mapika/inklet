"""The figure's numbers, in one place.

Every panel of a real figure is a different view of one experiment, and the
views have to agree: the Faradaic efficiency in (e) is the flux in (i) is the
plateau in (j). Generating each panel's data where it is drawn guarantees they
disagree, so all of it is here, deterministic, derived from one story.

The story: a gas-diffusion electrode of Cu(2+delta)O nanocubes reducing CO2 to
C2H4 in 1 M KOH. As the potential goes more negative the oxide reduces to
metallic Cu (panel g), C2H4 takes over from CO (panel e), and the parasitic
hydrogen evolution eventually wins (all of them). Nothing here is measured;
it is simulated to be the shape a measurement of this system would have.
"""

from __future__ import annotations

import math

import numpy as np

# -- the potential sweep every electrochemical panel shares -----------------

#: Applied potential, V vs RHE. Negative, and reported that way throughout.
POTENTIALS = [-0.60, -0.72, -0.84, -0.96, -1.08, -1.20, -1.32]

#: Faradaic efficiency, %, by species and potential. Built from a plausible
#: mechanism rather than typed: CO is the intermediate that peaks early, C2H4
#: builds from it, and H2 takes whatever is left as the potential drives past
#: the CO2 mass-transport limit.
def _efficiencies() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {k: [] for k in ("CO", "C2H4", "CH4", "HCOO", "H2")}
    for v in POTENTIALS:
        x = -v
        co = 46.0 * math.exp(-((x - 0.66) ** 2) / 0.055)
        c2h4 = 62.0 * math.exp(-((x - 1.02) ** 2) / 0.085)
        ch4 = 11.0 / (1.0 + math.exp(-(x - 1.16) / 0.06))
        hcoo = 9.5 * math.exp(-((x - 0.80) ** 2) / 0.30)
        h2 = 5.0 + 78.0 / (1.0 + math.exp(-(x - 1.20) / 0.10))
        total = co + c2h4 + ch4 + hcoo + h2
        for key, value in (("CO", co), ("C2H4", c2h4), ("CH4", ch4),
                           ("HCOO", hcoo), ("H2", h2)):
            out[key].append(round(100.0 * value / total, 1))
    return out


FARADAIC = _efficiencies()

#: Equilibrium potential for CO2 reduction to C2H4, V vs RHE, and the Tafel
#: parameters of the kinetic branch. A gas-diffusion electrode is kinetics in
#: series with CO2 transport through the diffusion layer, so the total current
#: is the harmonic sum -- which is what bends the Tafel plot over in (f) and
#: what the 320 mA/cm^2 limit in (j) is.
E_EQ = 0.08
TAFEL_B = 0.120                                   # V per decade
J0 = 4.4e-6                                       # mA/cm^2
J_LIMIT = 320.0


def _total_current(potential: float) -> float:
    kinetic = J0 * 10.0 ** ((abs(potential) - E_EQ) / TAFEL_B)
    return 1.0 / (1.0 / kinetic + 1.0 / J_LIMIT)


TOTAL_CURRENT = [round(_total_current(v), 3) for v in POTENTIALS]

#: Partial current density by species -- FE times the total, so the Tafel
#: panel and the bar panel cannot drift apart.
PARTIAL_CURRENT = {
    species: [float(f"{fe / 100.0 * j:.4g}")
              for fe, j in zip(values, TOTAL_CURRENT)]
    for species, values in FARADAIC.items()
}

#: Tafel slopes fitted to the low-overpotential end, mV per decade. Quoted in
#: the panel, and measured off PARTIAL_CURRENT rather than asserted.
def tafel_slope(species: str, points: int = 4) -> float:
    """Slope of eta against log10 of that species' partial current, mV/decade,
    fitted over the kinetically controlled end of the sweep."""
    # A product below the detection limit has a partial current of zero, and
    # zero has no logarithm. Those points are dropped rather than nudged: a
    # slope fitted to a fabricated 0.001 mA/cm^2 would be a fabricated slope.
    pairs = [(abs(v) - E_EQ, math.log10(j))
             for v, j in zip(POTENTIALS[:points], PARTIAL_CURRENT[species][:points])
             if j > 0.0]
    if len(pairs) < 3:
        raise ValueError(f"{species} has fewer than three points above the "
                         f"detection limit in the first {points} potentials")
    eta = [p[0] for p in pairs]
    logj = [p[1] for p in pairs]
    n = len(eta)
    mean_x, mean_y = sum(logj) / n, sum(eta) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(logj, eta))
    var = sum((a - mean_x) ** 2 for a in logj)
    return 1000.0 * cov / var


# -- operando XRD: the oxide reducing under load ---------------------------

#: Two-theta axis, degrees, and the times the patterns were taken at, minutes.
TWO_THETA = [round(28.0 + 0.25 * i, 2) for i in range(64)]
XRD_TIMES = [0, 4, 8, 12, 16, 20, 25, 30, 40, 50, 60, 75, 90, 110, 130, 150]

#: Peaks: (position, initial weight, final weight, width). Cu2O (111) at 36.4
#: and (200) at 42.3 fade; Cu (111) at 43.3 and (200) at 50.4 grow.
_PEAKS = [(36.42, 1.00, 0.06, 0.30),
          (42.30, 0.55, 0.04, 0.32),
          (43.30, 0.05, 0.95, 0.26),
          (50.43, 0.02, 0.42, 0.30),
          (38.70, 0.18, 0.05, 0.45)]


def _xrd() -> list[list[float]]:
    noise = np.random.default_rng(20250823)
    rows = []
    for minute in XRD_TIMES:
        # Reduction follows a nucleation-and-growth sigmoid in time, which is
        # what makes the map read as a transition rather than a fade.
        progress = 1.0 / (1.0 + math.exp(-(minute - 34.0) / 9.0))
        row = []
        for angle in TWO_THETA:
            value = 0.04
            for centre, start, end, width in _PEAKS:
                weight = start + (end - start) * progress
                value += weight * math.exp(-((angle - centre) ** 2) / (2 * width ** 2))
            row.append(round(value + float(noise.normal(0.0, 0.006)), 4))
        rows.append(row)
    return rows


XRD = _xrd()

#: The integrated Cu2O(111) and Cu(111) areas, per pattern -- the traces drawn
#: over the map, measured off the very rows below them.
def _integrated(low: float, high: float) -> list[float]:
    columns = [i for i, a in enumerate(TWO_THETA) if low <= a <= high]
    return [round(sum(row[i] for i in columns) / len(columns), 4) for row in XRD]


XRD_OXIDE = _integrated(35.6, 37.3)
XRD_METAL = _integrated(42.6, 44.1)


# -- operando FTIR: what sits on the surface -------------------------------

WAVENUMBERS = [round(1200.0 + 5.0 * i, 1) for i in range(160)]
FTIR_POTENTIALS = [-0.60, -0.84, -1.08, -1.32]

#: (centre, width, weight at -0.6 V, weight at -1.32 V, assignment)
FTIR_BANDS = [
    (1382.0, 14.0, 0.62, 0.10, "ν_{s}(OCO), *HCOO"),
    (1543.0, 18.0, 0.20, 0.74, "ν_{as}(OCO), *CO_{2}^{−}"),
    (1650.0, 26.0, 0.30, 0.34, "δ(H₂O)"),
    (1905.0, 22.0, 0.08, 0.66, "ν(CO), atop"),
    (1785.0, 30.0, 0.05, 0.28, "ν(CO), bridge"),
]


def _ftir() -> list[list[float]]:
    noise = np.random.default_rng(4711)
    out = []
    span = FTIR_POTENTIALS[-1] - FTIR_POTENTIALS[0]
    for potential in FTIR_POTENTIALS:
        t = (potential - FTIR_POTENTIALS[0]) / span
        row = []
        for k in WAVENUMBERS:
            value = 0.0
            for centre, width, start, end, _ in FTIR_BANDS:
                weight = start + (end - start) * t
                value += weight * math.exp(-((k - centre) ** 2) / (2 * width ** 2))
            row.append(round(value + float(noise.normal(0.0, 0.004)), 4))
        out.append(row)
    return out


FTIR = _ftir()


# -- the 500-hour pilot run ------------------------------------------------

#: Hours, current density (mA/cm^2), FE(C2H4) (%), and cell voltage (V).
#: Two electrolyte flushes arrest a slow salt-precipitation decline; the
#: shaded windows in the panel are these.
FLUSHES = [(168.0, 172.0), (336.0, 340.0)]


def _stability() -> tuple[list[float], list[float], list[float], list[float]]:
    noise = np.random.default_rng(90210)
    hours, current, efficiency, voltage = [], [], [], []
    since_flush = 0.0
    for step in range(0, 501, 2):
        hour = float(step)
        for start, end in FLUSHES:
            if start <= hour < end:
                since_flush = 0.0
        if not any(start <= hour < end for start, end in FLUSHES):
            since_flush += 2.0
        fouling = 1.0 - 0.00042 * since_flush          # salt in the pores
        ageing = 1.0 - 0.00021 * hour                  # irreversible
        j = 208.0 * fouling * ageing + float(noise.normal(0.0, 1.6))
        fe = 61.0 * (0.55 + 0.45 * fouling) * ageing + float(noise.normal(0.0, 0.9))
        v = 3.42 + 0.00035 * hour + 0.0008 * since_flush + float(noise.normal(0.0, 0.012))
        hours.append(hour)
        current.append(round(j, 2))
        efficiency.append(round(fe, 2))
        voltage.append(round(v, 3))
    return hours, current, efficiency, voltage


HOURS, CURRENT_DENSITY, FE_TRACE, CELL_VOLTAGE = _stability()


# -- carbon flux, for the Sankey -------------------------------------------
#
# Basis: 100 carbon atoms entering as CO2 at the pilot's operating point,
# -1.08 V, which is the column of FARADAIC the flux is taken from.

_OPERATING = POTENTIALS.index(-1.08)


def carbon_flux() -> dict[str, float]:
    """Share of entering carbon leaving as each product, and unconverted.

    Single-pass conversion is 38%; the rest of the CO2 goes round the loop
    again, which is the recycle arm in the process diagram. Of what reacts,
    the split follows the Faradaic efficiencies with the electrons-per-carbon
    each product costs -- 12 for C2H4, 2 for CO -- which is why C2H4's share
    of *carbon* is smaller than its share of current.
    """
    per_carbon = {"C2H4": 6.0, "CO": 2.0, "CH4": 8.0, "HCOO": 2.0}
    charge = {k: FARADAIC[k][_OPERATING] for k in per_carbon}
    moles = {k: charge[k] / per_carbon[k] for k in per_carbon}
    total = sum(moles.values())
    converted = 38.0
    flux = {k: round(converted * v / total, 2) for k, v in moles.items()}
    flux["recycle"] = round(100.0 - converted, 2)
    # C2H4 and CH4 carry two and one carbon per molecule; the flux above is in
    # carbon atoms, which is what a carbon balance has to close on.
    return flux


CARBON = carbon_flux()

#: Cyclic voltammograms for the small-multiples panel: four catalyst loadings.
LOADINGS = [0.5, 1.0, 2.0, 4.0]


def _cvs() -> dict[float, tuple[list[float], list[float]]]:
    noise = np.random.default_rng(1312)
    out = {}
    for loading in LOADINGS:
        volts, currents = [], []
        scan = [(-0.05 - 0.005 * i) for i in range(260)]
        scan += list(reversed(scan))
        for index, v in enumerate(scan):
            forward = index < len(scan) // 2
            # A reduction wave that grows with loading, plus the capacitive
            # box that separates the two sweep directions.
            wave = -loading * 3.1 / (1.0 + math.exp(-(-v - 0.62) / 0.045))
            capacitance = (0.34 if forward else -0.34) * loading * 0.55
            out_v = wave + capacitance + float(noise.normal(0.0, 0.035))
            volts.append(round(v, 4))
            currents.append(round(out_v, 4))
        out[loading] = (volts, currents)
    return out


CVS = _cvs()
