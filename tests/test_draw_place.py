"""`place`, and the frame that several `place` calls do or do not share.

The bug this file pins down: an author draws one picture in one set of
coordinates but builds it with three `place` calls -- the geometry, the labels
hung off its east side, the labels hung off its west side -- and each call
silently recentres on its own bounding box, so the three come out in three
different frames. Nothing raises. The figure is just wrong.
"""

from __future__ import annotations

import pytest

import inklet
from inklet import Vec2


def dot(at) -> tuple:
    return (at, inklet.marker("circle", 1.0))


def geometry() -> list:
    return [dot((-10, 0)), dot((10, 0))]


# -- the bug ---------------------------------------------------------------


def test_separate_place_calls_land_in_separate_frames():
    """The reproduction. Three calls, three frames, no complaint from anyone."""
    shapes = inklet.place(geometry())
    west = inklet.place([((-10, 0), inklet.text("in"))], anchor="e")
    east = inklet.place([((10, 0), inklet.text("a much longer label"))], anchor="w")

    # The author put the west label to the left of x=-10 and the east one to
    # the right of x=+10. Read back, both straddle zero.
    assert shapes.bbox.center.x == pytest.approx(0.0)
    assert west.bbox.center.x == pytest.approx(0.0)
    assert east.bbox.center.x == pytest.approx(0.0)
    assert west.bbox.x1 > 0.0 and east.bbox.x0 < 0.0

    # And overlaying them -- the obvious way to put one picture back together
    # -- stacks three different frames on one centre.
    together = inklet.overlay([shapes, west, east])
    assert together.bbox.width == pytest.approx(east.bbox.width)


def test_an_explicit_origin_keeps_the_frame():
    """The fix. Same three calls, one frame, coordinates that read back."""
    shapes = inklet.place(geometry(), origin=(0, 0))
    west = inklet.place([((-10, 0), inklet.text("in"))], anchor="e", origin=(0, 0))
    east = inklet.place([((10, 0), inklet.text("a much longer label"))],
                     anchor="w", origin=(0, 0))

    assert shapes.bbox.x0 == pytest.approx(-10.5)
    assert west.bbox.x1 == pytest.approx(-10.0)
    assert east.bbox.x0 == pytest.approx(10.0)


def test_the_frame_survives_being_composed_with_place():
    """`place` puts a bare diagram back where it was drawn, so groups nest."""
    shapes = inklet.place(geometry(), origin=(0, 0))
    labels = inklet.place([((10, 0), inklet.text("label"))], anchor="w",
                       origin=(0, 0))
    both = inklet.place([shapes, labels], origin=(0, 0))
    assert both.bbox.x0 == pytest.approx(-10.5)
    assert both.bbox.x1 == pytest.approx(labels.bbox.x1)

    # Without an origin on the outer call the register still holds; only the
    # frame moves, because the outer group recentres on its own box.
    loose = inklet.place([inklet.place(geometry(), origin=(0, 0)),
                       inklet.place([((10, 0), inklet.text("label"))], anchor="w",
                                 origin=(0, 0))])
    assert loose.bbox.width == pytest.approx(both.bbox.width)


def test_overlay_still_loses_the_frame_and_the_docstring_says_so():
    """`overlay` aligns bounding boxes. That is its job, `origin` or not."""
    shapes = inklet.place(geometry(), origin=(0, 0))
    labels = inklet.place([((10, 0), inklet.text("a much longer label"))],
                       anchor="w", origin=(0, 0))
    assert inklet.overlay([shapes, labels]).bbox.center.x == pytest.approx(0.0)
    assert "overlay" in inklet.place.__doc__


# -- what `origin` actually promises ---------------------------------------


def test_the_origin_anchor_sits_on_the_point_that_was_asked_for():
    node = inklet.place(geometry(), origin=(0, 0))
    assert node.anchor_point("origin") == Vec2(0.0, 0.0)


def test_a_non_zero_origin_puts_that_point_on_the_local_origin():
    """Useful when the interesting point is not (0, 0) -- a well, a junction."""
    node = inklet.place(geometry(), origin=(10, 0))
    assert node.anchor_point("origin") == Vec2(0.0, 0.0)
    assert node.bbox.x1 == pytest.approx(0.5)     # the marker at x=10


def test_translated_moves_by_the_numbers_that_were_typed():
    node = inklet.place(geometry(), origin=(0, 0)).translated(5, 0)
    assert node.bbox.x0 == pytest.approx(-5.5)


def test_putting_the_group_back_where_it_was_drawn_is_a_no_op():
    from inklet.draw.coords import as_drawn

    node = inklet.place(geometry(), origin=(0, 0))
    assert as_drawn(node).bbox == node.bbox


def test_a_string_origin_component_is_millimetres_like_everywhere_else():
    node = inklet.place(geometry(), origin=("10mm", 0))
    assert node.bbox.x1 == pytest.approx(0.5)


# -- the default is untouched ---------------------------------------------


def test_the_default_still_centres_on_its_own_box():
    """Changing this would move every existing figure, so it does not change."""
    node = inklet.place(geometry())
    assert node.bbox.center == Vec2(0.0, 0.0)
    assert node.anchor_point("origin") == Vec2(0.0, 0.0)


def test_the_default_origin_anchor_still_records_where_zero_went():
    node = inklet.place([dot((0, 0)), dot((20, 0))])
    # The anchor is (0, 0) in the pre-transform frame and the offset rides on
    # the group's transform, which is how `layout` and `drawn_group` do it.
    where = node.transform.apply(node.anchor_point("origin"))
    assert where.x == pytest.approx(-10.0)


def test_a_framed_group_renders_the_same_as_the_default_one_moved():
    default = inklet.place([dot((0, 0)), dot((20, 0))])
    framed = inklet.place([dot((0, 0)), dot((20, 0))], origin=(10, 0))
    assert framed.bbox == default.bbox


# -- the rest of place -----------------------------------------------------


def test_style_reaches_a_framed_group():
    node = inklet.place(geometry(), origin=(0, 0), stroke="#ff0000")
    assert node.style.stroke == "#ff0000"


def test_the_same_diagram_twice_is_still_refused():
    shared = inklet.marker("circle", 1.0)
    with pytest.raises(ValueError, match="same Diagram object twice"):
        inklet.place([((0, 0), shared), ((5, 0), shared)], origin=(0, 0))


def test_a_framed_place_is_deterministic():
    def build():
        node = inklet.place(geometry(), origin=(0, 0))
        return (node.bbox.x0, node.bbox.x1, node.anchor_point("origin"))

    assert build() == build()
