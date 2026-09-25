"""Smooth outlines round the dense core of a point cloud.

`core_outline` finds the region holding a cluster's core and returns it as
closed rings in page millimetres. `Panel.embedding(outline=...)` draws one per
cluster.

The core is a density threshold. The points are binned on a grid of about
half the bandwidth, and the counts are smoothed with a separable Gaussian. The
threshold is the density that the `core` fraction of the points reach or
pass, read at each point's cell. So the outline holds that fraction of the
points, and it follows a curved cluster rather than its convex hull.

Outliers cannot make the shape larger:

- Points more than `_WINDOW` robust spreads from the median are not binned.
- A stray point's own density is far below the threshold.
- A separate island of the threshold region is kept only when it holds at
  least `_ISLAND` of the cluster's points.

The rings come from marching squares on the smoothed grid, with the crossings
interpolated linearly, and are rounded by three passes of Chaikin's corner
cutting. The whole computation is pure Python and deterministic. It is
linear in the number of points, plus a fixed grid of at most `_CELLS` cells
on a side, so tens of thousands of points take a fraction of a second.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import Vec2

__all__ = ["core_outline"]

#: Points further than this many robust spreads (1.4826 times the median
#: absolute deviation) from the median, on either axis, are left out.
_WINDOW = 5.0
#: An island of the core region is kept when it holds at least this share of
#: the cluster's points. The largest is always kept.
_ISLAND = 0.1
#: The largest grid, in cells per side.
_CELLS = 120
#: The Gaussian bandwidth as a fraction of the cluster's smaller robust
#: spread, and its bounds in millimetres.
_BANDWIDTH_OF_SPREAD = 0.5
_BANDWIDTH_MIN, _BANDWIDTH_MAX = 0.4, 3.0
#: Passes of corner cutting on each ring.
_SMOOTHING = 3


def core_outline(points: Sequence[Vec2], *, core: float = 0.8,
                 bandwidth: float | None = None) -> list[list[Vec2]]:
    """Closed rings round the densest `core` share of `points`.

    `points` are page millimetres. `bandwidth` is the smoothing radius in
    millimetres (default: from the cluster's spread). Returns a list of
    rings, each a list of points without the closing repeat. Where the core
    region has a hole, the hole is a ring of its own, so the rings should be
    filled with the even-odd rule. Fewer than three points give no rings.
    """
    if not 0.0 < core < 1.0:
        raise ValueError(f"outline core is a fraction between 0 and 1, not {core!r}")
    pts = [p for p in points if math.isfinite(p.x) and math.isfinite(p.y)]
    if len(pts) < 3:
        return []
    mx = _median([p.x for p in pts])
    my = _median([p.y for p in pts])
    sx = 1.4826 * _median([abs(p.x - mx) for p in pts])
    sy = 1.4826 * _median([abs(p.y - my) for p in pts])
    spread = min(v for v in (sx, sy) if v > 0) if (sx > 0 or sy > 0) else 0.0
    if bandwidth is None:
        h = min(_BANDWIDTH_MAX, max(_BANDWIDTH_MIN, _BANDWIDTH_OF_SPREAD * spread))
    else:
        h = float(bandwidth)
    if h <= 0:
        raise ValueError(f"outline bandwidth must be positive, not {bandwidth!r}")
    wx = max(_WINDOW * sx, 3 * h)
    wy = max(_WINDOW * sy, 3 * h)
    inside = [p for p in pts if abs(p.x - mx) <= wx and abs(p.y - my) <= wy]
    if len(inside) < 3:
        return []
    margin = 3 * h
    x0 = min(p.x for p in inside) - margin
    x1 = max(p.x for p in inside) + margin
    y0 = min(p.y for p in inside) - margin
    y1 = max(p.y for p in inside) + margin
    cell = max(h / 2, (x1 - x0) / _CELLS, (y1 - y0) / _CELLS)
    nx = int(math.ceil((x1 - x0) / cell)) + 1
    ny = int(math.ceil((y1 - y0) / cell)) + 1
    counts = [[0.0] * nx for _ in range(ny)]
    where: list[tuple[int, int]] = []
    for p in inside:
        i = min(nx - 1, int((p.x - x0) / cell))
        j = min(ny - 1, int((p.y - y0) / cell))
        counts[j][i] += 1.0
        where.append((i, j))
    field = _blur(counts, h / cell)
    # The threshold every `core` share of all the points reaches; points
    # left out of the window count as below it.
    levels = sorted((field[j][i] for i, j in where), reverse=True)
    rank = int(math.ceil(core * len(pts))) - 1
    if rank >= len(levels):
        level = levels[-1] * 0.5
    else:
        level = levels[max(0, rank)]
    if level <= 0:
        return []
    keep = _islands(field, counts, level, len(pts))
    # Below-threshold values outside the kept islands, and a border of them,
    # so every ring closes inside the grid.
    grid = [[(field[j][i] - level) if keep[j][i] else -level
             for i in range(nx)] for j in range(ny)]
    for i in range(nx):
        grid[0][i] = grid[ny - 1][i] = -level
    for row in grid:
        row[0] = row[nx - 1] = -level
    rings = _contours(grid)
    out: list[list[Vec2]] = []
    for ring in rings:
        page = [Vec2(x0 + x * cell, y0 + y * cell) for x, y in ring]
        for _ in range(_SMOOTHING):
            page = _chaikin(page)
        if abs(_area(page)) >= cell * cell:
            out.append(page)
    return out


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2


def _blur(grid: list[list[float]], sigma: float) -> list[list[float]]:
    """A separable Gaussian blur, `sigma` in cells, zero beyond the edges."""
    reach = max(1, int(math.ceil(3 * sigma)))
    kernel = [math.exp(-0.5 * (k / sigma) ** 2) for k in range(-reach, reach + 1)]
    total = sum(kernel)
    kernel = [k / total for k in kernel]
    ny, nx = len(grid), len(grid[0])

    def run(row: list[float], n: int) -> list[float]:
        out = [0.0] * n
        for i, value in enumerate(row):
            if value == 0.0:
                continue
            lo = max(0, i - reach)
            hi = min(n - 1, i + reach)
            for t in range(lo, hi + 1):
                out[t] += value * kernel[t - i + reach]
        return out

    rows = [run(row, nx) for row in grid]
    columns = [run([rows[j][i] for j in range(ny)], ny) for i in range(nx)]
    return [[columns[i][j] for i in range(nx)] for j in range(ny)]


def _islands(field, counts, level: float, total: int) -> list[list[bool]]:
    """Cells of the connected parts of `field >= level` worth keeping: the
    part holding the most points, and every part holding `_ISLAND` of all."""
    ny, nx = len(field), len(field[0])
    label = [[-1] * nx for _ in range(ny)]
    held: list[float] = []
    for j in range(ny):
        for i in range(nx):
            if label[j][i] != -1 or field[j][i] < level:
                continue
            number = len(held)
            label[j][i] = number
            stack = [(i, j)]
            count = 0.0
            while stack:
                a, b = stack.pop()
                count += counts[b][a]
                for c, d in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if (0 <= c < nx and 0 <= d < ny and label[d][c] == -1
                            and field[d][c] >= level):
                        label[d][c] = number
                        stack.append((c, d))
            held.append(count)
    if not held:
        return [[False] * nx for _ in range(ny)]
    largest = max(range(len(held)), key=lambda k: (held[k], -k))
    wanted = {k for k, count in enumerate(held)
              if k == largest or count >= _ISLAND * total}
    return [[label[j][i] in wanted for i in range(nx)] for j in range(ny)]


def _contours(grid: list[list[float]]) -> list[list[tuple[float, float]]]:
    """The zero level of `grid` as closed rings, in cell coordinates.

    Marching squares: each crossing lies on a cell edge, found by linear
    interpolation, and each square joins two or four of them. A saddle is
    decided by the square's mean value. Every crossing is shared by two
    squares, so the segments chain into closed rings when the border of the
    grid is below zero.
    """
    ny, nx = len(grid), len(grid[0])

    def crossing(edge) -> tuple[float, float]:
        kind, i, j = edge
        if kind == "h":              # between (i, j) and (i + 1, j)
            a, b = grid[j][i], grid[j][i + 1]
            return i + a / (a - b), float(j)
        a, b = grid[j][i], grid[j + 1][i]
        return float(i), j + a / (a - b)

    links: dict = {}

    def join(p, q) -> None:
        links.setdefault(p, []).append(q)
        links.setdefault(q, []).append(p)

    for j in range(ny - 1):
        for i in range(nx - 1):
            v0 = grid[j][i] >= 0              # top left
            v1 = grid[j][i + 1] >= 0          # top right
            v2 = grid[j + 1][i + 1] >= 0      # bottom right
            v3 = grid[j + 1][i] >= 0          # bottom left
            code = v0 | (v1 << 1) | (v2 << 2) | (v3 << 3)
            if code in (0, 15):
                continue
            top, right = ("h", i, j), ("v", i + 1, j)
            bottom, left = ("h", i, j + 1), ("v", i, j)
            if code in (5, 10):
                middle = (grid[j][i] + grid[j][i + 1] + grid[j + 1][i + 1]
                          + grid[j + 1][i]) / 4 >= 0
                if (code == 5) == middle:
                    # The top-right and bottom-left corners cut off: the
                    # low ones of a joined 5, or the high ones of a split 10.
                    join(top, right)
                    join(bottom, left)
                else:
                    join(top, left)
                    join(bottom, right)
                continue
            edges = []
            if v0 != v1:
                edges.append(top)
            if v1 != v2:
                edges.append(right)
            if v2 != v3:
                edges.append(bottom)
            if v3 != v0:
                edges.append(left)
            join(edges[0], edges[1])
    rings: list[list[tuple[float, float]]] = []
    seen: set = set()
    for start in sorted(links):
        if start in seen:
            continue
        ring = [start]
        seen.add(start)
        previous, here = None, start
        while True:
            options = [e for e in links[here] if e != previous] or links[here]
            following = next((e for e in options if e not in seen), None)
            if following is None:
                break
            ring.append(following)
            seen.add(following)
            previous, here = here, following
        if len(ring) >= 3:
            rings.append([crossing(e) for e in ring])
    return rings


def _chaikin(ring: list[Vec2]) -> list[Vec2]:
    """One pass of Chaikin's corner cutting on a closed ring."""
    out: list[Vec2] = []
    n = len(ring)
    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]
        out.append(Vec2(0.75 * a.x + 0.25 * b.x, 0.75 * a.y + 0.25 * b.y))
        out.append(Vec2(0.25 * a.x + 0.75 * b.x, 0.25 * a.y + 0.75 * b.y))
    return out


def _area(ring: Sequence[Vec2]) -> float:
    """The signed area of a closed ring (shoelace)."""
    n = len(ring)
    return sum(ring[k].x * ring[(k + 1) % n].y - ring[(k + 1) % n].x * ring[k].y
               for k in range(n)) / 2
