"""What a scene's parts are, where they are painted, and what is really in front.

`scene(order="parts")` paints each part whole, furthest centre first. That is
the right answer nearly always and the wrong one exactly when a part's centre
is not where its geometry is: a nut standing proud of a plate but offset across
the stack sorts behind the plate, a rod through nine plates has no single
number that ranks it against all of them. `order="exact"` settles those cases
by fusing the scene; this module is the other half of the same problem --
**noticing**, so an author who did not know to reach for it is told.

The measurement is a coarse depth raster, one grid shared by every part of a
scene. Each part contributes, per cell it covers, the nearest and furthest
surface of *its own* geometry there. Then a pair is settled by reading the two
tables: if a part painted later is further away than the other part at every
single cell the two share, the paint order and the geometry disagree, and the
picture shows a plate through a bolt.

**Nearest against furthest, cell by cell.** Comparing whole parts -- A's
nearest against B's furthest across the entire overlap -- would miss the
commonest form of the bug, where the two interleave over most of the region
and disagree only where it matters. Comparing cell by cell is both stricter
about what counts as a finding and sensitive to the local case; and a rule that
fires on a well-formed figure is worse than no rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.geom import Rect
from .camera import View
from .mesh import Mesh

__all__ = ["ScenePaint", "DepthField", "depth_field", "behind_everywhere",
           "GRID_WIDE"]

#: Cells across the scene's projected width. Two hundred puts a 4 mm nut on a
#: 185 mm panel across four cells, which is enough to say whether it is in
#: front of the plate it sits on, and leaves rasterising the whole assembly
#: under a hundredth of a second because the tables are sparse.
GRID_WIDE = 200

#: Below this many shared cells a pair is a graze rather than an overlap, and
#: saying that a part four cells wide is painted wrongly against another is
#: noise. Twelve cells is about 0.3% of a part the size of one of the plates.
MIN_SHARED_CELLS = 12

#: A cell whose near and far depths differ by less than this, in the camera's
#: own units, is a surface seen edge-on inside one cell rather than a solid;
#: the two parts' order there is not decided by a comparison of numbers this
#: close. Scaled off the scene's own depth range, so it means the same thing
#: on a chip and on a protein.
_FLAT_FRACTION = 1e-4


@dataclass(frozen=True)
class ScenePaint:
    """A `scene()`'s parts, in declaration order, and the order they paint in.

    Recorded by `scene()` so that `inklet.lint` can compare the two -- and so an
    author can ask. `paint` is indices into `names`, back to front; `declared`
    holds the ones whose place the author set with `draw_order=`, `behind=`,
    `in_front_of=` or -- in a fused scene -- `overlay=True`, which the depth
    rule takes as the answer rather than as a thing to check.

    In a fused scene `paint` is the fused parts, which have no order among
    themselves because depth is settled facet by facet inside them, followed
    by the overlays in the order they were declared.
    """

    names: tuple[str, ...]
    nodes: tuple[str, ...]
    meshes: tuple[Mesh, ...]
    view: View
    paint: tuple[int, ...]
    declared: frozenset[int] = frozenset()
    fused: bool = False
    #: `(front, back)` pairs the author asserted, checked by `inklet.lint`.
    claims: tuple[tuple[str, str], ...] = ()

    def position(self, index: int) -> int:
        """Where a part comes in the paint order; larger is painted later."""
        return self.paint.index(index)


@dataclass(frozen=True)
class DepthField:
    """The nearest and furthest surface of one part, per cell of a page grid.

    Sparse, because a part covers a few hundred cells of a grid with forty
    thousand and a dense array per part of a twenty-five part assembly is
    megabytes to answer a question about a few dozen pairs.
    """

    #: cell -> (near, far), depth growing away from the camera.
    cells: dict[int, tuple[float, float]]
    #: The page rectangle the part covers, for the cheap rejection test.
    box: Rect | None

    def __bool__(self) -> bool:
        return bool(self.cells)


def depth_field(mesh: Mesh, view: View, frame: Rect, *,
                wide: int = GRID_WIDE) -> DepthField:
    """Rasterise one part's faces into the scene's shared grid.

    Every face, front and back: the question is how deep the part *is* at a
    page point, and the far side of a solid is what says a rod passes through
    a plate rather than stopping on it. Culling would answer a different
    question.
    """
    if mesh.is_empty or frame.width <= 0.0:
        return DepthField({}, None)
    points, depths = view.project_all(mesh.vertices)
    step = frame.width / wide
    tall = max(1, int(frame.height / step) + 1)
    x0, y0 = frame.x0, frame.y0
    cells: dict[int, tuple[float, float]] = {}
    lo_x = hi_x = lo_y = hi_y = None
    for a, b, c in mesh.faces:
        p, q, r = points[a], points[b], points[c]
        area = (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)
        if -1e-12 < area < 1e-12:
            continue
        first = max(0, int((min(p.y, q.y, r.y) - y0) / step))
        last = min(tall - 1, int((max(p.y, q.y, r.y) - y0) / step))
        left = max(0, int((min(p.x, q.x, r.x) - x0) / step))
        right = min(wide - 1, int((max(p.x, q.x, r.x) - x0) / step))
        dp, dq, dr = depths[a], depths[b], depths[c]
        for row in range(first, last + 1):
            y = y0 + (row + 0.5) * step
            base = row * wide
            for column in range(left, right + 1):
                x = x0 + (column + 0.5) * step
                u = ((x - p.x) * (r.y - p.y) - (y - p.y) * (r.x - p.x)) / area
                if u < 0.0:
                    continue
                v = ((q.x - p.x) * (y - p.y) - (q.y - p.y) * (x - p.x)) / area
                if v < 0.0 or u + v > 1.0:
                    continue
                deep = dp + (dq - dp) * u + (dr - dp) * v
                key = base + column
                known = cells.get(key)
                if known is None:
                    cells[key] = (deep, deep)
                    if lo_x is None:
                        lo_x = hi_x = x
                        lo_y = hi_y = y
                    else:
                        lo_x, hi_x = min(lo_x, x), max(hi_x, x)
                        lo_y, hi_y = min(lo_y, y), max(hi_y, y)
                elif deep < known[0]:
                    cells[key] = (deep, known[1])
                elif deep > known[1]:
                    cells[key] = (known[0], deep)
    if lo_x is None:
        return DepthField({}, None)
    return DepthField(cells, Rect(lo_x - step, lo_y - step,
                                  hi_x + step, hi_y + step))


def behind_everywhere(front: DepthField, back: DepthField,
                      *, span: float) -> tuple[int, float] | None:
    """Is `front` -- the part painted later -- behind `back` at every shared cell?

    Returns `(cells, clearance)` when it is: how many cells the two share and
    the smallest gap between them, in the camera's own units, so the caller can
    say how wrong the order is rather than only that it is. None when they
    interleave, when they barely touch, or when they do not overlap at all --
    all three of which are ordinary and must stay silent.

    `span` is the scene's own depth range, and the only reason it is needed is
    the flat case: a plane and the plate it lies on share every cell with the
    two depths equal to float noise, and calling that "behind" would report
    every decal in every figure.
    """
    if not front.cells or not back.cells or front.box is None or back.box is None:
        return None
    if front.box.overlap(back.box) is None:
        return None
    shared = 0
    clearance = float("inf")
    flat = max(span, 1e-12) * _FLAT_FRACTION
    for key, (near, far) in front.cells.items():
        other = back.cells.get(key)
        if other is None:
            continue
        shared += 1
        gap = near - other[1]        # how far the near face of `front` sits
        if gap <= flat:              # behind the far face of `back`
            return None
        clearance = min(clearance, gap)
    if shared < MIN_SHARED_CELLS:
        return None
    return shared, clearance
