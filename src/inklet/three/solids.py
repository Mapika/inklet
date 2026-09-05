"""Parametric solids, so the common case needs no asset file at all.

`inklet.solid("cube", width=20)` should work on a fresh checkout with nothing
downloaded, and most 3D in a paper figure is a box, a cylinder, a sphere or an
arrow. Everything here is built to the same conventions:

* **Centred on the origin**, matching `core.prims`. A solid drops into a stack
  without an anchor-correction step.
* **Z is up, right-handed**, matching `camera.py`. A cylinder stands on its end.
* **Roughly one unit across.** The renderer auto-fits to the requested
  millimetres, so absolute size is arbitrary -- but keeping everything near
  unit scale means the default camera distances and the depth tolerances are
  tuned once and hold for all of them.
* **Counter-clockwise seen from outside**, so face normals point out of the
  solid. Every winding below is checked in the tests by asserting the normal at
  a known face, because a reversed winding is invisible until the silhouette
  comes out inside-out.

Segment counts default to what looks right at 20-40 mm on paper and are all
overridable. Higher is not better: a 128-segment cylinder at 20 mm wide has
facets a fifth of a millimetre across, which no printer will resolve and which
quadruples the time hidden-line removal takes.
"""

from __future__ import annotations

import inspect
import math
from typing import Callable, Sequence

from .linalg import Mat4, Vec3
from .mesh import Mesh, MeshError, merge

__all__ = ["build", "solid_names", "SOLIDS", "cube", "box", "sphere", "cylinder",
           "cone", "torus", "tube", "plane", "arrow", "axes", "sweep",
           "segments_for", "subdivisions_for", "tessellation"]


def _quad(faces: list, a: int, b: int, c: int, d: int) -> None:
    """Split a quad along a-c. Both triangles keep the quad's own winding, and
    all four rim edges survive as mesh edges -- which is what lets a box have
    exactly six silhouette edges from a corner rather than a diagonal's worth
    more."""
    faces.append((a, b, c))
    faces.append((a, c, d))


def _ring(radius: float, z: float, segments: int) -> list[Vec3]:
    """A circle in the xy plane, counter-clockwise seen from +z."""
    return [Vec3(radius * math.cos(2.0 * math.pi * i / segments),
                 radius * math.sin(2.0 * math.pi * i / segments), z)
            for i in range(segments)]


def _check_segments(value: int, floor: int, what: str) -> int:
    if value < floor:
        raise MeshError(f"{what} needs at least {floor} segments, got {value}")
    return value


# -- boxes ----------------------------------------------------------------


def box(size_x: float = 1.0, size_y: float = 1.0, size_z: float = 1.0) -> Mesh:
    """A rectangular solid, centred, with its faces axis-aligned."""
    if min(size_x, size_y, size_z) <= 0.0:
        raise MeshError(f"a box needs positive sides, got "
                        f"{size_x} x {size_y} x {size_z}")
    hx, hy, hz = size_x / 2.0, size_y / 2.0, size_z / 2.0
    vertices = [
        Vec3(-hx, -hy, -hz), Vec3(hx, -hy, -hz), Vec3(hx, hy, -hz), Vec3(-hx, hy, -hz),
        Vec3(-hx, -hy, hz), Vec3(hx, -hy, hz), Vec3(hx, hy, hz), Vec3(-hx, hy, hz),
    ]
    faces: list[tuple[int, int, int]] = []
    _quad(faces, 0, 3, 2, 1)      # -z
    _quad(faces, 4, 5, 6, 7)      # +z
    _quad(faces, 0, 1, 5, 4)      # -y
    _quad(faces, 2, 3, 7, 6)      # +y
    _quad(faces, 1, 2, 6, 5)      # +x
    _quad(faces, 3, 0, 4, 7)      # -x
    return Mesh(tuple(vertices), tuple(faces), name="box")


def cube(size: float = 1.0) -> Mesh:
    return _named(box(size, size, size), "cube")


def _named(mesh: Mesh, name: str) -> Mesh:
    return Mesh(mesh.vertices, mesh.faces, mesh.groups, name)


# -- spheres --------------------------------------------------------------

# The icosahedron, in the standard (0, +-1, +-phi) form. Winding is
# counter-clockwise from outside for every face in this list; the test suite
# pins that down by checking one face's normal against its own centroid.
_PHI = (1.0 + math.sqrt(5.0)) / 2.0
_ICO_VERTICES = (
    (-1.0, _PHI, 0.0), (1.0, _PHI, 0.0), (-1.0, -_PHI, 0.0), (1.0, -_PHI, 0.0),
    (0.0, -1.0, _PHI), (0.0, 1.0, _PHI), (0.0, -1.0, -_PHI), (0.0, 1.0, -_PHI),
    (_PHI, 0.0, -1.0), (_PHI, 0.0, 1.0), (-_PHI, 0.0, -1.0), (-_PHI, 0.0, 1.0),
)
_ICO_FACES = (
    (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
    (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
    (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
    (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
)


def sphere(radius: float = 0.5, subdivisions: int = 3) -> Mesh:
    """An icosphere: an icosahedron subdivided and pushed onto the sphere.

    Chosen over a UV sphere because its facets are near-uniform. A UV sphere
    crowds hundreds of slivers at each pole, and every one of them is a
    candidate occluder that hidden-line removal has to test and then discard.

    Level 3 (1280 faces) is the default. Level 2 is four times faster and its
    facets meet at only about 20 degrees, so the default crease threshold keeps
    its interior just as quiet -- but its *silhouette* is a visible 20-gon at
    24 mm on paper, and the outline is the one thing a reader looks at. Level 0
    or 1 deliberately shows its facets, which is a legitimate look for a
    schematic.
    """
    if radius <= 0.0:
        raise MeshError(f"a sphere needs a positive radius, got {radius}")
    if not 0 <= subdivisions <= 6:
        raise MeshError(
            f"subdivisions must be 0..6, got {subdivisions}; level 6 is already "
            "81920 faces and nothing at figure scale needs more"
        )
    vertices = [Vec3(*v) for v in _ICO_VERTICES]
    faces = list(_ICO_FACES)
    midpoints: dict[tuple[int, int], int] = {}

    def middle(a: int, b: int) -> int:
        key = (a, b) if a < b else (b, a)
        found = midpoints.get(key)
        if found is None:
            found = midpoints[key] = len(vertices)
            vertices.append((vertices[a] + vertices[b]) * 0.5)
        return found

    for _ in range(subdivisions):
        split: list[tuple[int, int, int]] = []
        for a, b, c in faces:
            ab, bc, ca = middle(a, b), middle(b, c), middle(c, a)
            split += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = split
    onto = tuple(v.normalized() * radius for v in vertices)
    return Mesh(onto, tuple(faces), name="sphere")


# -- surfaces of revolution -----------------------------------------------


def cylinder(radius: float = 0.4, height: float = 1.0, segments: int = 32,
             caps: bool = True) -> Mesh:
    """A capped tube standing on the z axis."""
    if radius <= 0.0 or height <= 0.0:
        raise MeshError(f"a cylinder needs positive radius and height, "
                        f"got {radius} and {height}")
    segments = _check_segments(segments, 3, "a cylinder")
    bottom = _ring(radius, -height / 2.0, segments)
    top = _ring(radius, height / 2.0, segments)
    vertices = bottom + top
    faces: list[tuple[int, int, int]] = []
    for i in range(segments):
        j = (i + 1) % segments
        _quad(faces, i, j, segments + j, segments + i)
    if caps:
        low = len(vertices)
        vertices.append(Vec3(0.0, 0.0, -height / 2.0))
        high = len(vertices)
        vertices.append(Vec3(0.0, 0.0, height / 2.0))
        for i in range(segments):
            j = (i + 1) % segments
            faces.append((low, j, i))                          # -z, wound back
            faces.append((high, segments + i, segments + j))   # +z
    return Mesh(tuple(vertices), tuple(faces), name="cylinder")


def tube(radius: float = 0.4, bore: float = 0.24, height: float = 1.0,
         segments: int = 32, caps: bool = True) -> Mesh:
    """A pipe standing on the z axis: a cylinder with an axial hole.

    `Mesh.drill` would cut the same shape out of a `cylinder`, and this is here
    because the answer it gives is better in the two ways that show on the
    page. The bore gets its own `segments`, so the hole is as round as the
    outside instead of as round as `DEFAULT_HOLE_SEGMENTS` happens to be, and
    the end faces come out as two annular rings rather than as the fan of
    triangles a re-triangulated cap leaves behind. Watertight by construction
    when `caps` is on.

    `bore` is the inner radius, and has to be under `radius`; `caps` off leaves
    the two barrels open at both ends, which is what a section drawing wants.
    """
    if radius <= 0.0 or height <= 0.0:
        raise MeshError(f"a tube needs positive radius and height, "
                        f"got {radius} and {height}")
    if not 0.0 < bore < radius:
        raise MeshError(f"a tube's bore has to be inside its wall: "
                        f"got bore {bore} in radius {radius}")
    segments = _check_segments(segments, 3, "a tube")
    n = segments
    vertices = (_ring(radius, -height / 2.0, n) + _ring(radius, height / 2.0, n)
                + _ring(bore, -height / 2.0, n) + _ring(bore, height / 2.0, n))
    faces: list[tuple[int, int, int]] = []
    for i in range(n):
        j = (i + 1) % n
        _quad(faces, i, j, n + j, n + i)                    # outside
        # The bore, wound the other way round, so its normals point into the
        # hole. A tube whose inner wall faces outward is a tube you can see
        # through from any angle that culls back faces.
        _quad(faces, 3 * n + i, 3 * n + j, 2 * n + j, 2 * n + i)
    if caps:
        for i in range(n):
            j = (i + 1) % n
            _quad(faces, 2 * n + i, 2 * n + j, j, i)        # -z annulus
            _quad(faces, n + i, n + j, 3 * n + j, 3 * n + i)  # +z annulus
    return Mesh(tuple(vertices), tuple(faces), name="tube")


def cone(radius: float = 0.4, height: float = 1.0, segments: int = 32) -> Mesh:
    """A cone with its apex at +z and its base disc at -z."""
    if radius <= 0.0 or height <= 0.0:
        raise MeshError(f"a cone needs positive radius and height, "
                        f"got {radius} and {height}")
    segments = _check_segments(segments, 3, "a cone")
    base = _ring(radius, -height / 2.0, segments)
    vertices = base + [Vec3(0.0, 0.0, height / 2.0), Vec3(0.0, 0.0, -height / 2.0)]
    apex, centre = segments, segments + 1
    faces: list[tuple[int, int, int]] = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, apex))
        faces.append((centre, j, i))
    return Mesh(tuple(vertices), tuple(faces), name="cone")


def torus(radius: float = 0.4, tube: float = 0.14, segments: int = 40,
          rings: int = 14) -> Mesh:
    """A ring in the xy plane. `radius` is to the centre of the tube."""
    if radius <= 0.0 or tube <= 0.0:
        raise MeshError(f"a torus needs positive radius and tube, "
                        f"got {radius} and {tube}")
    if tube >= radius:
        raise MeshError(
            f"tube {tube} is not smaller than radius {radius}, so the ring "
            "closes through its own centre and the surface self-intersects"
        )
    segments = _check_segments(segments, 3, "a torus")
    rings = _check_segments(rings, 3, "a torus")
    vertices: list[Vec3] = []
    for i in range(segments):
        theta = 2.0 * math.pi * i / segments
        for j in range(rings):
            phi = 2.0 * math.pi * j / rings
            out = radius + tube * math.cos(phi)
            vertices.append(Vec3(out * math.cos(theta), out * math.sin(theta),
                                 tube * math.sin(phi)))
    faces: list[tuple[int, int, int]] = []
    for i in range(segments):
        ni = (i + 1) % segments
        for j in range(rings):
            nj = (j + 1) % rings
            _quad(faces, i * rings + j, ni * rings + j,
                  ni * rings + nj, i * rings + nj)
    return Mesh(tuple(vertices), tuple(faces), name="torus")


# -- open surfaces --------------------------------------------------------


def plane(width: float = 1.0, depth: float = 1.0, segments: int = 1) -> Mesh:
    """A flat sheet in the xy plane, facing +z.

    Open, so it has boundary edges and hidden-line removal cannot cull its back
    faces -- seen from below it is exactly as solid as from above, and pretending
    otherwise would make a ground plane vanish.
    """
    if width <= 0.0 or depth <= 0.0:
        raise MeshError(f"a plane needs positive sides, got {width} x {depth}")
    segments = _check_segments(segments, 1, "a plane")
    step_x, step_y = width / segments, depth / segments
    vertices = [Vec3(-width / 2.0 + i * step_x, -depth / 2.0 + j * step_y, 0.0)
                for j in range(segments + 1) for i in range(segments + 1)]
    stride = segments + 1
    faces: list[tuple[int, int, int]] = []
    for j in range(segments):
        for i in range(segments):
            base = j * stride + i
            _quad(faces, base, base + 1, base + stride + 1, base + stride)
    return Mesh(tuple(vertices), tuple(faces), name="plane")


# -- arrows and frames ----------------------------------------------------


def arrow(length: float = 1.0, shaft: float = 0.035, head: float = 0.22,
          head_radius: float = 0.09, segments: int = 20) -> Mesh:
    """A 3D arrow along +z, from the origin to `length`.

    Not centred, unlike everything else here, and deliberately: an arrow means
    something *from* a place *to* a place, so its tail sits on the origin where
    a coordinate frame or an exploded-view path can put it.

    The proportions default to a drawn arrow rather than a physical one -- a
    long thin shaft and a head about a fifth of the length -- because at 30 mm
    on paper a geometrically reasonable head disappears.
    """
    if length <= 0.0 or shaft <= 0.0 or head <= 0.0:
        raise MeshError("an arrow needs a positive length, shaft and head")
    if head >= length:
        raise MeshError(
            f"the head ({head}) is at least as long as the whole arrow "
            f"({length}); there is no shaft left to draw"
        )
    stem = cylinder(shaft, length - head, segments).transformed(
        Mat4.translation(Vec3(0.0, 0.0, (length - head) / 2.0)))
    tip = cone(head_radius, head, segments).transformed(
        Mat4.translation(Vec3(0.0, 0.0, length - head / 2.0)))
    return _named(stem.merged(tip), "arrow")


# Direction and label for each axis of the frame, in draw order. A tuple rather
# than a dict comprehension over "xyz" so the rotation that puts +z onto each
# axis is written down once and can be read.
_AXES = (
    ("x", Vec3(0.0, 1.0, 0.0), 90.0),     # +z turned about +y lands on +x
    ("y", Vec3(-1.0, 0.0, 0.0), 90.0),    # +z turned about -x lands on +y
    ("z", Vec3(0.0, 0.0, 1.0), 0.0),
)


def axes(length: float = 1.0, thickness: float = 1.0, segments: int = 20,
         hub: bool = True) -> Mesh:
    """A right-handed coordinate frame: three arrows and a hub at the origin.

    Faces are grouped `x`, `y`, `z` and `origin`, which is what lets the
    authoring layer hang a text label off each arrow's tip without the author
    working out where the tip landed on the page.
    """
    if length <= 0.0:
        raise MeshError(f"axes need a positive length, got {length}")
    parts = []
    for name, axis, degrees in _AXES:
        one = arrow(length, 0.03 * thickness * length, 0.20 * length,
                    0.072 * thickness * length, segments)
        if degrees:
            one = one.transformed(Mat4.rotation(axis, degrees))
        parts.append(one.grouped(name))
    if hub:
        parts.append(sphere(0.05 * thickness * length, 1).grouped("origin"))
    return _named(merge(parts), "axes")


# -- the registry ---------------------------------------------------------

SOLIDS: dict[str, Callable[..., Mesh]] = {
    "arrow": arrow,
    "axes": axes,
    "box": box,
    "cone": cone,
    "cube": cube,
    "cylinder": cylinder,
    "plane": plane,
    "sphere": sphere,
    "torus": torus,
    "tube": tube,
}


def solid_names() -> tuple[str, ...]:
    """Every name `build()` and `inklet.solid()` know, sorted.

    Sorted so that anything printing or iterating them -- an error message
    listing what was expected, a gallery figure -- stays deterministic.
    """
    return tuple(sorted(SOLIDS))


def build(kind: str, **options) -> Mesh:
    """Make a solid by name, passing the rest through to its builder."""
    maker = SOLIDS.get(kind.strip().lower())
    if maker is None:
        raise MeshError(
            f"unknown solid {kind!r}; known solids are {solid_names()}")
    try:
        return maker(**options)
    except TypeError as exc:
        raise MeshError(f"{kind}(): {exc}") from None


# -- how fine, for the page -----------------------------------------------

#: The default chord tolerance: how far a drawn outline may sit from the curve
#: it stands for, in millimetres **on the page**.
#:
#: 0.06 mm is two thirds of a pixel at 300 dpi and under half of one at 600,
#: and it is not invented -- it is the tolerance the hand-set defaults in this
#: module were already sitting at. A 32-segment cylinder of radius 0.4 drawn
#: 20 mm wide departs from a true circle by 0.06 mm, and a level-3 icosphere at
#: 24 mm by 0.05 mm. Choosing segment counts from the page therefore reproduces
#: the shipped defaults at the sizes they were chosen for, and only changes
#: what happens at the sizes nobody tuned them for.
DEFAULT_TOLERANCE = 0.06

#: Below an octagon a swept curve stops reading as one. Not because the chord
#: error is large -- on a 2 mm tube a hexagon is well within any tolerance --
#: but because `style="shaded"` gives every facet its own flat tone, so the
#: facet count *is* the tonal banding, and six tones around a tube reads as a
#: prism however small it is.
ROUND_FLOOR = 8

#: How far a level-k icosphere of radius 1 sits inside its own sphere, measured
#: rather than derived: the largest `1 - |centroid|` over its faces. Level 0 is
#: the icosahedron itself and each level after the first takes about a quarter
#: of what is left, which is why the table stops where `sphere` does.
#: `tests/test_three_solids.py` checks it against freshly built meshes.
_ICO_DEVIATION = (0.205346, 0.065828, 0.017753, 0.004528,
                  0.001138, 0.000285, 0.0000712)


def segments_for(radius: float, tolerance: float, *,
                 floor: int = ROUND_FLOOR, ceiling: int = 256) -> int:
    """How many segments a circle of `radius` needs to stay within `tolerance`.

    Both are in the same units -- pass millimetres on the page for both and the
    answer is what the reader will actually see. An n-gon inscribed in a circle
    of radius r bulges inward by r(1 - cos(pi/n)) at the middle of each chord,
    so the smallest n that keeps that under the tolerance is

        n = pi / acos(1 - tolerance / r)

    rounded up. The inward direction matters: the drawn polygon is *inside* the
    true curve, so a shape sampled this way comes out very slightly small, never
    large, which is the safe way round for something that has to fit a stated
    width.
    """
    if radius <= 0.0 or tolerance <= 0.0:
        return ceiling
    if tolerance >= 2.0 * radius:
        return floor            # the whole circle is inside the tolerance
    inner = max(-1.0, min(1.0, 1.0 - tolerance / radius))
    return max(floor, min(ceiling, math.ceil(math.pi / math.acos(inner))))


def subdivisions_for(radius: float, tolerance: float) -> int:
    """The icosphere level a sphere of `radius` needs, for `tolerance`.

    Same units for both, same reasoning as `segments_for`, but read off
    `_ICO_DEVIATION` instead of a formula, because a subdivided icosahedron's
    faces are not regular and there is no closed form worth trusting over a
    measurement.
    """
    if radius <= 0.0 or tolerance <= 0.0:
        return len(_ICO_DEVIATION) - 1
    for level, relative in enumerate(_ICO_DEVIATION):
        if relative * radius <= tolerance:
            return level
    return len(_ICO_DEVIATION) - 1


#: Which of a builder's keywords set how finely a curve is sampled, and the
#: radius of the curve each one is sampling, from that builder's own arguments.
#: A shape with no curve in it is simply absent.
#:
#: The radius is the one that governs the *silhouette*, which is what a reader
#: judges roundness by: a torus is seen across its whole outer sweep, so its
#: ring count answers to `radius + tube` and only its tube section answers to
#: `tube`.
_ROUNDNESS: dict[str, Callable[[dict], dict[str, float]]] = {
    "arrow": lambda a: {"segments": max(a["shaft"], a["head_radius"])},
    "axes": lambda a: {"segments": 0.072 * a["thickness"] * a["length"]},
    "cone": lambda a: {"segments": a["radius"]},
    "cylinder": lambda a: {"segments": a["radius"]},
    "sphere": lambda a: {"subdivisions": a["radius"]},
    "torus": lambda a: {"segments": a["radius"] + a["tube"], "rings": a["tube"]},
    "tube": lambda a: {"segments": a["radius"]},
}

#: Which rule answers each of those keywords.
_CHOOSER: dict[str, Callable[[float, float], int]] = {
    "rings": segments_for,
    "segments": segments_for,
    "subdivisions": subdivisions_for,
}


def tessellation(kind: str, options: dict, scale: float,
                 tolerance: float = DEFAULT_TOLERANCE) -> dict[str, int]:
    """Segment counts for `kind` at `scale` millimetres per model unit.

    `options` is what the author passed to the builder. Anything they set
    themselves is left out of the result: stating `segments=6` is a decision
    about how the drawing should look, and an engine that silently raised it to
    32 because 32 is smoother would be overruling the author on the one axis
    they were explicit about.

    Returns `{}` for a shape with no curves in it, and for an unknown shape --
    a caller's own builder registered in `SOLIDS` is welcome, it just does not
    get this for free.
    """
    radii = _ROUNDNESS.get(kind.strip().lower())
    if radii is None or scale <= 0.0:
        return {}
    maker = SOLIDS[kind.strip().lower()]
    bound = inspect.signature(maker).bind_partial(**options)
    bound.apply_defaults()
    chosen: dict[str, int] = {}
    for keyword, radius in radii(dict(bound.arguments)).items():
        if keyword not in options:
            chosen[keyword] = _CHOOSER[keyword](radius * scale, tolerance)
    return chosen


def sweep(rings: Sequence[Sequence[Vec3]], *, caps: bool = True,
          closed: bool = False, groups: Sequence[str] | None = None,
          name: str = "sweep") -> Mesh:
    """Stitch a run of cross-sections into a tube.

    Every named solid above is a formula. This one is not: the caller hands in
    the cross-sections already placed in space, one ring of points per station
    along the path, and gets back the surface through them. That is what a
    protein cartoon needs and no parametric solid can give -- the section has
    to change shape along the path (a strand widens into an arrowhead, a helix
    flattens into a ribbon and rounds back into a coil at each end) while the
    path itself is an arbitrary curve.

    Every ring must have the same number of points, and corresponding points
    must be *corresponding*: point `k` of one ring joins point `k` of the next.
    Getting that wrong is the classic swept-surface bug -- the tube twists a
    full turn between two stations -- and it is the caller's job to carry a
    consistent frame along the path, because only the caller knows what
    "consistent" means for the shape it is sweeping.

    `caps` closes both ends with a fan from the ring's centroid, which makes
    the surface closed and so back-face-cullable and shadeable. `closed` joins
    the last ring back to the first for a loop, and takes precedence over caps.

    `groups` names one group per cross-section; the band between two stations
    takes the earlier one's name, and each cap takes its own station's. That is
    what lets a single swept surface be coloured in stretches -- a ribbon whose
    helices and strands differ -- without cutting it into separate meshes that
    would then have to be depth-sorted against each other.
    """
    stations = [tuple(ring) for ring in rings]
    if len(stations) < 2:
        raise MeshError(f"a sweep needs at least two cross-sections, "
                        f"got {len(stations)}")
    width = len(stations[0])
    if width < 3:
        raise MeshError(f"a cross-section needs at least three points, "
                        f"got {width}")
    for index, ring in enumerate(stations):
        if len(ring) != width:
            raise MeshError(
                f"cross-section {index} has {len(ring)} points but the first "
                f"has {width}; every ring in a sweep must have the same number, "
                "so that point k of one joins point k of the next")

    if groups is not None and len(groups) != len(stations):
        raise MeshError(f"{len(groups)} group names for {len(stations)} "
                        "cross-sections; give one per ring or none at all")

    vertices: list[Vec3] = [point for ring in stations for point in ring]
    faces: list[tuple[int, int, int]] = []
    named: list[str] = []
    pairs = list(range(len(stations) - 1))
    if closed:
        pairs.append(len(stations) - 1)
    for station in pairs:
        here = station * width
        there = ((station + 1) % len(stations)) * width
        for i in range(width):
            j = (i + 1) % width
            _quad(faces, here + i, here + j, there + j, there + i)
        if groups is not None:
            named += [groups[station]] * (2 * width)
    if caps and not closed:
        for station, back in ((0, True), (len(stations) - 1, False)):
            ring = stations[station]
            centre = len(vertices)
            vertices.append(sum(ring, Vec3()) * (1.0 / width))
            base = station * width
            for i in range(width):
                j = (i + 1) % width
                faces.append((centre, base + j, base + i) if back
                             else (centre, base + i, base + j))
            if groups is not None:
                named += [groups[station]] * width
    return Mesh(tuple(vertices), tuple(faces),
                groups=tuple(named), name=name)
