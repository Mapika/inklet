"""Date axes: where the year and the date are written, and what they read as.

The rule is the same for every calendar unit: the first tick names the year (or
the date, for a clock axis), and a tick names it again wherever it changes. No
year is written past the last tick, where a reader would have to carry it back
to the wrong end of the axis.
"""

from __future__ import annotations

import datetime as dt
import re

import inklet as i
from inklet.core import resolve
from inklet.draw.coords import as_drawn
from inklet.plot import panel
from inklet.plot.timescale import dates


def svg_texts(chart) -> list[str]:
    """Every text run in the picture, in document order."""
    return re.findall(r">([^<]+)</text>", chart.to_svg(text="names"))


def page_words(node) -> list[str]:
    return [placed.diagram.prim.text
            for placed in resolve(as_drawn(node)).values()
            if getattr(placed.diagram.prim, "text", None) is not None]


def labels_of(scale, count: int = 5) -> tuple[str, ...]:
    return scale.tick_labels(scale.ticks(count))


# The three ranges from the one-call examples: a range inside one year, a range
# of years, and a range of clock hours that spans two days.
DAYS_2021 = [dt.date(2021, 3, 1) + dt.timedelta(d) for d in range(120)]
MONTHS_2019_2024 = [dt.date(2019 + m // 12, m % 12 + 1, 1) for m in range(72)]
HOURS_3_MAY = [dt.datetime(2021, 5, 3) + dt.timedelta(hours=h) for h in range(48)]


# --- a range inside one year -------------------------------------------------


def test_a_range_inside_one_year_writes_the_year_on_its_first_tick() -> None:
    scale = dates((DAYS_2021[0], DAYS_2021[-1]), (0.0, 100.0))
    assert labels_of(scale) == ("Mar 2021", "Apr", "May", "Jun")


def test_the_year_is_not_written_again_past_the_last_tick() -> None:
    chart = i.line(x=DAYS_2021, y=list(range(120)))
    texts = svg_texts(chart)
    assert "2021" not in texts
    assert texts[:4] == ["Mar 2021", "Apr", "May", "Jun"]


# --- a range of years --------------------------------------------------------


def test_a_range_of_years_writes_each_year_and_nothing_else() -> None:
    scale = dates((MONTHS_2019_2024[0], MONTHS_2019_2024[-1]), (0.0, 100.0))
    assert labels_of(scale) == ("2019", "2020", "2021", "2022", "2023", "2024")


def test_a_range_of_years_draws_each_year_on_the_page() -> None:
    chart = i.line(x=MONTHS_2019_2024, y=list(range(72)))
    texts = svg_texts(chart)
    for year in ("2019", "2020", "2021", "2022", "2023", "2024"):
        assert year in texts


# --- monthly ticks that cross a year -----------------------------------------


def test_monthly_ticks_across_new_year_write_the_year_on_january() -> None:
    scale = dates(("2020-10-01", "2021-06-01"), (0.0, 100.0))
    assert labels_of(scale) == ("Oct 2020", "Nov", "Dec", "Jan 2021",
                                "Feb", "Mar", "Apr", "May", "Jun")


def test_quarterly_ticks_across_new_year_write_the_year_on_january() -> None:
    scale = dates(("2019-06-01", "2021-06-01"), (0.0, 100.0))
    assert labels_of(scale) == ("Jul 2019", "Jan 2020", "Jul", "Jan 2021")


# --- daily and weekly ticks --------------------------------------------------


def test_daily_ticks_across_new_year_write_the_year_on_the_first_of_january() -> None:
    scale = dates(("2020-12-27", "2021-01-06"), (0.0, 100.0))
    assert labels_of(scale) == ("27 Dec 2020", "29 Dec", "31 Dec",
                                "2 Jan 2021", "4 Jan", "6 Jan")


def test_weekly_ticks_across_new_year_write_the_year_on_the_first_new_one() -> None:
    scale = dates(("2019-12-01", "2020-02-01"), (0.0, 100.0))
    assert labels_of(scale) == ("9 Dec 2019", "23 Dec", "6 Jan 2020", "20 Jan")


# --- clock time ---------------------------------------------------------------


def test_hours_within_a_day_put_the_date_on_the_first_tick() -> None:
    scale = dates(("2021-05-03T00:00", "2021-05-03T23:00"), (0.0, 100.0))
    assert labels_of(scale) == ("3 May 2021 00:00", "06:00", "12:00", "18:00")


def test_hours_across_midnight_put_the_date_on_each_midnight() -> None:
    chart = i.line(x=HOURS_3_MAY, y=list(range(48)))
    texts = svg_texts(chart)
    assert texts[:4] == ["3 May 2021 00:00", "12:00", "4 May 00:00", "12:00"]


def test_hours_across_new_year_write_the_year_at_the_midnight_that_changes_it() -> None:
    scale = dates(("2020-12-31T12:00", "2021-01-01T12:00"), (0.0, 100.0))
    assert labels_of(scale) == ("31 Dec 2020 12:00", "18:00",
                                "1 Jan 2021 00:00", "06:00", "12:00")


def test_the_three_ranges_render_byte_identically_twice() -> None:
    for x, n in ((DAYS_2021, 120), (MONTHS_2019_2024, 72), (HOURS_3_MAY, 48)):
        first = i.line(x=x, y=list(range(n))).to_svg(text="names")
        again = i.line(x=x, y=list(range(n))).to_svg(text="names")
        assert first == again


def test_minutes_put_the_date_on_the_first_tick() -> None:
    scale = dates(("2021-05-03T08:00", "2021-05-03T08:40"), (0.0, 100.0))
    assert labels_of(scale)[:2] == ("3 May 2021 08:00", "08:05")


# --- the explicit offset still works -----------------------------------------


def _date_panel():
    return panel(60, 30, x=dates((DAYS_2021[0], DAYS_2021[-1])), y=(0, 10))


def test_a_date_axis_adds_nothing_past_its_ticks_by_default() -> None:
    p = _date_panel()
    p.axis("bottom")
    words = page_words(p.build())
    assert words[-1] == "Jun"
    assert "2021" not in words


def test_offset_false_adds_nothing_past_the_ticks() -> None:
    plain = _date_panel()
    plain.axis("bottom")
    silent = _date_panel()
    silent.axis("bottom", offset=False)
    assert page_words(silent.build()) == page_words(plain.build())


def test_an_explicit_offset_string_is_written_once_past_the_last_tick() -> None:
    p = _date_panel()
    p.axis("bottom", offset="all of 2021")
    words = page_words(p.build())
    assert words[-1] == "all of 2021"
    assert words.count("all of 2021") == 1
