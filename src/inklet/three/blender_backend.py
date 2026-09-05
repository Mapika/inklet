"""The Blender renderer, wired into the backend registry.

`inklet.three.blender` deliberately registers itself nowhere: it is a function
that takes a mesh file and gives back millimetres, with no opinion about
figures. This module is the join. It turns a `Request` into a bake and the
bake back into a `Rendering`, so that

    inklet.model("brain.obj", width=40, backend="blender")

differs from the builtin only in who did the hidden-line removal.

Two things have to be true for that to be more than a slogan, and both are
this module's job:

* **The mesh Blender draws is the mesh inklet was asked about.** `inklet.model`
  applies `up_axis` and `transform` before rendering, so the file on disk is
  not necessarily the geometry in hand. The request's mesh is written out
  afresh; `line_art` hashes what it is given, so the cache stays honest.
* **The view is inklet's view.** Blender frames a subject its own way. Rather
  than teach inklet that framing, the drawing is mapped onto the projection
  `Camera.frame` already computed -- so `node.at("nose")` lands in the same
  place whichever backend drew it, which is the entire point of having two.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from ..assets.cache import cache_root
from ..core import Diagram, Rect, Vec2
from .backend import (
    INK_KIND, OUTLINE_KIND, Look, Rendering, Request, _ink_node, _theme,
    register_backend,
)
from .camera import View
from .mesh import Mesh, MeshError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .blender import LineArtDrawing

#: Styles the bake can actually produce. Line Art draws lines; asking it for a
#: shaded solid would silently hand back an outline, which is worse than a
#: sentence saying so.
SUPPORTED_STYLES = ("lineart",)

#: Enough precision that a millimetre-scale figure cannot tell the written mesh
#: from the one in memory, and few enough digits that the file stays small.
_OBJ_FORMAT = "{:.9g}"

_ALIGN_EPS = 1e-9


def _mesh_obj(mesh: Mesh, cache: Path) -> Path:
    """Write the mesh out, named by its own content.

    Content-addressed rather than temporary, because `line_art` caches on the
    bytes it is handed: the same mesh asked for twice must produce the same
    path *and* the same hash, or every render is a cold bake.
    """
    body = _obj_text(mesh)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{_slug(mesh.name) or 'mesh'}-{digest}.obj"
    if not path.exists():
        # Written beside and moved, so a reader in another process never sees
        # a half-written file and hands Blender a truncated mesh.
        staging = path.with_suffix(".obj.part")
        staging.write_text(body, encoding="utf-8")
        staging.replace(path)
    return path


def _obj_text(mesh: Mesh) -> str:
    fmt = _OBJ_FORMAT
    out = ["# written by inklet.three.blender_backend\n"]
    for v in mesh.vertices:
        out.append(f"v {fmt.format(v.x)} {fmt.format(v.y)} {fmt.format(v.z)}\n")
    for a, b, c in mesh.faces:
        out.append(f"f {a + 1} {b + 1} {c + 1}\n")
    return "".join(out)


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name)[:40].strip("-")


def _fit(source: Rect, target: Rect) -> tuple[float, Vec2]:
    """Uniform scale and translation carrying one box onto another.

    Uniform because the two projections agree on aspect ratio -- they are the
    same orthographic camera -- so any difference between the axes is fitting
    noise, and letting x and y scale apart would quietly shear the drawing to
    hide it. The residual is measured instead, by `align_error`.
    """
    if source.width <= _ALIGN_EPS or source.height <= _ALIGN_EPS:
        return 1.0, Vec2(0.0, 0.0)
    scale = min(target.width / source.width, target.height / source.height)
    centre, aim = source.center, target.center
    return scale, Vec2(aim.x - centre.x * scale, aim.y - centre.y * scale)


def align_error(drawing: "LineArtDrawing", mesh: Mesh, view: View) -> float:
    """How far, in mm, Blender's framing disagrees with inklet's after fitting.

    Exposed because it is the one number that says whether an arrow aimed at a
    3D landmark will land on the ink. It is not zero: Line Art draws stroke
    centres and chains them with a tolerance, so the outline it returns sits a
    fraction inside the true silhouette.
    """
    box = _drawn_box(drawing)
    if box is None:
        return 0.0
    projected = _projected_box(mesh, view)
    scale, shift = _fit(box, projected)
    scaled = Rect(box.x0 * scale + shift.x, box.y0 * scale + shift.y,
                  box.x1 * scale + shift.x, box.y1 * scale + shift.y)
    return max(abs(scaled.x0 - projected.x0), abs(scaled.y0 - projected.y0),
               abs(scaled.x1 - projected.x1), abs(scaled.y1 - projected.y1))


def _drawn_box(drawing: "LineArtDrawing") -> Rect | None:
    points = [p for line in drawing.polylines for p in line]
    if drawing.silhouette is not None:
        points.extend(drawing.silhouette.points)
    return Rect.hull(points) if points else None


def _projected_box(mesh: Mesh, view: View) -> Rect:
    points, _ = view.project_all(mesh.vertices)
    return Rect.hull(points)


def render_with_blender(request: Request) -> Rendering:
    """Bake the request's mesh and return it in inklet's own view."""
    from .blender import LineArtOptions, line_art

    mesh, look = request.mesh, request.look
    if mesh.is_empty:
        raise MeshError("there is nothing to render: the mesh has no faces")
    if look.style not in SUPPORTED_STYLES:
        raise MeshError(
            f"the blender backend draws {'/'.join(SUPPORTED_STYLES)}, not "
            f"{look.style!r}; render it with backend='builtin', or ask for "
            "lineart and fill behind it"
        )

    view = request.camera.frame(mesh, request.width, request.height)
    box = _projected_box(mesh, view)
    cache = cache_root(None)
    path = _mesh_obj(mesh, cache / "meshes")

    drawing = line_art(
        path,
        width=max(box.width, _ALIGN_EPS),
        height=max(box.height, _ALIGN_EPS),
        camera=request.camera,
        # The request's mesh is already in inklet's frame: `inklet.model` applied
        # `up_axis` on the way in, and applying it twice would lie the model
        # onto its side.
        up_axis="z",
        options=_options(look),
    )

    drawn = _drawn_box(drawing)
    scale, shift = _fit(drawn, box) if drawn is not None else (1.0, Vec2(0.0, 0.0))

    def place(points):
        return tuple(Vec2(p.x * scale + shift.x, p.y * scale + shift.y) for p in points)

    theme = _theme()
    ink = look.ink or theme.ink
    weight = look.stroke_width if look.stroke_width is not None else theme.stroke
    chains = [(place(line), False) for line in drawing.polylines if len(line) >= 2]
    node = Diagram(children=tuple(_ink_node(chains, OUTLINE_KIND, ink, weight)),
                   kind=INK_KIND)

    silhouette: tuple = ()
    if drawing.silhouette is not None and len(drawing.silhouette.points) >= 2:
        silhouette = ((place(drawing.silhouette.points), True),)
    return Rendering(node, silhouette, view)


def _options(look: Look) -> "LineArtOptions":
    from .blender import LineArtOptions

    known = {f.name for f in LineArtOptions.__dataclass_fields__.values()}
    extra = {k: v for k, v in look.options if k in known}
    return LineArtOptions(crease=look.crease, hidden=look.hidden, cull=look.cull,
                          **extra)


def _available() -> bool:
    from .blender import blender_available

    return blender_available()


# Above the builtin, so `backend="auto"` prefers the exact hidden-line removal
# when Blender is installed and falls back silently when it is not.
register_backend("blender", render_with_blender, priority=10, available=_available)
