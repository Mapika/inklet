"""A hole through a solid, and the general boolean when trimesh is there.

`build("box")` and its friends are parametric solids with no boolean anywhere
near them, so until now the only way to draw a bolt hole was a thin dark disc
parked a hundredth of a unit proud of the face -- one per hole per plate. That
is a z-fight waiting for a camera that looks at the face edge-on, and it is a
lie: the hole is a sticker, and turning the camera round shows the plate to be
solid.

`Mesh.drill(axis, radius, at=)` cuts the real thing. It is not general CSG and
does not pretend to be. What it does is the case a figure keeps asking for --
**a cylinder straight through a solid** -- and it does that exactly:

* the faces the hole passes through are re-tessellated, not stamped over, so
  the rim is a real edge and the silhouette pass finds it;
* the inner wall is real geometry with its normals pointing into the hole, so
  the hole survives being looked at from the other side, from an angle, and
  under `sort="exact"`;
* the result is watertight when the input was, which is what lets back-face
  culling and hidden-line removal keep their licence.

**Where the hole comes out is asked, not assumed.** A ray along the axis is
cast through the mesh at the centre of the hole and at every corner of its
circle, and the crossings -- sorted, and required to be the same even number
for every ray -- say which surfaces the hole passes through. That is what makes
one call work on a plate, on a cylinder drilled along its own axis, and on a
stack of two slabs in one mesh, and what turns a hole running off the edge of
a part into an error with a sentence rather than a mesh with a gap in it.

**A hole through a flat face is cut a face at a time, and adds no vertices to
that face's border.** When the surface a crossing goes through is a single flat
patch (`Mesh.coplanar_patches`), the whole patch is re-triangulated at once:
its boundary loops, the holes already in it, and the new circle, run through
hole-bridging and ear clipping. Ear clipping is worth the code for exactly one
property -- it introduces no vertices of its own. Anything that cut the patch
with lines instead would leave a point in the middle of an edge that the
neighbouring side wall knows nothing about, which is a T-junction: invisible to
the eye, and a hole to everything that counts faces per edge. It would also
turn a 12-triangle box into a 300-triangle box for one bolt hole, and a
25-plate assembly into something nobody wants to project.

**A hole through a curved wall is cut a facet at a time, and the pieces are
welded.** A pipe with a side port has no flat patch to re-triangulate: the
circle comes out across a strip of the barrel, whose facets lie in different
planes and so have to be clipped one by one. That *does* put a point in the
middle of a shared edge, wherever the circle crosses one -- but it is not a
T-junction, because the facet on the other side of that edge is being cut too,
computes the same point from the same two lines, and gets the same index from
the welding table. Which is why the strip is grown to every facet the circle
reaches rather than to the ones the rays happened to land on. The rim that
comes out has more corners than the circle does, and not the same ones on the
way in as on the way out, so the wall between the two rims is built by walking
both in angle order rather than by zipping them.

**Watertight means sharing indices, not sharing coordinates.** `Mesh.is_closed`
counts the faces on each *edge*, and an edge is a pair of vertex indices, so
two coincident points at different indices are a hole however close they are.
Every point this module makes goes through one welding table, seeded with the
mesh's own vertices so that a rim point landing on an existing corner becomes
that corner.
"""

from __future__ import annotations

import math
from typing import Sequence

from .linalg import Vec3
from .mesh import Mesh, MeshError
from .place import as_axis

__all__ = ["drill", "subtract", "DEFAULT_HOLE_SEGMENTS"]

#: Sides on a drilled hole. Twenty is what a bolt hole on a printed assembly
#: drawing was already being faked with, and a hole is small on the page by
#: definition -- it is a feature of a part, not the part. `Mesh.drill` repeats
#: this default in its own signature; they are meant to agree.
DEFAULT_HOLE_SEGMENTS = 20

#: Two crossings of one ray closer together than this fraction of the solid's
#: own size are one crossing found twice -- a ray passing exactly along an edge
#: shared by two triangles. Merged rather than refused, because a corner of a
#: polygonised circle landing on a triangulation seam is not the author's
#: mistake and happens on any regular solid.
_SAME_HIT = 1e-9

#: How far apart two points have to be to be two points, as a fraction of the
#: solid's size. Everything closer welds onto one index.
_WELD = 1e-7

#: One turn, for angles round the hole. The rim of a cut through a curved
#: strip is kept in angle order rather than in corner order, because it has
#: corners the circle does not.
_TURN = 2.0 * math.pi

#: Below this, a projected triangle has no area in the plane perpendicular to
#: the axis: it is a face lying *along* the drilling direction -- the side wall
#: of a plate, or the wall of a hole already drilled -- and a ray parallel to
#: the axis neither hits it nor is stopped by it.
_FLAT_AREA = 1e-14


def drill(mesh: Mesh, axis: str | Sequence[float] | Vec3 = "z", *,
          radius: float, at: Sequence[float] | Vec3 | None = None,
          segments: int = DEFAULT_HOLE_SEGMENTS,
          group: str | None = None) -> Mesh:
    """A cylindrical hole straight through `mesh`, all the way out both sides.

    `at` is any point on the hole's axis and defaults to the solid's centre;
    `axis` is `"x"`, `"y"`, `"z"`, an optionally signed name, or a vector.
    `group=` names the inner wall as a face group, so it can be painted apart
    from the surface it is cut into -- `model(colors={"hole": ...})` is what a
    bolt hole wants, since the inside of a hole is in shadow whatever the light
    outside it is doing.

    Curved walls are cut too -- a side port through a pipe, a bore through a
    sphere -- so the hole is not limited to axes that meet flat faces.

    Raises rather than guessing when the hole does not go cleanly through: a
    radius that reaches the edge of the part or an existing hole, a surface
    that folds away from the drill inside the circle, a facet corner the circle
    grazes. The alternative is a mesh with a gap in it, which nothing
    downstream would notice until the silhouette came out wrong.
    """
    if radius <= 0.0:
        raise MeshError(f"a hole needs a positive radius; got {radius}")
    if segments < 3:
        raise MeshError(f"a hole needs at least three sides; got {segments}")
    if mesh.is_empty:
        raise MeshError("there is nothing to drill: the mesh has no faces")

    frame = _Frame(mesh, as_axis(axis), at)
    ring = tuple((radius * math.cos(k * _TURN / segments),
                  radius * math.sin(k * _TURN / segments))
                 for k in range(segments))
    plan = _surfaces_crossed(mesh, frame, ring, _levels(mesh, frame, ring))

    weld = _Welder(mesh.vertices, frame.tolerance)
    cut = {face for _, faces in plan for face in faces}
    faces: list[tuple[int, int, int]] = []
    groups: list[str] = []
    named = bool(mesh.groups) or group is not None
    fallback = mesh.name or "solid"

    def own(index: int) -> str:
        return (mesh.groups[index] if mesh.groups else fallback) if named else ""

    for index, face in enumerate(mesh.faces):
        if index not in cut:
            faces.append(face)
            groups.append(own(index))

    rims: list[list[tuple[float, int]]] = []
    for flat, surface in plan:
        if flat:
            cap, rim = _recut(mesh, surface, frame, ring, weld)
            angles = [(math.atan2(y, x) % _TURN, index)
                      for index, (x, y) in zip(rim, ring)]
            angles.sort()
        else:
            cap, angles = _strip_cut(mesh, surface, frame, ring, weld)
        faces.extend(cap)
        groups.extend([own(next(iter(surface)) if flat else min(surface))]
                      * len(cap))
        rims.append(angles)

    wall = group if group is not None else fallback
    for near, far in zip(rims[0::2], rims[1::2]):
        for triangle in _wall(near, far):
            faces.append(triangle)
            groups.append(wall if named else "")

    out = _compacted(weld.points, faces, tuple(groups) if named else (),
                     mesh.name)
    if mesh.is_closed and not out.is_closed:
        raise MeshError(
            "the hole did not come out watertight, so the cut has found a "
            "surface it cannot handle; `Mesh.subtract` with a cylinder, which "
            "trimesh does, is the general answer")
    return out


def subtract(mesh: Mesh, tool: Mesh) -> Mesh:
    """`mesh` with `tool` removed, by trimesh's boolean. Needs trimesh.

    The general case `drill` deliberately is not. It is here as a *widening*
    rather than as the default: what `inklet.solid("box", ...)` draws must not
    depend on what happens to be installed, so nothing reaches for this unless
    the author names it.
    """
    from .deps import require

    trimesh = require("trimesh")
    if mesh.is_empty or tool.is_empty:
        raise MeshError("both meshes need faces for a boolean")
    result = _as_trimesh(trimesh, mesh).difference(_as_trimesh(trimesh, tool))
    faces = tuple(tuple(int(i) for i in face) for face in result.faces)
    if not faces:
        raise MeshError("the difference is empty: the tool covers the whole solid")
    vertices = tuple(Vec3(float(x), float(y), float(z))
                     for x, y, z in result.vertices)
    return Mesh(vertices, faces, name=mesh.name)          # type: ignore[arg-type]


def _as_trimesh(trimesh, mesh: Mesh):
    return trimesh.Trimesh(
        vertices=[v.as_tuple() for v in mesh.vertices],
        faces=[list(f) for f in mesh.faces], process=False)


# -- the frame perpendicular to the axis ----------------------------------


class _Frame:
    """`(u, v, w)` with `w` along the drill, and the flattening it gives.

    Everything the cut decides happens in the `(u, v)` plane, where the hole is
    a circle and the drilling direction is a point. `w` completes it
    right-handed so that a wall wound one way has its normal pointing into the
    hole rather than out of it, which is the difference between a hole and a
    boss.
    """

    def __init__(self, mesh: Mesh, axis: Vec3, at: Sequence[float] | Vec3 | None):
        helper = Vec3(0.0, 0.0, 1.0)
        if abs(axis.dot(helper)) > 0.9:
            helper = Vec3(1.0, 0.0, 0.0)
        self.w = axis
        self.u = helper.cross(axis).normalized()
        self.v = axis.cross(self.u)
        if at is None:
            self.origin = mesh.center
        elif isinstance(at, Vec3):
            self.origin = at
        else:
            values = tuple(float(c) for c in at)
            if len(values) != 3:
                raise MeshError(f"at= needs three coordinates, got {len(values)}")
            self.origin = Vec3(*values)
        size = mesh.size
        self.span = max(size.x, size.y, size.z, 1.0)
        self.tolerance = self.span * _WELD

    def flat(self, p: Vec3) -> tuple[float, float]:
        d = p - self.origin
        return (d.dot(self.u), d.dot(self.v))

    def at(self, x: float, y: float, t: float) -> Vec3:
        return self.origin + self.u * x + self.v * y + self.w * t


class _Plane:
    """One flat patch's plane, read in the frame's coordinates.

    A point of the cut is chosen in `(u, v)` and has to be put back on the
    surface it came from. That is one division, and it is exact: the patch is
    flat, and the line through the point along the axis meets it once because
    the patch is not parallel to the drill.
    """

    def __init__(self, normal: Vec3, base: Vec3, frame: _Frame):
        self.nu, self.nv = normal.dot(frame.u), normal.dot(frame.v)
        self.nw = normal.dot(frame.w)
        self.offset = normal.dot(base - frame.origin)
        if abs(self.nw) < 1e-15:
            raise MeshError("a surface parallel to the drill has no depth here")

    def depth(self, x: float, y: float) -> float:
        return (self.offset - self.nu * x - self.nv * y) / self.nw


# -- where the hole comes out ---------------------------------------------


def _levels(mesh: Mesh, frame: _Frame, ring) -> list[set[int]]:
    """The faces the hole passes through, one set per crossing, front to back.

    Cast down the axis at the centre of the hole and at each corner of it, and
    insist that all of them cross the same number of times. That is the whole
    validation: a hole that runs off the edge of a plate crosses twice at some
    corners and not at all at others, and one that leaves through a curved wall
    lands on a different surface at each corner -- both come back here as a
    count that does not agree, which is a sentence the author can act on rather
    than a mesh with a gap in it.
    """
    flattened = _Flattened(mesh, frame)
    columns = [flattened.crossings(x, y) for x, y in [(0.0, 0.0)] + list(ring)]
    counts = len(columns[0])
    if counts == 0 or counts % 2:
        raise MeshError(
            f"the drill axis crosses this solid {counts} times through the "
            "middle of the hole, and a hole has to go in one side and out "
            "another; check the axis and where it is placed")
    for column in columns[1:]:
        if len(column) != counts:
            raise MeshError(
                f"the hole crosses the solid {counts} times at its centre and "
                f"{len(column)} times at its rim, so it does not pass cleanly "
                "through: it reaches an edge of the part, or leaves through a "
                "surface that runs along the drill")
    return [set().union(*(column[level][1] for column in columns))
            for level in range(counts)]


class _Flattened:
    """Every face of the mesh, projected once into the drill's own plane.

    Twenty-one rays go down the same axis, and the naive loop re-projects the
    whole mesh for each of them. A plate with four holes in it is drilled four
    times and grows as it goes, so that is the difference between a bolt hole
    costing a millisecond and costing sixteen -- and the electrolyser poster
    drills twenty-eight of them. Projecting once and keeping a page box per
    face turns each ray into a bounds test on most of the mesh.
    """

    __slots__ = ("mesh", "frame", "faces", "near")

    def __init__(self, mesh: Mesh, frame: _Frame):
        self.mesh = mesh
        self.frame = frame
        self.near = frame.span * _SAME_HIT
        flat = [frame.flat(v) for v in mesh.vertices]
        self.faces = []
        for index, (a, b, c) in enumerate(mesh.faces):
            corners = (flat[a], flat[b], flat[c])
            area = _area(corners)
            if abs(area) <= _FLAT_AREA:
                continue           # a face along the drill: no ray meets it
            xs = (corners[0][0], corners[1][0], corners[2][0])
            ys = (corners[0][1], corners[1][1], corners[2][1])
            self.faces.append((min(xs), max(xs), min(ys), max(ys),
                               corners, area, index))

    def crossings(self, x: float, y: float):
        """Where a ray along the axis at `(x, y)` meets the mesh, by depth.

        Returns `(depth, faces)` per crossing; more than one face when the ray
        goes exactly through an edge or a corner, which the tolerance folds
        into one crossing rather than into an odd count.
        """
        found: list[tuple[float, int]] = []
        for x0, x1, y0, y1, corners, area, index in self.faces:
            if x < x0 or x > x1 or y < y0 or y > y1:
                continue
            if not _inside(corners, area, x, y):
                continue
            plane = _Plane(self.mesh.face_normals[index],
                           self.mesh.vertices[self.mesh.faces[index][0]],
                           self.frame)
            found.append((plane.depth(x, y), index))
        found.sort()
        out: list[tuple[float, set[int]]] = []
        for depth, index in found:
            if out and depth - out[-1][0] <= self.near:
                out[-1][1].add(index)
            else:
                out.append((depth, {index}))
        return out


def _surfaces_crossed(mesh: Mesh, frame: _Frame, ring, levels):
    """What the hole goes through at each crossing, front to back.

    Each entry is `(flat, faces)`. A crossing that lands wholly inside one
    coplanar patch is cut the cheap way, by re-triangulating that patch as a
    whole; anything else is a curved strip, and the faces are the ones the
    circle actually reaches rather than the ones the rays happened to hit.
    """
    patches = mesh.coplanar_patches(range(len(mesh.faces)))
    home = {face: patch for patch in patches for face in patch}
    out = []
    for faces in levels:
        owners = {home[face] for face in faces}
        if len(owners) == 1:
            out.append((True, owners.pop()))
        else:
            out.append((False, _strip_faces(mesh, frame, ring, faces)))
    seen: set[int] = set()
    for _, faces in out:
        if seen & set(faces):
            raise MeshError(
                "the hole goes in and out through the same facets, so it does "
                "not pass through the solid; check the axis and where it is "
                "placed")
        seen |= set(faces)
    return out


# -- re-triangulating one flat face ---------------------------------------


def _recut(mesh: Mesh, patch: tuple[int, ...], frame: _Frame, ring,
           weld: "_Welder"):
    """Replace a flat patch with the same face, plus one more hole in it.

    Returns the patch's new triangles and the indices of the new rim, in the
    ring's own corner order so the wall can be built on it. The patch's border
    is untouched -- same vertices, same edges -- which is what keeps the side
    walls attached to it.
    """
    normal = mesh.face_normals[patch[0]]
    plane = _Plane(normal, mesh.vertices[mesh.faces[patch[0]][0]], frame)
    #: A patch facing away from the drill projects clockwise. Mirroring one
    #: axis puts every patch into one convention, so the triangulator only ever
    #: sees a counter-clockwise outline -- and mirroring back is free, because
    #: the triangles come out as vertex indices.
    flip = -1.0 if normal.dot(frame.w) < 0.0 else 1.0

    def flat(index: int) -> tuple[float, float]:
        x, y = frame.flat(mesh.vertices[index])
        return (x, y * flip)

    rings = [[(index,) + flat(index) for index in loop]
             for loop in _loops(mesh, patch)]
    rings.sort(key=lambda loop: -abs(_ring_area([(p[1], p[2]) for p in loop])))
    if not rings:
        raise MeshError(
            "this face has no outline, so the hole has nothing to be cut into; "
            "the mesh may be non-manifold there")

    rim = [weld.add(frame.at(x, y, plane.depth(x, y))) for x, y in ring]
    hole = [(index, x, y * flip) for index, (x, y) in zip(rim, ring)]
    # The triangulator wants the outline counter-clockwise and every hole
    # clockwise. Which way a loop came out of the border walk depends on which
    # way the patch faces and on where its geometry came from, so say it here
    # rather than depend on it: three signs settled once, instead of a wrong
    # answer that survives one hole and falls over on the third.
    outer = _wound(rings[0], True)
    holes = [_wound(loop, False) for loop in rings[1:]] + [_wound(hole, False)]
    _check_clear(outer, holes[:-1], holes[-1])
    triangles = _earcut(outer, holes)
    if triangles is None:
        raise MeshError(
            "this face could not be re-triangulated around the hole; it may be "
            "self-intersecting, or the hole may touch its edge")
    return triangles, rim


def _wound(loop, anticlockwise: bool):
    """A loop turning the way the triangulator needs it to turn."""
    area = _ring_area([(p[1], p[2]) for p in loop])
    if area == 0.0:
        raise MeshError(
            "this face has an outline with no area in it, which the cut cannot "
            "make sense of; the mesh may be degenerate there")
    return list(loop) if (area > 0.0) == anticlockwise else list(reversed(loop))


def _loops(mesh: Mesh, patch: tuple[int, ...]) -> list[list[int]]:
    """A flat patch's border, as closed loops of vertex indices.

    A directed edge with no partner going the other way is on the border. The
    loops come out wound the way the faces are, so the outer one and the holes
    already in the patch are told apart by the sign of their area.
    """
    directed = set()
    for face in patch:
        a, b, c = mesh.faces[face]
        directed.update(((a, b), (b, c), (c, a)))
    border = {a: b for a, b in directed if (b, a) not in directed}
    if len(border) != len(set(border.values())):
        raise MeshError(
            "this face's border passes through one corner twice, which the cut "
            "cannot follow; simplify the mesh or use `Mesh.subtract`")
    loops = []
    seen: set[int] = set()
    for start in sorted(border):
        if start in seen:
            continue
        loop = [start]
        seen.add(start)
        node = border[start]
        while node != start:
            if node in seen:
                raise MeshError("this face's border is not a set of closed loops")
            seen.add(node)
            loop.append(node)
            node = border[node]
        loops.append(loop)
    return loops


def _check_clear(outer, holes, hole) -> None:
    """Refuse a hole that runs into the edge of the face or into another hole.

    Ear clipping would produce *something* for overlapping loops, and that
    something would be wrong in a way no later error message could explain.
    """
    for other in [outer] + list(holes):
        for i in range(len(other)):
            ax, ay = other[i][1], other[i][2]
            bx, by = other[(i + 1) % len(other)][1], other[(i + 1) % len(other)][2]
            for j in range(len(hole)):
                cx, cy = hole[j][1], hole[j][2]
                dx, dy = hole[(j + 1) % len(hole)][1], hole[(j + 1) % len(hole)][2]
                if _crosses(ax, ay, bx, by, cx, cy, dx, dy):
                    raise MeshError(
                        "the hole runs into the edge of the face or into a hole "
                        "already in it; move it or narrow it")


def _crosses(ax, ay, bx, by, cx, cy, dx, dy) -> bool:
    def side(px, py, qx, qy, rx, ry) -> int:
        value = (qx - px) * (ry - py) - (qy - py) * (rx - px)
        return (value > 0.0) - (value < 0.0)

    return (side(ax, ay, bx, by, cx, cy) * side(ax, ay, bx, by, dx, dy) < 0
            and side(cx, cy, dx, dy, ax, ay) * side(cx, cy, dx, dy, bx, by) < 0)


# -- ear clipping, with holes ---------------------------------------------


def _earcut(outer, holes):
    """Triangulate a counter-clockwise outline with clockwise holes in it.

    Only the vertices given: no point is invented, which is the property the
    whole patch-at-a-time design rests on. Each hole is spliced into the
    outline through a bridge to a vertex that can see it, leaving one simple
    polygon with slits in it, and the polygon is then reduced ear by ear.
    """
    polygon = list(outer)
    for hole in sorted(holes, key=lambda h: min(p[1] for p in h)):
        polygon = _bridge(polygon, hole)
        if polygon is None:
            return None
    return _clip_ears(polygon)


def _bridge(polygon, hole):
    """Splice one hole into the outline through a vertex that can see it.

    Take the hole's leftmost corner and look left. The first outline edge the
    ray meets going *downwards* -- the outline winds counter-clockwise, so
    those are the ones facing the hole -- gives a candidate to bridge to. If
    some other corner sits in the triangle between the hole, the ray hit and
    that candidate, it is in the way, and the one at the shallowest angle to
    the ray is the corner that can really see the hole.

    This is the hole elimination every ear-clipper uses, and its whole point is
    that the bridge lands on a vertex that already exists rather than on a new
    one in the middle of an edge.
    """
    start = min(range(len(hole)), key=lambda i: (hole[i][1], hole[i][2]))
    hx, hy = hole[start][1], hole[start][2]
    count = len(polygon)
    reach = None
    best = None
    for i in range(count):
        ax, ay = polygon[i][1], polygon[i][2]
        j = (i + 1) % count
        bx, by = polygon[j][1], polygon[j][2]
        if ay == by or not by <= hy <= ay:
            continue
        x = ax + (hy - ay) * (bx - ax) / (by - ay)
        if x > hx or (reach is not None and x <= reach):
            continue
        reach = x
        best = i if ax < bx else j
    if best is None:
        return None
    mx, my = polygon[best][1], polygon[best][2]
    corners = ((hx, hy, mx, my, reach, hy) if hy < my
               else (reach, hy, mx, my, hx, hy))
    shallow = None
    for i in range(count):
        px, py = polygon[i][1], polygon[i][2]
        if px == hx or not mx <= px <= hx:
            continue
        if not _in_triangle(*corners, px, py):
            continue
        if not _sees(polygon[i - 1], polygon[i], polygon[(i + 1) % count],
                     hole[start]):
            continue
        slope = abs(hy - py) / (hx - px)
        if shallow is None or slope < shallow or (
                slope == shallow and px > polygon[best][1]):
            shallow, best = slope, i
    rotated = hole[start:] + hole[:start]
    return polygon[:best + 1] + rotated + [rotated[0]] + polygon[best:]


def _sees(prev, here, following, target) -> bool:
    """Does `target` lie in the polygon's interior wedge at `here`?

    A bridge out of a corner has to leave on the inside of it, which for a
    corner that turns back on itself is the wider of the two sides.
    """
    if _turn(prev, here, following) > 0.0:
        return (_turn(here, target, following) <= 0.0
                and _turn(here, prev, target) <= 0.0)
    return (_turn(here, target, prev) > 0.0
            or _turn(here, following, target) > 0.0)


def _in_triangle(ax, ay, bx, by, cx, cy, px, py) -> bool:
    d1 = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    d2 = (cx - bx) * (py - by) - (cy - by) * (px - bx)
    d3 = (ax - cx) * (py - cy) - (ay - cy) * (px - cx)
    return not ((d1 < 0.0 or d2 < 0.0 or d3 < 0.0)
                and (d1 > 0.0 or d2 > 0.0 or d3 > 0.0))


def _clip_ears(polygon):
    """Reduce a simple counter-clockwise polygon to triangles, an ear at a time.

    Quadratic, and unapologetically so: the polygons here are one flat face of
    a solid with a few holes in it, tens of corners at the very most, and a
    sweep-line triangulator would be a hundred lines of edge cases to save a
    few thousand comparisons.
    """
    verts = list(polygon)
    out = []
    shed = 0
    while len(verts) > 3:
        count = len(verts)
        cut = None
        for i in range(count):
            a, b, c = verts[i - 1], verts[i], verts[(i + 1) % count]
            if _turn(a, b, c) <= 0.0:
                continue
            if any(p[0] not in (a[0], b[0], c[0])
                   and _in_triangle(a[1], a[2], b[1], b[2], c[1], c[2],
                                    p[1], p[2])
                   for p in verts):
                continue
            cut = i
            break
        if cut is None:
            # Nothing convex and empty is left, which happens where a bridge
            # doubled a vertex back on itself: shed a corner that lies on the
            # line between its neighbours. That is an ear of no area, and it
            # costs the triangulation nothing to drop rather than emit.
            for i in range(count):
                if _turn(verts[i - 1], verts[i], verts[(i + 1) % count]) == 0.0:
                    cut = i
                    break
            if cut is None or shed > count:
                return None
            shed += 1
            verts.pop(cut)
            continue
        a, b, c = verts[cut - 1], verts[cut], verts[(cut + 1) % count]
        out.append((a[0], b[0], c[0]))
        verts.pop(cut)
    if len({v[0] for v in verts}) == 3:
        out.append((verts[0][0], verts[1][0], verts[2][0]))
    return out


def _turn(a, b, c) -> float:
    return (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1])


def _ring_area(points) -> float:
    total = 0.0
    for i in range(len(points)):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % len(points)]
        total += x0 * y1 - x1 * y0
    return total * 0.5


def _area(flat) -> float:
    (ax, ay), (bx, by), (cx, cy) = flat
    return ((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) * 0.5


def _inside(flat, area: float, x: float, y: float) -> bool:
    """Point in projected triangle, inclusive on the boundary.

    Inclusive because a ray landing on a shared edge must be seen by both of
    the triangles that own it, or the crossing count comes out odd; the pair of
    hits it then finds is collapsed by the tolerance in `_crossings`.
    """
    (ax, ay), (bx, by), (cx, cy) = flat
    sign = 1.0 if area > 0.0 else -1.0
    for (px, py), (qx, qy) in (((ax, ay), (bx, by)), ((bx, by), (cx, cy)),
                               ((cx, cy), (ax, ay))):
        if ((qx - px) * (y - py) - (qy - py) * (x - px)) * sign < 0.0:
            return False
    return True


# -- a hole through a curved strip ----------------------------------------


def _neighbours(mesh: Mesh) -> dict[int, tuple[int, ...]]:
    """Face -> the faces across its three edges."""
    out: dict[int, list[int]] = {}
    for owners in mesh.edge_faces.values():
        for face in owners:
            out.setdefault(face, []).extend(o for o in owners if o != face)
    return {face: tuple(sorted(set(others))) for face, others in out.items()}


def _strip_faces(mesh: Mesh, frame: _Frame, ring, seeds: set[int]):
    """Every facet of one sheet that the hole's circle reaches, grown from the rays.

    The rays only find the facets they happen to land on, and a facet the
    circle merely clips a corner off can sit between two of them. Growing the
    seed set across shared edges, taking in any neighbour the circle actually
    overlaps, is what makes the strip complete. The same condition is what
    stops the walk wandering round the barrel onto the sheet on the far side:
    in the drill's own plane that sheet sits under the same circle, but the
    facets joining the two run *along* the drill and have no area here.
    """
    flat = [frame.flat(v) for v in mesh.vertices]
    disc = list(ring)
    across = _neighbours(mesh)
    strip: set[int] = set()
    queue = sorted(seeds)
    while queue:
        face = queue.pop()
        if face in strip:
            continue
        if face not in seeds:
            a, b, c = mesh.faces[face]
            tri = (flat[a], flat[b], flat[c])
            if abs(_area(tri)) <= _FLAT_AREA or not _meets(tri, disc):
                continue
        strip.add(face)
        queue.extend(across.get(face, ()))
    return strip


def _meets(one, two) -> bool:
    """Do two convex outlines share area? Touching along a line does not count."""
    for poly in (one, two):
        count = len(poly)
        for i in range(count):
            (ax, ay), (bx, by) = poly[i], poly[(i + 1) % count]
            nx, ny = ay - by, bx - ax
            if nx == 0.0 and ny == 0.0:
                continue
            here = [nx * px + ny * py for px, py in one]
            there = [nx * px + ny * py for px, py in two]
            if max(here) <= min(there) or max(there) <= min(here):
                return False
    return True


def _strip_cut(mesh: Mesh, faces: set[int], frame: _Frame, ring,
               weld: "_Welder"):
    """Replace a curved strip of facets with the same strip, one hole in it.

    The flat cut owes its no-new-vertices property to re-triangulating a whole
    patch at once, and a curved strip cannot be handled that way: its facets
    lie in different planes, so each has to be cut on its own. That does put a
    point in the middle of a shared edge -- wherever the circle crosses one --
    but it is not a T-junction, because the facet on the other side of that
    edge is in the strip too and computes the same point from the same two
    lines, and the welding table gives both the one index. Which is why the
    strip is grown to *every* facet the circle reaches rather than to the ones
    the rays happened to hit.

    Returns the strip's new triangles and its rim, as `(angle, index)` sorted
    by angle: unlike the flat cut, the rim has more corners than the circle
    does, and they are not at the same angles on the way in as on the way out.
    """
    order = sorted(faces)
    flip = 0.0
    for face in order:
        along = mesh.face_normals[face].dot(frame.w)
        if abs(along) < 1e-12:
            raise MeshError(
                "the hole comes out along a surface that runs edge-on to the "
                "drill, so there is nothing there to cut a rim into; change "
                "the axis, or use `Mesh.subtract` with a cylinder")
        want = -1.0 if along < 0.0 else 1.0
        if flip == 0.0:
            flip = want
        elif flip != want:
            raise MeshError(
                "the hole comes out through a fold: the surface turns away "
                "from the drill inside the circle, so the rim would cross "
                "itself. Move or narrow the hole, or use `Mesh.subtract`")

    seen: dict[int, tuple[float, float]] = {}

    def flat_of(index: int) -> tuple[float, float]:
        point = seen.get(index)
        if point is None:
            x, y = frame.flat(mesh.vertices[index])
            point = seen[index] = (x, y * flip)
        return point

    circle = [(("r", k), x, y * flip) for k, (x, y) in enumerate(ring)]
    if _ring_area([(p[1], p[2]) for p in circle]) < 0.0:
        circle.reverse()
    _check_strip_clear(mesh, faces, flat_of, circle)

    triangles: list[tuple[int, int, int]] = []
    rim: dict[int, float] = {}
    for face in order:
        corners = mesh.faces[face]
        subject = [(("v", i),) + flat_of(i) for i in corners]
        if _ring_area([(p[1], p[2]) for p in subject]) < 0.0:
            subject.reverse()
        plane = _Plane(mesh.face_normals[face], mesh.vertices[corners[0]], frame)

        def place(node):
            tag, x, y = node
            if tag[0] == "v":
                return (tag[1], x, y)
            down = y * flip
            index = weld.add(frame.at(x, down, plane.depth(x, down)))
            rim[index] = math.atan2(down, x) % _TURN
            return (index, x, y)

        loops, holed = _minus(subject, circle, frame.tolerance)
        if holed:
            outer = _wound([place(p) for p in loops[0]], True)
            inner = _wound([place(p) for p in loops[1]], False)
            _check_clear(outer, [], inner)
            cut = _earcut(outer, [inner])
        else:
            cut = []
            for loop in loops:
                if len(loop) < 3:
                    continue
                piece = _clip_ears([place(p) for p in loop])
                if piece is None:
                    cut = None
                    break
                cut.extend(piece)
        if cut is None:
            raise MeshError(
                "a facet the hole passes through could not be re-triangulated "
                "around it; the circle may be touching one of its corners, "
                "which a nudge to `at=` or `radius=` moves off")
        # A corner of the circle landing on a facet edge welds onto the point
        # that edge's own crossing made, and the sliver between them collapses.
        # It is a triangle of no area, and keeping it would leave an edge with
        # its two sides on the same face -- watertight arithmetic counting a
        # hole where there is none.
        triangles.extend(t for t in cut if len(set(t)) == 3)
    return triangles, sorted((angle, index) for index, angle in rim.items())


def _check_strip_clear(mesh: Mesh, faces: set[int], flat_of, circle) -> None:
    """Refuse a hole whose circle crosses an edge the strip does not own.

    An edge with a facet on one side only, or with its far side outside the
    strip, is the boundary of the surface being cut: the hole is running off
    it, and the wall would have nothing to attach to.
    """
    owners = mesh.edge_faces
    for face in sorted(faces):
        corners = mesh.faces[face]
        for k in range(3):
            p, q = corners[k], corners[(k + 1) % 3]
            (ax, ay), (bx, by) = flat_of(p), flat_of(q)
            hit = False
            for j in range(len(circle)):
                cx, cy = circle[j][1], circle[j][2]
                dx, dy = circle[(j + 1) % len(circle)][1], circle[(j + 1) % len(circle)][2]
                if _crosses(ax, ay, bx, by, cx, cy, dx, dy):
                    hit = True
                    break
            if not hit:
                continue
            both = owners.get((p, q) if p < q else (q, p), ())
            if len(both) != 2 or any(other not in faces for other in both):
                raise MeshError(
                    "the hole runs off the edge of the surface it is cut "
                    "into: move it, narrow it, or use `Mesh.subtract`")


def _minus(subject, clip, tolerance: float):
    """A convex outline minus a convex one, as counter-clockwise loops.

    Returns `(loops, holed)`. `holed` says the clip sits wholly inside the
    subject, and then `loops` is the subject and the clip, to be handed to the
    ear clipper as an outline with a hole. Otherwise every loop is a simple
    polygon on its own -- there can be two of them, because a band across a
    triangle leaves a piece on each side.

    Weiler-Atherton, and it leans on both outlines being convex: their border
    crossings then alternate in and out along each of them, so following the
    subject forward and the clip backward, swapping at every crossing, walks
    each piece of the difference exactly once.
    """
    ns, nc = len(subject), len(clip)
    # A corner of the circle landing *on* a facet edge is not a near miss to be
    # rounded away: it is where the two borders meet, and a strict crossing
    # test sees neither of the two circle edges that share it, which leaves the
    # crossings odd and the walk with nowhere to go. It is also not rare -- the
    # pole of an icosphere is a vertex, and a circle drilled through it has its
    # first corner on one of the edges radiating from it. Found first, so that
    # the ordinary scan can leave those two circle edges alone.
    touching: dict[int, tuple[int, float, bool]] = {}
    for j in range(nc):
        px, py = clip[j][1], clip[j][2]
        for i in range(ns):
            ax, ay = subject[i][1], subject[i][2]
            bx, by = subject[(i + 1) % ns][1], subject[(i + 1) % ns][2]
            rx, ry = bx - ax, by - ay
            length = math.hypot(rx, ry)
            if length <= 0.0:
                continue
            if abs(rx * (py - ay) - ry * (px - ax)) > tolerance * length:
                continue
            along = ((px - ax) * rx + (py - ay) * ry) / (length * length)
            if not 0.0 < along < 1.0:
                continue
            side = _wedge(clip, j, rx, ry)
            if side is not None:
                touching[j] = (i, along, side)
            else:
                touching[j] = (i, along, None)      # a graze: no crossing here
            break

    cuts_a: list[list[tuple[float, int]]] = [[] for _ in range(ns)]
    at_corner: dict[int, int] = {}
    cuts_b: list[list[tuple[float, int]]] = [[] for _ in range(nc)]
    crossings: list[tuple[tuple, float, float, bool]] = []
    for j, (i, along, side) in sorted(touching.items()):
        if side is None:
            continue
        at_corner[j] = len(crossings)
        cuts_a[i].append((along, len(crossings)))
        crossings.append((clip[j][0], clip[j][1], clip[j][2], side))

    for i in range(ns):
        ax, ay = subject[i][1], subject[i][2]
        bx, by = subject[(i + 1) % ns][1], subject[(i + 1) % ns][2]
        rx, ry = bx - ax, by - ay
        for j in range(nc):
            if touching.get(j, (None,))[0] == i:
                continue                      # the corner itself, already had
            if touching.get((j + 1) % nc, (None,))[0] == i:
                continue                      # the other edge on that corner
            cx, cy = clip[j][1], clip[j][2]
            dx, dy = clip[(j + 1) % nc][1], clip[(j + 1) % nc][2]
            if not _crosses(ax, ay, bx, by, cx, cy, dx, dy):
                continue
            sx, sy = dx - cx, dy - cy
            denom = rx * sy - ry * sx
            if denom == 0.0:
                continue
            t = ((cx - ax) * sy - (cy - ay) * sx) / denom
            u = ((cx - ax) * ry - (cy - ay) * rx) / denom
            cuts_a[i].append((t, len(crossings)))
            cuts_b[j].append((u, len(crossings)))
            # Leaving the clip when the subject's direction turns clockwise off
            # the clip's, which for a counter-clockwise clip means stepping out
            # of its interior.
            crossings.append((("x", i, j), ax + rx * t, ay + ry * t, denom > 0.0))

    if not crossings:
        if _within(clip[0], subject):
            return [list(subject), list(clip)], True
        if _within(subject[0], clip):
            return [], False
        return [list(subject)], False

    exits = [cid for cid, entry in enumerate(crossings) if entry[3]]
    if not exits or len(exits) * 2 != len(crossings):
        raise MeshError(
            "the hole grazes a facet corner where it comes out, which the cut "
            "cannot resolve; nudge `at=` or `radius=` so the circle crosses "
            "the surface cleanly")

    walk_a, walk_b = [], []
    where_a: dict[int, int] = {}
    where_b: dict[int, int] = {}
    for i in range(ns):
        walk_a.append((subject[i], None))
        for _, cid in sorted(cuts_a[i]):
            where_a[cid] = len(walk_a)
            walk_a.append((crossings[cid][:3], cid))
    for j in range(nc):
        cid = at_corner.get(j)
        where_b[cid] = len(walk_b) if cid is not None else None
        walk_b.append((clip[j], cid))
        for _, other in sorted(cuts_b[j]):
            where_b[other] = len(walk_b)
            walk_b.append((crossings[other][:3], other))

    loops = []
    done: set[int] = set()
    for start in exits:
        if start in done:
            continue
        loop = []
        cid = start
        for _ in range(len(crossings) + 1):
            done.add(cid)
            loop.append(crossings[cid][:3])
            k = (where_a[cid] + 1) % len(walk_a)
            while walk_a[k][1] is None:
                loop.append(walk_a[k][0])
                k = (k + 1) % len(walk_a)
            entered = walk_a[k][1]
            loop.append(crossings[entered][:3])
            k = (where_b[entered] - 1) % len(walk_b)
            while walk_b[k][1] is None:
                loop.append(walk_b[k][0])
                k = (k - 1) % len(walk_b)
            cid = walk_b[k][1]
            if cid == start:
                break
        else:
            raise MeshError(
                "the cut could not walk round the hole in one of the facets it "
                "comes out through; nudge `at=` or `radius=`")
        loops.append(loop)
    return loops, False


def _wedge(clip, j: int, dx: float, dy: float):
    """Does a line through corner `j` go into the clip, out of it, or past it?

    `True` for out, `False` for in, `None` for a line that only touches. The
    interior of a counter-clockwise convex outline at a corner is the wedge to
    the left of both edges meeting there, so a direction is inside when it is
    to the left of both.
    """
    ax, ay = clip[j - 1][1], clip[j - 1][2]
    bx, by = clip[j][1], clip[j][2]
    cx, cy = clip[(j + 1) % len(clip)][1], clip[(j + 1) % len(clip)][2]
    into = (bx - ax, by - ay)
    away = (cx - bx, cy - by)
    forward = (into[0] * dy - into[1] * dx > 0.0
               and away[0] * dy - away[1] * dx > 0.0)
    if forward:
        return False
    backward = (into[1] * dx - into[0] * dy > 0.0
                and away[1] * dx - away[0] * dy > 0.0)
    return True if backward else None


def _within(point, poly) -> bool:
    """Is a point strictly inside a convex, counter-clockwise outline?"""
    x, y = point[1], point[2]
    for i in range(len(poly)):
        ax, ay = poly[i][1], poly[i][2]
        bx, by = poly[(i + 1) % len(poly)][1], poly[(i + 1) % len(poly)][2]
        if (bx - ax) * (y - ay) - (by - ay) * (x - ax) <= 0.0:
            return False
    return True


def _wall(near, far):
    """Triangles bridging two rims, which need not have the same corners.

    The flat cut gives each rim the circle's own corners and nothing else, so
    the two zip together. A cut through a curved strip also has a rim point
    wherever the circle crossed a facet edge, and those land at different
    angles going in and coming out. Walking both rims in angle order and always
    advancing whichever is behind bridges them without inventing a point on
    either -- the merge two sorted lists get -- and on two rims that do match it
    lays down exactly the two triangles per side that zipping would.
    """
    out = []
    n, m = len(near), len(far)
    if n < 3 or m < 3:
        raise MeshError("the hole came out with less than a rim; it may be "
                        "leaving the solid through more than one surface")
    start = m - 1
    for k in range(m):
        if far[k][0] <= near[0][0]:
            start = k
    shift = 0.0 if far[start][0] <= near[0][0] else -_TURN
    walk_n = [(near[k % n][0] + _TURN * (k // n), near[k % n][1])
              for k in range(n + 1)]
    walk_f = [(far[(start + k) % m][0] + _TURN * ((start + k) // m) + shift,
               far[(start + k) % m][1]) for k in range(m + 1)]
    here, there = walk_n[0][1], walk_f[0][1]
    p = q = 0
    while p < n or q < m:
        if q < m and (p >= n or walk_f[q + 1][0] <= walk_n[p + 1][0]):
            q += 1
            triangle = (here, there, walk_f[q][1])
            there = walk_f[q][1]
        else:
            p += 1
            triangle = (here, there, walk_n[p][1])
            here = walk_n[p][1]
        if len(set(triangle)) == 3:
            out.append(triangle)
    return out

# -- keeping the result watertight ----------------------------------------


class _Welder:
    """One index per distinct point, including the mesh's own.

    Seeded with the original vertices so that a rim landing exactly on a corner
    reuses it, and looked up over the 27 cells around a rounded key so that two
    points either side of a grid line do not come out as two points.
    """

    def __init__(self, vertices: Sequence[Vec3], tolerance: float):
        self.points = list(vertices)
        self.tolerance = tolerance
        self.table: dict[tuple[int, int, int], list[int]] = {}
        for index, point in enumerate(vertices):
            self.table.setdefault(self._key(point), []).append(index)

    def _key(self, p: Vec3) -> tuple[int, int, int]:
        t = self.tolerance
        return (int(round(p.x / t)), int(round(p.y / t)), int(round(p.z / t)))

    def add(self, point: Vec3) -> int:
        key = self._key(point)
        limit = self.tolerance * self.tolerance
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for index in self.table.get((key[0] + dx, key[1] + dy,
                                                 key[2] + dz), ()):
                        gap = self.points[index] - point
                        if gap.dot(gap) <= limit:
                            return index
        self.points.append(point)
        self.table.setdefault(key, []).append(len(self.points) - 1)
        return len(self.points) - 1


def _compacted(points: Sequence[Vec3], faces, groups, name: str) -> Mesh:
    """Drop the vertices the cut orphaned, so bounds and radius stay honest."""
    used = sorted({i for face in faces for i in face})
    renumber = {old: new for new, old in enumerate(used)}
    return Mesh(tuple(points[i] for i in used),
                tuple(tuple(renumber[i] for i in face) for face in faces),
                groups, name)                          # type: ignore[arg-type]
