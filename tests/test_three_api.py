"""The authoring surface: `inklet.model`, `inklet.solid`, `inklet.scene`, `inklet.axes`.

What is being defended here is the promise the whole package exists to make --
that a 3D object behaves like every other node. It sizes itself to a width in
millimetres, it stacks, it takes the theme's colours, an arrow finds its
silhouette rather than its bounding box, and it emits the same bytes twice.
A scene adds one promise on top: several objects in one projection, at one
scale, with the near ones drawn over the far ones.
"""

from __future__ import annotations

import collections
import hashlib
import itertools
import math
import os
import re
import subprocess
import sys
import textwrap

import pytest

import inklet
from inklet.core import Vec2, flatten, resolve
from inklet.diagnostics import lint
from inklet.three import (
    MODEL_KIND, Mat4, Mesh, MeshError, SILHOUETTE_KIND, Vec3, anchor3d,
    available_backends, backends, build, page_scale, register_backend, view_of,
)
from inklet.three.api import _refined
from inklet.three.backend import Look, Rendering, Request, _BACKENDS, render
from inklet.three import solids
from inklet.three.solids import cube, cylinder, segments_for, sphere


def extent(node):
    return node.bbox


# -- sizing ---------------------------------------------------------------


@pytest.mark.parametrize("width", [6.0, 20.0, 63.5])
def test_a_solid_comes_out_the_width_it_was_asked_for(width):
    # The auto-fit is the contract: the author names millimetres and never
    # learns what the model's units were.
    node = inklet.solid("cube", width=width, view="isometric")
    assert extent(node).width == pytest.approx(width, rel=1e-9)


def test_height_alone_fits_the_height():
    node = inklet.solid("cylinder", height=15.0, view="front")
    assert extent(node).height == pytest.approx(15.0, rel=1e-9)


def test_both_dimensions_fit_inside_the_box():
    node = inklet.solid("box", width=30.0, height=6.0, size_x=3.0, view="front")
    rect = extent(node)
    assert rect.width <= 30.0 + 1e-9 and rect.height <= 6.0 + 1e-9


def test_a_width_in_a_string_is_a_unit():
    assert extent(inklet.solid("cube", width="12mm")).width == pytest.approx(12.0)


def test_the_default_width_is_used_when_nothing_is_said():
    from inklet.three import DEFAULT_WIDTH

    assert extent(inklet.solid("cube")).width == pytest.approx(DEFAULT_WIDTH)


def test_the_node_is_centred_on_its_own_origin():
    # Everything in inklet is. A model that is not would drift when stacked.
    rect = extent(inklet.solid("cone", width=20.0, view="three-quarter"))
    assert rect.center.x == pytest.approx(0.0, abs=1e-9)
    assert rect.center.y == pytest.approx(0.0, abs=1e-9)


def test_a_model_stacks_like_any_other_node():
    row = inklet.hstack([inklet.solid("cube", width=10.0), inklet.box("label")], gap=4.0)
    assert row.bbox.width > 14.0


# -- styles ---------------------------------------------------------------


@pytest.mark.parametrize("style", ["lineart", "shaded", "solid", "wireframe"])
def test_every_style_draws_something(style):
    svg = _svg((inklet.solid("cube", width=20.0, style=style)))
    assert svg.count("<path") >= 1


def test_wireframe_draws_more_paths_than_line_art():
    ball = sphere(0.5, subdivisions=1)
    wire = _svg((inklet.model(ball, width=20.0, style="wireframe")))
    line = _svg((inklet.model(ball, width=20.0, style="lineart")))
    assert len(wire) > len(line)


def test_an_unknown_style_lists_the_known_ones():
    with pytest.raises(MeshError, match="lineart"):
        inklet.solid("cube", width=10.0, style="cel")


def test_hidden_false_keeps_the_back_edges():
    shown = _svg((inklet.solid("cube", width=20.0, hidden=False)))
    hidden = _svg((inklet.solid("cube", width=20.0, hidden=True)))
    assert len(shown) > len(hidden)


def test_colour_is_taken_from_the_theme_not_hard_coded():
    svg = _svg((inklet.solid("cube", width=20.0, style="shaded")))
    assert "#000000" not in svg or inklet.current_theme().ink_color != "#000000"


def test_an_explicit_colour_reaches_the_output():
    svg = _svg((inklet.solid("cube", width=20.0, style="shaded",
                                       color="#ff00aa")))
    assert "ff" in svg.lower()


# -- anchors --------------------------------------------------------------


def test_a_named_3d_anchor_lands_where_the_projection_says():
    # The stated feature: an author names a point on the object in 3D and gets
    # a 2D anchor an arrow can aim at.
    node = inklet.solid("cube", width=20.0, view="front",
                     anchors={"top": (0.0, 0.0, 0.5)})
    where = node.anchor_point("top")
    assert where.x == pytest.approx(0.0, abs=1e-9)
    assert where.y == pytest.approx(-10.0, rel=1e-9)   # page y grows downward


def test_anchors_move_with_the_view():
    front = inklet.solid("cube", width=20.0, view="front",
                      anchors={"corner": (0.5, -0.5, 0.5)}).anchor_point("corner")
    right = inklet.solid("cube", width=20.0, view="right",
                      anchors={"corner": (0.5, -0.5, 0.5)}).anchor_point("corner")
    assert front != right


def test_anchor_point_is_local_and_placement_point_is_world():
    # The trap this package had to be careful about, pinned so it stays true.
    node = inklet.solid("cube", width=20.0, view="front", anchors={"top": (0, 0, 0.5)})
    fig = _figure(inklet.hstack([inklet.box("x"), node], gap=10.0))
    _, places = fig.build()
    assert node.anchor_point("top").x == pytest.approx(0.0, abs=1e-9)
    assert abs(places[node.id].point("top").x) > 1.0


def test_face_groups_become_anchors_automatically():
    frame = inklet.solid("axes", width=20.0)
    for name in ("x", "y", "z"):
        assert frame.anchor_point(name) is not None


def test_an_explicit_anchor_beats_a_group_of_the_same_name():
    mesh = cube(1.0).grouped("body")
    node = inklet.model(mesh, width=20.0, view="front", anchors={"body": (0, 0, 0.5)})
    assert node.anchor_point("body").y == pytest.approx(-10.0, rel=1e-9)


def test_anchor3d_adds_one_after_the_fact():
    node = inklet.solid("cube", width=20.0, view="front")
    anchor3d(node, "base", (0.0, 0.0, -0.5))
    assert node.anchor_point("base").y == pytest.approx(10.0, rel=1e-9)


def test_anchor3d_on_a_node_this_package_did_not_build_says_so():
    with pytest.raises(MeshError, match="3D view"):
        anchor3d(inklet.box("plain"), "x", (0, 0, 0))


def test_an_anchor_with_the_wrong_arity_is_refused():
    with pytest.raises(MeshError, match="three coordinates"):
        inklet.solid("cube", width=10.0, anchors={"nose": (1.0, 2.0)})


def test_up_axis_rotates_the_anchor_with_the_geometry():
    # A y-up file's "tip" must not end up ninety degrees from its geometry.
    node = inklet.model(cube(1.0), width=20.0, view="front", up_axis="y",
                     anchors={"tip": (0.0, 0.5, 0.0)})
    assert node.anchor_point("tip").y == pytest.approx(-10.0, rel=1e-9)


# -- tessellation follows the page ----------------------------------------


def _outline_points(node) -> int:
    """How many points the silhouette is drawn with -- the facet count, seen."""
    trace = next(n for n in _walk(node) if n.kind == SILHOUETTE_KIND)
    return sum(len(sub.points) for sub in trace.prim.subpaths)


def test_page_scale_is_the_millimetres_a_model_unit_becomes():
    # A unit cube seen face-on at 30 mm is 30 mm per unit, exactly. Anything
    # else and every tessellation decision downstream is off by that factor.
    assert page_scale(cube(1.0), width=30.0, view="front") == \
        pytest.approx(30.0)
    assert page_scale(cube(2.0), width=30.0, view="front") == \
        pytest.approx(15.0)


def test_page_scale_is_the_scale_the_drawing_actually_used():
    node = inklet.solid("sphere", width=37.0, view="three-quarter",
                     tolerance=None)
    assert view_of(node).scale == pytest.approx(
        page_scale(sphere(), width=37.0, view="three-quarter"), rel=1e-9)


@pytest.mark.parametrize("width", [6.0, 20.0, 37.0, 80.0])
def test_refining_settles_where_another_pass_would_ask_for_nothing_more(width):
    """The fixed point, stated as a test rather than as a hope.

    The fit that chooses the tessellation is measured on the mesh the
    tessellation replaces, so the answer moves under its own feet. What
    `_refined` promises is not that the drift is zero but that it stops on the
    safe side: the mesh it returns is at least as fine as its *own* fitted
    scale calls for, so a further pass would change nothing.
    """
    options = {"width": width, "view": "three-quarter"}
    mesh = _refined("cylinder", {}, cylinder(), 0.06, options)
    segments = (len(mesh.vertices) - 2) // 2      # two rings and two cap hubs
    assert segments >= segments_for(0.4 * page_scale(mesh, **options), 0.06)


def test_the_same_cylinder_is_coarser_small_and_finer_large():
    """The point of the whole exercise: a shape that looks round at every size
    it is asked for, without the author working out what that costs."""
    small = _outline_points(inklet.solid("cylinder", width=6.0, view="top"))
    medium = _outline_points(inklet.solid("cylinder", width=20.0, view="top"))
    large = _outline_points(inklet.solid("cylinder", width=80.0, view="top"))
    assert small < medium < large
    assert small >= 8 + 2          # never below the floor, however small


def test_turning_the_tolerance_off_restores_the_builders_own_default():
    off = inklet.solid("cylinder", width=80.0, view="top", tolerance=None)
    assert _outline_points(off) == 32 + 2


def test_an_explicit_segment_count_is_never_overruled():
    stated = inklet.solid("cylinder", width=80.0, view="top", segments=9)
    assert _outline_points(stated) == 9 + 2


@pytest.mark.parametrize("width", [4.0, 6.0, 20.0, 37.0, 40.0, 80.0, 120.0])
def test_the_drawn_outline_meets_the_tolerance_at_its_own_scale(width):
    """End to end, checked where the promise is made -- on the page.

    Seen down the axis a cylinder's silhouette *is* its segment polygon, so
    counting its distinct corners counts the facets the reader is looking at.
    Bounded on both sides: enough to meet the tolerance at the scale the
    drawing came out at, and never more than the one spare segment `_refined`
    can end up holding when the fit moves under it.
    """
    node = inklet.solid("cylinder", width=width, view="top", tolerance=0.06)
    trace = next(n for n in _walk(node) if n.kind == SILHOUETTE_KIND)
    corners = {(round(p.x, 6), round(p.y, 6))
               for sub in trace.prim.subpaths for p in sub.points}
    needed = segments_for(0.4 * view_of(node).scale, 0.06)
    assert needed <= len(corners) <= needed + 1


def test_a_coordinate_frame_follows_the_page_too():
    """`axes` builds its own mesh rather than going through `solid`, so the
    rule has to be applied there as well or the one 3D element every methods
    section uses is the one that never adapts."""
    small = _svg(inklet.axes(width=14.0))
    large = _svg(inklet.axes(width=80.0))
    assert small.count("<path") < large.count("<path")
    fixed = _svg(inklet.axes(width=14.0, tolerance=None))
    # Bytes rather than paths for the second half: the two are drawn with the
    # same number of tone bands and merge into much the same number of runs,
    # and what the coarser tessellation saves is the *coordinates* in them.
    assert len(fixed) > len(small)


# -- the silhouette trace -------------------------------------------------


def test_the_node_carries_an_inert_silhouette_path():
    node = inklet.solid("sphere", width=20.0)
    found = [n for n in _walk(node) if n.kind == SILHOUETTE_KIND]
    assert len(found) == 1
    svg = _svg((node))
    assert 'stroke="none"' in svg      # present in the tree, invisible on the page


def test_an_arrow_clips_on_the_silhouette_not_the_bounding_box():
    # A sphere's bounding box corner is 41% further out than its outline. An
    # arrow that stopped at the box would visibly float.
    probe = inklet.box("probe")
    node = inklet.solid("sphere", width=20.0, view="front")
    # Approaching diagonally is the whole point. Head-on, the bounding box and
    # the circle stop the arrow at the same place; at 45 degrees the box
    # corner is sqrt(2) further out and an arrow that used it visibly floats.
    fig = _figure(inklet.hstack(
        [inklet.vstack([probe, inklet.spacer(1.0, 44.0)], gap=0.0), node], gap=24.0))
    fig.link(probe, node)
    _, places = fig.build()
    box = places[node.id].bbox
    end = _route_end(fig)
    assert end is not None
    centre, radius = box.center, box.width / 2.0
    # On the circle, not on the square: off-axis the two differ by up to 41%.
    assert math.hypot(end.x - centre.x, end.y - centre.y) == pytest.approx(
        radius, rel=0.03)
    assert end.x < box.x1 - 0.5 and end.y > box.y0 + 0.5


def test_a_model_with_no_silhouette_still_builds():
    # A single triangle seen edge-on has no closed outline to smuggle.
    sliver = Mesh((Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0)), ((0, 1, 2),))
    assert inklet.model(sliver, width=10.0, view="front") is not None


# -- the backend registry -------------------------------------------------


def test_builtin_is_registered_and_available_everywhere():
    assert "builtin" in backends()
    assert "builtin" in available_backends()


def test_backends_are_listed_sorted():
    assert backends() == tuple(sorted(backends()))


def test_auto_resolves_to_something_registered():
    node = inklet.solid("cube", width=10.0, backend="auto")
    assert view_of(node) is not None


def test_an_unknown_backend_names_what_is_registered():
    with pytest.raises(MeshError, match="builtin"):
        inklet.solid("cube", width=10.0, backend="blenderr")


def test_a_third_party_backend_can_register_and_be_chosen():
    # The seam a second implementer builds against: same Request in, same
    # Rendering out, no edit to this package.
    calls = []

    def fake(request: Request) -> Rendering:
        calls.append(request)
        view = request.camera.frame(request.mesh, request.width, request.height)
        return Rendering(diagram=inklet.spacer(1.0, 1.0), silhouette=(), view=view)

    register_backend("test-double", fake, priority=99)
    try:
        assert "test-double" in backends()
        node = inklet.solid("cube", width=10.0, backend="test-double")
        assert len(calls) == 1
        assert calls[0].width == 10.0
        assert isinstance(calls[0].look, Look)
        # `auto` ranks by priority, so the double outranks builtin.
        inklet.solid("cube", width=10.0, backend="auto")
        assert len(calls) == 2
    finally:
        del _BACKENDS["test-double"]


def test_an_unavailable_backend_is_registered_but_not_auto_selected():
    register_backend("never", lambda r: None, priority=99,
                     available=lambda: False)
    try:
        assert "never" in backends()
        assert "never" not in available_backends()
        inklet.solid("cube", width=10.0, backend="auto")     # must not pick it
    finally:
        del _BACKENDS["never"]


def test_a_backend_returning_the_wrong_type_is_caught_at_the_seam():
    register_backend("wrong", lambda r: "not a rendering")
    try:
        with pytest.raises(MeshError, match="Rendering"):
            inklet.solid("cube", width=10.0, backend="wrong")
    finally:
        del _BACKENDS["wrong"]


# -- scenes ---------------------------------------------------------------
#
# What `inklet.scene` promises over twelve `inklet.model` calls: one scale, one
# projection, and a paint order that says which part is in front.


def _at(mesh, x=0.0, y=0.0, z=0.0):
    return mesh.transformed(Mat4.translation(Vec3(x, y, z)))


def _paint_order(scene):
    """Part names in the order the renderer will actually draw them."""
    owner = {}
    for child in scene.children:
        part = next(n.name for n in _walk(child) if n.kind == MODEL_KIND)
        for node in _walk(child):
            owner[node.id] = part
    order = []
    for item in flatten(scene):
        part = owner.get(item.id)
        if part is not None and part not in order:
            order.append(part)
    return order


def _part_boxes(scene):
    places = resolve(scene)
    return {node.name: places[node.id].bbox
            for node in _walk(scene)
            if node.kind == MODEL_KIND and node is not scene}


def test_a_scene_frames_its_parts_together_not_each_one_to_the_width():
    # The whole reason this exists. Asked separately, both cubes come out the
    # width they were asked for and the big one stops being big.
    small, big = _at(cube(1.0), x=-3.0), _at(cube(2.0), x=3.0)

    scene = inklet.scene([("small", small), ("big", big)], width=30.0, view="front")

    boxes = _part_boxes(scene)
    assert boxes["big"].width == pytest.approx(2.0 * boxes["small"].width, rel=1e-9)
    assert (inklet.model(small, width=30.0, view="front").bbox.width
            == pytest.approx(inklet.model(big, width=30.0, view="front").bbox.width))


def test_a_scene_comes_out_the_width_it_was_asked_for():
    scene = inklet.scene([("a", _at(cube(1.0), x=-3.0)), ("b", _at(cube(2.0), x=3.0))],
                      width=42.0, view="three-quarter")
    assert scene.bbox.width == pytest.approx(42.0, rel=1e-9)


def test_parts_land_where_the_shared_projection_puts_them():
    left, right = _at(cube(1.0), x=-4.0), _at(cube(1.0), x=4.0)

    scene = inklet.scene([("left", left), ("right", right)], width=40.0, view="front")

    view = view_of(scene)
    apart = view.project(Vec3(4.0, 0, 0)).point.x - view.project(Vec3(-4.0, 0, 0)).point.x
    boxes = _part_boxes(scene)
    assert boxes["right"].center.x - boxes["left"].center.x == pytest.approx(apart)
    # And the scene's own anchors agree with its parts.
    assert scene.anchor_point("right").x == pytest.approx(boxes["right"].center.x)


def test_the_nearer_part_is_painted_over_the_one_behind_it():
    # A front view puts the eye at -y, so the cube at -3 is the near one. Both
    # project to the same square: whichever is drawn second is the one you see.
    near, far = _at(cube(1.0), y=-3.0), _at(cube(1.0), y=3.0)

    scene = inklet.scene([("near", near), ("far", far)], width=20.0,
                      view="front", style="shaded")

    assert _paint_order(scene) == ["far", "near"]


def test_declaration_order_does_not_decide_what_is_in_front():
    # The bug this fixes: the parts used to paint in the order they were
    # written, so a specimen plane declared after the objective above it came
    # out in front of the objective.
    near, far = _at(cube(1.0), y=-3.0), _at(cube(1.0), y=3.0)

    written = [inklet.scene([("near", near), ("far", far)], width=20.0, view="front"),
               inklet.scene([("far", far), ("near", near)], width=20.0, view="front")]

    assert [_paint_order(s) for s in written] == [["far", "near"], ["far", "near"]]


def test_a_scene_projects_any_point_in_it_the_way_it_drew_the_parts():
    scene = inklet.scene([("a", _at(cube(1.0), x=-3.0)), ("b", _at(cube(1.0), x=3.0))],
                      width=30.0, view="three-quarter")

    anchor3d(scene, "corner", (3.5, 0.5, 0.5))

    assert scene.anchor_point("corner") == view_of(scene).project(
        Vec3(3.5, 0.5, 0.5)).point


def test_an_edge_on_part_still_takes_its_place():
    # A plane seen edge-on projects to a vertical line and has no width to fit.
    # Height carries the same scale, so it is placed rather than refused.
    wall = Mesh((Vec3(0, 0, -1), Vec3(0, 0, 1), Vec3(0, 1, 1), Vec3(0, 1, -1)),
                ((0, 1, 2), (0, 2, 3)))
    scene = inklet.scene([("wall", wall), ("block", _at(cube(1.0), x=3.0))],
                      width=30.0, view="front")
    assert _part_boxes(scene)["wall"].height > 0.0


def test_a_part_may_not_choose_its_own_camera_or_size():
    with pytest.raises(MeshError, match="scene's to set"):
        inklet.scene([("a", cube(1.0), {"view": "front"})], width=20.0, view="top")


def test_two_parts_may_not_share_a_name():
    with pytest.raises(MeshError, match="distinct"):
        inklet.scene([("a", cube(1.0)), ("a", _at(cube(1.0), x=3.0))], width=20.0)


def test_a_scene_wants_geometry_rather_than_a_finished_drawing():
    with pytest.raises(MeshError, match="not a Mesh"):
        inklet.scene([("a", inklet.solid("cube", width=10.0))], width=20.0)


def test_an_empty_scene_says_so():
    with pytest.raises(MeshError, match="at least one part"):
        inklet.scene([], width=20.0)


# -- order="exact" --------------------------------------------------------
#
# The parts sort by one number each -- their centre's depth -- which is the
# right answer for an assembly of separate objects and the wrong one the
# moment two parts interpenetrate. `order="exact"` draws the whole scene as
# one mesh so the sort is per facet, and keeps every part as a node that
# names, anchors and catches arrows without painting anything itself.


def _ring_and_rod():
    """A torus with a rod through its hole: the smallest thing whose parts
    cannot be ordered back to front, because the ring is in front of the rod
    on one side of the hole and behind it on the other."""
    ring = build("torus", radius=3.0, tube=0.6).transformed(
        Mat4.rotation(Vec3(0.0, 1.0, 0.0), 90.0))
    rod = build("cylinder", radius=0.5, height=14.0).transformed(
        Mat4.rotation(Vec3(0.0, 1.0, 0.0), 90.0))
    return ring, rod


def _threaded(order):
    ring, rod = _ring_and_rod()
    return inklet.scene([("ring", ring, {"color": "#ff0000"}),
                      ("rod", rod, {"color": "#0000ff"})],
                     width=60.0, view="three-quarter", style="shaded",
                     order=order)


def _fill_runs(scene):
    """Which part each painted facet came from, in paint order, with repeats
    collapsed. Two runs means one part was drawn and then the other; more
    means they were interleaved, which is what threading looks like."""
    who = []
    for item in flatten(scene):
        fill = item.style.fill
        if not fill or fill == "none":
            continue
        who.append("ring" if int(fill[1:3], 16) > int(fill[5:7], 16) else "rod")
    return [name for name, _ in itertools.groupby(who)]


def test_parts_ordering_draws_one_whole_part_and_then_the_other():
    assert _fill_runs(_threaded("parts")) == ["ring", "rod"]


def test_exact_ordering_threads_the_parts_through_each_other():
    runs = _fill_runs(_threaded("exact"))
    assert len(runs) > 2
    assert set(runs) == {"ring", "rod"}


def test_an_exact_scene_frames_itself_the_way_the_parts_scene_does():
    # Same camera, same fit, same page: only the paint order changes.
    loose, fused = _threaded("parts"), _threaded("exact")
    assert fused.bbox.width == pytest.approx(loose.bbox.width, abs=1e-9)
    assert fused.bbox.height == pytest.approx(loose.bbox.height, abs=1e-9)


def test_every_part_of_an_exact_scene_is_still_a_node_with_an_anchor():
    scene = _threaded("exact")
    for name in ("ring", "rod"):
        part = scene.find(name)
        assert part is not None
        assert scene.anchor_point(name) is not None


def test_a_part_of_an_exact_scene_carries_its_outline_and_no_ink():
    # The part is painted with the rest of the scene, so its own node has to
    # be a shape an arrow can find and a lint rule can name -- and paint
    # nothing, or the facets would be drawn twice.
    scene = _threaded("exact")
    ring = scene.find("ring")
    items = flatten(ring)
    assert items
    assert all(item.style.fill in (None, "none")
               and item.style.stroke in (None, "none") for item in items)
    assert any(item.prim.subpaths for item in items)


def test_an_exact_part_may_not_ask_for_a_look_of_its_own():
    ring, rod = _ring_and_rod()
    with pytest.raises(MeshError, match="one pass"):
        inklet.scene([("ring", ring, {"style": "wire"}), ("rod", rod)],
                  width=60.0, view="three-quarter", order="exact")


def test_an_exact_part_may_carry_its_own_line_weight():
    # Weight is how a technical illustration says which part the figure is
    # about, and a fused mesh can carry it per face group the way it carries
    # colour. Three weights on the page: the rod's outline, the rod's creases
    # at the crease ratio, and the theme's own for the ring.
    ring, rod = _ring_and_rod()
    scene = inklet.scene([("ring", ring), ("rod", rod, {"stroke_width": 0.9})],
                      width=60.0, view="three-quarter", style="shaded",
                      order="exact")
    weights = {item.style.stroke_width for item in flatten(scene)
               if item.style.stroke not in (None, "none")}
    assert 0.9 in weights
    assert len(weights) >= 2


def test_a_named_group_may_carry_its_own_line_weight():
    # The same door `colors=` goes through: a face group, on one mesh. Here
    # the rim of a bolt hole, drawn heavier than the plate it is cut into.
    from inklet.three import build

    plate = build("box", size_z=0.2).drill("z", radius=0.15, group="hole")
    node = inklet.model(plate, width=30.0, view="three-quarter",
                     stroke_widths={"hole": 0.8})
    assert 0.8 in {item.style.stroke_width for item in flatten(node)
                   if item.style.stroke not in (None, "none")}


def test_toon_fills_in_the_numbers_a_cartoon_look_wants():
    # Three bands is the whole point, and the author saying otherwise wins.
    from inklet.three import TOON

    fills = _fills(inklet.solid("sphere", width=40.0, view="three-quarter",
                             style="toon"))
    assert 1 < len(fills) <= TOON["levels"]
    many = _fills(inklet.solid("sphere", width=40.0, view="three-quarter",
                            style="toon", levels=12))
    assert len(many) > len(fills)


def test_toon_is_still_a_drawing_with_lines_on_it():
    node = inklet.solid("cube", width=30.0, view="isometric", style="toon")
    assert any(item.style.stroke not in (None, "none") for item in flatten(node))
    assert any(item.style.fill not in (None, "none") for item in flatten(node))


def _fills(node):
    return {item.style.fill for item in flatten(node)
            if item.style.fill not in (None, "none")}


def test_a_scene_order_has_to_be_one_it_knows():
    with pytest.raises(MeshError, match="order="):
        inklet.scene([("a", cube(1.0))], width=20.0, order="sorted")


def _leader_over(order, through=()):
    """A tag out on clear paper, pointing at the far cube of three in a row.

    Its leader has to cross the two nearer cubes to get there, which is what
    the linter should say -- naming the cubes, and not the drawing that
    happens to paint all three of them.
    """
    scene = inklet.scene([("left", _at(cube(2.0), x=-6.0)), ("mid", cube(2.0)),
                       ("right", _at(cube(2.0), x=6.0))],
                      width=60.0, view="front", style="shaded", order=order)
    tag = inklet.label("far side").translated(-45.0, 0.0)
    content = inklet.place([tag, scene])
    leader = inklet.link(tag, scene.find("right"), kind="line", head="none",
                      name="tag",
                      through=tuple(scene.find(name) for name in through))
    routed = inklet.route_all([leader], resolve(content))
    return inklet.Diagram(children=(content, routed), kind="panel")


def test_a_leader_over_an_exact_scene_is_reported_against_the_parts():
    # The failure this pins down: a fused scene is one drawing, so the finding
    # used to read "runs through scene-body", which names nothing the reader
    # can move and nothing `through=` can cite.
    crossed = {d.message.split(" runs through ")[1].split(" for ")[0]
               for d in lint(_leader_over("exact"))
               if d.code == "LINK_CROSSES"}

    assert crossed == {"left", "mid"}


def test_an_exact_scene_part_can_be_declared_as_crossed_on_purpose():
    quiet = lint(_leader_over("exact", through=("left", "mid")))

    assert [d for d in quiet if d.code == "LINK_CROSSES"] == []


# -- axes -----------------------------------------------------------------


def test_axes_label_each_arrow_at_its_tip():
    frame = inklet.axes(width=26.0, view="isometric")
    from inklet.core.prims import TextPrim

    text = [n for n in _walk(frame) if isinstance(n.prim, TextPrim)]
    assert len(text) == 3


def test_axes_labels_can_be_renamed_or_dropped():
    named = inklet.axes(width=20.0, labels=("u", "v", "w"))
    bare = inklet.axes(width=20.0, labels=None)
    assert _svg((named)) != _svg((bare))
    assert bare.bbox.width <= named.bbox.width + 1e-9


def test_axes_tips_are_anchors_at_the_ends_not_the_middles():
    # `group_center` is a centroid, so anchoring on the group put the label
    # halfway down the shaft. The tips are explicit for that reason.
    frame = inklet.axes(width=26.0, view="front", length=1.0)
    z = frame.anchor_point("z")
    origin = frame.anchor_point("origin") if "origin" in frame.anchors else Vec2(0, 0)
    assert abs(z.y - origin.y) > frame.bbox.height * 0.25


# -- determinism ----------------------------------------------------------


def test_the_same_figure_twice_in_one_process_draws_the_same_geometry():
    # Node ids are minted from a process-wide counter, so two figures built in
    # one process differ in their `id=` attributes and in nothing else. The
    # cross-process test below is the one that pins the bytes.
    first, second = _svg_of_the_stress_scene(), _svg_of_the_stress_scene()
    assert _paths(first) == _paths(second)


def test_the_same_figure_across_hash_seeds_is_byte_identical():
    # The hard contract. Anything iterated out of a set or a dict whose order
    # depends on string hashing would differ here and nowhere else.
    script = textwrap.dedent("""
        import hashlib, sys
        sys.path.insert(0, %r)
        import inklet
        from inklet.three.solids import sphere
        fig = inklet.figure(width=120)
        fig.add(inklet.hstack([
            inklet.solid("cube", width=20, view="isometric", style="shaded"),
            inklet.solid("torus", width=20, view="three-quarter"),
            inklet.model(sphere(0.5, 2), width=20, view="dimetric", style="shaded"),
            inklet.axes(width=20),
        ], gap=4))
        sys.stdout.write(hashlib.md5(fig.to_svg().encode()).hexdigest())
    """) % str(_src_root())
    digests = {seed: subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "PYTHONHASHSEED": seed}, check=True).stdout
        for seed in ("0", "12345", "99991")}
    assert len(set(digests.values())) == 1, digests


# -- errors ---------------------------------------------------------------


def test_an_unknown_solid_lists_the_known_ones():
    with pytest.raises(MeshError, match="cylinder"):
        inklet.solid("tesseract", width=10.0)


def test_an_unknown_up_axis_is_refused():
    with pytest.raises(MeshError, match="up_axis"):
        inklet.solid("cube", width=10.0, up_axis="w")


def test_shape_arguments_reach_the_builder():
    coarse = inklet.solid("cylinder", width=20.0, segments=6)
    fine = inklet.solid("cylinder", width=20.0, segments=64)
    assert len(_svg((fine))) > len(_svg((coarse)))


def test_a_transform_is_applied_before_the_up_axis_fix():
    flat = inklet.model(cube(1.0), width=20.0, view="front",
                     transform=Mat4.scaling(1.0, 1.0, 0.25))
    assert flat.bbox.height < flat.bbox.width


# -- helpers --------------------------------------------------------------


def _figure(node):
    fig = inklet.figure(width=120.0)
    fig.add(node)
    return fig


def _svg(node):
    """Through a Figure, always: colour is resolved at figure-build time, so
    `to_svg` on a bare node emits geometry with the theme still unapplied."""
    return _figure(node).to_svg()


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _src_root():
    import pathlib

    return pathlib.Path(inklet.__file__).resolve().parent.parent


def _svg_of_the_stress_scene():
    fig = inklet.figure(width=120.0)
    fig.add(inklet.hstack([
        inklet.solid("cube", width=20.0, view="isometric", style="shaded"),
        inklet.solid("torus", width=20.0, view="three-quarter"),
        inklet.axes(width=20.0),
    ], gap=4.0))
    return fig.to_svg()


def _route_end(fig):
    from inklet.links import route

    _, places = fig.build()
    return route(fig._links[0], places).anchor_point("end")


def _paths(svg: str) -> list[str]:
    import re

    return re.findall(r' d="([^"]+)"', svg)


# -- the zero-dependency promise ------------------------------------------


OPTIONAL = ("trimesh", "scipy", "shapely", "networkx", "fast_simplification",
            "numpy", "PIL")


def test_no_module_imports_an_optional_package_at_module_scope():
    # `inklet.solid("cube", width=20)` has to work in a bare `pip install inklet`.
    # A bare `import trimesh` anywhere in this package would pass here, where
    # everything is installed, and fail for everyone else -- so it is checked
    # by reading the source rather than by importing.
    import ast
    import pathlib

    package = pathlib.Path(inklet.three.__file__).parent
    offenders = []
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            if node.col_offset != 0:
                continue     # indented: inside a function, which is the rule
            for name in names:
                if name.split(".")[0] in OPTIONAL:
                    offenders.append(f"{path.name}:{node.lineno} {name}")
    assert offenders == []


def test_the_built_in_pipeline_runs_with_the_optional_packages_blocked():
    script = textwrap.dedent("""
        import sys
        BLOCK = %r
        class Block:
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in BLOCK:
                    raise ImportError(name + " blocked")
                return None
        sys.meta_path.insert(0, Block())
        sys.path.insert(0, %r)
        import inklet
        from inklet.three import load, supported_formats
        assert supported_formats() == ("obj", "ply", "stl"), supported_formats()
        for style in ("lineart", "shaded", "solid", "wireframe"):
            inklet.solid("sphere", width=20, style=style)
        fig = inklet.figure(width=60)
        fig.add(inklet.axes(width=20))
        assert fig.to_svg()
        print("ok")
    """) % (OPTIONAL, str(_src_root()))
    done = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


# -- shading --------------------------------------------------------------


def test_a_shaded_model_is_the_asked_for_width_to_within_the_bleed():
    # Facets are grown outward by a hundredth of a millimetre so that adjacent
    # fills overlap instead of leaving an antialiased hairline. The growth is a
    # mitred offset, so a corner reaches further than a side does -- capped at
    # `_MITRE_LIMIT` bleeds, which is what makes this a bound rather than a
    # hope. Still a twentieth of a millimetre, well under the finest line any
    # press holds, but it is not zero and should not be asserted away.
    from inklet.three.backend import _FACET_BLEED, _MITRE_LIMIT

    width = extent(inklet.solid("sphere", width=20.0, style="shaded")).width
    assert 20.0 <= width <= 20.0 + 2 * _MITRE_LIMIT * _FACET_BLEED


def test_shading_merges_facets_into_far_fewer_paths_than_facets():
    from inklet.three.solids import sphere

    ball = sphere(0.5, 3)                            # 1280 facets
    node = inklet.model(ball, width=30.0, style="shaded", view="three-quarter")
    paths = [n for n in _walk(node) if n.prim is not None
             and getattr(n.prim, "filled", False)]
    assert len(paths) < 60


def test_merging_loses_no_facet():
    # Every facet has to end up in exactly one run. Dropping one leaves a
    # paper-coloured hole in the middle of a solid, which is the failure mode
    # this whole merge could plausibly have.
    from inklet.three.backend import _gather_runs
    from inklet.three.camera import Camera
    from inklet.three.edges import facing_faces
    from inklet.three.shade import sorted_facets
    from inklet.three.solids import sphere

    ball = sphere(0.5, 3)
    view = Camera.named("three-quarter").frame(ball, width=30.0)
    points, depths = view.project_all(ball.vertices)
    facing = facing_faces(ball, view)
    facets = sorted_facets(ball, view, points, depths, facing, cull=True)
    runs = _gather_runs(facets)
    placed = [facet for _, members in runs for facet in members]
    assert len(placed) == len(facets)
    assert {id(f) for f in placed} == {id(f) for f in facets}


def test_dissolving_a_run_keeps_the_area_it_covers():
    """The invariant that makes the dissolve safe, checked by Stokes.

    Signed area is a linear functional of a boundary, so cancelling an edge
    against its own reverse cannot change it. Anything that dropped a facet,
    double-counted one, or wound a ring the wrong way moves this number.
    """
    from inklet.three.backend import _gather_runs
    from inklet.three.camera import Camera
    from inklet.three.edges import facing_faces
    from inklet.three.shade import dissolve, sorted_facets
    from inklet.three.solids import torus

    ring = torus()                       # concave, and every facet is curved
    view = Camera.named("three-quarter").frame(ring, width=30.0)
    points, depths = view.project_all(ring.vertices)
    facing = facing_faces(ring, view)
    facets = sorted_facets(ring, view, points, depths, facing, cull=True)

    def area(loop):
        return sum(loop[i].x * loop[(i + 1) % len(loop)].y
                   - loop[(i + 1) % len(loop)].x * loop[i].y
                   for i in range(len(loop))) / 2.0

    merged = 0
    for _, members in _gather_runs(facets):
        where = {}
        for facet in members:
            where.update(zip(facet.ring, facet.points))
        rings = dissolve([facet.ring for facet in members])
        loose = sum(area(facet.points) for facet in members)
        joined = sum(area([where[i] for i in ring]) for ring in rings)
        assert abs(joined - loose) < 1e-9 * max(1.0, abs(loose))
        merged += len(members) - len(rings)
    assert merged > len(facets) // 10       # and it really did dissolve edges


def test_merging_never_reorders_two_overlapping_facets_of_different_tones():
    # The one property that makes the merge safe. Checked directly: for every
    # pair of facets that overlap and disagree on tone, the path each ended up
    # in must be emitted in the same relative order they were sorted in.
    from inklet.three.backend import _MERGE_TOUCH, _gather_runs
    from inklet.three.order import overlaps
    from inklet.three.camera import Camera
    from inklet.three.edges import facing_faces
    from inklet.three.shade import sorted_facets
    from inklet.three.solids import torus

    ring = torus()                       # concave: parts of it hide other parts
    view = Camera.named("three-quarter").frame(ring, width=30.0)
    points, depths = view.project_all(ring.vertices)
    facing = facing_faces(ring, view)
    facets = sorted_facets(ring, view, points, depths, facing, cull=True)

    painted = _painted_order(facets, _gather_runs(facets))
    for i in range(len(facets)):
        for j in range(i + 1, len(facets)):
            if facets[i].tone == facets[j].tone:
                continue
            if not overlaps(_corners(facets[i]), _corners(facets[j]),
                             _MERGE_TOUCH):
                continue
            assert painted[i] < painted[j], (i, j)


def _area(points):
    return sum(points[i].x * points[(i + 1) % len(points)].y
               - points[(i + 1) % len(points)].x * points[i].y
               for i in range(len(points))) / 2.0


def _shaded(mesh, view_name="three-quarter", cull=True, **kwargs):
    from inklet.three.camera import Camera
    from inklet.three.edges import facing_faces
    from inklet.three.shade import sorted_facets

    view = Camera.named(view_name).frame(mesh, width=30.0)
    points, depths = view.project_all(mesh.vertices)
    facing = facing_faces(mesh, view)
    return sorted_facets(mesh, view, points, depths, facing, cull=cull,
                         **kwargs)


def test_the_depth_cue_fades_the_far_end_of_the_scene_and_not_the_near_one():
    """Which way round the fog goes, asserted rather than assumed.

    `View.project` measures depth along `forward`, so it grows away from the
    camera and the *smallest* depth is nearest -- the same convention
    hidden-line removal reads, and the opposite of what "near" reads as when
    the two are mixed up. Getting it backwards leaves a picture that is
    perfectly self-consistent and exactly wrong: the foreground washes out and
    the background stays saturated, which the eye reads as the far parts being
    the near ones.
    """
    from inklet.three.linalg import Mat4
    from inklet.three.mesh import merge
    from inklet.three.solids import sphere

    close = sphere(0.5, 2).transformed(Mat4.translation(Vec3(-1.2, -3.0, 0.0)))
    away = sphere(0.5, 2).transformed(Mat4.translation(Vec3(1.2, 3.0, 0.0)))
    both = merge([close.grouped("close"), away.grouped("away")])
    facets = _shaded(both, "front", depth_cue=0.5)
    cues = {name: [f.cue for f in facets if f.group == name]
            for name in ("close", "away")}
    depths = {name: [f.depth for f in facets if f.group == name]
              for name in ("close", "away")}
    assert max(depths["close"]) < min(depths["away"])    # nearer is smaller
    assert max(cues["close"]) < min(cues["away"])        # and fades less


def test_the_bands_of_a_smooth_shade_tile_exactly_the_facets_they_replace():
    """The guarantee a painter's-algorithm fill needs and cannot check itself.

    A band is a piece of a triangle, so the bands of a mesh have to cover the
    same page area as its facets -- no more, or two fills overlap and the
    order between them starts to matter; no less, and there is a
    paper-coloured crack along a band boundary in the middle of a solid.
    Signed area is additive over a subdivision, so one number settles it.
    """
    from inklet.three.solids import sphere

    ball = sphere(0.5, 3)
    flat = sum(_area(f.points) for f in _shaded(ball))
    bands = sum(_area(f.points) for f in _shaded(ball, smooth_degrees=90.0))
    assert len(_shaded(ball, smooth_degrees=90.0)) > len(_shaded(ball))
    assert abs(bands - flat) < 1e-9 * abs(flat)


def test_a_band_boundary_point_is_one_point_however_many_facets_want_it():
    """Two triangles either side of an edge must agree, index and coordinate.

    They are handed the same two vertex tones, so they cut the edge at the
    same parameter; the index is keyed on the edge and the step, so they name
    that cut the same way. Both halves matter. Agreeing on the coordinate but
    not the index would leave `dissolve` unable to cancel the shared boundary,
    and the file would carry every band twice; agreeing on the index but not
    the coordinate would move a band boundary to whichever triangle wrote last.
    """
    from inklet.three.solids import sphere

    facets = _shaded(sphere(0.5, 3), smooth_degrees=90.0)
    where = {}
    corners = 0
    for facet in facets:
        for index, point in zip(facet.ring, facet.points):
            corners += 1
            if index in where:
                assert where[index] == point, index
            where[index] = point
    made = [i for i in where if i >= len(sphere(0.5, 3).vertices)]
    assert made                                  # boundaries were cut at all
    # And they are genuinely shared: every cut belongs to two triangles, so
    # naming one costs far fewer indices than there are corners.
    assert len(where) < corners / 2


def test_dissolving_a_run_of_bands_keeps_the_area_it_covers():
    from inklet.three.backend import _gather_runs
    from inklet.three.shade import dissolve
    from inklet.three.solids import torus

    facets = _shaded(torus(), smooth_degrees=90.0)
    merged = 0
    for _, members in _gather_runs(facets):
        where = {}
        for facet in members:
            where.update(zip(facet.ring, facet.points))
        rings = dissolve([facet.ring for facet in members])
        loose = sum(_area(facet.points) for facet in members)
        joined = sum(_area([where[i] for i in ring]) for ring in rings)
        assert abs(joined - loose) < 1e-9 * max(1.0, abs(loose))
        merged += len(members) - len(rings)
    assert merged > len(facets) // 2       # bands dissolve harder than facets


def test_a_box_is_shaded_the_same_way_however_the_smoothing_is_set():
    # Every vertex of a box is on a right angle, so there is no smooth region
    # to band and the whole pass has to be a no-op -- not "nearly", since a
    # box is the shape a reader would notice a stray band boundary on.
    flat = _shaded(cube(1.0), "isometric")
    smooth = _shaded(cube(1.0), "isometric", smooth_degrees=90.0)
    assert [(f.points, f.tone) for f in flat] == [(f.points, f.tone)
                                                  for f in smooth]


def test_flat_shading_pays_nothing_for_more_tones_and_smooth_shading_pays():
    """The cost model `shading=` is documented by, made executable.

    A flat facet has one tone however finely the ramp is cut, so raising
    `levels` cannot add a polygon. A band is a piece of a triangle bounded by
    two steps, so raising `levels` cuts more pieces. That asymmetry is the
    whole reason `shading="smooth"` is opt-in and the whole reason to drop
    `levels` when turning it on.
    """
    from inklet.three.solids import sphere

    ball = sphere(0.5, 2)
    flat = [len(_shaded(ball, levels=n)) for n in (8, 32)]
    smooth = [len(_shaded(ball, levels=n, smooth_degrees=90.0))
              for n in (8, 32)]
    assert flat[0] == flat[1]
    assert smooth[1] > 2 * smooth[0]


def test_smooth_shading_is_reachable_from_the_authoring_surface():
    node = inklet.solid("sphere", width=20.0, style="shaded", shading="smooth",
                     levels=8, view="three-quarter")
    plain = inklet.solid("sphere", width=20.0, style="shaded", levels=8,
                      view="three-quarter")
    assert _fills(node) != _fills(plain)
    with pytest.raises(MeshError, match="unknown shading"):
        inklet.solid("sphere", width=20.0, style="shaded", shading="gouraud")


# -- the exact painter's order ---------------------------------------------


def _blades(tilt=2.0):
    """Two quads that cross in view.

    Both span the same page rectangle; one leans toward the camera going
    right, the other away. They meet down the middle, so neither is in front
    of the other and the mean of four depths is identical for both -- the case
    a sort key cannot answer, whatever key it is.
    """
    from inklet.three.mesh import Mesh
    from inklet.three.linalg import Vec3

    verts, faces, groups = [], [], []
    for index, lean in enumerate((tilt, -tilt)):
        base = len(verts)
        verts.extend([Vec3(-4, -lean, -1.5), Vec3(4, lean, -1.5),
                      Vec3(4, lean, 1.5), Vec3(-4, -lean, 1.5)])
        faces.extend([(base, base + 1, base + 2), (base, base + 2, base + 3)])
        groups.extend([f"blade{index}"] * 2)
    return Mesh(tuple(verts), tuple(faces), tuple(groups))


def _nearest(mesh, view, points, depths, x, y):
    """Which group is really nearest under a page point, by ray casting.

    Ground truth that owes nothing to any sort: the ray through the page point
    meets some triangles, and the eye sees whichever it meets first.
    """
    best = None
    for index, face in enumerate(mesh.faces):
        a, b, c = (points[i] for i in face)
        area = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
        if abs(area) < 1e-12:
            continue
        u = ((x - a.x) * (c.y - a.y) - (y - a.y) * (c.x - a.x)) / area
        v = ((b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x)) / area
        if u < 0.0 or v < 0.0 or u + v > 1.0:
            continue
        da, db, dc = (depths[i] for i in face)
        deep = da + (db - da) * u + (dc - da) * v
        if best is None or deep < best[0]:
            best = (deep, mesh.groups[index])
    return None if best is None else best[1]


def _on_top(facets, x, y):
    """Which group the last facet painted over a page point belongs to."""
    found = None
    for facet in facets:
        pts = facet.points
        crossings = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            if (a.y > y) != (b.y > y):
                crossings.append(a.x + (b.x - a.x) * (y - a.y) / (b.y - a.y))
        crossings.sort()
        for k in range(0, len(crossings) - 1, 2):
            if crossings[k] <= x <= crossings[k + 1]:
                found = facet.group
    return found


def _sampled(mesh, sort, view_name="front", steps=24):
    """Paint the scene both ways over a grid and count where they disagree.

    Returns `(wrong, covered)`: how many sample points the painted picture got
    wrong, and how many the object covers at all.
    """
    from inklet.three.camera import Camera
    from inklet.three.edges import facing_faces
    from inklet.three.shade import sorted_facets

    view = Camera.named(view_name).frame(mesh, width=40.0)
    points, depths = view.project_all(mesh.vertices)
    facing = facing_faces(mesh, view)
    facets = sorted_facets(mesh, view, points, depths, facing, cull=None,
                           sort=sort)
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    wrong = covered = 0
    for r in range(steps):
        y = min(ys) + (max(ys) - min(ys)) * (r + 0.5) / steps
        for c in range(steps):
            x = min(xs) + (max(xs) - min(xs)) * (c + 0.5) / steps
            truth = _nearest(mesh, view, points, depths, x, y)
            if truth is None:
                continue
            covered += 1
            if _on_top(facets, x, y) != truth:
                wrong += 1
    return wrong, covered


def test_two_facets_that_cross_have_no_order_and_the_depth_sort_invents_one():
    """The failure the exact order exists for, stated as a measurement.

    Half the picture, not a hairline: where two big facets cross, painting
    either one second puts it over the whole of the other, and exactly half of
    that is wrong. This is the baseline the next test has to beat.
    """
    wrong, covered = _sampled(_blades(), "depth")
    assert covered > 300
    assert wrong / covered > 0.4


def test_the_exact_order_paints_crossing_facets_right_the_whole_way_across():
    wrong, covered = _sampled(_blades(), "exact")
    assert covered > 300
    assert wrong == 0


def test_a_crossing_is_settled_by_cutting_once_and_not_by_cutting_both():
    """One cut per crossing pair, on the smaller facet.

    Both halves of a cut facet lie wholly on one side of the other's plane, so
    each has a definite order against it and the other keeps its outline. It
    matters more than it sounds: a cone pushed through a wall crosses the wall
    once per cone facet, and cutting the wall every time would shred one quad
    into a hundred pieces to settle what the cone's own facets settle between
    them.
    """
    from inklet.three.camera import Camera
    from inklet.three.edges import facing_faces
    from inklet.three.shade import sorted_facets

    mesh = _blades()
    view = Camera.named("front").frame(mesh, width=40.0)
    points, depths = view.project_all(mesh.vertices)
    facing = facing_faces(mesh, view)
    facets = sorted_facets(mesh, view, points, depths, facing, cull=None,
                           sort="exact")
    # Two quads in, three polygons out: one blade whole, the other in halves.
    assert len(facets) == 3
    counted = collections.Counter(f.group for f in facets)
    assert sorted(counted.values()) == [1, 2]


def test_the_exact_order_changes_nothing_about_a_convex_solid():
    """Front-facing facets of a convex solid never overlap, so there is nothing
    for the pairwise test to find and nothing for it to reorder. Byte for byte
    the same file, which is also what says the exact path did not quietly stop
    merging coplanar faces."""
    def drawn(sort):
        node = inklet.solid("box", width=30.0, view="three-quarter",
                         style="shaded", sort=sort)
        return _fills(node)

    assert drawn("depth") == drawn("exact")


def test_the_exact_order_keeps_a_flat_face_in_one_piece():
    """The pairwise test wants convex outlines, and a coplanar patch is not
    always one -- but dropping the merge wholesale would take a plane's
    triangulation with it and leave a hairline down every seam. Merged where
    the outline came out convex, split back into triangles where it did not."""
    from inklet.three.solids import plane

    facets = _shaded(plane(1.0, 1.0, segments=4), cull=False, sort="exact")
    # One polygon, not the thirty-two triangles it was built from. Its outline
    # is the grid's perimeter, so sixteen corners rather than four.
    assert len(facets) == 1
    assert len(facets[0].points) == 16


def test_a_concave_patch_falls_back_to_its_own_triangles():
    """An L-shaped flat face is one coplanar patch and not a convex outline.
    Clipping one against another only gives the region they share when both
    are convex, so this one goes back to triangles rather than being asked a
    question it would answer wrongly."""
    from inklet.three.mesh import Mesh
    from inklet.three.linalg import Vec3

    # An L in the xz plane, as four triangles of one flat patch.
    corners = [Vec3(0, 0, 0), Vec3(2, 0, 0), Vec3(2, 0, 1), Vec3(1, 0, 1),
               Vec3(1, 0, 2), Vec3(0, 0, 2)]
    faces = ((0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5))
    mesh = Mesh(tuple(corners), faces)
    plain = _shaded(mesh, "front", cull=False, sort="depth")
    exact = _shaded(mesh, "front", cull=False, sort="exact")
    assert len(plain) == 1                      # merged: one L-shaped ring
    assert len(exact) == len(faces)             # and back to triangles


def test_the_exact_order_is_reachable_from_the_authoring_surface():
    node = inklet.solid("torus", width=30.0, view="three-quarter",
                     style="shaded", sort="exact")
    assert _fills(node)
    with pytest.raises(MeshError, match="unknown sort"):
        inklet.solid("torus", width=30.0, style="shaded", sort="painter")


# -- transparency -----------------------------------------------------------


def test_opacity_is_written_once_on_the_group_and_not_on_every_path():
    """The whole reason it goes on the group.

    SVG composites a group at its opacity *after* drawing it, so facets inside
    cannot darken each other where they overlap -- and they do overlap, by the
    hundredth of a millimetre the bleed adds to cover antialiasing seams. Per
    path, every one of those joins would come out as a dark hairline, which is
    the seam problem again with the sign flipped.
    """
    fig = inklet.Figure(width=40.0)
    fig.add(inklet.solid("sphere", width=30.0, view="three-quarter",
                      style="shaded", opacity=0.4))
    assert fig.to_svg().count('opacity="0.4"') == 1


def test_opacity_leaves_the_inked_edges_alone():
    """A ghosted object still has to read as an object, and what says where it
    is is its outline. The other reading -- the whole node faded -- is a style
    away: `node.styled(opacity=...)`."""
    from inklet.three.backend import FACETS_KIND, INK_KIND, OUTLINE_KIND

    node = inklet.solid("sphere", width=30.0, view="three-quarter",
                     style="shaded", opacity=0.4)
    faded = [n for n in _walk(node) if n.style.opacity is not None]
    assert len(faded) == 1
    assert faded[0].kind in (FACETS_KIND, "model-facet")
    assert all(n.style.opacity is None for n in _walk(node)
               if n.kind in (INK_KIND, OUTLINE_KIND))


def test_a_fully_opaque_model_is_the_file_it_always_was():
    """The default has to cost nothing, down to the byte -- otherwise every
    figure in the repository moves for a feature none of them use."""
    def drawn(**kwargs):
        fig = inklet.Figure(width=40.0)
        fig.add(inklet.solid("torus", width=30.0, view="three-quarter",
                          style="shaded", **kwargs))
        return _normalised(fig.to_svg())

    assert drawn() == drawn(opacity=1.0)


def test_opacity_has_to_be_a_fraction():
    with pytest.raises(MeshError, match="opacity is a fraction"):
        inklet.solid("sphere", width=20.0, style="shaded", opacity=1.5)


def _normalised(svg):
    """Two figures built in one process get different generated ids; nothing
    about the drawing depends on them."""
    return re.sub(r'(id|href)="[^"]*"', "", re.sub(r"#[a-z]+\d+", "#x", svg))


def _fills(node):
    return [n.prim.subpaths for n in _walk(node)
            if n.prim is not None and getattr(n.prim, "filled", False)]


def _corners(facet):
    """`_overlaps` takes plain pairs; unpacking `Vec2` per read cost a fifth
    of the render."""
    return tuple((p.x, p.y) for p in facet.points)


def _painted_order(facets, runs):
    """Which path index each facet ended up in."""
    where = {}
    for position, (_, members) in enumerate(runs):
        for facet in members:
            where[id(facet)] = position
    return [where[id(facet)] for facet in facets]


# -- ambient occlusion ------------------------------------------------------


def _occluded(mesh, view_name="three-quarter", **kwargs):
    """Per-vertex enclosure, through the same view the shader would use."""
    from inklet.three.camera import Camera
    from inklet.three.edges import facing_faces
    from inklet.three.occlude import vertex_occlusion

    view = Camera.named(view_name).frame(mesh, width=30.0)
    points, depths = view.project_all(mesh.vertices)
    facing = facing_faces(mesh, view)
    drawable = [i for i, front in enumerate(facing) if front]
    return vertex_occlusion(mesh, view, points, depths, drawable, **kwargs)


@pytest.mark.parametrize("name, mesh", [
    ("sphere", solids.sphere(1.0, 3)),
    ("fine sphere", solids.sphere(1.0, 5)),
    ("box", solids.box(1.0, 1.0, 1.0)),
    ("cylinder", solids.cylinder(0.5, 1.4, segments=96)),
    ("cone", solids.cone(0.5, 1.2, segments=96)),
])
def test_a_convex_solid_is_occluded_nowhere(name, mesh):
    """The load-bearing invariant, and the reason the measurement is written
    the way it is.

    A convex body occludes no part of itself: stand anywhere on it, look out
    along any direction above the tangent plane, and you leave. So the correct
    answer for every vertex of a sphere, a box, a cylinder and a cone is
    exactly zero, and anything above zero is the measurement mistaking the
    body's own curvature for a hollow.

    The obvious screen-space test -- "is the surface at this sample nearer the
    camera than I am?" -- fails this outright. At the rim of a sphere half the
    disc around a vertex is nearer, so the whole silhouette comes out
    darkened, which reads as a bruise around every ball in the figure. Testing
    against the tangent plane instead is what makes this pass.

    The fine sphere is here because it is the harder case and it fails
    differently: a vertex normal is an average of the facets meeting at it, so
    on any faceted surface the neighbours stand a little above the tangent
    plane, and the finer the mesh the smaller the disc that still reaches only
    them. That is what `_COARSEST` and `_ABOVE` are for, and a subdivision-five
    icosphere is what set both.
    """
    found = _occluded(mesh)
    assert max(found) == pytest.approx(0.0, abs=1e-12), \
        f"{name}: {max(found)}"


def test_a_hollow_is_darker_than_the_wall_it_is_cut_into():
    """And the point of the whole exercise: the shape has to be *told apart*
    from its surroundings, not merely darkened along with them.

    A torus is the smallest honest test -- one concavity, the inside of the
    hole, and everything else convex. The vertices facing the hole have to
    come out well up, and the vertices on the outer rim have to stay near
    zero, on the same object in the same pass.
    """
    mesh = solids.torus(1.0, 0.3, segments=48, rings=20)
    found = _occluded(mesh)                  # three-quarter: the hole is open
    inner, outer = [], []
    for index, point in enumerate(mesh.vertices):
        away = (point.x ** 2 + point.y ** 2) ** 0.5
        (inner if away < 1.0 else outer).append(found[index])
    assert max(inner) > 0.2
    assert sum(outer) / len(outer) < 0.01


def test_a_tight_channel_and_a_broad_hollow_both_read_at_one_setting():
    """Why the disc is a stack of three and not one.

    A milled channel and a torus's hole are hollows two octaves apart in size,
    and a single radius serves one at the cost of the other. Measured on a
    disc wide enough to span the torus, the channel is diluted -- most of that
    disc is out in the open air above the channel, and the blocked fraction
    comes out small. Measured on a disc narrow enough to sit inside the
    channel, the torus is missed entirely, because the whole disc lands on the
    hole's own far wall and nothing on it stands above the tangent plane.

    So both are asked here, at one setting, with the walls of each required to
    darken and the outsides of each required not to.
    """
    from inklet.three.linalg import Mat4

    def trench(span=2.0, gap=0.5, wall=0.9, thick=0.45):
        """A floor plate with a wall standing either side: a pocket, milled."""
        plates = [solids.box(span, span, 0.2)]
        for side in (-1.0, 1.0):
            plates.append(solids.box(thick, span, wall).transformed(
                Mat4.translation(Vec3(side * (gap + thick) / 2.0, 0.0,
                                      (wall + 0.2) / 2.0))))
        return plates[0].merged(*plates[1:])

    mesh = trench()
    found = _occluded(mesh)
    inside = [found[i] for i, p in enumerate(mesh.vertices)
              if abs(p.x) < 0.3]                    # the channel's own walls
    outside = [found[i] for i, p in enumerate(mesh.vertices)
               if abs(p.x) > 0.7]                   # the walls' outer faces
    assert max(inside) > 0.05
    assert max(outside) == pytest.approx(0.0, abs=1e-12)

    # And the hollow two octaves up, in the same pass at the same setting.
    ring = solids.torus(1.0, 0.3, segments=48, rings=20)
    found = _occluded(ring)
    hole = [found[i] for i, p in enumerate(ring.vertices)
            if (p.x ** 2 + p.y ** 2) ** 0.5 < 1.0]
    assert max(hole) > 0.2


def test_occlusion_only_ever_darkens():
    """It is a *shadow* term: it comes off the tone and is never added to it.
    A hollow that came out brighter than its surroundings would read as a
    bump, which is the one reading the effect exists to prevent."""
    mesh = solids.torus(1.0, 0.3, segments=48, rings=20)
    plain = {f.ring: f.tone for f in _shaded(mesh)}
    dark = {f.ring: f.tone for f in _shaded(mesh, occlusion=0.4)}
    assert plain.keys() == dark.keys()       # flat facets, so they correspond
    assert any(dark[ring] < plain[ring] for ring in plain)
    assert all(dark[ring] <= plain[ring] for ring in plain)


def test_occlusion_costs_no_extra_fills():
    """The reason it is folded into the tone rather than painted over it. A
    protein collapses into a few dozen paths because its facets quantise onto
    a handful of tones; a separate darkening pass would hand every facet its
    own value and undo that in one step."""
    mesh = solids.torus(1.0, 0.3, segments=48, rings=20)
    plain = _shaded(mesh, smooth_degrees=40.0, levels=12)
    dark = _shaded(mesh, smooth_degrees=40.0, levels=12, occlusion=0.4)
    assert len({f.tone for f in dark}) <= 12
    assert len(dark) < len(plain) * 1.1


def test_an_unoccluded_model_is_the_file_it_always_was():
    """Off has to cost nothing, down to the byte."""
    def drawn(**kwargs):
        fig = inklet.Figure(width=40.0)
        fig.add(inklet.solid("torus", width=30.0, view="three-quarter",
                          style="shaded", **kwargs))
        return _normalised(fig.to_svg())

    assert drawn() == drawn(occlusion=0.0)


def test_occlusion_is_reachable_from_the_authoring_surface():
    plain = inklet.solid("torus", width=30.0, view="three-quarter",
                      style="shaded")
    dark = inklet.solid("torus", width=30.0, view="three-quarter",
                     style="shaded", occlusion=0.45)
    assert _normalised(_svg_of(plain)) != _normalised(_svg_of(dark))


def test_occlusion_has_to_be_a_fraction():
    with pytest.raises(MeshError, match="occlusion is a fraction"):
        inklet.solid("sphere", width=20.0, style="shaded", occlusion=1.5)


def test_occlusion_is_the_same_twice():
    """The spiral is turned by the golden angle per vertex rather than by a
    random one, so that two runs of one figure are the same file."""
    mesh = solids.torus(1.0, 0.3, segments=48, rings=20)
    assert _occluded(mesh) == _occluded(mesh)


def _svg_of(node):
    fig = inklet.Figure(width=40.0)
    fig.add(node)
    return fig.to_svg()


# -- anchors that know what is in front of them -----------------------------


def _blocked_scene():
    """A bar leaning away from the camera, with a wall across its near end.

    In the "front" view y is depth and z is up the page, so the bar runs from
    near-and-low to far-and-high and the wall stands nearer than any of it,
    covering the lower half of the page. The bar's *nearest* point is therefore
    behind the wall and its visible points are the high ones -- which is the
    whole distinction, made as small as it can be made.
    """
    from inklet.three.linalg import Mat4

    bar = solids.box(0.3, 0.3, 3.0).transformed(
        Mat4.rotation(Vec3(1.0, 0.0, 0.0), -30.0))
    wall = solids.box(4.0, 0.2, 1.6).transformed(
        Mat4.translation(Vec3(0.0, -2.0, -0.9)))
    along = [Vec3(0.0, math.sin(math.radians(-30.0)) * t,
                  math.cos(math.radians(-30.0)) * t)
             for t in (-1.4, -0.7, 0.0, 0.7, 1.4)]
    return bar, wall, along


def test_pick_centroid_is_what_anchor3d_always_did():
    """One point in, that point out. The default cannot move."""
    node = inklet.solid("sphere", width=30.0, view="front")
    inklet.three.anchor3d(node, "top", (0.0, 0.0, 0.5))
    inklet.three.anchor3d(node, "same", [(0.0, 0.0, 0.5)], pick="visible")
    assert node.anchor_point("top") == node.anchor_point("same")


def test_pick_centroid_averages_the_points_it_is_given():
    node = inklet.solid("sphere", width=30.0, view="front")
    inklet.three.anchor3d(node, "mean", [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
    inklet.three.anchor3d(node, "middle", (0.0, 0.0, 0.0))
    assert node.anchor_point("mean") == node.anchor_point("middle")


def test_pick_nearest_takes_the_candidate_closest_to_the_camera():
    """`View.project` measures depth along `forward`, so nearest is the
    *smallest* depth -- the convention every other part of the engine reads,
    and the one it is easiest to write backwards."""
    from inklet.three.mesh import merge

    bar, wall, along = _blocked_scene()
    node = inklet.three.model(merge([bar, wall]), width=30.0, view="front",
                           style="shaded")
    view = inklet.three.view_of(node)
    inklet.three.anchor3d(node, "near", along, pick="nearest")
    want = min(along, key=lambda p: view.project(p).depth)
    assert node.anchor_point("near") == view.project(want).point


def test_pick_visible_refuses_a_point_with_something_drawn_in_front_of_it():
    """The distinction the whole option exists for.

    The nearest point of the bar is the one behind the wall. A leader aimed
    there stops inside the wall and appears to name the wall, which is the
    failure this replaces -- and no amount of choosing by depth can avoid it,
    because depth is exactly what makes that point the wrong one.
    """
    from inklet.three.mesh import merge

    bar, wall, along = _blocked_scene()
    node = inklet.three.model(merge([bar, wall]), width=30.0, view="front",
                           style="shaded")
    view = inklet.three.view_of(node)
    inklet.three.anchor3d(node, "near", along, pick="nearest")
    inklet.three.anchor3d(node, "seen", along, pick="visible")
    assert node.anchor_point("seen") != node.anchor_point("near")
    # It gave up depth to get out from behind the wall, which is the trade the
    # nearest-of-the-run rule cannot make.
    picked = {view.project(p).point: p for p in along}
    seen = picked[node.anchor_point("seen")]
    near = picked[node.anchor_point("near")]
    assert view.project(seen).depth > view.project(near).depth


def test_pick_visible_sees_across_the_parts_of_a_scene():
    """A feature hidden behind a *different part* is hidden all the same, so
    the test is run against the parts merged rather than one at a time."""
    bar, wall, along = _blocked_scene()
    rig = inklet.three.scene([("bar", bar), ("wall", wall)],
                          width=30.0, view="front", style="shaded")
    inklet.three.anchor3d(rig, "near", along, pick="nearest")
    inklet.three.anchor3d(rig, "seen", along, pick="visible")
    assert rig.anchor_point("seen") != rig.anchor_point("near")


def test_pick_visible_falls_back_to_nearest_when_nothing_can_be_seen():
    """A helix wholly behind a sheet has no visible point, and the honest
    answer is the near side of it rather than no label at all."""
    from inklet.three.linalg import Mat4
    from inklet.three.mesh import merge

    hidden = solids.box(0.4, 0.4, 0.4).transformed(
        Mat4.translation(Vec3(0.0, 2.0, 0.0)))
    front = solids.box(4.0, 0.2, 4.0).transformed(
        Mat4.translation(Vec3(0.0, -2.0, 0.0)))
    node = inklet.three.model(merge([hidden, front]), width=30.0, view="front",
                           style="shaded")
    inside = [Vec3(0.0, 2.0, z) for z in (-0.1, 0.0, 0.1)]
    inklet.three.anchor3d(node, "near", inside, pick="nearest")
    inklet.three.anchor3d(node, "seen", inside, pick="visible")
    assert node.anchor_point("seen") == node.anchor_point("near")


def test_the_depth_grid_is_built_once_per_node():
    """A figure hangs several labels off one model, and rasterising fifty
    thousand faces once a label is the difference between a tenth of a second
    and a second."""
    from inklet.three.api import _FRONTS

    node = inklet.solid("torus", width=30.0, view="three-quarter",
                     style="shaded")
    before = len(_FRONTS)
    spots = [(0.0, 0.0, 0.4), (0.0, 0.4, 0.0), (0.4, 0.0, 0.0)]
    for count in range(3):
        inklet.three.anchor3d(node, f"a{count}", spots, pick="visible")
    assert len(_FRONTS) == before + 1


def test_a_node_inklet_three_did_not_build_has_no_anchors_to_add():
    with pytest.raises(MeshError, match="no 3D view"):
        inklet.three.anchor3d(inklet.text("plain"), "x", (0.0, 0.0, 0.0))


def test_pick_has_to_be_one_of_the_three():
    node = inklet.solid("sphere", width=30.0, view="front")
    with pytest.raises(MeshError, match="pick is one of"):
        inklet.three.anchor3d(node, "x", (0.0, 0.0, 0.5), pick="closest")


def test_an_anchor_needs_points():
    node = inklet.solid("sphere", width=30.0, view="front")
    with pytest.raises(MeshError, match="was given no points"):
        inklet.three.anchor3d(node, "x", [])
