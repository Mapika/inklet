"""inklet.plot: scales, and the numbers they choose to show.

Tick selection is the part of a plotting stack that a reader notices without
knowing they noticed. Everything here is about the numbers being ones a person
can divide in their head.
"""

from __future__ import annotations

import math

import pytest

from inklet.plot.scale import (
    Scale, ScaleError, band, format_number, linear, log, log_ticks, nice_bounds,
    nice_step, nice_ticks, power_label, si_labels, symlog,
)


def is_one_two_or_five(step: float) -> bool:
    """A step a reader can count by."""
    magnitude = 10.0 ** math.floor(math.log10(step))
    return round(step / magnitude, 6) in (1.0, 2.0, 5.0, 10.0)


def spacing(ticks) -> float:
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert max(gaps) - min(gaps) < 1e-9, f"uneven ticks: {ticks}"
    return gaps[0]


# --- nice numbers ------------------------------------------------------------


def test_ticks_over_a_range_spanning_zero() -> None:
    assert nice_ticks(-3.2, 7.9) == (-2.0, 0.0, 2.0, 4.0, 6.0)


def test_a_range_spanning_zero_gets_a_tick_exactly_at_zero() -> None:
    """Not 1e-17, and not -0.0: zero is the value a reader checks for."""
    for lo, hi in ((-3.2, 7.9), (-0.06, 0.02), (-1e4, 3e4), (-7.0, 7.0)):
        ticks = nice_ticks(lo, hi)
        assert 0.0 in ticks
        assert format_number(0.0, spacing(ticks)) in ("0", "0.0", "0.00", "0.000")


@pytest.mark.parametrize("lo,hi", [
    (-100.0, -20.0), (-1.0, -0.001), (0.0, 1.0), (0.9999, 1.0001),
    (-3.2, 7.9), (1e-6, 4e-6), (2e5, 9e5), (-1e5, 1e5), (0.0, 7.0),
])
def test_every_step_is_a_one_two_or_five_decade(lo: float, hi: float) -> None:
    """`linspace` would divide 7.9 - -3.2 into 2.22, which is not a number."""
    ticks = nice_ticks(lo, hi)
    assert len(ticks) >= 2
    assert is_one_two_or_five(spacing(ticks))


@pytest.mark.parametrize("lo,hi", [
    (-100.0, -20.0), (0.9999, 1.0001), (-3.2, 7.9), (1e-6, 4e-6), (0.0, 7.0),
])
def test_ticks_stay_inside_the_domain(lo: float, hi: float) -> None:
    ticks = nice_ticks(lo, hi)
    assert ticks[0] >= lo - 1e-12 and ticks[-1] <= hi + 1e-12


def test_a_negative_range_ticks_like_a_positive_one() -> None:
    assert nice_ticks(-100.0, -20.0) == (-100.0, -80.0, -60.0, -40.0, -20.0)


def test_a_tiny_range_still_gets_round_numbers() -> None:
    ticks = nice_ticks(0.9999, 1.0001)
    assert ticks[0] == pytest.approx(0.9999) or ticks[0] > 0.9999
    assert all(abs(t - round(t, 5)) < 1e-12 for t in ticks)


def test_a_domain_with_no_width_has_one_number_in_it() -> None:
    assert nice_ticks(4.0, 4.0) == (4.0,)


def test_the_count_is_a_target_not_a_promise() -> None:
    """Asking for 3 gives round numbers near 3, never 3 arbitrary ones."""
    for count in (2, 3, 5, 8, 12):
        ticks = nice_ticks(0.0, 100.0, count)
        assert count / 2 <= len(ticks) <= count * 2 + 1
        assert is_one_two_or_five(spacing(ticks))


def test_a_reversed_domain_still_comes_back_ascending() -> None:
    assert nice_ticks(7.9, -3.2) == nice_ticks(-3.2, 7.9)


def test_nice_bounds_end_the_axis_on_a_tick() -> None:
    lo, hi = nice_bounds(-3.2, 7.9)
    assert (lo, hi) == (-4.0, 8.0)
    assert lo in nice_ticks(lo, hi) and hi in nice_ticks(lo, hi)


def test_a_non_finite_domain_is_refused() -> None:
    with pytest.raises(ScaleError, match="non-finite"):
        nice_ticks(0.0, float("inf"))


def test_a_step_needs_a_positive_span() -> None:
    with pytest.raises(ScaleError, match="span"):
        nice_step(0.0)


# --- labels ------------------------------------------------------------------


def test_one_axis_gets_one_number_of_decimals() -> None:
    step = 0.5
    assert [format_number(v, step) for v in (0.0, 0.5, 1.0)] == ["0.0", "0.5", "1.0"]


def test_a_tick_at_minus_zero_is_a_tick_at_zero() -> None:
    assert format_number(-0.0, 1.0) == "0"
    assert format_number(-0.0000001, 0.1) == "0.0"


def test_very_large_and_very_small_numbers_go_exponential() -> None:
    assert format_number(2.5e-6) == "2.5e-6"
    assert format_number(3e8) == "3e8"


def test_labels_do_not_drift() -> None:
    """0.1 + 0.1 + 0.1 is 0.30000000000000004; a tick lattice must not be."""
    assert [format_number(t, 0.1) for t in nice_ticks(0.0, 0.5, 5)] == [
        "0.0", "0.1", "0.2", "0.3", "0.4", "0.5",
    ]


# --- linear ------------------------------------------------------------------


def test_linear_maps_the_domain_onto_the_range() -> None:
    scale = linear((0.0, 10.0), (0.0, 50.0))
    assert scale.map(0.0) == 0.0
    assert scale.map(10.0) == 50.0
    assert scale.map(2.5) == 12.5


def test_linear_inverts() -> None:
    scale = linear((-3.0, 11.0), (20.0, -20.0))
    for value in (-3.0, 0.0, 4.4, 11.0):
        assert scale.invert(scale.map(value)) == pytest.approx(value)


def test_a_range_may_run_backwards() -> None:
    """Which is how a y axis is built: data up the page, y down it."""
    scale = linear((0.0, 1.0), (20.0, -20.0))
    assert scale.map(1.0) < scale.map(0.0)


def test_a_domain_of_one_value_lands_in_the_middle() -> None:
    assert linear((5.0, 5.0), (0.0, 10.0)).map(5.0) == 5.0


def test_clamping_holds_the_ends() -> None:
    scale = linear((0.0, 1.0), (0.0, 10.0), clamp=True)
    assert scale.map(-4.0) == 0.0 and scale.map(9.0) == 10.0


def test_lengths_and_units() -> None:
    assert linear((0.0, 1.0), (0.0, "40mm")).length == 40.0


def test_a_domain_is_a_pair() -> None:
    with pytest.raises(ScaleError, match="a domain is"):
        linear(4.0)


# --- log ---------------------------------------------------------------------


def test_a_log_domain_must_be_positive() -> None:
    with pytest.raises(ScaleError, match="use symlog"):
        log((0.0, 100.0))
    with pytest.raises(ScaleError, match="use symlog"):
        log((-1.0, 100.0))


def test_a_log_scale_refuses_to_place_zero() -> None:
    with pytest.raises(ScaleError, match="undefined at or below zero"):
        log((1.0, 100.0)).map(0.0)


def test_decades_land_exactly() -> None:
    """log(1000, 10) is 2.9999999999999996, and a tick one pixel short of the
    end of the axis is a bug you find in print."""
    scale = log((1.0, 1000.0), (0.0, 30.0))
    assert scale.map(1000.0) == pytest.approx(30.0, abs=1e-12)
    assert scale.map(10.0) == pytest.approx(10.0, abs=1e-12)
    assert scale.ticks() == (1.0, 10.0, 100.0, 1000.0)


def test_a_short_log_range_subdivides_the_decade() -> None:
    assert log_ticks(1.0, 4.0) == (1.0, 2.0, 3.0, 4.0)


def test_a_long_log_range_thins_to_every_nth_decade() -> None:
    ticks = log_ticks(1e-6, 1e6, 5)
    assert ticks[0] == pytest.approx(1e-6) and ticks[-1] == pytest.approx(1e6)
    assert len(ticks) <= 8
    for a, b in zip(ticks, ticks[1:]):
        assert b / a == pytest.approx(ticks[1] / ticks[0])


def test_log_inverts() -> None:
    scale = log((0.1, 100.0), (0.0, 60.0))
    for value in (0.1, 1.0, 7.3, 100.0):
        assert scale.invert(scale.map(value)) == pytest.approx(value)


def test_log_labels_are_written_to_their_own_precision() -> None:
    scale = log((0.01, 10.0))
    assert scale.tick_labels(scale.ticks()) == ("0.01", "0.1", "1", "10")


# --- symlog ------------------------------------------------------------------


def test_symlog_crosses_zero() -> None:
    scale = symlog((-1000.0, 1000.0), (0.0, 100.0))
    assert scale.map(0.0) == pytest.approx(50.0)
    assert scale.map(-1000.0) == pytest.approx(0.0)
    assert scale.map(1000.0) == pytest.approx(100.0)


def test_symlog_is_odd_about_zero() -> None:
    scale = symlog((-100.0, 100.0), (-50.0, 50.0))
    for value in (0.3, 1.0, 17.0, 100.0):
        assert scale.map(-value) == pytest.approx(-scale.map(value))


def test_symlog_inverts_on_both_sides() -> None:
    scale = symlog((-100.0, 100.0), (0.0, 80.0), linthresh=1.0)
    for value in (-100.0, -3.0, -0.4, 0.0, 0.4, 3.0, 100.0):
        assert scale.invert(scale.map(value)) == pytest.approx(value, abs=1e-9)


def test_symlog_ticks_reach_both_ends_and_include_zero() -> None:
    ticks = symlog((-1000.0, 1000.0)).ticks()
    assert ticks[0] == pytest.approx(-1000.0)
    assert ticks[-1] == pytest.approx(1000.0)
    assert 0.0 in ticks
    assert list(ticks) == sorted(ticks)


def test_linthresh_must_be_positive() -> None:
    with pytest.raises(ScaleError, match="linthresh"):
        symlog((-1.0, 1.0), linthresh=0.0)


# --- band --------------------------------------------------------------------


CATEGORIES = ("wt", "ko", "rescue")


def test_a_band_scale_puts_each_category_in_its_own_slot() -> None:
    scale = band(CATEGORIES, (0.0, 60.0))
    centres = [scale.map(c) for c in CATEGORIES]
    assert centres == sorted(centres)
    assert spacing(tuple(centres)) == pytest.approx(scale.step)
    assert 0.0 < centres[0] < centres[-1] < 60.0


def test_a_band_is_narrower_than_its_step() -> None:
    scale = band(CATEGORIES, (0.0, 60.0), padding=0.2)
    assert scale.bandwidth == pytest.approx(scale.step * 0.8)
    lo, hi = scale.edges("ko")
    assert hi - lo == pytest.approx(scale.bandwidth)
    assert lo < scale.map("ko") < hi


def test_bands_do_not_overlap() -> None:
    scale = band(CATEGORIES, (0.0, 60.0))
    edges = [scale.edges(c) for c in CATEGORIES]
    for (_, before), (after, _) in zip(edges, edges[1:]):
        assert after > before


def test_a_band_scale_inverts_to_the_nearest_category() -> None:
    scale = band(CATEGORIES, (0.0, 60.0))
    assert scale.invert(scale.map("ko")) == "ko"
    assert scale.invert(-100.0) == "wt"


def test_a_band_axis_labels_every_category() -> None:
    """Skipping one would leave the reader guessing which bar is which."""
    scale = band(CATEGORIES, (0.0, 60.0))
    assert scale.ticks(2) == CATEGORIES
    assert scale.tick_labels(scale.ticks()) == CATEGORIES


def test_an_unknown_category_says_what_it_knows() -> None:
    with pytest.raises(ScaleError, match="unknown category 'nope'"):
        band(CATEGORIES).map("nope")


def test_categories_must_be_distinct() -> None:
    with pytest.raises(ScaleError, match="distinct"):
        band(("a", "b", "a"))


def test_a_band_scale_needs_a_category() -> None:
    with pytest.raises(ScaleError, match="at least one category"):
        band(())


# --- the interface -----------------------------------------------------------


@pytest.mark.parametrize("scale", [
    linear((0.0, 10.0), (0.0, 40.0)),
    log((1.0, 1000.0), (0.0, 40.0)),
    symlog((-10.0, 10.0), (0.0, 40.0)),
    band(CATEGORIES, (0.0, 40.0)),
])
def test_every_scale_maps_ticks_inside_its_range(scale: Scale) -> None:
    for value in scale.ticks():
        assert -1e-9 <= scale.map(value) <= 40.0 + 1e-9
    assert len(scale.tick_labels(scale.ticks())) == len(scale.ticks())


@pytest.mark.parametrize("scale", [
    linear((0.0, 10.0)), log((1.0, 1000.0)), symlog((-10.0, 10.0)),
    band(CATEGORIES),
])
def test_re_ranging_keeps_the_domain(scale: Scale) -> None:
    moved = scale.with_range(10.0, 90.0)
    assert moved.range == (10.0, 90.0)
    assert moved.domain == scale.domain
    assert type(moved) is type(scale)


# --- SI prefixes and powers --------------------------------------------------


def test_one_prefix_serves_the_whole_axis() -> None:
    """Mixing 900 and 1 k on one axis makes a reader do arithmetic."""
    assert si_labels((0.0, 500.0, 1000.0, 1500.0)) == (
        "0", "0.5 k", "1.0 k", "1.5 k")


def test_si_labels_leave_small_numbers_alone() -> None:
    assert si_labels((0.0, 1.0, 2.0)) == ("0", "1", "2")


def test_si_labels_go_down_as_well_as_up() -> None:
    assert si_labels((1e-9, 2e-9)) == ("1 n", "2 n")


def test_si_labels_stop_at_the_prefixes_that_exist() -> None:
    got = si_labels((1e30, 2e30))
    assert got[0].endswith("Y") or "e" in got[0].lower()


def test_a_power_label_uses_the_superscript_markup() -> None:
    assert power_label(1000.0) == "10^{3}"
    assert power_label(0.001) == "10^{-3}"


def test_a_power_label_keeps_a_mantissa_when_there_is_one() -> None:
    assert power_label(2.5e5).startswith("2.5")
    assert "10^{5}" in power_label(2.5e5)


def test_a_log_axis_of_decades_drops_the_padding_zeros() -> None:
    """0.10 / 1.00 / 10.00 is the shared-decimals rule misapplied."""
    scale = log((0.1, 100.0))
    ticks = scale.ticks(5)
    assert scale.tick_labels(ticks) == ("0.1", "1", "10", "100")


def test_a_log_axis_of_four_decades_sets_its_ticks_as_powers() -> None:
    """Where a column of numbers stops being a column: 1 against 10000."""
    scale = log((1.0, 1e4))
    assert scale.tick_labels(scale.ticks(5)) == (
        "10^{0}", "10^{1}", "10^{2}", "10^{3}", "10^{4}")
    # Three decades is still four digits at most, and reads better as numbers.
    assert log((1.0, 1e3)).tick_labels(log((1.0, 1e3)).ticks(5)) == (
        "1", "10", "100", "1000")


def test_a_log_axis_reaches_for_powers_only_past_readable_decimals() -> None:
    scale = log((1e-6, 1e6))
    labels = scale.tick_labels(scale.ticks(5))
    assert all("10^{" in text for text in labels)


def test_a_log_axis_inside_one_decade_still_reads_as_numbers() -> None:
    scale = log((1.0, 5.0))
    assert all("^" not in text for text in scale.tick_labels(scale.ticks(5)))


# --- minor ticks -------------------------------------------------------------


def test_a_scale_has_no_minor_ticks_unless_it_says_so() -> None:
    assert Scale.minor_ticks(linear((0.0, 10.0)), (0.0, 5.0, 10.0)) == ()


def test_linear_minor_ticks_subdivide_the_major_step() -> None:
    scale = linear((0.0, 10.0), (0.0, 100.0))
    majors = scale.ticks(5)
    minors = scale.minor_ticks(majors)

    assert minors
    assert not set(minors) & set(majors)
    for value in minors:
        assert majors[0] <= value <= majors[-1]


def test_a_five_step_is_cut_in_five_and_a_two_step_in_four() -> None:
    fives = linear((0.0, 25.0), (0.0, 200.0))
    assert len(fives.minor_ticks(fives.ticks(6))) == 5 * 4      # 5 gaps, 4 each


def test_minor_ticks_give_up_when_they_would_not_be_readable() -> None:
    scale = linear((0.0, 10.0), (0.0, 3.0))
    assert scale.minor_ticks(scale.ticks(5), clear=1.0) == ()


def test_log_minor_ticks_are_the_mantissas_of_each_decade() -> None:
    scale = log((1.0, 100.0), (0.0, 200.0))
    minors = scale.minor_ticks(scale.ticks())

    assert 2.0 in minors and 20.0 in minors
    assert 1.0 not in minors


def test_log_minor_ticks_thin_out_as_the_axis_shortens() -> None:
    long = log((1.0, 100.0), (0.0, 200.0))
    short = log((1.0, 100.0), (0.0, 12.0))

    assert len(short.minor_ticks(short.ticks(), clear=1.5)) < \
        len(long.minor_ticks(long.ticks(), clear=1.5))
