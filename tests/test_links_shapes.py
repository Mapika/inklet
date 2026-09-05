"""The connector shapes that are not one line between two boxes.

Waypoints, shared trunks, self-loops, bowed parallel edges and ports, checked
numerically on hand-placed geometry the same way `test_links.py` does -- no
layout engine, no theme, so every number here can be worked out on paper.
"""

from __future__ import annotations

import pytest

from inklet.core import (
    Diagram, EllipsePrim, PathPrim, Placement, RectPrim, Vec2, group, resolve,
)
from inklet.links import (
    CONNECTOR_KIND, HEAD_KIND, Link, LinkError, link, link_ends, route,
    route_all,
)

TOL = 1e-6


def box(w: float = 20.0, h: float = 10.0, radius: float = 0.0) -> Diagram:
    return Diagram(prim=RectPrim(w, h, radius))


def figure(*nodes: Diagram) -> dict[str, Placement]:
    return resolve(group(nodes))


def subpaths(routed: Diagram) -> list[list[Vec2]]:
    """Every shaft subpath of a routed link, in world coordinates."""
    places = resolve(routed)
    out: list[list[Vec2]] = []
    for node in routed.walk():
        if node.kind != CONNECTOR_KIND or not isinstance(node.prim, PathPrim):
            continue
        world = places[node.id].world
        out.extend([world.apply(p) for p in sub.points]
                   for sub in node.prim.subpaths)
    return out


def shaft(routed: Diagram) -> list[Vec2]:
    return subpaths(routed)[0]


def head_tips(routed: Diagram) -> list[Vec2]:
    """Where each arrowhead points. The tip is the first point of the head."""
    places = resolve(routed)
    return [places[node.id].world.apply(node.prim.subpaths[0].points[0])
            for node in routed.walk() if node.kind == HEAD_KIND]


def ends(routed: Diagram) -> tuple[Vec2, Vec2]:
    return routed.anchor_point("start"), routed.anchor_point("end")


# -- waypoints ------------------------------------------------------------


def test_a_straight_route_visits_every_waypoint_in_order():
    a, b = box(), box()
    places = figure(a, b.translated(80, 0))

    routed = route(link(a, b, waypoints=[Vec2(20, -30), (60, -30)]), places)

    points = shaft(routed)
    assert points[1] == Vec2(20, -30)
    assert points[2] == Vec2(60, -30)
    # Still clipped onto the two boxes, and onto the face the detour actually
    # leaves by: both vias are above the boxes, so the line goes out of one
    # top face and back in through the other.
    start, end = ends(routed)
    assert start.y == pytest.approx(-5.0, abs=TOL)
    assert end.y == pytest.approx(-5.0, abs=TOL)
    assert 0.0 < start.x < 10.0
    assert 70.0 < end.x < 80.0


def test_an_orthogonal_route_turns_at_its_waypoints_rather_than_through_them():
    a, b = box(), box()
    places = figure(a, b.translated(80, 0))

    routed = route(link(a, b, route="orthogonal", waypoints=[Vec2(40, -30)]),
                   places)

    points = shaft(routed)
    assert Vec2(40, -30) in points
    for first, second in zip(points, points[1:]):
        assert abs(first.x - second.x) < TOL or abs(first.y - second.y) < TOL


def test_a_leg_out_of_a_waypoint_carries_on_the_way_it_came_in():
    """The corner the route already turned is not turned again at the via.

    `failed -> queued` in `examples/state_machine.py`: the waypoint is exactly
    above the source, so the first leg is vertical, and the second used to
    turn horizontal immediately -- straight through the box in the middle --
    because the target was a hair further across than it was up.
    """
    a = box().translated(26, 24)
    b = box().translated(0, -28)
    places = figure(a, b)

    routed = route(link(a, b, route="orthogonal", waypoints=[Vec2(26, 0)]),
                   places)

    points = shaft(routed)
    # One run down the corridor and one turn into the target's east face --
    # the via is collinear with both its neighbours, so it is not a corner.
    assert [(p.x, p.y) for p in points] == [(26.0, 19.0), (26.0, -28.0),
                                            (12.0, -28.0)]


def test_carrying_on_gives_way_when_it_would_run_inside_the_target():
    """The corridor ends above the box, not above the gap beside it: carrying
    on south would draw the shaft down through the box and turn at its centre.
    The arrival rule takes it back, and the route comes in on the north face.
    """
    a = box().translated(18, 0)
    b = box().translated(10, 30)
    places = figure(a, b)

    routed = route(link(a, b, route="orthogonal", waypoints=[Vec2(18, 20)]),
                   places)

    points = shaft(routed)
    assert [(p.x, p.y) for p in points] == [(18.0, 5.0), (18.0, 20.0),
                                            (10.0, 20.0), (10.0, 23.0)]
    assert ends(routed)[1] == Vec2(10.0, 25.0)      # the north face


def test_a_manhattan_leg_turns_on_the_corner_that_misses_a_shape():
    a = box().translated(40, 0)
    b = box().translated(-30, -30)
    wall = box(10, 20).translated(-30, -15)
    spec = dict(route="orthogonal", waypoints=[Vec2(0, 0)])

    clear = route_all([link(a, b, **spec)], figure(a, b)).children[0]
    blocked = route_all([link(a, b, **spec)], figure(a, b, wall)).children[0]

    # Nothing in the way: carry on west and turn down onto the target.
    assert [(p.x, p.y) for p in shaft(clear)] == [(30.0, 0.0), (-30.0, 0.0),
                                                  (-30.0, -23.0)]
    # That corner's second leg runs the length of `wall`, so the other corner
    # -- down first, then west -- takes it instead.
    assert [(p.x, p.y) for p in shaft(blocked)] == [(30.0, 0.0), (0.0, 0.0),
                                                    (0.0, -30.0), (-18.0, -30.0)]


def test_a_waypoint_may_be_an_anchor_and_moves_with_what_it_is_on():
    a, b = box(), box()
    post = box(4, 4).anchor("top", Vec2(0, -2))
    places = figure(a, b.translated(80, 0), post.translated(40, -30))

    routed = route(link(a, b, waypoints=[post.at("top")]), places)

    assert Vec2(40, -32) in shaft(routed)


def test_the_label_and_the_arrowhead_follow_the_real_polyline():
    a, b = box(), box()
    label = Diagram(prim=RectPrim(6, 3))
    places = figure(a, b.translated(80, 0))

    routed = route(link(a, b, label=label, waypoints=[Vec2(40, -40)]), places)

    # The label rides the detour, not the straight line between the boxes.
    assert routed.bbox.y0 < -30.0
    # The head is on the last leg, which arrives travelling down and right.
    tip = head_tips(routed)[0]
    assert tip.x == pytest.approx(ends(routed)[1].x, abs=TOL)


def test_a_waypoint_that_is_not_a_point_is_refused_clearly():
    a, b = box(), box()
    places = figure(a, b.translated(80, 0))

    with pytest.raises(LinkError, match="waypoint"):
        route(link(a, b, waypoints=["over there"]), places)


# -- shared trunk ---------------------------------------------------------


def test_a_fork_draws_one_stem_and_one_branch_per_leaf():
    a = box()
    b, c = box(), box()
    places = figure(a, b.translated(60, -20), c.translated(60, 20))

    routed = route(link(a, [b, c]), places)

    # Stem, rail and one drop per leaf: several subpaths, one stroke.
    assert len(subpaths(routed)) > 1
    assert len(head_tips(routed)) == 2


def test_a_fork_carries_a_head_at_every_leaf_and_none_at_the_stem():
    a = box()
    b, c = box(), box()
    places = figure(a, b.translated(60, -20), c.translated(60, 20))

    tips = head_tips(route(link(a, [b, c]), places))

    # Each branch is a straight line from the fork, so it arrives through the
    # face it actually meets -- the near horizontal one, not the leaf's centre.
    assert all(tip.x < 60.0 for tip in tips)
    assert {round(tip.y, 3) for tip in tips} == {-15.0, 15.0}


def test_a_merge_points_its_one_head_at_the_target():
    a, b = box(), box()
    c = box()
    places = figure(a.translated(0, -20), b.translated(0, 20),
                    c.translated(60, 0))

    routed = route(link([a, b], c), places)
    tips = head_tips(routed)

    assert len(tips) == 1
    assert tips[0].x == pytest.approx(50.0, abs=1.0)
    assert tips[0].y == pytest.approx(0.0, abs=TOL)


def test_a_trunk_names_one_source_and_one_target_but_attaches_to_all():
    a = box()
    b, c = box(), box()
    places = figure(a, b.translated(60, -20), c.translated(60, 20))

    routed = route(link(a, [b, c]), places)
    attached = routed.attached_to

    assert link_ends(attached) == (a.id, b.id)
    assert set(attached) == {a.id, b.id, c.id}


def test_an_empty_side_is_refused_rather_than_drawn_as_nothing():
    a = box()
    with pytest.raises(LinkError):
        Link(source=a, target=[])


# -- self-loops -----------------------------------------------------------


def test_a_self_loop_leaves_and_returns_on_the_side_it_was_given():
    a = box()
    places = figure(a)

    north = shaft(route(link(a, a, loop="n"), places))
    south = shaft(route(link(a, a, loop="s"), places))

    assert min(p.y for p in north) < -5.0      # above the box, which ends at -5
    assert max(p.y for p in south) > 5.0


def test_a_loop_picks_the_free_side_when_it_is_not_told():
    a = box()
    above = box().translated(0, -30)
    places = figure(a, above)

    routed = route_all([link(above, a), link(a, a)], places)
    loop = routed.children[1]

    # North is taken by the arrow coming in, so the arc goes somewhere else.
    assert min(p.y for p in shaft(loop)) > -8.0


def test_a_loops_size_follows_the_arrowhead_unless_it_is_given_one():
    a = box()
    places = figure(a)

    small = route(link(a, a, loop="n", arrow_size=1.0), places)
    large = route(link(a, a, loop="n", arrow_size=4.0), places)

    assert min(p.y for p in shaft(large)) < min(p.y for p in shaft(small))
    fixed = route(link(a, a, loop="n", loop_size=20.0), places)
    assert min(p.y for p in shaft(fixed)) == pytest.approx(-25.0, abs=1.0)


def test_an_unknown_loop_side_is_refused_clearly():
    a = box()
    with pytest.raises(LinkError, match="loop"):
        link(a, a, loop="north")


# -- parallel edges -------------------------------------------------------


def test_an_offset_bows_the_shaft_off_the_centre_line():
    a, b = box(), box()
    places = figure(a, b.translated(60, 0))

    straight = shaft(route(link(a, b), places))
    bowed = shaft(route(link(a, b, offset=5.0), places))

    assert max(abs(p.y) for p in straight) < 0.5
    # Positive is to the right of travel, and travel here is rightward, so the
    # bow goes down the page -- `offset` millimetres off its own chord, which
    # is not the centre line because each end is clipped along its tangent.
    middle = (bowed[0] + bowed[-1]) * 0.5
    apex = max(bowed, key=lambda point: point.y)
    assert apex.y - middle.y == pytest.approx(5.0, abs=1.0)


def test_two_opposing_edges_with_one_offset_land_on_opposite_sides():
    a, b = box(), box()
    places = figure(a, b.translated(60, 0))

    there = shaft(route(link(a, b, offset=4.0), places))
    back = shaft(route(link(b, a, offset=4.0), places))

    assert max(p.y for p in there) > 3.0
    assert min(p.y for p in back) < -3.0


def test_each_bowed_edge_carries_its_own_label_on_its_own_curve():
    a, b = box(), box()
    places = figure(a, b.translated(60, 0))
    first = link(a, b, offset=5.0, label=Diagram(prim=RectPrim(6, 3)))
    second = link(a, b, offset=-5.0, label=Diagram(prim=RectPrim(6, 3)))

    routed = route_all([first, second], places)
    plates = [n for n in routed.walk() if isinstance(n.prim, RectPrim)]

    assert len(plates) == 2
    places_out = resolve(routed)
    centres = [places_out[n.id].world.apply(Vec2(0, 0)) for n in plates]
    assert centres[1].y < 0 < centres[0].y


# -- ports ----------------------------------------------------------------


def test_a_port_slides_the_end_along_the_face_it_leaves_through():
    a, b = box(), box()
    places = figure(a, b.translated(0, 60))

    plain = ends(route(link(a, b), places))[0]
    # Both ends ported by the same amount, so the shaft stays vertical and the
    # firing ray does not lean back across the face it is leaving.
    ported = ends(route(link(a, b, port=6.0, target_port=6.0), places))[0]

    assert plain.x == pytest.approx(0.0, abs=TOL)
    assert ported.x == pytest.approx(6.0, abs=TOL)
    assert ported.y == pytest.approx(plain.y, abs=TOL)


def test_a_port_wider_than_the_face_is_clamped_rather_than_left_in_mid_air():
    a, b = box(), box()
    places = figure(a, b.translated(0, 60))

    start = ends(route(link(a, b, port=40.0), places))[0]

    assert abs(start.x) < 10.0                 # still on the 20mm-wide face
    assert start.y == pytest.approx(5.0, abs=TOL)


def test_the_two_ends_take_their_own_ports():
    a, b = box(), box()
    places = figure(a, b.translated(0, 60))

    start, end = ends(route(link(a, b, port=-4.0, target_port=4.0), places))

    # Opposite ports tilt the shaft, so each end lands a little short of its
    # own port -- but on its own side of the centre, which is the point.
    assert -4.0 <= start.x < -3.0
    assert 3.0 < end.x <= 4.0


# -- arrowheads and corners -----------------------------------------------


def test_an_arrowhead_lands_clear_of_a_rounded_corner():
    a = box(20, 10)
    b = box(20, 10, radius=2.0)
    places = figure(a, b.translated(40, 22))

    end = ends(route(link(a, b, arrow_size=2.0), places))[1]

    # Aimed at the centre, the line meets the outline on the corner arc at
    # (30.9, 17.0)-ish, where a triangle would hang half over the rounding.
    # The head is walked along the face until it has a head's length of flat.
    corner = Vec2(30.0, 17.0)
    assert (end - corner).length >= 2.0 - TOL
    assert end.x == pytest.approx(30.0, abs=TOL)     # on the flat left face


def test_a_circle_is_left_where_it_lands_because_it_has_no_corner():
    a = box(20, 10)
    b = Diagram(prim=EllipsePrim(10, 10)).translated(40, 25)
    places = figure(a, b)

    end = ends(route(link(a, b, arrow_size=2.0), places))[1]

    assert (end - Vec2(40, 25)).length == pytest.approx(10.0, abs=TOL)
