"""How much of the plot height each series spans, for `SERIES_FLATTENED`.

A panel fits one y scale to every series drawn on it, so a series of values
near 0.5 beside one of values near 5000 is drawn as a line along the floor. The
picture is faithful and unreadable, and nothing in the geometry says so: a flat
line is a perfectly good line. Only the data knows that its changes are a few
tenths of a percent of the axis, so the panel keeps that fact and the linter
judges it.

Each `line` and `scatter` call adds one record: its series name, the lowest and
highest value it drew, the sum of the absolute values (for a mean), and the y
scale it was drawn through. A twin axis from `Panel.twin_y` draws through a
second scale, so its series are weighed only against the others on that scale.

`declare_series` runs at build time. It merges the records of one name on one
scale -- a series drawn as a line with markers is one series, however many
calls drew it -- and publishes each series' extent as a fraction of the plot
height on the panel node. The thresholds live in the rule, not here.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass
from typing import Iterable

from ..core import Diagram, Rect

__all__ = ["SERIES_SPAN_NOTE", "declare_series", "record_series"]

#: The note on a panel node: `{"series": (dict, ...)}`, one dict per series with
#: `name` (None when unnamed), `axis` (an index into the panel's y scales),
#: `span` (fraction of the plot height), `lo`, `hi` and `mean_abs`.
SERIES_SPAN_NOTE = "series_spans"


@dataclass(frozen=True)
class _Record:
    name: str | None
    lo: float
    hi: float
    total: float          # sum of absolute values
    count: int
    scale: object         # the y scale it was drawn through, by identity


def record_series(records: list, name: str | None, values: Iterable,
                  scale) -> None:
    """Remember the values one drawing call put on the y axis.

    Unnamed series are recorded too, because a large unnamed curve is still
    what squashes a named one beside it. They are never merged with each other:
    a gapped series is drawn as several unnamed runs, and joining them would
    be guessing.
    """
    lo = hi = None
    total, count = 0.0, 0
    for raw in values:
        if not isinstance(raw, numbers.Real):
            continue
        value = float(raw)
        if not math.isfinite(value):
            continue
        lo = value if lo is None else min(lo, value)
        hi = value if hi is None else max(hi, value)
        total += abs(value)
        count += 1
    if lo is None:
        return
    records.append(_Record(None if name is None else str(name), lo, hi,
                           total, count, scale))


def declare_series(node: Diagram, records: list, area: Rect) -> None:
    """Publish each series' extent on `node`, the panel's built group.

    Silent when nothing was recorded, so a panel with no series carries no note.
    """
    if not records:
        return
    scales: list = []
    merged: list[dict] = []
    named: dict[tuple, dict] = {}
    for record in records:
        axis = next((index for index, scale in enumerate(scales)
                     if scale is record.scale), None)
        if axis is None:
            scales.append(record.scale)
            axis = len(scales) - 1
        cell = named.get((record.name, axis)) if record.name is not None else None
        if cell is None:
            cell = {"name": record.name, "axis": axis, "lo": record.lo,
                    "hi": record.hi, "total": 0.0, "count": 0}
            merged.append(cell)
            if record.name is not None:
                named[(record.name, axis)] = cell
        cell["lo"] = min(cell["lo"], record.lo)
        cell["hi"] = max(cell["hi"], record.hi)
        cell["total"] += record.total
        cell["count"] += record.count

    out = []
    for cell in merged:
        span = _span_fraction(scales[cell["axis"]], cell["lo"], cell["hi"], area)
        if span is None:
            continue
        out.append({"name": cell["name"], "axis": cell["axis"], "span": span,
                    "lo": cell["lo"], "hi": cell["hi"],
                    "mean_abs": cell["total"] / cell["count"]})
    if out:
        node.note(SERIES_SPAN_NOTE, {"series": tuple(out)})


def _span_fraction(scale, lo: float, hi: float, area: Rect) -> float | None:
    """The part of the plot height `lo..hi` covers once drawn through `scale`.

    Clipped to the area, because that is what a reader sees. None when the
    scale cannot place the values (a log scale given zero, say).
    """
    bottom, top = min(area.y0, area.y1), max(area.y0, area.y1)
    height = top - bottom
    if not height > 0:
        return None
    try:
        a = float(scale.map(lo))
        b = float(scale.map(hi))
    except (ValueError, TypeError, ArithmeticError):
        return None
    if not (math.isfinite(a) and math.isfinite(b)):
        return None
    drawn = min(max(a, b), top) - max(min(a, b), bottom)
    return max(0.0, drawn) / height
