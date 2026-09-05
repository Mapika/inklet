"""Flat-shaded facets, for when line art is not enough.

Three looks come out of the same machinery: line art alone, solid alone, and
solid with the feature edges inked over it. The third is what most methods
figures actually want -- the fill gives the object volume, the outline gives it
an edge that survives being printed at 40 mm wide.

Two decisions are worth defending.

**Coplanar facets are merged before they are drawn.** A shaded cube built from
twelve triangles has six diagonal seams down the middle of its faces, because
two abutting filled polygons antialias against each other and leave a
half-covered hairline. Merging them into six polygons removes the seam by
removing the join, which is better than papering over it with a matching
stroke: there is nothing left to fight.

**Painter's algorithm, not a depth buffer.** The output is vector paths, and a
depth buffer would mean rasterising. Sorting by depth is exact for a convex
solid, where front-facing facets never overlap at all, and is the usual
approximation everywhere else. It is also a better approximation than it
sounds: a mesh fine enough to look curved has facets small enough that a mean
depth is close to the depth everywhere on them, and measured against a
ray-cast reference the mean-depth sort gets a 48,000-face protein right to
seven sample points in twenty-four thousand. Where it fails is *large* facets
that cross -- two solids pushed through each other, a plane through a cone --
and `sort="exact"` in `sorted_facets` settles those by asking the pairs and
cutting the ones with no answer. See `order`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from ..core.geom import Vec2
from ..themes.color import mix
from .camera import View
from .linalg import Vec3
from .mesh import Mesh
from .occlude import vertex_occlusion
from .order import painter_sort

__all__ = ["Facet", "sorted_facets", "sorts_exactly", "facet_tone",
           "vertex_tones", "dissolve", "DEFAULT_LIGHT", "DEFAULT_LEVELS",
           "DEFAULT_LIFT", "DEFAULT_SHADE", "AUTO_EXACT_FACETS",
           "AUTO_EXACT_PAIRS"]

#: Up to this many faces, `sort="auto"` -- the default -- offers the mesh to
#: the exact painting order rather than settling it by each facet's mean
#: depth. See `sorts_exactly` for how the number was arrived at, and for the
#: measurements behind the 2,000 and the 8,000 it used to be.
AUTO_EXACT_FACETS = 22000

#: ...and up to this many *candidate pairs*, which is the one that governs.
#: `sort="auto"` hands this to `order.painter_sort` as a budget; over it the
#: run stops and the facets come back in depth order. See `sorts_exactly` for
#: why there are two numbers and which of them is doing the work.
AUTO_EXACT_PAIRS = 400000

#: Light direction in *view* space: x right, y up, z toward the viewer. Over
#: the viewer's left shoulder and slightly above, which is where every
#: draughtsman since Dürer has put it, and -- being view-relative -- it stays
#: there when the camera moves, so a figure of six views is lit consistently
#: instead of six objects each lit from a different side of the room.
DEFAULT_LIGHT = Vec3(-0.40, 0.55, 0.73)

#: Tones are quantised to this many steps. Quantising is not a concession: a
#: continuous ramp across a subdivided sphere prints as mud, while a score of
#: steps reads as a shaded object and compresses the SVG, because neighbouring
#: facets share a fill and collapse into one path.
#:
#: Twenty rather than a dozen because of what a band boundary looks like on a
#: *triangulated* sphere. The boundary is not a smooth curve; it is the jagged
#: staircase where a triangle's own normal happens to tip across a step, and
#: the eye reads that staircase as a defect in the object. Fewer steps do not
#: hide it, they widen it and raise the contrast across it. Twenty makes each
#: step small enough that the staircase stops registering, and is still coarse
#: enough that a 1280-face sphere collapses to a few dozen paths.
#:
#: All of which is an argument about *flat* shading, and it stops applying the
#: moment `sorted_facets` is given a `smooth_degrees`: a band boundary is then
#: the isoline it stands for, there is no staircase to make small, and a step
#: costs real polygons instead of being free. A smooth-shaded body wants
#: roughly half this, and comes out both rounder and lighter for it.
DEFAULT_LEVELS = 20

#: How far `tint` lifts the lit end of the ramp toward paper, and pushes the
#: dark end toward ink. Pale by default, because the shipped styles ink their
#: feature edges over the fill and the edges have to stay the strongest thing
#: on the page. Lower the lift when the shaded body *is* the subject.
DEFAULT_LIFT, DEFAULT_SHADE = 0.72, 0.30


@dataclass(frozen=True, slots=True)
class Facet:
    """One filled polygon: page outline, how far away, and how light it is."""

    points: tuple[Vec2, ...]
    depth: float
    tone: float          # 0 = facing away from the light, 1 = facing into it
    group: str = ""
    #: How far this facet is faded toward paper for being far away. 0 at the
    #: front of the scene, at most `depth_cue` at the back.
    cue: float = 0.0
    #: The mesh vertex indices behind `points`, same order, wound the way the
    #: faces are. Carried so that two facets which end up the same colour can
    #: be dissolved into one outline by cancelling the edge between them --
    #: see `dissolve`. Empty when a caller built the facet by hand.
    ring: tuple[int, ...] = ()
    #: The plane the facet lies in, as `(normal, offset)` with
    #: `normal . point == offset`. Only the exact painter's order reads it, and
    #: it is what makes that order exact: `depth` is a mean over three corners
    #: and says nothing about the middle, while the plane answers for every
    #: point of the facet at once. `None` when a caller built the facet by
    #: hand, which the exact order takes as "leave this one where it is".
    plane: tuple[Vec3, float] | None = None
    #: Which coplanar patch this facet came from, or -1 for "no patch". Set
    #: only on the rings of a patch that has a *hole* in it, and only under
    #: the exact sort, where the hole has to be put back beside its own face
    #: after the sort has moved the face -- see `sorted_facets`. Survives a
    #: cut, because `order._cut` copies the facet it splits.
    patch: int = -1


def sorts_exactly(mesh: Mesh, sort: str) -> bool:
    """Whether this mesh, asked for this sort, is offered the exact order.

    `"auto"` is the default and the only interesting answer: offered up to
    `AUTO_EXACT_FACETS` faces, mean depth above it. *Offered*, not given --
    the face count is the cheap half of a two-part gate, and the half that
    settles it is `AUTO_EXACT_PAIRS`, read inside `order.painter_sort`.

    **The cost is linear in the number of candidate pairs, and the face count
    is a poor proxy for it.** That is the fact both numbers turn on. Sort
    alone, one camera, best of three, after the array separating-axis pass:

    | mesh                | faces  | facets | pairs     | sort    | us/pair | us/face |
    |---------------------|--------|--------|-----------|---------|---------|---------|
    | sphere, 4 subdivs   |  5,120 |  2,560 |     9,587 |   12 ms |    1.21 |    2.27 |
    | sphere, 5 subdivs   | 20,480 | 10,240 |    41,604 |   56 ms |    1.34 |    2.72 |
    | sphere, 6 subdivs   | 81,920 | 40,960 |   176,497 |  241 ms |    1.36 |    2.94 |
    | torus, 40 x 40      |  3,200 |    800 |     3,211 |    9 ms |    2.77 |    2.80 |
    | digimouse body      |  1,500 |    704 |     3,316 |    6 ms |    1.78 |    3.96 |
    | Allen hemi, cut     |  5,020 |  2,122 |    20,579 |   23 ms |    1.12 |    4.60 |
    | Allen brain         |  9,000 |  4,501 |    40,083 |   44 ms |    1.11 |    4.93 |
    | spot                |  5,856 |  5,814 |    70,014 |   84 ms |    1.20 |   14.39 |
    | Stanford bunny      |  3,000 |  2,999 |    53,085 |   66 ms |    1.23 |   21.83 |
    | brain-lh            | 18,000 |  8,883 |   343,942 |  420 ms |    1.22 |   23.34 |
    | EGFR kinase, smooth | 44,576 | 66,444 | 1,202,709 | 3524 ms |    2.93 |   79.05 |

    **Pairs predict the clock within a factor of 2.6 and faces within a factor
    of 35.** The face count misses in both directions and for two unrelated
    reasons. Downwards, because a scan piles slivers into one grid cell and a
    parametric solid does not: the bunny asks 17.7 pairs per face and a sphere
    2.0, so a face buys nine times the work on one than on the other. Upwards,
    because a face is not a facet -- coplanar merging takes the torus's 3,200
    faces down to 800, and smooth banding takes the kinase's 44,576 *up* to
    66,444, because a band boundary cuts facets out of the surface.

    So why is the entry gate still counting faces? Because the pair count is
    not knowable before the facets exist, and the facets cannot be built
    before the gate has answered -- `sorted_facets` gives a facet a plane, and
    splits a concave patch into its triangles, only when the answer is yes. The
    obvious way out is to count pairs among the raw drawable *triangles*, which
    needs nothing but the projected points, and it does not survive contact:
    that count is 2.9 times too high on the torus, where merging has not
    happened yet, and 2.9 times too low on the kinase, where banding has not
    happened yet. A gate that wrong is not a gate.

    **The two numbers, then.** `AUTO_EXACT_FACETS` is a cheap bound that keeps
    the obviously hopeless out without measuring anything, and
    `AUTO_EXACT_PAIRS` is the real budget, read at the one moment when the
    cost is known and unpaid: `order._candidates` has run, the grid has offered
    its pairs, and nothing per-pair has been spent yet. Over budget, the run
    hands back the depth order. Counting is a few percent of a sort and the
    only thing wasted when the answer is no.

    That is what let the face ceiling go from 8,000 to **22,000**. Under the
    old single gate the number had to be safe for the worst mesh in the
    repository, so every well-behaved one was refused at the same line: a
    subdivision-5 sphere at 20,480 faces sorts exactly in 56 ms and was turned
    away for being nine times an object that takes 400 ms. Now the pair budget
    catches the pathological case whatever its face count, and the face
    ceiling only has to be somewhere sane. 22,000 is the worst measured
    pairs-per-face spent in full -- 400,000 / 17.7 = 22,600 -- so a mesh as
    self-overlapping as the bunny reaches the budget and the ceiling at about
    the same moment, and the valve is a backstop rather than routine.

    **400,000 pairs** is half a second at the 1.2 us the triangle meshes hold
    to across a factor of 36 in size. Half a second is where a fit loop -- a
    panel that rebuilds its scene four or five times to settle a width --
    starts to be felt, which is the same line the 8,000 was drawn on. Two
    honest caveats. The rate is per *pair*, not per corner, and a facet with
    many corners falls out of the array path into the scalar one: a 256-segment
    cylinder asks only 123 pairs and spends 62 ms on them, because its caps are
    256-gons. And a mesh that passed both gates while being all many-cornered
    facets would cost about 1.2 s rather than 0.5. Neither is in the corpus,
    both are soft failures -- a slow figure, not a wrong one -- and both are
    visible in the profile the moment they appear.

    Below the ceiling the mean-depth order is measurably wrong on real anatomy
    and not by a rounding: on the midsagittal section of the Allen brain it
    gets 51 of 1,524 overlapping pairs backwards at 1,580 faces and 92 of 7,632
    at 8,816, and one such pair is a nucleus painted out by the cap in front of
    it. On the closed whole brain it is 0.2 percent, which is small and still
    not zero. Out past the ceiling the approximation stops mattering as much as
    the clock: on the kinase it was measured right to seven sample points in
    twenty-four thousand.

    The face half of the gate reads the mesh's own face count rather than the
    drawable one, so it does not change when the camera turns. The pair half
    necessarily does -- it is a measurement of this projection -- which is the
    price of it being a measurement at all, and is why an explicit
    `sort="exact"` is never subject to it.
    """
    if sort == "auto":
        return len(mesh.faces) <= AUTO_EXACT_FACETS
    return sort == "exact"


def _light_in_world(view: View, light: Vec3) -> Vec3:
    """Turn the view-space light into a world direction the normals can meet."""
    return (view.right * light.x + view.up * light.y
            - view.forward * light.z).normalized()


def facet_tone(normal: Vec3, light: Vec3, levels: int,
               shadow: float = 0.0) -> float:
    """Half-Lambert, quantised.

    Plain Lambert clamps everything past 90 degrees to zero, so the whole
    shadowed side of a cylinder becomes one flat black region and the form
    disappears. Wrapping the cosine into 0..1 instead keeps the turn readable
    all the way round, which is what a technical illustrator draws and not what
    a physically-based renderer computes.

    `shadow` is taken off before the rounding, so a facet in a hollow lands on
    a darker step of the same ramp and shares its fill with everything else on
    that step. See `occlude`.
    """
    lambert = 0.5 * (1.0 + normal.dot(light)) - shadow
    step = max(1, levels - 1)
    return round(min(max(lambert, 0.0), 1.0) * step) / step


def vertex_tones(mesh: Mesh, light: Vec3,
                 shadow: tuple[float, ...] | None = None) -> tuple[float, ...]:
    """The same half-Lambert as `facet_tone`, on the vertex normals, unrounded.

    Unrounded because this is a field to be contoured rather than a colour to
    be used: `_bands` cuts it at the quantiser's own step boundaries, so the
    rounding happens to the *region* instead of to the sample.

    `shadow` is how much each vertex is already taken off for being in a
    hollow. It goes in here rather than into a pass of its own because
    occlusion moves a surface along the same ramp the light does -- so the
    quantiser sees one number, the fills stay countable, and under
    `smooth_degrees` the bands contour the sum of the two for nothing.
    """
    if shadow is None:
        return tuple(min(max(0.5 * (1.0 + normal.dot(light)), 0.0), 1.0)
                     for normal in mesh.vertex_normals)
    return tuple(min(max(0.5 * (1.0 + normal.dot(light)) - dark, 0.0), 1.0)
                 for normal, dark in zip(mesh.vertex_normals, shadow))


#: A polygon this much of a quantiser step across contributes nothing but
#: coordinates. Slivers along a band boundary are the common case -- a triangle
#: whose corner grazes the next step -- and dropping them costs nothing,
#: because the neighbouring band is painted right up to the same edge.
_SLIVER = 1e-9


def _bands(face, tones, points, depths, step: int, cut) -> list:
    """One triangle cut into the bands of constant quantised tone across it.

    The tone field is linear over a triangle, so a band -- the strip where the
    field lies within one quantiser step -- meets it in a convex polygon, and
    the boundary between two bands is a straight chord. That is the whole
    reason this is exact rather than a subdivision: no curve is being
    approximated, the isolines really are the segments drawn.

    The trick that keeps it short is to subdivide the triangle's boundary
    *once*, at every step boundary any of its three edges crosses, before
    cutting anything. After that a band's polygon needs no clipping at all: it
    is the subdivided boundary filtered to the points inside the band, taken in
    cyclic order. The two chords close themselves, because the points either
    side of an omitted stretch both sit exactly on the same isoline, and a
    convex region can leave a triangle's boundary at most twice.

    Every point on a mesh edge is keyed on that edge and the step boundary it
    sits at, so the triangle on the other side of that edge computes the same
    index for the same point. Shared edges therefore still cancel in
    `dissolve`, and the whole file-size argument for merging survives being
    given curved band boundaries.

    Interpolation is in *page* coordinates, not in space. The difference is one
    facet's worth of foreshortening -- nothing at the scale a facet is drawn --
    and it buys the guarantee that matters here: the bands of a triangle tile
    exactly the triangle, so a painter's-algorithm fill can never show a gap
    where a band boundary should be.
    """
    # `cut` is memoised on the canonical edge, so the two triangles either side
    # of one get the identical corner rather than two roundings of it. Reading
    # the edge in traversal order instead would be right to the last ulp and
    # wrong in the last bit, and a band boundary that disagrees with itself by
    # a bit is a boundary `dissolve` cannot cancel.
    a, b, c = face
    ring = []
    for u, v in ((a, b), (b, c), (c, a)):
        one, two = tones[u] * step, tones[v] * step
        ring.append((u, points[u], depths[u], one))
        low, high = (one, two) if one < two else (two, one)
        # Every half-integer strictly between the ends: those are the step
        # boundaries, band k running from k - 0.5 to k + 0.5.
        first = math.floor(low + 0.5) + 1
        last = math.ceil(high + 0.5) - 1
        cuts = range(first, last + 1) if one < two else range(last, first - 1, -1)
        key = (u, v) if u < v else (v, u)
        for level in cuts:
            ring.append(cut(key, level))

    # The range is read off the corners, not off the subdivided ring: a
    # crossing sits exactly on a boundary and belongs to the bands either side
    # of it, so it would name one band too many at each end.
    scaled = [tones[a] * step, tones[b] * step, tones[c] * step]
    lowest = math.floor(min(scaled) + 0.5)
    highest = math.floor(max(scaled) + 0.5)
    if lowest == highest:
        return [(lowest / step, ring)]      # one band: no cutting to do
    out = []
    for level in range(lowest, highest + 1):
        low, high = level - 0.5 - _SLIVER, level + 0.5 + _SLIVER
        inside = [corner for corner in ring if low <= corner[3] <= high]
        if len(inside) >= 3:
            out.append((level / step, inside))
    return out


def _by_smoothness(mesh: Mesh, drawable: list[int], degrees: float | None
                   ) -> tuple[list[int], list[int]]:
    """Split the drawable faces into the band-shaded ones and the flat ones.

    A triangle qualifies only if none of its three corners is on a fold, which
    is the same gate the smooth outline uses -- see `Mesh.rough_vertices`. The
    consequence worth knowing about is that a crease leaves a one-triangle
    ribbon of flat shading either side of it. That is not a defect to be
    feathered away: a hard edge is exactly where the tone is meant to jump, and
    the flat pair either side of it is the jump.
    """
    if degrees is None:
        return [], drawable
    rough = mesh.rough_vertices(degrees)
    if not rough:
        return drawable, []
    smooth: list[int] = []
    flat: list[int] = []
    for index in drawable:
        a, b, c = mesh.faces[index]
        target = flat if a in rough or b in rough or c in rough else smooth
        target.append(index)
    return smooth, flat


def _banded_facets(mesh: Mesh, points: list[Vec2], depths: list[float],
                   faces: list[int], light: Vec3, levels: int, near: float,
                   span: float, depth_cue: float, exact: bool = False,
                   shadow: tuple[float, ...] | None = None) -> list[Facet]:
    """Every smooth triangle as its bands of constant tone.

    The new points get indices past the end of whatever table the caller
    passed, and the same index whenever two triangles ask for the same crossing
    of the same mesh edge -- which is what keeps `dissolve` working on integers
    and keeps the bands of one tone collapsing into one path.
    """
    tones = vertex_tones(mesh, light, shadow)
    step = max(1, levels - 1)
    steps = step
    made: dict[tuple[tuple[int, int], int], tuple] = {}
    nowhere = len(points)

    def cut(edge: tuple[int, int], level: int) -> tuple:
        found = made.get((edge, level))
        if found is None:
            lo, hi = edge
            at = level - 0.5
            here, there = tones[lo] * step, tones[hi] * step
            share = (at - here) / (there - here)
            found = (nowhere + len(made),
                     points[lo] + (points[hi] - points[lo]) * share,
                     depths[lo] + (depths[hi] - depths[lo]) * share, at)
            made[(edge, level)] = found
        return found

    normals = mesh.face_normals
    out: list[Facet] = []
    for index in faces:
        face = mesh.faces[index]
        group = mesh.groups[index] if mesh.groups else ""
        # Every band of a triangle lies in that triangle's own plane -- the
        # bands cut the *tone* across it, not the geometry -- so one plane
        # serves them all.
        plane = _plane_of(mesh, index, normals[index]) if exact else None
        for tone, ring in _bands(face, tones, points, depths, step, cut):
            outline = tuple(corner[1] for corner in ring)
            depth = sum(corner[2] for corner in ring) / len(ring)
            cue = 0.0
            if span > 1e-9:
                cue = round((depth - near) / span * depth_cue * steps) / steps
            out.append(Facet(outline, depth, tone, group, cue,
                             tuple(corner[0] for corner in ring), plane))
    return out


def sorted_facets(mesh: Mesh, view: View, points: list[Vec2],
                  depths: list[float], facing: tuple[bool, ...], *,
                  cull: bool | None = None, light: Vec3 = DEFAULT_LIGHT,
                  levels: int = DEFAULT_LEVELS, depth_cue: float = 0.0,
                  smooth_degrees: float | None = None,
                  sort: str = "auto", occlusion: float = 0.0) -> list[Facet]:
    """Every drawable facet, furthest first, ready to paint in order.

    `sort="depth"` keys on the mean depth of a facet's own vertices. For a
    convex solid the order is irrelevant, because front-facing facets do not
    overlap. For a concave one it is the standard painter's approximation, and
    it fails in the standard way: two long facets that interpenetrate in
    depth, or a horseshoe curling over itself, will pick one order for the
    whole polygon where the truth changes across it.

    `sort="exact"` asks the overlapping pairs instead of guessing from a key,
    and cuts the pairs that have no answer. It is right where the mean depth is
    wrong, and it costs about a second per ten thousand facets; `order` has the
    argument for both. It also drops the coplanar merge, since the pairwise
    test needs convex polygons and a merged patch need not be one -- `dissolve`
    puts the merge back at the end of the pipeline anyway, by cancelling the
    interior edges of whatever ends up in one path, so what is lost is the
    early saving and not the result.

    `sort="auto"`, the default, is exact up to `AUTO_EXACT_FACETS` faces and
    mean depth above -- see `sorts_exactly`. The threshold is there because
    the exact order costs a fixed multiple of the render rather than a fixed
    fee, so on the meshes a *drawn* object is made of it is a few
    milliseconds, and on a scanned surface it is seconds.

    `depth_cue` fades the far end of the scene toward paper. Shading alone
    tells you which way a surface faces, not which of two surfaces is nearer,
    and on a body that folds back over itself -- a protein, a knot, a coil --
    that is the whole question. Every molecular viewer has this, usually called
    fog or depth cue, for exactly that reason. 0 is off; around 0.3 is enough
    to separate front from back without washing the back out.

    `smooth_degrees` shades the smooth part of the mesh as the surface it
    stands for. The quantiser stays -- a continuous ramp still prints as mud --
    but the *bands* are cut on the vertex-normal field instead of being handed
    out one per facet, so a band boundary is the isoline it should be rather
    than the staircase of whichever triangles happened to tip across the step.
    See `DEFAULT_LEVELS` for why that staircase is the thing worth removing.
    `None` is off and gives flat facets everywhere. Anything else is a dihedral
    angle: a triangle with a corner on a fold sharper than that is left flat,
    the same gate and the same answer `edges.smooth_silhouette` uses, so the
    outline and the shading agree about where the surface is smooth. On a mesh
    with no smooth region -- a box, a polyhedron -- this changes nothing at
    all, down to the byte.

    `occlusion` darkens the parts of the surface that are in a hollow, by that
    fraction of the ramp at full enclosure. It is what makes a pocket read as a
    pocket: a light says which way a surface faces and nothing about whether it
    is inside something. See `occlude` for how it is measured. It costs a
    rasterisation and a dozen samples per vertex, and it costs *no fills*,
    because it is taken off the tone before the quantiser rather than applied
    after it. 0 is off; a third is a strong effect.
    """
    if cull is None:
        cull = mesh.is_closed
    drawable = [i for i, front in enumerate(facing) if front] if cull \
        else list(range(len(mesh.faces)))
    if not drawable:
        return []

    world_light = _light_in_world(view, light)
    normals = mesh.face_normals
    shadow = None
    if occlusion > 0.0:
        found = vertex_occlusion(mesh, view, points, depths, drawable)
        shadow = tuple(value * occlusion for value in found)
    banded, flat = _by_smoothness(mesh, drawable, smooth_degrees)
    # `View.project` takes depth along `forward`, so depth grows *away* from
    # the camera and the smallest depth is the nearest point -- the same
    # convention hidden-line removal reads. Quantised to the same number of
    # steps as the tone, so cueing adds bands of colour rather than a distinct
    # path per facet.
    near = min(depths) if depth_cue > 0.0 and depths else 0.0
    far = max(depths) if depth_cue > 0.0 and depths else 0.0
    span = far - near
    steps = max(1, levels - 1)
    exact = sorts_exactly(mesh, sort)
    facets: list[Facet] = []
    riders: dict[int, list[Facet]] = {}
    for number, patch in enumerate(mesh.coplanar_patches(flat)):
        normal = normals[patch[0]]
        if normal == Vec3():
            continue                       # degenerate: no normal, no shading
        tone = facet_tone(normal, world_light, levels,
                          _patch_shadow(mesh, patch, shadow))
        group = mesh.groups[patch[0]] if mesh.groups else ""
        plane = _plane_of(mesh, patch[0], normal) if exact else None
        rings = _patch_rings(mesh, patch)
        split = exact and not _all_convex(rings, points)
        if split:
            # The pairwise test clips one outline against the other, and that
            # is only the intersection when both are convex. A patch that came
            # out concave -- an L -- goes back to its own triangles, which are
            # convex by construction. It costs paths in this function and
            # nothing in the file that comes out, since `dissolve` merges
            # whatever lands in one path anyway.
            #
            # What comes back is a *tiling*, not an outline and its holes: the
            # triangles are siblings covering between them exactly what the
            # rings covered, holes included, because a hole is simply where
            # the triangulation put nothing. So none of the rider machinery
            # below applies to them. Every triangle is a facet of its own,
            # with a depth of its own, and every one goes to the sort --
            # riding them on the widest instead took a 215-triangle
            # midsagittal cap out of the exact pass entirely and painted the
            # lot at one depth, over a nucleus standing a millimetre proud of
            # it.
            rings = [mesh.faces[face] for face in patch]
        # One depth for the whole patch, not one per ring. A flat face with a
        # hole in it comes out of `_patch_rings` as an outer ring and an inner
        # one, and they are only a hole when they are painted as *one path*:
        # an inner ring on its own fills, whatever way it is wound. Ranking
        # them separately puts the bore's own facets between them, which
        # closes the run and paints the hole in as a disc of the face's own
        # colour -- which is what a drilled plate did before this line.
        # Coplanar rings have no order between them anyway, so nothing is lost
        # by giving them one, and the same key plus a stable sort keeps them
        # adjacent and so in one run. The face's depth is its *outer* ring's:
        # the holes are absences, and they should not drag the face forward.
        # A split patch is the exception: its triangles are not one face, so
        # each keys on its own corners.
        face_depth = None if split else _outer_depth(rings, points, depths)
        # Under the exact sort one depth is not enough to keep a hole with its
        # face. `painter_sort` is free to give any two facets whatever order
        # the geometry allows, and an inner ring *is* a facet to it: a disc
        # lying exactly on the face, which the bore's own wall is legitimately
        # behind -- so the wall goes between the two, the run closes, and the
        # hole fills in with the face's colour. The inner rings therefore do
        # not go to the sort at all. They ride with whichever piece of their
        # outer ring comes back containing them (`_punched`), which is also
        # the right answer for overlap: the outer ring covers the hole, so
        # everything under the hole is already ranked against the face.
        holed = exact and not split and len(rings) > 1
        widest = _widest(rings, points) if holed else 0
        for which, ring in enumerate(rings):
            depth = (sum(depths[i] for i in ring) / len(ring)
                     if face_depth is None else face_depth)
            cue = 0.0
            if span > 1e-9:
                cue = round((depth - near) / span * depth_cue * steps) / steps
            outline = tuple(points[i] for i in ring)
            made = Facet(outline, depth, tone, group, cue, ring, plane,
                         number if holed else -1)
            if holed and which != widest:
                riders.setdefault(number, []).append(made)
            else:
                facets.append(made)

    if banded:
        facets.extend(_banded_facets(mesh, points, depths, banded, world_light,
                                     levels, near, span, depth_cue, exact,
                                     shadow))
    # Furthest first. The face index breaks ties so that two facets at exactly
    # the same depth -- the two halves of a symmetric part -- keep a fixed
    # order rather than one that depends on the sort's implementation.
    facets.sort(key=lambda f: (-f.depth, f.points[0].x, f.points[0].y))
    if not exact:
        return facets
    # Past every index in use, the banded crossings included: cutting invents
    # corners, and one that reused a band boundary's name would cancel against
    # it in `dissolve` and open the outline.
    fresh = max((max(f.ring) for f in facets if f.ring),
                default=len(points) - 1) + 1
    # An explicit `sort="exact"` is answered whatever it costs; `"auto"`
    # is capped, and `painter_sort` reads the cap where the cost is known.
    ordered = painter_sort(facets, view, fresh,
                           AUTO_EXACT_PAIRS if sort == "auto" else None)
    return _punched(ordered, riders) if riders else ordered


def _punched(ordered: list[Facet], riders: dict[int, list[Facet]]) -> list[Facet]:
    """Put each patch's holes back beside the piece of its face that holds them.

    The sort has just been run without the inner rings, so each one has to
    rejoin its face -- immediately after it, because "immediately after" is
    what `_gather_runs` needs to keep the two in one path and so what
    `dissolve` needs to make the second a hole in the first rather than a disc
    on top of it.

    Which piece: a face crossed by something is cut, so it can come back as
    several, and a hole belongs to the one it lies in. The containment test
    is a point in a polygon, which is honest for a hole entirely inside one
    piece and is the only case cutting produces -- the cut line comes from
    another facet's plane, and `order._cut` splits whichever of the pair is
    smaller, which across the whole corpus is never the drilled face.
    """
    homes: dict[int, list[int]] = {}
    for index, facet in enumerate(ordered):
        if facet.patch >= 0 and facet.patch in riders:
            homes.setdefault(facet.patch, []).append(index)
    after: dict[int, list[Facet]] = {}
    for number, holes in riders.items():
        places = homes.get(number)
        if not places:
            continue                # the whole face was culled: no hole to cut
        for hole in holes:
            home = places[-1]
            if len(places) > 1:
                inside = [i for i in places
                          if _encloses(ordered[i].points, hole.points[0])]
                home = inside[-1] if inside else places[-1]
            after.setdefault(home, []).append(hole)
    out: list[Facet] = []
    for index, facet in enumerate(ordered):
        out.append(facet)
        out.extend(after.get(index, ()))
    return out


def _encloses(outline: tuple[Vec2, ...], point: Vec2) -> bool:
    """Crossing count: is the page point inside this outline?"""
    inside = False
    count = len(outline)
    for i in range(count):
        a, b = outline[i], outline[i - 1]
        if (a.y > point.y) != (b.y > point.y):
            span = b.y - a.y
            if span and point.x < a.x + (point.y - a.y) / span * (b.x - a.x):
                inside = not inside
    return inside


def _widest(rings, points) -> int:
    """Which of a patch's rings is its outer one: the widest on the page."""
    return max(range(len(rings)),
               key=lambda i: abs(_page_area(rings[i], points)))


def _outer_depth(rings, points, depths) -> float:
    """The mean depth of the widest of a patch's rings.

    Widest by page area rather than by vertex count: a bore drilled with
    twenty sides has more corners than the square it is cut into.
    """
    ring = rings[0] if len(rings) == 1 else rings[_widest(rings, points)]
    return sum(depths[i] for i in ring) / len(ring)


def _page_area(ring, points) -> float:
    """Twice the signed area the ring encloses on the page."""
    total = 0.0
    for index in range(len(ring)):
        a, b = points[ring[index]], points[ring[index - 1]]
        total += b.x * a.y - a.x * b.y
    return total


def _patch_shadow(mesh: Mesh, patch: tuple[int, ...], shadow) -> float:
    """One occlusion figure for a flat patch: the mean over its vertices.

    A flat facet gets one tone, so it gets one shadow, and the honest one is
    the average over the corners it is drawn from -- which is as fine as the
    mesh is, and no finer. A curved surface subdivided enough to look curved
    has small facets and this is nearly per-vertex; a large flat face gets one
    number for the whole of it, which is what "flat" already meant.
    """
    if shadow is None:
        return 0.0
    total = count = 0
    for face in patch:
        for index in mesh.faces[face]:
            total += shadow[index]
            count += 1
    return total / count if count else 0.0


def _plane_of(mesh: Mesh, face: int, normal: Vec3) -> tuple[Vec3, float]:
    """The face's plane as `(normal, offset)`, in world coordinates."""
    return (normal, normal.dot(mesh.vertices[mesh.faces[face][0]]))


def _all_convex(rings: list[tuple[int, ...]], points: list[Vec2]) -> bool:
    """Is every one of these rings convex on the page?

    Each ring becomes a facet of its own, and the pairwise depth test clips one
    against another, so convexity is asked of them one at a time rather than of
    the patch as a whole. A drilled plate is the case that makes the difference:
    outline square, holes round, all five convex, and the patch stays one facet
    per ring instead of collapsing into the eighty triangles its
    re-triangulation happens to have -- eighty outlines that no longer merge
    into one path, and so eighty hairline seams across a face that should be
    flat. Two rings of one patch are coplanar, so the depth test finds no
    difference between them and their order among themselves does not matter.

    A ring is convex when every corner turns the same way; a straight run counts
    as either, so a merged patch whose seam left a corner at exactly 180
    degrees still passes.
    """
    return all(_convex(ring, points) for ring in rings)


def _convex(ring: tuple[int, ...], points: list[Vec2]) -> bool:
    n = len(ring)
    if n < 3:
        return False
    sign = 0
    for i in range(n):
        a, b, c = (points[ring[(i + k) % n]] for k in range(3))
        turn = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x)
        if turn > 1e-12:
            if sign < 0:
                return False
            sign = 1
        elif turn < -1e-12:
            if sign > 0:
                return False
            sign = -1
    return True


def _patch_rings(mesh: Mesh, patch: tuple[int, ...]) -> list[tuple[int, ...]]:
    """The outline of a set of coplanar faces, wound the way the faces are.

    A ring per boundary, so a flat face with a hole in it yields two. Both are
    emitted as subpaths of one path, and the winding is what makes the hole a
    hole: an interior boundary comes out turning the opposite way to the
    outside, which is exactly what a nonzero fill rule needs. Deriving it from
    *directed* edges rather than counting undirected ones is the whole of the
    difference, and it costs nothing.
    """
    if len(patch) == 1:
        return [mesh.faces[patch[0]]]      # by far the commonest, and free
    return dissolve(tuple(mesh.faces[face] for face in patch))


def dissolve(loops: Sequence[Sequence[int]]) -> list[tuple[int, ...]]:
    """The boundary of a set of wound loops, as closed rings.

    Every loop contributes its directed edges; an edge that appears in both
    directions is interior to the set and cancels. What is left is threaded
    into rings by following the direction, so the result keeps the winding of
    the input and separates an outer boundary from a hole by the sign of its
    turn.

    This is how two facets that came out the same colour stop drawing the edge
    between them. The saving is coordinates, not paths: `_tone_runs` in the
    builtin backend already gathers same-fill facets into one path, but it
    kept each facet's own outline as a subpath, so the shared edge was written
    down twice and painted twice. On a shaded protein about a fifth of the
    interior edges have the same fill on both sides, and every one of them was
    two page coordinates that drew nothing.

    Cancelling is exact rather than geometric: two faces of one mesh share
    *vertex indices*, so the shared edge projects to the same two page points
    for both, whatever the camera. Nothing here compares coordinates, and
    there is no tolerance to get wrong.
    """
    counts: dict[tuple[int, int], int] = {}
    for loop in loops:
        for index, a in enumerate(loop):
            b = loop[(index + 1) % len(loop)]
            if a != b:
                counts[(a, b)] = counts.get((a, b), 0) + 1
    outgoing: dict[int, list[int]] = {}
    total = 0
    for (a, b), count in sorted(counts.items()):
        surplus = count - counts.get((b, a), 0)
        if surplus > 0:
            outgoing.setdefault(a, []).extend([b] * surplus)
            total += surplus

    rings: list[tuple[int, ...]] = []
    for first in sorted(outgoing):
        # A vertex where several boundaries pinch together starts more than
        # one ring, so the same vertex is revisited until its edges run out.
        while outgoing.get(first):
            ring = [first]
            at = first
            for _ in range(total):
                nxt = _step(outgoing, at)
                if nxt is None:
                    ring = []                  # a chain that does not close
                    break
                if nxt == first:
                    break
                ring.append(nxt)
                at = nxt
            else:
                ring = []                      # ran out of budget: drop it
            if len(ring) >= 3:
                rings.append(tuple(ring))
    return rings


def _step(outgoing: dict[int, list[int]], at: int) -> int | None:
    """Take one boundary edge out of `at`, smallest first, and consume it."""
    ahead = outgoing.get(at)
    if not ahead:
        return None
    nxt = ahead.pop(0)
    if not ahead:
        del outgoing[at]
    return nxt


def tint(tone: float, base: str, paper: str, ink: str, *,
         lift: float = DEFAULT_LIFT, shade: float = DEFAULT_SHADE) -> str:
    """Map a tone onto the theme, staying on-palette.

    The ramp runs from the base colour heavily lifted toward paper to the base
    colour pushed a little toward ink -- not from white to black. That keeps
    every facet recognisably the same hue, which is what makes a shaded object
    read as one object, and it keeps the darkest facet above the point where a
    printer's ink coverage turns it into a blob.
    """
    pale = mix(base, paper, lift)
    deep = mix(base, ink, shade)
    return mix(deep, pale, tone)
