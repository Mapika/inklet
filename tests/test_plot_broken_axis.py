"""inklet.plot: an axis with a piece cut out of it.

A broken axis is the one scale in the library that draws a picture the data
does not support, so the tests are mostly about the promises that make it
survivable: the bands keep one rate, no tick ever lands in the gap, the spine
stops and starts, and the note the axis leaves says where the missing stretch
went. The rule that reads that note lives in
`tests/test_diagnostics_break_distorts.py`.
"""

from __future__ import annotations

import pytest

from inklet.core import Rect, resolve
from inklet.draw.coords import as_drawn
from inklet.plot import axis, broken, linear, panel, tick_values
from inklet.plot.axis import SPINE_KIND, TICK_KIND
from inklet.plot.breaks import (
    BREAK_KIND, BREAK_NOTE, AxisBreaks, axis_breaks_note, outside_breaks,
    spine_runs,
)
from inklet.plot.panel import GRID_KIND
from inklet.plot.scale import ScaleError

#: The shape every visual test here uses: colony counts where one plate ran
#: away with it, which is the case a break is actually for.
COUNTS = {"wt": 12.0, "dA": 31.0, "dB": 44.0, "dC": 385.0}
BREAK = (45.0, 330.0)


def broken_y(length: float = 40.0):
    """A y scale over the counts, drawn bottom-up like a panel's."""
    return broken((0.0, 400.0), (length, 0.0), breaks=[BREAK], gap=1.5)


def placements(node, kind: str):
    return [p for p in resolve(as_drawn(node)).values() if p.diagram.kind == kind]


def boxes(node, kind: str) -> list[Rect]:
    return [p.bbox for p in placements(node, kind)]


def gap_of(p) -> tuple[float, float]:
    """A panel's y break as a plain low-to-high pair of panel millimetres.

    Read off the panel's own scale rather than the one handed to it: `panel`
    re-ranges what it is given onto a box centred on the origin, so the bands
    a bare scale reports are not the ones on the page.
    """
    (a, b), = p.y.gap_bands()
    return (min(a, b), max(a, b))


# --- the scale ---------------------------------------------------------------


def test_the_breaks_become_the_segments_that_are_left() -> None:
    scale = broken((0.0, 400.0), breaks=[BREAK])
    assert scale.segments == ((0.0, 45.0), (330.0, 400.0))
    assert scale.breaks == (BREAK,)


def test_a_scale_with_no_breaks_is_simply_linear_in_one_piece() -> None:
    """The factory does not decide anything on its own: no `breaks=`, no gap.
    Nothing in inklet infers a break from the data, and this is where that starts."""
    scale = broken((0.0, 400.0), (0.0, 40.0))
    assert scale.segments == ((0.0, 400.0),)
    assert scale.gap_bands() == ()
    assert scale.map(200.0) == pytest.approx(20.0)


@pytest.mark.parametrize("breaks", [
    [(-10.0, 20.0)],           # starts outside the domain
    [(380.0, 500.0)],          # ends outside it
    [(0.0, 45.0)],             # swallows the low end
    [(100.0, 100.0)],          # no width
    [(40.0, 100.0), (80.0, 200.0)],   # overlapping
])
def test_a_break_that_is_not_strictly_inside_the_domain_is_refused(breaks) -> None:
    with pytest.raises(ScaleError):
        broken((0.0, 400.0), breaks=breaks)


def test_a_break_given_backwards_is_read_as_the_same_missing_piece() -> None:
    """A break is an interval, and which end the author typed first says
    nothing about the data."""
    assert broken((0.0, 400.0), breaks=[(330.0, 45.0)]).segments == (
        (0.0, 45.0), (330.0, 400.0))


def test_every_band_is_drawn_at_the_same_millimetres_per_unit() -> None:
    """The promise that makes a length inside one band mean what it means
    inside the other. Without it the break distorts twice over."""
    scale = broken_y()
    (a0, a1), (b0, b1) = scale.bands()
    lower = abs(a1 - a0) / 45.0
    upper = abs(b1 - b0) / 70.0
    assert lower == pytest.approx(upper)


def test_the_bands_and_the_gap_add_up_to_the_range() -> None:
    scale = broken_y(40.0)
    (a0, a1), (b0, b1) = scale.bands()
    assert abs(a1 - a0) + abs(b1 - b0) + scale.gap == pytest.approx(40.0)
    assert a0 == pytest.approx(40.0)
    assert b1 == pytest.approx(0.0)      # exactly, not 3e-15 inside the panel


def test_weights_buy_a_band_more_room_than_its_span() -> None:
    scale = broken((0.0, 400.0), (0.0, 40.0), breaks=[BREAK], gap=2.0,
                   weights=(3.0, 1.0))
    (a0, a1), (b0, b1) = scale.bands()
    assert abs(a1 - a0) == pytest.approx(3.0 * abs(b1 - b0))


def test_gaps_that_do_not_fit_the_range_say_so() -> None:
    with pytest.raises(ScaleError, match="do not fit"):
        broken((0.0, 400.0), (0.0, 1.0), breaks=[BREAK], gap=1.5).bands()


def test_a_value_inside_a_break_lands_on_the_nearer_band_edge() -> None:
    """It has nowhere else to go -- that stretch of page does not exist -- and
    a line crossing the break still has to draw."""
    scale = broken_y()
    (_a0, a1), (b0, _b1) = scale.bands()
    assert scale.map(46.0) == pytest.approx(a1)
    assert scale.map(329.0) == pytest.approx(b0)


def test_data_past_the_end_of_the_axis_keeps_going_and_is_not_clamped() -> None:
    """Same as `Linear`: overflowing data should be visibly wrong, not tidied
    into the last tick."""
    scale = broken((0.0, 400.0), (0.0, 40.0), breaks=[BREAK])
    assert scale.map(-40.0) < scale.map(0.0)
    assert scale.map(440.0) > scale.map(400.0)


def test_positions_inside_the_segments_survive_the_round_trip() -> None:
    scale = broken_y()
    for value in (0.0, 12.0, 44.9, 330.0, 385.0, 400.0):
        assert scale.invert(scale.map(value)) == pytest.approx(value, abs=1e-9)


def test_no_tick_lands_inside_a_break() -> None:
    scale = broken_y()
    lo, hi = BREAK
    assert all(not (lo < t < hi) for t in scale.ticks(5)), scale.ticks(5)


def test_every_segment_gets_at_least_one_tick_of_its_own() -> None:
    """A band with no number against it is a band the reader cannot read, so
    the step refines until the short piece has one too."""
    scale = broken((0.0, 400.0), (0.0, 40.0), breaks=[(45.0, 330.0)])
    ticks = scale.ticks(5)
    for lo, hi in scale.segments:
        assert any(lo <= t <= hi for t in ticks), (lo, hi, ticks)


def test_ticks_are_one_lattice_across_both_bands() -> None:
    """Two independent lattices would give the reader two different counting
    steps on one axis."""
    ticks = sorted(broken_y().ticks(5))
    steps = {round(b - a, 9) for a, b in zip(ticks, ticks[1:])}
    step = min(steps)
    assert all(round(s / step, 6) == round(s / step) for s in steps)


def test_minor_ticks_never_cross_the_gap() -> None:
    scale = broken_y()
    majors = scale.ticks(5)
    lo, hi = BREAK
    assert all(not (lo < m < hi) for m in scale.minor_ticks(majors))


def test_a_hand_written_tick_inside_the_break_is_dropped() -> None:
    """`Broken.ticks` never proposes one; a caller passing `ticks=` can."""
    scale = broken_y()
    assert outside_breaks(scale, (0.0, 100.0, 200.0, 400.0)) == (0.0, 400.0)


def test_a_tick_exactly_on_a_band_edge_is_kept() -> None:
    """It is the last value the axis draws on that side, and dropping it would
    leave the break unlabelled on one end."""
    scale = broken_y()
    assert outside_breaks(scale, (45.0, 330.0)) == (45.0, 330.0)


def test_an_unbroken_scale_passes_every_value_through_untouched() -> None:
    assert outside_breaks(linear((0.0, 400.0)), (0.0, 100.0)) == (0.0, 100.0)


# --- the axis ----------------------------------------------------------------


def test_the_spine_is_drawn_in_one_piece_per_band() -> None:
    node = axis(broken((0.0, 400.0), (0.0, 60.0), breaks=[BREAK]), side="bottom")
    assert len(boxes(node, SPINE_KIND)) == 2


def test_the_spine_stops_where_the_gap_starts() -> None:
    scale = broken((0.0, 400.0), (0.0, 60.0), breaks=[BREAK])
    (gap_lo, gap_hi), = scale.gap_bands()
    runs = sorted(boxes(axis(scale, side="bottom"), SPINE_KIND),
                  key=lambda b: b.x0)
    assert runs[0].x1 == pytest.approx(gap_lo)
    assert runs[1].x0 == pytest.approx(gap_hi)


def test_the_break_glyph_is_drawn_across_the_gap() -> None:
    scale = broken((0.0, 400.0), (0.0, 60.0), breaks=[BREAK])
    (gap_lo, gap_hi), = scale.gap_bands()
    marks = boxes(axis(scale, side="bottom"), BREAK_KIND)
    assert len(marks) == 2                      # the two slashes
    for box in marks:
        assert gap_lo - 1.0 < box.x0 and box.x1 < gap_hi + 1.0


def test_an_unbroken_axis_draws_no_glyph_and_one_spine() -> None:
    node = axis(linear((0.0, 400.0), (0.0, 60.0)), side="bottom")
    assert len(boxes(node, SPINE_KIND)) == 1
    assert boxes(node, BREAK_KIND) == []


def test_no_tick_is_drawn_inside_the_gap_even_when_asked_for_by_hand() -> None:
    scale = broken((0.0, 400.0), (0.0, 60.0), breaks=[BREAK])
    (gap_lo, gap_hi), = scale.gap_bands()
    node = axis(scale, side="bottom", ticks=[0.0, 100.0, 200.0, 400.0])
    for box in boxes(node, TICK_KIND):
        assert not (gap_lo < box.x0 and box.x1 < gap_hi)


def test_gridlines_do_not_rule_across_the_break() -> None:
    """The gridlines come through the same `tick_values`, which is the whole
    reason the filtering lives there and not in the axis's own drawing."""
    scale = broken((0.0, 400.0), (0.0, 60.0), breaks=[BREAK])
    assert all(not (BREAK[0] < v < BREAK[1]) for v in tick_values(scale))
    p = panel(60.0, 40.0, x=(0.0, 10.0), y=broken_y())
    p.grid(x=False)
    lo, hi = gap_of(p)
    for box in boxes(p.build(), GRID_KIND):
        assert not (lo < box.y0 < hi), f"a gridline at {box.y0} is in the break"


# --- the note ----------------------------------------------------------------


def test_the_axis_leaves_a_note_saying_where_the_missing_stretch_went() -> None:
    node = axis(broken((0.0, 400.0), (0.0, 60.0), breaks=[BREAK]), side="bottom")
    note = node.notes[BREAK_NOTE]
    assert isinstance(note, AxisBreaks)
    assert note.horizontal is True
    assert note.segments == ((0.0, 45.0), (330.0, 400.0))
    assert len(note.bands) == 2


def test_a_left_axis_records_that_its_break_runs_down_the_page() -> None:
    node = axis(broken_y(), side="left")
    assert node.notes[BREAK_NOTE].horizontal is False


def test_an_unbroken_axis_leaves_no_note_at_all() -> None:
    """Which is what makes `BREAK_DISTORTS` structurally silent on every
    figure in the library that has no break."""
    node = axis(linear((0.0, 400.0), (0.0, 60.0)), side="bottom")
    assert BREAK_NOTE not in node.notes
    assert axis_breaks_note(linear((0.0, 1.0)), horizontal=True) is None


def test_the_note_reads_a_millimetre_back_into_the_value_it_stands_for() -> None:
    scale = broken_y()
    note = axis_breaks_note(scale, horizontal=False)
    for value in (0.0, 44.0, 330.0, 400.0):
        assert note.value_at(scale.map(value)) == pytest.approx(value, abs=1e-9)


def test_the_note_is_hashable_so_one_axis_is_counted_once() -> None:
    """It rides up onto every wrapper `carry_notes` builds; the reader keeps
    the deepest node per distinct value, which needs the value in a set."""
    a = axis_breaks_note(broken_y(), horizontal=False)
    b = axis_breaks_note(broken_y(), horizontal=False)
    assert len({a, b}) == 1


# --- the spine cutter --------------------------------------------------------


def test_spine_runs_with_no_gaps_is_the_whole_line() -> None:
    assert spine_runs(0.0, 60.0, ()) == [(0.0, 60.0)]


def test_spine_runs_follow_the_range_backwards_for_a_y_axis() -> None:
    """A panel's y range starts at the bottom and counts up the page, so the
    gaps have to be walked in that direction or the runs come out inverted."""
    runs = spine_runs(40.0, 0.0, [(22.5, 24.0)])
    assert runs == [(40.0, 24.0), (22.5, 0.0)]


def test_a_gap_flush_against_an_end_leaves_no_zero_length_run() -> None:
    assert spine_runs(0.0, 60.0, [(0.0, 4.0)]) == [(4.0, 60.0)]


# --- bars across the break ---------------------------------------------------


def bars_panel(*, marked: bool):
    p = panel(60.0, 40.0, x=list(COUNTS), y=broken_y())
    p.bars(list(COUNTS), list(COUNTS.values()))
    if marked:
        p.break_marks()
    p.axes(y="colonies")
    return p


def test_break_marks_cuts_only_the_bars_that_cross_the_gap() -> None:
    """Three of the four counts sit under the break; one runs through it."""
    plain = len(boxes(bars_panel(marked=False).build(), BREAK_KIND))
    marked = len(boxes(bars_panel(marked=True).build(), BREAK_KIND))
    assert plain == 2                       # the axis's own two slashes
    assert marked == 4                      # plus the two across the one bar


def test_break_marks_on_a_panel_where_nothing_crosses_changes_nothing() -> None:
    def build(mark: bool):
        p = panel(60.0, 40.0, x=["a", "b"], y=broken_y())
        p.bars(["a", "b"], [12.0, 40.0])
        if mark:
            p.break_marks()
        return p.build()
    assert len(boxes(build(True), BREAK_KIND)) == len(boxes(build(False), BREAK_KIND))


def test_the_mark_glyph_sits_inside_the_gap_it_marks() -> None:
    """Every slash the figure draws -- the axis's two and the bar's two -- is
    inside the missing stretch, give or take the tooth that overhangs it."""
    p = bars_panel(marked=True)
    lo, hi = gap_of(p)
    for box in boxes(p.build(), BREAK_KIND):
        assert lo - 1.5 < box.y0 and box.y1 < hi + 1.5, box
    assert len(boxes(p.build(), BREAK_KIND)) == 4


def test_a_bar_crossing_a_broken_x_axis_is_cut_the_other_way() -> None:
    """The cut has to face the axis it crosses; getting the two transposed
    draws two long lines down the panel, which is how this test exists."""
    p = panel(60.0, 40.0, y=["a", "b"],
              x=broken((0.0, 400.0), breaks=[BREAK]))
    p.bars(["a", "b"], [12.0, 385.0], orient="h")
    p.break_marks()
    p.axes(x="colonies")
    cuts = [b for b in boxes(p.build(), BREAK_KIND) if b.height < 6.0]
    assert cuts, "the bar cut should be short across and wide along the bar"
    assert all(cut.width < 4.0 for cut in cuts)


def test_the_same_panel_built_twice_gives_the_same_geometry() -> None:
    def corners():
        return [(b.x0, b.y0, b.x1, b.y1)
                for b in boxes(bars_panel(marked=True).build(), BREAK_KIND)]
    first, second = corners(), corners()
    assert first == second
