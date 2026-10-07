"""Hodgkin & Huxley (1952), J. Physiol. 117:500-544: membrane action potentials
calculated from their equations at 6.3 C, for four stimulus strengths.

Sub-threshold (6 and 12 uA/cm^2) and supra-threshold (14 and 25 uA/cm^2)
responses to a 0.5 ms current pulse. The traces are computed by simulate.py from
the paper's constants (SOURCE.md); this file only draws data/hh_1952_6p3C.csv.
The y axis is -V (mV), the paper's own axis: depolarisation is up.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

# -- data -------------------------------------------------------------------
data = pd.read_csv(HERE / "data" / "hh_1952_6p3C.csv")
t = data["time_ms"].to_numpy()

# (column, stimulus label, colour): sub-threshold blues, supra-threshold reds
TRACES = [
    ("minus_V_mV_6uA_cm2", "6", "#7aa6c2"),
    ("minus_V_mV_12uA_cm2", "12", "#2b6c96"),
    ("minus_V_mV_14uA_cm2", "14", "#e07a1f"),
    ("minus_V_mV_25uA_cm2", "25", "#b2182b"),
]
INK = "#1f2329"

# -- figure -------------------------------------------------------------------
doc = i.preset("scientific.modern", format="single-column").document()
p = i.plot_spec(80, 58, x=(0, 10), y=(-15, 125))
p.grid(x_options=dict(ticks=[0, 5, 10]), y_options=dict(ticks=[0, 50, 100]))
for column, label, color in TRACES:
    p.line(np.c_[t, data[column].to_numpy()], stroke=color, stroke_width=0.3, name=label)
# The traces meet near rest at the right edge, so a titled key names them
# rather than labels at the line ends.
p.legend(corner="ne", title="Stimulus (µA cm^{-2})")
p.axes(x="Time (ms)", y="−V (mV)",
       x_options=dict(ticks=[0, 5, 10]), y_options=dict(ticks=[0, 50, 100]))
doc.add("hh", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "hodgkin_huxley_1952.svg", OUT / "hodgkin_huxley_1952.pdf")
figure.save(OUT / "hodgkin_huxley_1952.png", dpi=200)
print(figure.report())
