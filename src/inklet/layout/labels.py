"""Choosing where a page of labels goes -- all of them, together.

`inklet.annotate` places one label the moment it is called. It is honest about
being greedy: it walks the compass from the side you asked for until it finds
one that misses the labels already down, and the label you write last is the
one that gets shoved. That is the right trade for a rig with six callouts and
the wrong one for a field of forty, where the label placed second has no idea
that the point three millimetres north-east is about to want the same room.

This module is the other half of a loop the library already had one end of.
`fig.lint()` reports `CROWDING` and `OVERLAP` -- it knows exactly which labels
are too close, and it has known since the first round. Until now the answer was
"go and move them yourself". `place_labels` is the answer instead: it takes the
same tree, reconsiders every label against every other one at once, and hands
back a tree the same linter is quiet about. Lint finds it; layout fixes it.

    art = rig
    for part, text in LABELS:
        art = inklet.annotate(rig.find(part), text, within=art)
    art = inklet.place_labels(art)          # now decide all of them together

Nothing about it is clever. The candidate set is finite -- eight compass sides
at two clearances, so sixteen slots per label -- the pass is greedy, and the
order is the order the *targets* appear in the frame, never the order the
`annotate` calls were written in. That last choice is the point: two scripts
that label the same picture in a different order get the same picture back.

**Scope.** v1 moves point-labels with leaders and nothing else. It does not
move panels, ticks, axis labels, legends, titles or the marks themselves, and
it will not: those are laid out by the things that own them, and a placer that
second-guesses `Panel` would be fighting the layout rather than finishing it.
A label whose target it cannot find in the frame is left exactly where the
author put it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace as _replace
from typing import Mapping, Sequence

from ..core import (
    AnchorRef, Diagram, Placement, Rect, Vec2, mm, resolve,
)
from ..draw.annotate import (
    ANNOTATE_SIDES, ANNOTATION_KIND, LABEL_SPEC_NOTE, LabelSpec, annotate,
    label_slot,
)

__all__ = [
    "DEFAULT_RADII", "LabelChoice", "LabelWeights",
    "label_plan", "place_labels",
]

#: Multiples of the clearance the author asked for. Two of them, near first:
#: the second exists so a label with nowhere to go can step back rather than
#: sit on its neighbour, and it costs leader length, so it is never free.
#:
#: 2.4 was measured, not guessed. Over eight 34-label fields (the `stress/
#: label_storm.py` table and seven more from the same generator, 91 findings
#: between them before placing) the surviving `CROWDING` + `OVERLAP` +
#: `LINK_CROSSES` count was 5 at 2.0, 1 at 2.4, 2 at 2.6 and 4 at 3.0: too
#: near and a crowded label has nowhere to go, too far and it stops being
#: obvious which dot it belongs to and the leaders start tangling instead.
DEFAULT_RADII = (1.0, 2.4)

_DIRECTION = {
    "n": Vec2(0.0, -1.0), "s": Vec2(0.0, 1.0),
    "e": Vec2(1.0, 0.0), "w": Vec2(-1.0, 0.0),
    "ne": Vec2(2.0 ** -0.5, -(2.0 ** -0.5)),
    "nw": Vec2(-(2.0 ** -0.5), -(2.0 ** -0.5)),
    "se": Vec2(2.0 ** -0.5, 2.0 ** -0.5),
    "sw": Vec2(-(2.0 ** -0.5), 2.0 ** -0.5),
}
#: Which corner or edge of the label the leader arrives at, per side.
_FACING = {"n": "s", "s": "n", "e": "w", "w": "e",
           "ne": "sw", "sw": "ne", "nw": "se", "se": "nw"}

_EPS = 1e-9


@dataclass(frozen=True)
class LabelWeights:
    """What the placer is trading off, in units it can actually compare.

    Everything is converted to one number and the smallest wins, so the weights
    are the whole design. They are written as "how many millimetres of leader is
    this worth avoiding", which is the only way to read them honestly:

    * `overlap` is per square millimetre of label sitting on something -- or
      coming within the linter's clearance of it, since the candidate box is
      grown by that first. A word of small type is about 12mm^2, so half a
      label on a neighbour costs ~6 units, more than any leader this placer
      will ever draw. Collisions win, which is the whole ranking in one line.
      Growing the box by the linter's clearance rather than comparing raw
      boxes is what makes the `CROWDING` count go to zero rather than merely
      down: a slot that clears by 0.9mm is a finding, and the placer has to
      be able to see that it is one.
    * `crossing` is per leader that crosses another, or per mark a leader is
      driven through. Priced at four -- two thirds of a half-overlap -- so it
      decides a tie and never a collision. Be honest about what it bought:
      on the eight fields the other two weights were measured against it never
      changed the answer, because a slot whose leader tangles is nearly always
      a slot that also overlaps something. It is here for the case where it
      is the only term with an opinion, and `test_place_labels.py` pins one.
    * `length` is per millimetre of *visible* leader -- the gap between the
      target's silhouette and the label, not the distance between their
      centres. The same eight fields scored 1 finding at 0.3, 3 at 0.5 and 11
      at 0.8: past about half a unit per millimetre it starts buying a shorter
      leader with a real overlap, which is the wrong trade every time.
    """

    overlap: float = 1.0
    crossing: float = 4.0
    length: float = 0.3


@dataclass(frozen=True)
class LabelChoice:
    """Where one label ended up, and what it cost.

    Returned by `label_plan` so a caller can see the decision without
    rasterising anything -- and so a test can assert that a particular label
    moved, which is the only assertion about a placer worth writing.
    """

    target: str
    side: str
    clear: float
    score: float
    asked: str
    overlap: float = 0.0
    crossings: int = 0
    length: float = 0.0

    @property
    def moved(self) -> bool:
        """Whether the placer overrode the side the author asked for."""
        return self.side != self.asked


def place_labels(art: Diagram, *, sides: Sequence[str] = ANNOTATE_SIDES,
                 radii: Sequence[float] = DEFAULT_RADII,
                 weights: LabelWeights | None = None,
                 clearance: float | str | None = None) -> Diagram:
    """Re-place every `annotate` label in `art`, deciding all of them at once.

    The tree comes back the same shape, with the same frame and the same node
    ids for everything that was not a label, and with each label on whichever
    of its sixteen candidate slots scored best against the marks in the frame,
    the labels already placed in this pass, and the leaders already drawn.
    `label_plan` returns the same decision as data if you want to read it.

    Opt-in, and idempotent: `place_labels(place_labels(art)) == place_labels(art)`.
    The score never looks at the side the author requested, so replaying a
    placed tree scores the same candidates in the same order and reaches the
    same fixed point -- which is also why the placer *overrides* a requested
    side rather than preferring it. Calling it is the author saying "you
    choose". The equality is `Diagram.__eq__`'s, so it is up to node ids:
    rebuilding mints fresh ones, and the SVG of the second pass differs from
    the first in `id=` attributes and in nothing else.

    A chain holding a label whose target is not resolvable in its own frame is
    left exactly as it was -- `annotate` cannot re-place what it cannot find,
    and half-placing a figure is worse than not placing it -- and a tree with
    no `annotate` in it comes back as the very same object. Safe to call on
    anything.
    """
    options = _Options(tuple(sides), tuple(float(r) for r in radii),
                       weights or LabelWeights(), _clearance(clearance))
    return _rewrite(art, options)


def label_plan(art: Diagram, *, sides: Sequence[str] = ANNOTATE_SIDES,
               radii: Sequence[float] = DEFAULT_RADII,
               weights: LabelWeights | None = None,
               clearance: float | str | None = None) -> tuple[LabelChoice, ...]:
    """What `place_labels` would do, without doing it.

    One `LabelChoice` per label, in the order the placer decided them -- which
    is the order their targets appear in the frame, not the order the
    `annotate` calls were written. `choice.moved` says whether the author's
    requested side survived.
    """
    options = _Options(tuple(sides), tuple(float(r) for r in radii),
                       weights or LabelWeights(), _clearance(clearance))
    out: list[LabelChoice] = []
    for frame, specs in _chains(art):
        out.extend(_choose(frame, specs, options))
    return tuple(out)


# -- the decision ---------------------------------------------------------


@dataclass(frozen=True)
class _Options:
    sides: tuple[str, ...]
    radii: tuple[float, ...]
    weights: LabelWeights
    clearance: float


def _clearance(value: float | str | None) -> float:
    """How much daylight a slot has to leave, in millimetres.

    Defaults to the clearance `inklet.lint` measures against, imported at call
    time because `diagnostics` imports `draw` and this module must not turn
    that into a cycle. Aiming at the linter's own threshold is what makes the
    `CROWDING` count drop rather than merely improve: a slot that clears by
    0.9mm is a finding, and the placer has to know that to avoid it.
    """
    if value is not None:
        return mm(value)
    from ..diagnostics.rules import DEFAULT_MIN_CLEARANCE_MM

    return DEFAULT_MIN_CLEARANCE_MM


def _choose(frame: Diagram, specs: Sequence[LabelSpec],
            options: _Options) -> list[LabelChoice]:
    places = resolve(frame)
    marks = _marks(frame, places)
    order = _document_order(frame)
    ranked = sorted(range(len(specs)),
                    key=lambda i: (order.get(specs[i].target_id, len(order)), i))

    taken: list[Rect] = []
    leaders: list[tuple[Vec2, Vec2]] = []
    chosen: dict[int, LabelChoice] = {}
    for index in ranked:
        spec = specs[index]
        seat = _seat(frame, places, spec, marks, taken, leaders, options)
        if seat is None:
            continue
        choice, rect, leader = seat
        chosen[index] = choice
        taken.append(rect)
        if leader is not None:
            leaders.append(leader)
    return [chosen[i] for i in ranked if i in chosen]


def _seat(frame: Diagram, places: Mapping[str, Placement], spec: LabelSpec,
          marks: Sequence[tuple[str, Rect]], taken: Sequence[Rect],
          leaders: Sequence[tuple[Vec2, Vec2]],
          options: _Options):
    """The best of the sixteen slots for one label, or None if it has no frame.

    Candidates are walked near radius first and then in compass order, and the
    first strict minimum wins, so a tie goes to the nearer, more northerly
    slot every time.
    """
    node = (spec.target.diagram if isinstance(spec.target, AnchorRef)
            else spec.target)
    here = places.get(node.id)
    if here is None:
        return None
    own = _subtree(node)
    others = [box for ident, box in marks if ident not in own]
    blocked = others + [box for box in _avoided(spec, places)]
    through = {ident for item in spec.through for ident in _subtree(item)}
    box = here.bbox
    start = box.center if box is not None else here.point()
    reach = _reach_from(here, start)
    pad = options.clearance

    best = None
    for radius in options.radii:
        clear = spec.clear * radius
        for side in options.sides:
            if side not in _DIRECTION:
                continue
            rect = label_slot(spec.target, spec.body, side=side, clear=clear,
                              within=frame, placements=places)
            grown = rect.pad(pad)
            area = sum(_area(grown, other) for other in blocked)
            area += sum(_area(grown, other) for other in taken)
            end = _corner(rect, _FACING[side])
            span = end - start
            length = max(0.0, span.length - reach(span))
            crossings = sum(1 for a, b in leaders
                            if _crosses(start, end, a, b))
            crossings += sum(1 for ident, other in marks
                             if ident not in own and ident not in through
                             and _hits(start, end, other))
            score = (options.weights.overlap * area
                     + options.weights.crossing * crossings
                     + options.weights.length * length)
            if best is None or score < best[0] - _EPS:
                choice = LabelChoice(target=node.id, side=side, clear=clear,
                                     score=score, asked=spec.side,
                                     overlap=area, crossings=crossings,
                                     length=length)
                best = (score, choice, rect, (start, end))
    if best is None:
        return None
    return best[1], best[2], (best[3] if spec.leader else None)


def _marks(frame: Diagram, places: Mapping[str, Placement]
           ) -> list[tuple[str, Rect]]:
    """Every node in the frame that actually puts ink down, with its box.

    Leaves only: a group's box is the union of its children's and standing off
    that would push labels out of a field they belong inside.
    """
    out: list[tuple[str, Rect]] = []
    for node in frame.walk():
        if node.prim is None:
            continue
        here = places.get(node.id)
        if here is not None and here.bbox is not None:
            out.append((node.id, here.bbox))
    return out


def _document_order(frame: Diagram) -> dict[str, int]:
    """Position of each node in the frame's own pre-order walk.

    This is the placer's tie-free ordering, and it is deliberately a property
    of the *picture* rather than of the script: the label on the leftmost dot
    is decided first whether it was written first or last.
    """
    return {node.id: i for i, node in enumerate(frame.walk())}


def _avoided(spec: LabelSpec, places: Mapping[str, Placement]) -> list[Rect]:
    out: list[Rect] = []
    for item in spec.avoid:
        if isinstance(item, Rect):
            out.append(item)
            continue
        node = item.diagram if isinstance(item, AnchorRef) else item
        here = places.get(node.id)
        if here is not None and here.bbox is not None:
            out.append(here.bbox)
    return out


def _subtree(node) -> set[str]:
    inner = node.diagram if isinstance(node, AnchorRef) else node
    return {child.id for child in inner.walk()}


def _area(a: Rect, b: Rect) -> float:
    hit = a.overlap(b)
    return 0.0 if hit is None else max(hit.width, 0.0) * max(hit.height, 0.0)


def _reach_from(here: Placement, centre: Vec2):
    """How far the target reaches from its middle, towards an arbitrary point.

    The support function, not half the bounding box: for a 1.2mm dot the box
    reaches 0.85mm along the diagonal and the dot reaches 0.6mm, and the
    difference is enough to make every label on an open field prefer a corner
    over north. Subtracting it from the centre-to-label distance leaves the
    length of leader a reader actually sees.
    """
    envelope = here.envelope
    box = here.bbox

    def reach(towards: Vec2) -> float:
        if towards.length < _EPS:
            return 0.0
        unit = towards.normalized()
        value = None if envelope.is_empty else envelope.extent(unit)
        if value is None:
            if box is None:
                return 0.0
            value = (abs(unit.x) * box.width / 2.0
                     + abs(unit.y) * box.height / 2.0 + box.center.dot(unit))
        return max(0.0, value - centre.dot(unit))

    return reach


def _corner(rect: Rect, name: str) -> Vec2:
    x = rect.x0 if "w" in name else (rect.x1 if "e" in name else rect.center.x)
    y = rect.y0 if "n" in name else (rect.y1 if "s" in name else rect.center.y)
    return Vec2(x, y)


def _side_of(a: Vec2, b: Vec2, p: Vec2) -> float:
    return (b - a).cross(p - a)


def _crosses(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> bool:
    """Proper crossing of two open segments; touching at an end does not count.

    Leaders that meet at a shared endpoint are two labels on one target, which
    is a fan and not a tangle.
    """
    d1, d2 = _side_of(c, d, a), _side_of(c, d, b)
    d3, d4 = _side_of(a, b, c), _side_of(a, b, d)
    return ((d1 > _EPS) != (d2 > _EPS)) and ((d3 > _EPS) != (d4 > _EPS)) \
        and abs(d1) > _EPS and abs(d2) > _EPS \
        and abs(d3) > _EPS and abs(d4) > _EPS


def _hits(a: Vec2, b: Vec2, box: Rect) -> bool:
    """Whether the segment drives through `box` rather than merely ending in it.

    A leader ends *on* things by design -- it starts on its target's boundary
    and stops short of its own label -- so an endpoint inside a box is not a
    finding. Only a segment that goes in one side and out another is.
    """
    if box.contains(a) or box.contains(b):
        return False
    corners = box.corners
    edges = ((corners[0], corners[1]), (corners[1], corners[2]),
             (corners[2], corners[3]), (corners[3], corners[0]))
    return any(_crosses(a, b, c, d) for c, d in edges)


# -- rebuilding the tree --------------------------------------------------


def _chain(node: Diagram) -> tuple[Diagram, tuple[LabelSpec, ...]] | None:
    """Peel a stack of `annotate` wrappers down to the frame underneath.

    `annotate` returns `wrapper(inner(frame, label), leader)`, so a chain of
    them is a spine of two-deep pairs with the *last* call outermost. Walking
    it down gives the bare frame and the specs in the order they were asked
    for. Anything that is not that shape is not a chain, which is how a hand
    -built tree with an annotation buried in it still gets found by `_rewrite`.
    """
    specs: list[LabelSpec] = []
    cur = node
    while (cur.kind == ANNOTATION_KIND and LABEL_SPEC_NOTE in cur.notes
           and cur.children and cur.children[0].kind == ANNOTATION_KIND
           and len(cur.children[0].children) == 2):
        specs.append(cur.notes[LABEL_SPEC_NOTE])
        cur = cur.children[0].children[0]
    if not specs:
        return None
    specs.reverse()
    return cur, tuple(specs)


def _chains(node: Diagram):
    """Every annotation chain in the tree, outermost first, frame and specs."""
    found = _chain(node)
    if found is not None:
        yield found
        return
    for child in node.children:
        yield from _chains(child)


def _rewrite(node: Diagram, options: _Options) -> Diagram:
    found = _chain(node)
    if found is not None:
        frame, specs = found
        choices = _choose(frame, specs, options)
        if len(choices) != len(specs):
            # A spec naming a node this frame never held. Rebuilding would
            # drop that label on the floor -- `annotate` cannot place a target
            # it cannot resolve -- so the whole chain stays as the author
            # built it. Half-placing a figure is worse than not placing it.
            return node
        return _rebuild(frame, specs, choices)
    kids = tuple(_rewrite(child, options) for child in node.children)
    if all(new is old for new, old in zip(kids, node.children)):
        return node
    return _replace(node, children=kids, id=node.id, _cache={},
                    anchors=dict(node.anchors), notes=dict(node.notes))


def _rebuild(frame: Diagram, specs: Sequence[LabelSpec],
             choices: Sequence[LabelChoice]) -> Diagram:
    """Ask `annotate` again, in the order the author wrote, with better sides.

    Rebuilding rather than translating the labels in place is what keeps the
    leaders honest: a moved label needs its leader re-clipped to the target's
    real boundary and re-aimed at its own facing edge, and `annotate` is the
    one implementation of that. `search=False` is essential -- annotate's local
    walk would second-guess a decision that was made globally.
    """
    where = {choice.target: choice for choice in choices}
    art = frame
    for spec in specs:
        choice = where.get(spec.target_id)
        side = spec.side if choice is None else choice.side
        clear = spec.clear if choice is None else choice.clear
        art = annotate(spec.target, spec.body, side=side, clear=clear,
                       within=art, leader=spec.leader, head=spec.head,
                       shoulder=spec.shoulder, avoid=spec.avoid,
                       through=spec.through, leader_style=spec.leader_style,
                       name=spec.name, search=False)
    return art
