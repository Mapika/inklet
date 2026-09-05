"""inklet.plot.polar: the angle map, the notes it publishes, and mark geometry.

Three things are worth pinning here and the rest follows from them. The
mapping from a data angle to a page angle, because `zero` x `winding` x `unit`
is the one part of a polar plot every library gets subtly differently and a
figure built on the wrong one is wrong without looking wrong. The two notes,
because `inklet.row`, `inklet.letters`, `OFF_PANEL` and `KEY_MISMATCH` all read them
and none of them knows this module exists. And the marks' geometry, measured
on the page through `resolve()` the way `test_plot_axis` does, because a rose
wedge that is half a degree out is a rose wedge nobody can see is out.
"""

from __future__ import annotations

import math

import pytest

from inklet.core import DiagramError, Rect, Vec2, resolve
from inklet.draw.coords import as_drawn, plot_area
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import (
    PolarPanel, Theta, circular_histogram, circular_mean, polar, theta_ticks,
)
from inklet.plot.axis import AXIS_KIND, SPINE_KIND, TICK_KIND, TICK_LABEL_KIND
from inklet.plot.panel import PANEL_KIND


def placements(node, kind: str):
    """Every placed node of one kind, in tree order."""
    return [p for p in resolve(as_drawn(node)).values() if p.diagram.kind == kind]


def boxes(node, kind: str) -> list[Rect]:
    return [p.bbox for p in placements(node, kind)]


def texts(node, kind: str = TICK_LABEL_KIND) -> list[str]:
    out = []
    for p in placements(node, kind):
        content = getattr(p.diagram.prim, "text", None)
        if content:
            out.append(content)
    return out


# --- the angle map -----------------------------------------------------------


def test_zero_direction_and_winding_are_independent() -> None:
    """The four combinations a field can ask for, on the page.

    Page degrees are the library's: 0 due east, increasing clockwise because y
    grows downward. So `zero="up"` is -90, and a quarter turn of *data* from
    there lands at 0 (east) going clockwise and at 180 (west) going
    anticlockwise.
    """
    assert polar(10, zero="east", winding="cw").angle(90) == pytest.approx(90)
    assert polar(10, zero="east", winding="ccw").angle(90) == pytest.approx(-90)
    assert polar(10, zero="up", winding="cw").angle(90) == pytest.approx(0)
    assert abs(polar(10, zero="up", winding="ccw").angle(90)) == pytest.approx(180)


def test_zero_may_be_a_number_of_page_degrees() -> None:
    """`zero="up"` and `zero=-90` are the same instruction, said twice."""
    assert polar(10, zero=-90).angle(0) == polar(10, zero="up").angle(0)
    assert polar(10, zero=30, winding="cw").angle(15) == pytest.approx(45)


@pytest.mark.parametrize("unit,quarter", [
    ("deg", 90.0), ("rad", math.pi / 2), ("turn", 0.25), ("grad", 100.0),
])
def test_a_quarter_turn_is_a_quarter_turn_in_every_unit(unit, quarter) -> None:
    p = polar(10, theta=(0, quarter * 4), unit=unit, winding="cw")
    assert p.angle(quarter) == pytest.approx(90.0)


def test_page_and_unpage_are_inverses() -> None:
    theta = Theta(domain=(0.0, 360.0), zero=-90.0, winding="cw")
    for value in (0.0, 17.5, 123.0, 359.9):
        assert theta.unpage(theta.page(value)) == pytest.approx(value)


def test_an_unknown_zero_direction_is_refused() -> None:
    with pytest.raises(DiagramError):
        polar(10, zero="northwest")


def test_an_unknown_winding_is_refused() -> None:
    with pytest.raises(DiagramError):
        polar(10, winding="widdershins")


def test_point_puts_r_along_the_mapped_angle() -> None:
    p = polar(20, r=(0, 10), zero="up", winding="cw")
    def xy(theta, r):
        point = p.point(theta, r)
        return (point.x, point.y)

    assert xy(0, 10) == pytest.approx((0.0, -20.0), abs=1e-9)   # straight up
    assert xy(90, 10) == pytest.approx((20.0, 0.0), abs=1e-9)   # a quarter round
    assert xy(0, 5) == pytest.approx((0.0, -10.0), abs=1e-9)    # half the radius


def test_the_pole_is_the_panels_own_origin() -> None:
    assert polar(20).centre == Vec2(0, 0)


def test_a_built_polar_panel_is_a_panel_to_everything_downstream() -> None:
    """It is not a `Panel` subclass, and it must not need to be: what the
    plot rules, `letters` and the OFF_PANEL exemptions read is the kind and
    the notes on the built node."""
    p = polar(20, r=(0, 10))
    assert isinstance(p, PolarPanel)
    assert p.build().kind == PANEL_KIND


# --- the angular tick lattice ------------------------------------------------


def test_degree_ticks_land_on_divisors_of_the_turn() -> None:
    assert theta_ticks(0, 360, 8) == (0, 45, 90, 135, 180, 225, 270, 315)
    assert theta_ticks(0, 360, 4) == (0, 90, 180, 270)
    assert theta_ticks(0, 360, 12) == tuple(range(0, 360, 30))


def test_a_whole_turn_does_not_label_the_same_spoke_twice() -> None:
    """360 and 0 are one tick; `closed=True` is for a fan that really ends."""
    assert 360 not in theta_ticks(0, 360, 8)
    assert theta_ticks(0, 180, 4, closed=True)[-1] == 180


def test_radian_ticks_are_written_as_fractions_of_pi() -> None:
    theta = Theta(domain=(0.0, 2 * math.pi), unit="rad")
    labels = theta.labels(theta.ticks(8))
    assert labels[0] == "0"
    assert "π/4" in labels
    assert "π" in labels
    assert "3π/2" in labels
    assert not any("1.57" in text for text in labels)


def test_a_lattice_step_is_never_a_decimal_slice_of_a_turn() -> None:
    """The point of the lattice: 0, 50, 100 is what `nice_ticks` would give."""
    for count in (3, 5, 6, 7, 9, 11):
        steps = {round(b - a, 9) for a, b
                 in zip(theta_ticks(0, 360, count), theta_ticks(0, 360, count)[1:])}
        assert len(steps) == 1
        assert 360.0 % steps.pop() == pytest.approx(0.0, abs=1e-9)


# --- the notes ---------------------------------------------------------------


def test_a_built_panel_declares_its_plot_area() -> None:
    """`inklet.row`, `inklet.letters` and OFF_PANEL all read this and nothing else."""
    node = polar(20, r=(0, 10)).grid().theta_axis().r_axis().build()
    area = plot_area(node)
    assert area is not None
    assert area.width == pytest.approx(40.0)
    assert area.height == pytest.approx(40.0)


def test_a_fans_declared_area_is_the_wedge_not_the_square() -> None:
    """A half disc opening downward is half as tall as the square on its rim.

    Zero is due east and the winding is clockwise, so a 0..180 fan sweeps the
    lower half of the page: 40mm across, 20mm down. Declaring the square would
    hang the panel letter a centimetre above the ink.
    """
    p = polar(20, theta=(0, 180), winding="cw")
    assert p.area.width == pytest.approx(40.0)
    assert p.area.height == pytest.approx(20.0)


def test_a_built_panel_declares_its_r_domain() -> None:
    node = polar(20, r=(0, 42)).build()
    assert node.notes["scale_domain"] == pytest.approx((0.0, 42.0))


def test_the_area_moves_with_the_node_it_is_declared_on() -> None:
    """`plot_area` reads through `transform`; the raw note does not."""
    node = polar(20, r=(0, 10)).theta_axis().build()
    here = plot_area(node)
    there = plot_area(node.translated(7, -3))
    assert there.x0 - here.x0 == pytest.approx(7.0)
    assert there.y0 - here.y0 == pytest.approx(-3.0)


# --- furniture ---------------------------------------------------------------


def test_the_theta_axis_is_furniture_so_off_panel_stays_quiet() -> None:
    """OFF_PANEL exempts AXIS_KIND, which is why the rim labels are wrapped."""
    node = polar(18, r=(0, 10)).grid().theta_axis(count=8).r_axis(count=2).build()
    assert placements(node, AXIS_KIND)
    assert not [d for d in _figure(node).lint() if d.code == "OFF_PANEL"]


def test_every_theta_label_clears_the_rim_by_the_same_margin() -> None:
    """The whole point of `_outward`: one offset, not one circle.

    A compass anchor quantises the push-out direction to eight ways; the exact
    continuous form gives every label of a twelve-tick ring the same clearance
    from the tick it belongs to, whatever its shape.
    """
    radius = 20.0
    node = polar(radius, r=(0, 10)).theta_axis(count=12, thin=False).build()
    gaps = []
    for box in boxes(node, TICK_LABEL_KIND):
        centre = box.center
        towards = math.degrees(math.atan2(centre.y, centre.x))
        reach = _outward_reach(box, towards)
        gaps.append(math.hypot(centre.x, centre.y) - reach - radius)
    assert len(gaps) == 12
    assert max(gaps) - min(gaps) < 0.01


def test_the_ticks_stay_when_the_labels_thin() -> None:
    """A circle is a clock face: 24 marks, 12 numbers, and the rhythm holds."""
    node = polar(9, r=(0, 10)).theta_axis(count=24).build()
    assert len(placements(node, TICK_KIND)) == 24
    assert len(texts(node)) < 24


def test_thinning_keeps_a_stride_that_divides_the_ring() -> None:
    """Otherwise the wrap-around pair collides at the top of the plot."""
    node = polar(7, r=(0, 10)).theta_axis(count=12).build()
    kept = [t for t in texts(node) if t.endswith("°")]
    steps = {round(float(b[:-1]) - float(a[:-1]), 6)
             for a, b in zip(kept, kept[1:])}
    assert len(steps) == 1
    assert 360.0 % steps.pop() == pytest.approx(0.0, abs=1e-9)


def test_the_rim_is_the_theta_axiss_spine() -> None:
    assert placements(polar(20).theta_axis().build(), SPINE_KIND)
    assert not placements(polar(20).theta_axis(spine=False).build(), SPINE_KIND)


def test_the_default_r_axis_bisects_the_widest_gap_between_spokes() -> None:
    """At twelve ticks the fixed 22.5 degrees sat 7.5 off the `30` label."""
    p = polar(20, r=(0, 10), winding="cw")
    p.theta_axis(count=12)
    assert p._quiet_spoke() == pytest.approx(15.0)
    q = polar(20, r=(0, 10), winding="cw")
    q.theta_axis(count=8)
    assert q._quiet_spoke() == pytest.approx(22.5)
    # And it follows the winding, so "first gap round from zero" means the
    # same thing to a compass figure and a mathematical one.
    a = polar(20, r=(0, 10), winding="ccw")
    a.theta_axis(count=12)
    assert a._quiet_spoke() == pytest.approx(-15.0)


def test_a_fan_puts_its_r_axis_at_the_start_of_the_view() -> None:
    p = polar(20, r=(0, 10), theta=(0, 180), winding="cw")
    p.theta_axis(count=6)
    assert p._quiet_spoke() == pytest.approx(p.angle(0))


def test_no_r_tick_is_drawn_at_the_pole() -> None:
    """A tick at r=0 is a mark on the middle of the plot, where data goes."""
    node = polar(20, r=(0, 10)).r_axis(count=2).build()
    assert "0" not in texts(node)


# --- marks -------------------------------------------------------------------


def test_a_polar_line_is_interpolated_along_arcs_not_chords() -> None:
    """Twelve samples round a circle must not come out a dodecagon."""
    node = polar(20, r=(0, 10)).line([(a, 10) for a in range(0, 360, 30)],
                                     closed=True).build()
    points = _points(node, MARK_LINE_KIND)
    assert len(points) > 60
    assert max(abs(math.hypot(p.x, p.y) - 20.0) for p in points) < 0.2


def test_interpolation_can_be_turned_off() -> None:
    node = polar(20, r=(0, 10)).line([(a, 10) for a in range(0, 360, 30)],
                                     closed=True, interpolate=False).build()
    points = _points(node, MARK_LINE_KIND)
    assert len(points) <= 13


def test_a_rose_wedge_spans_its_own_bin() -> None:
    """Four bars over a whole turn are quadrants; `width` shrinks each one."""
    p = polar(20, r=(0, 4))
    node = p.rose([1, 2, 3, 4]).build()
    wedges = placements(node, MARK_KIND)
    assert len(wedges) == 4
    reach = [max(math.hypot(v.x, v.y) for v in _hull(w)) for w in wedges]
    assert reach == pytest.approx([5.0, 10.0, 15.0, 20.0], abs=0.2)


def test_a_narrow_rose_leaves_paper_between_the_petals() -> None:
    wide = _span(polar(20, r=(0, 4)).rose([1, 2, 3, 4], width=1.0).build())
    thin = _span(polar(20, r=(0, 4)).rose([1, 2, 3, 4], width=0.5).build())
    assert thin < wide / 1.8


def test_a_rose_refuses_a_mismatched_at() -> None:
    with pytest.raises(DiagramError):
        polar(20, r=(0, 4)).rose([1, 2, 3], at=[0, 90])


def test_a_lone_rose_is_a_tint_of_the_ink_not_palette_colour_zero() -> None:
    """Palette 0 is black in the print theme, and sixteen black wedges
    meeting at a point is a wall with a hole in it."""
    node = polar(20, r=(0, 4)).rose([1, 2, 3, 4]).build()
    fills = {p.diagram.style.fill for p in placements(node, MARK_KIND)}
    assert fills != {"#000000"}
    assert len(fills) == 1


def test_the_mean_vector_length_carries_the_resultant() -> None:
    """R = 1 reaches the rim; a half-concentrated sample reaches halfway."""
    radius = 20.0
    node = polar(radius, r=(0, 10)).mean_vector([90, 90, 90]).build()
    ink = _points(node, MARK_LINE_KIND) + _points(node, "arrowhead")
    tip = max(ink, key=lambda v: math.hypot(v.x, v.y))
    assert math.hypot(tip.x, tip.y) == pytest.approx(radius, abs=0.05)
    half = polar(radius, r=(0, 10)).mean_vector([0, 120], order=1).build()
    reach = max(math.hypot(v.x, v.y) for v in _points(half, "arrowhead"))
    assert reach == pytest.approx(radius * 0.5, abs=0.05)


def test_a_resultant_too_short_for_a_head_is_drawn_as_a_dot() -> None:
    """An arrow shorter than its own triangle reads as a large resultant
    pointing nowhere, which is the opposite of what the data says."""
    node = polar(20, r=(0, 10)).mean_vector([0, 90, 180, 270]).build()
    assert not _points(node, MARK_LINE_KIND)
    assert placements(node, MARK_KIND)


def test_a_mean_vector_is_data_ink_not_a_routed_link() -> None:
    """An arrow from the pole must cross any band that rings the pole, so a
    routed one would earn a structural LINK_CROSSES on every such figure."""
    p = polar(20, r=(0, 10))
    p.band([0, 90, 180, 270], [2, 2, 2, 2], [4, 4, 4, 4], closed=True)
    p.mean_vector([80, 90, 100])
    found = _figure(p.build()).lint()
    assert not [d for d in found if d.code in ("LINK_CROSSES", "PATH_CROSSES")]


# --- circular statistics -----------------------------------------------------


def test_the_circular_mean_of_359_and_1_is_zero() -> None:
    """The reason the function exists: the arithmetic mean is 180."""
    mean, resultant = circular_mean([359.0, 1.0])
    assert mean == pytest.approx(0.0, abs=1e-9)
    assert resultant == pytest.approx(math.cos(math.radians(1.0)))


def test_a_uniform_sample_has_no_mean_direction() -> None:
    _mean, resultant = circular_mean([0, 90, 180, 270])
    assert resultant == pytest.approx(0.0, abs=1e-12)


def test_order_two_is_the_orientation_statistic() -> None:
    """A cell answering equally at 90 and 270 is perfectly oriented and has
    no direction: order 1 says R = 0, order 2 says R = 1."""
    sample = [90.0, 270.0]
    assert circular_mean(sample, order=1)[1] == pytest.approx(0.0, abs=1e-12)
    mean, resultant = circular_mean(sample, order=2)
    assert resultant == pytest.approx(1.0)
    assert mean == pytest.approx(90.0)


def test_weights_make_it_the_mean_of_a_histogram() -> None:
    centres = [0.0, 90.0, 180.0, 270.0]
    mean, resultant = circular_mean(centres, [10.0, 1.0, 0.0, 1.0])
    assert mean == pytest.approx(0.0, abs=1e-9)
    assert 0.0 < resultant < 1.0


def test_a_circular_histogram_wraps_and_a_fan_does_not() -> None:
    centres, counts = circular_histogram([1.0, 359.0], bins=4)
    assert centres == pytest.approx((45.0, 135.0, 225.0, 315.0))
    assert counts == pytest.approx((1.0, 0.0, 0.0, 1.0))
    _c, kept = circular_histogram([1.0, 359.0], bins=4, domain=(0, 180))
    assert sum(kept) == 1.0


def test_density_divides_by_the_sample_count() -> None:
    _c, counts = circular_histogram([1.0, 2.0, 3.0, 200.0], bins=2, density=True)
    assert sum(counts) == pytest.approx(1.0)


def test_circular_helpers_refuse_an_unknown_unit() -> None:
    with pytest.raises(DiagramError):
        circular_mean([1.0], unit="furlongs")
    with pytest.raises(DiagramError):
        circular_histogram([1.0], unit="furlongs")


# --- curved labels -----------------------------------------------------------


def test_curved_labels_keep_the_thinning_of_upright_ones() -> None:
    """Turning curving on rotates the numbers; it never relabels the axis."""
    straight = texts(polar(9, r=(0, 10)).theta_axis(count=24).build())
    # A curved run is one `glyphs` child per shaping cluster, so the string
    # comes back in pieces; the ring it spells out is the assertion.
    curved = texts(polar(9, r=(0, 10)).theta_axis(count=24, curved=True).build(),
                   "glyphs")
    assert "".join(curved) == "".join(straight)
    assert len(curved) > len(straight)


def test_curved_labels_start_where_upright_ones_would() -> None:
    """`gap=0` on `text_on_arc`, with the tick and pad already in the radius,
    so the switch does not move the ring in or out."""
    radius = 20.0
    upright = polar(radius, r=(0, 10)).theta_axis(count=4, thin=False).build()
    curved = polar(radius, r=(0, 10)).theta_axis(count=4, thin=False,
                                                 curved=True).build()
    near = [min(math.hypot(c.x, c.y)
                for c in (Vec2(b.x0, b.y0), Vec2(b.x1, b.y0),
                          Vec2(b.x0, b.y1), Vec2(b.x1, b.y1)))
            for b in boxes(upright, TICK_LABEL_KIND)]
    also = [min(math.hypot(c.x, c.y)
                for c in (Vec2(b.x0, b.y0), Vec2(b.x1, b.y0),
                          Vec2(b.x0, b.y1), Vec2(b.x1, b.y1)))
            for b in boxes(curved, TICK_LABEL_KIND)]
    assert min(also) > radius
    assert abs(min(also) - min(near)) < 1.0


# --- determinism -------------------------------------------------------------


def test_the_same_panel_lands_in_the_same_places_twice() -> None:
    """Node ids count up per process, so the geometry is what is compared --
    the same thing the corpus proof compares between two worktrees."""
    def draw() -> str:
        p = polar(18, r=(0, 10), zero="up", winding="cw")
        p.grid(r_count=3, theta_count=8)
        p.line([(a, 3 + (a % 120) / 30) for a in range(0, 360, 15)])
        p.rose([1, 4, 2, 6, 3, 5], name="cells")
        p.mean_vector(range(0, 360, 15), [1, 4, 2, 6, 3, 5] * 4)
        p.theta_axis(count=8, label="direction").r_axis(count=3, label="rate")
        node = p.build()
        placed = resolve(as_drawn(node))
        return repr([(item.diagram.kind, round(item.bbox.x0, 9),
                      round(item.bbox.y0, 9), round(item.bbox.x1, 9),
                      round(item.bbox.y1, 9))
                     for item in placed.values()])

    assert draw() == draw()


# --- helpers -----------------------------------------------------------------


def _figure(node):
    import inklet

    fig = inklet.figure(width=90)
    fig.add(node)
    return fig


def _outward_reach(box: Rect, degrees: float) -> float:
    """The distance from a box's centre to its boundary in one direction."""
    ux, uy = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    reaches = []
    if abs(ux) > 1e-12:
        reaches.append(box.width / 2.0 / abs(ux))
    if abs(uy) > 1e-12:
        reaches.append(box.height / 2.0 / abs(uy))
    return min(reaches) if reaches else 0.0


def _points(node, kind: str) -> list[Vec2]:
    out: list[Vec2] = []
    for placed in placements(node, kind):
        prim = placed.diagram.prim
        for sub in getattr(prim, "subpaths", ()):
            out.extend(placed.world.apply(p) for p in sub.points)
    return out


def _hull(placed) -> list[Vec2]:
    out: list[Vec2] = []
    for sub in getattr(placed.diagram.prim, "subpaths", ()):
        out.extend(placed.world.apply(p) for p in sub.points)
    return out


def _span(node) -> float:
    """The angular width of the first rose wedge, in degrees."""
    wedge = placements(node, MARK_KIND)[0]
    angles = [math.degrees(math.atan2(v.y, v.x)) for v in _hull(wedge)
              if math.hypot(v.x, v.y) > 1e-6]
    return max(angles) - min(angles)
