"""Which edges of a mesh are worth drawing.

A wireframe draws all of them and reads as a fishing net. A drawing draws three
kinds, and that difference is most of what makes a rendered solid look like it
was inked rather than dumped:

**silhouette** -- the two faces on this edge disagree about whether they face
the viewer, so the surface turns away here. These are the outline. They move
when the camera moves, which is why they are recomputed per view and cannot be
cached on the mesh.

**crease** -- the two faces meet at a sharp angle. The rim of a cylinder, the
corner of a chip. View-independent, so a mesh could cache them, but the
threshold is the author's to choose and the cost is one dot product per edge.

**boundary** -- only one face uses this edge, so the surface just stops. Spot's
eyes and mouth are boundaries; so is the open end of a cut-away.

Everything else is interior tessellation: the diagonal across a quad, the fine
subdivision of a sphere. Drawing it is what makes a render look like a mesh
instead of like an object.

Sign tests near zero are the whole risk in this file, and each tolerance below
says what it is protecting against.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from ..core.geom import Vec2
from .camera import View
from .linalg import Vec3
from .mesh import Mesh

__all__ = [
    "FeatureEdge", "feature_edges", "chain_edges", "facing_faces",
    "smooth_silhouette", "Smoothed",
    "SILHOUETTE", "CREASE", "BOUNDARY", "DEFAULT_CREASE_DEGREES",
    "SMOOTH_CEILING",
]

SILHOUETTE = "silhouette"
CREASE = "crease"
BOUNDARY = "boundary"

#: A fold sharper than this gets a line. Thirty degrees keeps the twenty facets
#: of an icosphere quiet (adjacent faces meet at about 41 degrees at level 0 but
#: under 21 by level 2) while still inking the 90-degree corner of a box and the
#: 60-degree break at the rim of a cone.
DEFAULT_CREASE_DEGREES = 30.0

# The facing test is a strict sign comparison with no dead band, and that is
# deliberate. A tolerance band would classify an exactly edge-on face as
# neither front nor back, and the silhouette -- which is defined as the
# transition between the two -- would come apart into an open curve with gaps
# where the surface is most nearly tangent to the view. Instead, edge-on counts
# as back-facing, consistently, so the loop always closes. The consequence to
# know about: a cube seen exactly face-on has four silhouette edges (the near
# face's outline), not eight.
_FRONT = 0.0

# Two edges count as running the same way, and so as rivals for one inked line,
# when their directions are within this much of parallel. Generous, because the
# thing being compared is two sides of one fold and a fold that twists along
# its length -- which is what a ribbon does -- still has one line down it.
_PARALLEL = math.cos(math.radians(40.0))


@dataclass(frozen=True, slots=True)
class FeatureEdge:
    """One edge worth drawing. `a < b` always, so an edge has one identity."""

    a: int
    b: int
    kind: str

    @property
    def key(self) -> tuple[int, int]:
        return (self.a, self.b)


def facing_faces(mesh: Mesh, view: View) -> tuple[bool, ...]:
    """Whether each face turns toward the camera.

    Degenerate faces have a zero normal and come back False. That is the safe
    answer: a face with no area cannot occlude anything and must not be allowed
    to invent a silhouette edge on either of its sides.
    """
    normals = mesh.face_normals
    centroids = mesh.face_centroids
    return tuple(
        normals[i].dot(view.to_eye(centroids[i])) > _FRONT
        for i in range(len(mesh.faces))
    )


def feature_edges(mesh: Mesh, view: View, *,
                  crease_degrees: float | Sequence[float] =
                  DEFAULT_CREASE_DEGREES,
                  facing: tuple[bool, ...] | None = None,
                  ridges: bool | Sequence[bool] = True) -> list[FeatureEdge]:
    """The drawable edges, in ascending edge order.

    Order is the mesh's own sorted edge order, so the SVG comes out in the same
    sequence on every run and on every machine.

    `ridges=False` inks every fold sharper than the threshold instead of only
    the sharpest one across each fold -- see `_ridges` for why that is almost
    never what a rounded corner wants.

    `crease_degrees` may be one angle for the whole mesh or one per face, and
    `ridges` likewise one flag or one per face. The per-face forms are what let
    a fused scene ink a 168-facet organic nucleus and an 1,800-facet brain at
    different thresholds, and a sectioned brain ink its cut rim whole while the
    surface it was cut from still gets one line per fold: they are one mesh by
    then, and both "how far must a fold turn" and "is a fold here a rim or a
    ridge" are facts about the part, not about the pass.
    """
    per_face = not isinstance(crease_degrees, (int, float))
    angles = tuple(crease_degrees) if per_face else ()
    for angle in angles if per_face else (crease_degrees,):
        if not 0.0 <= angle <= 180.0:
            raise ValueError(
                f"crease angle must be between 0 and 180 degrees, got {angle}")
    if per_face and len(angles) != len(mesh.faces):
        raise ValueError(
            f"one crease angle per face, or one for the mesh: got "
            f"{len(angles)} for {len(mesh.faces)} faces")
    if not isinstance(ridges, bool) and len(ridges) != len(mesh.faces):
        raise ValueError(
            f"one ridges flag per face, or one for the mesh: got "
            f"{len(ridges)} for {len(mesh.faces)} faces")
    front = facing_faces(mesh, view) if facing is None else facing
    inked = _creases(mesh, angles if per_face else crease_degrees, ridges)

    found: list[FeatureEdge] = []
    for (a, b), faces in mesh.edge_faces.items():
        if len(faces) != 2:
            # One face: the surface stops here. Three or more is non-manifold,
            # which happens in scanned and CSG meshes; there is no dihedral
            # angle and no front/back pair, so it is drawn unconditionally --
            # an edge the renderer cannot reason about is one the reader
            # should see.
            found.append(FeatureEdge(a, b, BOUNDARY))
        elif front[faces[0]] != front[faces[1]]:
            found.append(FeatureEdge(a, b, SILHOUETTE))
        elif (a, b) in inked:
            found.append(FeatureEdge(a, b, CREASE))
    return found


def _creases(mesh: Mesh, crease_degrees: float | Sequence[float],
             ridges: bool | Sequence[bool]) -> set[tuple[int, int]]:
    """Which folds get a line: everything sharp enough, then the ridge of it."""
    normals = mesh.face_normals
    per_face_ridges = None if isinstance(ridges, bool) else list(ridges)
    # Compare cosines rather than angles: one cos() here instead of an acos()
    # per edge, and it sidesteps acos's own precision loss near 0 and pi. The
    # cosine runs backwards -- a *smaller* dot is a sharper fold -- which is
    # the only thing to keep in mind reading `_ridges`.
    if isinstance(crease_degrees, (int, float)):
        one = math.cos(math.radians(crease_degrees))
        by_face = None
    else:
        one = 0.0
        by_face = [math.cos(math.radians(a)) for a in crease_degrees]
    turn = {}
    for key, faces in mesh.edge_faces.items():
        if len(faces) == 2:
            # An edge between two parts takes the *stricter* of their two
            # thresholds -- the smaller cosine, since the cosine runs
            # backwards -- so raising one part's angle never inks a fold on
            # its neighbour that the neighbour's own setting would not.
            sharp_below = one if by_face is None \
                else min(by_face[faces[0]], by_face[faces[1]])
            fold = normals[faces[0]].dot(normals[faces[1]])
            if fold < sharp_below:
                turn[key] = fold
    if not turn:
        return set()
    if per_face_ridges is None:
        return _ridges(mesh, turn) if ridges else set(turn)
    # An edge is suppressed only if *both* its faces asked for suppression --
    # the opposite of the stricter-of-two rule the crease angles take, and on
    # purpose. A group turns ridges off to say "my folds are rims, ink them
    # whole", and the edges that makes any difference to are exactly the ones
    # on the group's border, where the other face belongs to somebody else. A
    # rule that let the neighbour's ridges-on win would leave the setting with
    # nothing to act on: the mouse cutaway's cap is flat inside, so its rim
    # against the surface group is the whole of what it has to say.
    unsuppressed = {key for key, faces in mesh.edge_faces.items()
                    if key in turn and len(faces) == 2
                    and not (per_face_ridges[faces[0]]
                             and per_face_ridges[faces[1]])}
    if len(unsuppressed) == len(turn):
        return set(turn)
    # Suppression still reads the *whole* fold set for rivals. Leaving the
    # ridges-off edges out of the neighbourhood would let a fold that used to
    # be beaten by one of them come back, which is a change to the group that
    # did not ask for anything.
    return _ridges(mesh, turn) | unsuppressed


def _ridges(mesh: Mesh, turn: dict[tuple[int, int], float]) -> set[tuple[int, int]]:
    """Keep the sharpest fold across each fold, and drop the rest of it.

    A dihedral threshold answers "is the surface steep here", and on anything
    built by sweeping a section it is the wrong question. A ribbon's edge is a
    rounded corner spread over a fan of facets whose dihedrals climb from
    nothing to ninety degrees and back, so *any* threshold in between lands
    inside the fan and inks a band of near-parallel lines down both edges of
    every ribbon. Raising the threshold does not fix it, it moves the band; the
    only setting with no band is 180 degrees, which is why every ribbon in the
    repository is drawn with no creases at all and has no inked edge either.

    The question worth asking is "is the surface steepest here", which is a
    question about a neighbourhood. Non-maximum suppression across the fold:
    an edge is a ridge unless some *rival* -- an edge in the same
    neighbourhood, running the same way, so a competitor for the same line --
    folds strictly harder. A fan of 20, 35 and 20 degrees keeps the 35 and
    draws one line. A box edge keeps its ninety, because the parallel edge two
    faces away folds by exactly as much and the test is strict.

    Rivals are found by walking one face outward rather than by a distance,
    because a distance is a tolerance nobody can set and the fold's own width
    is exactly what is not known. Two faces out is where the opposite side of a
    quad is: split a quad into triangles and its two parallel edges land in the
    two halves, which is precisely the pair a swept surface needs compared.
    """
    faces, verts = mesh.faces, mesh.edge_faces
    kept: set[tuple[int, int]] = set()
    for key, fold in turn.items():
        along = _direction(mesh.vertices[key[1]] - mesh.vertices[key[0]])
        if along is None:
            continue                            # no length, no direction
        beaten = False
        for other in _nearby(faces, verts, key):
            rival = turn.get(other)
            if rival is None or rival >= fold or other == key:
                continue
            side = _direction(mesh.vertices[other[1]] - mesh.vertices[other[0]])
            if side is not None and abs(along.dot(side)) >= _PARALLEL:
                beaten = True
                break
        if not beaten:
            kept.add(key)
    return kept


def _direction(along: Vec3) -> Vec3 | None:
    length_sq = along.dot(along)
    return None if length_sq <= 0.0 else along * (length_sq ** -0.5)


def _nearby(faces, edge_faces, key: tuple[int, int]):
    """Every edge of the faces on `key` and of the faces next to those.

    Yields duplicates. Deduplicating costs a set per edge and the caller is
    doing dictionary lookups either way, so it is cheaper to let them repeat.
    """
    for face in edge_faces[key]:
        for step in _edges_of(faces[face]):
            yield step
            for neighbour in edge_faces.get(step, ()):
                if neighbour != face:
                    yield from _edges_of(faces[neighbour])


def _edges_of(face):
    a, b, c = face
    return ((a, b) if a < b else (b, a),
            (b, c) if b < c else (c, b),
            (c, a) if c < a else (a, c))


def chain_edges(edges) -> list[tuple[tuple[int, ...], bool]]:
    """Thread edges into the longest polylines they will make.

    Two payoffs. A stroked corner gets a mitre or a round join instead of two
    butt caps that leave a notch, and the number of subpaths drops by roughly
    the average chain length -- which matters more than it should, because
    `core.trace` unions one closure per subpath and every ray query walks the
    whole chain of them.

    Ties are broken by the smallest edge index throughout, so a vertex where
    three edges meet resolves the same way on every run. Returns `(vertices,
    closed)` pairs; a closed chain does not repeat its first vertex.
    """
    pairs = [(min(a, b), max(a, b)) for a, b in edges]
    incident: dict[int, list[int]] = {}
    for index, (a, b) in enumerate(pairs):
        incident.setdefault(a, []).append(index)
        incident.setdefault(b, []).append(index)

    used = [False] * len(pairs)
    chains: list[tuple[tuple[int, ...], bool]] = []

    def step(vertex: int) -> int | None:
        for candidate in incident.get(vertex, ()):
            if not used[candidate]:
                return candidate
        return None

    for start in range(len(pairs)):
        if used[start]:
            continue
        used[start] = True
        a, b = pairs[start]
        chain = [a, b]
        # Forward, then backward from the original start. Walking both ways
        # rather than restarting keeps a chain that begins in the middle of a
        # run from being cut in two.
        while (nxt := step(chain[-1])) is not None:
            used[nxt] = True
            p, q = pairs[nxt]
            chain.append(q if p == chain[-1] else p)
        while (prv := step(chain[0])) is not None:
            used[prv] = True
            p, q = pairs[prv]
            chain.insert(0, q if p == chain[0] else p)
        closed = len(chain) > 3 and chain[0] == chain[-1]
        chains.append((tuple(chain[:-1] if closed else chain), closed))
    return chains


# -- the silhouette of the surface, not of the facets ---------------------

#: Nothing sharper than a right angle is ever taken for the tessellation of a
#: curve, whatever the author has said about creases.
#:
#: Where the smooth silhouette may be computed is a statement about the
#: geometry -- which folds are the model's own edges and which are only how
#: finely a curve was cut -- and the author has already made that statement by
#: choosing a crease angle, so the renderer reuses it rather than asking twice.
#: This is the guard on reusing it. `crease=180` means "ink the outline and
#: nothing else", which is the right thing to say about a ribbon and says
#: nothing at all about whether a box has edges; without a ceiling it would be
#: read as "this box has none", and the outline of the box would come out
#: rounded off at every corner.
SMOOTH_CEILING = 90.0

#: How far the smooth silhouette is lifted toward the viewer before it is
#: tested for occlusion, in multiples of the mesh edge the crossing sits on.
#:
#: It has to be lifted at all because the curve is computed on the surface the
#: facets *stand for* and tested against the facets themselves. Exactly where
#: the curve runs the surface is turning away from the eye, so a chord that
#: departs from it by a sagitta sideways departs by far more than that in
#: depth -- for a cylinder of radius `r` sampled at sagitta `s`, by about
#: `sqrt(2rs)`, which is the facet's own length. An unbiased test therefore has
#: the outline hiding behind the object it outlines, in dashes.
#:
#: One facet, then, and not a fraction of the scene: the quantity being
#: defended against is the size of a facet and nothing else. It is safe at that
#: size because the parts of the curve that are *genuinely* hidden -- the far
#: side of a tube, the back of the hole in a torus -- are behind by something
#: of the order of the object, which is hundreds of facets.
_SURFACE_BIAS = 1.0


@dataclass(frozen=True, slots=True)
class Smoothed:
    """A feature set whose silhouette follows the surface, not the facets.

    `points` and `depths` extend the caller's own tables: the mesh's vertices
    keep their indices and the crossings the silhouette needs are appended, so
    every downstream stage -- occlusion, chaining, the outline the trace clips
    on -- keeps working on plain integer indices and never learns that some of
    them are not vertices.
    """

    edges: list[FeatureEdge]
    points: list[Vec2]
    depths: list[float]
    #: Which faces each *new* edge lies on, for edges that are not in
    #: `mesh.edge_faces` because their endpoints are not mesh vertices.
    adjacency: dict[tuple[int, int], tuple[int, ...]]
    #: How many of `edges` are the interpolated kind. Diagnostics only.
    interpolated: int = 0


def smooth_silhouette(mesh: Mesh, view: View, features: list[FeatureEdge],
                      points: list[Vec2], depths: list[float], *,
                      smooth_degrees: float = SMOOTH_CEILING) -> Smoothed:
    """Replace the facet silhouette with the surface's own, where it can.

    The facet silhouette is the set of edges whose two faces disagree about
    facing the viewer. On a surface that is nearly tangent to the view -- the
    flat of a ribbon, the far shoulder of a tube -- neighbouring facets
    disagree in patches rather than along a line, and the "outline" comes out
    as a zig-zag through the interior that reads as hatching. It is not a
    tessellation error that a finer mesh fixes cheaply: halving the facet size
    halves the amplitude and doubles the number of them.

    So compute the curve the facets stand for instead. Give every vertex the
    signed quantity `n . to_eye`, which is positive where the smooth surface
    faces the viewer and negative where it turns away, and take the zero set.
    On a triangulation that field is piecewise linear, so within one triangle
    the zero set is one straight segment between two edge crossings -- never a
    fan, never a patch, by construction rather than by cleanup. Marching
    triangles, in other words, on the facing field.

    Two crossings are shared exactly when two triangles share the edge they lie
    on, because the crossing is keyed on that edge and computed once, so the
    segments come out already threaded into closed curves.

    Where the model has a real fold the facet silhouette *is* the right answer
    -- the silhouette of a cube is its edges -- so the smooth pass stays away
    from anything within one triangle of a fold, a border or a branch, and the
    original edges are kept there. The two regimes meet at a triangle's width.
    """
    rough = mesh.rough_vertices(smooth_degrees)
    if len(rough) >= len(mesh.vertices):
        return Smoothed(features, points, depths, {})   # no smooth region

    faces, verts = mesh.faces, mesh.vertices
    field = [n.dot(view.to_eye(v))
             for n, v in zip(mesh.vertex_normals, verts)]
    table = mesh.edge_faces

    crossings: dict[tuple[int, int], int] = {}
    made: list[Vec3] = []
    lift: list[float] = []

    def cut(u: int, v: int) -> int:
        key = (u, v) if u < v else (v, u)
        found = crossings.get(key)
        if found is None:
            lo, hi = key
            here, there = field[lo], field[hi]
            share = here / (here - there)      # the signs differ: never 0/0
            along = verts[hi] - verts[lo]
            found = len(verts) + len(made)
            made.append(verts[lo] + along * share)
            lift.append(math.sqrt(along.dot(along)) * _SURFACE_BIAS)
            crossings[key] = found
        return found

    on_surface: dict[tuple[int, int], tuple[int, ...]] = {}
    new: list[FeatureEdge] = []
    replaced: set[int] = set()
    for index, (a, b, c) in enumerate(faces):
        if a in rough or b in rough or c in rough:
            continue
        near = field[a] > _FRONT, field[b] > _FRONT, field[c] > _FRONT
        if near[0] == near[1] == near[2]:
            replaced.add(index)
            continue
        pair, sides = [], []
        for (u, v), (one, two) in zip(((a, b), (b, c), (c, a)),
                                      ((0, 1), (1, 2), (2, 0))):
            if near[one] != near[two]:
                pair.append(cut(u, v))
                sides.append((u, v) if u < v else (v, u))
        if len(pair) != 2:
            continue                     # cannot happen on a triangle; cheap
        replaced.add(index)
        edge = FeatureEdge(min(pair), max(pair), SILHOUETTE)
        skip = {index}
        for side in sides:
            skip.update(table[side])
        new.append(edge)
        on_surface[edge.key] = tuple(sorted(skip))

    kept = [e for e in features
            if e.kind != SILHOUETTE or not _covered(table[e.key], replaced)]
    grown, deep = view.project_all(made)
    return Smoothed(kept + new, points + grown,
                    depths + [d - up for d, up in zip(deep, lift)],
                    on_surface, len(new))


def _covered(faces: tuple[int, ...], replaced: set[int]) -> bool:
    """Whether the smooth pass has already spoken for both sides of an edge."""
    return len(faces) == 2 and faces[0] in replaced and faces[1] in replaced
