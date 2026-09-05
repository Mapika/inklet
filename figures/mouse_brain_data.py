"""Every number in `mouse_brain.py`, invented here and nowhere else.

There is no such experiment. The point of putting the simulation in its own
module is that the figure beside it can then never quote a number it did not
draw: the significance bracket in panel (e) is computed from the same
per-animal values the panel plots, and the peak firing rate the caption names
is read off the same PSTH panel (d) draws.

Determinism is the other reason. Every series comes from `random.Random` with
a stated seed and no wall clock anywhere, so two builds of the figure produce
the same bytes -- which is what lets the test suite compare them.

Shapes and units are chosen to be plausible rather than merely pretty: percent
correct on a two-alternative task starts at chance and saturates, a
dopaminergic unit fires a few spikes a second at rest and bursts to a few tens
of hertz, and an AAV needs about three weeks to express.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

# -- the two groups ---------------------------------------------------------

#: Opsin animals first, so that group 0 is the manipulated one everywhere --
#: in the learning curves, in the raster, in the summary, and in the colour
#: each panel picks by index.
GROUPS = ("ChR2", "eYFP")
COHORT = {"ChR2": 12, "eYFP": 11}

DAYS = tuple(range(1, 9))

#: Chance is 50% on a two-port task, and no animal starts above it. The
#: asymptote is where the group ends up and `tau` how many sessions it takes
#: to get two thirds of the way there.
_LEARNING = {"ChR2": (50.5, 88.0, 2.5), "eYFP": (50.0, 71.5, 3.1)}

#: Between-animal spread of the asymptote and of the rate, then the
#: session-to-session noise on one animal's score. A session is 120 trials, so
#: the binomial standard error at 80% correct is 3.7 points; 3.4 is that,
#: rounded down because a well-trained animal is a little more consistent than
#: a coin.
_ANIMAL_SPREAD = (7.0, 0.55)
_SESSION_NOISE = 3.4


@dataclass(frozen=True)
class Curve:
    """One group's learning curve: the mean, and one standard error either side."""

    group: str
    mean: tuple[float, ...]
    sem: tuple[float, ...]
    animals: tuple[tuple[float, ...], ...]

    @property
    def lo(self) -> tuple[float, ...]:
        return tuple(m - s for m, s in zip(self.mean, self.sem))

    @property
    def hi(self) -> tuple[float, ...]:
        return tuple(m + s for m, s in zip(self.mean, self.sem))


def learning(group: str) -> Curve:
    """Percent correct per session for every animal in one group.

    Seeded off the group name so that adding an animal to one cohort cannot
    silently redraw the other.
    """
    start, plateau, tau = _LEARNING[group]
    rng = random.Random(4310 + sum(map(ord, group)))
    animals = []
    for _ in range(COHORT[group]):
        ceiling = plateau + rng.gauss(0.0, _ANIMAL_SPREAD[0])
        rate = max(0.9, tau + rng.gauss(0.0, _ANIMAL_SPREAD[1]))
        scores = []
        for day in DAYS:
            ideal = ceiling - (ceiling - start) * math.exp(-(day - 1) / rate)
            # Clipped at both ends: percent correct is a percentage, and an
            # animal that guesses cannot score below chance for long.
            scores.append(min(99.0, max(35.0, ideal + rng.gauss(0.0, _SESSION_NOISE))))
        animals.append(tuple(round(s, 2) for s in scores))
    mean = tuple(round(sum(col) / len(col), 3) for col in zip(*animals))
    sem = tuple(round(_sem(col), 3) for col in zip(*animals))
    return Curve(group, mean, sem, tuple(animals))


def endpoint(group: str) -> tuple[float, ...]:
    """Each animal's score on the last session -- what panel (e) plots."""
    return tuple(animal[-1] for animal in learning(group).animals)


def _sem(values) -> float:
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(var / n)


def mean_sem(values) -> tuple[float, float]:
    return sum(values) / len(values), _sem(values)


# -- the one statistical claim the figure makes -----------------------------

#: How many relabellings the permutation test draws. 23 animals admit 1.35
#: million distinct splits; twenty thousand of them resolve a p of 1e-3 to
#: about a fifth of itself, which is all the precision a bracket needs.
PERMUTATIONS = 20_000


def permutation_p(a, b, *, seed: int = 90210,
                  rounds: int = PERMUTATIONS) -> float:
    """Two-sided permutation test on the difference of means.

    A permutation test rather than a t-test because it needs no distribution
    function the standard library does not have, makes no normality
    assumption, and is exactly reproducible from a seed. The returned value is
    the fraction of relabellings whose difference is at least as extreme as
    the observed one, with the observed labelling counted in both numerator
    and denominator -- the usual correction, and the reason this can never
    return a flat zero.
    """
    pool = list(a) + list(b)
    cut = len(a)
    observed = abs(sum(a) / len(a) - sum(b) / len(b))
    rng = random.Random(seed)
    extreme = 0
    for _ in range(rounds):
        rng.shuffle(pool)
        left, right = pool[:cut], pool[cut:]
        if abs(sum(left) / cut - sum(right) / (len(pool) - cut)) >= observed:
            extreme += 1
    return (extreme + 1) / (rounds + 1)


def p_text(p: float) -> str:
    """A p value written the way a figure legend writes one.

    Reported against 0.001 rather than to four places: twenty thousand
    relabellings cannot resolve a p below about 5e-5, and quoting one to more
    digits than the test can carry is the commonest small dishonesty in a
    figure legend.
    """
    return "//P// < 0.001" if p < 0.001 else f"//P// = {p:.3f}"


def stars(p: float) -> str:
    """The bracket's label. Nothing is drawn above 0.05."""
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "n.s."


# -- the recording ----------------------------------------------------------

TRIALS = 32
WINDOW = (-0.5, 1.5)          # seconds around cue onset
STIM = (0.0, 0.5)             # the light is on for half a second
BIN = 0.025                   # PSTH bin width, seconds

#: Baseline, the phasic burst, the plateau while the light is on, and the
#: pause that follows it. Rates in spikes per second.
_BASELINE = 4.6
_PEAK = 31.0
_PLATEAU = 12.5
_PAUSE = 1.3


def rate(t: float) -> float:
    """The intensity of the point process at time `t`, in Hz.

    A ramp-and-pause of the kind a dopaminergic unit shows to a reward-
    predicting cue: a burst locked to the light, a lower plateau while it
    stays on, and a pause on offset before baseline returns.
    """
    if t < STIM[0]:
        return _BASELINE
    if t < STIM[1]:
        burst = (_PEAK - _PLATEAU) * math.exp(-((t - 0.055) / 0.055) ** 2)
        return _PLATEAU + burst
    if t < 0.95:
        # The pause recovers exponentially rather than stepping back, which is
        # what a rebound looks like in a peri-event histogram.
        return _BASELINE - (_BASELINE - _PAUSE) * math.exp(-(t - STIM[1]) / 0.28)
    return _BASELINE


def spike_trains(seed: int = 7719) -> tuple[tuple[float, ...], ...]:
    """One inhomogeneous Poisson train per trial, by thinning.

    Thinning is the textbook way to sample a Poisson process whose rate
    varies: draw from a homogeneous process at the highest rate the window
    reaches, then keep each event with probability `rate(t) / ceiling`. It
    needs nothing but a uniform generator, so the trains are reproducible from
    the seed alone.
    """
    rng = random.Random(seed)
    ceiling = _PEAK * 1.05
    trains = []
    for _ in range(TRIALS):
        spikes, t = [], WINDOW[0]
        while True:
            t -= math.log(1.0 - rng.random()) / ceiling
            if t >= WINDOW[1]:
                break
            if rng.random() < rate(t) / ceiling:
                spikes.append(round(t, 5))
        trains.append(tuple(spikes))
    return tuple(trains)


def psth(trains=None) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Bin centres and mean firing rate, in seconds and Hz.

    Divided by the bin width and by the trial count, so the y axis is a rate
    an author can compare with the model above rather than a count that
    depends on how the window was cut.
    """
    trains = spike_trains() if trains is None else trains
    count = int(round((WINDOW[1] - WINDOW[0]) / BIN))
    hits = [0] * count
    for train in trains:
        for spike in train:
            index = int((spike - WINDOW[0]) / BIN)
            if 0 <= index < count:
                hits[index] += 1
    centres = tuple(round(WINDOW[0] + (i + 0.5) * BIN, 5) for i in range(count))
    rates = tuple(round(h / (BIN * len(trains)), 3) for h in hits)
    return centres, rates


def peak_rate() -> float:
    """The tallest PSTH bin, for the caption to quote."""
    return max(psth()[1])


# -- the protocol -----------------------------------------------------------

#: Step, what happens, how long. Read in order; panel (b) draws it as a chain.
PROTOCOL = (
    ("habituation", "handling,\nhead-plate", "3 d"),
    ("surgery", "AAV5-DIO-ChR2\n+ fibre, VTA", "d -21"),
    ("expression", "no testing", "3 wk"),
    ("training", "cue → reward,\n120 trials/d", "d 1-8"),
    ("recording", "acute probe\n+ 473 nm", "d 9-10"),
)

#: Where the fibre tip and the virus went, in millimetres from bregma --
#: the coordinates a methods section would print, to the tenth of a
#: millimetre a stereotaxic frame is driven to.
#:
#: They are not the figure's source of truth for the *geometry* any more.
#: `mouse_brain.py` puts the fibre at the centre of the right VTA lobe of the
#: Allen atlas mesh it draws, and these three numbers are that centre rounded;
#: `tests/test_mouse_figure.py` fails if the two ever drift apart. That way
#: round because a drawing that reads its target off the atlas cannot point
#: somewhere the atlas does not agree with, and a caption still has round
#: numbers to quote.
TARGET = {"ml": 0.8, "ap": -3.0, "dv": -4.8}
# Dorsal to the *target coordinate*, which is the centre of the nucleus and
# not its top: the lobe stands about 0.4 mm proud of its own centre, so a tip
# 0.3 mm above the coordinate is inside the tissue, which is where a fibre
# lighting a nucleus 0.9 mm deep belongs. The caption says "dorsal to the
# target" for that reason and not "above the nucleus", which the render shows
# would be a different and wronger drawing.
FIBRE_TIP_ABOVE = 0.3
FIBRE_DIAMETER = 0.2          # 200 um core, the usual multimode patch fibre
