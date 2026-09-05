"""inklet.plot: axes and panels, measured on the page.

These assertions are about where things land after layout, so they go through
`resolve()` rather than reading transforms by hand -- the same path the
renderer takes.
"""

from __future__ import annotations

import pytest

from inklet.core import DiagramError, Rect, Vec2, resolve
from inklet.diagnostics import lint
from inklet.draw import marker
from inklet.draw.shapes import MARK_KIND
from inklet.draw.coords import ORIGIN_ANCHOR, as_drawn
from inklet.plot import (
    axis, band, linear, log, panel, ramp, row, tick_texts, tick_values,
)
from inklet.plot.axis import (
    AXIS_LABEL_KIND, SPINE_KIND, TICK_KIND, TICK_LABEL_KIND,
)
from inklet.plot.panel import GRID_KIND


def placements(node, kind: str):
    """Every placed node of one kind, in tree order."""
    return [p for p in resolve(as_drawn(node)).values() if p.diagram.kind == kind]


def boxes(node, kind: str) -> list[Rect]:
    return [p.bbox for p in placements(node, kind)]


def overlap(a: Rect, b: Rect) -> bool:
    return (a.x0 < b.x1 and b.x0 < a.x1) and (a.y0 < b.y1 and b.y0 < a.y1)


# --- axes --------------------------------------------------------------------


def test_the_spine_is_exactly_the_length_of_the_scale() -> None:
    node = axis(linear((0.0, 10.0)), length=60.0)
    spine = boxes(node, SPINE_KIND)[0]
    assert spine.width == pytest.approx(60.0)


def test_a_horizontal_axis_is_built_from_the_start_of_its_scale() -> None:
    """So that an x axis and a y axis meet at the bottom-left corner of the
    plot without anybody nudging either of them."""
    node = as_drawn(axis(linear((0.0, 10.0), (0.0, 60.0))))
    spine = boxes(node, SPINE_KIND)[0]
    assert spine.x0 == pytest.approx(0.0)
    assert spine.y0 == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("side,inside", [
    ("bottom", lambda box: box.y0 > 0), ("top", lambda box: box.y1 < 0),
    ("left", lambda box: box.x1 < 0), ("right", lambda box: box.x0 > 0),
])
def test_ticks_hang_off_the_side_they_are_asked_for(side, inside) -> None:
    scale = linear((0.0, 10.0), (0.0, 60.0) if side in ("bottom", "top")
                   else (0.0, -60.0))
    node = axis(scale, side=side)
    for box in boxes(node, TICK_LABEL_KIND):
        assert inside(box), f"a {side} label landed at {box}"


def test_a_negative_tick_size_puts_the_ticks_inside() -> None:
    outside = boxes(axis(linear((0, 10), (0, 60))), TICK_KIND)[0]
    inside = boxes(axis(linear((0, 10), (0, 60)), tick_size=-1.5), TICK_KIND)[0]
    assert outside.y1 > 0 and inside.y0 < 0


def test_tick_labels_do_not_collide() -> None:
    """A short axis asked for many ticks drops to every second or third one
    rather than printing them on top of each other."""
    node = axis(linear((0.0, 1000.0), (0.0, 25.0)), count=12)
    labels = boxes(node, TICK_LABEL_KIND)
    assert len(labels) >= 2
    for before, after in zip(labels, labels[1:]):
        assert not overlap(before, after)


def test_thinning_keeps_an_even_stride() -> None:
    """Dropping whichever label happens to collide would break the rhythm a
    reader counts by."""
    values = tick_values(linear((0.0, 1000.0), (0.0, 25.0)), 12)
    gaps = [b - a for a, b in zip(values, values[1:])]
    assert len(set(round(g, 9) for g in gaps)) == 1


def test_the_axis_label_clears_the_tick_labels() -> None:
    node = axis(linear((0.0, 1000.0), (0.0, 60.0)), label="mass / kg")
    name = boxes(node, AXIS_LABEL_KIND)[0]
    for label in boxes(node, TICK_LABEL_KIND):
        assert not overlap(name, label)
        assert name.y0 >= label.y1 - 1e-9


def test_a_vertical_axis_label_reads_bottom_to_top() -> None:
    node = axis(linear((0.0, 10.0), (0.0, -60.0)), side="left", label="signal")
    name = boxes(node, AXIS_LABEL_KIND)[0]
    assert name.height > name.width          # rotated a quarter turn
    for label in boxes(node, TICK_LABEL_KIND):
        assert not overlap(name, label)
        assert name.x1 <= label.x0 + 1e-9


def test_a_band_axis_labels_every_category() -> None:
    node = axis(band(("wt", "ko", "rescue"), (0.0, 60.0)))
    assert len(boxes(node, TICK_LABEL_KIND)) == 3


AREAS = ("V1", "V2", "LM", "AL", "RL", "AM", "PM", "LI", "POR", "A")


def test_a_crowded_band_axis_labels_every_category_anyway() -> None:
    """Ten rows down 22mm cannot fit ten labels, and thinning them would leave
    rows the reader cannot name. An overlap is at least visible."""
    node = axis(band(AREAS, (0.0, -22.0)), side="left")
    assert len(boxes(node, TICK_LABEL_KIND)) == len(AREAS)


def test_gridlines_follow_a_band_axis_rather_than_thinning() -> None:
    """`grid` asks `tick_values`, so a rule and a row label agree here too."""
    assert tick_values(band(AREAS, (0.0, -22.0)), horizontal=False) == AREAS


def test_categories_can_be_thinned_if_the_caller_insists() -> None:
    node = axis(band(AREAS, (0.0, -22.0)), side="left", thin=True)
    assert 1 < len(boxes(node, TICK_LABEL_KIND)) < len(AREAS)


def test_a_numeric_axis_can_refuse_to_drop_a_tick() -> None:
    crowded = axis(linear((0.0, 1000.0), (0.0, 25.0)), count=12, thin=False)
    assert len(boxes(crowded, TICK_LABEL_KIND)) == 11


def test_ticks_can_be_given_outright() -> None:
    node = axis(linear((0.0, 10.0), (0.0, 60.0)), ticks=(0.0, 3.0, 9.0))
    assert len(boxes(node, TICK_KIND)) == 3


def test_a_format_of_ones_own() -> None:
    node = axis(linear((0.0, 1.0), (0.0, 60.0)), count=3,
                format=lambda v: f"{v:.0%}")
    assert len(boxes(node, TICK_LABEL_KIND)) >= 2


def test_an_unknown_side_says_what_it_knows() -> None:
    with pytest.raises(ValueError, match="unknown axis side"):
        axis(linear(), side="sideways")


# --- panels ------------------------------------------------------------------


def test_a_panel_is_the_size_it_was_asked_for() -> None:
    p = panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 1.0))
    assert (p.area.width, p.area.height) == (60.0, 40.0)


def test_data_grows_up_the_page() -> None:
    """The one place in inklet where y is allowed to mean what a reader thinks."""
    p = panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 1.0))
    assert p.point(0.0, 1.0).y < p.point(0.0, 0.0).y


def test_the_corners_of_the_area_are_the_ends_of_the_scales() -> None:
    p = panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 1.0))
    assert p.point(0.0, 0.0) == Vec2(-30.0, 20.0)
    assert p.point(10.0, 1.0) == Vec2(30.0, -20.0)


def test_a_pair_of_numbers_is_a_linear_scale_and_anything_else_is_a_band() -> None:
    p = panel(60.0, 40.0, x=("wt", "ko"), y=(0.0, 1.0))
    assert p.x.map("wt") < p.x.map("ko")
    assert p.y.map(0.5) == 0.0


def test_a_panel_needs_a_positive_size() -> None:
    with pytest.raises(ValueError, match="positive size"):
        panel(0.0, 40.0)


def test_marks_land_on_their_data() -> None:
    points = ((0.0, 0.0), (5.0, 0.5), (10.0, 1.0))
    p = panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 1.0))
    p.marks(marker("circle", 2.0), points)
    placed = placements(p.build(), "mark")
    assert len(placed) == 3
    for spot, (x, y) in zip(placed, points):
        at = spot.point("center")
        assert (at.x, at.y) == pytest.approx((p.point(x, y).x, p.point(x, y).y),
                                             abs=1e-9)


def test_marks_copy_rather_than_share() -> None:
    """A Diagram may appear in a tree once. One marker per point is the shape
    of every scatter there is, so `marks` copies for you."""
    p = panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 1.0))
    p.marks(marker("circle", 2.0), ((0.0, 0.0), (5.0, 0.5)))
    assert len(resolve(p.build())) > 0        # would raise on a shared node


def test_gridlines_sit_exactly_under_the_ticks() -> None:
    p = panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 1.0))
    p.grid(y=False).axis("bottom")
    built = p.build()
    rules = sorted(box.center.x for box in boxes(built, GRID_KIND))
    ticks = sorted(box.center.x for box in boxes(built, TICK_KIND))
    assert rules == pytest.approx(ticks, abs=1e-9)


def test_the_panel_origin_is_the_centre_of_the_area_not_of_the_furniture() -> None:
    """Which is what lets two panels line up when one has wider labels."""
    p = panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 100000.0))
    p.axes(x="t", y="counts")
    built = p.build()
    # The assembly is centred on its own bbox, like every other diagram; the
    # anchor is what remembers where the area went inside it.
    assert built.bbox.center == Vec2(0.0, 0.0)
    area = built.transform.apply(built.anchor_point(ORIGIN_ANCHOR))
    assert area.x > 1.0, "the y labels hang to the left, so the area sits right"
    assert area.y < -1.0, "the x labels hang below, so the area sits high"


def test_a_row_lines_up_the_plot_areas_not_the_bounding_boxes() -> None:
    """One panel labelled 0..1 and another labelled 0..100000 have furniture of
    different widths. Stacked by bbox their areas would sit at different
    heights, which is the misalignment that makes a figure look homemade."""
    made = []
    for domain in ((0.0, 1.0), (0.0, 100000.0)):
        p = panel(40.0, 30.0, x=(0.0, 10.0), y=domain)
        p.axes(x="t", y="y")
        made.append(p)
    placed = placements(row(made, gap=6.0), "panel")
    assert len(placed) == 2
    first, second = (spot.point(ORIGIN_ANCHOR) for spot in placed)
    assert first.y == pytest.approx(second.y, abs=1e-9)
    assert second.x > first.x + 40.0


def test_building_twice_gives_the_same_diagram() -> None:
    """Fresh node ids on every build would make two renders of one figure
    disagree byte for byte."""
    p = panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 1.0))
    p.line(((0.0, 0.0), (10.0, 1.0)))
    assert p.build() is p.build()


def test_touching_a_panel_after_building_rebuilds_it() -> None:
    p = panel(60.0, 40.0, x=(0.0, 10.0), y=(0.0, 1.0))
    first = p.build()
    p.outline()
    assert p.build() is not first


def test_an_unknown_panel_side() -> None:
    with pytest.raises(ValueError, match="unknown axis side"):
        panel(60.0, 40.0).axis("diagonal")


# --- matrices ----------------------------------------------------------------


GREY = ramp(("#ffffff", "#000000"))


def cells_of(p) -> list:
    return [q for q in resolve(as_drawn(p.build())).values()
            if q.diagram.kind == MARK_KIND]


def test_a_matrix_draws_one_cell_per_value() -> None:
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([[0.0, 0.5, 1.0], [1.0, 0.5, 0.0]], ramp=GREY)

    assert len(cells_of(p)) == 6


def test_a_matrix_covers_the_area_edge_to_edge() -> None:
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([[0.0, 1.0], [1.0, 0.0]], ramp=GREY)

    covered = None
    for cell in cells_of(p):
        covered = cell.bbox if covered is None else covered.union(cell.bbox)

    assert covered.width == pytest.approx(40, abs=2.0)
    assert covered.height == pytest.approx(20, abs=2.0)


def test_matrix_rows_run_top_to_bottom() -> None:
    """`values[0]` is the first row, and a reader expects it at the top."""
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([[0.0], [1.0]], ramp=GREY)

    first, second = sorted(cells_of(p), key=lambda c: c.bbox.y0)

    assert first.diagram.style.fill == "#ffffff"      # values[0], at the top
    assert second.diagram.style.fill == "#000000"


def test_matrix_cells_overlap_so_no_grid_shows() -> None:
    """Same reason a colorbar's bands overlap: abutting rects antialias to a
    pale seam, once per join, which reads as a grid over the whole matrix."""
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([[0.0, 1.0, 0.0, 1.0]], ramp=GREY)

    left, right = sorted(cells_of(p), key=lambda c: c.bbox.x0)[:2]

    assert left.bbox.x1 > right.bbox.x0


def test_a_matrix_takes_the_scale_the_colorbar_takes() -> None:
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([[1.0, 1000.0]], ramp=GREY, scale=log((1.0, 1000.0)))

    low, high = sorted(cells_of(p), key=lambda c: c.bbox.x0)

    assert low.diagram.style.fill == "#ffffff"
    assert high.diagram.style.fill == "#000000"


def test_matrix_cells_are_marks_so_they_do_not_crowd_each_other() -> None:
    """Without this a 40 x 90 matrix is 20,500 CROWDING findings about its own
    neighbours, which buries every other diagnostic in the report."""
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([[c / 9.0 for c in range(10)] for _ in range(10)], ramp=GREY)

    assert lint(p.build()) == []


def test_explicit_centres_go_through_the_scale() -> None:
    p = panel(40, 20, x=(0, 10), y=(0, 1))
    p.matrix([[0.0, 1.0]], ramp=GREY, x=[0, 10])

    left, right = sorted(cells_of(p), key=lambda c: c.bbox.x0)

    assert left.bbox.center.x == pytest.approx(-20.0, abs=1.5)
    assert right.bbox.center.x == pytest.approx(20.0, abs=1.5)


def test_a_matrix_needs_values() -> None:
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    with pytest.raises(DiagramError, match="at least one row"):
        p.matrix([], ramp=GREY)


def test_a_matrix_needs_square_rows() -> None:
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    with pytest.raises(DiagramError, match="equal length"):
        p.matrix([[0.0, 1.0], [0.0]], ramp=GREY)


def test_cells_meet_at_the_midpoints_when_the_samples_are_uneven() -> None:
    """Unevenly sampled data: a cell reaches half way to each neighbour.

    The old fixed pitch drew every cell the width of the first gap, which put
    gaps and overlaps into a heat map of, say, a log-spaced sweep.
    """
    p = panel(40, 20, x=(0, 10), y=(0, 1))
    p.matrix([[0.0, 0.5, 1.0]], ramp=GREY, x=[0, 2, 10])

    left, middle, right = sorted(cells_of(p), key=lambda c: c.bbox.x0)

    # 0, 2, 10 map to -20, -12, 20, so the cells meet at -16 and 4 and the
    # outer two reach half a gap past the samples: 8mm, 20mm, 32mm, each grown
    # a hair so neighbours overlap rather than leave a seam.
    assert left.bbox.width == pytest.approx(8.0, rel=0.1)
    assert middle.bbox.width == pytest.approx(20.0, rel=0.1)
    assert right.bbox.width == pytest.approx(32.0, rel=0.1)
    assert left.bbox.x1 >= middle.bbox.x0                      # no gap
    assert middle.bbox.x1 >= right.bbox.x0
    assert middle.bbox.center.x == pytest.approx(-6.0, abs=0.01)


def test_evenly_spaced_cells_are_still_all_one_size() -> None:
    p = panel(40, 20, x=(0, 10), y=(0, 1))
    p.matrix([[0.0, 0.5, 1.0]], ramp=GREY, x=[0, 5, 10])

    widths = {round(c.bbox.width, 6) for c in cells_of(p)}
    assert len(widths) == 1


# --- tick label formatting ---------------------------------------------------


def test_a_suffix_is_appended_to_every_number() -> None:
    assert tick_texts(linear((0.0, 100.0)), (0.0, 50.0, 100.0), format=" %") == (
        "0 %", "50 %", "100 %")


def test_a_format_string_is_applied_to_the_value() -> None:
    got = tick_texts(linear((0.0, 1.0)), (0.0, 0.5, 1.0), format="{:.2f}x")
    assert got == ("0.00x", "0.50x", "1.00x")


def test_a_callable_format_gets_the_value_itself() -> None:
    got = tick_texts(linear((0.0, 3.0)), (1.0, 2.0), format=lambda v: "ab"[int(v) - 1])
    assert got == ("a", "b")


def test_si_labels_share_one_prefix_across_the_whole_axis() -> None:
    got = tick_texts(linear((0.0, 3000.0)), (0.0, 1000.0, 2000.0, 3000.0), si=True)
    assert got == ("0", "1 k", "2 k", "3 k")


def test_si_labels_reach_below_one() -> None:
    got = tick_texts(linear((0.0, 3e-6)), (1e-6, 2e-6, 3e-6), si=True)
    assert got == ("1 µ", "2 µ", "3 µ")


def test_an_si_axis_carries_the_prefix_into_the_page() -> None:
    node = axis(linear((0.0, 4000.0)), si=True, length=60.0)
    assert any(p.diagram.prim.lines[0].text.endswith("k")
               for p in placements(node, TICK_LABEL_KIND))


# --- minor ticks -------------------------------------------------------------


def test_minor_ticks_are_off_until_asked_for() -> None:
    plain = axis(linear((0.0, 10.0)), length=60.0)
    dense = axis(linear((0.0, 10.0)), length=60.0, minor=True)

    assert len(boxes(dense, TICK_KIND)) > len(boxes(plain, TICK_KIND))


def test_a_minor_tick_is_shorter_than_a_major_one() -> None:
    node = axis(linear((0.0, 10.0)), length=60.0, minor=True)

    lengths = sorted({round(b.height, 4) for b in boxes(node, TICK_KIND)})
    assert len(lengths) == 2
    assert lengths[0] < lengths[1]


def test_minor_ticks_land_between_the_majors() -> None:
    node = axis(linear((0.0, 10.0)), length=60.0, minor=True)

    xs = sorted(b.center.x for b in boxes(node, TICK_KIND))
    steps = [round(b - a, 4) for a, b in zip(xs, xs[1:])]
    assert len(set(steps)) == 1                       # one even comb


def test_the_number_of_pieces_may_be_asked_for() -> None:
    node = axis(linear((0.0, 10.0)), length=60.0, minor=4)

    assert len(boxes(node, TICK_KIND)) == 5 + 4 * 4   # 5 majors, 3 minors each


def test_minor_ticks_stay_away_when_there_is_no_room_for_them() -> None:
    """Nine decades in 20mm is a solid comb, not information."""
    tight = axis(log((1e-3, 1e6)), length=20.0, minor=True)
    roomy = axis(log((1e-3, 1e6)), length=200.0, minor=True)

    assert len(boxes(tight, TICK_KIND)) < len(boxes(roomy, TICK_KIND))


def test_log_minor_ticks_are_the_mantissas() -> None:
    node = axis(log((1.0, 100.0)), length=120.0, minor=True)

    assert len(boxes(node, TICK_KIND)) > 3


# --- labels off --------------------------------------------------------------


def test_an_axis_can_keep_its_ticks_and_drop_its_numbers() -> None:
    node = axis(linear((0.0, 10.0)), length=60.0, labels=False)

    assert boxes(node, TICK_KIND)
    assert boxes(node, SPINE_KIND)
    assert not boxes(node, TICK_LABEL_KIND)


def test_a_nameless_axis_without_numbers_takes_no_room_for_them() -> None:
    with_numbers = axis(linear((0.0, 10.0)), length=60.0)
    without = axis(linear((0.0, 10.0)), length=60.0, labels=False)

    assert without.bbox.height < with_numbers.bbox.height


def test_an_axis_label_still_sits_clear_when_the_numbers_are_gone() -> None:
    node = axis(linear((0.0, 10.0)), length=60.0, labels=False, label="t / s")

    name = boxes(node, AXIS_LABEL_KIND)[0]
    assert name.y0 > boxes(node, SPINE_KIND)[0].y1


# --- nice domains ------------------------------------------------------------


def test_a_panel_leaves_the_domain_alone_by_default() -> None:
    p = panel(60, 40, x=(0.45, 1.3), y=(0, 1))

    assert p.x.domain == (0.45, 1.3)


def test_nice_rounds_the_domain_out_to_the_tick_lattice() -> None:
    p = panel(60, 40, x=(0.45, 1.3), y=(-0.06, 3.7), nice=True)

    assert p.x.domain == (0.4, 1.4)
    assert p.y.domain[0] <= -0.06 and p.y.domain[1] >= 3.7
    assert p.y.domain[1] == 4.0


# --- the domain a picture declares -------------------------------------------


def test_a_matrix_records_the_domain_its_colours_were_mapped_through() -> None:
    """`inklet.diagnostics` cannot see two domains over one ramp by colour alone.

    A bar labelled 0..100 over a matrix mapped 0..10 draws exactly the same
    pixels, so the rule reads a declared domain instead. This is the plot layer
    holding up its end of that contract.
    """
    from inklet.plot import colorbar, ramp as make_ramp

    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([[0.0, 5.0, 10.0]], ramp=GREY, scale=linear((0.0, 10.0)))
    bar = colorbar(make_ramp(("#ffffff", "#000000")), scale=linear((0.0, 100.0)))

    assert p.build().notes["scale_domain"] == (0.0, 10.0)
    assert bar.notes["scale_domain"] == (0.0, 100.0)


def test_a_matrix_with_no_scale_declares_nothing() -> None:
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([[0.0, 1.0]], ramp=GREY)

    assert "scale_domain" not in p.build().notes


def test_a_categorical_scale_has_no_domain_to_declare() -> None:
    """A `Band` has categories, not a range, and two of them cannot disagree
    about one."""
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([["a", "b"]], ramp=GREY, scale=band(["a", "b"]))

    assert "scale_domain" not in p.build().notes


def test_a_key_and_a_picture_on_two_domains_is_a_finding() -> None:
    from inklet.plot import colorbar, ramp as make_ramp

    bar = make_ramp(("#ffffff", "#000000"))
    p = panel(40, 20, x=(0, 1), y=(0, 1))
    p.matrix([[0.0, 5.0, 10.0]], ramp=GREY, scale=linear((0.0, 10.0)))
    sheet = row([p.build(), colorbar(bar, scale=linear((0.0, 100.0)))], gap=8)

    codes = [d.code for d in lint(sheet)]
    assert "KEY_MISMATCH" in codes


# --- rotated tick labels -----------------------------------------------------
#
# The other answer to labels that will not fit, and the only one available when
# every label has to stay: eight named conditions along a 39mm panel.


def test_rotating_the_labels_turns_them() -> None:
    cats = ["alpha strain", "beta strain", "gamma strain", "delta variant"]
    upright = axis(band(cats), length=40.0)
    slanted = axis(band(cats), length=40.0, rotate=45.0)
    tall = boxes(slanted, TICK_LABEL_KIND)[0]
    flat = boxes(upright, TICK_LABEL_KIND)[0]
    assert tall.height > flat.height * 2
    assert tall.width < flat.width


def test_a_slanted_label_ends_under_its_tick() -> None:
    """The last letter of the word sits on the tick, and the word runs away
    from the plot -- otherwise the reader has to guess which end to read from."""
    cats = ["alpha strain", "beta strain", "gamma strain"]
    node = axis(band(cats), length=40.0, rotate=45.0)
    scale = band(cats).with_range(0.0, 40.0)
    for text, box in zip(cats, boxes(node, TICK_LABEL_KIND)):
        assert box.x1 == pytest.approx(scale.map(text), abs=0.3)


def test_slanting_lets_labels_stay_that_upright_would_lose() -> None:
    cats = [f"condition {i}" for i in range(8)]
    upright = axis(band(cats), length=40.0, thin=True)
    slanted = axis(band(cats), length=40.0, thin=True, rotate=45.0)
    assert len(boxes(slanted, TICK_LABEL_KIND)) > len(boxes(upright,
                                                            TICK_LABEL_KIND))


def test_slanted_labels_still_do_not_collide() -> None:
    cats = [f"condition {i}" for i in range(8)]
    found = boxes(axis(band(cats), length=40.0, thin=True, rotate=45.0),
                  TICK_LABEL_KIND)
    # Neighbouring 45-degree labels are parallel strips, so their *boxes*
    # overlap while the type does not. What must clear is the perpendicular
    # distance between the anchors, which is the spacing times sin 45.
    anchors = sorted(box.x1 for box in found)
    height = max(box.height for box in found) / (2 ** 0.5)
    assert all(b - a >= height / (2 ** 0.5) * 0.9
               for a, b in zip(anchors, anchors[1:]))


def test_the_axis_name_clears_the_slanted_labels() -> None:
    cats = ["alpha strain", "beta strain", "gamma strain"]
    node = axis(band(cats), length=40.0, rotate=45.0, label="strain")
    name = boxes(node, AXIS_LABEL_KIND)[0]
    assert all(not overlap(name, box) for box in boxes(node, TICK_LABEL_KIND))


def test_leaning_the_other_way_hangs_from_the_other_corner() -> None:
    cats = ["alpha strain", "beta strain"]
    node = axis(band(cats), length=40.0, rotate=-45.0)
    scale = band(cats).with_range(0.0, 40.0)
    for text, box in zip(cats, boxes(node, TICK_LABEL_KIND)):
        assert box.x0 == pytest.approx(scale.map(text), abs=0.3)


def test_slanted_labels_do_not_read_as_overlapping_boxes() -> None:
    """BACKLOG 424: six categories at 45 degrees used to be four OVERLAPs.

    The picture was always right; the boxes were the wrong shape. Where the
    axis has proved its own clearance, it says so with `inklet.abutting`.
    """
    from inklet.diagnostics import lint as run_lint

    cats = ["baseline", "cue onset", "delay", "response", "reward",
            "intertrial"]
    p = panel(39, 24, x=cats, y=(0, 1))
    p.bars(cats, [0.2, 0.5, 0.7, 0.4, 0.6, 0.3])
    p.axis("bottom", rotate=45.0)
    codes = {d.code for d in run_lint(as_drawn(p.build()))}
    assert "OVERLAP" not in codes


def test_upright_labels_are_not_declared_abutting() -> None:
    """The declaration is scoped to the case that earns it."""
    from inklet.diagnostics.abut import abutting

    cats = ["wt", "ko"]
    node = axis(band(cats), length=40.0)
    kinds = {placed.diagram.kind for placed in resolve(as_drawn(node)).values()}
    assert abutting(TICK_LABEL_KIND) not in kinds


def test_a_panel_passes_the_rotation_through() -> None:
    cats = ["alpha strain", "beta strain", "gamma strain"]
    p = panel(40, 30, x=cats, y=(0, 10))
    p.bars(cats, [1, 2, 3]).axis("bottom", rotate=45.0)
    flat = panel(40, 30, x=cats, y=(0, 10))
    flat.bars(cats, [1, 2, 3]).axis("bottom")
    assert p.build().bbox.height > flat.build().bbox.height


# --- tabular figures ---------------------------------------------------------


def test_tabular_figures_are_on_by_default() -> None:
    """A column of tick labels is a table, and a table wants lining digits.

    Noto Sans's default figures are already tabular, so asking for the feature
    moved no bytes in the corpus -- but the axis should not depend on that.
    """
    ticks = [1111.0, 1000.0, 1888.0]
    lining = axis(linear((0.0, 2000.0)), length=60.0, ticks=ticks)
    widths = {round(box.width, 6) for box in boxes(lining, TICK_LABEL_KIND)}
    assert len(widths) == 1


def test_tabular_figures_can_be_turned_off() -> None:
    """For a face whose tabular digits are uglier than its proportional ones."""
    plain = axis(linear((0.0, 1000.0)), length=60.0, tnum=False)
    assert boxes(plain, TICK_LABEL_KIND)


# --- an axis that crosses the data -------------------------------------------


def test_an_axis_can_cross_at_a_data_value() -> None:
    p = panel(40, 30, x=(0, 10), y=(-1, 1))
    p.axis("bottom", at=0.0)
    spine = boxes(p.build(), SPINE_KIND)[0]
    assert spine.center.y == pytest.approx(p.y.map(0.0), abs=1e-6)


def test_a_crossing_axis_is_read_on_the_perpendicular_scale() -> None:
    p = panel(40, 30, x=(-5, 5), y=(0, 10))
    p.axis("left", at=0.0)
    spine = boxes(p.build(), SPINE_KIND)[0]
    assert spine.center.x == pytest.approx(p.x.map(0.0), abs=1e-6)


def test_without_at_an_axis_is_still_on_the_edge() -> None:
    p = panel(40, 30, x=(0, 10), y=(-1, 1))
    p.axis("bottom")
    spine = boxes(p.build(), SPINE_KIND)[0]
    assert spine.center.y == pytest.approx(p.area.y1, abs=1e-6)
