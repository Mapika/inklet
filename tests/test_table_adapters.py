"""DataFrame adapters preserve identity and reject lossy scalar conversions."""
from datetime import date, datetime, timedelta
from decimal import Decimal
import os
import subprocess
import sys

import pytest

from inklet.experimental.selection import KeyedTable, SelectionState


@pytest.fixture(params=['pandas', 'polars'])
def adapter(request):
    library = pytest.importorskip(request.param)
    return library, getattr(KeyedTable, f'from_{request.param}')


def test_core_import_and_direct_table_need_no_optional_dataframe_libraries():
    script = '''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'pandas', 'polars', 'numpy'}:
        raise ImportError('optional dependency deliberately unavailable: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from inklet.experimental.selection import KeyedTable
assert KeyedTable('rows', {'id': ['a'], 'value': [1]}).row_ids == ('a',)
for method in (KeyedTable.from_pandas, KeyedTable.from_polars):
    try:
        method('rows', object())
    except ImportError:
        pass
    else:
        raise AssertionError('missing dependency should raise ImportError')
'''
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                            env=os.environ.copy())
    assert result.returncode == 0, result.stderr


def test_scalar_snapshot_matches_direct_digest_and_preserves_row_order(adapter):
    library, convert = adapter
    data = {'id': ['third', 'first', 'second'], 'integer': [2, None, -3],
            'real': [1.5, None, -2.0], 'flag': [True, None, False],
            'label': ['yes', None, 'no']}
    if library.__name__ == 'pandas':
        frame = library.DataFrame({k: library.Series(v, dtype=object) for k, v in data.items()})
    else:
        frame = library.DataFrame(data)
    table = convert('rows', frame)
    direct = KeyedTable('rows', data)
    assert table.digest == direct.digest
    assert table.row_ids == ('third', 'first', 'second')
    assert dict(table.columns) == dict(direct.columns)
    assert type(table.columns['integer'][0]) is int
    assert type(table.columns['real'][0]) is float
    assert type(table.columns['flag'][0]) is bool
    with pytest.raises(TypeError):
        table.columns['integer'] = (9, 9, 9)
    if library.__name__ == 'pandas':
        frame.loc[0, 'integer'] = 100
        frame.loc[0, 'id'] = 'changed'
    else:
        frame[0, 'integer'] = 100
        frame[0, 'id'] = 'changed'
    assert table.digest == direct.digest
    assert table.row_ids[0] == 'third'
    assert table.columns['integer'][0] == 2


def test_projection_preserves_requested_order_and_can_exclude_unsupported_cells(adapter):
    library, convert = adapter
    frame = library.DataFrame({'id': ['b', 'a'], 'value': [2, 1], 'nested': [[1], [2]]})
    result = convert('rows', frame, columns=['value', 'id'])
    assert list(result.columns) == ['value', 'id']
    assert result.digest == KeyedTable('rows', {'id': ['b', 'a'], 'value': [2, 1]}).digest


@pytest.mark.parametrize('columns', ['id', b'id', [], ['value'], ['id', 'id'],
                                     ['id', 'missing'], ['id', ''], ['id', 1],
                                     {'id': 1}, {'id', 'value'}])
def test_invalid_projection_is_rejected(adapter, columns):
    library, convert = adapter
    frame = library.DataFrame({'id': ['a'], 'value': [2]})
    with pytest.raises((TypeError, ValueError)):
        convert('rows', frame, columns=columns)


@pytest.mark.parametrize('ids', [['a', 'a'], [''], [None], [1], [True]])
def test_invalid_explicit_row_identity_is_rejected(adapter, ids):
    library, convert = adapter
    with pytest.raises((TypeError, ValueError)):
        convert('rows', library.DataFrame({'id': ids}))


def test_custom_key_and_empty_frames(adapter):
    library, convert = adapter
    table = convert('rows', library.DataFrame({'sample': ['z', 'a'], 'value': [1, 2]}), key='sample')
    assert table.key == 'sample'
    assert table.row_ids == ('z', 'a')
    empty = convert('rows', library.DataFrame({'sample': [], 'value': []}), key='sample')
    assert empty.row_ids == ()
    assert empty.digest == KeyedTable('rows', {'sample': [], 'value': []}, key='sample').digest
    with pytest.raises(ValueError):
        convert('rows', library.DataFrame({'value': [1]}))


@pytest.mark.parametrize('key', ['', 1, None])
def test_invalid_key_name(adapter, key):
    library, convert = adapter
    with pytest.raises((TypeError, ValueError)):
        convert('rows', library.DataFrame({'id': ['a']}), key=key)


def test_only_concrete_dataframe_is_accepted(adapter):
    library, convert = adapter
    for source in ({'id': ['a']}, [{'id': 'a'}], library.Series(['a']), object()):
        with pytest.raises((TypeError, ValueError)):
            convert('rows', source)


def test_polars_lazyframe_is_rejected_without_collecting(monkeypatch):
    pl = pytest.importorskip('polars')
    lazy = pl.DataFrame({'id': ['a'], 'value': [1]}).lazy()
    def forbidden(*args, **kwargs):
        pytest.fail('adapter must not collect a LazyFrame implicitly')
    monkeypatch.setattr(pl.LazyFrame, 'collect', forbidden)
    with pytest.raises((TypeError, ValueError)):
        KeyedTable.from_polars('rows', lazy)


@pytest.mark.parametrize('labels', [['id', 'duplicate', 'duplicate'], ['id', '', 'value'],
                                    ['id', 42, 'value']])
def test_pandas_invalid_source_labels_rejected_even_when_projected_away(labels):
    pd = pytest.importorskip('pandas')
    frame = pd.DataFrame([['a', 1, 2]], columns=labels)
    with pytest.raises((TypeError, ValueError)):
        KeyedTable.from_pandas('rows', frame, columns=['id'])


def test_pandas_multiindex_columns_rejected():
    pd = pytest.importorskip('pandas')
    frame = pd.DataFrame([['a', 1]], columns=pd.MultiIndex.from_tuples([('id', ''), ('value', '')]))
    with pytest.raises((TypeError, ValueError)):
        KeyedTable.from_pandas('rows', frame)


def test_pandas_index_never_supplies_or_changes_identity():
    pd = pytest.importorskip('pandas')
    frame = pd.DataFrame({'id': ['b', 'a'], 'value': [2, 1]}, index=['repeat', 'repeat'])
    table = KeyedTable.from_pandas('rows', frame)
    frame.index = [100, -100]
    assert KeyedTable.from_pandas('rows', frame).digest == table.digest
    with pytest.raises(ValueError):
        KeyedTable.from_pandas('rows', frame.set_index('id'))


def test_pandas_nullable_and_categorical_scalars():
    pd = pytest.importorskip('pandas')
    frame = pd.DataFrame({
        'id': ['a', 'b', 'c'],
        'integer': pd.Series([1, pd.NA, 3], dtype='Int64'),
        'real': pd.Series([1.5, pd.NA, 3.5], dtype='Float64'),
        'flag': pd.Series([True, pd.NA, False], dtype='boolean'),
        'label': pd.Series(['yes', pd.NA, 'no'], dtype='string'),
        'group': pd.Categorical(['north', None, 'south'], categories=['south', 'north', 'unused'], ordered=True),
        'numeric_group': pd.Categorical([1, None, 2]),
    })
    table = KeyedTable.from_pandas('rows', frame)
    expected = {'id': ['a', 'b', 'c'], 'integer': [1, None, 3], 'real': [1.5, None, 3.5],
                'flag': [True, None, False], 'label': ['yes', None, 'no'],
                'group': ['north', None, 'south'], 'numeric_group': [1, None, 2]}
    assert table.digest == KeyedTable('rows', expected).digest


def test_pandas_object_missing_values_and_numpy_scalars():
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    data = [None, pd.NA, pd.NaT, float('nan'), np.float64('nan'), np.int64(4),
            np.float32(1.5), np.bool_(True), np.str_('text')]
    frame = pd.DataFrame({'id': [str(i) for i in range(len(data))],
                          'value': pd.Series(data, dtype=object)})
    table = KeyedTable.from_pandas('rows', frame)
    assert table.columns['value'] == (None, None, None, None, None, 4, 1.5, True, 'text')
    assert [type(x) for x in table.columns['value'][5:]] == [int, float, bool, str]


def test_polars_nan_and_categorical_values():
    pl = pytest.importorskip('polars')
    frame = pl.DataFrame({'id': ['a', 'b', 'c'], 'value': [1.5, float('nan'), None],
                          'group': ['north', None, 'south']}).with_columns(pl.col('group').cast(pl.Categorical))
    expected = KeyedTable('rows', {'id': ['a', 'b', 'c'], 'value': [1.5, None, None],
                                  'group': ['north', None, 'south']})
    assert KeyedTable.from_polars('rows', frame).digest == expected.digest


BAD_VALUES = [float('inf'), float('-inf'), 2**53, -(2**53), Decimal('1.25'), complex(1, 2),
              date(2026, 1, 1), datetime(2026, 1, 1, 12), timedelta(seconds=1), [1, 2],
              {'nested': 1}, b'bytes']


@pytest.mark.parametrize('value', BAD_VALUES)
def test_unsupported_cells_report_column_and_zero_based_row(adapter, value):
    library, convert = adapter
    if library.__name__ == 'pandas':
        frame = library.DataFrame({'id': ['good', 'bad'], 'measurement': library.Series([None, value], dtype=object)})
    else:
        frame = library.DataFrame({'id': ['good', 'bad'],
                                   'measurement': library.Series('measurement', [None, value], dtype=library.Object)})
    with pytest.raises(ValueError) as error:
        convert('rows', frame)
    message = str(error.value)
    assert 'measurement' in message
    assert 'row 1' in message or 'row=1' in message or 'row index 1' in message


@pytest.mark.parametrize('value', [date(2026, 1, 1), datetime(2026, 1, 1, 12), timedelta(seconds=1), Decimal('1.25')])
def test_polars_native_temporal_and_decimal_dtypes_rejected(value):
    pl = pytest.importorskip('polars')
    with pytest.raises(ValueError, match='measurement'):
        KeyedTable.from_polars('rows', pl.DataFrame({'id': ['a', 'b'], 'measurement': [None, value]}))


def test_safe_integer_boundaries_and_numeric_type_identity(adapter):
    library, convert = adapter
    data = {'id': ['a', 'b'], 'value': [-(2**53 - 1), 2**53 - 1]}
    assert convert('rows', library.DataFrame(data)).digest == KeyedTable('rows', data).digest
    integers = convert('rows', library.DataFrame({'id': ['a'], 'value': [1]}))
    floats = convert('rows', library.DataFrame({'id': ['a'], 'value': [1.0]}))
    assert integers.digest != floats.digest


def test_dataframe_revision_preserves_keys_across_reordering_and_removal(adapter):
    from inklet.experimental.browser import BrowserFigure, ScatterView
    library, convert = adapter
    old = convert('rows', library.DataFrame({'id': ['a', 'b', 'c'], 'x': [1, 2, 3], 'y': [2, 4, 6]}))
    new = convert('rows', library.DataFrame({'id': ['c', 'a', 'd'], 'x': [3, 1, 4], 'y': [7, 2, 8]}))
    figure = BrowserFigure(old, [ScatterView('points', 'x', 'y', (0, 5), (0, 10))])
    state = figure.state(SelectionState.for_table(old, selected=['a', 'b'], visible=['b', 'c']))
    with pytest.raises(ValueError):
        figure.replace_data(new, state=state)
    revised = figure.replace_data(new, state=state, missing='drop')
    selection, _ = revised.figure.validate_state(revised.state())
    assert selection.selected_ids == ('a',)
    assert selection.visible_ids == ('c',)
    assert revised.figure.table.row_ids == ('c', 'a', 'd')
    assert figure.table.row_ids == ('a', 'b', 'c')


@pytest.mark.parametrize('kind', ['datetime', 'timedelta'])
def test_pandas_numpy_nanosecond_temporal_scalars_do_not_become_integers(kind):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    value = np.datetime64('1970-01-01T00:00:00.000000001', 'ns') if kind == 'datetime' else np.timedelta64(1, 'ns')
    assert value.item() == 1  # Blind .item() would silently discard the unit/type.
    frame = pd.DataFrame({'id': ['a', 'b'], 'measurement': pd.Series([None, value], dtype=object)})
    with pytest.raises(ValueError, match='measurement'):
        KeyedTable.from_pandas('rows', frame)
