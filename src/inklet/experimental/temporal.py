"""Calendar-date and UTC helpers for keyed tables; moved to `inklet.selection._temporal` in 4.3.

Deprecated: importing this path warns from Inklet 4.4 and the path is removed
in 5.0. The helpers are private to `inklet.selection` from 4.3 (`KeyedTable`
converts dates itself); `inklet.experimental.browser.timeaxis` still exports
`time_value`, `time_seconds` and `time_milliseconds`.
"""
from inklet._compat import moved_module as _moved_module
from inklet.selection._temporal import (  # noqa: F401
    time_milliseconds,
    time_seconds,
    time_value,
)

_moved_module(__name__, 'inklet.selection._temporal',
              hint=('the helpers are private to inklet.selection from 4.3 (KeyedTable '
                    'converts dates itself); inklet.experimental.browser.timeaxis '
                    'still exports time_value, time_seconds and time_milliseconds'))
