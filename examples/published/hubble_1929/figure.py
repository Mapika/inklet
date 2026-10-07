"""Hubble (1929), PNAS 15:168, Figure 1: velocity-distance relation.

Radial velocities corrected for solar motion against distance for the 24
nebulae of Table 1 (black discs, full line: the solution for the nebulae
individually), the 9 group means (circles, broken line: the solution for the
groups) and the mean of the 22 nebulae of Table 2 (cross). See SOURCE.md.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

INK, GROUP, CROSS = "#1f2329", "#8a5a00", "#c1121f"

# -- data -------------------------------------------------------------------
table = pd.read_csv(HERE / "data" / "table1.csv")
coords = pd.read_csv(HERE / "data" / "coordinates.csv")
groups = pd.read_csv(HERE / "data" / "group_means.csv")
neb = table.merge(coords, on="object")

# Hubble's two least-squares solutions of  rK + X cos a cos d + Y sin a cos d
# + Z sin d = v  (paper, p. 170), in km/s and km/s per 10^6 parsecs.
INDIVIDUAL = dict(K=465, X=-65, Y=226, Z=-195)   # 24 nebulae
GROUPED = dict(K=513, X=3, Y=230, Z=-133)        # 9 groups


def to_b1900(ra, dec):
    """Precess J2000 coordinates (degrees) to B1900 (IAU 1976, T = -1)."""
    T, arcsec = -1.0, np.pi / 180 / 3600
    zeta = (2306.2181 * T + 0.30188 * T**2 + 0.017998 * T**3) * arcsec
    z = (2306.2181 * T + 1.09468 * T**2 + 0.018203 * T**3) * arcsec
    th = (2004.3109 * T - 0.42665 * T**2 - 0.041833 * T**3) * arcsec
    a, d = np.radians(ra) + zeta, np.radians(dec)
    A = np.cos(d) * np.sin(a)
    B = np.cos(th) * np.cos(d) * np.cos(a) - np.sin(th) * np.sin(d)
    C = np.sin(th) * np.cos(d) * np.cos(a) + np.cos(th) * np.sin(d)
    return np.arctan2(A, B) + z, np.arcsin(C)


# "The solar motion has been eliminated from the observed velocities":
# v_corrected = v - (X cos a cos d + Y sin a cos d + Z sin d).
a, d = to_b1900(neb.ra_j2000_deg.to_numpy(), neb.dec_j2000_deg.to_numpy())
s = INDIVIDUAL
solar = s["X"] * np.cos(a) * np.cos(d) + s["Y"] * np.sin(a) * np.cos(d) + s["Z"] * np.sin(d)
neb["v_corr"] = neb.v_kms - solar

# -- figure -------------------------------------------------------------------
doc = i.preset("scientific.modern", format="single-column").document()
p = i.plot_spec(89, 62, x=(-1 / 3, 7 / 3), y=(-1000 / 3, 4000 / 3))
p.grid(x_options=dict(ticks=[0, 1, 2]), y_options=dict(ticks=[0, 500, 1000]))
p.line([(0, 0), (2.22, 2.22 * INDIVIDUAL["K"])], stroke=INK, stroke_width=0.3,
       name="Fit to nebulae, //K// = 465")
p.line([(0, 0), (2.14, 2.14 * GROUPED["K"])], stroke=GROUP, stroke_width=0.3,
       dash="dashed", name="Fit to groups, //K// = 513")
p.scatter(groups[["r_mpc", "v_kms"]].to_numpy(), size=1.7, color=GROUP, hollow=True,
          stroke_width=0.3, name="Group means")
p.scatter(neb[["r_mpc", "v_corr"]].to_numpy(), size=1.3, color=INK,
          name="Nebulae (Table 1)")
# stroke= as well as color=: a "plus" marker ignores color= (ISSUES-physics.md, 5).
p.scatter([(1.4, 745)], marker="plus", size=2.6, color=CROSS, stroke=CROSS,
          stroke_width=0.3, name="Mean, 22 nebulae (Table 2)")
p.axes(x="Distance (10^{6} parsecs)", y="Velocity (km s^{-1})",
       x_options=dict(ticks=[0, 1, 2]), y_options=dict(ticks=[0, 500, 1000]))
p.legend(corner="se", names=["Nebulae (Table 1)", "Fit to nebulae, //K// = 465",
                             "Group means", "Fit to groups, //K// = 513",
                             "Mean, 22 nebulae (Table 2)"])

doc.add("hubble", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "hubble_1929.svg", OUT / "hubble_1929.pdf")
figure.save(OUT / "hubble_1929.png", dpi=200)
print(figure.report())
