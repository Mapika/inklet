"""inklet.plot: the mark helpers, measured on the page.

The statistics get plain unit tests -- a quantile either is the R type-7
quantile or it is not -- and the geometry is checked the way the rest of the
plot tests are, by resolving the diagram and looking at where the rectangles
actually landed. That matters more here than usual: every one of these helpers
exists to save an author from converting data coordinates by hand, so the only
interesting question is whether the conversion is right.
"""

from __future__ import annotations

import math

import pytest

from inklet.core import DiagramError, Rect, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import (
    band, box_stats, histogram, kde, log, panel, quantile,
)
from inklet import use_theme


def placements(node, kind: str):
    return [p for p in resolve(as_drawn(node)).values() if p.diagram.kind == kind]


def boxes(p, kind: str = MARK_KIND) -> list[Rect]:
    return [q.bbox for q in placements(p.build(), kind)]


def fills(p, kind: str = MARK_KIND) -> list[str]:
    return [q.diagram.style.fill for q in placements(p.build(), kind)]


# --- statistics --------------------------------------------------------------


def test_quantile_is_the_type_7_quantile_r_and_numpy_agree_on() -> None:
    values = [1.0, 2.0, 3.0, 4.0]

    assert quantile(values, 0.0) == pytest.approx(1.0)
    assert quantile(values, 0.25) == pytest.approx(1.75)
    assert quantile(values, 0.5) == pytest.approx(2.5)
    assert quantile(values, 1.0) == pytest.approx(4.0)


def test_quantile_of_one_value_is_that_value() -> None:
    assert quantile([7.0], 0.31) == pytest.approx(7.0)


def test_quantile_wants_a_fraction() -> None:
    with pytest.raises(DiagramError):
        quantile([1.0, 2.0], 1.5)


def test_box_stats_puts_the_whiskers_on_real_observations() -> None:
    """Tukey's rule reaches 1.5 IQR, then stops at the last point inside it."""
    stats = box_stats([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])

    assert stats.q1 == pytest.approx(3.25)
    assert stats.q3 == pytest.approx(7.75)
    assert stats.iqr == pytest.approx(4.5)
    assert stats.high == 9              # not 7.75 + 1.5 * 4.5
    assert stats.outliers == (100,)
    assert stats.count == 10


def test_box_stats_of_a_clean_sample_has_no_outliers() -> None:
    stats = box_stats(range(1, 11))

    assert stats.outliers == ()
    assert stats.low == 1
    assert stats.high == 10


def test_box_stats_needs_a_sample() -> None:
    with pytest.raises(DiagramError):
        box_stats([])


def test_histogram_counts_every_value_once() -> None:
    values = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    edges, heights = histogram(values, 3)

    assert sum(heights) == len(values)
    assert len(edges) == len(heights) + 1


def test_histogram_puts_the_top_value_in_the_last_bin() -> None:
    """A closed last bin, or the maximum falls out of the plot entirely."""
    edges, heights = histogram([0.0, 1.0], 2)

    assert heights[-1] == 1


def test_histogram_edges_land_on_the_same_lattice_as_ticks() -> None:
    values = [i / 7.0 for i in range(50)]
    edges, _ = histogram(values, 10)

    step = edges[1] - edges[0]
    assert step == pytest.approx(0.5)
    assert edges[0] == pytest.approx(0.0)


def test_histogram_edges_may_be_given_outright() -> None:
    edges, heights = histogram([0.5, 1.5, 2.5], [0.0, 1.0, 2.0, 3.0])

    assert edges == (0.0, 1.0, 2.0, 3.0)
    assert heights == (1.0, 1.0, 1.0)


def test_a_density_histogram_integrates_to_one() -> None:
    values = [i / 11.0 for i in range(60)]
    edges, heights = histogram(values, 8, density=True)

    width = edges[1] - edges[0]
    assert sum(h * width for h in heights) == pytest.approx(1.0)


def test_histogram_of_one_repeated_value_still_has_a_bin() -> None:
    edges, heights = histogram([2.0] * 5, 4)

    assert sum(heights) == 5
    assert edges[-1] > edges[0]


def test_kde_is_a_density_and_peaks_where_the_data_is() -> None:
    values = [-1.0, -0.5, 0.0, 0.5, 1.0]
    grid = [i / 10.0 - 3.0 for i in range(61)]
    y = kde(values, grid)

    step = grid[1] - grid[0]
    assert sum(y) * step == pytest.approx(1.0, abs=0.02)
    assert grid[max(range(len(y)), key=y.__getitem__)] == pytest.approx(0.0, abs=0.2)


# --- bars --------------------------------------------------------------------


CATS = ["a", "b", "c"]


def test_a_bar_stands_on_the_baseline_and_reaches_its_value() -> None:
    p = panel(60, 40, x=CATS, y=(0, 10))
    p.bars(CATS, [5, 10, 0])
    area = p.area

    tall, short = sorted(boxes(p), key=lambda b: -b.height)
    assert area.y1 - tall.y1 == pytest.approx(0.0, abs=1e-9)     # on zero
    assert tall.height == pytest.approx(40.0)                    # 10 of 10
    assert short.height == pytest.approx(20.0)                   # 5 of 10


def test_a_zero_bar_draws_nothing_rather_than_a_hairline() -> None:
    p = panel(60, 40, x=CATS, y=(0, 10))
    p.bars(CATS, [5, 10, 0])

    assert len(boxes(p)) == 2


def test_bars_take_a_fraction_of_their_slot() -> None:
    p = panel(60, 40, x=CATS, y=(0, 10))
    p.bars(CATS, [1, 1, 1], width=0.5)

    assert boxes(p)[0].width == pytest.approx(p.x.step * 0.5)


def test_horizontal_bars_grow_along_x() -> None:
    p = panel(60, 40, x=(0, 10), y=CATS)
    p.bars(CATS, [5, 10, 2], orient="h")
    area = p.area

    widest = max(boxes(p), key=lambda b: b.width)
    assert widest.width == pytest.approx(60.0)
    assert widest.x0 == pytest.approx(area.x0)


def test_a_negative_bar_hangs_below_the_baseline() -> None:
    p = panel(60, 40, x=CATS, y=(-10, 10))
    p.bars(CATS, [-5, 5, 1])

    zero = p.y.map(0.0)
    below = [b for b in boxes(p) if b.y0 >= zero - 1e-9]
    assert len(below) == 1
    assert below[0].height == pytest.approx(10.0)


def test_stacked_bars_sit_on_each_other() -> None:
    p = panel(60, 40, x=CATS, y=(0, 10))
    p.bars(CATS, [[2, 2, 2], [3, 3, 3]], stacked=True)

    left = min(b.x0 for b in boxes(p))
    column = sorted((b for b in boxes(p) if b.x0 < left + 1e-6),
                    key=lambda b: b.y0)
    assert len(column) == 2
    assert column[0].y1 == pytest.approx(column[1].y0)           # no seam
    assert column[0].height == pytest.approx(12.0)               # the 3
    assert column[1].height == pytest.approx(8.0)                # the 2


def test_grouped_bars_share_one_slot_without_overlapping() -> None:
    p = panel(60, 40, x=CATS, y=(0, 10))
    p.bars(CATS, [[2, 2, 2], [3, 3, 3]], grouped=True)

    first, second = sorted(boxes(p), key=lambda b: b.x0)[:2]
    assert first.x1 <= second.x0 + 1e-9
    assert second.x1 - first.x0 <= p.x.step * 0.8 + 1e-9


def test_several_series_are_grouped_unless_told_to_stack() -> None:
    p = panel(60, 40, x=CATS, y=(0, 10))
    p.bars(CATS, [[2, 2, 2], [3, 3, 3]])

    assert len({round(b.x0, 6) for b in boxes(p)}) == 6


def test_bars_are_either_stacked_or_grouped() -> None:
    p = panel(60, 40, x=CATS, y=(0, 10))
    with pytest.raises(DiagramError):
        p.bars(CATS, [[1, 1, 1], [1, 1, 1]], stacked=True, grouped=True)


def test_bars_check_the_lengths_they_were_given() -> None:
    p = panel(60, 40, x=CATS, y=(0, 10))
    with pytest.raises(DiagramError):
        p.bars(CATS, [1, 2])


def test_one_series_of_bars_is_a_tint_and_several_take_the_palette() -> None:
    theme = use_theme("nature")
    single = panel(60, 40, x=CATS, y=(0, 10))
    single.bars(CATS, [1, 2, 3])
    many = panel(60, 40, x=CATS, y=(0, 10))
    many.bars(CATS, [[1, 1, 1], [2, 2, 2]], stacked=True)

    assert len(set(fills(single))) == 1
    assert set(fills(many)) == {theme.color(0), theme.color(1)}


def test_bars_take_the_colours_they_are_given() -> None:
    p = panel(60, 40, x=CATS, y=(0, 10))
    p.bars(CATS, [[1, 1, 1], [2, 2, 2]], colors=["#ff0000", "#00ff00"])

    assert set(fills(p)) == {"#ff0000", "#00ff00"}


def test_bars_on_a_numeric_axis_are_centred_on_their_x() -> None:
    p = panel(60, 40, x=(0, 3), y=(0, 10))
    p.bars([0.5, 1.5, 2.5], [1, 2, 3], width=1.0)

    first = min(boxes(p), key=lambda b: b.x0)
    assert first.center.x == pytest.approx(p.point(0.5, 0).x)
    assert first.width == pytest.approx(20.0)


# --- histogram on a panel ----------------------------------------------------


def test_hist_draws_one_bar_per_non_empty_bin() -> None:
    values = [0.0, 0.5, 1.0, 1.5, 2.0]
    edges, heights = histogram(values, 4)
    p = panel(60, 40, x=(edges[0], edges[-1]), y=(0, max(heights)))
    p.hist(values, 4)

    assert len(boxes(p)) == sum(1 for h in heights if h > 0)


def test_hist_bars_touch_because_the_bins_do() -> None:
    p = panel(60, 40, x=(0, 4), y=(0, 4))
    p.hist([0.5, 1.5, 2.5, 3.5], [0.0, 1.0, 2.0, 3.0, 4.0])

    got = sorted(boxes(p), key=lambda b: b.x0)
    for a, b in zip(got, got[1:]):
        assert a.x1 == pytest.approx(b.x0)


def test_bins_gives_the_panel_the_domain_the_histogram_wants() -> None:
    values = [i / 7.0 for i in range(50)]
    edges, heights = histogram(values, 10)
    p = panel(60, 40, x=(edges[0], edges[-1]), y=(0, max(heights)))
    p.hist(values, 10)

    covered = None
    for b in boxes(p):
        covered = b if covered is None else covered.union(b)
    assert covered.width == pytest.approx(60.0)


# --- error bars --------------------------------------------------------------


def test_an_error_bar_spans_twice_the_error() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.errorbars([(5, 5)], yerr=1)

    whisker = max(placements(p.build(), MARK_LINE_KIND), key=lambda q: q.bbox.height)
    assert whisker.bbox.height == pytest.approx(8.0)             # 2 in 10 of 40


def test_error_bars_take_one_error_per_point() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.errorbars([(1, 1), (2, 2)], yerr=[0.5, 1.5])

    heights = sorted(q.bbox.height for q in placements(p.build(), MARK_LINE_KIND))
    assert heights[-1] == pytest.approx(12.0)
    assert heights[-2] == pytest.approx(4.0)


def test_asymmetric_errors_are_a_low_high_pair() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.errorbars([(5, 5)], yerr=[(1, 3)])

    whisker = max(placements(p.build(), MARK_LINE_KIND), key=lambda q: q.bbox.height)
    assert whisker.bbox.height == pytest.approx(16.0)
    assert whisker.bbox.center.y == pytest.approx(p.point(5, 6).y)


def test_x_errors_run_across() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.errorbars([(5, 5)], xerr=2)

    whisker = max(placements(p.build(), MARK_LINE_KIND), key=lambda q: q.bbox.width)
    assert whisker.bbox.width == pytest.approx(24.0)


def test_error_bars_want_an_error() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    with pytest.raises(DiagramError):
        p.errorbars([(5, 5)])


# --- area, fill_between, step ------------------------------------------------


def test_an_area_reaches_from_the_curve_to_the_baseline() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.fill([(0, 5), (10, 5)])

    got = boxes(p)[0]
    assert got.y0 == pytest.approx(p.point(0, 5).y)
    assert got.y1 == pytest.approx(p.point(0, 0).y)
    assert got.width == pytest.approx(60.0)


def test_fill_between_spans_the_two_curves() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.fill_between([0, 10], [2, 2], [8, 8])

    got = boxes(p)[0]
    assert got.height == pytest.approx(24.0)


def test_fill_between_takes_a_constant_for_either_edge() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.fill_between([0, 10], 0, [5, 5])

    assert boxes(p)[0].height == pytest.approx(20.0)


def test_fill_between_checks_its_lengths() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    with pytest.raises(DiagramError):
        p.fill_between([0, 10], [1, 2, 3], 0)


def test_a_step_holds_its_value_until_the_next_x() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.step([(0, 2), (5, 8)])

    got = placements(p.build(), MARK_LINE_KIND)[0].bbox
    assert got.width == pytest.approx(30.0)
    assert got.height == pytest.approx(24.0)


def test_where_pre_steps_before_the_sample_not_after() -> None:
    post = panel(60, 40, x=(0, 10), y=(0, 10))
    post.step([(0, 0), (5, 10)], where="post")
    pre = panel(60, 40, x=(0, 10), y=(0, 10))
    pre.step([(0, 0), (5, 10)], where="pre")

    # Same envelope, different corner: the rise is at the start, not the end.
    assert post.build().bbox.width == pytest.approx(pre.build().bbox.width)


def test_step_wants_a_known_where() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    with pytest.raises(DiagramError):
        p.step([(0, 1), (1, 2)], where="sideways")


# --- box and violin ----------------------------------------------------------


SAMPLE = {"a": [1, 2, 3, 4, 5], "b": [2, 3, 4, 5, 6]}


def test_a_box_spans_the_interquartile_range() -> None:
    p = panel(60, 40, x=list(SAMPLE), y=(0, 10))
    p.boxplot(SAMPLE)

    stats = box_stats(SAMPLE["a"])
    tall = min(boxes(p), key=lambda b: b.x0)
    assert tall.height == pytest.approx(
        abs(p.y.map(stats.q3) - p.y.map(stats.q1)))


def test_a_box_plot_takes_a_plain_sequence_of_samples() -> None:
    p = panel(60, 40, x=["a", "b"], y=(0, 10))
    p.boxplot([[1, 2, 3], [4, 5, 6]])

    assert len(boxes(p)) == 2


def test_outliers_are_drawn_as_points() -> None:
    p = panel(60, 40, x=["a"], y=(0, 110))
    p.boxplot({"a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]})

    dots = [b for b in boxes(p) if b.width < 2.0]
    assert len(dots) == 1
    assert dots[0].center.y == pytest.approx(p.point("a", 100).y, abs=0.01)


def test_a_violin_is_symmetric_about_its_slot() -> None:
    p = panel(60, 40, x=["a", "b"], y=(0, 10))
    p.violin(SAMPLE)

    first = min(boxes(p), key=lambda b: b.x0)
    assert first.center.x == pytest.approx(p.point("a", 0).x, abs=0.01)


def test_box_and_violin_want_samples() -> None:
    p = panel(60, 40, x=["a"], y=(0, 10))
    with pytest.raises(DiagramError):
        p.boxplot([])
    with pytest.raises(DiagramError):
        p.violin([])


# --- scatter -----------------------------------------------------------------


def test_scatter_puts_one_marker_on_each_point() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.scatter([(1, 1), (5, 5), (9, 9)])

    got = sorted(boxes(p), key=lambda b: b.x0)
    assert len(got) == 3
    assert got[1].center.x == pytest.approx(p.point(5, 5).x)
    assert got[1].center.y == pytest.approx(p.point(5, 5).y)


def test_scatter_sizes_and_colours_may_be_data() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.scatter([(1, 1), (9, 9)], size=[1.0, 3.0], color=["#ff0000", "#0000ff"])

    got = sorted(placements(p.build(), MARK_KIND), key=lambda q: q.bbox.x0)
    assert got[0].bbox.width == pytest.approx(1.0)
    assert got[1].bbox.width == pytest.approx(3.0)
    assert [q.diagram.style.fill for q in got] == ["#ff0000", "#0000ff"]


def test_scatter_checks_a_per_point_sequence() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    with pytest.raises(DiagramError):
        p.scatter([(1, 1), (2, 2)], size=[1.0])


# --- reference lines, in data coordinates ------------------------------------


def test_an_hline_is_at_a_data_y_and_spans_the_area() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.hline(2.5)

    got = placements(p.build(), MARK_LINE_KIND)[0].bbox
    assert got.width == pytest.approx(60.0)
    assert got.center.y == pytest.approx(p.point(0, 2.5).y)


def test_a_vline_may_be_cut_to_a_data_span() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.vline(5, span=(2, 8))

    got = placements(p.build(), MARK_LINE_KIND)[0].bbox
    assert got.height == pytest.approx(24.0)


def test_a_vspan_is_a_band_between_two_data_x() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.vspan(2, 4)

    got = boxes(p)[0]
    assert got.width == pytest.approx(12.0)
    assert got.height == pytest.approx(40.0)


def test_an_hspan_is_a_band_between_two_data_y() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.hspan(2, 4)

    got = boxes(p)[0]
    assert got.height == pytest.approx(8.0)
    assert got.width == pytest.approx(60.0)


def test_a_rect_is_the_data_rectangle_it_names() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.rect(2, 2, 4, 6)

    got = boxes(p)[0]
    assert got.width == pytest.approx(12.0)
    assert got.height == pytest.approx(16.0)


def test_reference_marks_go_under_the_data_unless_asked() -> None:
    """A threshold behind the curve; a callout in front of it."""
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.hline(5)
    p.line([(0, 0), (10, 10)])
    p.hline(2, front=True)

    order = [q.diagram.kind for q in resolve(as_drawn(p.build())).values()
             if q.diagram.kind in (MARK_LINE_KIND, "path")]
    assert order == [MARK_LINE_KIND, "path", MARK_LINE_KIND]


def test_a_rule_is_at_one_coordinate_not_two() -> None:
    from inklet.plot.marks import rule
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    with pytest.raises(DiagramError):
        rule(p, x=1, y=1)


def test_reference_lines_work_on_a_log_axis_too() -> None:
    p = panel(60, 40, x=(0, 10), y=log((0.1, 100)))
    p.hline(1.0)

    got = placements(p.build(), MARK_LINE_KIND)[0].bbox
    assert got.center.y == pytest.approx(p.point(0, 1.0).y)


# --- the whole thing ---------------------------------------------------------


def test_a_panel_of_marks_lints_clean() -> None:
    use_theme("nature")
    p = panel(60, 40, x=CATS, y=(0, 10))
    p.bars(CATS, [3, 7, 5])
    p.errorbars([("a", 3), ("b", 7), ("c", 5)], yerr=0.5)
    p.hline(5, stroke_dash=(0.9, 0.7))
    p.axes(x="group", y="signal")

    assert not [d for d in lint(p.build()) if d.severity == "error"]


def test_marks_are_deterministic() -> None:
    def build() -> str:
        p = panel(60, 40, x=(0, 10), y=(0, 10))
        p.hist([math.sin(i) * 3 + 5 for i in range(60)], 8)
        p.scatter([(i, i) for i in range(10)])
        return repr(sorted((b.x0, b.y0, b.x1, b.y1) for b in boxes(p)))

    assert build() == build()


def test_a_bar_needs_a_band_or_a_number_it_can_map() -> None:
    p = panel(60, 40, x=band(["a", "b"]), y=(0, 10))
    p.bars(["a", "b"], [1, 2])

    assert len(boxes(p)) == 2


def test_a_twin_axis_maps_its_own_marks() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    right = p.twin_y((0, 100), axis=False)
    right.scatter([(5, 50)])

    got = boxes(p)[0]
    assert got.center.y == pytest.approx(p.point(5, 5).y, abs=0.01)


# --- error bands -------------------------------------------------------------
#
# The shaded envelope that belongs under a mean: `band()` on its own, and
# `line(err=)` as the one-call version of the same picture.


def drawn_box(node) -> Rect:
    """Where the node landed, not where its own envelope is centred.

    `Diagram.bbox` is a local measurement; a panel's content sits at panel
    coordinates, so the question these tests ask is answered by resolving.
    """
    return next(iter(resolve(as_drawn(node)).values())).bbox


def test_a_band_covers_the_ground_between_its_edges() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 10))
    p.band([0, 1, 2], [2, 3, 2], [6, 8, 6])
    box = drawn_box(p.build())
    assert box.y0 == pytest.approx(p.y.map(8), abs=1e-6)
    assert box.y1 == pytest.approx(p.y.map(2), abs=1e-6)


def test_a_band_edge_may_be_one_number() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 10))
    p.band([0, 1, 2], 0.0, [6, 8, 6])
    assert drawn_box(p.build()).y1 == pytest.approx(p.y.map(0), abs=1e-6)


def test_a_band_is_paler_than_the_line_it_belongs_to() -> None:
    from inklet.themes.color import parse_color, to_lab

    p = panel(40, 30, x=(0, 2), y=(0, 10))
    p.band([0, 1, 2], [2, 3, 2], [6, 8, 6], color="#0055aa")
    fills = [n.style.fill for n in resolve(as_drawn(p.build())).values()
             if n.style.fill]
    assert fills
    assert to_lab(parse_color(fills[0]))[0] > to_lab(parse_color("#0055aa"))[0]


def test_err_shades_a_band_by_default() -> None:
    data = [(0, 5.0), (1, 6.0), (2, 5.5)]
    plain = panel(40, 30, x=(0, 2), y=(0, 10)).line(data)
    spread = panel(40, 30, x=(0, 2), y=(0, 10)).line(data, err=1.0)
    assert drawn_box(spread.build()).height > drawn_box(plain.build()).height


def test_the_band_paints_before_the_line() -> None:
    """A line that disappears under its own uncertainty is not a line."""
    data = [(0, 5.0), (1, 6.0), (2, 5.5)]
    p = panel(40, 30, x=(0, 2), y=(0, 10)).line(data, err=1.0, name="mean")
    kinds = [n.diagram.kind for n in resolve(as_drawn(p.build())).values()]
    assert kinds.index(MARK_KIND) < len(kinds) - 1


def test_err_can_be_whiskers_instead() -> None:
    data = [(0, 5.0), (1, 6.0), (2, 5.5)]
    p = panel(40, 30, x=(0, 2), y=(0, 10))
    p.line(data, err=1.0, err_style="bars")
    assert drawn_box(p.build()).height > 0


def test_an_unknown_error_style_says_the_two_that_exist() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 10))
    with pytest.raises(DiagramError, match="band"):
        p.line([(0, 1.0), (1, 2.0)], err=1.0, err_style="cloud")


def test_asymmetric_error_is_taken_as_down_and_up() -> None:
    data = [(0, 5.0), (1, 5.0)]
    p = panel(40, 30, x=(0, 1), y=(0, 10))
    p.line(data, err=[(1.0, 3.0), (1.0, 3.0)])
    box = drawn_box(p.build())
    assert box.y0 == pytest.approx(p.y.map(8.0), abs=1e-6)
    assert box.y1 == pytest.approx(p.y.map(4.0), abs=1e-6)


# --- error-bar caps at small sizes -------------------------------------------


def _cap_width(p) -> float:
    """The widest horizontal mark-line in the drawing: a whisker's end cap."""
    widths = [placed.bbox.width
              for placed in resolve(as_drawn(p.build())).values()
              if placed.diagram.kind == MARK_LINE_KIND and placed.bbox.height < 1e-9]
    return max(widths) if widths else 0.0


def test_a_sparse_error_bar_gets_the_cap_the_type_asks_for() -> None:
    use_theme("nature")
    p = panel(40, 30, x=(0, 6), y=(0, 10))
    p.errorbars([(x, 5.0) for x in range(1, 6)], yerr=1.0)
    assert _cap_width(p) == pytest.approx(2 * 0.30 * 2.4694, abs=0.02)


def test_crowded_error_bars_get_narrower_caps() -> None:
    """Twenty points on a 40mm panel: caps sized off the type would touch."""
    use_theme("nature")
    p = panel(40, 30, x=(0, 21), y=(0, 10))
    p.errorbars([(x, 5.0) for x in range(1, 21)], yerr=1.0)
    spacing = 40.0 / 21.0
    assert _cap_width(p) == pytest.approx(2 * 0.30 * spacing, abs=0.02)
    assert _cap_width(p) < 2 * 0.30 * 2.4694


def test_caps_vanish_rather_than_smudge() -> None:
    use_theme("nature")
    p = panel(40, 30, x=(0, 121), y=(0, 10))
    p.errorbars([(x, 5.0) for x in range(1, 121)], yerr=1.0)
    assert _cap_width(p) == 0.0


def test_an_explicit_cap_is_still_obeyed() -> None:
    use_theme("nature")
    p = panel(40, 30, x=(0, 121), y=(0, 10))
    p.errorbars([(x, 5.0) for x in range(1, 121)], yerr=1.0, cap=0.8)
    assert _cap_width(p) == pytest.approx(1.6, abs=1e-6)
