"""Simulated data for the drug-discovery figure.

**None of this is real.** There is no compound DGM-431 and no trial of it. The
numbers are drawn from textbook models -- a Hill curve for the assays, a
Weibull for the survival times -- with fixed seeds, so the figure is the same
every time it is built and anyone can see exactly where each number came from.
A figure demonstrating a drawing library should not be mistakable for a
clinical result, so the caption says so too.

Everything here returns plain lists of numbers. Nothing in this module knows
what a diagram is.
"""

from __future__ import annotations

import math
import random

# --- in vitro --------------------------------------------------------------

#: Concentration, potency, Hill slope and top of curve for each series member.
COMPOUNDS = (
    ("DGM-431",  3.2e-9,  1.15, 99.0),
    ("DGM-118",  4.7e-8,  1.05, 97.0),
    ("DGM-002",  1.9e-6,  0.90, 93.0),
)
#: The counter-screen: the closest paralogue, which the series must not hit.
COUNTER = ("KIN-B (paralogue)", 6.2e-6, 1.0, 88.0)

#: The lead in cells, which is always worse than the enzyme assay.
CELL_IC50 = 1.1e-8

DOSES = tuple(10.0 ** (-10.0 + 0.6667 * i) for i in range(10))   # 0.1 nM..100 uM


def pic50(molar: float) -> float:
    return -math.log10(molar)


def selectivity_fold() -> float:
    """How far the lead is from the paralogue it must not hit."""
    return COUNTER[1] / COMPOUNDS[0][1]


def hill(dose: float, ic50: float, slope: float, top: float,
         bottom: float = 1.5) -> float:
    """Percent inhibition at one concentration."""
    return bottom + (top - bottom) / (1.0 + (ic50 / dose) ** slope)


def response(ic50: float, slope: float, top: float, seed: int
             ) -> list[tuple[float, float, float]]:
    """(dose, mean, standard error) at every concentration, with noise on it.

    The error grows towards the middle of the curve, which is where replicate
    assays actually disagree: at the top and bottom the answer is saturated and
    everyone measures the same thing.
    """
    rng = random.Random(seed)
    out = []
    for dose in DOSES:
        true = hill(dose, ic50, slope, top)
        spread = 1.4 + 3.6 * math.sin(math.pi * min(1.0, true / max(top, 1.0)))
        out.append((dose, true + rng.gauss(0.0, spread * 0.45), spread))
    return out


# --- selectivity -----------------------------------------------------------

#: The panel the series was screened against. The first is the intended target.
KINASES = ("KIN-A", "KIN-B", "KIN-C", "AURK-B", "CDK2", "CDK9", "GSK3B",
           "JAK2", "MAP2K1", "PLK1", "ROCK1", "SRC", "SYK", "TRKA")
SERIES = ("DGM-002", "DGM-055", "DGM-118", "DGM-247", "DGM-390", "DGM-431")

#: Where the three compounds with a full dose-response sit in the series. The
#: panel screens six analogues; only these three were taken all the way.
MEASURED = {"DGM-002": 0, "DGM-118": 2, "DGM-431": 5}


def _between(known: dict[int, float], step: int) -> float:
    """Straight-line interpolation between the steps that were measured."""
    if step in known:
        return known[step]
    marks = sorted(known)
    low = max(m for m in marks if m < step)
    high = min(m for m in marks if m > step)
    share = (step - low) / (high - low)
    return known[low] + share * (known[high] - known[low])


def selectivity() -> list[list[float]]:
    """pIC50 for every kinase against every compound in the series.

    The target row is not invented: it is the potency of the same three
    compounds panel (d) titrates, interpolated across the analogues in
    between, and KIN-B's last entry is the counter-screen from that panel. A
    figure whose heatmap and whose curves disagree about the same number is
    worse than one without the heatmap, and nothing in the library can catch
    it -- both panels lint perfectly clean while contradicting each other.

    Everything else is invented, but built so the story is legible rather than
    random: potency against the off-targets drifts down as the chemistry is
    optimised, and the near paralogue KIN-B climbs with the target early and is
    then engineered away, which is what the counter-screen is watching for.
    """
    rng = random.Random(20260822)
    target_row = {MEASURED[name]: pic50(ic50) for name, ic50, _, _ in COMPOUNDS}
    last = len(SERIES) - 1
    rows = []
    for index, kinase in enumerate(KINASES):
        row = []
        for step, _ in enumerate(SERIES):
            progress = step / last
            if kinase == "KIN-A":
                row.append(round(_between(target_row, step), 2))
                continue
            if kinase == "KIN-B":
                # Up with the target for the first half, then away from it.
                start, peak, end = 5.72, 6.85, pic50(COUNTER[1])
                value = (start + (peak - start) * (progress / 0.5) if progress <= 0.5
                         else peak + (end - peak) * ((progress - 0.5) / 0.5))
            else:
                base = 5.3 + 1.5 * rng.random()
                value = base - 0.9 * progress + 0.25 * math.sin(index * 1.7)
            row.append(round(max(4.5, min(9.4, value + rng.gauss(0, 0.11))), 2))
        rows.append(row)
    return rows


# --- the trial -------------------------------------------------------------

#: name, patients, Weibull scale (months), shape, seed. Both arms share a
#: shape so the hazards really are proportional and a single hazard ratio is a
#: fair summary of them -- quoting one over curves that cross would not be.
SHAPE = 1.35
ARMS = (("DGM-431 + SoC", 214, 14.8, SHAPE, 20260101),
        ("Placebo + SoC", 212, 7.4, SHAPE, 20260202))

FOLLOW_UP = 24.0          # months; anyone still in the trial is censored here
RISK_TIMES = (0, 3, 6, 9, 12, 15, 18, 21, 24)

def hazard_ratio() -> tuple[float, float, float]:
    """The true hazard ratio of the generating model, and a CI around it.

    For two Weibulls of the same shape the ratio is exact, so the figure quotes
    the number its own data were drawn from rather than a decoration. The
    interval is the usual large-sample one on log HR, whose standard error is
    the root of the reciprocal event counts -- an approximation, but one that
    moves when the simulated event counts move.
    """
    treated, control = ARMS[0][2], ARMS[1][2]
    ratio = (control / treated) ** SHAPE
    events = [sum(1 for _, seen in _times(*ARMS[arm][1:]) if seen)
              for arm in (0, 1)]
    error = math.sqrt(sum(1.0 / count for count in events))
    return ratio, ratio * math.exp(-1.96 * error), ratio * math.exp(1.96 * error)


def hazard_text() -> str:
    ratio, low, high = hazard_ratio()
    return f"HR {ratio:.2f} (95% CI {low:.2f}-{high:.2f}), p < 0.0001"


def _times(count: int, scale: float, shape: float, seed: int
           ) -> list[tuple[float, bool]]:
    """Progression times and whether each was observed or censored."""
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        event = scale * (-math.log(1.0 - rng.random())) ** (1.0 / shape)
        drop = rng.expovariate(1.0 / 46.0)          # loss to follow-up
        end = min(event, drop, FOLLOW_UP)
        out.append((end, end == event))
    return sorted(out)


def survival(arm: int) -> tuple[list[tuple[float, float]], list[float], list[int]]:
    """Kaplan-Meier steps, the censored times, and the number still at risk."""
    _, count, scale, shape, seed = ARMS[arm]
    observed = _times(count, scale, shape, seed)
    steps, censored = [(0.0, 1.0)], []
    at_risk, estimate = count, 1.0
    for when, event in observed:
        if event:
            estimate *= (at_risk - 1) / at_risk
            steps.append((when, estimate))
        else:
            censored.append(when)
        at_risk -= 1
    steps.append((FOLLOW_UP, estimate))
    remaining = [sum(1 for when, _ in observed if when >= mark)
                 for mark in RISK_TIMES]
    return steps, censored, remaining


def median_survival(arm: int) -> float:
    """Where the curve first crosses one half."""
    steps, _, _ = survival(arm)
    for when, estimate in steps:
        if estimate <= 0.5:
            return when
    return float("nan")


# --- best response ---------------------------------------------------------

#: RECIST thresholds: below -30% is a partial response, above +20% progression.
PARTIAL, PROGRESSION = -30.0, 20.0


def waterfall() -> list[float]:
    """Best percentage change in the sum of target lesions, worst first."""
    rng = random.Random(4310)
    out = []
    for index in range(58):
        # A responder population with a tail: most shrink, a few do not.
        centre = -80.0 + 122.0 * (index / 57.0) ** 1.75
        out.append(round(max(-100.0, centre + rng.gauss(0.0, 9.0)), 1))
    return sorted(out)


def response_class(change: float) -> str:
    if change <= -100.0 + 1e-9:
        return "complete"
    if change <= PARTIAL:
        return "partial"
    if change >= PROGRESSION:
        return "progressive"
    return "stable"
