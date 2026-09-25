"""Strip plots and sina plots: every observation of each group, spread
sideways.

Both take groups the way `boxplot`, `violin` and `swarm` do, and both keep
each value exact: only the position across the group's slot changes.

A strip plot spreads the points uniformly across `width` of the slot. A sina
plot (Sidiropoulos et al., 2018, J. Comput. Graph. Stat. 27:673-676) spreads
each point by at most the group's kernel density at its value, so the cloud
of points takes the outline a violin would draw: wide where the data are
dense and narrow in the tails.

The sideways offsets come from a random generator seeded by `seed`, so the
same call draws the same figure every time; change `seed` to redraw the
jitter. With `jitter=0` a strip plot puts every point on the centre line.
"""

from __future__ import annotations

import math
import random

from ..core import Diagram, DiagramError, mm
from ..draw.coords import active_theme
from ..draw.place import place as draw_place
from ..draw.shapes import marker as make_marker
from . import marks as _marks
from .kernel_density import bandwidth as _rule_bandwidth
from .statistics import kde

__all__ = ["strip_layer", "sina_layer"]


def _dots(theme, size) -> float:
    dot = _marks._SWARM_OF_TYPE * theme.font_size if size is None else mm(size)
    if not dot > 0:
        raise DiagramError(f"dots need a positive size, got {size!r}")
    return dot


def strip_layer(panel, groups, *, at=None, width: float = 0.8, jitter: float = 0.5,
                orient: str = "v", size=None, seed: int = 0, color=None,
                marker: str = "circle", **style) -> tuple[Diagram, dict]:
    """Jittered points of `Panel.strip`. Returns `(node, note)`."""
    if not 0.0 <= jitter <= 1.0:
        raise DiagramError(f"strip jitter is a fraction of the slot, 0 to 1, got {jitter!r}")
    places, data = _marks._groups(panel, groups, at, orient)
    position, value = _marks._axes_of(panel, orient)
    theme = active_theme()
    inks = _marks._swarm_colors(color, len(data), theme)
    dot = _dots(theme, size)
    rng = random.Random(seed)
    items: list = []
    note = {"drawn": [], "seed": seed}
    for where, sample, ink in zip(places, data, inks):
        lo, hi = _marks._slot(position, where, width)
        middle = (lo + hi) / 2
        reach = max(0.0, jitter * abs(hi - lo) / 2 - dot / 2)
        paint = {"fill": ink}
        paint.update(style)
        count = 0
        for v in sample:
            if not math.isfinite(v):
                continue
            offset = rng.uniform(-reach, reach) if reach > 0 else 0.0
            items.append((_marks._point(orient, middle + offset, value.map(v)),
                          make_marker(marker, dot, **paint)))
            count += 1
        note["drawn"].append(count)
    if not items:
        raise DiagramError("strip() had nothing to draw")
    node = draw_place(items, origin=(0, 0), kind="strip")
    node.notes["strip"] = note
    return node, note


def sina_layer(panel, groups, *, at=None, width: float = 0.8, orient: str = "v",
               bandwidth="scott", adjust: float = 1.0, size=None, seed: int = 0,
               color=None, marker: str = "circle", **style) -> tuple[Diagram, dict]:
    """Density-scaled jittered points of `Panel.sina`. Returns `(node, note)`."""
    places, data = _marks._groups(panel, groups, at, orient)
    position, value = _marks._axes_of(panel, orient)
    theme = active_theme()
    inks = _marks._swarm_colors(color, len(data), theme)
    dot = _dots(theme, size)
    rng = random.Random(seed)
    items: list = []
    note = {"drawn": [], "bandwidth": [], "seed": seed}
    for where, sample, ink in zip(places, data, inks):
        clean = [v for v in sample if math.isfinite(v)]
        lo, hi = _marks._slot(position, where, width)
        middle = (lo + hi) / 2
        reach = max(0.0, abs(hi - lo) / 2 - dot / 2)
        if len(clean) >= 2:
            h = _rule_bandwidth(clean, bandwidth, adjust=adjust)
            density = kde(clean, clean, bandwidth=h)
            peak = max(density) or 1.0
            spread = [d / peak for d in density]
        else:
            h = None
            spread = [0.0] * len(clean)
        paint = {"fill": ink}
        paint.update(style)
        for v, s in zip(clean, spread):
            offset = rng.uniform(-1.0, 1.0) * reach * s
            items.append((_marks._point(orient, middle + offset, value.map(v)),
                          make_marker(marker, dot, **paint)))
        note["drawn"].append(len(clean))
        note["bandwidth"].append(h)
    if not items:
        raise DiagramError("sina() had nothing to draw")
    node = draw_place(items, origin=(0, 0), kind="sina")
    node.notes["sina"] = note
    return node, note
