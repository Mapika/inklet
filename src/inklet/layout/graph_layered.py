"""Sugiyama layered layout: the four passes, in millimetres.

The classic pipeline, with one adaptation that matters for a diagram library:
every vertex has a **size**, not a slot. A layered drawing of points can space
its ranks evenly and count integer positions; a layered drawing of labelled
boxes cannot, because "one position to the right" is 12mm for one box and 34mm
for the next. So ordering is done on positions (integers, where the classic
heuristics are stated and understood) and coordinate assignment is done in
millimetres, with a separation function that knows how wide each vertex is.

The four passes:

1. **Cycle breaking.** A depth-first walk in input order; an edge back to a
   vertex still on the stack is reversed for layout purposes only. The drawn
   arrow keeps the direction the author wrote.
2. **Layering.** Longest path from the sources, then a local tightening pass:
   a vertex with more successors than predecessors is pulled down as far as its
   successors allow, which is the move network simplex would make and costs a
   few passes over the vertices instead of a simplex tableau.
3. **Ordering.** Dummy vertices first, one per rank a long edge crosses, so a
   long edge is a chain of short ones and reserves a corridor of its own.
   Then median sort plus adjacent-swap transposition, a few sweeps each way,
   keeping the best ordering seen.
4. **Coordinates.** Brandes-Koepf: four biased passes that each straighten as
   many vertical chains as they can -- a long edge's dummy chain first, since
   a bent long edge is what a reader notices -- averaged into one drawing.

Everything here is integers, floats and lists in input order. No set iteration,
no randomness, no time: the same graph gives the same millimetres twice.
"""

from __future__ import annotations

import heapq
from typing import Sequence

__all__ = ["layered_positions"]

Size = tuple[float, float]
Point = tuple[float, float]

#: How many times the tightening pass may sweep the vertices. It converges in
#: two or three on every graph tried; the cap is there so a pathological input
#: cannot spin.
_TIGHTEN_PASSES = 8

#: Transposition rounds inside one ordering sweep. The pass is O(E) per round
#: and stops early when nothing swapped, so this is a ceiling and not a cost.
_TRANSPOSE_ROUNDS = 8

def layered_positions(
    sizes: Sequence[Size], edges: Sequence[tuple[int, int]], *,
    gap: float, rank_gap: float, lane: float, sweeps: int = 4,
    fit: float | None = None,
) -> tuple[list[Point], list[int], list[list[Point]]]:
    """Positions in (across, along) mm, the rank of each vertex, and the
    corridor reserved for each edge.

    `sizes` is one `(across, along)` pair per vertex -- width and height for a
    downward layout, height and width for a rightward one, which is the whole
    of what this module needs to know about orientation. `gap` separates two
    real vertices in a rank, `lane` separates anything from a long edge's
    corridor, and `rank_gap` is the clear space between one rank and the next.

    The third return value is the point this layout reserved for each edge on
    each rank it skips, in the direction the edge was *written* -- empty for a
    short edge, which crosses nothing and needs no corridor. Handing it back
    is the difference between a router that rediscovers the corridor and one
    that is simply told: the dummy chain is where the drawing already decided
    the line goes, and throwing it away was the one piece of work this module
    did that nothing downstream could see.

    `fit` is how many millimetres across the drawing has to come out in. It is
    not a guarantee and not a scale: the ranks are slid sideways until the
    boxes fit or nothing more can be won, and a rank wider than `fit` on its
    own cannot be helped by sliding it. None -- the default -- skips the pass
    entirely, because a drawing that already fits gains nothing from being
    narrower. `_compact_ranks` says why that is not the tautology it looks.
    """
    n = len(sizes)
    if n == 0:
        return [], [], []

    dag, flipped = _break_cycles(n, edges)
    rank = _rank(n, dag)
    across, along, dummy, segments, rank, chains = _expand(n, dag, rank, sizes, lane)

    layers = _layers(rank, len(across))
    pred, succ = _adjacency(len(across), segments)
    _order(layers, pred, succ, sweeps)
    across_at = _assign_across(layers, across, dummy, pred, succ, gap, lane,
                               chains, fit)
    along_at = _assign_along(layers, along, rank_gap)

    thick = [max((along[v] for v in layer), default=0.0) for layer in layers]
    corridors = []
    for index, chain in enumerate(chains):
        lane_points = _corridor(chain, across_at, along_at, rank, thick)
        corridors.append(lane_points[::-1] if flipped[index] else lane_points)
    return ([(across_at[i], along_at[rank[i]]) for i in range(n)], rank[:n],
            corridors)


def _corridor(chain: Sequence[int], across_at: Sequence[float],
              along_at: Sequence[float], rank: Sequence[int],
              thick: Sequence[float]) -> list[Point]:
    """One long edge's reserved lane, from the gap it enters to the gap it
    leaves.

    A dummy sits on a rank's centre line, level with the boxes either side of
    it, so a route that turned there would turn *inside* a rank and have to
    dodge whatever shares it. The two extra points put the turn in the clear
    space between ranks instead, which is the only place across a layered
    drawing where nothing is in the way. It is the same reason the layout
    reserved the lane at all.
    """
    if not chain:
        return []
    points = [(across_at[d], along_at[rank[d]]) for d in chain]
    first, last = rank[chain[0]], rank[chain[-1]]
    return ([(points[0][0], _between(along_at, thick, first - 1, first))]
            + points
            + [(points[-1][0], _between(along_at, thick, last, last + 1))])


def _between(along_at: Sequence[float], thick: Sequence[float],
             upper: int, lower: int) -> float:
    """The middle of the clear space between two neighbouring ranks."""
    if not 0 <= upper < len(along_at) or not 0 <= lower < len(along_at):
        return along_at[max(0, min(len(along_at) - 1, upper))]
    return ((along_at[upper] + thick[upper] / 2.0)
            + (along_at[lower] - thick[lower] / 2.0)) / 2.0


# -- 1. cycle breaking ----------------------------------------------------


def _break_cycles(n: int, edges: Sequence[tuple[int, int]]
                  ) -> tuple[list[tuple[int, int]], list[bool]]:
    """Every edge, oriented so the result is acyclic, and which ones turned.

    Greedy depth-first: reversing exactly the back edges of a DFS forest always
    leaves a DAG, and walking the vertices and their out-edges in input order
    is what makes *which* edges get reversed a property of the input rather
    than of the hash seed.
    """
    out: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for k, (u, v) in enumerate(edges):
        out[u].append((v, k))

    state = [0] * n                       # 0 unseen, 1 on the stack, 2 done
    flipped = [False] * len(edges)
    for start in range(n):
        if state[start]:
            continue
        state[start] = 1
        stack = [(start, 0)]
        while stack:
            u, i = stack[-1]
            if i == len(out[u]):
                state[u] = 2
                stack.pop()
                continue
            stack[-1] = (u, i + 1)
            v, k = out[u][i]
            if state[v] == 1:
                flipped[k] = True
            elif state[v] == 0:
                state[v] = 1
                stack.append((v, 0))
    return ([(v, u) if flipped[k] else (u, v) for k, (u, v) in enumerate(edges)],
            flipped)


# -- 2. layering ----------------------------------------------------------


def _rank(n: int, dag: Sequence[tuple[int, int]]) -> list[int]:
    """Longest path from the sources, then tightened."""
    succ: list[list[int]] = [[] for _ in range(n)]
    pred: list[list[int]] = [[] for _ in range(n)]
    indeg = [0] * n
    for u, v in dag:
        succ[u].append(v)
        pred[v].append(u)
        indeg[v] += 1

    ready = [i for i in range(n) if indeg[i] == 0]
    heapq.heapify(ready)                  # lowest index first: a stable order
    order: list[int] = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in succ[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(ready, v)

    rank = [0] * n
    for u in order:
        for v in succ[u]:
            if rank[v] < rank[u] + 1:
                rank[v] = rank[u] + 1

    _tighten(n, pred, succ, rank)
    floor = min(rank)
    return [r - floor for r in rank]


def _tighten(n: int, pred: Sequence[Sequence[int]], succ: Sequence[Sequence[int]],
             rank: list[int]) -> None:
    """Shorten the edges nobody is holding taut.

    Longest-path layering pins every vertex against its predecessors, which
    leaves a vertex with one parent and four children sitting a whole rank
    above where it wants to be and four long edges hanging off it. The total
    edge length is linear in a vertex's rank with slope `indegree - outdegree`,
    so a vertex with more successors than predecessors strictly improves the
    drawing by moving as far down as its successors allow -- and the converse
    upward. That is the direction network simplex would take, arrived at by
    local descent, which is exact for this objective on each vertex in turn.
    """
    for _ in range(_TIGHTEN_PASSES):
        moved = False
        for v in range(n):
            up, down = len(pred[v]), len(succ[v])
            if down > up and succ[v]:
                target = min(rank[w] for w in succ[v]) - 1
                if target > rank[v]:
                    rank[v] = target
                    moved = True
            elif up > down and pred[v]:
                target = max(rank[w] for w in pred[v]) + 1
                if target < rank[v]:
                    rank[v] = target
                    moved = True
            elif succ[v]:
                # Balanced in and out: moving costs nothing, so take the move
                # that keeps a vertex next to what consumes it. This is what
                # frees a source further up -- an input two ranks above the
                # step that reads it can only descend once the step between
                # them has, and neither move pays for itself alone.
                target = min(rank[w] for w in succ[v]) - 1
                if target > rank[v]:
                    rank[v] = target
                    moved = True
        if not moved:
            return


# -- 3. dummies and ordering ----------------------------------------------


def _expand(n: int, dag: Sequence[tuple[int, int]], rank: list[int],
            sizes: Sequence[Size], lane: float
            ) -> tuple[list[float], list[float], list[bool],
                       list[tuple[int, int]], list[int], list[list[int]]]:
    """Replace every long edge with a chain of zero-width dummy vertices.

    A dummy is not a placeholder for a picture; it is a *reservation*. It takes
    part in ordering and in coordinate assignment exactly as a box does, so the
    ranks a long edge crosses leave a corridor for it instead of closing up and
    forcing the line over a label.
    """
    across = [float(sizes[i][0]) for i in range(n)]
    along = [float(sizes[i][1]) for i in range(n)]
    dummy = [False] * n
    rank = list(rank)
    segments: list[tuple[int, int]] = []
    chains: list[list[int]] = []
    for u, v in dag:
        prev = u
        chain: list[int] = []
        for r in range(rank[u] + 1, rank[v]):
            d = len(across)
            across.append(0.0)
            along.append(0.0)
            dummy.append(True)
            rank.append(r)
            segments.append((prev, d))
            chain.append(d)
            prev = d
        segments.append((prev, v))
        chains.append(chain)
    return across, along, dummy, segments, rank, chains


def _layers(rank: Sequence[int], count: int) -> list[list[int]]:
    """Vertices by rank, in index order -- which for the dummies means in the
    order their edges were declared, so the initial ordering already reflects
    how the author wrote the graph."""
    depth = (max(rank) + 1) if rank else 0
    layers: list[list[int]] = [[] for _ in range(depth)]
    for v in range(count):
        layers[rank[v]].append(v)
    return layers


def _adjacency(count: int, segments: Sequence[tuple[int, int]]
               ) -> tuple[list[list[int]], list[list[int]]]:
    pred: list[list[int]] = [[] for _ in range(count)]
    succ: list[list[int]] = [[] for _ in range(count)]
    for u, v in segments:
        succ[u].append(v)
        pred[v].append(u)
    return pred, succ


def _order(layers: list[list[int]], pred: Sequence[Sequence[int]],
           succ: Sequence[Sequence[int]], sweeps: int) -> None:
    """Median sort and transposition, alternating direction, best kept.

    Both heuristics are from Gansner et al.: the median sort moves a vertex to
    where its neighbours are, and transposition then swaps adjacent pairs while
    that removes crossings. Neither alone is much good; together they get
    within a few crossings of what a human would draw.
    """
    best = [list(layer) for layer in layers]
    fewest = _crossings(layers, succ)
    for sweep in range(max(0, sweeps) * 2):
        downward = sweep % 2 == 0
        span = (range(1, len(layers)) if downward
                else range(len(layers) - 2, -1, -1))
        neighbours = pred if downward else succ
        for r in span:
            layers[r] = _median_sort(layers[r], layers[r - 1 if downward else r + 1],
                                     neighbours)
        _transpose(layers, pred, succ)
        count = _crossings(layers, succ)
        if count < fewest:
            fewest = count
            best = [list(layer) for layer in layers]
    for r, layer in enumerate(best):
        layers[r] = layer


def _median_sort(layer: Sequence[int], fixed: Sequence[int],
                 adj: Sequence[Sequence[int]]) -> list[int]:
    """Sort a rank by the median position of each vertex's neighbours in the
    rank next to it. A vertex with no neighbours there keeps its share of the
    row, rather than being swept to one end."""
    place = {v: i for i, v in enumerate(fixed)}
    span = max(1, len(fixed) - 1)
    keys: list[float] = []
    for i, v in enumerate(layer):
        spots = sorted(place[w] for w in adj[v] if w in place)
        if not spots:
            keys.append(i / max(1, len(layer) - 1) * span)
        elif len(spots) % 2:
            keys.append(float(spots[len(spots) // 2]))
        else:
            mid = len(spots) // 2
            keys.append((spots[mid - 1] + spots[mid]) / 2.0)
    return [layer[i] for i in sorted(range(len(layer)), key=lambda i: (keys[i], i))]


def _transpose(layers: list[list[int]], pred: Sequence[Sequence[int]],
               succ: Sequence[Sequence[int]]) -> None:
    """Swap adjacent pairs while it removes crossings. Strictly fewer, so the
    loop cannot cycle between two equally good orderings."""
    for _ in range(_TRANSPOSE_ROUNDS):
        swapped = False
        for r, layer in enumerate(layers):
            above = {v: i for i, v in enumerate(layers[r - 1])} if r else {}
            below = ({v: i for i, v in enumerate(layers[r + 1])}
                     if r + 1 < len(layers) else {})
            for i in range(len(layer) - 1):
                a, b = layer[i], layer[i + 1]
                here = (_pair_crossings(a, b, pred, above)
                        + _pair_crossings(a, b, succ, below))
                there = (_pair_crossings(b, a, pred, above)
                         + _pair_crossings(b, a, succ, below))
                if there < here:
                    layer[i], layer[i + 1] = b, a
                    swapped = True
        if not swapped:
            return


def _pair_crossings(left: int, right: int, adj: Sequence[Sequence[int]],
                    place: dict[int, int]) -> int:
    """Crossings between two vertices' edges into one adjacent rank, given that
    `left` sits to the left of `right`."""
    if not place:
        return 0
    total = 0
    for a in adj[left]:
        pa = place.get(a)
        if pa is None:
            continue
        for b in adj[right]:
            pb = place.get(b)
            if pb is not None and pb < pa:
                total += 1
    return total


def _crossings(layers: Sequence[Sequence[int]],
               succ: Sequence[Sequence[int]]) -> int:
    total = 0
    for r in range(len(layers) - 1):
        place = {v: i for i, v in enumerate(layers[r + 1])}
        pairs = [(i, place[w]) for i, v in enumerate(layers[r])
                 for w in succ[v] if w in place]
        for i in range(len(pairs)):
            ai, aj = pairs[i]
            for j in range(i + 1, len(pairs)):
                bi, bj = pairs[j]
                if (ai - bi) * (aj - bj) < 0:
                    total += 1
    return total


# -- 4. coordinates -------------------------------------------------------
#
# Brandes and Koepf, "Fast and Simple Horizontal Coordinate Assignment" (2002).
# The idea is worth stating because it is what makes a layered drawing look
# drawn: pick chains of vertices that *should* be vertically aligned -- a long
# edge's dummies above all, since a bent long edge is the most visible defect a
# layered drawing has -- then compact everything else around those chains
# rather than the other way round.
#
# It runs four times: aligning upward and downward, biased left and right. Each
# pass is a legal drawing on its own, and the four disagree about which chains
# to straighten. The published answer to that is to average the two middle
# values per vertex, which keeps what all four agree on and splits the
# difference where they do not.
#
# The one extension here is that separation is a function of the pair rather
# than a constant, because these vertices are boxes with words in them.


def _assign_across(layers: Sequence[Sequence[int]], across: Sequence[float],
                   dummy: Sequence[bool], pred: Sequence[Sequence[int]],
                   succ: Sequence[Sequence[int]], gap: float, lane: float,
                   chains: Sequence[Sequence[int]] = (),
                   fit: float | None = None) -> list[float]:
    """Positions across the ranks, in millimetres, nothing overlapping."""
    count = len(across)
    if not count:
        return []

    def sep(a: int, b: int) -> float:
        clear = lane if (dummy[a] or dummy[b]) else gap
        return (across[a] + across[b]) / 2.0 + clear

    marked = _type_one_conflicts(layers, pred, dummy)
    runs = [_bk_run(layers, pred, succ, marked, sep, count, upward, rightward)
            for upward in (False, True) for rightward in (False, True)]
    at = _balance(runs, count)
    _enforce(layers, at, sep)
    _settle(layers, at, sep, pred, succ, dummy, across)
    if fit is not None and _overflow(
            [_rank_span(layer, at, dummy, across) for layer in layers], fit):
        # Only when it does not fit. A drawing already inside the column comes
        # out exactly as the settling pass left it, which is what keeps every
        # graph that never asked to be fitted byte-identical.
        _compact_ranks(layers, at, pred, succ, dummy, across, fit)
    for _ in range(_STRAIGHTEN_ROUNDS):
        # After settling, never during it: this moves corridors only, into the
        # room the boxes have already finished claiming, so a drawing with no
        # long edges comes out of here exactly as it always did.
        if not _straighten(layers, at, sep, chains, pred, succ):
            break
    return at


def _type_one_conflicts(layers: Sequence[Sequence[int]],
                        pred: Sequence[Sequence[int]],
                        dummy: Sequence[bool]) -> set[tuple[int, int]]:
    """Edges that cross a long edge's own segment, which must never be aligned.

    An *inner* segment joins two dummies -- it is the middle of a long edge.
    Straightening something that crosses it would put a kink in the long edge
    to take one out of a short one, which is the wrong trade every time.
    """
    marked: set[tuple[int, int]] = set()
    if len(layers) < 3:
        return marked
    place = _places(layers)
    for i in range(1, len(layers) - 1):
        upper, lower = layers[i], layers[i + 1]
        k0, scan = 0, 0
        for k1, v in enumerate(lower):
            inner = next((u for u in pred[v] if dummy[u]), None) if dummy[v] else None
            if inner is None and k1 != len(lower) - 1:
                continue
            edge = len(upper) - 1 if inner is None else place[inner]
            while scan <= k1:
                for u in pred[lower[scan]]:
                    if place[u] < k0 or place[u] > edge:
                        marked.add((u, lower[scan]))
                        marked.add((lower[scan], u))
                scan += 1
            k0 = edge
    return marked


def _places(layers: Sequence[Sequence[int]]) -> dict[int, int]:
    return {v: k for layer in layers for k, v in enumerate(layer)}


def _bk_run(layers: Sequence[Sequence[int]], pred: Sequence[Sequence[int]],
            succ: Sequence[Sequence[int]], marked: set[tuple[int, int]],
            sep, count: int, upward: bool, rightward: bool) -> list[float]:
    """One of the four passes. Reversing the ranks turns "align to the rank
    above" into "align to the rank below", and reversing each rank turns a
    left bias into a right one, so the same twenty lines serve all four."""
    view = [list(reversed(layer)) if rightward else list(layer)
            for layer in layers]
    if upward:
        view.reverse()
    above = succ if upward else pred

    place = _places(view)
    home = {v: i for i, layer in enumerate(view) for v in layer}
    root = list(range(count))
    align = list(range(count))

    for i in range(1, len(view)):
        reached = -1
        for v in view[i]:
            spots = sorted(place[u] for u in above[v])
            if not spots:
                continue
            for m in sorted({(len(spots) - 1) // 2, len(spots) // 2}):
                if align[v] != v:
                    break
                u = view[i - 1][spots[m]]
                if (u, v) not in marked and reached < spots[m]:
                    align[u] = v
                    root[v] = root[u]
                    align[v] = root[v]
                    reached = spots[m]

    at = _compact(view, place, home, root, align, sep, count)
    return [-value for value in at] if rightward else at


def _compact(view: Sequence[Sequence[int]], place: dict[int, int],
             home: dict[int, int], root: Sequence[int], align: Sequence[int],
             sep, count: int) -> list[float]:
    """Push every block as far left as its left neighbours allow.

    The published version recurses on the block to the left; this one
    topologically sorts the blocks by that same dependency and walks them in
    order. Same answer, and no stack limit on a graph deep enough to matter.
    """
    blocks = [v for v in range(count) if root[v] == v]
    needs: dict[int, list[int]] = {}
    for r in blocks:
        left: list[int] = []
        w = r
        while True:
            k = place[w]
            if k:
                left.append(root[view[home[w]][k - 1]])
            w = align[w]
            if w == r:
                break
        needs[r] = left

    sink = list(range(count))
    shift = [float("inf")] * count
    at = [0.0] * count
    for r in _in_dependency_order(blocks, needs):
        at[r] = 0.0
        w = r
        while True:
            k = place[w]
            if k:
                u = view[home[w]][k - 1]
                anchor = root[u]
                if sink[r] == r:
                    sink[r] = sink[anchor]
                if sink[r] != sink[anchor]:
                    sink_at = sink[anchor]
                    shift[sink_at] = min(shift[sink_at],
                                         at[r] - at[anchor] - sep(u, w))
                else:
                    at[r] = max(at[r], at[anchor] + sep(u, w))
            w = align[w]
            if w == r:
                break

    out = [0.0] * count
    for v in range(count):
        out[v] = at[root[v]]
        slide = shift[sink[root[v]]]
        if slide < float("inf"):
            out[v] += slide
    return out


def _in_dependency_order(blocks: Sequence[int],
                         needs: dict[int, list[int]]) -> list[int]:
    """Blocks, each after the ones it is pushed away from. Lowest index first
    among the ready ones, so the order is the input's and not the hash's."""
    waiting = {r: 0 for r in blocks}
    feeds: dict[int, list[int]] = {r: [] for r in blocks}
    for r, left in needs.items():
        for other in left:
            if other != r:
                feeds[other].append(r)
                waiting[r] += 1
    ready = [r for r in blocks if waiting[r] == 0]
    heapq.heapify(ready)
    order: list[int] = []
    while ready:
        r = heapq.heappop(ready)
        order.append(r)
        for nxt in feeds[r]:
            waiting[nxt] -= 1
            if waiting[nxt] == 0:
                heapq.heappush(ready, nxt)
    if len(order) < len(blocks):
        placed = set(order)
        order.extend(r for r in blocks if r not in placed)
    return order


def _balance(runs: Sequence[Sequence[float]], count: int) -> list[float]:
    """Average the two middle values of the four passes.

    The passes are first slid onto a common reference -- the left-biased ones
    by their left edge, the right-biased ones by their right -- against
    whichever came out narrowest, which is the published recipe and the reason
    the average is not simply four drawings smeared together.
    """
    narrowest = min(range(len(runs)), key=lambda i: max(runs[i]) - min(runs[i]))
    low, high = min(runs[narrowest]), max(runs[narrowest])
    aligned = []
    for index, run in enumerate(runs):
        slide = (low - min(run)) if index % 2 == 0 else (high - max(run))
        aligned.append([value + slide for value in run])
    out = []
    for v in range(count):
        values = sorted(run[v] for run in aligned)
        out.append((values[1] + values[2]) / 2.0)
    return out


def _enforce(layers: Sequence[Sequence[int]], at: list[float], sep) -> None:
    """Make the separations true again after the averaging.

    Each of the four passes leaves every rank properly spaced, but different
    vertices take their value from different passes, and the mean of two legal
    drawings is not one. The violations are fractions of a millimetre; a single
    left-to-right pass per rank removes them, and a rank that was already legal
    is not touched at all.
    """
    for layer in layers:
        for i in range(1, len(layer)):
            need = at[layer[i - 1]] + sep(layer[i - 1], layer[i])
            if at[layer[i]] < need:
                at[layer[i]] = need


def _assign_along(layers: Sequence[Sequence[int]], along: Sequence[float],
                  rank_gap: float) -> list[float]:
    """The centre line of each rank. A rank is as thick as its tallest member,
    and the gap between two ranks is clear space, not centre-to-centre: that is
    what keeps the arrows between two ranks the same length down the figure
    however tall the boxes happen to be."""
    centres: list[float] = []
    front = 0.0
    for layer in layers:
        thickness = max((along[v] for v in layer), default=0.0)
        centres.append(front + thickness / 2.0)
        front += thickness + rank_gap
    return centres


# -- 5. settling ----------------------------------------------------------
#
# Brandes-Koepf hands back the average of four drawings, and an average of two
# legal drawings that disagree is a drawing that agrees with neither. On a
# graph whose ranks are all the same width the four barely differ and the
# average is the answer. On a pipeline with a couple of skip connections they
# differ a great deal -- the left-biased passes put the spine hard left and the
# right-biased ones stack it against whichever long-edge lane happens to be in
# that rank -- and the average is a staircase where the eye wants a column.
#
# So the coordinates are settled afterwards. Each vertex would like to be at
# the median of its neighbours above and below; within a rank that wish is a
# vector of desired positions, and the closest arrangement to it that still
# separates every pair is a weighted isotonic regression, which pool-adjacent-
# violators solves exactly in one pass. Dummies are weighted eight to one,
# which is how a long edge comes out straight while the boxes give way.
#
# Sweeping down and then up is a Gauss-Seidel iteration on that projection, and
# because the ordering is fixed it can never introduce a crossing. What it is
# *not* is a contraction, and the reason is worth writing down because it took
# a while to find. The isotonic step can push a vertex past its own wish to
# make room for a rank-mate, and the next rank reads that pushed position as
# where its neighbour wants to be. On `examples/graph.py` the corridor for
# `batch -> panels` does it in a two-rank loop: the lower dummy wishes for
# 3.46mm, its rank shoves it to 6.89mm, the upper dummy and `batch` adopt
# 6.89mm as *their* wish, and one sweep later the lower dummy is shoved from
# 6.89mm to 10.3mm. Nothing pulls back, so the drawing walks sideways for as
# long as it is swept -- 103.7mm, 205.4mm, wider -- which is why nothing has
# ever been allowed to call this twice.
#
# Damping does not fix a drift, and neither does the honest repair of making
# each rank an exact minimiser: the sweep then converges, and converges to a
# worse drawing. Three variants were built and measured on `examples/graph.py`
# against a 69.2mm lower bound (the widest rank, packed):
#
#   exact weighted-L1 per rank (block coordinate descent)   115.4mm, idempotent
#   exact weighted-L2 per rank (681 sweeps to converge)      93.2mm, idempotent
#   corridors moved as one rigid piece                       86.0mm, 2-cycle
#   this pass, stopped at sweep 24                           78.5mm, divergent
#
# The narrow drawing is a *transient*. Compaction and the drift are the same
# motion, and the sweep count was tuned to the moment the first has finished
# and the second has not yet taken over -- which is not a thing to leave a
# tuned constant in charge of. So the pass keeps the best drawing it has seen
# and stops when sweeping stops improving on it, exactly as `_order` above
# keeps the ordering with the fewest crossings. That makes the width a stated
# criterion instead of a side effect of a loop bound, and it makes a second
# call safe: the drawing it starts from is in the comparison, so calling this
# again can only leave it alone or narrow it. On every graph here it leaves it
# alone.

#: A ceiling on the sweeps, not the schedule -- the pass stops when sweeping
#: stops improving. Each sweep carries information one rank, so a deep drawing
#: needs a few dozen before it has even seen itself; 64 is past where anything
#: here is still improving, and the patience below is what actually ends it.
_SETTLE_SWEEPS = 64

#: Sweeps without an improvement that end the pass. The best drawing on
#: `examples/graph.py` is sweep 24's and sweeps 25-30 hover a tenth of a
#: millimetre behind it before the drift takes over, so a patience shorter
#: than that would stop on a plateau and call it a summit.
_SETTLE_PATIENCE = 8

#: What a long edge's corridor is worth against a box when a rank is too tight
#: for both to sit where they want. Less than a box, which is not obvious and
#: is the whole trick: the corridor's *wish* is already "wherever the rest of
#: me is", so a light weight lets it be displaced sideways as one piece and
#: stay straight, while a heavy one would freeze it where the previous pass
#: left it and bend the column of boxes around it instead.
_DUMMY_WEIGHT = 0.25

#: What one edge is worth in the pull on its endpoints, by what it joins. A
#: kink in the middle of a long edge is the most visible defect a layered
#: drawing has, so dummy-to-dummy dominates. Box-to-corridor is the weakest of
#: the three on purpose: the corridor is a line and has to be straight, while
#: the box at the end of it only has to be somewhere an arrow can reach, and
#: letting the corridor drag its endpoint sideways bends the spine of real
#: boxes -- which is the drawing the reader is actually following.
_PULL_BOTH_DUMMY = 8.0
_PULL_BOTH_REAL = 1.0
_PULL_MIXED = 0.5


#: How many times the corridors are slid home. One round is enough unless two
#: corridors share a rank, where the room the first one leaves is what the
#: second one gets; three is past the point where anything moves on the graphs
#: here, and a graph with no long edges never enters the loop at all.
_STRAIGHTEN_ROUNDS = 3

#: A corridor closer than this to where it already is counts as home. Well
#: under what the renderer prints, so a round that only jitters stops the loop
#: instead of spending the next two rounds on nothing.
_STRAIGHT_EPS = 1e-6


def _straighten(layers: Sequence[Sequence[int]], at: list[float], sep,
                chains: Sequence[Sequence[int]],
                pred: Sequence[Sequence[int]],
                succ: Sequence[Sequence[int]]) -> bool:
    """Slide each corridor, whole, towards the line between its endpoints.

    The settling pass cannot do this. It weighs a dummy's pull towards the next
    dummy far above its pull towards a box, which is exactly what keeps a long
    edge straight -- but a chain of two or more dummies then holds *itself* in
    place: every member's wish is where its neighbour in the chain already is,
    and the endpoints never get a vote. Brandes-Koepf can leave such a chain
    far outside the drawing (it is the leftmost thing in its rank, so nothing
    pushes back) and the average of four passes keeps it there. Nobody noticed
    while the corridor was a number the router threw away; it is a visible
    40mm of white space as soon as the arrow actually runs down it.

    So the chain is moved as one rigid piece, to the midpoint of its two
    endpoints, clamped to what its rank neighbours leave room for. Returns
    whether anything moved, so the caller can stop early.
    """
    if not chains:
        return False
    place = _places(layers)
    home = {v: r for r, layer in enumerate(layers) for v in layer}
    moved = False
    for chain in chains:
        if not chain:
            continue
        low, high = float("-inf"), float("inf")
        for d in chain:
            layer = layers[home[d]]
            k = place[d]
            if k:
                left = layer[k - 1]
                low = max(low, at[left] + sep(left, d))
            if k + 1 < len(layer):
                right = layer[k + 1]
                high = min(high, at[right] - sep(d, right))
        if low > high:
            # The ranks disagree about where there is room. Leaving it is the
            # honest answer: forcing a value here would push a box sideways
            # for a corridor, which is the trade this module never makes.
            continue
        ends = [at[u] for u in pred[chain[0]]] + [at[v] for v in succ[chain[-1]]]
        wish = sum(ends) / len(ends) if ends else at[chain[0]]
        target = _one_bend(ends, min(max(wish, low), high), low, high)
        if any(abs(at[d] - target) > _STRAIGHT_EPS for d in chain):
            moved = True
        for d in chain:
            at[d] = target
    return moved


def _one_bend(ends: Sequence[float], middle: float,
              low: float, high: float) -> float:
    """Where to park a corridor: on one of its endpoints if there is room,
    otherwise where the midpoint was clamped to.

    Halfway between two endpoints is the shortest arrow, and it is also two
    bends -- one leaving the source, one entering the target -- for an edge
    whose whole point is that it runs straight down the page. Sitting on an
    endpoint spends the same millimetres and draws one bend instead of two,
    and a reader follows one bend without noticing it. Only the rank
    neighbours can veto it, which is the same room the midpoint had to fit in.

    With both endpoints free the *upper* one wins -- `ends` is in reading
    order, source side first. That is where the bend is cheapest to read: the
    arrow leaves the box it came from going the way the whole drawing goes,
    runs straight down the page, and turns once at the far end, next to the
    head, where the reader is looking anyway.
    """
    for end in ends:
        if low - _STRAIGHT_EPS <= end <= high + _STRAIGHT_EPS:
            return end
    return middle


def _settle(layers: Sequence[Sequence[int]], at: list[float], sep,
            pred: Sequence[Sequence[int]], succ: Sequence[Sequence[int]],
            dummy: Sequence[bool], across: Sequence[float]) -> None:
    """Pull every vertex towards its neighbours, rank by rank, and keep the
    best drawing the sweeps went through.

    "Best" is how wide the boxes come out, ties broken by how much edge the
    drawing spends -- the page is a fixed column, so nothing else matters
    until it fits, and among drawings that fit equally the shorter arrows win.
    The corridors are scored through that second term rather than through the
    first: a lane that has drifted out of the drawing costs eight times a box
    edge here and is pulled back in by `_straighten` afterwards either way.
    """
    weights = [_DUMMY_WEIGHT if flag else 1.0 for flag in dummy]

    def pull(v: int, w: int) -> float:
        return _pull(dummy, v, w)

    def score() -> tuple[float, float]:
        spread = [(at[v] - across[v] / 2.0, at[v] + across[v] / 2.0)
                  for v in range(len(across)) if not dummy[v]]
        width = (max(hi for _, hi in spread) - min(lo for lo, _ in spread)
                 if spread else 0.0)
        return width, _spent(at, succ, dummy)

    best, kept, waiting = score(), list(at), 0
    for step in range(_SETTLE_SWEEPS):
        span = (range(len(layers)) if step % 2 == 0
                else range(len(layers) - 1, -1, -1))
        for r in span:
            layer = layers[r]
            wish = []
            for v in layer:
                spots = [(at[w], pull(v, w))
                         for w in pred[v]] + [(at[w], pull(v, w))
                                              for w in succ[v]]
                wish.append(_weighted_median(spots) if spots else at[v])
            if len(layer) == 1:
                at[layer[0]] = wish[0]
            else:
                _isotonic(layer, at, sep, wish, [weights[v] for v in layer])
        here = score()
        if here < best:
            best, kept, waiting = here, list(at), 0
        else:
            waiting += 1
            if waiting >= _SETTLE_PATIENCE:
                break
    at[:] = kept


#: Rounds of rigid rank shifts the fitting pass will spend. Each round moves
#: the one rank that buys the most, so a round is a whole pass over the ranks
#: and the count is a ceiling, not a schedule: the pass stops the moment no
#: rank can improve on the drawing it has. Sixty is past where anything here
#: is still moving -- `examples/graph.py` widened to 20mm boxes stops at 38.
_FIT_ROUNDS = 60

#: An improvement smaller than this is not one. Well under what the renderer
#: prints, so a rank that can only jitter does not keep the loop alive.
_FIT_EPS = 1e-9


def _compact_ranks(layers: Sequence[Sequence[int]], at: list[float],
                   pred: Sequence[Sequence[int]], succ: Sequence[Sequence[int]],
                   dummy: Sequence[bool], across: Sequence[float],
                   limit: float) -> bool:
    """Slide whole ranks sideways until the drawing fits across `limit`.

    The settling pass cannot do this, and the reason is the one thing section 5
    above is careful to say: inside a sweep, compaction and the sideways drift
    are the same motion, so a rule that stops the drift stops the compaction
    too. Moving a rank *rigidly* is a different motion. It cannot disturb the
    order or the separations -- every vertex in the rank keeps its neighbours
    and its spacing -- so it can be accepted or refused on the drawing it
    produces, one rank at a time, which makes this a monotone descent with a
    fixed point rather than a sweep with a tuned stopping place.

    What it descends on is overflow first and edge length second, because the
    page is a fixed column: a drawing that fits has nothing left to gain from
    being narrower, and asking for it anyway buys crossings. So the pass has
    no opinion at all until the drawing is too wide, and stops having one the
    moment it is not -- after which the same rank shifts go on shortening
    edges, which is free.

    Returns whether anything moved.
    """
    spans = [_rank_span(layer, at, dummy, across) for layer in layers]
    if not any(span for span in spans):
        return False
    moved = False
    for _ in range(_FIT_ROUNDS):
        here = _fit_score(layers, at, spans, succ, dummy, limit)
        gain, pick = here, None
        for index, layer in enumerate(layers):
            if not layer:
                continue
            for shift in _fit_shifts(index, layers, at, spans, pred, succ,
                                     dummy, limit):
                if abs(shift) < _FIT_EPS:
                    continue
                trial = _shifted_score(index, layers, at, spans, succ, dummy,
                                       limit, shift)
                if trial < gain:
                    gain, pick = trial, (index, shift)
        if pick is None or gain >= here:
            break
        index, shift = pick
        for v in layers[index]:
            at[v] += shift
        if spans[index] is not None:
            low, high = spans[index]
            spans[index] = (low + shift, high + shift)
        moved = True
    return moved


def _rank_span(layer: Sequence[int], at: Sequence[float],
               dummy: Sequence[bool], across: Sequence[float]
               ) -> tuple[float, float] | None:
    """How far one rank's real boxes reach, or None for a rank of corridors.

    Corridors are left out for the same reason `_settle` scores them out of
    the width: a lane that has drifted wide is `_straighten`'s to pull back,
    and counting it here would have the boxes give way to it instead.
    """
    real = [v for v in layer if not dummy[v]]
    if not real:
        return None
    return (min(at[v] - across[v] / 2.0 for v in real),
            max(at[v] + across[v] / 2.0 for v in real))


def _fit_shifts(index: int, layers: Sequence[Sequence[int]],
                at: Sequence[float], spans: Sequence[tuple[float, float] | None],
                pred: Sequence[Sequence[int]], succ: Sequence[Sequence[int]],
                dummy: Sequence[bool], limit: float) -> list[float]:
    """Every shift of one rank that could be the best one.

    Both terms of the score are piecewise linear in the shift, so the minimum
    sits on a breakpoint and there is no line search to tune. An edge bends
    where the rank's end of it passes the other end; the width bends where
    this rank stops being the widest thing in the drawing. Testing exactly
    those is what makes the descent exact instead of a ladder of guesses.
    """
    out = [0.0]
    for v in layers[index]:
        for w in (*pred[v], *succ[v]):
            out.append(at[w] - at[v])
    span = spans[index]
    if span is not None:
        rest = [other for i, other in enumerate(spans)
                if i != index and other is not None]
        if rest:
            low = min(other[0] for other in rest)
            high = max(other[1] for other in rest)
            out.append(low - span[0])
            out.append(high - span[1])
            out.append(low + limit - span[1])
            out.append(high - limit - span[0])
    return out


def _fit_score(layers: Sequence[Sequence[int]], at: Sequence[float],
               spans: Sequence[tuple[float, float] | None],
               succ: Sequence[Sequence[int]], dummy: Sequence[bool],
               limit: float) -> tuple[float, float]:
    """Overflow past the column, then the edge length spent."""
    return (_overflow(spans, limit), _spent(at, succ, dummy))


def _shifted_score(index: int, layers: Sequence[Sequence[int]],
                   at: Sequence[float],
                   spans: Sequence[tuple[float, float] | None],
                   succ: Sequence[Sequence[int]], dummy: Sequence[bool],
                   limit: float, shift: float) -> tuple[float, float]:
    """The score if one rank moved by `shift`, without moving it.

    Only the edges with exactly one end in the rank change length, and only
    this rank's span moves, so the whole trial costs what the rank touches
    rather than what the drawing holds.
    """
    trial = list(spans)
    span = spans[index]
    if span is not None:
        trial[index] = (span[0] + shift, span[1] + shift)
    inside = set(layers[index])
    spent = 0.0
    for u in range(len(dummy)):
        for v in succ[u]:
            here, there = at[u], at[v]
            if (u in inside) != (v in inside):
                if u in inside:
                    here += shift
                else:
                    there += shift
            elif u in inside:
                continue        # both ends move together: length unchanged
            spent += _pull(dummy, u, v) * abs(here - there)
    return (_overflow(trial, limit), spent)


def _overflow(spans: Sequence[tuple[float, float] | None],
              limit: float) -> float:
    """How much wider than the column the boxes reach, or zero if they fit."""
    real = [span for span in spans if span is not None]
    if not real:
        return 0.0
    width = max(high for _, high in real) - min(low for low, _ in real)
    return max(0.0, width - limit)


def _pull(dummy: Sequence[bool], v: int, w: int) -> float:
    """What one edge is worth in the pull on its endpoints, by what it joins."""
    if dummy[v] and dummy[w]:
        return _PULL_BOTH_DUMMY
    if dummy[v] or dummy[w]:
        return _PULL_MIXED
    return _PULL_BOTH_REAL


def _spent(at: Sequence[float], succ: Sequence[Sequence[int]],
           dummy: Sequence[bool]) -> float:
    """Total weighted edge length across the ranks."""
    return sum(_pull(dummy, u, v) * abs(at[u] - at[v])
               for u in range(len(dummy)) for v in succ[u])


def _weighted_median(spots: Sequence[tuple[float, float]]) -> float:
    """Where the weighted sum of distances to the neighbours is least.

    A median rather than a mean because the cost of an edge is its length, not
    its length squared: a vertex with three neighbours on the left and one far
    to the right belongs on the left, not a third of the way across. When the
    weight splits exactly in two -- the chain case, one neighbour above and one
    below -- every point between them is equally good and the midpoint is the
    one that draws a straight line.
    """
    run = sorted(spots)
    half = sum(weight for _, weight in run) / 2.0
    seen = 0.0
    for index, (value, weight) in enumerate(run):
        seen += weight
        if seen > half + 1e-12:
            return value
        if abs(seen - half) <= 1e-12:
            return ((value + run[index + 1][0]) / 2.0
                    if index + 1 < len(run) else value)
    return run[-1][0]


def _isotonic(layer: Sequence[int], at: list[float], sep,
              wish: Sequence[float], weight: Sequence[float]) -> None:
    """The closest legal arrangement of one rank to what it wishes for.

    Subtracting the cumulative minimum separations turns "each vertex at least
    `sep` past the last" into "non-decreasing", which is ordinary isotonic
    regression; pool-adjacent-violators solves it exactly, in one pass, with no
    parameter to tune. Adding the offsets back gives millimetres again.
    """
    count = len(layer)
    offset = [0.0] * count
    for i in range(1, count):
        offset[i] = offset[i - 1] + sep(layer[i - 1], layer[i])

    values: list[float] = []
    masses: list[float] = []
    runs: list[int] = []
    for i in range(count):
        value, mass, run = wish[i] - offset[i], weight[i], 1
        while values and values[-1] > value:
            back, back_mass, back_run = values.pop(), masses.pop(), runs.pop()
            value = (value * mass + back * back_mass) / (mass + back_mass)
            mass += back_mass
            run += back_run
        values.append(value)
        masses.append(mass)
        runs.append(run)

    i = 0
    for value, run in zip(values, runs):
        for _ in range(run):
            at[layer[i]] = value + offset[i]
            i += 1
