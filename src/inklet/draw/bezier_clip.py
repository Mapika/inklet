"""Convex clipping of open cubics by parameter subdivision.

Intersections are isolated between derivative roots, then bisected. Retained
segments use De Casteljau controls; sampling is only for envelopes and traces.
"""
from __future__ import annotations

import math

from ..core import DiagramError, Subpath
from ..links.curves import at, split


def roots(values):
    """Roots on [0, 1] of scalar cubic Bernstein coefficients."""
    scale = max(map(abs, values))
    if scale == 0:
        return ()
    v0, v1, v2, v3 = (v / scale for v in values)
    a, b, c, d = -v0+3*v1-3*v2+v3, 3*v0-6*v1+3*v2, -3*v0+3*v1, v0
    critical = []
    # Stable quadratic derivative roots; linear and constant degeneracies.
    aa, bb = 3*a, 2*b
    if aa == 0:
        if bb != 0:
            critical.append(-c/bb)
    else:
        disc = bb*bb-4*aa*c
        if disc >= 0:
            q = -.5*(bb+math.copysign(math.sqrt(disc), bb))
            if q:
                critical.extend((q/aa, c/q))
            else:
                critical.append(-bb/(2*aa))
    cuts = sorted({0., 1., *(t for t in critical if 0 < t < 1)})
    def value(t):
        # Bernstein evaluation is less cancellation-prone near endpoints.
        u = 1-t
        return v0*u*u*u+3*v1*u*u*t+3*v2*u*t*t+v3*t*t*t
    found = [t for t in cuts if abs(value(t)) <= 2e-15]
    for lo, hi in zip(cuts, cuts[1:]):
        left, right = value(lo), value(hi)
        if left*right >= 0:
            continue
        for _ in range(55):
            mid = (lo+hi)/2
            if mid in (lo, hi):
                break
            val = value(mid)
            if val == 0:
                lo = hi = mid
                break
            if (val < 0) == (left < 0):
                lo, left = mid, val
            else:
                hi = mid
        found.append((lo+hi)/2)
    return tuple(sorted(set(found)))


def sample(curve, tolerance=1e-4):
    """Flatten within a control-polygon/chord error of 0.0001 clip-frame mm."""
    points = [curve[0]]
    pending = [curve]
    visits = 0
    while pending:
        part = pending.pop()
        visits += 1
        if visits > 131071:
            raise DiagramError('clipped curve exceeds 65,536 sampling segments')
        a, b, c, d = part
        chord = d-a
        squared = chord.dot(chord)
        def distance(p):
            t = max(0., min(1., (p-a).dot(chord)/squared)) if squared else 0.
            return (p-(a+chord*t)).length
        if max(distance(b), distance(c)) <= tolerance:
            points.append(d)
        else:
            left, right = split(part, .5)
            pending.extend((right, left))
    return points


def clip_curves(curves, world, home, edges, *, closed=False):
    """Return separate retained runs without joining over removed intervals."""
    planes = [(a, (b-a).perp().normalized()) for a, b in edges]
    runs = []
    run = []
    previous_kept = False
    for original in curves:
        curve = tuple(world.apply(p) for p in original)
        cuts = sorted({0., 1., *(t for a, n in planes
                       for t in roots(tuple(n.dot(p-a) for p in curve)))})
        for lo, hi in zip(cuts, cuts[1:]):
            if hi-lo <= 1e-15:
                continue
            middle = at(curve, (lo+hi)/2)
            keep = all(n.dot(middle-a) >= -1e-10 for a, n in planes)
            if not keep:
                if run:
                    runs.append(run)
                    run = []
                previous_kept = False
                continue
            part = split(curve, hi)[0] if hi < 1 else curve
            if lo > 0:
                part = split(part, lo/hi)[1]
            if previous_kept and run and (run[-1][-1]-part[0]).length > 1e-8:
                runs.append(run)
                run = []
            run.append(part)
            previous_kept = True
    if run:
        runs.append(run)
    # An unfilled closed curve can be cut across its arbitrary starting point.
    if closed and len(runs) > 1 and (runs[-1][-1][-1]-runs[0][0][0]).length <= 1e-9:
        runs = [runs[-1]+runs[0]]+runs[1:-1]
    out = []
    for run in runs:
        points = [run[0][0]]
        for part in run:
            points.extend(sample(part)[1:])
        is_closed = closed and len(runs) == 1 and (points[0]-points[-1]).length <= 1e-9
        out.append(Subpath(tuple(home.apply(p) for p in points), is_closed,
                           tuple(tuple(home.apply(p) for p in part) for part in run)))
    return out
