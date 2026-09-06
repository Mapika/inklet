"""Saying what a thing is: labels that clear it, brackets, dimensions, letters.

Everything here answers the same question -- *where does the writing go?* -- and
it is the question a figure generator gets wrong most often, because the answer
depends on the finished geometry of something else. A label 2mm north of a
rotated ellipse is not 2mm north of its bounding box; a leader that stops at a
box is wrong when the box is a micrograph with a cut-out silhouette; a panel
letter tucked into the top-left corner lands on the y-axis label that is
already there.

So none of these take a coordinate. They take the thing being named, ask its
envelope how far it reaches in the direction the writing is going, and put the
writing just past that -- and, for a leader, ask its *trace* where a ray leaves
its real boundary, which is what makes the line touch the silhouette of a
cut-out and the curve of an ellipse rather than the corner of a box.

    rig = inklet.scene(parts, width=60)
    art = inklet.annotate(rig.find("objective"), "objective", side="e", clear=2.6)

`annotate` returns a diagram holding the target, the label and the leader
between them, so the annotation travels as one object. That is deliberate, and
it is the one place in `inklet` where a connector is not deferred to `Figure`:
a leader's endpoints depend only on the target and its own label, both of which
are settled the moment the label is placed, so there is nothing left for the
page to contribute. `fig.link` stays for the connections the page *does* decide.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable, Mapping, Sequence

from ..core import (
    AnchorRef, Diagram, DiagramError, Placement, Rect, Vec2, mm, resolve,
)
from ..links import link as make_link, route
from ..typeset import shape
from .coords import (ORIGIN_ANCHOR, Point, active_theme, drawn_group,
                     needs_diagram, plot_area, to_point)
from .path import polygon, polyline

__all__ = [
    "ANNOTATION_KIND", "ANNOTATION_LABEL_KIND", "BRACKET_KIND",
    "DIMENSION_KIND", "LABEL_SPEC_NOTE", "LETTER_KIND", "LETTER_STYLES",
    "SCALEBAR_KIND", "ANNOTATE_SIDES", "LabelSpec",
    "annotate", "annotation_side", "bracket", "dimension", "label_slot",
    "label_specs", "letters", "scalebar",
]

_EPS = 1e-9

#: Compass points, clockwise from north. `annotate` walks outward from the
#: requested one when it collides, so the order is load-bearing.
ANNOTATE_SIDES = ("n", "ne", "e", "se", "s", "sw", "w", "nw")

_DIRECTION = {
    "n": Vec2(0.0, -1.0), "s": Vec2(0.0, 1.0),
    "e": Vec2(1.0, 0.0), "w": Vec2(-1.0, 0.0),
    "ne": Vec2(2.0 ** -0.5, -(2.0 ** -0.5)), "nw": Vec2(-(2.0 ** -0.5), -(2.0 ** -0.5)),
    "se": Vec2(2.0 ** -0.5, 2.0 ** -0.5), "sw": Vec2(-(2.0 ** -0.5), 2.0 ** -0.5),
}
_OPPOSITE = {"n": "s", "s": "n", "e": "w", "w": "e",
             "ne": "sw", "sw": "ne", "nw": "se", "se": "nw"}

ANNOTATION_KIND = "annotation"
ANNOTATION_LABEL_KIND = "annotation-label"
BRACKET_KIND = "bracket"
DIMENSION_KIND = "dimension"
SCALEBAR_KIND = "scalebar"
#: A panel letter's own kind. It was `"title"` until round 7, so that the
#: theme's `panel-title` role would style it -- at the cost that nothing could
#: tell a letter from a `p.title(...)`: `[n for n in page.walk() if n.kind ==
#: "title"]` returned both, which cost round 6 a wrong measurement before the
#: count gave it away. The letter now carries that role's face on itself
#: (`_letter_node`) and keeps a kind of its own, and the two are selectable
#: apart. Not a pixel moved: the group's `font-family`, `font-size` and
#: `font-weight` come out identical, and the only byte that changed in the
#: corpus was the `id=` prefix, which is minted from the kind.
LETTER_KIND = "letter"

#: Marks the side a label actually ended up on, appended to the annotation's
#: name. `inklet.links` marks a degenerate connector the same way, for the same
#: reason: a caller that has to know can read it off the tree.
SIDE_SEP = "!"

#: Below this the leader would be a stub shorter than the gap it spans, which
#: reads as a speck of dirt rather than as a line. The label is close enough to
#: be unambiguous without one.
_MIN_LEADER = 0.6

#: How far short of the label the leader stops. A line that touches its label
#: reads as part of the drawing rather than as pointing at it -- the same gap
#: `figures/annot.py` had to leave by hand.
_LABEL_GAP = 0.6

#: The anchor `annotate` puts on a placed label for its leader to aim at.
_LEADER_ANCHOR = "leader"

LETTER_STYLES = ("bold-lower", "lower", "upper", "bold-upper", "paren")

#: Key under which `annotate` records what it was asked for, on the wrapper it
#: returns. `inklet.place_labels` reads it back.
LABEL_SPEC_NOTE = "label_spec"


@dataclass(frozen=True)
class LabelSpec:
    """Everything `annotate` was asked for, kept so the call can be repeated.

    `annotate` places one label the moment it is called and bakes the answer
    into the tree; nothing downstream can move it, because the arguments that
    produced it are gone. A placer that wants to reconsider a page of labels
    together has to have them, so every `annotate` result carries its own spec
    under `LABEL_SPEC_NOTE` and `inklet.place_labels` peels the chain apart and
    builds it again with better sides. The body is the *built* label rather
    than the string it came from, so replaying costs no shaping and a label
    passed in as a diagram replays as itself.

    `side` and `clear` are what the author asked for, not what they got --
    `annotation_side` is still the answer to the second question.
    """

    target: "Diagram | AnchorRef"
    body: Diagram
    side: str = "n"
    clear: float = 2.0
    leader: bool = True
    head: str = "none"
    shoulder: float | str | None = None
    avoid: tuple = ()
    through: tuple = ()
    leader_style: dict | None = None
    name: str | None = None
    #: Excluded from equality for the same reason `Diagram.id` is: two specs
    #: asking for the same label of the same target are the same request.
    within_id: str | None = field(default=None, compare=False)

    @property
    def target_id(self) -> str:
        node = (self.target.diagram if isinstance(self.target, AnchorRef)
                else self.target)
        return node.id

    def asking(self, side: str, clear: float) -> "LabelSpec":
        """The same request, aimed at a different side and clearance."""
        return replace(self, side=side, clear=clear)


def label_specs(node: Diagram) -> tuple[LabelSpec, ...]:
    """Every `annotate` request recorded anywhere in `node`, in call order.

    Reading order is `walk()`'s, which is the order the tree was built in for a
    chain of `annotate` calls -- the outermost wrapper is the *last* call, so
    the tuple comes back reversed into the order the author wrote.
    """
    found = [n.notes[LABEL_SPEC_NOTE] for n in node.walk()
             if LABEL_SPEC_NOTE in n.notes]
    return tuple(reversed(found))


# -- a label that clears its target ---------------------------------------


def annotate(target: Diagram | AnchorRef, text: str | Diagram, *,
             side: str = "n", clear: float | str = 2.0, leader: bool = True,
             avoid: Sequence[Diagram | Rect] = (),
             within: Diagram | None = None, size: float | str | None = None,
             align: str = "center", name: str | None = None,
             head: str = "none", shoulder: float | str | None = None,
             through: Sequence[Diagram] = (),
             leader_style: dict | None = None, search: bool = True,
             **style) -> Diagram:
    """Put `text` outside `target`, `clear` millimetres off it, with a leader.

    The clearance is measured against the target's *envelope*, not its box, so
    a label north-east of a rotated ellipse sits 2mm off the curve rather than
    2mm off an empty corner. The leader is a `kind="leader"` link, so it stops
    on the target's real boundary -- the silhouette of a cut-out image, the
    outline of a projected mesh part, the round of a rounded rectangle.

    `target` may be any Diagram, including a part of a `inklet.model` or
    `inklet.scene` found with `.find()`, or an `AnchorRef` naming an exact spot.
    Annotating a part rather than a whole needs the frame it lives in: pass it
    as `within`, and the result wraps *that*. Chaining is how a rig gets a
    dozen labels, each new call seeing where the last one went:

        art = rig
        for part, text, side in LABELS:
            art = inklet.annotate(rig.find(part), text, side=side, within=art)

    `avoid` names diagrams the label must miss. Labels already placed by
    `annotate` inside `within` are avoided without being asked, since a label
    on a label is never what anyone meant. When the requested side is blocked
    the search walks outward around the compass -- n, ne, nw, e, w, ... -- and
    the side it settled on is appended to the result's name after a `!`, which
    `annotation_side` reads back.

    `through` names shapes the leader is *meant* to cross. A callout into a
    buried pocket has to cross the assembly in front of it, and without this
    the only way to say so is `inklet.abutting` round the leader and the model,
    which also stops the label at the far end being measured against the thing
    it is naming. This is the narrow claim and only the narrow claim: the two
    crossing rules skip the leader against those shapes, and every other rule
    goes on exactly as before. See `inklet.crossing`, which is what it calls.

    `search=False` takes `side` as final and skips the walk. It exists for
    `inklet.place_labels`, which weighs all eight sides of every label on the page
    against each other before calling this at all; letting the local search
    then move one of them would quietly undo the global decision.
    """
    node = (target.diagram if isinstance(target, AnchorRef)
            else needs_diagram("annotate", target,
                               "the diagram being labelled"))
    root = node if within is None else within
    if side not in _DIRECTION:
        raise ValueError(
            f"unknown side {side!r}; expected one of {', '.join(ANNOTATE_SIDES)}"
        )
    gap = mm(clear)
    placements = resolve(root)
    here = placements.get(node.id)
    if here is None:
        raise DiagramError(
            f"{node.id} is not inside the frame being annotated; pass the "
            "diagram that contains it as within="
        )

    body = text if isinstance(text, Diagram) else _text(text, size, align, style)
    if isinstance(text, Diagram) and style:
        body = body.styled(**style)
    if name is not None:
        body = body.named(f"{name}-label")

    reach, centre = _reach_of(here, target)
    blockers = ((_blockers(avoid, placements) + _placed_labels(root, placements))
                if search else [])
    chosen, at = _pick_side(side, body, reach, centre, gap, blockers,
                            search=search)

    offset = at - body.bbox.center
    placed = Diagram(children=(body.translated(offset.x, offset.y),),
                     kind=ANNOTATION_LABEL_KIND)
    facing = placed.anchor_point(_OPPOSITE[chosen]) - _DIRECTION[chosen] * _LABEL_GAP
    placed.anchor(_LEADER_ANCHOR, facing)
    inner = Diagram(children=(root, placed), kind=ANNOTATION_KIND)
    parts: tuple[Diagram, ...] = (inner,)

    if leader:
        drawn = _leader(target, placed, chosen, head, shoulder, leader_style,
                        inner)
        if drawn is not None:
            # On the routed leader rather than on the wrapper: the wrapper also
            # holds the label, and a declaration there would be read as the
            # label's too by anything that walks up a chain. Imported here
            # because `diagnostics` imports `draw` -- the linter measures what
            # this module draws, so the dependency only runs one way at import
            # time and the other way at call time.
            if through:
                from ..diagnostics.cross import crossing

                drawn = crossing(drawn, *through)
            parts = (inner, drawn)

    out = Diagram(children=parts, kind=ANNOTATION_KIND,
                  name=f"{name or 'annotate'}{SIDE_SEP}{chosen}")
    # What was asked for, so `inklet.place_labels` can ask again with a better
    # side. A note is invisible to every measurement and to the renderer, so
    # recording it moves no bytes.
    out.note(LABEL_SPEC_NOTE, LabelSpec(
        target=target, body=body, side=side, clear=gap, leader=leader,
        head=head, shoulder=shoulder, avoid=tuple(avoid),
        through=tuple(through), leader_style=leader_style, name=name,
        within_id=None if within is None else within.id,
    ))
    return _keep_origin(out, root)


def annotation_side(node: Diagram | str) -> str | None:
    """Which side an `annotate` label actually landed on.

    The requested side is only a request -- a blocked one is moved. Reading it
    back is how a caller checks that the figure it asked for is the figure it
    got, without rasterising anything.
    """
    name = node if isinstance(node, str) else node.name
    if not name or SIDE_SEP not in name:
        return None
    tail = name.rsplit(SIDE_SEP, 1)[1]
    return tail if tail in _DIRECTION else None


def label_slot(target: Diagram | AnchorRef, body: Diagram, *,
               side: str = "n", clear: float | str = 2.0,
               within: Diagram | None = None,
               placements: Mapping[str, Placement] | None = None) -> Rect:
    """The rectangle `annotate` would put this label in, without building it.

    Where a label goes is geometry, and a placer weighing eight sides of forty
    labels should not have to build three hundred diagrams to find out. This
    is the same answer `annotate(target, body, side=side, clear=clear)` gives
    -- measured off the target's *envelope*, so a north-east slot clears the
    curve rather than an empty corner -- for the price of one support query.

    Pass `placements` when you already have `resolve(frame)` in hand; the
    frame is `within` if given and the target itself otherwise.
    """
    node = (target.diagram if isinstance(target, AnchorRef)
            else needs_diagram("label_slot", target, "the diagram being labelled"))
    if side not in _DIRECTION:
        raise ValueError(
            f"unknown side {side!r}; expected one of {', '.join(ANNOTATE_SIDES)}"
        )
    places = (resolve(node if within is None else within)
              if placements is None else placements)
    here = places.get(node.id)
    if here is None:
        raise DiagramError(
            f"{node.id} is not inside the frame being measured; pass the "
            "diagram that contains it as within="
        )
    reach, centre = _reach_of(here, target)
    at = _label_centre(body, reach, centre, mm(clear), _DIRECTION[side])
    return Rect.from_size(body.width, body.height, at)


def _text(content: str, size: float | str | None, align: str,
          style: dict) -> Diagram:
    theme = active_theme()
    prim = shape(content, font=theme.font_family,
                 size=theme.font_size_small if size is None else mm(size),
                 align=align, line_height=theme.line_height)
    node = Diagram(prim=prim, kind="label")
    return node.styled(**style) if style else node


def _reach_of(here: Placement, target: Diagram | AnchorRef):
    """How far the target reaches in each direction, and where its middle is.

    A support function, so the clearance is off the silhouette. An `AnchorRef`
    is a point and reaches nowhere, which is the honest answer: the author
    named that exact spot and the label should clear the spot, not the shape.
    """
    if isinstance(target, AnchorRef):
        point = here.point(target.name)
        return (lambda d: point.dot(d)), point
    envelope = here.envelope
    box = here.bbox
    if box is None or envelope.is_empty:
        point = here.point()
        return (lambda d: point.dot(d)), point

    def reach(direction: Vec2) -> float:
        value = envelope.extent(direction)
        return box.center.dot(direction) if value is None else value

    return reach, box.center


def _pick_side(side: str, body: Diagram, reach, centre: Vec2, gap: float,
               blockers: Sequence[Rect], *,
               search: bool = True) -> tuple[str, Vec2]:
    """The first candidate side that is clear, or the least blocked of them.

    `search=False` turns the walk off and takes the requested side as given:
    `inklet.place_labels` has already weighed all eight against every other label
    on the page, and a second, local opinion here would undo it.
    """
    best: tuple[float, str, Vec2] | None = None
    for candidate in (_side_order(side) if search else (side,)):
        direction = _DIRECTION[candidate]
        at = _label_centre(body, reach, centre, gap, direction)
        spot = Rect.from_size(body.width, body.height, at)
        blocked = sum(_overlap_area(spot, other) for other in blockers)
        if blocked <= 0.0:
            return candidate, at
        if best is None or blocked < best[0]:
            best = (blocked, candidate, at)
    return best[1], best[2]


def _side_order(side: str) -> list[str]:
    """The requested side, then its neighbours, alternating out to the far side.

    Deterministic and symmetric: a blocked north tries north-east before
    north-west every time, so the same figure comes out the same way twice.
    """
    start = ANNOTATE_SIDES.index(side)
    order = [side]
    for step in range(1, 5):
        order.append(ANNOTATE_SIDES[(start + step) % 8])
        if step < 4:
            order.append(ANNOTATE_SIDES[(start - step) % 8])
    return order


def _label_centre(body: Diagram, reach, centre: Vec2, gap: float,
                  direction: Vec2) -> Vec2:
    """Where the label's centre goes so its near edge clears by `gap`.

    Solved on the support function of both shapes rather than on their boxes,
    which is the only way a diagonal clearance means what it says.
    """
    local = body.bbox.center
    back = body.extent(-direction) - local.dot(-direction)
    along = reach(direction) + gap + back - centre.dot(direction)
    return centre + direction * along


def _leader(target: Diagram | AnchorRef, placed: Diagram, side: str,
            head: str, shoulder: float | str | None,
            leader_style: dict | None, inner: Diagram) -> Diagram | None:
    """The line from the label back to the target's boundary, or None.

    Routed here rather than deferred to `Figure`, because both ends are already
    settled: the label is where this call put it and the target's trace is
    whatever it is. The link aims a hair short of the label's *facing* edge, so
    the line arrives at the side nearest the target and stops before touching
    the type.
    """
    spec = make_link(target, placed.at(_LEADER_ANCHOR), kind="leader",
                     head=head, shoulder=shoulder,
                     **(leader_style or {}))
    routed = route(spec, resolve(inner))
    span = routed.anchor_point("end") - routed.anchor_point("start")
    return None if span.length < _MIN_LEADER else routed


def _blockers(avoid: Sequence[Diagram | Rect],
              placements: dict[str, Placement]) -> list[Rect]:
    boxes: list[Rect] = []
    for item in avoid:
        if isinstance(item, Rect):
            boxes.append(item)
            continue
        node = item.diagram if isinstance(item, AnchorRef) else item
        here = placements.get(node.id)
        box = here.bbox if here is not None else _own_box(node)
        if box is not None:
            boxes.append(box)
    return boxes


def _own_box(node: Diagram) -> Rect | None:
    try:
        return node.bbox
    except DiagramError:
        return None


def _placed_labels(root: Diagram,
                   placements: dict[str, Placement]) -> list[Rect]:
    """Every label a previous `annotate` put in this frame."""
    boxes = []
    for node in root.walk():
        if node.kind != ANNOTATION_LABEL_KIND:
            continue
        here = placements.get(node.id)
        if here is not None and here.bbox is not None:
            boxes.append(here.bbox)
    return boxes


def _overlap_area(a: Rect, b: Rect) -> float:
    hit = a.overlap(b)
    return 0.0 if hit is None else max(hit.width, 0.0) * max(hit.height, 0.0)


def _keep_origin(out: Diagram, root: Diagram) -> Diagram:
    """Carry a drawn frame's `origin` anchor through the wrapper.

    Without it `Panel.draw` and `place` would stop being able to put an
    annotated group back in the coordinates it was drawn in, which is the whole
    contract of `inklet.draw`.
    """
    if ORIGIN_ANCHOR not in root.anchors:
        return out
    return out.anchor(ORIGIN_ANCHOR,
                      root.transform.apply(root.anchors[ORIGIN_ANCHOR]))


# -- brackets and dimensions ----------------------------------------------


def bracket(a, b, *, side: str = "n", text: str | Diagram | None = None,
            tick: float | str = 1.0, clear: float | str = 0.0,
            pad: float | str | None = None, size: float | str | None = None,
            within: Diagram | None = None, kind: str = BRACKET_KIND,
            **style) -> Diagram:
    """The grouping bracket over two things, with `text` centred on it.

    The significance bar over a pair of bars, the brace naming three panels as
    one condition: a flat span with a tick turned toward the things it covers
    at each end. `side` says which way it faces -- "n" sits above and its ticks
    point down.

    `a` and `b` are points in millimetres, or diagrams sharing one frame (pass
    that frame as `within` when they are nested inside it), in which case the
    span runs between their facing edges rather than their centres.

    The result is drawn in the coordinates it was given, so `inklet.place` and
    `Panel.draw` put it back there. In a panel, `Panel.bracket(x0, x1, y)`
    speaks data instead.
    """
    if side not in ("n", "s", "e", "w"):
        raise ValueError(f"bracket side must be n, s, e or w, not {side!r}")
    theme = active_theme()
    gap = theme.gap("2xs") if pad is None else mm(pad)
    reach, drop = mm(tick), mm(clear)
    placements = None if within is None else resolve(within)
    pa = _corner_point(a, side, placements)
    pb = _corner_point(b, side, placements)

    if side in ("n", "s"):
        lo, hi = min(pa.x, pb.x), max(pa.x, pb.x)
        turn = -1.0 if side == "n" else 1.0
        bar = min(pa.y, pb.y) - drop if side == "n" else max(pa.y, pb.y) + drop
        spine = ((lo, bar - turn * reach), (lo, bar), (hi, bar),
                 (hi, bar - turn * reach))
        anchor = Vec2((lo + hi) / 2.0, bar)
    else:
        lo, hi = min(pa.y, pb.y), max(pa.y, pb.y)
        turn = -1.0 if side == "w" else 1.0
        bar = min(pa.x, pb.x) - drop if side == "w" else max(pa.x, pb.x) + drop
        spine = ((bar - turn * reach, lo), (bar, lo), (bar, hi),
                 (bar - turn * reach, hi))
        anchor = Vec2(bar, (lo + hi) / 2.0)

    parts = [polyline(spine, kind=kind, **style)]
    if text is not None:
        body = text if isinstance(text, Diagram) else _text(text, size, "center", {})
        away = _DIRECTION[side]
        centre = anchor + away * (gap + _half(body, away))
        parts.append(body.translated(centre.x - body.bbox.center.x,
                                     centre.y - body.bbox.center.y))
    return drawn_group([_at_origin(p) for p in parts], kind)


def dimension(a, b, text: str | Diagram | None = None, *,
              offset: float | str = 0.0, tick: float | str = 1.2,
              witness: bool = True, plate: bool = True,
              size: float | str | None = None, within: Diagram | None = None,
              kind: str = DIMENSION_KIND, **style) -> Diagram:
    """A dimension line from `a` to `b`, ticked at both ends and labelled.

    Drafting convention, because it is the one a reader already knows: the
    measurement is written *on* the line, on a plate that breaks it, rather
    than floating above one end where it could belong to either dimension. The
    ticks cross the line so the extent is unambiguous where two dimensions meet
    end to end.

    `offset` moves the line off the thing measured, along the left-hand normal
    of a-to-b; witness lines then join the two, the way a drawing does it. `a`
    and `b` are points in millimetres or diagrams in one frame, as in
    `bracket`.
    """
    theme = active_theme()
    placements = None if within is None else resolve(within)
    pa = _plain_point(a, placements)
    pb = _plain_point(b, placements)
    span = pb - pa
    if span.length <= _EPS:
        raise ValueError("a dimension needs two distinct points")
    along = span.normalized()
    normal = Vec2(-along.y, along.x)
    shift = normal * mm(offset)
    qa, qb = pa + shift, pb + shift
    arm = normal * (mm(tick) / 2.0)

    parts = [polyline((qa, qb), kind=kind, **style),
             polyline((qa - arm, qa + arm), kind=kind, **style),
             polyline((qb - arm, qb + arm), kind=kind, **style)]
    if witness and mm(offset) != 0.0:
        over = normal * (mm(offset) + _sign(mm(offset)) * mm(tick) / 2.0)
        parts.append(polyline((pa, pa + over), kind=kind,
                              **({'stroke_width':theme.hairline} | style)))
        parts.append(polyline((pb, pb + over), kind=kind,
                              **({'stroke_width':theme.hairline} | style)))
    if text is not None:
        body = text if isinstance(text, Diagram) else _text(text, size, "center", {})
        if plate:
            body = _plated(body, theme)
        middle = (qa + qb) * 0.5
        parts.append(body.translated(middle.x - body.bbox.center.x,
                                     middle.y - body.bbox.center.y))
    return drawn_group([_at_origin(p) for p in parts], kind)


def _plated(body: Diagram, theme) -> Diagram:
    """The label on an opaque tile, so the line reads as broken under it."""
    from ..layout import frame as make_frame

    return make_frame(body, pad=theme.gap("2xs"), kind="label-plate").styled(
        fill=theme.paper, stroke="none")


# -- scale bars -----------------------------------------------------------


def scalebar(length: float, text: str | Diagram | None = None, *,
             panel=None, over: Diagram | None = None, corner: str = "sw",
             pad: float | str | None = None,
             thickness: float | str | None = None,
             plate: bool | None = None, axis: str = "x",
             ink: str | None = None, kind: str = SCALEBAR_KIND,
             **style) -> Diagram:
    """A scale bar, with its length written under it.

    `length` is millimetres on the page unless `panel=` is given, in which case
    it is a distance in that panel's data and is measured through the scale --
    so "10 µm" on a log axis is as long as 10 µm actually is at that end of it.

    Give `over=` an image and the bar is placed in that image's corner and
    returned drawn over it, on a plate. The plate is not decoration: paper-white
    type straight onto a dark micrograph is the journal standard *and* is
    currently reported as `LOW_CONTRAST`, because the contrast rule cannot see
    an image underneath. Pass `plate=False` and set `ink=` yourself when that
    is fixed, or when the micrograph is pale.

    With `panel=` and no `over=`, the bar comes back in panel coordinates for
    `Panel.over(...)` to paint on top.
    """
    theme = active_theme()
    gap = theme.gap("s") if pad is None else mm(pad)
    tall = theme.thick * 1.6 if thickness is None else mm(thickness)
    long = _bar_length(length, panel, axis)
    colour = theme.ink if ink is None else ink

    bar = polygon(((-long / 2.0, -tall / 2.0), (long / 2.0, -tall / 2.0),
                   (long / 2.0, tall / 2.0), (-long / 2.0, tall / 2.0)),
                  kind=kind, fill=colour, stroke="none", **style)
    stack: list[Diagram] = [bar]
    if text is not None:
        body = text if isinstance(text, Diagram) else _text(text, None, "center",
                                                            {"text_fill": colour})
        lift = tall / 2.0 + theme.gap("xs") + body.height / 2.0
        stack.append(body.translated(-body.bbox.center.x,
                                     -body.bbox.center.y - lift))
    group = drawn_group([_at_origin(item) for item in stack], kind)
    if plate is None:
        plate = over is not None
    if plate:
        group = _plated(group, theme)

    box = _corner_frame(panel, over)
    if box is None:
        return group
    placed = _into_corner(group, box, corner, gap)
    return placed if over is None else Diagram(children=(over, placed),
                                               kind=kind)


def _bar_length(length: float, panel, axis: str) -> float:
    if panel is None:
        return mm(length)
    scale = panel.x if axis == "x" else panel.y
    lo = scale.domain[0]
    return abs(scale.map(lo + length) - scale.map(lo))


def _corner_frame(panel, over: Diagram | None) -> Rect | None:
    if over is not None:
        return _own_box(over)
    return None if panel is None else panel.area


def _into_corner(node: Diagram, box: Rect, corner: str, pad: float) -> Diagram:
    if corner not in ("nw", "ne", "sw", "se"):
        raise ValueError(f"corner must be nw, ne, sw or se, not {corner!r}")
    here = node.bbox
    x = (box.x0 + pad + here.width / 2.0 if corner[1] == "w"
         else box.x1 - pad - here.width / 2.0)
    y = (box.y0 + pad + here.height / 2.0 if corner[0] == "n"
         else box.y1 - pad - here.height / 2.0)
    return node.translated(x - here.center.x, y - here.center.y)


# -- panel letters --------------------------------------------------------


def letters(items: Iterable, *, start: str = "a", style: str = "bold-lower",
            corner: str = "nw", pad: float | str | None = None,
            inside: bool = False, size: float | str | None = None,
            **text_style) -> list[Diagram]:
    """`a`, `b`, `c` on the corner of each item, as diagrams you can stack.

    Each item comes back wrapped, not rewritten: the group holds the very
    object you passed, so a handle kept for `fig.link` still resolves and the
    result drops straight into `row`, `column` or `grid`.

    The letter sits **outside** the item's box by default. A y-axis label
    reaches the top-left corner of every panel that has one, and a letter
    tucked in on top of it is the one collision a multi-panel figure always
    has; `inside=True` when the corner really is empty.

    `style` is one of "bold-lower" (the default: **a**), "lower", "upper",
    "bold-upper" or "paren" -- (a) -- which is the other house style.
    `Panel` objects are built for you, so a list of panels goes in directly.

    A built `Panel` says where its plot area is, and the letter hangs off the
    top of *that*, not off the top of the box: the box grows with a legend or a
    title and the area does not, and the area is the line `column`, `row` and
    `facets` line panels up on. So `inklet.facets(inklet.letters(panels), cols=2)`
    puts every letter on one line even where one panel carries a legend over it
    and its neighbour does not. Anything that is not a panel is lettered off
    its box as before; for a hand-built row of those, `align="top"` is what
    makes the tops agree.
    """
    if style not in LETTER_STYLES:
        raise ValueError(
            f"unknown letter style {style!r}; expected one of "
            f"{', '.join(LETTER_STYLES)}"
        )
    theme = active_theme()
    gap = theme.gap("s") if pad is None else mm(pad)
    if isinstance(items, Diagram) or not hasattr(items, "__iter__"):
        raise TypeError(
            "letters() takes the panels to letter, as a list -- "
            "inklet.letters([a, b, c]) -- not "
            f"{type(items).__name__} ({items!r})"
        )
    out: list[Diagram] = []
    for index, item in enumerate(items):
        node = item.build() if hasattr(item, "build") else item
        mark = _letter_node(_letter_text(start, index, style), style, size,
                            text_style)
        out.append(_tagged(node, mark, corner, gap, inside))
    return out


def _letter_text(start: str, index: int, style: str) -> str:
    base = chr(ord(start) + index)
    if style in ("upper", "bold-upper"):
        base = base.upper()
    return f"({base})" if style == "paren" else base


def _letter_node(content: str, style: str, size: float | str | None,
                 text_style: dict) -> Diagram:
    """The letter itself, wearing the theme's panel-title face.

    Bold and large still come from the theme rather than from numbers here,
    which is what keeps the letters on one page agreeing with each other and
    with the panel titles beside them -- but they are now read off
    `style_for("panel-title")` and written onto the node, rather than arriving
    because the node claimed to *be* a title. See `LETTER_KIND`. `font_size`
    and `font_family` are restated for the same reason: without them the group
    would stop carrying them and the renderer would move them onto the `<text>`
    element instead, which is the same picture spelled differently.
    """
    theme = active_theme()
    face = theme.style_for("panel-title")
    weight = face.font_weight if style.startswith("bold") else "normal"
    node = _text(content, theme.font_size_large if size is None else size,
                 "center", {"font_family": face.font_family,
                            "font_size": (theme.font_size_large if size is None
                                          else mm(size)),
                            "font_weight": weight, **text_style})
    return Diagram(prim=node.prim, kind=LETTER_KIND,
                   style=node.style)


def _tagged(node: Diagram, mark: Diagram, corner: str, pad: float,
            inside: bool) -> Diagram:
    if corner not in ("nw", "ne", "sw", "se"):
        raise ValueError(f"corner must be nw, ne, sw or se, not {corner!r}")
    box = node.bbox
    # A built `Panel` records its plot area (plot's `plot_area` note), and for
    # a *row* of panels that rectangle is the only line they all agree on:
    # `column`, `row` and `facets` align plot areas, not boxes, so a panel with
    # a legend over it has a taller box than the one beside it and its letter
    # used to ride 4.9mm higher. Two letters on two lines is the first thing a
    # reader notices about a multi-panel figure. Height comes from the area;
    # the sideways edge still comes from the box, because a y-axis label
    # reaches the box's west edge and the letter has to clear it. `inside=True`
    # asks for the corner of the data region, so there both come from the area.
    area = _plot_area(node)
    down = area if area is not None else box
    across = area if (area is not None and inside) else box
    here = mark.bbox
    sign_x = -1.0 if corner[1] == "w" else 1.0
    sign_y = -1.0 if corner[0] == "n" else 1.0
    edge_x = across.x0 if corner[1] == "w" else across.x1
    edge_y = down.y0 if corner[0] == "n" else down.y1
    if inside:
        x = edge_x - sign_x * (pad + here.width / 2.0)
        y = edge_y - sign_y * (pad + here.height / 2.0)
    else:
        x = edge_x + sign_x * (pad + here.width / 2.0)
        y = edge_y + sign_y * here.height / 2.0
    placed = mark.translated(x - here.center.x, y - here.center.y)
    out = Diagram(children=(node, placed), kind="tagged")
    out = _keep_origin(out, node)
    return _carry(out, node)


#: Notes a two-child wrapper must not inherit: they index `node.children` by
#: position, and this wrapper's children are (item, letter).
CHILD_INDEXED_NOTES = ("grid_cells",)


def _carry(out: Diagram, node: Diagram) -> Diagram:
    """The item's notes, on the wrapper `letters` put round it and its letter.

    Core's `carry_notes` is the one implementation and it is written for a
    wrapper round *one* child; this wrapper has two, and that difference shows
    up in exactly one place. A note that describes the item's geometry is as
    true of the wrapper, which adds no transform of its own -- `plot_area` is
    the one the library ships, and passing it on is what lets `facets` line a
    row of lettered panels up on their data regions and a second `letters` pass
    see the same rectangle the panel declared, instead of the box the letter
    has just changed the shape of. A note that indexes children by *position*
    is not: `grid_cells` is "one (row, col) per child, in `node.children`
    order", and `diagnostics.rules._grid_cell` looks it up by slot, so copied
    onto (item, letter) it reads the letter as the item's next-door cell and
    forgives a genuinely crowded pair. So the carry is `carry_notes` less the
    positional keys, rather than the hand-written single-note copy that stood
    here -- which computed the same rectangle but dropped `gap`, `col_gap`,
    `row_gap` and `grid_shape` from a lettered `row`, `column` or `grid`.
    """
    if not hasattr(out, "carry_notes"):                  # pragma: no cover
        return out                                       # pre-M19 core
    out = out.carry_notes(node)
    for key in CHILD_INDEXED_NOTES:
        out.notes.pop(key, None)
    return out


def _plot_area(node: Diagram) -> Rect | None:
    """The plot area of a built `Panel` -- or of a `row`/`column`/`facets`
    group of them, whose note is the union of its members' -- in the frame
    `node.bbox` is in. `coords.plot_area` is the one implementation; this name
    stays because the frame question it answers is the whole reason `_tagged`
    reads a note rather than the box (see `coords.plot_area`'s docstring)."""
    return plot_area(node)


# -- shared helpers -------------------------------------------------------


def _at_origin(node: Diagram) -> Diagram:
    """Undo `inklet.draw`'s recentring so several shapes share one frame."""
    from .coords import as_drawn

    return as_drawn(node)


def _half(node: Diagram, direction: Vec2) -> float:
    box = node.bbox
    return abs(direction.x) * box.width / 2.0 + abs(direction.y) * box.height / 2.0


def _sign(value: float) -> float:
    return 1.0 if value >= 0.0 else -1.0


def _plain_point(item, placements) -> Vec2:
    """A point, a diagram's centre, or an anchor, in one shared frame."""
    if isinstance(item, (Diagram, AnchorRef)):
        return _box_of(item, placements)[1]
    return to_point(item)


def _corner_point(item, side: str, placements) -> Vec2:
    """Where a bracket's end sits: the facing edge of a diagram, or the point."""
    if not isinstance(item, (Diagram, AnchorRef)):
        return to_point(item)
    box, centre = _box_of(item, placements)
    if box is None:
        return centre
    if side == "n":
        return Vec2(box.center.x, box.y0)
    if side == "s":
        return Vec2(box.center.x, box.y1)
    if side == "w":
        return Vec2(box.x0, box.center.y)
    return Vec2(box.x1, box.center.y)


def _box_of(item, placements) -> tuple[Rect | None, Vec2]:
    node = item.diagram if isinstance(item, AnchorRef) else item
    if placements is not None and node.id in placements:
        here = placements[node.id]
        if isinstance(item, AnchorRef):
            point = here.point(item.name)
            return None, point
        return here.bbox, (here.bbox.center if here.bbox is not None
                           else here.point())
    if isinstance(item, AnchorRef):
        point = node.transform.apply(node.anchor_point(item.name))
        return None, point
    box = _own_box(node)
    return box, (Vec2(0.0, 0.0) if box is None else box.center)
