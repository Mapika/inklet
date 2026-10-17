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


# The series names are the key's rows. Every regional panel draws the same
# names, so the key can be built from any one of them.
REGION = "Region, monthly P-score"
BAND = "95% uncertainty interval"
GLOBAL = "Global (repeated in every panel)"
ZERO = "0% line"


def draw_series(p, source):
    """Every mark in a regional panel. The names are the key's rows."""
    p.hline(0, stroke=INK, stroke_width=0.3, name=ZERO)
    if source != "Global":
        t, mean, low, high = series("Global")
        p.band(t, low, high, color=GREY, fill_opacity=0.18, name=GLOBAL)
        p.line(np.c_[t, mean], stroke=GREY, stroke_width=0.3, name=GLOBAL)
    t, mean, low, high = series(source)
    p.band(t, low, high, color=BLUE, fill_opacity=0.35, name=BAND)
    p.line(np.c_[t, mean], stroke=BLUE, stroke_width=0.55, name=REGION)
    return p


# -- one panel per region -----------------------------------------------------
def panel(source, title):
    p = draw_series(i.plot_spec(36, 52, x=XLIM, y=YLIM, clip=True), source)
    p.title(title)
    # The y name is set once for the grid (doc.label below).
    p.axes(x=None, y=None,
           x_options=dict(ticks=XTICKS, minor=2, format=year_label),
           y_options=dict(ticks=YTICKS))
    return p


def sea_peak(p):
    """Label the South-East Asian peak, the value that sets the shared scale's top."""
    t, mean, low, high = series("South-East Asian Region")
    k = int(np.argmax(mean))
    p.text(t[k], high[k] + 4, f"{mean[k]:.0f}%", anchor="s", size=i.pt(6))


doc = i.preset("scientific.nature", format="double-column").document(
    columns=4, gap=3, row_gap=4, share_plot_margins=True)
for source, title, row, column in PANELS:
    p = panel(source, title)
    if source == "South-East Asian Region":
        sea_peak(p)
    doc.add(f"r{row}c{column}", p, row=row, column=column)
# The empty eighth cell holds the key. key_diagram() reads the rows from a
# drawn panel that carries every named series (a regional panel, with its
# Global reference and 0% line), so the key matches the marks it explains.
key_source = draw_series(i.panel(36, 52, x=XLIM, y=YLIM), "European Region")
doc.add("key", key_source.key_diagram(names=[REGION, BAND, GLOBAL, ZERO]),
        row=1, column=3)
doc.label(y="P-score (%)")
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "who_excess_2023_fig2_improved.svg",
            OUT / "who_excess_2023_fig2_improved.pdf")
figure.save(OUT / "who_excess_2023_fig2_improved.png", dpi=200)
print(figure.report())
