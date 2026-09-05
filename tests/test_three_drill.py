"""Holes that survive being looked at from the other side.

A hole drawn as a disc on the front face is a lie the moment the camera moves:
there is nothing inside it, so the far wall of the solid shows through, and
hidden-line removal has no wall to hide anything behind. `Mesh.drill` cuts the
geometry instead, and the property that makes that worth having is that the
result is still **closed** -- every edge shared by exactly two faces. A cut
that leaves a T-junction looks perfect and breaks every stage downstream, so
most of what is asserted here is arity of the edge table rather than pictures.
"""

from __future__ import annotations

import math
from collections import Counter

import pytest

from inklet.three import Mat4, Mesh, MeshError, Vec3, build
from inklet.three.drill import DEFAULT_HOLE_SEGMENTS, drill


def _plate(width: float = 4.0, thickness: float = 0.6) -> Mesh:
    return build("box", size_x=width, size_y=width, size_z=thickness)


def _arity(mesh: Mesh) -> Counter:
    """How many faces meet along each edge. A closed mesh answers `{2: n}`."""
    return Counter(len(v) for v in mesh.edge_faces.values())


# -- the property that matters --------------------------------------------


def test_a_drilled_box_is_still_closed():
    out = _plate().drill("z", radius=0.5)
    assert out.is_closed
    assert _arity(out) == Counter({2: len(out.edge_faces)})


def test_drilling_removes_no_border_vertices_from_the_faces_it_cuts():
    # The cut re-triangulates a whole flat face around the hole, and the only
    # reason it can stay watertight is that ear clipping adds no points on the
    # border. If the border ever gained one, the untouched side walls would
    # not share it and the mesh would come apart along a seam that is
    # invisible in every render.
    plate = _plate()
    corners = set(plate.vertices)
    out = plate.drill("z", radius=0.5)
    assert corners <= set(out.vertices)


def test_four_holes_in_one_plate_are_each_closed():
    # Four is the case that first broke: a bridge into the fourth hole has to
    # be routed past the three already cut into the same face.
    mesh = _plate(width=6.0)
    for x, y in ((-2, -2), (2, -2), (2, 2), (-2, 2)):
        mesh = mesh.drill("z", radius=0.5, at=(x, y, 0))
        assert mesh.is_closed
    assert len(mesh.vertices) == len({v.as_tuple() for v in mesh.vertices})


def test_a_hole_through_a_cylinder_end_to_end_is_closed():
    tube = build("cylinder", radius=1.0, height=3.0, segments=24)
    out = tube.drill("z", radius=0.35)
    assert out.is_closed


def test_a_hole_across_the_stack_is_closed():
    # Drilling along -x rather than z: the frame has to stay right-handed, or
    # the ring comes out wound the wrong way and the walls face inwards.
    out = _plate().drill("-x", radius=0.15)
    assert out.is_closed


def test_the_hole_is_actually_open():
    # The centre of the hole must have no surface in it. Cast a ray down the
    # axis and count crossings of the projected faces: zero, where the solid
    # itself gives two.
    # Off the exact centre, because the box's own faces are split on a
    # diagonal that runs through it and a ray along it counts both halves.
    plate = _plate()
    assert _crossings(plate, 0.11, 0.07) == 2
    assert _crossings(plate.drill("z", radius=0.5), 0.11, 0.07) == 0


def _crossings(mesh: Mesh, x: float, y: float) -> int:
    hits = 0
    for a, b, c in mesh.faces:
        p, q, r = mesh.vertices[a], mesh.vertices[b], mesh.vertices[c]
        area = (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)
        if abs(area) < 1e-12:
            continue
        u = ((x - p.x) * (r.y - p.y) - (y - p.y) * (r.x - p.x)) / area
        v = ((q.x - p.x) * (y - p.y) - (q.y - p.y) * (x - p.x)) / area
        if u >= 0.0 and v >= 0.0 and u + v <= 1.0:
            hits += 1
    return hits


def test_the_inner_wall_faces_into_the_hole():
    # Every wall facet's normal must point back at the axis. Get this wrong and
    # the hole shades as a boss standing proud of the plate.
    out = _plate().drill("z", radius=0.5, group="bore")
    walls = [i for i, g in enumerate(out.groups) if g == "bore"]
    assert walls
    for i in walls:
        centroid, normal = out.face_centroids[i], out.face_normals[i]
        outward = Vec3(centroid.x, centroid.y, 0.0).normalized()
        assert normal.dot(outward) < 1e-9


def test_the_wall_faces_the_same_way_when_the_axis_is_reversed():
    forward = _plate().drill("z", radius=0.5, group="bore")
    backward = _plate().drill("-z", radius=0.5, group="bore")
    assert len(forward.faces) == len(backward.faces)
    for out in (forward, backward):
        for i, g in enumerate(out.groups):
            if g != "bore":
                continue
            c = out.face_centroids[i]
            assert out.face_normals[i].dot(
                Vec3(c.x, c.y, 0.0).normalized()) < 1e-9


# -- what the hole is made of ---------------------------------------------


def test_the_wall_has_two_triangles_per_side():
    out = _plate().drill("z", radius=0.5, segments=8, group="bore")
    assert sum(1 for g in out.groups if g == "bore") == 16


def test_the_default_segment_count_is_the_documented_one():
    out = _plate().drill("z", radius=0.5, group="bore")
    assert sum(1 for g in out.groups if g == "bore") == 2 * DEFAULT_HOLE_SEGMENTS


def test_the_hole_has_the_radius_it_was_given():
    out = _plate().drill("z", radius=0.5, group="bore")
    rim = {out.vertices[i] for f, g in zip(out.faces, out.groups)
           if g == "bore" for i in f}
    for p in rim:
        assert math.hypot(p.x, p.y) == pytest.approx(0.5, abs=1e-9)


def test_an_unnamed_hole_keeps_the_groups_the_mesh_already_had():
    plate = _plate().grouped("plate")
    out = plate.drill("z", radius=0.5)
    assert set(out.groups) == {"plate"}


def test_the_hole_lands_where_it_was_put():
    out = _plate(width=6.0).drill("z", radius=0.4, at=(1.5, -1.0, 0), group="bore")
    rim = [out.vertices[i] for f, g in zip(out.faces, out.groups)
           if g == "bore" for i in f]
    assert min(p.x for p in rim) == pytest.approx(1.1, abs=1e-9)
    assert max(p.y for p in rim) == pytest.approx(-0.6, abs=1e-9)


def test_drilling_does_not_move_the_solid():
    plate = _plate()
    out = plate.drill("z", radius=0.5)
    assert out.bounds[0] == plate.bounds[0]
    assert out.bounds[1] == plate.bounds[1]


def test_drilling_is_deterministic():
    first = _plate().drill("z", radius=0.5, at=(0.3, 0.2, 0))
    again = _plate().drill("z", radius=0.5, at=(0.3, 0.2, 0))
    assert first.vertices == again.vertices
    assert first.faces == again.faces


def test_a_drilled_plate_can_be_moved_like_any_other_mesh():
    out = _plate().drill("z", radius=0.5).transformed(
        Mat4.translation(Vec3(10.0, 0.0, 0.0)))
    assert out.is_closed
    assert out.center.x == pytest.approx(10.0)


# -- what it refuses ------------------------------------------------------


def test_a_hole_needs_a_positive_radius():
    with pytest.raises(MeshError, match="positive radius"):
        _plate().drill("z", radius=0.0)


def test_a_hole_needs_three_sides():
    with pytest.raises(MeshError, match="three sides"):
        _plate().drill("z", radius=0.4, segments=2)


def test_a_hole_that_misses_the_solid_says_so():
    with pytest.raises(MeshError, match="one side and out another"):
        _plate().drill("z", radius=0.3, at=(20.0, 0.0, 0.0))


def test_a_hole_hanging_off_the_edge_says_so():
    with pytest.raises(MeshError, match="reaches an edge|touch its edge|does not pass cleanly"):
        _plate().drill("z", radius=0.3, at=(2.0, 0.0, 0.0))


def test_two_holes_may_not_overlap():
    plate = _plate().drill("z", radius=0.5, at=(-0.4, 0, 0))
    with pytest.raises(MeshError):
        plate.drill("z", radius=0.5, at=(0.4, 0, 0))


def test_a_hole_through_a_curved_wall_comes_out_watertight():
    # Sideways through a cylinder: the hole leaves through the barrel, which is
    # a fan of facets rather than one flat face, so it is cut a facet at a time
    # and the pieces welded. Watertight is the whole test -- a strip cut that
    # misses a crossing leaves an edge with one face on it.
    barrel = build("cylinder", radius=1.0, height=3.0, segments=24)
    out = barrel.drill("x", radius=0.3, segments=20)
    assert out.is_closed
    assert all(len(faces) == 2 for faces in out.edge_faces.values())
    assert len(out.faces) > len(barrel.faces)


def test_a_hole_through_a_sphere_comes_out_watertight():
    # The icosphere has a vertex at the pole, and the drill's first rim corner
    # lands exactly on one of the edges radiating from it: the degenerate case
    # the clip has to see rather than round away.
    ball = build("sphere", radius=1.0, subdivisions=3)
    out = ball.drill("z", radius=0.25, segments=20)
    assert out.is_closed
    assert all(len(faces) == 2 for faces in out.edge_faces.values())


@pytest.mark.parametrize("axis", ["x", "y", (1.0, 1.0, 0.0), (0.3, 1.0, 0.2)])
@pytest.mark.parametrize("radius", [0.1, 0.25])
def test_curved_cuts_stay_watertight_over_axes_and_radii(axis, radius):
    barrel = build("cylinder", radius=0.9, height=2.2, segments=32)
    assert barrel.drill(axis, radius=radius, segments=16).is_closed


def test_a_curved_cut_names_its_wall_as_a_group():
    barrel = build("cylinder", radius=1.0, height=3.0, segments=24)
    out = barrel.drill("x", radius=0.3, segments=20, group="port")
    assert "port" in set(out.groups)
    assert out.is_closed


def test_a_hole_that_runs_off_a_curved_surface_is_refused():
    # A bore wider than the cone is deep at that height breaks out of the tip
    # rather than coming out the other side.
    cone = build("cone", radius=0.4, height=1.0, segments=24)
    with pytest.raises(MeshError):
        cone.drill("x", radius=0.16, at=(0.0, 0.05, -0.07), segments=20)


def test_a_tube_is_watertight_and_has_an_annular_end():
    pipe = build("tube", radius=0.5, bore=0.3, height=1.2, segments=24)
    assert pipe.is_closed
    assert all(len(faces) == 2 for faces in pipe.edge_faces.values())
    # Two barrels and two flat ends, all with 24 quads: nothing fanned.
    assert len(pipe.faces) == 4 * 24 * 2
    with pytest.raises(MeshError, match="inside its wall"):
        build("tube", radius=0.3, bore=0.4)


def test_a_tube_with_no_caps_is_open_at_both_ends():
    assert not build("tube", caps=False).is_closed


def test_an_empty_mesh_cannot_be_drilled():
    with pytest.raises(MeshError, match="nothing to drill"):
        Mesh((), ()).drill("z", radius=0.4)


def test_the_module_function_and_the_method_agree():
    assert drill(_plate(), "z", radius=0.5).faces == \
        _plate().drill("z", radius=0.5).faces
