"""inklet.plot: dates and clock time on an axis."""

from __future__ import annotations

import datetime as dt

import pytest

from inklet.plot import panel
from inklet.plot.scale import ScaleError
from inklet.plot.timescale import (
    Time, dates, is_time_like, time_ticks, to_time,
)

DAY = dt.timedelta(days=1)


def labels(scale: Time, count: int = 5) -> tuple[str, ...]:
    ticks = scale.ticks(count)
    return scale.tick_labels(ticks)


# --- reading a value ---------------------------------------------------------


def test_every_spelling_of_one_instant_agrees() -> None:
    wanted = dt.datetime(2024, 3, 1, 9, 30)
    assert to_time("2024-03-01T09:30") == wanted
    assert to_time(dt.datetime(2024, 3, 1, 9, 30)) == wanted
    assert to_time(dt.date(2024, 3, 1)) == dt.datetime(2024, 3, 1)


def test_a_timezone_is_dropped_rather_than_honoured() -> None:
    """A figure is a picture of one clock; an axis that moves in Berlin is
    not an axis."""
    aware = dt.datetime(2024, 3, 1, 9, 0, tzinfo=dt.timezone.utc)
    assert to_time(aware) == dt.datetime(2024, 3, 1, 9, 0)


def test_something_that_is_not_a_date_says_what_one_looks_like() -> None:
    with pytest.raises(ScaleError, match="ISO 8601"):
        to_time("last Tuesday")


def test_a_bare_number_is_not_a_date() -> None:
    assert not is_time_like(2024)
    assert not is_time_like(0.0)
    assert is_time_like("2024-01-01")
    assert is_time_like(dt.date(2024, 1, 1))


def test_a_word_is_not_a_date_either() -> None:
    assert not is_time_like("control")


# --- the scale ---------------------------------------------------------------


def test_the_ends_of_the_domain_map_to_the_ends_of_the_range() -> None:
    scale = dates(("2024-01-01", "2024-12-31"), (0.0, 100.0))
    assert scale.map("2024-01-01") == pytest.approx(0.0)
    assert scale.map("2024-12-31") == pytest.approx(100.0)


def test_map_and_invert_are_inverses() -> None:
    scale = dates(("2024-01-01", "2024-12-31"), (0.0, 100.0))
    back = scale.invert(scale.map("2024-06-15T12:00"))
    assert abs((back - dt.datetime(2024, 6, 15, 12, 0)).total_seconds()) < 1.0


def test_a_panel_recognises_a_pair_of_dates() -> None:
    p = panel(60, 30, x=("2024-01-01", "2024-12-31"), y=(0, 1))
    assert isinstance(p.x, Time)


def test_a_panel_recognises_a_pair_of_datetimes() -> None:
    p = panel(60, 30, x=(dt.date(2024, 1, 1), dt.date(2024, 3, 1)), y=(0, 1))
    assert isinstance(p.x, Time)


def test_a_pair_of_numbers_is_still_a_linear_scale() -> None:
    from inklet.plot.scale import Linear

    p = panel(60, 30, x=(0, 2024), y=(0, 1))
    assert isinstance(p.x, Linear)


def test_clamping_is_carried_through_a_re_range() -> None:
    scale = dates(("2024-01-01", "2024-01-02"), (0.0, 10.0), clamp=True)
    assert scale.with_range(0.0, 20.0).map("2025-01-01") == pytest.approx(20.0)


# --- where the ticks land ----------------------------------------------------


def test_a_yearly_axis_ticks_on_new_year() -> None:
    ticks = time_ticks(dt.datetime(2019, 4, 2), dt.datetime(2025, 8, 9), 5)
    assert all(t.month == 1 and t.day == 1 for t in ticks)


def test_a_monthly_axis_ticks_on_the_first() -> None:
    ticks = time_ticks(dt.datetime(2024, 1, 17), dt.datetime(2024, 12, 3), 5)
    assert all(t.day == 1 for t in ticks)
    assert len({t.month for t in ticks}) == len(ticks)


def test_a_daily_axis_ticks_at_midnight() -> None:
    ticks = time_ticks(dt.datetime(2024, 3, 1, 7, 13),
                       dt.datetime(2024, 3, 9, 4, 2), 5)
    assert all(t.hour == 0 and t.minute == 0 for t in ticks)


def test_an_hourly_axis_ticks_on_the_hour() -> None:
    ticks = time_ticks(dt.datetime(2024, 3, 1, 8, 13),
                       dt.datetime(2024, 3, 1, 20, 2), 5)
    assert all(t.minute == 0 and t.second == 0 for t in ticks)


def test_ticks_are_inside_the_domain() -> None:
    lo, hi = dt.datetime(2024, 3, 1, 8, 13), dt.datetime(2024, 3, 1, 20, 2)
    assert all(lo <= t <= hi for t in time_ticks(lo, hi, 5))


def test_a_february_does_not_get_a_thirtieth() -> None:
    """Walking calendar units rather than adding a constant is the whole
    reason this module is not a Linear with a formatter."""
    ticks = time_ticks(dt.datetime(2024, 1, 1), dt.datetime(2024, 6, 1), 6)
    assert all(t.day == 1 for t in ticks)


def test_a_reversed_domain_is_still_ticked() -> None:
    ticks = time_ticks(dt.datetime(2024, 6, 1), dt.datetime(2024, 1, 1), 4)
    assert len(ticks) >= 2


def test_a_span_of_decades_falls_back_to_round_years() -> None:
    ticks = time_ticks(dt.datetime(1900, 1, 1), dt.datetime(2000, 1, 1), 5)
    assert all(t.month == 1 and t.day == 1 for t in ticks)
    assert all(t.year % 10 == 0 for t in ticks)


# --- what the ticks are called -----------------------------------------------


def test_a_yearly_axis_writes_years() -> None:
    scale = dates(("2010-01-01", "2024-01-01"), (0.0, 100.0))
    assert all(text.isdigit() and len(text) == 4 for text in labels(scale))


def test_a_monthly_axis_inside_one_year_omits_the_year() -> None:
    scale = dates(("2024-01-01", "2024-12-01"), (0.0, 100.0))
    assert labels(scale)[0] == "Jan"


def test_a_monthly_axis_across_two_years_keeps_it() -> None:
    scale = dates(("2023-06-01", "2025-06-01"), (0.0, 100.0))
    assert all(" " in text for text in labels(scale))


def test_a_daily_axis_writes_the_day_and_the_month() -> None:
    scale = dates(("2024-03-01", "2024-03-12"), (0.0, 100.0))
    first = labels(scale)[0]
    assert first.split()[0].isdigit() and first.split()[1].isalpha()


def test_an_hourly_axis_writes_a_clock() -> None:
    scale = dates(("2024-03-01T08:00", "2024-03-01T20:00"), (0.0, 100.0))
    assert all(":" in text for text in labels(scale))


def test_a_minute_axis_writes_minutes() -> None:
    scale = dates(("2024-03-01T08:00", "2024-03-01T08:40"), (0.0, 100.0))
    assert all(text.count(":") == 1 for text in labels(scale))


def test_the_labels_say_what_the_ticks_are_not_what_the_scale_guessed() -> None:
    """A caller's own ticks are read for coarseness the same way."""
    scale = dates(("2024-01-01", "2024-12-31"), (0.0, 100.0))
    given = [dt.datetime(2024, m, 1) for m in (1, 4, 7, 10)]
    assert scale.tick_labels(given) == ("Jan", "Apr", "Jul", "Oct")


# --- the axis it builds ------------------------------------------------------


def test_an_axis_over_a_year_of_weekly_data_reads() -> None:
    start = dt.date(2024, 1, 1)
    series = [(start + 7 * i * DAY, i % 5) for i in range(52)]
    p = panel(60, 30, x=(series[0][0], series[-1][0]), y=(0, 5))
    p.line(series).axes(x="date", y="rate")
    assert p.build().bbox.width > 60


def test_minor_ticks_divide_into_the_next_unit_down() -> None:
    scale = dates(("2020-01-01", "2024-01-01"), (0.0, 200.0))
    majors = scale.ticks(4)
    minors = scale.minor_ticks(majors, None, 1.0)
    assert minors
    assert all(m.day == 1 for m in minors)


def test_minor_ticks_that_would_not_clear_are_dropped() -> None:
    scale = dates(("2020-01-01", "2024-01-01"), (0.0, 5.0))
    assert scale.minor_ticks(scale.ticks(4), None, 2.0) == ()
