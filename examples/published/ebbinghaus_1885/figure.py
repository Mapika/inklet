"""Ebbinghaus's forgetting curve: savings against time since learning, 1885.

Recreates the savings curve from H. Ebbinghaus, "Über das Gedächtnis" (1885),
and its English translation "Memory" (1913): the seven savings values at 20
min to 31 days, each with its probable error of the mean (P.E.m), on the
logarithmic time axis of the Murre & Dros (2015) replication. Data: the
summary table of the 1913 translation, see SOURCE.md.
"""
from pathlib import Path

import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

INK = "#1f2329"

# -- data ---------------------------------------------------------------------
savings = pd.read_csv(HERE / "data" / "ebbinghaus_savings.csv")
days = savings.hours_after_learning / 24.0             # the table gives hours
points = list(zip(days, savings.savings_pct))

# -- figure -------------------------------------------------------------------
doc = i.preset("scientific.modern", format="single-column").document()
p = i.plot_spec(89, 62, x=i.log((0.01, 100)), y=(0, 70))
p.line(points, stroke=INK, stroke_width=0.35, name="Savings")
p.errorbars(points, yerr=savings.pem_pct.tolist(), stroke=INK, stroke_width=0.3,
            cap=0.6)
p.scatter(points, color=INK, marker="diamond", size=1.6, stroke="none",
          name="Ebbinghaus (1885)")
p.axes(x="Time since learning / days", y="Savings (%)",
       x_options=dict(ticks=[0.01, 0.1, 1, 10, 100], format=lambda v: f"{v:g}"),
       y_options=dict(ticks=list(range(0, 71, 10))))
p.label_points(points, list(savings.interval_label), size=i.pt(7))

doc.add("ebbinghaus", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "ebbinghaus_1885.svg", OUT / "ebbinghaus_1885.pdf")
figure.save(OUT / "ebbinghaus_1885.png", dpi=200)
print(figure.report())
