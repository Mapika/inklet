"""Bar labels, dumbbells, lollipops, labelled points, ECDFs, radar and pie.

One journal-width figure with a panel for each plot type added in the
capability-gap work (see docs/design/capability-gaps.md):

    a  stacked horizontal bars with a count in every segment that fits
    b  a dumbbell: expression before and after, per gene
    c  a lollipop: enrichment per pathway
    d  a volcano plot whose highlighted genes are named by `label_points`
    e  empirical cumulative distributions of two samples
    f  a radar chart of two models over six scores
    g  a donut of cell-type shares

All data are simulated or illustrative. Writes examples/new_plot_types.svg,
.pdf and .png, and prints the lint report.

    PYTHONPATH=src .venv/bin/python examples/new_plot_types.py
"""

from __future__ import annotations

import random

import inklet

rng = random.Random(11)
BLUE, ORANGE, GREEN, GREY, YELLOW = "#24698c", "#a4532f", "#1f6f60", "#b9b8b4", "#e6b93f"

# -- a: stacked bars with segment counts -----------------------------------

cells = ["79", "81", "102", "116", "153", "186"]
specific = [43, 18, 51, 40, 26, 9]
shared = [0, 7, 1, 6, 7, 3]
common = [0, 1, 0, 3, 3, 1]
bars = inklet.panel(38, 30, x=(0, 60), y=cells)
bars.bars(cells, [specific, shared, common], stacked=True, orient="h", width=0.72,
          color=["#668fb8", YELLOW, GREY], name=["specific", "shared", "common"],
          labels=True, stroke="none")
bars.axes(x="cell types", y="neuron class").legend(side="top")

# -- b: dumbbell -------------------------------------------------------------

genes = ["Gad1", "Slc17a7", "Pvalb", "Sst", "Vip", "Olig2"]
before = [2.1, 3.4, 1.2, 4.0, 2.6, 0.8]
after = [3.9, 2.0, 1.9, 5.2, 3.4, 0.9]
dumbbell = inklet.panel(30, 30, x=(0, 6), y=genes)
dumbbell.dumbbell(genes, [before, after], orient="h", name=["before", "after"],
                  color=[BLUE, ORANGE])
dumbbell.axes(x="log CPM").legend(side="top")

# -- c: lollipop -------------------------------------------------------------

pathways = ["synapse", "axon", "myelin", "immune", "vascular", "cilia", "ribosome"]
scores = [2.8, 2.1, 1.4, -0.9, -1.6, 0.6, -2.3]
lollipop = inklet.panel(30, 30, x=(-3, 3), y=pathways)
lollipop.vline(0, stroke="#5f6b7a")
lollipop.lollipop(pathways, scores, orient="h", color=GREEN)
lollipop.axes(x="enrichment")

# -- d: labelled volcano -----------------------------------------------------

cloud = [(rng.gauss(0, 1.2), abs(rng.gauss(0, 1.3)) * 1.6) for _ in range(600)]
hits = sorted(cloud, key=lambda g: -(g[1] + abs(g[0])))[:9]
names = ["Fos", "Arc", "Egr1", "Npas4", "Junb", "Nr4a1", "Bdnf", "Homer1", "Egr2"]
volcano = inklet.panel(32, 34, x=(-4.5, 4.5), y=(0, 9))
volcano.hline(1.3, stroke="#8a949e", stroke_dash=(0.8, 0.6))
volcano.scatter(cloud, size=0.6, color="#c4c9cf")
volcano.scatter(hits, size=0.9, color=ORANGE)
volcano.label_points(hits, names)
volcano.axes(x="log2 fold change", y="-log10 p")

# -- e: ECDF -----------------------------------------------------------------

control = [rng.gauss(4.1, 0.62) for _ in range(72)]
treated = [rng.gauss(4.65, 0.78) for _ in range(72)]
ecdf = inklet.panel(28, 34, x=(1, 8), y=(0, 1))
ecdf.ecdf(control, name="control", stroke=BLUE)
ecdf.ecdf(treated, name="treated", stroke=GREEN)
ecdf.axes(x="measurement / a.u.", y="cumulative fraction").legend(side="top")

# -- f: radar ----------------------------------------------------------------

radar = inklet.polar(13, r=(0, 1), zero="up", winding="cw")
radar.radar_grid(["speed", "accuracy", "recall", "depth", "range", "stability"])
radar.radar([0.8, 0.6, 0.9, 0.4, 0.7, 0.5], name="model A", color=BLUE)
radar.radar([0.5, 0.9, 0.6, 0.8, 0.4, 0.7], name="model B", color=ORANGE)
radar.legend(side="bottom")

# -- g: donut ----------------------------------------------------------------

donut = inklet.polar(11, hole=5.5, zero="up", winding="cw")
donut.pie([54, 28, 12, 4, 2], color=[BLUE, GREEN, ORANGE, YELLOW, GREY],
          name=["neurons", "glia", "vascular", "immune", "other"])
donut.legend(side="bottom")

fig = inklet.figure(width=180, theme="nature")
top = inklet.row(inklet.letters([bars, dumbbell, lollipop]), gap=8, align="top")
bottom = inklet.row(inklet.letters([volcano, ecdf, radar.build(), donut.build()],
                                   start="d"), gap=4, align="top")
fig.add(inklet.column([top, bottom], gap=6))
fig.save("examples/new_plot_types.svg")
fig.save("examples/new_plot_types.pdf")
with open("examples/new_plot_types.png", "wb") as out:
    out.write(fig.to_png(dpi=300))
print(inklet.format_report(fig.lint()))
