"""Cameras: where you stand, and how the world flattens onto the page.

Two halves, kept apart on purpose.

A `Camera` is what an author writes: a named view, or an azimuth and an
elevation, or an explicit `look_at`. It carries no distances and no scale,
because an author who has to know that a brain scan is 0.14 units across before
they can point a camera at it has been made to compute a coordinate -- which is
the one thing this library exists to prevent.

A `View` is what the renderer uses: an eye position, an orthonormal basis, and
the millimetre scale that makes the projection come out at the width that was
asked for. It is produced by `Camera.frame(mesh, width=...)`, which is the step
that resolves everything the camera left open.

**Model space is z-up, right-handed.** That is the CAD, engineering and Blender
convention, and it is what makes `axes()` label the vertical arrow `z` the way
a methods figure does. Files exported from y-up tools are rotated on the way in
by `up_axis="y"`, once, rather than by every view having to know.

**Screen space is millimetres with y growing downward**, matching the rest of
inklet. The sign flip happens exactly once, in `project`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from ..core.geom import Rect, Vec2
from .linalg import Vec3
from .mesh import Mesh, MeshError

__all__ = ["Camera", "View", "Projected", "PRESETS", "preset_names", "as_camera"]

# An elevation this close to straight up leaves `up` and the view direction
# parallel, so the right vector is undefined. Half a degree is far tighter than
# any view an author types and far looser than the float noise in a cosine.
_POLE = 89.5

# Perspective needs the eye a definite distance away, and that distance is the
# whole character of the shot. Three radii is a mild wide-angle: enough
# convergence to read as depth, not enough to look like a fisheye photograph of
# a chip. Orthographic is placed further out only so depths stay positive.
_PERSPECTIVE_DISTANCE = 3.0
_ORTHOGRAPHIC_DISTANCE = 8.0

# A vertex closer to the eye than this fraction of the framing distance is
# behind or inside the lens, where the perspective divide has no meaning.
_NEAR_FRACTION = 0.01


@dataclass(frozen=True, slots=True)
class Projected:
    """A point on the page, and how far away it was."""

    point: Vec2
    depth: float


def _direction(azimuth: float, elevation: float) -> Vec3:
    """A unit vector from the subject toward the eye.

    Azimuth is measured from straight-ahead (the -y axis, so the camera starts
    in front of the model looking north) and turns toward +x, which is the
    author's right. Elevation lifts toward +z. Both in degrees, because nobody
    types a view angle in radians.
    """
    a, e = math.radians(azimuth), math.radians(elevation)
    return Vec3(math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e))


@dataclass(frozen=True)
class Camera:
    """Where to stand. Distances and scale are resolved later, by `frame`."""

    azimuth: float = 0.0
    elevation: float = 0.0
    perspective: bool = False
    #: Vertical field of view in degrees. Ignored when orthographic.
    fov: float = 30.0
    #: Degrees of roll about the view axis, positive turning the model
    #: clockwise on the page. Rarely wanted, occasionally essential.
    roll: float = 0.0
    #: Set by `look_at` to pin the eye; otherwise the framing derives it.
    eye: Vec3 | None = None
    target: Vec3 | None = None
    up: Vec3 | None = None

    @staticmethod
    def named(name: str) -> Camera:
        try:
            return PRESETS[name.strip().lower()]
        except KeyError:
            raise MeshError(
                f"unknown view {name!r}; known views are {preset_names()}, or "
                "pass an (azimuth, elevation) pair or a Camera"
            ) from None

    @staticmethod
    def look_at(eye: Vec3, target: Vec3 = Vec3(), up: Vec3 = Vec3(0.0, 0.0, 1.0),
                *, perspective: bool = False, fov: float = 30.0) -> Camera:
        """The explicit form, for when the author really does have coordinates.

        `azimuth`/`elevation` are still filled in, derived from the eye, so a
        camera always answers the same questions however it was built.
        """
        offset = eye - target
        if offset.length == 0.0:
            raise MeshError("look_at needs the eye and the target to differ")
        unit = offset.normalized()
        return Camera(
            azimuth=math.degrees(math.atan2(unit.x, -unit.y)),
            elevation=math.degrees(math.asin(max(-1.0, min(1.0, unit.z)))),
            perspective=perspective, fov=fov, eye=eye, target=target, up=up,
        )

    def turned(self, azimuth: float = 0.0, elevation: float = 0.0) -> Camera:
        """Nudge a preset. `Camera.named("isometric").turned(elevation=-10)`
        reads better at a call site than remembering that isometric is 35.26."""
        return replace(self, azimuth=self.azimuth + azimuth,
                       elevation=self.elevation + elevation, eye=None)

    @property
    def direction(self) -> Vec3:
        """From the subject toward the eye."""
        if self.eye is not None:
            return (self.eye - (self.target or Vec3())).normalized()
        return _direction(self.azimuth, self.elevation)

    def _up(self) -> Vec3:
        if self.up is not None:
            return self.up
        # Looking straight down, world z is parallel to the view and cannot
        # define "up on the page". +y takes over, which puts north at the top
        # of a plan view -- the convention every map uses.
        if abs(self.elevation) > _POLE:
            return Vec3(0.0, 1.0, 0.0)
        return Vec3(0.0, 0.0, 1.0)

    # -- resolution -------------------------------------------------------

    def frame(self, mesh: Mesh, width: float | None = None,
              height: float | None = None) -> View:
        """Resolve into a `View` that renders this mesh at the given size.

        Exactly the auto-fit the contract asks for: the author states a width in
        millimetres and never learns what the model's units were. Both `width`
        and `height` given means fit inside the box and keep the aspect;
        neither means unit scale, which only the tests want.
        """
        if mesh.is_empty:
            raise MeshError("cannot frame an empty mesh")
        target = self.target if self.target is not None else mesh.center
        radius = max(mesh.radius, 1e-9)
        if self.eye is not None:
            eye = self.eye
        else:
            span = _PERSPECTIVE_DISTANCE if self.perspective else _ORTHOGRAPHIC_DISTANCE
            eye = target + self.direction * (radius * span)

        forward = (target - eye)
        if forward.length == 0.0:
            raise MeshError("the camera is standing on its own target")
        forward = forward.normalized()
        right = forward.cross(self._up())
        if right.length < 1e-9:
            raise MeshError(
                f"up {self._up()} is parallel to the view direction; pass a "
                "different up= so the horizon has a direction"
            )
        right = right.normalized()
        up = right.cross(forward)
        if self.roll:
            a = math.radians(self.roll)
            cos, sin = math.cos(a), math.sin(a)
            right, up = (right * cos + up * sin), (up * cos - right * sin)

        focal = 1.0 / math.tan(math.radians(self.fov) / 2.0) if self.perspective else 1.0
        raw = View(eye=eye, right=right, up=up, forward=forward,
                   perspective=self.perspective, focal=focal,
                   near=radius * _NEAR_FRACTION)
        return raw.fitted(mesh, width, height)


@dataclass(frozen=True)
class View:
    """A resolved camera: everything needed to turn a `Vec3` into a page point.

    `scale` and `offset` are the auto-fit, applied after the projection so that
    the same basis serves every size the same model is drawn at.
    """

    eye: Vec3
    right: Vec3
    up: Vec3
    forward: Vec3
    perspective: bool = False
    focal: float = 1.0
    near: float = 1e-6
    scale: float = 1.0
    offset: Vec2 = Vec2(0.0, 0.0)

    def to_eye(self, point: Vec3) -> Vec3:
        """Which way the camera is, from a point on the surface.

        The only place the two projections differ in how *facing* is decided:
        under orthographic every point sees the eye in the same direction, and
        using the real eye there would make a distant flat panel curl away from
        the viewer at its edges.
        """
        return (self.eye - point) if self.perspective else -self.forward

    def project(self, p: Vec3) -> Projected:
        d = p - self.eye
        x, y, depth = d.dot(self.right), d.dot(self.up), d.dot(self.forward)
        if self.perspective:
            # Clamped rather than raised on: a single vertex drifting behind the
            # lens should distort one triangle, not abort a whole figure. The
            # clamp pins it to the near plane, which is where a rasteriser
            # would clip it to anyway.
            divisor = depth if depth > self.near else self.near
            x, y = x * self.focal / divisor, y * self.focal / divisor
        # The one place page-space y flips. Screen up is -y everywhere in inklet.
        return Projected(Vec2(x * self.scale + self.offset.x,
                              -y * self.scale + self.offset.y), depth)

    def project_all(self, points) -> tuple[list[Vec2], list[float]]:
        """Every vertex at once, which is where the time goes on a big mesh."""
        pts: list[Vec2] = []
        depths: list[float] = []
        for p in points:
            hit = self.project(p)
            pts.append(hit.point)
            depths.append(hit.depth)
        return pts, depths

    def raw_bounds(self, mesh: Mesh) -> Rect:
        """The projection's extent before any fit, in the camera's own units."""
        unfitted = replace(self, scale=1.0, offset=Vec2(0.0, 0.0))
        points, _ = unfitted.project_all(mesh.vertices)
        return Rect.hull(points)

    def fitted(self, mesh: Mesh, width: float | None,
               height: float | None) -> View:
        """Scale and centre the projection into the requested millimetres.

        Centring on the *projected* bounding box rather than on the model's
        centre is what makes the result obey inklet's "primitives are centred on
        their local origin" rule: an off-centre model still comes out with its
        drawn ink balanced about the node's origin, so it stacks like a box.
        """
        box = self.raw_bounds(mesh)
        if width is None and height is None:
            scale = 1.0
        else:
            options = []
            if width is not None:
                options.append(width / box.width if box.width > 1e-12 else math.inf)
            if height is not None:
                options.append(height / box.height if box.height > 1e-12 else math.inf)
            scale = min(options)
            if not math.isfinite(scale):
                raise MeshError(
                    "this view projects the mesh to a line, so it has no size to "
                    "fit; rotate the camera off the degenerate axis"
                )
        # `raw_bounds` measures the projection with the y-flip already applied,
        # so its centre is in page space and both components subtract. The
        # tempting `+centre.y` -- "undo the flip" -- is wrong and invisible on
        # anything symmetric: a cone's outline is a triangle over an ellipse
        # and its projected box is off-centre even when the mesh is not.
        centre = box.center
        return replace(self, scale=scale,
                       offset=Vec2(-centre.x * scale, -centre.y * scale))


# -- presets --------------------------------------------------------------

# Isometric is the true one: elevation atan(1/sqrt(2)), which is what makes all
# three axes foreshorten equally and a cube project to a regular hexagon.
_ISOMETRIC_ELEVATION = math.degrees(math.atan(1.0 / math.sqrt(2.0)))
# Dimetric's 2:1 -- the flat-rotated pixel-art convention, atan(1/2). Two axes
# match, the third does not, and vertical edges stay noticeably taller than in
# isometric, which reads better for anything tall and thin.
_DIMETRIC_ELEVATION = math.degrees(math.atan(0.5))

PRESETS: dict[str, Camera] = {
    "front": Camera(0.0, 0.0),
    "back": Camera(180.0, 0.0),
    "right": Camera(90.0, 0.0),
    "left": Camera(-90.0, 0.0),
    "top": Camera(0.0, 90.0),
    "bottom": Camera(0.0, -90.0),
    "isometric": Camera(45.0, _ISOMETRIC_ELEVATION),
    "dimetric": Camera(45.0, _DIMETRIC_ELEVATION),
    # Turned enough to show a second face and lifted enough to show the top,
    # but not to 45/35 -- a three-quarter view is meant to look like a
    # photograph of an object on a desk, not like a CAD drawing.
    "three-quarter": Camera(35.0, 20.0),
    "three-quarter-left": Camera(-35.0, 20.0),
    # A gentle perspective for the one figure in a paper that wants to look
    # like an object rather than like a diagram of one.
    "hero": Camera(30.0, 18.0, perspective=True, fov=28.0),
}


def preset_names() -> tuple[str, ...]:
    """Sorted, so anything that prints or iterates these stays deterministic."""
    return tuple(sorted(PRESETS))


def as_camera(view: Camera | str | tuple[float, float] | None) -> Camera:
    """Coerce the `view=` argument: a preset name, an angle pair, or a Camera."""
    if view is None:
        return PRESETS["three-quarter"]
    if isinstance(view, Camera):
        return view
    if isinstance(view, str):
        return Camera.named(view)
    if isinstance(view, tuple) and len(view) == 2:
        return Camera(float(view[0]), float(view[1]))
    raise MeshError(
        f"view must be a preset name, an (azimuth, elevation) pair or a Camera, "
        f"not {type(view).__name__}"
    )
