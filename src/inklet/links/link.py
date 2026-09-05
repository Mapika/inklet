"""Connectors: the arrows between things.

A link is a *spec*, not geometry. Where an arrow starts depends on where its
endpoints ended up, so the spec is recorded first and resolved after layout:
`route(link, placements)` returns a Diagram in world coordinates, ready to be
overlaid on the figure.

The rule that makes diagrams look drawn rather than generated: an arrow must
touch the shape it points at and stop there. Every endpoint is found by firing a
ray from a shape's centre and asking its `Trace` where that ray leaves -- so a
rounded rectangle clips on the round, an ellipse on the curve, and an image
clips on its cutout rather than on the picture frame. Nothing here measures
text, sets a colour or picks a stroke width; the theme owns all of that.
"""

from __future__ import annotations

import heapq
import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, fields
from typing import Iterable, Iterator, Mapping, Sequence

from . import curves as bezier
from ..core import (
    EAST, EMPTY_STYLE, AnchorRef, Diagram, DiagramError, PathPrim, PhantomPrim,
    Placement, Rect, Style, Subpath, Trace, Vec2,
)

__all__ = [
    "Link", "LinkError", "Obstacle", "link", "route", "route_all",
    "link_flags", "link_name", "is_degenerate",
    "LINK_KIND", "CONNECTOR_KIND", "HEAD_KIND", "LABEL_KIND", "FLAG_SEP",
    "KINDS", "ROUTES", "HEADS", "LABEL_SIDES", "LOOP_SIDES",
    "DEFAULT_ARROW_SIZE", "DEFAULT_SHOULDER", "CLEARANCE", "DEFAULT_LOOP",
    "FLAG_COINCIDENT", "FLAG_ZERO_LENGTH", "FLAG_OVERLAP", "FLAG_SHORT",
    "FLAG_SOURCE_NO_TRACE", "FLAG_TARGET_NO_TRACE",
    "FLAG_SOURCE_MISSED", "FLAG_TARGET_MISSED",
    "FLAG_SOURCE_NO_EXTENT", "FLAG_TARGET_NO_EXTENT",
    "FLAG_NO_CLEAR_ROUTE", "link_ends",
]

EPS = 1e-9
_ALIGN_TOL = 1e-6      # mm: closer than this and the author meant "aligned"
_MIN_GAP = 0.5         # mm of clear space needed before a Z elbow is worth it
_KAPPA = 0.5522847498307936   # circle-to-cubic constant, exact for 90 degrees

DEFAULT_ARROW_SIZE = 2.0      # mm, measured along the shaft: head length
DEFAULT_SHOULDER = 3.5        # mm, a leader's horizontal run into its label
#: How far a self-loop reaches off the shape, as a multiple of the arrowhead.
#: Tying it to the head rather than to a millimetre count is what keeps a loop
#: in proportion when a theme scales a figure up for a poster.
DEFAULT_LOOP = 2.5
_HEAD_HALF_WIDTH = 0.35       # fraction of head length, so the head is 0.7 wide
#: How far in from a shape's corner an arrowhead must land, as a multiple of
#: the head's length. One head length clears the corner radius of every theme
#: here -- all three round a box by less than they draw an arrow -- and a head
#: that far along a face has its whole base on the straight.
_CORNER_GUARD = 1.0
#: How close to its own bounding box a landing point has to be to count as
#: being *on* that edge. A hair, not a tolerance: the point either came off a
#: rectangle's side or it came off a curve that only touches it.
_EDGE_TOL = 1e-6
_DOT_RADIUS = 0.30            # fraction of head length

KINDS = ("arrow", "line", "double", "leader")
ROUTES = ("straight", "orthogonal", "avoid")
HEADS = ("triangle", "open", "dot", "none")
LABEL_SIDES = ("center", "start", "end")
LOOP_SIDES = ("n", "e", "s", "w", "auto")

LINK_KIND = "link"            # the routed group; the linter walks for this
CONNECTOR_KIND = "connector"  # the shaft path
HEAD_KIND = "arrowhead"
LABEL_KIND = "link-label"

# Degenerate links are marked on the routed diagram's name, after this
# separator, so a linter can flag them without re-deriving the geometry.
FLAG_SEP = "!"

FLAG_COINCIDENT = "coincident-centres"
FLAG_ZERO_LENGTH = "zero-length"
FLAG_OVERLAP = "overlapping-shapes"
FLAG_SHORT = "shorter-than-head"
FLAG_SOURCE_NO_TRACE = "source-has-no-trace"
FLAG_TARGET_NO_TRACE = "target-has-no-trace"
FLAG_SOURCE_MISSED = "source-clip-missed"
FLAG_TARGET_MISSED = "target-clip-missed"
FLAG_SOURCE_NO_EXTENT = "source-has-no-extent"
FLAG_TARGET_NO_EXTENT = "target-has-no-extent"
FLAG_NO_CLEAR_ROUTE = "no-clear-route"

_NO_TRACE = {"source": FLAG_SOURCE_NO_TRACE, "target": FLAG_TARGET_NO_TRACE}
_MISSED = {"source": FLAG_SOURCE_MISSED, "target": FLAG_TARGET_MISSED}
_NO_EXTENT = {"source": FLAG_SOURCE_NO_EXTENT, "target": FLAG_TARGET_NO_EXTENT}


class LinkError(ValueError):
    pass


# -- the spec -------------------------------------------------------------


@dataclass(frozen=True)
class Link:
    """An arrow that has not been drawn yet.

    `source` and `target` are either a Diagram -- clipped to its boundary -- or
    an AnchorRef, which is used verbatim because the author named that exact
    spot. Either one may also be a **list**, which is a shared trunk: one stem
    leaves the single end and forks to every shape on the other side. See
    `link()`.

    A `label=` is an already-built Diagram, positioned by two fields that are
    easy to confuse:

    * `label_side` says **where along the line** it sits: `"center"` (the
      default, the midpoint), `"start"` (near the source) or `"end"` (near the
      target). It does *not* choose a side of the line -- the placer picks
      that, trying the requested spot first and flipping across the shaft only
      when something is in the way.
    * `label_offset` is the clearance in millimetres between the shaft and the
      label's box, measured across the line. Raise it when a label sits on a
      hairline it should be clear of; it is also the fix `inklet.lint` suggests
      for a label crowding a corner.
    """

    source: Diagram | AnchorRef | Sequence[Diagram | AnchorRef]
    target: Diagram | AnchorRef | Sequence[Diagram | AnchorRef]
    # Shapes this connector goes *through* on purpose, neither clipped to nor
    # stopped by. A long-pass dichroic transmits 920nm, so drawing the
    # excitation beam stopping at it would be a lie about the instrument --
    # but a line drawn through a box it has nothing to do with is the most
    # visible way a figure looks broken, and `inklet.lint` cannot tell the two
    # apart by looking. This is how the author says which one it is.
    through: Sequence[Diagram | AnchorRef] = ()
    kind: str = "arrow"           # arrow | line | double | leader
    route: str = "straight"       # straight | orthogonal | avoid
    label: Diagram | None = None  # already built; this module never shapes text
    label_side: str = "center"    # along the line: center | start | end
    label_offset: float = 1.0     # mm of clearance across the line, shaft to box
    standoff: float = 0.0         # mm gap between shape boundary and arrow tip
    arrow_size: float | None = None   # mm head length; None -> DEFAULT_ARROW_SIZE
    style: Style = EMPTY_STYLE
    name: str | None = None
    # Beyond the minimum spec, all defaulting to the M1 look:
    head: str | None = None       # triangle | open | dot | none; None = by kind
    corner: float = 0.0           # mm elbow rounding; 0 keeps corners square
    shoulder: float | None = None # mm leader shoulder; None -> DEFAULT_SHOULDER
    # Ordered via-points the route must pass through, in figure coordinates:
    # Vec2, (x, y), an AnchorRef for "wherever that spot ends up", or
    # (AnchorRef, dx, dy) for a fixed clearance off one.
    waypoints: Sequence[
        Vec2 | tuple[float, float] | AnchorRef
        | tuple[AnchorRef, float, float]] = ()
    # Millimetres along the shape's own edge, across the direction the
    # connector leaves (or arrives) on: this is what spreads three arrows out
    # of one box into three ports instead of three lines out of one point.
    port: float = 0.0
    target_port: float = 0.0
    # Millimetres this route bows off the straight line between its ends,
    # measured at the midpoint, positive to the right of travel. What draws two
    # arrows between the same pair of shapes as two visible curves.
    offset: float = 0.0
    loop: str | None = None       # n | e | s | w | auto: a self-loop's side
    loop_size: float | None = None  # mm the loop reaches off the shape
    stem: float | None = None     # mm from a trunk's source to where it forks

    def __post_init__(self) -> None:
        _check(self.kind, KINDS, "kind")
        _check(self.route, ROUTES, "route")
        _check(self.label_side, LABEL_SIDES, "label_side")
        if self.head is not None:
            _check(self.head, HEADS, "head")
        if self.loop is not None:
            _check(self.loop, LOOP_SIDES, "loop")
        for field_name in ("through", "waypoints", "source", "target"):
            value = getattr(self, field_name)
            if isinstance(value, list):
                object.__setattr__(self, field_name, tuple(value))
        if not isinstance(self.through, tuple):
            object.__setattr__(self, "through", tuple(self.through))
        if _many(self.source) and _many(self.target):
            raise LinkError(
                "a trunk forks on one side only: pass a list of shapes as the "
                "source or as the target, not as both")
        for side in ("source", "target"):
            if _many(getattr(self, side)) and not getattr(self, side):
                raise LinkError(f"{side} is an empty list; a trunk needs "
                                "something to fork to")


def _check(value: str, allowed: tuple[str, ...], field: str) -> None:
    if value not in allowed:
        raise LinkError(f"unknown {field} {value!r}; expected one of {', '.join(allowed)}")


def _many(side) -> bool:
    """True when this end of a link is a list of shapes, i.e. a trunk.

    A Diagram is not a Sequence and an AnchorRef is not either, so the test is
    the honest one: only something the author wrote as a list or a tuple forks.
    """
    return isinstance(side, (list, tuple))


def _sides(side) -> tuple:
    """One end of a link as a tuple of endpoint specs, forked or not."""
    return tuple(side) if _many(side) else (side,)


#: Everything `Link` names itself. Anything else a caller passes is style.
_LINK_FIELDS = frozenset(f.name for f in fields(Link)) - {"source", "target"}


def link(source, target, **kwargs) -> Link:
    """Declare a connector. Nothing is measured until `route()`.

    Loose style keywords are collected into `style`, the way `inklet.box` and
    `inklet.polyline` take them -- `link(a, b, stroke_dash=(1.1, 0.7))` rather than
    `link(a, b, style=Style(stroke_dash=(1.1, 0.7)))`. An explicit `style=`
    still wins over a loose keyword of the same name, so passing both is not
    ambiguous, merely redundant.

    Everything in `Link` may be passed here, including `label=` with its
    `label_side=` -- "center", "start" or "end", meaning *where along the
    line* -- and `label_offset=`, the millimetres of clearance across the line
    between the shaft and the label's box.

    Four shapes beyond one line from A to B, each with its own keyword:

    * `waypoints=[...]` -- via-points the route must pass through, in figure
      coordinates, as `AnchorRef`s, or as `(anchor, dx, dy)` for a fixed
      clearance off one. A straight route becomes a polyline
      through them, an orthogonal one takes Manhattan legs between them, and
      `route="avoid"` searches each leg in turn, so the corridor a layout
      already worked out can be handed over instead of rediscovered.
    * `link(a, [b, c, d])` -- a shared trunk: one stem leaves `a` and forks to
      each target, with `stem=` millimetres saying where the fork happens.
      `link([a, b], c)` is the same thing merging instead of branching.
    * `link(a, a, loop="n")` -- a self-loop, an arc off one side of a shape and
      back into it. `loop="auto"` picks the least crowded side.
    * `offset=` -- millimetres the route bows off the straight line, so two
      arrows between the same pair of shapes are two curves rather than one
      line wearing two heads. Give both the same offset and they land on
      opposite sides, because each is measured from its own direction of
      travel.

    `kind="leader"` is the one kind whose ends mean different things: the dot
    lands on `source` and the horizontal shoulder runs into `target`, so an
    illustrator's callout reads `link(region, label)` -- what is being named
    first. `inklet.annotate` takes the same two in the order a caption writes
    them. See `_leader_points`.

    `port=` and `target_port=` are the fifth thing, and not a shape: they slide
    an end along the face it leaves through, which turns three arrows out of
    one box's centre into three arrows out of three points. `inklet.graph` spreads
    its own; this is for links placed by hand.
    """
    if "corner_radius" in kwargs and "corner" not in kwargs:
        # `Style.corner_radius` exists and rounds a *rectangle*; on a shaft it
        # would be accepted as a loose style keyword and silently do nothing.
        kwargs["corner"] = kwargs.pop("corner_radius")
    loose = {key: kwargs.pop(key) for key in tuple(kwargs)
             if key not in _LINK_FIELDS}
    if not loose:
        return Link(source=source, target=target, **kwargs)
    try:
        extra = Style(**loose)
    except TypeError:
        unknown = ", ".join(sorted(loose))
        raise LinkError(
            f"unknown keyword(s) for a link: {unknown}; expected a link field "
            f"({', '.join(sorted(_LINK_FIELDS))}) or a style property"
        ) from None
    kwargs["style"] = kwargs.get("style", EMPTY_STYLE).over(extra)
    return Link(source=source, target=target, **kwargs)


# -- resolved endpoints ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class _End:
    point: Vec2          # the centre to fire from, or an anchor's exact spot
    trace: Trace | None  # None means "do not clip": anchored, or no trace at all
    box: Rect            # world bbox, for deciding elbows
    pinned: bool         # True for an AnchorRef: no clipping, no standoff
    guard: float = 0.0   # mm to keep the landing point clear of a corner


def _end_id(spec: Diagram | AnchorRef) -> str:
    """The node an endpoint spec refers to, anchored or not."""
    return (spec.diagram if isinstance(spec, AnchorRef) else spec).id


def _resolve_end(spec: Diagram | AnchorRef, placements: Mapping[str, Placement],
                 side: str, flags: list[str], guard: float = 0.0) -> _End:
    diagram = spec.diagram if isinstance(spec, AnchorRef) else spec
    anchor = spec.name if isinstance(spec, AnchorRef) else "center"
    placement = placements.get(diagram.id)
    if placement is None:
        raise DiagramError(
            f"{diagram.id} is not part of this figure; add it before linking to it"
        )
    try:
        point = placement.point(anchor)
    except DiagramError:
        # Nothing with an extent, so it has no centre either. Its own origin is
        # the only honest answer; flag it and carry on rather than exploding.
        _flag(flags, _NO_EXTENT[side])
        point = Vec2(placement.world.e, placement.world.f)
    box = placement.bbox or Rect(point.x, point.y, point.x, point.y)
    if isinstance(spec, AnchorRef):
        return _End(point, None, box, True)
    trace = placement.trace
    if trace.is_empty:
        # A phantom or an empty text node catches no rays: fall back to the
        # centre so the arrow still lands somewhere, and say so.
        _flag(flags, _NO_TRACE[side])
        return _End(point, None, box, False)
    return _End(point, trace, box, False, guard)


def _clip(end: _End, ray: Vec2, standoff: float, side: str, flags: list[str]) -> Vec2:
    """Where the connector meets this endpoint, firing outward along `ray`."""
    if end.trace is None:
        return end.point                       # anchored, or nothing to clip on
    hit = end.trace.boundary_point(end.point, ray)
    if hit is None:
        _flag(flags, _MISSED[side])            # concave outline, centre in a hole
        return end.point
    hit = _off_corner(end, hit, ray)
    return hit + ray * standoff                # standoff pulls back off the shape


def _off_corner(end: _End, hit: Vec2, ray: Vec2) -> Vec2:
    """The same landing, moved out of the shape's corner if it is in one.

    A theme draws a box with rounded corners, and the outline a ray is clipped
    against follows them, so the tip of a diagonal arrow lands on the arc --
    correctly, and still wrongly: the head is a triangle nearly as wide as it
    is long, and a head whose tip is on the curve has half its base out in the
    air beside the corner. It reads as an arrow that missed. Moved a head's
    length along the face it arrived through, the whole head sits on a
    straight run, which is where a person would have drawn it.

    The move is a probe rather than a nudge: fire a fresh ray at the face from
    outside and take what comes back, so the landing is on the real outline
    and not on the bounding rectangle used to find it. A shape with no
    straight face there -- a circle, a diamond -- answers that probe with a
    point somewhere else entirely, and is left exactly where it landed.
    """
    if end.guard <= 0.0 or end.trace is None:
        return hit
    box, guard = end.box, end.guard
    if box.width <= EPS or box.height <= EPS:
        return hit
    left, right = hit.x - box.x0, box.x1 - hit.x
    top, bottom = hit.y - box.y0, box.y1 - hit.y
    upright = min(abs(left), abs(right)) <= _EDGE_TOL      # on a left/right face
    flat = min(abs(top), abs(bottom)) <= _EDGE_TOL         # on a top/bottom face
    if not (upright or flat):
        # On the arc between two faces, or on a curve that has no faces. Only
        # the first is a corner, and the probe below is what tells them apart.
        if min(left, right) > guard or min(top, bottom) > guard:
            return hit
        upright, flat = abs(ray.x) > abs(ray.y), abs(ray.x) <= abs(ray.y)
    elif upright and flat:
        # Dead on a sharp corner, on both faces at once: the one it arrived
        # most squarely through is the one to land on.
        upright, flat = abs(ray.x) > abs(ray.y), abs(ray.x) <= abs(ray.y)
    if upright:
        reach = min(guard, box.height / 2.0)
        x = box.x0 if left < right else box.x1
        y = min(max(hit.y, box.y0 + reach), box.y1 - reach)
        out = Vec2(1.0, 0.0) if left < right else Vec2(-1.0, 0.0)
    else:
        reach = min(guard, box.width / 2.0)
        x = min(max(hit.x, box.x0 + reach), box.x1 - reach)
        y = box.y0 if top < bottom else box.y1
        out = Vec2(0.0, 1.0) if top < bottom else Vec2(0.0, -1.0)
    want = Vec2(x, y)
    if (want - hit).length <= _EDGE_TOL:
        return hit
    # From a hand outside the face, firing back at it: the first thing the ray
    # meets is the face itself, if the shape has one there.
    away = guard + box.width + box.height
    probe = end.trace.boundary_point(want - out * away, out, from_inside=False)
    if probe is None or (probe - want).length > _EDGE_TOL:
        return hit
    return probe


# -- routing --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Obstacle:
    """A world box, and the id of the node that put it there.

    A bare `Rect` says where something is but not what it is, and a router has
    to know: the one thing a link must be free to touch is the pair of shapes
    it was drawn to join. Anything reaching `route()` as a plain Rect keeps an
    empty id, which no node answers to, so it obstructs everything -- the
    conservative reading, and the one that keeps older callers working.
    """

    id: str
    rect: Rect


def route(link: Link, placements: Mapping[str, Placement],
          obstacles: Sequence[Rect | Obstacle] = (),
          drawn: Sequence[tuple[Vec2, Vec2]] = ()) -> Diagram:
    """Turn a spec into geometry: shaft, heads and label, in world coordinates.

    The result is a group with `kind == LINK_KIND`, an identity transform,
    `start`/`end` anchors on the two tips, and `attached_to` naming the two
    endpoint nodes.

    `obstacles` are the boxes to keep a label -- and, under `route="avoid"`,
    the shaft itself -- away from. `route_all` collects them from the layout;
    a caller routing one link may pass its own, as `Obstacle`s or as bare
    `Rect`s. `drawn` is the ink already on the page: line segments a detour
    would rather not cross and must not be drawn on top of. Neither is
    required. Obstacles change nothing for a straight route, and for an
    elbowed one only where it turns at a `waypoints=` via: there they decide
    which of the leg's two corners it turns on.
    """
    marked = _as_obstacles(obstacles)
    plan, flags = _route_points(link, placements, marked, drawn)
    return _assemble(link, plan, flags, marked, drawn)


@dataclass(frozen=True, slots=True)
class _Strand:
    """One stroke of a connector, and which of its ends wear a head.

    A plain arrow is one strand. A shared trunk is a stem, a bus and one drop
    per target -- separate strokes on purpose, because two branches drawn as
    two whole polylines would lie on top of each other along the shared part,
    which is the very defect a trunk exists to remove.

    `curves` is the exact form for a strand that is not a polyline (a bow, a
    self-loop); `points` is always the flattened version core measures with.
    """

    points: tuple[Vec2, ...]
    curves: tuple = ()
    start_head: str | None = None
    end_head: str | None = None


@dataclass(frozen=True, slots=True)
class _Plan:
    """Everything a route decided: what to stroke, and the line a label rides.

    `spine` is one polyline through the connector even when the strands are
    several -- the stem and the first branch of a trunk, the loop itself for a
    self-loop -- because a label sits *somewhere along the link*, and "along"
    needs a single arclength to be measured on.
    """

    strands: tuple[_Strand, ...]
    spine: tuple[Vec2, ...]


def _route_points(link: Link, placements: Mapping[str, Placement],
                  marked: Sequence[Obstacle],
                  drawn: Sequence[tuple[Vec2, Vec2]]) -> tuple[_Plan, list[str]]:
    """What a link draws, once the layout is known, and what went wrong."""
    flags: list[str] = []
    if _many(link.source) or _many(link.target):
        return _trunk_plan(link, placements, flags), flags

    src_head, dst_head = _head_kinds(link)
    guard = _CORNER_GUARD * (DEFAULT_ARROW_SIZE if link.arrow_size is None
                             else link.arrow_size)
    src = _resolve_end(link.source, placements, "source", flags,
                       guard if src_head else 0.0)
    dst = _resolve_end(link.target, placements, "target", flags,
                       guard if dst_head else 0.0)

    if link.kind == "leader":
        points = _leader_points(link, src, dst, flags)
    elif _is_loop(link):
        return _loop_plan(link, src, marked, drawn, flags), flags
    else:
        vias = _vias(link, placements, flags)
        src, dst = _ported(link, src, dst)
        if abs(link.offset) > EPS:
            return _bow_plan(link, src, dst, src_head, dst_head, flags), flags
        if vias:
            points = _via_points(link, src, dst, vias, marked, drawn, flags)
        elif link.route == "avoid":
            points = _avoid_points(link, src, dst, marked, drawn, flags)
        elif link.route == "orthogonal":
            points = _orthogonal_points(src, dst, link.standoff, flags)
        else:
            points = _straight_points(src, dst, link.standoff, flags)
    strand = _Strand(tuple(points), (), src_head, dst_head)
    return _Plan((strand,), tuple(points)), flags


def _assemble(link: Link, plan: _Plan, flags: list[str],
              marked: Sequence[Obstacle],
              drawn: Sequence[tuple[Vec2, Vec2]]) -> Diagram:
    """Shaft, heads and label for a route already decided.

    `drawn` is what the label must stay off: a label plate covers the ink
    beneath it, but a connector drawn *later* goes straight over the plate,
    so every other shaft on the page counts against a candidate spot.
    """
    flags = list(flags)
    size = DEFAULT_ARROW_SIZE if link.arrow_size is None else link.arrow_size
    heads: list[Diagram] = []
    subpaths = tuple(_stroke(link, strand, size, heads, flags)
                     for strand in plan.strands)

    children: list[Diagram] = [
        Diagram(prim=PathPrim(subpaths, filled=False), kind=CONNECTOR_KIND)]
    children.extend(heads)
    if link.label is not None:
        own = tuple((a, b) for strand in plan.strands
                    for a, b in zip(strand.points, strand.points[1:]))
        placed = _place_label(link.label, list(plan.spine), link.label_side,
                              link.label_offset, marked, drawn, own=own)
        if placed is not None:
            children.append(placed)

    out = Diagram(
        children=tuple(children),
        style=link.style,                      # the theme fills in the rest
        kind=LINK_KIND,
        name=_mark(link.name, flags),
        # The shapes this was built to touch. Touching them is the whole point
        # of an arrow, so the linter needs them to tell a head resting on its
        # target apart from one straying across a box it has nothing to do
        # with. **The first two are the endpoints**, in that order -- for a
        # trunk, the first shape of each side, the rest of the fork following
        # them; anything after that is a `through=` shape the author declared
        # this connector passes over. `link_ends` says so out loud.
        attached_to=_attachments(link),
    )
    out.anchor("start", plan.spine[0])
    out.anchor("end", plan.spine[-1])
    return out


def _attachments(link: Link) -> tuple[str, ...]:
    sources = tuple(_end_id(spec) for spec in _sides(link.source))
    targets = tuple(_end_id(spec) for spec in _sides(link.target))
    return ((sources[0], targets[0]) + sources[1:] + targets[1:]
            + tuple(_end_id(spec) for spec in link.through))


def _stroke(link: Link, strand: _Strand, size: float, heads: list[Diagram],
            flags: list[str]) -> Subpath:
    """One strand as a subpath, with its heads pushed onto `heads`.

    The head comes first because it decides how far the shaft has to stop
    short: a filled triangle drawn over the last two millimetres of its own
    line is a bulge, not an arrow.
    """
    points = list(strand.points)
    start_head, end_head = strand.start_head, strand.end_head
    if _path_length(points) <= EPS:
        _flag(flags, FLAG_ZERO_LENGTH)
        start_head = end_head = None           # a head on a point is a blob

    start_inset = end_inset = 0.0
    if start_head is not None:
        direction = -_unit(points[1] - points[0], EAST)
        prim, start_inset = _head_prim(start_head, points[0], direction, size)
        heads.append(Diagram(prim=prim, kind=HEAD_KIND))
    if end_head is not None:
        direction = _unit(points[-1] - points[-2], EAST)
        prim, end_inset = _head_prim(end_head, points[-1], direction, size)
        heads.append(Diagram(prim=prim, kind=HEAD_KIND))

    if strand.curves:
        return _curved_subpath(strand.curves, start_inset, end_inset, flags)
    shaft_points = _inset_path(points, start_inset, end_inset, flags)
    shaft_points, curves = _round_corners(shaft_points, link.corner)
    return Subpath(shaft_points, closed=False, curves=curves)


def _curved_subpath(curves: tuple, start_inset: float, end_inset: float,
                    flags: list[str]) -> Subpath:
    """A curved strand, cut back from each tip by its head's length."""
    cut = bezier.trim_end(bezier.trim_start(tuple(curves), start_inset), end_inset)
    if not cut:
        # Shorter than its own heads. Keep half of it rather than nothing, the
        # same bargain `_trim_front` strikes for a polyline.
        _flag(flags, FLAG_SHORT)
        cut = (bezier.split(curves[0], 0.5)[0],)
    return Subpath(bezier.flatten(cut), closed=False, curves=cut)


def route_all(links: Iterable[Link], placements: Mapping[str, Placement],
              obstacles: Sequence[Rect | Obstacle] | None = None) -> Diagram:
    """Route every link into one overlay group, in the order given.

    Each shaft joins the ink the next link is routed against, so a detour
    steps around the connectors already on the page instead of being drawn
    along them. Order therefore matters -- the first link declared gets the
    inside lane -- which is the only sense in which routing one link is not
    independent of the rest, and it is the sense a reader wants: the figure is
    drawn in the order it was written.
    """
    if obstacles is None:
        obstacles = _obstacles(placements)
    marked = _as_obstacles(obstacles)
    drawn: list[tuple[Vec2, Vec2]] = []
    out: list[Diagram] = []
    decided: list[tuple[Link, _Plan, list[str], slice]] = []
    for spec in links:
        plan, flags = _route_points(spec, placements, marked, drawn)
        routed = _assemble(spec, plan, flags, marked, drawn)
        start = len(drawn)
        drawn.extend(_shaft_segments(routed))
        decided.append((spec, plan, flags, slice(start, len(drawn))))
        out.append(routed)

    # A loop picks its side against the ink it can see, and in declaration
    # order that is whatever was written before it -- which on a state machine
    # is usually one arrow in and nothing else, so the arc goes east and the
    # transition drawn three lines later goes straight through it. Decide it
    # again now, against every shaft. Same reasoning as the label pass below,
    # and the same price: a re-decided loop costs one more route, and a figure
    # where the first answer was already right is untouched.
    #
    # A label is ink too, and a plate is opaque, so the side an arc picks has
    # to see the plates as well as the shafts -- otherwise it dodges a shaft
    # only to have someone else's label land on it, which is what happened to
    # `examples/state_machine.py`'s `retry`. The plates are the ones the first
    # routing pass placed: a reservation list, not a prediction, which is why
    # this is one extra pass rather than a fixed point between two placers.
    plates = [_label_rect(node) for node in out]
    for index, (spec, plan, flags, own) in enumerate(decided):
        if not _is_loop(spec) or spec.loop not in (None, "auto"):
            continue
        others = drawn[:own.start] + drawn[own.stop:]
        reserved = marked + tuple(
            Obstacle("", rect) for other, rect in enumerate(plates)
            if other != index and rect is not None)
        again, again_flags = _route_points(spec, placements, reserved, others)
        if again.spine == plan.spine:
            continue
        out[index] = _assemble(spec, again, again_flags, marked, others)
        decided[index] = (spec, again, again_flags, own)
        fresh = list(_shaft_segments(out[index]))
        if len(fresh) == own.stop - own.start:
            # Same shape, different side: the slices the label pass reads are
            # still true. A loop that somehow changed length is left alone
            # rather than shifting every slice after it.
            drawn[own] = fresh

    # A label is placed knowing only the links declared before it, because
    # that is all there is to know at the time. When one routed later ends up
    # drawn across it, place it again -- against every shaft this time. Only
    # then: a figure with no such collision comes out exactly as it did
    # before, and a re-placed label costs one label placement, not a reroute.
    for index, (spec, plan, flags, own) in enumerate(decided):
        plate = None if spec.label is None else _label_rect(out[index])
        if plate is None:
            continue
        others = drawn[:own.start] + drawn[own.stop:]
        if not any(_run_inside(plate, a, b) > 0.0 for a, b in others):
            continue
        out[index] = _assemble(spec, plan, flags, marked, others)
    return Diagram(children=tuple(out), kind="links")


def _label_rect(routed: Diagram) -> Rect | None:
    """Where a routed link's label sits, plate included, in world coordinates."""
    for child in routed.children:
        if child.kind == LABEL_KIND:
            try:
                return child.bbox
            except DiagramError:
                return None
    return None


def _shaft_segments(routed: Diagram) -> Iterator[tuple[Vec2, Vec2]]:
    """A routed link's shaft, segment by segment, in world coordinates.

    Heads and labels are left out: a head sits on the shape it points at,
    where a route has no business being anyway, and a label is a box that
    belongs in `obstacles` rather than a line to be crossed.

    The head half of that is true of the drawings here and not true in
    general, which matters to anyone counting crossings. A link arriving
    along a box's flank stops one head-length short of it -- 2mm at the
    default -- and if a lane runs down that flank inside those 2mm, the head
    lies across it while the shaft does not, so the crossing is drawn and
    `LINK_CROSSES_LINK` does not see it. Round 6 found exactly that while
    measuring the lane-swap idea for `stress/dense_graph.py`; no shipped
    figure has one (measured: zero head-over-shaft overlaps across the
    corpus), which is why this still yields shafts alone.
    """
    for child in routed.children:
        if child.kind != CONNECTOR_KIND or not isinstance(child.prim, PathPrim):
            continue
        for sub in child.prim.subpaths:
            for a, b in zip(sub.points, sub.points[1:]):
                if (b - a).length > _GRID_TOL:
                    yield a, b


def _obstacles(placements: Mapping[str, Placement]) -> tuple[Obstacle, ...]:
    """World boxes a label should not land on, and a route should not cross.

    Only nodes that actually draw something count. A group's box spans all of
    its children, so counting groups too would mark the whole figure occupied
    and leave the label nowhere better to go. Phantoms are excluded for the
    same reason padding does not clip an arrow: they are space, not ink.

    That exclusion is also what settles a question `route="avoid"` would
    otherwise have to answer: an endpoint's *ancestors* -- the stack, grid or
    pad holding it -- never appear here, because a combinator returns a group
    with children and no prim of its own. What does appear is a `frame()`'s
    backdrop, which draws, contains its content geometrically, and is a
    *sibling* of it rather than an ancestor; the router drops that by
    containment rather than by lineage. See `_blocking_boxes`.
    """
    out: list[Obstacle] = []
    for node_id, placement in placements.items():   # insertion order, so stable
        prim = placement.diagram.prim
        if prim is None or isinstance(prim, PhantomPrim):
            continue
        box = placement.bbox
        if box is not None:
            out.append(Obstacle(node_id, box))
    return tuple(out)


def _as_obstacles(obstacles: Sequence[Rect | Obstacle]) -> tuple[Obstacle, ...]:
    """Accept either form. An unlabelled box belongs to nobody, so it blocks
    every link -- including the ones it was cut from."""
    return tuple(o if isinstance(o, Obstacle) else Obstacle("", o)
                 for o in obstacles)


def _straight_points(src: _End, dst: _End, standoff: float,
                     flags: list[str]) -> list[Vec2]:
    delta = dst.point - src.point
    if delta.length <= EPS:
        _flag(flags, FLAG_COINCIDENT)
    direction = _unit(delta, EAST)
    start = _clip(src, direction, standoff, "source", flags)
    end = _clip(dst, -direction, standoff, "target", flags)
    return _two_point(start, end, direction, flags)


def _two_point(start: Vec2, end: Vec2, direction: Vec2, flags: list[str]) -> list[Vec2]:
    if (end - start).dot(direction) < -EPS:
        # The clipped ends crossed over: the shapes overlap or one contains the
        # other. Draw a point rather than an arrow pointing the wrong way.
        _flag(flags, FLAG_OVERLAP)
        mid = (start + end) * 0.5
        return [mid, mid]
    return _dedupe([start, end])


def _elbow_plan(src: _End, dst: _End) -> tuple[Vec2, Vec2, str]:
    """Exit and entry directions for an orthogonal route, dominant axis first.

    The connector leaves along whichever axis separates the two centres most.
    If the shapes are clear of each other on that axis there is room to leave
    *and* arrive along it, jogging across in the middle -- a Z. If they overlap
    on it there is no such corridor, so the route turns once and arrives on the
    minor axis -- an L. Deciding here, before any clipping, is what keeps every
    segment exactly axis-aligned: the ends are then clipped along these
    directions, not along the centre-to-centre line.
    """
    a, b = src.point, dst.point
    dx, dy = b.x - a.x, b.y - a.y
    if abs(dx) >= abs(dy):
        out = Vec2(_sign(dx), 0.0)
        if abs(dy) <= _ALIGN_TOL:
            return out, out, "straight"
        gap = dst.box.x0 - src.box.x1 if dx >= 0 else src.box.x0 - dst.box.x1
        if gap > _MIN_GAP:
            return out, out, "z"
        return out, Vec2(0.0, _sign(dy)), "l"
    out = Vec2(0.0, _sign(dy))
    if abs(dx) <= _ALIGN_TOL:
        return out, out, "straight"
    gap = dst.box.y0 - src.box.y1 if dy >= 0 else src.box.y0 - dst.box.y1
    if gap > _MIN_GAP:
        return out, out, "z"
    return out, Vec2(_sign(dx), 0.0), "l"


def _orthogonal_points(src: _End, dst: _End, standoff: float,
                       flags: list[str]) -> list[Vec2]:
    delta = dst.point - src.point
    if delta.length <= EPS:
        _flag(flags, FLAG_COINCIDENT)
        return _straight_points(src, dst, standoff, flags)

    exit_dir, entry_dir, shape = _elbow_plan(src, dst)
    start = _clip(src, exit_dir, standoff, "source", flags)
    end = _clip(dst, -entry_dir, standoff, "target", flags)
    horizontal = exit_dir.y == 0.0

    if shape == "straight":
        # Sub-micron misalignment would leave a segment that is not quite
        # axis-aligned; snap it, since the author clearly meant a straight run.
        end = Vec2(end.x, start.y) if horizontal else Vec2(start.x, end.y)
        return _two_point(start, end, exit_dir, flags)

    if shape == "z":
        if horizontal:
            mid = (start.x + end.x) / 2
            points = [start, Vec2(mid, start.y), Vec2(mid, end.y), end]
        else:
            mid = (start.y + end.y) / 2
            points = [start, Vec2(start.x, mid), Vec2(end.x, mid), end]
    else:
        corner = Vec2(end.x, start.y) if horizontal else Vec2(start.x, end.y)
        points = [start, corner, end]

    if (points[1] - points[0]).dot(exit_dir) < -EPS:
        _flag(flags, FLAG_OVERLAP)   # the elbow doubles back; still drawable
    return _dedupe(points)


# -- obstacle-aware routing -----------------------------------------------
#
# `route="avoid"` is the elbow above with its eyes open. The search is A* over
# a Hanan-style lattice: the lines through the obstacles' inflated edges, plus
# the midline of every gap between them. That lattice is not a sampling of the
# plane, it is the whole of it -- an optimal rectilinear path can always be
# slid onto those lines without getting longer or gaining a bend -- so a
# continuous problem becomes a few thousand nodes with nothing lost.
#
# The obvious alternative, nudging a straight line off whatever it hits, was
# not attempted for one reason: it is iterative, and an iteration count that
# depends on the order shapes happen to be visited is a different figure every
# time somebody adds a box. A lattice search reads the geometry and nothing
# else, which is the only way to keep the determinism this library promises.

#: Millimetres of clear space a detour keeps from anything it is not attached
#: to. The linter calls 1.0mm the least a figure should leave between two
#: things, so a corridor tighter than that would be routed and then reported;
#: 1.5mm clears that with room for a stroke width. The ceiling is the gap a
#: stack leaves between boxes -- 4 to 7mm in practice -- because two
#: clearances have to fit inside one gap or the corridor between neighbours
#: seals shut and every route goes the long way round.
CLEARANCE = 1.5

#: What a corner costs, in millimetres of travel it is worth to avoid one.
#: Purely a matter of looks: two routes of equal length are not equally
#: readable, and the one with fewer bends is the one that reads as drawn. Six
#: millimetres is about one gap between boxes -- enough to refuse a staircase
#: through a corridor, small enough that a bend still beats a lap of the page.
_TURN_COST = 6.0

#: What crossing one line already on the page costs, in the same millimetres.
#: Small, because connectors crossing is ordinary and the linter says as much;
#: large enough that between two routes of a length a reader cannot tell
#: apart, the one through open paper wins.
_CROSS_COST = 2.0

#: What a run drawn on top of another connector costs, as a multiple of its
#: own length. Crossing a line is a moment; sharing one is two arrows a reader
#: sees as a single arrow, which is worse than any detour of comparable size.
#: Three means a shared centimetre has to save two clear centimetres to be
#: worth taking.
_SHARE_COST = 3.0

#: Toll bytes pack both: the low bits count crossings, the high bit says the
#: edge would be drawn along something. One byte per lattice edge per axis,
#: which is what keeps the grid small enough to build per link.
_SHARED = 0x40
_CROSSINGS = 0x3F

#: Two coordinates closer than this are one lattice line. Layout arithmetic
#: reaches the same edge by two routes and lands a few ulps apart; a duplicate
#: line costs a whole row of nodes and buys nothing.
_GRID_TOL = 1e-6

#: How far into an obstacle a segment must reach before it counts as going
#: through it. A route is *meant* to run along an inflated edge -- that is what
#: the clearance is for -- so contact is free and only a real incursion counts.
#: A tenth of a micron is far below anything that can be drawn or measured.
_INSIDE_TOL = 1e-4

#: Twice the area of the triangle a point makes with a segment, below which
#: the point is on the line. Two shafts meeting at a shared port, or one
#: turning off another, are not a crossing; only a segment that has room on
#: both sides of the other is. Squared units, so it is set well under the
#: smallest triangle any real pair of connectors makes.
_CUT_TOL = 1e-7

#: Lattice nodes past which the search gives up rather than grinds. Measured:
#: a figure of 45 boxes at 45 distinct coordinates fills a grid this size and
#: takes about 20ms to route one link through. Past that the figure wants a
#: layout engine rather than a router, and a link that quietly falls back to
#: an elbow is a better outcome than a build that appears to hang.
_MAX_LATTICE_NODES = 60_000

#: Obstacle count past which the contained-box prune (quadratic) is skipped.
#: A figure that dense overruns the node cap anyway, so the prune would only
#: be paying for a fallback it cannot prevent.
_PRUNE_LIMIT = 200

#: Sides are tried in this order, and the search settles ties in favour of
#: whichever it saw first, so this is the house style for a route that has a
#: genuine choice: leave upwards, else to the left. That is where a reader
#: expects a skip connection to run -- above the flow, or outside the column --
#: and both alternatives cost exactly the same when the two shapes share a row
#: or a column, which is precisely when this mode gets used.
_PORT_DIRS = (Vec2(0.0, -1.0), Vec2(-1.0, 0.0), Vec2(0.0, 1.0), Vec2(1.0, 0.0))

_FINISH = -1      # the node the search stops on; not a lattice point


def _avoid_points(link: Link, src: _End, dst: _End,
                  obstacles: Sequence[Obstacle], drawn: Sequence[tuple[Vec2, Vec2]],
                  flags: list[str]) -> list[Vec2]:
    """An elbow while the elbow is clear, a detour once it is not.

    Trying the elbow first is not an optimisation. It is what lets an author
    set `route="avoid"` on a link without having to look at what it does to a
    figure that was already fine: with nothing in the way the answer is the
    same polyline `route="orthogonal"` draws, to the last decimal.
    """
    own = _own_ids(link.source) | _own_ids(link.target)
    boxes = _blocking_boxes(obstacles, own, src, dst)
    # The elbow's own complaints are held back until we know which route is
    # actually being drawn: a discarded elbow must not leave its flags behind.
    aside: list[str] = []
    elbow = _orthogonal_points(src, dst, link.standoff, aside)
    if not boxes or not _crosses(elbow, boxes):
        clear = _uncrossed(link, src, dst, boxes, drawn, elbow, flags)
        if clear is not None:
            return clear
        return _keep(elbow, aside, flags)

    detour = _detour_points(src, dst, link.standoff, boxes, drawn, flags)
    if detour is not None:
        return detour
    # Enclosed, walled in, or too big a lattice to search. Drawing the elbow
    # anyway beats drawing nothing; the flag is how the linter says so.
    _flag(flags, FLAG_NO_CLEAR_ROUTE)
    return _keep(elbow, aside, flags)


def _keep(points: list[Vec2], aside: list[str], flags: list[str]) -> list[Vec2]:
    for name in aside:
        _flag(flags, name)
    return points


def _uncrossed(link: Link, src: _End, dst: _End, boxes: Sequence[Rect],
               drawn: Sequence[tuple[Vec2, Vec2]], elbow: Sequence[Vec2],
               flags: list[str]) -> list[Vec2] | None:
    """A same-length corridor for an elbow that clears the shapes but cuts an
    already-drawn connector, or None to keep the elbow.

    `route="avoid"` exists to get a line out of a shape's way, and that is
    still what decides whether the search runs at all. But when the elbow is
    already clear of every shape and the lattice can reach the target without
    going any further, crossing a neighbour's shaft is a defect with a free
    fix, and taking it is what an author drawing by hand would do.

    Free is meant literally: the detour is adopted only if it cuts fewer
    shafts *and* costs no more to draw, measured the way the search itself
    measures -- millimetres of travel plus `_TURN_COST` per bend, so a route
    that trades a corner for a few millimetres still counts as free and one
    that wanders does not. A figure with no better corridor is left at the
    polyline `route="orthogonal"` would have drawn, to the last decimal, so
    this cannot move a figure it does not improve.
    """
    cut = _shaft_crossings(elbow, drawn)
    if not cut:
        return None
    spare: list[str] = []
    detour = _detour_points(src, dst, link.standoff, boxes, drawn, spare)
    if detour is None or _shaft_crossings(detour, drawn) >= cut:
        return None
    if _drawing_cost(detour) > _drawing_cost(elbow) + _GRID_TOL:
        return None
    return _keep(detour, spare, flags)


def _shaft_crossings(points: Sequence[Vec2], drawn: Sequence[tuple[Vec2, Vec2]]) -> int:
    """How many already-drawn segments this polyline cuts through.

    Proper crossings only. Two connectors that meet end to end at a shared
    port, or that run along each other, are not what this counts -- a shaft
    passing *through* another is.
    """
    return sum(_cuts(a, b, c, d)
               for a, b in zip(points, points[1:]) for c, d in drawn)


def _cuts(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> bool:
    """Do a-b and c-d cross at a point strictly inside both?"""
    def side(p: Vec2, q: Vec2, r: Vec2) -> float:
        return (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)

    ab = (side(a, b, c), side(a, b, d))
    cd = (side(c, d, a), side(c, d, b))
    return all(min(pair) < -_CUT_TOL and max(pair) > _CUT_TOL
               for pair in (ab, cd))


def _drawing_cost(points: Sequence[Vec2]) -> float:
    """What a polyline costs to draw, in the search's own currency: its length
    plus `_TURN_COST` for every corner."""
    length = sum((b - a).length for a, b in zip(points, points[1:]))
    return length + _TURN_COST * _bends(points)


def _bends(points: Sequence[Vec2]) -> int:
    """Corners in a polyline: interior vertices where the direction changes."""
    return sum(1 for a, b, c in zip(points, points[1:], points[2:])
               if abs((b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x))
               > _CUT_TOL or (b - a).dot(c - b) < 0.0)


def _own_ids(spec: Diagram | AnchorRef) -> frozenset[str]:
    """Every node an endpoint covers: itself, and everything inside it.

    The endpoint node alone is not enough. `box("LGN")` is a group holding a
    rectangle and a text, and both of those draw, so both are obstacles; a
    route made to keep clear of its own label could never reach the shape the
    label sits in. Membership only -- the set is never iterated, so it cannot
    leak hash order into the geometry.
    """
    node = spec.diagram if isinstance(spec, AnchorRef) else spec
    return frozenset(child.id for child in node.walk())


def _blocking_boxes(obstacles: Sequence[Obstacle], own: frozenset[str],
                    src: _End, dst: _End) -> list[Rect]:
    """What this link must keep clear of, inflated by the clearance.

    Two exclusions, both load-bearing:

    * Anything belonging to either endpoint. A link that treated the shapes it
      joins as walls could not reach them: the search would fail on every link
      in the figure and every one of them would fall back.
    * Anything *containing* an endpoint -- a `frame()` backdrop, a panel, a
      plate. The route has to cross it to get out at all, which is the same
      exemption LINK_CROSSES makes for a container a link starts inside. The
      test is geometric rather than structural for the reason that rule gives:
      `frame()` puts the backdrop and its content side by side, so an ancestor
      test misses the commonest idiom in the library.

    A third box that merely *overlaps* an endpoint is not excluded. The route
    is allowed out of its own shape, not through its neighbour's.
    """
    kept: list[Rect] = []
    for obstacle in obstacles:                  # caller order, so deterministic
        if obstacle.id in own:
            continue
        if _covers(obstacle.rect, src.box) or _covers(obstacle.rect, dst.box):
            continue
        kept.append(obstacle.rect.pad(CLEARANCE))
    return _drop_contained(kept)


def _drop_contained(boxes: list[Rect]) -> list[Rect]:
    """Drop boxes swallowed whole by another box.

    A label inside its own box is the overwhelming case, and it contributes
    four lattice lines that buy nothing -- the box already blocks everything
    the text does. Halving the coordinates on an axis quarters the lattice,
    which on a real figure is the difference between a search and a wait.
    """
    if len(boxes) > _PRUNE_LIMIT:
        return boxes
    return [box for i, box in enumerate(boxes)
            if not any(_covers(other, box) and (_area(other) > _area(box) or j < i)
                       for j, other in enumerate(boxes) if j != i)]


def _detour_points(src: _End, dst: _End, standoff: float, boxes: Sequence[Rect],
                   drawn: Sequence[tuple[Vec2, Vec2]],
                   flags: list[str]) -> list[Vec2] | None:
    """The routed polyline, landed on both shapes, or None if there is none."""
    points = _detour_raw(src, dst, boxes, drawn)
    if points is None:
        return None
    return _clip_ends(src, dst, points, standoff, flags)


def _detour_raw(src: _End, dst: _End, boxes: Sequence[Rect],
                drawn: Sequence[tuple[Vec2, Vec2]]) -> list[Vec2] | None:
    """The search result, centre to centre and unclipped.

    Separate from `_detour_points` because a leg between two waypoints has no
    shape to clip against and is joined to its neighbours instead: the whole
    polyline is landed on the two shapes once, at the end, however many
    searches it took to build.
    """
    starts = _ports(src, boxes)
    goals = _ports(dst, boxes)
    if not starts or not goals:
        return None                     # walled in: no way out of a shape

    ends = [src.point, dst.point] + [port for port, _ in starts + goals]
    xs = _lattice([p.x for p in ends],
                  [v for b in boxes for v in (b.x0, b.x1)]
                  + _sidelines(drawn, vertical=True))
    ys = _lattice([p.y for p in ends],
                  [v for b in boxes for v in (b.y0, b.y1)]
                  + _sidelines(drawn, vertical=False))
    if len(xs) * len(ys) > _MAX_LATTICE_NODES:
        return None

    from_src = _terminals(xs, ys, starts, src.point)
    to_dst = _terminals(xs, ys, goals, dst.point)
    if not from_src or not to_dst:
        return None                     # a port that lost its line: no search

    grid = _Lattice(
        xs=xs, ys=ys,
        down=_blocked(xs, ys, [(b.x0, b.x1, b.y0, b.y1) for b in boxes]),
        across=_blocked(ys, xs, [(b.y0, b.y1, b.x0, b.x1) for b in boxes]),
        down_toll=_tolls(xs, ys, [(a.x, a.y, b.x, b.y) for a, b in drawn]),
        across_toll=_tolls(ys, xs, [(a.y, a.x, b.y, b.x) for a, b in drawn]),
    )
    path = _search(grid, from_src, to_dst)
    if not path:
        return None

    return _collapse([src.point] + [Vec2(xs[i], ys[j]) for i, j in path]
                     + [dst.point])


@dataclass(frozen=True, slots=True)
class _Lattice:
    """The search space: candidate coordinates, and what each edge between
    them runs into.

    `down` and `across` say which edges are inside a shape and cannot be used
    at all; `down_toll` and `across_toll` say what the rest cost beyond their
    length. Rows are indexed by line and then by the gap between two
    consecutive coordinates, so `down[i][j]` is the vertical edge on `xs[i]`
    between `ys[j]` and `ys[j+1]`, and `across[j][i]` is its counterpart.
    """

    xs: list[float]
    ys: list[float]
    down: list[bytearray]
    across: list[bytearray]
    down_toll: list[bytearray]
    across_toll: list[bytearray]


def _ports(end: _End, boxes: Sequence[Rect]) -> list[tuple[Vec2, Vec2]]:
    """Where a detour may leave an endpoint, or join it: one point per side,
    a clearance clear of the shape's own box, with the way out to reach it.

    A side whose stub already crosses something is dropped here rather than
    left for the search to discover, so a shape wedged against a neighbour
    simply has fewer ways out instead of a lattice full of dead ends.
    """
    out: list[tuple[Vec2, Vec2]] = []
    for direction in _PORT_DIRS:
        port = _port_point(end, direction)
        if not any(_hits(end.point, port, box) for box in boxes):
            out.append((port, direction))
    return out


def _port_point(end: _End, direction: Vec2) -> Vec2:
    """One clearance beyond the endpoint's own box, on the named side."""
    box = end.box
    if direction.x > 0.0:
        reach = box.x1 + CLEARANCE - end.point.x
    elif direction.x < 0.0:
        reach = end.point.x - (box.x0 - CLEARANCE)
    elif direction.y > 0.0:
        reach = box.y1 + CLEARANCE - end.point.y
    else:
        reach = end.point.y - (box.y0 - CLEARANCE)
    # An anchored endpoint can sit on -- or outside -- its own box, where that
    # reach is short or negative. One clearance is the floor either way, which
    # is what guarantees the first bend happens outside the shape it came from
    # and so that the clip below can never overshoot it.
    return end.point + direction * max(reach, CLEARANCE)


def _sidelines(drawn: Sequence[tuple[Vec2, Vec2]], vertical: bool) -> list[float]:
    """A lane either side of every straight run already on the page.

    A connector is a line, not a box, so the Hanan construction gives it no
    edges of its own -- and without a coordinate to move to, a second link
    forced down the same corridor can only be drawn on top of the first. One
    clearance out on each side is the next place a person would put it, and it
    is exactly far enough that the toll for sharing no longer applies.

    Diagonals are skipped: an orthogonal route cannot run alongside one, so
    the lines would cost a lattice row apiece and buy nothing.
    """
    out: list[float] = []
    for a, b in drawn:
        along = abs(a.x - b.x) if vertical else abs(a.y - b.y)
        across = a.x if vertical else a.y
        if along > _GRID_TOL or (b - a).length <= _GRID_TOL:
            continue
        out.extend((across - CLEARANCE, across + CLEARANCE))
    return out


def _lattice(required: Sequence[float], optional: Sequence[float]) -> list[float]:
    """Candidate coordinates on one axis: everything that matters, plus the
    midline of every gap.

    The midlines are not decoration. Without them the only way past two boxes
    is along one of their inflated edges, so a route with a clean corridor to
    take is pressed against a wall instead. With them the lattice offers the
    middle of every gap in the figure, which is where a person would draw it.
    """
    kept: list[float] = []
    for value in sorted(list(required) + list(optional)):
        if kept and value - kept[-1] <= _GRID_TOL:
            continue                    # the same line, reached by other means
        kept.append(value)
    out: list[float] = []
    for low, high in zip(kept, kept[1:]):
        out.append(low)
        middle = (low + high) / 2.0
        if middle - low > _GRID_TOL and high - middle > _GRID_TOL:
            out.append(middle)
    out.append(kept[-1])
    return out


def _blocked(lines: Sequence[float], steps: Sequence[float],
             spans: Sequence[tuple[float, float, float, float]]) -> list[bytearray]:
    """Which lattice edges run through an obstacle.

    One row per line; entry `k` is the edge between `steps[k]` and
    `steps[k+1]`. Each box marks an interval of rows and an interval of edges,
    so the cost is the area a box actually covers rather than the whole
    lattice once per box.

    "Through" means the interior: a segment lying exactly on an inflated edge
    is free, which is the entire point of inflating. The clearance is the
    margin, and a route is meant to be able to use it.
    """
    rows = [bytearray(max(len(steps) - 1, 0)) for _ in lines]
    for across_lo, across_hi, along_lo, along_hi in spans:
        first = bisect_right(lines, across_lo + _INSIDE_TOL)
        last = bisect_left(lines, across_hi - _INSIDE_TOL)
        if first >= last:
            continue                    # every line misses this box's interior
        lo = max(bisect_right(steps, along_lo + _INSIDE_TOL) - 1, 0)
        hi = min(bisect_left(steps, along_hi - _INSIDE_TOL), len(steps) - 1)
        if lo >= hi:
            continue
        fill = b"\x01" * (hi - lo)
        for row in rows[first:last]:
            row[lo:hi] = fill
    return rows


def _tolls(lines: Sequence[float], steps: Sequence[float],
           runs: Sequence[tuple[float, float, float, float]]) -> list[bytearray]:
    """What each lattice edge costs beyond its length, given the ink already
    drawn. Same shape as `_blocked`, same line-then-gap indexing.

    A drawn segment does one of two things to an edge parallel to these lines.
    If it cuts across them it is a crossing, charged once, wherever it happens
    to pass; the point it crosses each line fixes exactly which edge pays.
    If it runs along them it is the other thing entirely -- a second connector
    drawn on the same line as the first -- so every edge within a clearance of
    it is marked instead, and the search pays by the millimetre rather than by
    the encounter.
    """
    rows = [bytearray(max(len(steps) - 1, 0)) for _ in lines]
    last_gap = len(steps) - 2
    if last_gap < 0:
        return rows
    for a_across, a_along, b_across, b_along in runs:
        if abs(b_across - a_across) > _GRID_TOL:
            span = b_across - a_across
            low, high = sorted((a_across, b_across))
            for i in range(bisect_left(lines, low), bisect_right(lines, high)):
                at = a_along + (lines[i] - a_across) / span * (b_along - a_along)
                j = min(max(bisect_right(steps, at) - 1, 0), last_gap)
                if rows[i][j] & _CROSSINGS != _CROSSINGS:
                    rows[i][j] += 1
            continue
        first = bisect_right(lines, a_across - CLEARANCE + _INSIDE_TOL)
        stop = bisect_left(lines, a_across + CLEARANCE - _INSIDE_TOL)
        low, high = sorted((a_along, b_along))
        lo = max(bisect_right(steps, low + _INSIDE_TOL) - 1, 0)
        hi = min(bisect_left(steps, high - _INSIDE_TOL), len(steps) - 1)
        for i in range(first, stop):
            for j in range(lo, hi):
                rows[i][j] |= _SHARED
    return rows


def _price(step: float, toll: int) -> float:
    """One edge's cost: its length, dearer where it would be drawn along
    something, plus a flat charge for each line it cuts across."""
    if not toll:
        return step
    length = step * (_SHARE_COST if toll & _SHARED else 1.0)
    return length + _CROSS_COST * (toll & _CROSSINGS)


def _terminals(xs: Sequence[float], ys: Sequence[float],
               ports: Sequence[tuple[Vec2, Vec2]],
               centre: Vec2) -> list[tuple[int, int, int, float]]:
    """Ports as (x index, y index, axis, stub length) on the lattice.

    The stub is the run between the shape's centre and its port. It is charged
    for even though its first millimetres are inside the shape and never
    drawn, because what is being compared is where the *rest* of the route
    then has to start from.
    """
    out: list[tuple[int, int, int, float]] = []
    for port, direction in ports:
        i, j = _index(xs, port.x), _index(ys, port.y)
        if i is not None and j is not None:
            axis = 0 if abs(direction.x) >= abs(direction.y) else 1
            out.append((i, j, axis, (port - centre).length))
    return out


def _index(values: Sequence[float], value: float) -> int | None:
    """Which lattice line this coordinate became, once near-equal lines merged."""
    pos = bisect_left(values, value - _GRID_TOL)
    if pos < len(values) and abs(values[pos] - value) <= _GRID_TOL:
        return pos
    return None


def _search(grid: _Lattice,
            starts: Sequence[tuple[int, int, int, float]],
            goals: Sequence[tuple[int, int, int, float]],
            ) -> list[tuple[int, int]] | None:
    """A* over the lattice: shortest route, bends charged for.

    A node is a lattice point *and* the axis it was reached along, because a
    turn costs something, and a path arriving sideways is not the same
    proposition as one arriving head on.

    The heuristic is the Manhattan distance to the nearest port on the far
    shape plus that port's own stub. It never overestimates -- a rectilinear
    path is at least the Manhattan gap, the stub is exact, and the turns and
    tolls it ignores only ever cost more -- so the first time the search pops
    the finish, it holds the cheapest route there is.

    Nothing here orders a Vec2 or iterates a set. The heap holds
    `(cost, sequence number, packed node)`, and that sequence number settles
    every tie in favour of the branch discovered first, which is what makes
    `_PORT_DIRS` an order rather than a suggestion.
    """
    xs, ys = grid.xs, grid.ys
    span = len(ys)
    exits: dict[int, list[tuple[int, float]]] = {}
    for i, j, axis, stub in goals:
        exits.setdefault(i * span + j, []).append((axis, stub))
    marks = [(xs[i], ys[j], stub) for i, j, _, stub in goals]

    def remaining(i: int, j: int) -> float:
        x, y = xs[i], ys[j]
        return min(abs(x - gx) + abs(y - gy) + stub for gx, gy, stub in marks)

    best: dict[int, float] = {}
    came: dict[int, int] = {}
    done: dict[int, bool] = {}
    heap: list[tuple[float, int, int]] = []
    order = 0
    for i, j, axis, stub in starts:
        node = (i * span + j) * 2 + axis
        if stub < best.get(node, math.inf):
            best[node] = stub
            heapq.heappush(heap, (stub + remaining(i, j), order, node))
            order += 1

    while heap:
        _, _, node = heapq.heappop(heap)
        if done.get(node):
            continue                    # a cheaper way here was already taken
        done[node] = True
        if node == _FINISH:
            return _unwind(came, span)
        cost = best[node]
        point, axis = divmod(node, 2)
        i, j = divmod(point, span)

        for axis_out, stub in exits.get(point, ()):
            price = cost + stub + (0.0 if axis_out == axis else _TURN_COST)
            if _offer(heap, best, came, node, _FINISH, price, 0.0, order):
                order += 1
        for ni, nj, naxis, step in _moves(i, j, axis, grid):
            price = cost + step + (0.0 if naxis == axis else _TURN_COST)
            if _offer(heap, best, came, node, (ni * span + nj) * 2 + naxis,
                      price, remaining(ni, nj), order):
                order += 1
    return None


def _offer(heap: list, best: dict[int, float], came: dict[int, int],
           node: int, target: int, price: float, rest: float, order: int) -> bool:
    """Relax one edge. Prices are compared with a tolerance, like every other
    float in this module; two routes agreeing to a nanometre are the same
    route, and the one already found keeps the node."""
    if price >= best.get(target, math.inf) - _GRID_TOL:
        return False
    best[target] = price
    came[target] = node
    heapq.heappush(heap, (price + rest, order, target))
    return True


def _moves(i: int, j: int, axis: int,
           grid: _Lattice) -> Iterator[tuple[int, int, int, float]]:
    """The four neighbours and what each move costs, in `_PORT_DIRS` order so
    ties break the same way everywhere: north, west, south, east."""
    xs, ys = grid.xs, grid.ys
    if j > 0 and not grid.down[i][j - 1]:
        yield i, j - 1, 1, _price(ys[j] - ys[j - 1], grid.down_toll[i][j - 1])
    if i > 0 and not grid.across[j][i - 1]:
        yield i - 1, j, 0, _price(xs[i] - xs[i - 1], grid.across_toll[j][i - 1])
    if j + 1 < len(ys) and not grid.down[i][j]:
        yield i, j + 1, 1, _price(ys[j + 1] - ys[j], grid.down_toll[i][j])
    if i + 1 < len(xs) and not grid.across[j][i]:
        yield i + 1, j, 0, _price(xs[i + 1] - xs[i], grid.across_toll[j][i])


def _unwind(came: Mapping[int, int], span: int) -> list[tuple[int, int]]:
    """The lattice points from the finish back to whichever port it started
    from, in drawing order."""
    out: list[tuple[int, int]] = []
    node = came.get(_FINISH)
    while node is not None:
        out.append(divmod(node // 2, span))
        node = came.get(node)
    out.reverse()
    return out


def _collapse(points: list[Vec2]) -> list[Vec2]:
    """One point per corner: repeated points dropped, collinear runs merged.

    The search returns a vertex per lattice line it crossed, which for a
    straight run down a figure is dozens of points on one line. They are the
    same segment, and leaving them in would give `_round_corners` a fillet to
    cut at every one of them.
    """
    out = [points[0]]
    for point in points[1:]:
        if (point - out[-1]).length <= _GRID_TOL:
            continue
        if len(out) >= 2 and _collinear(out[-2], out[-1], point):
            out[-1] = point
        else:
            out.append(point)
    return out


def _collinear(a: Vec2, b: Vec2, c: Vec2) -> bool:
    first, second = b - a, c - b
    return abs(first.cross(second)) <= _GRID_TOL * (first.length + second.length)


def _clip_ends(src: _End, dst: _End, points: list[Vec2], standoff: float,
               flags: list[str]) -> list[Vec2]:
    """Land the polyline's two ends on the shapes, exactly as an elbow does.

    Everything downstream -- the head insets, `corner=` rounding, the label --
    reads this list and nothing else, so a detour owes the same thing an elbow
    hands over: a clipped, deduped, axis-aligned polyline.
    """
    exit_dir = _unit(points[1] - points[0], EAST)
    entry_dir = _unit(points[-1] - points[-2], EAST)
    start = _clip(src, exit_dir, standoff, "source", flags)
    end = _clip(dst, -entry_dir, standoff, "target", flags)
    if len(points) == 2:
        end = (Vec2(end.x, start.y) if _horizontal(exit_dir)
               else Vec2(start.x, end.y))
        return _two_point(start, end, exit_dir, flags)
    # The clips fired from the centres rather than along a lattice line, and
    # near-equal lines were merged to within a micron on the way in, so the
    # two runs that touch the shapes are re-squared onto the tips they now
    # leave from. Every interior corner already shares exact coordinates.
    points[0], points[-1] = start, end
    points[1] = _square(points[1], start, exit_dir)
    points[-2] = _square(points[-2], end, entry_dir)
    if (points[1] - points[0]).dot(exit_dir) < -EPS:
        # A standoff longer than the clearance pushes the tip past the first
        # corner. Still drawable, and the same complaint the elbow makes.
        _flag(flags, FLAG_OVERLAP)
    return _dedupe(points)


def _horizontal(direction: Vec2) -> bool:
    return abs(direction.x) >= abs(direction.y)


def _square(point: Vec2, tip: Vec2, direction: Vec2) -> Vec2:
    return Vec2(point.x, tip.y) if _horizontal(direction) else Vec2(tip.x, point.y)


def _crosses(points: Sequence[Vec2], boxes: Sequence[Rect]) -> bool:
    return any(_hits(a, b, box)
               for a, b in zip(points, points[1:]) for box in boxes)


def _hits(a: Vec2, b: Vec2, box: Rect) -> bool:
    """Does the segment a->b get inside `box`?

    Liang-Barsky against a box shrunk by `_INSIDE_TOL`, so running along an
    edge is not entering, and clipped to a real length, so touching a corner
    is not either. One test for every segment in this module, axis-aligned or
    not, because the elbow it vets is sometimes neither.
    """
    span = b - a
    low, high = 0.0, 1.0
    for slope, room in (
        (-span.x, a.x - (box.x0 + _INSIDE_TOL)),
        (span.x, (box.x1 - _INSIDE_TOL) - a.x),
        (-span.y, a.y - (box.y0 + _INSIDE_TOL)),
        (span.y, (box.y1 - _INSIDE_TOL) - a.y),
    ):
        if abs(slope) <= EPS:
            if room < 0.0:
                return False            # parallel to this side and outside it
            continue
        cut = room / slope
        if slope < 0.0:
            low = max(low, cut)
        else:
            high = min(high, cut)
        if low > high:
            return False
    return (high - low) * span.length > _INSIDE_TOL


def _covers(outer: Rect, inner: Rect) -> bool:
    return (inner.x0 >= outer.x0 - _INSIDE_TOL
            and inner.x1 <= outer.x1 + _INSIDE_TOL
            and inner.y0 >= outer.y0 - _INSIDE_TOL
            and inner.y1 <= outer.y1 + _INSIDE_TOL)


def _area(box: Rect) -> float:
    return max(box.width, 0.0) * max(box.height, 0.0)


def _leader_points(link: Link, src: _End, dst: _End, flags: list[str]) -> list[Vec2]:
    """The scientific-illustration callout: a leg off the spot, then a
    horizontal shoulder running into the label. `route` is ignored for these.

    **The two ends are not interchangeable, and the source is the spot.** The
    dot goes on `source` (`_head_kinds` gives a leader its head at the source
    end and nothing at the target) and the horizontal shoulder runs into
    `target`, so a callout is declared `link(region, label)` -- the thing
    being named first, the word second. That is the opposite of reading order,
    and declaring it the way it reads puts a dot beside the word and an elbow
    against the drawing, which looks like a bug in the router rather than a
    swapped pair of arguments. `inklet.annotate(target, text, ...)` is the
    spelling that takes them in the order a caption is written and gets this
    right for you.

    The asymmetry is not incidental. The shoulder is horizontal so that the
    line arrives along the baseline of the word it points at, and only one end
    of a leader can be a word; the clipping is asymmetric for the same reason,
    since `end` is clipped along `toward` while the leg leaves the source
    along its own direction.
    """
    shoulder = DEFAULT_SHOULDER if link.shoulder is None else link.shoulder
    if (dst.point - src.point).length <= EPS:
        _flag(flags, FLAG_COINCIDENT)
        return [src.point, src.point]

    toward = Vec2(_sign(dst.point.x - src.point.x), 0.0)
    end = _clip(dst, -toward, link.standoff, "target", flags)
    # A shoulder longer than the run itself would fold back on the leg.
    shoulder = min(shoulder, abs(end.x - src.point.x) * 0.5)
    knee = end - toward * shoulder
    leg = knee - src.point
    if leg.length <= EPS:
        return _dedupe([_clip(src, toward, link.standoff, "source", flags), end])
    start = _clip(src, leg.normalized(), link.standoff, "source", flags)
    return _dedupe([start, knee, end])


# -- waypoints, ports and the routes that are not one line ----------------
#
# Everything below shares the two rules the plain routes follow: an end that
# is a shape is clipped to its boundary along the direction the connector
# actually leaves on, and nothing is decided from a coordinate the author did
# not give. What changes is the shape of the polyline in between.


def _vias(link: Link, placements: Mapping[str, Placement],
          flags: list[str]) -> list[Vec2]:
    """The via-points, in figure coordinates, in the order given."""
    return [_via_point(spec, placements) for spec in link.waypoints]


def _via_point(spec, placements: Mapping[str, Placement]) -> Vec2:
    if isinstance(spec, Vec2):
        return spec
    if isinstance(spec, AnchorRef):
        placement = placements.get(spec.diagram.id)
        if placement is None:
            raise DiagramError(
                f"{spec.diagram.id} is not part of this figure; add it before "
                "routing a link through one of its anchors")
        return placement.point(spec.name)
    if isinstance(spec, (tuple, list)) and len(spec) == 2:
        return Vec2(float(spec[0]), float(spec[1]))
    if isinstance(spec, (tuple, list)) and len(spec) == 3:
        # `(anchor, dx, dy)` -- that spot, nudged. The clearance a route needs
        # off a shape is a distance from the shape, not a coordinate on the
        # page, and writing it as one throws away the only thing that makes the
        # route survive the shape moving.
        return _via_point(spec[0], placements) + Vec2(float(spec[1]),
                                                      float(spec[2]))
    raise LinkError(
        f"a waypoint is a Vec2, an (x, y) pair, an AnchorRef or an "
        f"(anchor, dx, dy) triple, not a {type(spec).__name__}; a shape's own "
        "centre is spelt shape.at('center')")


def _free_end(at: Vec2) -> _End:
    """A via-point as an endpoint: nothing to clip on, nothing to leave."""
    return _End(at, None, Rect(at.x, at.y, at.x, at.y), True)


def _via_points(link: Link, src: _End, dst: _End, vias: Sequence[Vec2],
                obstacles: Sequence[Obstacle],
                drawn: Sequence[tuple[Vec2, Vec2]],
                flags: list[str]) -> list[Vec2]:
    """A route through every via-point in turn, one leg at a time.

    The legs are independent by construction, which is the point: a layout
    that already knows where a long edge should run hands over the corridor
    and gets exactly that polyline back, rather than paying for a search that
    has to rediscover it and might not.
    """
    # Every route that turns wants these, not only `avoid`: a search uses them
    # to go round a box, and a plain Manhattan leg uses them to pick which of
    # its two corners to turn on. Only `straight` never asks.
    boxes = (_blocking_boxes(obstacles, _own_ids(link.source) | _own_ids(link.target),
                             src, dst)
             if link.route != "straight" else [])
    ends = [src] + [_free_end(via) for via in vias] + [dst]
    points = [src.point]
    for a, b in zip(ends, ends[1:]):
        arriving = (_unit(points[-1] - points[-2], EAST)
                    if len(points) >= 2 else None)
        points.extend(_unkinked(points,
                                _leg(link.route, a, b, arriving, boxes, drawn)))
    return _land(link, src, dst, _collapse(points), flags)


def _unkinked(points: Sequence[Vec2], leg: list[Vec2]) -> list[Vec2]:
    """The same leg, mirrored if it would start by retracing the one before.

    Two Manhattan legs meeting at a via each choose their corner alone, and
    each choice is defensible on its own: the pair can still arrive and leave
    on the same axis, which draws the line up to the via and straight back
    down over itself. Nothing survives that -- collinear points collapse, and
    the via disappears with the spike -- so the waypoint the caller asked for
    is silently ignored. A Manhattan leg has exactly two shapes, and the other
    one turns the pair into a single run *through* the via, which is what a
    waypoint was for.
    """
    if len(points) < 2 or len(leg) != 2:
        return leg
    via = points[-1]
    if (via - points[-2]).dot(leg[0] - via) >= -EPS:
        return leg
    return [via + leg[-1] - leg[0], leg[-1]]


def _leg(route: str, a: _End, b: _End, arriving: Vec2 | None,
         boxes: Sequence[Rect],
         drawn: Sequence[tuple[Vec2, Vec2]]) -> list[Vec2]:
    """One leg of a route with waypoints: everything after `a`, up to `b`."""
    if route == "straight":
        return [b.point]
    corner = _corner_points(a, b, arriving, boxes)
    if route == "avoid" and boxes and _crosses([a.point] + corner, boxes):
        detour = _detour_raw(a, b, boxes, drawn)
        if detour is not None:
            return detour[1:]
    return corner


def _corner_points(a: _End, b: _End, arriving: Vec2 | None,
                   boxes: Sequence[Rect] = ()) -> list[Vec2]:
    """The Manhattan leg from `a` to `b`: at most one corner, on the axis that
    keeps the run out of the shapes at either end.

    Four rules, in the order they are allowed to decide. A leg leaving a shape
    turns on whichever axis gets it out of that shape, because the alternative
    starts the route inside the box it is leaving. A leg *carrying on* through
    a via-point keeps the axis it arrived on whenever that still heads toward
    the target: the two legs then collapse into one straight run, which is
    both the shorter answer and the one an author placing a via-point meant --
    a waypoint is a line to follow, not a corner to add. A leg arriving at a
    shape mirrors the first rule. Failing all three, the dominant separation
    decides.

    Then the veto: whichever corner the rules chose, if its two segments cut
    through a shape and the other corner's do not, the other one wins. The
    rules above are local -- each sees two points and one box -- and near a tie
    they can send a leg straight through the middle of the drawing. This is
    not a search and does not become one: two candidates, one test each, and
    a route with nothing in the way comes out exactly as the rules said.
    """
    dx, dy = b.point.x - a.point.x, b.point.y - a.point.y
    if abs(dx) <= _ALIGN_TOL:
        return [Vec2(a.point.x, b.point.y)]
    if abs(dy) <= _ALIGN_TOL:
        return [Vec2(b.point.x, a.point.y)]
    sideways = Vec2(b.point.x, a.point.y)       # turn after a horizontal run
    upright = Vec2(a.point.x, b.point.y)        # turn after a vertical one
    carry = _carries_on(a.point, arriving, sideways, upright, b.box)
    if not a.pinned:
        horizontal = _leaves_sideways(a.box, a.point, b.point)
    elif carry is not None:
        horizontal = carry
    elif not b.pinned:
        horizontal = not _leaves_sideways(b.box, b.point, a.point)
    elif arriving is not None:
        horizontal = abs(arriving.x) > abs(arriving.y)
    else:
        horizontal = abs(dx) >= abs(dy)
    corner = sideways if horizontal else upright
    other = upright if horizontal else sideways
    if boxes and (_crosses([a.point, corner, b.point], boxes)
                  and not _crosses([a.point, other, b.point], boxes)):
        corner = other
    return [corner, b.point]


def _carries_on(via: Vec2, arriving: Vec2 | None,
                sideways: Vec2, upright: Vec2, target: Rect) -> bool | None:
    """Would carrying on the way the route came in reach one of the corners?

    True for the horizontal-first corner, False for the vertical-first one,
    and None in the three cases where the question does not apply: there is no
    incoming leg; the continuation would head *away* from the target, which is
    a spike rather than a run and is `_unkinked`'s problem, not this one; or
    the run to that corner would go *into* the shape it is aiming at, which is
    the case the arrival rule below exists for -- a route that turns at the
    target's centre has already drawn itself across the target's face.
    """
    if arriving is None:
        return None
    horizontal = abs(arriving.x) > abs(arriving.y)
    corner = sideways if horizontal else upright
    if (corner - via).dot(arriving) <= EPS or _hits(via, corner, target):
        return None
    return horizontal


def _leaves_sideways(box: Rect, inside: Vec2, outside: Vec2) -> bool:
    """Would a run from `inside` to `outside` leave `box` left or right?

    Not by the angle, which would send a route out through the long side of a
    wide box for a target a millimetre off the centre line, but by which way
    is *out*: a point level with the box has to be reached sideways whatever
    the angle says. Only when it is beyond the box on both axes does the
    dominant separation decide.
    """
    within_x = box.x0 - _ALIGN_TOL <= outside.x <= box.x1 + _ALIGN_TOL
    within_y = box.y0 - _ALIGN_TOL <= outside.y <= box.y1 + _ALIGN_TOL
    if within_y and not within_x:
        return True
    if within_x and not within_y:
        return False
    return abs(outside.x - inside.x) >= abs(outside.y - inside.y)


def _land(link: Link, src: _End, dst: _End, points: list[Vec2],
          flags: list[str]) -> list[Vec2]:
    """Clip a finished polyline onto the two shapes it runs between."""
    if len(points) < 2:
        points = [points[0], points[0]]
    exit_dir = _unit(points[1] - points[0], EAST)
    entry_dir = _unit(points[-1] - points[-2], EAST)
    start = _clip(src, exit_dir, link.standoff, "source", flags)
    end = _clip(dst, -entry_dir, link.standoff, "target", flags)
    points[0], points[-1] = start, end
    if link.route != "straight" and len(points) > 2:
        # The clip fired from a centre, so it agrees with the first corner to
        # the last bit; square it, exactly as a detour's ends are squared.
        points[1] = _square(points[1], start, exit_dir)
        points[-2] = _square(points[-2], end, entry_dir)
    if (points[1] - points[0]).dot(exit_dir) < -EPS:
        _flag(flags, FLAG_OVERLAP)      # the first leg is inside its own shape
    return _dedupe(points)


def _ported(link: Link, src: _End, dst: _End) -> tuple[_End, _End]:
    """Slide each end along its own shape's edge by `port` millimetres.

    The axis is the one across the connector's dominant direction -- the same
    axis the elbow leaves on -- so a port is always a step *along* the edge
    the arrow crosses and never a step out through it. That is what turns
    three arrows out of one box's centre into three arrows out of three
    points, which is the difference between a bundle and a single line
    wearing three heads.
    """
    if not link.port and not link.target_port:
        return src, dst
    delta = dst.point - src.point
    across = Vec2(1.0, 0.0) if abs(delta.x) < abs(delta.y) else Vec2(0.0, 1.0)
    return _slid(src, across * link.port), _slid(dst, across * link.target_port)


#: How much of a shape's half-extent a port may use. The clip ray is fired
#: from the slid point, so a port that leaves the shape has nothing to clip
#: against and the arrow runs to a point in mid-air. Keeping a tenth back also
#: keeps the outermost shaft off a rounded corner.
_PORT_LIMIT = 0.9


def _slid(end: _End, by: Vec2) -> _End:
    """The same endpoint, firing from a different point on the same shape.

    Clamped to stay inside the shape: a caller asking for a port wider than
    the face it is on means "as far out as this box goes", not "off the box".
    """
    reach = (end.box.width if abs(by.x) > abs(by.y) else end.box.height) / 2.0
    limit = reach * _PORT_LIMIT
    span = by.length
    if span > limit > 0.0:
        by = by * (limit / span)
    return _End(end.point + by, end.trace, end.box, end.pinned, end.guard)


def _bow_plan(link: Link, src: _End, dst: _End, src_head: str | None,
              dst_head: str | None, flags: list[str]) -> _Plan:
    """A route bowed off the straight line, so a second arrow between the same
    two shapes is a second visible curve.

    `offset` is measured at the midpoint and to the right of travel, so two
    opposing arrows given the *same* offset come out either side of the line
    between their shapes -- which is what a reader expects of a pair, and what
    makes the graph layer's job one number rather than one number and a sign.
    """
    if (dst.point - src.point).length <= EPS:
        _flag(flags, FLAG_COINCIDENT)
        return _Plan((_Strand((src.point, src.point)),), (src.point, src.point))
    # Clip along the curve's own end tangents rather than along the chord: a
    # bowed line meets its shape at an angle, and clipping on the chord would
    # leave the tip floating off the boundary by most of the sagitta.
    guess = bezier.bow(src.point, dst.point, link.offset)
    start = _clip(src, _unit(guess[1] - guess[0], EAST), link.standoff,
                  "source", flags)
    end = _clip(dst, _unit(guess[2] - guess[3], EAST), link.standoff,
                "target", flags)
    if (end - start).dot(dst.point - src.point) < -EPS:
        _flag(flags, FLAG_OVERLAP)
        middle = (start + end) * 0.5
        return _Plan((_Strand((middle, middle)),), (middle, middle))
    arc = bezier.bow(start, end, link.offset)
    points = bezier.flatten((arc,))
    return _Plan((_Strand(points, (arc,), src_head, dst_head),), points)


# -- self-loops -----------------------------------------------------------

_LOOP_DIRS = {"n": Vec2(0.0, -1.0), "e": Vec2(1.0, 0.0),
              "s": Vec2(0.0, 1.0), "w": Vec2(-1.0, 0.0)}

#: How far off the side's own normal the two ends of a loop sit. Half a
#: normal is about 27 degrees each way: wide enough that the loop reads as a
#: loop rather than as a line doubling back, narrow enough that both feet stay
#: on the side the author asked for even on a box twice as wide as it is tall.
_LOOP_LEAN = 0.5


def _is_loop(link: Link) -> bool:
    """Does this link start and end on the same shape?

    An explicit `loop=` always says so. Otherwise it is inferred only from two
    bare shapes: `link(a.at("w"), a.at("e"))` names two exact spots and means
    the line between them, which is a chord and not a loop.
    """
    if _many(link.source) or _many(link.target):
        return False        # a trunk has no single shape to loop on
    if link.loop is not None:
        return True
    if isinstance(link.source, AnchorRef) or isinstance(link.target, AnchorRef):
        return False
    return _end_id(link.source) == _end_id(link.target)


def _loop_plan(link: Link, src: _End, obstacles: Sequence[Obstacle],
               drawn: Sequence[tuple[Vec2, Vec2]], flags: list[str]) -> _Plan:
    """An arc out of one side of a shape and back into it."""
    size = DEFAULT_ARROW_SIZE if link.arrow_size is None else link.arrow_size
    height = DEFAULT_LOOP * size if link.loop_size is None else link.loop_size
    out = _LOOP_DIRS[_loop_side(link, src, obstacles, drawn, height)]
    across = out.perp()
    leave = _clip(src, (out - across * _LOOP_LEAN).normalized(), link.standoff,
                  "source", flags)
    back = _clip(src, (out + across * _LOOP_LEAN).normalized(), link.standoff,
                 "target", flags)
    curves = bezier.loop_curves(leave, back, out, height)
    points = bezier.flatten(curves)
    src_head, dst_head = _head_kinds(link)
    return _Plan((_Strand(points, curves, src_head, dst_head),), points)


def _loop_side(link: Link, src: _End, obstacles: Sequence[Obstacle],
               drawn: Sequence[tuple[Vec2, Vec2]], height: float) -> str:
    """Which side a loop goes on: the one asked for, or the emptiest.

    Scored the way a label's candidate spots are -- obstructed area plus ink
    crossed -- because it is the same question. Ties go to the first side
    tried, so a box with nothing around it always loops north and a row of
    states all loop the same way.

    The paper a side has to be clear of is the arc *plus the label it carries*,
    which is why `_label_reach` is added to the arc's own height. A loop and
    its label are one mark, and a side that fits the arc but not the word on it
    is a side the placer will have to shove the word off. On the four-mark-deep
    arcs in this library the difference is two to three times the span scored:
    `examples/state_machine.py`'s `poll` reaches 8.7mm off its box, not 4mm.
    """
    if link.loop not in (None, "auto"):
        return link.loop
    own = _own_ids(link.source)
    free = [obstacle for obstacle in obstacles if obstacle.id not in own]
    reach = height + _label_reach(link)
    best: tuple[float, str] | None = None
    for side, out in _LOOP_DIRS.items():
        span = _loop_box(src.box, out, reach)
        blocked = _blocked_area(span, free) + _crossed_length(span, drawn)
        if best is None or blocked < best[0]:
            best = (blocked, side)
        if blocked <= 0.0:
            break
    return best[1]


def _label_reach(link: Link) -> float:
    """How far past the arc the loop's label will want to be, in millimetres.

    The larger of the label's two dimensions rather than the one facing out:
    the placer is free to sit the word beside the arc or beyond it, and a side
    that only fits the narrow reading is a side the label will be pushed off.
    A link with no label reaches nothing extra.
    """
    if link.label is None:
        return 0.0
    try:
        box = link.label.bbox
    except DiagramError:
        return 0.0
    return max(box.width, box.height)


def _loop_box(box: Rect, out: Vec2, height: float) -> Rect:
    """The paper a loop on this side would take up."""
    if out.y < 0:
        return Rect(box.x0, box.y0 - height, box.x1, box.y0)
    if out.y > 0:
        return Rect(box.x0, box.y1, box.x1, box.y1 + height)
    if out.x > 0:
        return Rect(box.x1, box.y0, box.x1 + height, box.y1)
    return Rect(box.x0 - height, box.y0, box.x0, box.y1)


# -- shared trunk ---------------------------------------------------------


def _trunk_plan(link: Link, placements: Mapping[str, Placement],
                flags: list[str]) -> _Plan:
    """One stem that forks: `link(a, [b, c])`, and its mirror `link([a, b], c)`.

    A branch-and-merge flow drawn as one link per pair is several lines
    leaving one box at once, and the reader has to work out that they are the
    same signal. Drawn as a trunk it is what it is: one stem, one place where
    it divides, one branch each. The shared part is a single stroke, so there
    is nothing for `COINCIDENT_SHAFT` to find -- it keys segments by the link
    that owns them, and a trunk owns all of its own.

    `route="orthogonal"` draws the bus: a stem, a run across, a drop into each
    shape. Anything else draws the fan: a stem to one fork point and a
    straight line from there to each shape. `route="avoid"` is the bus, since
    a trunk is a declaration of where the ink goes and there is nothing left
    for a search to decide.
    """
    forks_at_target = _many(link.target)
    stem_side = "source" if forks_at_target else "target"
    leaf_side = "target" if forks_at_target else "source"
    stem = _resolve_end(link.source if forks_at_target else link.target,
                        placements, stem_side, flags)
    leaves = [_resolve_end(spec, placements, leaf_side, flags)
              for spec in _sides(link.target if forks_at_target else link.source)]

    middle = sum((leaf.point for leaf in leaves), Vec2(0.0, 0.0)) * (1.0 / len(leaves))
    delta = middle - stem.point
    if delta.length <= EPS:
        _flag(flags, FLAG_COINCIDENT)
        point = stem.point
        return _Plan((_Strand((point, point)),), (point, point))

    vertical = abs(delta.y) >= abs(delta.x)
    step = _sign(delta.y if vertical else delta.x)
    forward = Vec2(0.0, step) if vertical else Vec2(step, 0.0)

    def compose(across: float, along: float) -> Vec2:
        return Vec2(across, along) if vertical else Vec2(along, across)

    def across_of(point: Vec2) -> float:
        return point.x if vertical else point.y

    def along_of(point: Vec2) -> float:
        return point.y if vertical else point.x

    def front(box: Rect) -> float:
        if vertical:
            return box.y1 if step > 0 else box.y0
        return box.x1 if step > 0 else box.x0

    def back(box: Rect) -> float:
        if vertical:
            return box.y0 if step > 0 else box.y1
        return box.x0 if step > 0 else box.x1

    stem_tip = _clip(stem, forward, link.standoff, stem_side, flags)
    if link.stem is not None:
        reach = link.stem
    else:
        # Halfway to the nearest shape on the far side, which is where a
        # person puts it: far enough out of the box for the corner to be
        # visible, near enough that the branches are the long part.
        clear = min((back(leaf.box) - front(stem.box)) * step for leaf in leaves)
        reach = max(_MIN_GAP, clear * 0.5)
    fork_at = along_of(stem_tip) + step * reach

    strands: list[_Strand] = []
    src_head, dst_head = _head_kinds(link)
    stem_head = src_head if forks_at_target else dst_head
    leaf_head = dst_head if forks_at_target else src_head
    stem_points = (stem_tip, compose(across_of(stem_tip), fork_at))

    if link.route == "straight":
        fork = stem_points[-1]
        branches = []
        for leaf in leaves:
            toward = _unit(fork - leaf.point, EAST)
            tip = _clip(leaf, toward, link.standoff, leaf_side, flags)
            branches.append((fork, tip))
    else:
        branches = []
        for leaf in leaves:
            tip = _clip(leaf, -forward, link.standoff, leaf_side, flags)
            branches.append((compose(across_of(tip), fork_at), tip))
        rail = [across_of(stem_tip)] + [across_of(tip) for _, tip in branches]
        if max(rail) - min(rail) > EPS:
            strands.append(_Strand((compose(min(rail), fork_at),
                                    compose(max(rail), fork_at))))

    strands.insert(0, _Strand(stem_points, (), stem_head, None))
    strands.extend(_Strand(branch, (), None, leaf_head) for branch in branches)
    # The spine runs source to target whichever side forked, so `label_side`
    # and the start/end anchors mean the same thing on a merge as on a fork.
    spine = tuple(stem_points) + tuple(branches[0])
    return _Plan(tuple(strands), spine if forks_at_target else spine[::-1])


# -- arrow heads ----------------------------------------------------------


def _head_kinds(link: Link) -> tuple[str | None, str | None]:
    """(head at the source end, head at the target end)."""
    if link.kind == "line" or link.head == "none":
        return None, None
    if link.kind == "leader":
        return (link.head or "dot"), None
    head = link.head or "triangle"
    if link.kind == "double":
        return head, head
    return None, head


def _head_prim(kind: str, tip: Vec2, direction: Vec2,
               size: float) -> tuple[PathPrim, float]:
    """A head whose tip sits exactly on `tip`, plus how far the shaft must stop
    short of it so the two do not pile up into a bulge."""
    across = direction.perp()
    if kind == "triangle":
        back = tip - direction * size
        half = across * (size * _HEAD_HALF_WIDTH)
        sub = Subpath((tip, back + half, back - half), closed=True)
        return PathPrim((sub,), filled=True), size
    if kind == "open":
        back = tip - direction * size
        half = across * (size * _HEAD_HALF_WIDTH)
        # One three-point subpath, so the two strokes miter at the tip.
        return PathPrim((Subpath((back + half, tip, back - half)),), filled=False), 0.0
    if kind == "dot":
        return PathPrim((_circle(tip, size * _DOT_RADIUS),), filled=True), 0.0
    raise LinkError(f"unknown arrow head {kind!r}")


def _circle(center: Vec2, radius: float, steps: int = 6) -> Subpath:
    """Four cubics, kept in `curves` so the backend can emit real beziers, plus
    the flattened points every geometry query in core works from."""
    points: list[Vec2] = []
    curves: list[tuple[Vec2, Vec2, Vec2, Vec2]] = []
    for quadrant in range(4):
        a0 = math.pi * quadrant / 2
        a1 = a0 + math.pi / 2
        p0 = center + Vec2(math.cos(a0), math.sin(a0)) * radius
        p3 = center + Vec2(math.cos(a1), math.sin(a1)) * radius
        c1 = p0 + Vec2(-math.sin(a0), math.cos(a0)) * (_KAPPA * radius)
        c2 = p3 - Vec2(-math.sin(a1), math.cos(a1)) * (_KAPPA * radius)
        curves.append((p0, c1, c2, p3))
        points.extend(_bezier(p0, c1, c2, p3, i / steps) for i in range(steps))
    return Subpath(tuple(points), closed=True, curves=tuple(curves))


# -- shaft ----------------------------------------------------------------


def _inset_path(points: list[Vec2], start_inset: float, end_inset: float,
                flags: list[str]) -> list[Vec2]:
    """Pull the shaft back from each tip by the head length."""
    pts = _trim_front(list(points), start_inset, flags)
    pts.reverse()
    pts = _trim_front(pts, end_inset, flags)
    pts.reverse()
    if len(pts) < 2:
        pts = [points[0], points[-1]]
    return pts


def _trim_front(pts: list[Vec2], amount: float, flags: list[str]) -> list[Vec2]:
    while amount > EPS and len(pts) >= 2:
        segment = pts[1] - pts[0]
        length = segment.length
        if length <= EPS:
            pts.pop(0)
            continue
        if amount < length - EPS:
            pts[0] = pts[0] + segment * (amount / length)
            return pts
        if len(pts) == 2:
            # The whole link is shorter than its own head. Keep a stub so the
            # shaft does not vanish, and let the linter complain.
            _flag(flags, FLAG_SHORT)
            pts[0] = pts[0] + segment * 0.5
            return pts
        amount -= length
        pts.pop(0)
    return pts


def _round_corners(points: list[Vec2], radius: float,
                   steps: int = 4) -> tuple[tuple[Vec2, ...], tuple]:
    """Fillet the elbows.

    `points` stays the flattened form core measures with; `curves` carries the
    exact cubics for the backend. The backend draws from `curves` alone when
    they are present, so the chain has to cover the whole path -- straight runs
    included, as cubics with their controls on the line. The kappa constant is
    exact at 90 degrees, which is every corner an orthogonal route makes.
    """
    if radius <= 0 or len(points) < 3:
        return tuple(points), ()
    flat = [points[0]]
    curves: list[tuple[Vec2, Vec2, Vec2, Vec2]] = []
    cursor = points[0]

    def run_to(p: Vec2) -> None:
        if (p - cursor).length > EPS:
            curves.append(_straight_cubic(cursor, p))

    for i in range(1, len(points) - 1):
        previous, corner, following = points[i - 1], points[i], points[i + 1]
        v_in, v_out = corner - previous, following - corner
        square = v_in.length > EPS and v_out.length > EPS
        if square:
            u_in, u_out = v_in.normalized(), v_out.normalized()
            square = abs(u_in.cross(u_out)) > EPS      # collinear: nothing to round
        if not square:
            run_to(corner)
            flat.append(corner)
            cursor = corner
            continue
        r = min(radius, v_in.length / 2, v_out.length / 2)
        enter, leave = corner - u_in * r, corner + u_out * r
        c1, c2 = enter + u_in * (r * _KAPPA), leave - u_out * (r * _KAPPA)
        run_to(enter)
        curves.append((enter, c1, c2, leave))
        flat.append(enter)
        flat.extend(_bezier(enter, c1, c2, leave, s / steps) for s in range(1, steps))
        flat.append(leave)
        cursor = leave
    run_to(points[-1])
    flat.append(points[-1])
    return tuple(flat), tuple(curves)


def _straight_cubic(p0: Vec2, p3: Vec2) -> tuple[Vec2, Vec2, Vec2, Vec2]:
    """A cubic that is exactly its own chord."""
    step = (p3 - p0) * (1 / 3)
    return (p0, p0 + step, p0 + step * 2, p3)


# -- label ----------------------------------------------------------------


def _place_label(label: Diagram, points: list[Vec2], side: str, offset: float,
                 obstacles: Sequence[Obstacle] = (),
                 drawn: Sequence[tuple[Vec2, Vec2]] = (), *,
                 own: Sequence[tuple[Vec2, Vec2]] = ()) -> Diagram | None:
    """Sit the label beside the line, and clear of everything else.

    M1 keeps labels horizontal rather than rotating them to follow the line:
    horizontal text is more readable at figure sizes and it is what journals
    print. Rotation, if it ever arrives, belongs behind an explicit option.

    The midpoint of a shaft is the natural place for a label and, on a branch
    that converges, the worst one: it is exactly where the two shapes being
    joined already sit. So the asked-for spot is only the first candidate. If
    it lands on something the label flips to the other side of the line and
    slides along it, and the least-obstructed candidate wins. The first
    candidate is kept whenever it is clear, so an uncluttered figure places
    labels exactly where it always did.
    """
    try:
        box = label.bbox
    except DiagramError:
        return None                             # an empty label has nowhere to go
    total = _path_length(points)
    best: tuple[float, Vec2] | None = None
    for at, normal in _label_candidates(points, box, side, offset, total):
        centre = at + normal * (offset + _half_extent(box, normal))
        spot = Rect.from_size(box.width, box.height, centre)
        blocked = _blocked_area(spot, obstacles) + _crossed_length(spot, drawn)
        if best is None or blocked < best[0]:
            best = (blocked, centre)
        if blocked <= 0.0:
            break                               # nothing beats open space
    if best[0] > 0.0:
        # A fallback beside a fork must clear every branch, including the
        # one omitted from the label's spine. Otherwise moving off a box can
        # simply hide the branch under the label's background instead.
        for centre in _label_bend_candidates(points, box, offset):
            spot = Rect.from_size(box.width, box.height, centre)
            blocked = (_blocked_area(spot, obstacles)
                       + _crossed_length(spot, drawn)
                       + _crossed_length(spot, own))
            if blocked <= 0.0:
                best = (blocked, centre)
                break
    delta = best[1] - box.center
    return Diagram(children=(label.translated(delta.x, delta.y),), kind=LABEL_KIND)


def _label_candidates(points: list[Vec2], box: Rect, side: str, offset: float,
                      total: float) -> Iterable[tuple[Vec2, Vec2]]:
    """Where a label may sit, best guess first: the requested spot, then the
    mirror of it across the line, then progressively further along the line."""
    base = _label_distance(points, box, side, offset, total)
    for distance in (base, total * 0.30, total * 0.70, total * 0.18, total * 0.82):
        at, tangent = _point_along(points, min(max(distance, 0.0), total))
        normal = _label_normal(tangent)
        yield at, normal
        yield at, -normal


def _label_bend_candidates(points: list[Vec2], box: Rect,
                           offset: float) -> Iterable[Vec2]:
    """Extra positions beside bends, used only when ordinary placement fails."""
    # A short fork's sampled positions can all land too close to the source
    # or on a diagonal whose normal lifts the label back into the source.
    # The bend itself can still have room beside it. Try both incident
    # directions after the usual positions, preserving labels that fit.
    # A trunk's stem and fork may repeat a vertex; skip those zero-length runs.
    vertices = _dedupe(points)
    for previous, corner, following in zip(vertices, vertices[1:], vertices[2:]):
        incoming = (corner - previous).normalized()
        outgoing = (following - corner).normalized()
        if abs(incoming.cross(outgoing)) <= EPS:
            continue
        for tangent in (incoming, outgoing):
            normal = _label_normal(tangent)
            for extra in (0.0, max(abs(offset), 1.0), max(box.width, box.height)):
                reach = offset + _half_extent(box, normal) + extra
                yield corner + normal * reach
                yield corner - normal * reach


#: A connector through a label is scored as if it were a stroke this wide
#: lying on the text: a 1 mm line across a 10 mm word blocks as much as a
#: 10 mm^2 box does, which is enough to make any clear spot preferable.
_CROSSING_WEIGHT = 1.0


def _crossed_length(rect: Rect, drawn: Sequence[tuple[Vec2, Vec2]]) -> float:
    """Length of already-drawn connector lying inside `rect`, as blocked area."""
    if not drawn:
        return 0.0
    return _CROSSING_WEIGHT * sum(_run_inside(rect, a, b) for a, b in drawn)


def _run_inside(rect: Rect, a: Vec2, b: Vec2) -> float:
    """How much of segment a-b lies inside an axis-aligned box (Liang-Barsky)."""
    dx, dy = b.x - a.x, b.y - a.y
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a.x - rect.x0), (dx, rect.x1 - a.x),
                 (-dy, a.y - rect.y0), (dy, rect.y1 - a.y)):
        if abs(p) < EPS:
            if q < 0.0:
                return 0.0
            continue
        t = q / p
        if p < 0.0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return 0.0
    return (t1 - t0) * math.hypot(dx, dy)


def _blocked_area(rect: Rect, obstacles: Sequence[Obstacle]) -> float:
    """Total area of `rect` covered by obstacles.

    Overlapping obstacles are double-counted. That is deliberate: this is a
    ranking, not a measurement, and piling up makes a crowded spot lose harder.
    """
    area = 0.0
    for other in (o.rect for o in obstacles):
        hit = rect.overlap(other)
        if hit is not None:
            area += hit.width * hit.height
    return area


def _label_distance(points: list[Vec2], box: Rect, side: str, offset: float,
                    total: float) -> float:
    if side == "center":
        return total / 2
    if side == "start":
        along = _half_extent(box, _unit(points[1] - points[0], EAST)) + offset
        return min(along, total / 2)
    along = _half_extent(box, _unit(points[-1] - points[-2], EAST)) + offset
    return max(total - along, total / 2)


def _label_normal(tangent: Vec2) -> Vec2:
    """Above the line, since y grows downward; east of a vertical line, which is
    where a reader looks first."""
    normal = tangent.perp()
    if normal.y > EPS:
        return -normal
    if abs(normal.y) <= EPS and normal.x < 0:
        return -normal
    return normal


def _half_extent(box: Rect, direction: Vec2) -> float:
    """How far a box reaches from its centre along a direction."""
    return abs(direction.x) * box.width / 2 + abs(direction.y) * box.height / 2


# -- small helpers --------------------------------------------------------


def _sign(value: float) -> float:
    return 1.0 if value >= 0 else -1.0


def _unit(v: Vec2, fallback: Vec2) -> Vec2:
    return fallback if v.length <= EPS else v.normalized()


def _dedupe(points: list[Vec2]) -> list[Vec2]:
    out = [points[0]]
    for p in points[1:]:
        if (p - out[-1]).length > EPS:
            out.append(p)
    if len(out) < 2:
        out.append(out[0])                      # a point, not a crash
    return out


def _path_length(points: list[Vec2]) -> float:
    return sum((b - a).length for a, b in zip(points, points[1:]))


def _point_along(points: list[Vec2], distance: float) -> tuple[Vec2, Vec2]:
    """Point at `distance` along the polyline, with the local direction."""
    remaining = max(0.0, distance)
    for a, b in zip(points, points[1:]):
        length = (b - a).length
        if length <= EPS:
            continue
        if remaining <= length:
            direction = (b - a) * (1.0 / length)
            return a + direction * remaining, direction
        remaining -= length
    direction = _unit(points[-1] - points[-2], EAST)
    return points[-1], direction


def _bezier(p0: Vec2, c1: Vec2, c2: Vec2, p3: Vec2, t: float) -> Vec2:
    u = 1.0 - t
    return (p0 * (u * u * u) + c1 * (3 * u * u * t)
            + c2 * (3 * u * t * t) + p3 * (t * t * t))


def _flag(flags: list[str], name: str) -> None:
    if name not in flags:
        flags.append(name)


def _mark(name: str | None, flags: list[str]) -> str | None:
    if not flags:
        return name
    return f"{name or LINK_KIND}{FLAG_SEP}{','.join(flags)}"


def link_flags(routed: Diagram) -> tuple[str, ...]:
    """Whatever went wrong while routing this link, for the linter."""
    if routed.name is None or FLAG_SEP not in routed.name:
        return ()
    return tuple(routed.name.split(FLAG_SEP, 1)[1].split(","))


def link_ends(attached: Sequence[str]) -> tuple[str, ...]:
    """The two endpoint ids out of a routed link's `attached_to`.

    Everything after them is a declared `through=` shape, which is exempt from
    the crossing and clearance rules but is not an end of the arrow: it must
    not appear in "a -> b", and it must not be asked whether an elbow has room
    to turn between it and something else.
    """
    return tuple(attached[:2])


def link_name(routed: Diagram) -> str | None:
    """The author's name for a routed link, with any flags stripped off."""
    if routed.name is None:
        return None
    base = routed.name.split(FLAG_SEP, 1)[0]
    return base if base and base != LINK_KIND else None


def is_degenerate(routed: Diagram) -> bool:
    return bool(link_flags(routed))
