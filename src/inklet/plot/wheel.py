"""Radar charts and pie (or donut) charts on a `PolarPanel`.

Both divide a whole turn into equal or proportional parts, so both need a
panel whose theta domain is a whole turn. Angles follow the panel's own
`zero` and `winding`: `inklet.polar(20, zero="up", winding="cw")` starts the
first spoke or slice at twelve o'clock and runs clockwise, which is how both
charts are usually drawn.

**Radar.** `radar_spokes(panel, n)` returns the theta of each of `n` equally
spaced spokes, the first at the start of the domain. `radar` draws one closed
polygon through `(spoke, value)` points: straight chords, since the space
between two categories has no values. `radar_grid` draws the rings (polygons
by default, so the rings are parallel to the data's edges) and the spokes
under the data, and writes the category names outside the rim.

**Pie.** `pie` draws one sector per value from the hole to the rim, each
spanning its share of the turn, separated by thin paper-coloured lines.
Labels are written inside a slice when their box fits in it with a margin,
in ink or paper by contrast with the slice; otherwise outside the rim in the
theme ink. An outside label that would overlap another label, a leader or
a breakout connector moves out or round the rim to the nearest clear spot,
and gets a hairline leader back to its slice when it ends up away from it.
A donut is `inklet.polar(radius, hole=...)`.

**Breakout bar.** `breakout` expands one or more adjacent slices of the pie
into a stacked bar beside the disc, with two connector lines from the rim at
the slices' outer edges to the bar's top and bottom corners. The bar is
stacked from the top in the order the parts are given, and each part is
labelled beside the bar with its share of the bar.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, Rect, Vec2, mm
from ..draw.coords import active_theme, as_drawn
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND, marker as make_marker
from ..draw.shapes import sector as draw_sector
from ..themes.color import mix
from . import marks as _marks
from .axis import AXIS_KIND, TICK_LABEL_KIND, _PAD_OF_TYPE, _TICK_OF_TYPE, text_node
from ..themes import contrast_ratio
from .bar_labels import _ink_on
from .furniture import GRID_KIND
from .scale import format_number

__all__ = ["RING_SHAPES", "radar_spokes", "radar", "radar_grid",
           "ring_value_items", "pie",
           "pie_label_texts", "breakout", "breakout_frame",
           "breakout_connectors", "breakout_turn", "BREAKOUT_SIDES"]

#: Accepted values of `radar_grid(rings=)`'s shape.
RING_SHAPES = ("polygon", "circle")

#: Radar fill opacity: light enough that two or three overlapping series and
#: the grid under them remain visible.
_RADAR_FILL_OPACITY = 0.16

#: Radar vertex dot, as a fraction of the type size.
_VERTEX_OF_TYPE = 0.42

#: Margin kept between an inside pie label and its slice's edges, as a
#: fraction of the label size.
_SLICE_MARGIN_OF_TYPE = 0.2


def _full(panel, what: str) -> None:
    if not panel.theta.full:
        raise DiagramError(
            f"{what}() needs a panel whose theta domain is a whole turn")


def radar_spokes(panel, count: int) -> tuple[float, ...]:
    """The theta of `count` equally spaced spokes, the first at the start of
    the theta domain."""
    if count < 3:
        raise DiagramError(f"a radar chart needs at least 3 spokes, got {count}")
    low, high = panel.theta.domain
    step = (high - low) / count
    return tuple(low + k * step for k in range(count))


def radar(panel, values: Sequence[float], *, color: str | None = None,
          fill: bool = True, markers: bool = True,
          size: float | str | None = None, **style) -> Diagram:
    """One closed polygon through a value on each spoke. See
    `PolarPanel.radar`."""
    _full(panel, "radar")
    data = [float(v) for v in values]
    spokes = radar_spokes(panel, len(data))
    theme = active_theme()
    ink = color or theme.ink
    points = [panel.point(t, v) for t, v in zip(spokes, data)]
    parts: list = []
    if fill:
        parts.append(polyline(points, closed=True, filled=True, kind=MARK_KIND,
                              fill=ink, fill_opacity=_RADAR_FILL_OPACITY,
                              stroke="none"))
    line = {"stroke": ink, "stroke_width": theme.stroke,
            "stroke_linejoin": "round"}
    line.update(style)
    parts.append(polyline(points, closed=True, kind=MARK_LINE_KIND, **line))
    if markers:
        dot = _VERTEX_OF_TYPE * theme.font_size if size is None else mm(size)
        parts.extend((p, make_marker("circle", dot, fill=ink)) for p in points)
    return draw_place(parts, origin=(0, 0), kind="radar")


def radar_grid(panel, categories: Sequence[str], *, rings=None,
               shape: str = "polygon", labels: bool = True,
               values: bool = False, levels_out: list | None = None,
               **style) -> tuple[list[Diagram], Diagram | None, list]:
    """Rings, spokes and category names for a radar chart.

    Returns `(grid lines, label node or None, [(page angle, box)])`. With
    `values=True` the label node also holds each ring's value, on the gap
    after the first spoke; `PolarPanel.radar_grid` instead records the rings
    and places their values with `ring_values` when the panel is built, once
    the data is known.
    """
    _full(panel, "radar_grid")
    if shape not in RING_SHAPES:
        raise DiagramError(
            f"radar_grid shape is one of {', '.join(RING_SHAPES)}, not {shape!r}")
    names = [str(c) for c in categories]
    spokes = radar_spokes(panel, len(names))
    if rings is None:
        levels = list(panel.r.ticks(4))
    elif isinstance(rings, int):
        levels = list(panel.r.ticks(rings))
    else:
        levels = [float(v) for v in rings]
    top = max(panel.r.domain)
    if all(abs(v - top) > 1e-9 for v in levels):
        levels.append(top)
    drawn: list[float] = []
    lines: list[Diagram] = []
    for value in levels:
        distance = panel.r.map(value)
        if distance <= max(panel.hole, 1e-6) + 1e-9 or distance > panel.radius + 1e-9:
            continue
        if shape == "polygon":
            ring = [panel.point(t, value) for t in spokes]
        else:
            ring = [Vec2(math.cos(a) * distance, math.sin(a) * distance)
                    for a in (2 * math.pi * k / 96 for k in range(96))]
        lines.append(polyline(ring, closed=True, kind=GRID_KIND, **style))
        drawn.append(value)
    if levels_out is not None:
        levels_out.extend(drawn)
    for t in spokes:
        lines.append(polyline((_along(panel, t, panel.hole),
                               _along(panel, t, panel.radius)),
                              kind=GRID_KIND, **style))
    if not labels and not values:
        return lines, None, []
    theme = active_theme()
    # Clear of the rim by what a theta axis's tick and pad would take, so a
    # vertex on the rim does not touch the name beyond it.
    gap = (_TICK_OF_TYPE + _PAD_OF_TYPE) * theme.font_size
    items: list = []
    ring_boxes: list = []
    if values:
        items.extend(ring_value_items(panel, drawn, len(names), shape, ())[0])
    for t, name in zip(spokes, names if labels else ()):
        node = text_node(name, theme.font_size_small, TICK_LABEL_KIND, markup=False)
        angle = panel.angle(t)
        centre = _outward_centre(node.bbox, panel.radius + gap, angle)
        items.append((centre, node))
        box = node.bbox
        ring_boxes.append((angle, Rect(box.x0 + centre.x, box.y0 + centre.y,
                                       box.x1 + centre.x, box.y1 + centre.y)))
    node = draw_place(items, origin=(0, 0), kind=AXIS_KIND)
    return lines, node, ring_boxes


#: The paper halo round a ring value, as a fraction of the type size: the
#: stroke painted under the glyphs, half of it outside them.
_RING_HALO_OF_TYPE = 0.3

#: The clear space a ring value keeps from the data's lines and dots, as a
#: fraction of the type size.
_RING_CLEAR_OF_TYPE = 0.25


def ring_value_items(panel, levels: Sequence[float], count: int, shape: str,
                     data: Sequence[Sequence[Vec2]]) -> tuple[list, dict]:
    """Ring values of a radar grid of `count` spokes, as `(items, note)`.

    The values go up one gap between two spokes, each where its ring crosses
    the gap's bisector, in the theme ink on a paper halo. From the outermost
    ring inward, a value is left out when it would touch the value above it,
    or come within `_RING_CLEAR_OF_TYPE` of a line or vertex dot of the
    closed polygons in `data` (panel millimetres). The gap that writes the
    most values wins, then the one whose values keep furthest from the data,
    then the one that follows the first spoke. `note` records the gap (its
    index: 0 follows the first spoke), the values written and the smallest
    clearance to the data in millimetres (None without data)."""
    theme = active_theme()
    spokes = radar_spokes(panel, count)
    step = (panel.theta.domain[1] - panel.theta.domain[0]) / count
    size = theme.font_size_small
    halo = _RING_HALO_OF_TYPE * size
    clear = theme.gap("xs") * 0.5
    need = _RING_CLEAR_OF_TYPE * size
    # A vertex dot's radius and half a data stroke, which the clearance is
    # measured beyond.
    dot = _VERTEX_OF_TYPE * theme.font_size / 2
    line = theme.stroke / 2
    nodes = [(value, text_node(format_number(value), size, TICK_LABEL_KIND,
                               markup=False, halo=halo, text_fill=theme.ink))
             for value in sorted(levels, reverse=True)]
    squeeze = math.cos(math.pi / count) if shape == "polygon" else 1.0
    points = [p for series in data for p in series]
    edges = [(a, b) for series in data
             for a, b in zip(series, list(series[1:]) + list(series[:1]))]

    def room(box: Rect) -> float | None:
        if not edges:
            return None
        near = min(_box_segment_distance(box, a, b) for a, b in edges) - line
        for p in points:
            dx = max(box.x0 - p.x, 0.0, p.x - box.x1)
            dy = max(box.y0 - p.y, 0.0, p.y - box.y1)
            near = min(near, math.hypot(dx, dy) - dot)
        return max(near, 0.0)

    best = None
    for gap in range(count):
        radians = math.radians(panel.angle(spokes[gap] + step / 2))
        ux, uy = math.cos(radians), math.sin(radians)
        items: list = []
        kept: list[Rect] = []
        written: list[float] = []
        rooms: list[float] = []
        for value, node in nodes:
            distance = panel.r.map(value) * squeeze
            if distance <= max(panel.hole, 1e-6) + 1e-9:
                continue
            at = Vec2(ux * distance, uy * distance) - node.bbox.center
            box = _moved(node.bbox, at)
            if any(_touch(box, other, clear) for other in kept):
                continue
            space = room(box)
            if space is not None and space < need:
                continue
            kept.append(box)
            written.append(value)
            items.append((at, node))
            if space is not None:
                rooms.append(space)
        least = min(rooms) if rooms else None
        score = (len(written), least if least is not None else 0.0, -gap)
        if best is None or score > best[0]:
            best = (score, items, {"gap": gap, "values": written,
                                   "clearance": least})
        if not edges:
            break
    return best[1], best[2]


def _box_segment_distance(box: Rect, a: Vec2, b: Vec2) -> float:
    """The shortest distance between a box and the segment a-b (0 when they
    meet)."""
    if _segment_hits(box, a, b):
        return 0.0
    corners = [Vec2(box.x0, box.y0), Vec2(box.x1, box.y0),
               Vec2(box.x1, box.y1), Vec2(box.x0, box.y1)]
    best = min(_point_segment_distance(c, a, b) for c in corners)
    for p in (a, b):
        dx = max(box.x0 - p.x, 0.0, p.x - box.x1)
        dy = max(box.y0 - p.y, 0.0, p.y - box.y1)
        best = min(best, math.hypot(dx, dy))
    return best


def _point_segment_distance(p: Vec2, a: Vec2, b: Vec2) -> float:
    dx, dy = b.x - a.x, b.y - a.y
    length = dx * dx + dy * dy
    t = 0.0 if length < 1e-18 else max(0.0, min(1.0, ((p.x - a.x) * dx
                                                    + (p.y - a.y) * dy) / length))
    return math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy)


def _along(panel, theta: float, distance: float) -> Vec2:
    radians = math.radians(panel.angle(theta))
    return Vec2(math.cos(radians) * distance, math.sin(radians) * distance)


def _outward_centre(box: Rect, distance: float, degrees: float) -> Vec2:
    """Where a box's centre goes so that its edge touches the point
    `distance` out along `degrees` (page degrees)."""
    radians = math.radians(degrees)
    ux, uy = math.cos(radians), math.sin(radians)
    reaches = []
    if abs(ux) > 1e-12:
        reaches.append(box.width / 2 / abs(ux))
    if abs(uy) > 1e-12:
        reaches.append(box.height / 2 / abs(uy))
    reach = min(reaches) if reaches else 0.0
    # The box's own centre may not be its origin; correct for that.
    offset = box.center
    return Vec2(ux * (distance + reach) - offset.x,
                uy * (distance + reach) - offset.y)


def pie_label_texts(labels, values: Sequence[float]) -> list[str | None]:
    """One string (or None) per slice.

    `"percent"` writes each share as a whole percentage; `"value"` writes the
    value with `format_number`; a format string containing `{}` receives the
    value and may name `{share}` (a fraction) as well; a callable receives
    `(value, share)`; a sequence gives the strings directly.
    """
    total = sum(values)
    shares = [v / total for v in values]
    if labels == "percent":
        return [f"{round(100 * s):d}%" for s in shares]
    if labels == "value":
        return [format_number(v) for v in values]
    if isinstance(labels, str):
        if "{" not in labels:
            raise DiagramError(
                'pie(labels=) is "percent", "value", a format such as '
                f'"{{share:.0%}}", a callable or a sequence; got {labels!r}')
        return [labels.format(v, share=s) for v, s in zip(values, shares)]
    if callable(labels):
        return [None if (text := labels(v, s)) is None else str(text)
                for v, s in zip(values, shares)]
    given = list(labels)
    if len(given) != len(values):
        raise DiagramError(
            f"pie(labels=) has {len(given)} labels for {len(values)} slices")
    return [None if item is None else str(item) for item in given]


def pie(panel, values: Sequence[float], *, colors=None, labels="percent",
        label_options: Mapping | None = None, separator: bool = True,
        avoid: Sequence[tuple[Vec2, Vec2]] = (), avoid_boxes: Sequence[Rect] = (),
        **style) -> tuple[Diagram, tuple[str, ...], dict]:
    """Sectors that divide the turn in proportion to `values`. See
    `PolarPanel.pie`.

    `avoid` holds line segments and `avoid_boxes` rectangles, in panel
    millimetres, that labels placed outside the rim keep clear of; a
    breakout passes its connectors and its bar. Returns `(node, fills,
    note)`, where `note` records which labels went inside and which outside,
    and under `"crossing"` any outside label that could not clear `avoid`.
    """
    _full(panel, "pie")
    data = [float(v) for v in values]
    if not data:
        raise DiagramError("pie() was given no values")
    if any(v < 0 or math.isnan(v) for v in data):
        raise DiagramError("pie() values must be zero or positive")
    total = sum(data)
    if total <= 0:
        raise DiagramError("pie() values sum to zero")
    theme = active_theme()
    fills = _marks.series_colors(colors, len(data)) if colors is not None \
        else tuple(theme.color(k) for k in range(len(data)))
    if len(fills) != len(data):
        raise DiagramError(f"pie() has {len(fills)} colours for {len(data)} slices")
    options = dict(label_options or {})
    unknown = set(options) - {"size", "fill", "markup", "font_weight"}
    if unknown:
        raise DiagramError(
            "label_options accepts size, fill, markup and font_weight; "
            f"got {', '.join(sorted(unknown))}")
    size = theme.font_size_small if options.get("size") is None else mm(options["size"])
    texts = ([None] * len(data) if labels is None
             else pie_label_texts(labels, data))
    style.setdefault("stroke", theme.paper if separator else "none")
    style.setdefault("stroke_width", theme.stroke)
    low, high = panel.theta.domain
    span = high - low
    inner, outer = panel.hole, panel.radius
    wedges: list = []
    inside: list = []
    outside: list = []
    note = {"inside": [], "outside": [], "angles": [], "values": data,
            "crossing": []}
    start = low
    for index, (value, fill) in enumerate(zip(data, fills)):
        end = start + span * value / total
        a0, a1 = sorted((panel.angle(start), panel.angle(end)))
        note["angles"].append((a0, a1))
        if value <= 0:
            continue
        if a1 - a0 >= 360.0 - 1e-9:
            # A single slice is the whole disc: two halves, one outline.
            wedges.append(as_drawn(draw_sector(outer, a0, a0 + 180, inner=inner,
                                               kind=MARK_KIND, fill=fill,
                                               stroke="none")))
            wedges.append(as_drawn(draw_sector(outer, a0 + 180, a1, inner=inner,
                                               kind=MARK_KIND, fill=fill,
                                               stroke="none")))
        else:
            wedges.append(as_drawn(draw_sector(outer, a0, a1, inner=inner,
                                               kind=MARK_KIND, fill=fill,
                                               **style)))
        text = texts[index]
        if text:
            weight = options.get("font_weight")
            extra = {} if weight is None else {"font_weight": weight}
            node = text_node(text, size, TICK_LABEL_KIND,
                             markup=bool(options.get("markup", False)), **extra)
            mid = (a0 + a1) / 2
            middle = (inner + outer) / 2 if inner > 0 else outer * 0.62
            centre = Vec2(math.cos(math.radians(mid)) * middle,
                          math.sin(math.radians(mid)) * middle)
            margin = _SLICE_MARGIN_OF_TYPE * size
            box = _moved(node.bbox, centre - node.bbox.center)
            if _fits_slice(box, inner, outer, a0, a1, margin):
                ink = options.get("fill") or _ink_on(fill, theme)
                inside.append((centre - node.bbox.center, node.styled(text_fill=ink)))
                note["inside"].append(index)
            else:
                outside.append((index, mid, node, a0, a1))
        start = end
    gap = _PAD_OF_TYPE * theme.font_size
    clear = theme.gap("xs") * 0.5
    slice_boxes = [w.bbox for w in wedges]

    def place(order):
        """Outside labels placed one by one in `order`, with a score: the
        labels that could not clear, then the total displacement."""
        placed_boxes: list[Rect] = []
        placed_leaders: list[tuple[Vec2, Vec2]] = []
        spots = {}
        failed = 0.0
        moved = 0.0
        for k in order:
            index, mid, node, a0, a1 = outside[k]
            at, box, crossing, leader = _outside_spot(
                node, mid, a0, a1, outer, gap, size, placed_boxes, clear,
                avoid, avoid_boxes, slice_boxes, placed_leaders)
            if crossing:
                clash = any(_touch(box, other, 0.0) for other in placed_boxes)
                failed += 2 if clash else 1
            placed_boxes.append(box)
            if leader is not None:
                placed_leaders.append(leader)
            first = _outward_centre(node.bbox, outer + gap, mid)
            moved += math.hypot(at.x - first.x, at.y - first.y)
            spots[k] = (at, crossing, leader)
        return (failed, moved), spots

    # Round the rim in slice order first; a run of small slices can box its
    # last labels in, so the reverse and middle-out orders are tried when a
    # label does not clear, and the order that clears most labels is kept.
    count = len(outside)
    score, spots = place(range(count))
    if score[0] > 0 and count > 1:
        middle = sorted(range(count), key=lambda k: (abs(k - (count - 1) / 2), k))
        for order in (range(count - 1, -1, -1), middle):
            other = place(order)
            if other[0] < score:
                score, spots = other
    labels_out: list = []
    leader_lines: list = []
    note["leaders"] = []
    ink = options.get("fill") or theme.ink
    for k, (index, mid, node, a0, a1) in enumerate(outside):
        at, crossing, leader = spots[k]
        if crossing:
            note["crossing"].append(index)
        if leader is not None:
            note["leaders"].append(index)
            leader_lines.append(polyline(leader, kind=MARK_LINE_KIND,
                                         stroke=ink, stroke_width=theme.hairline))
        labels_out.append((at, node.styled(text_fill=ink)))
        note["outside"].append(index)
    parts = [draw_place(wedges, origin=(0, 0), kind="pie")]
    if leader_lines:
        parts.append(draw_place(leader_lines, origin=(0, 0), kind="pie-leaders"))
    if inside or labels_out:
        parts.append(draw_place(inside + labels_out, origin=(0, 0),
                                kind=AXIS_KIND))
    node = draw_place(parts, origin=(0, 0), kind="pie")
    node.notes["pie_labels"] = note
    return node, tuple(fills), note


#: An outside pie label farther than this from its slice, beyond the usual
#: rim gap, gets a leader line back to the slice, as a fraction of the label
#: size. Nearer labels read as belonging to the slice they face.
_LEADER_AFTER_OF_TYPE = 0.45

#: Extra cost of a spot that needs a leader, in label sizes of displacement:
#: a label next to its slice beats one out on a leader unless that one is
#: much closer to where the label wanted to be.
_LEADER_COST_OF_TYPE = 1.5

#: How far a label may move from its first spot, in label sizes: radially
#: and along the rim.
_OUT_REACH_OF_TYPE = 4.0
_AROUND_REACH_OF_TYPE = 6.0


def _outside_spot(node: Diagram, mid: float, a0: float, a1: float,
                  outer: float, gap: float, size: float, placed: Sequence[Rect],
                  clear: float, avoid: Sequence[tuple[Vec2, Vec2]],
                  avoid_boxes: Sequence[Rect], slices: Sequence[Rect],
                  leaders: Sequence[tuple[Vec2, Vec2]] = (),
                  ) -> tuple[Vec2, Rect, bool, tuple[Vec2, Vec2] | None]:
    """Where an outside pie label goes, as `(offset, box, crossing, leader)`.

    The label first tries `gap` beyond the rim `outer` on the slice's middle
    angle. If that spot meets a label already `placed`, a leader, a segment
    of `avoid` or a box of `avoid_boxes`, spots further out (up to three type
    sizes) and round the rim (up to four type sizes of arc) are tried, and
    the one nearest the first spot that clears everything wins; a spot that
    needs a leader counts one and a half type sizes more. A label placed
    away from its slice (outside its angles, or more than about half a type
    size beyond the usual gap) gets `leader`, a segment from the slice's rim
    to the nearest point of the label, which must itself cross no label,
    leader, `avoid` segment or box and must leave the rim outward. The lint
    measures a slice by its box (`slices`), so a moved label also either
    keeps the lint's clearance from each box or overlaps it. If nothing
    clears, the first spot is kept without a leader and `crossing` is
    True."""
    from ..diagnostics.rules import DEFAULT_MIN_CLEARANCE_MM as keep

    def free_of_labels(box: Rect) -> bool:
        return (not any(_touch(box, other, clear) for other in placed)
                and not any(_segment_hits(_grown(box, clear), a, b)
                            for a, b in leaders))

    def free_of_avoid(box: Rect) -> bool:
        grown = _grown(box, keep)
        return (not any(_segment_hits(grown, a, b) for a, b in avoid)
                and not any(_touch(box, other, keep) for other in avoid_boxes))

    def free_of_rim(box: Rect) -> bool:
        x = min(max(0.0, box.x0), box.x1)
        y = min(max(0.0, box.y0), box.y1)
        return (math.hypot(x, y) >= outer + keep
                and not any(_touch(box, other, keep) and not _touch(box, other, 0.0)
                            for other in slices))

    def leader_for(box: Rect) -> tuple[Vec2, Vec2] | None:
        """The leader a label at `box` needs, or None when it sits by its
        slice. Returns False-like `()` when a leader is needed but cannot be
        drawn cleanly."""
        centre = box.center
        bearing = math.degrees(math.atan2(centre.y, centre.x))
        while bearing < a0 - 180:
            bearing += 360
        while bearing > a0 + 180:
            bearing -= 360
        inside = a0 <= bearing <= a1
        anchor_angle = math.radians(min(max(bearing, a0), a1))
        ux, uy = math.cos(anchor_angle), math.sin(anchor_angle)
        anchor = Vec2(ux * outer, uy * outer)
        near = Vec2(min(max(anchor.x, box.x0), box.x1),
                    min(max(anchor.y, box.y0), box.y1))
        dx, dy = near.x - anchor.x, near.y - anchor.y
        length = math.hypot(dx, dy)
        if inside and length <= gap + _LEADER_AFTER_OF_TYPE * size:
            return None
        if length < 1e-9 or (dx * ux + dy * uy) / length < 0.35:
            return ()
        segment = (anchor, near)
        for other in placed:
            if _segment_hits(_grown(other, clear * 0.5), anchor, near):
                return ()
        for a, b in leaders:
            if _segments_cross(anchor, near, a, b):
                return ()
        for a, b in avoid:
            if _segments_cross(anchor, near, a, b):
                return ()
        for other in avoid_boxes:
            if _segment_hits(_grown(other, keep * 0.5), anchor, near):
                return ()
        return segment

    at = _outward_centre(node.bbox, outer + gap, mid)
    box = _moved(node.bbox, at)
    first = box.center
    if free_of_labels(box) and ((not avoid and not avoid_boxes) or free_of_avoid(box)):
        return at, box, False, None
    reach = outer + gap

    def candidates(scale: float):
        radial = int(round(_OUT_REACH_OF_TYPE * 3 * scale))
        around = int(round(_AROUND_REACH_OF_TYPE * 3 * scale))
        scored = []
        for step in range(radial + 1):
            distance = reach + step * size / 3
            for turn in range(-around, around + 1):
                if step == 0 and turn == 0:
                    continue
                degrees = mid + math.degrees(turn * size / 3 / distance)
                spot = _outward_centre(node.bbox, distance, degrees)
                moved = _moved(node.bbox, spot)
                centre = moved.center
                scored.append((math.hypot(centre.x - first.x, centre.y - first.y),
                               spot, moved))
        scored.sort(key=lambda item: item[0])
        return scored

    def search(scored, strict: bool):
        best = None
        for cost, spot, moved in scored:
            if best is not None and cost >= best[0]:
                break
            if not (free_of_labels(moved) and free_of_rim(moved)
                    and (not strict or free_of_avoid(moved))):
                continue
            line = leader_for(moved)
            if line == ():
                continue
            total = cost + (_LEADER_COST_OF_TYPE * size if line else 0.0)
            if best is None or total < best[0]:
                best = (total, spot, moved, line)
        return best

    near = candidates(1.0)
    best = search(near, True)
    if best is None:
        far = candidates(2.0)
        best = search(far, True)
        if best is None:
            # Nothing clears the connectors: keep the label clear of the
            # other labels at least, and report it.
            best = search(far, False)
            if best is not None:
                return best[1], best[2], True, best[3]
    if best is not None:
        return best[1], best[2], False, best[3]
    # Out along the slice's middle until clear of the other labels.
    for _ in range(40):
        at = _outward_centre(node.bbox, reach, mid)
        box = _moved(node.bbox, at)
        if not any(_touch(box, other, clear) for other in placed):
            break
        reach += 0.3 * size
    line = leader_for(box)
    return at, box, True, (line or None)


def _grown(box: Rect, pad: float) -> Rect:
    return Rect(box.x0 - pad, box.y0 - pad, box.x1 + pad, box.y1 + pad)


def _segments_cross(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> bool:
    """Whether segments a-b and c-d cross (touching ends do not count)."""
    def side(p, q, r):
        return (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)
    d1, d2 = side(c, d, a), side(c, d, b)
    d3, d4 = side(a, b, c), side(a, b, d)
    return d1 * d2 < 0 and d3 * d4 < 0


def _segment_hits(box: Rect, a: Vec2, b: Vec2) -> bool:
    """Whether the segment from `a` to `b` passes through `box`."""
    low, high = 0.0, 1.0
    dx, dy = b.x - a.x, b.y - a.y
    for p, q in ((-dx, a.x - box.x0), (dx, box.x1 - a.x),
                 (-dy, a.y - box.y0), (dy, box.y1 - a.y)):
        if abs(p) < 1e-12:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            low = max(low, t)
        else:
            high = min(high, t)
        if low > high:
            return False
    return True


def _moved(box: Rect, by: Vec2) -> Rect:
    return Rect(box.x0 + by.x, box.y0 + by.y, box.x1 + by.x, box.y1 + by.y)


def _touch(a: Rect, b: Rect, pad: float) -> bool:
    return (a.x0 - pad < b.x1 and b.x0 - pad < a.x1
            and a.y0 - pad < b.y1 and b.y0 - pad < a.y1)


def _fits_slice(box: Rect, inner: float, outer: float, a0: float, a1: float,
                margin: float) -> bool:
    """Whether every corner of `box` lies inside the annular sector, at least
    `margin` millimetres from its straight edges and arcs."""
    for x in (box.x0, box.x1):
        for y in (box.y0, box.y1):
            radius = math.hypot(x, y)
            if radius > outer - margin or radius < inner + margin:
                return False
            angle = math.degrees(math.atan2(y, x))
            # Bring the corner's bearing into the slice's own turn.
            while angle < a0 - 180:
                angle += 360
            while angle > a0 + 180:
                angle -= 360
            if angle < a0 or angle > a1:
                if not (a1 - a0 > 180 and (angle + 360 <= a1)):
                    return False
            # Distance to each straight edge.
            for edge in (a0, a1):
                ex, ey = math.cos(math.radians(edge)), math.sin(math.radians(edge))
                if abs(x * ey - y * ex) < margin and x * ex + y * ey > 0:
                    return False
    return True


#: Breakout bar geometry, as fractions of the pie radius: the bar's width,
#: and the space between the rim and the bar that the connectors cross.
_BREAKOUT_WIDTH_OF_RADIUS = 0.22
_BREAKOUT_GAP_OF_RADIUS = 0.75

#: Sides a breakout bar may stand on.
BREAKOUT_SIDES = ("right", "left")


def breakout(panel, pie_note: Mapping, slices, parts=None, *, fills=(),
             colors=None, labels="percent", label_options: Mapping | None = None,
             side: str = "right", width: float | str | None = None,
             height: float | str | None = None, gap: float | str | None = None,
             title: str | None = None, connector: Mapping | None = None,
             separator: bool = True,
             **style) -> tuple[Diagram, tuple[str, ...], dict]:
    """A stacked bar that expands slices of a pie. See `PolarPanel.breakout`.

    `pie_note` is the `pie_labels` note of the pie drawn on `panel`; it holds
    each slice's page angles and value, and `fills` its colours. Returns
    `(node, fills, note)`.
    """
    if side not in BREAKOUT_SIDES:
        raise DiagramError(
            f"breakout side is one of {', '.join(BREAKOUT_SIDES)}, not {side!r}")
    angles = list(pie_note["angles"])
    values = list(pie_note["values"])
    chosen = [slices] if isinstance(slices, int) else [int(i) for i in slices]
    if not chosen:
        raise DiagramError("breakout() was given no slices")
    if any(i < 0 or i >= len(angles) for i in chosen):
        raise DiagramError(
            f"breakout() slices must be between 0 and {len(angles) - 1}, "
            f"got {chosen}")
    ordered = sorted(set(chosen))
    if ordered != list(range(ordered[0], ordered[-1] + 1)):
        raise DiagramError(f"breakout() slices must be adjacent, got {chosen}")
    theme = active_theme()
    if parts is None:
        data = [values[i] for i in ordered]
        given = colors if colors is not None else [fills[i] for i in ordered]
    else:
        data = [float(v) for v in parts]
        given = colors
    if not data or any(v < 0 or math.isnan(v) for v in data):
        raise DiagramError("breakout() parts must be zero or positive")
    total = sum(data)
    if total <= 0:
        raise DiagramError("breakout() parts sum to zero")
    if given is not None:
        colours = _marks.series_colors(given, len(data))
    else:
        colours = _shades(fills[ordered[0]], len(data), theme)
    if len(colours) != len(data):
        raise DiagramError(
            f"breakout() has {len(colours)} colours for {len(data)} parts")
    options = dict(label_options or {})
    unknown = set(options) - {"size", "fill", "markup", "font_weight"}
    if unknown:
        raise DiagramError(
            "label_options accepts size, fill, markup and font_weight; "
            f"got {', '.join(sorted(unknown))}")
    size = theme.font_size_small if options.get("size") is None else mm(options["size"])
    _, top, bar_height, x0, x1 = breakout_frame(panel, side=side, width=width,
                                                height=height, gap=gap)
    # The segments, stacked downward from the top of the bar.
    segments: list = []
    spans: list[tuple[float, float]] = []
    edge = top
    for value, fill in zip(data, colours):
        extent = bar_height * value / total
        spans.append((edge, edge + extent))
        if extent > 0:
            segments.append(polyline(
                (Vec2(x0, edge), Vec2(x1, edge), Vec2(x1, edge + extent),
                 Vec2(x0, edge + extent)), closed=True, filled=True,
                kind=MARK_KIND, fill=fill, stroke="none"))
        edge += extent
    if separator:
        rule = {"stroke": theme.paper, "stroke_width": theme.stroke}
        rule.update(style)
        for a, _ in spans[1:]:
            segments.append(polyline((Vec2(x0, a), Vec2(x1, a)),
                                     kind=MARK_LINE_KIND, **rule))
    line = {"stroke": theme.muted, "stroke_width": theme.hairline}
    line.update(connector or {})
    links = [polyline(ends, kind=MARK_LINE_KIND, **line)
             for ends in breakout_connectors(panel, angles, ordered, side=side,
                                             width=width, height=height, gap=gap)]
    layers = [draw_place(links, origin=(0, 0), kind="breakout-links"),
              draw_place(segments, origin=(0, 0), kind="breakout-bar")]
    texts = ([None] * len(data) if labels is None
             else pie_label_texts(labels, data))
    note = {"slices": ordered, "parts": data, "labelled": [], "moved": []}
    pad = max(_PAD_OF_TYPE * theme.font_size, theme.gap("s"))
    weight = options.get("font_weight")
    extra = {} if weight is None else {"font_weight": weight}
    wanted: list = []
    for index, (text, (a, b)) in enumerate(zip(texts, spans)):
        if not text:
            continue
        node = text_node(text, size, TICK_LABEL_KIND,
                         markup=bool(options.get("markup", False)), **extra)
        wanted.append((index, (a + b) / 2,
                       node.styled(text_fill=options.get("fill") or theme.ink)))
    centres = _stacked_centres([(m, n.bbox.height) for _, m, n in wanted],
                               theme.gap("xs") * 0.5, top + bar_height)
    items: list = []
    for (index, middle, node), centre in zip(wanted, centres):
        box = node.bbox
        x = (x1 + pad - box.x0) if side == "right" else (x0 - pad - box.x1)
        items.append((Vec2(x, centre - box.center.y), node))
        note["labelled"].append(index)
        if abs(centre - middle) > 1e-6:
            note["moved"].append(index)
    if title:
        node, at = _breakout_title(panel, title, size, top, x0, x1)
        items.append((at, node))
    if items:
        layers.append(draw_place(items, origin=(0, 0), kind=AXIS_KIND))
    node = draw_place(layers, origin=(0, 0), kind="breakout")
    node.notes["pie_breakout"] = note
    return node, tuple(colours), note


def _breakout_title(panel, title: str, size: float, top: float, x0: float,
                    x1: float) -> tuple[Diagram, Vec2]:
    """The breakout title's node and offset: centred over the bar."""
    theme = active_theme()
    pad = max(_PAD_OF_TYPE * theme.font_size, theme.gap("s"))
    node = text_node(title, size, TICK_LABEL_KIND, markup=False)
    node = node.styled(text_fill=theme.ink)
    box = node.bbox
    return node, Vec2((x0 + x1) / 2 - box.center.x, top - pad - box.y1)


def breakout_title_box(panel, title: str | None, *, side: str = "right",
                       width: float | str | None = None,
                       height: float | str | None = None,
                       gap: float | str | None = None,
                       label_options: Mapping | None = None) -> Rect | None:
    """The panel-mm box a breakout's title takes, or None without one."""
    if not title:
        return None
    theme = active_theme()
    options = dict(label_options or {})
    size = (theme.font_size_small if options.get("size") is None
            else mm(options["size"]))
    _, top, _, x0, x1 = breakout_frame(panel, side=side, width=width,
                                       height=height, gap=gap)
    node, at = _breakout_title(panel, title, size, top, x0, x1)
    box = node.bbox
    return Rect(box.x0 + at.x, box.y0 + at.y, box.x1 + at.x, box.y1 + at.y)


def breakout_frame(panel, *, side: str = "right", width: float | str | None = None,
                   height: float | str | None = None,
                   gap: float | str | None = None) -> tuple[float, ...]:
    """A breakout bar's place in panel millimetres, as `(near, top, height,
    x0, x1)`: `near` is the x of the bar's side that faces the pie."""
    radius = panel.radius
    bar_width = radius * _BREAKOUT_WIDTH_OF_RADIUS if width is None else mm(width)
    bar_height = 2 * radius if height is None else mm(height)
    space = radius * _BREAKOUT_GAP_OF_RADIUS if gap is None else mm(gap)
    if bar_width <= 0 or bar_height <= 0 or space < 0:
        raise DiagramError("breakout() needs a positive width and height "
                           "and a gap of zero or more")
    sign = 1.0 if side == "right" else -1.0
    near = sign * (radius + space)
    x0, x1 = sorted((near, near + sign * bar_width))
    return near, -bar_height / 2, bar_height, x0, x1


def breakout_connectors(panel, angles: Sequence[tuple[float, float]],
                        slices: Sequence[int], *, side: str = "right",
                        width: float | str | None = None,
                        height: float | str | None = None,
                        gap: float | str | None = None) -> list[tuple[Vec2, Vec2]]:
    """A breakout's two connector segments: from where the outer edges of
    the adjacent `slices` meet the rim to the bar's near corners, the upper
    rim point to the top corner. `angles` are the slices' page angles from
    the pie's `pie_labels` note."""
    near, top, bar_height, _, _ = breakout_frame(panel, side=side, width=width,
                                                 height=height, gap=gap)
    a0 = min(angles[i][0] for i in slices)
    a1 = max(angles[i][1] for i in slices)
    if a1 - a0 >= 360 - 1e-9:
        raise DiagramError("breakout() slices cover the whole pie")
    radius = panel.radius
    rim = sorted((Vec2(math.cos(math.radians(a)) * radius,
                       math.sin(math.radians(a)) * radius) for a in (a0, a1)),
                 key=lambda v: v.y)
    return [(rim[0], Vec2(near, top)), (rim[1], Vec2(near, top + bar_height))]


def breakout_turn(theta, values: Sequence[float], slices: Sequence[int], *,
                  side: str, zero: bool = True,
                  winding: bool = True) -> tuple[float, str]:
    """The `zero` (page degrees) and `winding` of `theta` that turn a pie of
    `values` so the middle of the adjacent `slices` faces a breakout bar on
    `side`. The winding runs the slices down the facing side, so the first
    one is uppermost like the bar's first part. `zero` and `winding` say
    which of the two may change; the other keeps `theta`'s own."""
    new_winding = ("cw" if side == "right" else "ccw") if winding else theta.winding
    if not zero:
        return theta.zero, new_winding
    sign = 1.0 if new_winding == "cw" else -1.0
    total = sum(values)
    low, high = theta.domain
    start = sum(values[:slices[0]]) / total
    end = sum(values[:slices[-1] + 1]) / total
    middle = low + (high - low) * (start + end) / 2
    target = 0.0 if side == "right" else 180.0
    return (target - sign * middle * 360.0 / theta.turn) % 360.0, new_winding


#: The lightest shade of a breakout bar's default colours, as a blend of the
#: slice colour towards paper (or ink, for a pale slice).
_SHADE_REACH = 0.7


def _shades(color: str, count: int, theme) -> tuple[str, ...]:
    """`count` shades of one slice colour, from the colour itself towards
    paper, or towards ink when the colour is already pale."""
    if count == 1:
        return (color,)
    pale = contrast_ratio(color, theme.paper) < 1.6
    toward = theme.ink if pale else theme.paper
    return tuple(mix(color, toward, _SHADE_REACH * k / (count - 1))
                 for k in range(count))


def _stacked_centres(wanted: Sequence[tuple[float, float]], clear: float,
                     bottom: float) -> list[float]:
    """Label centres down a column: each at its wanted centre, moved down
    just clear of the label above it. If the last one then hangs past
    `bottom`, the labels that were moved are lifted back, the lowest first,
    as far as the ones above them allow."""
    centres: list[float] = []
    for index, (middle, height) in enumerate(wanted):
        if centres:
            above = centres[-1] + wanted[index - 1][1] / 2 + clear + height / 2
            centres.append(max(middle, above))
        else:
            centres.append(middle)
    if not centres:
        return centres
    over = centres[-1] + wanted[-1][1] / 2 - bottom
    if over > 0:
        centres[-1] -= over
        for index in range(len(centres) - 2, -1, -1):
            limit = (centres[index + 1] - wanted[index + 1][1] / 2 - clear
                     - wanted[index][1] / 2)
            centres[index] = min(centres[index], limit)
    return centres
