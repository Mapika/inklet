"""Pie breakouts, ridgelines, rainclouds, volcano, dendrogram and UpSet plots.

One journal-width figure with a panel for each plot type added in the second
round of capability-gap work (see docs/design/capability-gaps.md):

    a  a pie whose smaller slices are broken out into a stacked bar
    b  ridgelines: onset-time densities for six developmental stages
    c  rainclouds: half violin, box and jittered observations per group
    d  a volcano plot with threshold rules and the top hits named
    e  a clustered heatmap with gene and sample dendrograms
    f  an UpSet plot of the genes each assay detects

All data are simulated or illustrative. Writes examples/more_plot_types.svg,
.pdf and .png, and prints the lint report.

    PYTHONPATH=src .venv/bin/python examples/more_plot_types.py
"""

from __future__ import annotations

import math
import random

import inklet
from inklet.plot import dendrogram_layout

rng = random.Random(11)
BLUE, GREEN, INK, YELLOW, GREY = "#24698c", "#288675", "#262626", "#e6b93f", "#e4e4e4"

# -- a: pie with a breakout bar ----------------------------------------------

# The pie turns so the broken-out slices face the bar.
share = inklet.polar(10)
share.pie([24.8, 1.5, 73.7], colors=[INK, YELLOW, GREY], labels=["24.8%", None, "73.7%"],
          names=["isomorphic", "dimorphic", "noise"])
share.breakout([0, 1], labels="{share:.1%}", title="without noise")
share.legend(side="bottom")

# -- b: ridgelines -----------------------------------------------------------

stages = ["E12", "E14", "E16", "E18", "P0", "P7"]
onsets = {s: [rng.gauss(2 + k * 0.9, 0.9 - 0.08 * k) for _ in range(80)]
          + [rng.gauss(4.2 + k * 0.9, 0.4) for _ in range(20 * (k % 3))]
          for k, s in enumerate(stages)}
ridges = inklet.panel(34, 34, x=(0, 10), y=stages[::-1])
ridges.ridgeline(onsets, overlap=1.8, stroke="white",
                 colors=["#24698c", "#2d7d8a", "#3a9083", "#5aa374", "#8bb35f", "#c2bf52"])
ridges.axes(x="onset time / h")

# -- c: rainclouds -----------------------------------------------------------

samples = {"control": [rng.gauss(4.1, 0.62) for _ in range(60)],
           "treated": [rng.gauss(4.65, 0.78) for _ in range(40)]
           + [rng.gauss(6.2, 0.3) for _ in range(20)]}
rain = inklet.panel(38, 34, x=(1, 8), y=["treated", "control"])
rain.raincloud(samples, colors=[BLUE, GREEN], size=0.7)
rain.axes(x="measurement / a.u.")

# -- d: volcano --------------------------------------------------------------

fold, pvalues = [], []
for _ in range(1200):
    effect = rng.gauss(0, 0.5) if rng.random() < 0.9 else rng.gauss(0, 1.8)
    fold.append(effect)
    pvalues.append(math.erfc(abs(effect * 1.3 + rng.gauss(0, 1)) / math.sqrt(2)))
genes = [f"G{k}" for k in range(len(fold))]
volcano = inklet.panel(42, 40, x=(-6, 6), y=(0, 16))
volcano.volcano(fold, pvalues, labels=genes, top=6, names=("down", None, "up"), size=0.7)
volcano.axes(x="log2 fold change", y="-log10 p").legend(side="top")

# -- e: clustered heatmap ----------------------------------------------------

markers = ["Fos", "Arc", "Egr1", "Npas4", "Junb", "Gfap", "Aqp4", "Mbp", "Plp1", "Mog"]
runs = ["S1", "S2", "S3", "S4", "S5", "S6"]
values = [[1.1, .8, -.8, -2, .1, -.7], [1.9, 1.3, -.5, -1.4, .3, 0],
          [1.2, 1.3, -1.4, -1.3, .4, .1], [1.4, 2, -1, -1.4, .3, -.1],
          [1.4, 1.1, -.3, -1.2, .3, .3], [-.3, -.9, 1.2, 2, -.8, -.1],
          [-.8, 0, 1.1, .3, -.1, -.2], [-.1, .4, -.2, .1, 1.4, 1.9],
          [.5, .2, -.5, .3, 1.8, 1], [-.2, .6, -.3, -.1, 1.7, 1.4]]
# Average-linkage Euclidean clustering of the rows and of the columns.
gene_tree = [[7, 9, .66, 2], [1, 4, .68, 2], [2, 3, .87, 2], [8, 10, 1.12, 3],
             [11, 12, 1.13, 4], [0, 14, 1.43, 5], [5, 6, 2.11, 2],
             [13, 15, 3.19, 8], [16, 17, 4.06, 10]]
run_tree = [[4, 5, 1.57, 2], [0, 1, 1.7, 2], [2, 3, 2.3, 2], [6, 7, 3.82, 4],
            [8, 9, 5.51, 6]]
rows = list(dendrogram_layout(gene_tree, labels=markers).leaves)
cols = list(dendrogram_layout(run_tree, labels=runs).leaves)
cells = [[values[markers.index(g)][runs.index(s)] for s in cols] for g in rows]
heat = inklet.panel(27, 36, x=cols, y=rows)
heat.matrix(cells, x=cols, y=rows, ramp=inklet.ramp("tol-sunset"),
            scale=inklet.linear((-2, 2)), raster=False)
heat.axis("bottom", spine=False).axis("right", spine=False)
heat.colorbar(label="z-score", side="bottom")
gene_side = inklet.panel(9, 36, x=(4.06, 0), y=rows)
gene_side.dendrogram(gene_tree, labels=markers, orient="h", threshold=2)
run_side = inklet.panel(27, 6, x=cols, y=(0, 5.51))
run_side.dendrogram(run_tree, labels=runs)
clustered = inklet.column([run_side, inklet.row([gene_side, heat], gap=1)],
                          gap=1, align="right")

# -- f: UpSet plot -----------------------------------------------------------

pool = [f"g{k}" for k in range(600)]
assays = {"RNA-seq": {g for g in pool if rng.random() < 0.5},
          "ATAC-seq": {g for g in pool if rng.random() < 0.3},
          "ChIP-seq": {g for g in pool if rng.random() < 0.18},
          "proteomics": {g for g in pool if rng.random() < 0.1}}
overlap = inklet.upset(assays, max_intersections=8, height=22, set_width=11)

fig = inklet.figure(width=180, theme="nature")
top = inklet.row(inklet.letters([share.build(), ridges, rain]), gap=10, align="top")
bottom = inklet.row(inklet.letters([volcano, clustered, overlap], start="d"), gap=8,
                    align="top")
fig.add(inklet.column([top, bottom], gap=8))
fig.save("examples/more_plot_types.svg")
fig.save("examples/more_plot_types.pdf")
with open("examples/more_plot_types.png", "wb") as out:
    out.write(fig.to_png(dpi=300))
print(inklet.format_report(fig.lint()))
