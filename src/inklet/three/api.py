"""`inklet.model()`, `inklet.solid()`, `inklet.scene()` and `inklet.axes()` -- 3D that
composes like a box.

    chip = inklet.solid("box", width=26, view="isometric", style="shaded",
                     size_x=1.6, size_z=0.25)
    head = inklet.model("spot.obj", width=34, view="three-quarter")
    rig = inklet.scene([("body", body), ("lid", lid)], width=90, view="front")
    fig.link(inklet.box("probe"), head.at("nose"))

What comes back is an ordinary `Diagram` of vector paths. It stacks, it takes
the theme's colours, it scales without going soft, and -- the point of the
exercise -- an arrow aimed at it clips on the object's silhouette rather than
on its bounding box, and can be aimed at a *named point in three dimensions*
that this module projects onto the page for you.

Three things this layer owns, and the backend does not:

**Anchors.** `anchors={"tip": (0, 0, 1)}` names a point in the model's own
coordinates. It is projected through the same fitted view the drawing used and
registered as a plain 2D anchor in the node's local frame -- local, because
that is what `Diagram.anchor_point` returns and what `Placement.point` then
maps into the world. Getting that backwards puts every arrow at the top-left of
the page. Face groups become anchors too, so an OBJ that names its parts gives
you `assembly.at("housing")` for free.

**The trace.** The silhouette is attached as a `PathPrim` styled to draw
nothing. Core has no way for a node to contribute a trace without also
contributing ink -- `PhantomPrim` is the only inkless primitive and its trace is
deliberately empty -- so the outline is smuggled in on an inert path, exactly as
`inklet.assets` does it. See the note in `_carrier`.

**Sizing.** `width` and `height` are millimetres or unit strings, and one is
enough: the other follows the projection's aspect. The author never learns what
the model's units were. `scene()` is where that stops being enough: fitting
each of a dozen parts to the same width is a collage, so a scene fits the parts
*together* and hands each one its share of the one projection.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..core.envelope import Envelope
from ..core.diagram import Diagram
from ..core.geom import IDENTITY, Rect, Vec2
from ..core.prims import PathPrim, Subpath
from ..core.units import mm
from .backend import (Look, Rendering, Request, TOON,
                      outline_of as _mesh_outline, render)
from .camera import Camera, View, as_camera
from .edges import facing_faces
from .linalg import Mat4, Vec3
from .mesh import Mesh, MeshError, merge
from .depth import ScenePaint
from .occlude import _EMPTY, _depth_grid
from .parse import load
from .place import placement
from .solids import DEFAULT_TOLERANCE
from .solids import build as build_solid
from .solids import solid_names, tessellation

__all__ = ["model", "solid", "scene", "axes", "view_of", "anchor3d", "PICKS",
           "page_scale", "outline_of", "parts_of", "scene_paint",
           "MODEL_KIND", "SILHOUETTE_KIND", "DEFAULT_WIDTH"]

MODEL_KIND = "model"
SILHOUETTE_KIND = "model-silhouette"
#: What `scene(order="exact")` wraps its one drawing in. The lint rules read
#: it: everything under it is a *painting* of parts that are themselves nodes,
#: so a crossing or an overlap belongs to the part, not to the painting.
FUSED_KIND = "model-fused"

#: A figure is 89 mm wide. A 3D inset that has to sit beside a label and still
#: read is about a quarter of that; anything else the author states.
DEFAULT_WIDTH = 24.0

# Rotations that bring a file's own up-axis onto inklet's z-up. Y-up is what most
# graphics exporters write; x-up is vanishingly rare but costs one line.
_UP_ROTATION = {
    "z": None,
    "y": (Vec3(1.0, 0.0, 0.0), 90.0),
    "x": (Vec3(0.0, 1.0, 0.0), -90.0),
}

# The fitted view of every node this module built, so a caller can project more
# 3D points after the fact. Keyed by node id, like `inklet.assets.provenance`, and
# with the same honest caveat: `Diagram` has no metadata slot, so this leaks for
# the lifetime of the process and does not survive pickling.
_VIEWS: dict[str, View] = {}

# The geometry each node was drawn from, in the same world space its view
# projects. Only `anchor3d(pick="visible")` reads it, and only to ask what is
# drawn in front of a point. Same key and same caveat as `_VIEWS`.
_MESHES: dict[str, Mesh] = {}

# What each `scene()` node is made of and the order it paints its parts in, so
# that `inklet.lint` can compare the two. Same key and same caveat as `_VIEWS`.
_SCENES: dict[str, ScenePaint] = {}

# One depth grid per node, because a figure hangs several labels off one model
# and rasterising fifty thousand faces once a label is the difference between
# a tenth of a second and a second. Keyed by node id like the two above.
_FRONTS: dict[str, tuple] = {}


def view_of(node: Diagram) -> View:
    """The fitted camera a 3D node was drawn with."""
    found = _VIEWS.get(node.id)
    if found is None:
        raise MeshError(
            f"{node.id} was not built by inklet.three, so it has no 3D view")
    return found


#: How `anchor3d` turns several candidate points into the one it anchors at.
PICKS = ("centroid", "nearest", "visible")


def anchor3d(node: Diagram, name: str,
             point: Sequence[float] | Sequence[Sequence[float]],
             *, pick: str = "centroid") -> Diagram:
    """Add an anchor at a 3D point, after the fact. Returns the node.

    `point` is one point, or several to choose between. Several is the useful
    case, and the reason is that **the point that names a feature is not a
    property of the feature -- it depends on where the camera is standing.**
    The centroid of a helix is inside the helix, so the helix's own front
    surface hides it and a leader aimed there appears to stop at whatever is
    drawn in front, which on a protein is something else with a name of its
    own. Hand in the feature's points and say how to choose:

        run = [residue.ca for residue in helix]
        inklet.anchor3d(node, "helix-C", run, pick="visible")

    `pick="centroid"` is the default and the mean of what it is given, which
    for one point is that point: the behaviour this function has always had.

    `pick="nearest"` is the candidate nearest the camera -- the near surface of
    the feature. Costs nothing but a dot product, and it is right far more
    often than the centroid.

    `pick="visible"` is the candidate the reader can actually see: the ones
    that are the frontmost drawn surface at their own place on the page, and
    of those the one furthest from the feature's edge, so the leader lands in
    the middle of the visible part rather than on its rim. If none is visible
    -- a helix wholly behind a sheet -- it falls back to `"nearest"`, because
    the near side of a buried feature is still the best available answer and
    the alternative is refusing to draw the label.

    **`"nearest"` is not `"visible"`, and the gap is the whole point.** On the
    kinase in `figures/`, `"nearest"` leaves the b3 strand's anchor buried 1.4
    model units behind the ribbon in front of it, and puts helix aC's anchor 2.0
    units out in *front* of the drawing, in mid-air -- because a spline through
    alpha carbons cuts the corners the atoms sit on. Every one of the seven
    features has at least three residues that are genuinely unobstructed, and
    `"visible"` finds them. It costs one rasterisation of the mesh, cached per
    node, so the first label pays about a tenth of a second and the rest are
    free.
    """
    if pick not in PICKS:
        raise MeshError(f"pick is one of {PICKS}, got {pick!r}")
    view = view_of(node)
    points = _as_points(point, name)
    if len(points) == 1:
        chosen = points[0]
    elif pick == "centroid":
        chosen = sum(points, Vec3()) * (1.0 / len(points))
    elif pick == "nearest":
        chosen = min(points, key=lambda p: view.project(p).depth)
    else:
        chosen = _most_visible(node, view, points)
    return node.anchor(name, view.project(chosen).point)


def _most_visible(node: Diagram, view: View, points: list[Vec3]) -> Vec3:
    """The candidate standing furthest from the edge of what is drawn.

    Not simply the first unobstructed one, and not the nearest of them. A
    point that is unobstructed but a hair from a silhouette is a point the
    leader will appear to miss, because the leader has width and the reader
    reads its whole tip. So among the visible candidates, take the one whose
    surroundings are also visible: the score is how many of the eight cells
    around it are the same surface.
    """
    front = _front_grid(node)
    if front is None:
        return min(points, key=lambda p: view.project(p).depth)
    grid, x0, y0, step, wide, tall = front
    slack = step * _SLACK

    best, score = None, -1
    for candidate in points:
        at = view.project(candidate)
        cx = int((at.point.x - x0) / step)
        cy = int((at.point.y - y0) / step)
        if cx < 1 or cy < 1 or cx >= wide - 1 or cy >= tall - 1:
            continue
        here = grid[cy * wide + cx]
        if here == _EMPTY or at.depth - here > slack:
            continue                          # something is drawn in front
        clear = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if abs(grid[(cy + dy) * wide + cx + dx] - here) < slack)
        if clear > score:
            best, score = candidate, clear
    if best is None:
        return min(points, key=lambda p: view.project(p).depth)
    return best


def _front_grid(node: Diagram):
    """The nearest drawn surface under each cell of the page, once per node."""
    found = _FRONTS.get(node.id)
    if found is not None:
        return found or None
    mesh = _MESHES.get(node.id)
    if mesh is None:
        _FRONTS[node.id] = ()
        return None
    view = _VIEWS[node.id]
    points, depths = view.project_all(mesh.vertices)
    facing = facing_faces(mesh, view)
    drawable = [i for i, front in enumerate(facing) if front]
    grid, box = _depth_grid(mesh, points, depths, drawable)
    if grid is None:
        _FRONTS[node.id] = ()
        return None
    _FRONTS[node.id] = (grid, *box)
    return _FRONTS[node.id]


def page_scale(mesh: Mesh, *,
               width: float | str | None = None,
               height: float | str | None = None,
               view: Camera | str | tuple[float, float] | None = None,
               up_axis: str = "z",
               transform: Mat4 | None = None) -> float:
    """Millimetres per model unit, for the projection `model()` would use.

    The auto-fit is the whole point of `width=`: the author states millimetres
    and never learns what the model's units were. The cost of that is that
    nothing upstream of the render knows how big a facet is going to be, so
    every tessellation decision -- `subdivisions=`, `segments=`, how many
    cross-sections to sweep -- gets made against a scale only the engine has.
    This hands it over. Same arguments as `model()`, same answer it would fit.

    Exact under the orthographic projection inklet uses by default, where the
    scale is one number for the whole drawing. Under `perspective=True` it is
    the scale at the camera's target: nearer parts of the model are drawn
    larger and further ones smaller, so treat it as the middle of a range.

    There is a chicken and egg here and it is worth being plain about it: the
    fit is measured on a mesh, and the mesh is what the answer is used to
    build. Rebuilding moves the projected bounds by the chord error itself, so
    asking again gives a slightly different scale -- and not always a smaller
    one, because the bounding box of an n-gon is not monotone in n. It is a
    drift of about one segment in forty. `solid` closes it by only ever
    refining: see the loop there.
    """
    matrix = _orientation(up_axis, transform)
    placed = mesh.transformed(matrix) if matrix is not None else mesh
    size = _size(width, height)
    return as_camera(view).frame(placed, size[0], size[1]).scale


# -- the two entry points -------------------------------------------------


def model(source: str | Path | Mesh, *,
          width: float | str | None = None,
          height: float | str | None = None,
          view: Camera | str | tuple[float, float] | None = None,
          style: str = "lineart",
          shading: str | None = None,
          sort: str = "auto",
          opacity: float = 1.0,
          occlusion: float = 0.0,
          backend: str = "builtin",
          crease: float = 30.0,
          ridges: bool | Mapping[str, bool] = True,
          hidden: bool = True,
          cull: bool | None = None,
          smooth: bool | float | None = None,
          up_axis: str = "z",
          at: Sequence[float] | Vec3 | None = None,
          spin: Any = None,
          scale: float | Sequence[float] | None = None,
          transform: Mat4 | None = None,
          repair: bool = False,
          ink: str | None = None,
          color: str | None = None,
          colors: Mapping[str, str] | None = None,
          stroke_width: float | str | None = None,
          stroke_widths: Mapping[str, float | str] | None = None,
          creases: Mapping[str, float] | None = None,
          light: Vec3 | None = None,
          levels: int | None = None,
          depth_cue: float | None = None,
          lift: float | None = None,
          shade: float | None = None,
          anchors: Mapping[str, Sequence[float]] | None = None,
          groups: bool = True,
          options: Sequence[tuple[str, Any]] = (),
          name: str | None = None) -> Diagram:
    """Draw a mesh -- from a file or already in hand -- as vector line art.

    `view` is a preset name (`"isometric"`, `"three-quarter"`, `"front"`, ...),
    an `(azimuth, elevation)` pair in degrees, or a `Camera`. `style` is one of
    `"lineart"`, `"shaded"`, `"solid"`, `"toon"`, `"wireframe"`.

    `"toon"` is `"shaded"` with the four numbers a cartoon look wants already
    chosen -- three tone bands, cut smoothly, on a ramp pulled in at both ends
    so the three are told apart at a glance. State any of `shading=`,
    `levels=`, `lift=` or `shade=` yourself and yours is used; see
    `inklet.three.TOON` for what it fills in.

    `at`, `spin` and `scale` place the solid without a line of matrix
    algebra: `at=(1.4, 0, 0)` is where its own origin lands, `spin=("y", 90)`
    or `spin=(0, 90, 0)` turns it, `scale=` sizes it in model units. They are
    applied scale, then spin, then move -- and after an explicit `transform=`,
    which is written in the file's own frame. Coordinates are the model's own,
    the same frame `anchors=` uses, so `up_axis=` still corrects both.

    `repair=True` asks trimesh, when it is installed, to weld duplicate
    vertices and make the winding consistent. Worth doing to anything
    downloaded: both the silhouette test and the shading read the sign of a
    face normal, and a mesh with mixed winding grows silhouette edges through
    the middle of flat surfaces.

    `stroke_widths` does the same for line weight, and exists for
    `scene(order="exact")`, where one drawing pass covers every part.

    `colors` maps a mesh group name to a facet colour, for a mesh whose parts
    interleave in depth. Two meshes are sorted against each other as wholes, so
    a two-coloured object that folds through itself has to be one mesh with two
    groups -- and then this is the only way to give the groups different
    colours.

    `lift` and `shade` set the tonal range: how far the lit end of the ramp is
    lifted toward paper and the dark end pushed toward ink. The defaults are
    pale on purpose, so inked edges stay the strongest mark on the page; drop
    `lift` toward a half when the shaded body is the subject and the edges are
    only its outline.

    `crease` inks a fold sharper than that many degrees -- but only the
    sharpest edge across each fold, which is what lets a swept surface have an
    inked edge at all. Turn that off with `ridges=False` to ink every edge over
    the threshold, which on a rounded corner is a band of them. `creases=`
    names a threshold per mesh group, the way `stroke_widths` names a weight,
    for the case where one mesh holds parts of very different tessellations.

    `ridges=` takes a mapping too, and one scene can need it both ways. A
    sectioned solid is the case: `ridges={"brain/cut": False}` inks the cut
    rim whole -- there the fold *is* the line, and one edge of it is a dash
    trailing off into nothing -- while the surface it was cut from keeps one
    line per fold. Groups the mapping does not name keep suppression. Without
    it the rim has to be bought by raising the *surface's* threshold until
    ridges-off stops fragmenting it, which spends the surface's detail on the
    rim.

    By default the outline goes on the surface the facets stand for rather than
    on the facets themselves, which is what stops a nearly edge-on ribbon or
    tube from growing a fan of short strokes across its own interior. Where
    that surface is well defined comes from `crease`, capped at a right angle:
    saying which folds to ink is already saying which folds are the model's
    own. `smooth=False` puts the outline back on the facets, and a number sets
    the fold threshold independently of the inked one.

    `depth_cue` (shaded styles) fades the far end of the scene toward paper.
    Use it on anything that folds back over itself -- a protein, a coil, a
    stack of layers -- where shading alone cannot say which of two surfaces is
    in front. `levels` sets how many tones the shading is quantised to; raise
    it on a smoothly swept body, where the band boundaries fall along the sweep
    instead of staircasing across triangles.

    `shading="smooth"` cuts those bands out of the surface rather than handing
    one tone to each facet, so a band boundary is a curve across the model
    instead of a staircase round whichever triangles tipped over the step. It
    uses the same threshold as `smooth`, so the shading and the outline agree
    about where the surface is curved. Two things to know before turning it
    on. It pays *per level*, where flat shading pays nothing for them -- a
    facet has one tone however finely the ramp is cut -- so a body drawn with
    `levels=48` is asking for several polygons per triangle; drop `levels`
    when you turn this on, and the picture usually improves twice over,
    because the reason for a high count in the first place was to make the
    staircase small. And it earns its keep on a *coarse* curved body: on a
    mesh already fine enough that no staircase is visible there is little to
    win and a good deal of file to lose.

    `sort` settles which facet is painted over which. `"exact"` asks each pair
    of overlapping facets which of them is nearer, instead of guessing from a
    mean depth, and cuts the pair in two along the line where their planes
    meet when neither answer is right for all of the region they share. What
    wants it is a surface that folds back over itself, where a long facet seen
    almost edge-on has a mean depth near its middle while its near end reaches
    much closer, and gets painted over by something behind it -- or a plate
    whose bore is painted over the wall it goes through. `"depth"` is the mean
    depth alone, and it costs nothing.

    The default is `"auto"`: exact up to `inklet.three.AUTO_EXACT_FACETS` faces,
    mean depth above. The two answers are the same picture on a convex body,
    where front-facing facets never overlap at all, so the threshold does not
    buy a different-looking sphere -- it buys the awkward object coming out
    right without anyone having to know the argument exists. It is a threshold
    rather than a flat "always exact" because the exact order is a fixed
    multiple of the render, about 1.3x, which is under a hundredth of a second
    on the meshes a drawn object is made of and several seconds on a scanned
    surface of fifty thousand faces -- where the mean depth was measured wrong
    at seven sample points in twenty-four thousand, and is worth its cost.

    `opacity` makes the facets translucent so that whatever is behind them
    shows through -- a solvent surface over a cartoon, a case over a mechanism,
    a slab over the thing it was cut from. It applies to the fills only; the
    inked edges keep their weight, which is what makes a ghosted object still
    read as an object. For the whole node including its ink, style it from
    outside instead: `inklet.solid(...).styled(opacity=0.4)`.

    Transparency raises the stakes on two things that were free while
    everything was opaque, and both want saying out loud rather than being
    changed underfoot. **`cull=False`**, because through a translucent surface
    you see its own far side, and the default culls it. **`sort="exact"`**,
    because a wrong painting order is invisible behind an opaque facet and
    obvious through a translucent one. Neither is turned on for you: a
    translucent *open* surface has no far side to show, and a translucent
    convex one has no ordering to get wrong.

    `occlusion` darkens whatever sits in a hollow, by that fraction of the
    ramp. It is the third of three questions about a surface and the only one
    nothing else answers: `light` says which way a face turns, `depth_cue` says
    which of two faces is nearer, and neither of them can tell a binding pocket
    from the flat beside it -- a pocket faces the light exactly as its
    surroundings do. Around 0.3 is a strong effect and 0.15 a quiet one; it
    costs one rasterisation and a dozen samples per vertex, and no extra fills
    at all, because it is taken off the tone before the quantiser rather than
    painted on after it.
    """
    if depth_cue is not None and not 0.0 <= depth_cue <= 1.0:
        raise MeshError(
            f"depth_cue is a fraction of the way to paper, 0..1; got {depth_cue}")
    # `style="toon"` is four numbers under one name, and they are filled in
    # here rather than in `Look` because here is where "the author did not say"
    # is still distinguishable from "the author said the default".
    if style == "toon":
        shading = TOON["shading"] if shading is None else shading
        levels = TOON["levels"] if levels is None else levels
        lift = TOON["lift"] if lift is None else lift
        shade = TOON["shade"] if shade is None else shade
    mesh = source if isinstance(source, Mesh) else load(source, repair=repair)
    if repair and isinstance(source, Mesh):
        from .parse import repaired

        mesh = repaired(mesh)
    matrix = _orientation(up_axis, _placed(transform, at, spin, scale))
    placed = mesh.transformed(matrix) if matrix is not None else mesh

    # `ridges` is one flag, or a mapping naming the groups that want their
    # folds inked whole. The mapping form leaves everything it does not name
    # under ridge suppression, which is the setting that is right for a
    # surface; what it is for is the exception, a cut rim or a sheet edge.
    ridge_rule = ridges if isinstance(ridges, bool) else True
    ridge_groups = () if isinstance(ridges, bool) else tuple(sorted(ridges.items()))

    look = Look(
        style=style, sort=sort, opacity=opacity,
        **({"shading": shading} if shading is not None else {}),
        occlusion=occlusion,
        crease=crease, ridges=ridge_rule, ridge_groups=ridge_groups,
        hidden=hidden, cull=cull, smooth=smooth, ink=ink,
        color=color, colors=tuple(sorted((colors or {}).items())),
        stroke_width=None if stroke_width is None else mm(stroke_width),
        stroke_widths=tuple(sorted((name, mm(value)) for name, value
                                   in (stroke_widths or {}).items())),
        creases=tuple(sorted((creases or {}).items())),
        **({"light": light} if light is not None else {}),
        **({"levels": levels} if levels is not None else {}),
        **({"depth_cue": depth_cue} if depth_cue is not None else {}),
        **({"lift": lift} if lift is not None else {}),
        **({"shade": shade} if shade is not None else {}),
        options=tuple(sorted(options)),
    )
    size = _size(width, height)
    result = render(Request(placed, as_camera(view), size[0], size[1], look),
                    backend=backend)
    node = _assemble(result, name or mesh.name or "model")
    _MESHES[node.id] = placed
    _attach_anchors(node, placed, result.view, anchors, groups, matrix)
    return node


def solid(kind: str = "cube", *,
          tolerance: float | None = DEFAULT_TOLERANCE, **options) -> Diagram:
    """A parametric solid, with no asset file involved.

    Shape arguments go to the builder and everything else to `model`:
    `inklet.solid("cylinder", width=18, segments=48, view="dimetric")`. The known
    shapes are in `inklet.three.solid_names()`.

    **The tessellation follows the page.** `tolerance` is how far the drawn
    outline may sit from the curve it stands for, in millimetres *on paper*,
    and the segment counts are chosen from it: the same cylinder comes out a
    16-gon at 6 mm wide and a 58-gon at 80 mm, because that is what it takes to
    look round at each. The shape is built once so the camera can be fitted to
    it and then rebuilt at the count that fit implies; `page_scale` says why
    that needs a second look and `_refined` is the second look.

    Anything you set yourself is left alone. `segments=48` above is honoured
    exactly, `tolerance=None` turns the whole thing off and restores each
    builder's own default, and a shape with no curve in it (`box`, `plane`) was
    never affected either way.

    A `Mesh` is not a `kind`: `model` draws one you already have, and `scene`
    draws several. Passing one here is a `TypeError` that says so.
    """
    if not isinstance(kind, str):
        # The obvious first guess when you have a mesh in hand, and without
        # this it reaches `str.strip` deep inside the parser and reports that
        # a Mesh has no `strip`. Name both the thing that was expected and the
        # call that draws what was actually passed.
        raise TypeError(
            f"solid() takes the *name* of a parametric shape, not the "
            f"{type(kind).__name__} it was given: one of "
            f"{', '.join(solid_names())}. A mesh you already have is drawn by "
            f"model(mesh, ...), or by scene([(name, mesh), ...]) with the "
            f"others it shares a projection with")
    shape = {key: options.pop(key) for key in tuple(options)
             if key not in _MODEL_ARGS}
    mesh = build_solid(kind, **shape)
    if tolerance is not None and not mesh.is_empty:
        mesh = _refined(kind, shape, mesh, tolerance, options)
    options.setdefault("name", kind)
    return model(mesh, **options)


_MODEL_ARGS = frozenset(model.__kwdefaults__ or ())


def _refined(kind: str, shape: dict, mesh: Mesh, tolerance: float,
             options: dict) -> Mesh:
    """Rebuild `mesh` as finely as the page turns out to need, and no finer.

    The loop is there because the fit that chooses the tessellation is measured
    on the mesh the tessellation replaces. Refining a curve pushes its vertices
    outward onto the true circle, which grows the projected bounds and so
    shrinks the scale that fits them into the stated width -- except that the
    *bounding box* of an n-gon is not monotone in n, since which way its widest
    span points depends on where the vertices land. So the second measurement
    can ask for one segment more than the first, and just occasionally does.

    Only ever going finer is what makes that terminate and what makes the
    promise true. Counts rise, never fall, so the loop is bounded by the
    ceilings in `segments_for`; and the mesh that is finally drawn meets the
    tolerance at the scale it is finally drawn at, which is the only scale the
    reader ever sees. In practice it runs once and stops.
    """
    def fit(current: Mesh) -> float:
        return page_scale(
            current, width=options.get("width"), height=options.get("height"),
            view=options.get("view"), up_axis=options.get("up_axis", "z"),
            transform=options.get("transform"))

    chosen = tessellation(kind, shape, fit(mesh), tolerance)
    while chosen:
        mesh = build_solid(kind, **shape, **chosen)
        again = tessellation(kind, shape, fit(mesh), tolerance)
        stepped = {key: value for key, value in again.items()
                   if value > chosen[key]}
        if not stepped:
            return mesh
        chosen = {**chosen, **stepped}
    return mesh


# -- several meshes, one projection ---------------------------------------

#: Keywords a scene owns outright. A part may not set them, because a scene
#: that let one part choose its own width or its own camera would be twelve
#: drawings on one sheet rather than one drawing of twelve things.
_SCENE_OWNED = ("width", "height", "view", "name")

#: How a part overrides where it comes in the paint order. Per part and never
#: shared, because each of the three is a statement about *this* part: an
#: absolute place in the order, or a place relative to a named neighbour.
_ORDER_KEYS = ("draw_order", "behind", "in_front_of")


def scene(parts, *,
          width: float | str | None = None,
          height: float | str | None = None,
          view: Camera | str | tuple[float, float] | None = None,
          order: str = "parts",
          assert_order: Sequence[tuple[str, str]] = (),
          name: str = "scene",
          **shared) -> Diagram:
    """Several meshes in one projection, painted back to front.

    `model()` auto-fits whatever it is handed to the width it was asked for,
    which is right for one object and wrong for a scene: twelve calls give
    twelve different scales and no common ground to stand them on. `scene()`
    frames the parts *together* and then asks for each one at its own share of
    that projection, so what comes back is a single drawing whose pieces are
    still separate nodes -- each with its own colour, its own anchors, and its
    own silhouette for an arrow to clip on.

    Parts are `(name, mesh)` pairs, or `(name, mesh, options)` where the
    options override the keywords the whole scene shares:

        rig = inklet.scene([("body", body), ("lid", lid, {"color": "#c33"})],
                        width=90, view="three-quarter", style="shaded")
        rig.find("lid")      # the part itself, to aim an arrow at
        rig.at("lid")        # where it sits, as an anchor on the scene
        rig.at("lid.ne")     # ...and the eight compass points of its box
        inklet.anchor3d(rig, "focus", (0, 0, 12))   # any point in the scene

    **Every part answers to its own projected box.** `rig.at("lid.n")` and the
    other seven compass points, plus `"lid.center"`, which is `"lid"`; and any
    3D point a part names for itself comes along under the same prefix, so
    `("bolt", rod, {"anchors": {"tip": (2, 0, 0)}})` gives `rig.at("bolt.tip")`.
    That is the arithmetic a label off the end of a slanted rod used to need
    written out by hand. `inklet.three.outline_of(rig.find("lid"))` hands back the
    projected silhouette itself when a box is not enough.

    **A part says where it stands in its own options.** `at=`, `spin=` and
    `scale=` mean on a part what they mean on `solid()` -- scale, then turn,
    then move -- and are folded into the geometry before the camera is fitted,
    so the scene frames the assembly as it will be drawn:

        rig = inklet.scene([("plate", plate),
                         ("bolt", bolt, {"at": (0, 0, 14), "spin": ("x", 90)})],
                        width=90, view="three-quarter")

    That is the whole placement vocabulary an assembly needs, and it replaces
    a `Mat4` per part built at the call site. An explicit `transform=` still
    works and composes underneath the three.

    **Occlusion between parts is paint order.** By default they are drawn
    furthest centre first, so under `style="shaded"` or `"solid"` a nearer part
    covers the one behind it, which is what an assembly is meant to look like.
    Two things follow from that, and both are worth knowing before the drawing
    surprises you. Hidden-line removal runs per part -- it has no way to see
    across them -- so in `"lineart"`, where nothing is filled, a part behind
    another shows straight through it. And parts that interleave in depth, a
    rod through a ring, cannot be ordered by one number at all: whichever way
    the pair is sorted, some of the rod comes out on the wrong side of the
    ring.

    **Three per-part keywords override the order** where the geometry is
    honest and the author still wants the other picture. `draw_order=` is a
    place in the queue counting from zero at the back, and parts without one
    keep the place depth gave them, so the two mix. `behind="lid"` and
    `in_front_of="lid"` name a neighbour instead, which is the spelling that
    survives the scene growing a tenth part. `inklet.lint`'s `DEPTH_ORDER` rule
    takes any of the three as the answer and stops checking that part -- it is
    the knob the rule tells you to reach for.

    **`assert_order=[("objective", "sample")]` states the requirement** rather
    than hoping the drawing meets it. Each pair says the first part must come
    out in front of the second, and `inklet.lint`'s `DEPTH_ORDER` rule checks it
    against the projected geometry -- so the claim survives the camera being
    turned, the data changing, or a part being added between the two.

    **A leader that has to cross the scene can cite the scene.**
    `through=(rig,)` exempts every part inside it, because the lint rules ask
    whether the crossed node is *inside* anything the link declared -- so a
    tag on an atom in a wireframe cage no longer names all twelve rods.
    `inklet.three.parts_of(rig, lambda p: "edge" in p.name)` is the middle case:
    the rods, but not the atom the arrow is meant to stop on.

    `order="exact"` is the answer to both. It draws the whole scene in one
    pass -- one mesh, one hidden-line removal, one facet sort, the `"exact"`
    one -- so depth is settled facet by facet across parts instead of once per
    part, and a rod through a ring comes out threaded. It costs time: the
    exact sort resolves overlapping facets pairwise and splits them where they
    cross, and doing that across the whole assembly rather than inside each
    part is the price of the answer. On the eleven-part stack in
    `stress/electro/cell.py` -- 22 solids, ~5500 facets -- it is 0.89s against
    0.17s for `order="parts"`, and a panel that fits its width by rebuilding
    the scene pays that on every pass.

    What it costs is that a part is no longer separately *painted*, so only
    `color`, `colors` and `stroke_width` may still vary between parts -- the
    three the fused mesh can carry per face group; anything else a part sets
    is an error rather than a setting quietly ignored. Every part is
    still its own node with its own name, anchors and silhouette -- `find`,
    `at`, `through=` and arrows clipping on a part's outline all work exactly
    as they do under `order="parts"` -- but the node draws nothing, and what
    you see is the fused drawing behind it.

    **`overlay=True` on a part buys it out of the pass**, which is the only
    coherent way for a fused part to have a style of its own:

        rig = inklet.scene([("stack", stack), ("case", case,
                         {"overlay": True, "opacity": 0.35, "cull": False})],
                        width=90, view="three-quarter", order="exact",
                        style="shaded")

    The part is left out of the fused mesh and drawn as its own `model()` in
    the scene's projection, so it takes anything `model()` takes -- `style`,
    `opacity`, `occlusion`, `hidden`, `cull`, `sort`. The depth story is one
    sentence, and it is the price: **an overlay is always on top.** It hides
    nothing behind it and nothing hides it, because it was not in the pass
    that decides that; the two drawings are composited. Reach for it when
    that is what you want anyway -- a ghosted case over a mechanism, a
    cutting plane, one part in line art over a shaded assembly -- and not for
    anything that has to thread through the rest. `inklet.lint` reads the same
    story: `DEPTH_ORDER` treats an overlay as a part whose place the author
    set, exactly as it treats `draw_order=`.
    """
    entries = _scene_parts(parts)
    for owned in _SCENE_OWNED:
        if owned in shared or any(owned in options for _, _, options in entries):
            raise MeshError(
                f"{owned!r} is the scene's to set, not a part's: parts share "
                "one projection, and each is named by its entry in `parts`")
    for key in _ORDER_KEYS:
        if key in shared:
            raise MeshError(
                f"{key!r} is a part's to set, not the scene's: it says where "
                "one part comes in the paint order, so it belongs in that "
                "part's options")
    if "overlay" in shared:
        raise MeshError(
            "'overlay' is a part's to set, not the scene's: it takes one part "
            "out of the fused pass and draws it on top, and a scene with "
            "every part on top is order='parts'")
    claims = _claims(assert_order, [part for part, _, _ in entries])
    if order not in _SCENE_ORDERS:
        raise MeshError(
            f"order={order!r} is not one of {_SCENE_ORDERS}: 'parts' sorts the "
            "parts against each other by their centres, 'exact' draws them as "
            "one mesh and sorts facet by facet")

    camera = as_camera(view)
    whole = merge([mesh for _, mesh, _ in entries])
    size = _size(width, height)
    fitted = camera.frame(whole, size[0], size[1])
    origin = fitted.raw_bounds(whole).center
    # Pinning the eye and the target is what makes the framings agree. Left to
    # itself `Camera.frame` derives both from the mesh in front of it, so it
    # would stand somewhere different for each part -- and under perspective
    # that is not a translation of the same picture, it is a different picture.
    # Fixed, the only thing the per-part fit still does is scale and centre,
    # and asking for a part at its own projected width reproduces the scene's
    # own scale exactly. (Its near plane is derived per part as well, which
    # matters only to a vertex behind the lens.)
    pinned = replace(
        camera, eye=fitted.eye,
        target=camera.target if camera.target is not None else whole.center)
    if order == "exact":
        return _fused(entries, shared, fitted, pinned, size, whole, name, claims)

    depths: list[float] = []
    nodes: list[Diagram] = []
    boxes: list[Rect] = []
    for part, mesh, options in entries:
        if options.get("overlay"):
            raise MeshError(
                f"part {part!r} sets overlay=True, which order='parts' has "
                "nothing to opt out of: every part here is already its own "
                "node with its own style, and its place in the paint order is "
                "draw_order=, behind= or in_front_of=")
        box = fitted.raw_bounds(mesh)
        settings = {key: value for key, value in {**shared, **options}.items()
                    if key not in _ORDER_KEYS}
        settings.update(_share_of(box, fitted.scale))
        depths.append(fitted.project(mesh.center).depth)
        nodes.append(model(mesh, view=pinned, name=part, **settings))
        boxes.append(_in_scene(box, origin, fitted.scale))

    back = _paint_order(entries, depths)
    node = Diagram(
        children=tuple(nodes[i].placed(_translate(boxes[i].center)) for i in back),
        kind=MODEL_KIND, name=name)
    _attach_parts(node, entries, nodes, boxes)
    _VIEWS[node.id] = fitted
    # The parts merged, so that `pick="visible"` can see across them: a helix
    # hidden behind a *different part* is hidden all the same, and the scene's
    # own view is the one projection they all share.
    _MESHES[node.id] = whole
    _SCENES[node.id] = ScenePaint(
        names=tuple(part for part, _, _ in entries),
        nodes=tuple(one.id for one in nodes),
        meshes=tuple(mesh for _, mesh, _ in entries),
        view=fitted, paint=tuple(back), declared=_declared(entries),
        claims=claims)
    return node


#: How a scene settles depth between its parts. `"parts"` gives each part one
#: number and sorts on it; `"exact"` fuses them and sorts facet by facet.
_SCENE_ORDERS = ("parts", "exact")

#: What a part may still say for itself once the scene is drawn in one pass.
#: Colour, line weight and the fold threshold survive because a fused mesh
#: keeps its groups, and `colors=`, `stroke_widths=` and `creases=` are all per
#: group; the anchor keywords survive because they name points and never draw.
#: `crease` in particular is not a property of the pass at all -- it only
#: decides which of an already-computed pair of facets gets a stroke between
#: them -- and a 168-facet nucleus beside an 1,800-facet brain genuinely wants
#: its own angle.
#:
#: `style` is the interesting refusal. Fusing means one hidden-line pass over
#: one surface, and that pass hides an edge behind a part whether or not that
#: part is going to be painted -- so a part asking for `"lineart"` inside a
#: `"shaded"` scene would come out as a hole with nothing behind it: no fill of
#: its own, and no lines of whatever it stands in front of either. Opacity,
#: occlusion, `hidden`, `cull` and `sort` are the same argument in other
#: words: each is a property of the pass, and under `order="exact"` there is
#: one pass for the whole scene. `order="parts"` is where they all still work.
#:
#: The way out of every one of those refusals is `overlay=True`, which says
#: the part is not in the pass at all -- see `_fused`.
_FUSED_PART_KEYS = ("color", "colors", "crease", "stroke_width", "anchors",
                    "groups", "overlay")


def _fused(entries, shared: dict, fitted: View, pinned: Camera,
           size, whole: Mesh, name: str,
           claims: tuple[tuple[str, str], ...] = ()) -> Diagram:
    """The whole scene as one drawing, with a ghost node per part.

    Fusing is what makes depth exact: one mesh means one hidden-line pass and
    one facet sort, so a rod through a ring is settled where the two actually
    cross rather than by whose centre is nearer. The cost is that "part" stops
    being a unit of painting -- so the parts come back as outlines that draw
    nothing, and everything a caller does with a part by name (find it, anchor
    to it, clip an arrow on it, cite it in `through=`) goes on working against
    those.

    **`overlay=True` buys a part back out of the pass.** It is left out of the
    fused mesh, drawn as its own `model()` node in the scene's own projection,
    and painted after the fused drawing -- so it may set anything `model()`
    takes, `style`, `opacity`, `sort` and the rest, exactly as it could under
    `order="parts"`. What it costs is the thing fusing was bought for: an
    overlay is *always on top*. It does not hide the scene behind it and the
    scene does not hide it; the two are composited, not sorted. That is the
    right trade for the cases it exists for -- a ghosted case over a
    mechanism, a cutting plane, a highlighted part drawn in line art over a
    shaded assembly -- and the wrong one for anything that has to thread.
    Two overlays are painted in the order they were declared.
    """
    labelled: list[Mesh] = []
    colors = dict(shared.get("colors") or {})
    widths: dict[str, float] = {}
    folds: dict[str, float] = {}
    over = [bool(options.get("overlay")) for _, _, options in entries]
    if all(over):
        raise MeshError(
            "every part of this scene is overlay=True, so there is nothing "
            "left to fuse and nothing for the exact order to settle; "
            "order='parts' is what a scene of separately painted parts is")
    for on_top, (part, mesh, options) in zip(over, entries):
        ordering = sorted(set(options) & set(_ORDER_KEYS))
        if ordering:
            raise MeshError(
                f"part {part!r} sets {', '.join(ordering)}, which order='exact' "
                "has nowhere to put: there is no order between the parts to "
                "override, because depth is settled facet by facet across the "
                "whole scene. Use order='parts' if the paint order is yours to "
                "choose")
        if on_top:
            continue          # drawn as its own node below, and free to differ
        extra = sorted(set(options) - set(_FUSED_PART_KEYS))
        if extra:
            raise MeshError(
                f"part {part!r} sets {', '.join(extra)}, which order='exact' "
                f"cannot honour: the scene is drawn in one pass, so only "
                f"{', '.join(_FUSED_PART_KEYS)} may still differ between "
                f"parts. overlay=True takes {part!r} out of that pass and "
                f"draws it on top, where it may set whatever model() takes")
        own = options.get("color", shared.get("color"))
        heavy = options.get("stroke_width")
        fold = options.get("crease")
        by_group = options.get("colors") or {}
        # Namespaced, because two parts of an assembly will happily both call
        # a group "hole" and the fused mesh has only one set of group names.
        if mesh.groups:
            labelled.append(replace(
                mesh, groups=tuple(f"{part}/{g}" if g else part
                                   for g in mesh.groups),
                name=part, _derived={}))
            for group in mesh.group_names:
                chosen = by_group.get(group, own)
                if chosen is not None:
                    colors[f"{part}/{group}"] = chosen
                if heavy is not None:
                    widths[f"{part}/{group}"] = heavy
                if fold is not None:
                    folds[f"{part}/{group}"] = fold
        else:
            labelled.append(mesh.grouped(part))
            if own is not None:
                colors[part] = own
            if heavy is not None:
                widths[part] = heavy
            if fold is not None:
                folds[part] = fold

    look = {k: v for k, v in shared.items()
            if k not in ("color", "colors", "sort")}
    if widths:
        look["stroke_widths"] = widths
    if folds:
        look["creases"] = folds
    # Unnamed, and wrapped in a kind the lint rules know to look past. The
    # drawing is one node and the parts are nine, so a leader that clips the
    # membrane has to be reported against `membrane` -- something `through=`
    # can name -- and not against the single node that happens to paint the
    # whole stack.
    # Named, because `merge` hands the fused mesh the *first* part's name and
    # a node called `anode_end` that is really the whole stack would answer
    # `find("anode_end")` before the part does.
    origin = fitted.raw_bounds(whole).center
    fused_mesh = merge(labelled)
    # Sized as the scene, unless an overlay was taken out of it: then the
    # fused mesh is smaller than the scene and fitting it to the scene's width
    # would scale it up to fill it. Its share of the projection, carried to
    # its own centre, is the same arithmetic a painted part gets below.
    if any(over):
        body_box = fitted.raw_bounds(fused_mesh)
        sizing = _share_of(body_box, fitted.scale)
        shift = _in_scene(body_box, origin, fitted.scale).center
    else:
        sizing, shift = {"width": size[0], "height": size[1]}, None
    drawing = model(fused_mesh, view=pinned, name=f"{name}-body", sort="exact",
                    colors=colors, color=shared.get("color"), groups=False,
                    **sizing, **look)
    if shift is not None:
        drawing = drawing.placed(_translate(shift))
    body = Diagram(children=(drawing,), kind=FUSED_KIND)

    ghosts: list[Diagram] = []
    boxes: list[Rect] = []
    offsets: list[Vec2] = []
    drawn: list[Diagram] = []
    for on_top, (part, mesh, options) in zip(over, entries):
        box = _in_scene(fitted.raw_bounds(mesh), origin, fitted.scale)
        if on_top:
            settings = {key: value for key, value in {**shared, **options}.items()
                        if key not in _ORDER_KEYS and key != "overlay"}
            settings.update(_share_of(fitted.raw_bounds(mesh), fitted.scale))
            ghost = model(mesh, view=pinned, name=part, **settings)
            drawn.append(ghost.placed(_translate(box.center)))
            # A painted part is fitted to its own box and carried into place,
            # so its anchors are measured from its own centre.
            offsets.append(box.center)
        else:
            outline = _mesh_outline(mesh, fitted,
                                    crease=options.get(
                                        "crease", shared.get("crease", 30.0)),
                                    ridges=shared.get("ridges", True),
                                    smooth=shared.get("smooth"))
            carrier = _ghost(outline)
            ghost = Diagram(children=() if carrier is None else (carrier,),
                            kind=MODEL_KIND, name=part)
            _attach_anchors(ghost, mesh, fitted, options.get("anchors"),
                            options.get("groups", True), None)
            drawn.append(ghost)
            # A ghost is already drawn in the scene's own frame -- it was
            # outlined through the scene's fitted view rather than being
            # fitted to itself and carried into place -- so its anchors need
            # no shift, where a painted part's do.
            offsets.append(Vec2(0.0, 0.0))
        ghosts.append(ghost)
        boxes.append(box)

    # The body first, then the parts in declaration order: a ghost paints
    # nothing, so the only order this decides is the overlays', and theirs is
    # the order they were written in.
    node = Diagram(children=(body, *drawn), kind=MODEL_KIND, name=name)
    _attach_parts(node, entries, ghosts, boxes, offsets=offsets)
    _VIEWS[node.id] = fitted
    _MESHES[node.id] = whole
    fused_first = [i for i, on_top in enumerate(over) if not on_top]
    _SCENES[node.id] = ScenePaint(
        names=tuple(part for part, _, _ in entries),
        nodes=tuple(one.id for one in ghosts),
        meshes=tuple(mesh for _, mesh, _ in entries),
        # The fused parts have no order among themselves -- depth is settled
        # facet by facet inside them -- and the overlays come after all of
        # them, which is the whole of what `overlay=True` promises. They are
        # `declared` for the same reason a `draw_order=` part is: the author
        # chose the place, so the depth rule reads it rather than checking it.
        view=fitted,
        paint=tuple(fused_first + [i for i, on_top in enumerate(over) if on_top]),
        declared=frozenset(i for i, on_top in enumerate(over) if on_top),
        fused=True, claims=claims)
    return node


def _in_scene(box: Rect, origin: Vec2, scale: float) -> Rect:
    """One part's projected bounds, in the scene node's own millimetres.

    The scene is centred on the projected box of everything in it, so a part's
    place on the page is its own projected box measured from that centre and
    scaled. This is the rectangle the part's compass anchors come off, and its
    centre is where the part's node is placed -- so `scene.at("lid")` and
    `scene.at("lid.center")` are the same point by construction rather than by
    two pieces of arithmetic agreeing.
    """
    return Rect((box.x0 - origin.x) * scale, (box.y0 - origin.y) * scale,
                (box.x1 - origin.x) * scale, (box.y1 - origin.y) * scale)


def _paint_order(entries, depths: Sequence[float]) -> list[int]:
    """Which part is painted when: furthest centre first, then what was said.

    The depth order is the whole answer for nearly every scene, and the two
    ways of overriding it are there for the ones where the geometry is honest
    and the author still wants the other picture -- a cutaway, a ghosted case,
    a decal that has to read over the panel it is on.

    **`draw_order=` is a place in the queue, not a depth.** Parts without one
    take their place from depth, counting from zero at the back, so the two
    kinds of part are comparable: `draw_order=0` is behind everything the
    camera did not already put behind everything, and a number past the part
    count is in front of the lot. Ties break on the order the parts were
    written in, which is also what makes two runs paint identically.

    **`behind=`/`in_front_of=` name a neighbour** and are applied afterwards,
    in declaration order, each one lifting its part out of the queue and
    dropping it back beside the part it names. That is the spelling that
    survives a scene being edited: adding a tenth part does not renumber the
    statement that the nut goes in front of the plate.
    """
    count = len(entries)
    # Furthest first, and stable, so parts at the same depth keep the order
    # they were written in and two runs paint the scene identically.
    order = sorted(range(count), key=lambda i: (-depths[i], i))
    rank = {index: place for place, index in enumerate(order)}
    where = {part: i for i, (part, _, _) in enumerate(entries)}

    given: dict[int, int] = {}
    for i, (part, _, options) in enumerate(entries):
        said = [key for key in _ORDER_KEYS if options.get(key) is not None]
        if len(said) > 1:
            raise MeshError(
                f"part {part!r} sets {' and '.join(said)}; a part has one "
                "place in the paint order, so say it once")
        if options.get("draw_order") is not None:
            given[i] = int(options["draw_order"])
    if given:
        order = sorted(range(count), key=lambda i: (given.get(i, rank[i]), i))

    for i, (part, _, options) in enumerate(entries):
        for key in ("behind", "in_front_of"):
            other = options.get(key)
            if other is None:
                continue
            if other == part:
                raise MeshError(f"part {part!r} is {key}= itself")
            if other not in where:
                raise MeshError(
                    f"part {part!r} is {key}={other!r}, which is not a part of "
                    f"this scene; the parts are {tuple(where)}")
            order.remove(i)
            beside = order.index(where[other])
            order.insert(beside if key == "behind" else beside + 1, i)
    return order


def _claims(assert_order, names: Sequence[str]) -> tuple[tuple[str, str], ...]:
    """`assert_order=[("objective", "sample")]`, checked for spelling now.

    The claim itself is checked by `inklet.lint`, not here, and that is the
    point: a requirement worth writing down is one that has to keep holding
    while the figure is edited, so it belongs where the rest of the figure's
    correctness is reported rather than in an exception at build time. What
    *is* worth raising immediately is a part name with a typo in it, because
    an assertion about a part that does not exist would otherwise pass in
    silence.
    """
    out: list[tuple[str, str]] = []
    known = set(names)
    for claim in assert_order:
        pair = tuple(claim)
        if len(pair) != 2:
            raise MeshError(
                f"assert_order takes (front, back) pairs; got {claim!r}")
        for part in pair:
            if part not in known:
                raise MeshError(
                    f"assert_order names {part!r}, which is not a part of this "
                    f"scene; the parts are {tuple(names)}")
        if pair[0] == pair[1]:
            raise MeshError(
                f"assert_order says {pair[0]!r} is in front of itself")
        out.append((str(pair[0]), str(pair[1])))
    return tuple(out)


def _declared(entries) -> frozenset[int]:
    """Parts whose place in the paint order the author set for themselves."""
    return frozenset(
        i for i, (_, _, options) in enumerate(entries)
        if any(options.get(key) is not None for key in _ORDER_KEYS))


#: The compass points every part of a scene answers to, as fractions of its
#: own projected box. Written out rather than taken from `Diagram.anchor_point`
#: because these go on the *scene*, where the part is one rectangle among many
#: and there is no local box to read them off.
_COMPASS = {
    "center": (0.5, 0.5), "n": (0.5, 0.0), "s": (0.5, 1.0),
    "w": (0.0, 0.5), "e": (1.0, 0.5), "nw": (0.0, 0.0), "ne": (1.0, 0.0),
    "sw": (0.0, 1.0), "se": (1.0, 1.0),
}


def _attach_parts(node: Diagram, entries, parts: Sequence[Diagram],
                  boxes: Sequence[Rect],
                  offsets: Sequence[Vec2] | None = None) -> None:
    """Register every part's place on the scene: centre, compass, own anchors.

    A part used to contribute exactly one anchor to the scene it is in, its
    centre, so clearing a label off a slanted rod meant probing the rod's ends
    with `anchor3d` and doing the projected arithmetic by hand. The projected
    box is already computed -- it is what places the part -- so the eight
    compass points around it are free, and `scene.at("rod.ne")` is the thing
    that was being written out longhand.

    The part's own anchors come along under the same prefix, so a 3D point
    named on a part (`anchors={"tip": ...}`) is reachable from the scene as
    `scene.at("bolt.tip")` as well as from the part. They are registered last,
    so a part that names a point `"n"` wins over the compass -- the same rule
    `_attach_anchors` uses for a group against an explicit anchor.
    """
    for index, (part, _, _) in enumerate(entries):
        box = boxes[index]
        node.anchor(part, box.center)
        for name, (u, v) in sorted(_COMPASS.items()):
            node.anchor(f"{part}.{name}",
                        Vec2(box.x0 + u * box.width, box.y0 + v * box.height))
        shift = box.center if offsets is None else offsets[index]
        for name in sorted(parts[index].anchors):
            here = parts[index].anchors[name]
            node.anchor(f"{part}.{name}", Vec2(here.x + shift.x, here.y + shift.y))


def _share_of(box: Rect, scale: float) -> dict[str, float]:
    """The millimetres one part takes up in the scene's own projection.

    Width, unless the part has none: an edge-on plane projects to a vertical
    line, and the fit refuses to scale a mesh with no width. Height carries the
    same scale, so either answer places the part in the same spot.
    """
    if box.width > _FLAT:
        return {"width": box.width * scale}
    if box.height > _FLAT:
        return {"height": box.height * scale}
    raise MeshError(
        "a part of this scene projects to a single point, so it has no size "
        "to fit; rotate the camera off the degenerate axis")


#: Below this, in the camera's own units, a projected extent is not a size.
_FLAT = 1e-12


def scene_paint(node: Diagram) -> ScenePaint | None:
    """What a `scene()` is made of and the order it paints its parts in.

    None for anything this module did not build as a scene. `inklet.lint` reads
    it to compare the paint order against the camera; it is public because an
    author debugging a stack wants the same answer.
    """
    return _SCENES.get(node.id)


def parts_of(node: Diagram,
             where: Callable[[Diagram], bool] | None = None) -> tuple[Diagram, ...]:
    """A scene's parts, in the order they were declared, optionally filtered.

    The case this exists for is `through=`. A leader into a wireframe cage has
    to cross a rod of the cage -- unavoidable, not a mistake -- and saying so
    used to mean naming every rod at the call site, which is why all twelve
    edges of the unit cell in `stress/electro/cell.py` carry a name they are
    never otherwise used by. Now:

        inklet.link(tag, cage.find("atom"), kind="leader",
                 through=inklet.three.parts_of(cage, lambda p: "edge" in p.name))

    Citing the *whole* scene needs nothing from this at all -- `through=(cage,)`
    already exempts everything inside it, because the lint rules ask whether
    the crossed node is inside anything the link declared. This is for the
    middle case: the cage's rods but not the atom the arrow is meant to stop
    on.
    """
    paint = _SCENES.get(node.id)
    if paint is None:
        raise MeshError(
            f"{node.id} was not built by inklet.scene, so it has no parts")
    found = [node.find(part) for part in paint.names]
    return tuple(one for one in found if where is None or where(one))


def outline_of(part: Diagram | Mesh, view: View | None = None, *,
               crease: float = 30.0, ridges: bool = True,
               smooth: bool | float | None = None):
    """A part's projected outline: `((points, closed), ...)` in its own frame.

    Given a node, this is the curve `inklet.three` already computed for it and
    attached as the trace an arrow clips on -- read back out, so that a caller
    can measure it, clear a label off it, or draw along it. It works the same
    under `order="parts"`, where the part paints its own silhouette, and under
    `order="exact"`, where the part paints nothing and the outline is all it
    is. Coordinates are the node's own local millimetres, the frame
    `anchor_point` answers in.

    Given a `Mesh` and a framed `View` instead, it computes one: the form the
    scene machinery uses for a part that shares a projection with the rest of
    the scene rather than being fitted to itself.
    """
    if isinstance(part, Mesh):
        if view is None:
            raise MeshError(
                "outlining a mesh needs the view to project it through; pass "
                "the scene's own, or hand in the part's node instead")
        return _mesh_outline(part, view, crease=crease, ridges=ridges,
                             smooth=smooth)
    out: list[tuple[tuple[Vec2, ...], bool]] = []
    _gather_outline(part, IDENTITY, out)
    return tuple(out)


def _gather_outline(node: Diagram, into, out: list) -> None:
    """Every silhouette carrier under a node, in the node's local frame.

    The node's *own* transform is deliberately not applied: `anchor_point` and
    `local_bbox` both answer before it, and an outline that did not agree with
    them would be a trap rather than a convenience.
    """
    if node.kind == SILHOUETTE_KIND and isinstance(node.prim, PathPrim):
        for sub in node.prim.subpaths:
            out.append((tuple(into.apply(p) for p in sub.points), sub.closed))
    for child in node.children:
        _gather_outline(child, into @ child.transform, out)


def _scene_parts(parts) -> list[tuple[str, Mesh, Mapping[str, Any]]]:
    """`(name, mesh)`, `(name, mesh, options)` or a mapping, in one shape."""
    listed = list(parts.items() if isinstance(parts, Mapping) else parts)
    if not listed:
        raise MeshError("a scene needs at least one part")
    out: list[tuple[str, Mesh, Mapping[str, Any]]] = []
    seen: set[str] = set()
    for entry in listed:
        part, mesh, options = (tuple(entry) + ({},))[:3] if len(entry) < 3 else entry
        if not isinstance(mesh, Mesh):
            raise MeshError(
                f"part {part!r} is a {type(mesh).__name__}, not a Mesh; load or "
                "build it first -- a scene shares one camera, so it needs the "
                "geometry rather than a finished drawing")
        if part in seen:
            raise MeshError(
                f"two parts of this scene are called {part!r}; names are how a "
                "part is found again, so they have to be distinct")
        seen.add(part)
        settings = dict(options)
        # Placement is folded into the geometry here, before the camera is
        # fitted, and that is the only place it can go: a scene frames the
        # meshes it was handed and then asks each part for its own share of
        # that projection, so a part carried into place *inside* `model()`
        # would be drawn somewhere the scene had not made room for and placed
        # by the box it had before it moved.
        where = _placed(settings.pop("transform", None),
                        settings.pop("at", None), settings.pop("spin", None),
                        settings.pop("scale", None))
        if where is not None:
            mesh = mesh.transformed(where)
        out.append((part, mesh, settings))
    return out


# -- a labelled coordinate frame ------------------------------------------


def axes(*, width: float | str = 26.0,
         view: Camera | str | tuple[float, float] | None = "isometric",
         labels: Sequence[str] | None = ("x", "y", "z"),
         style: str = "shaded",
         length: float = 1.0,
         thickness: float = 1.0,
         gap: float | None = None,
         label_size: float | str | None = None,
         name: str = "axes",
         tolerance: float | None = DEFAULT_TOLERANCE,
         **options) -> Diagram:
    """Three arrows and their labels: the figure element every methods section
    needs and nobody wants to draw twice.

    The labels are real text, placed by projecting each arrow's tip through the
    same view the arrows were drawn with and pushing outward from the frame's
    origin. The group's envelope therefore includes the labels, so `width` sizes
    the *arrows* and the assembled node comes out a little larger -- the same
    way a box is bigger than the word inside it.

    `x`, `y`, `z` and `origin` are anchors on the result, so an arrow can be
    aimed at an axis: `fig.link(caption, frame.at("z"))`.

    `tolerance` is `solid`'s, and means the same thing here: how far the
    arrowheads' outlines may sit from a true circle, in millimetres on the
    page. `None` restores the builder's own segment count.
    """
    from .. import current_theme, label as make_label

    # Explicit tip anchors, overriding the ones the face groups would give.
    # A group's anchor is the centroid of its vertices, which for an arrow is
    # halfway along the shaft -- the middle of the thing, not the end of it,
    # and a label hung there sits on top of the arrow it names.
    tips = {"x": (length, 0.0, 0.0), "y": (0.0, length, 0.0),
            "z": (0.0, 0.0, length)}
    options.setdefault("anchors", tips)
    shape = {"length": length, "thickness": thickness}
    mesh = build_solid("axes", **shape)
    if tolerance is not None:
        # Same rule `solid` follows, and for the same reason: three arrowheads
        # at 26 mm want nine segments each, not the twenty a frame drawn at
        # 80 mm would.
        mesh = _refined("axes", shape, mesh, tolerance,
                        {**options, "width": width, "view": view})
    frame = model(mesh, width=width, view=view, style=style, name=name,
                  **options)
    if not labels:
        return frame

    theme = current_theme()
    clearance = theme.gap("xs") if gap is None else mm(gap)
    origin = frame.anchor_point("origin")
    parts: list[Diagram] = [frame]
    for axis, text in zip(("x", "y", "z"), labels):
        if not text:
            continue
        tip = frame.anchor_point(axis)
        glyph = make_label(text, size=label_size or theme.font_size_small)
        box = glyph.local_bbox
        away = tip - origin
        span = away.length
        # Push the label clear along the arrow's own direction on the page, by
        # the label's half-diagonal so a wide glyph clears as well as a tall
        # one. A degenerate axis -- one pointing straight at the camera -- has
        # no direction to push along, so it is left on the tip.
        step = clearance + 0.5 * (box.width ** 2 + box.height ** 2) ** 0.5
        offset = tip if span < 1e-9 else tip + away * (step / span)
        parts.append(glyph.placed(_translate(offset)))
    node = Diagram(children=tuple(parts), kind=MODEL_KIND, name=name)
    # The wrapper's transform is the identity, so the frame's local anchors are
    # already correct in the wrapper's frame. Copying them up means callers can
    # write `frame.at("x")` on the thing they were handed.
    for anchor, point in sorted(frame.anchors.items()):
        node.anchor(anchor, point)
    return node


def _translate(p: Vec2):
    from ..core.geom import Affine

    return Affine.translation(p.x, p.y)


# -- assembly -------------------------------------------------------------


def _assemble(result: Rendering, name: str) -> Diagram:
    children = [result.diagram]
    carrier = _carrier(result.silhouette)
    if carrier is not None:
        children.append(carrier)
    node = Diagram(children=tuple(children), kind=MODEL_KIND, name=name,
                   envelope_override=_extent(result))
    _VIEWS[node.id] = result.view
    return node


def _extent(result: Rendering) -> Envelope | None:
    """The model's own extent: where the projection went, not where ink went.

    A model measured off its paths is measured off `_bleed`'s work. The bleed
    grows every facet outward by fifteen microns along the mitre at each
    corner, which is how the hairline between two facets is closed without a
    sub-hairline stroke -- and the mitre reach depends on the corner's angle,
    so it is not a uniform fifteen microns but anything up to the mitre limit.
    Three things follow, and all three are wrong:

    * `inklet.solid("cube", width=40)` measured 40.04 mm. A fit that asked for
      forty millimetres got a node that was not forty millimetres wide.
    * A model's box depended on the *painting order*, by a micron. The exact
      sort dissolves facets into different paths, the corner at the extreme
      reaches out at a different angle, and a page holding a model re-centred
      -- `stress/three_figure.svg` moved 1,309 lines for about 200 real ones
      the last time the sort changed.
    * The bleed's own docstring promises it closes the crack "without
      measurably fattening the silhouette", and off the paths it did.

    So the node claims the projection instead. Every corner the renderer drew
    is one of these points or lies on a segment between two of them: facet
    corners are projected vertices, a cut corner is on the edge it cut, and the
    smooth outline's points are in the table too, because `smooth_silhouette`
    appends them. A convex hull of the lot is therefore a superset of the ink's
    geometry and, unlike the paths, is a fact about the model and the camera
    alone.

    Stroke width is still not in it -- nothing in this library measures ink --
    but that is a consistent policy rather than an accident of one code path.
    """
    if not result.points:
        return None
    return Envelope.from_points(result.points)


def _carrier(silhouette) -> Diagram | None:
    """The outline, as a path that draws nothing.

    No core primitive can contribute a trace without also carrying ink:
    `PhantomPrim` is the only inkless one and its trace is empty by design, so
    that padding never intercepts an arrow. The silhouette needs the opposite
    -- geometry that catches rays and paints nothing -- and the only way to
    express it today is a real `PathPrim` styled `fill="none" stroke="none"`.
    `inklet.assets` reached the same conclusion independently, which is the
    strongest evidence available that core is missing a primitive rather than
    that two authors were both being lazy.

    It is inert in the output: one `<path fill="none" stroke="none"/>`. And it
    is harmless to the arrows, because `Trace.exit` takes the *furthest*
    crossing, so an interior crease can never win over the outline.
    """
    subpaths = tuple(Subpath(points, closed)
                     for points, closed in silhouette if len(points) >= 2)
    if not subpaths:
        return None
    return Diagram(prim=PathPrim(subpaths, filled=False),
                   kind=SILHOUETTE_KIND).styled(fill="none", stroke="none")


def _ghost(silhouette) -> Diagram | None:
    """A part's outline in a fused scene: filled, and painting nothing.

    `_carrier` makes the same curve unfilled, which is right when the part is
    also painted right there -- an unfilled path is not a region, and the bbox
    rules skip it on purpose. Here the part is *not* painted where it stands,
    so this outline is the only thing on the page that is the part, and it has
    to answer as a region: a label sitting on the anode plate has to be an
    overlap with `anode_end`, and a leader through the membrane has to be a
    crossing of `membrane`. It still draws nothing.
    """
    subpaths = tuple(Subpath(points, closed)
                     for points, closed in silhouette if len(points) >= 2)
    if not subpaths:
        return None
    return Diagram(prim=PathPrim(subpaths, filled=True),
                   kind=SILHOUETTE_KIND).styled(fill="none", stroke="none")


def _attach_anchors(node: Diagram, mesh: Mesh, view: View,
                    anchors: Mapping[str, Sequence[float]] | None,
                    groups: bool, matrix: Mat4 | None) -> None:
    """Project named 3D points into the node's *local* millimetres.

    Group anchors first, so an explicit `anchors=` entry of the same name wins.
    Both are registered in sorted order, which costs nothing and means two runs
    build the anchor dict identically.
    """
    if groups and mesh.groups:
        for group in mesh.group_names:
            node.anchor(group, view.project(mesh.group_center(group)).point)
    for anchor in sorted(anchors or {}):
        point = _as_vec3(anchors[anchor], anchor)
        if matrix is not None:
            # The author gave coordinates in the file's own frame, so the
            # up-axis fix has to be applied to the anchor as well as to the
            # geometry -- otherwise "the tip" ends up ninety degrees away.
            point = matrix.apply(point)
        node.anchor(anchor, view.project(point).point)


def _as_points(point, what: str) -> list[Vec3]:
    """One point or several, told apart by whether the first item is a number.

    Ambiguous only for an empty sequence, which is an error either way, and
    for a three-point run written as a flat list of nine numbers, which is not
    a thing anyone writes.
    """
    if isinstance(point, Vec3):
        return [point]
    items = list(point)
    if not items:
        raise MeshError(f"anchor {what!r} was given no points")
    if isinstance(items[0], (int, float)):
        return [_as_vec3(items, what)]
    return [_as_vec3(one, what) for one in items]


#: How far either side of the grid's own depth a point still counts as being
#: the surface in that cell. The grid samples one depth per cell and a surface
#: seen edge-on crosses several cells' worth of depth inside one cell, so a
#: tolerance is not optional; three cells' width is under a millimetre on a
#: figure-sized panel and is well inside the width of a leader's own tip.
_SLACK = 3.0


def _as_vec3(point: Sequence[float], what: str) -> Vec3:
    if isinstance(point, Vec3):
        return point
    values = tuple(point)
    if len(values) != 3:
        raise MeshError(
            f"anchor {what!r} needs three coordinates, got {len(values)}")
    return Vec3(float(values[0]), float(values[1]), float(values[2]))


def _placed(transform: Mat4 | None, at, spin, scale) -> Mat4 | None:
    """`at`/`spin`/`scale` folded onto an explicit `transform=`.

    The author's own matrix goes first, because it is written in the model's
    own frame -- the frame the file was exported in -- while the three
    keywords are about where the finished solid stands in the scene. Composing
    them the other way round would make `at=` mean "and then whatever the
    transform does to that point", which is not what anyone writes it for.
    """
    stand = placement(at, spin, scale)
    if stand is None:
        return transform
    return stand if transform is None else stand @ transform


def _orientation(up_axis: str, transform: Mat4 | None) -> Mat4 | None:
    key = up_axis.strip().lower()
    if key not in _UP_ROTATION:
        raise MeshError(
            f"up_axis must be one of {tuple(sorted(_UP_ROTATION))}, got {up_axis!r}")
    spin = _UP_ROTATION[key]
    fix = None if spin is None else Mat4.rotation(spin[0], spin[1])
    if transform is None:
        return fix
    # The author's transform is expressed in the model's own frame, so it
    # applies before the up-axis correction, not after.
    return transform if fix is None else fix @ transform


def _size(width: float | str | None,
          height: float | str | None) -> tuple[float | None, float | None]:
    if width is None and height is None:
        return (DEFAULT_WIDTH, None)
    return (None if width is None else mm(width),
            None if height is None else mm(height))
