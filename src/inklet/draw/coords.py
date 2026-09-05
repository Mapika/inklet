"""Author coordinates, and the convention every drawn node keeps.

Two rules hold across `inklet.draw`.

**A point is millimetres.** It may be a `Vec2` or an `(x, y)` pair, and each
component goes through `core.units.mm`, so `(3, "4mm")` and `Vec2(3, 4)` name
the same place and `pt(7)` works here exactly as it does everywhere else.

**What comes back is centred on its own origin, like a primitive.** Core
centres `RectPrim` on the local origin so that rotation and stacking need no
anchor-correction step, and a path that ignored that would sit in an `hstack`
off by half its own width and rotate about a point outside itself. So the
geometry is built in the coordinates the author wrote and then shifted onto the
origin.

That shift would otherwise throw those coordinates away, which is fatal for
anything drawn as a *set* of shapes -- a wedge and the label that belongs in
it, a curve and the markers riding on it. Every node built here therefore
carries an `origin` anchor recording where the author's (0, 0) ended up, and
`as_drawn()` -- `layout.align_to(node, "origin")` with a shorter name -- puts
it back exactly where it was drawn. That is the whole trick behind `place()`
and behind `plot.Panel`: draw in data space, compose in shape space, and keep
the two reconcilable.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from ..core import (
    IDENTITY, ORIGIN, Affine, Diagram, DiagramError, Prim, Rect, Vec2, mm,
    note_through,
)

__all__ = [
    "AREA_NOTE", "ORIGIN_ANCHOR", "Point", "as_drawn", "declare_area", "drawn",
    "drawn_group", "needs_diagram", "plot_area",
    "placed_anchor", "to_point", "to_points",
]

#: Where the author's (0, 0) sits in a drawn node's local frame.
ORIGIN_ANCHOR = "origin"

#: The note a built panel -- and a `row`, `column` or `facets` grid of them --
#: uses to declare where the axes stop and the data starts. Everything that
#: lines panels up reads it, because a bounding box is the furniture and the
#: furniture is exactly what differs between two panels that must agree.
AREA_NOTE = "plot_area"


Point = Vec2 | tuple[float | str, float | str] | Sequence[float | str]


def to_point(value: Point) -> Vec2:
    """A `Vec2` or an `(x, y)` pair, in millimetres."""
    if isinstance(value, Vec2):
        return value
    if isinstance(value, str):
        # A string unpacks into two characters and would fail far from here.
        raise TypeError(f"expected a point, not the string {value!r}")
    try:
        x, y = value
    except (TypeError, ValueError):
        raise TypeError(
            f"expected a point -- a Vec2 or an (x, y) pair -- not {value!r}"
        ) from None
    return Vec2(mm(x), mm(y))


def to_points(values: Iterable[Point]) -> tuple[Vec2, ...]:
    if isinstance(values, (Vec2, str)) or not hasattr(values, "__iter__"):
        raise TypeError(
            f"expected a sequence of points -- [(x, y), (x, y), ...] -- not "
            f"{values!r}"
        )
    return tuple(to_point(v) for v in values)


def drawn(prim: Prim, origin: Vec2, kind: str, style: dict) -> Diagram:
    """A leaf whose geometry has already been shifted onto the local origin.

    `origin` is where the author's (0, 0) landed under that shift -- for a
    single recentred shape, minus the centre it was moved by.
    """
    node = Diagram(prim=prim, kind=kind)
    node.anchor(ORIGIN_ANCHOR, origin)
    return node.styled(**style) if style else node


def drawn_group(children: Sequence[Diagram], kind: str,
                style: dict | None = None) -> Diagram:
    """Children already placed in author coordinates, shifted onto the origin.

    The offset rides on the group's own transform rather than on another
    wrapper, exactly as `layout` does it, so the children keep the coordinates
    they were drawn in and the `origin` anchor is simply (0, 0).
    """
    box = _union_box(children)
    transform = (IDENTITY if box is None
                 else Affine.translation(-box.center.x, -box.center.y))
    node = Diagram(children=tuple(children), transform=transform, kind=kind)
    node.anchor(ORIGIN_ANCHOR, ORIGIN)
    return node.styled(**style) if style else node


def as_drawn(node: Diagram) -> Diagram:
    """Put a drawn node back at the coordinates it was drawn in.

    The inverse of the centring above: it moves the node so its `origin` anchor
    lands on the parent's origin. A node with no such anchor was never
    recentred by this package, so it is already in the frame it belongs to and
    comes back untouched.

        rings = [inklet.polyline(track, stroke=c) for track, c in tracks]
        overlay = inklet.drawn(rings)          # each ring back on the shared frame
        scene = inklet.overlay([picture, inklet.as_drawn(overlay)])

    `node.anchors` rather than `anchor_point`, deliberately: since M16 a
    transform wrapper answers for the shape inside it, and the question here is
    about *this* node. A wrapper someone put round a drawn shape is a placement
    they meant, and reaching past it to the child's origin would undo it --
    which moved `stress/electro_figure.py` 6.5mm when the look-through first
    landed.
    """
    origin = node.anchors.get(ORIGIN_ANCHOR)
    if origin is None:
        return node
    point = node.transform.apply(origin)
    return node.translated(-point.x, -point.y)


def needs_diagram(what: str, item, role: str = "a diagram"):
    """Refuse a non-Diagram at the door, by name.

    Every combinator here takes a `Diagram` and reaches straight for one of its
    attributes, so the wrong type surfaces as `'int' object has no attribute
    'is_empty'` several frames down, naming neither the function nor the
    argument. One check buys the sentence that would have been read.
    """
    if isinstance(item, Diagram):
        return item
    if isinstance(item, str):
        raise TypeError(
            f"{what}() takes {role}, not a string; shape it first -- "
            f"{what}(inklet.text({item!r}))"
        )
    raise TypeError(
        f"{what}() takes {role}, not {type(item).__name__} ({item!r})"
    )


_COMPASS = ("c", "center", "e", "n", "ne", "nw", "s", "se", "sw", "w")


def placed_anchor(item: Diagram, anchor: str = "center") -> Vec2:
    """An item's named anchor, in the coordinates of whoever holds it.

    `Diagram.anchor_point` answers in the item's *own* frame, before its own
    transform. That is right for a registered anchor -- `mouse.at("ear")` names
    a point of the mouse and travels with it -- and wrong for a compass point
    of something rotated: the "n" of a label turned a quarter turn is the north
    of the *unturned* label, which now faces west, while `item.bbox` has
    already swapped width for height. Mixing the two is the arithmetic that
    costs a regression per rotated axis label.

    So compass names are resolved against the item's *placed* bounding box --
    the one `bbox`, `width` and `height` report -- and registered anchors are
    carried through the transform as before. For an item with no transform the
    two readings are identical, which is why this can be the one `place` and
    `align_to` use.

    A registered anchor lives on the node it was put on, and `translated`,
    `rotated` and friends wrap rather than rewrite, so ask the node that
    carries the anchor -- not a wrapper around it.
    """
    if anchor in item.anchors:
        return item.transform.apply(item.anchors[anchor])
    if anchor not in _COMPASS:
        known = ", ".join(sorted(set(_COMPASS) | set(item.anchors)))
        raise DiagramError(f"{item.id} has no anchor {anchor!r}; known: {known}")
    box = item.envelope.bbox()
    if box is None:
        raise DiagramError(
            f"{item.id} is empty, so it has no {anchor!r} to place"
        )
    mid = box.center
    # y grows downward, so north is the smaller y.
    table = {
        "center": mid, "c": mid,
        "n": Vec2(mid.x, box.y0), "s": Vec2(mid.x, box.y1),
        "w": Vec2(box.x0, mid.y), "e": Vec2(box.x1, mid.y),
        "nw": Vec2(box.x0, box.y0), "ne": Vec2(box.x1, box.y0),
        "sw": Vec2(box.x0, box.y1), "se": Vec2(box.x1, box.y1),
    }
    return table[anchor]


def hull(points: Sequence[Vec2]) -> Rect:
    return Rect.hull(points)


def active_theme():
    """The theme new content is built against.

    Imported late on purpose: `inklet/__init__` imports this package while it is
    still executing its own module body, and the current theme is a global
    there -- reading it at call time is what makes `use_theme()` affect
    everything drawn afterwards.
    """
    from .. import current_theme

    return current_theme()


def _union_box(items: Iterable[Diagram]) -> Rect | None:
    box = None
    for item in items:
        other = item.envelope.bbox()
        if other is not None:
            box = other if box is None else box.union(other)
    return box


# -- the plot-area contract -----------------------------------------------
#
# One rectangle, written by whatever built the node and read by whatever lines
# it up against a neighbour. It lives here rather than in `plot` because
# `draw.annotate.letters` reads it too, and three copies of the frame
# arithmetic below is exactly how the first attempt at panel alignment halved
# its error instead of removing it.


def plot_area(node: Diagram) -> Rect | None:
    """Where a panel keeps its data, or None for a node that is not one.

    The rectangle a built `Panel` -- or a `row`, `column` or `facets` group of
    them -- declares as its data region, so a figure composing panels by hand
    can line them up the way `inklet.row` does instead of measuring boxes and
    inheriting exactly the misalignment this exists to remove:

        here = inklet.plot_area(left)
        there = inklet.plot_area(right)
        right = right.translated(0, here.center.y - there.center.y)

    **The frame is the one `node.bbox` is in** -- the parent's -- and that is
    the trap. The note itself is written in the frame the node was *drawn* in,
    before the recentring that puts a built panel on its own origin; this
    carries it through `node.transform` so the two are comparable. Reading
    `node.notes["plot_area"]` raw and holding it against `node.bbox` agrees
    only for a panel whose furniture happens to be symmetric, and a legend
    across the top is precisely the asymmetry the rectangle describes.

    Under a rotation there is no rectangle to hand back -- the data region is
    genuinely turned -- so what comes back is the upright box around it, which
    over-reports the extent and reports the *centre* exactly. The centre is
    what `row`, `column` and `facets` line panels up on, so a turned panel
    still aligns; a caller measuring the region's width off a rotated node is
    reading the box, and the note is not the tool for that. Core's
    `note_through` is the one implementation, shared with the note carry a
    transform wrapper performs (M19).

    None when the node never declared one, which is every node that is not a
    panel or a grid of panels.
    """
    area = getattr(node, "notes", {}).get(AREA_NOTE)
    if area is None:
        return None
    return note_through(node.transform, area)


def declare_area(node: Diagram, area: Rect) -> Diagram:
    """Record `area` on `node`, with the matching `area-nw`/`area-se` anchors.

    In the node's own drawn frame -- see `plot_area` for the frame the reader
    gets it back in. `note` is core M17, so it is read defensively: a build of
    inklet without it still gets the anchors.
    """
    node.anchor("area-nw", Vec2(area.x0, area.y0))
    node.anchor("area-se", Vec2(area.x1, area.y1))
    note = getattr(node, "note", None)
    if callable(note):
        note(AREA_NOTE, area)
    return node
