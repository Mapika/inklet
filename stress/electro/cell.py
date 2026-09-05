"""Panels a-b: the hardware the experiment runs in, and the crystal it runs on.

Two views of the same object at nine orders of magnitude apart:

* `panel_a` is the flow cell exploded along its stack axis -- nine components,
  two tie bolts and the four streams that cross the stack, all framed through
  **one** `inklet.scene` camera so a plate is the size it would be on the bench
  and a near part paints over a far one.
* `panel_b` is the cuprite unit cell built atom by atom from parametric
  meshes -- spheres, trimmed bond cylinders and edge rods in one projection --
  with the lattice constant taken off the drawing by a dimension line rather
  than asserted beside it.

Both work to `common.fit`'s width contract and take every colour from the
theme; the one identity that crosses panels is the catalyst's vermillion,
which is the same `theme.color` slot on the thin layer in (a) and on the Cu
atoms in (b).

Run it:

    .venv/bin/python stress/electro/cell.py
    scripts/rasterise.sh stress/electro/cell.svg stress/electro/cell.png 3
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Sequence

import inklet
from inklet import Diagram, Vec2
from inklet.core.geom import Rect
from inklet.three import Camera, Mat4, Mesh, Vec3, anchor3d, build

try:
    from . import common
except ImportError:                                     # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from electro import common

__all__ = ["panel_a", "panel_b"]

#: One camera for the whole stack. A shallow azimuth keeps the exploded axis
#: nearly horizontal across a full-width panel -- true isometric would run a
#: nine-part train diagonally off the page -- and sixteen degrees of lift is
#: enough for the plates to show a top face without foreshortening the gaps
#: the eye needs to read "exploded".
STACK = Camera(azimuth=20.0, elevation=16.0)

#: The unit cell, three-quarter. Turned far enough off face-on that all three
#: cell directions read, but shy of true isometric, where the body-centre
#: oxygen would sit exactly behind a corner one and the Cu-O geometry would
#: collapse into it.
CELL = Camera(azimuth=28.0, elevation=20.0)


# -- shared helpers (the idiom of stress/panels/apparatus) -----------------


def _mesh_stroke(theme) -> float:
    """`common.model_stroke`, clamped to the print floor.

    The shared helper thins model ink to 0.62 of a hairline because a dense
    line-art mesh puts thousands of strokes on the page. These scenes put
    tens, and 0.081mm is under the 0.088mm the HAIRLINE rule (and the press)
    accepts -- so the outline is clamped back up to the hairline, where the
    backend's own crease floor already puts the crease lines beside it.
    """
    return max(common.model_stroke(theme), theme.hairline)


def _at(node: Diagram, x: float, y: float, anchor: str = "center") -> Diagram:
    """Move a node so `anchor` lands on (x, y) of the frame being drawn in."""
    here = node.transform.apply(node.anchor_point(anchor))
    return node.translated(x - here.x, y - here.y)


def _extent(box: Rect, direction: Vec2) -> float:
    """How far a box reaches from its own centre along a direction."""
    return abs(direction.x) * box.width / 2.0 + abs(direction.y) * box.height / 2.0


def _outward(node: Diagram, anchor: Vec2, direction: Vec2, clearance: float,
             from_box: Rect | None = None) -> Diagram:
    """Push a node clear of something, along a direction, by what it measures.

    The distance is the two half-extents plus the clearance, so a wide label
    clears as surely as a tall one and no call site ever types a millimetre.
    """
    unit = direction.normalized()
    reach = 0.0 if from_box is None else _extent(from_box, unit)
    step = reach + clearance + _extent(node.local_bbox, unit)
    here = anchor + unit * step
    return _at(node, here.x, here.y)


def _orient(direction: Vec3) -> Mat4 | None:
    """The rotation that takes a solid's +z onto `direction` -- every
    parametric solid in `inklet.three` is built z-up."""
    n = direction.normalized()
    z = Vec3(0.0, 0.0, 1.0)
    axis = z.cross(n)
    if axis.length < 1e-9:
        return None if n.dot(z) > 0.0 else Mat4.rotation(Vec3(1.0, 0.0, 0.0), 180.0)
    angle = math.degrees(math.acos(max(-1.0, min(1.0, z.dot(n)))))
    return Mat4.rotation(axis.normalized(), angle)


def _rod(p: Vec3, q: Vec3, radius: float, *, segments: int = 16,
         trim_p: float = 0.0, trim_q: float = 0.0) -> Mesh:
    """A cylinder from `p` to `q`, optionally stopped short of either end.

    The trims are what keep a stick out of the ball it runs to: a bond drawn
    centre-to-centre pokes its end cap through the far sphere's silhouette
    whenever the painter puts the bond on top, and trimming it back to the
    sphere's surface removes the overlap instead of hoping the sort hides it.
    """
    axis = q - p
    unit = axis.normalized()
    a = p + unit * trim_p
    b = q - unit * trim_q
    length = (b - a).length
    mesh = build("cylinder", radius=radius, height=length, segments=segments)
    turn = _orient(unit)
    if turn is not None:
        mesh = mesh.transformed(turn)
    return mesh.transformed(Mat4.translation((a + b) * 0.5))


def _row_ladder(points: dict[str, Vec2], texts: dict[str, Diagram],
                y: float, gap: float) -> dict[str, Diagram]:
    """A row of labels above the drawing, in the order of their targets.

    `apparatus._ladder` turned sideways: two leaders can only cross if the
    labels they run to are out of order, so the labels are sorted by their
    target's x and pushed apart until none overlaps, then the row is recentred
    on the targets so spreading pushes both ends out rather than dragging the
    whole row to the right.
    """
    order = sorted(points, key=lambda name: (points[name].x, name))
    widths = [texts[name].local_bbox.width for name in order]
    xs = [points[name].x for name in order]
    for i in range(1, len(order)):
        floor = xs[i - 1] + (widths[i - 1] + widths[i]) / 2.0 + gap
        xs[i] = max(xs[i], floor)
    wanted = sum(points[name].x for name in order) / len(order)
    shift = wanted - sum(xs) / len(xs)
    return {name: _at(texts[name], x + shift, y) for name, x in zip(order, xs)}


# =====================================================================
# a -- the exploded cell stack
# =====================================================================

# The stack, in its own units, anode at -x. Face sizes and thicknesses are
# proportioned to read, not to scale: a real membrane is 50 um against 20 mm
# of end plate, and drawn honestly it is thinner than its own outline. The
# *order* is the physics: anolyte hardware, membrane between its gaskets,
# then catalyst on GDL -- the electrode the figure is about -- and the gas
# side's plumbing.

_END_FACE = 3.8       # end plates overhang the working parts, as clamps do
_INNER_FACE = 3.4
_RING_R = 1.25        # gasket ring, framing the active area
_RING_TUBE = 0.10
_GAP = 0.85           # the explosion, face to face
#: Wider around the gaskets: a ring is short, so a leader from the ladder has
#: to descend past its neighbours' top corners to reach it, and the corridor
#: it descends through is this gap minus what those corners overhang.
_RING_GAP = 1.05
_BOLT_Y = 1.42        # tie bolts, across the stack
_BOLT_Z = 0.70        # ... and up it
_ROD_R = 0.11
_HOLE_R = 0.155       # the hole the bolt passes through, on the face it enters
#: A bolt hole is two millimetres across on the printed page. Twelve sides is
#: already below what the line weight can resolve there, and every side is a
#: rim edge to hide and a wall facet to sort, twenty-eight times over.
_HOLE_SIDES = 12
_STUB = 0.28          # thread showing beyond each end plate
#: Shorter than this, in stack units, a surviving stretch of bolt is a dot
#: rather than a rod, and reads as dirt on the plate.
_MIN_RUN = 0.05
#: How far short of the face it comes out at a merged rod stops, so that its
#: end cap is inside the plate rather than coplanar with the plate's own face,
#: where two facets in one plane have no order between them.
_SUNK = 0.03

#: Four tie bolts, which is how a stack is actually clamped, and the drawing
#: whose whole job is to say what the cell is made of should not pretend
#: otherwise. Two of them are on the camera's side and thread the exploded
#: gaps in full; of the other two the eye gets what the plates leave -- the
#: wider gaps towards the cathode, and four nuts standing proud of the end
#: plate -- which is exactly what a photograph from here would get.
#:
#: `_BOLT_Z` is half `_BOLT_Y` and that is not decoration. A bolt at the top
#: corners clears the plates' top edges in this view -- the elevation lifts
#: the far pair *over* the stack rather than hiding it behind -- and a rod
#: across the top of the drawing is a fence every ladder leader has to cross.
#: Kept below 0.75 the far pair stays behind the plates, where it belongs.
_BOLTS = (
    ("near-low", -_BOLT_Y, -_BOLT_Z),
    ("near-high", -_BOLT_Y, _BOLT_Z),
    ("far-low", _BOLT_Y, -_BOLT_Z),
    ("far-high", _BOLT_Y, _BOLT_Z),
)

#: name, axial thickness, face size (None for a gasket ring), gap before.
_STACK: tuple[tuple[str, float, float | None, float], ...] = (
    ("anode_end", 0.55, _END_FACE, 0.0),
    ("anode_flow", 0.32, _INNER_FACE, _GAP),
    ("gasket_a", 2.0 * _RING_TUBE, None, _RING_GAP),
    ("membrane", 0.07, _INNER_FACE, _RING_GAP),
    ("gasket_c", 2.0 * _RING_TUBE, None, _RING_GAP),
    ("catalyst", 0.07, _INNER_FACE, _RING_GAP),
    # The catalyst layer is deposited on the GDL; the small gap keeps the two
    # readable as one electrode that has been peeled, not as strangers.
    ("gdl", 0.20, _INNER_FACE, 0.30),
    ("cathode_flow", 0.32, _INNER_FACE, _GAP),
    ("cathode_end", 0.55, _END_FACE, _GAP),
)

_STACK_TEXT = {
    "anode_end": "anode\nend plate",
    "anode_flow": "anode\nflow field",
    "gasket_a": "gasket",
    "membrane": "anion-exchange\nmembrane",
    "gasket_c": None,          # the second ring reads off the first's label
    "catalyst": "Cu_{2}O\ncatalyst",
    "gdl": "gas-diffusion\nlayer",
    "cathode_flow": "cathode\nflow field",
    "cathode_end": "cathode\nend plate",
}


def _stack_spans() -> dict[str, tuple[float, float]]:
    """Axial extent of every component, centred on the drawing's origin."""
    spans: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for name, thickness, _, gap in _STACK:
        left = cursor + gap
        spans[name] = (left, left + thickness)
        cursor = left + thickness
    middle = cursor / 2.0
    return {name: (a - middle, b - middle) for name, (a, b) in spans.items()}


def _stack_colors(theme) -> dict[str, str]:
    """Material classes, all derived from the theme.

    Two greys tell the machined frame from the carbon it clamps -- flow
    plates and GDL are graphite-dark, the frame is bare metal -- and the
    saturated slots are kept for the parts with chemistry in them: membrane,
    elastomer, and the catalyst's vermillion, which is the colour Cu2O keeps
    across the whole figure (panel b paints its Cu atoms with the same slot).
    """
    return {
        "frame": theme.muted,
        "flow": inklet.darken(theme.muted, 0.30),
        "gdl": inklet.darken(theme.muted, 0.55),
        "membrane": theme.color(2),
        "gasket": theme.color(1),
        "catalyst": theme.color(6),
    }


# -- the stack ------------------------------------------------------------


def _stack_parts(theme) -> list[tuple[str, Mesh, dict]]:
    """Every solid in the assembly, in the order the cell is built up.

    Nothing here works out what hides what. Four tie bolts run the whole
    length of the clamp, straight through nine plates and two gasket rings,
    and the scene is asked for `order="exact"` -- one mesh, one hidden-line
    pass, depth settled facet by facet -- so a rod is cut exactly where a
    plate's outline crosses it and the far pair disappears behind the plates
    the way it would from this side of the bench.

    That is a recent thing. `inklet.scene` used to give each part one depth
    number, its centre's, and a bolt threaded through nine plates has no
    single number that ranks it against all of them: it came out lying on a
    face it passes through, and the panel carried sixty lines of ray-box
    arithmetic to cut each rod up and hand the pieces to the plates that would
    otherwise have painted over them. All of that is now the library's job.
    """
    colors = _stack_colors(theme)
    material = {"anode_end": "frame", "anode_flow": "flow", "gasket_a": "gasket",
                "membrane": "membrane", "gasket_c": "gasket",
                "catalyst": "catalyst", "gdl": "gdl", "cathode_flow": "flow",
                "cathode_end": "frame"}
    spans = _stack_spans()
    parts: list[tuple[str, Mesh, dict]] = []

    for name, thickness, face, _ in _STACK:
        x = (spans[name][0] + spans[name][1]) / 2.0
        if face is None:
            mesh = build("torus", radius=_RING_R, tube=_RING_TUBE)
            turn = _orient(Vec3(1.0, 0.0, 0.0))     # ring axis along the stack
            mesh = mesh.transformed(turn).transformed(
                Mat4.translation(Vec3(x, 0.0, 0.0)))
        else:
            mesh = build("box", size_x=thickness, size_y=face,
                         size_z=face).transformed(
                Mat4.translation(Vec3(x, 0.0, 0.0)))
            # Four real bolt holes, straight through. Without them a rod
            # entering a plate is a rod stopping *on* a plate: correct in
            # three dimensions, and on the page indistinguishable from a stick
            # laid across the face. This panel used to fake each one with a
            # dark disc parked a hundredth of a unit proud of the face, which
            # read right from here and was a sticker -- the plate behind it
            # was solid, and the far side of the stack showed nothing.
            # `Mesh.drill` cuts the hole, so the rim is a real edge and the
            # inner wall is real geometry the shading can darken.
            mesh = mesh.grouped(name)
            for _, y, z in _BOLTS:
                mesh = mesh.drill("x", radius=_HOLE_R, at=(x, y, z),
                                  segments=_HOLE_SIDES, group="hole")
        parts.append((name, mesh,
                      {"color": colors[material[name]],
                       "colors": {name: colors[material[name]],
                                  "hole": inklet.darken(colors[material[name]],
                                                     0.45)}}))

    plates = [name for name, _, face, _ in _STACK if face is not None]
    first, last = spans[plates[0]][0], spans[plates[-1]][1]
    for tag, y, z in _BOLTS:
        parts.append((f"rod-{tag}",
                      _rod(Vec3(first - _STUB, y, z),
                           Vec3(last + _STUB, y, z), _ROD_R),
                      {"color": colors["frame"]}))
        # A six-segment cylinder is a hexagonal prism: the head and the nut.
        for suffix, x in (("head", first - _STUB - 0.11),
                          ("nut", last + _STUB + 0.11)):
            hexagon = build("cylinder", radius=0.30, height=0.22, segments=6)
            hexagon = hexagon.transformed(_orient(Vec3(1.0, 0.0, 0.0)))
            parts.append((f"{suffix}-{tag}",
                          hexagon.transformed(Mat4.translation(Vec3(x, y, z))),
                          {"color": colors["frame"]}))
    return parts


def _stack_scene(scene_width: float, theme) -> tuple[
        Diagram, dict[str, Diagram], dict[str, Rect]]:
    """The whole assembly in one projection, and where each part landed."""
    parts = _stack_parts(theme)
    node = inklet.scene(parts, width=scene_width, view=STACK, style="shaded",
                     order="exact", stroke_width=_mesh_stroke(theme),
                     name="stack")
    nodes = {name: node.find(name) for name, _, _ in parts}
    placed = inklet.resolve(node)
    return node, nodes, {name: placed[n.id].bbox for name, n in nodes.items()}


#: The four streams, page-space directions out of the end plates they port
#: through (a real stack manifolds its fluids through the end plates, which
#: is what lets the arrows live at the corners instead of fighting the ladder
#: for the space above the flow fields). y grows downward on the page.
_FLOWS = (
    # name, plate, direction, label, phase, into the stack?
    # KOH comes in steeply. The obvious 45 degrees runs the arrow straight
    # down the line the low near-side bolt head stands on -- the head is at
    # the plate's lower-left corner and its own diagonal is 45 degrees too --
    # so the port is taken from below the plate instead of beside it.
    ("koh", "anode_end", Vec2(-0.32, 1.0), "1 M KOH", "liquid", True),
    ("o2", "anode_end", Vec2(-0.95, -0.75), "O_{2}", "gas", False),
    # The cathode streams port through the *edge* of the end plate rather than
    # straight out of its face, because the two far tie bolts stand off that
    # face on this side and a stream drawn across a nut reads as coming out of
    # the nut. Steeper in than out: the inbound arrow arrives between the
    # nuts, the outbound one leaves above them.
    ("co2", "cathode_end", Vec2(1.0, 0.95), "CO_{2}", "gas", True),
    ("out", "cathode_end", Vec2(0.95, -1.5),
     f"{common.SPECIES_LABEL['C2H4']} + {common.SPECIES_LABEL['CO']}",
     "gas", False),
)

#: One dash for everything liquid, written once. Given as a tuple here and as
#: the SVG-idiom string in the legend below -- the style layer accepts both.
_LIQUID_DASH = (1.2, 0.8)


def _flow_styles(theme) -> dict[str, inklet.Style]:
    """Gas solid, liquid dashed, in two palette slots the stack does not use."""
    return {
        "gas": inklet.Style(stroke=theme.color(5), stroke_width=theme.thick,
                         fill=theme.color(5)),
        "liquid": inklet.Style(stroke=theme.color(3), stroke_width=theme.thick,
                            stroke_dash=_LIQUID_DASH, fill=theme.color(3)),
    }


def _panel_a_content(scene_width: float) -> Diagram:
    theme = inklet.current_theme()
    stack, nodes, boxes = _stack_scene(scene_width, theme)
    rect = stack.local_bbox
    clear = theme.gap("m")

    # -- the ladder ----------------------------------------------------
    texts = {name: inklet.label(body, align="center")
             for name, body in _STACK_TEXT.items() if body}
    named = list(texts)
    # The row clears the plates it captions, not the whole scene: the scene's
    # own top edge already is the plates' top edge here, but measuring the
    # labelled parts keeps that true if a taller part is ever added.
    row_y = (min(boxes[name].y0 for name in named) - clear
             - max(texts[name].local_bbox.height for name in named) / 2.0)
    targets = {name: stack.anchor_point(name) for name in named}
    ladder = _row_ladder(targets, texts, row_y, theme.gap("xs"))

    items: list[Diagram] = [stack]
    items += [ladder[name] for name in named]

    # -- stream labels at the corners -----------------------------------
    flow_text = {name: inklet.label(body) for name, _, _, body, _, _ in _FLOWS}
    for name, plate, direction, _, _, _ in _FLOWS:
        # Pushed off the plate along the arrow's own direction by an extra
        # "xl" so the shaft between plate and label is long enough to read
        # as a stream and not as a tick.
        items.append(_outward(flow_text[name], stack.anchor_point(plate),
                              direction, theme.gap("xl"), boxes[plate]))

    # -- the tie bolt's tag ---------------------------------------------
    # Labelled at the low near-side nut: it stands clear of the cathode end
    # plate's bottom corner, so the leader reaches it without crossing a
    # plate, and it is on the bolt whose whole run through the stack is
    # visible -- pointing at a nut whose rod is hidden would name a part the
    # reader cannot follow.
    bolt_text = inklet.label("tie bolt")
    bolt_tag = _outward(bolt_text, stack.anchor_point("nut-near-low"),
                        Vec2(0.85, 0.6), theme.gap("m"), boxes["cathode_end"])
    items.append(bolt_tag)

    # -- furniture -------------------------------------------------------
    # The frame goes under the anode end, the key beside it: the band below
    # the stack is the one strip of paper no stream or leader wants, because
    # the bolts hold the mid-plane and the streams hold the corners.
    frame = inklet.axes(width=11.0, view=STACK, labels=("x", "y", "z"),
                     style="shaded", color=theme.muted,
                     stroke_width=_mesh_stroke(theme))
    styles = _flow_styles(theme)
    key = inklet.legend(
        [("gas", inklet.polyline([(0, 0), (5.5, 0)], stroke=theme.color(5),
                              stroke_width=theme.thick)),
         ("liquid", inklet.polyline([(0, 0), (5.5, 0)], stroke=theme.color(3),
                                 stroke_width=theme.thick,
                                 stroke_dash="1.2,0.8"))],
        title="streams")
    band_y = rect.y1 + theme.gap("s")
    items.append(_at(frame, rect.x0 + frame.local_bbox.width / 2.0,
                     band_y + frame.local_bbox.height / 2.0))
    items.append(_at(key, rect.x0 + frame.local_bbox.width + theme.gap("l")
                     + key.local_bbox.width / 2.0,
                     band_y + key.local_bbox.height / 2.0))

    content = inklet.place(items)

    # -- links ------------------------------------------------------------
    links: list[inklet.Link] = []
    for name, plate, _, _, phase, inward in _FLOWS:
        ends = ((flow_text[name], nodes[plate]) if inward
                else (nodes[plate], flow_text[name]))
        links.append(inklet.link(*ends, style=styles[phase], standoff=0.6,
                              arrow_size=theme.arrow_size, name=f"flow-{name}"))
    # A leader down into an exploded stack has to cross the plates standing
    # in front of the one it names -- that is what "exploded" means, and at
    # 184.6mm the gas-diffusion layer's leader clips the catalyst layer by
    # 1.94mm where at 178mm it just misses. Declaring the whole stack as
    # `through=` states the convention once instead of leaving the panel
    # clean at one width and not another. The whole stack, not the labelled
    # part of it: the second gasket carries no label of its own and is still
    # a ring the catalyst's leader has to come down through.
    links += [inklet.link(ladder[name], nodes[name], kind="line", head="none",
                       style=common.hair(theme), standoff=0.45,
                       name=f"tag-{name}",
                       through=tuple(nodes[other] for other in _STACK_TEXT
                                     if other != name))
              for name in named]
    # The nut is *on* the end plate's face, so the leader that names it has
    # to run across the plate to get out to clear paper; that is what a
    # leader to a fastener does on every assembly drawing ever printed.
    links.append(inklet.link(bolt_text, nodes["nut-near-low"], kind="line",
                          head="none", style=common.hair(theme), standoff=0.45,
                          name="tag-bolt", through=(nodes["cathode_end"],)))
    routed = inklet.route_all(links, inklet.resolve(content))
    return Diagram(children=(content, routed), kind="panel")


def panel_a(width: float = 178.0) -> Diagram:
    """Exploded electrolyser stack, full width."""
    return common.fit(_panel_a_content, width)


# =====================================================================
# b -- the Cu2O unit cell
# =====================================================================

#: Cuprite, in cell units. Oxygen on the bcc positions, copper on half the
#: tetrahedral holes; each Cu is linearly coordinated between the body-centre
#: O and its nearest corner. The lattice constant and the bond length quoted
#: in the annotations follow from these positions, not the other way round.
_A_NM = 0.427
_BOND_NM = _A_NM * math.sqrt(3.0) / 4.0    # 0.185: the Cu-O half-diagonal

_O_SITES = tuple((float(i), float(j), float(k))
                 for i in (0, 1) for j in (0, 1) for k in (0, 1)) + ((0.5, 0.5, 0.5),)
_CU_SITES = ((0.25, 0.25, 0.25), (0.75, 0.75, 0.25),
             (0.75, 0.25, 0.75), (0.25, 0.75, 0.75))

#: Display radii, in cell units. Ionic radii would put O at 1.4 A against the
#: 4.27 A cell and bury the bonds; these are ball-and-stick proportions,
#: which is the register every crystal-structure figure uses.
_R_O = 0.13
_R_CU = 0.10
_BOND_R = 0.024
_EDGE_R = 0.010


def _cell_parts(theme) -> tuple[list[tuple[str, Mesh, dict]], str]:
    """Atoms, bonds, cell edges and the facet plane, plus the name of the
    bond the annotation points at."""
    o_color = theme.color(2)
    cu_color = theme.color(6)      # the catalyst's slot, same as panel a
    parts: list[tuple[str, Mesh, dict]] = []

    for i, site in enumerate(_O_SITES):
        mesh = build("sphere", radius=_R_O, subdivisions=2).transformed(
            Mat4.translation(Vec3(*site)))
        parts.append((f"o-{i}", mesh, {"color": o_color}))
    for i, site in enumerate(_CU_SITES):
        mesh = build("sphere", radius=_R_CU, subdivisions=2).transformed(
            Mat4.translation(Vec3(*site)))
        parts.append((f"cu-{i}", mesh, {"color": cu_color}))

    # Each Cu bonds to the body centre and to the corner it rounds to --
    # rounding *is* the crystallography here, since every Cu sits a quarter
    # diagonal off its corner.
    bond_name = ""
    for i, cu in enumerate(_CU_SITES):
        corner = tuple(float(round(c)) for c in cu)
        for j, o_site in enumerate(((0.5, 0.5, 0.5), corner)):
            name = f"bond-{i}-{j}"
            options: dict = {"color": theme.muted}
            if (i, j) == (0, 0):
                # This bond runs from the front-lower-left Cu to the body
                # centre, which puts the whole of it behind the {111} plane --
                # and its *centre*, which is all a per-part depth sort has to
                # go on, in front of the plane's. It came out drawn unveiled
                # over a plane it is behind, next to two Cu atoms the same
                # plane correctly veils. `inklet.lint` now finds that
                # (DEPTH_ORDER); this is the answer it suggests.
                options["behind"] = "facet"
            parts.append((name,
                          _rod(Vec3(*cu), Vec3(*o_site), _BOND_R, segments=12,
                               trim_p=_R_CU, trim_q=_R_O),
                          options))
            if cu == (0.25, 0.25, 0.25) and o_site == corner:
                # The bond into the (0,0,0) corner: front-lower-left, on the
                # one flank of the cell the facet plane below leaves
                # uncovered, so its callout can land without writing over
                # the translucent plane.
                bond_name = name

    # Edges named by the corners they join, because two of them are load-
    # bearing for the annotations: a leader into a cage has to step over one
    # rod of it, and `through=` needs that rod by name.
    edges = [(a, b) for a in _O_SITES[:8] for b in _O_SITES[:8]
             if a < b and sum(x != y for x, y in zip(a, b)) == 1]
    code = lambda p: "".join(str(int(c)) for c in p)
    for a, b in edges:
        parts.append((f"edge-{code(a)}-{code(b)}",
                      _rod(Vec3(*a), Vec3(*b), _EDGE_R, segments=8,
                           trim_p=_R_O, trim_q=_R_O),
                      {"color": theme.muted}))

    # A {111} plane through three corners. Not x+y+z=1, though it is the one
    # everybody writes first: this camera sees that member of the family
    # within two degrees of edge-on, and it projects to an invisible sliver.
    # The (1,-1,1) member faces the viewer almost squarely, and cuts the cell
    # through three corner oxygens without touching any other atom.
    # Translucent, so the atoms behind it stay legible; an open triangle, so
    # it shades from both sides and never culls itself away.
    facet = Mesh((Vec3(1.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0),
                  Vec3(1.0, 1.0, 1.0)), ((0, 1, 2),), name="facet")
    # Light enough that the atoms behind it keep the colours the key gives
    # them; the plane only has to read as a plane, not as a filter.
    parts.append(("facet", facet, {"color": theme.accent, "opacity": 0.28}))
    return parts, bond_name


def _panel_b_content(scene_width: float) -> Diagram:
    theme = inklet.current_theme()
    parts, bond_name = _cell_parts(theme)
    cell = inklet.scene(parts, width=scene_width, view=CELL, style="shaded",
                     stroke_width=_mesh_stroke(theme), name="cell")
    # The front-bottom cell edge, projected: the ends of the dimension line.
    anchor3d(cell, "a0", (0.0, 0.0, 0.0))
    anchor3d(cell, "a1", (1.0, 0.0, 0.0))
    rect = cell.local_bbox

    items: list[Diagram] = [cell]

    # -- lattice constant, as a drawing dimension ------------------------
    p0 = cell.anchor_point("a0")
    p1 = cell.anchor_point("a1")
    rule_y = rect.y1 + theme.gap("m")
    for p in (p0, p1):
        items.append(inklet.polyline(
            [(p.x, p.y + _R_O * _page_scale(cell)), (p.x, rule_y + theme.gap("xs"))],
            stroke=theme.muted, stroke_width=theme.hairline))
    items.append(inklet.polyline([(p0.x, rule_y), (p1.x, rule_y)],
                              stroke=theme.ink, stroke_width=theme.hairline))
    items += [_at(inklet.marker("diamond", 1.1, fill=theme.ink, stroke="none"),
                  p.x, rule_y) for p in (p0, p1)]
    glyph = inklet.label(f"a = {_A_NM:g} nm")
    items.append(_outward(glyph, Vec2((p0.x + p1.x) / 2.0, rule_y),
                          Vec2(0.0, 1.0), theme.gap("xs")))

    # -- annotations -----------------------------------------------------
    # Both leaders have to enter the cage of cell edges to reach what they
    # name, so each is routed through open face area and declares, by name,
    # the one edge rod it steps over -- the same `through=` a beam uses for
    # the optic it legitimately passes.
    bond_text = inklet.label(f"Cu–O\n{_BOND_NM:.3f} nm", align="center")
    # Fully outside the projection's left edge, level with the bond it names:
    # pushed off the bond itself it lands against the left cage rod, and the
    # honest clearance is from the whole drawing, not from one part of it.
    bond_tag = _at(bond_text, rect.x0 - theme.gap("s")
                   - bond_text.local_bbox.width / 2.0,
                   cell.anchor_point(bond_name).y)
    # The facet is labelled where it meets the top face: a point on its own
    # boundary, pinned, because a near-vertical leader from above crosses
    # nothing but the top rear rod -- every path to the plane's interior
    # would cross an atom.
    anchor3d(cell, "facet-rim", (0.5, 0.5, 1.0))
    anchor3d(cell, "rim-end", (0.0, 1.0, 1.0))
    facet_text = inklet.label("{111}")
    rim = cell.anchor_point("facet-rim")
    # The rod the leader steps over climbs across the label's width, so the
    # label clears the rod's high end -- the corner it springs from -- not
    # merely the point straight below.
    rod_top = cell.anchor_point("rim-end").y - _EDGE_R * _page_scale(cell)
    facet_tag = _at(facet_text, rim.x,
                    rod_top - theme.gap("s")
                    - facet_text.local_bbox.height / 2.0)
    items += [bond_tag, facet_tag]

    # -- key, in the empty top-left corner -------------------------------
    # A cube's silhouette is a hexagon, so the bounding box's corners are
    # real paper; the top-left one is the far corner from both annotations.
    dot = theme.font_size * 1.1
    key = inklet.legend(
        [("Cu", inklet.marker("circle", dot, fill=theme.color(6), stroke="none")),
         ("O", inklet.marker("circle", dot, fill=theme.color(2), stroke="none"))],
        title="Cu_{2}O (cuprite)")
    items.append(_at(key, rect.x0 + key.local_bbox.width / 2.0,
                     rect.y0 + key.local_bbox.height / 2.0))

    content = inklet.place(items)
    links = [
        inklet.link(bond_text, cell.find(bond_name), kind="line", head="none",
                 style=common.hair(theme), standoff=0.4, name="tag-bond",
                 through=(cell.find("edge-000-001"),)),
        inklet.link(facet_text, cell.at("facet-rim"), kind="line", head="none",
                 style=common.hair(theme), standoff=0.4, name="tag-facet",
                 through=(cell.find("edge-011-111"),)),
    ]
    routed = inklet.route_all(links, inklet.resolve(content))
    return Diagram(children=(content, routed), kind="panel")


def _page_scale(cell: Diagram) -> float:
    """Page millimetres per cell unit, read off the fitted camera."""
    from inklet.three import view_of
    return view_of(cell).scale


def panel_b(width: float = 87.0) -> Diagram:
    """The cuprite unit cell, one column."""
    return common.fit(_panel_b_content, width)


# -- looking at it --------------------------------------------------------

if __name__ == "__main__":
    import time

    started = time.perf_counter()
    inklet.use_theme("nature")

    a = panel_a(common.FULL)
    b = panel_b(common.COLUMN)
    fig = inklet.figure(width=common.PAGE_WIDTH)
    fig.add(inklet.vstack([common.titled("a", a), common.titled("b", b)],
                       gap=6.0, align="left"))
    out = Path(__file__).with_suffix(".svg")
    fig.save(out)
    print(f"drawn in {time.perf_counter() - started:.1f} s -> {out}")
    # The report's CROWDING infos are all part-against-part inside the two
    # scenes: bolts in their holes, gaskets against the plates they seal,
    # bonded atoms tangent to their bonds. Those parts touch because the
    # hardware does; the linter is describing the assembly, not a mistake.
    print(fig.report())
    for letter, node in (("a", a), ("b", b)):
        print(f"panel_{letter}: {node.bbox.width:.2f} x "
              f"{node.bbox.height:.2f} mm")
