"""WHO excess mortality, Msemburi et al. (2023), Nature 613, 130-137, Figure 1.

Improved redesign of Figure 1: the same data and the same two panels (a,
cumulative deaths; b, death rates per 100,000), on one shared time axis, with
the series labelled at their ends instead of in a key, and with the 95%
uncertainty intervals kept. See NOTES.md for the changes and why.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

EXCESS, REPORTED = "#0072B2", "#D55E00"       # Okabe-Ito blue and vermilion
REPORTED_TEXT = "#a64200"                     # the vermilion, darkened for text
GUIDE = "#9aa3ad"
XLIM = (2019.9, 2022.0)                       # the data end at January 2022
XTICKS = [2020.0, 2021.0, 2022.0]

# -- data ---------------------------------------------------------------------
a = pd.read_csv(HERE / "data" / "fig1-panelA-cumulative.csv")
b = pd.read_csv(HERE / "data" / "fig1-panelB-rate.csv")
ta = (a.year + (a.month - 1) / 12).to_numpy()     # Jan 2020 = 2020.0
tb = (b.year + (b.month - 1) / 12).to_numpy()
last_a, last_b = a.iloc[-1], b.iloc[-1]           # December 2021


def year_label(value):
    return f"{int(round(value))}"


def panel(ylim, yticks, ylabel):
    p = i.plot_spec(52, 30, x=XLIM, y=ylim, clip=True)
    p.grid(x=True, y=False, x_options=dict(ticks=XTICKS))
    p.axes(x=None, y=ylabel,
           x_options=dict(ticks=XTICKS, minor=2, format=year_label),
           y_options=dict(ticks=yticks))
    return p


def end_label(p, x, y, text, color):
    """The series name and its December 2021 value, set beside the line end."""
    p.text(x, y, text, anchor="w", color=color, size=i.pt(6.5), markup=False,
           offset=(1.2, 0))


# -- a: cumulative deaths, in millions ----------------------------------------
pa = panel((-1.3, 17.0), [0, 5, 10, 15], "Deaths (millions)")
pa.band(ta, a["cumul.excess.low"].to_numpy() / 1e6,
        a["cumul.excess.high"].to_numpy() / 1e6, color=EXCESS, name="excess")
pa.line(np.c_[ta, a["cumul.excess.mean"] / 1e6], stroke=EXCESS, stroke_width=0.4,
        name="excess")
pa.line(np.c_[ta, a["cumul.rep.covid"] / 1e6], stroke=REPORTED, stroke_width=0.4,
        name="reported")
end_label(pa, 2022.0, last_a["cumul.excess.mean"] / 1e6,
          f"Excess {last_a['cumul.excess.mean'] / 1e6:.1f} M", EXCESS)
end_label(pa, 2022.0, last_a["cumul.rep.covid"] / 1e6,
          f"Reported {last_a['cumul.rep.covid'] / 1e6:.1f} M", REPORTED_TEXT)

# -- b: death rates per 100,000 population ------------------------------------
pb = panel((-6.0, 27.5), [0, 10, 20], "Death rate per 100,000")
pb.hline(0, stroke=GUIDE, stroke_width=0.2)
pb.band(tb, b["excess.low"].to_numpy(), b["excess.high"].to_numpy(), color=EXCESS,
        name="excess")
pb.line(np.c_[tb, b["excess.mean"]], stroke=EXCESS, stroke_width=0.4, name="excess")
pb.line(np.c_[tb, b["rep.covid"]], stroke=REPORTED, stroke_width=0.4,
        name="reported")
end_label(pb, 2022.0, last_b["excess.mean"],
          f"Excess {last_b['excess.mean']:.1f}", EXCESS)
end_label(pb, 2022.0, last_b["rep.covid"],
          f"Reported {last_b['rep.covid']:.1f}", REPORTED_TEXT)

doc = i.preset("scientific.nature", format="single-column").document(
    share_plot_margins=True, row_gap=5)
doc.add("a", pa)
doc.add("b", pb)
doc.letters()
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "who_excess_2023_fig1_improved.svg",
            OUT / "who_excess_2023_fig1_improved.pdf")
figure.save(OUT / "who_excess_2023_fig1_improved.png", dpi=200)
print(figure.report())
