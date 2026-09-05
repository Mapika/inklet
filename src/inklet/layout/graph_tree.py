"""Reingold-Tilford tidy trees, with real node widths.

The tidy-tree promise is three things at once: a parent sits centred over its
children, two subtrees never overlap, and the drawing is as narrow as those two
rules allow. The classic algorithm gets all three in linear time by threading
contours through the tree; the version here keeps the contours as explicit
per-depth profiles instead.

That is a deliberate trade. Threads are linear and assume every node is one
unit wide; profiles are O(nodes x depth) and do not care how wide anything is,
which is the case a diagram actually has -- a box labelled "Randomised (n=816)"
next to one labelled "n=4". A figure is a few hundred nodes and a dozen levels
deep, so the asymptotics never surface and the widths always do.

The input may be a forest, and it may be a DAG rather than a tree. A DAG is
laid out over a breadth-first spanning forest -- each node hangs under the
first parent that reaches it -- and the edges left over are drawn across the
tidy tree rather than shaping it. Anything unreachable from a root becomes a
root of its own, so no node is ever silently dropped.
"""

from __future__ import annotations

from collections import deque
from typing import Sequence

__all__ = ["tree_positions", "spanning_tree_edges"]

Size = tuple[float, float]
Point = tuple[float, float]

#: One subtree's shape: the leftmost and rightmost reach at each depth below
#: its own root, measured from that root at zero.
Profile = list[float]


def tree_positions(
    sizes: Sequence[Size], edges: Sequence[tuple[int, int]], *,
    gap: float, rank_gap: float, roots: Sequence[int] | None = None,
) -> tuple[list[Point], list[int]]:
    """Positions in (across, along) millimetres, and the depth of each vertex.

    `gap` is the clear space between two subtrees at their closest point --
    which is the point that matters, and the reason a tidy tree looks tidy.
    """
    n = len(sizes)
    if n == 0:
        return [], []

    children, depth, forest = _spanning_forest(n, edges, roots)
    across = [float(sizes[i][0]) for i in range(n)]

    offsets = [0.0] * n
    merged_left: Profile = []
    merged_right: Profile = []
    for index, root in enumerate(forest):
        local, left, right = _tidy(root, children, across, gap)
        shift = 0.0 if index == 0 else _clearance(merged_right, left, gap)
        for v, x in local.items():
            offsets[v] = x + shift
        _absorb(merged_left, merged_right, left, right, shift)

    along = _levels(depth, [float(sizes[i][1]) for i in range(n)], rank_gap)
    return [(offsets[i], along[depth[i]]) for i in range(n)], depth


def spanning_tree_edges(n: int, edges: Sequence[tuple[int, int]],
                        roots: Sequence[int] | None = None
                        ) -> frozenset[tuple[int, int]]:
    """Which edges the tidy tree drew as parent-to-child.

    A tree layout can only place a tree, and most graphs handed to one are not:
    the rest of the edges are cross links, drawn over a shape that was arranged
    without them in mind. Knowing which they are is what lets the caller route
    those round the boxes in the way and leave the real branches straight.
    """
    children, _depth, _forest = _spanning_forest(n, edges, roots)
    return frozenset((parent, child)
                     for parent, kids in enumerate(children) for child in kids)


def _spanning_forest(n: int, edges: Sequence[tuple[int, int]],
                     roots: Sequence[int] | None
                     ) -> tuple[list[list[int]], list[int], list[int]]:
    """Children, depth and the roots to grow from.

    Breadth-first rather than depth-first on purpose: in a DAG a node with two
    parents should hang under the shallower one, or the tree grows a long
    dangling limb where the drawing wants a short edge and a cross link.
    """
    out: list[list[int]] = [[] for _ in range(n)]
    indegree = [0] * n
    for u, v in edges:
        out[u].append(v)
        indegree[v] += 1

    if roots is None:
        starts = [i for i in range(n) if indegree[i] == 0]
    else:
        starts = list(roots)

    children: list[list[int]] = [[] for _ in range(n)]
    depth = [0] * n
    seen = [False] * n
    forest: list[int] = []

    queue: deque[int] = deque()

    def open_root(r: int) -> None:
        seen[r] = True
        depth[r] = 0
        forest.append(r)
        queue.append(r)

    def drain() -> None:
        while queue:
            u = queue.popleft()
            for v in out[u]:
                if not seen[v]:
                    seen[v] = True
                    depth[v] = depth[u] + 1
                    children[u].append(v)
                    queue.append(v)

    for r in starts:
        if not seen[r]:
            open_root(r)
    drain()          # one breadth-first wave from every root at once, so a
                     # shared node hangs under whichever root is nearer
    # A cycle, or a component reachable only from inside itself, has no
    # in-degree-zero vertex. Rooting it at its lowest index is arbitrary but
    # deterministic, and it beats dropping the component.
    for r in range(n):
        if not seen[r]:
            open_root(r)
            drain()
    return children, depth, forest


def _tidy(root: int, children: Sequence[Sequence[int]], across: Sequence[float],
          gap: float) -> tuple[dict[int, float], Profile, Profile]:
    """One subtree, laid out with its root at zero.

    Post-order, iteratively: a deep tree is a real input and a recursive
    contour merge would hit the interpreter's stack limit before the figure
    hit the page.
    """
    done: dict[int, tuple[dict[int, float], Profile, Profile]] = {}
    stack: list[tuple[int, bool]] = [(root, False)]
    while stack:
        v, ready = stack.pop()
        if not ready:
            stack.append((v, True))
            for c in reversed(children[v]):
                stack.append((c, False))
            continue

        half = across[v] / 2.0
        kids = children[v]
        if not kids:
            done[v] = ({v: 0.0}, [-half], [half])
            continue

        left: Profile = []
        right: Profile = []
        shifts: list[float] = []
        for index, c in enumerate(kids):
            _, kid_left, kid_right = done[c]
            shift = 0.0 if index == 0 else _clearance(right, kid_left, gap)
            shifts.append(shift)
            _absorb(left, right, kid_left, kid_right, shift)

        # The parent goes over the midpoint of its outermost children, not
        # over the centre of the block they occupy: that is what keeps a
        # parent visibly attached to a lopsided pair of subtrees.
        centre = (shifts[0] + shifts[-1]) / 2.0
        offsets = {v: 0.0}
        for index, c in enumerate(kids):
            for node, x in done[c][0].items():
                offsets[node] = x + shifts[index] - centre
            del done[c]
        done[v] = (
            offsets,
            [-half] + [x - centre for x in left],
            [half] + [x - centre for x in right],
        )
    return done[root]


def _clearance(right: Profile, left: Profile, gap: float) -> float:
    """How far to push a subtree so it clears what is already placed, at every
    depth the two share. Depths they do not share cost nothing, which is the
    whole point: a tall thin subtree slides in under a wide shallow one."""
    shift = 0.0
    for d in range(min(len(right), len(left))):
        need = right[d] + gap - left[d]
        if need > shift:
            shift = need
    return shift


def _absorb(left: Profile, right: Profile, add_left: Profile,
            add_right: Profile, shift: float) -> None:
    """Merge a shifted subtree's contour into the accumulated one, in place."""
    for d in range(len(add_left)):
        if d < len(left):
            left[d] = min(left[d], add_left[d] + shift)
            right[d] = max(right[d], add_right[d] + shift)
        else:
            left.append(add_left[d] + shift)
            right.append(add_right[d] + shift)


def _levels(depth: Sequence[int], along: Sequence[float],
            rank_gap: float) -> list[float]:
    """Centre line of each level, a level being as thick as its tallest node."""
    deepest = max(depth) if depth else 0
    thickness = [0.0] * (deepest + 1)
    for v, d in enumerate(depth):
        thickness[d] = max(thickness[d], along[v])
    centres: list[float] = []
    front = 0.0
    for value in thickness:
        centres.append(front + value / 2.0)
        front += value + rank_gap
    return centres
