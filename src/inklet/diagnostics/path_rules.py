"""`PATH_CROSSES` -- a stroke nobody routed, drawn through a picture.

`OVERLAP` compares bounding boxes and intersection *area*, and a stroke has
none: a leader through a protein and a hand-drawn polyline through a mesh both
report nothing, however much of the drawing they cut in half. `LINK_CROSSES`
closes that for connectors the router built, because a routed link records
what it was clipped to and so can be asked what it had no business touching.
Everything else -- `inklet.annotate`'s leader written by hand, a callout drawn
with `inklet.polyline`, an author's own arrow -- has no such record, and this is
the rule for those.

The measurement is the same one `LINK_CROSSES` makes, and deliberately shares
its code: walk the stroke's flattened segments and ask each shape's own
`Trace` how many millimetres of each segment land inside it. What is different
is the question of *whose* ink a stroke is allowed to be in, because without
an `attached_to` to read there is nothing structural to go on -- and the
corpus draws some seven hundred strokes that are part of the picture they sit
on. That question is answered by `_composed_with`, and it is the whole rule:

    **Composition is not membership.** A stroke drawn *inside* a picture is
    part of it; a stroke merely *stacked beside* one is pointing at it.

A `stack`, a `place`, a `grid` and a `pad` arrange things that stay separate.
Anything else holding both -- a panel, a scene, a model, a clip, a framed box
-- is a thing the stroke was drawn into. So a gridline over its own plot area,
a crease across the solid it belongs to and a bond into its own atom are all
silent, while the "hinge" leader of `figures/drug_discovery.py` panel (a),
which `annot.on` merely `place`s over the kinase fold, is a finding.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

from ..core import PathPrim, Rect, Trace, Vec2
from ..links import HEAD_KIND
from .abut import is_abutting_kind
from .rules import (
    Diagnostic, Item, LintContext, _area, _boxes_touch, _contains, _EPS_MM,
    _drawn_into, _inside, _link_owner, _MIN_CROSSING_MM, _mm, _object_label,
    _object_of, _outline, _pairable, _PointIndex, _rings, _sealed_in,
    _shaft_segments, _source_home,
)

__all__ = ["rule_path_crosses", "stroke_near_misses"]

#: Containers that only *arrange* what is inside them. Two things put side by
#: side, one above the other, or on named coordinates are still two things,
#: and a line across one of them came from outside it. Every other container
#: -- `panel`, `model`, `clip`, `framed`, `axis`, `legend` -- is a picture
#: that owns its contents, and a stroke inside one is part of the drawing.
_COMPOSING_KINDS = frozenset({
    "place", "stack", "flow", "grid", "pad", "spacer",
    "page", "panels", "facets", "content", "g", None,
})

#: Strokes whose position is not a choice anyone made, so "it crosses
#: something" is not a defect anyone can fix. Mesh ink lies on its own mesh by
#: construction, a silhouette *is* the outline of what it encloses, and an
#: arrowhead is answered by `CROWDING`'s own axis test. `Item.is_computed`
#: covers the data-driven half (`mark`, `mark-line`, `model-facet`...); these
#: are the strokes that are not marks but are not the author's line either.
_UNCHOSEN_STROKES = frozenset({
    HEAD_KIND, "silhouette", "model-silhouette",
})


def rule_path_crosses(ctx: LintContext) -> list[Diagnostic]:
    """A stroke that is not a routed link running through a drawing.

    What is exempt, and why each one has to be:

    * Everything `LINK_CROSSES` already owns. A stroke inside a routed link is
      that rule's business, and reporting it twice would teach a fix loop that
      its fix did not work.
    * Ink whose place was not chosen -- data marks, mesh facets and creases,
      silhouettes, arrowheads (`_UNCHOSEN_STROKES` and `Item.is_computed`).
    * Anything the stroke was declared to touch: `attached_to`, which covers
      `through=`, and `inklet.abutting(kind)`, which covers a molecule's bonds
      and a Sankey's ribbons.
    * Ink the stroke was drawn *into* rather than *over* -- see the module
      docstring and `_composed_with`. This is the exemption that decides
      whether the rule is usable at all: without it the corpus's ~700
      in-picture strokes report several hundred crossings of their own
      drawings, and with it they report none.
    * A shape that merely *contains* the whole stroke. A callout ring drawn
      inside a panel's frame has to be inside the frame.

    Severity follows `LINK_CROSSES`: a `warning`, or an `error` when the line
    cuts through glyphs, because a word with a line through it is broken in
    the way `TEXT_OVERFLOW` is broken.
    """
    strokes = [item for item in ctx.items if _is_free_stroke(ctx, item)]
    if not strokes:
        return []
    targets = [item for item in ctx.items
               if _pairable(ctx, item) and _link_owner(ctx, item.id) is None]
    if not targets:
        return []

    index = _PointIndex(targets)
    order = _paint_order(ctx)
    outlines: dict[str, Trace] = {}
    out: list[Diagnostic] = []
    for stroke in strokes:
        verdict: dict[str, bool] = {}
        depth: dict[str, float] = {}
        for points in _runs_of(ctx, stroke):
            objects: dict[str, list[Item]] = {}
            for shape in _near(ctx, order, index, verdict, stroke, points):
                objects.setdefault(_object_of(ctx, shape.id), []).append(shape)
            for object_id, parts in objects.items():
                spans: list[tuple[float, float, str]] = []
                for part in parts:
                    outline = outlines.get(part.id)
                    if outline is None:
                        outline = outlines[part.id] = _outline(part)
                    spans += [(lo, hi, part.id)
                              for lo, hi in _inside_spans(outline, points)]
                run, involved = _through(spans, _length(points))
                if run < _MIN_CROSSING_MM:
                    continue
                for part in parts:
                    if part.id in involved:
                        depth[part.id] = max(depth.get(part.id, 0.0), run)
        out.extend(_crossings(ctx, stroke, depth))
    return out


def _runs_of(ctx: LintContext, stroke: Item) -> list[list[Vec2]]:
    """`_polylines`, built once per stroke and shared by the rules that walk it.

    Two rules walk every free stroke in the figure -- `PATH_CROSSES` and the
    near-miss half of `CROWDING` -- and flattening a path to world points is
    the larger part of what either of them does: `stress/mega_figure.py` has
    581 strokes in 12,000 runs, and building them twice cost more than every
    distance query in both rules put together.
    """
    cache = ctx._memo.setdefault("runs", {})
    known = cache.get(stroke.id)
    if known is None:
        known = cache[stroke.id] = _polylines(ctx, stroke)
    return known


def _polylines(ctx: LintContext, stroke: Item) -> list[list[Vec2]]:
    """The stroke as whole runs of points, not loose segments.

    `_shaft_segments` is the right shape for a rule that only asks "does this
    piece land inside", and the wrong one here: telling a line that *ends* on
    a surface from one that goes *through* it needs to know where the line
    ends, which a segment does not.

    Returns the list rather than yielding it: the only caller wraps it in
    `list()` anyway, and at twelve thousand segments on `mega_figure` a
    generator frame per segment is real money.
    """
    runs: list[list[Vec2]] = []
    run: list[Vec2] = []
    for a, b in _shaft_segments(ctx, stroke):
        if not run or math.hypot(a.x - run[-1].x, a.y - run[-1].y) > _EPS_MM:
            if len(run) > 1:
                runs.append(run)
            run = [a]
        run.append(b)
    if len(run) > 1:
        runs.append(run)
    return runs


def _near(ctx: LintContext, order: Mapping[str, int], index: _PointIndex,
          verdict: dict[str, bool], stroke: Item,
          points: Sequence[Vec2]) -> list[Item]:
    """Shapes this run of the stroke could be inside, in id order.

    Prefiltered segment by segment rather than by the run's own bounding box:
    a leader across a panel has a box the width of the panel and touches four
    things, not four hundred.
    """
    found: dict[str, Item] = {}
    for a, b in zip(points, points[1:]):
        span = Rect.hull((a, b))
        for shape in index.overlapping(span):
            if shape.id in found or not _cuts_box(a, b, shape.bbox):
                continue
            allowed = verdict.get(shape.id)
            if allowed is None:
                allowed = verdict[shape.id] = _crossable(
                    ctx, order, stroke, shape)
            if allowed:
                found[shape.id] = shape
    return [found[key] for key in sorted(found)]


def _cuts_box(a: Vec2, b: Vec2, box: Rect) -> bool:
    """Whether the segment a->b meets `box`, by the slab clip.

    The bounding box of a long diagonal leader overlaps most of a panel, and
    the ray cast that follows is the expensive part of this rule: on
    `figures/drug_discovery.py` the honest test throws away four fifths of the
    candidates a box-overlap test hands over, and the rule runs three times
    faster for it.
    """
    lo, hi = 0.0, 1.0
    for delta, near, far in ((b.x - a.x, box.x0 - a.x, box.x1 - a.x),
                             (b.y - a.y, box.y0 - a.y, box.y1 - a.y)):
        if abs(delta) <= _EPS_MM:
            if near > _EPS_MM or far < -_EPS_MM:
                return False       # parallel to this slab and outside it
            continue
        first, second = near / delta, far / delta
        if first > second:
            first, second = second, first
        lo, hi = max(lo, first), min(hi, second)
        if lo > hi:
            return False
    return True


def _length(points: Sequence[Vec2]) -> float:
    return sum((b - a).length for a, b in zip(points, points[1:]))


def _inside_spans(outline: Trace, points: Sequence[Vec2]
                  ) -> list[tuple[float, float]]:
    """Where along a polyline, in millimetres from its first point, the line
    is inside a closed outline.

    The cast that finds the crossings is asked to sift as well. Every `t` the
    outline reports is a crossing of the same infinite line, so an odd number
    of them ahead of the first point puts that point inside, and the parity
    flips at each crossing after it. Most of what this rule tests is nowhere
    near the inside of anything, and for those the answer now costs one ray
    cast instead of two -- ray casts being what the rule costs: 770ms of the
    900ms `inklet.lint` spent on `figures/drug_discovery.py`.

    Parity narrows; `_inside` decides. A line running *along* an edge is the
    case parity gets wrong -- the edge is parallel to the ray and so invisible
    to it, and the crossings at the two ends of the box read as an entry and
    an exit. `stress/mega_figure.py` panel (r) sets a rule down the left edge
    of its caption, and parity alone called that 21mm through the text.
    """
    hits = outline.hits
    if hits is None:
        return []
    spans: list[tuple[float, float]] = []
    walked = 0.0
    for a, b in zip(points, points[1:]):
        span = b - a
        length = span.length
        if length <= _EPS_MM:
            continue
        found = hits(a, span)
        cuts = sorted({0.0, 1.0}.union(t for t in found if 0.0 < t < 1.0))
        maybe = sum(1 for t in found if t > 0.0) % 2 == 1
        for lo, hi in zip(cuts, cuts[1:]):
            if maybe and _inside(outline, a + span * ((lo + hi) / 2)):
                spans.append((walked + lo * length, walked + hi * length))
            maybe = not maybe
        walked += length
    return spans


def _through(spans: Sequence[tuple[float, float, str]],
             total: float) -> tuple[float, set[str]]:
    """(millimetres passing *through*, the parts they pass through).

    The distinction this rule turns on, and the reason the spans arrive here
    for the whole object at once rather than part by part. A leader arrives at
    the thing it names, and arriving means its last millimetre is inside the
    surface it points at -- `figures/drug_discovery.py` panel (a) has several
    of those and every one is the annotation working. Going *through* means
    entering and leaving again with the line carrying on somewhere else.

    A ribbon cartoon is drawn as hundreds of separate facets, so a line
    burrowing into one is inside a dozen of them in turn: measured facet by
    facet, the arrival looks like twelve crossings. Merged over the object
    first, it is one interval, and one that reaches the end of the line, which
    is what "arrived" means. The intervals that touch neither end are the
    incursions worth a sentence.

    Both ends inside is a third case and the stroke is exempt: a line that
    begins and finishes on the same object was drawn *on* it. That is what the
    dashed hydrogen bonds of `figures/drug_discovery.py` panel (b) are -- both
    their atoms sit on the kinase, and the ribbon strand they skip over on the
    way lies behind them, which is how molecular figures are drawn.
    """
    merged: list[tuple[float, float, set[str]]] = []
    for lo, hi, part in sorted(spans):
        if merged and lo <= merged[-1][1] + _EPS_MM:
            last = merged[-1]
            merged[-1] = (last[0], max(last[1], hi), last[2] | {part})
        else:
            merged.append((lo, hi, {part}))
    if (len(merged) > 1 and merged[0][0] <= _EPS_MM
            and merged[-1][1] >= total - _EPS_MM):
        return 0.0, set()
    run, involved = 0.0, set()
    for lo, hi, parts in merged:
        if lo <= _EPS_MM or hi >= total - _EPS_MM:
            continue       # the line starts or ends in here: it arrived
        run += hi - lo
        involved |= parts
    return run, involved


def _is_free_stroke(ctx: LintContext, item: Item) -> bool:
    """An unfilled path the author drew, that no router is answerable for."""
    if not item.draws or not isinstance(item.prim, PathPrim) or item.prim.filled:
        return False
    if item.node.kind in _UNCHOSEN_STROKES or item.is_computed:
        return False
    if ctx.paints_parts(item.id):
        return False
    return _link_owner(ctx, item.id) is None


def _crossable(ctx: LintContext, order: Mapping[str, int],
               stroke: Item, shape: Item) -> bool:
    """True when this stroke has no business being inside this shape."""
    if ctx.is_related(stroke.id, shape.id):
        return False
    if ctx.is_attached(stroke.id, shape.id):
        return False
    if ctx.abuts(stroke.id, shape.id):
        return False
    if ctx.crosses_by_declaration(stroke.id, shape.id):
        return False       # `inklet.crossing`: this line, through that part
    if _contains(shape.bbox, stroke.bbox):
        return False       # the stroke is drawn wholly within it
    if _hidden_behind(ctx, order, stroke, shape):
        return False
    return not _composed_with(ctx, stroke.id, shape.id)


def _paint_order(ctx: LintContext) -> Mapping[str, int]:
    """Each node's position in the order the renderer paints it.

    `LintContext.items` is sorted by id and `Placement.depth` counts nesting,
    so neither answers "which of these two is on top". The node table is built
    by a pre-order walk and every backend emits children in order, so its
    insertion order *is* the paint order.
    """
    return {node_id: index for index, node_id in enumerate(ctx.nodes)}


def _hidden_behind(ctx: LintContext, order: Mapping[str, int],
                   stroke: Item, shape: Item) -> bool:
    """Whether the shape covers the stroke where the two meet.

    A crossing is something a reader can see. A scatter marker sits on the
    line it belongs to, a knockout plate goes under a tick label precisely so
    that the gridline stops there, and an arrowhead covers the last millimetre
    of its own shaft: in all three the stroke passes *behind* opaque ink and
    there is nothing on the page to fix. `stress/mega_figure.py` panel (i)
    alone has fifty of them -- every marker on its tuning curves, and every
    radial label the curves pass under.

    Only opaque fill counts and only when it is painted later: a line under a
    hollow ring still shows through it. Text is asked about its own backdrop,
    because a label that knocks out what is behind it hides the line as
    surely as the plate does -- and a label with nothing behind it, crossed by
    a line, is the error this rule most wants to report.
    """
    later = order.get(shape.id, 0) > order.get(stroke.id, 0)
    if shape.is_backdrop:
        return later
    if shape.is_text:
        _, plate = ctx.background_of(shape)
        return plate is not None and order.get(plate.id, 0) > order.get(stroke.id, 0)
    return False


def _composed_with(ctx: LintContext, stroke_id: str, shape_id: str) -> bool:
    """Whether the stroke was drawn *inside* the picture it crosses.

    The deepest node holding both decides. `stack`, `place` and their kin put
    two finished things next to each other and leave both whole, so a line
    that reaches from one into the other came from outside; every other
    container is a drawing, and the stroke is one of its lines.

    Structural rather than geometric on purpose. The alternative -- "the
    stroke's endpoints are inside the shape" -- reads as sensible and is
    wrong on the case this rule exists for: a leader starts *on* the surface
    of the thing it names, which is exactly the shape it must not cross.
    """
    ancestor = ctx.common_ancestor(stroke_id, shape_id)
    if ancestor is None:
        return False
    node = ctx.nodes.get(ancestor)
    kind = node.kind if node is not None else None
    return is_abutting_kind(kind) or kind not in _COMPOSING_KINDS


def _crossings(ctx: LintContext, stroke: Item,
               depth: Mapping[str, float]) -> list[Diagnostic]:
    """One stroke's measured incursions, turned into findings in id order.

    Parts of one object are folded into one finding for the reason
    `LINK_CROSSES` gives: a line through a mesh cuts a dozen facets, and the
    author moves the label, not its eleventh triangle.
    """
    hit = {node_id: run for node_id, run in depth.items()
           if run >= _MIN_CROSSING_MM}
    crossed = [item for item in (ctx.item(node_id) for node_id in sorted(hit))
               if item is not None]
    if not crossed:
        return []

    cut_text, folded = _folded_text(crossed)
    groups: dict[str, list[Item]] = {}
    for item in crossed:
        if item.id in folded:
            continue
        home = item.id if item.is_text else _object_of(ctx, item.id)
        groups.setdefault(home, []).append(item)

    out: list[Diagnostic] = []
    for object_id in sorted(groups):
        parts = groups[object_id]
        texts = tuple(t for part in parts for t in cut_text.get(part.id, ()))
        note = ("" if not texts else ", cutting through "
                + ", ".join(ctx.item(t).described for t in texts))  # type: ignore[union-attr]
        label = _object_label(ctx, parts[0].id)
        deepest = max(hit[part.id] for part in parts)
        where = parts[0].bbox
        for part in parts[1:]:
            where = where.union(part.bbox)
        if len(parts) == 1:
            named = parts[0].described if parts[0].id == object_id else label
            through = f"{named} for {_mm(deepest)}"
        else:
            # One measurement, not one per part: the run was merged over the
            # object before it got here, because the millimetres an author can
            # act on are the ones the line spends inside the drawing, not the
            # ones it spends inside its eleventh triangle.
            through = (f"{label} for {_mm(deepest)}, "
                       f"cutting {len(parts)} of its parts")
        out.append(Diagnostic(
            code="PATH_CROSSES",
            severity=("error" if texts or any(p.is_text for p in parts)
                      else "warning"),
            message=f"{_stroke_label(ctx, stroke)} runs through {through}{note}",
            targets=(stroke.id,) + tuple(sorted(p.id for p in parts)) + texts,
            where=where,
            hint=(f"move {label} off the line, route the stroke around it, or "
                  f"declare the crossing with through= if it is deliberate"),
        ))
    return out


def _folded_text(crossed: Sequence[Item]) -> tuple[dict[str, list[str]], set[str]]:
    """Crossed text, attributed to the box holding it.

    Geometric rather than structural containment, for the reason
    `LintContext.background_of` gives: `frame()` puts the rectangle and its
    label side by side in the tree, so an ancestor test would miss the
    commonest idiom. One line through a box and the word inside it is one
    defect, so the word is named in the box's finding rather than in its own.
    """
    cut_text: dict[str, list[str]] = {}
    for item in crossed:
        if not item.is_text:
            continue
        holder = min((other for other in crossed
                      if not other.is_text and _contains(other.bbox, item.bbox)),
                     key=lambda o: (_area(o.bbox), o.id), default=None)
        if holder is not None:
            cut_text.setdefault(holder.id, []).append(item.id)
    return cut_text, {node_id for ids in cut_text.values() for node_id in ids}


def _stroke_label(ctx: LintContext, stroke: Item) -> str:
    """What to call the offending line. Its own name if it has one, otherwise
    the named thing it belongs to, and its kind either way -- `path4711` alone
    tells an author nothing about which line to look for."""
    named = stroke.node.name or ctx.nodes[_object_of(ctx, stroke.id)].name
    kind = stroke.node.kind or "path"
    return f"{kind} {named!r}" if named else f"{kind} {stroke.id}"


# -- near misses ----------------------------------------------------------


def stroke_near_misses(ctx: LintContext, clearance: float) -> list[Diagnostic]:
    """A stroke that clears a shape by less than the clearance, as `CROWDING`.

    `CROWDING` compares bounding boxes, and `_pairable` drops unfilled paths
    from that comparison because a diagonal line's box is mostly empty. The
    cost of the exclusion is that the one thing a stroke does wrong *without*
    crossing anything -- coming within a tenth of a millimetre of a word and
    reading, at print size, as an underline that lost its way -- was reported
    by nothing at all. `PATH_CROSSES` starts at the moment the line is inside
    the shape; this is the millimetre before that.

    Measured properly: the real distance from each segment to the shape's own
    outline, which for a filled path or a cutout is its rings and for anything
    else is its box. Nothing else would do -- against boxes alone, a leader
    that clears a curve by two millimetres reads as touching it.

    Everything `PATH_CROSSES` exempts is exempt here too, through the same
    `_crossable`: a rule that stays quiet about a line inside a picture and
    then complains that the same line came close to it would be worse than
    either answer on its own. A stroke that actually reaches the outline is
    left alone for the same reason -- from there the crossing rule owns it,
    and a graze too short for `_MIN_CROSSING_MM` is a graze.

    One finding per (stroke, object) pair, tightest first, keyed like
    `_crowded_objects`: an author moves the leader, not the facet it grazed.
    """
    strokes = [item for item in ctx.items if _is_free_stroke(ctx, item)]
    if not strokes:
        return []
    targets = [item for item in ctx.items
               if _pairable(ctx, item) and _link_owner(ctx, item.id) is None
               and item.node.kind != HEAD_KIND]
    if not targets:
        return []

    parts: dict[str, int] = {}
    for item in targets:
        home = _object_of(ctx, item.id)
        parts[home] = parts.get(home, 0) + 1
    targets = [item for item in targets
               if parts[_object_of(ctx, item.id)] <= _TEXTURED_PARTS]
    if not targets:
        return []

    index = _PointIndex(targets)
    order = _paint_order(ctx)
    home = {item.id: (ctx.abutting_home(item.id) or _sealed_in(ctx, item)
                      or _drawn_into(ctx, item)) for item in targets}
    shapes: dict[str, _Edges | None] = {}
    out: list[Diagnostic] = []
    for stroke in strokes:
        mine = (ctx.abutting_home(stroke.id) or _sealed_in(ctx, stroke)
                or _drawn_into(ctx, stroke))
        source = _source_home(ctx, stroke.id)
        verdict: dict[str, bool] = {}
        nearest: dict[str, float] = {}
        touched: dict[str, Item] = {}
        if not any(True for _ in index.overlapping(stroke.bbox.pad(clearance))):
            continue        # nothing pairable within reach of the whole stroke
        runs = _runs_of(ctx, stroke)
        for points in runs:
            for a, b in zip(points, points[1:]):
                reach = Rect.hull((a, b)).pad(clearance)
                for shape in index.overlapping(reach):
                    if not _boxes_touch(reach, shape.bbox):
                        continue
                    allowed = verdict.get(shape.id)
                    if allowed is None:
                        allowed = verdict[shape.id] = (
                            (mine is None or mine != home.get(shape.id))
                            and not _one_drawing(ctx, source, stroke, shape)
                            and _crossable(ctx, order, stroke, shape))
                    if not allowed:
                        continue
                    touched[shape.id] = shape
                    if shape.id not in shapes:
                        shapes[shape.id] = _Edges.of(shape)
                    gap = _clearance_to(a, b, shape, shapes[shape.id],
                                        clearance)
                    if gap is None or gap >= clearance - _EPS_MM:
                        continue
                    nearest[shape.id] = min(nearest.get(shape.id, gap), gap)
        out.extend(_near_missed(ctx, stroke, runs, nearest, touched, shapes,
                                clearance))
    return out


def _one_drawing(ctx: LintContext, source: str | None, stroke: Item,
                 shape: Item) -> bool:
    """Whether a stroke and a computed shape came out of the same group.

    `_drawn_into` asks this of a `inklet.plot` panel, where the panel node itself
    is the giveaway. A chart built by hand has no panel to point at: panel (i)
    of `stress/mega_figure.py` draws its polar tuning curves as a `stack` of
    layers, and the markers on a curve sit a tenth of a millimetre off the
    line they belong to because that is where the measurement is. Seventeen of
    those, each offering to move a data point, is the whole of what this rule
    could contribute to that panel.

    The computed side is what makes it safe to ask. Two arranged things
    sharing a container are still two things; a data mark sharing one with the
    stroke that drew its curve is one picture of one measurement.
    """
    return (shape.is_computed and source is not None
            and source == _source_home(ctx, shape.id))


def _reach_from_ends(points: Sequence[Vec2], shape: Item,
                     edges: "_Edges | None", limit: float) -> float:
    """How close an *arriving* end of the run gets to a shape, or infinity
    when neither end of it is arriving.

    `_through` exempts a stroke whose last millimetre is inside the thing it
    points at, because arriving is what a leader does. A leader that stops two
    hundredths of a millimetre short of the same surface has done the same
    thing, and `figures/drug_discovery.py` draws eight of them. So a near miss
    at the tip of the line is not a finding; one along its middle is.

    Arriving means heading in, which is why the segment behind the tip is
    measured too. A rule drawn three tenths of a millimetre above a box runs
    *along* it: its ends are the closest points as well, and without that
    second question the whole line would read as two arrivals.
    """
    reach = ((lambda point: _segment_to_box(point, point, shape.bbox))
             if edges is None else
             (lambda point: edges.distance(point, point, limit)))
    best = float("inf")
    for tip, behind in ((points[0], points[1]), (points[-1], points[-2])):
        if edges is not None and _within(shape.bbox, tip) and _inside(
                edges.outline, tip):
            return 0.0                      # it did not stop short: it landed
        near = reach(tip)
        if near < limit and near < reach(behind) - _EPS_MM:
            best = min(best, near)
    return best


def _within(box: Rect, point: Vec2) -> bool:
    return box.x0 <= point.x <= box.x1 and box.y0 <= point.y <= box.y1


def _clearance_to(a: Vec2, b: Vec2, shape: Item,
                  edges: "_Edges | None", limit: float) -> float | None:
    """How far the segment a->b stays clear of `shape`, or None when it does
    not: touching, grazing and passing through are all the crossing rule's."""
    if edges is None:
        gap = _segment_to_box(a, b, shape.bbox)
        return gap if gap > _EPS_MM else None
    # Distance first, ray cast second. Anything the buckets say is further
    # than the clearance is not a finding whichever side of the outline it is
    # on, and `Trace.hits` is thirty times the price of the lookup: asked the
    # other way round, this rule spent 2.3 of its 2.9 seconds on
    # `figures/drug_discovery.py` proving that leaders are outside a protein.
    gap = edges.distance(a, b, limit)
    if gap >= limit or gap <= _EPS_MM:
        return None
    outline = edges.outline
    if _inside(outline, a) or _inside(outline, b):
        return None                         # inside it: the crossing rule's
    return gap


def _segment_to_box(a: Vec2, b: Vec2, box: Rect) -> float:
    """Shortest distance between a segment and an axis-aligned box; 0 when
    they meet.

    Also the near-miss query's prefilter: a shape whose *box* the line clears
    by a millimetre cannot have an outline that does not, and answering that
    in twenty floating-point operations is what keeps the rule from flattening
    two thousand ribbon facets into edge tables to find out.
    """
    if _cuts_box(a, b, box):
        return 0.0
    ax, ay, bx, by = a.x, a.y, b.x, b.y
    corners = ((box.x0, box.y0), (box.x1, box.y0),
               (box.x1, box.y1), (box.x0, box.y1))
    return min(_reach(ax, ay, bx, by, cx, cy, dx, dy)
               for (cx, cy), (dx, dy) in zip(corners, corners[1:] + corners[:1]))


def _segment_to_segment(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> float:
    """Shortest distance between two segments, crossings included (0).

    Spelled out in floats rather than `Vec2` arithmetic. It is the innermost
    loop of the near-miss query -- hundreds of thousands of calls on
    `figures/drug_discovery.py` -- and every operator here would otherwise
    allocate a frozen dataclass to throw away.
    """
    return _reach(a.x, a.y, b.x, b.y, c.x, c.y, d.x, d.y)


def _reach(ax: float, ay: float, bx: float, by: float,
           cx: float, cy: float, dx: float, dy: float) -> float:
    ux, uy = bx - ax, by - ay
    vx, vy = dx - cx, dy - cy
    denom = ux * vy - uy * vx
    if abs(denom) > _EPS_MM * _EPS_MM:
        wx, wy = cx - ax, cy - ay
        t = (wx * vy - wy * vx) / denom
        u = (wx * uy - wy * ux) / denom
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            return 0.0
    return min(_reach_point(ax, ay, cx, cy, dx, dy),
               _reach_point(bx, by, cx, cy, dx, dy),
               _reach_point(cx, cy, ax, ay, bx, by),
               _reach_point(dx, dy, ax, ay, bx, by))


def _reach_point(px: float, py: float, ax: float, ay: float,
                 bx: float, by: float) -> float:
    ux, uy = bx - ax, by - ay
    square = ux * ux + uy * uy
    if square <= _EPS_MM * _EPS_MM:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * ux + (py - ay) * uy) / square
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(px - ax - ux * t, py - ay - uy * t)


def _point_to_segment(point: Vec2, a: Vec2, b: Vec2) -> float:
    return _reach_point(point.x, point.y, a.x, a.y, b.x, b.y)


#: Past this many drawn parts, an object is a texture rather than a shape: a
#: protein ribbon, a shaded mesh, a hatch. "The leader passes 0.04mm from the
#: kinase" is a sentence about a surface a reader cannot see the edge of, and
#: the two rules that can say something useful about it already do --
#: `PATH_CROSSES` when the line goes in, and `CROWDING`'s own
#: `_crowded_objects` when another *shape* comes near. Cutting them here is
#: also what keeps the query off `figures/drug_discovery.py`'s two thousand
#: ribbon facets, which cost more than every other rule on that page together.
_TEXTURED_PARTS = 64


#: Below this many edges a flat scan beats bucketing them: the buckets cost a
#: dict lookup per cell and a set per query, and a label plate has four sides.
_FLAT_EDGES = 48


class _Edges:
    """A filled shape's outline as edges, bucketed so a segment can ask only
    the ones near it.

    `figures/drug_discovery.py` draws its kinase as ribbon facets holding some
    tens of thousands of edges between them, and a leader is measured against
    a shape once per segment. Asked flat, the distance query cost four and a
    half seconds on that page -- nine tenths of `inklet.lint`. Bucketed, with the
    `Trace` built once instead of once per query and the ray cast left until
    the buckets say something is close, it costs a fraction of that and
    answers exactly the same.
    """

    __slots__ = ("_cell", "_cells", "_edges", "_item", "_outline")

    def __init__(self, item: Item, rings: Sequence[Sequence[Vec2]]) -> None:
        self._item = item
        self._outline: Trace | None = None
        self._edges = [(first, second)
                       for ring in rings
                       for first, second in zip(ring, tuple(ring[1:]) + (ring[0],))]
        self._cells: dict[tuple[int, int], list[int]] | None = None
        box = item.bbox
        self._cell = max(box.width, box.height, _EPS_MM) / max(
            1.0, min(64.0, len(self._edges) ** 0.5))
        if len(self._edges) > _FLAT_EDGES:
            self._cells = {}
            for index, (first, second) in enumerate(self._edges):
                self._file(index, first, second)

    @classmethod
    def of(cls, item: Item) -> "_Edges | None":
        rings = _rings(item)
        return None if rings is None else cls(item, rings)

    @property
    def outline(self) -> Trace:
        if self._outline is None:
            self._outline = _outline(self._item)
        return self._outline

    def _file(self, index: int, first: Vec2, second: Vec2) -> None:
        cell = self._cell
        assert self._cells is not None
        for cx in range(int(min(first.x, second.x) // cell),
                        int(max(first.x, second.x) // cell) + 1):
            for cy in range(int(min(first.y, second.y) // cell),
                            int(max(first.y, second.y) // cell) + 1):
                self._cells.setdefault((cx, cy), []).append(index)

    def distance(self, a: Vec2, b: Vec2, limit: float) -> float:
        """Shortest distance from the segment a->b to the outline, or `limit`
        when the outline stays further away than that.

        Exact where it matters and cheap where it does not: every edge nearer
        than `limit` lies in a cell the padded query box covers, so the
        buckets outside it can be left unread. Callers only ever ask whether
        something is closer than the clearance.
        """
        best = limit
        ax, ay, bx, by = a.x, a.y, b.x, b.y
        lo_x, hi_x = (ax, bx) if ax <= bx else (bx, ax)
        lo_y, hi_y = (ay, by) if ay <= by else (by, ay)
        for first, second in self._near(a, b, limit):
            cx, cy, dx, dy = first.x, first.y, second.x, second.y
            # The cheapest possible rejection, and most edges take it: two
            # boxes that stay `best` apart cannot hold two segments that do
            # not. Written out because this is the loop, not a helper.
            if (min(cx, dx) - hi_x >= best or lo_x - max(cx, dx) >= best
                    or min(cy, dy) - hi_y >= best or lo_y - max(cy, dy) >= best):
                continue
            gap = _reach(ax, ay, bx, by, cx, cy, dx, dy)
            if gap < best:
                best = gap
        return best

    def _near(self, a: Vec2, b: Vec2,
              limit: float) -> Iterable[tuple[Vec2, Vec2]]:
        if self._cells is None:
            return self._edges
        cell = self._cell
        x0 = int((min(a.x, b.x) - limit) // cell)
        x1 = int((max(a.x, b.x) + limit) // cell)
        y0 = int((min(a.y, b.y) - limit) // cell)
        y1 = int((max(a.y, b.y) + limit) // cell)
        seen: set[int] = set()
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                for index in self._cells.get((cx, cy), ()):
                    if index not in seen:
                        seen.add(index)
                        yield self._edges[index]


def _near_missed(ctx: LintContext, stroke: Item,
                 runs: Sequence[Sequence[Vec2]], nearest: Mapping[str, float],
                 touched: Mapping[str, Item],
                 shapes: Mapping[str, "_Edges | None"],
                 clearance: float) -> list[Diagnostic]:
    """One stroke's near misses, folded onto the objects they were near.

    Folded *before* the arrival test, the way `_through` merges its spans over
    the object first. A leader into `figures/drug_discovery.py`'s kinase stops
    on one ribbon facet and skims the next one along on its way in; asked
    facet by facet the second is a near miss in the middle of the line, and
    asked of the kinase it is the same arrival.

    Which is also why the arrival is measured here rather than in the loop
    above: it needs every part of the object the stroke came near, including
    the one it landed *in* and so has no gap to report, and it is only worth
    knowing about the handful of objects that produced a finding at all.
    """
    def home_of(item: Item) -> str:
        return item.id if item.is_text else _object_of(ctx, item.id)

    objects: dict[str, list[tuple[Item, float]]] = {}
    for node_id in sorted(nearest):
        item = ctx.item(node_id)
        if item is not None:
            objects.setdefault(home_of(item), []).append((item, nearest[node_id]))
    families: dict[str, list[Item]] = {}
    for item in touched.values():
        families.setdefault(home_of(item), []).append(item)

    out: list[Diagnostic] = []
    for object_id in sorted(objects):
        parts = objects[object_id]
        tightest = min(gap for _, gap in parts)
        if _arrived_at(runs, families.get(object_id, ()), shapes,
                       tightest + _EPS_MM):
            continue
        where = parts[0][0].bbox
        for item, _ in parts[1:]:
            where = where.union(item.bbox)
        named = (parts[0][0].described if len(parts) == 1
                 and parts[0][0].id == object_id else _object_label(ctx, object_id))
        out.append(Diagnostic(
            code="CROWDING",
            severity="info",
            message=(f"{_stroke_label(ctx, stroke)} passes within "
                     f"{_mm(tightest)} of {named}, under the "
                     f"{_mm(clearance)} clearance"),
            targets=tuple(sorted([stroke.id] + [i.id for i, _ in parts])),
            where=where.union(stroke.bbox),
            hint=(f"add {_mm(clearance - tightest)} of clearance, or declare "
                  f"the touch with inklet.abutting if the line is meant to reach "
                  f"{named}"),
        ))
    return out


def _arrived_at(runs: Sequence[Sequence[Vec2]], parts: Iterable[Item],
                shapes: Mapping[str, "_Edges | None"], limit: float) -> bool:
    """Whether an end of the stroke gets at least as close as its tightest
    near miss -- in which case the line reached the object rather than
    passing it."""
    for part in parts:
        edges = shapes.get(part.id)
        for points in runs:
            if _reach_from_ends(points, part, edges, limit) <= limit:
                return True
    return False
