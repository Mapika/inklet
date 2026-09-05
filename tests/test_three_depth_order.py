"""`DEPTH_ORDER`: does a scene's paint order agree with its camera?

`scene(order="parts")` gives each part one depth -- its centre's -- and paints
furthest first. That is right nearly always and wrong exactly when a part's
centre is not where its geometry is, and the picture that comes out shows a
plate through a bolt. The scene below is the smallest thing that reproduces it:
a ramp receding away from the camera, whose *centre* is deep, and a small tag
sitting over the ramp's near end, whose centre is shallower and which is
therefore painted last -- over a surface it is entirely behind.

The other half of the file is the positive form. `assert_order=` is the only
way a requirement like "the objective is in front of the sample" survives the
figure being edited, so it is an error rather than a warning and the three ways
it can fail get three different sentences.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.three import Mat4, Mesh, MeshError, Vec3, build
from inklet.three.api import scene_paint

#: A plane running away from the camera under a front view, where depth is +y:
#: near and low at one edge, far and high at the other. Its centre is at depth
#: 6, which is the whole point -- nothing at its centre is anywhere near the
#: surface an overlapping part meets.
_RAMP = Mesh((Vec3(-3, -1, -2), Vec3(3, -1, -2), Vec3(3, 13, 2), Vec3(-3, 13, 2)),
             ((0, 1, 2), (0, 2, 3)), name="ramp")


def _tag(depth: float) -> Mesh:
    """A small solid over the ramp's near end, at the depth given."""
    return build("box", size_x=0.8, size_y=0.8, size_z=0.8).transformed(
        Mat4.translation(Vec3(0.0, depth, -1.5)))


def _rig(depth: float = 3.0, **kwargs) -> inklet.Diagram:
    return inklet.scene([("ramp", _RAMP), ("tag", _tag(depth), kwargs.pop("tag", {}))],
                     width=60, view="front", style="shaded", **kwargs)


def _findings(node: inklet.Diagram):
    figure = inklet.figure(width=70)
    figure.add(node)
    return figure.lint(rules=["DEPTH_ORDER"])


# -- the finding ----------------------------------------------------------


def test_a_part_painted_over_what_it_is_behind_is_reported():
    found = _findings(_rig())
    assert len(found) == 1
    assert found[0].code == "DEPTH_ORDER"
    assert found[0].severity == "warning"
    assert "tag is painted over ramp" in found[0].message


def test_the_finding_says_how_far_wrong_it_is():
    # A number in millimetres on the page, not in model units: "4.7mm behind"
    # is something an author can picture, "4.68 units" is not.
    assert "mm behind it everywhere the two overlap" in _findings(_rig())[0].message


def test_the_hint_names_both_ways_out():
    hint = _findings(_rig())[0].hint
    assert 'order="exact"' in hint
    assert "in_front_of=" in hint


def test_the_finding_points_at_both_parts():
    found = _findings(_rig())[0]
    assert len(found.targets) == 2
    assert found.where is not None


def test_a_part_really_in_front_is_silent():
    assert _findings(_rig(depth=-3.0)) == []


def test_parts_that_do_not_overlap_are_silent():
    aside = build("box", size_x=1, size_y=1, size_z=1).transformed(Mat4.translation(Vec3(20, 3, 0)))
    assert _findings(inklet.scene([("ramp", _RAMP), ("tag", aside)],
                               width=60, view="front", style="shaded")) == []


def test_a_flat_decal_on_the_face_it_lies_on_is_silent():
    # Two surfaces at the same depth share every cell with the two numbers
    # equal to float noise. Calling that "behind" would report every label on
    # every panel in every figure.
    decal = Mesh((Vec3(-1, -1, -2), Vec3(1, -1, -2), Vec3(1, -1 + 1e-9, -0.5)),
                 ((0, 1, 2),), name="decal")
    assert _findings(inklet.scene([("ramp", _RAMP), ("decal", decal)],
                               width=60, view="front", style="shaded")) == []


def test_an_exact_scene_has_no_per_part_order_to_be_wrong():
    # Depth is settled facet by facet there, so the rule has nothing to say.
    assert _findings(_rig(order="exact")) == []


def test_a_figure_with_no_3d_in_it_costs_nothing():
    figure = inklet.figure(width=70)
    figure.add(inklet.box("hello"))
    assert figure.lint(rules=["DEPTH_ORDER"]) == []


# -- the overrides silence it ---------------------------------------------


def test_behind_settles_it():
    assert _findings(_rig(tag={"behind": "ramp"})) == []


def test_in_front_of_is_taken_as_the_answer_rather_than_checked():
    # Overriding the depth order is what these exist for. Reporting the
    # override as a mistake would be the rule arguing with its own suggestion.
    assert _findings(_rig(tag={"in_front_of": "ramp"})) == []


def test_draw_order_settles_it():
    assert _findings(_rig(tag={"draw_order": 0})) == []


def test_behind_actually_moves_the_part_in_the_paint_order():
    rig = _rig(tag={"behind": "ramp"})
    paint = scene_paint(rig)
    assert paint.names == ("ramp", "tag")
    assert paint.position(1) < paint.position(0)
    assert paint.declared == frozenset({1})


def test_a_part_cannot_have_two_places_in_the_order():
    with pytest.raises(MeshError, match="say it once"):
        _rig(tag={"behind": "ramp", "draw_order": 3})


def test_a_neighbour_that_is_not_a_part_is_named():
    with pytest.raises(MeshError, match="not a part of this scene"):
        _rig(tag={"behind": "lid"})


def test_a_part_cannot_be_behind_itself():
    with pytest.raises(MeshError, match="itself"):
        _rig(tag={"behind": "tag"})


# -- the assertion --------------------------------------------------------


def test_a_true_assertion_is_silent():
    assert _findings(_rig(depth=-3.0, assert_order=[("tag", "ramp")])) == []


def test_an_assertion_the_paint_order_contradicts_is_an_error():
    found = _findings(_rig(depth=-3.0, assert_order=[("ramp", "tag")]))
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "was asserted in front of" in found[0].message
    assert "is painted over it" in found[0].message


def test_an_assertion_the_geometry_contradicts_says_to_move_the_geometry():
    # Painted in front, and behind. No paint order can fix that, so the hint
    # has to say so rather than suggest another keyword.
    found = _findings(_rig(assert_order=[("tag", "ramp")]))
    assert any("behind ramp everywhere" in d.message for d in found)
    error = [d for d in found if d.severity == "error"][0]
    assert "move the geometry" in error.hint


def test_an_assertion_two_parts_that_never_meet_cannot_settle():
    aside = build("box", size_x=1, size_y=1, size_z=1).transformed(Mat4.translation(Vec3(20, 3, 0)))
    found = _findings(inklet.scene([("ramp", _RAMP), ("tag", aside)],
                                width=60, view="front", style="shaded",
                                assert_order=[("tag", "ramp")]))
    assert len(found) == 1
    assert "do not overlap on the page" in found[0].message


def test_an_assertion_is_checked_on_an_exact_scene_too():
    # `order="exact"` silences the survey but not a written-down requirement:
    # fusing the scene draws the truth, and the assertion is about what the
    # truth has to be.
    found = _findings(_rig(order="exact", assert_order=[("tag", "ramp")]))
    assert len(found) == 1
    assert found[0].severity == "error"


def test_an_assertion_about_a_part_that_is_not_there_is_refused_at_build_time():
    with pytest.raises(MeshError, match="not a part of this scene"):
        _rig(assert_order=[("tag", "lid")])


def test_an_assertion_needs_a_pair():
    with pytest.raises(MeshError, match=r"\(front, back\) pairs"):
        _rig(assert_order=[("tag",)])


def test_a_part_cannot_be_asserted_in_front_of_itself():
    with pytest.raises(MeshError, match="in front of itself"):
        _rig(assert_order=[("tag", "tag")])


# -- the rule is registered -----------------------------------------------


def test_the_rule_is_in_the_default_set():
    from inklet.diagnostics.rules import RULES
    assert "DEPTH_ORDER" in RULES
    figure = inklet.figure(width=70)
    figure.add(_rig())
    assert any(d.code == "DEPTH_ORDER" for d in figure.lint())
