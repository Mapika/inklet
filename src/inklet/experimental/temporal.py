"""Explicit calendar dates and UTC instants for portable experimental tables."""
from datetime import date, datetime, timezone
import re


def time_value(value, mode):
    """Normalize a date or offset timestamp without guessing units or timezone.

    UTC instants have millisecond precision. Finer values must be rounded by
    the author, not silently truncated during serialization.
    """
    if mode not in ('date', 'utc'):
        raise ValueError('time mode must be date or utc')
    if value is None:
        return None
    if mode == 'date':
        if isinstance(value, date) and not isinstance(value, datetime):
            value = value.isoformat()
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('date values require YYYY-MM-DD calendar dates, without clock time')
        return date.fromisoformat(value).isoformat()
    if isinstance(value, datetime):
        value = value.isoformat()
    if not isinstance(value, str):
        raise ValueError('utc values require an aware datetime or an ISO timestamp with an explicit offset')
    match = re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})', value)
    if not match:
        raise ValueError('utc values require YYYY-MM-DDTHH:MM:SS with Z or an explicit ±HH:MM offset')
    fraction = match[1] or ''
    if any(c != '0' for c in fraction[3:]):
        raise ValueError('UTC timestamps require exact millisecond precision; round finer values explicitly')
    offset = match[2]
    if offset != 'Z' and (int(offset[1:3]) > 23 or int(offset[4:]) > 59):
        raise ValueError('invalid UTC offset')
    if offset == '-00:00':
        raise ValueError('unknown offset -00:00 is unsupported; provide a known UTC offset')
    try:
        instant = datetime.fromisoformat(value).astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ValueError('invalid or out-of-range UTC timestamp') from error
    return instant.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def time_seconds(value, mode):
    """Seconds from the UTC epoch; calendar dates use midnight coordinates."""
    value = time_milliseconds(value, mode)
    return None if value is None else value / 1000


def time_milliseconds(value, mode):
    """Exact integer milliseconds, avoiding cancellation at modern epochs."""
    normalized = time_value(value, mode)
    if normalized is None:
        return None
    instant = datetime.fromisoformat(normalized)
    if mode == 'date':
        instant = instant.replace(tzinfo=timezone.utc)
    delta = instant - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000
