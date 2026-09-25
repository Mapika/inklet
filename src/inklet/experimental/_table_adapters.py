"""pandas and Polars table adapters; moved to `inklet.selection._table_adapters` in 4.3.

This path keeps working and re-exports the same objects. New code should
import from `inklet.selection._table_adapters`.
"""
from inklet.selection._table_adapters import (  # noqa: F401
    Mapping,
    Set,
    _headers,
    _scalar,
    _time_columns,
    _time_scalar,
    math,
    pandas_columns,
    polars_columns,
)
