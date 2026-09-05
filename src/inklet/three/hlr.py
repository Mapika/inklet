"""Hidden-line removal: the part that makes this a drawing rather than a graph.

The algorithm is the classical one, and it is worth stating plainly because
every tolerance below exists to defend one of its steps.

1. Project every vertex once. Keep the depth alongside the page point.
2. Choose the occluders. For a closed surface, front-facing triangles are
   enough -- see `_occluders` for why culling the rest is not an approximation.
3. Cut each feature edge at every point where it crosses a projected triangle
   edge. Between two consecutive cuts an edge cannot change visibility, because
   visibility can only flip where the edge passes under a triangle's boundary.
4. Classify each piece by its midpoint: inside a triangle *and* behind it means
   hidden. One sample decides a whole piece, which is exactly what step 3 earns.
5. Emit the surviving pieces, threaded back into the longest polylines they
   will make.

Step 3's claim holds for surfaces that do not pass through one another, which
covers every mesh anyone loads from a file and every scene assembled by placing
solids beside each other. It fails for *interpenetrating* geometry: where an
edge pierces another surface, visibility flips at the piercing point, and in
projection that point is in the middle of a triangle rather than on its
boundary, so no cut is made there and the midpoint sample decides the whole
piece. A rod pushed halfway into a block loses the stub that sticks out, or
keeps the length that does not, depending on which side of the piercing point
the midpoint lands. Fixing it properly means computing surface-surface
intersection curves, which is a different and much larger algorithm; a
`merge()` of two solids that overlap in space is outside what this does.

Naive, step 3 is every edge against every triangle: 5856 faces and 1700 feature
edges is ten million pairs, which is a minute of Python. The fix is a uniform
grid keyed on each projected triangle's 2D bounding box, walked along each edge
with a DDA so a short edge only ever meets its own neighbourhood. Measured
timings for real meshes are in the module tests and in the report; the short
version is that a few thousand triangles stays interactive and tens of
thousands does not.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.geom import Rect, Vec2
from .camera import View
from .edges import FeatureEdge
from .mesh import Mesh

__all__ = ["VisibleRun", "Occluders", "visible_runs", "chain_runs", "polylines"]

# Barycentric coordinates are unitless, so this tolerance means the same thing
# whatever the model's scale. It is a *closed* test -- on the boundary counts as
# inside -- and that is load-bearing. Triangulating a quad puts a diagonal
# across it, and in an isometric view of a box that diagonal can land exactly on
# top of a hidden edge behind it. A strictly-interior test leaves that edge
# visible and draws a line through a solid; the closed test plus the depth
# margin below gets it right without depending on how the quad was split.
_INSIDE_EPS = 1e-9

# Two cuts closer together than this along an edge are the same cut. Relative to
# the edge, so it is scale-free; large enough to swallow the float noise of two
# triangle edges meeting at a shared vertex, small enough that no real sliver
# is lost at diagram sizes.
_PARAM_EPS = 1e-9

# An occluder has to be *clearly* in front to hide something, by this fraction
# of the scene's depth range. Coplanar geometry -- a decal on a face, the shared
# edge of two triangles in one flat quad -- comes out equal to within float
# noise, and without a margin the two would fight and the seam would flicker
# between drawn and not depending on the last bit of a dot product.
_DEPTH_MARGIN = 1e-7

# A projected triangle thinner than this fraction of the page cannot occlude
# anything you could see, and its barycentric divisor is meaningless. Edge-on
# faces of a closed solid land here constantly, which is why the test is on the
# projected area and not on the 3D one.
_SLIVER = 1e-10

# Cap on how many grid cells one triangle may be filed under. A single huge
# background quad would otherwise be inserted into every cell in the grid,
# which costs more than testing it against everything. Past the cap it goes in
# the "always test" list instead.
_MAX_CELLS_PER_FACE = 64


@dataclass(frozen=True, slots=True)
class VisibleRun:
    """A surviving stretch of one feature edge, as parameters along it."""

    edge: int
    kind: str
    t0: float
    t1: float


# -- the occluder set -----------------------------------------------------


class Occluders:
    """Projected triangles in a uniform grid, queried by segment.

    Built once per render and shared by every edge query, because projecting
    and binning 6000 triangles for each of 1700 edges is the naive algorithm
    wearing a hat.
    """

    __slots__ = ("points", "depths", "faces", "tri", "grid", "cols", "rows",
                 "box", "cell_w", "cell_h", "always", "perspective")

    def __init__(self, mesh: Mesh, view: View, points: list[Vec2],
                 depths: list[float], face_indices: list[int]) -> None:
        self.points = points
        self.depths = depths
        self.perspective = view.perspective
        # `tri` holds, per occluder: the face index, its three page points, its
        # three depths and the doubled signed area. Flat tuples rather than
        # objects -- this is read once per candidate test per edge piece.
        self.tri: list[tuple] = []
        self.faces = face_indices
        boxes: list[Rect] = []
        for f in face_indices:
            i, j, k = mesh.faces[f]
            a, b, c = points[i], points[j], points[k]
            area2 = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
            if abs(area2) < _SLIVER:
                continue
            self.tri.append((f, a, b, c, depths[i], depths[j], depths[k], area2))
            boxes.append(Rect(min(a.x, b.x, c.x), min(a.y, b.y, c.y),
                              max(a.x, b.x, c.x), max(a.y, b.y, c.y)))
        self.always: list[int] = []
        self._build_grid(boxes)

    def _build_grid(self, boxes: list[Rect]) -> None:
        self.grid: dict[int, list[int]] = {}
        if not boxes:
            self.box = Rect(0.0, 0.0, 0.0, 0.0)
            self.cols = self.rows = 1
            self.cell_w = self.cell_h = 1.0
            return
        box = boxes[0]
        for b in boxes[1:]:
            box = box.union(b)
        # One cell per triangle, squared off. Fewer cells and each query drags
        # in the whole neighbourhood; more and the walk costs more than the
        # tests it saves.
        side = max(1, int(math.sqrt(len(boxes))))
        self.box = box
        self.cols = self.rows = side
        self.cell_w = max(box.width / side, 1e-12)
        self.cell_h = max(box.height / side, 1e-12)
        for index, b in enumerate(boxes):
            x0, y0 = self._cell(b.x0, b.y0)
            x1, y1 = self._cell(b.x1, b.y1)
            if (x1 - x0 + 1) * (y1 - y0 + 1) > _MAX_CELLS_PER_FACE:
                self.always.append(index)
                continue
            for cy in range(y0, y1 + 1):
                for cx in range(x0, x1 + 1):
                    self.grid.setdefault(cy * self.cols + cx, []).append(index)

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        cx = int((x - self.box.x0) / self.cell_w)
        cy = int((y - self.box.y0) / self.cell_h)
        return (min(max(cx, 0), self.cols - 1), min(max(cy, 0), self.rows - 1))

    def near(self, p: Vec2, q: Vec2) -> list[int]:
        """Occluders whose bounding box could meet the segment `p`-`q`.

        Returned sorted, so the crossing parameters an edge collects come out in
        the same order on every run even though the answer does not depend on
        it. Determinism is cheaper to keep than to debug.
        """
        found: dict[int, None] = {i: None for i in self.always}
        clipped = _clip_to(p, q, self.box)
        if clipped is not None:
            for key in self._walk(clipped[0], clipped[1]):
                for index in self.grid.get(key, ()):
                    found[index] = None
        return sorted(found)

    def _walk(self, p: Vec2, q: Vec2):
        """Amanatides-Woo: step cell to cell along the segment, no sampling."""
        cx, cy = self._cell(p.x, p.y)
        ex, ey = self._cell(q.x, q.y)
        dx, dy = q.x - p.x, q.y - p.y
        step_x = 1 if dx > 0 else (-1 if dx < 0 else 0)
        step_y = 1 if dy > 0 else (-1 if dy < 0 else 0)

        def crossing(start: float, cell: int, size: float, origin: float,
                     delta: float, step: int) -> tuple[float, float]:
            if step == 0:
                return (math.inf, math.inf)
            edge = origin + (cell + (1 if step > 0 else 0)) * size
            return ((edge - start) / delta, size / abs(delta))

        t_max_x, t_delta_x = crossing(p.x, cx, self.cell_w, self.box.x0, dx, step_x)
        t_max_y, t_delta_y = crossing(p.y, cy, self.cell_h, self.box.y0, dy, step_y)

        # The walk is bounded by the grid, but a bound is cheaper than trusting
        # that no float comparison ever stalls the loop.
        for _ in range(self.cols + self.rows + 2):
            yield cy * self.cols + cx
            if cx == ex and cy == ey:
                return
            if t_max_x <= t_max_y:
                cx += step_x
                t_max_x += t_delta_x
                if not 0 <= cx < self.cols:
                    return
            else:
                cy += step_y
                t_max_y += t_delta_y
                if not 0 <= cy < self.rows:
                    return

    # -- the two questions an edge asks -----------------------------------

    def crossings(self, p: Vec2, q: Vec2, candidates: list[int],
                  skip: tuple[int, ...]) -> list[float]:
        """Parameters along `p`-`q` where it passes under a triangle's outline.

        Only these can change visibility, so they are the only places the edge
        needs cutting.
        """
        dx, dy = q.x - p.x, q.y - p.y
        cuts: list[float] = []
        for index in candidates:
            face, a, b, c, _, _, _, _ = self.tri[index]
            if face in skip:
                continue
            for u, v in ((a, b), (b, c), (c, a)):
                ex, ey = v.x - u.x, v.y - u.y
                denom = dx * ey - dy * ex
                if denom == 0.0:
                    continue                     # parallel: no single crossing
                wx, wy = u.x - p.x, u.y - p.y
                t = (wx * ey - wy * ex) / denom
                if not _PARAM_EPS < t < 1.0 - _PARAM_EPS:
                    continue
                s = (wx * dy - wy * dx) / denom
                if -_PARAM_EPS <= s <= 1.0 + _PARAM_EPS:
                    cuts.append(t)
        cuts.sort()
        return cuts

    def hides(self, point: Vec2, depth: float, candidates: list[int],
              skip: tuple[int, ...], margin: float) -> bool:
        """Is this page point covered by something nearer than `depth`?"""
        px, py = point.x, point.y
        for index in candidates:
            face, a, b, c, da, db, dc, area2 = self.tri[index]
            if face in skip:
                continue
            w0 = ((b.x - px) * (c.y - py) - (b.y - py) * (c.x - px)) / area2
            if w0 < -_INSIDE_EPS:
                continue
            w1 = ((c.x - px) * (a.y - py) - (c.y - py) * (a.x - px)) / area2
            if w1 < -_INSIDE_EPS:
                continue
            w2 = 1.0 - w0 - w1
            if w2 < -_INSIDE_EPS:
                continue
            if self.perspective:
                # Depth is not linear in screen space under perspective, but its
                # reciprocal is. Interpolating the depth directly would put a
                # steeply receding triangle's midpoint metres out of place.
                inv = w0 / da + w1 / db + w2 / dc
                if inv <= 0.0:
                    continue
                here = 1.0 / inv
            else:
                here = w0 * da + w1 * db + w2 * dc
            if here < depth - margin:
                return True
        return False


def _clip_to(p: Vec2, q: Vec2, box: Rect) -> tuple[Vec2, Vec2] | None:
    """Liang-Barsky. Clipping before the DDA rather than clamping the endpoints
    into range: a clamped walk can leave the true segment and visit cells it
    never touched, which is only wasteful, but it can also *skip* cells, which
    is a hidden line that stays drawn."""
    t0, t1 = 0.0, 1.0
    dx, dy = q.x - p.x, q.y - p.y
    for delta, room in ((-dx, p.x - box.x0), (dx, box.x1 - p.x),
                        (-dy, p.y - box.y0), (dy, box.y1 - p.y)):
        if delta == 0.0:
            if room < 0.0:
                return None      # parallel to this side and wholly outside it
            continue
        t = room / delta
        if delta < 0.0:
            if t > t1:
                return None
            t0 = max(t0, t)
        else:
            if t < t0:
                return None
            t1 = min(t1, t)
    if t0 > t1:
        return None
    return (Vec2(p.x + dx * t0, p.y + dy * t0), Vec2(p.x + dx * t1, p.y + dy * t1))


def _occluders(mesh: Mesh, facing: tuple[bool, ...], cull: bool) -> list[int]:
    """Which faces are allowed to hide things.

    Culling back faces on a closed surface is exact, not an approximation: any
    ray that reaches a back-facing triangle must have entered the solid first,
    and an entry is a front-facing triangle nearer to the eye. So a back face
    never hides anything a front face does not already hide. On an open mesh --
    a ground plane, a cut-away, Spot with her mouth open -- that argument fails
    and every triangle occludes.
    """
    if not cull:
        return list(range(len(mesh.faces)))
    return [i for i, front in enumerate(facing) if front]


# -- the main pass --------------------------------------------------------


def visible_runs(mesh: Mesh, view: View, edges: list[FeatureEdge],
                 points: list[Vec2], depths: list[float],
                 facing: tuple[bool, ...], *,
                 cull: bool | None = None,
                 on_surface: dict[tuple[int, int], tuple[int, ...]] | None = None
                 ) -> tuple[list[VisibleRun], Occluders]:
    """Cut the feature edges against the surface and keep what survives.

    Returns the runs in edge order, plus the occluder structure, which the
    caller reuses for shading rather than paying to build it twice.

    An edge is never tested against the faces it lies on, which for a mesh edge
    are the faces sharing it. `on_surface` names those faces for edges whose
    endpoints are not mesh vertices -- a smooth silhouette runs *through* a
    triangle rather than along an edge of it -- and is consulted first.
    """
    if cull is None:
        cull = mesh.is_closed
    occluders = Occluders(mesh, view, points, depths,
                          _occluders(mesh, facing, cull))
    span = max(depths) - min(depths) if depths else 0.0
    margin = max(span * _DEPTH_MARGIN, 1e-12)
    table = mesh.edge_faces

    runs: list[VisibleRun] = []
    for index, edge in enumerate(edges):
        p, q = points[edge.a], points[edge.b]
        if abs(q.x - p.x) < 1e-12 and abs(q.y - p.y) < 1e-12:
            continue                     # projects to a point: nothing to draw
        skip = table.get(edge.key, ()) if on_surface is None \
            else on_surface.get(edge.key) or table.get(edge.key, ())
        candidates = occluders.near(p, q)
        if not candidates:
            runs.append(VisibleRun(index, edge.kind, 0.0, 1.0))
            continue
        da, db = depths[edge.a], depths[edge.b]
        cuts = [0.0] + occluders.crossings(p, q, candidates, skip) + [1.0]

        kept: list[tuple[float, float]] = []
        previous = cuts[0]
        for cut in cuts[1:]:
            if cut - previous <= _PARAM_EPS:
                continue
            mid = (previous + cut) * 0.5
            here = Vec2(p.x + (q.x - p.x) * mid, p.y + (q.y - p.y) * mid)
            depth = _depth_at(da, db, mid, view.perspective)
            if not occluders.hides(here, depth, candidates, skip, margin):
                if kept and kept[-1][1] >= previous - _PARAM_EPS:
                    kept[-1] = (kept[-1][0], cut)   # touching: one run, not two
                else:
                    kept.append((previous, cut))
            previous = cut
        runs.extend(VisibleRun(index, edge.kind, lo, hi) for lo, hi in kept)
    return runs, occluders


def _depth_at(da: float, db: float, t: float, perspective: bool) -> float:
    if not perspective:
        return da + (db - da) * t
    inv = (1.0 - t) / da + t / db
    return 1.0 / inv if inv > 0.0 else min(da, db)


# -- back into polylines --------------------------------------------------


def chain_runs(edges: list[FeatureEdge], runs: list[VisibleRun],
               points: list[Vec2]) -> list[tuple[tuple[Vec2, ...], bool]]:
    """Thread surviving runs into polylines, joining at shared mesh vertices.

    Only runs that reach a vertex can join there -- a run cut short by an
    occluder ends in mid-air and must stay a separate stroke, or the drawing
    would grow a line across the gap it was meant to leave.
    """
    ends: list[tuple[int | None, int | None]] = []
    for run in runs:
        edge = edges[run.edge]
        ends.append((edge.a if run.t0 <= _PARAM_EPS else None,
                     edge.b if run.t1 >= 1.0 - _PARAM_EPS else None))

    incident: dict[int, list[int]] = {}
    for index, (head, tail) in enumerate(ends):
        for vertex in (head, tail):
            if vertex is not None:
                incident.setdefault(vertex, []).append(index)

    def at(index: int, t: float) -> Vec2:
        edge = edges[runs[index].edge]
        p, q = points[edge.a], points[edge.b]
        return Vec2(p.x + (q.x - p.x) * t, p.y + (q.y - p.y) * t)

    used = [False] * len(runs)

    def take(vertex: int) -> int | None:
        for candidate in incident.get(vertex, ()):
            if not used[candidate]:
                return candidate
        return None

    chains: list[tuple[tuple[Vec2, ...], bool]] = []
    for start in range(len(runs)):
        if used[start]:
            continue
        used[start] = True
        head, tail = ends[start]
        chain = [at(start, runs[start].t0), at(start, runs[start].t1)]

        while tail is not None and (nxt := take(tail)) is not None:
            used[nxt] = True
            head_v, tail_v = ends[nxt]
            if head_v == tail:
                chain.append(at(nxt, runs[nxt].t1))
                tail = tail_v
            else:
                chain.append(at(nxt, runs[nxt].t0))
                tail = head_v
        while head is not None and (prv := take(head)) is not None:
            used[prv] = True
            head_v, tail_v = ends[prv]
            if tail_v == head:
                chain.insert(0, at(prv, runs[prv].t0))
                head = head_v
            else:
                chain.insert(0, at(prv, runs[prv].t1))
                head = tail_v

        closed = head is not None and head == tail and len(chain) > 3
        chains.append((tuple(chain[:-1] if closed else chain), closed))
    return chains


def polylines(edges: list[FeatureEdge], runs: list[VisibleRun],
              points: list[Vec2],
              kinds: tuple[str, ...]) -> list[tuple[tuple[Vec2, ...], bool]]:
    """Chained polylines for just the edge kinds asked for.

    Split by kind before chaining so that a heavy silhouette and a light crease
    never end up in one stroke -- they are different weights on the page, and a
    joined path can only have one.
    """
    subset = [r for r in runs if r.kind in kinds]
    return chain_runs(edges, subset, points)
