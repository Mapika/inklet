"""WHO excess mortality, Msemburi et al. (2023), Nature 613, 130-137, Figure 2.

Monthly P-scores (excess deaths relative to expected deaths, in per cent),
January 2020 to December 2021, globally and for the six WHO regions, with 95%
uncertainty intervals. Data are the Nature Source Data workbook for Figure 2
(see SOURCE.md).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

# Panel order, titles and colours as in the original (ggplot's default hue
# palette for seven groups).
PANELS = [  # (source region name, panel title, colour, grid row, grid column)
    ("Global", "Global", "#F8766D", 0, 0),
    ("African Region", "African region", "#C49A00", 0, 1),
    ("Region of the Americas", "Region of the Americas", "#53B400", 0, 2),
    ("Eastern Mediterranean Region", "Eastern Mediterranean region", "#00C094", 0, 3),
    ("European Region", "European region", "#00B6EB", 1, 0),
    ("South-East Asian Region", "South-East Asian region", "#A58AFF", 1, 1),
    ("Western Pacific Region", "Western Pacific region", "#FB61D7", 1, 2),
]
XLIM = (2019.917, 2022.0)
XTICKS = [2020.0, 2020.75, 2021.5]
YLIM, YTICKS = (-44, 158), [0, 50, 100, 150]
INK = "#1a1a1a"                  # the journal's black, as the axes

# -- data ---------------------------------------------------------------------
data = pd.read_csv(HERE / "data" / "fig2-pscore.csv")
data["t"] = data.year + (data.month - 1) / 12          # Jan 2020 = 2020.0


def series(region):
    g = data[data.region == region].sort_values("t")
    return g.t.to_numpy(), 100 * g.pscore_mean.to_numpy(), \
        100 * g.pscore_low.to_numpy(), 100 * g.pscore_high.to_numpy()


def month_label(value):
    names = {2020.0: "January", 2020.75: "October", 2021.5: "July"}
    year = int(np.floor(value + 1e-9))
    return f"{names[round(value, 2)]}\n{year}"


# -- one panel per region -----------------------------------------------------
def panel(source, title, color, row, column):
    p = i.plot_spec(36, 50, x=XLIM, y=YLIM, clip=True)
    t, mean, low, high = series(source)
    p.hline(0, stroke=INK, stroke_width=0.25, stroke_dash=(1.0, 0.8))
    p.band(t, low, high, color=color, name=title)
    p.line(np.c_[t, mean], stroke=color, stroke_width=0.35, name=title)
    p.title(title)
    # The axis names belong once for the grid (doc.label below), so the cells
    # keep only their ticks.
    p.axes(x=None, y=None,
           x_options=dict(ticks=XTICKS, format=month_label),
           y_options=dict(ticks=YTICKS))
    return p


doc = i.preset("scientific.nature", format="double-column").document(
    columns=4, gap=3, row_gap=4, share_plot_margins=True)
for source, title, color, row, column in PANELS:
    doc.add(f"r{row}c{column}", panel(source, title, color, row, column),
            row=row, column=column)
doc.label(x="Month Year", y="P-score (%)")

figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "who_excess_2023_fig2.svg", OUT / "who_excess_2023_fig2.pdf")
figure.save(OUT / "who_excess_2023_fig2.png", dpi=200)
print(figure.report())
