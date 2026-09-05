"""Panels (a), (b) and (c) of the stress figure: the apparatus band.

Three panels that all ask the same question in different ways -- *does a
projection compose with the rest of the page?*

(a) two-photon rig
    Twelve parametric solids in **one** projection -- one `inklet.scene`, not
    twelve `inklet.solid()` calls stacked side by side, which is a collage: every
    part is framed through a single fitted camera, so the beam really does run
    down one optical axis and the parts are the size they would be on a bench,
    and the near ones are drawn over the far ones. The beam path is `inklet.link`
    arrows aimed at the parts themselves rather than at named points, so each
    one stops on the part's projected outline.

(b) cortical surface with labelled areas
    An 18000-face scan in line art, six retinotopic areas anchored to real
    surface vertices, leaders out to a label ladder that cannot cross itself, a
    scale bar in millimetres and an orientation cube in the same view.

(c) head-fixed preparation
    A raster cutout, flat vector shapes and a projected solid in one frame,
    with arrows that clip on the *bitmap's* silhouette.

Run it:

    .venv/bin/python stress/panels/apparatus.py
    scripts/rasterise.sh stress/panels/apparatus.svg stress/panels/apparatus.png 3
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Sequence

import inklet
from inklet.core.geom import Rect, Vec2
from inklet.three import Camera, Mat4, Mesh, Vec3, build, load, merge, view_of

ROOT = Path(__file__).resolve().parents[2]
MESHES = ROOT / "stress" / "meshes"
ASSETS = ROOT / "stress" / "assets"

#: One camera for the whole bench, so nothing on it reads as a separate
#: drawing. A shallow azimuth keeps a long optical train nearly horizontal --
#: true isometric would run it diagonally off a short, full-width panel.
BENCH = Camera(azimuth=18.0, elevation=20.0)

#: The left hemisphere seen from its lateral side: the eye is on -x, so the
#: gyri face the reader and anterior falls to the left. Turned twenty degrees
#: past a flat lateral so the orientation cube beside it has three faces to
#: show, which a square cannot.
LATERAL = Camera(azimuth=-110.0, elevation=10.0)

#: A near-side view for (c). The mouse photograph is lateral, so the objective
#: over it has to be lateral too; twelve degrees of lift is enough for the
#: barrel to show a rim rather than collapse to a bare triangle.
BENCHSIDE = Camera(azimuth=90.0, elevation=12.0)

#: `brain-lh.obj` ships normalised into a 2-unit cube; the NIH surface it came
#: from spans 177 mm. That ratio is the only thing that turns a projection back
#: into millimetres, and it is a property of the file, not of the drawing.
BRAIN_MM_PER_UNIT = 177.0 / 2.0

WINDOW_DIAMETER_MM = 3.0
OBJECTIVE_TILT = 20.0

#: `inklet.three.backend` draws creases at 0.62 of the outline weight and does not
#: export the ratio. Dividing by it here is how a model's *thinnest* line is
#: made to land exactly on the theme's hairline instead of below it, which
#: keeps the whole figure inside three stroke weights.
_CREASE_RATIO = 0.62


# -- shared helpers -------------------------------------------------------


def _at(node: inklet.Diagram, x: float, y: float, anchor: str = "center") -> inklet.Diagram:
    """Move a node so `anchor` lands on (x, y) of the frame being drawn in.

    `inklet.place` does this for one anchor per call; the compositions below mix
    "centre it here" with "hang it below here" in one coordinate system, which
    needs the per-item form.
    """
    here = node.transform.apply(node.anchor_point(anchor))
    return node.translated(x - here.x, y - here.y)


def _extent(box: Rect, direction: Vec2) -> float:
    """How far a box reaches from its own centre along a direction."""
    return abs(direction.x) * box.width / 2.0 + abs(direction.y) * box.height / 2.0


def _outward(node: inklet.Diagram, anchor: Vec2, direction: Vec2, clearance: float,
             from_box: Rect | None = None) -> inklet.Diagram:
    """Push a node clear of something, along a direction, by what it measures.

    The same move `inklet.axes` makes to keep an axis label off its own arrow: the
    distance is the two half-extents plus the theme's gap, so a wide label
    clears as surely as a tall one and no call site ever types a millimetre.
    """
    unit = direction.normalized()
    reach = 0.0 if from_box is None else _extent(from_box, unit)
    step = reach + clearance + _extent(node.local_bbox, unit)
    here = anchor + unit * step
    return _at(node, here.x, here.y)


def _crest(outline: Sequence[Vec2], x0: float, x1: float) -> float | None:
    """The highest a traced subject reaches between two x, or None if it does
    not reach there at all.

    A photograph's bounding box is the *frame's*; `outline` is the animal, and
    between the two is however much sky is in the picture -- above a mouse
    lying along the frame, most of the top half of it. Anything hung off the
    box therefore lands on the subject, which is what happened to the headplate
    tag: it cleared the box by the theme's gap and sat squarely on the mouse's
    back.

    Vertices inside the span, plus where the boundary crosses each end: the
    outline is a polygon, so between two vertices it can only run straight, and
    those are the only places an extreme can be.
    """
    ys = [p.y for p in outline if x0 <= p.x <= x1]
    for a, b in zip(outline, tuple(outline[1:]) + (outline[0],)):
        for edge in (x0, x1):
            if (a.x - edge) * (b.x - edge) < 0:
                ys.append(a.y + (b.y - a.y) * (edge - a.x) / (b.x - a.x))
    return min(ys) if ys else None


def _lift_clear(node: inklet.Diagram, outline: Sequence[Vec2],
                clearance: float) -> inklet.Diagram:
    """Raise a node until the traced subject beneath it is out from under it."""
    box = node.bbox
    crest = _crest(outline, box.x0, box.x1)
    if crest is None:
        return node
    drop = box.y1 - (crest - clearance)
    return node if drop <= 0.0 else node.translated(0.0, -drop)


def _fit(builder: Callable[[float], inklet.Diagram], target: float,
         passes: int = 4, tol: float = 0.05) -> inklet.Diagram:
    """Return a panel that is `target` wide -- exactly, not nearly.

    The requested width is a contract with whoever composes the page: a panel
    that comes out 8% over pushes its neighbour off the paper, and one that
    comes out short leaves a stripe of blank column. Labels hang off the ends
    of all three of these panels and their width does not scale with the
    drawing, so `drawn at 84 mm` never measures 84 mm on its own.

    Two stages, because neither alone is honest. First a solve: the residual
    is fed back into the drive width until it stops moving, which *widens the
    content* rather than centring a fixed-size drawing inside a box. Then, for
    whatever the solve cannot reach -- a label that gained a line, a glyph
    advance that rounds -- symmetric padding, which can only ever add empty
    paper and never claims a drawing is smaller than it is. The solve is
    deliberately biased to undershoot so the second stage always has slack of
    the right sign.
    """
    drive = target
    node = builder(drive)
    for _ in range(passes - 1):
        residual = target - node.bbox.width
        if abs(residual) <= tol:
            break
        drive += residual
        node = builder(drive)
    # Overshoot cannot be padded away -- negative padding would be a lie about
    # where the ink is -- so it is driven out, then padded.
    for _ in range(3):
        slack = target - node.bbox.width
        if slack >= 0.0:
            break
        node = builder(drive + slack - tol)
        drive += slack - tol
    slack = target - node.bbox.width
    if slack < 0.0:
        # Below a panel's floor. Type does not shrink with the drive, so past
        # some width the captions are the panel and no drive reaches the
        # target. Overflowing is the one outcome a composed page cannot
        # absorb -- it pushes the neighbour off the paper -- so the whole
        # panel is scaled instead, knowingly taking the type under 7pt with
        # it. The floor is a few tens of a millimetre below any width these
        # panels are meant for; reaching this branch means the request was
        # for a thumbnail.
        return node.scaled(target / node.bbox.width)
    if slack <= 1e-9:
        return node
    return inklet.pad(node, 0.0, slack / 2.0, 0.0, slack / 2.0)


def _hair(theme) -> inklet.Style:
    return inklet.Style(stroke=theme.muted, stroke_width=theme.hairline)


def _model_stroke(theme) -> float:
    return theme.hairline / _CREASE_RATIO


def _orient(normal: Vec3) -> Mat4 | None:
    """The rotation that takes a solid's +z onto `normal`.

    Every parametric solid in `inklet.three` is built z-up, so a mirror is a
    `plane` turned until its normal is the one that reflects the beam. Writing
    the *normal* down is what keeps the optics honest: a mirror turning a ray
    from direction `d` to direction `e` has normal proportional to `e - d`, and
    that is the expression at every call site below rather than a typed angle.
    """
    n = normal.normalized()
    z = Vec3(0.0, 0.0, 1.0)
    axis = z.cross(n)
    if axis.length < 1e-9:
        return None if n.dot(z) > 0.0 else Mat4.rotation(Vec3(1.0, 0.0, 0.0), 180.0)
    angle = math.degrees(math.acos(max(-1.0, min(1.0, z.dot(n)))))
    return Mat4.rotation(axis.normalized(), angle)


def _part(kind: str, at: Vec3, *, normal: Vec3 | None = None, **shape) -> Mesh:
    """A solid built, turned and put where it stands on the bench."""
    mesh = build(kind, **shape)
    if normal is not None:
        turn = _orient(normal)
        if turn is not None:
            mesh = mesh.transformed(turn)
    return mesh.transformed(Mat4.translation(at))


# -- (a) the two-photon rig ----------------------------------------------

# The bench, in optical units. These are positions in a scene, which is the 3D
# equivalent of a data coordinate -- what the drawing *is*, not where it sits
# on the page. The beam runs +x out of the laser, doglegs +y across the
# galvanometer pair, turns -z at the mirror, passes through the dichroic into
# the objective; fluorescence returns up that axis and is reflected -y to the
# detector, which is what puts the collection arm out in front of the bench
# rather than on top of it.

_BEAM_Y = 3.4       # the scan mirrors offset the beam by this much in y
_TURN_X = 2.0       # where the beam turns down toward the specimen
_DETECT_Z = -1.15   # height of the dichroic and of the whole collection arm

#: The objective, and the gap between its tip and the sample. A 16x dipping
#: objective has three millimetres of working distance against sixty of barrel,
#: which at this scale is a tenth of a millimetre on the page -- thinner than
#: the line that draws the tip, and nowhere near room for the arrow that says
#: the light gets there. So it is opened up. That is the same licence
#: `_MARGINAL` takes further down on the collection ray, and the same one every
#: optics schematic takes: the drawing is of what happens, not of what fits.
_OBJECTIVE_Z = -2.8
_OBJECTIVE_LENGTH = 1.35
_WORKING_DISTANCE = 0.85
_SPECIMEN_Z = _OBJECTIVE_Z - _OBJECTIVE_LENGTH / 2.0 - _WORKING_DISTANCE

_GALVO_IN = Vec3(-1.0, 1.0, 0.0)      # +x -> +y   (x galvanometer)
_GALVO_OUT = Vec3(1.0, -1.0, 0.0)     # +y -> +x   (y galvanometer)
_TURN_N = Vec3(-1.0, 0.0, -1.0)       # +x -> -z   (down into the objective)
_DICHROIC_N = Vec3(0.0, 1.0, -1.0)    # +z -> +y   (fluorescence to the PMT)


def _bench_parts() -> tuple[tuple[str, Mesh, str], ...]:
    """Every part on the bench: name, mesh in scene coordinates, material."""
    return (
        ("laser", _part("box", Vec3(-16.0, 0.0, 0.0),
                        size_x=3.0, size_y=1.2, size_z=0.8), "metal"),
        ("pockels", _part("box", Vec3(-12.4, 0.0, 0.0),
                          size_x=1.1, size_y=0.55, size_z=0.55), "metal"),
        ("galvo_x", _part("plane", Vec3(-9.6, 0.0, 0.0), normal=_GALVO_IN,
                          width=0.7, depth=0.7), "mirror"),
        ("galvo_y", _part("plane", Vec3(-9.6, _BEAM_Y, 0.0), normal=_GALVO_OUT,
                          width=0.7, depth=0.7), "mirror"),
        ("scan_lens", _part("cylinder", Vec3(-6.6, _BEAM_Y, 0.0),
                            normal=Vec3(1.0, 0.0, 0.0),
                            radius=0.45, height=0.18, segments=28), "glass"),
        ("tube_lens", _part("cylinder", Vec3(-2.6, _BEAM_Y, 0.0),
                            normal=Vec3(1.0, 0.0, 0.0),
                            radius=0.55, height=0.20, segments=28), "glass"),
        ("mirror", _part("plane", Vec3(_TURN_X, _BEAM_Y, 0.0), normal=_TURN_N,
                         width=0.8, depth=0.8), "mirror"),
        ("dichroic", _part("plane", Vec3(_TURN_X, _BEAM_Y, _DETECT_Z),
                           normal=_DICHROIC_N, width=0.85, depth=0.85), "mirror"),
        ("objective", _part("cone", Vec3(_TURN_X, _BEAM_Y, _OBJECTIVE_Z),
                            normal=Vec3(0.0, 0.0, -1.0),
                            radius=0.55, height=_OBJECTIVE_LENGTH,
                            segments=28), "metal"),
        ("specimen", _part("plane", Vec3(_TURN_X, _BEAM_Y, _SPECIMEN_Z),
                           width=2.4, depth=1.8), "sample"),
        # The collection arm runs to +y, on the far side of the beam from the
        # objective's own label. Sent the other way it lands on top of that
        # label, and no amount of leader routing recovers from two components
        # and two captions competing for the same square centimetre.
        ("filter", _part("cylinder", Vec3(_TURN_X, _BEAM_Y + 4.0, _DETECT_Z),
                         normal=Vec3(0.0, 1.0, 0.0),
                         radius=0.34, height=0.16, segments=28), "glass"),
        ("pmt", _part("cylinder", Vec3(_TURN_X, _BEAM_Y + 8.0, _DETECT_Z),
                      normal=Vec3(0.0, 1.0, 0.0),
                      radius=0.42, height=1.2, segments=28), "metal"),
    )


_BENCH_TEXT = {
    "laser": "Ti:sapphire\n920 nm",
    "pockels": "Pockels cell",
    "galvo_y": "galvanometer\nscan mirrors",
    "scan_lens": "scan lens",
    "tube_lens": "tube lens",
    "mirror": "turning mirror",
    "dichroic": "dichroic\n700 nm LP",
    "objective": "objective\n16× / 0.8 NA",
    "specimen": "specimen",
    "filter": "525/50\nemission filter",
    "pmt": "PMT",
}

#: Where each label goes relative to the part it names. `"row"` puts it on the
#: common baseline above the bench, which is what an optics figure does for a
#: train of components in a line; a direction puts it out that way by however
#: much the part and the label together measure. Choosing a side is authorship
#: -- the same call as choosing which column of a stack a tag goes in -- and
#: the distance is measured, never typed.
_BENCH_LABEL_SIDE: dict[str, str | Vec2] = {
    "laser": "row",
    "pockels": "row",
    "galvo_y": "row",
    "scan_lens": "row",
    "tube_lens": "row",
    "mirror": "row",
    "dichroic": Vec2(-1.0, 0.0),
    "objective": Vec2(-1.0, 0.0),
    "specimen": Vec2(1.0, 0.0),
    # Both detection captions go to the lower right of the arm, along it, so
    # they read as a pair and neither one crosses the fluorescence path.
    "filter": Vec2(0.76, 0.65),
    "pmt": Vec2(1.0, 0.0),
}

#: The parts whose captions share the baseline above the bench.
_BENCH_ROW = tuple(n for n, side in _BENCH_LABEL_SIDE.items() if side == "row")


def _material_color(theme) -> dict[str, str]:
    """Four material classes, so a reader can tell glass from a machined can.

    Kept clear of the two beam colours: the saturated end of the palette
    belongs to the light, not to the hardware carrying it.
    """
    return {
        "metal": theme.muted,
        "glass": theme.color(2),
        "mirror": theme.color(5),
        "sample": theme.color(1),
    }


def _bench_scene(scene_width: float, theme) -> tuple[
        inklet.Diagram, dict[str, inklet.Diagram], dict[str, Rect]]:
    """The whole bench in one projection, and where each part landed.

    `inklet.scene` is the call this panel exists to exercise: twelve meshes framed
    together rather than twelve `inklet.model` calls, which would auto-fit each
    part to the same width and give a collage of twelve scales. It also paints
    them furthest first, which is what puts the specimen plane *under* the
    objective that dips into it instead of over the top of it.

    The boxes come back from a `resolve` of the scene on its own, because a
    caption needs to know where its part is before the page it will sit on
    exists. Every number the layout below uses is measured off this, so moving
    a component moves its label with it.
    """
    colors = _material_color(theme)
    parts = _bench_parts()
    bench = inklet.scene(
        [(name, mesh, {"color": colors[material], "anchors": _bench_anchors(name)})
         for name, mesh, material in parts],
        width=scene_width, view=BENCH, style="shaded", crease=25.0,
        stroke_width=_model_stroke(theme), name="bench")
    nodes = {name: bench.find(name) for name, _, _ in parts}
    placed = inklet.resolve(bench)
    return bench, nodes, {name: placed[node.id].bbox for name, node in nodes.items()}


#: How far off the optical axis the collection beam is drawn, in scene units.
#: Excitation and fluorescence are coaxial in the instrument; separating them
#: is the licence an optics drawing takes when it draws a chief ray and a
#: marginal ray, and it is the only way two opposed arrows on one axis can both
#: be read. Offset in x, which the camera spreads across the page, rather than
#: in y, which it foreshortens to a millimetre.
_MARGINAL = 0.46


def _bench_anchors(name: str) -> dict[str, tuple[float, float, float]]:
    """The points on the bench a beam is aimed at, as real 3D coordinates.

    The marginal ray of the collection path, and the focus. The focus has to be
    a point rather than the specimen itself: the sample plane is three times
    the objective's width, so an arrow clipped on its outline stops at the
    plane's back edge, a centimetre from the one spot the light reaches.
    """
    if name == "objective":
        return {"collect": (_TURN_X + _MARGINAL, _BEAM_Y, -2.2)}
    if name == "dichroic":
        return {"collect": (_TURN_X + _MARGINAL, _BEAM_Y, _DETECT_Z)}
    if name == "specimen":
        return {"focus": (_TURN_X, _BEAM_Y, _SPECIMEN_Z)}
    return {}


def _panel_a_content(scene_width: float) -> inklet.Diagram:
    theme = inklet.current_theme()
    bench, parts, boxes = _bench_scene(scene_width, theme)
    rect = bench.local_bbox
    clear = theme.gap("m")

    texts = {name: inklet.label(body, align="center")
             for name, body in _BENCH_TEXT.items()}
    # The baseline clears the parts it captions, not the whole scene: measuring
    # it against the scene would let the PMT -- which is up and to the right of
    # everything, and captioned on its own -- lift the entire row and make the
    # panel taller for nothing.
    row_y = (min(boxes[name].y0 for name in _BENCH_ROW) - clear
             - max(texts[name].local_bbox.height for name in _BENCH_ROW) / 2.0)

    labels: dict[str, inklet.Diagram] = {}
    items: list[inklet.Diagram] = [bench]
    aside: list[inklet.Diagram] = []
    for name, side in _BENCH_LABEL_SIDE.items():
        text = texts[name]
        here = bench.anchor_point(name)
        labels[name] = text
        if side == "row":
            items.append(_at(text, here.x, row_y))
        else:
            placed = _outward(text, here, side, clear, boxes[name])
            aside.append(placed)
            items.append(placed)

    # The coordinate frame and the key go in the bench's own empty quadrant --
    # under the horizontal run, which nothing occupies because the beam only
    # ever turns downward, and at the far end from where it does.
    frame = inklet.axes(width=12.0, view=BENCH, labels=("x", "y", "z"),
                     style="shaded", color=theme.muted,
                     stroke_width=_model_stroke(theme))
    key = inklet.legend(
        [("excitation", inklet.polyline([(0, 0), (5.5, 0)], stroke=theme.color(6),
                                     stroke_width=theme.thick)),
         ("fluorescence", inklet.polyline([(0, 0), (5.5, 0)], stroke=theme.color(3),
                                       stroke_width=theme.thick,
                                       stroke_dash=(1.4, 0.9)))],
        title="light path")
    # Both sit on the bench's own baseline, so they read as one band of
    # furniture rather than two floating boxes. The frame goes in the corner,
    # where a coordinate frame belongs; the key goes under the middle of the
    # horizontal run, next to the light it is a key to, which is also the
    # widest piece of empty paper the layout leaves.
    # The key is centred in the gap the layout actually left: between the
    # frame it sits beside and whatever caption reaches furthest back along the
    # bench. Both edges are measured off placed nodes, so the key follows the
    # drawing when the drawing changes instead of being nudged after it.
    gutter = min((node.bbox.x0 for node in aside), default=rect.x1)
    left = rect.x0 + frame.local_bbox.width + theme.gap("l")
    for node, x in ((frame, rect.x0 + frame.local_bbox.width / 2.0),
                    (key, (left + gutter - theme.gap("l")) / 2.0)):
        items.append(_at(node, x,
                         rect.y1 - node.local_bbox.height / 2.0))

    content = inklet.place(items)
    routed = inklet.route_all(_bench_links(parts, labels, theme),
                           inklet.resolve(content))
    return inklet.Diagram(children=(content, routed), kind="panel")


def _bench_links(nodes, labels, theme) -> list[inklet.Link]:
    """The beam, then the leaders.

    Every beam segment is aimed at a *part*, never at one of its anchors, so
    each is clipped by the silhouette hidden-line removal produced rather than
    by a bounding box -- which is the whole reason the components are drawn in
    three dimensions instead of as rectangles. The one exception is the
    collection ray, which is aimed at two named 3D points because it has to
    leave the axis by a stated amount.
    """
    excite = inklet.Style(stroke=theme.color(6), stroke_width=theme.thick,
                       fill=theme.color(6))
    emit = inklet.Style(stroke=theme.color(3), stroke_width=theme.thick,
                     stroke_dash=(1.4, 0.9), fill=theme.color(3))
    beam = dict(standoff=0.5, arrow_size=theme.arrow_size)

    # `mirror -> objective` passes through the dichroic on purpose: a long-pass
    # dichroic transmits 920 nm, and drawing the excitation stopping at it
    # would be a lie about the instrument. `through=` is how that is declared,
    # so the linter can tell it from a line that wandered across an optic.
    train = [("laser", "pockels"), ("pockels", "galvo_x"),
             ("galvo_x", "galvo_y"), ("galvo_y", "scan_lens"),
             ("scan_lens", "tube_lens"), ("tube_lens", "mirror"),
             ("mirror", "objective"), ("objective", "specimen")]
    transmitted = {("mirror", "objective"): (nodes["dichroic"],)}
    aimed = {("objective", "specimen"): "focus"}
    links = [inklet.link(nodes[a], _aim(nodes[b], aimed.get((a, b))),
                      style=excite, name=f"beam-{a}-{b}",
                      through=transmitted.get((a, b), ()), **beam)
             for a, b in train]
    links += [
        inklet.link(nodes["objective"].at("collect"), nodes["dichroic"].at("collect"),
                 style=emit, name="beam-collect", **beam),
        inklet.link(nodes["dichroic"], nodes["filter"], style=emit,
                 name="beam-filter", **beam),
        inklet.link(nodes["filter"], nodes["pmt"], style=emit, name="beam-pmt", **beam),
    ]
    links += [inklet.link(labels[name], nodes[name], kind="line", head="none",
                       style=_hair(theme), standoff=0.5, name=f"tag-{name}")
              for name in _BENCH_LABEL_SIDE]
    return links


def _aim(node: inklet.Diagram, anchor: str | None):
    """The part, or a named point on it. See `_bench_anchors` for when the
    difference matters."""
    return node if anchor is None else node.at(anchor)


def panel_a(width: float = 178.0) -> inklet.Diagram:
    """Two-photon rig schematic, full width."""
    return _fit(_panel_a_content, width)


# -- (b) the cortical surface --------------------------------------------

#: Six retinotopic areas, as targets on the lateral wall rather than as
#: coordinates. `_surface_point` walks the mesh for the outermost vertex near
#: each of them, so every marker is on the surface by construction; three typed
#: numbers would put half of them inside it. Anterior is +y, dorsal +z, so all
#: six sit in the posterior third, which is where they belong.
_AREAS = (
    ("V1", -0.90, -0.05),
    ("V2", -0.80, 0.30),
    ("V3", -0.62, 0.54),
    ("hV4", -0.74, -0.42),
    # Dorsal to MT+ rather than level with it: at the level the atlas would
    # put it, LO and V1 project to within a millimetre of the same height and
    # their two leaders run side by side down the same corridor.
    ("LO", -0.48, 0.18),
    ("MT+", -0.36, -0.20),
)


def _surface_point(mesh: Mesh, y: float, z: float, pull: float = 9.0) -> Vec3:
    """The most lateral vertex near (y, z) on the -x wall.

    A plain extreme-vertex search -- `max` over one direction -- gives a pole
    and nothing between poles. Trading lateral position off against distance
    from a target is what lets six landmarks be spread over one hemisphere and
    still be *found* rather than guessed.
    """
    def score(v: Vec3) -> float:
        return -v.x - pull * ((v.y - y) ** 2 + (v.z - z) ** 2)

    return max(mesh.vertices, key=score)


def _ladder(points: dict[str, Vec2], texts: dict[str, inklet.Diagram],
            x: float, gap: float) -> dict[str, inklet.Diagram]:
    """A column of labels beside the drawing, in the order of their markers.

    Two leaders can only cross if the labels they run to are out of order, so
    the labels are sorted by their marker's height and then pushed apart until
    none of them overlaps. The block is recentred on the markers afterwards, so
    spreading pushes it outward in both directions rather than dragging the
    whole ladder downward.
    """
    order = sorted(points, key=lambda name: (points[name].y, name))
    heights = [texts[name].local_bbox.height for name in order]
    ys = [points[name].y for name in order]
    for i in range(1, len(order)):
        floor = ys[i - 1] + (heights[i - 1] + heights[i]) / 2.0 + gap
        ys[i] = max(ys[i], floor)
    wanted = sum(points[name].y for name in order) / len(order)
    shift = wanted - sum(ys) / len(ys)
    return {name: _at(texts[name], x, y + shift) for name, y in zip(order, ys)}


def _orientation_cube(theme, width: float) -> inklet.Diagram:
    """A labelled cube in the same view as the surface beside it.

    The four labels hang off projected 3D directions and are pushed outward, so
    a face the cube is hiding is still named -- which is the whole point of an
    orientation cube and something three visible faces cannot do.
    """
    marks = {"A": Vec3(0.0, 1.0, 0.0), "P": Vec3(0.0, -1.0, 0.0),
             "D": Vec3(0.0, 0.0, 1.0), "V": Vec3(0.0, 0.0, -1.0)}
    cube = inklet.solid("cube", size=1.0, width=width, view=LATERAL, style="shaded",
                     color=theme.color(2), name="orientation",
                     stroke_width=_model_stroke(theme),
                     anchors={k: (v * 0.5).as_tuple() for k, v in marks.items()})
    items: list[inklet.Diagram] = [cube]
    for key in sorted(marks):
        point = cube.anchor_point(key)
        glyph = inklet.label(key, size=theme.font_size_small)
        away = point if point.length > 1e-9 else Vec2(1.0, 0.0)
        # Pushed off the cube's box, not off the face centre it names: a face
        # centre is already on the surface, so clearing it by the glyph's own
        # half-width leaves the letter lying on the silhouette. Two of the four
        # directions are foreshortened almost to nothing in this view, which is
        # exactly when that goes wrong.
        items.append(_outward(glyph, Vec2(0.0, 0.0), away, theme.gap("xs"),
                              cube.local_bbox))
    return inklet.place(items)


def _scale_bar(theme, length_mm: float, page_mm: float) -> inklet.Diagram:
    """A bar of a stated length in the specimen's own units, plus its caption."""
    bar = inklet.polyline([(0, 0), (page_mm, 0)], stroke=theme.ink,
                       stroke_width=theme.thick, stroke_linecap="butt")
    return inklet.vstack([bar, inklet.label(f"{length_mm:g} mm")],
                      gap=theme.gap("xs"), align="center")


def _panel_b_content(cortex_width: float) -> inklet.Diagram:
    theme = inklet.current_theme()
    mesh = _brain()
    anchors = {name: _surface_point(mesh, y, z).as_tuple() for name, y, z in _AREAS}
    cortex = inklet.model(mesh, width=cortex_width, view=LATERAL, style="lineart",
                       crease=72.0, name="cortex", anchors=anchors,
                       stroke_width=_model_stroke(theme))

    points = {name: cortex.anchor_point(name) for name in anchors}
    # The leader ends on the marker, not on the 3D anchor under it. Aimed at
    # the anchor it would be exact -- and would then be drawn straight through
    # its own dot, because an AnchorRef endpoint is pinned and takes neither
    # clipping nor standoff. Aimed at the marker it clips on the marker.
    marks = {name: inklet.marker("circle", 1.5, fill=theme.accent,
                              stroke=theme.paper,
                              stroke_width=theme.hairline).named(f"dot-{name}")
             for name in anchors}
    dots = [(points[name], marks[name]) for name in sorted(marks)]
    texts = {name: inklet.label(name) for name in anchors}
    column = (cortex.local_bbox.x1 + theme.gap("m")
              + max(t.local_bbox.width for t in texts.values()) / 2.0)
    ring = _ladder(points, texts, column, theme.gap("xs"))

    body = inklet.place([cortex] + dots + [ring[name] for name in sorted(ring)])
    # Anterior is to the left in this view and the frontal pole leaves the
    # bottom-left of the panel empty, so the furniture goes there, in a column,
    # lined up with itself rather than with the outline.
    furniture = inklet.vstack(
        [_orientation_cube(theme, cortex_width * 0.17),
         _scale_bar(theme, 20.0, 20.0 / BRAIN_MM_PER_UNIT * view_of(cortex).scale)],
        gap=theme.gap("l"), align="center")
    content = inklet.hstack([furniture, body], gap=theme.gap("s"), align="bottom")

    links = [inklet.link(ring[name], marks[name], kind="line", head="none",
                      style=_hair(theme), standoff=0.35, name=f"area-{name}")
             for name in sorted(ring)]
    routed = inklet.route_all(links, inklet.resolve(content))
    return inklet.Diagram(children=(content, routed), kind="panel")


def panel_b(width: float = 84.0) -> inklet.Diagram:
    """Left cortical surface, lateral view, six visual areas labelled."""
    return _fit(lambda drive: _panel_b_content(drive * 0.62), width)


_BRAIN: Mesh | None = None


def _brain() -> Mesh:
    """The scan, parsed once. Line art over 18000 faces is most of a second and
    the panel is drawn more than once while its width is being solved for."""
    global _BRAIN
    if _BRAIN is None:
        _BRAIN = load(MESHES / "brain-lh.obj")
    return _BRAIN


# -- (c) the head-fixed preparation --------------------------------------

#: Where the implant sits on the photograph, as fractions of the subject's own
#: bounding box -- the coordinate system the sidecar's nose/tail/back anchors
#: already use. Read off the image, so it is data about the asset and not a
#: layout coordinate.
_WINDOW_UV = (0.795, 0.135)
_PLATE_UV = (0.815, 0.115)


def _panel_c_content(photo_width: float) -> inklet.Diagram:
    theme = inklet.current_theme()
    photo = inklet.asset(ASSETS / "mouse.png", width=photo_width, name="mouse",
                      anchors={"window": _WINDOW_UV, "plate": _PLATE_UV})
    frame = photo.local_bbox
    span = frame.width
    window_at = photo.anchor_point("window")
    plate_at = photo.anchor_point("plate")
    window_r = span * 0.055

    plate = inklet.frame(inklet.spacer(span * 0.42, window_r * 0.9), pad=0.0,
                      radius=window_r * 0.45, kind="implant").styled(
        fill=theme.grid, stroke=theme.ink,
        stroke_width=_model_stroke(theme)).named("headplate")
    window = inklet.circle(inklet.spacer(window_r * 1.6, window_r * 1.6), pad=0.0,
                        fill=theme.color(2), stroke=theme.ink,
                        stroke_width=_model_stroke(theme)).named("window")

    # The objective, in the same vocabulary as (a), tilted off vertical the way
    # it is on a real rig so it looks down the normal of a curved skull.
    tilt = math.radians(OBJECTIVE_TILT)
    # `axis` runs from the window back up the barrel. The rotation is negated
    # against it: turning the cone by -tilt about x sends its apex down and to
    # the *left* on this camera, which is the direction that has to point at
    # the window once the tip is put up and to the right of it. With the sign
    # the other way the barrel is drawn aiming past the animal entirely, and
    # the drawing looks right at thumbnail size while being wrong.
    axis = Vec2(math.sin(tilt), -math.cos(tilt))
    # Stubby on purpose. A 3:1 barrel drawn at a width that reads next to the
    # animal is twice as tall as the animal is long, and the panel ends up
    # mostly empty paper around one cone.
    barrel = _part("cone", Vec3(), normal=Vec3(0.0, 0.0, -1.0),
                   radius=0.62, height=0.92, segments=28).transformed(
        Mat4.rotation(Vec3(1.0, 0.0, 0.0), -OBJECTIVE_TILT))
    apex = 0.46
    objective = inklet.model(
        barrel, width=span * 0.20, view=BENCHSIDE, style="shaded", crease=25.0,
        color=theme.muted, name="objective", stroke_width=_model_stroke(theme),
        anchors={"tip": (0.0, -apex * math.sin(tilt), -apex * math.cos(tilt))})
    lift = window_r * 2.4
    tip = objective.anchor_point("tip")
    optic_at = window_at + axis * lift
    optic_center = Vec2(optic_at.x - tip.x, optic_at.y - tip.y)

    monitor = _monitor(theme, span * 0.34)
    monitor_at = Vec2(frame.x1 + theme.gap("l") + monitor.local_bbox.width / 2.0,
                      window_at.y + span * 0.15)

    tags = {"mouse": inklet.label("head-fixed,\nbody in a tube", align="center"),
            "monitor": inklet.label("stimulus monitor\n25 cm, 60 Hz", align="center"),
            "plate": inklet.label("titanium\nheadplate", align="center"),
            "optic": inklet.label("objective, as in (a)", align="center")}

    outline = [photo.transform.apply(point) for point in photo.prim.outline]

    items = [
        photo,
        _at(plate, plate_at.x, plate_at.y),
        _at(window, window_at.x, window_at.y),
        _at(objective, optic_at.x - tip.x, optic_at.y - tip.y),
        _outward(tags["optic"], optic_center, Vec2(-1.0, -0.22),
                 theme.gap("s"), objective.local_bbox),
        _at(monitor, monitor_at.x, monitor_at.y),
        _outward(tags["monitor"], monitor_at, Vec2(0.0, 1.0), theme.gap("xs"),
                 monitor.local_bbox),
        _outward(tags["mouse"], Vec2(frame.x0, frame.center.y), Vec2(-1.0, 0.0),
                 theme.gap("m")),
        # Left of the plate, because the tilt callout owns the space directly
        # over the window and the objective owns the space right of that -- and
        # then lifted clear of the *animal* rather than of the picture. The
        # photograph's box reaches well above the mouse's back here, so a tag
        # that clears the box by a gap still prints on the mouse.
        _lift_clear(
            _outward(tags["plate"], Vec2(plate_at.x - span * 0.20, plate_at.y),
                     Vec2(-1.0, -0.34), theme.gap("s")),
            outline, theme.gap("s")),
    ]
    items += _angle_callout(theme, window_at, axis, window_r, lift)
    items += _diameter_callout(theme, window_at, window_r,
                               frame.y1 + theme.gap("xs"))

    content = inklet.place(items)
    links = [
        # Aimed at the photograph itself, so it clips on the traced cutout and
        # not on the picture's frame.
        inklet.link(monitor, photo, standoff=1.2, name="stimulus",
                 style=inklet.Style(stroke=theme.color(1), stroke_width=theme.thick,
                                 fill=theme.color(1))),
        inklet.link(tags["mouse"], photo, kind="line", head="none",
                 style=_hair(theme), standoff=0.8, name="tag-mouse"),
        inklet.link(tags["plate"], plate, kind="line", head="none",
                 style=_hair(theme), standoff=0.5, name="tag-plate"),
        inklet.link(tags["optic"], objective, kind="line", head="none",
                 style=_hair(theme), standoff=0.5, name="tag-optic"),
    ]
    routed = inklet.route_all(links, inklet.resolve(content))
    return inklet.Diagram(children=(content, routed), kind="panel")


def panel_c(width: float = 84.0) -> inklet.Diagram:
    """Head-fixed mouse: raster cutout, flat vector implant, projected optic."""
    return _fit(lambda drive: _panel_c_content(drive * 0.525), width)


def _monitor(theme, width: float) -> inklet.Diagram:
    """A screen showing a drifting grating, drawn as real bars."""
    height = width * 0.78
    bars = 6
    step = width / bars
    stripes = [inklet.polygon([(i * step, 0.0), ((i + 0.52) * step, 0.0),
                            ((i + 0.52) * step, height), (i * step, height)],
                           fill=theme.ink, stroke="none")
               for i in range(bars)]
    screen = inklet.place([inklet.polygon([(0.0, 0.0), (width, 0.0),
                                     (width, height), (0.0, height)],
                                    fill=theme.paper, stroke="none")] + stripes)
    return inklet.frame(screen, pad=theme.gap("xs"), radius=theme.radius * 0.5,
                     kind="implant").styled(
        fill=theme.paper, stroke=theme.ink,
        stroke_width=_model_stroke(theme)).named("monitor")


def _angle_callout(theme, window_at: Vec2, axis: Vec2, window_r: float,
                   lift: float) -> list:
    """The objective's tilt off the skull normal.

    Both legs are drawn, not just one. An arc between a plumb line and an edge
    of the barrel is a 20-degree sliver of nothing at this size -- the reader
    has to supply the second leg from the shape of the cone, and at column
    width they will not. So the optical axis is struck as its own dashed ray up
    to the front element, the normal as another, and the arc closes the wedge
    the two of them make.
    """
    plumb = Vec2(0.0, -1.0)
    start = math.degrees(math.atan2(plumb.y, plumb.x))
    end = math.degrees(math.atan2(axis.y, axis.x))
    # Clear of the window: an arc struck inside the disc's own radius is
    # covered by it, which is how the first version of this callout vanished.
    radius = window_r * 1.75
    ray = dict(stroke=theme.muted, stroke_width=theme.hairline,
               stroke_dash=(0.9, 0.7))
    leg = lambda d, reach: inklet.polyline(
        [(window_at.x + d.x * window_r, window_at.y + d.y * window_r),
         (window_at.x + d.x * reach, window_at.y + d.y * reach)], **ray)
    # The number goes on the far side of the plumb rather than inside the
    # wedge: the wedge is 20 degrees wide and the axis is standing in it.
    away = math.radians(start - 26.0)
    glyph = inklet.label(f"{OBJECTIVE_TILT:g}°")
    return [
        leg(plumb, lift),
        leg(axis, lift * 0.94),
        # On its `origin` anchor, not its centre: a drawn node is recentred on
        # its own bounding box, and for a 20-degree arc that box is a sliver
        # nowhere near the circle it was struck from. `origin` is where the
        # author's (0, 0) -- here, the centre of curvature -- ended up.
        _at(inklet.arc(radius, min(start, end), max(start, end),
                    stroke=theme.ink, stroke_width=theme.hairline),
            window_at.x, window_at.y, "origin"),
        _outward(glyph, window_at + Vec2(math.cos(away), math.sin(away)) * radius,
                 Vec2(math.cos(away), math.sin(away)), theme.gap("xs")),
    ]


def _diameter_callout(theme, window_at: Vec2, radius: float, rule_y: float) -> list:
    """A dimension across the window, taken out clear of the animal.

    Extension lines run from the window's own rim down over the body -- in the
    window's colour, so they read on a photograph -- and the dimension itself
    sits under the silhouette where the arrowheads have room. Which is what a
    drawing does when the feature is smaller than its callout.
    """
    edges = (Vec2(window_at.x - radius, window_at.y),
             Vec2(window_at.x + radius, window_at.y))
    extension = [inklet.polyline([(p.x, p.y), (p.x, rule_y + theme.gap("xs"))],
                              stroke=theme.color(2), stroke_width=theme.hairline)
                 for p in edges]
    rule = inklet.polyline([(edges[0].x, rule_y), (edges[1].x, rule_y)],
                        stroke=theme.ink, stroke_width=theme.hairline)
    caps = [_at(inklet.marker("diamond", 1.1, fill=theme.ink, stroke="none"),
                p.x, rule_y) for p in edges]
    glyph = inklet.label(f"Ø {WINDOW_DIAMETER_MM:g} mm")
    return extension + [rule] + caps + [
        _outward(glyph, Vec2(window_at.x, rule_y), Vec2(0.0, 1.0), theme.gap("xs"))]


# -- looking at it --------------------------------------------------------

if __name__ == "__main__":
    import dataclasses
    import time

    started = time.perf_counter()
    TH = inklet.use_theme(
        dataclasses.replace(inklet.theme("nature"), font_family="Noto Sans"))

    def captioned(letter: str, text: str, node: inklet.Diagram, width=None):
        head = inklet.text(f"({letter})", size=TH.font_size_small, align="start")
        return inklet.vstack(
            [node, inklet.hstack([head, inklet.label(text, align="start", width=width)],
                              gap=1.2)],
            gap=TH.gap("s"), align="left")

    fig = inklet.figure(width=inklet.COLUMN_DOUBLE, margin=4)
    fig.add(inklet.vstack([
        captioned("a", "two-photon rig; one projection, arrows clipped on each "
                       "component's own outline", panel_a(178.0), width=150),
        inklet.hstack([
            captioned("b", "left cortex, lateral", panel_b(84.0), width=80),
            captioned("c", "head-fixed preparation", panel_c(84.0), width=80),
        ], gap=10.0, align="top"),
    ], gap=9.0, align="left"))

    out = Path(__file__).with_suffix(".svg")
    fig.save(out)
    print(f"drawn in {time.perf_counter() - started:.1f} s -> {out}")
    print(fig.report(rules=["EMPTY_DIAGRAM", "FONT_SUBSTITUTED", "HAIRLINE",
                            "INCONSISTENT_STROKE", "LINK_COLLAPSED",
                            "LINK_CROSSES", "LOW_CONTRAST", "LOW_DPI",
                            "OFF_CANVAS", "ROUTE_BLOCKED", "TEXT_OVERFLOW",
                            "TINY_TEXT"]))
