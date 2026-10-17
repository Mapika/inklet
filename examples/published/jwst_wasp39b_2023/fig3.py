"""WASP-39b transmission spectrum with model fits and remove-one-gas variants.

JWST Transiting Exoplanet Community Early Release Science Team (Ahrer et al.),
"Identification of carbon dioxide in an exoplanet atmosphere", Nature 614,
649-652 (2023), Figure 3 (top panel). The FIREFLy reduction (points with 1-sigma
error bars), the ScCHIMERA best fit (all opacity sources) and the six
remove-one-gas spectra. Data are the Zenodo 10.5281/zenodo.6809899 bundle (see
SOURCE.md). The authors did not release the bottom panel's molecular
cross-sections; they are computed here from HITRAN by `cross_sections.py`
(see NOTES.md), so that panel is a derivation, not the published curves.
"""
from pathlib import Path

import numpy as np
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
cross = pd.read_csv(HERE / "data" / "fig3_cross_sections.csv")

points = list(zip(firefly.wavelength_um, firefly.transit_depth * PCT))
sigma = (firefly.transit_depth_1sigma * PCT).tolist()


def binned(model, centres, widths, fine=50):
    """The model averaged over each data bin, as the caption says the blue
    curve is ("binned to the resolution of the data"); the remove-one-gas
    spectra in the bundle are already binned this way."""
    out = []
    for centre, width in zip(centres, widths):
        grid = np.linspace(centre - width/2, centre + width/2, fine)
        out.append(np.interp(grid, model.wavelength_um, model.transit_depth).mean())
    return np.array(out)


best_binned = binned(best, firefly.wavelength_um, firefly.bin_width_um)

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
# Single column (89 mm). The original is closed by a plain black frame, with
# inward ticks on the bottom and left axes only (axes="frame"). The original
# top panel is 862 x 318.5 px of an 1052 px wide image, so at 89 mm its plot box
# is 72.9 x 26.9 mm; x and y limits are read from its frame and tick marks.
doc = i.preset("scientific.nature", format="single-column", axes="frame").document(
    columns=1, row_gap=0, share_plot_margins=True)
p = i.plot_spec(72.9, 26.9, x=(2.89, 5.67), y=(2.057, 2.311), clip=True)

for name, column, colour in REMOVED:
    p.line(list(zip(ablation.wavelength_um, ablation[column] * PCT)),
           stroke=colour, stroke_width=0.25, name=name)
p.line(list(zip(firefly.wavelength_um, best_binned * PCT)),
       stroke=BLUE, stroke_width=0.25, name=ALL)
# Points are about 0.9 mm across in the original at 89 mm (11 px of 1052).
p.errorbars(points, yerr=sigma, stroke=DATA_BAR, stroke_width=0.2, cap=0)
p.scatter(points, size=0.9, color=DATA_DOT, name="Data")

XTICKS = [3.0, 3.5, 4.0, 4.5, 5.0, 5.5]
p.axes(x=None, y="Transit depth (%)",
       x_options=dict(ticks=XTICKS, labels=False),
       y_options=dict(ticks=[2.10, 2.15, 2.20, 2.25, 2.30], format="{:.2f}"))
# At 7 pt the key reaches the CO2 peak; at 6 pt (within Nature's 5-7 pt) it
# ends near 4.1 um, as the original's does.
p.legend(corner="nw", names=KEY_ORDER, order="column", columns=2, row_gap=0.2, pad=0.6,
         font_size=i.pt(6))

doc.add("spectrum", p, row=0)

# -- bottom panel: cross-sections -------------------------------------------------
# The original's lower panel is 862 x 130 px, so 72.9 x 11 mm at 89 mm; it shares
# the wavelength axis and abuts the upper panel. The y range runs lower than the
# original's -26 because HITRAN, a 296 K list, lacks the hot lines that fill the
# windows between bands (CO2 falls to -28 there); it runs higher to leave the
# key clear of the CO2 peak.
GASES = [("H_{2}O", "H2O", NAVY), ("CO", "CO", RED), ("CO_{2}", "CO2", BLACK),
         ("CH_{4}", "CH4", LIGHT_BLUE), ("H_{2}S", "H2S", ORANGE)]
q = i.plot_spec(72.9, 16, x=(2.89, 5.67), y=(-29, -11), clip=True)
for name, column, colour in GASES:
    curve = cross[["wavelength_um", f"log10_sigma_{column}"]].dropna()
    q.line(curve.to_numpy().tolist(), stroke=colour, stroke_width=0.25, name=name)
q.axes(x="Wavelength (µm)", y="log_{10}//σ//\n(cm^{2} mol^{−1})",
       x_options=dict(ticks=XTICKS, format="{:.1f}"),
       y_options=dict(ticks=[-25, -20, -15]))
q.legend(corner="nw", columns=5, row_gap=0.2, pad=0.4, col_gap=1.5)
doc.add("cross", q, row=1)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "jwst_wasp39b_2023_fig3.svg", OUT / "jwst_wasp39b_2023_fig3.pdf")
figure.save(OUT / "jwst_wasp39b_2023_fig3.png", dpi=200)
print(figure.report())
