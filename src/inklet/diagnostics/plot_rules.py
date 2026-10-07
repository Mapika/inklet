"""`OFF_PANEL` -- a label that leaves through the wall of its own plot box --
and `DATA_OUTSIDE`, its half for the data itself (see the second section).

`OFF_CANVAS` catches ink that runs off the page, and every rule in the library
is happy with a panel: the frame `inklet.panel(...).outline()` draws is a single
closed polyline, so it takes part in no overlap pair and no crowding pair, and
a label placed half outside it is nobody's finding. It is also one of the few
figure faults you cannot see in the data -- the label is *there*, correctly
positioned in data coordinates, and what removes half of it is the edge of the
box it was drawn in.

`figures/structure.py` panel (d) is the motivating case, and its own comment
says so: five concentration labels, each five response units above its own
curve, and the top one over a curve that reaches 36 of the 40 the axis is
marked to, in a box whose y range stops at 42. Five units above 36 is 41 and
the type is 1.4mm tall, so the label came out cut in half by the frame. The fix
in the figure is `lift = min(5.0, D_TOP - 0.6 - tall - level)` -- a clamp the
figure has to compute for itself, from numbers only it knows, because nothing
would have told it. This is the rule that tells it.

**Grade: info.** A label crossing the wall is nearly always a defect, but not
quite always -- a caption deliberately hung over the frame, a legend keyed to
sit on the edge -- and unlike `OFF_CANVAS` the ink is still on the page and
still printed. It is worth a line in the report and not worth failing on.

The plot box is the `plot_area` note, so this needs nothing new from `plot`:
`Panel.build` publishes it, `row`, `column` and `facets` publish the union of
their members', and `draw.annotate.letters` carries it onto the wrapper it puts
round a lettered panel. That last one is why the *nearest* declaring ancestor
is the one that answers -- a label inside a lettered panel has two of them
above it, naming the same rectangle, and reporting it twice would be a report
about the linter.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from ..core import Rect, Vec2
from ..draw.coords import AREA_NOTE
from ..plot.axis import (AXIS_KIND, AXIS_LABEL_KIND, SPINE_KIND, TICK_KIND,
                         TICK_LABEL_KIND)
from ..plot.key import COLORBAR_KIND, LEGEND_KIND
from ..plot.line_labels import LINE_LABELS_KIND
from .rules import (
    Diagnostic, Item, LintContext, _mm, _outside, _sides_phrase,
)

__all__ = ["rule_off_panel", "rule_data_outside", "rule_ticks_dropped",
           "TICKS_DROPPED_NOTE"]

#: Containers the plot layer places itself, whose contents sit where the layer
#: put them. A `side="top"` legend is above the plot box by construction and a
#: tick label is below it by construction, so where their text falls relative
#: to that rectangle is the layer's arithmetic and not a finding about the
#: figure. The geometric test below catches most of these on its own -- they
#: are usually clear of the box entirely -- but not all: a top legend's entry
#: dips a few tenths of a millimetre inside the frame, which is enough to make
#: it overlap and enough to make it "leave", and reporting that would put a
#: line in the report of every panel with a legend on it.
FURNITURE_KINDS = (AXIS_KIND, LEGEND_KIND, COLORBAR_KIND)

#: Labels the plot layer hangs off the *ends* of the data on purpose: the
#: names `Panel.label_lines()` sets past the last point of each curve, and the
#: value labels `slope()` and `bump()` set beside their first and last
#: columns. They leave the box sideways by construction -- that is where
#: there is room for them -- so only their top and bottom are judged: a curve
#: name pushed out through the top of the axes is still a finding.
SIDEWAYS_KINDS = (LINE_LABELS_KIND,)
SIDEWAYS_NOTES = ("slope", "bump")


def rule_off_panel(ctx: LintContext) -> list[Diagnostic]:
    """Text that leaves the plot box of the panel it was placed in."""
    out: list[Diagnostic] = []
    for item in ctx.items:
        if not item.is_text or not item.draws:
            continue
        if _is_furniture(ctx, item.id):
            continue
        home = _plot_box(ctx, item.id)
        if home is None:
            continue
        panel_id, box = home
        if box.overlap(item.bbox) is None:
            continue       # axis furniture: outside the box, and meant to be
        sides = _outside(item.bbox, box)
        if sides and _set_sideways(ctx, item.id):
            sides = {side: amount for side, amount in sides.items()
                     if side in ("top", "bottom")}
        if not sides:
            continue
        worst = max(sides, key=lambda side: sides[side])
        out.append(Diagnostic(
            code="OFF_PANEL",
            severity="info",
            message=(f"{item.described} leaves {ctx.label(panel_id)}'s plot "
                     f"box by {_sides_phrase(sides)}"),
            targets=(item.id,),
            where=item.bbox,
            hint=(f"clamp it to the axis range, or widen the panel's "
                  f"{'x' if worst in ('left', 'right') else 'y'} range by "
                  f"{_mm(sides[worst])} on the {worst}"),
        ))
    return out


def _set_sideways(ctx: LintContext, node_id: str) -> bool:
    """Whether this text is an end label, placed beside the box on purpose."""
    for step in ctx.chain(node_id):
        node = ctx.nodes.get(step)
        if node is None:
            continue
        if node.kind in SIDEWAYS_KINDS:
            return True
        notes = getattr(node, "notes", None)
        if isinstance(notes, Mapping) and any(n in notes for n in SIDEWAYS_NOTES):
            return True
    return False


def _is_furniture(ctx: LintContext, node_id: str) -> bool:
    """Whether this text was placed by an axis, a legend or a colour bar."""
    return any(getattr(ctx.nodes.get(step), "kind", None) in FURNITURE_KINDS
               for step in ctx.chain(node_id))


def _plot_box(ctx: LintContext, node_id: str) -> tuple[str, Rect] | None:
    """The plot box of the nearest ancestor-or-self that declares one.

    *Nearest*, because a lettered panel and the panel inside it both carry the
    note and both name the same rectangle; and because a `facets` grid's note
    is the union of its members', which a label inside one member is inside
    even when it has left that member's own box.

    The note is written in the declaring node's own local frame -- the frame it
    was drawn in, before the recentring a built panel gets -- and
    `Placement.world` maps exactly that frame onto the page, so one transform
    puts the rectangle in the same space as `Item.bbox`. Reading it through
    `draw.coords.plot_area` instead would apply the node's own transform twice.
    """
    for step in reversed(ctx.chain(node_id)):
        node = ctx.nodes.get(step)
        notes = getattr(node, "notes", None)
        area = notes.get(AREA_NOTE) if isinstance(notes, Mapping) else None
        if not isinstance(area, Rect):
            continue
        placed = ctx.placements.get(step)
        if placed is None:                               # pragma: no cover
            continue      # placements from a different resolve(); say nothing
        return step, area.transform(placed.world)
    return None


# -- DATA_OUTSIDE -----------------------------------------------------------
#
# `OFF_PANEL` is about words. The data's own ink leaving the plot box is the
# other half of the same fault, and the worse half: a line that runs on above
# the top of the axes, past the last tick, is drawn at a value the axis does
# not show, and a reader takes it for a datum that is not there. Nothing else
# reports it. The panel does not clip by default (`panel()` says why), every
# mark is correctly placed in data coordinates, and the only thing wrong is
# that the range the author gave the axis is smaller than the data -- which is
# exactly the kind of mistake an agent makes when it writes `y=(0, 2)` from
# memory of a dataset that has since grown.
#
# What counts as data is decided by elimination, the way `OFF_PANEL` decides
# what counts as a label: everything drawn inside a panel that is not text and
# not furniture the plot layer hangs off the box on purpose -- an axis, a key,
# a title, an inset and the hairlines that point at it, the at-risk table under
# a survival curve, the leaders that run from a curve's end to its name.
#
# **Grade: warning.** It is nearly always a range that is too narrow, and the
# fix is one word either way: a wider range, or `clip=True` when the author
# does mean to show only a window onto the data. Panels with no axis and no
# frame are not judged -- there is nothing on the page for the data to be
# outside of -- and neither is anything sitting wholly beside the box that
# does not call itself data (`DATA_KINDS`), which is how hand-placed gutters,
# trees and keys drawn through `over()` stay quiet.

#: Subtrees inside a panel that are placed outside the plot box by design.
DESIGNED_OUTSIDE_KINDS = frozenset({
    AXIS_KIND, LEGEND_KIND, COLORBAR_KIND, "colorband", "legend-plate",
    "swatch", "title", "panel-title", "inset", "frame", "at-risk",
    "size-key", "width-key", "line-labels", "label-leader", "point-labels",
    "label", "bar-labels", "axis-break", "plot-area", "gridline",
    "tick-plate", "datum", "arrow-ends", "marginal", "header",
    "forest-columns", "cluster-labels", "pie-leaders", "breakout",
    # `inklet.draw.annotate`'s furniture: callouts, significance brackets
    # stacked above the data, dimension lines, scale bars.
    "annotation", "annotation-label", "bracket", "dimension", "scalebar",
    # Axis furniture drawn by hand, and the things an author points with.
    SPINE_KIND, TICK_KIND, TICK_LABEL_KIND, AXIS_LABEL_KIND, "arrow", "link",
    "dendrogram", "dendrogram-abutting",
})

#: Kinds the plot layer gives the marks it draws from data. A node of one of
#: these is data wherever it lands -- a scatter point past the end of the axis
#: is the case this rule exists for. Anything else that sits *wholly* outside
#: the box (a gutter rule, a tree over a heatmap, a hand-placed key drawn
#: through `over()` in millimetres) was put there, and is left alone; only
#: when it starts inside the box and runs out of it is it data the range
#: failed to hold.
DATA_KINDS = frozenset({"mark", "mark-line", "mark-vector", "raster-scatter",
                        "hexbin", "kde", "hist", "violin", "strip", "sina"})

#: A `matrix` grows each cell past its pitch by a fraction of it so that no
#: antialiased seam shows between neighbours (`plot.matrix._CELL_OVERLAP`, 6%,
#: half on each side). The outer cells carry that bleed past the box edge too,
#: by design; this much of a cell's own size is let through for them.
_MATRIX_NOTE = "matrix_sampling"
_MATRIX_BLEED = 0.04

#: `ridgeline(fit=False)` lets the top ridges rise above the plot area and
#: records how far under this note's `above`.
_RIDGELINE_NOTE = "ridgeline"

#: How far ink may reach past the box before it is a finding. Half a
#: millimetre is a marker's rim on the axis line, a stroke's half-width, the
#: flattening of a smooth curve through a point on the edge: nothing a reader
#: would call "outside", and everything a float would.
DATA_SLACK_MM = 0.5

#: A shape no larger than this either way is a marker, a cap or a tick, and
#: what it stands for is its centre. A marker on the axis edge has half its
#: disc outside the box and is exactly where it belongs.
_MARKER_MM = 3.0

#: The kind of node `Panel.build` and `PolarPanel.build` produce. Spelled out
#: rather than imported from `plot.furniture` to keep this module's imports
#: to the plot layer's public constants.
_PANEL_KIND = "panel"


def rule_data_outside(ctx: LintContext) -> list[Diagnostic]:
    """Data drawn past the axes of its panel: a range narrower than the data.

    One warning per panel, naming how far past each side the marks reach and,
    when the axis prints numbers it can be read back from, the range that
    would hold them. Text, keys, axes, insets and other furniture placed
    outside the box on purpose are not data; marks cut with `clip=True` stay
    inside by construction.
    """
    found: dict[str, list[tuple[Item, dict[str, float], Rect]]] = {}
    boxes: dict[str, Rect] = {}
    for item in ctx.items:
        if item.is_text or not item.draws or not _paints(item):
            continue
        home = _data_home(ctx, item.id)
        if home is None:
            continue
        panel_id, box = home
        if not _framed(ctx, panel_id):
            continue
        reach = _reach(item)
        if reach is None:
            continue
        if box.overlap(item.bbox) is None and not _is_data(ctx, item):
            continue      # placed beside the box, not run out of it
        slack = _slack(ctx, item)
        sides = {side: amount for side, amount in _outside(reach, box).items()
                 if amount > slack[side]}
        if not sides:
            continue
        boxes[panel_id] = box
        found.setdefault(panel_id, []).append((item, sides, reach))
    out: list[Diagnostic] = []
    for panel_id in sorted(found):
        out.append(_data_finding(ctx, panel_id, boxes[panel_id],
                                 found[panel_id]))
    return out


def _data_finding(ctx: LintContext, panel_id: str, box: Rect,
                  marks: list[tuple[Item, dict[str, float], Rect]]) -> Diagnostic:
    worst: dict[str, float] = {}
    extent: Rect | None = None
    for _, sides, reach in marks:
        for side, amount in sides.items():
            worst[side] = max(worst.get(side, 0.0), amount)
        extent = reach if extent is None else extent.union(reach)
    assert extent is not None
    readers = _axis_readers(ctx, panel_id, box)
    parts, widen = [], []
    for axis, (low, high) in (("y", ("bottom", "top")), ("x", ("left", "right"))):
        sides = [side for side in (high, low) if side in worst]
        if not sides:
            continue
        reader = readers.get(axis)
        # The range the data needs, written low end first the way the author
        # wrote it: the box edge where nothing crosses it, the reach where
        # something does.
        ends = {"top": box.y0, "bottom": box.y1, "left": box.x0, "right": box.x1}
        edges = dict(ends)
        edges.update({side: reach for side, reach in (
            ("top", extent.y0), ("bottom", extent.y1),
            ("left", extent.x0), ("right", extent.x1)) if side in worst})
        for side in sides:
            phrase = f"{_mm(worst[side])} past the {side}"
            if reader is not None:
                reached = _format_value(reader(edges[side]), reader.step)
                stops = _format_value(reader(ends[side]), reader.step)
                if reached != stops:
                    phrase += f" (to {axis} = {reached}, where the axis stops at {stops})"
            parts.append(phrase)
        if reader is not None:
            wanted = tuple(_format_value(reader(edges[side]), reader.step)
                           for side in (low, high))
            if len(set(wanted)) == 2:
                widen.append(f"widen the {axis} range to ({wanted[0]}, {wanted[1]})")
                continue
        widen.append(f"widen the {axis} range at the {' and '.join(sides)}")
    count = len(marks)
    what = (f"{marks[0][0].phrase} reaches" if count == 1
            else f"{count} marks reach")
    named = _panel_name(ctx, panel_id)
    message = f"data in {named} runs outside the axes: {what} {'; '.join(parts)}"
    hint = (" and ".join(widen)
            + ", or pass clip=True to the drawing call to cut it at the axes")
    where = extent
    return Diagnostic(
        code="DATA_OUTSIDE",
        severity="warning",
        message=message,
        targets=tuple(sorted(item.id for item, _, _ in marks)),
        where=where,
        hint=hint,
    )


def _panel_name(ctx: LintContext, panel_id: str) -> str:
    """The panel as its author would find it: its name, or its cell's."""
    node = ctx.nodes.get(panel_id)
    if node is not None and node.name:
        return f"panel {node.name!r}"
    for step in ctx.ancestors(panel_id):
        above = ctx.nodes.get(step)
        if above is None:
            continue
        if above.kind == _PANEL_KIND:
            break
        if above.kind == "document-cell" and above.name:
            return f"cell {above.name!r} ({panel_id})"
    return panel_id


def _framed(ctx: LintContext, panel_id: str) -> bool:
    """Whether the panel draws anything that marks where its box is.

    "Outside the axes" needs axes, or at least a frame: a treemap, an icicle,
    a pie with its breakout, a network laid out in an unruled panel have a
    plot box only as a layout fact, and their leaders and labels reach past it
    by design with nothing on the page to say they did.
    """
    memo = ctx._memo.setdefault("framed", {})
    if panel_id not in memo:
        memo[panel_id] = bool(_furniture_of(ctx, panel_id, (AXIS_KIND, SPINE_KIND)))
    return memo[panel_id]


def _is_data(ctx: LintContext, item: Item) -> bool:
    """Whether the item, or the plot call that drew it, says it is data."""
    from ..core import MarkerBatchPrim
    if isinstance(item.prim, MarkerBatchPrim):
        return True
    return any(getattr(ctx.nodes.get(step), "kind", None) in DATA_KINDS
               for step in ctx.chain(item.id))


def _slack(ctx: LintContext, item: Item) -> dict[str, float]:
    """How far past each side of the box this item may reach unreported.

    `DATA_SLACK_MM` everywhere, widened where the plot layer draws past the
    box by design and says by how much: a matrix cell's seam bleed, and the
    top ridges of a `ridgeline(fit=False)`, which its note records under
    `above`.
    """
    slack = dict.fromkeys(("left", "right", "top", "bottom"), DATA_SLACK_MM)
    for step in ctx.chain(item.id):
        notes = getattr(ctx.nodes.get(step), "notes", None)
        if not isinstance(notes, Mapping):
            continue
        if _MATRIX_NOTE in notes:
            for side in ("left", "right"):
                slack[side] = max(slack[side], _MATRIX_BLEED * item.bbox.width)
            for side in ("top", "bottom"):
                slack[side] = max(slack[side], _MATRIX_BLEED * item.bbox.height)
        ridges = notes.get(_RIDGELINE_NOTE)
        if isinstance(ridges, Mapping):
            above = ridges.get("above")
            if isinstance(above, (int, float)) and above > 0:
                slack["top"] = max(slack["top"], DATA_SLACK_MM + float(above))
    return slack


def _paints(item: Item) -> bool:
    """Whether the item can put any ink down at all.

    Only an explicit "none" counts as nothing: a style left at None is
    inherited, and a tree linted before the theme is applied has nearly all
    of its paint still to come.
    """
    style = item.style
    if style.opacity is not None and style.opacity <= 0.0:
        return False
    from ..core import ImagePrim, MarkerBatchPrim, PathPrim
    if isinstance(item.prim, ImagePrim):
        return True
    shape = item.prim.shape if isinstance(item.prim, MarkerBatchPrim) else item.prim
    filled = not (isinstance(shape, PathPrim) and not shape.filled)
    fills = filled and not _none(style.fill)
    strokes = not _none(style.stroke) and (style.stroke_width is None
                                            or style.stroke_width > 0.0)
    return fills or strokes


def _none(paint) -> bool:
    return paint is not None and str(paint).strip().lower() in (
        "none", "transparent", "")


def _data_home(ctx: LintContext, node_id: str) -> tuple[str, Rect] | None:
    """The panel this item is data of, with its plot box -- or None.

    None when anything between the item and its panel was placed outside the
    box on purpose (`DESIGNED_OUTSIDE_KINDS`), and when the nearest plot box
    above it is not a panel's own: a `row` or a `facets` grid declares the
    union of its members' boxes, and what stands in the row beside the panels
    -- a shared key, a diagram -- is not data in any of them.
    """
    for step in reversed(ctx.chain(node_id)):
        node = ctx.nodes.get(step)
        if node is None:
            return None
        notes = getattr(node, "notes", None)
        area = notes.get(AREA_NOTE) if isinstance(notes, Mapping) else None
        if isinstance(area, Rect):
            if node.kind != _PANEL_KIND:
                return None
            placed = ctx.placements.get(step)
            if placed is None:                           # pragma: no cover
                return None
            return step, area.transform(placed.world)
        if node.kind in DESIGNED_OUTSIDE_KINDS:
            return None
    return None


def _reach(item: Item) -> Rect | None:
    """The box the item's data reaches, in world space.

    Geometry, not ink: a path's points rather than its stroke, a marker's
    centre rather than its disc, an error bar's cap by its middle. Cut to the
    item's own box, which `build_context` has already clipped to any clip
    region the item is drawn through.
    """
    from ..core import EllipsePrim, ImagePrim, MarkerBatchPrim, PathPrim, RectPrim
    prim, world = item.prim, item.world
    reach: Rect | None = None

    def add(box: Rect) -> None:
        nonlocal reach
        reach = box if reach is None else reach.union(box)

    if isinstance(prim, PathPrim):
        for sub in prim.subpaths:
            if not sub.points:
                continue
            add(_marker_or_box(Rect.hull([world.apply(p) for p in sub.points])))
    elif isinstance(prim, MarkerBatchPrim):
        xs, ys = [], []
        for x, y, _, _, _ in prim.records():
            point = world.apply(Vec2(x, y))
            xs.append(point.x)
            ys.append(point.y)
        if xs:
            add(Rect(min(xs), min(ys), max(xs), max(ys)))
    elif isinstance(prim, (RectPrim, EllipsePrim, ImagePrim)):
        add(_marker_or_box(item.bbox))
    else:
        return None
    if reach is None:
        return None
    return _clamp(reach, item.bbox)


def _marker_or_box(box: Rect) -> Rect:
    if max(box.width, box.height) <= _MARKER_MM:
        centre = box.center
        return Rect(centre.x, centre.y, centre.x, centre.y)
    return box


def _clamp(inner: Rect, outer: Rect) -> Rect:
    """`inner` cut to `outer`, keeping a degenerate result rather than None."""
    x0, x1 = max(inner.x0, outer.x0), min(inner.x1, outer.x1)
    y0, y1 = max(inner.y0, outer.y0), min(inner.y1, outer.y1)
    if x1 < x0:
        x0 = x1 = min(max(inner.center.x, outer.x0), outer.x1)
    if y1 < y0:
        y0 = y1 = min(max(inner.center.y, outer.y0), outer.y1)
    return Rect(x0, y0, x1, y1)


# -- reading data values back off an axis ------------------------------------
#
# The panel's scales are gone by the time a rule runs; what is left of them is
# the axis, which prints the value at each tick beside the tick. That is enough
# to read a position back as a number when the axis is linear or logarithmic,
# and the hint "widen the y range to include 4" is worth the trouble: it is the
# fix, written out, where "by 15mm" is a sum the author has to do.


class _Reader:
    """Position along one axis -> data value, from the ticks it prints."""

    __slots__ = ("at", "values", "log", "step")

    def __init__(self, at: list[float], values: list[float], log: bool) -> None:
        self.at, self.values, self.log = at, values, log
        diffs = [abs(b - a) for a, b in zip(values, values[1:]) if b != a]
        self.step = None if log or not diffs else min(diffs)

    def __call__(self, position: float) -> float:
        (p0, p1), (v0, v1) = (self.at[0], self.at[-1]), (self.values[0], self.values[-1])
        if self.log:
            v0, v1 = math.log10(v0), math.log10(v1)
        value = v0 + (position - p0) * (v1 - v0) / (p1 - p0)
        return 10 ** value if self.log else value


def _axis_readers(ctx: LintContext, panel_id: str,
                  box: Rect) -> dict[str, _Reader]:
    """{'x': reader, 'y': reader} for the axes of this panel that can be read.

    An orientation with two axes that disagree -- a twin y -- has no reader:
    the data could be on either scale, and a wrong number is worse than none.
    Ticks are only believed inside the box they measure: a tick off the end
    of the plot box is not one this panel's data is mapped through.
    """
    memo = ctx._memo.setdefault("axis_readers", {})
    if panel_id in memo:
        return memo[panel_id]
    ticks: dict[str, list[tuple[float, float, float]]] = {}
    for axis_id in _axes_of(ctx, panel_id):
        found = _ticks_of(ctx, axis_id)
        if found:
            ticks[axis_id] = found
    readers: dict[str, list[_Reader]] = {}
    for axis_id in sorted(ticks):
        found = ticks[axis_id]
        xs = [x for x, _, _ in found]
        ys = [y for _, y, _ in found]
        horizontal = max(xs) - min(xs) >= max(ys) - min(ys)
        at = xs if horizontal else ys
        low, high = (box.x0, box.x1) if horizontal else (box.y0, box.y1)
        reader = _fit([(p, v) for p, (_, _, v) in zip(at, found)
                       if low - 1.0 <= p <= high + 1.0])
        if reader is not None:
            readers.setdefault("x" if horizontal else "y", []).append(reader)
    answer: dict[str, _Reader] = {}
    for axis, found in readers.items():
        first = found[0]
        if all(_agree(first, other) for other in found[1:]):
            answer[axis] = first
    memo[panel_id] = answer
    return answer


def data_position(ctx: LintContext, item: Item) -> str:
    """`at x=.., y=..` for an item drawn in a panel, read off its axes.

    Empty when the item is not data in any panel or neither axis can be read
    (`_axis_readers` declines a twin axis or a categorical one), so a caller
    can append it unconditionally.
    """
    home = _data_home(ctx, item.id)
    if home is None:
        return ""
    panel_id, box = home
    readers = _axis_readers(ctx, panel_id, box)
    return at_position(item.bbox.center, readers)


def at_position(point: Vec2, readers: Mapping[str, _Reader]) -> str:
    """`at x=.., y=..` for a page point, through whichever readers exist."""
    bits = []
    for axis, value in (("x", point.x), ("y", point.y)):
        reader = readers.get(axis)
        if reader is not None:
            bits.append(f"{axis}={_format_value(reader(value), reader.step)}")
    return "at " + ", ".join(bits) if bits else ""


def _agree(a: _Reader, b: _Reader) -> bool:
    probes = (a.at[0], a.at[-1])
    return all(math.isclose(a(p), b(p), rel_tol=1e-3, abs_tol=1e-9) for p in probes)


def _axes_of(ctx: LintContext, panel_id: str) -> list[str]:
    """Axis nodes that belong to this panel and not to a panel inside it."""
    return _furniture_of(ctx, panel_id, (AXIS_KIND,))


def _furniture_of(ctx: LintContext, panel_id: str,
                  kinds: tuple[str, ...]) -> list[str]:
    """Nodes of these kinds drawn by this panel itself.

    Not by a panel nested in it -- an inset has axes of its own -- and not by
    anything placed outside the box on purpose: a breakout bar's axis is not
    the pie's.
    """
    out = []
    stack = [child.id for child in ctx.nodes[panel_id].children]
    while stack:
        node_id = stack.pop()
        node = ctx.nodes.get(node_id)
        if node is None or node.kind == _PANEL_KIND:
            continue
        if node.kind in kinds:
            out.append(node_id)
            continue
        if node.kind in DESIGNED_OUTSIDE_KINDS:
            continue
        stack.extend(child.id for child in node.children)
    return sorted(out)


def _ticks_of(ctx: LintContext, axis_id: str) -> list[tuple[float, float, float]]:
    """(x, y, value) for each numeric tick label, at its tick where it has one.

    A tick label is read at the tick before it in the axis' children, because
    that is the datum's position; a turned label's own centre is not.
    """
    out: list[tuple[float, float, float]] = []
    tick: Vec2 | None = None
    for child in ctx.nodes[axis_id].children:
        for step in _walk(child):
            item = ctx.item(step.id)
            if item is None:
                continue
            if step.kind == TICK_KIND:
                tick = item.bbox.center
            elif step.kind == TICK_LABEL_KIND and item.is_text:
                value = _number(item)
                if value is None:
                    continue
                at = tick if tick is not None else item.bbox.center
                out.append((at.x, at.y, value))
                tick = None
    return out


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _number(item: Item) -> float | None:
    text = "".join(line.text for line in item.prim.lines)  # type: ignore[union-attr]
    text = (text.replace("−", "-").replace(" ", "").replace(" ", "")
            .replace(",", "").replace(" ", "").rstrip("%"))
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _fit(points: list[tuple[float, float]]) -> _Reader | None:
    """A linear or log10 reader through the ticks, or None if neither fits."""
    points = sorted(dict(points).items())
    if len(points) < 2:
        return None
    at = [p for p, _ in points]
    values = [v for _, v in points]
    if at[-1] - at[0] < 1.0 or values[0] == values[-1]:
        return None
    for log in (False, True):
        if log and min(values) <= 0.0:
            break
        reader = _Reader(at, values, log)
        span = abs(math.log10(values[-1] / values[0]) if log
                   else values[-1] - values[0])
        if all(abs((math.log10(reader(p)) - math.log10(v)) if log
                   else reader(p) - v) <= 0.01 * span
               for p, v in points):
            return reader
    return None


def _format_value(value: float, step: float | None) -> str:
    """A tick-like spelling: two digits finer than the ticks, trimmed."""
    if step:
        quantum = 10 ** (math.floor(math.log10(step)) - 1)
        value = round(value / quantum) * quantum
        digits = max(0, -int(math.floor(math.log10(quantum))))
        text = f"{value:.{digits}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return "0" if text in ("-0", "") else text
    return f"{value:.2g}"


# -- TICKS_DROPPED -------------------------------------------------------------
#
# An axis given explicit `ticks=` thins them when their labels would collide,
# unless `thin=` says otherwise, and until now said so only with a Python
# `UserWarning` at build time -- which an agent running a script under a
# harness never sees, and which `figure.report()`, the one channel the guide
# tells it to read, did not repeat (ISSUES-earth-life 3). The month inset of
# `keeling_curve` asked for Feb, Apr, ... Dec and printed every other one.
#
# The axis records what it dropped in a note on its own node (`plot.axis`
# writes it under the same condition as the warning: explicit ticks, `thin`
# left at its default, labels on). The note is a mapping:
#
#     {"values": (...), "labels": ("Apr", "Aug", "Dec"), "supplied": 6,
#      "side": "bottom"}
#
# of which only `values` or `labels` is required; anything missing is said
# less precisely rather than not at all.
#
# **Grade: warning.** The author named those ticks; a figure that silently
# prints a different set is the failure, and the fix is one argument.

#: Read defensively: the axis may predate the note, and then says nothing.
TICKS_DROPPED_NOTE = "ticks_dropped"


def rule_ticks_dropped(ctx: LintContext) -> list[Diagnostic]:
    """Explicitly supplied ticks an axis left out for lack of room."""
    noted = {}
    for node_id, node in ctx.nodes.items():
        notes = getattr(node, "notes", None)
        dropped = notes.get(TICKS_DROPPED_NOTE) if isinstance(notes, Mapping) else None
        if isinstance(dropped, Mapping):
            noted[node_id] = dropped
    # A wrapper with one child inherits that child's notes (`carry_notes`),
    # so one axis's note turns up on every single-child wrapper above it.
    # The deepest holder is the axis itself.
    wrappers = {step for node_id in noted for step in ctx.ancestors(node_id)}
    out: list[Diagnostic] = []
    for node_id in sorted(noted):
        if node_id in wrappers:
            continue
        dropped = noted[node_id]
        labels = [str(v) for v in dropped.get("labels") or ()]
        if not labels:
            labels = [_tick_word(v) for v in dropped.get("values") or ()]
        if not labels:
            continue
        supplied = dropped.get("supplied")
        placed = ctx.placements.get(node_id)
        box = None if placed is None else placed.bbox
        side = dropped.get("side")
        axis = ("x" if side in ("top", "bottom") else "y" if side in ("left", "right")
                else None)
        if axis is None and box is not None:
            axis = "x" if box.width >= box.height else "y"
        named = _axis_owner(ctx, node_id)
        of = (f"{len(labels)} of {supplied}" if isinstance(supplied, int)
              else f"{len(labels)}")
        shown = ", ".join(labels[:6]) + (f" and {len(labels) - 6} more"
                                         if len(labels) > 6 else "")
        which = f"the {axis} axis" if axis else "an axis"
        span = "width" if axis == "x" else "height" if axis == "y" else "size"
        out.append(Diagnostic(
            code="TICKS_DROPPED",
            severity="warning",
            message=(f"{which} of {named} left out {of} explicitly supplied "
                     f"ticks because their labels would collide: {shown}"),
            targets=(node_id,),
            where=box,
            hint=(f"pass thin=False in that axis' options to keep every tick "
                  f"(rotate=45 makes room for long labels), supply fewer "
                  f"ticks, or give the plot more {span}; thin=True accepts "
                  f"the thinning and silences this"),
        ))
    return out


def _tick_word(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _axis_owner(ctx: LintContext, node_id: str) -> str:
    """The panel an axis belongs to, as `_panel_name` spells it -- and, for a
    panel inset in another, which one it is inset in."""
    panels = [step for step in ctx.ancestors(node_id)
              if getattr(ctx.nodes.get(step), "kind", None) == _PANEL_KIND]
    if not panels:
        return node_id
    if len(panels) > 1 and not ctx.nodes[panels[0]].name:
        return f"the inset {panels[0]} in {_panel_name(ctx, panels[1])}"
    return _panel_name(ctx, panels[0])
