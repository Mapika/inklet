"""One-call charts take the table and array types people actually have."""
from datetime import datetime, timezone

import pytest

import inklet as i
from inklet import quick


def _clean(chart):
    figure = chart.compile()
    serious = [d for d in figure.lint() if d.severity in ('error', 'warning')]
    assert serious == [], figure.report()
    return figure


# -- Polars ------------------------------------------------------------------


def test_polars_frame_nulls_datetimes_and_categoricals():
    pl = pytest.importorskip('polars')
    frame = pl.DataFrame({
        'when': [datetime(2024, 1, 1, 9), datetime(2024, 1, 1, 10), datetime(2024, 1, 1, 11),
                 None, datetime(2024, 1, 1, 13), datetime(2024, 1, 1, 14)],
        'signal': [1.0, 2.0, None, 4.0, 5.0, 6.0],
        'group': pl.Series(['a', 'a', 'a', 'b', 'b', 'b'], dtype=pl.Categorical),
        'stage': pl.Series(['pre', 'post', 'pre', 'post', 'pre', 'post'],
                           dtype=pl.Enum(['pre', 'post'])),
    })
    table = quick._table(frame)
    assert table['when'][0] == datetime(2024, 1, 1, 9)
    assert table['when'][3] is None
    assert table['signal'][2] is None
    assert table['group'] == ['a', 'a', 'a', 'b', 'b', 'b']
    assert table['stage'] == ['pre', 'post', 'pre', 'post', 'pre', 'post']

    chart = i.line(frame, x='when', y='signal', color='group')
    _clean(chart)
    points = [step[2][0] for step in chart.spec._steps]
    assert [list(p) for p in points] == [[(datetime(2024, 1, 1, 9), 1.0), (datetime(2024, 1, 1, 10), 2.0)],
                                         [(datetime(2024, 1, 1, 13), 5.0), (datetime(2024, 1, 1, 14), 6.0)]]
    _clean(i.bar(frame, x='stage', y='signal', color='group', agg='sum'))


# -- pandas categoricals -----------------------------------------------------


def test_pandas_categorical_x_keeps_declared_order():
    pd = pytest.importorskip('pandas')
    dose = pd.Categorical(['low', 'high', 'mid', 'low', 'high', 'mid'],
                          categories=['low', 'mid', 'high'])
    frame = pd.DataFrame({'dose': dose, 'resp': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})

    bar = i.bar(frame, x='dose', y='resp', agg='sum')
    assert list(bar.spec._steps[0][2][0]) == ['low', 'mid', 'high']
    _clean(bar)

    box = i.boxplot(frame, x='dose', y='resp')
    assert list(box.spec._steps[0][2][0]) == ['low', 'mid', 'high']
    _clean(box)


def test_pandas_categorical_colour_keeps_declared_order():
    pd = pytest.importorskip('pandas')
    group = pd.Categorical(['b', 'a', 'b', 'a'], categories=['a', 'b'])
    # Each (t, grp) once: the test is about the order of the colour groups.
    frame = pd.DataFrame({'t': [0, 1, 2, 3], 'v': [1.0, 2.0, 3.0, 4.0], 'grp': group})

    line = i.line(frame, x='t', y='v', color='grp')
    assert [step[3]['name'] for step in line.spec._steps] == ['a', 'b']
    _clean(line)

    bar = i.bar(frame, x='t', y='v', color='grp')
    assert list(bar.spec._steps[0][3]['name']) == ['a', 'b']
    _clean(bar)


def test_pandas_categorical_order_survives_facets():
    pd = pytest.importorskip('pandas')
    dose = pd.Categorical(['low', 'high', 'mid'] * 2, categories=['low', 'mid', 'high'])
    frame = pd.DataFrame({'dose': dose, 'resp': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                          'site': ['x'] * 3 + ['y'] * 3})
    figure = i.bar(frame, x='dose', y='resp', facet_col='site')
    for chart in figure.charts():
        assert list(chart.spec._steps[0][2][0]) == ['low', 'mid', 'high']


# -- pandas timezones and nullable dtypes ------------------------------------


def test_timezone_aware_datetimes_compile():
    pd = pytest.importorskip('pandas')
    times = pd.date_range('2024-01-01', periods=4, freq='D', tz='UTC')
    frame = pd.DataFrame({'t': times, 'v': [1.0, 3.0, 2.0, 4.0]})
    chart = i.line(frame, x='t', y='v')
    _clean(chart)
    first = chart.spec._steps[0][2][0][0][0]
    assert first == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert first.tzinfo is not None


def test_pandas_nullable_dtypes_drop_missing_rows():
    pd = pytest.importorskip('pandas')
    frame = pd.DataFrame({
        'time': pd.array([0, 1, 2, 3, 4, 5, 6, 7], dtype='Int64'),
        'signal': pd.array([1.0, 2.0, None, 4.0, 5.0, None, 7.0, 8.0], dtype='Float64'),
        'ok': pd.array([True, False, None, True, True, False, True, None], dtype='boolean'),
        'group': pd.array(['a', 'a', 'a', None, 'b', 'b', 'b', 'b'], dtype='string'),
    })
    assert quick._table(frame)['ok'][2] is None
    chart = i.line(frame, x='time', y='signal', color='group')
    _clean(chart)
    assert list(chart.spec._steps[0][2][0]) == [(0, 1.0), (1, 2.0)]
    assert list(chart.spec._steps[1][2][0]) == [(4, 5.0)]
    assert list(chart.spec._steps[2][2][0]) == [(6, 7.0), (7, 8.0)]


# -- CSV and TSV -------------------------------------------------------------


CSV = (
    '﻿name,dose,signal,empty,flag,tiny,sci,score\n'
    '"ctrl, A",0,-1.5,,TRUE,1e-3,2.5e+2,1.5\n'
    '"ctrl, A",1,-0.5,,FALSE,2e-3,3.0e+2,NA\n'
    '"drug, B",0,0.5,,TRUE,3e-3,4.0e+2,nan\n'
    '"drug, B",1,1.5,,FALSE,4e-3,5.0e+2,2.5\n'
    '\n'
    '\n'
)


def test_csv_edge_cases_parse_into_columns(tmp_path):
    path = tmp_path / 'trial.csv'
    path.write_text(CSV, encoding='utf-8')
    table = quick._read_table(path)
    assert list(table) == ['name', 'dose', 'signal', 'empty', 'flag', 'tiny', 'sci', 'score']
    assert table['name'] == ['ctrl, A', 'ctrl, A', 'drug, B', 'drug, B']
    assert table['dose'] == [0, 1, 0, 1]
    assert table['signal'] == [-1.5, -0.5, 0.5, 1.5]
    assert table['empty'] == [None] * 4
    assert table['flag'] == ['TRUE', 'FALSE', 'TRUE', 'FALSE']
    assert table['tiny'] == [1e-3, 2e-3, 3e-3, 4e-3]
    assert table['sci'] == [250, 300, 400, 500]
    assert table['score'] == [1.5, None, None, 2.5]

    _clean(i.line(path, x='dose', y='signal', color='name'))


def test_tsv_file_is_read_with_tabs(tmp_path):
    path = tmp_path / 'trial.tsv'
    path.write_text('time\tsignal\tgroup\n0\t1.0\tctrl\n1\t2.0\tctrl\n0\t3.0\tdrug\n1\t4.0\tdrug\n',
                    encoding='utf-8')
    table = quick._read_table(path)
    assert table == {'time': [0, 1, 0, 1], 'signal': [1.0, 2.0, 3.0, 4.0],
                     'group': ['ctrl', 'ctrl', 'drug', 'drug']}
    _clean(i.line(path, x='time', y='signal', color='group'))


# -- numpy arrays ------------------------------------------------------------


def test_numpy_arrays_as_x_and_y():
    np = pytest.importorskip('numpy')
    x = np.arange(4)
    y = np.array([1.0, 3.0, np.nan, 5.0])
    chart = i.line(x=x, y=y)
    _clean(chart)
    assert list(chart.spec._steps[0][2][0]) == [(0, 1.0), (1, 3.0)]
    assert list(chart.spec._steps[1][2][0]) == [(3, 5.0)]

    _clean(i.scatter(x=x, y=np.array([2.0, 4.0, 3.0, 5.0])))


def test_numpy_datetime64_array_as_x():
    np = pytest.importorskip('numpy')
    x = np.array(['2024-01-01', '2024-01-02', '2024-01-03'], dtype='datetime64[D]')
    chart = i.line(x=x, y=np.array([1.0, 2.0, 3.0]))
    _clean(chart)
    first = chart.spec._steps[0][2][0][0][0]
    assert first == datetime(2024, 1, 1)
