"""Dot plots, size keys and Kaplan-Meier survival curves.

One journal-width figure with a panel for each 4.2 plot type in this area
(see docs/design/capability-gaps.md):

    a  a single-cell dot plot of marker genes per cluster, with a cluster
       dendrogram, a colorbar and a size key
    b  Kaplan-Meier curves for two arms with log-log confidence bands,
       censor ticks, a supplied p-value and a number-at-risk table
    c  a scatter whose point areas are cell counts, explained by the same
       size key that panel a uses

All data are simulated or illustrative. Writes examples/dotplot_survival.svg,
.pdf and .png, and prints the lint report.

    PYTHONPATH=src .venv/bin/python examples/dotplot_survival.py
"""

from __future__ import annotations

import random

import inklet
from inklet.plot import area_scale, dendrogram_layout

rng = random.Random(21)
INK, BLUE, GREEN = "#262626", "#24698c", "#288675"

# -- a: dot plot with a cluster dendrogram -----------------------------------

genes = ["Cd3e", "Cd4", "Cd8a", "Nkg7", "Gzmb", "Ms4a1", "Cd79a", "Lyz2", "Csf1r"]
markers = {"CD4 T": {"Cd3e", "Cd4"}, "CD8 T": {"Cd3e", "Cd8a", "Gzmb"},
           "NK": {"Nkg7", "Gzmb"}, "B": {"Ms4a1", "Cd79a"},
           "Mono": {"Lyz2", "Csf1r"}, "DC": {"Lyz2", "Cd4"}}
tree = ((("CD4 T", "CD8 T"), "NK"), ("B", ("Mono", "DC")))
order = list(dendrogram_layout(tree).leaves)
fraction = [[rng.uniform(.6, .95) if g in markers[c] else rng.uniform(0, .25)
             for g in genes] for c in order]
mean = [[rng.uniform(1.6, 3) if g in markers[c] else rng.uniform(0, .8)
         for g in genes] for c in order]
# Cd79a was not measured in the DC cluster: that cell draws nothing.
fraction[order.index("DC")][genes.index("Cd79a")] = None

dots = inklet.panel(31, 24, x=genes, y=order)
dots.dotplot(fraction, mean)
dots.axis("bottom", rotate=90, spine=False).axis("right", spine=False)
dots.colorbar(label="mean expression", length=13)
dots.size_key(title="fraction", format="{:.0%}")
side = inklet.panel(8, 24, x=(3, 0), y=order)
side.dendrogram(tree, orient="h")
clustered = inklet.row([side, dots], gap=1)

# -- b: Kaplan-Meier curves --------------------------------------------------


def arm(rate: float, n: int = 60) -> tuple[list[float], list[bool]]:
    durations, events = [], []
    for _ in range(n):
        event, dropout = rng.expovariate(rate), rng.uniform(6, 60)
        durations.append(round(min(event, dropout, 36), 1))
        events.append(event <= min(dropout, 36))
    return durations, events


months = [0, 12, 24, 36]
survival = inklet.panel(38, 30, x=(0, 36), y=(0, 1))
survival.kaplan_meier({"control": arm(1 / 14), "treated": arm(1 / 30)},
                      color=[INK, BLUE], pvalue=0.003)
survival.axes(x="time / months", y="survival", x_options={"ticks": months})
survival.legend(corner="ne")
survival.at_risk(ticks=months)

# -- c: a scatter sized by cell count ----------------------------------------

cells = area_scale(2000, 3.2)
counts = [rng.choice([80, 150, 400, 900, 1600, 2000]) for _ in range(18)]
spots = [(rng.uniform(0.5, 9.5), rng.uniform(0.5, 9.5)) for _ in counts]
bubbles = inklet.panel(28, 28, x=(0, 10), y=(0, 10))
bubbles.scatter(spots, size=[cells(v) for v in counts], color=GREEN,
                stroke="white", stroke_width=0.15)
bubbles.axes(x="UMAP 1", y="UMAP 2", ticks=[])
bubbles.size_key(cells, title="cells", values=[200, 1000, 2000], side="bottom",
                 fill=GREEN, stroke="white", stroke_width=0.15)

fig = inklet.figure(width=180, theme="nature")
fig.add(inklet.row(inklet.letters([clustered, survival, bubbles]), gap=7, align="top"))
fig.save("examples/dotplot_survival.svg")
fig.save("examples/dotplot_survival.pdf")
with open("examples/dotplot_survival.png", "wb") as out:
    out.write(fig.to_png(dpi=300))
print(inklet.format_report(fig.lint()))
