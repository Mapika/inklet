"""An immutable triangle mesh, and the tables everything else reads.

A `Mesh` is vertices, triangles, and optionally a name per triangle. Everything
past that -- normals, the edge-to-face map, bounds -- is *derived*, computed on
first use and kept. Three separate passes ask for the edge map (feature edges,
hidden-line removal, the closed-surface test) and rebuilding it three times for
a 20k-triangle scan is the difference between a figure that renders while you
watch and one you go for coffee over.

The mesh is frozen so that a cached derivation can never be stale. Every
"modifying" helper returns a new mesh, which also means a scene can share one
loaded body between several placements without any of them stepping on the
others.

Winding is counter-clockwise seen from outside, so a face normal points out of
the solid. Nothing here enforces that -- an OBJ from the wild may disagree --
but the silhouette test and the shading both assume it, so `parse.load(...,
repair=True)` exists to make it true when trimesh is available.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Iterable, Sequence

from .linalg import Mat4, Vec3

__all__ = ["Mesh", "MeshError"]


class MeshError(ValueError):
    """A mesh that cannot be built or read: a bad index, a malformed file, a
    degenerate request."""


# Two triangles whose normals differ by less than this are treated as one flat
# surface. It is a hair over the float noise you get from normalising a normal
# computed by two cross products, and far under any angle a person would call a
# fold. Used for merging coplanar facets, not for creases -- creases have their
# own, much larger, threshold that the author sets.
_COPLANAR_EPS = 1e-7

# Two edges of a triangle shorter than this at a shared corner have no reliable
# direction between them, so the angle they subtend is not worth weighting a
# normal by. Squared, because that is how it is tested.
_TINY_EDGE_SQ = 1e-24

# Below this, a triangle's two edges are parallel enough that the cross product
# is numerically meaningless. Such faces are kept (deleting them would break
# every index in the file) but their normal is reported as the zero vector and
# every consumer skips them.
_DEGENERATE_AREA = 1e-14


def _corner_angle(one: Vec3, two: Vec3) -> float:
    """The angle between two edges leaving a corner, in radians.

    `acos` of a clamped cosine rather than `atan2` of the cross product: the
    two agree, and the clamp is the part that matters, because a corner of a
    sliver triangle produces a cosine a few ulps outside [-1, 1] and `acos`
    raises on it rather than returning something near 0 or pi.
    """
    one_sq, two_sq = one.dot(one), two.dot(two)
    if one_sq < _TINY_EDGE_SQ or two_sq < _TINY_EDGE_SQ:
        return 0.0
    cosine = one.dot(two) / math.sqrt(one_sq * two_sq)
    return math.acos(max(-1.0, min(1.0, cosine)))


@dataclass(frozen=True)
class Mesh:
    vertices: tuple[Vec3, ...]
    faces: tuple[tuple[int, int, int], ...]
    #: One name per face, or empty for an unnamed mesh. Names come from OBJ
    #: `g`/`o` records and from `Mesh.merged`, and are what lets an author
    #: anchor an arrow on "cortex" rather than on a vertex number.
    groups: tuple[str, ...] = ()
    name: str = ""
    _derived: dict = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        count = len(self.vertices)
        for index, face in enumerate(self.faces):
            if len(face) != 3:
                raise MeshError(
                    f"face {index} has {len(face)} vertices; meshes are triangles "
                    "-- triangulate polygons at parse time"
                )
            for i in face:
                if not 0 <= i < count:
                    raise MeshError(
                        f"face {index} refers to vertex {i}, but the mesh has "
                        f"{count} vertices"
                    )
        if self.groups and len(self.groups) != len(self.faces):
            raise MeshError(
                f"{len(self.groups)} group names for {len(self.faces)} faces; "
                "give one per face or none at all"
            )

    def __len__(self) -> int:
        return len(self.faces)

    @property
    def is_empty(self) -> bool:
        return not self.faces

    # -- derived tables ---------------------------------------------------

    @property
    def face_normals(self) -> tuple[Vec3, ...]:
        """Unit outward normals. Degenerate faces get the zero vector, which
        every consumer reads as "skip me" -- returning an arbitrary unit vector
        instead would silently put a random silhouette edge in the drawing."""
        if "normals" not in self._derived:
            out = []
            for i, j, k in self.faces:
                a, b, c = self.vertices[i], self.vertices[j], self.vertices[k]
                n = (b - a).cross(c - a)
                length_sq = n.dot(n)
                out.append(n * (length_sq ** -0.5) if length_sq > _DEGENERATE_AREA
                           else Vec3())
            self._derived["normals"] = tuple(out)
        return self._derived["normals"]

    @property
    def face_centroids(self) -> tuple[Vec3, ...]:
        if "centroids" not in self._derived:
            self._derived["centroids"] = tuple(
                (self.vertices[i] + self.vertices[j] + self.vertices[k]) * (1.0 / 3.0)
                for i, j, k in self.faces
            )
        return self._derived["centroids"]

    @property
    def vertex_normals(self) -> tuple[Vec3, ...]:
        """The smooth surface these facets stand for, one normal per vertex.

        A triangle mesh is a *sample* of a surface, and its face normals are
        piecewise constant: they say which way each flat scrap points, never
        which way the thing it approximates points. That difference is what
        makes a silhouette come out as a zig-zag through the facets rather than
        as the curve it should be, and what makes a crease threshold unable to
        tell a real fold from the fold-per-facet of a swept tube. Both want to
        know about the surface, so both want these.

        **Angle-weighted**, after Thurmer & Wuthrich: each incident face
        contributes its normal scaled by the angle it subtends *at that
        vertex*. The obvious alternatives are both wrong in ways that show. An
        unweighted mean lets the side of a mesh that happens to be finely
        triangulated outvote the side that is not, so refining one half of a
        model tilts the normals along the seam. An area-weighted mean has the
        same defect in a different currency. The subtended angle is the only
        weight that depends on the *surface* and not on how it was cut up, so a
        vertex where four coarse quads meet and one where forty slivers meet
        come out the same.

        A vertex nothing references, or one where every incident face is
        degenerate, gets the zero vector -- the same "skip me" convention
        `face_normals` uses.

        **This is not a smoothing group.** Every incident face is averaged in,
        including across a hard fold, so a cube's corner normal points along
        the body diagonal. That is the honest answer to "which way does the
        surface face here" when the surface genuinely has a corner there, and
        it is why anything using these has to gate on the dihedral itself
        rather than trusting them blind.
        """
        if "vertex_normals" not in self._derived:
            normals = self.face_normals
            summed = [Vec3()] * len(self.vertices)
            for index, face in enumerate(self.faces):
                normal = normals[index]
                if normal == Vec3():
                    continue                      # degenerate: nothing to say
                for corner in range(3):
                    at = face[corner]
                    here = self.vertices[at]
                    one = self.vertices[face[(corner + 1) % 3]] - here
                    two = self.vertices[face[(corner + 2) % 3]] - here
                    summed[at] = summed[at] + normal * _corner_angle(one, two)
            self._derived["vertex_normals"] = tuple(
                v.normalized() if v.dot(v) > 0.0 else Vec3() for v in summed)
        return self._derived["vertex_normals"]

    def rough_vertices(self, degrees: float) -> frozenset[int]:
        """Vertices with a fold, a border or a branch somewhere around them.

        The gate `vertex_normals` says it needs. A vertex normal is the average
        of every face that meets there, so across a fold it is the average of
        two answers, and the mean of two right answers is a wrong one. Anything
        that wants to treat the mesh as the smooth surface it stands for --
        the outline in `edges.smooth_silhouette`, the shading in
        `shade.sorted_facets` -- asks this first and leaves those vertices to
        the facets.

        The whole one-ring goes, not just the fold itself: a triangle is
        smooth-shaded or it is not, and one corner of it sitting on a crease is
        enough to disqualify the triangle. That is the granularity both callers
        work at, and it is why they agree about where the smooth region is when
        they are given the same angle.

        The comparison is `<=`, where `feature_edges` uses `<`. An edge exactly
        at the threshold counts as a fold rather than as a curve, so that a
        right-angled corner is still a corner when the ceiling above happens to
        be a right angle -- `cos(radians(90))` is 6e-17, not 0, and a cube's
        face normals dot to exactly 0.0.
        """
        key = ("rough", degrees)
        if key not in self._derived:
            normals = self.face_normals
            sharp_below = math.cos(math.radians(degrees))
            rough: set[int] = set()
            for (a, b), faces in self.edge_faces.items():
                if len(faces) != 2 or \
                        normals[faces[0]].dot(normals[faces[1]]) <= sharp_below:
                    rough.add(a)
                    rough.add(b)
            self._derived[key] = frozenset(rough)
        return self._derived[key]

    @property
    def edge_faces(self) -> dict[tuple[int, int], tuple[int, ...]]:
        """Undirected edge -> the faces on it, both in ascending order.

        Keys are `(lo, hi)` so the two directed uses of one edge collapse onto
        the same entry, and the face lists are sorted so that "the other face"
        is the same face on every run. Insertion order already follows face
        order, but the sort is written down rather than relied on: a dict that
        happens to be ordered is not a promise.
        """
        if "edge_faces" not in self._derived:
            table: dict[tuple[int, int], list[int]] = {}
            for index, (i, j, k) in enumerate(self.faces):
                for a, b in ((i, j), (j, k), (k, i)):
                    table.setdefault((a, b) if a < b else (b, a), []).append(index)
            self._derived["edge_faces"] = {
                key: tuple(sorted(value)) for key, value in sorted(table.items())
            }
        return self._derived["edge_faces"]

    @property
    def edges(self) -> tuple[tuple[int, int], ...]:
        """Every undirected edge, sorted. The iteration order of the drawing."""
        if "edges" not in self._derived:
            self._derived["edges"] = tuple(self.edge_faces)
        return self._derived["edges"]

    @property
    def is_closed(self) -> bool:
        """No edge has a free side: the surface bounds a solid region.

        This is the licence to cull back faces before hidden-line removal, and
        on a real scan it is worth roughly a five-fold speedup. The argument
        for culling being *exact* rather than an approximation is that any ray
        reaching a back face must have entered through a nearer front face, so
        the front face already hid whatever the back one would have.

        That argument needs the surface to bound a region, which is a weaker
        condition than manifoldness: an *even* number of faces on every edge is
        enough, because a mod-2 two-cycle in space always bounds. Insisting on
        exactly two would throw the speedup away over the six pinched edges a
        decimator leaves in an otherwise sealed cortical surface -- a real mesh
        this was measured on, where the strict test cost 4.6x for nothing. An
        odd arity really is a boundary, whether it is one face or three, and
        those are refused.
        """
        if "closed" not in self._derived:
            self._derived["closed"] = bool(self.faces) and all(
                len(f) % 2 == 0 for f in self.edge_faces.values()
            )
        return self._derived["closed"]

    @property
    def bounds(self) -> tuple[Vec3, Vec3]:
        """Axis-aligned low and high corners. Raises on an empty mesh, the same
        way `Diagram.bbox` refuses to invent a box for nothing."""
        if "bounds" not in self._derived:
            if not self.vertices:
                raise MeshError("an empty mesh has no bounds")
            lo = hi = self.vertices[0]
            for v in self.vertices[1:]:
                lo, hi = lo.min(v), hi.max(v)
            self._derived["bounds"] = (lo, hi)
        return self._derived["bounds"]

    @property
    def center(self) -> Vec3:
        lo, hi = self.bounds
        return (lo + hi) * 0.5

    @property
    def size(self) -> Vec3:
        lo, hi = self.bounds
        return hi - lo

    @property
    def radius(self) -> float:
        """Distance from the bbox centre to the furthest vertex. What a camera
        needs to know to frame the thing without clipping it."""
        if "radius" not in self._derived:
            c = self.center
            self._derived["radius"] = max(
                ((v - c).length for v in self.vertices), default=0.0)
        return self._derived["radius"]

    @property
    def group_names(self) -> tuple[str, ...]:
        """Distinct face-group names, sorted -- so anchors derived from them
        come out in the same order whatever the file's ordering was."""
        if "group_names" not in self._derived:
            self._derived["group_names"] = tuple(sorted({g for g in self.groups if g}))
        return self._derived["group_names"]

    def group_center(self, name: str) -> Vec3:
        """Centroid of the vertices belonging to a named group, area-weighted
        by nothing: a plain average of the distinct vertices the group touches.
        Area weighting would drag the point toward whichever end of a part
        happened to be finely tessellated."""
        if not self.groups:
            raise MeshError(f"this mesh has no face groups, so no group {name!r}")
        seen: dict[int, None] = {}
        for face, group in zip(self.faces, self.groups):
            if group == name:
                for i in face:
                    seen[i] = None
        if not seen:
            raise MeshError(
                f"no group named {name!r}; this mesh has {self.group_names}")
        total = Vec3()
        for i in sorted(seen):
            total = total + self.vertices[i]
        return total * (1.0 / len(seen))

    # -- derivation -------------------------------------------------------

    def transformed(self, matrix: Mat4) -> Mesh:
        """Move the mesh. A mirroring transform reverses every winding, because
        the alternative is a solid whose normals all point inward and whose
        silhouette comes out inside-out."""
        vertices = tuple(matrix.apply(v) for v in self.vertices)
        faces = self.faces
        if matrix.determinant < 0.0:
            faces = tuple((k, j, i) for i, j, k in self.faces)
        return Mesh(vertices, faces, self.groups, self.name)

    def merged(self, *others: Mesh) -> Mesh:
        """Concatenate, keeping each part's group names.

        Vertices are not welded. Welding would merge the seam between two parts
        of an exploded assembly and turn two silhouettes into one, which is
        exactly the thing an exploded view exists to avoid.
        """
        parts = (self, *others)
        vertices: list[Vec3] = []
        faces: list[tuple[int, int, int]] = []
        groups: list[str] = []
        named = any(p.groups or p.name for p in parts)
        for part in parts:
            offset = len(vertices)
            vertices.extend(part.vertices)
            faces.extend((i + offset, j + offset, k + offset)
                         for i, j, k in part.faces)
            if named:
                fallback = part.name
                groups.extend(part.groups if part.groups
                              else (fallback,) * len(part.faces))
        return Mesh(tuple(vertices), tuple(faces),
                    tuple(groups) if named else (), self.name)

    def grouped(self, name: str) -> Mesh:
        """The same geometry with every face labelled, for `merged` to keep."""
        return replace(self, groups=(name,) * len(self.faces), name=name,
                       _derived={})

    def centered(self) -> Mesh:
        c = self.center
        return self.transformed(Mat4.translation(-c))

    def scaled_to_fit(self, size: float) -> Mesh:
        """Uniformly scale so the longest bounding-box side is `size`.

        Uniform, always: matching all three sides would squash a cortical
        column into a cube, and the author asked for a size, not a redesign.
        """
        extent = self.size
        longest = max(extent.x, extent.y, extent.z)
        if longest <= 0.0:
            raise MeshError("a mesh with no extent cannot be scaled to fit")
        return self.transformed(Mat4.scaling(size / longest))

    def drill(self, axis: str | Sequence[float] | Vec3 = "z", *,
              radius: float, at: Sequence[float] | Vec3 | None = None,
              segments: int = 20, group: str | None = None) -> Mesh:
        """A cylindrical hole straight through the solid, both sides open.

        Real geometry, not a dark disc parked proud of the face: the rim is an
        edge the silhouette pass can find, the inner wall has normals pointing
        into the hole, and the result is watertight when this mesh was -- so
        the hole is still there when the camera comes round the back.

            plate = build("box", size_z=0.2).drill("z", radius=0.15,
                                                   at=(1.4, 0.7, 0))

        See `inklet.three.drill` for what it will and will not cut, and
        `Mesh.subtract` for the general boolean when trimesh is installed.
        """
        from .drill import drill

        return drill(self, axis, radius=radius, at=at, segments=segments,
                     group=group)

    def subtract(self, tool: Mesh) -> Mesh:
        """This mesh with `tool` removed. Needs trimesh; `drill` does not."""
        from .drill import subtract

        return subtract(self, tool)

    def coplanar_patches(self, faces: Sequence[int]) -> list[tuple[int, ...]]:
        """Group a subset of faces into maximal flat, connected patches.

        This is what stops a shaded cube from being twelve triangles with six
        hairline seams down the middle of its faces. Two triangles join when
        they share an edge *and* their normals agree to within float noise, so
        a curved surface stays subdivided and a flat one becomes one polygon.
        """
        members = {f: None for f in sorted(faces)}
        normals = self.face_normals
        neighbours: dict[int, list[int]] = {f: [] for f in members}
        for (_, _), touching in self.edge_faces.items():
            if len(touching) != 2:
                continue
            a, b = touching
            if a in members and b in members:
                if normals[a].dot(normals[b]) >= 1.0 - _COPLANAR_EPS:
                    neighbours[a].append(b)
                    neighbours[b].append(a)
        seen: dict[int, None] = {}
        patches: list[tuple[int, ...]] = []
        for start in members:
            if start in seen:
                continue
            stack, patch = [start], []
            seen[start] = None
            while stack:
                current = stack.pop()
                patch.append(current)
                for other in sorted(neighbours[current]):
                    if other not in seen:
                        seen[other] = None
                        stack.append(other)
            patches.append(tuple(sorted(patch)))
        return patches


def merge(meshes: Iterable[Mesh]) -> Mesh:
    """Fold a sequence into one mesh; an empty sequence is an empty mesh."""
    parts = list(meshes)
    if not parts:
        return Mesh((), ())
    return parts[0].merged(*parts[1:])
