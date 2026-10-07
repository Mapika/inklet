"""Gutenberg-Richter law: cumulative earthquake counts against magnitude.

log10 N(>=M) = a - bM, with N the mean number of earthquakes per year at or
above magnitude M. Data: global USGS earthquake catalogue, M >= 4.5, 2016-2025
(earthquake-type events only), see SOURCE.md. The line is a least-squares fit
to log10 N over the linear range 5.0 <= M <= 7.5. Points below 5.0 bend away
(steeper than b = 1) and points above 7.5 are few, so they are drawn but not fitted.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

BLUE, GREY, RED = "#1f4fb4", "#9aa3ad", "#c8102e"
YEARS = 10.0                       # 2016-01-01 to 2025-12-31
FIT_LOW, FIT_HIGH = 5.0, 7.5

# -- data ---------------------------------------------------------------------
quakes = pd.read_csv(HERE / "data" / "usgs_m4.5_2016_2025.csv")
mag = quakes["mag"].to_numpy(float)

# Cumulative counts on the 0.1 magnitude grid used by the catalogue.
grid = np.round(np.arange(4.5, 8.85, 0.1), 1)
per_year = np.array([np.sum(mag >= m - 1e-9) for m in grid]) / YEARS
keep = per_year > 0
grid, per_year = grid[keep], per_year[keep]

fit = (grid >= FIT_LOW - 1e-9) & (grid <= FIT_HIGH + 1e-9)
slope, intercept = np.polyfit(grid[fit], np.log10(per_year[fit]), 1)
a, b = intercept, -slope
resid = np.log10(per_year[fit]) - (a - b * grid[fit])
s2 = np.sum(resid**2) / (fit.sum() - 2)
b_err = np.sqrt(s2 / np.sum((grid[fit] - grid[fit].mean())**2))
r2 = 1 - np.sum(resid**2) / np.sum((np.log10(per_year[fit]) - np.log10(per_year[fit]).mean())**2)

# -- figure -------------------------------------------------------------------
inside = pd.DataFrame({"mag": grid[fit], "rate": per_year[fit]})
outside = pd.DataFrame({"mag": grid[~fit], "rate": per_year[~fit]})
line_m = np.linspace(FIT_LOW, FIT_HIGH, 50)
line = pd.DataFrame({"mag": line_m, "rate": 10 ** (a - b * line_m)})

chart = i.scatter(inside, x="mag", y="rate", color=BLUE, name=f"Fitted, {FIT_LOW} ≤ M ≤ {FIT_HIGH}",
                  yscale="log", xlim=(4.4, 8.9), width="single", height=66, legend="ne")
chart.scatter(outside, x="mag", y="rate", color=GREY, name="Not fitted")
chart.line(line, x="mag", y="rate", color=RED, linewidth=0.3, name="Least-squares fit")
chart.labels(x="Magnitude, M", y="Number of earthquakes per year, N(≥M)",
             title="Gutenberg–Richter law, global earthquakes 2016–2025")
chart.annotate(5.7, 0.45, f"log_{{10}} N = {a:.2f} − {b:.2f} M,  //b// = {b:.2f} ± {b_err:.2f}")

if __name__ == "__main__":
    print(f"fit M {FIT_LOW}-{FIT_HIGH}: a = {a:.3f}, b = {b:.3f} +/- {b_err:.3f}, R^2 = {r2:.4f}")
    OUT.mkdir(parents=True, exist_ok=True)
    figure = chart.save(OUT / "gutenberg_richter.png", OUT / "gutenberg_richter.svg",
                        OUT / "gutenberg_richter.pdf", dpi=200)
    print(figure.report())
