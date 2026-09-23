"""Labels for many data points at once, placed clear of marks and each other.

`Panel.label_points` names a set of points -- the highlighted genes of a
volcano plot, the named cell types of a scatter -- in one call. Each label is
placed by a deterministic search:

1. Candidate positions are eight compass directions around the point at the
   minimum clearance, then sixteen directions on rings further out, up to
   `reach` millimetres. Boxes straight above, below or beside the point are
   also tried slid along that side, so an end of the label rather than its
   middle lines up with the point.
2. A candidate is rejected if its box leaves the plot area. Otherwise it is
   scored by how much it overlaps drawn marks (kept a quarter of the theme's
   small gap away), other labelled points and labels already placed (kept
   the whole gap away), how many line segments and leaders it crosses, and
   (when it needs a leader) whether that leader crosses a label, a leader
   or another labelled point. Needing a leader costs a fixed amount on top
   of the distance.
3. The first free candidate on the first ring wins. Otherwise every
   candidate is scored with its distance from the point added, and the
   lowest total wins.

Points are labelled most crowded first. A repair pass then lifts each label
that ended on a leader or in conflict, together with the labels near its
point, places it first and puts the others back, keeping the result when it
has fewer conflicts or a lower total. A label placed off the first ring gets
a hairline leader back to its point. A label that still covers a labelled
point or another label, or whose leader crosses something, is listed as
unresolved in the node's `point_labels` note.

This works on the panel's content at the time of the call: draw the marks
first and label them last. Labels drawn by later calls are not avoided.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import (Diagram, DiagramError, MarkerBatchPrim, PathPrim, Rect,
                   Vec2, mm, resolve)
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from .axis import text_node

__all__ = ["POINT_LABEL_KIND", "LEADER_KIND", "label_points"]

#: Kind of each label text node.
POINT_LABEL_KIND = "label"
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

#: Clear space kept between a label and marks that are not labelled points,
#: as a fraction of the gap kept from labels and labelled points.
_MARK_PAD_OF_GAP = 0.25

#: Scores. Covering a mark, a labelled point or another label, or coming
#: within `spacing` of a labelled point or a label, counts `_OVERLAP_WEIGHT`
#: per square millimetre; reaching into the small pad kept round other marks
#: counts `_PAD_WEIGHT` per square millimetre. A stroked line through a label
#: counts `_CROSSING_WEIGHT`. A leader that crosses another leader, or
#: passes through a label or a labelled point, counts
#: `_LEADER_CROSSING_WEIGHT`, as does a leader passing through this label.
#: Each millimetre from the point counts `_DISTANCE_WEIGHT`, and needing a
#: leader at all counts `_LEADER_WEIGHT`, so a label next to its point that
#: grazes a pad wins over a free one out on a leader.
_OVERLAP_WEIGHT = 10.0
_PAD_WEIGHT = 1.0
_CROSSING_WEIGHT = 2.0
_LEADER_CROSSING_WEIGHT = 6.0
_DISTANCE_WEIGHT = 0.3
_LEADER_WEIGHT = 2.0

#: How many times the repair pass runs over the labels at most.
_REPAIR_ROUNDS = 3


def label_points(panel, points: Sequence[Sequence], labels: Sequence[str], *,
                 size: float | str | None = None,
                 clear: float | str | None = None,
                 reach: float | str | None = None,
                 leader: bool = True, markup: bool = False,
                 avoid: Sequence[Diagram] = (),
                 leader_style: dict | None = None, **style) -> Diagram:
    """Place one label per point. See `Panel.label_points`."""
    data = [tuple(p) for p in points]
    names = list(labels)
    if len(data) != len(names):
        raise DiagramError(
            f"label_points() got {len(names)} labels for {len(data)} points")
    if not data:
        raise DiagramError("label_points() was given no points")
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
    boxes, segments = _obstacles([*panel._content, *panel._over, *avoid])
    index_of = _Grid(boxes, max(ring * 2, 1.0))
    # The markers drawn at each labelled point (there may be two: a grey
    # cloud and a highlight drawn over it).
    own_marker: dict[int, set[int]] = {}
    radii: list[float] = []
    for number, a in enumerate(anchors):
        mine = [other for other in index_of.near(Rect(a.x, a.y, a.x, a.y))
                if abs(other.center.x - a.x) < 1e-6
                and abs(other.center.y - a.y) < 1e-6
                and other.width <= 2.5 * target]
        own_marker[number] = {id(other) for other in mine}
        # A point with a marker of its own is kept clear by that marker's
        # radius; a point with none by the default zone.
        radii.append(max((other.width / 2 for other in mine), default=target))
    targets = [Rect(a.x - r, a.y - r, a.x + r, a.y + r)
               for a, r in zip(anchors, radii)]
    nodes = [text_node(str(name), font, POINT_LABEL_KIND, markup=markup, **style)
             for name in names]
    order = sorted(range(len(data)),
                   key=lambda i: (-_crowding(i, anchors, index_of, far), i))
    placed: dict[int, Rect] = {}
    leaders: dict[int, tuple[Vec2, Vec2]] = {}
    chosen: dict[int, tuple] = {}

    def evaluate(index: int, box: Rect, distance: float,
                 first: bool) -> tuple:
        """`(total, box, leader, conflicts, distance, first, soft)` for one
        label at one position, against everything drawn and every other label
        now placed.

        `conflicts` is non-zero when the label covers a labelled point or
        another label, a stroked line crosses it, or a leader crosses it or
        is crossed. `soft` is the rest of the score: background marks
        covered or crowded, and labels or labelled points closer than
        `spacing`.
        """
        score = 0.0
        soft = 0.0
        # Everything except the point's own marker is kept `spacing` away;
        # the own marker only must not be covered, since the first ring
        # already sits `clear` from it.
        spaced = _grown(box, spacing)
        padded = _grown(box, _MARK_PAD_OF_GAP * spacing)
        # Leaders pass labels with half the gap to spare.
        passed = _grown(box, spacing / 2)
        for other in index_of.near(spaced):
            if id(other) in own_marker[index]:
                continue
            # Labelled points' markers are in `targets` below, kept the full
            # gap away; other marks only a small pad, so a label can still
            # sit in a gap in a dense cloud.
            soft += _OVERLAP_WEIGHT * _overlap(box, other)
            soft += _PAD_WEIGHT * _overlap(padded, other)
        # Covering a labelled point or another label is a conflict; coming
        # closer than `spacing` to one is not, but is scored as heavily, so
        # the gap is kept whenever there is room for it.
        for number, other in enumerate(targets):
            score += _OVERLAP_WEIGHT * _overlap(box, other)
            if number != index:
                soft += _OVERLAP_WEIGHT * (_overlap(spaced, other)
                                           - _overlap(box, other))
        for number, other in placed.items():
            if number != index:
                score += _OVERLAP_WEIGHT * _overlap(box, other)
                soft += _OVERLAP_WEIGHT * (_overlap(spaced, other)
                                           - _overlap(box, other))
        score += _CROSSING_WEIGHT * sum(
            1 for a, b in segments if _segment_hits(a, b, box))
        score += _LEADER_CROSSING_WEIGHT * sum(
            1 for number, (a, b) in leaders.items()
            if number != index and _segment_hits(a, b, passed))
        line = None
        if not first and leader:
            line = _leader(anchors[index], box, radii[index] * _STANDOFF)
            if line is not None:
                score += _LEADER_CROSSING_WEIGHT * sum(
                    1 for number, other in placed.items()
                    if number != index
                    and _segment_hits(line[0], line[1],
                                      _grown(other, spacing / 2)))
                score += _LEADER_CROSSING_WEIGHT * sum(
                    1 for number, (a, b) in leaders.items()
                    if number != index
                    and _segments_cross(line[0], line[1], a, b))
                score += _LEADER_CROSSING_WEIGHT * sum(
                    1 for number, other in enumerate(targets)
                    if number != index
                    and _segment_hits(line[0], line[1], other))
        total = score + soft + _DISTANCE_WEIGHT * distance
        if line is not None:
            total += _LEADER_WEIGHT
        return total, box, line, score, distance, first, soft

    def search(index: int) -> tuple:
        """The best position for one label, as `evaluate` reports it."""
        width, height = nodes[index].bbox.width, nodes[index].bbox.height
        best = None
        for distance, angle, slide, first in _candidates(
                gap + radii[index], ring, far):
            box = _box_at(anchors[index], angle, distance, width, height, slide)
            if not _within(box, area):
                continue
            here = evaluate(index, box, distance, first)
            if best is None or here[0] < best[0]:
                best = here
            if first and here[3] == 0.0 and here[6] == 0.0:
                break
        if best is None:
            raise DiagramError(
                f"label {names[index]!r} does not fit inside the plot area; "
                "enlarge the panel or shorten the label")
        return best

    def put(index: int, best: tuple) -> None:
        chosen[index] = best
        placed[index] = best[1]
        leaders.pop(index, None)
        if best[2] is not None:
            leaders[index] = best[2]

    def take(index: int) -> None:
        del chosen[index]
        del placed[index]
        leaders.pop(index, None)

    for index in order:
        put(index, search(index))

    # Repair: a label that ended on a leader or in conflict may have lost its
    # place next to the point to a neighbour placed before it. Lift it and
    # the labels near its point, place it first, put the others back, and
    # keep the result if the group has fewer conflicts, or as many and a
    # lower summed cost (each label scored against all the others). Rounds
    # repeat while something improves, up to `_REPAIR_ROUNDS`.
    def standing(group: Sequence[int]) -> tuple[int, float]:
        scored = [evaluate(i, chosen[i][1], chosen[i][4], chosen[i][5])
                  for i in group]
        return sum(1 for s in scored if s[3] > 0), sum(s[0] for s in scored)

    for _ in range(_REPAIR_ROUNDS):
        improved = False
        seeds = [i for i in chosen if i in leaders or chosen[i][3] > 0]
        for index in sorted(seeds, key=lambda i: (-chosen[i][0], i)):
            here = anchors[index]
            reach_box = Rect(here.x - far, here.y - far,
                             here.x + far, here.y + far)
            group = [index, *sorted((i for i in chosen if i != index
                                     and _overlap(placed[i], reach_box) > 0),
                                    key=order.index)]
            before = {i: chosen[i] for i in group}
            conflicts, total = standing(group)
            for i in group:
                take(i)
            for i in group:
                put(i, search(i))
            new_conflicts, new_total = standing(group)
            if (new_conflicts, new_total) < (conflicts, total - 1e-9):
                improved = True
                continue
            for i in group:
                take(i)
            for i in group:
                put(i, before[i])
        if not improved:
            break

    # Scored again now that every label is down: a label placed early did not
    # see the ones placed after it.
    unresolved = [i for i in range(len(data))
                  if evaluate(i, chosen[i][1], chosen[i][4], chosen[i][5])[3] > 0]
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
        "unresolved": [names[i] for i in sorted(unresolved)],
    }
    return node


def _candidates(start: float, ring: float, far: float):
    """`(distance, page angle, slide, first ring?)` in search order.

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


def _obstacles(nodes: Sequence[Diagram]) -> tuple[list[Rect], list[tuple[Vec2, Vec2]]]:
    """Boxes of filled shapes and text, and segments of stroked paths.

    A stroked line is represented by its segments rather than its bounding
    box: a fitted line across the whole panel would otherwise block every
    candidate.
    """
    boxes: list[Rect] = []
    segments: list[tuple[Vec2, Vec2]] = []
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
                        boxes.append(Rect.hull(pts))
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
            elif type(node.prim).__name__.startswith("Image"):
                continue                # a raster layer covers the whole area
            elif placed.bbox is not None:
                boxes.append(placed.bbox)
    return boxes, segments


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
