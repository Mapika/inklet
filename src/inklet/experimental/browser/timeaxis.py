"""Measured temporal axes; browser engines receive resolved geometry only."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections.abc import Mapping, Set

from ...plot.timescale import Time, time_ticks, to_time
from ...plot.scale import linear
from ..temporal import time_value, time_seconds, time_milliseconds

_EPOCH = datetime(1970, 1, 1)


@dataclass(frozen=True)
class TimeAxis:
    """An explicit calendar-date or UTC-instant domain, in either direction.

    Table coordinates are ISO strings or None. UTC values require an offset
    and exact millisecond precision. Date values contain no clock or timezone.
    """
    domain: tuple[str, str]
    mode: str = 'date'
    seconds: tuple[float, float] = field(init=False)
    milliseconds: tuple[int, int] = field(init=False, repr=False)

    def __post_init__(self):
        if isinstance(self.domain, (str, bytes, Mapping, Set)):
            raise ValueError('time domain needs two distinct endpoints')
        try:
            domain = tuple(time_value(v, self.mode) for v in self.domain)
        except TypeError as error:
            raise ValueError('time domain needs two distinct endpoints') from error
        if len(domain) != 2 or any(v is None for v in domain) or domain[0] == domain[1]:
            raise ValueError('time domain needs two distinct endpoints')
        seconds = tuple(time_seconds(v, self.mode) for v in domain)
        object.__setattr__(self, 'domain', domain)
        object.__setattr__(self, 'seconds', seconds)
        object.__setattr__(self, 'milliseconds', tuple(time_milliseconds(v, self.mode) for v in domain))

    def scale(self):
        return _MeasuredTime(self.seconds, mode=self.mode, milliseconds=self.milliseconds)

    def metadata(self):
        return dict(mode=self.mode, domain=self.domain, unit='seconds')


@dataclass(frozen=True, slots=True)
class _MeasuredTime(Time):
    mode: str = 'date'
    milliseconds: tuple[int, int] = (0, 86400000)

    @property
    def start(self):
        return _EPOCH + timedelta(milliseconds=self.milliseconds[0])

    @property
    def end(self):
        return _EPOCH + timedelta(milliseconds=self.milliseconds[1])

    def map(self, value):
        delta = to_time(value) - _EPOCH
        value_ms = (delta.days*86400 + delta.seconds)*1000 + delta.microseconds/1000
        low, high = self.milliseconds
        t = (value_ms-low)/(high-low)
        if self.clamp:
            t = min(1., max(0., t))
        return self.range[0] + t*(self.range[1]-self.range[0])

    def ticks(self, count=5):
        low_ms, high_ms = sorted(self.milliseconds)
        span = (high_ms-low_ms)/1000
        if self.mode == 'utc' and span < 10:
            # The legacy calendar tick ladder starts at whole seconds.
            # Generate short-interval ticks relative to a nearby second, so
            # large epoch coordinates do not lose millisecond detail.
            origin = low_ms//1000*1000
            values = linear((low_ms-origin, high_ms-origin)).ticks(min(count, high_ms-low_ms))
            ticks = sorted({origin+round(v) for v in values if low_ms <= origin+round(v) <= high_ms})
            return tuple(_EPOCH + timedelta(milliseconds=v) for v in ticks)
        if self.mode == 'date':
            count = min(count, max(1, int(span/86400)))
        try:
            return time_ticks(self.start, self.end, count)
        except (ValueError, OverflowError):
            # Extreme Python calendar bounds can exceed the next aligned
            # tick. Endpoint ticks remain valid and explicitly labelled.
            return tuple(_EPOCH + timedelta(milliseconds=v) for v in (low_ms, high_ms))

    def tick_labels(self, ticks):
        values = tuple(ticks)
        if not values:
            return ()
        span = abs(self.domain[1] - self.domain[0])
        if self.mode == 'utc' and span < 10:
            template = '%Y-%m-%d %H:%M:%S.' if len({t.date() for t in values}) > 1 else '%H:%M:%S.'
            return tuple(t.strftime(template) + f'{t.microsecond//1000:03d}' for t in values)
        if len({t.date() for t in values}) > 1 and any(t.hour or t.minute or t.second for t in values):
            return tuple(t.strftime('%Y-%m-%d %H:%M') for t in values)
        if len({t.year for t in values}) > 1:
            return tuple(t.strftime('%Y-%m-%d') for t in values)
        return Time.tick_labels(self, values)

    def minor_ticks(self, majors, count=None, clear=0):
        # Major ticks and their measured labels define this preview's axes.
        return ()

    def offset_label(self, ticks):
        if self.mode == 'utc' and abs(self.milliseconds[1]-self.milliseconds[0]) < 10000 and ticks:
            return ticks[0].date().isoformat() if len({t.date() for t in ticks}) == 1 else None
        return Time.offset_label(self, ticks)
