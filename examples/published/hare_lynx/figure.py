"""Snowshoe hare and Canada lynx: Hudson's Bay Company pelt returns, 1845-1935.

Recreates the classic predator-prey figure from Odum's "Fundamentals of
Ecology" (after MacLulich 1937 and Elton & Nicholson 1942): the annual number
of hare (solid) and lynx (dashed) pelts, in thousands, over 91 years. Data:
the Whitman College copy of the series (the same numbers as R package astsa's
Hare and Lynx), see SOURCE.md.
"""
from pathlib import Path

import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

# Okabe-Ito blue and vermillion: distinct in colour, and the lynx line is also
# dashed, so the two stay apart in greyscale.
HARE, LYNX = "#0072B2", "#D55E00"

# -- data ---------------------------------------------------------------------
pelts = pd.read_csv(HERE / "data" / "LynxHare.txt", sep=r"\s+", header=None,
                    names=["year", "hare", "lynx"])          # thousands of pelts

# -- figure -------------------------------------------------------------------
doc = i.preset("scientific.modern", format="single-column").document()
p = i.plot_spec(89, 62, x=(1845, 1935), y=(0, 160))
p.line(pelts[["year", "hare"]].to_numpy(), stroke=HARE, stroke_width=0.35,
       name="Hare")
p.line(pelts[["year", "lynx"]].to_numpy(), stroke=LYNX, stroke_width=0.35,
       dash="dashed", name="Lynx")
p.axes(x="Year", y="Pelts purchased (thousands)",
       x_options=dict(ticks=list(range(1845, 1936, 10))),
       y_options=dict(ticks=list(range(0, 161, 20))))
p.legend(corner="ne")

doc.add("hare_lynx", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "hare_lynx.svg", OUT / "hare_lynx.pdf")
figure.save(OUT / "hare_lynx.png", dpi=200)
print(figure.report())
