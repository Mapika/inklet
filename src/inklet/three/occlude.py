"""How enclosed each point of a surface is, and therefore how dark it sits.

Shading from a light says which way a surface faces. It says nothing about
whether the surface is in a hole. A binding pocket, a hollow, the inside of a
fold: all of them face the light exactly as their surroundings do, so a
Lambert term draws them the same tone and they read as flat. Every molecular
viewer computes some form of ambient occlusion for that reason, and it is the
single largest perceptual difference between a shaded mesh and a rendered one.

**The measurement is screen-space.** Rasterise the drawable faces into a depth
grid once, then ask, around each vertex, how much of the nearby surface sits
*above its own tangent plane*. A point out on an exposed face has nothing above
it and comes out at zero; a point at the bottom of a pocket has the pocket's
walls above it from most directions and comes out near one.

Above the tangent plane, not merely nearer the camera, and that is the whole
difference between this working and not. Nearer-the-camera counts a sphere's
own curvature as occlusion: at the rim of a sphere half the disc around a
vertex is nearer than it is, so a convex solid -- which by definition occludes
nothing -- would come out darkened all round its edge. So each sample is
unprojected back into a world point, and only counts if it stands above the
plane the surface is locally lying in. A sphere then comes out at zero
everywhere, which is the correct answer and the test.

Three objections to screen-space occlusion, and why they are not objections
here.

*It is view-dependent.* So is the light: `shade.DEFAULT_LIGHT` is a direction
in **view** space, deliberately, so that six panels of one object are lit the
same way instead of six objects each lit from a different side of the room.
Occlusion that follows the camera is the same decision, and it keeps the same
promise -- what the reader sees is shaded for where they are looking from.

*It sees a silhouette as a wall.* A near object does darken a far one behind
it. That is a contact shadow when the two are close and nonsense when they are
not, so a sample only counts when the thing in front is within `reach` -- the
same distance the disc covers on the page, carried into depth.

*It is noisy.* Twelve samples per vertex is a dozen yes-or-no answers, and a
dozen coin flips look like a dozen coin flips. So the answer is smoothed over
the mesh's own adjacency afterwards, which is the mesh-space form of the blur
every screen-space implementation ends with, and is deterministic where a
random rotation per sample would not be.

**The result is per vertex, and it goes into the tone.** Not into a separate
darkening pass: occlusion moves a surface along its own ramp, which is exactly
what the tone is, so folding it in costs no new fills -- the quantiser sees one
number as before, and a shaded protein keeps collapsing into a few dozen paths.
It also means `shading="smooth"` gets occlusion contoured into its bands for
nothing, because those bands are cut out of the vertex-tone field.
"""

from __future__ import annotations

import math

from .camera import View
from .linalg import Vec3
from .mesh import Mesh

__all__ = ["vertex_occlusion", "DEFAULT_SAMPLES", "DEFAULT_REACH",
           "DEFAULT_SMOOTHING"]

#: Directions tried around each vertex, shared out across the octaves below.
#: Twenty-four is eight per octave, which is where the smoothing pass stops
#: having to work hard; more costs linearly and buys very little, because the
#: mesh has many vertices and they average each other out.
DEFAULT_SAMPLES = 24

#: How far the *widest* disc reaches, as a fraction of the model's page
#: diagonal. A tenth of the object is about the width of a binding cleft on a
#: protein drawn at a page of one, and the octaves below carry the measurement
#: down from there to the width of a single fold.
DEFAULT_REACH = 0.10

#: How many discs, each half the width of the last, and the answer is the
#: largest of them. One radius cannot serve both ends of the question. Measured
#: on a wide disc, a tight crevice is diluted -- most of the disc is out in the
#: open, and the fraction that is blocked comes out small. Measured on a narrow
#: one, a broad hollow is missed entirely, because the whole disc lies on the
#: hollow's own floor and sees nothing above it. The numbers say so plainly: a
#: torus needs a disc a fifth of the page to register its hole, and at that
#: width a milled channel reads at half the strength a disc a twentieth of the
#: page gives it. Three octaves span a factor of four, and taking the largest
#: asks the question that was actually meant -- is this point inside something,
#: at any scale -- rather than one arbitrary size of something.
_OCTAVES = 3

#: How many times the answer is averaged over the mesh's own adjacency. Two is
#: enough to turn a dozen coin flips into a smooth field without spreading a
#: pocket's darkening out past the pocket.
DEFAULT_SMOOTHING = 2

#: The depth grid's width in cells. Fine enough that the disc covers a decent
#: number of them, coarse enough that rasterising it is a tenth of a second on
#: fifty thousand faces. Occlusion is a low-frequency quantity -- it is the
#: thing that varies *slowly* across a surface -- so resolving it finely would
#: be resolving noise.
_GRID_WIDE = 256

#: How far above the tangent plane a sample has to stand before it counts, as
#: the cosine of the angle from that plane. Not zero, because the depth grid
#: quantises and a vertex normal averages over a corner, so a curved surface
#: produces samples a hair either side of its own tangent plane. A fifth is
#: about eleven degrees, and it is the smallest value at which a finely
#: tessellated sphere -- the hardest convex case, because its facet normals
#: differ by very little and there are very many of them -- comes out at zero
#: everywhere. A tenth leaves a few percent of a subdivision-five icosphere
#: darkened; three tenths costs half the signal in a torus's hole and buys
#: nothing further.
_ABOVE = 0.20

#: Depths are stored as floats with this standing for "nothing here". Larger
#: than any real depth, so an empty cell is never nearer than a vertex.
_EMPTY = float("inf")

#: The golden angle in radians. Turning by it each step spreads directions as
#: evenly as anything can without a random number, which matters twice here:
#: within one vertex's pattern, and between neighbouring vertices' patterns.
_GOLDEN = 2.399963229728653

#: How much further than the disc a sample may be and still count, in world
#: units. The range check is there to stop a near object darkening a distant
#: one behind it, and if it were set to the disc's own radius it would also
#: throw away the case this whole module is for: the floor of a pocket is
#: within a disc of its walls *on the page* and several disc-radii from them in
#: depth. Four leaves a pocket four times as deep as it is wide still reading
#: as a pocket, and still throws out a background a screen away.
_RANGE = 4.0

#: How many facet widths across the narrowest disc has to be. Two is not
#: enough: it puts the disc's edge two facets out, which is still inside the
#: neighbourhood where a vertex normal is an average of the facets around it
#: and they therefore stand above its tangent plane. Six clears that
#: neighbourhood on a subdivision-five icosphere, and on anything with enough
#: facets to matter -- a protein at fifty thousand -- six facet widths is still
#: under a millimetre, so the fine octave survives it untouched.
_COARSEST = 6.0


def vertex_occlusion(mesh: Mesh, view: View, points, depths,
                     faces, *, samples: int = DEFAULT_SAMPLES,
                     reach: float = DEFAULT_REACH,
                     smoothing: int = DEFAULT_SMOOTHING) -> tuple[float, ...]:
    """How enclosed each vertex is, 0 (out in the open) to 1 (walled in).

    `faces` is the drawable subset -- the same list `shade.sorted_facets`
    paints. Back faces are behind the front ones and can never be the nearest
    thing at a page point, so rasterising them would cost time for nothing.

    Vertices no drawable face uses come back as 0. Nothing reads them, and
    giving them a real answer would mean rasterising the whole mesh.
    """
    if not faces or samples < 1:
        return (0.0,) * len(mesh.vertices)
    grid, box = _depth_grid(mesh, points, depths, faces)
    if grid is None:
        return (0.0,) * len(mesh.vertices)
    x0, y0, step, wide, tall = box
    span = ((wide * step) ** 2 + (tall * step) ** 2) ** 0.5
    each = max(samples // _OCTAVES, 1)
    # Each disc half the width of the last, and each with its own range: the
    # depth a sample may sit at and still belong to the same hollow is set by
    # how wide the hollow is, so the narrow disc must not accept a wall the
    # wide one is there to find.
    #
    # The range is in world units, which is what the tangent-plane test
    # measures in. Under perspective it and the page radius agree only at the
    # framing distance, which is where the object is; the error is the order of
    # the object's own depth range, inside a quantity about to be rounded to a
    # twentieth.
    #
    # A disc narrower than the mesh's own facets measures the tessellation and
    # not the shape: every vertex of a coarse sphere has neighbouring facets
    # standing a hair above its tangent plane, because a vertex normal is an
    # average of them, and a disc that reaches no further than those neighbours
    # sees nothing else. So the smallest octave is floored at a facet's own
    # width on the page, below which there is no shape left to measure.
    # Never past the reach that was asked for: on a model with a few dozen
    # facets the floor would otherwise swallow every octave and widen the disc
    # past the scale the caller named. There the stack collapses to one disc,
    # which is the right answer for a model that has no fine scale to look at.
    floor = min(_facet_width(wide * step, tall * step, len(faces)) * _COARSEST,
                span * reach)
    discs = []
    for octave in range(_OCTAVES):
        radius = max(span * reach / (2 ** octave), floor, step)
        discs.append((_spiral(each, radius),
                      radius / max(view.scale, 1e-9) * _RANGE))
    normals = mesh.vertex_normals
    world = mesh.vertices
    raw = [0.0] * len(world)
    seen = bytearray(len(world))
    for face in faces:
        for index in mesh.faces[face]:
            seen[index] = 1
    for index in range(len(world)):
        if not seen[index]:
            continue
        here = points[index]
        mine = world[index]
        normal = normals[index]
        # Turn the pattern by a different angle at every vertex, so the twelve
        # directions do not line up across the surface and print as a texture.
        # The golden angle is the standard choice and needs no random numbers,
        # which is what keeps two runs byte-identical.
        turn = index * _GOLDEN
        spin, tip = math.cos(turn), math.sin(turn)
        most = 0
        for pattern, far in discs:
            blocked = 0
            for dx, dy in pattern:
                x = here.x + dx * spin - dy * tip
                y = here.y + dx * tip + dy * spin
                cx = int((x - x0) / step)
                cy = int((y - y0) / step)
                if cx < 0 or cy < 0 or cx >= wide or cy >= tall:
                    continue
                deep = grid[cy * wide + cx]
                if deep == _EMPTY:
                    continue                 # paper: nothing to be under
                toward = _unprojected(view, x, y, deep) - mine
                length = toward.length
                if length > far or length < 1e-12:
                    continue                 # too far to matter, or itself
                if normal.dot(toward) / length > _ABOVE:
                    blocked += 1
            if blocked > most:
                most = blocked
        raw[index] = most / each
    return _smoothed(mesh, raw, faces, smoothing)


def _facet_width(wide: float, tall: float, faces: int) -> float:
    """About how far across one facet is on the page.

    The bounding box over the facet count, rooted. Coarse -- a silhouette fills
    perhaps two thirds of its box, and facets are not all one size -- but this
    only ever sets a floor, and the thing it is protecting against is a disc
    smaller than a facet by a factor of ten.
    """
    if faces < 1:
        return 0.0
    return (wide * tall / faces) ** 0.5


def _unprojected(view: View, x: float, y: float, deep: float) -> Vec3:
    """The world point that projects to this page point at this depth.

    `View.project` run backwards. The page point names a ray from the eye and
    the depth says how far along it to stop.
    """
    across = (x - view.offset.x) / view.scale
    down = -(y - view.offset.y) / view.scale
    if view.perspective:
        return view.eye + (view.right * (across / view.focal)
                           + view.up * (down / view.focal)
                           + view.forward) * deep
    return (view.eye + view.right * across + view.up * down
            + view.forward * deep)


def _spiral(samples: int, radius: float) -> list[tuple[float, float]]:
    """Sample offsets on a disc, spread evenly over area rather than over
    radius -- `sqrt` of the fraction, or every sample crowds the centre where
    the surface's own neighbourhood already answers."""
    out = []
    for k in range(samples):
        share = (k + 0.5) / samples
        angle = k * _GOLDEN
        far = radius * share ** 0.5
        out.append((far * math.cos(angle), far * math.sin(angle)))
    return out


def _depth_grid(mesh: Mesh, points, depths, faces):
    """The nearest drawable surface under each cell of a page grid.

    Scanline rasterising with the triangles bucketed by row, which is the
    difference between a tenth of a second and a minute: without it every
    triangle is tested against every row of its bounding box whether or not it
    reaches that far.
    """
    xs = ys = None
    for face in faces:
        for index in mesh.faces[face]:
            p = points[index]
            if xs is None:
                xs = [p.x, p.x]
                ys = [p.y, p.y]
            else:
                if p.x < xs[0]:
                    xs[0] = p.x
                elif p.x > xs[1]:
                    xs[1] = p.x
                if p.y < ys[0]:
                    ys[0] = p.y
                elif p.y > ys[1]:
                    ys[1] = p.y
    if xs is None or xs[1] - xs[0] < 1e-12:
        return None, None
    step = (xs[1] - xs[0]) / _GRID_WIDE
    tall = max(1, min(_GRID_WIDE * 8, int((ys[1] - ys[0]) / step) + 1))
    wide = _GRID_WIDE
    x0, y0 = xs[0], ys[0]
    grid = [_EMPTY] * (wide * tall)

    rows: list[list[int]] = [[] for _ in range(tall)]
    for face in faces:
        a, b, c = mesh.faces[face]
        low = min(points[a].y, points[b].y, points[c].y)
        high = max(points[a].y, points[b].y, points[c].y)
        first = max(0, int((low - y0) / step))
        last = min(tall - 1, int((high - y0) / step))
        for row in range(first, last + 1):
            rows[row].append(face)

    for row in range(tall):
        here = rows[row]
        if not here:
            continue
        y = y0 + (row + 0.5) * step
        base = row * wide
        for face in here:
            a, b, c = mesh.faces[face]
            p, q, r = points[a], points[b], points[c]
            area = (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)
            if -1e-12 < area < 1e-12:
                continue
            lo = max(0, int((min(p.x, q.x, r.x) - x0) / step))
            hi = min(wide - 1, int((max(p.x, q.x, r.x) - x0) / step))
            dp, dq, dr = depths[a], depths[b], depths[c]
            for cell in range(lo, hi + 1):
                x = x0 + (cell + 0.5) * step
                u = ((x - p.x) * (r.y - p.y) - (y - p.y) * (r.x - p.x)) / area
                if u < 0.0:
                    continue
                v = ((q.x - p.x) * (y - p.y) - (q.y - p.y) * (x - p.x)) / area
                if v < 0.0 or u + v > 1.0:
                    continue
                deep = dp + (dq - dp) * u + (dr - dp) * v
                if deep < grid[base + cell]:
                    grid[base + cell] = deep
    return grid, (x0, y0, step, wide, tall)


def _smoothed(mesh: Mesh, raw: list[float], faces, passes: int):
    """Average each vertex with its neighbours, `passes` times.

    A dozen yes-or-no samples per vertex is a dozen coin flips, and the mesh's
    own adjacency is the right thing to average them over: it follows the
    surface, so a pocket's darkness does not leak across the gap to whatever
    happens to be next to it on the page.
    """
    if passes < 1:
        return tuple(raw)
    around: dict[int, set[int]] = {}
    for face in faces:
        a, b, c = mesh.faces[face]
        for one, two in ((a, b), (b, c), (c, a)):
            around.setdefault(one, set()).add(two)
            around.setdefault(two, set()).add(one)
    here = raw
    for _ in range(passes):
        there = list(here)
        for index, neighbours in around.items():
            total = here[index]
            for other in neighbours:
                total += here[other]
            there[index] = total / (len(neighbours) + 1)
        here = there
    return tuple(here)
