"""Explicit coordinates, for the diagrams that genuinely have them.

Everything else in `inklet` refuses to let an author type a coordinate, and that
is right for a diagram whose meaning is "this box, then that one". It is wrong
for a scatter plot, a map or a circuit, where the coordinates *are* the
content. `place()` is the one door into that world, and it is deliberately
narrow: it positions children and does nothing else.
"""

from __future__ import annotations

from typing import Iterable

from ..core import ORIGIN, Affine, Diagram, Vec2
from .coords import (
    ORIGIN_ANCHOR, Point, as_drawn, drawn_group, placed_anchor, to_point,
)

__all__ = ["drawn", "place"]

PLACE_KIND = "place"


def place(items: Iterable[tuple[Point, Diagram] | Diagram], *,
          anchor: str = "center", origin: Point | None = None,
          kind: str = PLACE_KIND, **style) -> Diagram:
    """Put children at explicit coordinates, in millimetres.

    An item is either a `(point, diagram)` pair -- that diagram's `anchor`
    lands on that point -- or a bare diagram already drawn in these very
    coordinates, which is put back where it was drawn. The two mix freely, so
    a curve and the markers riding on it can be placed in one call:

        place([curve(track)] + [(p, marker("circle")) for p in track])

    By default the result is centred on its own bounding box like everything
    else here, with an `origin` anchor remembering where (0, 0) of these
    coordinates ended up. That is right for a single group and quietly wrong
    for several: **each call centres on its own box, so two `place` calls over
    one drawing come out in two different frames**, and the geometry, the
    east-anchored text and the west-anchored text of what the author thinks is
    one picture drift apart by half the difference in their widths. Nothing
    raises; the figure is simply out of register.

    `origin=(0, 0)` is the fix. The group is then expressed in the author's own
    coordinates -- that point sits on the local origin, `bbox` reads in the
    numbers that were typed, and `translated(dx, dy)` moves by them. Several
    such groups share one frame exactly, so composing them keeps the register:

        geometry = place(shapes, origin=(0, 0))
        east     = place(right_labels, anchor="w", origin=(0, 0))
        panel    = place([geometry, east])          # still in register

    That last line matters either way: `place` puts a bare diagram back where
    it was drawn, and so do `Panel.draw` and `overlay(..., align="origin")`.
    The stacks and `overlay`'s compass alignments do not -- they align bounding
    boxes, which is what they are for -- so a drawing assembled with
    `overlay(items)` loses its frame whatever `origin` says.

    `inklet.drawn(items)` is this call with `origin=(0, 0)`, under a name that
    says which of the two you meant.
    """
    if isinstance(items, Diagram):
        raise TypeError(
            "place takes a list of items, not one diagram; write "
            "place([((x, y), d)]) to position it, or inklet.drawn(d) to put it "
            "back where it was drawn"
        )
    placed: list[Diagram] = []
    seen: set[int] = set()
    for index, item in enumerate(items):
        node, point = _unpack(item, index)
        if id(node) in seen:
            raise ValueError(
                f"place was handed the same Diagram object twice (item {index}); "
                "use .copy() to place the same shape more than once"
            )
        seen.add(id(node))
        placed.append(as_drawn(node) if point is None else _at(node, point, anchor))
    if origin is None:
        return drawn_group(placed, kind, style)
    return _in_frame(placed, to_point(origin), kind, style)


def drawn(items: Diagram | Iterable[Diagram], *, kind: str = PLACE_KIND,
          **style) -> Diagram:
    """Absolute-coordinate geometry, back in the coordinates it was drawn in.

    Every shape `inklet.draw` builds is shifted onto its own origin -- that is
    what lets it stack and rotate like a primitive -- and remembers where the
    author's (0, 0) went. `drawn` is the undo: hand it a shape, or several
    drawn in one frame, and what comes back is expressed in *that* frame, with
    (0, 0) on the local origin.

        ring = inklet.polygon(pocket)          # points in the scene's own mm
        tag  = inklet.label("hinge")
        fig.add(inklet.drawn([scene, ring, ((x, y), tag)]))

    This is what a drawing over a projected 3D scene needs: `anchor_point` on
    the scene answers in scene millimetres, and so do the shapes drawn from
    those numbers, so nothing has to be re-derived from a bounding box.
    `inklet.plot.Panel.draw` does the same thing for data coordinates.

    One item or many behave the same way, and `(point, diagram)` pairs mix in
    exactly as they do in `place` -- `drawn(items)` *is* `place(items,
    origin=(0, 0))`, under the name that says what it is for.
    """
    if isinstance(items, Diagram):
        items = [items]
    elif not hasattr(items, "__iter__"):
        raise TypeError(
            f"drawn() takes a shape or a list of them, not "
            f"{type(items).__name__} ({items!r})"
        )
    return place(items, origin=ORIGIN, kind=kind, **style)


def _in_frame(children: list[Diagram], origin: Vec2, kind: str,
              style: dict) -> Diagram:
    """A group whose local origin is a point the author chose.

    The same shape as `drawn_group`, with the offset coming from the author
    rather than from the bounding box. The `origin` anchor still records where
    the author's (0, 0) went, so `as_drawn` and `Panel.draw` keep working; with
    `origin=(0, 0)` it lands on (0, 0) and putting the group back where it was
    drawn is a no-op, which is the point.
    """
    node = Diagram(children=tuple(children), kind=kind,
                   transform=Affine.translation(-origin.x, -origin.y))
    node.anchor(ORIGIN_ANCHOR, ORIGIN)
    return node.styled(**style) if style else node


def _unpack(item, index: int) -> tuple[Diagram, Vec2 | None]:
    if isinstance(item, Diagram):
        return item, None
    try:
        point, node = item
    except (TypeError, ValueError):
        raise TypeError(
            f"place item {index} is not a diagram or a (point, diagram) pair: "
            f"{item!r}"
        ) from None
    if not isinstance(node, Diagram):
        raise TypeError(
            f"place item {index} pairs a point with a "
            f"{type(node).__name__}, not a Diagram"
        )
    return node, to_point(point)


def _at(node: Diagram, point: Vec2, anchor: str) -> Diagram:
    """Move `node` so its anchor sits on `point`, in the parent's frame."""
    here = placed_anchor(node, anchor)
    return node.translated(point.x - here.x, point.y - here.y)
