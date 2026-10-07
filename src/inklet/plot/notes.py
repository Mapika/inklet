"""Writing on a plot, in the plot's own units.

Everything here takes data coordinates. That is the whole point: the three
things an author reaches for after the data is drawn -- a word next to a point,
an arrow from one place to another, a callout on a peak -- are the three places
where a plotting API usually hands back millimetres and lets the author do the
arithmetic. `Panel.over()` says at length why that goes wrong.

None of it is new geometry. `Panel.text` is `draw.place` with the point mapped,
`Panel.arrow` is a `inklet.links` connector between two anchors, and
`Panel.annotate` is `inklet.annotate` with an invisible target sitting on the
datum. What this module contributes is the mapping and, for the callout, one
decision worth stating: **the label is kept inside the plot area by default.**
A peak near the top of a panel is exactly where an outward-searching label
wants to go over the spine, and a caption floating above the axis reads as
belonging to the panel above it.
"""

from __future__ import annotations

from typing import Sequence

from ..core import Diagram, DiagramError, EllipsePrim, PhantomPrim, Rect, Vec2, mm
from ..draw.coords import active_theme
from ..draw.place import place as draw_place
from ..typeset import shape

__all__ = ["ANNOTATION_TARGET_KIND", "RULE_SIDES", "arrow_between", "callout",
           "check_rule_side", "rule_label", "text_at"]

TEXT_KIND = "label"
ANNOTATION_TARGET_KIND = "datum"

#: The invisible disc a callout points at, as a fraction of the type size. Its
#: radius is where the leader stops, so it is about half a marker: near enough
#: to the datum to be unambiguous, far enough that the line does not touch it.
_TARGET_OF_TYPE = 0.31

#: How far outside the plot area the "stay inside" blockers reach. Anything
#: larger than the panel's own furniture; the search only asks whether a
#: candidate label overlaps one.
_OUTSIDE = 1e4

#: The sides a reference line's label may take, by the axis the rule is at. A
#: horizontal rule (at a y) is labelled above ("n") or below ("s"); a vertical
#: one (at an x) to the right ("e") or left ("w").
RULE_SIDES = {"y": ("n", "s"), "x": ("e", "w")}

#: Slack added to a rule label's search strip, in millimetres. See `rule_label`.
_SLACK = 1e-6


def text_at(panel, x, y, content: str | Diagram, *, anchor: str = "center",
            offset: Sequence[float] = (0.0, 0.0), size: float | str | None = None,
            markup: bool = True, kind: str = TEXT_KIND, **style) -> Diagram:
    """`content` at one data point, with `anchor` of it on that point.

    `anchor` is a compass point on the *label*: `"w"` puts its west edge on the
    datum, so the writing runs east from there. `offset` nudges it in
    millimetres afterwards, which is the right unit for a nudge -- it is a
    typographic clearance, not a quantity.

    `markup=False` sets the string exactly as typed. Writing on a plot is
    usually prose the author wrote, so markup is on; pass this the moment the
    string came out of the data instead -- a gene name, a sample id, anything
    that may contain `**` or `//`.
    """
    node = (content if isinstance(content, Diagram)
            else _text(content, size, style, markup=markup))
    if isinstance(content, Diagram) and style:
        node = node.styled(**style)
    at = panel.point(x, y) + Vec2(mm(offset[0]), mm(offset[1]))
    return draw_place([(at, node)], anchor=anchor, origin=(0, 0), kind=kind)


def _text(content: str, size, style: dict, *, markup: bool = True) -> Diagram:
    theme = active_theme()
    prim = shape(content, font=theme.font_family,
                 size=theme.font_size_small if size is None else mm(size),
                 align=style.pop("align", "center"),
                 line_height=theme.line_height, markup=markup)
    node = Diagram(prim=prim, kind=TEXT_KIND)
    return node.styled(**style) if style else node


def rule_label(panel, content: str | Diagram, *, x=None, y=None,
               span: Sequence | None = None, side: str | None = None,
               clear: float | str | None = None,
               size: float | str | None = None, marks: Sequence = (),
               **style) -> Diagram:
    """The name of a reference line, set at an end of it and clear of the data.

    A threshold with no word against it is a line the reader has to be told
    about in the caption. This is that word. Candidates are tried in order: the
    preferred side (the one with room, unless `side` forces one), then the
    other side if `side` does not forbid it; on each side the labelled end of
    the rule, the far end, then steps along the rule. The first candidate that
    clears `marks` wins, found by the same search a legend uses
    (`place_in_clear_space`). With `marks=()` the first candidate is taken, the
    labelled end on the preferred side.

    Set at the *end* of the rule, not centred on it: the middle of a reference
    line is where the data crosses it, and a label there is read as a datum.
    """
    theme = active_theme()
    gap = theme.gap("xs") if clear is None else mm(clear)
    node = content if isinstance(content, Diagram) else _text(content, size, style)
    if isinstance(content, Diagram) and style:
        node = node.styled(**style)
    if node.kind != TEXT_KIND:
        # Every rule label is a label to lint and to the layout, whatever the
        # Diagram it was given was made as.
        node = Diagram(children=(node,), kind=TEXT_KIND)
    box = node.bbox
    area = panel.area
    if (x is None) == (y is None):
        raise ValueError("a rule label belongs to one x or one y, not both")
    axis = "y" if y is not None else "x"
    check_rule_side(side, axis)
    from ..layout.clear_space import place_in_clear_space
    if axis == "y":
        at = panel.y.map(y)
        low, high = _span_range(panel.x, span, area.x0, area.x1)
        preferred = side or ("n" if at - area.y0 >= box.height + 2 * gap else "s")
        order = [preferred] if side else [preferred, "s" if preferred == "n" else "n"]

        def strip(chosen: str) -> Rect:
            # The label's free coordinate is along the rule alone, so the strip
            # is one label thick. The slack keeps rounding from emptying it.
            top = at - 2 * gap - box.height if chosen == "n" else at
            return Rect(low, top, high, top + 2 * gap + box.height + _SLACK)
    else:
        at = panel.x.map(x)
        low, high = _span_range(panel.y, span, area.y0, area.y1)
        preferred = side or ("e" if area.x1 - at >= box.width + 2 * gap else "w")
        order = [preferred] if side else [preferred, "w" if preferred == "e" else "e"]

        def strip(chosen: str) -> Rect:
            left = at - 2 * gap - box.width if chosen == "w" else at
            return Rect(left, low, left + 2 * gap + box.width + _SLACK, high)

    for chosen in order:
        try:
            return place_in_clear_space(node, within=strip(chosen),
                                        avoid=marks, pad=gap)
        except DiagramError:
            continue
    # Nothing clear on any side allowed: the labelled end on the preferred
    # side, as drawn with no search at all. Lint reports the collision.
    return place_in_clear_space(node, within=strip(order[0]), avoid=(), pad=gap)


def check_rule_side(side: str | None, axis: str) -> None:
    """Refuse a `label_side` that a rule of this orientation does not have."""
    if side is None or side in RULE_SIDES[axis]:
        return
    allowed = " or ".join(repr(s) for s in RULE_SIDES[axis])
    kind = "hline" if axis == "y" else "vline"
    raise ValueError(f"{kind} label_side must be {allowed}, not {side!r}")


def _span_range(scale, span: Sequence | None, low: float,
                high: float) -> tuple[float, float]:
    """The stretch of a rule that its label may use, in millimetres, low first.

    A rule with no `span` runs the whole plot area. One with a span runs where
    the span does, and its label is searched only along that stretch, so it
    follows the span in rather than floating out over the axis.
    """
    if span is None:
        return low, high
    ends = (scale.map(span[0]), scale.map(span[1]))
    return min(ends), max(ends)


def arrow_between(panel, a: Sequence, b: Sequence, *, head: str = "triangle",
                  label: str | Diagram | None = None,
                  **style) -> tuple[Diagram, Diagram]:
    """An arrow from data point `a` to data point `b`.

    Routed by `inklet.links` rather than drawn here, so the head is the same head
    every other arrow in the figure has and `head=`, `kind=`, dashes and labels
    all mean what they mean elsewhere. The two ends are *anchors* on a carrier
    node -- points, not shapes -- so nothing is clipped: an arrow between two
    data coordinates ends on those coordinates exactly.

    Returns the carrier and the routed arrow; both belong in the panel, the
    carrier because a connector that names an endpoint outside the tree has
    lost the provenance `inklet.lint` reads.
    """
    from ..core import resolve
    from ..links import link as make_link, route

    if isinstance(label, str):
        # `inklet.links` never shapes text -- it takes a built label so that the
        # caller owns the type. A plot's arrow is a small piece of writing on
        # the plot, so it is set in the same face `text_at` uses.
        label = _text(label, None, {})
    start, end = panel.point(*a), panel.point(*b)
    # A `PhantomPrim` spanning the two ends rather than a bare node: a diagram
    # with no prim and no children draws nothing and occupies nothing, which is
    # what `EMPTY_DIAGRAM` is for, and an arrow that lints dirty every time it
    # is drawn teaches authors to stop reading the linter. The box is exactly
    # the span the shaft already covers, and a phantom catches no rays, so the
    # carrier claims no space the arrow did not claim anyway.
    span = Rect(min(start.x, end.x), min(start.y, end.y),
                max(start.x, end.x), max(start.y, end.y))
    carrier = Diagram(prim=PhantomPrim(span), kind="arrow-ends")
    carrier.anchor("from", start)
    carrier.anchor("to", end)
    spec = make_link(carrier.at("from"), carrier.at("to"), head=head,
                     label=label, **style)
    return carrier, route(spec, resolve(carrier))


def callout(panel, x, y, text: str | Diagram, *, side: str = "n",
            clear: float | str | None = None, leader: bool = True,
            inside: bool = True, dot: bool = False,
            avoid: Sequence = (), **kwargs) -> Diagram:
    """A label clear of one data point, with a leader back to it.

    `inklet.annotate` does the placing, so the side is a *request*: a blocked one
    walks around the compass and `inklet.annotation_side` reads back where the
    label went. What this adds is the datum -- an invisible disc half a marker
    across, sitting on the data point, which is what the leader stops on -- and
    the plot area as a boundary the label is kept inside.

    `dot=True` makes that disc visible, which is what a callout on a curve with
    no marker of its own usually wants.
    """
    from ..draw.annotate import annotate as draw_annotate

    theme = active_theme()
    at = panel.point(x, y)
    # A marker drawn on the point is part of the datum, so the clearance
    # starts at its edge rather than inside it.
    radius = _marker_radius(panel, at, _TARGET_OF_TYPE * theme.font_size)
    target = Diagram(prim=EllipsePrim(radius, radius),
                     kind=ANNOTATION_TARGET_KIND)
    target = target.translated(at.x, at.y)
    target = (target.styled(fill=theme.ink, stroke="none") if dot
              else target.styled(fill="none", stroke="none"))
    blockers = list(avoid) + (_outside(panel.area) if inside else [])
    gap = theme.gap("xs") if clear is None else mm(clear)
    return draw_annotate(target, text, side=side, clear=gap, leader=leader,
                         avoid=blockers, **kwargs)


def _marker_radius(panel, at: Vec2, least: float) -> float:
    """Half the largest mark the panel centers on `at`, and at least `least`.

    Only marks up to a few type sizes across count, so a shape that happens
    to be centered on the point (a band, a disc of a pie) is not taken for
    its marker.
    """
    from ..core import resolve

    largest = 4 * active_theme().font_size
    radius = least
    for layer in panel._content:
        box = layer.bbox
        if not (box.x0 - 1e-6 <= at.x <= box.x1 + 1e-6 and box.y0 - 1e-6 <= at.y <= box.y1 + 1e-6):
            continue
        for placed in resolve(layer).values():
            if placed.diagram.prim is None:
                continue
            mark = placed.envelope.bbox()
            half = max(mark.width, mark.height) / 2
            if (half <= largest / 2 and abs(mark.center.x - at.x) < 1e-3
                    and abs(mark.center.y - at.y) < 1e-3):
                radius = max(radius, half)
    return radius


def _outside(area: Rect) -> list[Rect]:
    """The four half-planes around the plot area.

    `inklet.annotate` scores a candidate side by how much of the label overlaps
    something it must miss, so handing it the *outside* as an obstacle turns
    "keep the label in the panel" into the search it is already running.
    """
    return [
        Rect(area.x0 - _OUTSIDE, area.y0 - _OUTSIDE, area.x1 + _OUTSIDE, area.y0),
        Rect(area.x0 - _OUTSIDE, area.y1, area.x1 + _OUTSIDE, area.y1 + _OUTSIDE),
        Rect(area.x0 - _OUTSIDE, area.y0 - _OUTSIDE, area.x0, area.y1 + _OUTSIDE),
        Rect(area.x1, area.y0 - _OUTSIDE, area.x1 + _OUTSIDE, area.y1 + _OUTSIDE),
    ]
