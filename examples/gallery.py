"""Sixteen plots on one 89mm column: the whole vocabulary at journal size.

A gallery is not a demo. Everything here is drawn at the width a single-column
figure actually gets, with the theme's own defaults and no style overrides, so
that anything ugly is a fault in the library rather than in the script. If a
panel needs a hand-tuned number to look right, that number belongs in `inklet`.

    python examples/gallery.py
"""

import math
import random

import inklet

TH = inklet.use_theme("nature")

# One plot area for every panel, so they read as a set. 21.5mm is what a
# 2-across grid inside one 89mm column comes to once every panel carries its own
# labelled axes and its letter, and one of them a twin axis: the columns are as
# wide as the widest furniture in them, which is the price of having the areas
# line up. The point of the exercise is to see the defaults at the size they are
# actually used at, so nothing here is hand-tuned to flatter them.
W, H = 21.5, 15.5

RNG = random.Random(7)


def noise(scale: float) -> float:
    return RNG.uniform(-scale, scale)


# --- a: a mean with its confidence band --------------------------------------

T = [i / 2.0 for i in range(21)]
MEAN = [math.exp(-t / 4.0) * math.cos(t) for t in T]
SPREAD = [0.05 + 0.02 * t for t in T]

a = inklet.panel(W, H, x=(0, 10), y=(-1, 1))
a.hline(0.0)
a.band(T, [m - s for m, s in zip(MEAN, SPREAD)],
       [m + s for m, s in zip(MEAN, SPREAD)], name="model")
a.line(list(zip(T, MEAN)), name="model")
a.axes(x="t / s", y="x")

# --- b: a scatter and the line through it ------------------------------------

XS = [i / 1.8 for i in range(15)]
YS = [0.8 * x + 1.0 + noise(0.8) for x in XS]
SLOPE = sum(x * y for x, y in zip(XS, YS)) / sum(x * x for x in XS)

b = inklet.panel(W, H, x=(0, 8), y=(0, 9))
b.scatter(list(zip(XS, YS)), name="cells")
b.line([(0.0, 0.0), (8.0, SLOPE * 8.0)], name="fit", stroke_dash=(1.0, 0.8))
b.axes(x="dose / nM", y="response")

# --- c: bars with the spread on them -----------------------------------------

COND = ["wt", "het", "ko"]
LEVEL = [1.0, 0.62, 0.24]
ERR = [0.08, 0.11, 0.06]

c = inklet.panel(W, H, x=COND, y=(0, 1.2))
c.bars(COND, LEVEL)
c.errorbars(list(zip(COND, LEVEL)), yerr=ERR)
c.axes(y="expression")

# --- d: grouped bars, keyed from what was drawn ------------------------------

d = inklet.panel(W, H, x=COND, y=(0, 1.2))
d.bars(COND, [[1.0, 0.62, 0.24], [0.90, 0.71, 0.40]],
       names=["vehicle", "drug"])
d.axes(y="expression")
d.legend(side="top", columns=2)

# --- e: the same three conditions as parts of a whole ------------------------

STAGE = ["G1", "S", "G2"]
e = inklet.panel(W, H, x=COND, y=(0, 100))
e.bars(COND, [[52, 44, 61], [30, 33, 24], [18, 23, 15]], stacked=True,
       names=STAGE)
e.axes(y="cells / %")
e.legend(side="top", columns=3)

# --- f: a distribution ---------------------------------------------------------

SAMPLE = [RNG.gauss(0.0, 1.0) + 0.4 * RNG.gauss(0.0, 1.0) ** 2
          for _ in range(400)]

f = inklet.panel(W, H, x=(-3, 5), y=(0, 90))
f.hist(SAMPLE, bins=16)
f.axes(x="z", y="count")

# --- g: five-number summaries -------------------------------------------------

GROUPS = {name: [RNG.gauss(m, s) for _ in range(40)]
          for name, m, s in (("wt", 1.0, 0.25), ("het", 0.7, 0.3),
                             ("ko", 0.35, 0.2))}

g = inklet.panel(W, H, x=list(GROUPS), y=(-0.2, 2.0))
g.boxplot(GROUPS)
g.axes(y="ratio")

# --- h: the same summaries as densities --------------------------------------

h = inklet.panel(W, H, x=list(GROUPS), y=(-0.2, 2.0))
h.violin(GROUPS)
h.axes(y="ratio")

# --- i: a field, and the ramp that explains it -------------------------------

SIDE = 48
FIELD = [[math.sin(r / 7.0) * math.cos(col / 5.0) for col in range(SIDE)]
         for r in range(SIDE)]
HEAT = inklet.ramp("tol-sunset")
HEAT_SCALE = inklet.linear((-1.0, 1.0))

i = inklet.panel(W, H, x=(0, SIDE - 1), y=(0, SIDE - 1))
i.matrix(FIELD, ramp=HEAT, scale=HEAT_SCALE)
i.axes(x="x / um", y="y / um")
i.colorbar(side="bottom", label="dF/F")

# --- j: a quantity that changes at instants ----------------------------------

START = "2024-01-01"
DAYS = [f"2024-{1 + n // 28:02d}-{1 + n % 28:02d}" for n in range(0, 168, 14)]
SURVIVAL = [100, 96, 91, 91, 84, 77, 77, 70, 64, 61, 55, 52]

j = inklet.panel(W, H, x=(DAYS[0], DAYS[-1]), y=(0, 100))
j.step(list(zip(DAYS, SURVIVAL)), name="treated")
# No x name: the axis writes the year itself, once, past the last tick, which
# is the whole reason not to spend a label on saying "2024" twice.
j.axes(y="alive / %")

# --- k: four decades, with the minor ticks that make them readable -----------

FREQ = [10.0 ** (i / 6.0) for i in range(25)]
GAIN = [1e3 / (1.0 + (fr / 40.0) ** 2) for fr in FREQ]

k = inklet.panel(W, H, x=inklet.log((1.0, 1e4)), y=inklet.log((0.01, 2e3)))
k.line(list(zip(FREQ, GAIN)))
k.axis("bottom", label="f / Hz", minor=True)
k.axis("left", label="gain", minor=True)

# --- l: two quantities, two scales, one rectangle ----------------------------

HOURS = list(range(0, 25, 2))
TEMP = [12 + 8 * math.sin((hr - 8) / 24 * 2 * math.pi) for hr in HOURS]
RAIN = [0.0, 0.0, 0.4, 1.8, 2.6, 1.1, 0.2, 0.0, 0.0, 0.5, 1.4, 0.6, 0.0]

lo = inklet.panel(W, H, x=(0, 24), y=(0, 4))
lo.bars(HOURS, RAIN, width=1.6)
lo.axis("bottom", label="hour", ticks=[0, 6, 12, 18, 24])
lo.axis("left", label="rain / mm")
warm = lo.twin_y((0, 24), label="T / C", color=TH.color(1))
warm.line(list(zip(HOURS, TEMP)), stroke=TH.color(1))


# --- m: data that runs off the top, cut at the edge --------------------------

RAW = [math.sin(t * 3.0) + 0.32 * RNG.gauss(0.0, 1.0) for t in [i / 8 for i in range(161)]]
SECONDS = [i / 8 for i in range(161)]

# clip=True is the claim that the domain is the interesting range and the
# reader will not mistake a cut trace for a flat one. Off by default: silently
# truncating data is a lie, and a spike that leaves the panel usually matters.
m = inklet.panel(W, H, x=(0, 20), y=(-1.2, 1.2), clip=True)
m.line(list(zip(SECONDS, RAW)), name="raw")
m.axes(x="t / s", y="dF/F")

# --- n: the number the curve is read for, written on the line ----------------

DOSE = [2.0 ** (i / 2.0) for i in range(11)]
BOUND = [100.0 / (1.0 + (8.0 / d) ** 1.6) for d in DOSE]

n = inklet.panel(W, H, x=inklet.log((1, 40)), y=(0, 110))
n.line(list(zip(DOSE, BOUND)))
n.hline(50, label="EC50", stroke_dash=(1.0, 0.8))
n.vline(8, stroke_dash=(1.0, 0.8))
n.axes(x="dose / nM", y="bound / %")

# --- o: a comparison, and what came of it ------------------------------------

o = inklet.panel(W, H, x=COND, y=(0, 1.2))
o.bars(COND, LEVEL)
o.errorbars(list(zip(COND, LEVEL)), yerr=ERR)
# No height given: the bracket clears the bars and their error bars itself,
# which is the number that changes every time the data does.
o.bracket("wt", "ko", "***")
o.axes(y="expression")

# --- p: a third quantity, in colour ------------------------------------------

CELLS = [(RNG.uniform(0, 10), RNG.uniform(0, 10)) for _ in range(60)]
DEPTH = [x + y + noise(1.0) for x, y in CELLS]

p = inklet.panel(W, H, x=(0, 10), y=(0, 10))
p.scatter(CELLS, color=DEPTH, ramp=inklet.ramp("tol-ylorbr"))
p.axes(x="x / um", y="y / um")
p.colorbar(side="bottom", label="depth / um")

# --- the page ----------------------------------------------------------------

# `letters` before `facets`, and `facets(axes=False)` rather than a stack of
# rows: the letters keep the panels' origin anchors, so the grid still lines the
# *plot areas* up in both directions. Stacking the bounding boxes instead
# is what makes a multi-panel figure look homemade -- one panel's y numbers
# being wider than its neighbour's shoves its data out of line with the panel
# above it, and the eye reads the misalignment long before it reads the data.
PANELS = [a, b, c, d, e, f, g, h, i, j, k, lo, m, n, o, p]

fig = inklet.figure(width="89mm", theme="nature")
fig.add(inklet.facets(inklet.letters(PANELS), cols=2, axes=False,
                   gap=5, row_gap=4))

print(fig.report())
fig.save("examples/gallery.svg")
