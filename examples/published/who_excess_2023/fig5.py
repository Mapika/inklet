"""WHO excess mortality, Msemburi et al. (2023), Nature 613, 130-137, Figure 5.

The 25 countries with the highest mean P-scores for 2020 and 2021 (excess
deaths relative to expected deaths, in per cent), among WHO member states with
populations above 200,000. Grey dots are the means and the bars the 95%
uncertainty intervals. Data are the Nature Source Data workbook for Figure 5
(see SOURCE.md).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

DOT, INK = "#bdbdbd", "#000000"
XLIM, XTICKS = (13, 104), [25, 50, 75, 100]

# The figure's rows, top to bottom. The workbook's 25 rows differ: Andorra, San
# Marino and Saint Vincent and the Grenadines are in the workbook but not the
# figure, and Kuwait, Lebanon and the Republic of Moldova are in the figure but
# not the workbook (see NOTES.md). Only the 22 rows both sources share are drawn.
FIGURE_ROWS = [
    "Peru", "Ecuador", "Bolivia (Plurinational State of)", "Mexico", "Armenia",
    "Oman", "Azerbaijan", "Colombia", "Russian Federation", "North Macedonia",
    "Turkey", "Iran (Islamic Republic of)", "Kazakhstan", "Paraguay", "Indonesia",
    "Montenegro", "Bulgaria", "India", "Guatemala", "Brazil", "Serbia", "Georgia",
]

# -- data ---------------------------------------------------------------------
c = pd.read_csv(HERE / "data" / "fig5-top25.csv")
c = c.set_index("Country").loc[FIGURE_ROWS].reset_index()
c[["pscore_mean", "pscore_low", "pscore_high"]] *= 100          # per cent
n = len(c)
ypos = np.arange(n)[::-1].astype(float)                         # rank 1 at the top
names = {round(y, 6): name for y, name in zip(ypos, c.Country)}

# -- the plot -----------------------------------------------------------------
p = i.plot_spec(98, 84, x=XLIM, y=(-0.6, n - 0.4), clip=True)
bars = [(m - lo, hi - m) for m, lo, hi in zip(c.pscore_mean, c.pscore_low, c.pscore_high)]
p.errorbars(np.c_[c.pscore_mean, ypos], xerr=bars, cap=1.2, stroke=INK,
            stroke_width=0.3)
p.scatter(np.c_[c.pscore_mean, ypos], size=1.8, color=DOT, stroke=INK,
          stroke_width=0.2)
p.axes(x="P-Score",
       x_options=dict(ticks=XTICKS, format="{:.0f}%"),
       y_options=dict(ticks=list(ypos), format=lambda v: names[round(v, 6)]))

doc = i.preset("scientific.nature", format="double-column").document(
    width=136)
doc.add("countries", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "who_excess_2023_fig5.svg", OUT / "who_excess_2023_fig5.pdf")
figure.save(OUT / "who_excess_2023_fig5.png", dpi=200)
print(figure.report())
