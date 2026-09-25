"""Forest plots, embedding scatters, split violins and stacked p-value brackets.

One journal-width figure with a panel for each plot type added in 4.2:

    a  a forest plot of odds ratios with subgroup headers, weighted squares,
       subtotal and overall diamonds, an interval clipped at the axis limits
       and aligned text columns
    b  a UMAP-style embedding of 16,000 cells coloured and named by cluster,
       with corner arrows instead of axes
    c  split violins: two conditions per region, with quartile lines
    d  a box plot of four genotypes with six stacked significance brackets

All data are simulated or illustrative, and the p-values are made up: no test
is run. Writes examples/study_plot_types.svg, .pdf and .png, and prints the
lint report.

    PYTHONPATH=src .venv/bin/python examples/study_plot_types.py
"""

from __future__ import annotations

import math
import random

import inklet

rng = random.Random(42)
BLUE, YELLOW = "#24698c", "#e6b93f"

# -- a: forest plot -----------------------------------------------------------

studies = [
    "Adults",
    {"label": "Ahmed 2019", "estimate": 0.72, "low": 0.55, "high": 0.94, "weight": 18.2, "n": 812},
    {"label": "Berg 2020", "estimate": 0.91, "low": 0.62, "high": 1.33, "weight": 9.4, "n": 355},
    {"label": "Chen 2021", "estimate": 0.64, "low": 0.38, "high": 1.08, "weight": 6.1, "n": 210},
    {"label": "Subtotal", "estimate": 0.76, "low": 0.63, "high": 0.92, "summary": True},
    "Children",
    {"label": "Diaz 2018", "estimate": 1.12, "low": 0.70, "high": 1.80, "weight": 6.3, "n": 240},
    {"label": "Evans 2022", "estimate": 0.58, "low": 0.12, "high": 6.4, "weight": 1.0, "n": 31},
    {"label": "Subtotal", "estimate": 1.02, "low": 0.66, "high": 1.58, "summary": True},
    {"label": "Overall", "estimate": 0.81, "low": 0.69, "high": 0.95, "summary": True},
]
forest = inklet.forest(studies, log=True, limits=(0.2, 5), measure="OR",
                       right=["ci", "n"], label="odds ratio", width=30,
                       summary_line=True)

# -- b: embedding ---------------------------------------------------------------

cell_types = {"T cells": (-4.2, 2.6), "NK": (-1.4, 4.6), "B cells": (-4.8, -2.6),
              "Monocytes": (2.8, 1.8), "DC": (4.9, 4.6), "pDC": (5.8, -0.4),
              "Erythroid": (0.2, -4.4), "Platelets": (4.6, -4.4)}
umap, labels = [], []
for name, (cx, cy) in cell_types.items():
    for _ in range(rng.randint(900, 3200)):
        turn = rng.uniform(0, 2 * math.pi)
        umap.append((cx + 0.55 * math.cos(turn) + rng.gauss(0, 0.6),
                     cy + 0.35 * math.sin(turn) + rng.gauss(0, 0.45)))
        labels.append(name)
cells = inklet.panel(50, 50, x=(-8, 8.5), y=(-7, 7))
cells.embedding(umap, labels, arrows="UMAP", size=0.3)

# -- c: split violins -------------------------------------------------------------

regions = ["CA1", "CA3", "DG"]
control = {r: [rng.gauss(4 + 1.2 * k, 0.9) for _ in range(80)] for k, r in enumerate(regions)}
treated = {r: [rng.gauss(4.6 + 0.8 * k, 1.1) for _ in range(60)]
           + [rng.gauss(9, 0.5) for _ in range(12 + 6 * k)] for k, r in enumerate(regions)}
violins = inklet.panel(52, 38, x=regions, y=(0, 12))
violins.split_violin(control, treated, name=["control", "treated"], quartiles=True,
                     color=[YELLOW, "#9cc3d5"])
violins.axes(y="firing rate / Hz").legend(side="top")

# -- d: stacked brackets -----------------------------------------------------------

genotypes = ["wt", "het", "ko", "rescue"]
response = {g: [rng.gauss(m, 0.45) for _ in range(10)]
            for g, m in zip(genotypes, (3.0, 3.4, 5.0, 3.6))}
signif = inklet.panel(50, 38, x=genotypes, y=(0, 10))
signif.boxplot(response, outliers=False).swarm(response, color=[BLUE] * 4)
signif.brackets([("wt", "het", 0.21), ("wt", "ko", 2e-5), ("het", "ko", 0.004),
                 ("ko", "rescue", 7e-4), ("wt", "rescue", 0.031),
                 ("het", "rescue", 0.46)], hide_ns=True)
signif.axes(y="response / a.u.")

fig = inklet.figure(width=180, theme="nature")
top = inklet.row(inklet.letters([forest, cells]), gap=12, align="top")
bottom = inklet.row(inklet.letters([violins, signif], start="c"), gap=16, align="top")
fig.add(inklet.column([top, bottom], gap=8))
fig.save("examples/study_plot_types.svg")
fig.save("examples/study_plot_types.pdf")
with open("examples/study_plot_types.png", "wb") as out:
    out.write(fig.to_png(dpi=300))
print(inklet.format_report(fig.lint()))
