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

from ..core import Diagram, EllipsePrim, PhantomPrim, Rect, Vec2, mm
from ..draw.coords import active_theme
from ..draw.place import place as draw_place
from ..typeset import shape

__all__ = ["ANNOTATION_TARGET_KIND", "arrow_between", "callout", "rule_label",
           "text_at"]

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
               size: float | str | None = None, **style) -> Diagram:
    """The name of a reference line, set at the far end of it and off it.

    A threshold with no word against it is a line the reader has to be told
    about in the caption. This is that word, placed the way `inklet.annotate`
    places a callout: on the side with room, flipped to the other when there is
    not. The rule is a straight line rather than a shape, so the side test is
    the simple one -- is there a line height between the rule and the edge of
    the plot area -- and there is no search to run.

    Set at the *end* of the rule, not centred on it: the middle of a reference
    line is where the data crosses it, and a label there is read as a datum.
    """
    theme = active_theme()
    gap = theme.gap("xs") if clear is None else mm(clear)
    node = content if isinstance(content, Diagram) else _text(content, size, style)
    if isinstance(content, Diagram) and style:
        node = node.styled(**style)
    box = node.bbox
    area = panel.area
    if (x is None) == (y is None):
        raise ValueError("a rule label belongs to one x or one y, not both")
    if y is not None:
        at = panel.y.map(y)
        end = _span_end(panel.x, span, area.x0, area.x1)
        above = at - area.y0 >= box.height + 2 * gap
        chosen = side or ("n" if above else "s")
        centre = Vec2(end - gap - box.width / 2,
                      at - gap - box.height / 2 if chosen == "n"
                      else at + gap + box.height / 2)
    else:
        at = panel.x.map(x)
        end = _span_end(panel.y, span, area.y1, area.y0)
        right = area.x1 - at >= box.width + 2 * gap
        chosen = side or ("e" if right else "w")
        centre = Vec2(at + gap + box.width / 2 if chosen == "e"
                      else at - gap - box.width / 2,
                      end + gap + box.height / 2)
    return draw_place([(centre, node)], origin=(0, 0), kind=TEXT_KIND)


def _span_end(scale, span: Sequence | None, low: float, high: float) -> float:
    """Where the labelled end of a rule is, in millimetres.

    `low` and `high` are the two ends of the plot area along the rule, in the
    order the label prefers them: a horizontal rule is labelled at its right
    end, a vertical one at its top. A rule with no `span` reaches the area's
    edge; one with a span ends where the span does, and the label follows it in
    rather than floating out over the axis.
    """
    if span is None:
        return high
    ends = (scale.map(span[0]), scale.map(span[1]))
    return max(ends) if high > low else min(ends)


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
    radius = _TARGET_OF_TYPE * theme.font_size
    at = panel.point(x, y)
    target = Diagram(prim=EllipsePrim(radius, radius),
                     kind=ANNOTATION_TARGET_KIND)
    target = target.translated(at.x, at.y)
    target = (target.styled(fill=theme.ink, stroke="none") if dot
              else target.styled(fill="none", stroke="none"))
    blockers = list(avoid) + (_outside(panel.area) if inside else [])
    gap = theme.gap("xs") if clear is None else mm(clear)
    return draw_annotate(target, text, side=side, clear=gap, leader=leader,
                         avoid=blockers, **kwargs)


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
