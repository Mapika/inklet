"""Hexbins, regression bands, Bland-Altman, letter values, sina, QQ, KDE and 100% bars.

One journal-width figure with a panel for each group of statistical plots:

    a  a hexbin of 20,000 correlated scores with a count colour bar
    b  a linear fit with its 95% confidence band
    c  a Bland-Altman plot of a meter against the lab, with 95% intervals
       on the bias and the limits of agreement
    d  letter-value (boxen) plots of three distributions of 5,000 values
    e  sina plots of two genotypes
    f  a normal QQ plot of a heavy-tailed sample
    g  kernel density curves of two conditions
    h  100% stacked bars with percent labels

All data are simulated. Writes examples/stat_plot_types.svg, .pdf and .png,
and prints the lint report.

    PYTHONPATH=src .venv/bin/python examples/stat_plot_types.py
"""

from __future__ import annotations

import random

import inklet

rng = random.Random(7)

# -- a: hexbin -------------------------------------------------------------------

scores = []
for _ in range(20000):
    a = rng.gauss(0, 1)
    scores.append((a, 0.6 * a + rng.gauss(0, 0.8)))
hexes = inklet.panel(32, 32, x=(-4, 4), y=(-4, 4))
hexes.hexbin(scores, gridsize=22).colorbar(label="Cells")
hexes.axes(x="Score A", y="Score B")

# -- b: regression -----------------------------------------------------------------

dose = [rng.uniform(0, 10) for _ in range(60)]
growth = [(d, 1.5 + 0.8 * d + rng.gauss(0, 1.4)) for d in dose]
fit = inklet.panel(32, 32, x=(0, 10), y=(-2, 14))
fit.regression(growth, confidence=0.95)
fit.axes(x="Dose / mg", y="Growth / mm")

# -- c: Bland-Altman -----------------------------------------------------------------

lab = [rng.uniform(60, 180) for _ in range(80)]
meter = [v + 3 + rng.gauss(0, 4.5) for v in lab]
agree = inklet.panel(32, 32, x=(50, 190), y=(-20, 25))
agree.bland_altman(meter, lab, confidence=0.95, format="{:.1f}")
agree.axes(x="Mean / mg dl⁻¹", y="Meter − lab / mg dl⁻¹")

# -- d: boxen -------------------------------------------------------------------------

shapes = {
    "Normal": [rng.gauss(0, 1) for _ in range(5000)],
    "Wide": [rng.gauss(0, 2) for _ in range(5000)],
    "Skewed": [rng.lognormvariate(0, 0.6) * 1.5 - 1.5 for _ in range(5000)],
}
boxen = inklet.panel(32, 32, x=list(shapes), y=(-8, 10))
boxen.boxen(shapes)
boxen.axes(y="Value / a.u.")

# -- e: sina ----------------------------------------------------------------------------

genotypes = {"wt": [rng.gauss(3, 0.5) for _ in range(250)],
             "ko": [rng.gauss(4.5, 1.0) for _ in range(250)]}
sina = inklet.panel(32, 32, x=list(genotypes), y=(0, 8))
sina.sina(genotypes, size=0.9)
sina.axes(y="Response / a.u.")

# -- f: QQ --------------------------------------------------------------------------------

heavy = [rng.gauss(0, 1) / max(0.25, rng.random()) ** 0.5 for _ in range(200)]
qq = inklet.panel(32, 32, x=(-3, 3), y=(-8, 8))
qq.qq(heavy)
qq.axes(x="Normal quantile", y="Sample quantile")

# -- g: KDE ------------------------------------------------------------------------------

control = [rng.gauss(4, 0.8) for _ in range(300)]
treated = [rng.gauss(5, 1.1) for _ in range(300)]
density = inklet.panel(32, 32, x=(0, 9), y=(0, 0.6))
density.kde(control, fill=True, name="Control")
density.kde(treated, fill=True, name="Treated")
density.axes(x="Response / a.u.", y="Density").legend()

# -- h: 100% stacked bars ------------------------------------------------------------------

samples = ["S1", "S2", "S3", "S4"]
counts = [[310, 420, 55, 260], [160, 150, 170, 75], [90, 170, 360, 230]]
share = inklet.panel(32, 32, x=samples, y=(0, 100))
share.bars(samples, counts, normalize=True, labels=True, width=0.7,
           names=["T cells", "B cells", "Myeloid"], stroke="none")
share.axes(y="Share of cells / %").legend(side="right")

fig = inklet.figure(width=180, theme="nature")
panels = inklet.letters([hexes, fit, agree, boxen, sina, qq, density, share])
rows = [inklet.row(panels[k:k + 3], gap=10, align="top") for k in range(0, 8, 3)]
fig.add(inklet.column(rows, gap=8))
fig.save("examples/stat_plot_types.svg")
fig.save("examples/stat_plot_types.pdf")
with open("examples/stat_plot_types.png", "wb") as out:
    out.write(fig.to_png(dpi=300))
print(inklet.format_report(fig.lint()))
