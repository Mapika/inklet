"""WASP-39b transmission spectrum and remove-one-gas tests, redesigned.

Same data and message as Figure 3 (top panel) of Ahrer et al., Nature 614,
649-652 (2023): the FIREFLy reduction with 1-sigma error bars, the ScCHIMERA
best fit, and the effect of each opacity source. The published top panel draws
seven near-identical curves on one axis. Here the observed spectrum and best
fit get their own panel, and each source gets a strip below on the same
wavelength axis, so the size of each contribution can be read directly.

Strip values are the best fit minus the best fit with that source removed,
in ppm of transit depth. The best fit is interpolated onto the 95 data
wavelengths, where the remove-one-gas models are binned (see SOURCE.md).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

# Okabe-Ito colour-blind-safe hues; each source keeps one colour in every strip.
CO2, H2O, CLOUD = "#d55e00", "#0072b2", "#7a7a7a"
CO, H2S, CH4 = "#009e73", "#e69f00", "#56b4e9"
# Darker shades of the same hues for text on white (WCAG 4.5:1).
CO2_TXT, CO_TXT, H2S_TXT, CH4_TXT, CLOUD_TXT = "#a94400", "#00704f", "#8a5a00", "#1b6f9c", "#5c5c5c"
DATA, FIT, RULE = "#3a3a3a", "#000000", "#9a9a9a"

PCT = 100.0
XLIM, XTICKS = (2.9, 5.6), [3.0, 3.5, 4.0, 4.5, 5.0, 5.5]

# -- data -----------------------------------------------------------------------
firefly = pd.read_csv(HERE / "data" / "fig3_firefly_data.csv")
best = pd.read_csv(HERE / "data" / "fig3_best_fit.csv")
ablation = pd.read_csv(HERE / "data" / "fig3_remove_one_gas.csv")

wl = firefly.wavelength_um.to_numpy()
depth = firefly.transit_depth.to_numpy() * PCT
sigma = firefly.transit_depth_1sigma.to_numpy() * PCT
fit_on_data = np.interp(wl, best.wavelength_um, best.transit_depth)   # absolute
fit_curve = best[best.wavelength_um.between(wl.min(), wl.max())]

# Strips, largest contribution first: (label, column, colour).
SOURCES = [  # (label, column, line colour, text colour)
    ("CO_{2}", "no_CO2", CO2, CO2_TXT),
    ("H_{2}O", "no_H2O", H2O, H2O),
    ("Clouds", "no_cloud", CLOUD, CLOUD_TXT),
    ("CO", "no_CO", CO, CO_TXT),
    ("H_{2}S", "no_H2S", H2S, H2S_TXT),
    ("CH_{4}", "no_CH4", CH4, CH4_TXT),
]
RANGE_PPM = (-60.0, 1300.0)   # one scale for every strip, so sizes compare

def effect_ppm(column):
    """Depth added by a source: best fit minus the fit with that source removed."""
    removed = ablation[column].to_numpy()          # absolute, binned to the data
    return (fit_on_data - removed) * 1e6

# -- top panel: the observation and the best fit --------------------------------
doc = i.preset("scientific.nature", format="double-column").document(
    columns=1, row_gap=3, share_plot_margins=True)

top = i.plot_spec(148, 46, x=XLIM, y=(2.06, 2.31), clip=True)
top.line(list(zip(fit_curve.wavelength_um, fit_curve.transit_depth * PCT)),
         stroke=FIT, stroke_width=0.3, name="Best fit")
top.errorbars(list(zip(wl, depth)), yerr=sigma.tolist(), stroke=DATA,
              stroke_width=0.2, cap=0)
top.scatter(list(zip(wl, depth)), size=1.3, color=DATA, hollow=True,
            stroke_width=0.2, name="Data")
top.axes(x=None, y="Transit depth (%)",
         x_options=dict(ticks=XTICKS, labels=False),
         y_options=dict(ticks=[2.10, 2.15, 2.20, 2.25, 2.30], format="{:.2f}"))
top.text(2.93, 2.305, "Best fit: 10× solar metallicity, C/O = 0.35, χ²/N = 1.3",
         anchor="nw", color=FIT)
top.text(5.55, 2.31, "Observed, ±1σ", anchor="ne", color=DATA)
top.text(5.55, 2.28, "Best fit, all sources", anchor="ne", color=FIT)
top.text(4.62, 2.245, "CO_{2} band, 4.3 µm", anchor="w", color=CO2_TXT)
top.text(3.02, 2.205, "H_{2}O: depth rises blueward of 3.6 µm", anchor="sw", color=H2O)
top.annotate(4.10, 2.088, "unmodelled feature, ~4 µm", side="s", text_fill=DATA)
doc.add("observed", top, row=0)

# -- strips: one source each, shared wavelength axis -----------------------------
last = len(SOURCES)            # row number of the bottom strip
for row, (label, column, colour, text) in enumerate(SOURCES, start=1):
    delta = effect_ppm(column)
    peak = int(np.argmax(delta))
    strip = i.plot_spec(148, 8.5, x=XLIM, y=RANGE_PPM, clip=True)
    strip.hline(0, stroke=RULE, stroke_width=0.2)
    strip.band(wl.tolist(), [0.0] * len(wl), delta.tolist(), color=colour, name=label)
    strip.line(list(zip(wl, delta)), stroke=colour, stroke_width=0.3, name=label)
    if row == 1:
        strip.title("Depth added by each source: best fit minus the fit without it")
    strip.axes(x=None, y="ppm" if row == 1 else None,
               x_options=dict(ticks=XTICKS, labels=row == last,
                              label="Wavelength (µm)" if row == last else None),
               y_options=dict(ticks=[0, 1000], format="{:,.0f}"))
    strip.text(5.55, RANGE_PPM[1] - 30,
               f"{label}: peak {delta[peak]:,.0f} ppm at {wl[peak]:.2f} µm",
               anchor="ne", color=text)
    doc.add(f"strip-{column}", strip, row=row)

figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "jwst_wasp39b_2023_fig3_improved.svg",
            OUT / "jwst_wasp39b_2023_fig3_improved.pdf")
figure.save(OUT / "jwst_wasp39b_2023_fig3_improved.png", dpi=200)
print(figure.report())
