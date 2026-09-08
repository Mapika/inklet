"""Explicit DataFrame time imports preserve identity, timezone and precision."""
from datetime import date, datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from inklet.experimental.selection import KeyedTable


@pytest.fixture(params=['pandas', 'polars'])
def adapter(request):
    library = pytest.importorskip(request.param)
    return library, getattr(KeyedTable, f'from_{request.param}')


def test_dates_and_utc_are_explicit_portable_scalar_snapshots(adapter):
    library, convert = adapter
    local = timezone(timedelta(hours=5, minutes=30))
    frame = library.DataFrame({
        'id': ['b', 'a'],
        'day': [date(2024, 2, 29), None],
        'instant': [datetime(2024, 3, 1, 0, 15, 0, 123000, tzinfo=local), None],
        'value': [3, 4],
    })
    mapping = {'day': 'date', 'instant': 'utc'}
    table = convert('observations', frame, time_columns=mapping)
    expected = KeyedTable('observations', {
        'id': ['b', 'a'], 'day': ['2024-02-29', None],
        'instant': ['2024-02-29T18:45:00.123Z', None], 'value': [3, 4],
    })
    assert table.digest == expected.digest
    assert table.row_ids == ('b', 'a')
    mapping['day'] = 'utc'
    assert table.columns['day'] == ('2024-02-29', None)
    with pytest.raises(ValueError, match="column 'day', row 0"):
        convert('observations', frame)


def test_iso_string_conversion_is_opt_in_and_normalizes_equivalent_offsets(adapter):
    library, convert = adapter
    frame = library.DataFrame({'id': ['a', 'b'], 'time': [
        '2024-01-01T12:00:00.120000000+02:00', '2024-01-01T10:00:00.12Z']})
    normal = convert('rows', frame, time_columns=MappingProxyType({'time': 'utc'}))
    raw = convert('rows', frame)
    assert normal.columns['time'] == ('2024-01-01T10:00:00.120Z',) * 2
    assert raw.columns['time'] != normal.columns['time']
    assert raw.digest != normal.digest


@pytest.mark.parametrize('mapping', [[], 'date', [('time', 'date')],
    {'id': 'date'}, {'absent': 'date'}, {'time': 'local'}, {'time': None},
    {'time': ['date']}, {1: 'date'}])
def test_invalid_time_mapping_is_rejected(adapter, mapping):
    library, convert = adapter
    frame = library.DataFrame({'id': ['a'], 'time': ['2024-01-01']})
    with pytest.raises(ValueError, match='time'):
        convert('rows', frame, time_columns=mapping)


def test_time_mapping_cannot_reintroduce_projected_columns(adapter):
    library, convert = adapter
    frame = library.DataFrame({'id': ['a'], 'time': ['2024-01-01']})
    with pytest.raises(ValueError, match='selected column'):
        convert('rows', frame, columns=['id'], time_columns={'time': 'date'})
    assert convert('rows', frame, columns=['id'], time_columns={}).row_ids == ('a',)


@pytest.mark.parametrize('value,mode', [
    ('2024-01-01T00:00:00', 'utc'),
    ('2024-01-01', 'utc'),
    ('2024-01-01T00:00:00Z', 'date'),
    ('2024-02-30', 'date'),
    ('2024-01-01T00:00:00.123001Z', 'utc'),
    ('2024-01-01T00:00:00-00:00', 'utc'),
    (3, 'date'), (True, 'utc'),
])
def test_invalid_time_value_reports_original_column_and_row(adapter, value, mode):
    library, convert = adapter
    frame = library.DataFrame({'id': ['a', 'b'], 'time': [None, value]})
    with pytest.raises(ValueError, match="column 'time', row 1"):
        convert('rows', frame, time_columns={'time': mode})


@pytest.mark.parametrize('mode', ['date', 'utc'])
def test_float_nan_normalizes_before_time_parsing(adapter, mode):
    library, convert = adapter
    frame = library.DataFrame({'id': ['a', 'b'], 'time': [None, float('nan')]})
    assert convert('rows', frame, time_columns={'time': mode}).columns['time'] == (None, None)


@pytest.mark.parametrize('value,mode', [
    (datetime(2024, 1, 1), 'utc'),
    (datetime(2024, 1, 1, tzinfo=timezone.utc), 'date'),
    (datetime(2024, 1, 1, microsecond=1, tzinfo=timezone.utc), 'utc'),
])
def test_native_datetime_rejects_naivety_date_coercion_and_submilliseconds(adapter, value, mode):
    library, convert = adapter
    frame = library.DataFrame({'id': ['a', 'b'], 'time': [None, value]})
    with pytest.raises(ValueError, match="column 'time', row 1"):
        convert('rows', frame, time_columns={'time': mode})


def test_pandas_missing_scalars_and_nanosecond_timestamps_preserve_precision():
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    values = [pd.NA, pd.NaT, np.datetime64('NaT', 'ns'), np.float32('nan'),
              pd.Timestamp('2024-01-01T00:00:00.123000000Z')]
    frame = pd.DataFrame({'id': ['a', 'b', 'c', 'd', 'e'], 'time': pd.Series(values, dtype=object)})
    result = KeyedTable.from_pandas('rows', frame, time_columns={'time': 'utc'})
    assert result.columns['time'] == (None, None, None, None, '2024-01-01T00:00:00.123Z')
    frame.at[4, 'time'] = pd.Timestamp('2024-01-01T00:00:00.123000001Z')
    with pytest.raises(ValueError, match="column 'time', row 4"):
        KeyedTable.from_pandas('rows', frame, time_columns={'time': 'utc'})


@pytest.mark.parametrize('mode', ['date', 'utc'])
def test_pandas_numpy_datetime_has_no_implicit_timezone_or_date_coercion(mode):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    frame = pd.DataFrame({'id': ['a'], 'time': pd.Series([np.datetime64('2024-01-01', 'D')], dtype=object)})
    with pytest.raises(ValueError, match="column 'time', row 0"):
        KeyedTable.from_pandas('rows', frame, time_columns={'time': mode})


@pytest.mark.parametrize('nanoseconds', [1, -1, 999999, -1000001, 123000001])
def test_polars_nanosecond_precision_is_checked_before_python_conversion(nanoseconds):
    pl = pytest.importorskip('polars')
    times = pl.Series('time', [None, nanoseconds], dtype=pl.Int64).cast(pl.Datetime('ns', 'UTC'))
    frame = pl.DataFrame({'id': ['a', 'b'], 'time': times})
    with pytest.raises(ValueError, match="column 'time', row 1.*millisecond"):
        KeyedTable.from_polars('rows', frame, time_columns={'time': 'utc'})


@pytest.mark.parametrize('unit', ['ns', 'us', 'ms'])
def test_polars_exact_milliseconds_survive_native_temporal_units(unit):
    pl = pytest.importorskip('polars')
    multiplier = {'ns': 1_000_000, 'us': 1000, 'ms': 1}[unit]
    times = pl.Series('time', [None, -123 * multiplier, 123 * multiplier], dtype=pl.Int64)
    frame = pl.DataFrame({'id': ['a', 'b', 'c'], 'time': times.cast(pl.Datetime(unit, 'UTC'))})
    table = KeyedTable.from_polars('rows', frame, time_columns={'time': 'utc'})
    assert table.columns['time'] == (None, '1969-12-31T23:59:59.877Z', '1970-01-01T00:00:00.123Z')
