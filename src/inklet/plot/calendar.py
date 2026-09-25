"""Calendar heatmaps: one square per day, weeks as columns.

The GitHub contribution chart: seven rows for the days of the week and one
column per week, so a weekly rhythm reads down the columns and a seasonal
one along the rows. Days in the range without a value are drawn pale;
days outside it are not drawn at all. Month names are written above the
first week that starts in each month, and every other weekday name at the
left.

The grid fills the plot area in millimetres, anchored at its top-left
corner, with square cells as large as both dimensions allow; it does not
use the panel's scales. Colours go through the matrix ramps, so
`Panel.colorbar()` afterwards explains them. `calendar_weeks` returns the
number of columns, for sizing the panel first.
"""

from __future__ import annotations

import datetime as _dt
import math
from typing import Mapping

from ..core import Diagram, DiagramError, RectPrim, Vec2, mm
from ..draw.coords import active_theme
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND
from ..themes.color import mix
from .label_spread import label_text
from .metadata import declare_domain as _declare_domain
from .raster import is_missing
from .timescale import to_time

__all__ = ["calendar", "calendar_weeks", "WEEKDAYS"]

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
           "Nov", "Dec")

#: A day in range with no value, as a blend of the ink towards paper.
_EMPTY_TINT = 0.92


def _day(value) -> _dt.date:
    return to_time(value).date()


def _first(day: _dt.date, week_start: int) -> _dt.date:
    return day - _dt.timedelta(days=(day.weekday() - week_start) % 7)


def _week_start(week_start) -> int:
    if isinstance(week_start, int):
        return week_start % 7
    names = {n.lower(): i for i, n in enumerate(WEEKDAYS)}
    key = str(week_start)[:3].lower()
    if key not in names:
        raise DiagramError(f"calendar week_start= is a weekday name, not {week_start!r}")
    return names[key]


def calendar_weeks(start, end, *, week_start="monday") -> int:
    """How many week columns a calendar from `start` to `end` has."""
    first = _first(_day(start), _week_start(week_start))
    return (_day(end) - first).days // 7 + 1


def calendar(panel, values: Mapping, *, start=None, end=None, ramp=None,
             scale=None, center: float | None = None, week_start="monday",
             gap: float | str = 0.25, labels: bool = True,
             **style) -> tuple[Diagram, dict]:
    """Draw a calendar heatmap in `panel`'s plot area. See `Panel.calendar`.

    Returns `(node, note)`; the note holds the `ramp` and `scale` used.
    """
    from .matrix import default_coloring

    if not isinstance(values, Mapping):
        raise DiagramError("calendar() takes a mapping of date to value")
    days = {}
    for key, value in values.items():
        days[_day(key)] = value
    if not days and (start is None or end is None):
        raise DiagramError("calendar() was given no days")
    first_day = _day(start) if start is not None else min(days)
    last_day = _day(end) if end is not None else max(days)
    if last_day < first_day:
        raise DiagramError("calendar end is before its start")
    weekday0 = _week_start(week_start)
    origin = _first(first_day, weekday0)
    weeks = (last_day - origin).days // 7 + 1
    present = [v for d, v in days.items() if first_day <= d <= last_day and not is_missing(v)]
    if not present:
        raise DiagramError("calendar() has no values between its start and end")
    ramp, scale = default_coloring([present], ramp, scale, center)
    unit = None if scale is None else scale.with_range(0.0, 1.0)
    theme = active_theme()
    area = panel.area
    pitch = min(area.width / weeks, area.height / 7)
    side = max(pitch - mm(gap), pitch * 0.5)
    empty = mix(theme.ink, theme.paper, _EMPTY_TINT)
    items = []
    for offset in range((last_day - origin).days + 1):
        day = origin + _dt.timedelta(days=offset)
        if day < first_day:
            continue
        column, row = divmod(offset, 7)
        centre = Vec2(area.x0 + pitch * (column + 0.5), area.y0 + pitch * (row + 0.5))
        value = days.get(day)
        if value is None or is_missing(value):
            fill = empty
        else:
            t = float(value) if unit is None else unit.map(float(value))
            fill = ramp(min(1.0, max(0.0, t)))
        paint = {"fill": fill, "stroke": "none"}
        paint.update(style)
        items.append((centre, Diagram(prim=RectPrim(side, side), kind=MARK_KIND)
                      .styled(**paint)))
    written = []
    if labels:
        gap_text = theme.gap("xs")
        for row in range(0, 7, 2):
            name = WEEKDAYS[(weekday0 + row) % 7]
            written.append(draw_place(
                [(Vec2(area.x0 - gap_text, area.y0 + pitch * (row + 0.5)), label_text(name))],
                anchor="e", origin=(0, 0)))
        last_x = -math.inf
        for column in range(weeks):
            monday = origin + _dt.timedelta(days=7 * column)
            days_in = [monday + _dt.timedelta(days=k) for k in range(7)]
            starts = [d for d in days_in if d.day == 1 and first_day <= d <= last_day]
            if column == 0 and not starts:
                starts = [max(first_day, monday)]
            if not starts:
                continue
            x = area.x0 + pitch * column
            node = label_text(_MONTHS[starts[0].month - 1])
            if x < last_x:
                continue
            written.append(draw_place([(Vec2(x, area.y0 - gap_text), node)],
                                      anchor="sw", origin=(0, 0)))
            last_x = x + node.bbox.width + gap_text
    node = draw_place(items + written)
    if scale is not None:
        _declare_domain(node, scale)
    note = {"ramp": ramp, "scale": scale, "weeks": weeks, "cell": side,
            "start": first_day.isoformat(), "end": last_day.isoformat()}
    node.notes["calendar"] = {k: v for k, v in note.items() if k not in ("ramp", "scale")}
    return node, note
