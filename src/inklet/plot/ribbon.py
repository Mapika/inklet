"""Ribbons: a band of variable width flowing from one segment to another.

A Sankey link, an alluvial flow, a cohort peeling off a cascade -- all the same
shape, and all of it easy to get subtly wrong. The trap is the middle: two
edges eased independently cross the flow at different rates, so the band
pinches in one place and bulges in another and its width stops meaning what
the legend says it means. Both long edges here share one ease and one flow
direction, so every cross-section is square to the flow and the width eases
monotonically from one end width to the other -- never narrower than the
narrow end, never wider than the wide one.

The geometry is a single closed subpath of four cubics -- one eased edge, the
straight cubic that closes the far end, the other eased edge reversed, the
straight cubic that closes the near end -- because `inklet.path(curves=)` wants a
chain that spans the whole outline, straight runs included.

    inklet.ribbon((0, 0), (40, 12), width0=8, width1=3)
"""

from __future__ import annotations

from typing import Sequence

from ..core import Diagram, Vec2
from ..draw.coords import Point, to_point
from ..draw.path import Cubic, path, straight_cubic
from ..draw.shapes import MARK_KIND

__all__ = ["ALIGNMENTS", "RIBBON_EASE", "eased_cubic", "ribbon",
           "ribbon_between", "ribbon_cubics"]

_EPS = 1e-9

#: How far the control points reach along the flow, as a fraction of the
#: projected separation. 0.55 is where a band that swings across a panel gets a
#: full S while one that barely moves sideways stays visibly straight; it is
#: also what the two hand-rolled copies of this in `stress/` had settled on.
RIBBON_EASE = 0.55

ALIGNMENTS = ("center", "start", "end")


def eased_cubic(p0: Vec2, p3: Vec2, along: Vec2, ease: float) -> Cubic:
    """A cubic leaving `p0` and arriving at `p3` travelling along `along`.

    The control points sit `ease` of the *projected* separation out along that
    direction, so how much S an edge gets is a property of how far it actually
    travels, not of how long the caller's list of ribbons is.
    """
    reach = (p3 - p0).dot(along) * ease
    return (p0, p0 + along * reach, p3 - along * reach, p3)


def ribbon_cubics(a0: Point, a1: Point, b0: Point, b1: Point,
                  along: Point | None = None,
                  ease: float = RIBBON_EASE) -> tuple[Cubic, ...]:
    """The closed outline of a band from segment a0-a1 to segment b0-b1.

    Four cubics, in drawing order. `along` is the flow direction; left out, it
    is the normal of the near end pointing at the far one, which is the right
    answer whenever the two ends are the parallel faces of a flow -- a Sankey
    node, a stacked bar, an alluvial stratum.
    """
    pa0, pa1 = to_point(a0), to_point(a1)
    pb0, pb1 = to_point(b0), to_point(b1)
    flow = _flow(pa0, pa1, pb0, pb1) if along is None else to_point(along)
    return (
        eased_cubic(pa0, pb0, flow, ease),
        straight_cubic(pb0, pb1),
        eased_cubic(pb1, pa1, flow, ease),
        straight_cubic(pa1, pa0),
    )


def ribbon_between(a0: Point, a1: Point, b0: Point, b1: Point, *,
                   along: Point | None = None, ease: float = RIBBON_EASE,
                   kind: str = MARK_KIND, **style) -> Diagram:
    """`ribbon_cubics` as a filled diagram, given the four corners.

    The corner form, for a Sankey whose end faces are already known -- a bar's
    top edge, a stratum's slice of a node. `ribbon` is the same shape written
    as two centres and two widths.

    `kind="mark"`, because a ribbon's width is the measurement: asking a 0.3mm
    flux to keep 0.7mm clear of its neighbour would be asking the figure to
    lie.
    """
    return path(curves=ribbon_cubics(a0, a1, b0, b1, along, ease),
                closed=True, filled=True, kind=kind, **style)


def ribbon(a: Point, b: Point, *, width0: float, width1: float | None = None,
           along: Point | None = None, ease: float = RIBBON_EASE,
           align: str = "center", kind: str = MARK_KIND, **style) -> Diagram:
    """A band from `a` to `b`, `width0` wide at one end and `width1` at the other.

    `a` and `b` are the *centres* of the two end faces and the widths are
    measured across the flow, so a ribbon that halves in width has halved the
    thing it stands for; in between, the width eases from one to the other and
    never leaves the interval between them. `width1` defaults to `width0`,
    which is the constant band a process loop wants.

    `align` says which part of the end face `a` and `b` name: "center" by
    default, or "start"/"end" to hold one edge of the flow straight -- what a
    retention cascade does, so that what survives stays on one side and the
    losses peel off the other.
    """
    if align not in ALIGNMENTS:
        raise ValueError(
            f"unknown ribbon align {align!r}; expected one of {', '.join(ALIGNMENTS)}"
        )
    start, end = to_point(a), to_point(b)
    flow = _unit(end - start) if along is None else _unit(to_point(along))
    across = Vec2(-flow.y, flow.x)
    w0 = float(width0)
    w1 = w0 if width1 is None else float(width1)
    a0, a1 = _face(start, across, w0, align)
    b0, b1 = _face(end, across, w1, align)
    return ribbon_between(a0, a1, b0, b1, along=flow, ease=ease, kind=kind,
                          **style)


def _face(centre: Vec2, across: Vec2, width: float,
          align: str) -> tuple[Vec2, Vec2]:
    if align == "start":
        return centre, centre + across * width
    if align == "end":
        return centre - across * width, centre
    half = across * (width / 2.0)
    return centre - half, centre + half


def _flow(a0: Vec2, a1: Vec2, b0: Vec2, b1: Vec2) -> Vec2:
    """The near end's normal, turned to point at the far end.

    A zero-width near end has no normal of its own, so the line joining the two
    midpoints stands in -- degenerate geometry, but a caller sweeping a width
    down to nothing should get a taper rather than an exception.
    """
    across = a1 - a0
    toward = (b0 + b1) * 0.5 - (a0 + a1) * 0.5
    if across.length <= _EPS:
        return _unit(toward)
    normal = _unit(Vec2(-across.y, across.x))
    return -normal if normal.dot(toward) < 0.0 else normal


def _unit(v: Vec2) -> Vec2:
    return Vec2(1.0, 0.0) if v.length <= _EPS else v.normalized()


# -- in data coordinates --------------------------------------------------


def panel_ribbon(panel, a: Sequence, b: Sequence, *, width0: float,
                 width1: float | None = None, ease: float = RIBBON_EASE,
                 align: str = "center", **style) -> Diagram:
    """`ribbon` in a panel's data coordinates, widths included.

    Both ends and both widths go through the scales, so a band on a log axis
    tapers the way the data does rather than the way the millimetres do. The
    width is read on whichever axis the flow crosses: a ribbon travelling
    mostly left-to-right is `width0` tall *in y units* at its start.

    Backing `Panel.ribbon`; call it through the panel.
    """
    start, end = panel.point(*a), panel.point(*b)
    horizontal = abs(end.x - start.x) >= abs(end.y - start.y)
    a0, a1 = _panel_face(panel, a, width0, horizontal, align)
    w1 = width0 if width1 is None else width1
    b0, b1 = _panel_face(panel, b, w1, horizontal, align)
    flow = _unit(end - start)
    return ribbon_between(a0, a1, b0, b1, along=flow, ease=ease, **style)


def _panel_face(panel, at: Sequence, width: float, horizontal: bool,
                align: str) -> tuple[Vec2, Vec2]:
    """One end face, in millimetres, from a data point and a data width."""
    value = at[1] if horizontal else at[0]
    lo, hi = {
        "center": (value - width / 2.0, value + width / 2.0),
        "start": (value, value + width),
        "end": (value - width, value),
    }[align]
    if horizontal:
        return panel.point(at[0], lo), panel.point(at[0], hi)
    return panel.point(lo, at[1]), panel.point(hi, at[1])
