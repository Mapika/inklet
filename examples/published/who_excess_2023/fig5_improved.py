"""WHO excess mortality, Msemburi et al. (2023), Nature 613, 130-137, Figure 5.

Improved redesign of Figure 5: the mean P-score of each country with its 95%
uncertainty interval, ranked from highest to lowest. The scale starts at zero,
every 20% is labelled, each mean is written beside its dot, and one colour
carries the data. The rows are the 22 countries shared by the figure and the
source workbook (see NOTES.md). Data are the Nature Source Data workbook for
Figure 5 (see SOURCE.md).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

BLUE = "#0072B2"                 # Okabe-Ito blue, the one data colour
INK, GRID = "#222222", "#d9dde2"

# The 22 countries shared by the figure and the workbook, in the figure's order.
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
p = i.plot_spec(100, 100, x=(0, 110), y=(-0.6, n - 0.4), clip=True)
p.grid(x=True, y=False, x_options=dict(ticks=[0, 20, 40, 60, 80, 100]))
bars = [(m - lo, hi - m) for m, lo, hi in zip(c.pscore_mean, c.pscore_low, c.pscore_high)]
p.errorbars(np.c_[c.pscore_mean, ypos], xerr=bars, cap=1.2, stroke=BLUE,
            stroke_width=0.35)
p.scatter(np.c_[c.pscore_mean, ypos], size=1.7, color=BLUE, stroke="#ffffff",
          stroke_width=0.2)
for m, hi, y in zip(c.pscore_mean, c.pscore_high, ypos):
    p.text(hi, y, f"{m:.0f}%", anchor="w", offset=(1.6, 0), size=i.pt(6), color=INK)
p.axes(x="Mean P-score (%)",
       x_options=dict(ticks=[0, 20, 40, 60, 80, 100], minor=2, format="{:.0f}%"),
       y_options=dict(ticks=list(ypos), format=lambda v: names[round(v, 6)]))

doc = i.preset("scientific.nature", format="double-column",
               expected_fonts=("Arial", "Helvetica", "Liberation Sans")).document()
doc.add("countries", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "who_excess_2023_fig5_improved.svg",
            OUT / "who_excess_2023_fig5_improved.pdf")
figure.save(OUT / "who_excess_2023_fig5_improved.png", dpi=200)
print(figure.report())
