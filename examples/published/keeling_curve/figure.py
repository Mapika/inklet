"""The Keeling curve: monthly mean CO2 at Mauna Loa Observatory, 1958-2026.

Recreates the NOAA GML / Scripps "Atmospheric CO2 at Mauna Loa Observatory"
figure (monthly means with the seasonal cycle, plus the deseasonalized trend)
with the average seasonal cycle as an inset. Data: NOAA GML co2_mm_mlo.txt,
see SOURCE.md.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

RED, INK = "#c8102e", "#1f2329"
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

# -- data ---------------------------------------------------------------------
cols = ["year", "month", "decimal", "average", "deseasonalized", "ndays", "sdev", "unc"]
co2 = pd.read_csv(HERE / "data" / "co2_mm_mlo.txt", comment="#", sep=r"\s+", names=cols)

# Average seasonal cycle: monthly mean minus the deseasonalized value, averaged
# per calendar month. Months NOAA filled by interpolation (negative #days from
# May 1974 on, when NOAA data begin) are left out; the Scripps months before
# that carry no #days and are all kept.
measured = co2[(co2.ndays >= 0) | (co2.decimal < 1974.33)]
cycle = (measured.average - measured.deseasonalized).groupby(measured.month).mean()
first, last = co2.iloc[0], co2.iloc[-1]

# -- main panel ---------------------------------------------------------------
doc = i.preset("scientific.modern", format="single-column").document()
p = i.plot_spec(89, 60, x=(1955, 2030), y=(305, 440))
p.line(co2[["decimal", "average"]].to_numpy(), stroke=RED, stroke_width=0.3,
       name="Monthly mean")
p.line(co2[["decimal", "deseasonalized"]].to_numpy(), stroke=INK, stroke_width=0.35,
       name="Seasonally adjusted")
p.axes(x="Year", y="CO_{2} mole fraction (ppm)",
       x_options=dict(ticks=list(range(1960, 2031, 10)), minor=2))
p.legend(corner="se")
p.text(2029, 333, "Scripps Institution of Oceanography\nNOAA Global Monitoring Laboratory",
       anchor="se", size=i.pt(6), color="#5b6470")
p.title(f"Atmospheric CO_{{2}} at Mauna Loa Observatory, {first.year:.0f}–{last.year:.0f}")

# -- inset: average seasonal cycle -----------------------------------------
months = np.arange(1, 13)
wrap = np.r_[cycle.iloc[-1], cycle.to_numpy(), cycle.iloc[0]]
inset = i.plot_spec(25, 16, x=(0.5, 12.5), y=(-3.6, 3.6), clip=True)
inset.hline(0, stroke="#9aa3ad", stroke_width=0.15)
inset.line(list(zip(np.r_[0, months, 13], wrap)), smooth=0.5, stroke=RED, stroke_width=0.35)
inset.scatter(list(zip(months, cycle)), color=RED, size=0.8, stroke="none")
inset.axes(x=None, y="Departure (ppm)",
           x_options=dict(ticks=[1, 4, 7, 10],
                          format=lambda m: MONTHS[int(m) - 1]),
           y_options=dict(ticks=[-3, 0, 3]))
inset.title("Average seasonal cycle")
p.inset(inset, corner="nw", width=None, pad=2)

doc.add("co2", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "keeling_curve.svg", OUT / "keeling_curve.pdf")
figure.save(OUT / "keeling_curve.png", dpi=200)
print(figure.report())
