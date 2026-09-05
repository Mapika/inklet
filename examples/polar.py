"""Orientation tuning, the figure polar coordinates exist for.

Panel (a) is one cell's direction tuning curve: the mean rate at each of
twenty-four drifting directions, the standard error round it, and the axial
mean vector -- `order=2`, because a cell that answers equally to 40 and 220
degrees is perfectly *oriented* and has no preferred *direction*, and order 1
would report a resultant of zero for a beautifully tuned cell.

Panel (b) is the population: the preferred orientation of every cell in the
recording, binned into a rose. The r axis is moved off the busy quadrant and
its numbers are left unplated, because a knocked-out tile inside a wedge reads
as a hole in the data.

All of it is deterministic: one seed, stated here, and no other source of
randomness.
"""

import math
import random

import inklet

SEED = 11
DIRECTIONS = list(range(0, 360, 15))
PREFERRED = 40.0        # the cell's orientation axis, in degrees
TUNING_WIDTH = 26.0     # the von Mises width, as a standard deviation
TRIALS = 8

rng = random.Random(SEED)
TH = inklet.use_theme("nature")


def von_mises(angle: float, centre: float, width: float) -> float:
    """A bump on the circle, in the units a tuning curve is written in."""
    offset = ((angle - centre + 180.0) % 360.0) - 180.0
    return math.exp(-offset ** 2 / (2.0 * width ** 2))


def rate(angle: float) -> float:
    """The cell's expected rate: two lobes half a turn apart, plus baseline."""
    return 1.8 + 21.0 * von_mises(angle, PREFERRED, TUNING_WIDTH) \
        + 17.0 * von_mises(angle, PREFERRED + 180.0, TUNING_WIDTH)


trials = {a: [max(0.0, rng.gauss(rate(a), 2.4)) for _ in range(TRIALS)]
          for a in DIRECTIONS}
mean = [sum(trials[a]) / TRIALS for a in DIRECTIONS]
sem = [(sum((v - m) ** 2 for v in trials[a]) / (TRIALS - 1) / TRIALS) ** 0.5
       for a, m in zip(DIRECTIONS, mean)]

# The axial statistics the figure reports: the mean is halved back into the
# half turn, so 40 and 220 degrees come back as one orientation.
axis_angle, selectivity = inklet.circular_mean(DIRECTIONS, mean, order=2)

# -- (a) one cell ---------------------------------------------------------

cell = inklet.polar(21, r=(0, 30), zero="up", winding="cw")
cell.grid(r_count=3, theta_count=8)
cell.band(DIRECTIONS, [m - e for m, e in zip(mean, sem)],
          [m + e for m, e in zip(mean, sem)], name="cell 41")
cell.line(list(zip(DIRECTIONS, mean)), name="cell 41")
cell.scatter(list(zip(DIRECTIONS, mean)), size=0.9, name="cell 41")
ARROW = TH.ink_color(1, 4.5)     # readable against paper, unlike the fill
cell.mean_vector(DIRECTIONS, mean, order=2, stroke=ARROW)
cell.theta_axis(count=8, label="drift direction")
# Off the lobes: the cell answers at 40 and 220 degrees, so the axis and its
# name go through the quiet quadrant between them.
cell.r_axis(at=292.5, count=3, label="spikes s⁻¹")
cell.text(130, 27, f"//R// = {selectivity:.2f}", anchor="center",
          size=TH.font_size_small, text_fill=ARROW)

# -- (b) the population ---------------------------------------------------

# Preferred orientations cluster on the cardinal axes, as they do in carnivore
# visual cortex; the orientation domain is the half turn, so the panel is one.
population = [rng.gauss(rng.choice((0.0, 90.0)), 17.0) % 180.0
              for _ in range(220)]
centres, counts = inklet.circular_histogram(population, bins=18, domain=(0, 180))

rose = inklet.polar(21, r=(0, max(counts)), theta=(0, 180), hole=2.0)
rose.grid(r_count=2, theta_count=6)
rose.rose(counts, at=centres, width=0.94, name="cells")
rose.theta_axis(count=6, label="preferred orientation")
# No `at`: a fan's r axis defaults to its own straight edge, where the numbers
# stand outside the data instead of over it, and no plate is needed.
rose.r_axis(count=2, label="cells", plate=False)

fig = inklet.figure(width=136, theme="nature")
fig.add(inklet.row(inklet.letters([cell, rose]), gap=8, align="top"))
fig.save("examples/polar.svg")

print(f"axial mean {axis_angle:.1f} deg, R = {selectivity:.3f}")
print(fig.report())
