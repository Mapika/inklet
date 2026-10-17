"""Yengo et al. (2022), Nature 610:704-712, Figure 2: improved Brisbane plot.

Same data and message as fig2.py: the density of the 12,111 genome-wide
significant height SNPs along the genome, with the SNPs whose signal is
contributed by African, East Asian or Hispanic ancestry groups marked. Changes:
chromosomes separated by gaps and shaded in alternate bands (instead of
gold/black squares), one colour for the squares, colour-blind-safe Okabe-Ito
markers for the ancestry groups, one key for all five entries, and an even
y tick spacing. Data: Nature Source Data (see SOURCE.md).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

INK = "#2F4B7C"
BAND = "#EFEFEF"
MEAN_COLOUR, MEDIAN_COLOUR = "#B2182B", "#B2182B"
# Okabe-Ito markers, shape-distinct as well as colour-distinct.
AFR, EAS, HIS = "#D55E00", "#CC79A7", "#009E73"

# Chromosome lengths (GRCh37, Mb), used only to space the chromosomes along the
# x axis. Not part of the source data. A small gap separates neighbours.
LENGTH_MB = [249.25, 243.20, 198.02, 191.15, 180.92, 171.12, 159.14, 146.36,
             141.21, 135.53, 135.01, 133.85, 115.17, 107.35, 102.53, 90.35,
             81.20, 78.08, 59.13, 63.03, 48.13, 51.30]
GAP_MB = 12.0
OFFSET = np.concatenate([[0.0], np.cumsum(np.array(LENGTH_MB) + GAP_MB)[:-1]])
ENDS = OFFSET + np.array(LENGTH_MB)
TOTAL = float(ENDS[-1])
MEAN, MEDIAN = 2, 1
MEAN_LABEL = "Mean genome-wide density: 2 (LOCO-S.E. = 0.14)"
MEDIAN_LABEL = "Median genome-wide density: 1 (LOCO-S.E. = 0)"

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


flagged = sig[flag]

# -- figure -------------------------------------------------------------------
doc = i.preset("scientific.nature", format="double-column").document()
p = i.plot_spec(170, 56, x=(0, TOTAL), y=(0, 32))

for n in range(0, 22, 2):                      # every other chromosome shaded
    p.vspan(OFFSET[n] - GAP_MB / 2, ENDS[n] + GAP_MB / 2, fill=BAND)

p.scatter(squares(sig), marker="square", size=0.8, color=INK, stroke="none", raster=True)

for code, colour, shape, label in [("afr", AFR, "diamond", "African ancestries"),
                                   ("eas", EAS, "circle", "East Asian ancestries"),
                                   ("his", HIS, "triangle",
                                    "Hispanic ethnicities or ancestries")]:
    sub = flagged[flagged[code] == 1]
    p.scatter(list(zip(sub.x, sub.dens)), marker=shape, size=1.3, color=colour,
              stroke="#FFFFFF", stroke_width=0.12, name=label)

p.line([(0, MEAN), (TOTAL, MEAN)], stroke=MEAN_COLOUR, stroke_width=0.35, name=MEAN_LABEL)
p.line([(0, MEDIAN), (TOTAL, MEDIAN)], stroke=MEDIAN_COLOUR, stroke_width=0.35,
       stroke_dash=(1.0, 0.6), name=MEDIAN_LABEL)

centres = list(OFFSET + np.array(LENGTH_MB) / 2)
names_at = {round(c, 6): str(n + 1) for n, c in enumerate(centres)}
p.axes(x="Chromosome", y="Density of GWS SNPs within 100 kb",
       x_options=dict(ticks=centres, format=lambda v: names_at[round(v, 6)],
                      rotate=90, thin=False),
       y_options=dict(ticks=[0, 5, 10, 15, 20, 25, 30]))
p.legend(side="top", columns=3, names=[MEAN_LABEL, MEDIAN_LABEL, "African ancestries",
                             "East Asian ancestries",
                             "Hispanic ethnicities or ancestries"])

doc.add("fig2", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "yengo_height_2022_fig2_improved.svg",
            OUT / "yengo_height_2022_fig2_improved.pdf")
figure.save(OUT / "yengo_height_2022_fig2_improved.png", dpi=200)
print(figure.report())
