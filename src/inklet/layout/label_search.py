"""The shared search behind point labels, curve labels and keys.

Every placer in inklet that has to put many boxes of text somewhere asks the
same two questions: *what does this position cost on its own* (the marks,
lines, filled areas and furniture it covers, how far it is from what it names,
whether it needs a leader and what that leader runs through) and *what does it
cost together with the others* (two labels on each other, two leaders
crossing, a leader through somebody else's label). This module answers both,
and then chooses one candidate per label so that the total is small.

`ObstacleField` indexes the fixed geometry once: boxes (markers, bars, text,
legend plates), stroked segments (curves, error bars, rules, axes) and filled
polygons that are not rectangles (bands and areas, measured on their real
outline rather than their bounding box). `Candidate` is one position for one
label with its fixed cost already scored against that field. `solve` then
picks one candidate per label in four deterministic passes:

1. **Greedy**, most crowded label first, each against the labels already down.
2. **Best response**: every label in turn moves to its cheapest candidate
   given where all the others are, until nothing moves.
3. **Annealing** over the labels not at their cheapest candidate and their
   neighbours: heat-bath sweeps (each label re-drawn from all its candidates,
   weighted by `exp(-cost / temperature)`) on a falling temperature, from a
   generator seeded with a hash of the labels' own content. The best state
   seen is kept, then best response runs again.
4. **Pair repair**: two labels still in conflict are re-placed jointly, which
   finds the swaps that uncross two leaders.

No clock is read and nothing depends on dictionary or set iteration order, so
the same input gives the same output, byte for byte, in every process.

A label that still covers another label, a labelled point or a mark, is
crossed by a stroked line, or whose leader crosses another leader or label,
is reported by `solve` as a conflict; callers list it as unresolved rather
than hiding it.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Sequence

from ..core import MarkerBatchPrim, PathPrim, Rect, Vec2, resolve

__all__ = ["Candidate", "ObstacleField", "Weights", "Solution", "solve",
           "stack", "field_of", "seed_of", "segment_hits_box", "segments_cross"]

Box = tuple[float, float, float, float]
Seg = tuple[float, float, float, float]


@dataclass(frozen=True)
class Weights:
    """How the search trades one cost against another.

    Areas are per square millimetre, lengths per millimetre, the rest per
    event. Overlapping another label or a labelled point is weighted like
    covering a mark; the gap kept around labels (`spacing`) is weighted the
    same, so it is kept whenever there is room.
    """

    overlap: float = 10.0        # label on a label, a target or a mark, per mm^2
    pad: float = 1.0             # into the small pad kept round marks, per mm^2
    area: float = 0.6            # over a filled band or area, per mm^2
    crossing: float = 8.0        # a stroked line through the label, per segment
    graze: float = 0.5           # a stroked line within the pad, per segment
    leader_crossing: float = 6.0  # a leader crossing a leader, label or target
    leader_mark: float = 0.4     # a leader through a mark, per mark
    distance: float = 0.3        # per millimetre from the anchor
    leader: float = 2.0          # for needing a leader at all
    conflict: float = 40.0       # on top of the rest, per conflict


# -- geometry helpers -------------------------------------------------------


def _area(a: Box, b: Box) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    if w <= 0:
        return 0.0
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if h > 0 else 0.0


def _grow(b: Box, by: float) -> Box:
    return (b[0] - by, b[1] - by, b[2] + by, b[3] + by)


def _touch(a: Box, b: Box) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def segment_hits_box(ax: float, ay: float, bx: float, by: float,
                     box: Box) -> bool:
    """Whether segment a-b passes through the box (Liang-Barsky)."""
    enter, leave = 0.0, 1.0
    for start, delta, lo, hi in ((ax, bx - ax, box[0], box[2]),
                                 (ay, by - ay, box[1], box[3])):
        if abs(delta) < 1e-12:
            if start < lo or start > hi:
                return False
            continue
        t0 = (lo - start) / delta
        t1 = (hi - start) / delta
        if t0 > t1:
            t0, t1 = t1, t0
        if t0 > enter:
            enter = t0
        if t1 < leave:
            leave = t1
        if enter > leave:
            return False
    return True


def segments_cross(a: Seg, b: Seg) -> bool:
    """Whether two segments cross properly (touching ends do not count)."""
    ax, ay, bx, by = a
    cx, cy, dx, dy = b
    d1 = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx)
    d2 = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx)
    if d1 * d2 >= 0:
        return False
    d3 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    d4 = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax)
    return d3 * d4 < 0


#: A text box carries ascender and descender slack; a mark that only reaches
#: this far (mm) into it touches the box and not the glyphs.
_SLACK = 0.15


def _covers(box: Box, other: Box) -> bool:
    """Whether `box` really covers `other`: a square marker-sized obstacle is
    read as the disc it almost always is, anything else as its box."""
    w = other[2] - other[0]
    h = other[3] - other[1]
    if w <= 3.0 and abs(w - h) < 1e-6:
        cx = (other[0] + other[2]) / 2
        cy = (other[1] + other[3]) / 2
        nx = min(max(cx, box[0]), box[2])
        ny = min(max(cy, box[1]), box[3])
        return (cx - nx) ** 2 + (cy - ny) ** 2 < (w / 2) ** 2
    return _area(box, other) > 0


def _inside(poly: Sequence[tuple[float, float]], x: float, y: float) -> bool:
    hit = False
    n = len(poly)
    for k in range(n):
        x0, y0 = poly[k]
        x1, y1 = poly[(k + 1) % n]
        if (y0 > y) != (y1 > y):
            if x0 + (y - y0) * (x1 - x0) / (y1 - y0) > x:
                hit = not hit
    return hit


class _Grid:
    """Items bucketed on a square grid by their boxes."""

    def __init__(self, cell: float) -> None:
        self.cell = max(cell, 0.5)
        self.cells: dict[tuple[int, int], list[int]] = {}

    def keys(self, b: Box):
        c = self.cell
        for i in range(math.floor(b[0] / c), math.floor(b[2] / c) + 1):
            for j in range(math.floor(b[1] / c), math.floor(b[3] / c) + 1):
                yield i, j

    def add(self, number: int, b: Box) -> None:
        for key in self.keys(b):
            self.cells.setdefault(key, []).append(number)

    def near(self, b: Box) -> list[int]:
        seen: set[int] = set()
        out: list[int] = []
        for key in self.keys(b):
            for number in self.cells.get(key, ()):
                if number not in seen:
                    seen.add(number)
                    out.append(number)
        out.sort()
        return out


# -- the fixed field --------------------------------------------------------


class ObstacleField:
    """Fixed geometry a label should not cover, indexed for fast queries.

    * Solid boxes (`add_box`): bars, text, legend plates. Covering one is a
      conflict.
    * Marks (`add_box(..., mark=True)`): data markers. Covering one costs as
      much as covering a solid box, but is counted separately as *covered*
      rather than as a conflict: in a dense cloud a label cannot always
      avoid every point, and the caller reports it instead.
    * Targets (`add_target`): the points being labelled. No label and no
      leader may cover another label's target.
    * Segments (`add_segment`): stroked lines -- curves, error bars, rules.
      A line through a label is a conflict.
    * Areas (`add_area`): filled polygons that are not rectangles, measured
      on their outline. A label over one costs a little; never a conflict.
    """

    def __init__(self, cell: float = 2.0) -> None:
        self.cell = max(cell, 0.5)
        self.boxes: list[Box] = []
        self.is_mark: list[bool] = []
        self.targets: list[Box] = []
        self.segments: list[Seg] = []
        self.areas: list[tuple[Box, tuple[tuple[float, float], ...]]] = []
        self.edges: list[Seg] = []
        self._box_grid = _Grid(self.cell)
        self._seg_grid = _Grid(self.cell)
        self._target_grid = _Grid(self.cell)
        self._area_grid = _Grid(self.cell * 4)
        self._edge_grid = _Grid(self.cell)

    def add_box(self, b: Box, *, mark: bool = False) -> int:
        """Index a box; returns its number (for `own_boxes`)."""
        self._box_grid.add(len(self.boxes), b)
        self.boxes.append(b)
        self.is_mark.append(mark)
        return len(self.boxes) - 1

    def add_rect(self, rect: Rect, *, mark: bool = False) -> int:
        return self.add_box((rect.x0, rect.y0, rect.x1, rect.y1), mark=mark)

    def add_segment(self, s: Seg) -> None:
        self._seg_grid.add(len(self.segments), _seg_box(s))
        self.segments.append(s)

    def add_target(self, b: Box) -> None:
        self._target_grid.add(len(self.targets), b)
        self.targets.append(b)

    def add_area(self, poly: Sequence[tuple[float, float]]) -> None:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        b = (min(xs), min(ys), max(xs), max(ys))
        self._area_grid.add(len(self.areas), b)
        self.areas.append((b, tuple(poly)))
        for k in range(len(poly)):
            x0, y0 = poly[k]
            x1, y1 = poly[(k + 1) % len(poly)]
            edge = (x0, y0, x1, y1)
            self._edge_grid.add(len(self.edges), _seg_box(edge))
            self.edges.append(edge)

    # -- queries --------------------------------------------------------

    def cost(self, box: Box, *, spacing: float, weights: Weights,
             own: Sequence[int] = (), own_boxes: Sequence[int] = ()
             ) -> tuple[float, int, int]:
        """`(cost, conflicts, covered)` of a label box against the field.

        `own` are target indices the label belongs to (they may be touched,
        not covered -- the caller keeps its first ring clear of them), and
        `own_boxes` are box indices drawn at its own point. `covered` counts
        marks under the label; `cost` already includes `weights.conflict`
        per conflict.
        """
        cost = 0.0
        conflicts = 0
        covered = 0
        pad = _grow(box, 0.25 * spacing)
        spaced = _grow(box, spacing)
        inner = _grow(box, -_SLACK)
        for n in self._box_grid.near(pad):
            if n in own_boxes:
                continue
            other = self.boxes[n]
            hit = _area(box, other)
            if hit > 0:
                cost += weights.overlap * hit
                if _covers(inner, other):
                    if self.is_mark[n]:
                        covered += 1
                    else:
                        conflicts += 1
            cost += weights.pad * _area(pad, other)
        for n in self._target_grid.near(spaced):
            other = self.targets[n]
            hit = _area(box, other)
            cost += weights.overlap * hit
            if n not in own:
                if hit > 0 and _covers(inner, other):
                    conflicts += 1
                cost += weights.overlap * (_area(spaced, other) - hit)
        half = _grow(box, 0.5 * spacing)
        for n in self._seg_grid.near(half):
            s = self.segments[n]
            if segment_hits_box(s[0], s[1], s[2], s[3], inner):
                cost += weights.crossing
                conflicts += 1
            elif segment_hits_box(s[0], s[1], s[2], s[3], half):
                cost += weights.graze
        for n in self._area_grid.near(box):
            abox, poly = self.areas[n]
            if _area(box, abox) <= 0:
                continue
            inside = 0
            for i in range(5):
                x = box[0] + (box[2] - box[0]) * (i + 0.5) / 5
                for j in range(3):
                    y = box[1] + (box[3] - box[1]) * (j + 0.5) / 3
                    inside += _inside(poly, x, y)
            cost += (weights.area * inside / 15.0
                     * (box[2] - box[0]) * (box[3] - box[1]))
        for n in self._edge_grid.near(box):
            s = self.edges[n]
            if segment_hits_box(s[0], s[1], s[2], s[3], box):
                cost += weights.area
        return cost + weights.conflict * conflicts, conflicts, covered

    def leader_cost(self, seg: Seg, *, weights: Weights,
                    own: Sequence[int] = ()) -> tuple[float, int]:
        """`(cost, conflicts)` of a leader: through targets, marks, lines.

        Through another target is a conflict; through marks and across
        lines only costs, since a hairline over a grey cloud still reads.
        """
        b = _seg_box(seg)
        cost = 0.0
        conflicts = 0
        for n in self._target_grid.near(b):
            if n in own:
                continue
            if segment_hits_box(*seg, _grow(self.targets[n], -_SLACK)):
                cost += weights.leader_crossing
                conflicts += 1
        marks = 0
        for n in self._box_grid.near(b):
            if segment_hits_box(*seg, _grow(self.boxes[n], -0.05)):
                marks += 1
        cost += weights.leader_mark * min(marks, 40)
        for n in self._seg_grid.near(b):
            if segments_cross(seg, self.segments[n]):
                cost += weights.leader_mark
        return cost + weights.conflict * conflicts, conflicts


def _seg_box(s: Seg) -> Box:
    return (min(s[0], s[2]), min(s[1], s[3]), max(s[0], s[2]), max(s[1], s[3]))


# -- candidates and the solver ----------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """One position for one label.

    `box` is `(x0, y0, x1, y1)`; `leader` a segment `(x0, y0, x1, y1)` or
    None; `cost` the fixed cost (field, distance, leader, preference) and
    `conflicts` the fixed conflicts, both as scored by the caller. `data` is
    whatever the caller needs back to draw the choice, and `covered` the
    number of marks the label sits on (reported, not a conflict).
    """

    box: Box
    leader: Seg | None
    cost: float
    conflicts: int = 0
    data: object = None
    covered: int = 0

    @property
    def hull(self) -> Box:
        b = self.box
        s = self.leader
        if s is None:
            return b
        return (min(b[0], s[0], s[2]), min(b[1], s[1], s[3]),
                max(b[2], s[0], s[2]), max(b[3], s[1], s[3]))


@dataclass(frozen=True)
class Solution:
    """The chosen candidate index per label, and who is still in conflict."""

    chosen: tuple[int, ...]
    conflicted: tuple[int, ...]
    energy: float


def seed_of(*parts) -> int:
    """A 64-bit seed from the repr of the arguments -- content, not time."""
    digest = hashlib.sha256(repr(parts).encode()).digest()
    return int.from_bytes(digest[:8], "big")


class _Pairs:
    """Pairwise cost between labels at given candidates, memoised."""

    def __init__(self, options: Sequence[Sequence[Candidate]], spacing: float,
                 weights: Weights) -> None:
        self.options = options
        self.spacing = spacing
        self.w = weights
        self.hulls = [[_grow(c.hull, spacing) for c in opts] for opts in options]
        # The region each label's candidates can reach, and for each
        # candidate the labels whose region it meets: the only ones whose
        # position can change its cost.
        reach = []
        for hs in self.hulls:
            reach.append((min(h[0] for h in hs), min(h[1] for h in hs),
                          max(h[2] for h in hs), max(h[3] for h in hs)))
        grid = _Grid(max(4.0, spacing * 4))
        for n, r in enumerate(reach):
            grid.add(n, r)
        self.neighbours = [[j for j in grid.near(r) if j != i and _touch(r, reach[j])]
                           for i, r in enumerate(reach)]
        self.touching = [[[j for j in self.neighbours[i] if _touch(h, reach[j])]
                          for h in self.hulls[i]] for i in range(len(options))]
        self._memo: dict[tuple[int, int, int, int], tuple[float, int]] = {}

    def cost(self, i: int, a: int, j: int, b: int) -> tuple[float, int]:
        key = (i, a, j, b) if i < j else (j, b, i, a)
        found = self._memo.get(key)
        if found is None:
            found = self._memo[key] = self._cost(i, a, j, b)
        return found

    def _cost(self, i: int, a: int, j: int, b: int) -> tuple[float, int]:
        if not _touch(self.hulls[i][a], self.hulls[j][b]):
            return 0.0, 0
        ca = self.options[i][a]
        cb = self.options[j][b]
        w = self.w
        s = self.spacing
        cost = 0.0
        conflicts = 0
        hit = _area(ca.box, cb.box)
        if hit > 0:
            cost += w.overlap * hit
            conflicts += 1
        # The gap kept between labels, measured from both sides so the cost
        # is the same whichever of the two is asked about.
        cost += w.overlap * 0.5 * (_area(_grow(ca.box, s), cb.box)
                                   + _area(ca.box, _grow(cb.box, s))
                                   - 2 * hit)
        la, lb = ca.leader, cb.leader
        # A leader through another label is a conflict; one merely passing
        # within half the spacing of it costs the same, without being one.
        for line, box in ((la, cb.box), (lb, ca.box)):
            if line is None:
                continue
            if segment_hits_box(*line, _grow(box, -_SLACK)):
                cost += w.leader_crossing
                conflicts += 1
            elif segment_hits_box(*line, _grow(box, s / 2)):
                cost += w.leader_crossing
        if la is not None and lb is not None and segments_cross(la, lb):
            cost += w.leader_crossing
            conflicts += 1
        return cost + w.conflict * conflicts, conflicts


#: Annealing schedule: sweeps over the labels worth moving, and the
#: temperature (in cost units) at the first and last sweep.
_SWEEPS = 40
_HOT = 12.0
_COLD = 0.1


class _Live:
    """Where each label currently is, and what that costs."""

    def __init__(self, pairs: _Pairs, count: int) -> None:
        self.pairs = pairs
        self.chosen = [-1] * count

    def put(self, i: int, a: int) -> None:
        self.chosen[i] = a

    def near(self, i: int, a: int) -> list[int]:
        return [j for j in self.pairs.touching[i][a] if self.chosen[j] >= 0]

    def local(self, i: int, a: int) -> tuple[float, int]:
        """Fixed plus pairwise cost of label `i` at candidate `a`."""
        pairs = self.pairs
        c = pairs.options[i][a]
        cost, conflicts = c.cost, c.conflicts
        chosen = self.chosen
        hulls = pairs.hulls
        x0, y0, x1, y1 = hulls[i][a]
        for j in pairs.touching[i][a]:
            b = chosen[j]
            if b < 0:
                continue
            h = hulls[j][b]
            if h[0] >= x1 or x0 >= h[2] or h[1] >= y1 or y0 >= h[3]:
                continue
            pc, pk = pairs.cost(i, a, j, b)
            cost += pc
            conflicts += pk
        return cost, conflicts


def solve(options: Sequence[Sequence[Candidate]], *, spacing: float,
          order: Sequence[int] | None = None, weights: Weights | None = None,
          seed: int = 0, sweeps: int | None = None,
          fixed: Sequence[Candidate] = ()) -> Solution:
    """Choose one candidate per label, minimising fixed plus pairwise cost.

    `options[i]` are label `i`'s candidates, best listed first (the
    annealing pass samples the front of each list more often). `order` is
    the greedy order (default: as given). `fixed` are candidates already
    placed by an earlier call, which every label must also clear. `sweeps`
    is the number of annealing sweeps over the labels still worth moving
    (default 40). Every label needs at least one candidate.
    """
    w = weights or Weights()
    n = len(options)
    if any(not opts for opts in options):
        raise ValueError("every label needs at least one candidate")
    if n == 0:
        return Solution((), (), 0.0)
    everything = [list(o) for o in options] + [[c] for c in fixed]
    pairs = _Pairs(everything, spacing, w)
    live = _Live(pairs, len(everything))
    for k in range(n, len(everything)):
        live.put(k, 0)
    order = list(range(n)) if order is None else list(order)

    def best(i: int) -> int:
        winner, score = live.chosen[i], None
        for a in range(len(everything[i])):
            here = live.local(i, a)[0]
            if score is None or here < score - 1e-9:
                winner, score = a, here
        return winner

    # 1. greedy, in the caller's order
    for i in order:
        live.put(i, best(i))

    # 2. best response until nothing moves
    def settle(rounds: int = 8) -> None:
        for _ in range(rounds):
            moved = False
            for i in order:
                a = best(i)
                if (a != live.chosen[i] and live.local(i, a)[0]
                        < live.local(i, live.chosen[i])[0] - 1e-9):
                    live.put(i, a)
                    moved = True
            if not moved:
                return

    settle()

    # 3. anneal the labels that are not where they would be on their own --
    # in conflict, or pushed off their cheapest candidate by a neighbour --
    # together with their neighbours. Each step re-draws one label from all
    # its candidates at once, weighted by exp(-cost / temperature): a
    # heat-bath move, which at the end of the schedule is best response.
    floor = [min(c.cost for c in everything[i]) for i in range(n)]
    unhappy = [i for i in range(n)
               if live.local(i, live.chosen[i])[0] > floor[i] + 0.5]
    if unhappy:
        rng = random.Random(seed)
        pool = sorted(set(unhappy) | {j for i in unhappy
                                      for j in pairs.neighbours[i] if j < n})
        rounds = _SWEEPS if sweeps is None else sweeps
        hot, cold = _HOT, _COLD
        current = _energy(live, n)
        best_state, best_energy = list(live.chosen), current
        for sweep in range(rounds):
            t = hot * (cold / hot) ** (sweep / max(1, rounds - 1))
            visit = list(pool)
            rng.shuffle(visit)
            for i in visit:
                count = len(everything[i])
                if count < 2:
                    continue
                costs = [live.local(i, a)[0] for a in range(count)]
                low = min(costs)
                weights_ = [math.exp(-(c - low) / t) for c in costs]
                pick = rng.random() * sum(weights_)
                a = 0
                while a < count - 1 and pick >= weights_[a]:
                    pick -= weights_[a]
                    a += 1
                if a != live.chosen[i]:
                    current += costs[a] - costs[live.chosen[i]]
                    live.put(i, a)
                    if current < best_energy - 1e-9:
                        best_energy = current
                        best_state = list(live.chosen)
        for i in range(n):
            if live.chosen[i] != best_state[i]:
                live.put(i, best_state[i])
        settle()

    # 4. pairs still in conflict move together: two labels whose leaders
    # cross, or that sit on each other, often only come apart by trading
    # places, which no single move finds.
    for _ in range(_PAIR_ROUNDS):
        if not _repair_pairs(live, n, order):
            break
        settle()
    final = [i for i in range(n) if live.local(i, live.chosen[i])[1] > 0]
    return Solution(tuple(live.chosen[:n]), tuple(final), _energy(live, n))


#: Rounds of joint moves for pairs in conflict, and how many of each
#: label's cheapest candidates a joint move considers.
_PAIR_ROUNDS = 4
_PAIR_WIDTH = 24


def _repair_pairs(live: _Live, n: int, order: Sequence[int]) -> bool:
    """Re-place each conflicting pair jointly; True if anything improved."""
    pairs = live.pairs
    improved = False
    for i in order:
        a = live.chosen[i]
        for j in live.near(i, a):
            if j >= n:
                continue
            b = live.chosen[j]
            if pairs.cost(i, a, j, b)[1] == 0:
                continue
            before = (live.local(i, a)[0] + live.local(j, b)[0]
                      - pairs.cost(i, a, j, b)[0])
            live.put(i, -1)
            live.put(j, -1)
            li = sorted((live.local(i, x)[0], x)
                        for x in range(len(pairs.options[i])))[:_PAIR_WIDTH]
            lj = sorted((live.local(j, y)[0], y)
                        for y in range(len(pairs.options[j])))[:_PAIR_WIDTH]
            top = (before, a, b)
            for ci, x in li:
                if ci >= top[0]:
                    break
                for cj, y in lj:
                    total = ci + cj
                    if total >= top[0] - 1e-9:
                        break
                    total += pairs.cost(i, x, j, y)[0]
                    if total < top[0] - 1e-9:
                        top = (total, x, y)
            live.put(i, top[1])
            live.put(j, top[2])
            if (top[1], top[2]) != (a, b):
                improved = True
                a = top[1]
    return improved


def _energy(live: _Live, n: int) -> float:
    """Total cost: every label's fixed cost, and each pair once."""
    e = 0.0
    for i in range(n):
        a = live.chosen[i]
        e += live.pairs.options[i][a].cost
        for j in live.near(i, a):
            if j > i:
                e += live.pairs.cost(i, a, j, live.chosen[j])[0]
    return e



def stack(centres: Sequence[float], heights: Sequence[float], *, gap: float,
          top: float, bottom: float) -> list[float]:
    """Centres for boxes stacked in a column without overlap, moved least.

    `centres` are where each box would like its centre, `heights` its
    height; boxes keep their order (ties by index), stay `gap` apart and
    inside `[top, bottom]`, and the summed squared shift is the smallest
    possible (bounded isotonic regression by pooling adjacent violators).
    When the boxes do not fit between `top` and `bottom` the bounds are
    widened evenly about their middle -- the column overflows rather than
    overlapping. Returns one centre per box, in input order.
    """
    n = len(centres)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda k: (centres[k], k))
    hs = [heights[k] for k in order]
    offsets = [0.0]
    for a, b in zip(hs, hs[1:]):
        offsets.append(offsets[-1] + (a + b) / 2 + gap)
    need = offsets[-1] + hs[0] / 2 + hs[-1] / 2
    if need > bottom - top:
        middle = (top + bottom) / 2
        top, bottom = middle - need / 2, middle + need / 2
    blocks: list[list[float]] = []
    for j, k in enumerate(order):
        blocks.append([centres[k] - offsets[j], 1])
        while (len(blocks) > 1 and blocks[-2][0] / blocks[-2][1]
               > blocks[-1][0] / blocks[-1][1]):
            total, count = blocks.pop()
            blocks[-1][0] += total
            blocks[-1][1] += count
    lo = top + hs[0] / 2
    hi = bottom - hs[-1] / 2 - offsets[-1]
    levels = [max(lo, min(hi, total / count))
              for total, count in blocks for _ in range(int(count))]
    out = [0.0] * n
    for j, k in enumerate(order):
        out[k] = levels[j] + offsets[j]
    return out


#: A filled shape no larger than this (mm, both sides) is marker-sized.
_MARKER_SIZED = 3.0


def field_of(nodes, *, cell: float = 2.0) -> ObstacleField:
    """An `ObstacleField` of everything drawn in `nodes`, in page mm.

    Marker batches count point by point, stroked paths segment by segment,
    filled rectangles and marker-sized shapes by their box, other filled
    outlines (bands, areas, violins) by their polygon, and text and other
    primitives by their box. Raster images are left out: one covers the
    whole plot area it sits in.
    """
    field = ObstacleField(cell=cell)
    for art in nodes:
        for placed in resolve(art).values():
            node = placed.diagram
            prim = node.prim
            if prim is None:
                continue
            world = placed.world
            if isinstance(prim, PathPrim):
                filled = prim.filled and placed.style.fill not in (None, "none")
                for sub in prim.subpaths:
                    pts = [world.apply(v) for v in sub.points]
                    if not pts:
                        continue
                    if not filled:
                        for a, b in zip(pts, pts[1:]):
                            field.add_segment((a.x, a.y, b.x, b.y))
                        if sub.closed and len(pts) > 2:
                            field.add_segment((pts[-1].x, pts[-1].y,
                                               pts[0].x, pts[0].y))
                        continue
                    hull = Rect.hull(pts)
                    small = (hull.width <= _MARKER_SIZED
                             and hull.height <= _MARKER_SIZED)
                    square = all((abs(v.x - hull.x0) < 1e-6
                                  or abs(v.x - hull.x1) < 1e-6)
                                 and (abs(v.y - hull.y0) < 1e-6
                                      or abs(v.y - hull.y1) < 1e-6)
                                 for v in pts)
                    if small or square:
                        field.add_rect(hull, mark=small)
                    else:
                        field.add_area([(v.x, v.y) for v in pts])
            elif isinstance(prim, MarkerBatchPrim):
                scale = math.sqrt(abs(world.a * world.d - world.b * world.c))
                for x, y, size, _, _ in prim.records():
                    at = world.apply(Vec2(x, y))
                    half = size * scale / 2
                    field.add_box((at.x - half, at.y - half,
                                   at.x + half, at.y + half), mark=True)
            elif type(prim).__name__.startswith("Image"):
                continue
            elif placed.bbox is not None:
                field.add_rect(placed.bbox)
    return field


def emptiest(width: float, height: float, within: Rect, field: ObstacleField,
             *, pad: float, steps: int = 13,
             weights: Weights | None = None) -> tuple[Rect, float, bool]:
    """The least covered `width` x `height` spot inside `within`.

    Positions are a `steps` x `steps` grid over `within` less `pad`, corners
    included; each is scored by what it would cover in `field` (marks,
    lines, filled areas, text, all kept `pad` away), plus a small pull
    towards the nearest corner so that among equally empty spots the
    conventional one wins. Returns `(box, cost, clean)`, where `clean`
    says nothing at all is covered or crossed. Ties go to the earlier
    position (corners first: top right, top left, bottom right, bottom
    left), so the result is deterministic.
    """
    w = weights or Weights()
    lo, hi = within.x0 + pad, within.x1 - pad - width
    top, bottom = within.y0 + pad, within.y1 - pad - height
    if hi < lo - 1e-9 or bottom < top - 1e-9:
        raise ValueError("the box is larger than the region")
    spots = [(hi, top), (lo, top), (hi, bottom), (lo, bottom)]
    for r in range(steps):
        for c in range(steps - 1, -1, -1):
            spots.append((lo + (hi - lo) * c / (steps - 1),
                          top + (bottom - top) * r / (steps - 1)))
    corners = spots[:4]
    best = None
    for x, y in dict.fromkeys(spots):
        box = (x, y, x + width, y + height)
        cost, conflicts, covered = field.cost(_grow(box, pad), spacing=0.0,
                                              weights=w)
        clean = cost < 1e-9 and conflicts == 0 and covered == 0
        pull = min(math.hypot(x - cx, y - cy) for cx, cy in corners)
        total = cost + 0.02 * pull
        if best is None or total < best[1] - 1e-9:
            best = (Rect(*box), total, clean)
    return best
