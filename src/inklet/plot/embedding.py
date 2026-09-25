"""Embedding scatters (UMAP, t-SNE): points coloured by cluster, named in place.

`cluster_centres` finds where each cluster's name goes and draws nothing.
The centre is a robust one that lies on the data: by default the member
point nearest the coordinate-wise median of its cluster, so a curved or
elongated cluster is named over its own points rather than over the gap its
mean falls in. `"medoid"` uses the member with the smallest summed distance
to the others (computed on at most 400 evenly spaced members), and `"mean"`
the plain centroid.

`Panel.embedding` draws the points with one `scatter` call, so from 256
points up they are one packed marker batch, and writes each cluster's name at
its centre on a paper halo. A name that would overlap a name already placed,
or the points of another cluster, moves to the nearest free spot around its
centre, searched on the rings `label_points` uses. It may cover its own
cluster. `outline=` draws each cluster's core, found by `core_outline`, as a
thin line in its colour or a light fill under the points. `arrows=` replaces
the axes with two short arrows in the lower-left corner, labelled for example
UMAP1 and UMAP2.
"""

from __future__ import annotations

import math
import random
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, Rect, Vec2, mm
from ..draw.coords import active_theme
from ..draw.path import polygon, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND
from ..themes.color import mix
from .axis import text_node
from .outlines import core_outline
from .point_labels import (POINT_LABEL_KIND, _box_at, _candidates, _overlap,
                           _within)

__all__ = ["cluster_centres", "cluster_colors", "CENTRE_METHODS",
           "OUTLINE_STYLES"]

#: Accepted values of `cluster_centres(method=)`.
CENTRE_METHODS = ("median", "medoid", "mean")

#: At most this many members enter the medoid search.
_MEDOID_SAMPLE = 400

#: The halo behind a cluster name, in mm.
_HALO = 0.8

#: Accepted values of `Panel.embedding(outline=)`.
OUTLINE_STYLES = ("line", "fill")

#: An outline fill is the cluster colour blended this far towards paper.
_FILL_TOWARD_PAPER = 0.8

#: Cluster names: how far out the search goes, in type sizes; the weight of
#: covering another name (per square millimetre), of each outline crossed
#: and of each millimetre moved, against other clusters' points covered (per
#: square millimetre); and the smallest cell of the dot grid, in mm.
_REACH = 6.0
_NAME_WEIGHT = 10.0
_EDGE_WEIGHT = 4.0
_DISTANCE_WEIGHT = 0.3
_CELL_MIN = 0.2

#: Corner arrows: length as a fraction of the shorter panel side, clamped to
#: these millimetres, and the arrowhead's length and half-width.
_ARROW_OF_SIDE = 0.18
_ARROW_MIN, _ARROW_MAX = 5.0, 10.0
_HEAD_LENGTH = 0.9
_HEAD_HALF = 0.45


def _order(clusters: Sequence) -> list:
    """Cluster names in first-seen order, or sorted when they are all numbers."""
    seen = list(dict.fromkeys(clusters))
    if all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in seen):
        return sorted(seen)
    return seen


def cluster_centres(points: Sequence[Sequence[float]], clusters: Sequence, *,
                    method: str = "median") -> dict:
    """Where to write each cluster's name, in data coordinates.

    `points` are `(x, y)` pairs and `clusters` one cluster name per point.
    Returns a mapping of cluster to `(x, y)`, in cluster order (first seen,
    or ascending when every name is a number). See the module docstring for
    `method`.
    """
    if method not in CENTRE_METHODS:
        raise DiagramError(
            f"cluster_centres method is one of {', '.join(CENTRE_METHODS)}, not {method!r}")
    data = [(float(p[0]), float(p[1])) for p in points]
    names = list(clusters)
    if len(data) != len(names):
        raise DiagramError(
            f"embedding needs one cluster per point, got {len(names)} for {len(data)} points")
    members: dict = {}
    for point, name in zip(data, names):
        if math.isfinite(point[0]) and math.isfinite(point[1]):
            members.setdefault(name, []).append(point)
    out: dict = {}
    for name in _order(names):
        group = members.get(name)
        if not group:
            continue
        if method == "mean":
            out[name] = (sum(p[0] for p in group) / len(group),
                         sum(p[1] for p in group) / len(group))
            continue
        if method == "medoid":
            step = max(1, len(group) // _MEDOID_SAMPLE)
            pool = group[::step]
            out[name] = min(pool, key=lambda a: (sum(math.hypot(a[0] - b[0], a[1] - b[1])
                                                     for b in pool), a))
            continue
        mx = _median([p[0] for p in group])
        my = _median([p[1] for p in group])
        # Scaled by the cluster's spread on each axis, so a long thin
        # cluster is not measured in the units of its long side.
        sx = _spread([p[0] for p in group], mx)
        sy = _spread([p[1] for p in group], my)
        out[name] = min(group, key=lambda p: (((p[0] - mx) / sx) ** 2
                                              + ((p[1] - my) / sy) ** 2, p))
    return out


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2


def _spread(values: list[float], centre: float) -> float:
    spread = _median([abs(v - centre) for v in values])
    return spread if spread > 0 else 1.0


def cluster_colors(count: int) -> tuple[str, ...]:
    """`count` distinguishable colours for cluster labels.

    Paul Tol's muted palette, then his bright and vibrant ones without their
    greys, then the same list again blended a third of the way to the ink,
    and so on. The theme palette is not used because its first colour is
    the ink, which would read as "unassigned".
    """
    from ..themes.color import mix
    from ..themes.palettes import palette

    base = list(palette("tol-muted").colors)
    for name in ("tol-bright", "tol-vibrant"):
        base += [c for c in palette(name).colors if c not in base and c != "#bbbbbb"]
    out: list[str] = []
    round_ = 0
    while len(out) < count:
        for color in base:
            if len(out) == count:
                break
            out.append(color if round_ == 0 else mix(color, "#1a1a1a", min(0.6, 0.33 * round_)))
        round_ += 1
    return tuple(out)


def embedding(panel, points, clusters, *, colors=None, size=None,
              labels: bool = True, centre: str = "median",
              label_size: float | str | None = None,
              arrows=None, shuffle: bool = True, seed: int = 0,
              raster: bool = False, outline=None, outline_core: float = 0.8,
              **style) -> dict:
    """Draw an embedding scatter into `panel`. See `Panel.embedding`.

    Returns the note: cluster order, colours, centres and label positions.
    """
    data = [tuple(p) for p in points]
    names = list(clusters)
    if len(data) != len(names):
        raise DiagramError(
            f"embedding needs one cluster per point, got {len(names)} for {len(data)} points")
    if not data:
        raise DiagramError("embedding was given no points")
    order = _order(names)
    if colors is None:
        paint = dict(zip(order, cluster_colors(len(order))))
    elif isinstance(colors, Mapping):
        missing = [c for c in order if c not in colors]
        if missing:
            raise DiagramError(f"embedding colors has no colour for {missing}")
        paint = {c: colors[c] for c in order}
    elif isinstance(colors, str):
        paint = {c: colors for c in order}
    else:
        given = list(colors)
        if not given:
            raise DiagramError("embedding colors= was given no colours")
        paint = {c: given[k % len(given)] for k, c in enumerate(order)}
    if outline is True:
        outline = "line"
    if outline not in (None, False, *OUTLINE_STYLES):
        raise DiagramError(
            f"embedding outline= is one of {', '.join(OUTLINE_STYLES)}, not {outline!r}")
    if not 0.0 < outline_core < 1.0:
        raise DiagramError(
            f"embedding outline_core is a fraction between 0 and 1, not {outline_core!r}")
    pages = [panel.point(*p) if _finite(p) else None for p in data]
    rings: dict = {}
    if outline:
        rings = _outlines(pages, names, order, outline_core)
        if outline == "fill":
            panel.draw(*_outline_nodes(rings, paint, outline), clip=True)
    indices = list(range(len(data)))
    if shuffle:
        # Drawn in a seeded random order, so no cluster covers another just
        # because it came later in the table.
        random.Random(seed).shuffle(indices)
    panel.scatter([data[i] for i in indices],
                  color=[paint[names[i]] for i in indices], size=size,
                  raster=raster, **style)
    if outline and outline != "fill":
        panel.draw(*_outline_nodes(rings, paint, outline), clip=True)
    for name in order:
        panel._note(str(name), "marker", color=paint[name], marker="circle")
    centres = cluster_centres(data, names, method=centre)
    placed: dict = {}
    covering: list = []
    if labels:
        placed, covering = _names(panel, centres, label_size, pages, names,
                                  order, _dot_size(size), rings,
                                  own=outline == "fill")
    if arrows is not None:
        panel.over(_arrows(panel, arrows), clip=False)
    note = {"clusters": order, "colors": [paint[c] for c in order],
            "centres": centres, "labels": placed, "covering": covering}
    if outline:
        note["outline"] = {"style": outline, "core": outline_core,
                           "rings": {c: len(rings.get(c, ())) for c in order}}
    return note


def _finite(p) -> bool:
    return math.isfinite(float(p[0])) and math.isfinite(float(p[1]))


def _dot_size(size) -> float:
    """The largest dot diameter in mm."""
    from ..draw.shapes import _MARKER_OF_TYPE

    if size is None:
        return _MARKER_OF_TYPE * active_theme().font_size
    if isinstance(size, (int, float, str)):
        return mm(size)
    return max((mm(v) for v in size), default=0.0)


def _outlines(pages: Sequence, names: Sequence, order: Sequence,
              core: float) -> dict:
    """Each cluster's core rings, in page millimetres."""
    members: dict = {}
    for at, name in zip(pages, names):
        if at is not None:
            members.setdefault(name, []).append(at)
    return {name: core_outline(members.get(name, ()), core=core)
            for name in order}


def _outline_nodes(rings: dict, paint: dict, style: str) -> list:
    """One path per cluster: a thin line in its colour, or a light fill."""
    theme = active_theme()
    nodes = []
    for name, loops in rings.items():
        if not loops:
            continue
        if style == "fill":
            fill = mix(paint[name], theme.paper, _FILL_TOWARD_PAPER)
            nodes.append(polygon(loops[0], holes=loops[1:], fill_rule="evenodd",
                                 kind=MARK_KIND, fill=fill, stroke="none"))
        else:
            nodes.append(polygon(loops[0], holes=loops[1:], fill_rule="evenodd",
                                 kind=MARK_LINE_KIND, filled=False, fill="none",
                                 stroke=paint[name], stroke_width=theme.stroke,
                                 stroke_linejoin="round"))
    return nodes


def _names(panel, centres: dict, size, pages: Sequence, names: Sequence,
           order: Sequence, dot: float, rings: dict,
           own: bool = False) -> tuple[dict, list]:
    """Cluster names at their centres, moved clear of each other and of the
    points of other clusters.

    Candidates are the centre, then the rings `label_points` searches. The
    first that covers no name already placed, no point of another cluster
    and no edge of another cluster's outline wins; a name may cover its own
    cluster and its own outline line, on its halo. With `own` (a filled
    outline), a name must also not lap its own tint's edge, which the linter
    reports as an overlap: it sits wholly inside the tint or beside it.
    Otherwise the lowest score
    wins: names covered weigh most, then outlines crossed, then other clusters' points
    covered (in square millimetres), then the distance moved. Returns the
    positions and the names that still cover other clusters' points.
    """
    theme = active_theme()
    font = theme.font_size_small if size is None else mm(size)
    area = panel.area
    occupied = _Occupancy(pages, names, order, dot, rings)
    boxes: list[Rect] = []
    parts: list = []
    where: dict = {}
    covering: list = []
    ring = 0.6 * font
    for name, (x, y) in centres.items():
        node = text_node(str(name), font, POINT_LABEL_KIND, markup=False,
                         halo=_HALO)
        w, h = node.bbox.width, node.bbox.height
        anchor = panel.point(x, y)
        first = Rect(anchor.x - w / 2, anchor.y - h / 2, anchor.x + w / 2, anchor.y + h / 2)
        tries = [(first, 0.0)] + [
            (_box_at(anchor, angle, distance, w, h, slide), distance)
            for distance, angle, slide, _ in _candidates(0.2 * font, ring, _REACH * font)]
        best, cost, others = None, math.inf, 0.0
        for box, distance in tries:
            box = _inside(box, area)
            if box is None:
                continue
            clash = sum(_overlap(box, _grown(other, 0.3)) for other in boxes)
            crowd, edges = occupied.covered(box, name, own)
            if clash == 0 and crowd == 0 and edges == 0:
                best, others = box, 0.0
                break
            score = (_NAME_WEIGHT * clash + _EDGE_WEIGHT * edges + crowd
                     + _DISTANCE_WEIGHT * distance)
            if score < cost:
                best, cost, others = box, score, crowd
        if best is None:
            best = first
        if others > 0:
            covering.append(name)
        boxes.append(best)
        parts.append((best.center, node))
        where[name] = panel_data(panel, best.center)
    if parts:
        panel.over(draw_place(parts, origin=(0, 0), kind="cluster-labels"), clip=False)
    return where, covering


class _Occupancy:
    """Which clusters have a dot, and which an outline edge, in each cell
    of a fine square grid.

    The cell is the dot diameter (at least `_CELL_MIN` mm), and a dot marks
    every cell its box touches, so a name box tested against the grid sees
    every dot it could cover. An outline marks the cells it passes through.
    """

    def __init__(self, pages: Sequence, names: Sequence, order: Sequence,
                 dot: float, rings: dict) -> None:
        self.cell = max(dot, _CELL_MIN)
        self.bit = {name: 1 << k for k, name in enumerate(order)}
        self.cells: dict[tuple[int, int], int] = {}
        self.edges: dict[tuple[int, int], int] = {}
        half = dot / 2
        c = self.cell
        for owner, loop in ((n, r) for n, loops in rings.items() for r in loops):
            bit = self.bit[owner]
            for a, b in zip(loop, loop[1:] + loop[:1]):
                steps = max(1, math.ceil(math.hypot(b.x - a.x, b.y - a.y) / (c / 2)))
                for k in range(steps):
                    t = k / steps
                    key = (math.floor((a.x + (b.x - a.x) * t) / c),
                           math.floor((a.y + (b.y - a.y) * t) / c))
                    self.edges[key] = self.edges.get(key, 0) | bit
        for at, name in zip(pages, names):
            if at is None:
                continue
            bit = self.bit[name]
            for i in range(math.floor((at.x - half) / c),
                           math.floor((at.x + half) / c) + 1):
                for j in range(math.floor((at.y - half) / c),
                               math.floor((at.y + half) / c) + 1):
                    self.cells[i, j] = self.cells.get((i, j), 0) | bit

    def covered(self, box: Rect, name, own_edges: bool = False) -> tuple[float, int]:
        """Square millimetres of `box` over cells holding other clusters,
        and how many outlines of other clusters (and with `own_edges`, of
        this one) pass through it."""
        own = self.bit.get(name, 0)
        mask = -1 if own_edges else ~own
        c = self.cell
        count = 0
        edges = 0
        for i in range(math.floor(box.x0 / c), math.floor(box.x1 / c) + 1):
            for j in range(math.floor(box.y0 / c), math.floor(box.y1 / c) + 1):
                if self.cells.get((i, j), 0) & ~own:
                    count += 1
                edges |= self.edges.get((i, j), 0) & mask
        return count * c * c, bin(edges).count("1")


def _grown(box: Rect, by: float) -> Rect:
    return Rect(box.x0 - by, box.y0 - by, box.x1 + by, box.y1 + by)


def _inside(box: Rect, area: Rect) -> Rect | None:
    """`box` slid inside `area`, or None when it is larger than the area."""
    if box.width > area.width or box.height > area.height:
        return None
    dx = max(0.0, area.x0 - box.x0) - max(0.0, box.x1 - area.x1)
    dy = max(0.0, area.y0 - box.y0) - max(0.0, box.y1 - area.y1)
    return Rect(box.x0 + dx, box.y0 + dy, box.x1 + dx, box.y1 + dy)


def panel_data(panel, at: Vec2) -> tuple[float, float]:
    """Page millimetres back to data, for the note."""
    try:
        return panel.x.invert(at.x), panel.y.invert(at.y)
    except Exception:                                    # pragma: no cover
        return at.x, at.y


def _arrows(panel, arrows) -> Diagram:
    """Two arrows from the lower-left corner of the plot area, right and up,
    with their names outside the area: below the x arrow and left of the y
    arrow, reading upward."""
    if isinstance(arrows, str):
        names = (f"{arrows}1", f"{arrows}2")
    else:
        names = tuple(arrows)
        if len(names) != 2:
            raise DiagramError(f"embedding arrows= is a prefix or two names, not {arrows!r}")
    theme = active_theme()
    area = panel.area
    length = min(_ARROW_MAX, max(_ARROW_MIN, _ARROW_OF_SIDE * min(area.width, area.height)))
    corner = Vec2(area.x0, area.y1)
    ink = theme.ink
    line = {"kind": MARK_LINE_KIND, "stroke": ink, "stroke_width": theme.stroke,
            "stroke_linecap": "butt"}
    tip_x = Vec2(corner.x + length, corner.y)
    tip_y = Vec2(corner.x, corner.y - length)
    items: list = [
        polyline((corner, Vec2(tip_x.x - _HEAD_LENGTH, tip_x.y)), **line),
        polyline((corner, Vec2(tip_y.x, tip_y.y + _HEAD_LENGTH)), **line),
        polygon((tip_x, Vec2(tip_x.x - _HEAD_LENGTH, tip_x.y - _HEAD_HALF),
                 Vec2(tip_x.x - _HEAD_LENGTH, tip_x.y + _HEAD_HALF)),
                kind=MARK_KIND, fill=ink, stroke="none"),
        polygon((tip_y, Vec2(tip_y.x - _HEAD_HALF, tip_y.y + _HEAD_LENGTH),
                 Vec2(tip_y.x + _HEAD_HALF, tip_y.y + _HEAD_LENGTH)),
                kind=MARK_KIND, fill=ink, stroke="none"),
    ]
    font = theme.font_size_small
    pad = theme.gap("xs") / 2
    from .axis import AXIS_LABEL_KIND

    label_x = text_node(str(names[0]), font, AXIS_LABEL_KIND, markup=False)
    label_y = text_node(str(names[1]), font, AXIS_LABEL_KIND, markup=False).rotated(-90)
    bx, by = label_x.bbox, label_y.bbox
    items.append((Vec2(corner.x + bx.width / 2, corner.y + pad + bx.height / 2), label_x))
    items.append((Vec2(corner.x - pad - by.width / 2, corner.y - by.height / 2), label_y))
    return draw_place(items, origin=(0, 0), kind="embedding-arrows")
