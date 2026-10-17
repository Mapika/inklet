"""Shared loading code for the KATRIN 2022 figures (Figs 3 and 4).

Both inputs are the Nature Source Data text files, copied unchanged into
data/ (see SOURCE.md). Nothing here adds a data point: the contours are drawn
from the Fig 3 histogram by Panel.contour(hdr=), and the marginals are sums of
its grid.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIG3 = HERE / "data" / "41567_2021_1463_MOESM7_ESM.txt"
FIG4 = HERE / "data" / "41567_2021_1463_MOESM8_ESM.txt"


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


def bin_edges(centres):
    """Edges of equal-width bins whose centres are `centres`: one more edge than centre."""
    centres = np.asarray(centres, dtype=float)
    step = centres[1] - centres[0]
    return np.append(centres - step / 2, centres[-1] + step / 2)


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
