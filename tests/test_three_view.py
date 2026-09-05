"""Cameras, projection, and the auto-fit that spares the author a scale factor.

The load-bearing claims here are directional. A projection can be wrong in six
independent ways -- flipped y, swapped axes, mirrored handedness, an offset
that is not a centring, a scale that fits the wrong dimension, a perspective
divide with no divide -- and each one produces a picture that still looks like
a picture. So every test names the direction it is pinning down.
"""

from __future__ import annotations

import math

import pytest

from inklet.core import Vec2
from inklet.three import Camera, MeshError, PRESETS, Vec3, preset_names
from inklet.three.camera import as_camera
from inklet.three.solids import box, cube, sphere


CUBE = cube(1.0)


# -- orientation ----------------------------------------------------------

def test_front_view_looks_along_positive_y():
    # Azimuth is measured from -y toward +x, so azimuth 0 stands the camera in
    # front of the model on the -y side and looks the way the reader does.
    assert Camera(0.0, 0.0).direction.y == pytest.approx(-1.0)


def test_elevation_lifts_the_camera_along_positive_z():
    assert Camera(0.0, 90.0).direction.z == pytest.approx(1.0)


def test_page_y_grows_downward():
    # inklet's single most easily inverted convention. A point higher in the
    # model must come out with a *smaller* y on the page.
    view = Camera.named("front").frame(CUBE, width=10.0)
    high = view.project(Vec3(0.0, 0.0, 0.4)).point
    low = view.project(Vec3(0.0, 0.0, -0.4)).point
    assert high.y < low.y


def test_model_x_grows_rightward_in_a_front_view():
    view = Camera.named("front").frame(CUBE, width=10.0)
    assert view.project(Vec3(0.4, 0, 0)).point.x > view.project(Vec3(-0.4, 0, 0)).point.x


def test_depth_grows_away_from_the_camera():
    view = Camera.named("front").frame(CUBE, width=10.0)
    near = view.project(Vec3(0.0, -0.5, 0.0)).depth
    far = view.project(Vec3(0.0, 0.5, 0.0)).depth
    assert near < far


def test_top_view_flattens_z_not_x():
    view = Camera.named("top").frame(CUBE, width=10.0)
    flat = view.project(Vec3(0, 0, 0.5)).point
    assert flat.x == pytest.approx(0.0, abs=1e-9)
    assert flat.y == pytest.approx(0.0, abs=1e-9)


# -- presets --------------------------------------------------------------


def test_isometric_projects_a_cube_to_a_regular_hexagon():
    # The defining property of a *true* isometric: all three axes foreshorten
    # equally, so the six silhouette corners lie on one circle. Get the
    # elevation wrong by a degree and this is the test that notices.
    view = Camera.named("isometric").frame(CUBE, width=10.0)
    corners = [view.project(v).point for v in CUBE.vertices]
    radii = sorted(math.hypot(p.x, p.y) for p in corners)
    assert radii[-1] == pytest.approx(radii[2], rel=1e-9)   # six outer, two inner


def test_every_preset_frames_every_solid():
    for name in preset_names():
        for mesh in (CUBE, sphere(), box(2.0, 0.3, 1.0)):
            view = Camera.named(name).frame(mesh, width=20.0)
            assert view.scale > 0.0, name


def test_preset_names_are_sorted_and_include_the_documented_six():
    assert preset_names() == tuple(sorted(preset_names()))
    assert {"isometric", "dimetric", "front", "top", "right",
            "three-quarter"} <= set(preset_names())


def test_an_unknown_preset_lists_the_known_ones():
    with pytest.raises(MeshError, match="isometric"):
        Camera.named("obligue")


def test_as_camera_accepts_a_name_a_pair_or_a_camera():
    assert as_camera("top").elevation == 90.0
    assert as_camera((30.0, 12.0)).azimuth == 30.0
    same = Camera(1.0, 2.0)
    assert as_camera(same) is same
    assert as_camera(None) == PRESETS["three-quarter"]


# -- auto-fit -------------------------------------------------------------


@pytest.mark.parametrize("width", [4.0, 20.0, 137.5])
def test_fitting_a_width_produces_exactly_that_width(width):
    view = Camera.named("three-quarter").frame(CUBE, width=width)
    assert view.raw_bounds(CUBE).width * view.scale == pytest.approx(width, rel=1e-12)


def test_fitting_a_height_produces_exactly_that_height():
    view = Camera.named("dimetric").frame(box(3.0, 1.0, 1.0), height=9.0)
    mesh = box(3.0, 1.0, 1.0)
    assert view.raw_bounds(mesh).height * view.scale == pytest.approx(9.0, rel=1e-12)


def test_giving_both_fits_inside_the_box_and_keeps_the_aspect():
    mesh = box(4.0, 1.0, 1.0)
    view = Camera.named("front").frame(mesh, width=40.0, height=4.0)
    fitted = view.raw_bounds(mesh)
    assert fitted.width * view.scale <= 40.0 + 1e-9
    assert fitted.height * view.scale <= 4.0 + 1e-9
    # The tight constraint has to be the one that binds exactly.
    assert min(40.0 - fitted.width * view.scale,
               4.0 - fitted.height * view.scale) == pytest.approx(0.0, abs=1e-9)


def test_the_fit_centres_the_projected_ink_not_the_model():
    # A model whose geometry sits off to one side must still come out balanced
    # about the node's own origin, or it will not stack like every other
    # primitive in inklet.
    from inklet.three import Mat4

    lopsided = CUBE.merged(CUBE.transformed(Mat4.translation(Vec3(5, 0, 0))))
    view = Camera.named("front").frame(lopsided, width=10.0)
    drawn = view.raw_bounds(lopsided)
    points = [view.project(v).point for v in lopsided.vertices]
    assert (min(p.x for p in points) + max(p.x for p in points)) == pytest.approx(0.0, abs=1e-9)
    assert (min(p.y for p in points) + max(p.y for p in points)) == pytest.approx(0.0, abs=1e-9)
    assert drawn.width > 0.0


def test_a_degenerate_view_says_to_rotate_rather_than_dividing_by_zero():
    from inklet.three import Mesh

    edge_on = Mesh((Vec3(-1, 0, 0), Vec3(1, 0, 0), Vec3(0, 0, 0)), ((0, 1, 2),))
    with pytest.raises(MeshError, match="rotate the camera"):
        Camera.named("front").frame(edge_on, height=5.0)


def test_framing_an_empty_mesh_is_an_error():
    from inklet.three import Mesh

    with pytest.raises(MeshError, match="empty"):
        Camera.named("front").frame(Mesh((), ()), width=5.0)


# -- perspective ----------------------------------------------------------


def test_perspective_makes_the_far_face_smaller():
    view = Camera(0.0, 0.0, perspective=True, fov=40.0).frame(CUBE, width=20.0)
    near = view.project(Vec3(0.5, -0.5, 0.0)).point.x
    far = view.project(Vec3(0.5, 0.5, 0.0)).point.x
    assert far < near


def test_orthographic_keeps_the_far_face_the_same_size():
    view = Camera.named("front").frame(CUBE, width=20.0)
    assert view.project(Vec3(0.5, -0.5, 0)).point.x == pytest.approx(
        view.project(Vec3(0.5, 0.5, 0)).point.x)


def test_orthographic_facing_uses_the_view_direction_not_the_eye():
    # Under orthographic every surface point must see the eye in the same
    # direction, or a wide flat panel silhouettes against itself at the edges.
    view = Camera.named("front").frame(CUBE, width=20.0)
    assert view.to_eye(Vec3(100, 0, 0)) == view.to_eye(Vec3(-100, 0, 0))


def test_a_vertex_behind_the_lens_is_clamped_rather_than_raising():
    view = Camera(0.0, 0.0, perspective=True).frame(CUBE, width=20.0)
    behind = view.project(view.eye + view.forward * -1.0).point
    assert math.isfinite(behind.x) and math.isfinite(behind.y)


# -- look_at and roll -----------------------------------------------------


def test_look_at_points_the_camera_at_the_target():
    view = Camera.look_at(Vec3(0, -4, 0), Vec3()).frame(CUBE, width=10.0)
    assert view.forward.y == pytest.approx(1.0)


def test_an_up_parallel_to_the_view_says_so():
    with pytest.raises(MeshError, match="up"):
        Camera.look_at(Vec3(0, 0, 4), Vec3(), up=Vec3(0, 0, 1)).frame(CUBE, width=5.0)


def test_roll_turns_the_page_not_the_model():
    upright = Camera.named("front").frame(CUBE, width=10.0)
    rolled = Camera(0.0, 0.0, roll=90.0).frame(CUBE, width=10.0)
    top = Vec3(0, 0, 0.5)
    assert upright.project(top).point.y == pytest.approx(-upright.scale * 0.5)
    assert abs(rolled.project(top).point.x) == pytest.approx(rolled.scale * 0.5)


def test_turned_offsets_the_angles():
    assert Camera.named("front").turned(azimuth=30.0).azimuth == 30.0
