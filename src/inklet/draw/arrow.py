"""Authored arrows with exact curved shafts and tangent-aligned heads."""
from __future__ import annotations

import math
from ..core import Diagram, PathPrim, Subpath, Vec2, mm
from .coords import as_drawn, drawn_group, to_points
from .path import catmull_rom, straight_cubic


def arrow(points, *, smooth: float = 0.5, head: str = "triangle",
          head_length: float | str = 2.0, head_width: float | str | None = None,
          both: bool = False, color: str | None = None,
          stroke_width: float | str = 0.35, **style) -> Diagram:
    """Draw an arrow through waypoints, or along an existing single open path.

    Waypoints use the same Catmull–Rom spline as :func:`inklet.curve`; use
    ``smooth=0`` for straight segments. A path Diagram retains its exact cubics
    and placement. The head follows the endpoint tangent, and the shaft is cut
    back beneath it. Short arrows shrink their heads to leave a visible shaft.

    Lengths are millimetres (unit strings accepted). The result follows the
    drawing convention: centred for layout, ``as_drawn()`` restores supplied
    coordinates. ``start`` and ``end`` anchors mark the original tips.
    This is an authored path; use ``link`` for obstacle-aware routing.
    """
    # Shared curve arithmetic, imported late to avoid draw/links import cycles.
    from ..links import curves as bezier
    from .. import current_theme

    if head not in ("triangle", "open"):
        raise ValueError("arrow head must be 'triangle' or 'open'")
    length = mm(head_length)
    width = length * .8 if head_width is None else mm(head_width)
    weight = mm(stroke_width)
    if not all(math.isfinite(v) and v > 0 for v in (length, width, weight)):
        raise ValueError("arrow head sizes and stroke_width must be finite and positive")
    if not math.isfinite(smooth) or smooth < 0:
        raise ValueError("arrow smooth must be finite and non-negative")
    if isinstance(points, Diagram):
        transform = points.transform
        node = points
        while node.prim is None and len(node.children) == 1:
            node = node.children[0]
            transform = transform @ node.transform
        if not isinstance(node.prim, PathPrim) or len(node.prim.subpaths) != 1 or node.children:
            raise ValueError("arrow requires one open path, not a group or multiple subpaths")
        sub = node.prim.subpaths[0]
        if sub.closed:
            raise ValueError("arrow requires an open path")
        pts = tuple(transform.apply(v) for v in sub.points)
        chain = tuple(tuple(transform.apply(v) for v in c) for c in sub.curves)
        if not chain:
            chain = tuple(straight_cubic(a, b) for a, b in zip(pts, pts[1:]))
    else:
        pts = to_points(points)
        # Repeated stations have no direction and should not create loops.
        pts = tuple(v for k, v in enumerate(pts) if k == 0 or v != pts[k-1])
        chain = catmull_rom(pts, smooth) if len(pts) >= 2 else ()
    if not chain or not all(math.isfinite(v.x) and math.isfinite(v.y)
                            for c in chain for v in c):
        raise ValueError("arrow requires at least two distinct finite points")
    total = bezier.length(chain)
    if total <= 1e-9:
        raise ValueError("arrow requires a nonzero path length")
    scale = min(1., total * .4 / (length * (2 if both else 1)))
    length *= scale; width *= scale
    first, last = chain[0][0], chain[-1][-1]

    def direction(tip, candidates):
        for value in candidates:
            delta = tip - value
            if delta.length > 1e-9:
                return delta.normalized()
        raise ValueError("arrow endpoint has no tangent")

    ends = [(last, direction(last, reversed([v for c in chain for v in c[:-1]])))]
    if both:
        ends.append((first, direction(first, [v for c in chain for v in c[1:]])))
    ink = color or style.pop("stroke", None) or current_theme().ink
    cut = bezier.trim_end(chain, length if head == "triangle" else 0.)
    if both and head == "triangle":
        cut = bezier.trim_start(cut, length)
    shaft = Diagram(prim=PathPrim((Subpath(bezier.flatten(cut), curves=cut),)),
                    kind="arrow-shaft").styled(fill="none", stroke=ink,
                    stroke_width=weight, stroke_linecap="butt", stroke_linejoin="round")
    children = [shaft]
    for tip, tangent in ends:
        back = tip - tangent * length
        side = tangent.perp() * (width / 2)
        vertices = ((tip, back + side, back - side) if head == "triangle"
                    else (back + side, tip, back - side))
        children.append(Diagram(prim=PathPrim((Subpath(vertices, closed=head == "triangle"),),
                                             filled=head == "triangle"), kind="arrowhead").styled(
            fill=ink if head == "triangle" else "none",
            stroke="none" if head == "triangle" else ink, stroke_width=weight,
            stroke_linecap="round", stroke_linejoin="round"))
    node = drawn_group(children, "arrow", style)
    node.anchor("start", first); node.anchor("end", last)
    node.notes['arrow'] = dict(head=head, head_length=length, head_width=width,
                               both=both, original_length=total)
    return node
