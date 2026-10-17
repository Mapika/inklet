"""WASP-39b transmission spectrum with model fits and remove-one-gas variants.

JWST Transiting Exoplanet Community Early Release Science Team (Ahrer et al.),
"Identification of carbon dioxide in an exoplanet atmosphere", Nature 614,
649-652 (2023), Figure 3 (top panel). The FIREFLy reduction (points with 1-sigma
error bars), the ScCHIMERA best fit (all opacity sources) and the six
remove-one-gas spectra. Data are the Zenodo 10.5281/zenodo.6809899 bundle (see
SOURCE.md). The bottom panel (molecular absorption cross-sections) is not in
the bundle and is left out.
"""
from pathlib import Path

import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

# Colours sampled from the legend swatches of the published figure.
NAVY, RED, BLACK, ORANGE = "#000080", "#ff0000", "#000000", "#ffa500"
LIGHT_BLUE, GREY, BLUE = "#add8e6", "#808080", "#0000ff"
DATA_DOT, DATA_BAR = "#4d4d4d", "#8c8c8c"

PCT = 100.0   # the published axis is transit depth in per cent; files are absolute

# -- data -----------------------------------------------------------------------
firefly = pd.read_csv(HERE / "data" / "fig3_firefly_data.csv")
best = pd.read_csv(HERE / "data" / "fig3_best_fit.csv")
ablation = pd.read_csv(HERE / "data" / "fig3_remove_one_gas.csv")

points = list(zip(firefly.wavelength_um, firefly.transit_depth * PCT))
sigma = (firefly.transit_depth_1sigma * PCT).tolist()

# The "no X" series, drawn beneath the data, in the original's legend order.
REMOVED = [  # (key name, column, colour)
    ("No H_{2}O", "no_H2O", NAVY),
    ("No CO", "no_CO", RED),
    ("No CO_{2}", "no_CO2", BLACK),
    ("No H_{2}S", "no_H2S", ORANGE),
    ("No CH_{4}", "no_CH4", LIGHT_BLUE),
    ("No cloud", "no_cloud", GREY),
]
ALL = "All opacity"
KEY_ORDER = [name for name, _, _ in REMOVED[:4]] + [
    "No CH_{4}", "No cloud", ALL, "Data"]   # column-major, as published

# -- panel ----------------------------------------------------------------------
# Single column (89 mm), boxed with inward ticks as the original is. The original
# top panel is 862 x 318.5 px of an 1052 px wide image, so at 89 mm its plot box
# is 72.9 x 26.9 mm; x and y limits are read from its frame and tick marks.
doc = i.preset("scientific.nature", format="single-column", axes="box").document()
p = i.plot_spec(72.9, 26.9, x=(2.89, 5.67), y=(2.057, 2.311), clip=True)

for name, column, colour in REMOVED:
    p.line(list(zip(ablation.wavelength_um, ablation[column] * PCT)),
           stroke=colour, stroke_width=0.25, name=name)
inside = best.wavelength_um.between(firefly.wavelength_um.min(), firefly.wavelength_um.max())
p.line(list(zip(best.wavelength_um[inside], best.transit_depth[inside] * PCT)),
       stroke=BLUE, stroke_width=0.25, name=ALL)
p.errorbars(points, yerr=sigma, stroke=DATA_BAR, stroke_width=0.25, cap=0)
p.scatter(points, size=1.3, color=DATA_DOT, name="Data")

p.axes(x="Wavelength (µm)", y="Transit depth (%)",
       x_options=dict(ticks=[3.0, 3.5, 4.0, 4.5, 5.0, 5.5], format="{:.1f}"),
       y_options=dict(ticks=[2.10, 2.15, 2.20, 2.25, 2.30], format="{:.2f}"))
p.legend(side="top", names=KEY_ORDER, order="column", columns=2)

doc.add("fig3", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "jwst_wasp39b_2023_fig3.svg", OUT / "jwst_wasp39b_2023_fig3.pdf")
figure.save(OUT / "jwst_wasp39b_2023_fig3.png", dpi=200)
print(figure.report())
