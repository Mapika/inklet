"""Drawing on top of a projected 3D scene, in the scene's own coordinates.

`inklet.three.anchor3d` puts a 3D point on a scene and `anchor_point` reads it
back as millimetres, which is everything a leader line or a dashed pocket ring
needs. Two things about composition are worth knowing before any of it works,
because both fail silently and both look like a wrong anchor.

`overlay` centres each item's bounding box on the next, so an annotation off to
one side gets pulled back to the middle. Everything here goes through `place`,
which takes explicit coordinates and does not.

And `inklet.polyline([a, b])` does **not** keep `a` and `b`: every shape in
`inklet.draw` is rewritten to sit on its own origin, and the frame it was drawn in
is remembered as an anchor. `inklet.drawn(items)` -- and `place`, handed a bare
diagram rather than a pair -- undoes that, putting each shape back at the
coordinates it was drawn in. So `stroke()` below returns the shape itself and
`on()` is one `drawn` call; neither has to re-derive a position from a bounding
box, which is what the old `centre_of` helper here was doing and what broke as
soon as a shape's envelope was wider than its points.
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

import inklet

Item = tuple[tuple[float, float], inklet.Diagram] | inklet.Diagram


def on(scene: inklet.Diagram, *items: Item) -> inklet.Diagram:
    """`items`, already positioned in `scene`'s coordinates, drawn over it.

    A `(point, diagram)` pair puts that diagram's centre on that point; a bare
    diagram is one that already carries its coordinates, and goes back where it
    was drawn. `inklet.drawn` keeps the whole group in the scene's frame, so the
    result can be composed with another group drawn from the same numbers.
    """
    return inklet.drawn([scene, *items])


def at(scene: inklet.Diagram, name: str) -> tuple[float, float]:
    """A named anchor as a plain pair, which is what `place` wants."""
    point = scene.anchor_point(name)
    return point.x, point.y


def stroke(points: Sequence[Sequence[float]], *,
           make: Callable[..., inklet.Diagram] | None = None,
           **style) -> inklet.Diagram:
    """A path through absolute coordinates, still carrying those coordinates.

    Just the shape: `inklet.drawn` and `inklet.place` both put a bare diagram back
    where it was drawn, so there is nothing left for this to compute.
    """
    build = make or inklet.polyline
    return build(list(points), **style)


def text_at(content: str, where: Sequence[float], *, plate: str | None = None,
            pad: float = 0.35, **style) -> Item:
    """Text at a point. `plate` fills a rectangle behind it, in that colour.

    A number written over a drawing is unreadable and the linter says so twice
    -- once for the overlap and once for the contrast against whatever it
    landed on. The plate answers both, and it is what a structure figure does
    anyway: the measurement belongs to the reader, not to the molecule.
    """
    body = inklet.text(content, **style)
    if plate is None:
        return tuple(where), body
    return tuple(where), inklet.box(body, pad=pad, fill=plate, stroke="none")


def ring(centre: Sequence[float], width: float, height: float, *,
         name: str | None = None, **style) -> Item:
    """A dashed ellipse round a region, for the thing a zoom is a zoom of.

    `inklet.circle` is `box` underneath and takes style, not `kind`, so an ellipse
    that wants to be tagged as furniture is built from an arc instead.
    """
    kind = style.pop("kind", None)
    if kind is None:
        made = inklet.circle(width=width, height=height, fill="none", **style)
    else:
        points = [(width / 2 * math.cos(t * math.pi / 32),
                   height / 2 * math.sin(t * math.pi / 32)) for t in range(64)]
        made = inklet.polygon(points, fill="none", kind=kind, **style)
    return tuple(centre), made.named(name) if name else made


def leader(content: str | inklet.Diagram, target: Sequence[float],
           label_at: Sequence[float], *, size: float | None = None,
           ink: str | None = None, stroke_width: float | None = None,
           gap: float = 0.8, kind: str = "label",
           through: Sequence[inklet.Diagram] = ()) -> list[Item]:
    """A label away from the thing it names, with a line back to it.

    The line stops `gap` short of the label so the two never touch, which is
    what makes a leader read as pointing rather than as part of the drawing.
    Returns `place` items, so a caller can hand a whole list to `on()`.

    `content` may be a diagram rather than a string, for a label that is more
    than one run of type -- a name in the ink colour beside a measurement in
    the colour of the thing measured.

    `through` names the shapes this line is *meant* to cross, which a callout
    into a buried pocket always has to: the assembly in front of it is what
    "buried" means. It declares that and nothing more, via `inklet.crossing`, so
    the label at the far end goes on being measured for crowding against the
    very same model -- unlike `inklet.abutting` round the leader and the scene,
    which is the wider claim this replaces.
    """
    theme = inklet.current_theme()
    body = (content if isinstance(content, inklet.Diagram) else
            inklet.text(content, size=size or theme.font_size_small, kind=kind,
                     text_fill=ink or theme.ink))
    tx, ty = label_at
    dx, dy = tx - target[0], ty - target[1]
    span = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    # Stop at the label's own edge rather than its centre, measured along the
    # line: an ellipse of the text's half-width and half-height, which is close
    # enough for a leader and never leaves the line poking out of a corner.
    reach = (abs(dx) / span * body.width / 2 + abs(dy) / span * body.height / 2)
    stop = (tx - dx / span * (reach + gap), ty - dy / span * (reach + gap))
    line = stroke([tuple(target), stop], stroke=ink or theme.muted,
                  stroke_width=stroke_width or theme.hairline, kind="leader")
    if through:
        inklet.crossing(line, *through)
    return [line, ((tx, ty), body)]


def zoom(scene: inklet.Diagram, centre: Sequence[float], width: float,
         height: float, **style) -> inklet.Diagram:
    """A window cut out of a projected scene, re-centred on its own origin.

    A real crop of the same projection, not a second drawing of the same thing
    at a bigger size: render the scene once at the magnification the zoom wants
    and cut a rectangle out of it. Anything else and the reader has no way to
    know whether the enlargement is faithful.

    `strict=True`, because the region here is a window onto something larger
    rather than a plot area, so a mark half outside it should go rather than
    hang over the edge.
    """
    cx, cy = centre
    box = inklet.Rect(cx - width / 2, cy - height / 2,
                   cx + width / 2, cy + height / 2)
    return inklet.clip(scene, box, strict=True, **style).translated(-cx, -cy)


def moved(centre: Sequence[float], point: Sequence[float]) -> tuple[float, float]:
    """A point from the uncropped scene, in the coordinates `zoom` returns."""
    return point[0] - centre[0], point[1] - centre[1]


def origin_of(built: inklet.Diagram) -> tuple[float, float]:
    """Where a built panel's plot-area centre lands once `place` has centred it.

    `Panel.build` puts an `origin` anchor on the middle of the plot area, and
    `place` positions by bounding box -- which includes the axis labels, so the
    two differ by however wide the y labels happen to be. Anything that has to
    line up with the data rather than with the panel's outline needs this
    offset: a number-at-risk table under a survival plot, a bracket over a bar.
    """
    anchor = built.anchor_point("origin")
    middle = built.bbox.center
    return anchor.x - middle.x, anchor.y - middle.y
