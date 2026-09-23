"""Volcano plots: fold change against significance, with thresholds.

`volcano_points` does the arithmetic and draws nothing: it turns fold
changes and p-values into points `(log2 fold change, -log10 p)`, sorts each
point into "up", "down" or "ns" by the two thresholds, and ranks the
significant points for labelling. `Panel.volcano` draws the result with
`scatter`, `hline`, `vline` and `label_points`.

A p-value of 0 has no finite -log10. It is drawn at the smallest positive
p-value in the data (or at 1e-300 if there is none) and listed under
`capped`. Points whose fold change or p-value is missing (None or NaN) are
skipped and listed under `skipped`.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import DiagramError

__all__ = ["volcano_points", "VOLCANO_CLASSES"]

#: The classes a point can fall into, in drawing order.
VOLCANO_CLASSES = ("ns", "down", "up")

_FLOOR = 1e-300


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def volcano_points(fold: Sequence[float], p: Sequence[float], *,
                   fold_threshold: float = 1.0,
                   p_threshold: float = 0.05) -> dict:
    """Classify volcano points without drawing them.

    `fold` are log2 fold changes and `p` the p-values (or adjusted
    p-values), one per feature. A point is "up" when its p-value is below
    `p_threshold` and its fold change is at least `fold_threshold`, "down"
    when the fold change is at most `-fold_threshold`, and "ns" otherwise.

    Returns a dict with `points` (one `(fold, -log10 p)` pair per input, or
    None for a skipped input), `classes` (one of `VOLCANO_CLASSES` per input,
    or None), `ranked` (indices of the significant points, smallest p first,
    ties broken by the larger absolute fold change), `capped` (indices whose
    p-value was 0) and `skipped` (indices with a missing value).
    """
    fold, p = list(fold), list(p)
    if len(fold) != len(p):
        raise DiagramError(
            f"volcano needs one p-value per fold change, got {len(fold)} and {len(p)}")
    if fold_threshold < 0:
        raise DiagramError(
            f"volcano fold_threshold must be 0 or more, got {fold_threshold!r}")
    if not 0 < p_threshold <= 1:
        raise DiagramError(
            f"volcano p_threshold must be in (0, 1], got {p_threshold!r}")
    positive = [float(v) for v in p if not _missing(v) and float(v) > 0]
    floor = min(positive) if positive else _FLOOR
    points: list = []
    classes: list = []
    capped: list[int] = []
    skipped: list[int] = []
    for index, (f, q) in enumerate(zip(fold, p)):
        if _missing(f) or _missing(q):
            points.append(None)
            classes.append(None)
            skipped.append(index)
            continue
        f, q = float(f), float(q)
        if q < 0 or q > 1:
            raise DiagramError(f"volcano p-value {q!r} at index {index} is not in [0, 1]")
        if q == 0:
            capped.append(index)
            q = floor
        points.append((f, -math.log10(q)))
        if q < p_threshold and f >= fold_threshold and f > 0:
            classes.append("up")
        elif q < p_threshold and f <= -fold_threshold and f < 0:
            classes.append("down")
        else:
            classes.append("ns")
    ranked = sorted((i for i, c in enumerate(classes) if c in ("up", "down")),
                    key=lambda i: (-points[i][1], -abs(points[i][0]), i))
    return {"points": points, "classes": classes, "ranked": ranked,
            "capped": capped, "skipped": skipped}
