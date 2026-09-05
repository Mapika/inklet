"""Layout: stacking, grids, padding, framing.

Numbers here are hand-computed and pinned. The interesting ones are in
`test_envelope_*`, which is where a bounding-box implementation of the same
API would give visibly different answers.
"""

from __future__ import annotations

import math

import pytest

from inklet.core import (
    EAST, NORTH, SOUTH, WEST,
    Diagram, DiagramError, EllipsePrim, PhantomPrim, Rect, RectPrim,
    TextLine, TextPrim, Vec2, flatten, resolve,
)
from inklet.layout import (
    align_to, beside, box, flow, frame, grid, hstack, overlay, pad, spacer,
    stack, vstack,
)

SQRT2 = math.sqrt(2.0)
DIAGONAL = Vec2(1.0, 1.0).normalized()


def rect(w=20.0, h=10.0, **kw):
    return Diagram(prim=RectPrim(w, h), kind="box", **kw)


def circle(r=10.0, **kw):
    return Diagram(prim=EllipsePrim(r, r), kind="dot", **kw)


def ellipse(rx=20.0, ry=5.0, **kw):
    return Diagram(prim=EllipsePrim(rx, ry), kind="dot", **kw)


def label(advance=8.0, ascent=3.0, descent=1.0):
    """A pre-shaped text block: 8mm wide, 4mm tall, baseline 1mm below centre."""
    return Diagram(prim=TextPrim(
        lines=(TextLine("Hi", advance, 0.0),),
        font_family="Test", font_size=4.0, ascent=ascent, descent=descent,
    ), kind="text")


def hull_extent(item: Diagram, direction: Vec2) -> float:
    """What a bbox-based layout engine would measure: the item's local box
    pushed through its transform by hulling the corners."""
    hull = item.local_bbox.transform(item.transform)
    return max(p.dot(direction) for p in hull.corners)


def baseline_y(placement) -> float:
    prim = placement.diagram.prim
    return placement.world.apply(Vec2(0.0, prim.first_baseline)).y


# -- stacking: the basics -------------------------------------------------


def test_hstack_leaves_exactly_the_gap_between_neighbours():
    a, b = rect(20, 10), rect(20, 10)
    row = hstack([a, b], gap=5.0)

    placements = resolve(row)
    left, right = placements[a.id].bbox, placements[b.id].bbox
    assert left.width == pytest.approx(20.0)
    assert right.width == pytest.approx(20.0)
    assert right.x0 - left.x1 == pytest.approx(5.0)
    assert row.width == pytest.approx(45.0)
    assert row.height == pytest.approx(10.0)


def test_a_laid_out_row_comes_back_centred_on_its_origin():
    row = hstack([rect(20, 10), rect(20, 10)], gap=5.0)
    assert row.bbox == Rect(-22.5, -5.0, 22.5, 5.0)


def test_gaps_accept_unit_strings():
    a, b = rect(10, 10), rect(10, 10)
    assert hstack([a, b], gap="3mm").width == pytest.approx(23.0)


def test_negative_gap_overlaps():
    a, b = rect(20, 10), rect(20, 10)
    assert hstack([a, b], gap=-5.0).width == pytest.approx(35.0)


def test_vstack_runs_downward():
    top, bottom = rect(20, 10), rect(20, 10)
    column = vstack([top, bottom], gap=4.0)

    placements = resolve(column)
    assert column.height == pytest.approx(24.0)
    assert placements[bottom.id].bbox.y0 - placements[top.id].bbox.y1 == pytest.approx(4.0)
    assert placements[top.id].bbox.center.y < placements[bottom.id].bbox.center.y


def test_stack_west_reverses_the_run_without_flipping_the_cross_axis():
    a, b = rect(20, 10), rect(10, 6)
    row = stack([a, b], WEST, gap=5.0, align="top")

    placements = resolve(row)
    assert placements[b.id].bbox.x1 - placements[a.id].bbox.x0 == pytest.approx(-5.0)
    assert placements[a.id].bbox.y0 == pytest.approx(placements[b.id].bbox.y0)


# -- stacking: the envelope, which is the whole point ---------------------


def test_envelope_circles_pack_to_touching():
    a, b = circle(10.0), circle(10.0)
    assert hstack([a, b], gap=0.0).width == pytest.approx(40.0)


def test_envelope_rotated_squares_pack_on_their_diagonals():
    """Two 20mm squares turned 45 degrees: each reaches its half-diagonal,
    10*sqrt(2), to either side."""
    squares = [rect(20, 20).rotated(45.0) for _ in range(2)]
    half_diagonal = 10.0 * SQRT2

    row = hstack(squares, gap=0.0)
    assert squares[0].extent(EAST) == pytest.approx(half_diagonal)
    assert row.width == pytest.approx(4.0 * half_diagonal)
    assert row.width == pytest.approx(56.5685, abs=1e-4)

    # A rotated square is exactly the case where a hulled box tells the truth,
    # so this shape alone would not have justified the design.
    assert hull_extent(squares[0], EAST) == pytest.approx(half_diagonal)


def test_envelope_beats_a_hulled_box_for_a_rotated_ellipse():
    """The case that genuinely disagrees. A 40x10 ellipse turned 45 degrees
    reaches sqrt((20cos45)^2 + (5sin45)^2) = sqrt(212.5) = 14.5774mm east.
    Hulling its 40x10 box through the same rotation claims 25/sqrt(2) =
    17.6777mm, which would hold the pair 12.4mm further apart than they need."""
    spun = [ellipse(20.0, 5.0).rotated(45.0) for _ in range(2)]
    exact = math.sqrt(212.5)
    naive = 25.0 / SQRT2

    assert spun[0].extent(EAST) == pytest.approx(exact, abs=1e-9)
    assert hull_extent(spun[0], EAST) == pytest.approx(naive, abs=1e-9)
    assert exact != pytest.approx(naive, abs=1e-6)

    row = hstack(spun, gap=0.0)
    assert row.width == pytest.approx(4.0 * exact, abs=1e-9)
    assert row.width == pytest.approx(58.3095, abs=1e-4)
    assert 4.0 * naive == pytest.approx(70.7107, abs=1e-4)


def test_envelope_packs_a_diagonal_run_by_true_reach():
    """Stacking along the diagonal is where even an unrotated circle disagrees
    with its box: it reaches 10mm that way, its box 10*sqrt(2)."""
    a, b = circle(10.0), circle(10.0)
    run = stack([a, b], DIAGONAL, gap=0.0)

    placements = resolve(run)
    separation = placements[b.id].bbox.center - placements[a.id].bbox.center
    assert separation.length == pytest.approx(20.0)
    assert run.width == pytest.approx(20.0 + 10.0 * SQRT2)
    assert run.width == pytest.approx(34.1421, abs=1e-4)

    # A box-based engine would read 10*sqrt(2) of reach and push the centres
    # 28.28mm apart -- 20mm of x -- for a total of 40mm.
    assert hull_extent(a, DIAGONAL) == pytest.approx(10.0 * SQRT2)
    naive_width = 20.0 + 2.0 * hull_extent(a, DIAGONAL) / SQRT2
    assert naive_width == pytest.approx(40.0)
    assert run.width != pytest.approx(naive_width, abs=1e-6)


def test_cross_axis_alignment_uses_the_same_extents():
    """A rotated square aligned "top" sits on the line its corner reaches, not
    on the top of some larger box."""
    spun = rect(20, 20).rotated(45.0)
    flat = rect(10, 6)
    row = hstack([spun, flat], align="top")

    placements = resolve(row)
    assert placements[spun.id].bbox.y0 == pytest.approx(placements[flat.id].bbox.y0)
    assert row.height == pytest.approx(20.0 * SQRT2)


# -- alignment ------------------------------------------------------------


@pytest.mark.parametrize("name", ["top", "n"])
def test_hstack_top_alignment_flushes_the_upper_edges(name):
    tall, short = rect(20, 10), rect(10, 4)
    placements = resolve(hstack([tall, short], align=name))
    assert placements[tall.id].bbox.y0 == pytest.approx(placements[short.id].bbox.y0)


@pytest.mark.parametrize("name", ["bottom", "s"])
def test_hstack_bottom_alignment_flushes_the_lower_edges(name):
    tall, short = rect(20, 10), rect(10, 4)
    placements = resolve(hstack([tall, short], align=name))
    assert placements[tall.id].bbox.y1 == pytest.approx(placements[short.id].bbox.y1)


def test_hstack_centre_is_the_default():
    tall, short = rect(20, 10), rect(10, 4)
    placements = resolve(hstack([tall, short]))
    assert placements[tall.id].bbox.center.y == pytest.approx(
        placements[short.id].bbox.center.y)


@pytest.mark.parametrize("name,edge", [("left", "x0"), ("w", "x0"),
                                       ("right", "x1"), ("e", "x1")])
def test_vstack_alignment_flushes_the_named_side(name, edge):
    wide, narrow = rect(20, 10), rect(8, 10)
    placements = resolve(vstack([wide, narrow], align=name))
    assert getattr(placements[wide.id].bbox, edge) == pytest.approx(
        getattr(placements[narrow.id].bbox, edge))


def test_baseline_alignment_puts_text_on_the_line_a_reader_expects():
    shape, text = rect(20, 10), label()
    placements = resolve(hstack([shape, text], align="baseline"))

    assert baseline_y(placements[text.id]) == pytest.approx(
        placements[shape.id].bbox.center.y)
    # Centre alignment would have put the *middle* of the block on that line,
    # leaving the baseline 1mm (half the block minus the ascent) below it.
    centred = resolve(hstack([shape, text], align="center"))
    assert baseline_y(centred[text.id]) - centred[shape.id].bbox.center.y == \
        pytest.approx(1.0)


def test_baseline_alignment_finds_text_through_a_wrapper():
    shape, text = rect(20, 10), label()
    padded = pad(text, 2, 0, 6, 0)          # shifts the block up inside its box
    placements = resolve(hstack([shape, padded], align="baseline"))

    assert baseline_y(placements[text.id]) == pytest.approx(
        placements[shape.id].bbox.center.y)


def test_baseline_alignment_falls_back_to_centring_without_text():
    a, b = rect(20, 10), rect(10, 4)
    placements = resolve(hstack([a, b], align="baseline"))
    assert placements[a.id].bbox.center.y == pytest.approx(
        placements[b.id].bbox.center.y)


def test_an_axis_inappropriate_alignment_names_the_valid_ones():
    with pytest.raises(ValueError) as caught:
        hstack([rect(), rect()], align="left")
    message = str(caught.value)
    assert "'left'" in message
    assert "horizontal stack" in message
    for valid in ("top", "center", "bottom", "baseline"):
        assert valid in message
    assert "vertical stack" in message


def test_baseline_is_rejected_for_a_vertical_stack():
    with pytest.raises(ValueError, match="baseline"):
        vstack([rect(), rect()], align="baseline")


def test_an_unknown_alignment_is_rejected():
    with pytest.raises(ValueError, match="middle"):
        hstack([rect(), rect()], align="middle")


# -- nesting --------------------------------------------------------------


def test_nested_stacks_land_where_the_arithmetic_says():
    """row = a|b with a 5mm gap, then that over c with a 4mm gap.

    Row: a spans -10..10 and b 15..35 before centring; the row's box is
    -10..35, so it recentres by -12.5 and the leaves sit at x = -12.5 and 12.5.
    Column: the row reaches 5 down, c reaches 5 up, so c's centre is at
    y = 5 + 4 + 5 = 14; the column box runs -5..19 and recentres by -7.
    """
    a, b, c = rect(20, 10), rect(20, 10), rect(10, 10)
    figure = vstack([hstack([a, b], gap=5.0), c], gap=4.0)

    placements = resolve(figure)
    assert placements[a.id].point("center") == Vec2(-12.5, -7.0)
    assert placements[b.id].point("center") == Vec2(12.5, -7.0)
    assert placements[c.id].point("center") == Vec2(0.0, 7.0)
    assert figure.bbox == Rect(-22.5, -12.0, 22.5, 12.0)


def test_a_handle_survives_three_levels_of_layout():
    a, b, c = rect(20, 10), rect(20, 10), rect(10, 10)
    deep = vstack([hstack([a, b], gap=5.0), c], gap=4.0)

    placements = resolve(deep)
    assert a.id in placements
    assert placements[a.id].diagram is a
    assert placements[a.id].point("center") == Vec2(-12.5, -7.0)
    assert placements[a.id].point("nw") == Vec2(-22.5, -12.0)


def test_layout_does_not_place_the_same_object_twice():
    a = rect()
    with pytest.raises(DiagramError, match="twice"):
        hstack([a, a])


def test_layout_rejects_non_diagrams_by_position():
    with pytest.raises(TypeError, match="item 1"):
        hstack([rect(), "not a diagram"])


# -- padding --------------------------------------------------------------


def test_pad_grows_the_box_by_exactly_what_was_asked():
    content = rect(20, 10)
    padded = pad(content, 2, 4)
    assert padded.bbox == Rect(-14.0, -7.0, 14.0, 7.0)
    assert padded.width == pytest.approx(28.0)
    assert padded.height == pytest.approx(14.0)


def test_pad_follows_css_shorthand_order():
    """top 1, right 2, bottom 3, left 4: 26x14 in total, and the content ends
    up off-centre inside it, since the result is centred on its own origin."""
    content = rect(20, 10)
    padded = pad(content, 1, 2, 3, 4)

    assert padded.bbox == Rect(-13.0, -7.0, 13.0, 7.0)
    assert resolve(padded)[content.id].bbox.center == Vec2(1.0, -1.0)


def test_padding_does_not_catch_rays_aimed_at_the_content():
    content = rect(20, 10)
    padded = pad(content, 2, 4)

    entry = padded.trace.boundary_point(Vec2(-100.0, 0.0), EAST, from_inside=False)
    assert entry.x == pytest.approx(-10.0)          # the rect's own edge
    assert padded.trace.exit(Vec2(0.0, 0.0), EAST) == pytest.approx(10.0)
    assert padded.trace.exit(Vec2(0.0, 0.0), SOUTH) == pytest.approx(5.0)


def test_padding_draws_nothing():
    """Padding claims room without adding ink: the padded result renders exactly
    the primitives the content already had."""
    content = rect(20, 10)
    assert [i.prim for i in flatten(pad(content, 2, 4))] == [
        i.prim for i in flatten(content)]


def test_uniform_padding_grows_by_the_same_amount_in_every_direction():
    """A Minkowski sum with a disc, not a square. Padding a rotated shape by 1mm
    must add 1mm on the diagonal too, not 1.41mm."""
    spun = Diagram(prim=EllipsePrim(20.0, 5.0)).rotated(45.0)   # major axis lies NE
    padded = pad(spun, 1.0)
    diagonal = Vec2(1.0, 1.0).normalized()
    assert spun.extent(diagonal) == pytest.approx(20.0)
    assert padded.extent(diagonal) == pytest.approx(21.0)
    assert padded.extent(EAST) == pytest.approx(spun.extent(EAST) + 1.0)


def test_padding_takes_part_in_stacking():
    a, b = rect(20, 10), rect(20, 10)
    assert hstack([pad(a, 0, 4), b], gap=0.0).width == pytest.approx(48.0)


def test_padding_accepts_unit_strings():
    assert pad(rect(20, 10), "2mm").width == pytest.approx(24.0)


def test_zero_padding_changes_nothing():
    padded = pad(rect(20, 20).rotated(45.0), 0)
    assert padded.extent(EAST) == pytest.approx(10.0 * SQRT2)


# -- framing --------------------------------------------------------------


def test_frame_wraps_the_padded_content_and_paints_behind_it():
    content = rect(20, 10)
    framed = frame(content, pad=3.0)

    assert framed.bbox == Rect(-13.0, -8.0, 13.0, 8.0)
    drawn = flatten(framed)
    assert isinstance(drawn[0].prim, RectPrim)
    assert (drawn[0].prim.width, drawn[0].prim.height) == (26.0, 16.0)
    assert drawn[1].id == content.id            # content paints over the frame


def test_frame_holds_no_style_opinions():
    framed = frame(rect(20, 10), pad=3.0)
    assert all(item.style.is_empty for item in flatten(framed))


def test_frame_honours_minimum_sizes():
    framed = frame(rect(20, 10), pad=2.0, min_width=40.0, min_height=6.0)
    shape = flatten(framed)[0].prim
    assert (shape.width, shape.height) == (40.0, 14.0)
    assert framed.width == pytest.approx(40.0)


def test_frame_can_be_an_ellipse_sized_to_the_box():
    framed = frame(rect(20, 10), pad=1.0, shape="ellipse")
    shape = flatten(framed)[0].prim
    assert isinstance(shape, EllipsePrim)
    assert (shape.rx, shape.ry) == (11.0, 6.0)


def test_frame_passes_a_corner_radius_to_the_primitive():
    assert flatten(frame(rect(), pad=1.0, radius="2mm"))[0].prim.radius == 2.0


def test_frame_rejects_an_unknown_shape():
    with pytest.raises(ValueError, match="hexagon"):
        frame(rect(), shape="hexagon")


def test_frame_refuses_an_empty_diagram():
    with pytest.raises(DiagramError, match="empty"):
        frame(hstack([]))


def test_box_is_a_frame_with_room_to_breathe():
    boxed = box(rect(20, 10))
    assert boxed.width == pytest.approx(24.0)
    assert boxed.height == pytest.approx(14.0)


def test_a_framed_box_catches_rays_at_the_frame():
    framed = frame(rect(20, 10), pad=3.0)
    assert framed.trace.exit(Vec2(0.0, 0.0), EAST) == pytest.approx(13.0)


# -- grid -----------------------------------------------------------------


def test_grid_fills_row_major_with_aligned_columns():
    widths = [20.0, 30.0, 20.0, 20.0, 10.0, 20.0]
    items = [rect(w, 10.0) for w in widths]
    table = grid(items, cols=3, gap=5.0)

    # columns 20 + 30 + 20 with two 5mm gaps; rows 10 + 10 with one.
    assert table.width == pytest.approx(80.0)
    assert table.height == pytest.approx(25.0)

    placements = resolve(table)
    centres = [placements[item.id].bbox.center for item in items]
    assert [c.x for c in centres[:3]] == pytest.approx([c.x for c in centres[3:]])
    assert [c.y for c in centres[:3]] == pytest.approx([-7.5, -7.5, -7.5])
    assert [c.y for c in centres[3:]] == pytest.approx([7.5, 7.5, 7.5])
    assert [c.x for c in centres[:3]] == pytest.approx([-30.0, 0.0, 30.0])


def test_grid_columns_are_wider_than_a_row_of_stacks_would_be():
    """The discriminating case: row 2 is narrow, but its cells still line up
    under row 1, which nested hstacks would not manage."""
    items = [rect(20, 10), rect(30, 10), rect(4, 10), rect(4, 10)]
    placements = resolve(grid(items, cols=2, gap=0.0))
    first_column = [placements[items[0].id].bbox.center.x,
                    placements[items[2].id].bbox.center.x]
    assert first_column[0] == pytest.approx(first_column[1])


def test_grid_takes_a_ragged_final_row():
    items = [rect(20, 10) for _ in range(5)]
    table = grid(items, cols=3, gap=5.0)

    assert table.width == pytest.approx(70.0)
    assert table.height == pytest.approx(25.0)
    placements = resolve(table)
    assert placements[items[3].id].bbox.center.x == pytest.approx(
        placements[items[0].id].bbox.center.x)


def test_grid_derives_columns_from_rows():
    items = [rect(10, 10) for _ in range(6)]
    assert grid(items, rows=2, gap=0.0).width == pytest.approx(30.0)


def test_grid_defaults_to_a_squarish_shape():
    items = [rect(10, 10) for _ in range(9)]
    table = grid(items, gap=0.0)
    assert (table.width, table.height) == (30.0, 30.0)


def test_grid_gaps_can_differ_per_axis():
    items = [rect(10, 10) for _ in range(4)]
    table = grid(items, cols=2, col_gap=6.0, row_gap=2.0)
    assert table.width == pytest.approx(26.0)
    assert table.height == pytest.approx(22.0)


def test_grid_aligns_within_the_cell():
    items = [rect(20, 10), rect(4, 4), rect(20, 10), rect(4, 4)]
    placements = resolve(grid(items, cols=2, gap=0.0, align="left", valign="top"))
    assert placements[items[1].id].bbox.x0 == pytest.approx(
        placements[items[0].id].bbox.x1)
    assert placements[items[1].id].bbox.y0 == pytest.approx(
        placements[items[0].id].bbox.y0)


def test_grid_rejects_a_shape_that_cannot_hold_the_items():
    with pytest.raises(ValueError, match="do not fit"):
        grid([rect() for _ in range(6)], cols=2, rows=2)


def test_grid_rejects_an_axis_inappropriate_alignment():
    with pytest.raises(ValueError, match="top"):
        grid([rect()], cols=1, align="top")


# -- overlay, spacer, beside, align_to ------------------------------------


def test_overlay_centres_and_keeps_draw_order():
    under, over = rect(20, 10), rect(6, 6)
    stacked = overlay([under, over])

    placements = resolve(stacked)
    assert placements[under.id].bbox.center == Vec2(0.0, 0.0)
    assert placements[over.id].bbox.center == Vec2(0.0, 0.0)
    assert [item.id for item in flatten(stacked)] == [under.id, over.id]


def test_overlay_can_align_on_a_corner():
    a, b = rect(20, 10), rect(6, 6)
    placements = resolve(overlay([a, b], align="nw"))
    assert placements[a.id].bbox.x0 == pytest.approx(placements[b.id].bbox.x0)
    assert placements[a.id].bbox.y0 == pytest.approx(placements[b.id].bbox.y0)


def test_spacer_is_space_that_is_really_there():
    a, b = rect(20, 10), rect(20, 10)
    assert hstack([a, spacer(width=5.0), b], gap=0.0).width == pytest.approx(45.0)
    assert spacer(width="5mm", height=2.0).bbox == Rect(-2.5, -1.0, 2.5, 1.0)
    assert not spacer().is_empty


def test_beside_places_the_second_in_the_given_direction():
    a, b = rect(20, 10), rect(20, 10)
    placements = resolve(beside(a, b, EAST, gap=5.0))
    assert placements[b.id].bbox.x0 - placements[a.id].bbox.x1 == pytest.approx(5.0)

    over, under = rect(20, 10), rect(20, 10)
    up = resolve(beside(under, over, NORTH, gap=5.0))
    assert up[over.id].bbox.y1 - up[under.id].bbox.y0 == pytest.approx(-5.0)


def test_align_to_moves_the_named_anchor_to_the_origin():
    assert align_to(rect(20, 10), "nw").bbox == Rect(0.0, 0.0, 20.0, 10.0)
    assert align_to(rect(20, 10), "se").bbox == Rect(-20.0, -10.0, 0.0, 0.0)


def test_align_to_honours_a_registered_anchor():
    item = rect(20, 10).anchor("ear", (0.25, 0.0))
    moved = align_to(item, "ear")
    assert moved.bbox == Rect(-5.0, 0.0, 15.0, 10.0)


def test_align_to_reports_an_unknown_anchor():
    with pytest.raises(DiagramError, match="middle"):
        align_to(rect(), "middle")


# -- empty inputs ---------------------------------------------------------


def test_empty_inputs_give_an_empty_diagram():
    """An empty stack occupies no space at all, which is not the same as a
    zero-sized point at the origin -- so it has no bounding box either."""
    for empty in (hstack([]), vstack([]), grid([]), overlay([])):
        assert empty.is_empty
        assert empty.envelope.bbox() is None
        with pytest.raises(DiagramError):
            empty.bbox


def test_empty_items_take_no_room_and_eat_no_gap():
    a, b = rect(20, 10), rect(20, 10)
    assert hstack([a, hstack([]), b], gap=5.0).width == pytest.approx(45.0)


def test_a_single_item_stack_is_just_that_item_centred():
    a = rect(20, 10).translated(100.0, 0.0)
    assert hstack([a]).bbox == Rect(-10.0, -5.0, 10.0, 5.0)


# -- determinism and non-mutation -----------------------------------------


def test_laying_out_twice_gives_identical_placements():
    def build():
        a, b, c = rect(20, 10), circle(6.0), rect(20, 20).rotated(45.0)
        return vstack([hstack([a, b], gap=3.0, align="bottom"),
                       pad(c, 2, 4)], gap="1mm", align="left")

    first = [(item.world, type(item.prim).__name__) for item in flatten(build())]
    second = [(item.world, type(item.prim).__name__) for item in flatten(build())]
    assert first == second


def test_layout_leaves_its_inputs_alone():
    a, b = rect(20, 10), rect(20, 10)
    before = (a.transform, a.children, a.bbox, a.id, dict(a.anchors), a.style)

    row = hstack([a, b], gap=5.0)
    grid([a, b], cols=2)
    overlay([a, b])
    pad(a, 3)
    frame(a, pad=3)

    assert (a.transform, a.children, a.bbox, a.id, dict(a.anchors), a.style) == before
    assert a.transform.is_identity
    assert resolve(row)[a.id].diagram is a


# -- flow ------------------------------------------------------------------

def test_flow_packs_shorter_than_a_grid_of_the_same_items():
    """The whole reason it exists: a row costs its tallest cell, a column
    costs only what is actually in it."""
    items = [rect(20.0, h) for h in (10.0, 40.0, 12.0, 8.0, 30.0, 6.0)]

    packed = flow(items, columns=2, gap=2.0)

    assert grid(items, cols=2, gap=2.0).height == pytest.approx(86.0)
    assert packed.height == pytest.approx(62.0)
    assert packed.width == pytest.approx(42.0)


def test_flow_cuts_the_sequence_where_the_columns_come_out_evenest():
    tall, short, next_ = rect(10.0, 30.0), rect(10.0, 5.0), rect(10.0, 5.0)

    packed = flow([tall, short, next_], columns=2, gap=0.0)

    # The only contiguous cut that helps is after `tall`: the two short ones
    # share the second column and the height is still the tall one.
    assert packed.height == pytest.approx(30.0)


def column_order(packed: Diagram) -> list[list[str]]:
    """The names in each column, left to right and top to bottom."""
    lanes = sorted(packed.children, key=lambda c: c.bbox.center.x)
    return [[node.name for node in sorted(lane.walk(), key=lambda n: n.bbox.center.y)
             if node.name] for lane in lanes]


def test_flow_columns_are_runs_of_the_sequence():
    """Reading down the columns must give back the order they were written in.
    Sending each item to the currently shortest column does not: these six came
    out a, b, d, c, e, f, and eighteen panels came out a, b, c, e, d, f, g."""
    items = [rect(10.0, h).named(name) for name, h in
             zip("abcdef", (10.0, 40.0, 12.0, 8.0, 30.0, 6.0))]

    packed = flow(items, columns=2, gap=2.0)

    assert column_order(packed) == [["a", "b"], ["c", "d", "e", "f"]]


def test_flow_fills_earlier_columns_when_the_cuts_tie():
    """A ragged bottom in the last column is how a page reads; a ragged first
    column is how a mistake looks."""
    items = [rect(10.0, 5.0).named(name) for name in "abc"]

    packed = flow(items, columns=2, gap=0.0)

    assert column_order(packed) == [["a", "b"], ["c"]]


def test_flow_ties_go_left_so_the_first_row_reads_across():
    a, b = rect(10.0, 5.0).named("a"), rect(10.0, 5.0).named("b")

    packed = flow([a, b], columns=2, gap=0.0)

    left, right = packed.children
    assert left.bbox.center.x < right.bbox.center.x


def test_a_single_column_flow_is_just_a_vstack():
    items = [rect(10.0, h) for h in (4.0, 9.0, 2.0)]

    assert flow(items, columns=1, gap=1.5).height == pytest.approx(
        vstack(items, gap=1.5).height)


def test_flow_ignores_empty_items():
    items = [rect(10.0, 5.0), Diagram(), rect(10.0, 5.0)]

    assert flow(items, columns=2, gap=0.0).height == pytest.approx(5.0)


def test_flow_of_nothing_is_empty_like_a_grid():
    assert flow([], columns=3).is_empty


def test_flow_needs_a_column():
    with pytest.raises(DiagramError, match="at least one column"):
        flow([rect(1.0, 1.0)], columns=0)
