"""Arcs, wedges and the seven marker glyphs.

Angles are degrees measured from east and increasing *clockwise on the page*,
because y grows downward here as it does in SVG. Twelve o'clock is -90. This
is the same surprising constant core already pays for, and paying it once is
cheaper than having two conventions in one library.

An arc's `origin` anchor is the centre of its circle rather than the centre of
its bounding box, so `place()` puts a wedge exactly where its pie belongs
without anyone computing the offset of a chord.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import (
    Diagram, EllipsePrim, ORIGIN, PathPrim, Rect, RectPrim, Subpath, Vec2, mm,
)
from .coords import Point, active_theme, drawn, to_point
from .path import Cubic, EPS, path, straight_cubic

__all__ = ["MARKER_KINDS", "arc", "marker", "sector"]

ARC_KIND = "path"
# Two kinds, because the theme has to style them differently: an area mark
# is filled and unstroked, a line mark is stroked and unfilled, and a cross
# given the filled treatment would vanish.
MARK_KIND = "mark"
MARK_LINE_KIND = "mark-line"

MARKER_KINDS = ("circle", "square", "triangle", "diamond", "cross", "plus", "star")
_STROKE_MARKERS = ("cross", "plus")

# A marker's `size` is the diameter of the circle with the same area, so glyphs
# that stand for interchangeable series carry interchangeable weight. Drawn to
# a common bounding box instead, a square lays down 27% more ink than a circle
# and reads as a different emphasis. These are sqrt(pi/4 / shape_area_at_unit).
_SQUARE_SIDE = math.sqrt(math.pi) / 2                 # 0.8862
_DIAMOND_DIAGONAL = math.sqrt(math.pi / 2)            # 1.2533
_TRIANGLE_SIDE = math.sqrt(math.pi / math.sqrt(3.0))  # 1.3468
# A five-pointed star with this waist has area 5*k*sin(36 deg) per unit radius.
_STAR_WAIST = math.cos(math.radians(72)) / math.cos(math.radians(36))   # 0.3820
_STAR_RADIUS = math.sqrt(
    math.pi / 4 / (5 * _STAR_WAIST * math.sin(math.radians(36))))       # 0.8365

# Markers a reader is meant to see at a glance, without them eating the plot.
# Tied to type size rather than to a fixed millimetre value: a marker that
# outweighs the tick labels beside it is a marker drawn at the wrong scale.
_MARKER_OF_TYPE = 0.62

_MAX_ARC_SPAN = 90.0   # degrees per cubic; the kappa error is nil at 90, poor at 180


def arc(radius: float | str, start: float, end: float, *,
        closed: bool = False, kind: str = ARC_KIND, **style) -> Diagram:
    """A circular arc from `start` to `end` degrees, as real cubics.

    `closed` shuts the chord, giving a circular segment; for the wedge from the
    centre, use `sector`.
    """
    r = mm(radius)
    if r <= 0:
        raise ValueError(f"an arc needs a positive radius, got {radius!r}")
    chain = arc_cubics(ORIGIN, r, start, end)
    if not chain:
        raise ValueError(f"an arc of {end - start} degrees has no length")
    if closed:
        chain = chain + (straight_cubic(chain[-1][3], chain[0][0]),)
    return path(curves=chain, closed=closed, kind=kind, **style)


def sector(radius: float | str, start: float, end: float, *,
           inner: float | str = 0.0, kind: str = ARC_KIND,
           **style) -> Diagram:
    """The wedge between two angles: a pie slice, or a ring segment with
    `inner` set. Filled by default, since a sector is an area."""
    outer = mm(radius)
    hole = mm(inner)
    if outer <= 0:
        raise ValueError(f"a sector needs a positive radius, got {radius!r}")
    if not 0 <= hole < outer:
        raise ValueError(f"inner radius {inner!r} must be inside {radius!r}")

    chain = list(arc_cubics(ORIGIN, outer, start, end))
    if not chain:
        raise ValueError(f"a sector of {end - start} degrees has no area")
    if hole > 0:
        back = arc_cubics(ORIGIN, hole, end, start)
        chain.append(straight_cubic(chain[-1][3], back[0][0]))
        chain.extend(back)
    else:
        chain.append(straight_cubic(chain[-1][3], ORIGIN))
    chain.append(straight_cubic(chain[-1][3], chain[0][0]))

    style.setdefault("filled", True)
    return path(curves=tuple(chain), closed=True, kind=kind, **style)


def arc_cubics(centre: Vec2, radius: float, start: float, end: float,
               max_span: float = _MAX_ARC_SPAN) -> tuple[Cubic, ...]:
    """Split a sweep into cubics of at most `max_span` degrees.

    The control-point distance is (4/3)tan(d/4) of the radius, which is exact
    at the endpoints and tangents for any span and worst in the middle; at 90
    degrees the largest radial error is about 0.03% of the radius, which at a
    20mm radius is 6 micrometres.
    """
    sweep = end - start
    if abs(sweep) <= EPS:
        return ()
    count = max(1, math.ceil(abs(sweep) / max_span - 1e-9))
    step = sweep / count
    k = 4.0 / 3.0 * math.tan(math.radians(step) / 4.0) * radius
    chain: list[Cubic] = []
    for i in range(count):
        a0 = math.radians(start + step * i)
        a1 = math.radians(start + step * (i + 1))
        p0 = centre + Vec2(math.cos(a0), math.sin(a0)) * radius
        p3 = centre + Vec2(math.cos(a1), math.sin(a1)) * radius
        chain.append((
            p0,
            p0 + Vec2(-math.sin(a0), math.cos(a0)) * k,
            p3 - Vec2(-math.sin(a1), math.cos(a1)) * k,
            p3,
        ))
    return tuple(chain)


def marker(kind: str = "circle", size: float | str | None = None,
           **style) -> Diagram:
    """One data glyph, centred on its own origin so `place()` lands it on the
    point it stands for.

    `size` is the glyph's nominal diameter: the circle is exactly that wide and
    the filled shapes are scaled to the same area, so swapping one for another
    does not change how heavy a series looks. `cross` and `plus` are strokes
    rather than areas, and carry the same *length* of line as each other.
    """
    if isinstance(kind, (int, float)):
        # The first argument is the glyph, not the size, and a number here is
        # never anything but that mistake.
        raise TypeError(
            f"marker() takes the glyph name first: write "
            f"marker('circle', {kind!r}) for a {kind}mm circle"
        )
    if kind not in MARKER_KINDS:
        raise ValueError(
            f"unknown marker {kind!r}; known markers are {', '.join(MARKER_KINDS)}"
        )
    s = _MARKER_OF_TYPE * active_theme().font_size if size is None else mm(size)
    if s <= 0:
        raise ValueError(f"a marker needs a positive size, got {size!r}")
    builder = _MARKERS[kind]
    prim = builder(s)
    node_kind = MARK_LINE_KIND if kind in _STROKE_MARKERS else MARK_KIND
    return drawn(prim, ORIGIN, node_kind, style)


def _circle_prim(s: float) -> EllipsePrim:
    return EllipsePrim(s / 2, s / 2)


def _square_prim(s: float) -> RectPrim:
    return RectPrim(s * _SQUARE_SIDE, s * _SQUARE_SIDE)


def _diamond_prim(s: float) -> PathPrim:
    h = s * _DIAMOND_DIAGONAL / 2
    return _closed(((0.0, -h), (h, 0.0), (0.0, h), (-h, 0.0)), filled=True)


def _triangle_prim(s: float) -> PathPrim:
    side = s * _TRIANGLE_SIDE
    height = side * math.sqrt(3.0) / 2
    # Centred on the bounding box, not the centroid: a row of markers reads by
    # its silhouette, and a centroid-centred triangle sits visibly low.
    top, bottom = -height / 2, height / 2
    return _closed(((0.0, top), (side / 2, bottom), (-side / 2, bottom)), filled=True)


def _star_prim(s: float) -> PathPrim:
    outer = s * _STAR_RADIUS
    points = []
    for i in range(10):
        angle = math.radians(-90 + 36 * i)
        r = outer if i % 2 == 0 else outer * _STAR_WAIST
        points.append(Vec2(math.cos(angle) * r, math.sin(angle) * r))
    # A star is not vertically symmetric about its own circumcentre -- the
    # single top point reaches further than the two bottom ones -- so it is
    # recentred on its silhouette, for the same reason the triangle is.
    middle = Rect.hull(points).center
    return _closed([p - middle for p in points], filled=True)


def _cross_prim(s: float) -> PathPrim:
    h = s / 2 * math.sqrt(0.5)   # a diagonal arm covers more ground per mm of x
    return PathPrim((
        Subpath((Vec2(-h, -h), Vec2(h, h))),
        Subpath((Vec2(-h, h), Vec2(h, -h))),
    ), filled=False)


def _plus_prim(s: float) -> PathPrim:
    h = s / 2
    return PathPrim((
        Subpath((Vec2(-h, 0.0), Vec2(h, 0.0))),
        Subpath((Vec2(0.0, -h), Vec2(0.0, h))),
    ), filled=False)


_MARKERS = {
    "circle": _circle_prim,
    "square": _square_prim,
    "triangle": _triangle_prim,
    "diamond": _diamond_prim,
    "cross": _cross_prim,
    "plus": _plus_prim,
    "star": _star_prim,
}


def _closed(points: Sequence[Point], filled: bool) -> PathPrim:
    pts = tuple(to_point(p) for p in points)
    return PathPrim((Subpath(pts, closed=True),), filled=filled)
