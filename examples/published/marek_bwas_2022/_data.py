"""Shared loading for Marek et al. (2022) Fig. 1, read only from data/.

Every loader returns plain numpy arrays or pandas frames exactly as stored in
data/ (see SOURCE.md for how each file was made from the Source Data workbook).
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# Sample sizes of the 16 resample bins (columns of the e/f sheets), ascending.
# The last bin is the full-sample size of each phenotype pair: 3,604 for
# thickness and 3,928 for RSFC (see SOURCE.md).
BINS = [25, 33, 50, 70, 100, 135, 200, 265, 375, 525, 725, 1000, 1430, 2000, 2800]
BINS_THICKNESS = BINS + [3604]
BINS_RSFC = BINS + [3928]


def effects(name):
    """Effect sizes (signed r) as a frame; blank cells are NaN. name: 'a' or 'b'."""
    file = {"a": "fig1a_thickness_r.csv.gz", "b": "fig1b_rsfc_r.csv.gz"}[name]
    return pd.read_csv(DATA / file)


def resamples(name):
    """1,000 resamples x 16 sample-size bins. name: e/f + '_cognition' or '_psychopathology'."""
    file = {
        "e_cognition": "fig1e_thickness_cognition.csv",
        "e_psychopathology": "fig1e_thickness_psychopathology.csv",
        "f_cognition": "fig1f_rsfc_cognition.csv",
        "f_psychopathology": "fig1f_rsfc_psychopathology.csv",
    }[name]
    frame = pd.read_csv(DATA / file)
    frame.columns = [c.replace("n=", "") for c in frame.columns]
    return frame


def scatter(name):
    """DMN-vs-phenotype scatter: two n = 25 subsamples and the full sample.

    name: 'g_cognition', 'g_psychopathology' or 'h_cognition'.
    Returns (frame, meta) where meta maps each subsample to its columns and
    the sign of its legend r, so the dark/light colour choice is explicit.
    """
    file = {"g_cognition": "fig1g_thickness_cognition.csv",
            "g_psychopathology": "fig1g_thickness_psychopathology.csv",
            "h_cognition": "fig1h_rsfc_cognition.csv"}[name]
    frame = pd.read_csv(DATA / file)
    tag = frame.columns[1].split("_")[0]          # 'Cog' or 'Psy'
    meta = {
        "dark": (frame.columns[2], frame.columns[3]),   # DMN_25_2/Cog_25_2 for g; _1 for h
        "light": (frame.columns[0], frame.columns[1]),
        "full": ("DMN_fullsamp", f"{tag}_fullsamp"),
    }
    if name.startswith("h"):
        meta = {"dark": (frame.columns[0], frame.columns[1]),
                "light": (frame.columns[2], frame.columns[3]),
                "full": ("DMN_fullsamp", f"{tag}_fullsamp")}
    return frame, meta


def subsample(frame, xcol, ycol):
    """The rows that hold a value in both columns (25 for a subsample)."""
    sub = frame[[xcol, ycol]].dropna()
    return sub[xcol].to_numpy(float), sub[ycol].to_numpy(float)


def fit_line(x, y):
    """Least-squares slope and intercept, plus Pearson r."""
    slope, intercept = np.polyfit(x, y, 1)
    return slope, intercept, float(np.corrcoef(x, y)[0, 1])
