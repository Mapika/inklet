"""WHO excess mortality, Msemburi et al. (2023), Nature 613, 130-137, Figure 1.

Global cumulative excess and reported COVID-19 deaths (a) and the monthly
death rates per 100,000 population (b), January 2020 to December 2021, with
95% uncertainty intervals for the excess estimates. Data are the Nature Source
Data workbook for Figure 1 (see SOURCE.md).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

RED, PURPLE = "#e2231a", "#7c6fb8"
XLIM = (2019.9, 2022.0)
XTICKS = [2020.0, 2020.5, 2021.0, 2021.5, 2022.0]

# -- data ---------------------------------------------------------------------
a = pd.read_csv(HERE / "data" / "fig1-panelA-cumulative.csv")
b = pd.read_csv(HERE / "data" / "fig1-panelB-rate.csv")
ta = (a.year + (a.month - 1) / 12).to_numpy()     # Jan 2020 = 2020.0
tb = (b.year + (b.month - 1) / 12).to_numpy()


def month_label(value):
    year, half = int(np.floor(value + 1e-9)), value - np.floor(value + 1e-9)
    return f"January {year}" if half < 0.25 else f"July {year}"


def panel(ylim, yticks, ylabel):
    p = i.plot_spec(62, 34, x=XLIM, y=ylim, clip=True)
    p.axes(x="Month Year", y=ylabel,
           x_options=dict(ticks=XTICKS, format=month_label),
           y_options=dict(ticks=yticks))
    return p


# -- a: cumulative deaths, in millions ----------------------------------------
pa = panel((-1.3, 17.0), [0, 5, 10, 15], "Deaths (×10^{6})")
pa.band(ta, a["cumul.excess.low"].to_numpy() / 1e6,
        a["cumul.excess.high"].to_numpy() / 1e6, color=PURPLE,
        name="Cumulative excess deaths")
pa.line(np.c_[ta, a["cumul.excess.mean"] / 1e6], stroke=PURPLE, stroke_width=0.35,
        name="Cumulative excess deaths")
pa.line(np.c_[ta, a["cumul.rep.covid"] / 1e6], stroke=RED, stroke_width=0.35,
        name="Cumulative reported COVID-19 deaths")
pa.legend(side="bottom", names=["Cumulative reported COVID-19 deaths", "Cumulative excess deaths"])

# -- b: death rates per 100,000 population ------------------------------------
pb = panel((-5.9, 27.2), [0, 10, 20], "Death rate per 100,000 population")
pb.band(tb, b["excess.low"].to_numpy(), b["excess.high"].to_numpy(), color=PURPLE,
        name="Excess death rate per 100,000")
pb.line(np.c_[tb, b["excess.mean"]], stroke=PURPLE, stroke_width=0.35,
        name="Excess death rate per 100,000")
pb.line(np.c_[tb, b["rep.covid"]], stroke=RED, stroke_width=0.35,
        name="Reported COVID-19 death rate per 100,000")
pb.legend(side="bottom", names=["Reported COVID-19 death rate per 100,000", "Excess death rate per 100,000"])

doc = i.preset("scientific.nature", format="single-column",
               expected_fonts=("Arial", "Helvetica", "Liberation Sans")).document()
doc.add("a", pa)
doc.add("b", pb)
doc.letters()
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "who_excess_2023_fig1.svg", OUT / "who_excess_2023_fig1.pdf")
figure.save(OUT / "who_excess_2023_fig1.png", dpi=200)
print(figure.report())
