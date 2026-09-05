"""Coplanar patches that are not convex, and the four things that broke on them.

A run of triangles in one plane is merged into a single outline before the
painter's order runs, which is what keeps a flat cut face from showing its own
triangulation. When the merged outline comes out *concave* -- an L, or the
midsagittal section of a brain -- the pairwise test cannot be trusted on it,
because that test clips one outline against the other and a clip is only the
intersection when both are convex. The engine's answer is to hand the patch
back to its own triangles, and the way it used to do that is the subject of
most of this file: it reused the machinery for holes, which takes a ring *out*
of the sort and rides it next to another ring at that other ring's depth. On
the Allen brain that put 214 of a 215-triangle cap at one depth and painted a
nucleus standing a millimetre proud of the cut clean out of the picture.

The rest of the file covers the three smaller faults found beside it: a fold
angle that could not differ between parts of a fused scene, and `inklet.solid`
reporting a `Mesh` as a string with no `strip`.
"""

from __future__ import annotations

import math
import re

import pytest

import inklet
from inklet.three.camera import Camera
from inklet.three.edges import feature_edges, facing_faces
from inklet.three.linalg import Vec3
from inklet.three.mesh import Mesh, merge
from inklet.three.order import overlaps
from inklet.three.place import placement
from inklet.three.shade import sorted_facets
from inklet.three.solids import box, build


# -- the scene ---------------------------------------------------------------
#
# An L-shaped wall in the x = 0 plane, fanned from one corner, with a small cube
# standing in front of the far arm of the L. The fan's widest triangle is the
# *near* one, so under the old rider path the whole wall painted at the near
# depth and swallowed the cube. Both details matter: a fan from an arbitrary
# corner of a concave ring winds inconsistently and never merges into one patch
# at all, and a fan whose widest triangle is the far one paints the wall first
# and hides the fault.

_L_RING = ((-2.0, -2.0), (2.0, -2.0), (2.0, 0.0),
           (0.0, 0.0), (0.0, 3.0), (-2.0, 3.0))


def _wall() -> Mesh:
    corners = tuple(Vec3(0.0, y, z) for y, z in _L_RING)
    fan = tuple((0, i, i + 1) for i in range(1, len(_L_RING) - 1))
    return Mesh(vertices=corners, faces=fan).grouped("wall")


def _wall_and_stud() -> Mesh:
    stud = box(0.5, 0.5, 0.5).transformed(placement(at=(0.5, 1.0, -1.0)))
    return merge([_wall(), stud.grouped("stud")])


def _sorted(mesh: Mesh, **kwargs):
    view = Camera.named("three-quarter").frame(mesh, width=40.0)
    points, depths = view.project_all(mesh.vertices)
    facing = facing_faces(mesh, view)
    return sorted_facets(mesh, view, points, depths, facing, **kwargs)


def _flat(facet) -> tuple[tuple[float, float], ...]:
    return tuple((p.x, p.y) for p in facet.points)


# -- a concave patch goes back to its triangles, and they all go to the sort --


def test_a_concave_patch_keeps_all_its_triangles_in_the_exact_sort():
    """No rider survives the split: a tiling has no outer ring to ride on.

    The four fan triangles cover between them exactly what the merged L
    covered, so they are siblings, not a face and its holes, and every one of
    them is ranked on its own.
    """
    facets = _sorted(_wall(), sort="exact", cull=False)
    wall = [f for f in facets if f.group == "wall"]
    assert len(wall) == 4
    assert all(f.patch == -1 for f in wall), "a split patch must leave no riders"


def test_split_triangles_key_on_their_own_depth():
    """The whole point: four triangles at four distances, four ranks."""
    wall = [f for f in _sorted(_wall(), sort="exact", cull=False)
            if f.group == "wall"]
    assert len({round(f.depth, 6) for f in wall}) == 4


def test_split_triangles_take_their_own_depth_cue():
    """Fading follows depth, so one depth for the patch was one flat tone.

    The visible symptom on the mouse figure was a cut face with no recession
    across it at all.
    """
    wall = [f for f in _sorted(_wall(), sort="exact", cull=False, depth_cue=0.4)
            if f.group == "wall"]
    assert len({f.cue for f in wall}) > 1


def test_a_concave_patch_no_longer_paints_over_what_stands_in_front_of_it():
    """The regression proper, and the shape of the mouse-brain bug.

    Before the split, all four wall triangles carried the depth of the widest
    one -- the near arm -- so the far arm painted after the cube in front of
    it. Six wall-over-stud pairs came out backwards; now none do.
    """
    facets = _sorted(_wall_and_stud(), sort="exact", cull=False)
    backwards = [
        (i, j)
        for i, f in enumerate(facets) if f.group == "wall"
        for j, g in enumerate(facets[:i]) if g.group == "stud"
        and overlaps(_flat(f), _flat(g))
    ]
    assert backwards == []


def test_a_patch_with_a_real_hole_still_rides_beside_its_face():
    """The split must not cost the hole path, which a drilled plate needs.

    A bore's ring is *inside* the face it perforates, not a sibling of it, and
    it has to be re-inserted next to that face after the sort has moved it.
    """
    plate = build("box", size_x=4.0, size_y=3.0, size_z=0.4)
    plate = plate.drill("z", radius=0.3, at=(0.0, 0.0, 0.0), group="hole")
    facets = _sorted(plate, sort="exact")
    assert any(f.patch >= 0 for f in facets), "the bore must still be a rider"


def test_the_depth_sort_leaves_concave_patches_merged():
    """Splitting is the exact sort's price for a test it can trust.

    The mean-depth order never clips one facet against another, so it has no
    reason to pay, and a merged L is one path instead of four.
    """
    wall = [f for f in _sorted(_wall(), sort="depth", cull=False)
            if f.group == "wall"]
    assert len(wall) == 1


# -- one fold angle per part -------------------------------------------------


def _brain_and_bead():
    """A coarse sphere with a smooth surface, and a cube that wants its edges."""
    ball = build("sphere", radius=1.0, subdivisions=2)
    bead = build("box", size_x=0.4, size_y=0.4, size_z=0.4)
    return ball, bead


def test_a_fused_scene_takes_a_fold_angle_per_part():
    """`crease` is per-part in `scene` for the same reason `color` is.

    A shell wants a high threshold so its tessellation stays quiet; a boxy
    part inside it wants a low one so its corners are drawn. Fusing them into
    one mesh used to force one answer on both.
    """
    ball, bead = _brain_and_bead()
    bead = bead.transformed(placement(at=(0.0, 0.0, 2.0)))
    loose = inklet.scene([("shell", ball, {"crease": 120.0}),
                       ("bead", bead, {"crease": 120.0})],
                      order="exact", width=40.0)
    mixed = inklet.scene([("shell", ball, {"crease": 120.0}),
                       ("bead", bead, {"crease": 20.0})],
                      order="exact", width=40.0)
    assert _paths(loose) != _paths(mixed), "the bead's corners must appear"


def test_a_part_without_its_own_angle_takes_the_shared_one():
    ball, bead = _brain_and_bead()
    bead = bead.transformed(placement(at=(0.0, 0.0, 2.0)))
    named = inklet.scene([("shell", ball, {"crease": 20.0}),
                       ("bead", bead, {"crease": 20.0})],
                      order="exact", width=40.0, crease=20.0)
    shared = inklet.scene([("shell", ball), ("bead", bead)],
                       order="exact", width=40.0, crease=20.0)
    assert _paths(named) == _paths(shared)


def _paths(node) -> list[str]:
    fig = inklet.figure(width=120.0)
    fig.add(node)
    return re.findall(r' d="([^"]+)"', fig.to_svg())


# -- the per-face angle underneath it ----------------------------------------


def test_feature_edges_takes_one_angle_per_face():
    """The stricter of the two faces decides a shared edge.

    An edge between a part that wants its folds and one that does not is the
    boundary between them, and the part that asked to see its folds is the one
    that gets an answer.
    """
    cube = build("box")
    every = feature_edges(cube, _view(cube), crease_degrees=20.0)
    per_face = feature_edges(cube, _view(cube),
                             crease_degrees=[20.0] * len(cube.faces))
    assert every == per_face


def test_a_face_that_wants_its_folds_wins_the_edge_it_shares():
    cube = build("box")
    half = len(cube.faces) // 2
    mixed = _folds(feature_edges(cube, _view(cube),
                                 crease_degrees=[20.0] * half + [175.0] * half))
    loose = _folds(feature_edges(cube, _view(cube), crease_degrees=175.0))
    assert len(mixed) > len(loose)


def test_the_angle_list_must_be_one_per_face():
    cube = build("box")
    with pytest.raises(ValueError, match="one crease angle per face"):
        feature_edges(cube, _view(cube), crease_degrees=[30.0, 30.0])


def test_every_angle_in_the_list_is_checked():
    cube = build("box")
    with pytest.raises(ValueError, match="between 0 and 180"):
        feature_edges(cube, _view(cube),
                      crease_degrees=[30.0] * (len(cube.faces) - 1) + [200.0])


def _folds(edges) -> list:
    return [e for e in edges if e.kind == "crease"]


def _view(mesh):
    return Camera.named("three-quarter").frame(mesh, width=30.0)


# -- a Mesh is not the name of a solid ---------------------------------------


def test_solid_says_what_to_call_when_it_is_handed_a_mesh():
    """The obvious first guess, and it used to fail inside the parser.

    `'Mesh' object has no attribute 'strip'` names neither what was expected
    nor what to call instead.
    """
    mesh = build("box")
    with pytest.raises(TypeError) as caught:
        inklet.solid(mesh)
    said = str(caught.value)
    assert "Mesh" in said
    assert "model(" in said and "scene(" in said


def test_solid_still_takes_a_name():
    assert inklet.solid("cube", width=10.0) is not None
