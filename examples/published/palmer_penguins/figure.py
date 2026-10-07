"""Palmer penguins: bill dimensions and flipper length of three Pygoscelis species.

Recreates the widely reproduced palmerpenguins figures (Horst, Hill & Gorman
2020) of the Gorman, Williams & Fraser (2014) Palmer Station LTER data:
(a) bill length against bill depth by species, with a least-squares line per
species and the pooled line that reverses sign (Simpson's paradox), and
(b) flipper length distributions by species. See SOURCE.md.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

SPECIES = ["Adelie", "Chinstrap", "Gentoo"]
# The palmerpenguins colours (ggplot2 darkorange, purple, cyan4).
COLOR = dict(Adelie="#ff8c00", Chinstrap="#a020f0", Gentoo="#008b8b")
MARKER = dict(Adelie="circle", Chinstrap="triangle", Gentoo="square")

penguins = pd.read_csv(HERE / "data" / "penguins.csv")   # 'NA' -> NaN
bills = penguins.dropna(subset=["bill_length_mm", "bill_depth_mm"])
flippers = penguins.dropna(subset=["flipper_length_mm"])

doc = i.preset("scientific.modern", format="double-column").document(columns=2)

# -- a: bill length vs bill depth ---------------------------------------------
a = i.plot_spec(80, 62, x=(30, 62), y=(12.5, 22), clip=True)
pooled = bills[["bill_length_mm", "bill_depth_mm"]].to_numpy()
a.regression(pooled, scatter=False, confidence=None, color="#6b7280",
             dash="dashed", stroke_width=0.45, name="All species")
for s in SPECIES:
    pts = bills.loc[bills.species == s, ["bill_length_mm", "bill_depth_mm"]].to_numpy()
    a.scatter(pts, color=COLOR[s], marker=MARKER[s], size=1.2, opacity=0.7,
              stroke="none", name=s)
    a.regression(pts, scatter=False, confidence=0.95, color=COLOR[s],
                 stroke_width=0.45)
a.axes(x="Bill length (mm)", y="Bill depth (mm)")
a.legend(corner="sw")

# -- b: flipper length distributions ------------------------------------------
edges = np.arange(172, 234, 2.0)
b = i.plot_spec(80, 62, x=(170, 234), y=(0, 30))
b.hist({s: flippers.loc[flippers.species == s, "flipper_length_mm"].to_numpy()
        for s in SPECIES}, bins=edges, color=[COLOR[s] for s in SPECIES])
b.axes(x="Flipper length (mm)", y="Frequency")
b.legend(corner="ne")

doc.add("a", a)
doc.add("b", b, column=1, row=0)
doc.letters()
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "palmer_penguins.svg", OUT / "palmer_penguins.pdf")
figure.save(OUT / "palmer_penguins.png", dpi=200)
print(figure.report())
