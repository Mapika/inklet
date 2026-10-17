"""Shared loading code for the KATRIN 2022 figures (Figs 3 and 4).

Both inputs are the Nature Source Data text files, copied unchanged into
data/ (see SOURCE.md). Nothing here adds a data point: the highest-density
contours and the marginal histograms are derived from the Fig 3 histogram.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIG3 = HERE / "data" / "41567_2021_1463_MOESM7_ESM.txt"
FIG4 = HERE / "data" / "41567_2021_1463_MOESM8_ESM.txt"

# Probability enclosed by the 1 sigma and 2 sigma contours of a 2D Gaussian.
MASSES = (0.683, 0.954)


def load_histogram():
    """Fig 3 as a grid: (m2 bin centres, E0 bin centres, grid[row=E0][col=m2]).

    The file has six header lines and a units row before the 42 x 42 bins.
    """
    raw = np.genfromtxt(FIG3, delimiter="\t", skip_header=7)
    x, y, z = raw.T
    xs, ys = np.unique(x), np.unique(y)
    grid = np.zeros((ys.size, xs.size))
    grid[np.searchsorted(ys, y), np.searchsorted(xs, x)] = z
    return xs, ys, grid


def hdr_levels(grid, masses=MASSES):
    """Highest-density levels: sort the bins by count, and take the count at
    which the running total first reaches each share of all entries."""
    flat = np.sort(grid, axis=None)[::-1]
    running = np.cumsum(flat) / flat.sum()
    return {m: float(flat[np.searchsorted(running, m)]) for m in masses}


def hdr_contours(xs, ys, grid, level):
    """Closed rings bounding the bins with count >= level, in data units.

    Marching squares on the bin centres. The helper is private to inklet
    (`inklet.plot.outlines._contours`); there is no public contour of a grid.
    """
    from inklet.plot.outlines import _contours

    dx, dy = xs[1] - xs[0], ys[1] - ys[0]
    ny, nx = grid.shape
    field = [[float(grid[j, i] - level) for i in range(nx)] for j in range(ny)]
    for i in range(nx):                      # border below the level, so rings close
        field[0][i] = field[ny - 1][i] = -level
    for row in field:
        row[0] = row[nx - 1] = -level
    return [[(xs[0] + a * dx, ys[0] + b * dy) for a, b in ring]
            for ring in _contours(field) if len(ring) >= 3]


def load_experiments():
    """Fig 4 rows, oldest first: (label, best fit, lower bound, upper bound).

    The file's uncertainty columns are signed offsets from the best fit, so
    the bar runs from best + neg to best + pos.
    """
    df = pd.read_csv(FIG4, sep="\t", skiprows=5)
    df = df[pd.to_numeric(df["mnu2"], errors="coerce").notna()]
    rows = []
    for _, r in df.iloc[::-1].iterrows():
        best = float(r["mnu2"])
        rows.append((_label(r["experiment"]), best,
                     best - abs(float(r["uncertainty neg"])),
                     best + abs(float(r["uncertainty pos"]))))
    return rows


def _label(name):
    """'Mainz (05)' -> 'Mainz (2005)'; 'KATRIN (comb.)' -> 'KATRIN (combined)'."""
    m = re.match(r"(.*) \((\d\d)\)$", name)
    if m:
        yy = int(m.group(2))
        return f"{m.group(1)} ({1900 + yy if yy >= 90 else 2000 + yy})"
    return name.replace("comb.", "combined")
