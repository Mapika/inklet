"""Mesh algebra and the little linear algebra under it.

These tests assert equalities, not tolerances, wherever the answer is exact --
a unit cube's bounds, a reversed winding, an edge table's arity. The 3D
pipeline is a stack of sign tests near zero, and the only way to keep the
later stages honest is for the earliest one to be provably right.
"""

from __future__ import annotations

import math

import pytest

from inklet.three import Mat4, Mesh, MeshError, Vec3, build, merge, solid_names
from inklet.three.solids import (
    _ICO_DEVIATION, box, cube, cylinder, segments_for, sphere,
    subdivisions_for, tessellation, torus,
)


# -- linalg ---------------------------------------------------------------


def test_cross_product_is_right_handed():
    assert Vec3(1, 0, 0).cross(Vec3(0, 1, 0)) == Vec3(0, 0, 1)


def test_rotation_is_exact_on_the_quarter_turn():
    turned = Mat4.rotation(Vec3(0, 0, 1), 90.0).apply(Vec3(1, 0, 0))
    assert turned.x == pytest.approx(0.0, abs=1e-15)
    assert turned.y == pytest.approx(1.0, abs=1e-15)


def test_matmul_applies_self_after_other():
    # Same convention as core.geom.Affine: (a @ b)(p) == a(b(p)). Getting this
    # backwards is invisible on symmetric test shapes and wrong on everything.
    shift = Mat4.translation(Vec3(1.0, 0.0, 0.0))
    spin = Mat4.rotation(Vec3(0, 0, 1), 90.0)
    assert (spin @ shift).apply(Vec3()).y == pytest.approx(1.0)
    assert (shift @ spin).apply(Vec3()).x == pytest.approx(1.0)


def test_vector_transform_ignores_translation():
    assert Mat4.translation(Vec3(5, 5, 5)).apply_vector(Vec3(1, 0, 0)) == Vec3(1, 0, 0)


# -- construction and validation ------------------------------------------


def test_quads_are_refused_by_name():
    with pytest.raises(MeshError, match="triangles"):
        Mesh((Vec3(), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(1, 1, 0)),
             ((0, 1, 2, 3),))


def test_out_of_range_index_names_the_face_and_the_count():
    with pytest.raises(MeshError, match="face 0 refers to vertex 9"):
        Mesh((Vec3(), Vec3(1, 0, 0), Vec3(0, 1, 0)), ((0, 1, 9),))


def test_partial_group_names_are_refused():
    with pytest.raises(MeshError, match="one per face"):
        Mesh((Vec3(), Vec3(1, 0, 0), Vec3(0, 1, 0)), ((0, 1, 2),), groups=("a", "b"))


# -- derived tables -------------------------------------------------------


def test_unit_cube_bounds_and_size():
    lo, hi = cube(1.0).bounds
    assert (lo.x, lo.y, lo.z) == (-0.5, -0.5, -0.5)
    assert (hi.x, hi.y, hi.z) == (0.5, 0.5, 0.5)
    assert cube(1.0).size == Vec3(1.0, 1.0, 1.0)


def test_cube_edge_table_is_a_closed_manifold():
    table = cube(1.0).edge_faces
    # 12 cube edges plus one triangulation diagonal per face.
    assert len(table) == 18
    assert all(len(faces) == 2 for faces in table.values())
    assert cube(1.0).is_closed


def test_open_surface_reports_boundary_edges():
    from inklet.three.solids import plane

    sheet = plane(1.0, 1.0, segments=2)
    assert not sheet.is_closed
    assert sum(1 for faces in sheet.edge_faces.values() if len(faces) == 1) == 8


def test_face_normals_point_outward_on_a_closed_solid():
    solid = cube(1.0)
    for centroid, normal in zip(solid.face_centroids, solid.face_normals):
        # Outward means the normal agrees with the direction from the centre.
        assert centroid.dot(normal) > 0.0


def test_degenerate_face_gets_the_zero_normal():
    flat = Mesh((Vec3(), Vec3(1, 0, 0), Vec3(2, 0, 0)), ((0, 1, 2),))
    assert flat.face_normals[0] == Vec3()


def test_derived_tables_are_cached_not_recomputed():
    solid = cube(1.0)
    assert solid.face_normals is solid.face_normals


# -- transforms -----------------------------------------------------------


def test_mirroring_reverses_winding_so_normals_stay_outward():
    # A negative determinant turns every face inside out. `transformed` has to
    # flip the winding back, or a mirrored model shades and silhouettes as if
    # its surface faced inward.
    mirrored = cube(1.0).transformed(Mat4.scaling(-1.0, 1.0, 1.0))
    for centroid, normal in zip(mirrored.face_centroids, mirrored.face_normals):
        assert centroid.dot(normal) > 0.0


def test_scaled_to_fit_puts_the_longest_side_on_the_target():
    fitted = box(2.0, 1.0, 0.5).scaled_to_fit(3.0)
    assert max(fitted.size.as_tuple()) == pytest.approx(3.0)


def test_centered_moves_the_bounding_box_centre_to_the_origin():
    moved = cube(1.0).transformed(Mat4.translation(Vec3(10.0, -4.0, 7.0))).centered()
    assert moved.center.length == pytest.approx(0.0, abs=1e-12)


def test_merge_offsets_indices_and_keeps_both_shapes():
    a, b = cube(1.0), cube(1.0).transformed(Mat4.translation(Vec3(3, 0, 0)))
    both = merge([a.grouped("left"), b.grouped("right")])
    assert len(both.faces) == len(a.faces) + len(b.faces)
    assert both.group_names == ("left", "right")
    assert both.group_center("right").x == pytest.approx(3.0)
    assert max(i for face in both.faces for i in face) == len(both.vertices) - 1


def test_merge_of_nothing_is_empty_not_an_error():
    assert merge([]).is_empty


# -- coplanar patches -----------------------------------------------------


def test_coplanar_patches_reunite_a_triangulated_quad():
    # The two triangles of one cube face must come back as a single patch, or
    # the shader paints a seam down every flat surface.
    solid = cube(1.0)
    patches = solid.coplanar_patches(range(len(solid.faces)))
    assert len(patches) == 6
    assert sorted(len(p) for p in patches) == [2] * 6


def test_curved_surfaces_do_not_get_merged():
    ball = sphere(0.5, subdivisions=1)
    patches = ball.coplanar_patches(range(len(ball.faces)))
    assert len(patches) == len(ball.faces)


# -- the parametric catalogue ---------------------------------------------


def test_every_named_solid_builds_and_is_non_degenerate():
    for name in solid_names():
        mesh = build(name)
        assert mesh.faces, name
        assert mesh.radius > 0.0, name
        assert all(n != Vec3() for n in mesh.face_normals), name


def test_closed_solids_are_closed_and_open_ones_are_not():
    assert cube(1.0).is_closed
    assert sphere().is_closed
    assert cylinder().is_closed
    assert torus().is_closed
    assert not build("plane").is_closed


def test_icosphere_subdivision_quadruples_the_face_count():
    assert len(sphere(0.5, 0).faces) == 20
    assert len(sphere(0.5, 2).faces) == 320


def test_icosphere_vertices_all_sit_on_the_sphere():
    for v in sphere(0.7, 2).vertices:
        assert v.length == pytest.approx(0.7, abs=1e-12)


def test_unknown_solid_lists_the_known_ones():
    with pytest.raises(MeshError, match="cylinder"):
        build("dodecahedron")


def test_axes_arrows_are_grouped_by_letter():
    assert set(build("axes").group_names) >= {"x", "y", "z"}


def test_arrow_runs_from_the_origin_along_z():
    tip = build("arrow", length=2.0).bounds[1]
    assert tip.z == pytest.approx(2.0)
    assert build("arrow", length=2.0).bounds[0].z == pytest.approx(0.0)


def test_torus_hole_survives_as_a_genus_one_closed_surface():
    ring = torus()
    # Euler characteristic 0 is what makes it a torus rather than a sphere; a
    # ring built by an off-by-one in the wrap would come out as a cylinder.
    v, f = len(ring.vertices), len(ring.faces)
    e = len(ring.edge_faces)
    assert v - e + f == 0
    # The tube's own polygon has 14 sides, so its extreme misses the true
    # tube radius by the sagitta of one side -- close, never equal.
    assert ring.size.z == pytest.approx(2 * 0.14, rel=0.03)


# -- choosing a tessellation from the page --------------------------------


def _sagitta(n: int, radius: float) -> float:
    """How far an inscribed n-gon's chord sits inside the circle it samples."""
    return radius * (1.0 - math.cos(math.pi / n))


@pytest.mark.parametrize("radius", [0.4, 3.0, 12.0, 80.0])
@pytest.mark.parametrize("tolerance", [0.02, 0.06, 0.2])
def test_the_chosen_segment_count_is_the_smallest_one_that_fits(radius,
                                                                tolerance):
    n = segments_for(radius, tolerance, floor=3)
    assert _sagitta(n, radius) <= tolerance
    # Minimal, not merely sufficient: one fewer must overshoot, or the rule is
    # buying smoothness nobody asked for and paying for it in every facet.
    assert _sagitta(n - 1, radius) > tolerance


def test_a_curve_inside_the_tolerance_still_gets_a_polygon_not_a_triangle():
    # A 0.2 mm bead is under tolerance whole, but `style="shaded"` gives every
    # facet its own flat tone, so too few of them reads as a prism.
    assert segments_for(0.1, 0.06) == 8
    assert segments_for(0.1, 0.06, floor=3) == 3


def test_a_degenerate_radius_asks_for_the_ceiling_rather_than_dividing_by_it():
    assert segments_for(0.0, 0.06) == 256
    assert segments_for(1.0, 0.0) == 256


def test_the_icosphere_table_matches_meshes_built_now():
    """The table is measured, so it has to keep agreeing with the measurement."""
    for level, recorded in enumerate(_ICO_DEVIATION[:5]):
        ball = sphere(1.0, level)
        worst = max(
            1.0 - ((ball.vertices[a] + ball.vertices[b] + ball.vertices[c])
                   * (1.0 / 3.0)).length
            for a, b, c in ball.faces)
        assert worst == pytest.approx(recorded, rel=1e-3)


@pytest.mark.parametrize("radius", [2.0, 12.0, 60.0])
def test_the_chosen_subdivision_is_the_smallest_level_that_fits(radius):
    level = subdivisions_for(radius, 0.06)
    assert _ICO_DEVIATION[level] * radius <= 0.06
    if level:
        assert _ICO_DEVIATION[level - 1] * radius > 0.06


def test_tessellation_leaves_alone_whatever_the_author_stated():
    # 6 is far too coarse for 25 mm per unit and that is the author's business.
    assert tessellation("cylinder", {"segments": 6}, 25.0) == {}
    assert tessellation("torus", {"segments": 6}, 25.0) == {"rings": 17}


def test_a_shape_with_no_curve_in_it_is_left_entirely_alone():
    assert tessellation("box", {}, 25.0) == {}
    assert tessellation("plane", {}, 25.0) == {}
    assert tessellation("nothing-like-it", {}, 25.0) == {}


def test_tessellation_reads_the_builders_own_defaults():
    """`_ROUNDNESS` names arguments; the values come from the signature, so a
    default that moves does not leave a stale copy behind here."""
    wide = tessellation("cylinder", {"radius": 4.0}, 25.0)["segments"]
    narrow = tessellation("cylinder", {"radius": 0.05}, 25.0)["segments"]
    assert wide > tessellation("cylinder", {}, 25.0)["segments"] > narrow


# -- the smooth surface behind the facets ---------------------------------


def test_a_spheres_vertex_normals_converge_on_the_radius():
    """The one mesh with a known answer everywhere: on a unit sphere the
    surface normal at a point *is* the point.

    Asserting convergence rather than a threshold, because a threshold would
    also be met by a normal that is merely *close* -- an average of face
    normals with any sane weighting is close. What separates an estimate of the
    surface from a plausible-looking blend is that refining the mesh makes it
    better, and this one halves its error at every subdivision.
    """
    def worst(level):
        ball = sphere(radius=1.0, subdivisions=level)
        return max((vertex - normal).length
                   for vertex, normal in zip(ball.vertices, ball.vertex_normals))

    errors = [worst(level) for level in (2, 3, 4)]
    assert errors[0] < 0.01
    for coarse, fine in zip(errors, errors[1:]):
        assert fine < coarse / 2.0


def test_a_cube_corner_normal_points_down_the_body_diagonal():
    """Not a smoothing group: every face that meets at the corner is averaged
    in, folds included. That is what makes the answer useless *at* a fold, and
    it is why anything drawing with these has to gate on the dihedral rather
    than trust them blind."""
    corner = cube(2.0).vertices.index(Vec3(1.0, 1.0, 1.0))
    normal = cube(2.0).vertex_normals[corner]
    third = 1.0 / math.sqrt(3.0)
    assert normal.x == pytest.approx(third)
    assert normal.y == pytest.approx(third)
    assert normal.z == pytest.approx(third)


def test_vertex_normals_are_weighted_by_angle_not_by_triangle_count():
    """A square split into two triangles has one vertex touched by both and two
    touched by one each, so an unweighted average is a vote on how the square
    was cut. Cutting the same square the other way has to give the same
    normals, and only the angle weighting does."""
    corners = (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(1, 1, 0), Vec3(0, 1, 0))
    one = Mesh(corners, ((0, 1, 2), (0, 2, 3)))
    other = Mesh(corners, ((0, 1, 3), (1, 2, 3)))
    assert one.vertex_normals == other.vertex_normals


def test_a_degenerate_face_does_not_tip_the_normals_around_it():
    """A zero-area triangle has no normal, so it must contribute nothing rather
    than contribute `Vec3()` and drag the average toward the origin."""
    corners = (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(2, 0, 0))
    with_sliver = Mesh(corners, ((0, 1, 2), (0, 1, 3)))
    assert with_sliver.vertex_normals[0] == Vec3(0.0, 0.0, 1.0)


def test_vertex_normals_are_cached_like_the_rest():
    ball = sphere(subdivisions=1)
    assert ball.vertex_normals is ball.vertex_normals
