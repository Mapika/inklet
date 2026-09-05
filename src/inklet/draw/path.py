"""Polylines, polygons and smooth curves.

`path()` is the escape hatch: whatever you can express as one subpath, you can
draw. Everything else in this module is a shorter way of calling it.

Curves are the part with a contract to keep. `Subpath` carries two
representations of the same geometry -- `points`, the flattening every
measurement in core works from, and `curves`, the exact cubics the SVG backend
draws. They must agree, and `curves`, when present at all, must cover the
*whole* subpath: a renderer that finds them ignores `points` entirely, so a
chain that only describes the interesting parts silently drops the straight
runs between them. Straight segments are emitted here as cubics whose controls
lie on their own chord.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from ..core import Diagram, PathPrim, Rect, Subpath, Vec2
from .coords import Point, drawn, to_points

__all__ = ["curve", "encoded", "path", "polygon", "polyline"]

EPS = 1e-9

# Samples per cubic in the flattened form. Eight is where the error of a
# quarter-circle drops under a micrometre at figure sizes, which is well past
# the point where an envelope or a ray hit could notice; going further only
# gives the linter more points to chew on.
FLATTEN_STEPS = 8

PATH_KIND = "path"

# Kinds ending here declare that the node's *stroke width* carries a value.
ENCODED_KIND_SUFFIX = "-encoded"


def encoded(kind: str = PATH_KIND) -> str:
    """Mark a kind as one whose stroke width is data rather than design.

    A Sankey ribbon, a graph edge scaled by projection strength, a contour
    scaled by level: there the width *is* the measurement, and a figure that
    draws twenty of them has made one design decision, not twenty. Nothing
    about drawing changes; this only tells the weight-consistency check that
    the spread is a scale::

        inklet.polyline(pts, kind=inklet.encoded("connector"), stroke_width=w)

    The prefix survives, so every other rule still sees a connector.
    """
    if not isinstance(kind, str):
        raise TypeError(
            f"encoded() takes a kind name, not {type(kind).__name__} "
            f"({kind!r}); write inklet.polyline(pts, kind=inklet.encoded('connector'))"
        )
    return kind if is_encoded_kind(kind) else kind + ENCODED_KIND_SUFFIX


def is_encoded_kind(kind: str) -> bool:
    return kind.endswith(ENCODED_KIND_SUFFIX)

Cubic = tuple[Vec2, Vec2, Vec2, Vec2]


def path(points: Iterable[Point] = (), *, closed: bool = False,
         curves: Sequence[Sequence[Point]] | None = None,
         holes: Sequence[Iterable[Point]] = (),
         filled: bool | None = None, fill_rule: str = "nonzero",
         kind: str = PATH_KIND, **style) -> Diagram:
    """One subpath, exactly as given -- plus any rings cut out of it.

    `points` is the flattened form. `curves` is an optional chain of cubics
    `(p0, c1, c2, p3)` that must be contiguous and must span the whole path;
    give it and the backend draws real beziers. Either may be omitted: with no
    `curves` this is a polyline, and with no `points` the flattening is
    computed from the cubics.

    `filled` decides whether the interior is paintable at all; it defaults to
    True when the call passes a `fill`, so `path(pts, closed=True, fill="#eee")`
    does what it looks like.

    `holes` are further closed rings on the *same* prim, which is what makes
    them holes rather than two shapes lying on each other: a washer is one
    object, it clips as one object, and a ray leaves it through the outside.
    Two rings in one prim mean nothing without a rule for reading them, and
    that is `fill_rule` (core M14): the default `"nonzero"` needs the inner
    ring wound against the outer, while `"evenodd"` cuts the hole whichever way
    it was drawn -- the right choice for a ring whose winding came from data or
    from a tracer. It is a property of the geometry, not of the paint, so it
    lives on the prim and not in `Style`; passing it as a style keyword used to
    raise from `Style.__init__` with no hint that the field existed at all.
    """
    chain = _check_curves(curves)
    pts = to_points(points)
    if not pts and chain:
        pts = _flatten(chain, closed)
    if not pts:
        raise ValueError("a path needs at least one point")
    if chain:
        _check_ends(pts, chain, closed)
    rings = [to_points(ring) for ring in holes]
    if any(len(ring) < 3 for ring in rings):
        raise ValueError("a hole needs at least three points")

    centre = Rect.hull(list(pts) + [p for ring in rings for p in ring]).center
    subs = [Subpath(
        points=tuple(p - centre for p in pts),
        closed=closed,
        curves=tuple(tuple(q - centre for q in c) for c in chain),
    )]
    subs += [Subpath(tuple(p - centre for p in ring), closed=True)
             for ring in rings]
    if filled is None:
        filled = style.get("fill") not in (None, "none")
    prim = PathPrim(tuple(subs), filled=bool(filled), fill_rule=fill_rule)
    return drawn(prim, -centre, kind, style)


def polyline(points: Iterable[Point], **kwargs) -> Diagram:
    """An open run of straight segments."""
    kwargs.setdefault("closed", False)
    return path(points, **kwargs)


def polygon(points: Iterable[Point], **kwargs) -> Diagram:
    """A closed run of straight segments, fillable.

    `holes=[ring, ...]` and `fill_rule="evenodd"` make it a washer; see `path`.
    """
    kwargs.setdefault("closed", True)
    kwargs.setdefault("filled", True)
    return path(points, **kwargs)


def curve(points: Iterable[Point], *, smooth: float = 0.5,
          closed: bool = False, **kwargs) -> Diagram:
    """A Catmull-Rom spline through every point, as real cubics.

    The curve passes exactly through its control points -- that is what
    Catmull-Rom is for, and what makes it the right interpolant for data.
    `smooth` is the tension: 0 reproduces the polyline, 0.5 is the classical
    uniform Catmull-Rom, and beyond about 0.7 the overshoot between close
    points starts to look like a claim the data did not make.
    """
    pts = to_points(points)
    if len(pts) < 2:
        raise ValueError(f"a curve needs at least two points, got {len(pts)}")
    if smooth < 0.0:
        raise ValueError(f"smooth must not be negative, got {smooth}")
    chain = catmull_rom(pts, smooth, closed)
    return path(_flatten(chain, closed), closed=closed, curves=chain, **kwargs)


def catmull_rom(points: Sequence[Vec2], smooth: float,
                closed: bool = False) -> tuple[Cubic, ...]:
    """Catmull-Rom control points as a chain of cubic beziers.

    The tangent at Pi is (P(i+1) - P(i-1)) scaled by `smooth`, and a cubic's
    control point sits a third of the way along its own tangent -- hence the
    /3. At smooth=0.5 that is the textbook (P(i+1) - P(i-1))/6.

    An open curve has no neighbour beyond its ends, so the end point stands in
    for the one that is missing; the alternative, reflecting the interior
    point, bends the ends outward in a way that reads as data.
    """
    n = len(points)
    scale = smooth / 3.0
    chain: list[Cubic] = []
    last = n if closed else n - 1
    for i in range(last):
        p0 = points[i]
        p3 = points[(i + 1) % n]
        before = points[(i - 1) % n] if closed or i > 0 else p0
        after = points[(i + 2) % n] if closed or i + 2 < n else p3
        chain.append((p0, p0 + (p3 - before) * scale, p3 - (after - p0) * scale, p3))
    return tuple(chain)


def straight_cubic(p0: Vec2, p3: Vec2) -> Cubic:
    """A cubic that is exactly its own chord, for the straight runs a `curves`
    chain has to cover to stay whole."""
    step = (p3 - p0) * (1 / 3)
    return (p0, p0 + step, p0 + step * 2, p3)


def bezier(p0: Vec2, c1: Vec2, c2: Vec2, p3: Vec2, t: float) -> Vec2:
    u = 1.0 - t
    return (p0 * (u * u * u) + c1 * (3 * u * u * t)
            + c2 * (3 * u * t * t) + p3 * (t * t * t))


def flatten_cubic(cubic: Cubic, steps: int = FLATTEN_STEPS) -> list[Vec2]:
    """Samples after the start point, up to and including the end point."""
    p0, c1, c2, p3 = cubic
    return [bezier(p0, c1, c2, p3, i / steps) for i in range(1, steps + 1)]


def _flatten(chain: Sequence[Cubic], closed: bool,
             steps: int = FLATTEN_STEPS) -> tuple[Vec2, ...]:
    """The polyline core measures from. Bezier evaluation is exact at t=0 and
    t=1, so every knot survives the flattening untouched -- which is the whole
    reason a Catmull-Rom curve can be said to pass through its points."""
    if not chain:
        return ()
    pts = [chain[0][0]]
    for cubic in chain:
        pts.extend(flatten_cubic(cubic, steps))
    if closed and (pts[-1] - pts[0]).length <= EPS:
        pts.pop()      # `Subpath(closed=True)` draws that segment itself
    return tuple(pts)


def _check_curves(curves) -> tuple[Cubic, ...]:
    if not curves:
        return ()
    chain: list[Cubic] = []
    for index, cubic in enumerate(curves):
        pts = to_points(cubic)
        if len(pts) != 4:
            raise ValueError(
                f"cubic {index} has {len(pts)} points; a cubic is "
                "(start, control, control, end)"
            )
        if chain and (pts[0] - chain[-1][3]).length > EPS:
            raise ValueError(
                f"cubic {index} starts at {pts[0]} but cubic {index - 1} ended "
                f"at {chain[-1][3]}; a curve chain has to be contiguous"
            )
        chain.append((pts[0], pts[1], pts[2], pts[3]))
    return tuple(chain)


def _check_ends(points: Sequence[Vec2], chain: Sequence[Cubic],
                closed: bool) -> None:
    """The renderer draws `curves` and ignores `points` when both are present,
    so a chain that does not span the same geometry is a silent corruption."""
    if (points[0] - chain[0][0]).length > EPS:
        raise ValueError(
            f"the curve chain starts at {chain[0][0]} but the path starts at "
            f"{points[0]}; curves must cover the whole path"
        )
    tail = chain[-1][3]
    end = points[0] if closed else points[-1]
    if (end - tail).length > EPS:
        raise ValueError(
            f"the curve chain ends at {tail} but the path ends at {end}; "
            "curves must cover the whole path, straight runs included"
        )
