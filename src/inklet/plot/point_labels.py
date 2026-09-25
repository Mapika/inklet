"""Labels for many data points at once, placed clear of marks and each other.

`Panel.label_points` names a set of points -- the highlighted genes of a
volcano plot, the named cell types of a scatter -- in one call. Each label is
placed by a deterministic search:

1. Candidate positions are eight compass directions around the point at the
   minimum clearance, then sixteen directions on rings further out, up to
   `reach` millimetres. Boxes straight above, below or beside the point are
   also tried slid along that side, so an end of the label rather than its
   middle lines up with the point.
   Past `reach` further rings (sixteen directions) run out to
   `_FURTHER * reach`, for a label with no room near its point; each extra
   millimetre there costs more than the last.
2. A candidate is rejected if its box leaves the plot area. Otherwise it is
   scored against an obstacle field of everything drawn
   (`layout.label_search.ObstacleField`): markers, bars and text by their
   boxes, stroked lines by their segments, bands and areas by their
   outlines, and the other labelled points. A candidate off the first ring
   needs a leader, scored for the marks, lines and labelled points it runs
   through. Distance from the point is added.
3. The best `_KEEP` candidates per label go to `layout.label_search.solve`,
   which chooses one per label jointly -- greedy, best response, seeded
   annealing and pair repair -- so that labels do not overlap one another or
   labelled points, and leaders neither cross nor pass through labels.

A label placed off the first ring gets a hairline leader back to its point.
A label still in conflict is listed as unresolved in the node's
`point_labels` note (and reported by lint as `LABEL_UNPLACED`); one that
sits on a background mark is listed under `covering_marks`.

`Panel.label_points` defers the placement to `Panel.build`, so the labels
avoid every mark on the panel, including marks drawn after the call. Labels
from several calls are placed in call order, each clear of the ones before.
With nothing drawn after the call the result is the same as placing at once.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import (Diagram, DiagramError, MarkerBatchPrim, PathPrim, Rect,
                   Vec2, mm, resolve)
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..layout.label_search import (Candidate, ObstacleField, Weights, seed_of,
                                   solve)
from .axis import text_node

__all__ = ["POINT_LABEL_KIND", "LEADER_KIND", "PENDING_KIND", "label_points"]

#: Kind of each label text node.
POINT_LABEL_KIND = "label"
#: Kind of the empty node that holds a `Panel.label_points` call's place in
#: paint order until the panel is built.
PENDING_KIND = "point-labels-pending"
#: Kind of each leader line.
LEADER_KIND = "mark-line"

#: The zone around each labelled point that no label may cover, as a fraction
#: of the type size: the radius of a scatter marker (0.62 of the type size
#: across) plus a little.
_TARGET_OF_TYPE = 0.34

#: Ring spacing, as a fraction of the label size.
_RING_OF_TYPE = 0.9

#: Direction preference on the first ring, in order: east, north-east, west,
#: north-west, north, south-east, south-west, south. Page degrees, clockwise
#: from east (y grows downward).
_FIRST = (0.0, -45.0, 180.0, -135.0, -90.0, 45.0, 135.0, 90.0)

#: The directions whose boxes are also tried slid along their side: north,
#: south, east, west.
_CARDINAL = (-90.0, 90.0, 0.0, 180.0)

#: A leader is drawn from this far outside the point, as a fraction of the
#: target radius, so it does not touch the marker.
_STANDOFF = 1.15

#: What a candidate costs -- covering marks, labelled points and labels,
#: lines through it, leaders through marks or other labels, distance -- is
#: `layout.label_search.Weights`, shared with `label_lines` and
#: `place_labels(method="joint")`.

#: Candidates kept per label for the joint search, cheapest first.
_KEEP = 64

#: How far past `reach` the outer rings go, as a multiple of it, for a label
#: that has no room near its point.
_FURTHER = 2.5

#: Cost per square millimetre a candidate lies past `reach`.
_STRETCH = 0.02

#: Cost per step down the first ring's order of preference.
_PREFERENCE = 0.02


def label_points(panel, points: Sequence[Sequence], labels: Sequence[str], *,
                 size: float | str | None = None,
                 clear: float | str | None = None,
                 reach: float | str | None = None,
                 leader: bool = True, markup: bool = False,
                 avoid: Sequence[Diagram] = (),
                 leader_style: dict | None = None,
                 marks: Sequence[Diagram] | None = None, **style) -> Diagram:
    """Place one label per point. See `Panel.label_points`.

    `marks` are the drawn nodes to keep clear of; the default is what the
    panel holds now, in its content and over layers.
    """
    data, names = checked(points, labels)
    theme = active_theme()
    if "fill" in style:                 # text is coloured by text_fill
        style["text_fill"] = style.pop("fill")
    font = theme.font_size_small if size is None else mm(size)
    gap = theme.gap("xs") if clear is None else mm(clear)
    target = _TARGET_OF_TYPE * theme.font_size
    ring = _RING_OF_TYPE * font
    # Two labels keep the theme's small gap between them, the clearance the
    # linter's CROWDING rule checks text against.
    spacing = theme.gap("xs")
    far = 8 * font if reach is None else mm(reach)
    area = panel.area
    anchors = [panel.point(*p) for p in data]
    if marks is None:
        marks = [*panel._content, *panel._over]
    boxes, segments, polygons, flags = _obstacles([*marks, *avoid], split=True)
    field = ObstacleField(cell=max(ring * 2, 1.0))
    for box, flag in zip(boxes, flags):
        field.add_box((box.x0, box.y0, box.x1, box.y1), mark=flag)
    for a, b in segments:
        field.add_segment((a.x, a.y, b.x, b.y))
    for poly in polygons:
        field.add_area(poly)
    index_of = _Grid(boxes, max(ring * 2, 1.0))
    # The markers drawn at each labelled point (there may be two: a grey
    # cloud and a highlight drawn over it).
    own_marker: dict[int, list[int]] = {}
    radii: list[float] = []
    number_of = {id(box): n for n, box in enumerate(boxes)}
    for number, a in enumerate(anchors):
        mine = [other for other in index_of.near(Rect(a.x, a.y, a.x, a.y))
                if abs(other.center.x - a.x) < 1e-6
                and abs(other.center.y - a.y) < 1e-6
                and other.width <= 2.5 * target]
        own_marker[number] = sorted(number_of[id(other)] for other in mine)
        # A point with a marker of its own is kept clear by that marker's
        # radius; a point with none by the default zone.
        radii.append(max((other.width / 2 for other in mine), default=target))
    for a, r in zip(anchors, radii):
        field.add_target((a.x - r, a.y - r, a.x + r, a.y + r))
    nodes = [text_node(str(name), font, POINT_LABEL_KIND, markup=markup, **style)
             for name in names]
    weights = Weights()
    options: list[list[Candidate]] = []
    for index, anchor in enumerate(anchors):
        width, height = nodes[index].bbox.width, nodes[index].bbox.height
        own = (index,)
        found: list[tuple[float, int, Candidate]] = []
        for rank, (distance, angle, slide, first) in enumerate(_candidates(
                gap + radii[index], ring, far, further=_FURTHER * far)):
            box = _box_at(anchor, angle, distance, width, height, slide)
            if not _within(box, area):
                continue
            b = (box.x0, box.y0, box.x1, box.y1)
            cost, conflicts, covered = field.cost(
                b, spacing=spacing, weights=weights, own=own,
                own_boxes=own_marker[index])
            line = None
            if not first and leader:
                line = _leader(anchor, box, radii[index] * _STANDOFF)
            seg = None
            if line is not None:
                seg = (line[0].x, line[0].y, line[1].x, line[1].y)
                lc, lk = field.leader_cost(seg, weights=weights, own=own)
                cost += lc + weights.leader
                conflicts += lk
            cost += weights.distance * distance
            # Past `reach` a leader costs more for every extra millimetre,
            # so a far label is the last resort, not a cheap escape.
            cost += _STRETCH * max(0.0, distance - far) ** 2
            if first:
                # The first ring's order is a preference: east, then round.
                cost += _PREFERENCE * rank
            found.append((cost, rank, Candidate(b, seg, cost, conflicts,
                                                (box, line), covered)))
        if not found:
            raise DiagramError(
                f"label {names[index]!r} does not fit inside the plot area; "
                "enlarge the panel or shorten the label")
        found.sort(key=lambda item: (item[0], item[1]))
        options.append([c for _, _, c in found[:_KEEP]])
    order = sorted(range(len(data)),
                   key=lambda i: (-_crowding(i, anchors, index_of, far), i))
    solution = solve(options, spacing=spacing, order=order, weights=weights,
                     seed=seed_of(tuple(names),
                                  tuple((round(a.x, 4), round(a.y, 4))
                                        for a in anchors)))
    placed = {i: options[i][c].data[0] for i, c in enumerate(solution.chosen)}
    leaders = {i: options[i][c].data[1] for i, c in enumerate(solution.chosen)
               if options[i][c].data[1] is not None}
    unresolved = sorted(solution.conflicted)
    covering = [i for i, c in enumerate(solution.chosen)
                if options[i][c].covered and i not in solution.conflicted]
    ink = style.get("text_fill", theme.ink)
    line_style = {"stroke": ink, "stroke_width": theme.hairline}
    line_style.update(leader_style or {})
    parts: list = []
    for index in range(len(data)):
        if index in leaders:
            a, b = leaders[index]
            parts.append(polyline((a, b), kind=LEADER_KIND, **line_style))
    for index in range(len(data)):
        box = placed[index]
        parts.append((box.center, nodes[index]))
    node = draw_place(parts, origin=(0, 0), kind="point-labels")
    node.notes["point_labels"] = {
        "count": len(data),
        "leaders": sorted(leaders),
        "unresolved": [names[i] for i in unresolved],
        "covering_marks": [names[i] for i in covering],
    }
    return node


def checked(points: Sequence[Sequence], labels: Sequence[str]) -> tuple[list, list]:
    """The points as tuples and the labels as a list, or an error when they
    do not pair up."""
    data = [tuple(p) for p in points]
    names = list(labels)
    if len(data) != len(names):
        raise DiagramError(
            f"label_points() got {len(names)} labels for {len(data)} points")
    if not data:
        raise DiagramError("label_points() was given no points")
    return data, names


def _candidates(start: float, ring: float, far: float,
                further: float | None = None):
    """`(distance, page angle, slide, first ring?)` in search order.

    With `further`, rings continue past `far` out to `further`, two rings'
    spacing apart and with sixteen directions, so a label with no room near
    its point can still reach free space on a longer leader.

    `slide` moves a box placed straight above, below or beside the point
    along that side, so one of its ends lines up with the point instead of
    its middle (see `_box_at`). A wide label next to a crowded neighbour
    often fits with one end over the point where the centred box does not.
    """
    for angle in _FIRST:
        yield start, angle, 0, True
    for angle in _CARDINAL:
        for slide in (1, -1):
            yield start, angle, slide, True
    distance = start + ring
    while distance <= far + 1e-9:
        for step in range(16):
            angle = _FIRST[step % 8] if step < 8 else _FIRST[step % 8] + 22.5
            yield distance, angle, 0, False
        for angle in _CARDINAL:
            for slide in (1, -1):
                yield distance, angle, slide, False
        distance += ring
    if further is None:
        return
    while distance <= further + 1e-9:
        for step in range(16):
            angle = _FIRST[step % 8] if step < 8 else _FIRST[step % 8] + 22.5
            yield distance, angle, 0, False
        distance += 2 * ring


def _box_at(anchor: Vec2, angle: float, distance: float, width: float,
            height: float, slide: int = 0) -> Rect:
    """The label box whose nearest edge is `distance` from the anchor,
    in the direction `angle` (page degrees).

    With `slide` of 1 or -1 the box is moved along its side by half its
    length, so its end rather than its middle is level with the anchor.
    """
    radians = math.radians(angle)
    dx, dy = math.cos(radians), math.sin(radians)
    half = abs(dx) * width / 2 + abs(dy) * height / 2
    cx = anchor.x + dx * (distance + half)
    cy = anchor.y + dy * (distance + half)
    if slide:
        if abs(dy) > abs(dx):
            cx += slide * width / 2
        else:
            cy += slide * height / 2
    return Rect(cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)


def _within(box: Rect, area: Rect) -> bool:
    return (box.x0 >= area.x0 and box.x1 <= area.x1
            and box.y0 >= area.y0 and box.y1 <= area.y1)


def _grown(box: Rect, by: float) -> Rect:
    return Rect(box.x0 - by, box.y0 - by, box.x1 + by, box.y1 + by)


def _overlap(a: Rect, b: Rect) -> float:
    w = min(a.x1, b.x1) - max(a.x0, b.x0)
    h = min(a.y1, b.y1) - max(a.y0, b.y0)
    return w * h if w > 0 and h > 0 else 0.0


def _crowding(index: int, anchors: Sequence[Vec2], grid: "_Grid",
              far: float) -> int:
    here = anchors[index]
    reach = far / 2
    near = sum(1 for other in anchors
               if math.hypot(other.x - here.x, other.y - here.y) < reach)
    around = Rect(here.x - reach, here.y - reach, here.x + reach, here.y + reach)
    return near + sum(1 for _ in grid.near(around))


def _leader(anchor: Vec2, box: Rect, standoff: float) -> tuple[Vec2, Vec2] | None:
    """From just outside the point to the nearest point of the label box."""
    near = Vec2(min(max(anchor.x, box.x0), box.x1),
                min(max(anchor.y, box.y0), box.y1))
    dx, dy = near.x - anchor.x, near.y - anchor.y
    length = math.hypot(dx, dy)
    if length <= standoff * 1.5:
        return None
    start = Vec2(anchor.x + dx / length * standoff,
                 anchor.y + dy / length * standoff)
    return start, near


def _segments_cross(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> bool:
    """Whether segments a-b and c-d cross (touching ends do not count)."""
    def side(p, q, r):
        return (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)
    d1, d2 = side(c, d, a), side(c, d, b)
    d3, d4 = side(a, b, c), side(a, b, d)
    return d1 * d2 < 0 and d3 * d4 < 0


def _segment_hits(a: Vec2, b: Vec2, box: Rect) -> bool:
    """Whether segment a-b passes through the box (Liang-Barsky)."""
    enter, leave = 0.0, 1.0
    for start, end, lo, hi in ((a.x, b.x, box.x0, box.x1),
                               (a.y, b.y, box.y0, box.y1)):
        delta = end - start
        if abs(delta) < 1e-12:
            if start < lo or start > hi:
                return False
            continue
        t0, t1 = sorted(((lo - start) / delta, (hi - start) / delta))
        enter, leave = max(enter, t0), min(leave, t1)
        if enter > leave:
            return False
    return True


def _obstacles(nodes: Sequence[Diagram], split: bool = False):
    """Boxes of filled shapes and text, and segments of stroked paths.

    A stroked line is represented by its segments rather than its bounding
    box: a fitted line across the whole panel would otherwise block every
    candidate.

    With `split=True` two more lists are returned: filled polygons that are
    neither rectangles nor small (a confidence band, a shaded area, a
    violin), as `(x, y)` tuples, measured on their outline rather than their
    box -- a band's box covers most of a panel it only crosses -- and one
    flag per box, true for a data marker (a batch record or a marker-sized
    shape) and false for text, bars and plates.
    """
    boxes: list[Rect] = []
    flags: list[bool] = []
    segments: list[tuple[Vec2, Vec2]] = []
    polygons: list[tuple[tuple[float, float], ...]] = []
    for art in nodes:
        for placed in resolve(art).values():
            node = placed.diagram
            if node.prim is None:
                continue
            world = placed.world
            if isinstance(node.prim, PathPrim):
                filled = node.prim.filled and placed.style.fill not in (None, "none")
                for sub in node.prim.subpaths:
                    pts = tuple(world.apply(v) for v in sub.points)
                    if not pts:
                        continue
                    if filled:
                        hull = Rect.hull(pts)
                        if split and not _boxlike(pts, hull):
                            polygons.append(tuple((v.x, v.y) for v in pts))
                        else:
                            boxes.append(hull)
                            flags.append(_small(hull))
                    else:
                        segments.extend(zip(pts, pts[1:]))
                        if sub.closed:
                            segments.append((pts[-1], pts[0]))
            elif isinstance(node.prim, MarkerBatchPrim):
                scale = math.sqrt(abs(world.a * world.d - world.b * world.c))
                for x, y, size, _, _ in node.prim.records():
                    at = world.apply(Vec2(x, y))
                    half = size * scale / 2
                    boxes.append(Rect(at.x - half, at.y - half,
                                      at.x + half, at.y + half))
                    flags.append(True)
            elif type(node.prim).__name__.startswith("Image"):
                continue                # a raster layer covers the whole area
            elif placed.bbox is not None:
                boxes.append(placed.bbox)
                flags.append(type(node.prim).__name__ != "TextPrim"
                             and _small(placed.bbox))
    if split:
        return boxes, segments, polygons, flags
    return boxes, segments


def _small(box: Rect) -> bool:
    return box.width <= _SMALL_POLYGON and box.height <= _SMALL_POLYGON


#: A filled polygon no larger than this (mm, either side) is a marker-sized
#: shape and is kept clear of by its box.
_SMALL_POLYGON = 3.0


def _boxlike(pts: Sequence[Vec2], hull: Rect) -> bool:
    """Whether a filled outline is an axis-aligned rectangle or marker-small."""
    if hull.width <= _SMALL_POLYGON and hull.height <= _SMALL_POLYGON:
        return True
    eps = 1e-6
    return all((abs(v.x - hull.x0) < eps or abs(v.x - hull.x1) < eps)
               and (abs(v.y - hull.y0) < eps or abs(v.y - hull.y1) < eps)
               for v in pts)


class _Grid:
    """Obstacle boxes bucketed on a square grid, for dense scatters."""

    def __init__(self, boxes: Sequence[Rect], cell: float) -> None:
        self.cell = cell
        self.cells: dict[tuple[int, int], list[int]] = {}
        self.boxes = list(boxes)
        for number, box in enumerate(self.boxes):
            for key in self._keys(box):
                self.cells.setdefault(key, []).append(number)

    def _keys(self, box: Rect):
        c = self.cell
        for i in range(math.floor(box.x0 / c), math.floor(box.x1 / c) + 1):
            for j in range(math.floor(box.y0 / c), math.floor(box.y1 / c) + 1):
                yield i, j

    def near(self, box: Rect):
        seen: set[int] = set()
        for key in self._keys(box):
            for number in self.cells.get(key, ()):
                if number not in seen:
                    seen.add(number)
                    yield self.boxes[number]
