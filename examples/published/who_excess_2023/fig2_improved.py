"""WHO excess mortality, Msemburi et al. (2023), Nature 613, 130-137, Figure 2.

Improved redesign of Figure 2: monthly P-scores globally and for the six WHO
regions, with 95% uncertainty intervals. One colour carries the regional
series, the Global series is a faint grey reference in every panel, the 0%
line is solid, all seven panels share one y scale, and the uncertainty bands
are visible. See NOTES.md for the changes and the scale choice.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

BLUE = "#0072B2"                 # Okabe-Ito blue: the region, in every panel
BAND = "#9fcbe6"                 # the blue band as it looks over paper (0.35 tint)
GREY = "#8c949c"                 # the Global reference
INK = "#333333"
XLIM = (2019.917, 2022.0)
XTICKS = [2020.0, 2021.0, 2022.0]
YLIM, YTICKS = (-40, 160), [0, 50, 100, 150]

# (source region, panel title, grid row, grid column), in the original's order
PANELS = [
    ("Global", "Global", 0, 0),
    ("African Region", "African region", 0, 1),
    ("Region of the Americas", "Region of the Americas", 0, 2),
    ("Eastern Mediterranean Region", "Eastern Mediterranean region", 0, 3),
    ("European Region", "European region", 1, 0),
    ("South-East Asian Region", "South-East Asian region", 1, 1),
    ("Western Pacific Region", "Western Pacific region", 1, 2),
]

# -- data ---------------------------------------------------------------------
data = pd.read_csv(HERE / "data" / "fig2-pscore.csv")
data["t"] = data.year + (data.month - 1) / 12          # Jan 2020 = 2020.0


def series(region):
    g = data[data.region == region].sort_values("t")
    return (g.t.to_numpy(), 100 * g.pscore_mean.to_numpy(),
            100 * g.pscore_low.to_numpy(), 100 * g.pscore_high.to_numpy())


def year_label(value):
    return f"{int(round(value))}"


# -- one panel per region -----------------------------------------------------
def panel(source, title, column):
    p = i.plot_spec(36, 52, x=XLIM, y=YLIM, clip=True)
    p.hline(0, stroke=INK, stroke_width=0.3)
    if source != "Global":
        t, mean, low, high = series("Global")
        p.band(t, low, high, color=GREY, fill_opacity=0.18, name="Global")
        p.line(np.c_[t, mean], stroke=GREY, stroke_width=0.3, name="Global")
    t, mean, low, high = series(source)
    p.band(t, low, high, color=BLUE, fill_opacity=0.35, name=title)
    p.line(np.c_[t, mean], stroke=BLUE, stroke_width=0.55, name=title)
    p.title(title)
    p.axes(x=None, y="P-score (%)" if column == 0 else None,
           x_options=dict(ticks=XTICKS, minor=2, format=year_label),
           y_options=dict(ticks=YTICKS))
    return p


def sea_peak(p):
    """Label the South-East Asian peak, the value that sets the shared scale's top."""
    t, mean, low, high = series("South-East Asian Region")
    k = int(np.argmax(mean))
    p.text(t[k], high[k] + 4, f"{mean[k]:.0f}%", anchor="s", size=i.pt(6))


def key_cell():
    """The key, in the one empty cell: each swatch is drawn as it appears in the
    panels (a line, a band, the grey Global line, the 0% line), with its name
    set beside it. Nothing here is a legend object, so nothing is matched to a
    drawing elsewhere."""
    p = i.plot_spec(36, 52, x=(0, 1), y=(0, 1))
    swatch = (0.0, 0.14)            # the sample runs from 0 to 0.14 of the cell
    rows = [(0.84, "Region, monthly P-score"),
            (0.62, "95% uncertainty interval"),
            (0.38, "Global (repeated\nin every panel)"),
            (0.14, "0% line")]
    p.line([(swatch[0], 0.84), (swatch[1], 0.84)], stroke=BLUE, stroke_width=0.55)
    p.band([swatch[0], swatch[1]], [0.60, 0.60], [0.64, 0.64], color=BLUE,
           fill_opacity=0.35)
    p.line([(swatch[0], 0.38), (swatch[1], 0.38)], stroke=GREY, stroke_width=0.3)
    p.line([(swatch[0], 0.14), (swatch[1], 0.14)], stroke=INK, stroke_width=0.3)
    for at, name in rows:
        p.text(0.19, at, name, anchor="w", size=i.pt(6), markup=False, align="start")
    return p


doc = i.preset("scientific.nature", format="double-column",
               expected_fonts=("Arial", "Helvetica", "Liberation Sans")).document(
    columns=4, gap=3, row_gap=4, share_plot_margins=True)
for source, title, row, column in PANELS:
    p = panel(source, title, column)
    if source == "South-East Asian Region":
        sea_peak(p)
    doc.add(f"r{row}c{column}", p, row=row, column=column)
doc.add("key", key_cell(), row=1, column=3)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "who_excess_2023_fig2_improved.svg",
            OUT / "who_excess_2023_fig2_improved.pdf")
figure.save(OUT / "who_excess_2023_fig2_improved.png", dpi=200)
print(figure.report())
