"""Anscombe's quartet (Anscombe 1973, The American Statistician 27:17-21, Figs 1-4).

Four data sets with the same regression summary -- n = 11, mean x 9.0,
mean y 7.5, fitted line y = 3 + 0.5x, R^2 = 0.667 -- drawn as the paper drew
them: each scatter with that common line, on identical axes (x 0-20, y 0-13).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

data = pd.read_csv(HERE / "data" / "anscombe.csv")

charts = []
for k in range(1, 5):
    x, y = data[f"x{k}"].to_numpy(float), data[f"y{k}"].to_numpy(float)
    b1, b0 = np.polyfit(x, y, 1)            # every set: b0 = 3.00, b1 = 0.500
    # The fitted line first, so the points sit on top of it (set 4's x = 19).
    chart = i.line(x=[0, 20], y=[b0, b0 + 20 * b1], color="#c1121f",
                   xlim=(0, 20), ylim=(0, 13), title=f"Data set {k}", height=62)
    chart.scatter(x=x, y=y, color="#222222", size=1.4)
    # The paper's furniture: numbers every 5, a small tick at every unit.
    chart.axes(x="//x//", y="//y//",
               x_options={"ticks": [0, 5, 10, 15, 20], "minor": 5},
               y_options={"ticks": [0, 5, 10], "minor": 5})
    charts.append(chart)

# The paper captions them Figures 1-4; panel titles carry the data-set number.
layout = i.Layout("grid", charts, columns=2, width="double", letters=False)
OUT.mkdir(parents=True, exist_ok=True)
figure = layout.save(OUT / "anscombe_1973.png", OUT / "anscombe_1973.svg",
                     OUT / "anscombe_1973.pdf", dpi=200)
print(figure.report())
