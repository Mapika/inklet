"""Sampled regions and deterministic leader refinement for the research planner."""
from dataclasses import dataclass
from functools import lru_cache
import math

from inklet.core import Vec2
from inklet.three.scene_projection import ProjectedPoint, _vector


@dataclass(frozen=True)
class Region:
    """Author-supplied surface samples; neither pixel coverage nor recognition.

    All samples, including hidden/out-of-frame/unknown ones, enter the visibility
    denominator. min_span_mm is the longest side of the visible samples' projected
    bounding box at the chosen image size. Samples use scene world coordinates.
    """
    samples: tuple[tuple[float, float, float], ...]
    min_visible_fraction: float = .6
    min_span_mm: float = 3.

    def __post_init__(self):
        points = tuple(_vector(p) for p in self.samples)
        if not 2 <= len(points) <= 4096 or len(set(points)) != len(points):
            raise ValueError('Region requires 2–4096 distinct surface samples')
        fraction, span = float(self.min_visible_fraction), float(self.min_span_mm)
        if not math.isfinite(fraction) or not 0 < fraction <= 1:
            raise ValueError('min_visible_fraction must be in (0, 1]')
        if not math.isfinite(span) or span <= 0:
            raise ValueError('min_span_mm must be finite and positive')
        object.__setattr__(self, 'samples', points)
        object.__setattr__(self, 'min_visible_fraction', fraction)
        object.__setattr__(self, 'min_span_mm', span)


def project(render, world, bias):
    try:
        return render.project(world, depth_bias=bias)
    except ValueError as error:
        if 'on the perspective camera plane' not in str(error):
            raise
        return ProjectedPoint(Vec2(0, 0), 0., False, False)


def sample_region(render, region, bias):
    points = [project(render, world, bias) for world in region.samples]
    visible = [p.point for p in points if p.in_frame and p.visible is True]
    span = max(max(p.x for p in visible)-min(p.x for p in visible),
               max(p.y for p in visible)-min(p.y for p in visible)) if visible else 0.
    return dict(samples=len(points), visible_samples=len(visible),
                in_frame_samples=sum(p.in_frame for p in points),
                unknown_samples=sum(p.in_frame and p.visible is None for p in points),
                visible_fraction=len(visible)/len(points), span_at_render_mm=span)


def leader_points(target_x, target_y, x, y, side, image_width):
    sign = -1 if side == 'w' else 1
    return ((target_x, target_y), (sign*(image_width/2+1.5), y), (x-sign, y))


def _proper_crossing(a, b, c, d):
    def orientation(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    first, second = orientation(a, b, c), orientation(a, b, d)
    third, fourth = orientation(c, d, a), orientation(c, d, b)
    return ((first > 1e-9 and second < -1e-9) or (first < -1e-9 and second > 1e-9)) and (
        (third > 1e-9 and fourth < -1e-9) or (third < -1e-9 and fourth > 1e-9))


def leaders_cross(first, second):
    """One count per leader pair, excluding endpoint touches/collinear overlaps."""
    return any(_proper_crossing(a, b, c, d) for a, b in zip(first, first[1:])
               for c, d in zip(second, second[1:]))


def crossing_pairs(placements, image_width):
    lines = [leader_points(p.target_x, p.target_y, p.x, p.y, p.side, image_width) for p in placements]
    return [(a.target, b.target) for index, a in enumerate(placements)
            for j, b in enumerate(placements[index+1:], index+1)
            if a.view == b.view and leaders_cross(lines[index], lines[j])]


def refine(costs, assigned, lines, slot_views, penalty, max_steps):
    """Strictly improve linear cost + pair crossings using free moves and swaps.

    Hard constraints remain infinity in costs. This is local search, with no
    global quadratic-optimality claim. A step limit is reported conservatively.
    """
    assigned = list(assigned)
    n = len(assigned)

    @lru_cache(maxsize=32768)
    def pair(a, sa, b, sb):
        return int(slot_views[sa] == slot_views[sb] and leaders_cross(lines[a][sa], lines[b][sb]))

    def count():
        return sum(pair(a, assigned[a], b, assigned[b]) for a in range(n) for b in range(a+1, n))

    initial = count()
    if penalty == 0:
        return assigned, dict(initial_crossings=initial, crossings=initial, steps=0, status='disabled')
    if initial == 0:
        # The input is a minimum linear-cost assignment. Zero crossings already
        # attains the non-negative pair penalty's lower bound.
        return assigned, dict(initial_crossings=0, crossings=0, steps=0, status='local_optimum')
    for step in range(max_steps):
        occupied = {slot: row for row, slot in enumerate(assigned)}
        best, best_delta = None, -1e-9
        for a in range(n):
            for slot, cost in enumerate(costs[a]):
                if slot == assigned[a] or not math.isfinite(cost):
                    continue
                b = occupied.get(slot)
                if b is not None and (b < a or not math.isfinite(costs[b][assigned[a]])):
                    continue
                change = {a: slot} if b is None else {a: slot, b: assigned[a]}
                delta = sum(costs[row][new]-costs[row][assigned[row]] for row, new in change.items())
                affected = {(min(row, other), max(row, other)) for row in change for other in range(n) if row != other}
                delta += penalty*sum(pair(row, change.get(row, assigned[row]), other, change.get(other, assigned[other]))
                    -pair(row, assigned[row], other, assigned[other]) for row, other in sorted(affected))
                if delta < best_delta:
                    best, best_delta = change, delta
        if best is None:
            return assigned, dict(initial_crossings=initial, crossings=count(), steps=step, status='local_optimum')
        for row, slot in best.items():
            assigned[row] = slot
    return assigned, dict(initial_crossings=initial, crossings=count(), steps=max_steps, status='step_limit')
