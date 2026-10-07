"""One-call charts, layouts, notebook display and the agent tooling."""
import json
import warnings

import pytest

import inklet as i
from inklet.cli import main


DATA = {
    'time': [0, 1, 2, 3] * 2,
    'signal': [1.0, 3.0, 2.0, 4.0, 2.0, 4.0, 3.0, 5.0],
    'cond': ['ctrl'] * 4 + ['drug'] * 4,
}


def _clean(chart):
    figure = chart.compile()
    serious = [d for d in figure.lint() if d.severity in ('error', 'warning')]
    assert not serious, figure.report()
    return figure


@pytest.mark.parametrize('make', [
    lambda: i.line(DATA, x='time', y='signal', color='cond'),
    lambda: i.scatter(DATA, x='time', y='signal', color='cond'),
    lambda: i.bar(DATA, x='cond', y='signal'),
    lambda: i.bar(DATA, x='time', y='signal', color='cond', stacked=True),
    lambda: i.hist(DATA, x='signal', color='cond', bins=4),
    lambda: i.kde(DATA, x='signal'),
    lambda: i.ecdf(DATA, x='signal', color='cond'),
    lambda: i.boxplot(DATA, x='cond', y='signal', points=True),
    lambda: i.violin(DATA, x='cond', y='signal'),
    lambda: i.strip(DATA, x='cond', y='signal'),
    lambda: i.area(DATA, x='time', y='signal', color='cond'),
    lambda: i.regression(DATA, x='time', y='signal'),
    lambda: i.heatmap([[1, 2], [3, 4]], x=['a', 'b'], y=['r1', 'r2']),
    lambda: i.heatmap(DATA, x='time', y='cond', z='signal'),
    lambda: i.line(x=[1, 2, 3], y=[2, 4, 3]),
    lambda: i.line(DATA, x='time', y='signal', error_y='signal'),
])
def test_every_chart_compiles_cleanly(make):
    _clean(make())


def test_records_and_dataframes_are_tables():
    records = [{'x': 1, 'y': 2}, {'x': 2, 'y': 3}]
    _clean(i.scatter(records, x='x', y='y'))
    pandas = pytest.importorskip('pandas')
    frame = pandas.DataFrame(DATA)
    _clean(i.line(frame, x='time', y='signal', color='cond'))
    wide = pandas.DataFrame({'a': [1, 2, 3], 'b': [3, 1, 2]})
    chart = i.line(wide, y=['a', 'b'])
    assert chart._named == 2
    _clean(chart)


def test_missing_values_are_dropped_not_shifted():
    chart = i.line({'x': [0, 1, 2, 3], 'y': [1.0, float('nan'), 2.0, None]}, x='x', y='y')
    points = chart.spec._steps[0][2][0]
    assert points == ((0, 1.0), (2, 2.0))


def test_unknown_columns_name_the_columns_there_are():
    with pytest.raises(KeyError, match='columns are time, signal, cond'):
        i.line(DATA, x='time', y='sgnal')


def test_column_labels_become_axis_titles_and_groups_get_a_legend():
    chart = i.line(DATA, x='time', y='signal', color='cond')
    steps = {step[1]: step for step in chart.plot()._steps}
    assert steps['axes'][3]['x'] == 'time' and steps['axes'][3]['y'] == 'signal'
    assert 'legend' in steps
    single = i.line(DATA, x='time', y='signal')
    assert 'legend' not in {step[1] for step in single.plot()._steps}


def test_literal_colour_is_not_a_column():
    chart = i.line(DATA, x='time', y='signal', color='#c1121f')
    assert chart.spec._steps[0][3]['color'] == '#c1121f'


def test_bars_without_y_count_rows():
    chart = i.bar({'fruit': ['fig', 'fig', 'pear']}, x='fruit')
    assert chart.spec._steps[0][2][1] == (2.0, 1.0)


def test_layering_and_panel_methods_chain():
    chart = i.scatter(DATA, x='time', y='signal').line(DATA, x='time', y='signal')
    assert chart.hline(2.5) is chart
    assert [step[1] for step in chart.spec._steps] == ['scatter', 'line', 'hline']
    _clean(chart)


def test_explicit_limits_clip():
    chart = i.line(DATA, x='time', y='signal', ylim=(0, 2))
    assert chart.spec.options['clip'] is True
    assert chart.spec.options['y'] == (0, 2)


def test_sizes_styles_and_palettes():
    figure = i.line(DATA, x='time', y='signal', width='double', height=40,
                    style='scientific.nature', palette='okabe-ito').compile()
    assert figure.root.bbox.width == pytest.approx(183, abs=0.5)
    narrow = i.line(DATA, x='time', y='signal', width=120).compile()
    assert narrow.root.bbox.width == pytest.approx(120, abs=0.5)


def test_layouts_letter_every_chart_in_one_grid():
    a = i.line(DATA, x='time', y='signal')
    b = i.boxplot(DATA, x='cond', y='signal')
    c = i.hist(DATA, x='signal')
    layout = (a | b) / c
    assert layout.direction == 'column' and len(layout.items) == 2
    columns, cells = layout._grid()
    assert columns == 2 and [cell[1:] for cell in cells] == [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 2)]
    figure = layout.compile()
    svg = figure.to_svg(text='names')
    for letter in ('>a<', '>b<', '>c<'):
        assert letter in svg
    assert (a | b | c).items == (a, b, c)


def test_crowded_categories_turn_to_fit():
    labels = [f'a long category label {n}' for n in range(8)]
    _clean(i.bar({'c': labels, 'v': list(range(8))}, x='c', y='v'))
    chart = i.bar({'c': ['a', 'b'], 'v': [1, 2]}, x='c', y='v')
    profile = i.preset('scientific.general', format='single-column')
    assert chart._tick_options(80, profile) is None


def _crowded():
    # Explicit axes skip the automatic label rotation, so the labels collide.
    labels = [f'a long category label {n}' for n in range(8)]
    return i.bar({'c': labels, 'v': list(range(8))}, x='c', y='v').axes(x='c', y='v')


def test_save_warns_with_the_report_when_layout_has_problems(tmp_path):
    chart = _crowded()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        chart.save(tmp_path / 'a.svg')
    assert any(issubclass(w.category, i.LayoutWarning) for w in caught)


def test_notebook_bundles_hold_an_isolated_image():
    chart = i.line(DATA, x='time', y='signal')
    assert i.plot_spec()._repr_mimebundle_() == {'text/plain': '<inklet plot_spec, no marks yet>'}
    for obj in (chart, chart.document(), chart.compile(), chart | chart,
                i.plot_spec().line([(0, 1), (2, 3)])):
        bundle = obj._repr_mimebundle_()
        assert bundle['text/html'].startswith('<img src="data:image/svg+xml;base64,')
        assert bundle['image/svg+xml'].startswith('<svg') or '<svg' in bundle['image/svg+xml'][:200]
        assert bundle['text/plain'].startswith('<inklet figure')


def test_show_outside_a_notebook_writes_a_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path = i.line(DATA, x='time', y='signal').show()
    assert path.exists() and 'wrote' in capsys.readouterr().out


def test_cli_check_reports_and_writes_a_preview(tmp_path, capsys):
    script = tmp_path / 'chart.py'
    script.write_text("import inklet as i\nchart = i.line(x=[1, 2, 3], y=[2, 4, 3])\n")
    assert main(['check', str(script), '--json']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['ok'] and report['diagnostics'] == [] and report['size_mm'][0] == 89.0
    pytest.importorskip('resvg_py')
    assert main(['check', str(script), '--png', str(tmp_path / 'p.png')]) == 0
    assert (tmp_path / 'p.png').exists()


def test_cli_check_fails_on_errors(tmp_path, capsys):
    script = tmp_path / 'bad.py'
    script.write_text(
        "import inklet as i\nlabels = [f'a long category label {n}' for n in range(8)]\n"
        "chart = i.bar({'c': labels, 'v': list(range(8))}, x='c', y='v').axes(x='c', y='v')\n")
    assert main(['check', str(script)]) == 1
    assert 'OVERLAP' in capsys.readouterr().out


def test_guide_and_skill(tmp_path, capsys):
    assert main(['guide']) == 0
    text = capsys.readouterr().out
    assert 'i.line(df' in text and 'inklet check' in text
    assert main(['guide', '--api']) == 0
    api = capsys.readouterr().out
    for method in ('volcano', 'kaplan_meier', 'scatter'):
        assert f'- `{method}(' in api
    assert '<deprecated' not in api
    assert main(['skill', str(tmp_path)]) == 0
    skill = (tmp_path / 'inklet' / 'SKILL.md').read_text()
    assert skill.startswith('---\nname: inklet\ndescription: ')


def test_datetime_columns_become_a_time_axis():
    pandas = pytest.importorskip('pandas')
    frame = pandas.DataFrame({'when': pandas.date_range('2026-01-01', periods=4, freq='D'),
                              'v': [1.0, 2.0, 3.0, 4.0]})
    frame.loc[1, 'when'] = pandas.NaT
    chart = i.line(frame, x='when', y='v')
    points = chart.spec._steps[0][2][0]
    assert len(points) == 3 and points[0][0].year == 2026
    _clean(chart)


def test_forwarded_plot_methods_count_series_and_categories():
    chart = i.chart().barplot(['control', 'treated'], [[[1, 2], [2, 3]], [[1, 1], [2, 2]]],
                              name=['wt', 'ko'])
    assert chart._named == 2 and chart._x_categories == ['control', 'treated']
    assert 'legend' in {step[1] for step in chart.plot()._steps}


def test_a_list_of_colours_is_rejected_with_a_hint():
    with pytest.raises(TypeError, match='palette'):
        i.line(x=[1, 2], y=[1, 2], color=['red', 'blue'])


def test_an_empty_axis_title_reserves_no_row():
    chart = i.boxplot(DATA, x='cond', y='signal', xlabel='')
    axes = next(step for step in chart.plot()._steps if step[1] == 'axes')
    assert axes[3]['x'] is None


def test_grouped_error_bands_are_translucent_and_under_the_lines():
    chart = i.line(DATA, x='time', y='signal', color='cond', error_y='signal')
    bands = [k for _, m, _, k in chart.plot()._steps if m == 'band']
    assert len(bands) == 2 and all(k['fill_opacity'] < 1 for k in bands)
    _clean(chart)


def test_heatmap_colorbar_title():
    chart = i.heatmap([[1, 2], [3, 4]], colorbar='r')
    assert next(k for _, m, _, k in chart.spec._steps if m == 'colorbar')['title'] == 'r'


def test_save_passes_dpi_only_to_raster_output(tmp_path):
    i.line(x=[1, 2], y=[1, 2]).save(tmp_path / 'a.svg', tmp_path / 'a.pdf', dpi=200)
    assert (tmp_path / 'a.pdf').exists()


FACETS = [{'cell': cell, 'drug': drug, 't': t, 'v': t * (2 if drug == 'drug' else 1) + k}
          for k, cell in enumerate(('HeLa', 'U2OS', 'RPE1'))
          for drug in ('vehicle', 'drug') for t in range(4)]


def test_facets_share_scales_colours_and_one_key():
    layout = i.line(FACETS, x='t', y='v', color='drug', facet_col='cell')
    assert isinstance(layout, i.Layout) and layout.direction == 'grid' and layout.columns == 3
    charts = list(layout.charts())
    assert [c.title for c in charts] == ['HeLa', 'U2OS', 'RPE1']
    # Shared y domain covers the largest facet.
    assert len({c.spec.options['y'] for c in charts}) == 1
    assert charts[0].spec.options['y'][1] >= 8
    # Same group, same palette slot in every facet.
    for chart in charts:
        assert chart._series_tokens == {'vehicle': '@series0', 'drug': '@series1'}
    keys = [c for c in charts if 'legend' in {s[1] for s in c.plot()._steps}]
    assert keys == [charts[-1]]
    assert 'y' in charts[1]._hide_ticks and 'y' not in charts[0]._hide_ticks
    assert not layout.letters
    _clean(layout)


def test_facet_rows_and_wrapping():
    grid = i.scatter(FACETS, x='t', y='v', facet_row='drug', facet_col='cell')
    assert len(grid.items) == 6 and grid.columns == 3
    wrapped = i.boxplot(FACETS, x='drug', y='v', facet_col='cell', facet_col_wrap=2)
    charts = list(wrapped.charts())
    # The first facet has one below it; the second does not, so it keeps its numbers.
    assert 'x' in charts[0]._hide_ticks and 'x' not in charts[1]._hide_ticks
    _clean(grid)
    numeric = i.line(FACETS, x='t', y='v', facet_col='t')
    assert list(numeric.charts())[0].title == 't = 0'


def test_direct_labels_replace_the_key():
    chart = i.line(DATA, x='time', y='signal', color='cond', legend='direct')
    methods = {step[1] for step in chart.plot()._steps}
    assert 'label_lines' in methods and 'legend' not in methods
    scatter = i.scatter(DATA, x='time', y='signal', color='cond', legend='direct')
    assert 'legend' in {step[1] for step in scatter.plot()._steps}


def test_point_labels_and_sizes_follow_their_groups():
    data = {'x': [1, 2, 3, 4], 'y': [1, 3, 2, 4], 'g': ['a', 'b', 'a', None],
            's': [1.0, 2.0, 3.0, 4.0], 'name': ['p', None, 'r', 's']}
    chart = i.scatter(data, x='x', y='y', color='g', size='s', text='name')
    scatters = [(a, k) for _, m, a, k in chart.spec._steps if m == 'scatter']
    assert scatters[0][1]['size'] == (1.0, 3.0) and scatters[1][1]['size'] == (2.0,)
    labels = next(a for _, m, a, _ in chart.spec._steps if m == 'label_points')
    # The row without a group is not drawn, so it is not labelled.
    assert labels[1] == ('p', 'r')
    _clean(chart)


def test_csv_paths_are_tables(tmp_path):
    path = tmp_path / 'data.csv'
    path.write_text('when,count,dose,group\n2026-01-01,3,0.5,a\n2026-01-02,5,,b\n')
    from inklet.quick import _table
    table = _table(path)
    assert table['count'] == [3, 5] and table['dose'] == [0.5, None]
    assert table['when'][0].day == 1 and table['group'] == ['a', 'b']
    _clean(i.bar(str(path), x='group', y='count'))
    with pytest.raises(FileNotFoundError):
        i.line(tmp_path / 'missing.csv', x='a', y='b')


def test_bars_can_show_a_mean_with_its_error():
    data = {'g': ['a', 'a', 'a', 'b', 'b'], 'v': [1.0, 2.0, 3.0, 4.0, 6.0], 's': list('xyxyx')}
    chart = i.bar(data, x='g', y='v', agg='mean', error_y='sem', points=True)
    step = next(k for _, m, _, k in chart.spec._steps if m == 'barplot')
    assert step['estimator'] == 'mean' and step['error'] == 'sem' and step['points']
    _clean(chart)
    grouped = i.bar(data, x='g', y='v', color='s', agg='median')
    assert grouped._named == 2
    _clean(grouped)
    with pytest.raises(ValueError, match='sem'):
        i.bar(data, x='g', y='v', agg='mean', error_y='stderr')
    summed = i.bar(data, x='g', y='v')
    assert summed.spec._steps[0][2][1] == (6.0, 10.0)


def test_lines_join_points_in_x_order_and_default_to_every_numeric_column():
    chart = i.line({'x': [3, 1, 2], 'y': [30, 10, 20]}, x='x', y='y')
    assert chart.spec._steps[0][2][0] == ((1, 10), (2, 20), (3, 30))
    kept = i.line({'x': [3, 1, 2], 'y': [30, 10, 20]}, x='x', y='y', sort=False)
    assert kept.spec._steps[0][2][0] == ((3, 30), (1, 10), (2, 20))
    wide = i.line({'t': [0, 1], 'a': [1, 2], 'b': [2, 1], 'label': ['p', 'q']}, x='t')
    assert [k['name'] for _, m, _, k in wide.spec._steps if m == 'line'] == ['a', 'b']
