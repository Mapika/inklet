"""Which filled polygon is painted over which, and the page geometry for it.

A vector renderer has no depth buffer. The order the fills are written in *is*
the visibility, so getting it wrong is not a slightly worse picture, it is the
back of the object drawn through the front of it.

Sorting by each facet's mean depth -- what `shade.sorted_facets` does on its
own -- is exact for a convex solid, where front-facing facets never overlap at
all, and it is the usual approximation everywhere else. The usual
approximation has two failure modes, and they want different answers:

**A wrong order.** Two facets overlap on the page, neither passes through the
other, and the mean of three depths puts the nearer one first. A long facet
seen almost edge-on has a mean depth near its middle while its near end reaches
much closer, so this is common the moment a surface folds back over itself. The
fix is not a better sort key -- there is no key, since "in front of" is not a
total order on polygons -- but to *ask the pairs* and then topologically sort
what they answer.

**No right order.** Two facets genuinely cross in view: along one part of the
region they share the first is nearer, along the rest the second is. No
sequence of two whole polygons draws that. The only fix is to cut one of them
along the line where the two planes meet, and that line is straight on the page
in both projections -- the projection of a 3D line is a line -- so the cut is
exact rather than approximated.

Both are settled by the same test. The depth difference between two planes is
zero along one line and one sign either side of it, so evaluating it at the
corners of the region the two polygons share settles the pair: all one sign
means an order exists and says which, mixed signs mean it does not.

The cost is one pass over the pairs that overlap on the page, found with the
same grid the path merge uses, which is why the two live in one file.
"""

from __future__ import annotations

import heapq
from dataclasses import replace

from .camera import View

__all__ = ["painter_sort", "box_of", "cells_of", "boxes_meet", "overlaps",
           "span"]


def _numpy():
    """numpy if it is installed, else None, imported once.

    `deps.have` re-imports on every ask, and this is asked once per sort pass.
    """
    global _NUMPY
    if _NUMPY is _UNASKED:
        try:
            import numpy
        except ImportError:
            _NUMPY = None
        else:
            _NUMPY = numpy
    return _NUMPY


_UNASKED = object()
_NUMPY = _UNASKED


# -- page geometry, shared with the path merge ----------------------------


def box_of(points) -> tuple[float, float, float, float]:
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def cells_of(box, x0: float, y0: float, step_x: float, step_y: float,
             side: int) -> list[tuple[int, int]]:
    """The grid cells a facet's bounding box covers, in a fixed order."""
    lo_x = max(min(int((box[0] - x0) / step_x), side - 1), 0)
    hi_x = max(min(int((box[2] - x0) / step_x), side - 1), 0)
    lo_y = max(min(int((box[1] - y0) / step_y), side - 1), 0)
    hi_y = max(min(int((box[3] - y0) / step_y), side - 1), 0)
    return [(cx, cy) for cx in range(lo_x, hi_x + 1)
            for cy in range(lo_y, hi_y + 1)]


def boxes_meet(a, b, slack: float = 0.0) -> bool:
    return not (a[2] < b[0] - slack or b[2] < a[0] - slack
                or a[3] < b[1] - slack or b[3] < a[1] - slack)


def overlaps(a, b, slack: float = 0.0) -> bool:
    """Separating-axis test, answering "unless proven apart, assume together".

    Both polygons are sequences of `(x, y)` pairs rather than `Vec2`, because
    this is the innermost loop of the whole shaded pipeline and a dataclass
    attribute lookup is not free at two hundred thousand calls.

    Only the edge normals of the two polygons are tried, which is exactly right
    for convex ones and merely conservative for the occasional concave patch
    that coplanar merging produces -- there it may fail to find an axis that
    exists, and report an overlap that is not one. That is the harmless
    direction.

    `slack` is how far two polygons may reach into each other and still count
    as apart. Facets that merely share an edge are the common case and are not
    an overlap in any sense either caller means.
    """
    for points in (a, b):
        px, py = points[-1]
        for qx, qy in points:
            # The outward normal of this edge, unnormalised; the slack is
            # scaled by its length instead, which saves a square root.
            nx, ny = qy - py, px - qx
            px, py = qx, qy
            length = (nx * nx + ny * ny) ** 0.5
            if length < 1e-12:
                continue
            # `span` written out twice rather than called: this is the
            # innermost loop of the shaded pipeline, it runs a few hundred
            # thousand times on a protein, and the call frame was a fifth of
            # it. The function stays, because it is the readable statement of
            # what these eight lines do.
            a_lo = a_hi = a[0][0] * nx + a[0][1] * ny
            for x, y in a:
                value = x * nx + y * ny
                if value < a_lo:
                    a_lo = value
                elif value > a_hi:
                    a_hi = value
            b_lo = b_hi = b[0][0] * nx + b[0][1] * ny
            for x, y in b:
                value = x * nx + y * ny
                if value < b_lo:
                    b_lo = value
                elif value > b_hi:
                    b_hi = value
            edge = slack * length
            if a_hi < b_lo + edge or b_hi < a_lo + edge:
                return False
    return True


def span(points, nx: float, ny: float) -> tuple[float, float]:
    """The polygon's extent along an axis. Written out rather than built from
    `min`/`max` over a comprehension: it runs a few million times a figure."""
    lo = hi = points[0][0] * nx + points[0][1] * ny
    for i in range(1, len(points)):
        value = points[i][0] * nx + points[i][1] * ny
        if value < lo:
            lo = value
        elif value > hi:
            hi = value
    return lo, hi


#: Below this many candidate pairs the array path is not worth its own setup:
#: building the corner array and slicing it costs more than a few thousand
#: calls to `overlaps`. Measured on the crossover, which is flat between about
#: five hundred and five thousand pairs.
_VECTOR_FLOOR = 2000

#: How many pairs the array path tests at a time. The whole run at once
#: allocates twelve arrays of it and falls out of cache; a chunk this size
#: keeps the working set inside L2 and was 1.35x the unchunked version on the
#: 344,000 pairs of `stress/meshes/brain-lh.obj`.
_CHUNK = 16384


def _which_overlap(corners, first, second, slack: float):
    """Which of the candidate pairs really overlap: `overlaps` for a whole run.

    Same question as `overlaps(corners[i], corners[j], slack)` asked once per
    pair, same answer *to the bit*, and that is a promise rather than a hope:
    the array path does the same multiplies and the same comparisons in the
    same order, so there is no reassociation for the rounding to differ over.
    `tests/test_three_order_vector.py` holds the two against each other on
    random polygons and on every pair the corpus asks about.

    Triangles are done as arrays and everything else one at a time. That is not
    a simplification of the geometry, it is where the meshes are: of the 687,884
    polygons the brain scan's 343,942 candidate pairs are made of, 679,327 are
    triangles. Only a coplanar patch that `sorted_facets` did not have to split
    comes out with four corners or more, and padding the array to the longest
    of them would cost every triangle pair four times the arithmetic to spare
    one percent of pairs a Python call.
    """
    numpy = _numpy() if len(first) >= _VECTOR_FLOOR else None
    if numpy is None:
        return [overlaps(corners[i], corners[j], slack)
                for i, j in zip(first, second)]

    tri = numpy.fromiter((len(c) == 3 for c in corners), dtype=bool,
                         count=len(corners))
    ii = numpy.asarray(first, dtype=numpy.intp)
    jj = numpy.asarray(second, dtype=numpy.intp)
    out = numpy.zeros(len(ii), dtype=bool)
    both = tri[ii] & tri[jj]
    # A ragged sequence of triangles and non-triangles is not an array, so the
    # corner table is built for the triangles alone and the rest keep their
    # tuples. `numpy.array(corners)` on a mixed list is an object array and
    # silently thirty times slower.
    points = numpy.zeros((len(corners), 3, 2))
    for index, corner in enumerate(corners):
        if len(corner) == 3:
            points[index] = corner
    _vector_overlaps(numpy, points, ii[both], jj[both], slack,
                     out, numpy.flatnonzero(both))
    for k in numpy.flatnonzero(~both):
        out[k] = overlaps(corners[ii[k]], corners[jj[k]], slack)
    return out


def _vector_overlaps(numpy, points, ii, jj, slack: float, out, where) -> None:
    """The separating-axis test over triangle pairs, six axes at a time.

    Sets `out[where]` for the pairs that overlap and leaves the rest, which is
    why the caller hands over a zeroed array. The axes are the six edge
    normals, unnormalised, with the slack scaled by the edge length instead of
    the normal being -- exactly what `overlaps` does, and for the same reason.

    A pair that separates on one axis is dropped from the working set before
    the next, the way the scalar test returns on the spot. Nothing is lost by
    it: `together` only ever goes false, so an axis evaluated for an already
    separated pair could not change the answer, and each row's arithmetic is
    the same arithmetic whatever else is in the array beside it. On the brain
    scan's 166,794 triangle pairs the survivors run 77.5, 63.5, 55.2, 51.1,
    48.5 and finally 46.2 percent, so the six axes cost about four axes' worth
    of arithmetic rather than six. The attrition is that gentle because the box
    test upstream has already taken every pair that was nowhere near.
    """
    for start in range(0, len(ii), _CHUNK):
        stop = start + _CHUNK
        a = points[ii[start:stop]]              # (n, 3, 2)
        b = points[jj[start:stop]]
        seat = where[start:stop]
        for axis in range(6):
            # Axes 0-2 are `a`'s edge normals and 3-5 are `b`'s. Edge `edge`
            # runs from corner `edge - 1` to corner `edge`, so edge 0 is the
            # closing one -- `overlaps` starts its walk at `points[-1]` and
            # this is that same walk.
            source = a if axis < 3 else b
            edge = axis % 3
            px, py = source[:, edge - 1, 0], source[:, edge - 1, 1]
            qx, qy = source[:, edge, 0], source[:, edge, 1]
            nx = qy - py
            ny = px - qx
            length = numpy.sqrt(nx * nx + ny * ny)
            one = nx[:, None]
            two = ny[:, None]
            a_span = a[:, :, 0] * one + a[:, :, 1] * two
            b_span = b[:, :, 0] * one + b[:, :, 1] * two
            reach = slack * length
            apart = ((a_span.max(1) < b_span.min(1) + reach)
                     | (b_span.max(1) < a_span.min(1) + reach))
            # A repeated corner has no normal to separate along; the scalar
            # test skips such an edge and so does this.
            apart &= length >= 1e-12
            if not apart.any():
                continue
            together = ~apart
            a, b, seat = a[together], b[together], seat[together]
            if not len(seat):
                break
        out[seat] = True


# -- the order ------------------------------------------------------------

#: How far two facets may reach into each other before the pair is worth
#: asking about. In millimetres on the page, and generous on purpose: this is
#: the whole cost control, since every facet that shares an edge with another
#: would otherwise be a pair, and a mesh has three of those per triangle.
_TOUCH = 0.02

#: Depths closer than this are the same depth. Facets meeting along an edge
#: agree there exactly in exact arithmetic and to a few ulps in float, and a
#: pair reported as crossing because of the last bit would be split forever.
_LEVEL = 1e-7

#: How many facets the grid is sized for per cell. One, which is to say a
#: grid of about as many cells as there are facets. Two costs are traded: a
#: coarse grid puts more facets in a cell and so offers more pairs to the box
#: test, a fine one writes each facet into more cell lists. Measured on the
#: Allen brain at 8,816 faces, the exact sort takes 235 ms at a quarter, 210 at
#: a half, 178 at one and 182 at two, and 867 at a fiftieth. The picture does
#: not depend on it -- the grid decides only which pairs are *asked*, and
#: `_pairs` sorts what it found -- so this is purely a clock setting.
_CELLS_PER_FACET = 1.0

#: How many rounds of cutting before the remaining crossings are left to the
#: depth order. A cut can create a new crossing with a third facet, so this
#: loops; two rounds settle everything measured so far, and the cap is there
#: so that a pathological mesh costs a slightly wrong picture rather than the
#: whole render.
_ROUNDS = 3


def painter_sort(facets: list, view: View, next_index: int,
                 budget: int | None = None) -> list:
    """`facets` back to front, cut wherever no order between two of them is
    right.

    Takes the facets in any order and returns a new list in the order they
    must be painted. `next_index` is where new ring indices may start: cutting
    a facet makes corners that were not in the caller's point table, and they
    need names of their own so that `shade.dissolve` can still cancel the two
    halves of a cut against each other.

    A facet with no `plane` is left where the depth sort put it -- one built by
    hand has no plane to ask about.

    `budget` caps how many candidate pairs the whole run may ask about, and is
    how `sort="auto"` puts a *time* limit on itself rather than a size limit.
    Over the cap the facets come back in depth order, which is what the caller
    would have got had it never asked. `None` -- what an explicit
    `sort="exact"` passes -- means answer whatever it costs: a caller who named
    the exact order is owed the exact order, and silently handing back the
    approximation because a mesh turned out lumpy would be the worst kind of
    surprise. `shade.AUTO_EXACT_PAIRS` has the number and the argument for it.

    The cap is read *after* the grid and *before* the polygon test, which is
    the one place in the run where the true cost is known and none of it has
    been paid: `_candidates` is a few percent of the sort and every expensive
    thing downstream is per candidate pair. Bailing out mid-run is safe because
    a facet that a previous round cut in two is still a facet, and two halves
    painted at their own depths is exactly what the depth order does with them.
    """
    if len(facets) < 2:
        return list(facets)
    made = _Naming(next_index)
    items = list(facets)
    asked = 0
    for _ in range(_ROUNDS):
        left = None if budget is None else budget - asked
        before, crossings, cost = _pairs(items, view, left)
        asked += cost
        if before is None:
            return _bailed(items)
        if not crossings:
            return _threaded(items, before)
        items = _cut(items, crossings, view, made)
    before, _, cost = _pairs(items, view,
                             None if budget is None else budget - asked)
    return _bailed(items) if before is None else _threaded(items, before)


def _bailed(items) -> list:
    """The depth order, for a run that turned out to cost more than its budget.

    The same key `shade.sorted_facets` sorts by before it calls here, so a run
    that bails before cutting anything hands back exactly the list it was
    given. It is not quite the same picture `sort="depth"` would have drawn:
    the facets were *built* for the exact order, so a concave patch came in as
    its own triangles and any cutting an earlier round did stands. Both of
    those are differences `dissolve` mostly absorbs, and neither is a reason to
    throw the work away and build the scene twice.
    """
    return sorted(items, key=lambda f: (-f.depth, f.points[0].x, f.points[0].y))


class _Naming:
    """Fresh ring indices for cut corners, one per corner however often it is
    asked for. The two halves of a cut share the corners on the cut, so their
    shared edge cancels and a facet cut in two for ordering's sake still comes
    out as one outline when both halves land in the same path."""

    def __init__(self, start: int) -> None:
        self.next = start
        self.seen: dict = {}

    def index(self, key) -> int:
        found = self.seen.get(key)
        if found is None:
            found = self.next
            self.next += 1
            self.seen[key] = found
        return found


def _grid(boxes) -> tuple[dict, list[tuple[int, int]]]:
    """Facet indices by page cell, so only near neighbours are ever compared.

    Also returns each facet's *lowest* cell, which is what lets the pair loop
    skip a pair it has already seen without remembering it. Two boxes that
    share any cell share the one at `(max lo_x, max lo_y)` -- the corner of the
    overlap of their two cell ranges -- so a pair can be handled in that cell
    and ignored in every other, and a set of a third of a million tuples goes
    away.
    """
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    side = max(1, int((len(boxes) / _CELLS_PER_FACET) ** 0.5))
    step_x = max((x1 - x0) / side, 1e-9)
    step_y = max((y1 - y0) / side, 1e-9)
    cells: dict[tuple[int, int], list[int]] = {}
    lowest: list[tuple[int, int]] = []
    last = side - 1
    # `cells_of` written out: same arithmetic, but this runs once per facet on
    # every pass and the list of tuples it builds is thrown away immediately.
    for index, box in enumerate(boxes):
        lo_x = int((box[0] - x0) / step_x)
        hi_x = int((box[2] - x0) / step_x)
        lo_y = int((box[1] - y0) / step_y)
        hi_y = int((box[3] - y0) / step_y)
        lo_x = 0 if lo_x < 0 else (last if lo_x > last else lo_x)
        hi_x = 0 if hi_x < 0 else (last if hi_x > last else hi_x)
        lo_y = 0 if lo_y < 0 else (last if lo_y > last else lo_y)
        hi_y = 0 if hi_y < 0 else (last if hi_y > last else hi_y)
        lowest.append((lo_x, lo_y))
        for cx in range(lo_x, hi_x + 1):
            for cy in range(lo_y, hi_y + 1):
                found = cells.get((cx, cy))
                if found is None:
                    cells[(cx, cy)] = [index]
                else:
                    found.append(index)
    return cells, lowest


#: Below this many facets the grid is not worth an array pass: `numpy.repeat`
#: and an argsort have a floor of their own, and the Python loop is already
#: only a millisecond at a thousand facets.
_GRID_FLOOR = 1500


def _candidates(boxes, planes):
    """Every pair worth asking the polygon test about, as two index lists.

    A pair is worth asking about when the two facets share a grid cell, this
    cell is the one that owns the pair, both have a plane to compare, and their
    page boxes reach into each other by more than `_TOUCH`.

    Which pair comes out first is deliberately not part of the answer. It used
    to be -- the loop asked and recorded in one pass -- and it cannot matter:
    `_threaded` pops a heap keyed on depth and index, so the order the
    constraints were recorded in is not in the picture, and `_pairs` sorts
    `crossings` before anything reads it. That is what lets the array path
    group the grid by cell size instead of walking it in insertion order.
    """
    numpy = _numpy() if len(boxes) >= _GRID_FLOOR else None
    if numpy is not None:
        return _vector_candidates(numpy, boxes, planes)
    cells, lowest = _grid(boxes)
    first: list[int] = []
    second: list[int] = []
    # The box overlap test is written out rather than called: this is the
    # innermost loop of the exact order, it runs a third of a million times on
    # one panel, and the call frame was a tenth of it. `boxes_meet` stays,
    # because it is the readable statement of what these four comparisons do.
    for (cx, cy), members in cells.items():
        if len(members) < 2:
            continue
        for a in range(len(members)):
            i = members[a]
            if planes[i] is None:
                continue
            box_i = boxes[i]
            lo_i_x, lo_i_y = lowest[i]
            for b in range(a + 1, len(members)):
                j = members[b]
                lo_j_x, lo_j_y = lowest[j]
                if cx != (lo_i_x if lo_i_x > lo_j_x else lo_j_x) \
                        or cy != (lo_i_y if lo_i_y > lo_j_y else lo_j_y):
                    continue           # some other cell owns this pair
                if planes[j] is None:
                    continue
                box_j = boxes[j]
                if (box_i[2] < box_j[0] + _TOUCH or box_j[2] < box_i[0] + _TOUCH
                        or box_i[3] < box_j[1] + _TOUCH
                        or box_j[3] < box_i[1] + _TOUCH):
                    continue
                first.append(i)
                second.append(j)
    return first, second



#: How many pairs one batch of the group loop may materialise. A cell holding
#: m facets asks about m*(m-1)/2 pairs, and while the grid keeps m at a
#: handful on any real mesh, a degenerate camera can put a crowd in one cell.
#: Batching bounds the arrays without changing the answer.
_PAIR_BUDGET = 1 << 21


def _vector_candidates(numpy, boxes, planes):
    """`_candidates` as array passes, for meshes big enough to pay for them.

    Same grid, same owner-cell rule, same box test, same integer truncation --
    `astype` on a float64 array truncates toward zero exactly as `int()` does,
    and the clamp is the same clamp -- so this answers with the same set of
    pairs the loop above answers with. It answers in a different *order*, which
    the docstring on `_candidates` explains is not part of the answer.

    The one liberty taken is dropping facets with no plane before the grid is
    built rather than skipping them inside it. A facet with no plane is in no
    pair either way, and which cells it sits in cannot change which cell owns
    somebody else's pair: ownership is `max` of the two facets' own lowest
    cells and reads nothing about the neighbourhood.
    """
    b = numpy.array(boxes, dtype=float)
    x0, y0 = b[:, 0].min(), b[:, 1].min()
    x1, y1 = b[:, 2].max(), b[:, 3].max()
    side = max(1, int((len(boxes) / _CELLS_PER_FACET) ** 0.5))
    step_x = max((x1 - x0) / side, 1e-9)
    step_y = max((y1 - y0) / side, 1e-9)
    last = side - 1
    lo_x = numpy.clip(((b[:, 0] - x0) / step_x).astype(numpy.intp), 0, last)
    hi_x = numpy.clip(((b[:, 2] - x0) / step_x).astype(numpy.intp), 0, last)
    lo_y = numpy.clip(((b[:, 1] - y0) / step_y).astype(numpy.intp), 0, last)
    hi_y = numpy.clip(((b[:, 3] - y0) / step_y).astype(numpy.intp), 0, last)

    alive = numpy.flatnonzero(numpy.fromiter(
        (plane is not None for plane in planes), dtype=bool, count=len(planes)))
    if len(alive) < 2:
        return [], []
    # The cell list, flattened: one row per (facet, cell) with the facet's
    # index repeated across its own rectangle of cells. `repeat` gives the
    # owner column and a running offset within each facet gives the cell.
    wide = (hi_x - lo_x + 1)[alive]
    tall = (hi_y - lo_y + 1)[alive]
    per = wide * tall
    total = int(per.sum())
    owner = numpy.repeat(numpy.arange(len(alive), dtype=numpy.intp), per)
    within = numpy.arange(total, dtype=numpy.intp) \
        - numpy.repeat(numpy.cumsum(per) - per, per)
    height = tall[owner]
    cell_x = lo_x[alive][owner] + within // height
    cell_y = lo_y[alive][owner] + within % height

    # Group the rows by cell. A stable sort keeps each cell's members in facet
    # order, which is what makes the pair `(members[a], members[b])` for a < b
    # come out as `i < j` without a second sort.
    key = cell_x * side + cell_y
    seat = numpy.argsort(key, kind="stable")
    key, member = key[seat], owner[seat]
    head = numpy.flatnonzero(numpy.concatenate(
        ([True], key[1:] != key[:-1])))
    size = numpy.diff(numpy.append(head, total))
    crowded = size >= 2
    head, size = head[crowded], size[crowded]

    first: list[int] = []
    second: list[int] = []
    for width in numpy.unique(size):
        width = int(width)
        rows = head[size == width]
        left, right = numpy.triu_indices(width, 1)
        batch = max(1, _PAIR_BUDGET // len(left))
        for at in range(0, len(rows), batch):
            base = rows[at:at + batch]
            members = member[base[:, None] + numpy.arange(width)]
            i = alive[members[:, left].ravel()]
            j = alive[members[:, right].ravel()]
            here_x = numpy.repeat(key[base] // side, len(left))
            here_y = numpy.repeat(key[base] % side, len(left))
            take = ((here_x == numpy.maximum(lo_x[i], lo_x[j]))
                    & (here_y == numpy.maximum(lo_y[i], lo_y[j])))
            i, j = i[take], j[take]
            one, two = b[i], b[j]
            meet = ~((one[:, 2] < two[:, 0] + _TOUCH)
                     | (two[:, 2] < one[:, 0] + _TOUCH)
                     | (one[:, 3] < two[:, 1] + _TOUCH)
                     | (two[:, 3] < one[:, 1] + _TOUCH))
            first.extend(i[meet].tolist())
            second.extend(j[meet].tolist())
    return first, second



def _pairs(items, view: View, budget: int | None = None):
    """Every pair that overlaps: who must precede whom, and who cannot.

    Returns `(before, crossings, asked)` -- a map from a facet to the facets
    that must be painted after it, the pairs for which no such answer exists,
    and how many candidate pairs the grid offered.

    `budget` is how many candidates this round may ask about. Over it, the
    answer is `(None, None, asked)` and the caller falls back; the count is
    still returned, because the number is the whole point of asking.
    """
    corners = [tuple((p.x, p.y) for p in f.points) for f in items]
    boxes = [box_of(f.points) for f in items]
    rays = _Rays(view)
    planes = [None if f.plane is None else rays.of(f.plane) for f in items]
    # How far each facet reaches in depth, over its own corners. Depth under a
    # projection is monotone along any page segment, so a convex facet's
    # extremes are at its corners and this really is its whole range -- which
    # is what lets a pair whose ranges do not meet be settled without clipping
    # the shared region or evaluating a plane in it. On a mesh most
    # overlapping pairs are of that kind.
    spans = [None if plane is None else rays.span(plane, corner)
             for plane, corner in zip(planes, corners)]
    before: dict[int, list[int]] = {}
    crossings: list[tuple[int, int]] = []
    first, second = _candidates(boxes, planes)
    if budget is not None and len(first) > budget:
        return None, None, len(first)
    # Whether each candidate really overlaps is settled for the whole run at
    # once. Which pair is *asked* first cannot reach the picture -- `_threaded`
    # pops a heap keyed on depth and index, so the order the constraints were
    # recorded in is not in the answer, and `crossings` is sorted below -- so
    # this is free to batch.
    for k, together in enumerate(_which_overlap(corners, first, second,
                                                _TOUCH)):
        if not together:
            continue
        i, j = first[k], second[k]
        verdict = _order_of(planes[i], planes[j], spans[i], spans[j],
                            corners[i], corners[j], rays)
        if verdict is None:
            crossings.append((i, j))
        elif verdict:
            before.setdefault(i, []).append(j)
        else:
            before.setdefault(j, []).append(i)
    # Sorted, so that which cell of the grid happened to own a pair cannot
    # reach the picture: `_cut` applies a facet's cut lines one after another
    # and the pieces come out in that order.
    crossings.sort()
    return before, crossings, len(first)


class _Rays:
    """The camera as four numbers per plane, so a depth is scalar arithmetic.

    `_depth_at` used to build the ray through a page point out of `Vec3`s and
    dot the plane's normal into it: five vector objects per sample, and the
    exact order takes four hundred thousand samples on one panel. Every one of
    those products is fixed once the plane is known, so a plane reduces to
    `(n.right, n.up, n.forward, offset - n.eye)` and a sample to a couple of
    multiplies and a divide. The algebra is the same; only the allocation is
    gone.
    """

    __slots__ = ("scale", "ox", "oy", "focal", "perspective", "eye",
                 "right", "up", "forward")

    def __init__(self, view: View) -> None:
        self.scale = view.scale
        self.ox, self.oy = view.offset.x, view.offset.y
        self.focal = view.focal
        self.perspective = view.perspective
        self.eye, self.right = view.eye, view.right
        self.up, self.forward = view.up, view.forward

    def of(self, plane) -> tuple[float, float, float, float]:
        normal, offset = plane
        return (normal.dot(self.right), normal.dot(self.up),
                normal.dot(self.forward), offset - normal.dot(self.eye))

    def depth(self, plane, x: float, y: float):
        """How far the plane is under one page point, or `None` edge-on."""
        nr, nu, nf, k = plane
        across = (x - self.ox) / self.scale
        down = -(y - self.oy) / self.scale
        if self.perspective:
            divisor = nr * (across / self.focal) + nu * (down / self.focal) + nf
            if -1e-15 < divisor < 1e-15:
                return None
            return k / divisor
        if -1e-15 < nf < 1e-15:
            return None
        return (k - nr * across - nu * down) / nf

    def span(self, plane, corners):
        """The plane's depth range over a facet's own corners."""
        lo = hi = None
        for x, y in corners:
            found = self.depth(plane, x, y)
            if found is None:
                return None
            if lo is None or found < lo:
                lo = found
            if hi is None or found > hi:
                hi = found
        return (lo, hi)


def _order_of(one, two, one_span, two_span, mine, theirs, rays: "_Rays"):
    """True if `one` is behind `two`, False if in front, None if they cross.

    The region the two share is where the answer has to hold, so that is where
    the depth difference is sampled: at the corners of the clipped region, and
    nowhere else. Sampling the two polygons' own corners instead would report a
    crossing for every pair whose planes happen to meet somewhere off to the
    side of the part they actually share, which on a folded surface is most of
    them.
    """
    if one_span is not None and two_span is not None:
        # Whole-facet depth ranges that do not meet settle the pair outright:
        # every sample would come back the same sign, so take the answer and
        # skip both the clip and the samples. This is most pairs on a real
        # mesh -- four in five on the Allen brain -- and it is asked first for
        # that reason: it is four comparisons against a polygon clip.
        if one_span[0] - two_span[1] > _LEVEL:
            return True
        if two_span[0] - one_span[1] > _LEVEL:
            return False
    region = _clipped(mine, theirs)
    if len(region) < 3:
        return _apart()          # they only touch: the box test was generous
    behind = ahead = False
    for x, y in region:
        here = rays.depth(one, x, y)
        there = rays.depth(two, x, y)
        if here is None or there is None:
            continue
        gap = here - there
        if gap > _LEVEL:
            behind = True            # larger depth is further from the eye
        elif gap < -_LEVEL:
            ahead = True
    if behind and ahead:
        return None
    if behind:
        return True
    if ahead:
        return False
    return _apart()


def _apart():
    """Coplanar, or sharing only a boundary: no constraint either way."""
    return False


def _clipped(subject, clipper) -> list:
    """The convex intersection of two page polygons, Sutherland-Hodgman.

    Both are wound whichever way the projection left them, so the sign of the
    clipper's own area says which side of its edges is inside.
    """
    inside = 1.0 if _signed_area(clipper) >= 0.0 else -1.0
    out = list(subject)
    count = len(clipper)
    for k in range(count):
        if len(out) < 3:
            return []
        ax, ay = clipper[k]
        bx, by = clipper[(k + 1) % count]
        ex, ey = bx - ax, by - ay
        kept = []
        for i in range(len(out)):
            cur = out[i]
            nxt = out[(i + 1) % len(out)]
            here = (ex * (cur[1] - ay) - ey * (cur[0] - ax)) * inside
            there = (ex * (nxt[1] - ay) - ey * (nxt[0] - ax)) * inside
            if here >= 0.0:
                kept.append(cur)
            if (here >= 0.0) != (there >= 0.0):
                share = here / (here - there)
                kept.append((cur[0] + (nxt[0] - cur[0]) * share,
                             cur[1] + (nxt[1] - cur[1]) * share))
        out = kept
    return out


def _area(points) -> float:
    """Twice the page area of a facet's outline, unsigned."""
    total = 0.0
    for i in range(len(points)):
        a, b = points[i], points[(i + 1) % len(points)]
        total += a.x * b.y - b.x * a.y
    return abs(total)


def _signed_area(points) -> float:
    total = 0.0
    for i in range(len(points)):
        ax, ay = points[i]
        bx, by = points[(i + 1) % len(points)]
        total += ax * by - bx * ay
    return total


def _depth_at(view: View, plane, x: float, y: float):
    """How far away the plane is under one page point.

    The page point names a ray, and this is where the ray meets the plane. It
    is a division rather than an interpolation because under perspective depth
    is not linear across a facet, and the whole point of asking here rather
    than at a corner is to be right in the middle of one.
    """
    normal, offset = plane
    across = (x - view.offset.x) / view.scale
    down = -(y - view.offset.y) / view.scale
    if view.perspective:
        direction = (view.right * (across / view.focal)
                     + view.up * (down / view.focal) + view.forward)
        divisor = normal.dot(direction)
        if abs(divisor) < 1e-15:
            return None
        return (offset - normal.dot(view.eye)) / divisor
    divisor = normal.dot(view.forward)
    if abs(divisor) < 1e-15:
        return None
    start = view.eye + view.right * across + view.up * down
    return (offset - normal.dot(start)) / divisor


def _threaded(items, before) -> list:
    """The facets in an order that respects every pair, furthest first.

    Kahn's algorithm with the depth sort as the tie-break, so a scene with no
    constraints at all comes out exactly as `sorted_facets` left it and one
    with constraints comes out as close to that as the constraints allow. A
    cycle -- three facets each partly over the next, which cutting did not
    reach -- is drained in depth order at the end rather than dropped: a
    slightly wrong picture beats a missing one.
    """
    waiting = {index: 0 for index in range(len(items))}
    for outs in before.values():
        for index in outs:
            waiting[index] += 1
    free = [(-items[i].depth, i) for i, count in waiting.items() if count == 0]
    heapq.heapify(free)
    out = []
    while free:
        _, index = heapq.heappop(free)
        out.append(items[index])
        waiting[index] = -1
        for after in before.get(index, ()):
            waiting[after] -= 1
            if waiting[after] == 0:
                heapq.heappush(free, (-items[after].depth, after))
    if len(out) < len(items):
        stuck = [items[i] for i, count in waiting.items() if count > 0]
        out.extend(sorted(stuck, key=lambda f: -f.depth))
    return out


def _cut(items, crossings, view: View, made: _Naming) -> list:
    """Cut every facet that crosses another along the line where they meet.

    One facet may cross several, so the cuts are gathered first and applied one
    after another, each piece being offered to the next line. The line is the
    two planes' intersection projected onto the page -- straight, because the
    projection of a straight line is one -- so a cut is exact and a piece is
    still flat and still in its parent's plane.
    """
    lines: dict[int, list] = {}
    for i, j in crossings:
        line = _meeting(items[i].plane, items[j].plane, view)
        if line is None:
            continue
        # One of the two is enough. Both halves of a cut facet lie wholly on
        # one side of the other's plane, so each has a definite order against
        # it, and the other keeps its outline. Cut the smaller: a cone pushed
        # through a wall crosses the wall once per cone facet, and cutting the
        # wall each time shreds one quad into a hundred pieces to settle
        # something the cone's own facets settle between them.
        lines.setdefault(i if _area(items[i].points) <= _area(items[j].points)
                         else j, []).append(line)
    if not lines:
        return items
    out = []
    for index, facet in enumerate(items):
        pieces = [(facet.points, facet.ring)]
        for line in lines.get(index, ()):
            pieces = [half for piece in pieces
                      for half in _halves(piece, line, index, made)]
        if len(pieces) == 1:
            out.append(facet)
            continue
        for points, ring in pieces:
            depth = _mean_depth(view, facet.plane, points)
            out.append(_replaced(facet, points, ring,
                                 facet.depth if depth is None else depth))
    return out


def _replaced(facet, points, ring, depth):
    return replace(facet, points=tuple(points), ring=tuple(ring), depth=depth)


def _mean_depth(view: View, plane, points):
    total = 0.0
    for point in points:
        found = _depth_at(view, plane, point.x, point.y)
        if found is None:
            return None
        total += found
    return total / len(points)


def _meeting(one, two, view: View):
    """Where two planes meet, as a page point and a page direction."""
    first = one[0].cross(two[0])
    size = first.dot(first)
    if size < 1e-18:
        return None                      # parallel: they never meet
    on_both = (two[0].cross(first) * one[1]
               + first.cross(one[0]) * two[1]) * (1.0 / size)
    start = view.project(on_both).point
    along = view.project(on_both + first).point - start
    if along.x * along.x + along.y * along.y < 1e-18:
        # The line runs straight at the camera: it is a point on the page, and
        # a point cuts nothing.
        return None
    return start, along


def _halves(piece, line, index: int, made: _Naming):
    """One polygon cut by one page line, as one or two polygons.

    The corners on the cut are named once each and shared by both halves, so
    the seam between them cancels in `dissolve` if they ever end up in the same
    path -- which they do whenever nothing of another colour is painted between
    them, and then the cut costs nothing at all.
    """
    points, ring = piece
    start, along = line
    sides = [along.x * (p.y - start.y) - along.y * (p.x - start.x)
             for p in points]
    if all(s >= 0.0 for s in sides) or all(s <= 0.0 for s in sides):
        return [piece]
    near_points, near_ring, far_points, far_ring = [], [], [], []
    count = len(points)
    for i in range(count):
        j = (i + 1) % count
        here, there = sides[i], sides[j]
        if here >= 0.0:
            near_points.append(points[i])
            near_ring.append(ring[i])
        if here <= 0.0:
            far_points.append(points[i])
            far_ring.append(ring[i])
        if (here > 0.0) != (there > 0.0) and here != there:
            share = here / (here - there)
            crossed = points[i] + (points[j] - points[i]) * share
            name = made.index((index, ring[i], ring[j], start.x, start.y,
                               along.x, along.y))
            near_points.append(crossed)
            near_ring.append(name)
            far_points.append(crossed)
            far_ring.append(name)
    out = []
    for half_points, half_ring in ((near_points, near_ring),
                                   (far_points, far_ring)):
        if len(half_points) >= 3:
            out.append((half_points, half_ring))
    return out or [piece]
