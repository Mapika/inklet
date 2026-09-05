"""Cubics for the connectors that are not polylines.

Three of them need real curves rather than a chain of short segments: a
self-loop, a parallel edge bowed off the centre line, and any shaft an
arrowhead has to be cut back from. A `Subpath` carries both forms -- exact
control points in `curves` for the backend, a flattened polyline in `points`
for every geometry query in core -- so everything here comes in pairs: build
the cubics, then flatten them.

Trimming is the only part that is not one formula. An arrowhead is a length
measured *along the shaft*, and a cubic has no closed form for that, so the
split parameter is found on the flattened chord chain and the curve is then
split exactly with de Casteljau. The error is the flattening error, which at
32 samples over a 10mm bow is under a micron -- three orders below anything
the renderer can print.
"""

from __future__ import annotations

from ..core import Vec2

__all__ = [
    "Cubic", "bow", "flatten", "length", "loop_curves", "split", "straight",
    "trim_end", "trim_start",
]

#: Start point, two controls, end point -- the same 4-tuple `Subpath.curves`
#: holds, so nothing has to be converted on the way out.
Cubic = tuple[Vec2, Vec2, Vec2, Vec2]

EPS = 1e-9

#: Samples per cubic when measuring or flattening. A bow is a shallow curve
#: and a loop is four of these end to end; 16 chords hold both to well under
#: the 0.001mm the renderer rounds to.
STEPS = 16

#: A cubic control arm reaches this fraction of the offset it is asked to
#: bulge by, because the midpoint of a cubic sits three quarters of the way
#: out to its controls: B(0.5) = p0 + d/2 + (3/4)nk, so k = 4/3 gets the apex
#: exactly where the caller asked for it.
_APEX = 4.0 / 3.0


def at(curve: Cubic, t: float) -> Vec2:
    p0, c1, c2, p3 = curve
    u = 1.0 - t
    return (p0 * (u * u * u) + c1 * (3 * u * u * t)
            + c2 * (3 * u * t * t) + p3 * (t * t * t))


def straight(p0: Vec2, p3: Vec2) -> Cubic:
    """A cubic that is exactly its own chord."""
    step = (p3 - p0) * (1 / 3)
    return (p0, p0 + step, p0 + step * 2, p3)


def bow(p0: Vec2, p3: Vec2, offset: float) -> Cubic:
    """The chord p0-p3, bulged `offset` millimetres across it at the midpoint.

    Positive is to the right of travel: `perp()` is a quarter turn from (1, 0)
    to (0, 1), and y grows downward, so a positive offset on a rightward line
    bows *down* the page. Two links given the same offset in opposite
    directions therefore end up on opposite sides of the pair they join, which
    is what makes `offset=` symmetric for a pair of opposing arrows.
    """
    span = p3 - p0
    if span.length <= EPS or abs(offset) <= EPS:
        return straight(p0, p3)
    across = span.normalized().perp() * (offset * _APEX)
    return (p0, p0 + span * (1 / 3) + across, p0 + span * (2 / 3) + across, p3)


def loop_curves(start: Vec2, end: Vec2, out: Vec2, height: float) -> tuple[Cubic, ...]:
    """A self-loop: out of `start`, round, and back into `end`.

    Two cubics rather than one, meeting at the apex. One cubic can be made to
    pass through the apex but it leaves the shape at whatever angle the chord
    dictates, and a loop that leaves a box at 30 degrees and comes back at 30
    reads as a bent arrow rather than as a loop. Splitting it at the top lets
    each half leave along the side's own normal and arrive at the apex
    parallel to the edge, which is the shape a person draws.
    """
    across = out.perp()
    apex = (start + end) * 0.5 + out * height
    reach = height * 0.75
    spread = max((end - start).length * 0.5, height * 0.5)
    return (
        (start, start + out * reach, apex - across * spread, apex),
        (apex, apex + across * spread, end + out * reach, end),
    )


def split(curve: Cubic, t: float) -> tuple[Cubic, Cubic]:
    """De Casteljau, exact: the curve before `t` and the curve after it."""
    p0, c1, c2, p3 = curve
    a = p0 + (c1 - p0) * t
    b = c1 + (c2 - c1) * t
    c = c2 + (p3 - c2) * t
    d = a + (b - a) * t
    e = b + (c - b) * t
    f = d + (e - d) * t
    return (p0, a, d, f), (f, e, c, p3)


def length(curves: tuple[Cubic, ...], steps: int = STEPS) -> float:
    return sum(_chords(curve, steps)[-1] for curve in curves)


def trim_start(curves: tuple[Cubic, ...], amount: float,
               steps: int = STEPS) -> tuple[Cubic, ...]:
    """Cut `amount` millimetres off the front, measured along the curve."""
    if amount <= EPS:
        return curves
    out = list(curves)
    while out and amount > EPS:
        run = _chords(out[0], steps)
        if run[-1] <= amount + EPS:
            amount -= run[-1]
            out.pop(0)
            continue
        out[0] = split(out[0], _parameter(run, amount, steps))[1]
        return tuple(out)
    return tuple(out)


def trim_end(curves: tuple[Cubic, ...], amount: float,
             steps: int = STEPS) -> tuple[Cubic, ...]:
    if amount <= EPS:
        return curves
    out = list(curves)
    while out and amount > EPS:
        run = _chords(out[-1], steps)
        if run[-1] <= amount + EPS:
            amount -= run[-1]
            out.pop()
            continue
        out[-1] = split(out[-1], _parameter(run, run[-1] - amount, steps))[0]
        return tuple(out)
    return tuple(out)


def flatten(curves: tuple[Cubic, ...], steps: int = STEPS) -> tuple[Vec2, ...]:
    """The polyline core measures with: every cubic sampled, joins not doubled."""
    if not curves:
        return ()
    points = [curves[0][0]]
    for curve in curves:
        points.extend(at(curve, i / steps) for i in range(1, steps + 1))
    return tuple(points)


def _chords(curve: Cubic, steps: int) -> list[float]:
    """Cumulative chord length at each sample, starting at zero."""
    out = [0.0]
    previous = curve[0]
    for i in range(1, steps + 1):
        point = at(curve, i / steps)
        out.append(out[-1] + (point - previous).length)
        previous = point
    return out


def _parameter(run: list[float], distance: float, steps: int) -> float:
    """The parameter at `distance` along one cubic, interpolated between
    samples. Monotone in `distance`, which is what keeps a trimmed curve from
    ever doubling back on itself."""
    for i in range(1, len(run)):
        if run[i] >= distance:
            span = run[i] - run[i - 1]
            share = 0.0 if span <= EPS else (distance - run[i - 1]) / span
            return (i - 1 + share) / steps
    return 1.0
