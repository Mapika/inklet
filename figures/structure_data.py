"""Every number in the assay panels of `structure.py`, invented here.

There is no such experiment. The structure the figure is drawn from is real --
PDB 1M17, the EGFR kinase domain -- and nothing in this file is: the compound
does not exist, so neither do its binding constants, and the mutants were
never made.

What the simulation is *for* is the one claim the structure panels make and
cannot test. Two of the three hydrogen bonds the compound makes to the hinge
are to **main-chain** atoms -- the amide N of Met769 and the carbonyl O of
Gln767 -- and one is to a **side chain**, the gatekeeper Thr766. A mutation to
alanine takes a side chain away and leaves the main chain exactly where it
was, so the geometry predicts that Q767A and M769A should barely move the
affinity while anything done to Thr766 should wreck it. The numbers below are
written to say that, and `structure.py` reads which contact is which off
`target.RESTRAINTS` rather than being told, so the panel and the pose cannot
come to disagree about what is main chain.

Determinism is the other reason for a module: every series comes from
`random.Random` with a stated seed and no wall clock, so two builds produce
the same bytes.

Shapes and units are the ones a surface-plasmon-resonance experiment reports:
response in resonance units against seconds, association constants in
M^-1 s^-1, dissociation in s^-1, and an affinity in molar that is the ratio of
the two rather than a third free number.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

#: Analyte concentrations injected over the chip, in molar. Three-fold steps
#: spanning the wild-type affinity, which is how a kinetic titration is laid
#: out: two below the K_D, one on it, two above, so the curvature that carries
#: the rate constants is present in the family rather than only in its ends.
CONCENTRATIONS = (5.0e-10, 1.5e-9, 4.5e-9, 1.35e-8, 4.05e-8)

#: Injection start and stop, and the end of the wash, in seconds.
INJECTION = (0.0, 180.0)
FOLLOW = 600.0

#: The capture level of the chip: how much response a fully occupied surface
#: gives, in resonance units. Sized for a 6 kDa compound over a 30 kRU protein
#: surface, which is where a real experiment lands.
RMAX = 46.0

#: Baseline noise, in resonance units, and the refractive-index step the
#: buffer change makes at the start and end of every injection. The spike is
#: not noise -- it is real and every sensorgram has it -- but it is an artefact
#: of the fluid and not of the binding, so the fit ignores it and so does the
#: eye of anyone who has seen one.
NOISE = 0.22
SPIKE = 1.1


@dataclass(frozen=True)
class Variant:
    """One protein made and measured: what was changed and what it did.

    `residue` is the residue number in the deposited entry, so the panel can
    ask `target.RESTRAINTS` what the compound touches there instead of being
    told here. `note` is what a kinase paper calls the position.
    """

    name: str
    residue: int | None
    note: str
    kon: float            # M^-1 s^-1
    kd: float             # molar

    @property
    def koff(self) -> float:
        """s^-1, as the ratio rather than as a third free number."""
        return self.kon * self.kd

    @property
    def half_life(self) -> float:
        """How long the complex lasts, in seconds."""
        return math.log(2.0) / self.koff


#: The panel, in the order the residues sit in the pocket: the gatekeeper at
#: the back, the hinge in the middle, the catalytic lysine below the site.
#:
#: The two alanine mutants at the hinge are the controls the geometry asks
#: for. Their contacts are main-chain, so taking their side chains away should
#: do nothing measurable, and here it does not: 1.2- and 1.4-fold, inside the
#: scatter of the fits. T766A takes away a real hydrogen bond and costs 27
#: fold -- 2.0 kcal/mol at 25 C, which is what one is worth. T766M does not
#: take a bond away, it puts a methionine where the compound's carbonyl sits,
#: and 620-fold is what a steric clash costs. K721A never touches the compound
#: and its 3.4-fold is the indirect sort: the lysine holds the cleft shut.
VARIANTS = (
    Variant("wild type", None, "", 2.4e5, 3.1e-9),
    Variant("T766A", 766, "gatekeeper", 1.9e5, 8.4e-8),
    Variant("T766M", 766, "gatekeeper", 5.2e4, 1.9e-6),
    Variant("Q767A", 767, "hinge", 2.3e5, 3.6e-9),
    Variant("M769A", 769, "hinge", 2.2e5, 4.4e-9),
    Variant("K721A", 721, "catalytic", 1.7e5, 1.1e-8),
)

#: Fitting error on each rate, as a fraction: what a global fit to five
#: injections returns for a well-behaved 1:1 interaction. Kept as one number
#: rather than one per variant, because it is a property of the method.
FIT_ERROR = 0.11


def variant(name: str) -> Variant:
    for one in VARIANTS:
        if one.name == name:
            return one
    raise KeyError(f"no variant {name!r}; have {[v.name for v in VARIANTS]}")


def fold_change(one: Variant) -> float:
    """How much weaker than wild type, as the ratio of the affinities."""
    return one.kd / VARIANTS[0].kd


def ddg(one: Variant, celsius: float = 25.0) -> float:
    """The cost of the mutation in kcal/mol, from the ratio of affinities.

    RT ln(K_mut / K_wt), which is the only honest way to put a fold change on
    an energy axis: it is the same measurement in units a reader can add up
    against the hydrogen bond the structure panels draw.
    """
    rt = 1.98720425e-3 * (celsius + 273.15)
    return rt * math.log(fold_change(one))


def _langmuir(one: Variant, concentration: float,
              time: float) -> float:
    """Response at one instant for a 1:1 interaction, in resonance units.

    Association rises to its own plateau at `kon*C + koff`; dissociation is a
    plain exponential off whatever level the injection reached. Both halves
    are the closed-form solution rather than an integration, so the curve a
    reader sees is the model the constants belong to.
    """
    start, stop = INJECTION
    equilibrium = RMAX * concentration / (concentration + one.kd)
    rate = one.kon * concentration + one.koff
    if time <= start:
        return 0.0
    if time <= stop:
        return equilibrium * (1.0 - math.exp(-rate * (time - start)))
    at_stop = equilibrium * (1.0 - math.exp(-rate * (stop - start)))
    return at_stop * math.exp(-one.koff * (time - stop))


def sensorgram(one: Variant, concentration: float, *,
               samples: int = 121, seed: int = 0) -> list[tuple[float, float]]:
    """One injection, sampled at the rate an instrument records it.

    Seeded off the concentration as well as the variant so that adding a curve
    to the family cannot silently redraw the ones already in it.
    """
    rng = random.Random(9700 + seed + int(round(concentration * 1e12))
                        + sum(map(ord, one.name)))
    out = []
    for index in range(samples):
        time = FOLLOW * index / (samples - 1.0)
        value = _langmuir(one, concentration, time)
        # The buffer step, one sample wide at each end of the injection.
        for edge, sign in ((INJECTION[0], 1.0), (INJECTION[1], -1.0)):
            if abs(time - edge) < FOLLOW / (samples - 1.0) * 0.6:
                value += sign * SPIKE
        out.append((round(time, 3), round(value + rng.gauss(0.0, NOISE), 4)))
    return out


def fitted(one: Variant, concentration: float, *,
           samples: int = 241) -> list[tuple[float, float]]:
    """The model curve the constants stand for, without the noise."""
    return [(round(FOLLOW * i / (samples - 1.0), 3),
             round(_langmuir(one, concentration,
                             FOLLOW * i / (samples - 1.0)), 4))
            for i in range(samples)]


def replicates(one: Variant, count: int = 3) -> list[float]:
    """Independent K_D determinations, in molar.

    Log-normal about the true value, because an affinity is a ratio and its
    error is multiplicative: a fit that is 20% out is 20% out whether the
    number is a nanomolar or a micromolar.
    """
    rng = random.Random(5100 + sum(map(ord, one.name)))
    return [one.kd * math.exp(rng.gauss(0.0, FIT_ERROR)) for _ in range(count)]


def spread(one: Variant) -> tuple[float, float]:
    """Mean K_D of the replicates and one standard deviation, in molar."""
    values = replicates(one)
    logs = [math.log(v) for v in values]
    mean = sum(logs) / len(logs)
    variance = sum((v - mean) ** 2 for v in logs) / (len(logs) - 1)
    return math.exp(mean), math.sqrt(variance)
