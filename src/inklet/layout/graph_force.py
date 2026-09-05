"""Fruchterman-Reingold, and the circle it starts from.

Force layout has a reputation for being the one that will not sit still, and
that reputation is earned by the seed: a random start means a different picture
every run, which is not a figure, it is a slot machine. Everything here is
deterministic. The initial placement is the circular layout below -- input
order, evenly spaced -- and the loop is a fixed number of iterations over index
pairs in index order, so the same graph gives the same millimetres twice and a
figure regenerated for a revision is the figure the reviewer saw.

Two departures from the paper, both because nodes here are labelled boxes and
not points:

* **Repulsion knows how big things are.** The inverse-square term is the
  paper's, but once two nodes are close enough that their boxes are about to
  touch, a second term proportional to the overlap takes over. Points can share
  a coordinate; a box with a word in it cannot.
* **There is an overlap-removal pass at the end.** Attraction and repulsion
  balance at an equilibrium that has no opinion about whether "Spike
  deconvolution" is sitting on top of "Encoding model". The pass pushes
  overlapping pairs apart along the line between their centres, and if it has
  not converged it scales the whole drawing up, which resolves any overlap
  whatever because the nodes do not grow with it.
"""

from __future__ import annotations

import math
from typing import Sequence

__all__ = ["force_positions", "circular_positions", "remove_overlaps"]

Size = tuple[float, float]
Point = tuple[float, float]

#: Iterations of the push-apart pass before the drawing is simply scaled up.
#: It converges in a few dozen on anything the force loop produces; the cap is
#: what keeps a pathological input from spinning.
_SEPARATE_ROUNDS = 400

#: How much of a pair's overlap is taken out per round. Under 1 because a node
#: usually overlaps more than one neighbour, and resolving each pair in full
#: makes the pass oscillate instead of settle.
_SEPARATE_RELAXATION = 0.55


def circular_positions(sizes: Sequence[Size], *, gap: float,
                       start: float = -90.0) -> list[Point]:
    """Evenly spaced around a circle, in input order, clockwise from `start`.

    The radius is not a parameter because it is not a choice: it is whatever
    makes every neighbouring pair clear each other by `gap`. A ring of even
    boxes therefore comes out as small as it can be, and one wide box on the
    ring opens the whole circle rather than colliding with its neighbours.
    """
    n = len(sizes)
    if n == 0:
        return []
    if n == 1:
        return [(0.0, 0.0)]
    reach = [math.hypot(w, h) / 2.0 for w, h in sizes]
    step = 2.0 * math.pi / n
    chord = 2.0 * math.sin(step / 2.0)
    radius = max((reach[i] + reach[(i + 1) % n] + gap) / chord for i in range(n))
    angle0 = math.radians(start)
    return [(radius * math.cos(angle0 + i * step),
             radius * math.sin(angle0 + i * step)) for i in range(n)]


def force_positions(sizes: Sequence[Size], edges: Sequence[tuple[int, int]], *,
                    gap: float, iterations: int = 300) -> list[Point]:
    """Fruchterman-Reingold from a circular start, then overlaps removed."""
    n = len(sizes)
    if n <= 1:
        return circular_positions(sizes, gap=gap)

    points = circular_positions(sizes, gap=gap)
    reach = [math.hypot(w, h) / 2.0 for w, h in sizes]
    # The ideal edge length: far enough that two average boxes joined by an
    # edge sit clear of each other, which is the only length scale the drawing
    # has. Deriving it from the geometry rather than taking it as a parameter
    # is what lets one call lay out both a graph of initials and a graph of
    # sentences.
    k = 2.0 * sum(reach) / n + gap
    area = k * k * n
    temperature = math.sqrt(area) / 8.0
    cooling = temperature / max(1, iterations)

    links = [(u, v) for u, v in edges if u != v]
    for _ in range(iterations):
        fx = [0.0] * n
        fy = [0.0] * n
        for i in range(n):
            xi, yi = points[i]
            for j in range(i + 1, n):
                dx = xi - points[j][0]
                dy = yi - points[j][1]
                distance = math.hypot(dx, dy)
                if distance < 1e-9:
                    # Coincident centres have no direction to separate along.
                    # Index order gives one, and gives the same one twice.
                    dx, dy, distance = 1.0, 0.0, 1e-9
                push = k * k / distance
                clear = reach[i] + reach[j] + gap
                if distance < clear:
                    push += (clear - distance) * k
                ux, uy = dx / distance, dy / distance
                fx[i] += ux * push
                fy[i] += uy * push
                fx[j] -= ux * push
                fy[j] -= uy * push
        for u, v in links:
            dx = points[u][0] - points[v][0]
            dy = points[u][1] - points[v][1]
            distance = math.hypot(dx, dy)
            if distance < 1e-9:
                continue
            pull = distance * distance / k
            ux, uy = dx / distance, dy / distance
            fx[u] -= ux * pull
            fy[u] -= uy * pull
            fx[v] += ux * pull
            fy[v] += uy * pull
        for i in range(n):
            length = math.hypot(fx[i], fy[i])
            if length < 1e-12:
                continue
            step = min(length, temperature) / length
            points[i] = (points[i][0] + fx[i] * step,
                         points[i][1] + fy[i] * step)
        temperature -= cooling

    return remove_overlaps(points, sizes, gap=gap)


def remove_overlaps(points: Sequence[Point], sizes: Sequence[Size], *,
                    gap: float) -> list[Point]:
    """Push overlapping nodes apart, and guarantee it worked.

    The relaxation is the usual one and usually enough. What makes the promise
    unconditional is the fallback: node sizes are fixed, so scaling every
    position about the centroid strictly increases every centre distance, and
    a large enough factor separates any arrangement whose centres are distinct.
    """
    out = [(x, y) for x, y in points]
    n = len(out)
    if n <= 1:
        return out
    half = [(w / 2.0 + gap / 2.0, h / 2.0 + gap / 2.0) for w, h in sizes]

    for _ in range(_SEPARATE_ROUNDS):
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                dx = out[j][0] - out[i][0]
                dy = out[j][1] - out[i][1]
                span_x = half[i][0] + half[j][0]
                span_y = half[i][1] + half[j][1]
                if abs(dx) >= span_x or abs(dy) >= span_y:
                    continue
                moved = True
                distance = math.hypot(dx, dy)
                if distance < 1e-9:
                    dx, dy, distance = 1.0, 0.0, 1.0
                # How far along this direction the two boxes have to be to
                # clear: the smaller of the two axis requirements, scaled onto
                # the centre line, which is the cheapest way out of the
                # collision.
                need = min(span_x / abs(dx) if abs(dx) > 1e-9 else float("inf"),
                           span_y / abs(dy) if abs(dy) > 1e-9 else float("inf"))
                push = (need - 1.0) * _SEPARATE_RELAXATION / 2.0
                out[i] = (out[i][0] - dx * push, out[i][1] - dy * push)
                out[j] = (out[j][0] + dx * push, out[j][1] + dy * push)
        if not moved:
            return out

    return _spread(out, half)


def _spread(points: list[Point], half: Sequence[tuple[float, float]]) -> list[Point]:
    """Last resort: scale about the centroid until nothing overlaps."""
    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    factor = 1.0
    for _ in range(60):
        out = [(cx + (x - cx) * factor, cy + (y - cy) * factor)
               for x, y in points]
        if not _any_overlap(out, half):
            return out
        factor *= 1.5
    return points


def _any_overlap(points: Sequence[Point],
                 half: Sequence[tuple[float, float]]) -> bool:
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            if (abs(points[j][0] - points[i][0]) < half[i][0] + half[j][0]
                    and abs(points[j][1] - points[i][1]) < half[i][1] + half[j][1]):
                return True
    return False
