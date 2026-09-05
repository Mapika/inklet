"""The pair budget: what stops `sort="auto"` costing more than it promised.

`sorts_exactly` decides on the face count, which is cheap and wrong -- what the
exact painting order costs is its *candidate pairs*, and the two are related by
a factor that runs from 2 to 18 depending on how much of the surface lies over
itself in this projection. So the face count only gets a mesh as far as being
offered, and `order.painter_sort` reads the real number once the grid has
produced it and hands back the depth order if it is over budget.

What is worth holding down here is not the constants -- those are clock
settings and will move again -- but the three properties they hang on: that the
budget is read before any per-pair work is paid for, that going over it costs
the picture nothing worse than the mean-depth order, and that an explicit
`sort="exact"` is never quietly downgraded.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import inklet
from inklet.three import (AUTO_EXACT_FACETS, AUTO_EXACT_PAIRS, build,
                       painter_sort, sorts_exactly)
from inklet.three import order as _order
from inklet.three import shade as _shade
from inklet.three.camera import Camera
from inklet.three.parse import load
from inklet.three.solids import sphere


def _scene(mesh, **kw):
    """The facets and the view a render would hand to `painter_sort`."""
    caught = {}
    real = _shade.painter_sort

    def spy(facets, view, fresh, budget=None):
        caught["args"] = (list(facets), view, fresh, budget)
        return real(facets, view, fresh, budget)

    _shade.painter_sort = spy
    try:
        inklet.model(mesh, width=90.0, style="shaded", **kw)
    finally:
        _shade.painter_sort = real
    return caught["args"]


# -- the budget reaches the sort -------------------------------------------


def test_auto_hands_the_budget_down_and_exact_hands_down_none():
    """The whole mechanism in one assertion: `"auto"` is capped and `"exact"`
    is not. A caller who named the exact order is owed it whatever it costs --
    silently returning the approximation because a mesh turned out lumpy is the
    kind of surprise that makes a figure wrong and says nothing."""
    _, _, _, budget = _scene(build("box"), sort="auto")
    assert budget == AUTO_EXACT_PAIRS
    _, _, _, budget = _scene(build("box"), sort="exact")
    assert budget is None


def test_the_budget_is_a_pair_count_not_a_facet_count():
    """Stated because the two are easy to confuse and differ by an order of
    magnitude: the NIH brain asks many more candidate pairs than it draws facets.
    A budget mistakenly compared against the facet count would refuse
    everything."""
    mesh = load(str(Path(ROOT) / "stress/meshes/brain-lh.obj"))
    facets, view, fresh, _ = _scene(mesh, sort="exact")
    asked = []
    real = _order._candidates

    def spy(boxes, planes):
        out = real(boxes, planes)
        asked.append(len(out[0]))
        return out

    _order._candidates = spy
    try:
        painter_sort(facets, view, fresh)
    finally:
        _order._candidates = real
    assert asked and asked[0] > 4 * len(facets)


# -- going over it ----------------------------------------------------------


def test_over_budget_the_facets_come_back_in_depth_order():
    """A budget of one pair refuses every scene that has any, and what comes
    back is furthest-first on the same key `sorted_facets` uses. Not merely
    "some order": the caller asked for the painting order and has to be able to
    paint what it gets."""
    mesh = load(str(Path(ROOT) / "stress/meshes/brain-lh.obj"))
    facets, view, fresh, _ = _scene(mesh, sort="exact")
    bailed = painter_sort(facets, view, fresh, 1)
    assert len(bailed) == len(facets)
    assert [id(f) for f in bailed] == [id(f) for f in sorted(
        facets, key=lambda f: (-f.depth, f.points[0].x, f.points[0].y))]


def test_a_budget_that_bails_before_cutting_returns_the_list_it_was_given():
    """`sorted_facets` sorts on that key before it calls, so the cheapest
    possible bail is the identity. This is what makes the valve free: nothing
    is rebuilt and nothing is re-sorted."""
    mesh = load(str(Path(ROOT) / "stress/meshes/brain-lh.obj"))
    facets, view, fresh, _ = _scene(mesh, sort="exact")
    assert [id(f) for f in painter_sort(facets, view, fresh, 0)] \
        == [id(f) for f in facets]


def test_a_generous_budget_is_the_same_answer_as_no_budget_at_all():
    """The valve may not perturb a run it does not stop."""
    mesh = load(str(Path(ROOT) / "stress/meshes/brain-lh.obj"))
    facets, view, fresh, _ = _scene(mesh, sort="exact")
    free = painter_sort(facets, view, fresh)
    capped = painter_sort(facets, view, fresh, 10 ** 9)
    assert [f.points for f in free] == [f.points for f in capped]


def test_the_budget_is_spent_across_rounds_and_not_per_round():
    """Cutting re-asks, so a mesh that needs two rounds pays twice. The budget
    is the total, which is what makes it a bound on the clock rather than on
    one pass -- and it is why the second round of a nearly-affordable mesh is
    where the valve usually fires."""
    seen = []
    real = _order._pairs

    def spy(items, view, budget=None):
        seen.append(budget)
        return real(items, view, budget)

    mesh = load(str(Path(ROOT) / "stress/meshes/brain-lh.obj"))
    facets, view, fresh, _ = _scene(mesh, sort="exact")
    _order._pairs = spy
    try:
        painter_sort(facets, view, fresh, AUTO_EXACT_PAIRS)
    finally:
        _order._pairs = real
    assert len(seen) >= 2
    assert seen[0] == AUTO_EXACT_PAIRS
    assert seen[1] < seen[0]        # round one's pairs came out of the budget


# -- the number the valve exists for ---------------------------------------


def test_the_same_mesh_costs_different_pairs_from_different_angles():
    """The reason the face count cannot be the whole gate, as a measurement.
    brain-lh asks 343,942 candidate pairs from three-quarters and 510,151 from
    the front -- the same 18,000 faces, half again the work -- so no number
    computed off the mesh alone can tell the affordable case from the
    expensive one."""
    mesh = load(str(Path(ROOT) / "stress/meshes/brain-lh.obj"))
    counts = {}
    for name in ("three-quarter", "front"):
        asked = []
        real = _order._candidates

        def spy(boxes, planes):
            out = real(boxes, planes)
            asked.append(len(out[0]))
            return out

        _order._candidates = spy
        try:
            inklet.model(mesh, width=90.0, style="shaded", sort="exact",
                      view=name)
        finally:
            _order._candidates = real
        counts[name] = sum(asked)
    assert counts["front"] > 1.4 * counts["three-quarter"]
    assert counts["three-quarter"] < AUTO_EXACT_PAIRS < counts["front"]


def test_the_front_view_of_the_worst_mesh_in_the_repository_bails():
    """The valve firing on a real figure's worth of geometry rather than on a
    contrived budget. 18,000 faces is inside the face ceiling, so the mesh is
    offered the exact order and the pair count is what turns it away."""
    mesh = load(str(Path(ROOT) / "stress/meshes/brain-lh.obj"))
    assert sorts_exactly(mesh, "auto")
    bailed = []
    real = _order._bailed

    def spy(items):
        bailed.append(len(items))
        return real(items)

    _order._bailed = spy
    try:
        inklet.model(mesh, width=90.0, style="shaded", sort="auto", view="front")
        assert bailed, "the front view is over budget and should have bailed"
        bailed.clear()
        inklet.model(mesh, width=90.0, style="shaded", sort="auto",
                  view="three-quarter")
        assert not bailed, "three-quarters is inside the budget"
    finally:
        _order._bailed = real


def test_an_explicit_exact_is_never_turned_away_however_expensive():
    """The front view again, asked for by name. No bail, whatever it costs."""
    mesh = load(str(Path(ROOT) / "stress/meshes/brain-lh.obj"))
    bailed = []
    real = _order._bailed

    def spy(items):
        bailed.append(len(items))
        return real(items)

    _order._bailed = spy
    try:
        inklet.model(mesh, width=90.0, style="shaded", sort="exact", view="front")
    finally:
        _order._bailed = real
    assert not bailed


# -- the constants stay in the relation the argument assumes ----------------


def test_the_face_ceiling_is_the_worst_pairs_per_face_spent_in_full():
    """22,000 is not a round number, it is 400,000 / 17.7 rounded down: the
    budget divided by the most candidate pairs per face ever measured here (the
    Stanford bunny). The two constants are supposed to run out together, so
    that the valve is a backstop and not the routine path."""
    worst_pairs_per_face = 17.7
    assert AUTO_EXACT_FACETS == pytest.approx(
        AUTO_EXACT_PAIRS / worst_pairs_per_face, rel=0.05)


def test_a_ball_that_fits_both_gates_really_does_sort_inside_the_budget():
    """The subdivision-five sphere is the mesh the raise was for, so its pair
    count is worth pinning rather than trusting the table in the docstring."""
    ball = sphere(1.0, 5)
    assert sorts_exactly(ball, "auto")
    asked = []
    real = _order._candidates

    def spy(boxes, planes):
        out = real(boxes, planes)
        asked.append(len(out[0]))
        return out

    _order._candidates = spy
    try:
        inklet.model(ball, width=90.0, style="shaded", sort="auto")
    finally:
        _order._candidates = real
    assert 0 < sum(asked) < AUTO_EXACT_PAIRS / 4
