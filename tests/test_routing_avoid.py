"""`route="avoid"`: the router that goes round things.

Everything here is hand-placed with `core` alone, so the coordinates below can
be checked on paper. The boxes are 20x10 and the clearance is 1.5mm, which is
why "one clearance out from x = -10" reads as -11.5 throughout.

The two halves that matter most are the ones that are easy to skip: that a
figure with nothing in the way still draws the *identical* elbow (this mode
has to be safe to switch on), and that the search failing is a flag rather
than an exception (a router that raises on a dense figure is a router nobody
turns on).
"""

from __future__ import annotations

import hashlib
import importlib
import math
import subprocess
import sys
import textwrap

import pytest

from inklet.core import Diagram, PathPrim, Rect, RectPrim, Vec2, group, resolve
from inklet.diagnostics import lint
from inklet.links import (
    CLEARANCE, CONNECTOR_KIND, FLAG_NO_CLEAR_ROUTE, HEAD_KIND, LinkError,
    Obstacle, link, link_flags, route, route_all,
)

# The package re-exports the *function* `link`, which shadows the submodule of
# the same name, so `from inklet.links import link` never reaches the module. A
# test that pokes a module constant has to say so explicitly.
_module = importlib.import_module("inklet.links.link")

TOL = 1e-9


# -- fixtures and helpers -------------------------------------------------


def box(w: float = 20.0, h: float = 10.0) -> Diagram:
    return Diagram(prim=RectPrim(w, h), kind="box")


def column(count: int, gap: float = 20.0, **kwargs) -> tuple[list[Diagram], dict]:
    """`count` boxes stacked straight down, and the resolved layout."""
    boxes = [box(**kwargs) for _ in range(count)]
    return boxes, resolve(group([b.translated(0, gap * i)
                                 for i, b in enumerate(boxes)]))


def avoid(spec, placements) -> Diagram:
    """One link routed against everything the layout draws.

    `route_all` is what collects the obstacles in real use, so going through
    it here keeps the test honest about the plumbing as well as the search.
    """
    return route_all([spec], placements).children[0]


def polyline(routed: Diagram) -> list[Vec2]:
    """The shaft in world coordinates.

    Every test that reads geometry links with `kind="line"`, because an arrow
    head insets the shaft and would hide the last corner behind the barb.
    """
    places = resolve(routed)
    for node in routed.walk():
        if node.kind == CONNECTOR_KIND and isinstance(node.prim, PathPrim):
            world = places[node.id].world
            return [world.apply(p) for p in node.prim.subpaths[0].points]
    raise AssertionError("routed link has no shaft")


def rounded(points: list[Vec2], places: int = 6) -> list[tuple[float, float]]:
    return [(round(p.x, places), round(p.y, places)) for p in points]


def gap_to(a: Vec2, b: Vec2, rect: Rect) -> float:
    """Shortest distance from an axis-aligned segment to an axis-aligned box.

    Both are boxes as far as this is concerned -- the segment a degenerate one
    -- and the distance between two axis-aligned boxes is the hypotenuse of
    the two interval gaps. Exact, so the clearance test needs no sampling.
    """
    dx = max(0.0, rect.x0 - max(a.x, b.x), min(a.x, b.x) - rect.x1)
    dy = max(0.0, rect.y0 - max(a.y, b.y), min(a.y, b.y) - rect.y1)
    return math.hypot(dx, dy)


def closest(points: list[Vec2], rect: Rect) -> float:
    return min(gap_to(a, b, rect) for a, b in zip(points, points[1:]))


# -- the detour itself ----------------------------------------------------


def test_a_route_goes_round_the_box_between_its_endpoints():
    (top, middle, bottom), places = column(3, gap=25.0)

    routed = avoid(link(top, bottom, route="avoid", kind="line"), places)

    # Out of the west side, down past the middle box one clearance clear of
    # it, and back in. Two bends, both squared onto the tips.
    assert rounded(polyline(routed)) == [
        (-10.0, 0.0), (-11.5, 0.0), (-11.5, 50.0), (-10.0, 50.0),
    ]
    assert link_flags(routed) == ()


def test_the_straight_line_that_detour_replaces_really_did_cross_the_box():
    """The premise of the test above: without this, it proves nothing."""
    (top, middle, bottom), places = column(3, gap=25.0)
    middle_box = places[middle.id].bbox

    elbow = polyline(route(link(top, bottom, route="orthogonal", kind="line"), places))

    assert rounded(elbow) == [(0.0, 5.0), (0.0, 45.0)]      # straight through
    assert closest(elbow, middle_box) == pytest.approx(0.0, abs=TOL)


def test_a_detour_still_lands_on_both_boundaries():
    (top, _, bottom), places = column(3, gap=25.0)

    routed = avoid(link(top, bottom, route="avoid"), places)

    # `_clip_ends` owes the same contract an elbow does, arrow heads included.
    assert routed.anchor_point("start") == Vec2(-10.0, 0.0)
    assert routed.anchor_point("end") == Vec2(-10.0, 50.0)


# -- the simple case must not have moved ----------------------------------


def test_with_nothing_in_the_way_avoid_draws_the_orthogonal_elbow_exactly():
    a, b = box(), box()
    places = resolve(group([a, b.translated(60.0, 40.0)]))

    detour = avoid(link(a, b, route="avoid", kind="line"), places)
    elbow = route(link(a, b, route="orthogonal", kind="line"), places)

    assert rounded(polyline(detour)) == rounded(polyline(elbow))
    assert link_flags(detour) == link_flags(elbow) == ()


def test_a_degenerate_elbow_survives_avoid_untouched():
    """Endpoints sharing an axis collapse the elbow to a straight line, which
    is exactly the case NOTES calls out as *not* a workaround for crossings.
    With nothing between them there is nothing to work around, so it stands."""
    a, b = box(), box()
    places = resolve(group([a, b.translated(60.0, 0.0)]))

    detour = avoid(link(a, b, route="avoid", kind="line"), places)

    assert rounded(polyline(detour)) == [(10.0, 0.0), (50.0, 0.0)]


def test_avoid_with_no_obstacles_at_all_is_the_elbow():
    """Calling `route()` directly, with the obstacle argument left off."""
    (top, _, bottom), places = column(3, gap=25.0)

    bare = route(link(top, bottom, route="avoid", kind="line"), places)
    elbow = route(link(top, bottom, route="orthogonal", kind="line"), places)

    assert rounded(polyline(bare)) == rounded(polyline(elbow))


# -- a link's own endpoints are not obstacles to it -----------------------


def test_two_shapes_closer_than_two_clearances_still_link_directly():
    """The endpoint exemption, stated as geometry rather than as bookkeeping.

    The gap here is 2mm and a clearance is 1.5mm, so if a link treated its own
    target as an obstacle the corridor between them would be sealed and the
    arrow would take some ridiculous lap of the figure to arrive.
    """
    a, b = box(), box()
    places = resolve(group([a, b.translated(0.0, 12.0)]))   # 2mm apart

    routed = avoid(link(a, b, route="avoid", kind="line"), places)

    assert rounded(polyline(routed)) == [(0.0, 5.0), (0.0, 7.0)]
    assert link_flags(routed) == ()


def test_an_endpoints_own_children_are_not_obstacles_either():
    """`box("LGN")` is a group holding a rectangle *and* a text, and both draw.
    Exempting only the node named in the link would leave a route walled in by
    its own label."""
    inner = box(18.0, 8.0)
    outer = Diagram(prim=RectPrim(20.0, 10.0), children=(inner,), kind="box")
    target = box()
    places = resolve(group([outer, target.translated(0.0, 12.0)]))

    routed = avoid(link(outer, target, route="avoid", kind="line"), places)

    assert rounded(polyline(routed)) == [(0.0, 5.0), (0.0, 7.0)]
    assert link_flags(routed) == ()


def test_a_backdrop_containing_an_endpoint_is_not_a_wall():
    """A `frame()` puts its backdrop *beside* its content, not above it, so
    lineage cannot spot this one. Containment can."""
    backdrop = box(40.0, 30.0)
    inside, outside = box(10.0, 6.0), box(10.0, 6.0)
    places = resolve(group([backdrop, inside, outside.translated(60.0, 0.0)]))

    routed = avoid(link(inside, outside, route="avoid", kind="line"), places)

    # Straight out through the backdrop it is standing on: no detour, no flag.
    assert rounded(polyline(routed)) == [(5.0, 0.0), (55.0, 0.0)]
    assert link_flags(routed) == ()


def test_a_third_box_merely_overlapping_an_endpoint_is_still_an_obstacle():
    """The other half of the rule above. A route may leave its own shape; it
    may not tunnel through the neighbour that happens to be sitting on it."""
    source, target = box(10.0, 6.0), box(10.0, 6.0)
    intruder = box(10.0, 6.0)
    places = resolve(group([source, intruder.translated(9.0, 0.0),
                            target.translated(40.0, 0.0)]))

    routed = avoid(link(source, target, route="avoid", kind="line"), places)
    points = polyline(routed)

    assert closest(points, places[intruder.id].bbox) >= CLEARANCE - TOL
    assert rounded(points) == [(0.0, -3.0), (0.0, -4.5), (40.0, -4.5), (40.0, -3.0)]


# -- what a caller may pass as an obstacle --------------------------------


def test_a_caller_may_still_hand_route_a_plain_sequence_of_rects():
    """The signature widened rather than broke: `Sequence[Rect]` is what every
    caller before this change passed, and it routes to the same polyline as
    the labelled form."""
    (top, middle, bottom), places = column(3, gap=25.0)
    spec = link(top, bottom, route="avoid", kind="line")
    rect = places[middle.id].bbox

    plain = route(spec, places, [rect])
    labelled = route(spec, places, [Obstacle(middle.id, rect)])

    assert rounded(polyline(plain)) == rounded(polyline(labelled))
    assert rounded(polyline(plain)) == [
        (-10.0, 0.0), (-11.5, 0.0), (-11.5, 50.0), (-10.0, 50.0),
    ]


def test_an_unlabelled_box_blocks_even_the_link_it_was_cut_from():
    """The price of that compatibility, made visible. A `Rect` says where
    something is but not what it is, so it gets the empty id no node answers
    to. Here that is the source's own inner rectangle: labelled, the link
    walks straight out of itself; unlabelled, it is walled in by its own
    contents and falls back."""
    inner = box(18.0, 8.0)
    outer = Diagram(prim=RectPrim(20.0, 10.0), children=(inner,), kind="box")
    target = box()
    places = resolve(group([outer, target.translated(0.0, 12.0)]))
    spec = link(outer, target, route="avoid", kind="line")
    rect = places[inner.id].bbox

    assert link_flags(route(spec, places, [Obstacle(inner.id, rect)])) == ()
    assert FLAG_NO_CLEAR_ROUTE in link_flags(route(spec, places, [rect]))


# -- clearance ------------------------------------------------------------


def test_every_segment_keeps_the_clearance_from_every_obstacle():
    boxes, places = column(6, gap=20.0)
    obstacles = [places[b.id].bbox for b in boxes[1:-1]]

    routed = avoid(link(boxes[0], boxes[-1], route="avoid", kind="line"), places)
    points = polyline(routed)

    for rect in obstacles:
        assert closest(points, rect) >= CLEARANCE - TOL
    # And it is the clearance, not a lap of the page: the long run hugs the
    # column at exactly 1.5mm.
    assert min(closest(points, r) for r in obstacles) == pytest.approx(CLEARANCE)


def test_clearance_is_kept_on_both_axes_at_once():
    """A corner cut diagonally past a box would pass an axis-by-axis check and
    fail a real one, so the distance above is measured as a hypotenuse."""
    source, target = box(10.0, 6.0), box(10.0, 6.0)
    blocker = box(30.0, 30.0)
    places = resolve(group([source, blocker.translated(30.0, 0.0),
                            target.translated(60.0, 0.0)]))

    points = polyline(avoid(link(source, target, route="avoid", kind="line"), places))

    assert closest(points, places[blocker.id].bbox) >= CLEARANCE - TOL


# -- collinear runs are collapsed -----------------------------------------


def test_a_long_run_past_many_boxes_is_one_segment_not_one_per_lattice_line():
    """The search returns a vertex wherever it crossed a candidate line. Four
    boxes contribute eight y-lines plus midlines, and all of them lie on the
    same straight run down the side of the column."""
    boxes, places = column(6, gap=20.0)

    points = polyline(avoid(link(boxes[0], boxes[-1], route="avoid", kind="line"),
                            places))

    assert rounded(points) == [
        (-10.0, 0.0), (-11.5, 0.0), (-11.5, 100.0), (-10.0, 100.0),
    ]


def test_no_routed_polyline_keeps_a_collinear_or_repeated_vertex():
    boxes, places = column(6, gap=20.0)
    source, target = boxes[0], boxes[-1]

    points = polyline(avoid(link(source, target, route="avoid", kind="line"), places))

    for a, b in zip(points, points[1:]):
        assert (b - a).length > TOL                    # no repeats
    for a, b, c in zip(points, points[1:], points[2:]):
        assert abs((b - a).cross(c - b)) > TOL         # no straight-through bends


# -- falling back ---------------------------------------------------------


def walled_in() -> tuple[Diagram, Diagram, dict]:
    """A 10x10 box with a wall 1mm off each of its four sides.

    1mm is less than one clearance, so every port stub crosses an inflated
    wall and `_ports` hands the search nothing to start from.
    """
    middle, far = box(10.0, 10.0), box(10.0, 10.0)
    walls = [box(10.0, 1.0).translated(0.0, -6.0),
             box(10.0, 1.0).translated(0.0, 6.0),
             box(1.0, 10.0).translated(-6.0, 0.0),
             box(1.0, 10.0).translated(6.0, 0.0)]
    content = group([middle, far.translated(60.0, 0.0)] + walls)
    return middle, far, resolve(content)


def test_a_walled_in_endpoint_falls_back_to_the_elbow_and_says_so():
    middle, far, places = walled_in()

    routed = avoid(link(middle, far, route="avoid", kind="line"), places)
    elbow = route(link(middle, far, route="orthogonal", kind="line"), places)

    assert FLAG_NO_CLEAR_ROUTE in link_flags(routed)
    assert rounded(polyline(routed)) == rounded(polyline(elbow))


def test_the_fallback_keeps_its_arrow_head_and_its_anchors():
    """Falling back is a drawing decision, not a failure mode: the caller gets
    the same shape of result either way."""
    middle, far, places = walled_in()

    routed = avoid(link(middle, far, route="avoid"), places)

    assert routed.anchor_point("start") == Vec2(5.0, 0.0)
    assert routed.anchor_point("end") == Vec2(55.0, 0.0)
    assert [node.kind for node in routed.walk()].count(HEAD_KIND) == 1


def test_a_lattice_too_big_to_search_falls_back_rather_than_grinding():
    (top, _, bottom), places = column(3, gap=25.0)
    spec = link(top, bottom, route="avoid", kind="line")
    original = _module._MAX_LATTICE_NODES
    _module._MAX_LATTICE_NODES = 1
    try:
        routed = avoid(spec, places)
    finally:
        _module._MAX_LATTICE_NODES = original

    assert FLAG_NO_CLEAR_ROUTE in link_flags(routed)
    assert rounded(polyline(routed)) == [(0.0, 5.0), (0.0, 45.0)]
    # And the cap really was what did it -- the same link routes without it.
    assert link_flags(avoid(spec, places)) == ()


def test_both_ends_on_one_shape_is_a_loop_not_a_search():
    """Nothing to search for: a link onto its own shape is drawn as a loop."""
    only = box()
    places = resolve(group([only]))

    routed = avoid(link(only, only, route="avoid", kind="line"), places)
    points = polyline(routed)

    assert link_flags(routed) == ()
    assert len(points) > 2                       # an arc, not a collapsed point
    assert min(p.y for p in points) < -5.0       # and it leaves the box


def test_the_blocked_flag_reaches_the_linter():
    middle, far, places = walled_in()
    links = route_all([link(middle, far, route="avoid")], places)

    diagnostics = lint(group([links]), rules=["ROUTE_BLOCKED"])

    assert [d.code for d in diagnostics] == ["ROUTE_BLOCKED"]
    assert diagnostics[0].severity == "warning"
    assert "no clear corridor" in diagnostics[0].message
    # It names the link and both shapes, so the reader knows which arrow.
    assert diagnostics[0].targets[1:] == (middle.id, far.id)


def test_a_clear_route_leaves_the_linter_silent():
    (top, _, bottom), places = column(3, gap=25.0)
    links = route_all([link(top, bottom, route="avoid")], places)

    assert lint(group([links]), rules=["ROUTE_BLOCKED"]) == []


# -- the mode itself ------------------------------------------------------


def test_avoid_is_a_route_and_a_typo_is_not():
    assert link(box(), box(), route="avoid").route == "avoid"
    with pytest.raises(LinkError, match="avoid"):
        link(box(), box(), route="avoidance")


# -- determinism ----------------------------------------------------------


def test_routing_is_identical_across_repeated_calls():
    boxes, places = column(6, gap=20.0)
    spec = link(boxes[0], boxes[-1], route="avoid", kind="line")

    first = rounded(polyline(avoid(spec, places)))
    second = rounded(polyline(avoid(spec, places)))

    assert first == second


_SCRIPT = textwrap.dedent("""
    import dataclasses, inklet
    theme = dataclasses.replace(inklet.theme("nature"), font_family="DejaVu Sans")
    inklet.use_theme(theme)
    left = [inklet.box(n, width=18) for n in ("a", "b", "c", "d")]
    right = [inklet.box(n, width=18) for n in ("w", "x", "y")]
    fig = inklet.figure(width="180mm")
    fig.add(inklet.hstack([inklet.vstack(left, gap=5), inklet.spacer(50, 1),
                        inklet.vstack(right, gap=7)], gap=6))
    for a, b in ((0, 0), (1, 1), (2, 0), (3, 2)):
        fig.link(left[a], right[b])
    fig.link(left[0], left[2], route="avoid")
    fig.link(left[1], left[3], route="avoid")
    import sys
    sys.stdout.write(fig.to_svg())
""")


def _svg_digest(seed: str) -> str:
    result = subprocess.run([sys.executable, "-c", _SCRIPT],
                            capture_output=True, text=True,
                            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"})
    assert result.returncode == 0, result.stderr
    return hashlib.md5(result.stdout.encode()).hexdigest()


@pytest.mark.parametrize("seed", ["12345", "999"])
def test_a_routed_figure_is_byte_identical_under_a_different_hash_seed(seed):
    """The contract is "the same script twice", and a Hanan-grid search is
    exactly the sort of code that breaks it: one iteration over a set, one
    dict whose order came from hashing, and the corridor chosen changes."""
    assert _svg_digest(seed) == _svg_digest("0")
