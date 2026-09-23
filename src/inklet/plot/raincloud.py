"""Raincloud plots: a half violin, a box and the observations, per group.

Each group's slot on the band scale is split across its width into three
lanes. The half violin (the cloud) stands on the category's centre line and
rises to one side; a narrow box sits just below the line; the observations
(the rain) fill the far half of the slot. With `orient="h"` (groups on y,
values on x) the cloud rises up the page; with `orient="v"` it extends to
the right.

The cloud is the same kernel density `violin` draws, with the same
bandwidth rule and `cut`, scaled so its peak reaches the edge of the slot.
The box is the `boxplot` box: quartiles, a heavy median line and whiskers to
the furthest observations within `whisker` interquartile ranges, without
caps and without separate outlier points, since every observation is in the
rain. The rain is jittered by a seeded random offset (`points="jitter"`,
the default) or packed as a swarm (`points="swarm"`); in both, only the
position across the slot changes and the value is exact.
"""

from __future__ import annotations

import math
import random
from typing import Sequence

from ..core import Diagram, DiagramError, mm
from ..draw.coords import active_theme
from ..draw.path import polygon, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND, marker as make_marker
from ..themes import contrast_ratio
from ..themes.color import mix
from . import marks as _marks
from .statistics import _bandwidth, box_stats, kde

__all__ = ["raincloud", "RAIN_POINTS"]

#: Accepted values of `raincloud(points=)`.
RAIN_POINTS = ("jitter", "swarm", None)

#: Lanes across the slot, as fractions of its half-width measured from the
#: category's centre line towards the cloud (positive) or the rain
#: (negative): the cloud's peak, the box's centre and half-thickness, and the
#: rain's centre and half-spread.
_CLOUD_REACH = 0.95
_BOX_AT = -0.2
_BOX_HALF = 0.09
_RAIN_AT = -0.62
_RAIN_HALF = 0.3

#: How far the cloud's fill is blended towards paper, so the box and the rain
#: in the full colour stand out against it. A dark colour is blended further,
#: until its contrast with paper is at most `_CLOUD_CONTRAST`, so the ink box
#: outline stays visible where it crosses the cloud.
_CLOUD_TINT = 0.35
_CLOUD_CONTRAST = 3.0


def raincloud(panel, groups, *, at=None, orient: str = "h", width: float = 0.9,
              bandwidth: float | None = None, samples: int = 64,
              cut: float = 2.0, whisker: float = 1.5, points: str | None = "jitter",
              size: float | str | None = None, seed: int = 0,
              box: bool = True, colors=None,
              **style) -> tuple[Diagram, tuple[str, ...], dict]:
    """A half violin, a box and the points of each group. See
    `Panel.raincloud`.

    Returns `(node, colours, note)`.
    """
    if points not in RAIN_POINTS:
        raise DiagramError(
            f'raincloud points is "jitter", "swarm" or None, not {points!r}')
    if samples < 4:
        raise DiagramError(f"a raincloud needs at least 4 samples, got {samples}")
    places, data = _marks._groups(panel, groups, at, orient)
    position, value = _marks._axes_of(panel, orient)
    theme = active_theme()
    given = style.pop("fill", None) if colors is None else colors
    inks = _marks._swarm_colors(given, len(data), theme)
    # The single-series default is the ink; its cloud is the pale tint a
    # violin would have, not a grey blend of black.
    clouds = (_marks.series_colors(None, 1) * len(data) if given is None and len(data) == 1
              else tuple(_cloud(c, theme.paper) for c in inks))
    dot = _marks._SWARM_OF_TYPE * theme.font_size if size is None else mm(size)
    if dot <= 0:
        raise DiagramError(f"a raincloud needs a positive dot size, got {size!r}")
    # The cloud rises up the page (h) or to the right (v).
    toward = -1.0 if orient == "h" else 1.0
    rng = random.Random(seed)
    items: list = []
    note = {"drawn": [], "empty": [], "dot": dot}
    for index, (where, sample) in enumerate(zip(places, data)):
        clean = [v for v in sample if not math.isnan(v)]
        if not clean:
            note["empty"].append(index)
            continue
        lo, hi = _marks._slot(position, where, width)
        middle = (lo + hi) / 2
        half = abs(hi - lo) / 2

        def across(u: float) -> float:
            return middle + toward * u * half

        spread = _bandwidth(clean) if bandwidth is None else float(bandwidth)
        if len(clean) > 1 and spread > 0:
            pad = cut * spread
            low, high = _marks._within(value, min(clean) - pad, max(clean) + pad)
            if high > low:
                grid = [low + (high - low) * k / (samples - 1)
                        for k in range(samples)]
                density = kde(clean, grid, bandwidth=spread)
                peak = max(density)
                if peak > 0:
                    base = [_marks._point(orient, across(0.0), value.map(g))
                            for g in reversed(grid)]
                    rim = [_marks._point(orient, across(_CLOUD_REACH * d / peak),
                                         value.map(g))
                           for g, d in zip(grid, density)]
                    items.append(polygon(rim + base, kind=MARK_KIND,
                                         fill=clouds[index], stroke="none"))
        if box and len(clean) > 1:
            items.extend(_box(orient, value, box_stats(clean, whisker=whisker),
                              across(_BOX_AT), _BOX_HALF * half, theme))
        if points is not None:
            spots = [value.map(v) for v in clean]
            centre = across(_RAIN_AT)
            if points == "swarm":
                offsets, drawn = _marks._swarm_fit(
                    spots, 2 * _RAIN_HALF * half, dot, dot * _marks._SWARM_GAP)
            else:
                reach = max(0.0, _RAIN_HALF * half - dot / 2)
                offsets = [rng.uniform(-reach, reach) for _ in spots]
                drawn = dot
            fill = {"fill": inks[index]}
            fill.update(style)
            for offset, along in zip(offsets, spots):
                items.append((_marks._point(orient, centre + offset, along),
                              make_marker("circle", drawn, **fill)))
        note["drawn"].append(index)
    if not items:
        raise DiagramError("raincloud() had nothing to draw")
    node = draw_place(items, origin=(0, 0), kind="raincloud")
    node.notes["raincloud"] = note
    return node, tuple(inks), note


def _cloud(color: str, paper: str) -> str:
    """`color` blended towards paper: at least `_CLOUD_TINT`, and further in
    fixed 5% steps until its contrast with paper is at most
    `_CLOUD_CONTRAST`."""
    share = _CLOUD_TINT
    blend = mix(color, paper, share)
    while contrast_ratio(blend, paper) > _CLOUD_CONTRAST and share < 0.95:
        share = round(share + 0.05, 2)
        blend = mix(color, paper, share)
    return blend


def _box(orient: str, value, stats, centre: float, half: float,
         theme) -> list:
    """A narrow box with a heavy median and uncapped whiskers."""
    a, b = value.map(stats.q1), value.map(stats.q3)
    out: list = [polygon(
        (_marks._point(orient, centre - half, a), _marks._point(orient, centre + half, a),
         _marks._point(orient, centre + half, b), _marks._point(orient, centre - half, b)),
        kind=MARK_KIND, fill=theme.paper, stroke=theme.ink,
        stroke_width=theme.stroke)]
    median = value.map(stats.median)
    out.append(polyline((_marks._point(orient, centre - half, median),
                         _marks._point(orient, centre + half, median)),
                        kind=MARK_LINE_KIND, stroke=theme.ink,
                        stroke_width=theme.thick, stroke_linecap="butt"))
    for end, edge in ((stats.low, stats.q1), (stats.high, stats.q3)):
        out.append(polyline((_marks._point(orient, centre, value.map(edge)),
                             _marks._point(orient, centre, value.map(end))),
                            kind=MARK_LINE_KIND, stroke=theme.ink,
                            stroke_width=theme.stroke))
    return out
