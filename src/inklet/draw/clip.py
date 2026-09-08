"""Geometric clipping and explicit painted windows in local millimetres."""

from __future__ import annotations

import math
from dataclasses import replace

from typing import Iterable, Sequence

from ..core import (
    IDENTITY, Affine, Diagram, Envelope, PathPrim, Rect, RectPrim, Subpath, Vec2,
)
from .coords import Point, to_points

__all__ = ["window", "clip", "clip_polyline", "clip_polygon"]

CLIP_KIND = "clip"

EPS = 1e-9

#: Prims whose outline this module can rewrite exactly.
_EXACT = (PathPrim, RectPrim)


def clip(items: Diagram | Iterable[Diagram],
         region: Rect | Sequence[Point], *, kind: str = CLIP_KIND,
         strict: bool = False, **style) -> Diagram:
    """Cut `items` down to `region`, in the coordinate frame you pass it in.

    `region` is a `Rect` or a **convex** polygon. Convexity is checked, because
    Sutherland-Hodgman against a concave boundary produces a plausible-looking
    wrong answer rather than an error, and a wrong answer here is a figure that
    lies.

    Straight paths and square rectangles are cut geometrically. Text, images and ellipses -- which
    includes every `marker()` -- cannot be, so by default they are kept whole
    when they touch the region at all and dropped when they do not: a scatter
    point on the boundary stays a round dot half outside the axes, the way a
    journal draws it. `strict=True` drops those too, which is what you want
    when the region is a window onto something larger rather than a plot area.

    Anything that falls entirely inside is passed through *unchanged*, so the
    handle you are holding stays the node in the tree and `fig.link` can still
    find it. Anything actually cut is necessarily a new node.

    Open cubic curves retain exact subdivided controls. Their measurement
    polylines have a 0.0001 mm tolerance in the clip frame. Filled curves still
    use polygon geometry; use `window` to retain the original painted curves,
    rounded corners, stroke caps and fill topology without rewriting them.
    """
    nodes = [items] if isinstance(items, Diagram) else list(items)
    edges, box = _region(region)
    kept = [n for n in (_clip_node(n, IDENTITY, edges, box, strict)
                        for n in nodes) if n is not None]
    node = Diagram(children=tuple(kept), kind=kind)
    return node.styled(**style) if style else node


def window(items: Diagram | Iterable[Diagram], region: Rect | Sequence[Point],
           *, kind: str = "window", **style) -> Diagram:
    """Crop painted content to a fixed convex window, in local millimetres.

    SVG, PDF and PNG clip every paint, including images, glyphs, markers and
    stroke widths. Children and their handles remain unchanged. Layout and the
    window's connector trace reserve the complete window, even if empty.
    Child anchors still refer to authored geometry. `resolve` and `flatten`
    expose inherited world-space clip regions and `visible_at(point)` for
    consumers that need to filter picking; they do not remove source records.
    """
    edges, box = _region(region)
    nodes = (items,) if isinstance(items, Diagram) else tuple(items)
    node = Diagram(children=nodes, kind=kind,
                   clip_region=tuple(a for a, _ in edges),
                   envelope_override=Envelope.from_rect(box))
    return node.styled(**style) if style else node


# -- the region -----------------------------------------------------------

def _region(region: Rect | Sequence[Point]) -> tuple[tuple, Rect]:
    if isinstance(region, Rect):
        points = region.corners
    else:
        _refuse_flat_rect(region)
        points = to_points(region)
    if any(not math.isfinite(v) for p in points for v in (p.x, p.y)):
        raise ValueError("clip region coordinates must be finite")
    ring = _dedupe(points)
    if len(ring) < 3:
        raise ValueError(
            f"a clip region needs at least three distinct corners, got {len(ring)}")
    if abs(_signed_area(ring)) <= EPS:
        raise ValueError("clip region must have positive area")
    if not _is_convex(ring):
        raise ValueError(
            "clip regions must be convex; a concave one would be silently "
            "clipped to its own hull. Clip against each convex piece instead."
        )
    if _signed_area(ring) < 0.0:
        ring = tuple(reversed(ring))
    return tuple(zip(ring, ring[1:] + ring[:1])), Rect.hull(ring)


def _refuse_flat_rect(region) -> None:
    """`clip(d, (0, 0, 10, 10))` is a rectangle written the other way round,
    and reads as four malformed points three frames down."""
    if (isinstance(region, (tuple, list)) and len(region) == 4
            and all(isinstance(v, (int, float)) for v in region)):
        raise TypeError(
            f"a clip region is a inklet.Rect or a ring of corner points; "
            f"{tuple(region)} looks like a rectangle -- write "
            f"inklet.Rect{tuple(float(v) for v in region)}"
        )


def _dedupe(points: Sequence[Vec2]) -> tuple[Vec2, ...]:
    out: list[Vec2] = []
    for p in points:
        if not out or (p - out[-1]).length > EPS:
            out.append(p)
    while len(out) > 1 and (out[0] - out[-1]).length <= EPS:
        out.pop()
    return tuple(out)


def _signed_area(ring: Sequence[Vec2]) -> float:
    return 0.5 * sum(a.cross(b) for a, b in zip(ring, tuple(ring[1:]) + (ring[0],)))


def _is_convex(ring: Sequence[Vec2]) -> bool:
    """No sign change in the cross products around the ring.

    Collinear runs are ignored rather than rejected: a rectangle described with
    a redundant midpoint on one side is still a rectangle.
    """
    sign = 0
    n = len(ring)
    for i in range(n):
        a, b, c = ring[i], ring[(i + 1) % n], ring[(i + 2) % n]
        cross = (b - a).cross(c - b)
        if abs(cross) <= EPS:
            continue
        here = 1 if cross > 0.0 else -1
        if sign and here != sign:
            return False
        sign = here
    return True


def _inside(point: Vec2, edge: tuple[Vec2, Vec2]) -> float:
    """Signed distance-ish: positive inside, negative outside, zero on the line."""
    a, b = edge
    return (b - a).cross(point - a)


# -- the walk -------------------------------------------------------------

def _clip_node(node: Diagram, to_clip: Affine, edges, box: Rect,
               strict: bool) -> Diagram | None:
    """Cut one node, keeping its own transform and its children's structure.

    Geometry is clipped in the region's frame and mapped straight back into the
    node's local frame, so the tree that comes out has the same shape as the
    one that went in. Only the primitives that were actually cut are new.
    """
    here = to_clip @ node.transform
    reach = _bbox_in(node, here)
    if reach is None or not _touching(box, reach):
        return None
    if _within(reach, edges):
        return node                       # untouched, so the caller's handle lives

    try:
        home = here.inverse()
    except ValueError:
        # A collapsed transform has no frame to map back into. It draws nothing
        # measurable either, so dropping it is the honest answer.
        return None

    prim = node.prim
    if prim is not None:
        if isinstance(prim, _EXACT):
            prim = _clip_prim(prim, here, home, edges)
        elif strict:
            prim = None
        # Otherwise a glyph, a photograph or a marker: it touches the region,
        # so it is kept whole. `clip`'s docstring is where that is promised.

    children = tuple(kid for kid in (_clip_node(c, here, edges, box, strict)
                                     for c in node.children) if kid is not None)
    if prim is None and not children:
        return None
    if prim is node.prim and children == node.children:
        return node
    return replace(node, prim=prim, children=children, id="", _cache={})


def _bbox_in(node: Diagram, world: Affine) -> Rect | None:
    # A sampled envelope can miss a cubic excursion between samples. Cache a
    # conservative control hull separately; normal layout remains unchanged.
    key = "clip_control_bounds"
    if key not in node._cache:
        local = node.prim.envelope().bbox() if node.prim is not None else None
        if isinstance(node.prim, PathPrim):
            controls = [p for sub in node.prim.subpaths for c in sub.curves for p in c]
            if controls:
                hull = Rect.hull(controls)
                local = hull if local is None else local.union(hull)
        for child in node.children:
            other = _bbox_in(child, child.transform)
            if other is not None:
                local = other if local is None else local.union(other)
        node._cache[key] = local
    box = node._cache[key]
    if box is None:
        return None
    return Rect.hull([world.apply(c) for c in box.corners])


def _touching(box: Rect, reach: Rect) -> bool:
    return (reach.x0 <= box.x1 + EPS and reach.x1 >= box.x0 - EPS
            and reach.y0 <= box.y1 + EPS and reach.y1 >= box.y0 - EPS)


def _within(reach: Rect, edges) -> bool:
    return all(_inside(c, e) >= -EPS for c in reach.corners for e in edges)


def _clip_prim(prim, world: Affine, home: Affine, edges):
    if isinstance(prim, PathPrim):
        return _clip_path(prim, world, home, edges)
    return _clip_rect(prim, world, home, edges)


def _clip_path(prim: PathPrim, world: Affine, home: Affine,
               edges) -> PathPrim | None:
    """Cut one path, filled rings together and open runs one at a time.

    The rings of a filled path are one shape -- an outer ring and the ring of
    a hole in it mean nothing apart -- so they are cut as a set, which is also
    what lets a cut that separates them come back as separate rings. Open runs
    have no interior and are cut individually.
    """
    out: list[Subpath] = []
    rings = ([i for i, sub in enumerate(prim.subpaths) if sub.closed]
             if prim.filled else [])
    ring_set, first = set(rings), rings[0] if rings else -1
    for index, sub in enumerate(prim.subpaths):
        if index in ring_set:
            if index == first:
                out.extend(_clip_rings_of(prim, rings, world, home, edges))
            continue
        if sub.curves:
            from .bezier_clip import clip_curves
            out.extend(clip_curves(sub.curves, world, home, edges, closed=sub.closed))
            continue
        pts = [world.apply(p) for p in sub.points]
        for piece in clip_polyline(pts, edges, closed=sub.closed):
            if len(piece) >= 2:
                out.append(Subpath(tuple(home.apply(p) for p in piece), False))
    if not out:
        return None
    # `fill_rule` (M14) is part of what the path *means*: the same rings under
    # evenodd and under nonzero are two different shapes. `_clip_rings_of`
    # re-winds the rings so the cut comes out nonzero-correct, which is the
    # rule the clip itself works in, but the caller asked for a shape and the
    # answer has to be that shape -- so the declared rule rides along.
    # `getattr` because this file has to build against a core that predates it.
    return PathPrim(tuple(out), filled=prim.filled,
                    fill_rule=getattr(prim, "fill_rule", "nonzero"))


def _clip_rings_of(prim: PathPrim, rings: list[int], world: Affine,
                   home: Affine, edges) -> list[Subpath]:
    """The filled rings of `prim`, cut as one shape.

    Winding is what tells a hole from an outline under the nonzero fill rule
    every backend here uses, so the shape is turned the right way up before
    the cut and turned back afterwards: the algorithm needs "interior on the
    left" to know which way to run along the cut, and an author who drew their
    outline clockwise must still get their own winding back.
    """
    subject = [[world.apply(p) for p in prim.subpaths[i].points] for i in rings]
    reversed_ = sum(_signed_area(r) for r in subject) < 0.0
    if reversed_:
        subject = [list(reversed(r)) for r in subject]
    cut = clip_rings(subject, edges)
    if reversed_:
        cut = [list(reversed(r)) for r in cut]
    return [Subpath(tuple(home.apply(p) for p in ring), True)
            for ring in cut if len(ring) >= 3]


def _clip_rect(prim: RectPrim, world: Affine, home: Affine,
               edges) -> PathPrim | None:
    box = Rect(-prim.width / 2.0, -prim.height / 2.0,
               prim.width / 2.0, prim.height / 2.0)
    ring = clip_polygon([world.apply(c) for c in box.corners], edges)
    if len(ring) < 3:
        return None
    # A cut corner is no longer a rounded rectangle, and pretending otherwise
    # would round the *new* corners the clip just made.
    return PathPrim((Subpath(tuple(home.apply(p) for p in ring), True),),
                    filled=True)


# -- the two algorithms ---------------------------------------------------

def polygon_area(points: Sequence[Vec2]) -> float:
    """Unsigned area of a ring, zero for anything under three points."""
    ring = _dedupe(points)
    return abs(_signed_area(ring)) if len(ring) >= 3 else 0.0


def area_within(points: Sequence[Point], region: Rect | Sequence[Point]) -> float:
    """How much of a polygon lies inside a convex region.

    Written for the linter rather than for drawing. A Sankey ribbon's bounding
    box is mostly empty, so `bbox and bbox overlap` reports a percentage label
    as colliding with a curve it is a clear millimetre away from. This answers
    the question the box could not.
    """
    edges, _ = _region(region)
    return polygon_area(clip_polygon(to_points(points), edges))


def clip_polygon(points: Sequence[Vec2], edges) -> list[Vec2]:
    """Sutherland-Hodgman against a convex boundary."""
    ring = list(points)
    for edge in edges:
        if not ring:
            return []
        out: list[Vec2] = []
        previous = ring[-1]
        prior = _inside(previous, edge)
        for current in ring:
            here = _inside(current, edge)
            if here >= -EPS:
                if prior < -EPS:
                    out.append(_cross_at(previous, current, prior, here))
                out.append(current)
            elif prior >= -EPS:
                out.append(_cross_at(previous, current, prior, here))
            previous, prior = current, here
        ring = out
    return list(_dedupe(ring))


def clip_rings(rings: Sequence[Sequence[Vec2]], edges) -> list[list[Vec2]]:
    """Cut a filled shape -- outer rings and the rings of its holes -- to a
    convex region, keeping its pieces apart.

    Sutherland-Hodgman cannot do this. Clipping a concave ring that the region
    cuts into two leaves it one ring joined by a zero-width bridge running back
    along the clip boundary: correct as a *fill* under the nonzero rule, and
    wrong as everything else. The bridge is stroked, so a cut U-shape draws a
    line across the gap; it is wrong under the even-odd rule; and it is not the
    geometry, so nothing downstream that measures the outline is right either.
    Reproduction: `tests/test_draw_clip.py`, the U cut across both arms.

    So this cuts a half-plane at a time and reassembles instead. Each ring
    contributes the runs of it that survive, every run beginning and ending on
    the clip line, and the runs are then rejoined along that line -- from where
    the boundary left the interior forward to where it next enters, which is
    the only direction that keeps the interior on the same side it was on. A
    ring that ends up split comes back as two rings; a hole that the cut opens
    into the outline merges with it. Rings must arrive with the outer ones
    positively wound and holes negatively, which is what the nonzero rule means
    by a hole anyway.
    """
    current = [list(ring) for ring in rings]
    for edge in edges:
        current = _cut_rings(current, edge)
        if not current:
            return []
    return [ring for ring in current if len(_dedupe(ring)) >= 3]


def _cut_rings(rings: list[list[Vec2]], edge: tuple[Vec2, Vec2]
               ) -> list[list[Vec2]]:
    """Every ring cut by one half-plane, with the open runs rejoined."""
    start, finish = edge
    along = finish - start
    if along.length <= EPS:
        return rings
    along = along.normalized()

    kept: list[list[Vec2]] = []
    chains: list[list[Vec2]] = []
    for ring in rings:
        values = [_inside(p, edge) for p in ring]
        if all(v >= -EPS for v in values):
            kept.append(ring)
        elif any(v > EPS for v in values):
            chains.extend(_inside_runs(ring, values))
        # else: wholly outside, or lying along the line, and drops out
    if not chains:
        return kept
    rejoined = _rejoin(chains, start, along)
    if rejoined is None:
        # A degeneracy the pairing cannot read. Sutherland-Hodgman still gets
        # the filled area right, so take its answer for the whole set rather
        # than half of one and half of the other.
        return [cut for cut in (clip_polygon(ring, (edge,)) for ring in rings)
                if len(cut) >= 3]
    return kept + rejoined


def _inside_runs(ring: Sequence[Vec2], values: Sequence[float]
                 ) -> list[list[Vec2]]:
    """The parts of one ring inside the half-plane, as open runs.

    Each run begins where the ring entered and ends where it left, both points
    on the clip line. A vertex that lies *on* the line is its own crossing --
    `_cross_at` returns it -- which is what keeps a ring that grazes the
    boundary from producing an unbalanced set of ends.
    """
    count = len(ring)
    marked: list[tuple[Vec2, int]] = []
    for i in range(count):
        here, following = ring[i], ring[(i + 1) % count]
        value, next_value = values[i], values[(i + 1) % count]
        if value >= -EPS:
            marked.append((here, 0))
        if value >= -EPS and next_value < -EPS:
            marked.append((_cross_at(here, following, value, next_value), 1))
        elif value < -EPS and next_value >= -EPS:
            marked.append((_cross_at(here, following, value, next_value), -1))

    opening = [i for i, (_, mark) in enumerate(marked) if mark == -1]
    if not opening:
        return []
    marked = marked[opening[0]:] + marked[:opening[0]]
    runs: list[list[Vec2]] = []
    run: list[Vec2] | None = None
    for point, mark in marked:
        if mark == -1:
            run = [point]
        elif run is not None:
            run.append(point)
            if mark == 1:
                trimmed = list(_dedupe_open(run))
                if len(trimmed) >= 2:
                    runs.append(trimmed)
                run = None
    return runs


def _rejoin(chains: list[list[Vec2]], start: Vec2,
            along: Vec2) -> list[list[Vec2]] | None:
    """Close open runs into rings along the clip line.

    Where the boundary left the interior it must travel *forward* along the
    line -- the direction that keeps the interior on its left -- until it
    reaches the next place the boundary enters. Sorting the ends that way is
    the whole of it. `None` says the ends did not pair up, which is a
    degeneracy this cannot resolve and the caller falls back from.
    """
    def at(point: Vec2) -> float:
        return (point - start).dot(along)

    entries = sorted((at(chain[0]), i) for i, chain in enumerate(chains))
    following: dict[int, int] = {}
    for index, chain in enumerate(chains):
        leaving = at(chain[-1])
        nxt = next((i for t, i in entries if t > leaving + EPS), None)
        if nxt is None:
            return None
        following[index] = nxt

    rings: list[list[Vec2]] = []
    used: set[int] = set()
    for index in range(len(chains)):
        if index in used:
            continue
        ring: list[Vec2] = []
        walk = index
        while walk not in used:
            used.add(walk)
            ring.extend(chains[walk])
            walk = following[walk]
        if walk != index:
            return None          # ran into somebody else's ring
        rings.append(ring)
    return rings


def _dedupe_open(points: Sequence[Vec2]) -> tuple[Vec2, ...]:
    """`_dedupe` for a run rather than a ring: the ends are not neighbours, so
    a run that starts and finishes at one point keeps both."""
    out: list[Vec2] = []
    for p in points:
        if not out or (p - out[-1]).length > EPS:
            out.append(p)
    return tuple(out)


def clip_polyline(points: Sequence[Vec2], edges, *,
                  closed: bool = False) -> list[list[Vec2]]:
    """Cut an open chain into the pieces of it that lie inside.

    Segment at a time rather than Liang-Barsky over the whole run, because a
    polyline can leave the region and come back -- a trace with a spike in it
    does exactly that -- and it must come back as a *second* piece rather than
    be bridged by a straight line across the gap.
    """
    chain = list(points)
    if closed and len(chain) >= 2:
        chain.append(chain[0])
    pieces: list[list[Vec2]] = []
    current: list[Vec2] = []
    # Resolve half-plane coefficients once, not four Vec2 allocations per
    # edge of every segment in a dense trace.
    planes = tuple((a.x, a.y, a.y-b.y, b.x-a.x) for a,b in edges)
    for a, b in zip(chain, chain[1:]):
        lo, hi = 0., 1.
        dx, dy = b.x-a.x, b.y-a.y
        accepted = True
        for x, y, nx, ny in planes:
            denominator = nx*dx+ny*dy
            distance = nx*(a.x-x)+ny*(a.y-y)
            if abs(denominator) <= EPS:
                if distance < -EPS:
                    accepted = False
                    break
                continue
            t = -distance/denominator
            if denominator > 0:
                lo = max(lo, t)
            else:
                hi = min(hi, t)
            if lo > hi:
                accepted = False
                break
        span = ((a if lo == 0 else Vec2(a.x+dx*lo,a.y+dy*lo)),
                (b if hi == 1 else Vec2(a.x+dx*hi,a.y+dy*hi))) if accepted else None
        if span is None:
            if len(current) >= 2:
                pieces.append(current)
            current = []
            continue
        start, end = span
        if current and (current[-1] - start).length <= EPS:
            current.append(end)
        else:
            if len(current) >= 2:
                pieces.append(current)
            current = [start, end]
    if len(current) >= 2:
        pieces.append(current)
    return pieces


def _segment(a: Vec2, b: Vec2, edges) -> tuple[Vec2, Vec2] | None:
    """The part of segment a->b inside every half-plane, as a parameter range."""
    lo, hi = 0.0, 1.0
    d = b - a
    for edge in edges:
        start, end = edge
        normal = (end - start).perp()
        # inside(p) = normal . (p - start) >= 0, linear in t
        denominator = normal.dot(d)
        distance = normal.dot(a - start)
        if abs(denominator) <= EPS:
            if distance < -EPS:
                return None               # parallel and outside
            continue
        t = -distance / denominator
        if denominator > 0.0:
            lo = max(lo, t)               # entering
        else:
            hi = min(hi, t)               # leaving
        if lo > hi:
            return None
    return a + d * lo, a + d * hi


def _cross_at(a: Vec2, b: Vec2, da: float, db: float) -> Vec2:
    span = da - db
    if abs(span) <= EPS:
        return b
    return a + (b - a) * (da / span)
