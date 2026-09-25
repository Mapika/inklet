"""Hierarchies, networks, clustered matrices and genomics plots.

One journal-width figure with a panel for each plot type of this family:

    a  a treemap of cortical cell types
    b  the same hierarchy as a sunburst
    c  clustering levels as an icicle with a highlighted lineage
    d  a weighted network with a width key
    e  a directed chord diagram of flows between visual areas
    f  a correlogram
    g  an arc diagram of gene co-expression
    h  a clustered adjacency matrix with cluster boxes and a zoomed inset
    i  a clustermap with dendrograms and an annotation strip
    j  an MA plot
    k  a ternary plot of soil texture
    l  a Manhattan plot with labelled lead hits

All data are simulated or illustrative. Writes
examples/network_hierarchy_plot_types.svg, .pdf and .png, and prints the lint
report.

    PYTHONPATH=src .venv/bin/python examples/network_hierarchy_plot_types.py
"""

from __future__ import annotations

import math
import random

import inklet
from inklet.plot import correlation, cut, dendrogram_layout, linkage

rng = random.Random(3)

# -- a, b: treemap and sunburst ----------------------------------------------

cortex = {"cortex": {"L2/3 IT": 120, "L4/5 IT": 90, "L5 ET": 40, "L6 IT": 55, "L6 CT": 70,
                     "Inhibitory": {"Pvalb": 45, "Sst": 38, "Vip": 22, "Lamp5": 18, "Sncg": 6},
                     "Non-neuronal": {"Astro": 50, "Oligo": 64, "OPC": 15, "Micro": 12}}}
tree = inklet.panel(62, 36).treemap(cortex, values="{:.0f}")
rings = inklet.panel(36, 36).sunburst(cortex)

# -- c: clustering levels ----------------------------------------------------

levels = {"1": {"1.1": {"1.1.1": 8, "1.1.2": 5}, "1.2": {"1.2.1": 6, "1.2.2": 3, "1.2.3": 2}},
          "2": {"2.1": {"2.1.1": 7, "2.1.2": 7},
                "2.2": {"2.2.1": 4, "2.2.2": 3, "2.2.3": 2, "2.2.4": 2}}}
lineage = [("2",), ("2", "2.2"), ("2", "2.2", "2.2.2")]
icicle = inklet.panel(30, 36)
icicle.icicle(levels, gap=3, highlight=lineage, labels="highlight", levels=True, counts=True)

# -- d: weighted network -----------------------------------------------------

neurons = {"AVA": 60, "AVB": 34, "AVD": 22, "AVE": 28, "PVC": 25, "RIM": 18,
           "AIB": 16, "DVA": 12, "RIB": 10, "SMD": 9}
synapses = [("AVA", "AVD", 5200, "chemical"), ("AVD", "AVA", 1800, "chemical"),
            ("AVE", "AVA", 4100, "chemical"), ("AVB", "PVC", 900, "gap junction"),
            ("PVC", "AVB", 3300, "chemical"), ("RIM", "AVA", 2500, "gap junction"),
            ("AIB", "RIM", 1600, "chemical"), ("AIB", "AVE", 700, "chemical"),
            ("DVA", "AVB", 450, "gap junction"), ("RIB", "AVE", 300, "chemical"),
            ("SMD", "RIB", 1200, "gap junction"), ("AVA", "SMD", 200, "chemical")]
command = {n: "command" for n in ("AVA", "AVB", "AVD", "AVE", "PVC")}
net = inklet.panel(40, 40)
net.network(neurons, synapses, shape="square", diameter=5, arrows=True,
            groups={n: command.get(n, "other") for n in neurons},
            colors={"command": "#c0392b", "other": "#bdbdbd"},
            edge_colors={"chemical": "#4d4d4d", "gap junction": "#e69f00"})
net.width_key(title="synapses", values=[5000, 2000, 500], format="{:,.0f}")
net.legend(side="bottom")

# -- e, g: chord and arc diagrams --------------------------------------------

areas = ["V1", "LM", "AL", "RL", "AM", "PM"]
flows = [[0, 18, 9, 7, 4, 11], [16, 0, 8, 3, 2, 5], [7, 9, 0, 6, 3, 2],
         [5, 2, 7, 0, 6, 3], [3, 1, 2, 7, 0, 8], [12, 4, 1, 2, 9, 0]]
chords = inklet.panel(36, 36).chord(flows, areas, directed=True)
genes = ["Rbfox3", "Snap25", "Syt1", "Gad1", "Gad2", "Slc32a1", "Olig2", "Sox10", "Mbp"]
pairs = [("Rbfox3", "Snap25", 8), ("Snap25", "Syt1", 9), ("Rbfox3", "Syt1", 5),
         ("Gad1", "Gad2", 9), ("Gad2", "Slc32a1", 7), ("Gad1", "Slc32a1", 6),
         ("Olig2", "Sox10", 8), ("Sox10", "Mbp", 9), ("Olig2", "Mbp", 4),
         ("Syt1", "Gad1", 2), ("Snap25", "Mbp", 1)]
module = {g: "neuronal" for g in genes[:3]}
module.update({g: "inhibitory" for g in genes[3:6]}, **{g: "glial" for g in genes[6:]})
arcs = inklet.panel(62, 24).arc_diagram(genes, pairs, groups=module)
arcs.width_key(title="co-expression").legend(side="bottom")

# -- h: clustered matrix -----------------------------------------------------

n = 40
community = [k % 5 for k in range(n)]
rng.shuffle(community)
weights = [[0.0] * n for _ in range(n)]
for a in range(n):
    for b in range(a):
        linked = rng.random() < (0.7 if community[a] == community[b] else 0.05)
        weights[a][b] = weights[b][a] = linked * rng.uniform(0.3, 1)
link = linkage(weights, metric="correlation")
order = dendrogram_layout(link).order
groups = [cut(link, 5)[k] for k in order]
adjacency = [[weights[a][b] for b in order] for a in order]
lo = groups.index(2)
hi = lo + groups.count(2)
scale = inklet.linear((0, 1))
adj = inklet.panel(36, 36, x=(0, n), y=(n, 0))
adj.matrix(adjacency, scale=scale).clusters(groups, highlight=2, labels=True)
zoom = inklet.panel(16, 16)
zoom.matrix([row[lo:hi] for row in adjacency[lo:hi]], scale=scale)
adj.inset(zoom, side="right", width=None, zoom=(lo, hi, lo, hi), stroke="#c9352b",
          stroke_width=0.5, connector={"stroke_dash": (1, 0.6)})
adj.colorbar(side="bottom", label="weight", length=24)

# -- f: correlogram ----------------------------------------------------------

markers = ["Gad1", "Gad2", "Slc32a1", "Pvalb", "Sst", "Vip", "Slc17a7", "Satb2"]
base = [[rng.gauss(0, 1) for _ in range(40)] for _ in range(3)]
member = [0, 0, 0, 1, 1, 2, 2, 2]
sign = [1, 1, 1, 1, -1, -1, 1, 1]
table = [[sign[g] * base[member[g]][k] + rng.gauss(0, 0.7) for k in range(40)]
         for g in range(8)]
corr = inklet.panel(30, 30).correlogram(correlation(table), markers)
corr.colorbar(label="r", length=20)

# -- i: clustermap -----------------------------------------------------------

response = ["Fos", "Arc", "Egr1", "Npas4", "Junb", "Gfap", "Aqp4", "Aldh1l1",
            "Mbp", "Plp1", "Mog", "Olig2"]
samples = [f"S{k}" for k in range(1, 10)]
condition = ["ctrl", "ctrl", "ctrl", "KA", "KA", "KA", "LPS", "LPS", "LPS"]
signal = {"ctrl": 8, "KA": 0, "LPS": 4}
expression = [[rng.gauss(2.5 if signal[c] <= g < signal[c] + 4 else 0, 0.8)
               for c in condition] for g in range(12)]
heat = inklet.clustermap(expression, rows=response, columns=samples, standardize="rows",
                         k=3, col_colors={"condition": condition}, label="z-score", width=26)

# -- l: Manhattan plot -------------------------------------------------------

peaks = {"2": (60e6, 14), "6": (32e6, 22), "11": (100e6, 9), "16": (50e6, 10.5)}
chrom, pos, pvalues, ids = [], [], [], []
for number in [*range(1, 23), "X"]:
    c = str(number)
    length = 155e6 if c == "X" else 250e6 * (1 - 0.035 * (int(c) - 1))
    for _ in range(int(length / 2e6)):
        x = rng.uniform(0, length)
        y = rng.expovariate(1.0)
        if c in peaks and abs(x - peaks[c][0]) < 3e6:
            y = max(y, peaks[c][1] * math.exp(-((x - peaks[c][0]) / 1e6) ** 2))
        chrom.append("chr" + c)
        pos.append(x)
        pvalues.append(10 ** -y)
        ids.append(f"rs{rng.randint(1000, 999999)}")
    if c in peaks:
        for _ in range(30):
            x = peaks[c][0] + rng.gauss(0, 0.6e6)
            y = peaks[c][1] * math.exp(-((x - peaks[c][0]) / 1e6) ** 2) + rng.uniform(0, 1)
            chrom.append("chr" + c)
            pos.append(x)
            pvalues.append(10 ** -y)
            ids.append(f"rs{rng.randint(1000, 999999)}")
gwas = inklet.manhattan(chrom, pos, pvalues, labels=ids, top=4, width=160, height=34)

# -- j: MA plot --------------------------------------------------------------

mean = [2 ** rng.uniform(0, 15) for _ in range(800)]
fold = [rng.gauss(0, 0.5) + (rng.random() < 0.05) * rng.choice([-1, 1]) * rng.uniform(1, 4)
        for _ in range(800)]
padj = [min(1.0, 2 * math.exp(-abs(f) * 4 * rng.uniform(0.2, 1.5))) for f in fold]
ma = inklet.panel(36, 34, x=(0, 16), y=(-6, 6))
ma.ma(mean, fold, padj, labels=[f"Gene{k}" for k in range(800)], top=4,
      names=["down", None, "up"])
ma.axes(x="log_{2} mean expression", y="log_{2} fold change").legend(side="bottom")

# -- k: ternary plot ---------------------------------------------------------

upland = [(rng.uniform(5, 30), rng.uniform(40, 80), rng.uniform(10, 30)) for _ in range(30)]
valley = [(rng.uniform(30, 60), rng.uniform(5, 25), rng.uniform(25, 50)) for _ in range(30)]
soil = inklet.panel(34, 30)
soil.ternary(upland, labels=("clay", "sand", "silt"), name="upland")
soil.ternary(valley, name="valley").legend(side="bottom")

fig = inklet.figure(width=180, theme="nature")
rows = [inklet.row(inklet.letters([tree, rings, icicle]), gap=8, align="top"),
        inklet.row(inklet.letters([net, chords, corr], start="d"), gap=6, align="top"),
        inklet.row(inklet.letters([arcs, adj], start="g"), gap=8, align="top"),
        inklet.row(inklet.letters([heat, ma, soil], start="i"), gap=6, align="top"),
        inklet.row(inklet.letters([gwas.build()], start="l"), align="top")]
fig.add(inklet.column(rows, gap=8))
fig.save("examples/network_hierarchy_plot_types.svg")
fig.save("examples/network_hierarchy_plot_types.pdf")
with open("examples/network_hierarchy_plot_types.png", "wb") as out:
    out.write(fig.to_png(dpi=300))
print(inklet.format_report(fig.lint()))
