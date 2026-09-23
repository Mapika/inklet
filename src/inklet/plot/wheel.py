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
theme ink, pushed further out if they would overlap another outside label.
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

__all__ = ["RING_SHAPES", "radar_spokes", "radar", "radar_grid", "pie",
           "pie_label_texts", "breakout", "BREAKOUT_SIDES"]

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
               values: bool = False, **style) -> tuple[list[Diagram], Diagram | None, list]:
    """Rings, spokes and category names for a radar chart.

    Returns `(grid lines, label node or None, [(page angle, box)])`.
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
        # Each ring's value, just clockwise of the first spoke on the page.
        first = panel.angle(spokes[0])
        side = first + 90.0
        pad = _PAD_OF_TYPE * theme.font_size
        for value in drawn:
            text = format_number(value)
            node = text_node(text, theme.font_size_small, TICK_LABEL_KIND,
                             markup=False)
            base = _along(panel, spokes[0], panel.r.map(value))
            shift = _outward_centre(node.bbox, pad, side)
            items.append((base + shift, node))
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
        **style) -> tuple[Diagram, tuple[str, ...], dict]:
    """Sectors that divide the turn in proportion to `values`. See
    `PolarPanel.pie`.

    Returns `(node, fills, note)`, where `note` records which labels went
    inside and which outside.
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
    note = {"inside": [], "outside": [], "angles": [], "values": data}
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
                outside.append((index, mid, node))
        start = end
    placed_boxes: list[Rect] = []
    labels_out: list = []
    gap = _PAD_OF_TYPE * theme.font_size
    for index, mid, node in outside:
        distance = outer + gap
        for _ in range(40):
            at = _outward_centre(node.bbox, distance, mid)
            box = _moved(node.bbox, at)
            if not any(_touch(box, other, theme.gap("xs") * 0.5)
                       for other in placed_boxes):
                break
            distance += 0.3 * size
        placed_boxes.append(box)
        ink = options.get("fill") or theme.ink
        labels_out.append((at, node.styled(text_fill=ink)))
        note["outside"].append(index)
    parts = [draw_place(wedges, origin=(0, 0), kind="pie")]
    if inside or labels_out:
        parts.append(draw_place(inside + labels_out, origin=(0, 0),
                                kind=AXIS_KIND))
    node = draw_place(parts, origin=(0, 0), kind="pie")
    node.notes["pie_labels"] = note
    return node, tuple(fills), note


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
    radius = panel.radius
    bar_width = radius * _BREAKOUT_WIDTH_OF_RADIUS if width is None else mm(width)
    bar_height = 2 * radius if height is None else mm(height)
    space = radius * _BREAKOUT_GAP_OF_RADIUS if gap is None else mm(gap)
    if bar_width <= 0 or bar_height <= 0 or space < 0:
        raise DiagramError("breakout() needs a positive width and height "
                           "and a gap of zero or more")
    sign = 1.0 if side == "right" else -1.0
    near = sign * (radius + space)
    far = near + sign * (bar_width)
    x0, x1 = sorted((near, far))
    top = -bar_height / 2
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
    # Connectors: from where the slices' outer edges meet the rim to the
    # bar's near corners, the upper rim point to the top corner.
    a0 = angles[ordered[0]][0]
    a1 = angles[ordered[-1]][1]
    if abs(a1 - a0) >= 360 - 1e-9:
        raise DiagramError("breakout() slices cover the whole pie")
    rim = sorted((Vec2(math.cos(math.radians(a)) * radius,
                       math.sin(math.radians(a)) * radius) for a in (a0, a1)),
                 key=lambda v: v.y)
    line = {"stroke": theme.muted, "stroke_width": theme.hairline}
    line.update(connector or {})
    links = [polyline((rim[0], Vec2(near, top)), kind=MARK_LINE_KIND, **line),
             polyline((rim[1], Vec2(near, top + bar_height)),
                      kind=MARK_LINE_KIND, **line)]
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
        node = text_node(title, size, TICK_LABEL_KIND, markup=False)
        node = node.styled(text_fill=theme.ink)
        box = node.bbox
        items.append((Vec2((x0 + x1) / 2 - box.center.x, top - pad - box.y1),
                      node))
    if items:
        layers.append(draw_place(items, origin=(0, 0), kind=AXIS_KIND))
    node = draw_place(layers, origin=(0, 0), kind="breakout")
    node.notes["pie_breakout"] = note
    return node, tuple(colours), note


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
