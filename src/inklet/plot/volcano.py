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

__all__ = ["volcano_points", "VOLCANO_CLASSES", "VOLCANO_KEY_ORDER"]

#: The classes a point can fall into, in drawing order.
VOLCANO_CLASSES = ("ns", "down", "up")

#: The order the classes are listed in a key: the significant ones first,
#: although "ns" is drawn first so that it lies beneath them.
VOLCANO_KEY_ORDER = ("up", "down", "ns")

_FLOOR = 1e-300


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def volcano_points(fold: Sequence[float], p: Sequence[float], *,
                   fold_threshold: float = 1.0,
                   p_threshold: float = 0.05,
                   q: Sequence[float] | None = None) -> dict:
    """Classify volcano points without drawing them.

    `fold` are log2 fold changes and `p` the p-values (or adjusted
    p-values), one per feature. A point is "up" when its p-value is below
    `p_threshold` and its fold change is at least `fold_threshold`, "down"
    when the fold change is at most `-fold_threshold`, and "ns" otherwise.

    `q=` classes by a second sequence -- the adjusted p-values -- while `p`
    still gives the height: the usual published volcano, raw p on the axis
    and colour by FDR. A missing q (None or NaN, as DESeq2 writes for a gene
    it filtered out) makes that point "ns", not skipped.

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
    if q is not None:
        q = list(q)
        if len(q) != len(p):
            raise DiagramError(
                f"volcano needs one q-value per p-value, got {len(q)} and {len(p)}")
    positive = [float(v) for v in p if not _missing(v) and float(v) > 0]
    floor = min(positive) if positive else _FLOOR
    points: list = []
    classes: list = []
    capped: list[int] = []
    skipped: list[int] = []
    for index, (f, pv) in enumerate(zip(fold, p)):
        if _missing(f) or _missing(pv):
            points.append(None)
            classes.append(None)
            skipped.append(index)
            continue
        f, pv = float(f), float(pv)
        if pv < 0 or pv > 1:
            raise DiagramError(f"volcano p-value {pv!r} at index {index} is not in [0, 1]")
        if pv == 0:
            capped.append(index)
            pv = floor
        points.append((f, -math.log10(pv)))
        if q is None:
            judged = pv
        elif _missing(q[index]):
            judged = math.inf               # untested: never significant
        else:
            judged = float(q[index])
            if judged < 0 or judged > 1:
                raise DiagramError(
                    f"volcano q-value {judged!r} at index {index} is not in [0, 1]")
        if judged < p_threshold and f >= fold_threshold and f > 0:
            classes.append("up")
        elif judged < p_threshold and f <= -fold_threshold and f < 0:
            classes.append("down")
        else:
            classes.append("ns")
    ranked = sorted((i for i, c in enumerate(classes) if c in ("up", "down")),
                    key=lambda i: (-points[i][1], -abs(points[i][0]), i))
    return {"points": points, "classes": classes, "ranked": ranked,
            "capped": capped, "skipped": skipped}


def significant_first(panel, start: int, kinds: Sequence[str]) -> None:
    """List the key records a volcano (or MA) plot just added in
    `VOLCANO_KEY_ORDER`, whatever order they were drawn in.

    `start` is how many records the panel held before the classes were
    drawn and `kinds` the class of each named scatter drawn since, in order.
    """
    added = panel._keys[start:]
    if len(added) != len(kinds):
        return
    ranked = sorted(zip(kinds, added), key=lambda pair: VOLCANO_KEY_ORDER.index(pair[0]))
    panel._keys[start:] = [record for _, record in ranked]
