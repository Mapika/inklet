"""Split violins: two conditions per category as the two halves of one violin.

Each category's slot on the band scale holds one violin whose left half (or,
with `orient="h"`, upper half) is the first condition and whose right (lower)
half is the second. Each half is the kernel density `violin` draws, with the
same bandwidth rule, `samples` and `cut`, and the grid is kept inside the
value axis the same way.

`scale="shared"` (default) scales both halves of a category by the larger of
their two peaks, so the halves have equal areas and a wider half means more
density there; `scale="each"` gives each half its own peak width. The median
of each half is a solid line from the centre to the outline and, with
`quartiles=True`, the first and third quartiles are dashed lines.
"""

from __future__ import annotations

import math
from typing import Mapping

from ..core import Diagram, DiagramError
from ..draw.coords import active_theme
from ..draw.path import polygon, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND
from . import marks as _marks
from .statistics import _bandwidth, kde, quantile

__all__ = ["split_violin", "SPLIT_SCALES"]

#: Accepted values of `split_violin(scale=)`.
SPLIT_SCALES = ("shared", "each")

#: The dash of the quartile lines, in mm.
_QUARTILE_DASH = (0.8, 0.6)


def _pairs(panel, first, second, at, orient: str) -> tuple[list, list, list]:
    """Positions and the two samples at each, from two groups spelled as
    `violin` spells them. A category missing from one mapping has an empty
    half."""
    if isinstance(first, Mapping) or isinstance(second, Mapping):
        if not (isinstance(first, Mapping) and isinstance(second, Mapping)):
            raise DiagramError(
                "split_violin needs both conditions as mappings or both as sequences")
        keys = list(first.keys()) + [k for k in second.keys() if k not in first]
        places = list(at) if at is not None else keys
        if len(places) != len(keys):
            raise DiagramError(f"{len(places)} positions for {len(keys)} groups")
        a = [[float(v) for v in first.get(k, ())] for k in keys]
        b = [[float(v) for v in second.get(k, ())] for k in keys]
        return places, a, b
    places_a, a = _marks._groups(panel, first, at, orient)
    places_b, b = _marks._groups(panel, second, at, orient)
    if len(a) != len(b):
        raise DiagramError(
            f"split_violin has {len(a)} groups in the first condition and "
            f"{len(b)} in the second")
    return places_a, a, b


def split_violin(panel, first, second, *, at=None, orient: str = "v",
                 width: float = 0.8, bandwidth: float | None = None,
                 samples: int = 64, cut: float = 2.0, scale: str = "shared",
                 median: bool = True, quartiles: bool = False, colors=None,
                 **style) -> tuple[Diagram, tuple[str, str], dict]:
    """Two half violins per category. See `Panel.split_violin`.

    Returns `(node, (first colour, second colour), note)`.
    """
    if scale not in SPLIT_SCALES:
        raise DiagramError(f'split_violin scale is "shared" or "each", not {scale!r}')
    if samples < 4:
        raise DiagramError(f"a violin needs at least 4 samples, got {samples}")
    places, lefts, rights = _pairs(panel, first, second, at, orient)
    position, value = _marks._axes_of(panel, orient)
    theme = active_theme()
    given = style.pop("fill", None) if colors is None else colors
    if given is None:
        from .raincloud import _cloud

        fills = tuple(_cloud(c, theme.paper) for c in (theme.color(1), theme.color(2)))
    else:
        fills = _marks.series_colors(given, 2)
    # The first half runs toward smaller positions on the page: left for
    # vertical violins, up for horizontal ones (y grows downward on the page).
    toward = -1.0
    items: list = []
    note = {"drawn": [], "empty": []}
    for index, (where, pair) in enumerate(zip(places, zip(lefts, rights))):
        lo, hi = _marks._slot(position, where, width)
        middle = (lo + hi) / 2
        reach = abs(hi - lo) / 2
        shapes = []
        for side, sample in enumerate(pair):
            clean = [v for v in sample if not math.isnan(v)]
            spread = _bandwidth(clean) if (bandwidth is None and len(clean) > 1) \
                else (float(bandwidth) if bandwidth is not None else 0.0)
            if len(clean) < 2 or spread <= 0:
                note["empty"].append((index, side))
                shapes.append(None)
                continue
            pad = cut * spread
            low, high = _marks._within(value, min(clean) - pad, max(clean) + pad)
            if high <= low:
                note["empty"].append((index, side))
                shapes.append(None)
                continue
            grid = [low + (high - low) * k / (samples - 1) for k in range(samples)]
            density = kde(clean, grid, bandwidth=spread)
            if max(density) <= 0:
                note["empty"].append((index, side))
                shapes.append(None)
                continue
            shapes.append((clean, grid, density))
        peaks = [max(s[2]) for s in shapes if s is not None]
        if not peaks:
            continue
        for side, shape in enumerate(shapes):
            if shape is None:
                continue
            clean, grid, density = shape
            peak = max(peaks) if scale == "shared" else max(density)
            sign = toward if side == 0 else -toward

            def across(d: float) -> float:
                return middle + sign * reach * d / peak

            rim = [_marks._point(orient, across(d), value.map(g))
                   for g, d in zip(grid, density)]
            spine = [_marks._point(orient, middle, value.map(g))
                     for g in reversed(grid)]
            items.append(polygon(rim + spine, kind=MARK_KIND, fill=fills[side],
                                 stroke=theme.ink, stroke_width=theme.hairline))
            marks = []
            if quartiles:
                marks += [(quantile(clean, q), {"stroke_width": theme.hairline,
                                                "stroke_dash": _QUARTILE_DASH})
                          for q in (0.25, 0.75)]
            if median:
                marks.append((quantile(clean, 0.5), {"stroke_width": theme.stroke}))
            for level, paint in marks:
                if not grid[0] <= level <= grid[-1]:
                    continue
                edge = across(_marks._at(grid, density, level))
                items.append(polyline(
                    (_marks._point(orient, middle, value.map(level)),
                     _marks._point(orient, edge, value.map(level))),
                    kind=MARK_LINE_KIND, stroke=theme.ink, stroke_linecap="butt",
                    **paint))
        note["drawn"].append(index)
    if not items:
        raise DiagramError("split_violin() had nothing to draw")
    node = draw_place(items, origin=(0, 0), kind="split-violin", **style)
    node.notes["split_violin"] = note
    return node, (fills[0], fills[1]), note
