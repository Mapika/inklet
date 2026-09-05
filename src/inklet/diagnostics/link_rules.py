"""Three ways a connector can be drawn perfectly and still be unreadable.

All three are cases where nothing collides, nothing overflows and every
measurement is in range -- the shapes of defect `LINK_CROSSES` was written for,
one step further in, where the ink in the way belongs to a connector.

* `COINCIDENT_SHAFT`: two routes lying on the same line. Each is correct on its
  own; together they are one line wearing two arrowheads, and half the graph
  the author drew is not on the page.
* `LINK_CROSSES_LINK`: two routes that meet at a point. A clean X is ordinary
  in a branch-and-merge flow and reads fine, which is why this is an `info`;
  a crossing that runs through one of the two labels does not, and that is a
  warning.
* `LABEL_COVERS_SHAFT`: a link's own label plate over its own elbow. The placer
  keeps a label off every *other* shaft on the page and is exempt from lint on
  its own by design, because a label touching the line it names is what a label
  is; what is not exempt is a plate that swallows the corner and leaves a
  millimetre of ghost sliver poking out the far side.

All three reuse `rules._shaft_segments`, so all three follow a rounded corner
without knowing what a bezier is, and all three read one pass of
`_parts_by_link` rather than walking the item list once per connector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from ..core import PathPrim, Rect, Vec2
from ..links import (CONNECTOR_KIND, DEFAULT_ARROW_SIZE, HEAD_KIND, LINK_KIND,
                     link_ends)
from .rules import (
    Diagnostic, Item, LintContext, _arrow_axis, _candidate_pairs, _EPS_MM,
    _in_link_label, _link_owner, _MIN_CROSSING_MM, _mm, _nearest_in,
    _opaque_fill, _shaft_segments,
)

__all__ = ["rule_coincident_shaft", "rule_label_covers_shaft",
           "rule_link_crosses_link"]

#: Shared length at which two shafts stop looking like a crossing and start
#: looking like one line. A stroke is a quarter of a millimetre wide, so a
#: millimetre of coincidence is four stroke widths of a line that is not there.
_MIN_COINCIDENT_MM = 1.0

#: How far apart two shafts may be and still be the same line. About half a
#: stroke width: closer than this and the upper one hides the lower one.
_COLLINEAR_MM = 0.15

#: sin of the angle at which two segments stop being parallel -- 0.03 is 1.7
#: degrees, which over a 20mm run is 0.6mm of divergence, visible.
_PARALLEL_SIN = 0.03

_EPS = 1e-9


# -- COINCIDENT_SHAFT -----------------------------------------------------


def rule_coincident_shaft(ctx: LintContext) -> list[Diagnostic]:
    """Two links drawn along the same line, one hidden under the other.

    Found on the electrolyser poster: two orthogonal routes to different
    neighbours, both aimed at box centres, agreed on the centre height of the
    box they left and shared six millimetres of it. Nothing in the linter
    could see it -- the shafts are unfilled paths, which `_pairable` drops for
    the same reason it has to, and two connectors overlapping is ordinary in a
    branch-and-merge flow when they *cross*.

    The distinction this rule draws is collinear versus crossing: a crossing is
    two lines meeting at a point, which a reader resolves instantly, and a
    shared run is two lines the reader cannot tell apart at all.

    A shared trunk -- `link(a, [b, c, d])` -- needs no exemption, and that is
    not luck. The segments are keyed by the link that owns them and a trunk is
    one link, so its stem is one run of one route however many leaves hang off
    it; only two *different* links agreeing on a line are ever paired here.
    Which is also the rule for reading a report: a collinear run means two
    links, and drawing them as one trunk is usually the fix.

    Reported once per pair of links, at the longest run they share, because
    an orthogonal route agreeing with another over three of its segments is
    one defect with one fix.
    """
    if not ctx.attachments:
        return []
    owners: list[str] = []
    spans: list[tuple[Vec2, Vec2]] = []
    for item in ctx.items:
        if not _is_shaft(item):
            continue
        owner = _link_owner(ctx, item.id)
        if owner is None or _in_link_label(ctx, item.id):
            continue
        for a, b in _shaft_segments(ctx, item):
            owners.append(owner)
            spans.append((a, b))
    if len(spans) < 2:
        return []

    # Padding the boxes here rather than asking `_candidate_pairs` to do it
    # keeps the naive branch (under 200 segments, where most figures live)
    # honest: it does not pad, and a vertical shaft's box is zero-wide.
    boxes = [Rect.hull(span).pad(_COLLINEAR_MM) for span in spans]
    worst: dict[tuple[str, str], tuple[float, Rect]] = {}
    for i, j in _candidate_pairs(boxes, apart=owners):
        run = _collinear_run(spans[i], spans[j])
        if run is None:
            continue
        length, where = run
        if length < _MIN_COINCIDENT_MM:
            continue
        pair = tuple(sorted((owners[i], owners[j])))
        best = worst.get(pair)                      # type: ignore[arg-type]
        if best is None or length > best[0]:
            worst[pair] = (length, where)           # type: ignore[index]

    out: list[Diagnostic] = []
    for (first, second), (length, where) in sorted(worst.items()):
        out.append(Diagnostic(
            code="COINCIDENT_SHAFT",
            severity="warning",
            message=(f"{_between(ctx, first)} and {_between(ctx, second)} run "
                     f"along the same line for {_mm(length)}; the page shows "
                     f"one line wearing two arrowheads"),
            targets=(first, second),
            where=where,
            hint=("if they leave the same box, draw them as one trunk -- "
                  "link(a, [b, c]) is a stem that branches, and a stem is one "
                  "line on purpose; otherwise aim one at an anchor, since "
                  "link(a.at('n'), b) leaves from a different point than "
                  "link(a, c), or give one route= a different shape"),
        ))
    return out


def _is_shaft(item: Item) -> bool:
    return (item.draws and isinstance(item.prim, PathPrim)
            and not item.prim.filled)


def _between(ctx: LintContext, owner: str) -> str:
    """`link12 (source -> target)`, on one line whatever the boxes are called.

    A node named over two lines -- `inklet.box("MSigDB\nhallmarks")` -- carries
    the newline in its name, and a diagnostic message with a line break in the
    middle of it breaks every reader of the report, `format_report` included.
    """
    ends = link_ends(ctx.attachments.get(owner, ()))
    named = " -> ".join(" ".join(ctx.label(end).split()) for end in ends)
    return f"{ctx.label(owner)} ({named})" if named else ctx.label(owner)


@dataclass(slots=True)
class _Parts:
    """One routed connector, as the three rules in this file see it."""

    #: The unfilled paths the router drew for the route itself.
    shafts: list[Item] = field(default_factory=list)
    #: Boxes of the opaque shapes inside its label group, which hide ink.
    plates: list[Rect] = field(default_factory=list)
    #: Length of its arrowhead along the shaft, or None when it wears none.
    head: float | None = None


def _parts_by_link(ctx: LintContext) -> dict[str, _Parts]:
    """{link id: the parts of it these rules measure}, in one pass.

    One pass rather than one per link: a sheet with sixty connectors on four
    thousand nodes would otherwise walk the whole item list sixty times to find
    three children each.

    A label group's own bbox is not the plate -- it includes the type, which
    hides nothing. Only a filled shape inside it paints over the shaft.
    """
    found: dict[str, _Parts] = {}
    for item in ctx.items:
        if not item.draws:
            continue
        owner = _link_owner(ctx, item.id)
        if owner is None or ctx.nodes[owner].kind != LINK_KIND:
            continue
        parts = found.setdefault(owner, _Parts())
        if _in_link_label(ctx, item.id):
            if (not item.is_text and item.is_shape
                    and _opaque_fill(item.style.fill)):
                parts.plates.append(item.bbox)
        elif item.node.kind == CONNECTOR_KIND and _is_shaft(item):
            parts.shafts.append(item)
        elif item.node.kind == HEAD_KIND:
            axis = _arrow_axis(item)
            if axis is not None:
                length = (axis[0] - axis[1]).length
                parts.head = length if parts.head is None else max(parts.head,
                                                                   length)
    return found


def _collinear_run(first: tuple[Vec2, Vec2],
                   second: tuple[Vec2, Vec2]) -> tuple[float, Rect] | None:
    """Length of line the two segments share, and where, or None.

    Parallel, close, and overlapping when projected -- in that order, because
    the first two are two multiplications each and the projection is only worth
    computing for a pair that has passed them.
    """
    a1, b1 = first
    a2, b2 = second
    span = b1 - a1
    length = span.length
    other = b2 - a2
    if length < _EPS or other.length < _EPS:
        return None
    unit = span * (1.0 / length)
    if abs(unit.cross(other * (1.0 / other.length))) > _PARALLEL_SIN:
        return None
    normal = unit.perp()
    if max(abs((a2 - a1).dot(normal)), abs((b2 - a1).dot(normal))) > _COLLINEAR_MM:
        return None
    low, high = sorted(((a2 - a1).dot(unit), (b2 - a1).dot(unit)))
    low, high = max(0.0, low), min(length, high)
    if high - low < _EPS:
        return None
    return high - low, Rect.hull((a1 + unit * low, a1 + unit * high))


# -- LINK_CROSSES_LINK ----------------------------------------------------

#: Two crossings closer together than this are one crossing found twice: a
#: polyline's segments share their end vertices, so a route crossing another
#: exactly at a corner is reported by both of the segments meeting there.
_SAME_CROSSING_MM = 0.05

#: Slack on the segment parameters, so a crossing at a vertex is not lost to
#: float noise. In units of the segment, and 1e-9 of a 20mm leg is a nanometre.
_ENDPOINT_SLACK = 1e-9


def rule_link_crosses_link(ctx: LintContext) -> list[Diagnostic]:
    """Two connectors that cross each other.

    Neither `LINK_CROSSES` nor `PATH_CROSSES` can see this. The first walks a
    shaft against the *items* it might be inside, and `_pairable` drops every
    unfilled path before it gets there -- a shaft has no interior to be inside
    of. The second is for the strokes no router is answerable for. So two
    routed connectors were invisible to the whole linter, and the first draft
    of `examples/state_machine.py` put its `retry` elbow straight through the
    `error` shaft and reported `clean, 0 diagnostics`.

    An `info`, because a crossing is not by itself a defect: a branch-and-merge
    flow crosses its own lines constantly and a reader resolves a clean X
    without thinking about it. It is reported at all because a *count* is what
    an author cannot see -- eight crossings in one panel is a routing problem
    whatever any one of them looks like -- and because of the case that is a
    real defect, which is the one this is a `warning` for: a shaft through the
    other link's label plate. The plate is opaque, so one of the two lines
    stops dead in the middle of a word.

    What is exempt, and why each one has to be:

    * A trunk against its own strands, and a self-loop against its own shaft.
      Both are one link -- `link(a, [b, c])` is a single route with a subpath
      per branch -- and the pairs are keyed by the link that owns them, so
      neither needs an exemption written for it.
    * Two links that share an endpoint, crossing within one arrowhead of it.
      Routes clipped to the same box arrive along different bearings and the
      last millimetre of a fan can tangle; the fix for that is the spacing of
      the boxes, which is `CROWDING`'s arrowhead-fan finding, not a crossing.
    * Collinear runs. Two segments lying along one line have no crossing point
      to report, and `COINCIDENT_SHAFT` -- the worse defect of the two -- owns
      them.
    """
    if not ctx.attachments:
        return []
    parts = _parts_by_link(ctx)
    owners: list[str] = []
    spans: list[tuple[Vec2, Vec2]] = []
    for owner in sorted(parts):
        for item in sorted(parts[owner].shafts, key=lambda i: i.id):
            for span in _shaft_segments(ctx, item):
                owners.append(owner)
                spans.append(span)
    if len(spans) < 2:
        return []

    # A vertical shaft's hull is zero-wide, and `_candidate_pairs` only pads
    # when it buckets; padding here keeps the naive branch honest too.
    boxes = [Rect.hull(span).pad(_EPS_MM) for span in spans]
    crossings: dict[tuple[str, str], list[Vec2]] = {}
    for i, j in _candidate_pairs(boxes, apart=owners):
        point = _crossing_point(spans[i], spans[j])
        if point is None:
            continue
        pair = (owners[i], owners[j]) if owners[i] < owners[j] else (owners[j],
                                                                    owners[i])
        if _at_a_shared_end(ctx, parts, pair, point):
            continue
        found = crossings.setdefault(pair, [])
        if not any((point - seen).length <= _SAME_CROSSING_MM for seen in found):
            found.append(point)

    out: list[Diagnostic] = []
    for pair, points in sorted(crossings.items()):
        out.append(_crossing_finding(ctx, parts, pair, points))
    return out


def _crossing_finding(ctx: LintContext, parts: Mapping[str, _Parts],
                      pair: tuple[str, str], points: Sequence[Vec2]
                      ) -> Diagnostic:
    """One pair of links, one finding, whatever the two routes do to each other."""
    first, second = pair
    cut = (_cut_plates(ctx, parts, first, second)
           + _cut_plates(ctx, parts, second, first))
    where = Rect.hull(points)
    places = "" if len(points) == 1 else f" at {len(points)} points"
    at = (f" at {points[0].x:.2f}, {points[0].y:.2f}mm" if len(points) == 1
          else "")
    if cut:
        detail = (f" -- and {_mm(max(cut))} of the crossing runs under a label "
                  f"plate, so one of the two lines stops in the middle of a word")
    else:
        detail = ""
    return Diagnostic(
        code="LINK_CROSSES_LINK",
        severity="warning" if cut else "info",
        message=(f"{_between(ctx, first)} and {_between(ctx, second)} cross"
                 f"{places}{at}{detail}"),
        targets=pair,
        where=where,
        hint=("move the label off the crossing with label_side= or a larger "
              "label_offset=, or route one link around the other with "
              "waypoints= or route=\"avoid\"" if cut else
              "a clean crossing reads fine; if there are too many of them, "
              "reorder the boxes so fewer routes have to meet, or give one "
              "link waypoints= to take it round"),
    )


def _cut_plates(ctx: LintContext, parts: Mapping[str, _Parts], owner: str,
                other: str) -> list[float]:
    """How far each of `owner`'s label plates is crossed by `other`'s shafts.

    A plate is opaque and is drawn with its own link, so whichever of the two
    was routed second covers the other: either the word is struck through or
    the line vanishes into it. Both are the same finding.
    """
    plates = parts[owner].plates
    if not plates:
        return []
    found: list[float] = []
    for plate in plates:
        run = 0.0
        for item in parts[other].shafts:
            for a, b in _shaft_segments(ctx, item):
                inside = _inside_run(plate, a, b)
                if inside is not None:
                    run += (inside[1] - inside[0]) * (b - a).length
        if run >= _MIN_CROSSING_MM:
            found.append(run)
    return found


def _at_a_shared_end(ctx: LintContext, parts: Mapping[str, _Parts],
                     pair: tuple[str, str], point: Vec2) -> bool:
    """Whether a crossing is the tangle of two arrows landing on one box.

    Two routes clipped to the same shape arrive at different points on its
    rim, and between the rim and the first bend they can cross -- eight links
    into one hub cross each other within a couple of millimetres of it, every
    time, and there is nothing about any single one of those crossings for an
    author to move. What there is to say is that the fan is too tight for the
    box, and `CROWDING` says it once for the whole fan.

    An arrowhead's length is the measure because it is the length of route the
    reader cannot see anyway: under the head, plus the standoff the router cut
    the shaft back by to fit it.
    """
    first, second = pair
    shared = (set(link_ends(ctx.attachments.get(first, ())))
              & set(link_ends(ctx.attachments.get(second, ()))))
    if not shared:
        return False
    reach = max(parts[first].head or DEFAULT_ARROW_SIZE,
                parts[second].head or DEFAULT_ARROW_SIZE)
    for end in shared:
        placement = ctx.placements.get(end)
        box = None if placement is None else placement.bbox
        if box is not None and (_nearest_in(box, point) - point).length <= reach:
            return True
    return False


def _crossing_point(first: tuple[Vec2, Vec2],
                    second: tuple[Vec2, Vec2]) -> Vec2 | None:
    """Where two segments cross, or None when they do not meet at a point.

    Parallel is None on purpose, collinear included: two lines lying along one
    another have no crossing, they have a shared run, and `COINCIDENT_SHAFT`
    is the rule that measures those.

    So is any meeting at an end of either segment, and that clause carries
    three cases at once: two routes leaving one box leave it at the same point
    on its rim; two routes that share a line turn off it where one of them
    still runs, so the corner of one lands on the middle of the other; and a
    polyline's own vertex is an end twice over. In none of them does a line
    pass through another line, which is what a crossing is and what a reader
    has to unpick. Meeting is `COINCIDENT_SHAFT`'s business when it is
    anyone's.
    """
    a1, b1 = first
    a2, b2 = second
    span, other = b1 - a1, b2 - a2
    denom = span.cross(other)
    if abs(denom) < _EPS:
        return None
    delta = a2 - a1
    t = delta.cross(other) / denom
    u = delta.cross(span) / denom
    if not (-_ENDPOINT_SLACK <= t <= 1.0 + _ENDPOINT_SLACK
            and -_ENDPOINT_SLACK <= u <= 1.0 + _ENDPOINT_SLACK):
        return None
    point = a1 + span * t
    if _at_an_end(point, first) or _at_an_end(point, second):
        return None
    return point


def _at_an_end(point: Vec2, segment: tuple[Vec2, Vec2]) -> bool:
    return min((point - segment[0]).length,
               (point - segment[1]).length) <= _SAME_CROSSING_MM


# -- LABEL_COVERS_SHAFT ---------------------------------------------------

#: Visible shaft past the plate below which the remainder reads as an artefact
#: rather than as a line. A millimetre and a half is about half an arrowhead.
_MIN_STUB_MM = 1.5

#: Shaft the plate has to cover before this is the plate's doing at all. A
#: label offset onto the outside of a corner grazes its own line by a fraction
#: of a millimetre on any curved route, and that is the exemption being kept.
_MIN_COVERED_MM = 1.0

#: Below this a run is not ink: a plate edge landing exactly on the end of a
#: shaft leaves a mathematical sliver that nothing draws.
_INVISIBLE_MM = 0.05


def rule_label_covers_shaft(ctx: LintContext) -> list[Diagnostic]:
    """A link's own label plate drawn over its own elbow.

    Label-on-own-link is exempt from every other rule by design -- a label
    beside the line it names touches that line, and reporting it would fire on
    every figure with a labelled connector. The exemption is about *touching*.
    A plate is opaque, and when a two-elbow route folds back under it the
    corner is simply gone: what the reader sees is a stub of line, a word, and
    an arrowhead that appears to belong to nothing.

    A short route with a corner in the middle of it is how it happens, which
    makes the default `label_side="center"` the usual culprit. The placer
    offsets the label along the normal at one point of the route and knows
    nothing about the rest of it, so a corner two millimetres further on
    lands underneath.

    Only a label with an opaque plate can do this: bare type over a line is
    ugly but the line is still there, and the router's own placement search
    already prefers open space. The finding therefore names the plate, and the
    fix is a different `label_side=` or a larger `label_offset=`.
    """
    if not ctx.attachments:
        return []
    by_link = _parts_by_link(ctx)
    out: list[Diagnostic] = []
    for owner in sorted(by_link):
        plates, shafts = by_link[owner].plates, by_link[owner].shafts
        if not plates or not shafts:
            continue
        plate = plates[0]
        for box in plates[1:]:
            plate = plate.union(box)
        measured = _visible_runs(ctx, shafts, plate)
        if measured is None:
            continue
        total, covered, runs = measured
        if covered < _MIN_COVERED_MM:
            continue
        visible = [run for run in runs if run >= _INVISIBLE_MM]
        stub = min(visible) if visible else 0.0
        if visible and stub >= _MIN_STUB_MM:
            continue
        if not visible:
            detail = (f"covers all {_mm(total)} of its shaft, leaving the "
                      f"arrowheads with no line between them")
        else:
            detail = (f"covers {_mm(covered)} of its {_mm(total)} shaft and "
                      f"leaves a {_mm(stub)} stub past the plate edge")
        out.append(Diagnostic(
            code="LABEL_COVERS_SHAFT",
            severity="warning",
            message=f"{_between(ctx, owner)}: its own label plate {detail}",
            targets=(owner,),
            where=plate,
            hint=("move the label off the corner: label_side=\"start\" or "
                  "\"end\" puts it on a straight run instead of the elbow, and "
                  "a larger label_offset= lifts the plate clear of the line "
                  "altogether"),
        ))
    return out


def _visible_runs(ctx: LintContext, shafts: Sequence[Item],
                  plate: Rect) -> tuple[float, float, list[float]] | None:
    """(shaft length, length under the plate, the visible runs in order).

    The shaft is walked as one arclength axis so that a plate covering a corner
    is a single interval rather than one per segment, which is the whole point:
    the artefact is what is left on either side of it.
    """
    covered: list[tuple[float, float]] = []
    total = 0.0
    for item in sorted(shafts, key=lambda i: i.id):
        for a, b in _shaft_segments(ctx, item):
            length = (b - a).length
            inside = _inside_run(plate, a, b)
            if inside is not None:
                lo, hi = inside
                covered.append((total + lo * length, total + hi * length))
            total += length
    if total <= 0.0:
        return None
    covered.sort()
    merged: list[tuple[float, float]] = []
    for lo, hi in covered:
        if merged and lo <= merged[-1][1] + _EPS:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    runs: list[float] = []
    cursor = 0.0
    for lo, hi in merged:
        runs.append(lo - cursor)
        cursor = hi
    runs.append(total - cursor)
    hidden = sum(hi - lo for lo, hi in merged)
    return total, hidden, runs


def _inside_run(rect: Rect, a: Vec2, b: Vec2) -> tuple[float, float] | None:
    """The parameter interval of a->b inside an axis-aligned box, Liang-Barsky.

    `links.link._run_inside` answers the same question in millimetres; the
    interval is what is wanted here, because the runs *outside* it are the
    finding.
    """
    dx, dy = b.x - a.x, b.y - a.y
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a.x - rect.x0), (dx, rect.x1 - a.x),
                 (-dy, a.y - rect.y0), (dy, rect.y1 - a.y)):
        if abs(p) < _EPS:
            if q < 0.0:
                return None
            continue
        t = q / p
        if p < 0.0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return (t0, t1) if t1 - t0 > _EPS else None
