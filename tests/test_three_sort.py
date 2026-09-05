"""Which facet gets painted over which.

There is no depth buffer in an SVG: paint order *is* visibility, and the two
ways of settling it disagree exactly where it matters. Ranking each facet by
the mean depth of its corners is cheap and right for a convex solid, and wrong
the moment one part of a face is in front of another face that its centre is
nowhere near -- the wall of a bolt hole against the side of the plate it is
drilled through. The pairwise test is right and costs O(n^2) grid work. `auto`
picks between them on the one thing that predicts the cost, the face count,
and this file pins the pick, the threshold, and the two shapes of answer.
"""

from __future__ import annotations

import re

import pytest

import inklet
from inklet.three import AUTO_EXACT_FACETS, build, sorts_exactly
from inklet.three.backend import SORTS, Look
from inklet.three.solids import cylinder, sphere


def _plate():
    """The cookbook's drilled plate: four bores, one of them near the front
    edge where the mean-depth rank used to put its wall over the side face."""
    plate = build("box", size_x=4.0, size_y=3.0, size_z=0.4)
    for x, y in ((-1.4, -0.9), (1.4, -0.9), (1.4, 0.9), (-1.4, 0.9)):
        plate = plate.drill("z", radius=0.3, at=(x, y, 0), group="hole")
    return plate


def _facets(mesh, view_name="three-quarter", **kwargs):
    from inklet.three.camera import Camera
    from inklet.three.edges import facing_faces
    from inklet.three.shade import sorted_facets

    view = Camera.named(view_name).frame(mesh, width=30.0)
    points, depths = view.project_all(mesh.vertices)
    facing = facing_faces(mesh, view)
    return sorted_facets(mesh, view, points, depths, facing, **kwargs)


def _paths(node) -> list[str]:
    fig = inklet.figure(width=120.0)
    fig.add(node)
    return re.findall(r' d="([^"]+)"', fig.to_svg())


# -- the pick --------------------------------------------------------------


def test_auto_is_the_default_everywhere_it_can_be_named():
    assert Look().sort == "auto"
    assert SORTS[0] == "auto"
    assert set(SORTS) == {"auto", "depth", "exact"}


def test_auto_settles_small_meshes_exactly_and_big_ones_by_depth():
    small = build("box")
    assert len(small.faces) <= AUTO_EXACT_FACETS
    assert sorts_exactly(small, "auto")
    # Subdivision six, 81,920 faces. Five is 20,480 and sits *under* the
    # ceiling since it was raised to 22,000 -- it sorts exactly in 56 ms, and
    # the old 8,000 refused it for being big rather than for being expensive.
    big = sphere(1.0, 6)
    assert len(big.faces) > AUTO_EXACT_FACETS
    assert not sorts_exactly(big, "auto")


def test_the_ceiling_was_raised_far_enough_to_take_a_subdivision_five_ball():
    """The point of the two-part gate, as a fact about one mesh. 20,480 faces
    used to be refused outright; it now goes to the exact order, because what
    the sort costs is its candidate pairs and this ball has few of them for its
    size -- 41,604, a tenth of the budget."""
    ball = sphere(1.0, 5)
    assert 8000 < len(ball.faces) <= AUTO_EXACT_FACETS
    assert sorts_exactly(ball, "auto")


def test_naming_a_sort_overrides_the_face_count():
    small, big = build("box"), sphere(1.0, 6)
    assert not sorts_exactly(small, "depth")
    assert sorts_exactly(big, "exact")


def test_the_threshold_is_inclusive():
    # Stated as "up to this many faces", so a mesh sitting exactly on it is
    # still sorted exactly -- the docstring and the comparison agree.
    class _Fake:
        faces = (None,) * AUTO_EXACT_FACETS

    assert sorts_exactly(_Fake(), "auto")


# -- what the two orders do to a picture -----------------------------------


@pytest.mark.parametrize("shape", ["cube", "cylinder", "sphere"])
def test_a_convex_solid_looks_the_same_under_either_order(shape):
    # Nothing overlaps itself, so the pairwise test agrees with the centres
    # and the default flip costs these figures nothing at all.
    plain = _paths(inklet.solid(shape, width=30.0, view="three-quarter",
                             style="shaded", sort="depth"))
    exact = _paths(inklet.solid(shape, width=30.0, view="three-quarter",
                             style="shaded", sort="exact"))
    assert plain == exact


def test_a_solid_that_hides_part_of_itself_is_where_the_two_disagree():
    # A torus passes in front of its own far side, which is the whole reason
    # the pairwise test exists -- so this one is expected to move.
    plain = _paths(inklet.solid("torus", width=30.0, view="three-quarter",
                             style="shaded", sort="depth"))
    exact = _paths(inklet.solid("torus", width=30.0, view="three-quarter",
                             style="shaded", sort="exact"))
    assert plain != exact


def test_the_default_settles_the_drilled_plate_exactly():
    plate = _plate()
    assert len(plate.faces) <= AUTO_EXACT_FACETS
    auto = _paths(inklet.model(plate, width=60.0, view="three-quarter",
                            style="shaded", sort="auto"))
    exact = _paths(inklet.model(plate, width=60.0, view="three-quarter",
                             style="shaded", sort="exact"))
    plain = _paths(inklet.model(plate, width=60.0, view="three-quarter",
                             style="shaded", sort="depth"))
    assert auto == exact
    assert auto != plain
    # And it is the cheaper picture: the walls sort into fewer runs than the
    # mean-depth order interleaves them into.
    assert len(auto) < len(plain)


def test_a_bore_stays_a_hole_when_the_sort_moves_its_face():
    """The regression this file was opened for. A drilled face is one patch
    with inner rings, and the exact sort ranks each ring on its own -- so the
    wall of the bore legitimately comes out *between* a face and its own hole
    and fills it in. The rings ride along with the piece of the face that
    encloses them instead of being sorted."""
    facets = _facets(_plate(), sort="exact")
    riders = [f for f in facets if f.patch >= 0]
    assert riders, "the top face has four holes; they should be marked"
    # Every ring of a holed patch is adjacent to another ring of the same
    # patch, so nothing can be painted into the gap.
    for index, facet in enumerate(facets):
        if facet.patch < 0:
            continue
        neighbours = {facets[i].patch for i in (index - 1, index + 1)
                      if 0 <= i < len(facets)}
        assert facet.patch in neighbours


def test_the_holes_come_out_as_subpaths_of_the_face_they_are_cut_in():
    # Four bores through one top face: one path, five rings, and the fill
    # rule does the rest. If the sort had split them the count would drop.
    subpaths = sorted(d.count("M") for d in
                      _paths(inklet.model(_plate(), width=60.0, style="shaded",
                                       view="three-quarter", sort="auto")))
    assert subpaths[-1] >= 4


def test_the_mean_depth_order_is_still_reachable_and_still_deterministic():
    twice = [_paths(inklet.model(_plate(), width=60.0, view="three-quarter",
                              style="shaded", sort="depth")) for _ in range(2)]
    assert twice[0] == twice[1]


def test_a_mesh_over_the_threshold_falls_back_to_the_cheap_order():
    ball = sphere(1.0, 6)
    assert len(ball.faces) > AUTO_EXACT_FACETS
    auto = [f.points for f in _facets(ball, sort="auto")]
    plain = [f.points for f in _facets(ball, sort="depth")]
    assert auto == plain


def test_only_a_holed_patch_is_marked_with_a_patch_number():
    for facet in _facets(cylinder(1.0, 2.0, 24), sort="exact"):
        assert facet.patch == -1
