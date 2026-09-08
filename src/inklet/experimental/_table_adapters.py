"""Optional eager table adapters; keep the serialized scalar contract unchanged."""
import math
from collections.abc import Mapping, Set


def _headers(source, columns, key):
    if not isinstance(key, str) or not key:
        raise ValueError('key column must be a nonempty string')
    source = tuple(source)
    if any(not isinstance(name, str) or not name for name in source):
        raise ValueError('source column names must be nonempty strings')
    if len(set(source)) != len(source):
        raise ValueError('source contains duplicate column names')
    if columns is None:
        chosen = source
    else:
        if isinstance(columns, (str, bytes, Mapping, Set)):
            raise ValueError('columns must be a sequence of column names')
        try:
            chosen = tuple(columns)
        except TypeError as error:
            raise ValueError('columns must be a sequence of column names') from error
        if any(not isinstance(name, str) or not name for name in chosen):
            raise ValueError('column names must be nonempty strings')
        if len(set(chosen)) != len(chosen):
            raise ValueError('columns contains duplicate column names')
        unknown = set(chosen).difference(source)
        if unknown:
            raise ValueError(f'unknown columns: {sorted(unknown)!r}')
    if key not in chosen:
        raise ValueError(f'columns must contain the key column {key!r}; no index or row IDs are inferred')
    return chosen


def _scalar(value, column, row, key):
    location = f'column {column!r}, row {row}'
    if type(value) is float and math.isnan(value):
        value = None
    if column == key and (type(value) is not str or not value):
        raise ValueError(f'{location}: key must be a nonempty string row ID')
    if type(value) not in (str, int, float, bool, type(None)):
        raise ValueError(f'{location}: table cells must be JSON scalars; '
                         f'convert {type(value).__name__} explicitly or omit this column')
    if type(value) is float and not math.isfinite(value):
        raise ValueError(f'{location}: nonfinite numbers are unsupported; only NaN denotes missing data')
    if type(value) is int and abs(value) > 2**53 - 1:
        raise ValueError(f'{location}: integers outside the portable JSON range must be strings')
    return value


def _time_columns(time_columns, chosen, key):
    if time_columns is None:
        return {}
    if not isinstance(time_columns, Mapping):
        raise ValueError('time_columns must map selected non-key column names to date or utc')
    result = dict(time_columns)
    for column, mode in result.items():
        if not isinstance(column, str) or column not in chosen:
            raise ValueError(f'time column {column!r} must be a selected column')
        if column == key:
            raise ValueError('time_columns cannot convert the key column')
        if not isinstance(mode, str) or mode not in ('date', 'utc'):
            raise ValueError(f'time column {column!r}: mode must be date or utc')
    return result


def _time_scalar(value, mode, column, row):
    from .temporal import time_value
    if value is None or (type(value) is float and math.isnan(value)):
        return None
    try:
        return time_value(value, mode)
    except ValueError as error:
        raise ValueError(f'column {column!r}, row {row}: {error}') from error


def pandas_columns(frame, *, key, columns, time_columns=None):
    try:
        import pandas as pd
    except ImportError as error:
        raise ImportError('pandas input requires pandas; install inklet[pandas]') from error
    if not isinstance(frame, pd.DataFrame):
        raise TypeError('from_pandas requires a pandas DataFrame')
    import numpy as np  # pandas already requires NumPy; never loaded by core use.
    chosen = _headers(frame.columns, columns, key)
    temporal = _time_columns(time_columns, chosen, key)
    result = {}
    for column in chosen:
        values = []
        for row, value in enumerate(frame[column].tolist()):
            if value is pd.NA or value is pd.NaT:
                value = None
            elif isinstance(value, (np.datetime64, np.timedelta64)):
                # At nanosecond precision .item() can return an integer, which
                # would silently erase the temporal meaning and units.
                if np.isnat(value):
                    value = None
            elif isinstance(value, np.generic):
                value = value.item()
            if column in temporal:
                # Timestamp.isoformat preserves nanoseconds so the shared
                # parser can reject precision that a Python datetime would lose.
                if isinstance(value, pd.Timestamp) and temporal[column] == 'utc':
                    value = value.isoformat()
                values.append(_time_scalar(value, temporal[column], column, row))
            else:
                values.append(_scalar(value, column, row, key))
        result[column] = values
    return result


def polars_columns(frame, *, key, columns, time_columns=None):
    try:
        import polars as pl
    except ImportError as error:
        raise ImportError('Polars input requires polars; install inklet[polars]') from error
    if not isinstance(frame, pl.DataFrame):
        raise TypeError('from_polars requires an eager Polars DataFrame; collect lazy inputs explicitly')
    chosen = _headers(frame.columns, columns, key)
    temporal = _time_columns(time_columns, chosen, key)
    result = {}
    for column in chosen:
        series = frame.get_column(column)
        if column in temporal:
            if isinstance(series.dtype, pl.Datetime) and series.dtype.time_unit == 'ns':
                # to_list converts to Python datetime, truncating nanoseconds.
                # Inspect the original integer representation first.
                for row, value in enumerate(series.cast(pl.Int64).to_list()):
                    if value is not None and value % 1_000_000:
                        raise ValueError(f'column {column!r}, row {row}: '
                                         'timestamps require millisecond precision')
            result[column] = [_time_scalar(value, temporal[column], column, row)
                              for row, value in enumerate(series.to_list())]
        else:
            result[column] = [_scalar(value, column, row, key)
                              for row, value in enumerate(series.to_list())]
    return result
