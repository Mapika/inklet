"""`at=`, `spin=`, `scale=`, and the anchors a scene's parts answer to.

Two things that used to be arithmetic at the call site. Placing a solid was
four lines of `Mat4` that said nothing about the assembly, and clearing a label
off a part of a scene meant projecting the part's box by hand. Both are now
spellings, and a spelling is only worth having if it means exactly one thing --
which is what most of this file pins down.
"""

from __future__ import annotations

import re

import pytest

import inklet
from inklet.three import Mat4, Mesh, MeshError, Vec3, build, outline_of, parts_of
from inklet.three.api import _placed
from inklet.three.place import as_axis, placement


# -- the transform the keywords stand for ---------------------------------


def test_nothing_said_is_no_transform():
    # Not the identity: `model()` passes this straight to `transform=`, and a
    # mesh that is not moved should not be walked over to move it by nothing.
    assert placement() is None


def test_at_is_where_the_origin_lands():
    assert placement(at=(1.0, 2.0, 3.0)).apply(Vec3()) == Vec3(1.0, 2.0, 3.0)


def test_spin_takes_an_axis_and_an_angle():
    turned = placement(spin=("z", 90)).apply(Vec3(1, 0, 0))
    assert turned.y == pytest.approx(1.0)


def test_spin_takes_a_negative_axis():
    turned = placement(spin=("-z", 90)).apply(Vec3(1, 0, 0))
    assert turned.y == pytest.approx(-1.0)


def test_spin_takes_three_euler_angles():
    # x then y then z, which is the order the docstring promises.
    a = placement(spin=(90, 0, 0)).apply(Vec3(0, 1, 0))
    assert a.z == pytest.approx(1.0)
    b = placement(spin=(0, 0, 90)).apply(Vec3(1, 0, 0))
    assert b.y == pytest.approx(1.0)


def test_spin_takes_a_matrix_already_worked_out():
    turn = Mat4.rotation(Vec3(0, 0, 1), 30.0)
    assert placement(spin=turn).apply(Vec3(1, 0, 0)) == turn.apply(Vec3(1, 0, 0))


def test_scale_is_one_number_or_three():
    assert placement(scale=2.0).apply(Vec3(1, 1, 1)) == Vec3(2, 2, 2)
    assert placement(scale=(1, 2, 3)).apply(Vec3(1, 1, 1)) == Vec3(1, 2, 3)


def test_scale_then_spin_then_move():
    # The only order in which the numbers mean what they look like: `scale=` is
    # about the solid's own centre, and `at=` is a point rather than a
    # displacement some later rotation swings elsewhere.
    where = placement(at=(10, 0, 0), spin=("z", 90), scale=2.0)
    assert where.apply(Vec3(1, 0, 0)).as_tuple() == \
        pytest.approx((10.0, 2.0, 0.0))


def test_a_bare_angle_says_which_axis_it_wanted():
    with pytest.raises(MeshError, match=r"spin=\('z', 30\)"):
        placement(spin=30)


def test_a_nonsense_spin_is_named():
    with pytest.raises(MeshError, match="neither three Euler angles"):
        placement(spin=(1, 2, 3, 4))


def test_scale_zero_is_refused():
    with pytest.raises(MeshError, match="flattens"):
        placement(scale=0)
    with pytest.raises(MeshError, match="flattens"):
        placement(scale=(1, 0, 1))


def test_an_unknown_axis_lists_the_known_ones():
    with pytest.raises(MeshError, match="unknown axis"):
        as_axis("q")


def test_an_axis_may_be_a_vector():
    assert as_axis((0, 0, 5)) == Vec3(0, 0, 1)
    with pytest.raises(MeshError, match="zero vector"):
        as_axis((0, 0, 0))


# -- the keywords on the public calls -------------------------------------


def test_solid_places_itself_where_it_was_told():
    here = inklet.solid("cube", width=20, at=(0, 0, 0), view="front")
    there = inklet.solid("cube", width=20, at=(0, 0, 40), view="front")
    # Straight down the view, so the two draw the same size in different places.
    assert here.width == pytest.approx(there.width)


def test_placement_keywords_and_transform_agree():
    # The keywords are a spelling, not a second mechanism: the same placement
    # written either way has to give the same drawing, down to the path data.
    by_hand = Mat4.translation(Vec3(1, 0, 0)) @ Mat4.rotation(Vec3(0, 0, 1), 45.0)
    spelled = inklet.solid("box", width=20, spin=("z", 45), at=(1, 0, 0),
                        view="isometric")
    written = inklet.solid("box", width=20, transform=by_hand, view="isometric")
    assert _paths(spelled) == _paths(written)


def _paths(node) -> str:
    """A node's drawn geometry, with the generated ids taken back out."""
    svg = inklet.to_svg(inklet.figure(width=40).add(node))
    return re.sub(r' id="[^"]*"', "", svg)


def test_the_keywords_compose_onto_an_explicit_transform():
    # `transform=` is the model's own frame, so anything the keywords say
    # happens after it -- otherwise `at=` would mean "wherever the transform
    # carries that point", which is not what anyone writes it for.
    turn = Mat4.rotation(Vec3(0, 0, 1), 90.0)
    both = _placed(turn, (1, 0, 0), None, None)
    assert both.apply(Vec3(1, 0, 0)).as_tuple() == pytest.approx((1.0, 1.0, 0.0))


def test_the_top_level_names_are_exported():
    for name in ("Mesh", "Vec3", "Mat4", "anchor3d", "outline_of"):
        assert name in inklet.__all__
        assert getattr(inklet, name) is not None


# -- a scene's parts and where they are -----------------------------------


def _rig() -> inklet.Diagram:
    body = build("box", size_x=2.0, size_y=2.0, size_z=0.4)
    lid = build("box", size_x=1.0, size_y=1.0, size_z=0.2).transformed(
        Mat4.translation(Vec3(0.0, 0.0, 1.0)))
    return inklet.scene([("body", body),
                      ("lid", lid, {"anchors": {"tip": (0.0, 0.0, 1.1)}})],
                     width=60, view="front", style="shaded")


def test_every_part_answers_to_the_eight_compass_points():
    rig = _rig()
    for point in ("n", "s", "e", "w", "ne", "nw", "se", "sw", "center"):
        assert rig.at(f"lid.{point}") is not None


def test_the_centre_and_the_part_itself_are_the_same_point():
    rig = _rig()
    assert rig.anchor_point("lid") == rig.anchor_point("lid.center")


def test_the_compass_is_the_projected_box():
    rig = _rig()
    nw, se = rig.anchor_point("lid.nw"), rig.anchor_point("lid.se")
    centre = rig.anchor_point("lid.center")
    assert nw.x < centre.x < se.x
    assert nw.y < centre.y < se.y
    assert rig.anchor_point("lid.n").y == pytest.approx(nw.y)
    assert rig.anchor_point("lid.e").x == pytest.approx(se.x)


def test_the_lid_is_above_the_body_on_the_page():
    # Front view, z up: whatever else is true, the lid's box has to sit higher.
    rig = _rig()
    assert rig.anchor_point("lid.s").y < rig.anchor_point("body.n").y + 1e-6


def test_a_parts_own_3d_anchor_is_reachable_from_the_scene():
    rig = _rig()
    assert rig.at("lid.tip") is not None
    assert rig.anchor_point("lid.tip").y < rig.anchor_point("lid.center").y


def test_the_compass_is_there_under_exact_order_too():
    body = build("box", size_x=2.0, size_y=2.0, size_z=0.4)
    lid = build("box", size_x=1.0, size_y=1.0, size_z=0.2).transformed(
        Mat4.translation(Vec3(0.0, 0.0, 1.0)))
    rig = inklet.scene([("body", body), ("lid", lid)], width=60, view="front",
                    style="shaded", order="exact")
    assert rig.anchor_point("lid.ne") is not None
    assert rig.anchor_point("lid") == rig.anchor_point("lid.center")


def test_outline_of_a_part_is_a_closed_curve_in_its_own_frame():
    rig = _rig()
    curves = outline_of(rig.find("lid"))
    assert curves
    points, closed = curves[0]
    assert closed
    assert len(points) >= 3


def test_outline_of_a_mesh_needs_the_view_to_project_it():
    with pytest.raises(MeshError, match="needs the view"):
        outline_of(build("cube"))


def test_parts_of_gives_the_parts_in_declaration_order():
    rig = _rig()
    assert [p.name for p in parts_of(rig)] == ["body", "lid"]


def test_parts_of_filters():
    rig = _rig()
    assert [p.name for p in parts_of(rig, lambda p: p.name == "lid")] == ["lid"]


def test_parts_of_refuses_a_node_that_is_not_a_scene():
    with pytest.raises(MeshError, match="not built by inklet.scene"):
        parts_of(inklet.solid("cube", width=20))


def test_a_scene_part_can_be_placed_in_its_options():
    body = build("box", size_x=2.0, size_y=2.0, size_z=0.4)
    lid = build("box", size_x=1.0, size_y=1.0, size_z=0.2)
    rig = inklet.scene([("body", body), ("lid", lid, {"at": (0, 0, 2)})],
                    width=60, view="front", style="shaded")
    # Up the page, because the front view has z up and y grows downward.
    assert rig.anchor_point("lid").y < rig.anchor_point("body").y


def test_a_part_is_framed_where_it_was_placed_not_where_it_was_built():
    # The trap this guards: placement applied inside the part's own drawing
    # pass would carry it somewhere the scene had not made room for, and then
    # place it by the box it had before it moved.
    lid = build("box", size_x=1.0, size_y=1.0, size_z=0.2)
    near = inklet.scene([("lid", lid, {"at": (0, 0, 0)})], width=60, view="front")
    far = inklet.scene([("lid", lid, {"at": (0, 0, 9)})], width=60, view="front")
    assert near.anchor_point("lid") == far.anchor_point("lid")
    assert near.height == pytest.approx(far.height)


def test_placement_agrees_between_the_two_scene_orders():
    body = build("box", size_x=2.0, size_y=2.0, size_z=0.4)
    lid = build("box", size_x=1.0, size_y=1.0, size_z=0.2)
    parts = [("body", body), ("lid", lid, {"at": (0, 0, 2)})]
    loose = inklet.scene(parts, width=60, view="front", style="shaded")
    fused = inklet.scene(parts, width=60, view="front", style="shaded",
                      order="exact")
    assert loose.anchor_point("lid") == fused.anchor_point("lid")
