"""John Snow (1855), "On the Mode of Communication of Cholera", 2nd ed., map of
cholera deaths around the Broad Street pump, 1854 (Map 1 of the book).

Deaths (one mark per death), the water pumps and the street network, in Snow's
own map coordinates. Equal scale: one data unit is 8 mm on both axes. See
SOURCE.md for the data and NOTES.md for what matches the original.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

INK, STREET, PUMP = "#1f2329", "#6b7079", "#c1121f"
MM_PER_UNIT = 8.0       # one unit of map coordinate is the same length on x and y
XLIM = YLIM = (3.0, 20.0)

# -- data -------------------------------------------------------------------
deaths = pd.read_csv(HERE / "data" / "snow_deaths.csv")
pumps = pd.read_csv(HERE / "data" / "snow_pumps.csv")
streets = pd.read_csv(HERE / "data" / "snow_streets.csv")
broad = pumps[pumps.label == "Broad St"].iloc[0]

# -- figure -------------------------------------------------------------------
side = MM_PER_UNIT * (XLIM[1] - XLIM[0])
MARGIN = 4              # mm, page margin around the square map
PAGE = 144              # mm, the published page is square (NOTES.md)
doc = i.preset("scientific.modern").document(width=PAGE, margin=MARGIN)
# aspect='equal' keeps one unit the same length on x and y at any page width: a
# narrower page shrinks the map to the largest square it holds, never stretches it.
p = i.plot_spec(side, side, x=XLIM, y=YLIM, clip=True, aspect="equal")

for k, (_, seg) in enumerate(streets.groupby("street", sort=False)):
    p.line(seg[["x", "y"]].to_numpy(), stroke=STREET, stroke_width=0.15,
           name="Street" if k == 0 else None)

p.scatter(deaths[["x", "y"]].to_numpy(), marker="square", size=0.9, color=INK,
          name="Cholera death")
p.scatter(pumps[["x", "y"]].to_numpy(), marker="circle", size=2.6, color=PUMP,
          hollow=True, stroke=PUMP, stroke_width=0.45, name="Water pump")
# The label sits in the one clear patch near the pump, up and to the left, with a
# leader to the ring. Positions are worked out in millimetres (the map's own
# scale) and converted back to data units.
def to_data(X, Y):
    return XLIM[0] + (X - MARGIN) / MM_PER_UNIT, YLIM[1] - (Y - MARGIN) / MM_PER_UNIT


def to_mm(x, y):
    return MARGIN + (x - XLIM[0]) * MM_PER_UNIT, MARGIN + (YLIM[1] - y) * MM_PER_UNIT


pump_mm = np.array(to_mm(broad.x, broad.y))
label_left, label_mid = to_data(57.8, 57.7)
start = np.array([72.6, 57.7])                     # just right of the label's text
direction = (start - pump_mm) / np.linalg.norm(start - pump_mm)
end = pump_mm + 1.8 * direction                    # stop at the ring's edge
p.text(label_left, label_mid, "Broad St pump", anchor="w")
p.line([to_data(*start), to_data(*end)], stroke=INK, stroke_width=0.15)
p.outline(stroke=INK, stroke_width=0.45)
p.legend(corner="nw", names=["Cholera death", "Water pump", "Street"])

doc.add("snow", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "snow_cholera_1854.svg", OUT / "snow_cholera_1854.pdf")
figure.save(OUT / "snow_cholera_1854.png", dpi=200)
print(figure.report())
