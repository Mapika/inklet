"""The Sankey ribbon, and the property that makes it honest.

A ribbon's width is a measurement. If the two long edges are eased
independently the band pinches or bulges in the middle and the width stops
being the number it claims to be, which is the bug this shape exists to avoid
and the only thing here worth testing hard.
"""

from __future__ import annotations

import pytest

import inklet
from inklet import Vec2
from inklet.plot.ribbon import (
    RIBBON_EASE, eased_cubic, panel_ribbon, ribbon, ribbon_between,
    ribbon_cubics,
)


def bezier(cubic, t: float) -> Vec2:
    p0, c1, c2, p3 = cubic
    u = 1.0 - t
    return (p0 * (u ** 3) + c1 * (3 * u * u * t)
            + c2 * (3 * u * t * t) + p3 * (t ** 3))


# -- geometry -------------------------------------------------------------


def test_the_band_never_pinches_between_its_two_end_widths():
    """Both edges share one ease, so the width only ever eases between them.

    This is the property the shape exists for. Ease the two edges separately
    and the band is 8mm at one end and 2mm at the other and something else
    entirely in the middle, which is a lie about the flux.
    """
    chain = ribbon_cubics((0.0, -4.0), (0.0, 4.0), (40.0, -1.0), (40.0, 1.0))
    top, _, bottom, _ = chain
    widths = []
    for step in range(21):
        t = step / 20.0
        # The second eased edge runs from b1 back to a1, so it is reversed.
        here, there = bezier(top, t), bezier(bottom, 1.0 - t)
        assert here.x == pytest.approx(there.x, abs=1e-9)   # square to the flow
        widths.append((there - here).length)

    assert widths[0] == pytest.approx(8.0)
    assert widths[-1] == pytest.approx(2.0)
    assert all(2.0 - 1e-9 <= w <= 8.0 + 1e-9 for w in widths)
    assert all(b <= a + 1e-9 for a, b in zip(widths, widths[1:]))


def test_the_flow_direction_is_the_end_faces_normal_by_default():
    """Vertical faces flow horizontally; horizontal faces flow vertically."""
    across = ribbon_cubics((0.0, -2.0), (0.0, 2.0), (30.0, -2.0), (30.0, 2.0))
    # The first control point leaves along +x by ease * the projected span.
    assert across[0][1].y == pytest.approx(-2.0)
    assert across[0][1].x == pytest.approx(30.0 * RIBBON_EASE)

    down = ribbon_cubics((-2.0, 0.0), (2.0, 0.0), (-2.0, 30.0), (2.0, 30.0))
    assert down[0][1].x == pytest.approx(-2.0)
    assert down[0][1].y == pytest.approx(30.0 * RIBBON_EASE)


def test_the_outline_is_one_closed_chain():
    node = ribbon_between((0, 0), (0, 6), (30, 2), (30, 5))
    sub = node.prim.subpaths[0]
    assert sub.closed and len(sub.curves) == 4
    for a, b in zip(sub.curves, sub.curves[1:]):
        assert a[3] == b[0]
    assert sub.curves[-1][3] == sub.curves[0][0]


def test_centres_and_widths_give_the_same_band_as_the_corners():
    by_corner = ribbon_between((0, -3), (0, 3), (40, -1), (40, 1))
    by_width = ribbon((0, 0), (40, 0), width0=6.0, width1=2.0)
    assert by_corner.bbox.width == pytest.approx(by_width.bbox.width)
    assert by_corner.bbox.height == pytest.approx(by_width.bbox.height)


def test_alignment_holds_one_edge_of_the_flow_straight():
    node = ribbon((0, 0), (30, 0), width0=8.0, width1=2.0, align="start")
    box = node.bbox
    # Aligned at the start edge, the band only ever grows downward from it.
    assert box.height == pytest.approx(8.0)
    assert node.prim.subpaths[0].curves[0][0].y == pytest.approx(box.y0)


def test_a_constant_width_ribbon_defaults_to_the_first_width():
    node = ribbon((0, 0), (20, 0), width0=5.0)
    assert node.bbox.height == pytest.approx(5.0)


def test_a_ribbon_is_a_mark_because_its_width_is_data():
    assert ribbon((0, 0), (20, 0), width0=4.0).kind == "mark"


def test_an_unknown_alignment_is_refused():
    with pytest.raises(ValueError, match="unknown ribbon align"):
        ribbon((0, 0), (1, 0), width0=1.0, align="middle")


def test_a_taper_to_nothing_still_draws():
    node = ribbon_between((0, 0), (0, 0), (20, -2), (20, 2))
    assert node.bbox.width == pytest.approx(20.0)


def test_eased_cubic_leaves_and_arrives_along_the_flow():
    p0, c1, c2, p3 = eased_cubic(Vec2(0, 0), Vec2(10, 6), Vec2(1, 0), 0.5)
    assert (c1 - p0).normalized() == Vec2(1.0, 0.0)
    assert (p3 - c2).normalized() == Vec2(1.0, 0.0)


# -- in a panel -----------------------------------------------------------


def test_a_panel_ribbon_measures_its_width_through_the_scale():
    p = inklet.panel(60, 40, x=(0, 10), y=(0, 100))
    node = panel_ribbon(p, (1, 50), (9, 50), width0=20, width1=10)
    # 20 of 100 data units over 40mm of area.
    assert node.bbox.height == pytest.approx(8.0)


def test_a_panel_ribbon_on_a_log_axis_measures_where_the_data_is():
    """The same 18 units of width is 12.8mm low down and 0.016mm high up."""
    p = inklet.panel(60, 40, x=(0, 10), y=inklet.log((1, 10000)))
    low = panel_ribbon(p, (1, 10), (9, 10), width0=18)
    high = panel_ribbon(p, (1, 5000), (9, 5000), width0=18)
    assert low.bbox.height == pytest.approx(12.79, abs=0.01)
    assert high.bbox.height == pytest.approx(0.0156, abs=0.001)


def test_a_panel_ribbon_lands_in_the_panel():
    p = inklet.panel(60, 40, x=(0, 10), y=(0, 100))
    p.draw(panel_ribbon(p, (1, 50), (9, 50), width0=20))
    built = p.build()
    assert built.bbox.width <= 60.0 + 1e-9


# -- the stress modules it replaces ---------------------------------------


def test_it_reproduces_the_hand_rolled_ribbon_in_stress_relations():
    """The copy in `stress/panels/relations.py`, argument for argument."""
    def straight(p0, p3):
        step = (p3 - p0) * (1.0 / 3.0)
        return (p0, p0 + step, p0 + step * 2.0, p3)

    def eased(p0, p3, along, tension):
        reach = (p3 - p0).dot(along) * tension
        return (p0, p0 + along * reach, p3 - along * reach, p3)

    a0, a1 = Vec2(-20.0, -8.0), Vec2(-4.0, -8.0)
    b0, b1 = Vec2(-20.0, 9.0), Vec2(-9.0, 9.0)
    along = Vec2(0.0, 1.0)
    expected = (eased(a0, b0, along, 0.55), straight(b0, b1),
                eased(b1, a1, along, 0.55), straight(a1, a0))
    assert ribbon_cubics(a0, a1, b0, b1) == expected
    assert ribbon_cubics(a0, a1, b0, b1, along, 0.55) == expected


def test_panel_ribbon_through_the_panel_chains():
    """`Panel.draw` puts the band back in data coordinates, so x=1..9 lands."""
    p = inklet.panel(60, 40, x=(0, 10), y=(0, 100))
    assert p.ribbon((1, 50), (9, 50), width0=20, width1=10) is p
    box = p.build().bbox
    assert box.x0 == pytest.approx(-24.0)
    assert box.x1 == pytest.approx(24.0)


def test_it_reproduces_the_hand_rolled_ribbon_in_stress_electro():
    """The copy in `stress/electro/system.py`: flow pinned along +x."""
    a0, a1 = Vec2(4.0, -6.0), Vec2(4.0, 2.0)
    b0, b1 = Vec2(40.0, -3.0), Vec2(40.0, 1.0)
    node = ribbon_between(a0, a1, b0, b1, along=Vec2(1.0, 0.0), ease=0.55)
    assert node.kind == "mark"
    # `path` recentres on the local origin, so read the geometry back through
    # the origin anchor that records where the author's (0, 0) went.
    shift = node.anchor_point("origin")
    drawn = tuple(tuple(pt - shift for pt in curve)
                  for curve in node.prim.subpaths[0].curves)
    assert drawn == ribbon_cubics(a0, a1, b0, b1, Vec2(1.0, 0.0), 0.55)
