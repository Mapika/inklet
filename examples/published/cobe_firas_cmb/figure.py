"""COBE/FIRAS monopole spectrum of the cosmic microwave background.

Intensity (MJy/sr) against frequency (cm^-1) for the FIRAS monopole, with the
2.725 K blackbody curve. The error bars are 400 times the 1-sigma uncertainty,
as in the published FIRAS plots, so the tiny errors are visible; the factor is
stated on the figure. Data: NASA LAMBDA firas_monopole_spec_v1.txt, see SOURCE.md.
"""
from pathlib import Path

import numpy as np

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

RED, BLUE, INK = "#c8102e", "#1f4fb4", "#1f2329"
ERROR_FACTOR = 400          # error bars drawn at 400 x 1 sigma
T_CMB = 2.725               # K, Fixsen et al. (1996) / Fixsen & Mather (2002)

# SI constants (CODATA 2018, exact or rounded to the digits used here)
H = 6.62607015e-34          # J s
C = 299792458.0             # m s^-1
K_B = 1.380649e-23          # J K^-1
MJY_SR = 1e-20              # W m^-2 Hz^-1 sr^-1 in one MJy/sr


def planck(wavenumber_cm):
    """Planck's law B_nu(T) in MJy/sr for wavenumbers in cm^-1."""
    nu = np.asarray(wavenumber_cm, dtype=float) * 100.0 * C      # cm^-1 -> Hz
    radiance = 2.0 * H * nu**3 / C**2 / np.expm1(H * nu / (K_B * T_CMB))
    return radiance / MJY_SR


# -- data ---------------------------------------------------------------------
# Columns: wavenumber (cm^-1), monopole (MJy/sr), residual (kJy/sr), 1-sigma (kJy/sr).
firas = np.loadtxt(HERE / "data" / "firas_monopole_spec_v1.txt", comments="#")
nu, spectrum = firas[:, 0], firas[:, 1]
sigma = firas[:, 3] / 1000.0 * ERROR_FACTOR                      # MJy/sr, x400

# The file's monopole is the blackbody plus the residual (column 3). The
# difference is under 0.01 MJy/sr, a smooth constant-precision effect (peak 384).
residual_check = spectrum - planck(nu) - firas[:, 2] / 1000.0
assert np.max(np.abs(residual_check)) < 0.02, "monopole != blackbody + residual"

curve_nu = np.linspace(2.0, 22.0, 600)
curve = planck(curve_nu)

# -- figure -------------------------------------------------------------------
doc = i.preset("scientific.modern", format="single-column").document()
p = i.plot_spec(89, 66, x=(2, 22), y=(0, 400))
p.line(np.c_[curve_nu, curve], stroke=BLUE, stroke_width=0.25,
       name=f"Black body, T = {T_CMB} K")
points = list(zip(nu, spectrum))
p.errorbars(points, yerr=sigma, cap=0.5, stroke=RED, stroke_width=0.25, clip=True)
p.scatter(points, marker="plus", size=1.6, color=RED, stroke=RED, stroke_width=0.25,
          name="COBE/FIRAS data")
p.axes(x="Frequency / cm^{-1}", y="Intensity / (MJy sr^{-1})",
       x_options=dict(ticks=list(range(2, 23, 2))),
       y_options=dict(ticks=list(range(0, 401, 50))))
p.legend(corner="ne")
p.title("Cosmic microwave background spectrum (COBE/FIRAS)")
p.text(2.4, 8, f"Error bars ×{ERROR_FACTOR}", anchor="sw", size=i.pt(6), color="#5b6470")
doc.add("firas", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "cobe_firas_cmb.svg", OUT / "cobe_firas_cmb.pdf")
figure.save(OUT / "cobe_firas_cmb.png", dpi=200)
print(figure.report())
