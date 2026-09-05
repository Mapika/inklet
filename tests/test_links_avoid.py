"""What `route="avoid"` does about ink, and the three ways a caller nudges it.

`test_links.py` pins the geometry of a connector against shapes. This file is
about the things a route has to notice that are not shapes: the connectors
already drawn, the plate a label reserves, a waypoint hung off an anchor, and
a theme that wants every elbow rounded.
"""

from __future__ import annotations

import dataclasses

import pytest

import inklet
from inklet.core import Diagram, Rect, RectPrim, Vec2, group, resolve
from inklet.links import CONNECTOR_KIND, Obstacle, link, route
from inklet.links.link import (
    _cuts, _drawing_cost, _shaft_crossings, _via_point,
)

TOL = 1e-6


def box(w: float = 20.0, h: float = 10.0) -> Diagram:
    return Diagram(prim=RectPrim(w, h))


def shaft(routed: Diagram) -> list[Vec2]:
    places = resolve(routed)
    for node in routed.walk():
        if node.kind == CONNECTOR_KIND:
            return [places[node.id].world.apply(p)
                    for p in node.prim.subpaths[0].points]
    raise AssertionError("no connector in the routed link")


def loop_side(page: Diagram, places, node: Diagram) -> str:
    """Which way the last connector on the page leaves `node`."""
    centre = places[node.id].envelope.bbox().center
    last = [n for n in page.walk() if n.kind == CONNECTOR_KIND][-1]
    points = [places[last.id].world.apply(p)
              for sub in last.prim.subpaths for p in sub.points]
    dx = sum(p.x for p in points) / len(points) - centre.x
    dy = sum(p.y for p in points) / len(points) - centre.y
    if dy < -abs(dx):
        return "n"
    if dy > abs(dx):
        return "s"
    return "e" if dx > 0 else "w"


# -- crossing arithmetic --------------------------------------------------


def test_two_shafts_that_only_touch_are_not_a_crossing():
    a, b = Vec2(0, 0), Vec2(10, 0)
    through = (Vec2(5, -5), Vec2(5, 5))
    meeting = (Vec2(10, 0), Vec2(10, 10))     # end to end at a shared port
    turning = (Vec2(5, 0), Vec2(5, 10))       # a T, not an X
    assert _cuts(a, b, *through)
    assert not _cuts(a, b, *meeting)
    assert not _cuts(a, b, *turning)


def test_a_polylines_crossings_are_counted_once_each():
    line = [Vec2(0, 0), Vec2(0, 20), Vec2(20, 20)]
    drawn = [(Vec2(-5, 10), Vec2(5, 10)), (Vec2(10, 15), Vec2(10, 25))]
    assert _shaft_crossings(line, drawn) == 2
    assert _shaft_crossings(line, []) == 0


def test_drawing_cost_charges_the_corners():
    straight = [Vec2(0, 0), Vec2(10, 0)]
    bent = [Vec2(0, 0), Vec2(5, 0), Vec2(5, 5)]
    assert _drawing_cost(straight) == pytest.approx(10.0)
    assert _drawing_cost(bent) == pytest.approx(10.0 + 6.0)


# -- avoid, against ink rather than shapes --------------------------------


def _pair() -> tuple[Diagram, Diagram, dict]:
    src = box().translated(0, 0)
    dst = box().translated(80, 30)
    return src, dst, resolve(group([src, dst]))


def test_avoid_draws_the_plain_elbow_when_nothing_is_in_the_way():
    src, dst, places = _pair()
    spec = link(src, dst, route="avoid", kind="line")
    plain = link(src, dst, route="orthogonal", kind="line")
    assert shaft(route(spec, places)) == shaft(route(plain, places))


def test_avoid_steps_off_a_drawn_shaft_when_the_corridor_is_free():
    """The elbow clears every shape, so `avoid` would normally stop there.

    It crosses a connector already on the page, though, and the lattice can
    reach the target for the same money -- one bend instead of two, five
    millimetres longer, which is the trade `_TURN_COST` says is even. Taking
    it is the whole point: the crossing was avoidable and nothing was spent.
    """
    src, dst, places = _pair()
    spec = link(src, dst, route="avoid", kind="line")
    obstacles = (Obstacle("aside", Rect(45, 40, 65, 50)),)
    drawn = [(Vec2(30, 15), Vec2(50, 15))]

    elbow = shaft(route(spec, places, obstacles))
    stepped = shaft(route(spec, places, obstacles, drawn))
    assert _shaft_crossings(elbow, drawn) == 1
    assert _shaft_crossings(stepped, drawn) == 0
    assert _drawing_cost(stepped) <= _drawing_cost(elbow) + TOL


def test_avoid_keeps_the_elbow_when_the_detour_would_cost_more():
    """A crossing that cannot be undone for free is left alone: `avoid` is
    about shapes, and a longer route is a worse drawing than a clean X."""
    src, dst, places = _pair()
    spec = link(src, dst, route="avoid", kind="line")
    # A shaft long enough that every corridor between the two boxes meets it.
    drawn = [(Vec2(-40, 15), Vec2(120, 15))]
    assert shaft(route(spec, places, (), drawn)) == shaft(route(spec, places))


# -- the plate a label reserves -------------------------------------------


def _loop_page(labelled: bool) -> tuple[Diagram, dict, Diagram]:
    left, right, node = inklet.box("left"), inklet.box("right"), inklet.box("a")
    fig = inklet.figure(width=120)
    fig.add(inklet.vstack([inklet.hstack([left, right], gap=40), node], gap=9))
    if labelled:
        # Pushed down off its own shaft, onto the paper the loop wants.
        fig.link(left, right, label="reset", label_offset=-8)
    else:
        fig.link(left, right)
    fig.link(node, node, label="tick")
    page, places = fig.build()
    return page, places, node


def test_a_loop_takes_another_side_rather_than_land_on_a_label():
    """Loop sides are decided before labels are placed, so the second pass
    reserves every plate: a side that was empty when the loop was routed and
    carries a word by the time it is drawn is not an empty side."""
    plain, plain_places, node = _loop_page(labelled=False)
    assert loop_side(plain, plain_places, node) == "n"

    busy, busy_places, node = _loop_page(labelled=True)
    assert loop_side(busy, busy_places, node) == "e"


# -- waypoints and the theme ----------------------------------------------


def test_a_waypoint_can_be_an_anchor_with_an_offset():
    """An anchor says *which* shape the detour hangs off; the two numbers say
    how far clear of it, in millimetres, so the corridor survives the shape
    being resized or moved."""
    src, dst, places = _pair()
    here = _via_point(dst.at("n"), places)
    clear = _via_point((dst.at("n"), 4.0, -6.0), places)
    assert (clear.x, clear.y) == pytest.approx((here.x + 4.0, here.y - 6.0))

    # And it reaches the router the same way a bare anchor does.
    spec = link(src, dst, route="orthogonal", kind="line",
                waypoints=[(dst.at("n"), 0.0, -6.0)])
    assert min(p.y for p in shaft(route(spec, places))) < here.y


def test_a_bad_waypoint_says_what_it_wanted():
    src, dst, places = _pair()
    spec = link(src, dst, waypoints=[(1.0, 2.0, 3.0, 4.0)])
    with pytest.raises(Exception, match="waypoint"):
        route(spec, places)


def test_a_theme_can_round_every_elbow_at_once():
    rounded = dataclasses.replace(inklet.theme("nature"), link_radius=1.5)
    a, b = inklet.box("a"), inklet.box("b")
    fig = inklet.figure(width=90, theme=rounded)
    fig.add(inklet.hstack([a, b], gap=40))
    assert fig.link(a, b, route="orthogonal", waypoints=[(0, -14)]).corner == 1.5


def test_an_explicit_corner_beats_the_theme():
    rounded = dataclasses.replace(inklet.theme("nature"), link_radius=1.5)
    a, b = inklet.box("a"), inklet.box("b")
    fig = inklet.figure(width=90, theme=rounded)
    fig.add(inklet.hstack([a, b], gap=40))
    assert fig.link(a, b, route="orthogonal", corner=0).corner == 0
    assert fig.link(b, a, route="orthogonal", corner_radius=3).corner == 3


def test_the_default_theme_still_draws_square_corners():
    assert inklet.theme("nature").link_radius == 0.0
    a, b = inklet.box("a"), inklet.box("b")
    fig = inklet.figure(width=90)
    fig.add(inklet.hstack([a, b], gap=40))
    assert fig.link(a, b, route="orthogonal").corner == 0.0
