"""Yengo et al. (2022), Nature 610:704-712, Figure 2: the Brisbane plot.

Genomic density of the 12,111 genome-wide significant, quasi-independent height
SNPs along the genome, chromosome by chromosome. Each SNP is a column of squares
from 0 up to its signal density (the number of other independent SNPs within
100 kb). SNPs whose signal is contributed by African, East Asian or Hispanic
ancestry groups are marked at the top of their column. The gene labels of the
original are not in the source data and are omitted. Data: Nature Source Data
(see SOURCE.md).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

GOLD, BLACK, RED = "#DAA520", "#000000", "#FF0000"
AFR, EAS, HIS = "#1E90FF", "#EE82EE", "#43CD80"

# Chromosome lengths (GRCh37, Mb), used only to space the chromosomes along the
# x axis as in the original. Not part of the source data.
LENGTH_MB = [249.25, 243.20, 198.02, 191.15, 180.92, 171.12, 159.14, 146.36,
             141.21, 135.53, 135.01, 133.85, 115.17, 107.35, 102.53, 90.35,
             81.20, 78.08, 59.13, 63.03, 48.13, 51.30]
OFFSET = np.concatenate([[0.0], np.cumsum(LENGTH_MB)[:-1]])
TOTAL = float(np.sum(LENGTH_MB))
MEAN, MEDIAN = 2, 1
MEAN_SE, MEDIAN_SE = "0.14", "0"
MEAN_LABEL = f"Mean genome-wide density: {MEAN} (LOCO-S.E. = {MEAN_SE})"
MEDIAN_LABEL = f"Median genome-wide density: {MEDIAN} (LOCO-S.E. = {MEDIAN_SE})"

# -- data ---------------------------------------------------------------------
sig = pd.read_csv(HERE / "data" / "fig2_source.csv")
sig.columns = ["chr", "pos", "dens", "afr", "eas", "his"]
sig["x"] = OFFSET[sig.chr.to_numpy() - 1] + sig.pos.to_numpy() / 1e6
flag = ((sig.afr + sig.eas + sig.his) > 0).to_numpy()


def squares(rows):
    """Squares 0..density for each SNP. A flagged SNP's top square is left out:
    its ancestry marker stands there (the source does not give that height)."""
    pts = []
    for x, d, f in zip(rows.x, rows.dens, flag[rows.index]):
        top = int(d) - 1 if f else int(d)
        pts.extend((x, k) for k in range(top + 1))
    return pts


odd = sig[sig.chr % 2 == 1]
even = sig[sig.chr % 2 == 0]
flagged = sig[flag]

# -- figure -------------------------------------------------------------------
doc = i.preset("scientific.nature", format="double-column").document()
p = i.plot_spec(170, 46, x=(0, TOTAL), y=(-0.6, 32), clip=True)

p.scatter(squares(odd), marker="square", size=0.8, color=GOLD, stroke="none", raster=True)
p.scatter(squares(even), marker="square", size=0.8, color=BLACK, stroke="none", raster=True)

# The ancestry marker of each flagged SNP stands on its column's top square.
for code, color, shape, label in [("afr", AFR, "square", "African ancestries"),
                                  ("eas", EAS, "circle", "East Asian ancestries"),
                                  ("his", HIS, "triangle",
                                   "Hispanic ethnicities or ancestries")]:
    sub = flagged[flagged[code] == 1]
    p.scatter(list(zip(sub.x, sub.dens)), marker=shape, size=1.0, color=color,
              stroke="none", name=label)

p.line([(0, MEAN), (TOTAL, MEAN)], stroke=RED, stroke_width=0.35, name=MEAN_LABEL)
p.line([(0, MEDIAN), (TOTAL, MEDIAN)], stroke=RED, stroke_width=0.35,
       stroke_dash=(1.0, 0.6), name=MEDIAN_LABEL)

centres = list(OFFSET + np.array(LENGTH_MB) / 2)
names_at = {round(c, 6): str(n + 1) for n, c in enumerate(centres)}
p.axes(x="Chromosome", y="Density of GWS\nSNPs within 100 kb",
       x_options=dict(ticks=centres, format=lambda v: names_at[round(v, 6)], stroke="#000000", stroke_width=0.21,
                      rotate=90, thin=False),
       y_options=dict(ticks=list(range(0, 31, 2)), thin=False, stroke="#000000", stroke_width=0.21))
p.legend(corner="nw", names=[MEAN_LABEL, MEDIAN_LABEL])

# Ancestry key, under the mean and median key at the top left. The original puts it
# top right, but the ACAN column (density 24) rises under its text there.
KEY_X = 60
p.text(KEY_X, 24.0, "Associations contributed by", anchor="w", size=i.pt(7))
for row, (color, shape, label) in enumerate([(AFR, "square", "African ancestries"),
                                             (EAS, "circle", "East Asian ancestries"),
                                             (HIS, "triangle",
                                              "Hispanic ethnicities or ancestries")]):
    y = 21.5 - 2.0 * row
    p.scatter([(KEY_X + 2, y)], marker=shape, size=1.0, color=color, stroke="none")
    p.text(KEY_X + 32, y, label, anchor="w", size=i.pt(7))

doc.add("fig2", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "yengo_height_2022_fig2.svg", OUT / "yengo_height_2022_fig2.pdf")
figure.save(OUT / "yengo_height_2022_fig2.png", dpi=200)
print(figure.report())
