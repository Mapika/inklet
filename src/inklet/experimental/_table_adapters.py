"""pandas and Polars table adapters; moved to `inklet.selection._table_adapters` in 4.3.

Deprecated: importing this path warns from Inklet 4.4 and the path is removed
in 5.0. Use KeyedTable.from_pandas() or KeyedTable.from_polars() from inklet.selection.
"""
from inklet._compat import moved_module as _moved_module
from inklet.selection._table_adapters import (  # noqa: F401
    _headers,
    _scalar,
    _time_columns,
    _time_scalar,
    pandas_columns,
    polars_columns,
)

_moved_module(__name__, 'inklet.selection._table_adapters',
              hint='use KeyedTable.from_pandas() or KeyedTable.from_polars() from inklet.selection')
