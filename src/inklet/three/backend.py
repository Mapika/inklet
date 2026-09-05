"""The render contract, and the one implementation that needs nothing installed.

A backend turns geometry into ink. It is handed a `Request` -- a mesh, a
camera, a size in millimetres and a `Look` -- and returns a `Rendering`:

``diagram``
    A `core.Diagram` of paths in **local millimetres, centred on the node's own
    origin**, exactly like any other primitive in inklet. No transform on the root;
    the authoring layer owns placement.
``silhouette``
    The outer boundary of the projection, as `(points, closed)` chains in the
    same local millimetres. This is what arrows clip against, so it must be the
    *object's* outline and not its bounding box. A backend that cannot produce
    one returns `()` and the authoring layer falls back to the convex hull of
    the drawn ink.
``view``
    The fitted `View` that produced the drawing. Not optional. Named 3D anchors
    are projected through it after the fact, and an arrow that points at "the
    tip of the probe" is the entire reason this package produces vectors
    instead of a raster -- a backend that will not say where a 3D point landed
    cannot support that, whatever else it draws.

Backends are registered by name, following `inklet.assets.cutout`: a name is the
only thing that can be recorded, printed in a report, or put in a cache key.

`"builtin"` is the default rather than `"auto"`, on purpose. `auto` picks the
best backend installed, which means a figure can render differently on two
machines -- fine when you ask for it, wrong as a default for a library whose
contract is byte-identical output.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Callable

from ..core.diagram import Diagram
from ..core.geom import Vec2
from ..core.prims import PathPrim, Subpath
from ..themes.color import mix
from .camera import Camera, View
from .edges import (
    BOUNDARY, CREASE, SILHOUETTE, SMOOTH_CEILING, chain_edges, facing_faces,
    feature_edges, smooth_silhouette,
)
from .hlr import polylines, visible_runs
from .linalg import Vec3
from .mesh import Mesh, MeshError
from .order import box_of as _box_of, cells_of as _cells_of, overlaps
from .shade import (DEFAULT_LEVELS, DEFAULT_LIFT, DEFAULT_LIGHT,
                    DEFAULT_SHADE, dissolve, sorted_facets, tint)

__all__ = [
    "Look", "Request", "Rendering", "STYLES", "SHADINGS", "SORTS", "TOON",
    "register_backend", "backends", "available_backends", "render",
    "FACETS_KIND", "OUTLINE_KIND", "CREASE_KIND", "INK_KIND", "outline_of",
]

#: `lineart` inks the feature edges and nothing else. `solid` fills the facets
#: and nothing else. `shaded` does both, which is what most methods figures
#: want. `wireframe` draws every edge with no hidden-line removal -- honest
#: about the tessellation, and occasionally the point.
STYLES = ("lineart", "shaded", "solid", "toon", "wireframe")

#: What `style="toon"` supplies for the four numbers an author usually does not
#: want to think about. Three bands rather than twenty, because the whole point
#: of a toon is that the eye can count the tones; smooth shading rather than
#: flat, because with only three bands a staircased boundary *is* the drawing;
#: and a ramp pulled in from the line-art defaults at both ends, so those three
#: bands are told apart at a glance without any of them going dark enough to
#: compete with the ink. Anything the author states themselves wins.
TOON = MappingProxyType({"shading": "smooth", "levels": 3,
                         "lift": 0.55, "shade": 0.42})

INK_KIND = "model-ink"
FACETS_KIND = "model-facets"
OUTLINE_KIND = "model-outline"
CREASE_KIND = "model-crease"

# Creases carry less weight than the outline. Roughly five-eighths, which is
# the ratio between a technical pen's 0.25 and 0.15 nibs -- enough that the
# silhouette reads as the object's edge and the interior folds recede, not so
# little that the folds drop out when the figure is reduced on the page.
#: How a facet gets its tone. See `Look.shading`.
SHADINGS = ("flat", "smooth")

#: How the facets are put in painting order. See `Look.sort`.
SORTS = ("auto", "depth", "exact")

_CREASE_RATIO = 0.62

# `Envelope.union` and `Trace.union` each wrap two closures in a third, so a
# node with N siblings costs N stack frames every time its extent is asked for,
# and `PathPrim.trace` does the same per subpath. A shaded sphere is a few
# hundred of both, and 986 frames into `hstack` Python gives up -- which is how
# these two constants were arrived at, not by taste. Chunking the subpaths and
# nesting the chunks eight-wide turns O(N) frames into O(8 log8 N), preserves
# depth-first paint order exactly, and costs a handful of extra `<g>` elements
# that a designer opening the file in Illustrator will read as sensible
# grouping. The right fix is an iterative union in core; this is the one
# available from outside it.
_MAX_SUBPATHS = 64
_FANOUT = 8

# Adjacent filled polygons antialias against each other and leave a
# half-covered hairline where they meet. Growing every facet outward by this
# many millimetres makes them overlap instead. Chosen an order of magnitude
# under the finest line any press will hold, so it closes the crack without
# measurably fattening the silhouette. A matching stroke would do the same job
# but would be a sub-hairline stroke, which the linter is right to complain
# about and which some renderers snap up to a device pixel.
_FACET_BLEED = 0.015


@dataclass(frozen=True)
class Look:
    """Everything about how a mesh is drawn, with no geometry in it."""

    style: str = "lineart"
    #: Dihedral angle, in degrees, past which an interior fold is inked.
    crease: float = 30.0
    #: Ink the sharpest fold across each fold rather than every fold sharper
    #: than `crease`. On, because a rounded corner is a fan of facets whose
    #: dihedrals climb through any threshold and back, and a threshold inside
    #: that fan draws a band of near-parallel lines instead of an edge.
    ridges: bool = True
    #: Remove hidden lines. Off is faster and occasionally wanted -- an
    #: x-ray of an assembly is a legitimate figure.
    hidden: bool = True
    #: Force back-face culling on or off. None asks the mesh: closed surfaces
    #: are culled, open ones are not.
    cull: bool | None = None
    #: Put the outline on the surface the facets stand for rather than on the
    #: facets themselves, wherever the mesh is smooth enough to say what that
    #: surface is. On, because the facet outline of a near-tangent surface is
    #: not a slightly rough version of the right answer -- it is a zig-zag
    #: through the interior that reads as hatching. See `smooth_silhouette`.
    #: `None` takes the fold threshold from `crease`, capped at a right angle:
    #: the author has already said where this model's real edges are and does
    #: not need to say it twice. A number states it separately; `False` puts
    #: the outline back on the facets.
    smooth: bool | float | None = None
    #: `"flat"` gives every facet one tone, `"smooth"` cuts the bands out of
    #: the vertex-normal field instead, so a band boundary is the isoline it
    #: stands for rather than the staircase of whichever triangles tipped
    #: across the step. Flat by default, and the reason is cost rather than
    #: taste: flat shading pays nothing for extra `levels` -- a facet has one
    #: tone however finely the ramp is cut -- while smooth shading pays per
    #: level, because every step boundary a triangle spans is another polygon
    #: with its own outline. It earns that on a coarse curved body, where the
    #: staircase is the thing you see; it is close to a wash on a mesh already
    #: fine enough to hide one. Uses the same threshold as `smooth`.
    shading: str = "flat"
    #: `"depth"` paints the facets in order of their mean depth; `"exact"` asks
    #: each overlapping pair which is nearer and cuts the pairs that have no
    #: single answer; `"auto"`, the default, is exact up to
    #: `AUTO_EXACT_FACETS` faces and depth above.
    #:
    #: Auto rather than depth because the two orders *agree* on everything a
    #: mean depth can rank -- a convex body has no overlapping front faces at
    #: all -- so what the threshold buys is not a different picture of the
    #: usual object, it is the unusual one coming out right: a bore painted
    #: over the wall it goes through, a horseshoe curling over itself. Auto
    #: rather than exact because the exact order is a fixed *multiple* of the
    #: render (about 1.3x), which is nothing on the meshes a drawn object is
    #: made of and seconds on a scanned one. See `shade.sorts_exactly`.
    sort: str = "auto"
    #: How opaque the facets are, 0..1. 1 is off and is the default. Applies to
    #: the *fills* and not to the inked edges, because that is the ghosting a
    #: technical illustrator draws -- a surface you can see the cartoon through,
    #: with a silhouette that still reads -- and because the other one is
    #: already available from outside as `node.styled(opacity=...)`.
    #:
    #: Emitted once, on the group holding the facets, rather than per path. SVG
    #: composites a group at its opacity *after* drawing it, so the facets
    #: inside cannot darken each other where they overlap; per-path opacity
    #: would put a dark seam along every join the bleed makes.
    #:
    #: Transparency is what makes a wrong painting order visible: behind an
    #: opaque facet nobody can see it. See `sort` and `cull`, both of which
    #: this raises the stakes on.
    opacity: float = 1.0
    ink: str | None = None            # None -> the theme's ink
    color: str | None = None          # facet base; None -> the theme's accent
    #: Per-group facet colours, overriding `color` for faces in a named group.
    #: Sorted pairs rather than a dict so a look stays hashable.
    #:
    #: This is what lets *one* mesh be many colours. Without it a two-coloured
    #: object has to be two meshes, and two meshes are depth-sorted against
    #: each other as wholes -- fine for a lid on a box, wrong the moment the
    #: parts interleave, which is the normal case for anything folded.
    colors: tuple[tuple[str, str], ...] = ()
    stroke_width: float | None = None  # None -> the theme's stroke
    #: Per-group line weights, overriding `stroke_width` for the edges of the
    #: faces in a named group. Sorted pairs, for the same reason as `colors`.
    #:
    #: The point of it is `scene(order="exact")`, where the whole assembly is
    #: one drawing pass and a part can no longer set its own weight by being
    #: its own node. Weight is how a technical illustration says which part the
    #: figure is about, so losing it to fusing loses something real. An edge
    #: takes the weight of the first of its faces that names one, and edges
    #: with no named group keep `stroke_width`.
    stroke_widths: tuple[tuple[str, float], ...] = ()
    #: Per-group fold thresholds, overriding `crease` for the edges of the
    #: faces in a named group. Sorted pairs, for the same reason as `colors`.
    #:
    #: Same argument as `stroke_widths`, and the same place it bites: under
    #: `scene(order="exact")` the assembly is one mesh, and one threshold then
    #: has to serve a 168-facet organic nucleus and an 1,800-facet brain. At
    #: the angle the tissue needs, every second edge of the nucleus creases and
    #: it reads as cracked rather than rounded. An edge takes the stricter of
    #: its two faces' angles, so a part can only ever quieten its own folds.
    #:
    #: It moves the *inked* folds and nothing else. Where the mesh stands for a
    #: smooth surface is still one question with one answer, `smooth`, because
    #: the outline and the shading have to agree about it.
    creases: tuple[tuple[str, float], ...] = ()
    #: Per-group ridge suppression, overriding `ridges` for the folds of the
    #: faces in a named group. Sorted pairs, for the same reason as `colors`.
    #:
    #: One scene can need it both ways, and a sectioned solid is the case.
    #: `ridges=True` is right for a surface -- a fold is a fan of facets and
    #: only its crest should be inked -- and wrong for the rim where the knife
    #: went, because there the fold *is* the line and inking one edge of it
    #: draws a dash trailing off into nothing. Without this the author buys the
    #: rim with the surface's detail, by raising the surface threshold until
    #: ridges-off stops fragmenting it.
    #:
    #: An edge is suppressed only when *both* its faces asked for it, which is
    #: the opposite of the stricter-of-two rule `creases` takes. See
    #: `edges._creases` for why: a group's ridges-off has nothing to act on
    #: except its own border.
    ridge_groups: tuple[tuple[str, bool], ...] = ()
    light: Vec3 = DEFAULT_LIGHT
    levels: int = DEFAULT_LEVELS
    #: Fade the far end of the scene toward paper by this much, 0..1. Shading
    #: says which way a surface faces; only this says which of two surfaces is
    #: in front. Off by default because a single convex solid does not need it.
    depth_cue: float = 0.0
    #: Darken the parts of the surface that sit in a hollow, 0..1. The other
    #: half of the same sentence: a light says which way a surface faces, the
    #: cue says which of two surfaces is nearer, and only this says whether a
    #: surface is *inside* something. Off by default because a convex solid has
    #: no hollows and would pay a rasterisation for nothing. See `occlude`.
    occlusion: float = 0.0
    #: How far the lit end of the ramp is lifted toward paper, and the dark end
    #: pushed toward ink. The defaults are a line-art house style -- pale, so
    #: that inked edges stay the strongest thing on the page. A figure whose
    #: subject *is* the shaded body wants a lift nearer a half.
    lift: float = DEFAULT_LIFT
    shade: float = DEFAULT_SHADE
    #: Backend-specific settings. Sorted pairs rather than a dict so that a
    #: look is hashable and prints the same way twice.
    options: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.style not in STYLES:
            raise MeshError(
                f"unknown style {self.style!r}; expected one of {', '.join(STYLES)}")
        if self.shading not in SHADINGS:
            raise MeshError(
                f"unknown shading {self.shading!r}; expected one of "
                f"{', '.join(SHADINGS)}")
        if self.sort not in SORTS:
            raise MeshError(
                f"unknown sort {self.sort!r}; expected one of "
                f"{', '.join(SORTS)}")
        if not 0.0 <= self.opacity <= 1.0:
            raise MeshError(
                f"opacity is a fraction, 0..1; got {self.opacity}")
        if not 0.0 <= self.occlusion <= 1.0:
            raise MeshError(
                f"occlusion is a fraction of the ramp, 0..1; "
                f"got {self.occlusion}")

    def option(self, name: str, default: Any = None) -> Any:
        for key, value in self.options:
            if key == name:
                return value
        return default


@dataclass(frozen=True)
class Request:
    """What a backend is asked to draw."""

    mesh: Mesh
    camera: Camera
    width: float | None = None
    height: float | None = None
    look: Look = field(default_factory=Look)


@dataclass(frozen=True)
class Rendering:
    """What a backend gives back. See the module docstring for the contract."""

    diagram: Diagram
    silhouette: tuple[tuple[tuple[Vec2, ...], bool], ...]
    view: View
    backend: str = "builtin"
    #: Every page point the projection produced, for the node to claim as its
    #: extent instead of measuring the paths it drew. `None` leaves the
    #: measurement to the paths, which is what a backend that does not project
    #: in millimetres has to do.
    #:
    #: The distinction is not pedantry: `_bleed` grows every facet outward by
    #: `_FACET_BLEED` to close the hairlines between them, and a bled corner is
    #: a point the model does not have. Measured off the paths, a 40 mm model
    #: is 40.04 mm wide, and *which* corner reaches furthest depends on how the
    #: facets dissolved -- so the same object measured a micron differently
    #: under the two painting orders and re-flowed every page it sat on. See
    #: `_extent`.
    points: tuple[Vec2, ...] | None = None


# -- the registry ---------------------------------------------------------

BackendFn = Callable[[Request], Rendering]

_BACKENDS: dict[str, tuple[BackendFn, int, Callable[[], bool]]] = {}


def register_backend(name: str, handler: BackendFn, *, priority: int = 0,
                     available: Callable[[], bool] | None = None) -> None:
    """Add a renderer.

    `handler(request)` returns a `Rendering` obeying the module contract.
    `priority` orders `"auto"`, highest first. `available()` is checked before
    `"auto"` picks it and should be cheap -- a `shutil.which`, not a subprocess
    -- because it runs on every render that asks for `"auto"`.
    """
    _BACKENDS[name] = (handler, priority, available or (lambda: True))


def backends() -> tuple[str, ...]:
    """Every registered name, sorted. Deterministic for printing and testing."""
    return tuple(sorted(_BACKENDS))


def available_backends() -> tuple[str, ...]:
    """Those whose dependencies are actually present, sorted."""
    return tuple(sorted(n for n, (_, _, ok) in _BACKENDS.items() if ok()))


def _resolve(name: str) -> tuple[str, BackendFn]:
    if name == "auto":
        ranked = sorted(
            ((-priority, key) for key, (_, priority, ok) in _BACKENDS.items() if ok()))
        if not ranked:
            raise MeshError("no render backend is available at all")
        chosen = ranked[0][1]
        return chosen, _BACKENDS[chosen][0]
    entry = _BACKENDS.get(name)
    if entry is None:
        raise MeshError(
            f"unknown render backend {name!r}; registered backends are "
            f"{backends()}, of which {available_backends()} are available here"
        )
    return name, entry[0]


def render(request: Request, backend: str = "builtin") -> Rendering:
    """Draw a mesh with the named backend. `"auto"` picks the best installed."""
    name, handler = _resolve(backend)
    result = handler(request)
    if not isinstance(result, Rendering):
        raise MeshError(
            f"render backend {name!r} returned {type(result).__name__}, not a "
            "Rendering; see inklet.three.backend for the contract"
        )
    return replace(result, backend=name)


# -- the built-in renderer ------------------------------------------------


def _theme():
    """Late import: `inklet` imports this package, never the other way round."""
    from .. import current_theme

    return current_theme()


def _builtin(request: Request) -> Rendering:
    """Project, find the feature edges, remove what is hidden, ink the rest."""
    mesh, look = request.mesh, request.look
    if mesh.is_empty:
        raise MeshError("there is nothing to render: the mesh has no faces")

    view = request.camera.frame(mesh, request.width, request.height)
    points, depths = view.project_all(mesh.vertices)
    facing = facing_faces(mesh, view)
    features = feature_edges(mesh, view, facing=facing,
                             ridges=_ridge_flags(mesh, look),
                             crease_degrees=_crease_angles(mesh, look))
    on_surface: dict[tuple[int, int], tuple[int, ...]] = {}
    # The angle at which this mesh stops standing for a smooth surface: one
    # number, read once, handed to both halves. Where the surface is curved is
    # a fact about the model, not about the outline, so if the outline and the
    # shading were told separately they could disagree, and the disagreement
    # would show as a band boundary crossing an inked edge. `smooth=` and
    # `shading=` each decide only whether their own half acts on it.
    smooth_degrees = (float(look.smooth)
                      if look.smooth is not None
                      and not isinstance(look.smooth, bool)
                      else min(look.crease, SMOOTH_CEILING))
    if look.smooth is not False and look.style != "wireframe":
        smoothed = smooth_silhouette(mesh, view, features, points, depths,
                                     smooth_degrees=smooth_degrees)
        features, points = smoothed.edges, smoothed.points
        depths, on_surface = smoothed.depths, smoothed.adjacency

    theme = _theme()
    ink = look.ink or theme.ink
    weight = look.stroke_width if look.stroke_width is not None else theme.stroke
    children: list[Diagram] = []

    if look.style in ("solid", "shaded", "toon"):
        children.extend(_facet_nodes(
            mesh, view, points, depths, facing, look, theme,
            smooth_degrees if look.shading == "smooth" else None))
    if look.style != "solid":
        children.extend(
            _line_nodes(mesh, view, features, points, depths, facing, look, ink,
                        weight, on_surface))

    silhouette = _silhouette(mesh, features, points)
    node = Diagram(children=tuple(children), kind=INK_KIND)
    return Rendering(node, silhouette, view, points=tuple(points))


def _crease_angles(mesh: Mesh, look: Look) -> float | list[float]:
    """One fold threshold for the mesh, or one per face when a group asks.

    A face takes its own group's angle and every other face takes `crease` --
    the rule `stroke_widths` already follows for line weight, so a fused scene
    says both the same way.
    """
    if not look.creases or not mesh.groups:
        return look.crease
    by_group = dict(look.creases)
    return [by_group.get(group, look.crease) for group in mesh.groups]


def _ridge_flags(mesh: Mesh, look: Look) -> bool | list[bool]:
    """One ridge rule for the mesh, or one per face when a group asks.

    The same shape as `_crease_angles`, and said the same way for the same
    reason: under `scene(order="exact")` the assembly is one mesh, so a part
    can no longer set this by being its own node.
    """
    if not look.ridge_groups or not mesh.groups:
        return look.ridges
    by_group = dict(look.ridge_groups)
    return [by_group.get(group, look.ridges) for group in mesh.groups]


def _line_nodes(mesh: Mesh, view: View, features, points, depths, facing,
                look: Look, ink: str, weight: float,
                on_surface=None) -> list[Diagram]:
    """The outline and the creases, as two nodes at two weights."""
    if look.style == "wireframe":
        # Every edge, no visibility test: the tessellation is the subject.
        chains = chain_edges(mesh.edges)
        return _ink_node(
            [(tuple(points[i] for i in chain), closed) for chain, closed in chains],
            OUTLINE_KIND, ink, weight * _CREASE_RATIO)

    if look.hidden:
        runs, _ = visible_runs(mesh, view, features, points, depths, facing,
                               cull=look.cull, on_surface=on_surface)
    else:
        runs = _all_runs(features)

    # Creases are floored at the theme's own hairline: below that a line does
    # not survive the press, and a crease that drops out is worse than one
    # drawn at the same weight as the outline.
    hairline = _theme().hairline
    nodes = []
    for own, subset in _by_weight(mesh, features, runs, look, weight,
                                  on_surface):
        nodes += _ink_node(
            polylines(features, subset, points, (SILHOUETTE, BOUNDARY)),
            OUTLINE_KIND, ink, own)
        nodes += _ink_node(polylines(features, subset, points, (CREASE,)),
                           CREASE_KIND, ink,
                           max(own * _CREASE_RATIO, hairline))
    return nodes


def _by_weight(mesh: Mesh, features, runs, look: Look, weight: float,
               on_surface):
    """The visible runs split into one bucket per line weight.

    One bucket, the whole drawing, unless `stroke_widths` names a group -- the
    fused-scene case, where the parts share a drawing pass and weight is the
    only way left to say which of them the figure is about. Splitting before
    chaining rather than after is what keeps a part's outline one stroke: a
    chain that spanned two weights could only be drawn at one of them.
    """
    by_group = dict(look.stroke_widths)
    if not by_group or not mesh.groups:
        return [(weight, runs)]
    owners = mesh.edge_faces
    groups = mesh.groups
    found: dict[tuple[int, int], float] = {}
    buckets: dict[float, list] = {}
    for run in runs:
        key = features[run.edge].key
        own = found.get(key)
        if own is None:
            faces = owners.get(key) or (on_surface or {}).get(key) or ()
            own = weight
            for face in faces:
                named = by_group.get(groups[face])
                if named is not None:
                    own = named
                    break
            found[key] = own
        buckets.setdefault(own, []).append(run)
    return sorted(buckets.items())


def _all_runs(features):
    from .hlr import VisibleRun

    return [VisibleRun(i, e.kind, 0.0, 1.0) for i, e in enumerate(features)]


def _ink_node(chains, kind: str, ink: str, weight: float) -> list[Diagram]:
    subpaths = [Subpath(pts, closed) for pts, closed in chains if len(pts) >= 2]
    if not subpaths:
        return []
    node = _grouped([
        Diagram(prim=PathPrim(tuple(subpaths[i:i + _MAX_SUBPATHS]), filled=False),
                kind=kind)
        for i in range(0, len(subpaths), _MAX_SUBPATHS)
    ], kind)
    return [node.styled(fill="none", stroke=ink, stroke_width=weight,
                        stroke_linecap="round", stroke_linejoin="round")]


def _grouped(nodes: list[Diagram], kind: str) -> Diagram:
    """Nest a flat list into a shallow tree, keeping depth-first order.

    Order is preserved because every group holds a *contiguous* slice, and the
    renderer walks depth-first -- so the painter's algorithm still paints in
    exactly the sequence it was handed.
    """
    if len(nodes) == 1:
        return nodes[0]
    level = nodes
    while len(level) > _FANOUT:
        level = [Diagram(children=tuple(level[i:i + _FANOUT]), kind=kind)
                 for i in range(0, len(level), _FANOUT)]
    return Diagram(children=tuple(level), kind=kind)


def _facet_nodes(mesh: Mesh, view: View, points, depths, facing,
                 look: Look, theme, smooth_degrees=None) -> list[Diagram]:
    """Filled polygons, furthest first, same-tone facets gathered into paths."""
    facets = sorted_facets(mesh, view, points, depths, facing, cull=look.cull,
                           light=look.light, levels=look.levels,
                           depth_cue=look.depth_cue,
                           smooth_degrees=smooth_degrees, sort=look.sort,
                           occlusion=look.occlusion)
    if not facets:
        return []
    base = look.color or theme.accent
    palette = dict(look.colors)
    nodes = [_facet_node(subpaths, _fill(tone, cue, colour, theme, look))
             for (tone, cue, colour), subpaths in
             _tone_runs(facets, palette, base)]
    group = _grouped(nodes, FACETS_KIND)
    if look.opacity < 1.0:
        group = group.styled(opacity=look.opacity)
    return [group]


def _fill(tone: float, cue: float, base: str, theme, look: Look) -> str:
    """A facet's colour: its tone on the theme's ramp, then faded for distance.

    Cue is applied *after* the tone rather than folded into it, because the two
    say different things. Tone moves along the object's own ramp and keeps the
    hue; cue moves toward paper and takes the hue with it, which is what makes
    a far-away part recede instead of merely darkening.
    """
    colour = tint(tone, base, theme.paper, theme.ink,
                  lift=look.lift, shade=look.shade)
    return mix(colour, theme.paper, cue) if cue else colour


# The occlusion grid `_tone_runs` merges against. A few cells per facet: fine
# enough that the exact test below is only asked about facets that are really
# near each other, coarse enough that a facet does not have to be written into
# fifty cell lists.
_MERGE_CELLS_PER_FACET = 0.25
# How far back a cell's history is searched before giving up and closing the
# run anyway. A busy cell in a deep fold can accumulate hundreds of entries,
# and this scan is the one part of the merge that could go quadratic. Closing
# early costs a path; it can never cost correctness.
_MERGE_SCAN = 64
# Two facets closer than this are treated as not overlapping. It has to exceed
# `_FACET_BLEED`, because the bleed is what makes edge-sharing neighbours
# overlap at all, and the sliver it creates is a hundredth of a millimetre
# wide -- far under any press's resolution, so which of the two colours wins
# inside it is not a fact about the drawing.
_MERGE_TOUCH = _FACET_BLEED * 1.5


def _tone_runs(facets, palette: dict[str, str] | None = None, base: str = ""
               ) -> list[tuple[tuple[float, float, str], list[Subpath]]]:
    """The facets as paths: `_gather_runs` decides, `_run_subpaths` draws."""
    return [(key, _run_subpaths(members))
            for key, members in _gather_runs(facets, palette, base)]


def _gather_runs(facets, palette: dict[str, str] | None = None, base: str = ""
                 ) -> list[tuple[tuple[float, float, str], list]]:
    """Gather the facets into as few paths as the picture will allow.

    Painter's order only constrains facets that actually *overlap*: two
    triangles on opposite sides of the drawing may be painted in either order
    with the same result, and so may two that merely share an edge. Facets of
    one tone are one colour, so their order among themselves never matters
    either. Together those mean a facet can join an earlier run of its own tone
    whenever nothing of a different tone that would paint between them overlaps
    it.

    That is worth a great deal on a real mesh. Sorting by depth interleaves the
    tones -- a shaded cow's facets alternate light and dark all the way down
    the sort -- so merging only *consecutive* equal tones barely merges
    anything: 5856 facets came out as 5100 paths. Merging across the gaps takes
    the same drawing to a few dozen, and a 2.4 MB figure to a fraction of that.

    The overlap test is a grid to find candidates and separating axes to
    decide. Both are sound in the same direction: a separating axis proves two
    polygons are apart, and failing to find one is treated as overlap. So the
    merge can only ever be too cautious, which costs a path, never too
    eager, which would cost the picture.

    Returns `(key, facets)` in the order the paths must be emitted, which is
    the order their first facets appear in. The key is tone *and* depth cue,
    since both decide the fill and only facets of one fill may be reordered.
    """
    look_up = palette or {}
    keys = [(facet.tone, facet.cue, look_up.get(facet.group, base))
            for facet in facets]
    # The same fill as a small integer, because the scan below asks "is this
    # my fill?" once per history entry it walks past -- a few hundred thousand
    # times on a protein -- and an int compares in one op where the key is a
    # float, a float and a colour string.
    numbered: dict[tuple[float, float, str], int] = {}
    fills = [numbered.setdefault(key, len(numbered)) for key in keys]
    # The separating-axis test runs about two hundred thousand times on a
    # protein and reads four numbers per corner each time. Unpacking `Vec2`
    # once here rather than on every read is worth a fifth of the render.
    # A list comprehension rather than a generator: 3.12 inlines the first and
    # builds a frame per facet for the second, and there are 66,000 facets.
    corners = [tuple([(p.x, p.y) for p in facet.points]) for facet in facets]
    # Bounding boxes off the unpacked corners, in one pass each. `box_of`
    # walks the points twice through two more comprehensions, and this is the
    # only caller for which that shows up.
    boxes = []
    for points in corners:
        low_x, low_y = high_x, high_y = points[0]
        for x, y in points:
            if x < low_x:
                low_x = x
            elif x > high_x:
                high_x = x
            if y < low_y:
                low_y = y
            elif y > high_y:
                high_y = y
        boxes.append((low_x, low_y, high_x, high_y))
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    side = max(1, int((len(facets) / _MERGE_CELLS_PER_FACET) ** 0.5))
    step_x = max((x1 - x0) / side, 1e-9)
    step_y = max((y1 - y0) / side, 1e-9)

    # cell -> [facet index, ...] in increasing index order. The cell is one
    # integer `cx * side + cy` rather than the pair it stands for, and the
    # entry is the facet's index alone rather than the index paired with its
    # fill: a protein writes eight hundred thousand of these, and a tuple per
    # entry and a tuple per lookup was a third of the gather. The fill is
    # `keys[other]`, which the scan already has the list for.
    history: dict[int, list[int]] = defaultdict(list)
    # fill key -> the index of the open run's first facet.
    open_at: dict[tuple[float, float, str], int] = {}
    # run start index -> the facets in it. Keyed by start so the emitted order
    # is the sorted keys, with no reliance on dict insertion order.
    runs: dict[int, list] = {}

    last = side - 1
    for index, facet in enumerate(facets):
        # `cells_of` written out, and the clamp with it: this is once per
        # facet and the two `min`/`max` frames per axis cost more than the
        # comparisons they wrap. Same cells, same order.
        bx0, by0, bx1, by1 = boxes[index]
        lo_x = int((bx0 - x0) / step_x)
        hi_x = int((bx1 - x0) / step_x)
        lo_y = int((by0 - y0) / step_y)
        hi_y = int((by1 - y0) / step_y)
        lo_x = 0 if lo_x < 0 else last if lo_x > last else lo_x
        hi_x = 0 if hi_x < 0 else last if hi_x > last else hi_x
        lo_y = 0 if lo_y < 0 else last if lo_y > last else lo_y
        hi_y = 0 if hi_y < 0 else last if hi_y > last else hi_y
        if lo_x == hi_x and lo_y == hi_y:
            cells = (lo_x * side + lo_y,)   # by far the commonest facet
        else:
            cells = [cx * side + cy for cx in range(lo_x, hi_x + 1)
                     for cy in range(lo_y, hi_y + 1)]
        key = keys[index]
        start = open_at.get(key)
        if start is not None and not _clear_since(
                history, cells, start, index, fills, corners, boxes):
            start = None
        if start is None:
            start = index
            open_at[key] = index
            runs[index] = []
        runs[start].append(facet)
        for cell in cells:
            history[cell].append(index)
    return [(keys[start], runs[start]) for start in sorted(runs)]


def _run_subpaths(members: list) -> list[Subpath]:
    """One run's facets as the fewest closed outlines they will make.

    Everything in a run is painted in one colour, so an edge with a member on
    both sides of it draws nothing: it is written down twice, painted twice,
    and covered by the same fill either way. `dissolve` cancels those edges
    combinatorially -- two faces of a mesh share vertex *indices*, so their
    shared edge is the same pair of page points for both, and no coordinate is
    ever compared.

    The saving is in coordinates rather than paths, which is the half of the
    file `_tone_runs` alone could not reach. Falls back to a subpath per facet
    for anything the dissolve cannot close, so a hand-built facet with no ring
    still draws.
    """
    if not all(facet.ring for facet in members):
        return [Subpath(_bleed(facet.points), closed=True) for facet in members]
    where: dict[int, Vec2] = {}
    for facet in members:
        where.update(zip(facet.ring, facet.points))
    rings = dissolve([facet.ring for facet in members])
    if not rings:
        return [Subpath(_bleed(facet.points), closed=True) for facet in members]
    return [Subpath(_bleed(tuple(where[i] for i in ring)), closed=True)
            for ring in rings]


def _clear_since(history, cells, start: int, index: int, fills, corners,
                 boxes) -> bool:
    """Has anything of another tone overlapped this facet since `start`?

    "Another tone" means another *fill*: tone, depth cue and group colour
    together, since two facets alike in one but not the others are painted
    different colours and so cannot be reordered against each other.

    Each cell's list is scanned backwards, because the entries that matter are
    the recent ones. The scan stops at `start` or at `_MERGE_SCAN` entries,
    whichever comes first; hitting the cap closes the run, which is the
    cautious answer.
    """
    mine = corners[index]
    key = fills[index]
    # Unpacked, and the box test written out below rather than called: this
    # runs about seventy thousand times on a protein and rejects nearly every
    # candidate on those four comparisons, so the call frame around them was
    # most of what the rejection cost.
    ax0, ay0, ax1, ay1 = boxes[index]
    slack = _MERGE_TOUCH
    tested: set[int] = set()
    look = history.get       # a `defaultdict`, so never subscript it here
    for cell in cells:
        entries = look(cell)
        # Entries go in in increasing index order, so the last one is the
        # newest: if even that predates the run, the scan below would break on
        # its first step. Most cells of most facets are in that state, and
        # this test is what stops us building an iterator to find out.
        if not entries or entries[-1] <= start:
            continue
        seen = 0
        for other in reversed(entries):
            if other <= start:
                break
            seen += 1
            if seen > _MERGE_SCAN:
                return False
            if fills[other] == key or other in tested:
                continue
            tested.add(other)
            bx0, by0, bx1, by1 = boxes[other]
            if (ax1 < bx0 - slack or bx1 < ax0 - slack
                    or ay1 < by0 - slack or by1 < ay0 - slack):
                continue
            if overlaps(mine, corners[other], slack):
                return False
    return True


def _facet_node(subpaths: list[Subpath], color: str) -> Diagram:
    return Diagram(prim=PathPrim(tuple(subpaths), filled=True),
                   kind="model-facet").styled(fill=color, stroke="none")


#: How far a mitred corner may reach, as a multiple of the bleed. A shaded
#: model is therefore at most `2 * _MITRE_LIMIT * _FACET_BLEED` wider than the
#: width it was asked for -- a twentieth of a millimetre, and bounded.
_MITRE_LIMIT = 2.0


def _bleed(points: tuple[Vec2, ...]) -> tuple[Vec2, ...]:
    """Grow an outline outward by `_FACET_BLEED`, corner by corner.

    Offset along the mitre of the two edges meeting at each corner, not
    radially from the centre. The two agree on a triangle and part company on
    anything long: a dissolved ribbon is 30mm end to end and a millimetre
    across, and pushing its side vertices away from its centre moves them
    almost entirely *along* it -- which leaves the sides exactly where they
    were, and the hairline this function exists to cover open down both of
    them.

    A ring wound the other way -- a hole -- offsets the other way by the same
    arithmetic, which is what keeps a hole from growing shut.
    """
    n = len(points)
    if n < 3:
        return points
    # The corners as plain pairs, and the normals kept as pairs too. Every
    # multiply, divide and comparison below is the one this function has always
    # made, on the same operands and in the same order -- what is gone is a
    # `Vec2` per edge, a modulo per term and two attribute lookups per read.
    # It is worth the loss of prose: a dissolved protein calls this fourteen
    # thousand times for a tenth of the panel.
    corner = [(p.x, p.y) for p in points]
    # A running sum rather than `sum()` over a comprehension, and the terms in
    # the order that had: corner 0 to 1 first and the closing edge last. Not
    # pedantry -- float addition does not associate, and `turn` is the sign of
    # this number, so a reordered sum could flip a near-degenerate ring inside
    # out and offset it the wrong way.
    area = 0.0
    ax, ay = corner[0]
    for i in range(1, n):
        bx, by = corner[i]
        area += ax * by - bx * ay
        ax, ay = bx, by
    bx, by = corner[0]
    area += ax * by - bx * ay
    turn = -1.0 if area < 0.0 else 1.0
    bleed, limit = _FACET_BLEED, _MITRE_LIMIT
    normals = []
    ax, ay = corner[0]
    for i in range(n):
        bx, by = corner[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        span = (dx * dx + dy * dy) ** 0.5
        normals.append((0.0, 0.0) if span < 1e-12
                       else (dy / span * turn, -dx / span * turn))
        ax, ay = bx, by
    grown = []
    add = grown.append
    for i in range(n):
        (fx, fy), (tx, ty) = normals[i - 1], normals[i]
        mx, my = fx + tx, fy + ty
        half = (mx * mx + my * my) ** 0.5 / 2.0    # cos of half the turn
        px, py = corner[i]
        if half < 1e-9:                            # doubled back on itself
            sx, sy = (tx, ty) if (tx or ty) else (fx, fy)
            add(Vec2(px + sx * bleed, py + sy * bleed))
            continue
        # Mitre length is bleed / cos(half the turn), capped: a needle-thin
        # facet would otherwise grow a spike many times the bleed long.
        reach = min(bleed / (2.0 * half * half), bleed * limit / (2.0 * half))
        add(Vec2(px + mx * reach, py + my * reach))
    return tuple(grown)


def ridges_for(mesh: Mesh, ridges) -> bool | list[bool]:
    """`ridges` as `feature_edges` takes it: one flag, or one per face.

    A mapping names the groups that want their folds inked whole; anything it
    does not name keeps ridge suppression. A mesh with no groups has nothing
    for the mapping to select, so it takes the rule that applies to everything
    the mapping did not name.
    """
    if isinstance(ridges, bool):
        return ridges
    if not mesh.groups:
        return True
    return [ridges.get(group, True) for group in mesh.groups]


def outline_of(mesh: Mesh, view: View, *, crease: float = 30.0,
               ridges=True, smooth: bool | float | None = None) -> tuple:
    """One mesh's outline in a view that is already framed.

    The same curve `render` hands back as `Rendering.silhouette`, without
    drawing anything: for a part of a scene that is *painted* as part of a
    larger mesh but still has to catch an arrow of its own. Framing is the
    caller's, because the whole point is that the part shares a projection
    with the rest of the scene rather than being fitted to itself.
    """
    points, depths = view.project_all(mesh.vertices)
    facing = facing_faces(mesh, view)
    features = feature_edges(mesh, view, crease_degrees=crease, facing=facing,
                             ridges=ridges_for(mesh, ridges))
    degrees = (float(smooth) if smooth is not None and not isinstance(smooth, bool)
               else min(crease, SMOOTH_CEILING))
    if smooth is not False:
        smoothed = smooth_silhouette(mesh, view, features, points, depths,
                                     smooth_degrees=degrees)
        features, points = smoothed.edges, smoothed.points
    return _silhouette(mesh, features, points)


def _silhouette(mesh: Mesh, features, points) -> tuple:
    """The outline the trace clips on: every silhouette and boundary edge.

    Visibility is deliberately ignored. `Trace.exit` keeps the furthest
    crossing, so handing it the whole silhouette curve -- including the parts
    hidden behind the object -- still lands an arrow on the outer boundary,
    and it means the trace does not change when a fold happens to be occluded.
    """
    rim = [(e.a, e.b) for e in features if e.kind in (SILHOUETTE, BOUNDARY)]
    if not rim:
        return ()
    return tuple((tuple(points[i] for i in chain), closed)
                 for chain, closed in chain_edges(rim) if len(chain) >= 2)


register_backend("builtin", _builtin, priority=0)
