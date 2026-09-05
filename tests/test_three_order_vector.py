"""The array separating-axis test against the one it replaces.

`order._which_overlap` answers for a whole run of candidate pairs what
`order.overlaps` answers for one, and `order._vector_candidates` produces that
run the way the grid loop produces it. The exact painting order is built on
both. Two implementations of one predicate is a standing invitation for a
figure to come out differently on a machine with numpy than on one without, so
what is pinned here is not "both are reasonable" but *equality* -- pair by pair
on the polygons the corpus really asks about, and byte for byte on the SVG.

Bit-exactness is achievable rather than lucky: the array path does the same
multiplies, the same minima and the same comparisons in the same order, so
there is no reassociation for the rounding to differ over. These tests are what
says it stayed that way.
"""

from __future__ import annotations

import random
import re

import pytest

import inklet
from inklet.three import build
from inklet.three.order import (_candidates, _vector_candidates,
                             _which_overlap, overlaps)
from inklet.three.parse import load
from inklet.three.solids import sphere


@pytest.fixture
def both_paths(monkeypatch):
    """Run a body twice: once through the array path, once through numpy's
    absence. Returns a function that takes a no-argument callable."""

    def run(body):
        monkeypatch.setattr("inklet.three.order._VECTOR_FLOOR", 1)
        monkeypatch.setattr("inklet.three.order._GRID_FLOOR", 1)
        with_arrays = body()
        monkeypatch.setattr("inklet.three.order._numpy", lambda: None)
        without = body()
        return with_arrays, without

    return run


# -- the predicate ---------------------------------------------------------


def _polygons(count, sides, rng, spread=6.0):
    """Convex polygons scattered over a page, wound either way.

    Points on a circle in angle order, which is convex whatever the radii, and
    the radii vary so that the pairs land in every relation: apart, nested,
    corner-on-edge, and sharing an edge exactly.
    """
    import math

    out = []
    for _ in range(count):
        cx, cy = rng.uniform(-spread, spread), rng.uniform(-spread, spread)
        start = rng.uniform(0.0, 2.0 * math.pi)
        turn = 1.0 if rng.random() < 0.5 else -1.0
        points = []
        for k in range(sides):
            angle = start + turn * 2.0 * math.pi * k / sides
            radius = rng.uniform(0.2, 3.0)
            points.append((cx + radius * math.cos(angle),
                           cy + radius * math.sin(angle)))
        out.append(tuple(points))
    return out


@pytest.mark.parametrize("sides", [3, 4, 5])
@pytest.mark.parametrize("slack", [0.0, 0.02, 0.5])
def test_the_array_test_answers_what_the_scalar_one_answers(sides, slack,
                                                            monkeypatch):
    rng = random.Random(20260824 + sides)
    corners = _polygons(400, sides, rng)
    first = [i for i in range(len(corners)) for _ in range(i + 1, len(corners))]
    second = [j for i in range(len(corners)) for j in range(i + 1, len(corners))]
    monkeypatch.setattr("inklet.three.order._VECTOR_FLOOR", 1)
    array = list(_which_overlap(corners, first, second, slack))
    one_by_one = [overlaps(corners[i], corners[j], slack)
                  for i, j in zip(first, second)]
    assert array == one_by_one
    # A test that never sees an overlap would pass on a broken implementation.
    assert 0 < sum(one_by_one) < len(one_by_one)


def test_a_mixed_run_of_triangles_and_larger_polygons_agrees(monkeypatch):
    # Only triangles go through the arrays; anything wider is handed back to
    # the scalar test one at a time. The seam between the two is worth its own
    # case, because a run is normally 99 percent triangles and a bug in the
    # remainder would hide.
    rng = random.Random(7)
    corners = (_polygons(150, 3, rng) + _polygons(60, 4, rng)
               + _polygons(40, 6, rng))
    rng.shuffle(corners)
    first = [i for i in range(len(corners)) for _ in range(i + 1, len(corners))]
    second = [j for i in range(len(corners)) for j in range(i + 1, len(corners))]
    monkeypatch.setattr("inklet.three.order._VECTOR_FLOOR", 1)
    assert list(_which_overlap(corners, first, second, 0.02)) == \
        [overlaps(corners[i], corners[j], 0.02) for i, j in zip(first, second)]


def test_a_repeated_corner_is_not_an_axis(monkeypatch):
    # A degenerate edge has no normal to separate along. The scalar test skips
    # it; if the array path let a zero-length normal separate a pair, every
    # such pair would come back apart.
    flat = ((0.0, 0.0), (2.0, 0.0), (2.0, 0.0))
    over = ((0.5, -0.5), (1.5, -0.5), (1.0, 0.5))
    monkeypatch.setattr("inklet.three.order._VECTOR_FLOOR", 1)
    assert list(_which_overlap([flat, over], [0], [1], 0.0)) == \
        [overlaps(flat, over, 0.0)]


def test_the_floor_sends_a_short_run_to_the_scalar_test():
    # Below the floor there is no numpy call at all, so a machine without it
    # is on the same road as a small figure on a machine with it.
    rng = random.Random(3)
    corners = _polygons(20, 3, rng)
    first = [i for i in range(len(corners)) for _ in range(i + 1, len(corners))]
    second = [j for i in range(len(corners)) for j in range(i + 1, len(corners))]
    assert list(_which_overlap(corners, first, second, 0.02)) == \
        [overlaps(corners[i], corners[j], 0.02) for i, j in zip(first, second)]


# -- the picture -----------------------------------------------------------


def _svg(node):
    """The figure's bytes, with the `id` counter taken out.

    Element ids come from a counter that runs for the life of the process, so
    rendering the same thing twice in one test numbers it twice. Everything
    else -- every coordinate, every fill, the order the paths are written in --
    is compared as it stands.
    """
    fig = inklet.figure()
    fig.add(node)
    return re.sub(r' id="[^"]*"', "", fig.to_svg())


@pytest.mark.parametrize("shape,fineness", [("torus", {"segments": 40}),
                                            ("sphere", {"subdivisions": 4})])
def test_a_solid_renders_the_same_with_and_without_numpy(shape, fineness,
                                                         both_paths):
    # The proof the two paths are one predicate: not "the pictures look alike"
    # but the same bytes, on a shape whose facets really do overlap. Fine
    # enough that the run clears the floor and the arrays are really used.
    with_arrays, without = both_paths(
        lambda: _svg(inklet.solid(shape, width=60.0, view="three-quarter",
                               style="shaded", sort="exact", **fineness)))
    assert with_arrays == without


def test_a_scanned_surface_renders_the_same_with_and_without_numpy(both_paths):
    # A scan is where the array path earns its keep -- slivers pile many facets
    # into one grid cell -- and where a rounding difference would first show.
    mesh = load("stress/meshes/brain-lh.obj")
    with_arrays, without = both_paths(
        lambda: _svg(inklet.model(mesh, width=60.0, view="three-quarter",
                               style="shaded", sort="exact")))
    assert with_arrays == without


def test_a_drilled_plate_renders_the_same_with_and_without_numpy(both_paths):
    # Cut facets: the exact order splits these and gives the halves fresh ring
    # indices, so a pair answered differently would show up as a renumbering
    # and not only as a moved point.
    plate = build("box", size_x=4.0, size_y=3.0, size_z=0.4)
    for x, y in ((-1.4, -0.9), (1.4, -0.9), (1.4, 0.9), (-1.4, 0.9)):
        plate = plate.drill("z", radius=0.3, at=(x, y, 0), group="hole")
    with_arrays, without = both_paths(
        lambda: _svg(inklet.model(plate, width=60.0, view="three-quarter",
                               style="shaded", sort="exact")))
    assert with_arrays == without


def test_every_pair_a_real_mesh_asks_about_is_answered_the_same(monkeypatch):
    """The corpus proof, at the level of the predicate rather than the file.

    Renders a sphere the exact way with `_which_overlap` recording what it was
    asked, then replays every one of those pairs through both paths. It is the
    same guarantee the SVG comparisons above give, stated so that a failure
    names the pair instead of a diff of a megabyte.
    """
    import inklet.three.order as order

    asked = []
    real = order._which_overlap

    def recording(corners, first, second, slack):
        asked.append(([tuple(c) for c in corners], list(first), list(second),
                      slack))
        return real(corners, first, second, slack)

    monkeypatch.setattr(order, "_which_overlap", recording)
    inklet.model(sphere(subdivisions=4), width=60.0, view="three-quarter",
              style="shaded", sort="exact")
    assert asked, "the exact sort asked nothing: the probe missed"
    monkeypatch.undo()

    total = 0
    for corners, first, second, slack in asked:
        monkeypatch.setattr("inklet.three.order._VECTOR_FLOOR", 1)
        array = list(_which_overlap(corners, first, second, slack))
        monkeypatch.setattr("inklet.three.order._numpy", lambda: None)
        scalar = list(_which_overlap(corners, first, second, slack))
        monkeypatch.undo()
        monkeypatch.undo()
        assert array == scalar
        total += len(first)
    assert total > 5000, f"only {total} pairs: the mesh got too small to prove much"


# -- the candidate list ----------------------------------------------------


def _boxes(corners):
    from inklet.three.order import box_of

    class _P:
        __slots__ = ("x", "y")

        def __init__(self, x, y):
            self.x, self.y = x, y

    return [box_of([_P(x, y) for x, y in c]) for c in corners]


def _both_candidates(corners, planes, monkeypatch):
    """The grid loop's pairs and the array pass's, as sets."""
    import numpy

    monkeypatch.setattr("inklet.three.order._GRID_FLOOR", 10 ** 12)
    boxes = _boxes(corners)
    loop = set(zip(*_candidates(boxes, planes)))
    array = set(zip(*_vector_candidates(numpy, boxes, planes)))
    return loop, array


@pytest.mark.parametrize("count", [200, 900, 4000])
def test_the_array_grid_offers_the_pairs_the_loop_offers(count, monkeypatch):
    """Set equality, not list equality. Which pair comes out first is
    deliberately not part of the answer -- `_threaded` pops a heap keyed on
    depth and index and `_pairs` sorts its crossings, so nothing downstream can
    see the order -- and the array path groups the grid by cell size rather
    than walking it in insertion order."""
    rng = random.Random(11 + count)
    corners = _polygons(count, 3, rng, spread=1.0 + count / 400.0)
    loop, array = _both_candidates(corners, [True] * count, monkeypatch)
    assert loop == array
    assert loop                       # the case would be vacuous otherwise


def test_the_array_grid_still_orders_each_pair_low_index_first(monkeypatch):
    """`_pairs` reads `first[k]` and `second[k]` as i and j and never sorts
    them, and `_cut` keys its cut lines on the facet index, so a pair arriving
    the other way round would be a second entry for the same pair rather than
    the same one."""
    import numpy

    rng = random.Random(5)
    corners = _polygons(1200, 3, rng, spread=4.0)
    first, second = _vector_candidates(numpy, _boxes(corners),
                                       [True] * len(corners))
    assert first and all(i < j for i, j in zip(first, second))
    assert len(set(zip(first, second))) == len(first)     # and no duplicates


def test_a_facet_with_no_plane_is_in_no_pair_either_way(monkeypatch):
    """The array path drops the plane-less facets before it builds the grid
    rather than skipping them inside it, which is only sound because ownership
    of a pair is a `max` over the two facets' own cells and reads nothing about
    who else is nearby."""
    rng = random.Random(7)
    corners = _polygons(1500, 3, rng, spread=5.0)
    planes = [None if k % 3 == 0 else True for k in range(len(corners))]
    loop, array = _both_candidates(corners, planes, monkeypatch)
    assert loop == array
    assert not any(planes[i] is None or planes[j] is None for i, j in array)


def test_a_crowd_in_one_cell_is_batched_without_changing_the_answer(
        monkeypatch):
    """Every facet piled on top of every other puts them all in one grid cell,
    which is the case the pair batching exists for. Squeezing the batch down to
    a handful of pairs must not change what comes out."""
    import numpy

    rng = random.Random(3)
    corners = _polygons(120, 3, rng, spread=0.05)
    boxes = _boxes(corners)
    planes = [True] * len(corners)
    whole = set(zip(*_vector_candidates(numpy, boxes, planes)))
    monkeypatch.setattr("inklet.three.order._PAIR_BUDGET", 4)
    assert set(zip(*_vector_candidates(numpy, boxes, planes))) == whole
    monkeypatch.setattr("inklet.three.order._GRID_FLOOR", 10 ** 12)
    assert set(zip(*_candidates(boxes, planes))) == whole


def test_every_candidate_list_a_real_mesh_builds_is_built_the_same(
        monkeypatch):
    """The corpus version of the above: record what the grid was actually asked
    on a detailed surface, then answer each one both ways."""
    import numpy

    from inklet.three import order

    asked = []
    real = order._candidates

    def spy(boxes, planes):
        asked.append((list(boxes), list(planes)))
        return real(boxes, planes)

    monkeypatch.setattr("inklet.three.order._candidates", spy)
    inklet.model(load("stress/meshes/spot.obj"), width=70.0,
              style="shaded", sort="exact")
    monkeypatch.undo()
    assert asked
    for boxes, planes in asked:
        array = set(zip(*_vector_candidates(numpy, boxes, planes)))
        monkeypatch.setattr("inklet.three.order._GRID_FLOOR", 10 ** 12)
        loop = set(zip(*order._candidates(boxes, planes)))
        monkeypatch.undo()
        assert loop == array
        assert len(array) > 1000
