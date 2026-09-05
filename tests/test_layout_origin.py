"""The drawn frame as a first-class alignment, and the doors that refuse a size.

Two round-1 findings, and they turn out to be the same finding twice. A
`inklet.draw` shape is rewritten to sit on its own origin and remembers where the
author's (0, 0) went; every combinator that *aligns bounding boxes* therefore
throws that frame away. `place(..., origin=(0, 0))` -- spelled `inklet.drawn` --
keeps it, and this file pins down the three other places that now can:
`overlay(align="origin")`, the stacks' cross axis, and `placed_anchor`, which
is what finally makes `place(..., anchor="e")` mean the east of the item as it
is actually oriented rather than the east it had before it was turned.
"""

from __future__ import annotations

import pytest

import inklet
from inklet import Vec2
from inklet.draw.coords import ORIGIN_ANCHOR
from inklet.layout import spacer
from inklet.layout import flow as _flow_function          # noqa: F401  (the door)
from inklet.layout.flow import _ORIGIN_ALIGN


def dot(x: float, y: float, size: float = 1.0):
    return ((x, y), inklet.marker("circle", size))


def group(*points, **kwargs):
    """A `place` group in the author's own coordinates."""
    return inklet.drawn([dot(*p) for p in points], **kwargs)


# -- the frame that overlay used to lose -----------------------------------


def test_overlay_on_origin_keeps_three_groups_in_register():
    """The reproduction, and the fix. Three groups drawn from one set of
    numbers; the default centres each box on the next and pulls them apart."""
    left = group((-10, 0), (0, 0))
    right = group((0, 0), (30, 0))
    both = inklet.overlay([left, right], align="origin")
    # -10 .. 30 plus the markers' half-millimetre each side.
    assert both.bbox.width == pytest.approx(41.0)
    assert inklet.drawn(both).bbox.x0 == pytest.approx(-10.5)
    assert inklet.drawn(both).bbox.x1 == pytest.approx(30.5)

    # What it used to do, and still does when asked for boxes: each group is
    # centred on its own box first, so the two frames slide apart.
    boxes = inklet.overlay([left, right])
    assert boxes.bbox.width == pytest.approx(31.0)


def test_an_origin_overlay_is_itself_in_the_frame():
    """So overlays of overlays keep composing, and `drawn` can take one."""
    node = inklet.overlay([group((0, 0)), group((10, 0))], align="origin")
    assert node.anchor_point(ORIGIN_ANCHOR) == Vec2(0.0, 0.0)
    back = inklet.drawn(node)
    assert back.bbox.x0 == pytest.approx(-0.5)
    assert back.bbox.x1 == pytest.approx(10.5)


def test_an_item_with_no_origin_anchor_uses_its_own_local_origin():
    """A plain layout node was never recentred by `inklet.draw`, so its own (0, 0)
    is the only frame it has and that is what gets aligned."""
    plain = spacer(10, 10)
    node = inklet.drawn(inklet.overlay([plain, group((4, 0))], align="origin"))
    assert node.bbox.x0 == pytest.approx(-5.0)      # the spacer, on its own zero
    assert node.bbox.x1 == pytest.approx(5.0)       # the dot at x = 4, plus 0.5


def test_origin_is_listed_among_the_alignments_overlay_will_take():
    with pytest.raises(ValueError) as caught:
        inklet.overlay([spacer(1, 1)], align="middle")
    assert "origin" in str(caught.value)


# -- the same thing on a stack's cross axis --------------------------------


def test_hstack_on_origin_lines_up_the_drawn_zero_like_a_baseline():
    """Sparklines drawn in data coordinates share a y = 0 across the row."""
    high = group((0, -8), (0, 0))
    low = group((0, 0), (0, 8))
    row = inklet.hstack([high, low], 2, align="origin")
    ys = [child.bbox.center.y for child in row.children]
    assert ys[0] == pytest.approx(-4.0)
    assert ys[1] == pytest.approx(4.0)
    assert inklet.hstack([high, low], 2).children[0].bbox.center.y == pytest.approx(0.0)


def test_vstack_on_origin_lines_up_the_drawn_zero_across_the_column():
    left = group((-8, 0), (0, 0))
    right = group((0, 0), (8, 0))
    column = inklet.vstack([left, right], 2, align="origin")
    xs = [child.bbox.center.x for child in column.children]
    assert xs[0] == pytest.approx(-4.0)
    assert xs[1] == pytest.approx(4.0)


def test_origin_is_accepted_on_every_axis_including_a_diagonal():
    node = inklet.stack([group((0, 0)), group((5, 5))], Vec2(1, 1), 1,
                     align="origin")
    assert not node.is_empty


def test_the_alignment_name_is_the_anchor_name():
    """Anti-drift: rename the anchor and this alignment has to be renamed too."""
    assert _ORIGIN_ALIGN == {ORIGIN_ANCHOR: ORIGIN_ANCHOR}


# -- an anchor means where the item is now, not where it was drawn ---------


def rotated_bar() -> inklet.Diagram:
    """20 x 4, turned a quarter turn: 4 wide and 20 tall on the page."""
    return inklet.layout.frame(spacer(20, 4)).rotated(90)


def test_a_rotated_items_compass_point_reads_the_placed_box():
    bar = rotated_bar()
    assert bar.bbox.width == pytest.approx(4.0)
    # `anchor_point` answers in the item's own frame, before its transform.
    assert bar.anchor_point("e").x == pytest.approx(10.0)
    # `placed_anchor` answers in the frame whoever holds it is working in.
    assert inklet.placed_anchor(bar, "e").x == pytest.approx(2.0)


def test_place_puts_a_rotated_items_real_east_on_the_point():
    """The hazard: before this, a label hung off `anchor="e"` of a rotated bar
    was placed 10mm out instead of 2mm, and nothing said so."""
    node = inklet.place([((0, 0), rotated_bar())], anchor="e", origin=(0, 0))
    assert node.bbox.x1 == pytest.approx(0.0)
    assert node.bbox.x0 == pytest.approx(-4.0)


def test_a_registered_anchor_is_read_through_the_items_own_transform():
    """A named anchor is a point *of* the thing, so it travels with it -- which
    is the reading `anchor_point` already had, and the one kept here."""
    bar = inklet.layout.frame(spacer(20, 4))
    bar.anchor("tip", Vec2(10.0, 0.0))
    assert inklet.placed_anchor(bar, "tip") == Vec2(10.0, 0.0)
    # `translated` wraps rather than rewrites, and the wrapper carries no
    # anchors -- so ask the node the anchor was put on. `place` does.
    assert inklet.place([((0, 0), bar)], anchor="tip",
                     origin=(0, 0)).bbox.x1 == pytest.approx(0.0)


def test_align_to_and_place_agree_about_where_an_anchor_is():
    bar = rotated_bar()
    moved = inklet.align_to(bar, "e")
    assert moved.bbox.x1 == pytest.approx(0.0)


def test_an_unknown_anchor_lists_what_there_is():
    with pytest.raises(inklet.DiagramError) as caught:
        inklet.placed_anchor(spacer(2, 2), "middle")
    assert "middle" in str(caught.value)
    assert "center" in str(caught.value)


# -- doors that refuse a size where the content goes -----------------------


@pytest.mark.parametrize("call", [
    lambda: inklet.circle(16),
    lambda: inklet.box(16),
])
def test_a_number_for_content_names_the_function_and_the_keyword(call):
    with pytest.raises(TypeError) as caught:
        call()
    message = str(caught.value)
    assert "width=16" in message and "height=16" in message


def test_the_suggestion_drops_the_keyword_that_was_already_given():
    with pytest.raises(TypeError) as caught:
        inklet.box(16, width=20)
    assert "height=" not in str(caught.value)


def test_a_wrong_type_for_content_is_named_rather_than_unpacked():
    with pytest.raises(TypeError) as caught:
        inklet.circle([1, 2])
    assert "list" in str(caught.value)


def test_frame_says_where_a_size_goes_and_how_to_shape_a_label():
    with pytest.raises(TypeError) as caught:
        inklet.frame(3)
    message = str(caught.value)
    assert "min_width" in message and "inklet.text" in message


@pytest.mark.parametrize("call, wanted", [
    (lambda: inklet.hstack(spacer(1, 1)), "hstack(["),
    (lambda: inklet.vstack(spacer(1, 1)), "vstack(["),
    (lambda: inklet.grid(spacer(1, 1)), "grid(["),
    (lambda: inklet.overlay(spacer(1, 1)), "overlay(["),
    (lambda: inklet.place(spacer(1, 1)), "inklet.drawn"),
    (lambda: inklet.marker(1.5), "marker('circle', 1.5)"),
    (lambda: inklet.polyline(Vec2(1, 2)), "(x, y)"),
    (lambda: inklet.grid([spacer(1, 1)], cols=1.5), "int"),
    (lambda: inklet.flow(spacer(1, 1)), "flow(["),
    (lambda: inklet.pad(3, 2), "pad() takes a diagram"),
    (lambda: inklet.pad("caption", 2), "inklet.text('caption')"),
    (lambda: inklet.align_to(3, "n"), "align_to() takes a diagram"),
    (lambda: inklet.annotate(3, "hi"), "the diagram being labelled"),
    (lambda: inklet.letters(spacer(1, 1)), "inklet.letters([a, b, c])"),
    (lambda: inklet.encoded(5), "encoded() takes a kind name"),
    (lambda: inklet.drawn(5), "drawn() takes a shape"),
    (lambda: inklet.clip(spacer(1, 1), (0, 0, 10, 10)), "inklet.Rect(0.0, 0.0, 10.0, 10.0)"),
])
def test_a_combinator_handed_the_wrong_shape_of_argument_says_so(call, wanted):
    with pytest.raises(TypeError) as caught:
        call()
    assert wanted in str(caught.value)


def test_a_gap_that_is_really_an_alignment_is_caught_at_the_door():
    """`hstack(items, "center")` reads fine and means nothing."""
    with pytest.raises(ValueError) as caught:
        inklet.hstack([spacer(1, 1), spacer(1, 1)], "center")
    assert "align='center'" in str(caught.value)


def test_a_stack_direction_that_is_a_word_points_at_hstack():
    with pytest.raises(TypeError) as caught:
        inklet.stack([spacer(1, 1)], "east")
    assert "hstack" in str(caught.value)


# -- drawn -----------------------------------------------------------------


def test_drawn_is_place_with_a_zero_origin():
    items = [dot(-10, 0), dot(10, 0)]
    assert inklet.drawn(items).bbox == inklet.place(items, origin=(0, 0)).bbox


def test_drawn_takes_one_shape_as_well_as_a_list():
    line = inklet.polyline([(4, 0), (14, 0)])
    node = inklet.drawn(line)
    assert node.bbox.x0 == pytest.approx(4.0)
    assert node.bbox.x1 == pytest.approx(14.0)


def test_drawn_undoes_the_recentring_that_every_shape_gets():
    line = inklet.polyline([(4, 0), (14, 0)])
    assert line.bbox.center.x == pytest.approx(0.0)      # recentred
    assert inklet.drawn(line).bbox.center.x == pytest.approx(9.0)


def test_drawn_mixes_bare_shapes_with_placed_pairs():
    node = inklet.drawn([inklet.polyline([(0, 0), (20, 0)]), dot(20, 0, 4.0)])
    assert node.bbox.x1 == pytest.approx(22.0)


def test_drawn_is_deterministic():
    def build():
        node = inklet.drawn([inklet.polyline([(0, 0), (5, 5)])])
        return node.bbox.x0, node.bbox.x1, node.anchor_point(ORIGIN_ANCHOR)

    assert build() == build()
