"""One-call pie, lollipop, dumbbell, waterfall and slope charts, and the names they export."""
import pytest

import inklet as i
from inklet import quick
from inklet.core import DiagramError


CELLS = {
    'cell': ['Neurons', 'Glia', 'Vascular', 'Immune', 'Other'],
    'n': [54, 28, 12, 4, 2],
}

PATHWAYS = {
    'pathway': ['Interferon', 'Apoptosis', 'Cell cycle', 'Hypoxia', 'Lipid'],
    'score': [2.4, -1.1, 0.6, -2.3, 1.2],
}

SITES = {
    'site': ['Ridge', 'Meadow', 'Marsh', 'Forest'],
    'before': [4.1, 5.0, 3.2, 6.1],
    'after': [5.6, 4.8, 4.4, 7.0],
}

STEPS = {
    'step': ['Start', 'Sales', 'Costs', 'Tax', 'End'],
    'change': [120, 45, -30, -12, None],
}

SURVEY = {
    'year': [2015, 2015, 2015, 2025, 2025, 2025],
    'country': ['Denmark', 'Spain', 'Italy', 'Denmark', 'Spain', 'Italy'],
    'share': [42, 30, 25, 61, 28, 40],
}


def _clean(chart):
    figure = chart.compile()
    serious = [d for d in figure.lint() if d.severity in ('error', 'warning')]
    assert not serious, figure.report()
    return figure


def _step(chart, method):
    return next(step for step in chart.spec._steps if step[1] == method)


def _axis_titles(chart):
    axes = next(k for _, m, _, k in chart.plot()._steps if m == 'axes')
    return axes['x'], axes['y']


# -- pie --------------------------------------------------------------------

@pytest.mark.parametrize('make', [
    lambda: i.pie(CELLS, names='cell', values='n'),
    lambda: i.pie(CELLS, names='cell', values='n', hole=0.5, legend='bottom'),
    lambda: i.pie(CELLS, names='cell', values='n', legend=False, labels='value'),
    lambda: i.pie(CELLS, names='cell', values='n', labels='{share:.1%}', title='Cell types'),
    lambda: i.pie(CELLS, names='cell', values='n', legend='left', width=60),
    lambda: i.pie(values=[1, 2, 3], names=['a', 'b', 'c']),
])
def test_pie_builds_and_compiles(make):
    _clean(make())


def test_pie_draws_slices_in_palette_order():
    palette = ['#111111', '#222222', '#333333', '#444444', '#555555']
    svg = i.pie(CELLS, names='cell', values='n', palette=palette, legend=False).to_svg()
    positions = [svg.index(colour) for colour in palette]
    assert positions == sorted(positions)


def test_pie_labels_are_the_pie_shares_by_default():
    svg = i.pie(CELLS, names='cell', values='n').to_svg()
    assert '54%' in svg and '28%' in svg
    assert '54%' not in i.pie(CELLS, names='cell', values='n', labels='value').to_svg()


def test_donut_has_a_hole_and_pie_does_not():
    pie = i.pie(CELLS, names='cell', values='n').to_svg()
    donut = i.pie(CELLS, names='cell', values='n', hole=0.5).to_svg()
    assert donut != pie


def test_pie_hole_is_a_fraction_of_the_radius():
    # A millimetre hole (hole=7) would be silently a huge one on a small disc.
    for hole in (5, 1, -0.1, True, 'half'):
        with pytest.raises(ValueError, match='fraction of the radius'):
            i.pie(CELLS, names='cell', values='n', hole=hole)


def test_pie_names_its_missing_and_mismatched_inputs():
    with pytest.raises(ValueError, match='values='):
        i.pie(CELLS, names='cell')
    with pytest.raises(KeyError, match='nope'):
        i.pie(CELLS, names='cell', values='nope')
    with pytest.raises(ValueError, match='3 names for 5 values'):
        i.pie(CELLS, names=['a', 'b', 'c'], values='n')
    with pytest.raises(ValueError, match='missing'):
        i.pie({'cell': ['a', 'b'], 'n': [1, None]}, names='cell', values='n')


def test_pie_key_sits_beside_the_disc():
    # A corner key lands on the slices; the lint says so, so the call refuses it.
    for legend in ('ne', 'sw', 'direct'):
        with pytest.raises(ValueError, match='beside the disc'):
            i.pie(CELLS, names='cell', values='n', legend=legend)


def test_pie_takes_a_bare_sequence_only_as_named_arguments():
    with pytest.raises(TypeError, match=r'names=\[\.\.\.\], values=\[\.\.\.\]'):
        i.pie([54, 28, 12])


def test_pie_fits_its_cell_width():
    narrow = _clean(i.pie(CELLS, names='cell', values='n', width=50))
    wide = _clean(i.pie(CELLS, names='cell', values='n', width=120))
    assert narrow.to_svg() != wide.to_svg()


def test_pie_is_a_chart_so_layouts_and_save_take_it(tmp_path):
    pie = i.pie(CELLS, names='cell', values='n')
    figure = pie | i.lollipop(PATHWAYS, x='pathway', y='score')
    assert isinstance(pie, quick.Chart)
    path = tmp_path / 'pair.svg'
    figure.save(path)
    assert path.read_text().count('<svg') >= 1


# -- lollipop ---------------------------------------------------------------

@pytest.mark.parametrize('make', [
    lambda: i.lollipop(PATHWAYS, x='pathway', y='score'),
    lambda: i.lollipop(PATHWAYS, x='pathway', y='score', orient='h'),
    lambda: i.lollipop(PATHWAYS, x='pathway', y='score', color='#c1121f', baseline=-1.0),
])
def test_lollipop_builds_and_compiles(make):
    _clean(make())


def test_lollipop_titles_its_axes_from_the_columns():
    assert _axis_titles(i.lollipop(PATHWAYS, x='pathway', y='score')) == ('pathway', 'score')
    assert _axis_titles(i.lollipop(PATHWAYS, x='pathway', y='score', orient='h')) == ('score', 'pathway')


def test_lollipop_colour_is_one_colour_not_a_column():
    chart = i.lollipop(PATHWAYS, x='pathway', y='score', color='#c1121f')
    assert _step(chart, 'lollipop')[3]['color'] == '#c1121f'
    with pytest.raises(ValueError, match='facet_col='):
        i.lollipop(PATHWAYS, x='pathway', y='score', color='pathway')


def test_lollipop_wants_one_row_per_category():
    table = {'pathway': ['a', 'b', 'a'], 'score': [1, 2, 3]}
    with pytest.raises(ValueError, match="'a' appears more than once"):
        i.lollipop(table, x='pathway', y='score')


def test_lollipop_horizontal_reads_rows_top_down():
    chart = i.lollipop(PATHWAYS, x='pathway', y='score', orient='h')
    assert tuple(chart.spec.options['y']) == tuple(reversed(PATHWAYS['pathway']))


def test_lollipop_missing_value_draws_nothing_for_its_category():
    table = {**PATHWAYS, 'score': [2.4, None, 0.6, -2.3, 1.2]}
    _clean(i.lollipop(table, x='pathway', y='score'))


# -- dumbbell ---------------------------------------------------------------

def test_dumbbell_builds_and_compiles():
    _clean(i.dumbbell(SITES, y='site', x=['before', 'after']))


def test_dumbbell_names_its_dots_and_titles_the_value_axis():
    chart = i.dumbbell(SITES, y='site', x=['before', 'after'])
    assert tuple(_step(chart, 'dumbbell')[3]['name']) == ('before', 'after')
    assert _axis_titles(chart) == ('before / after', 'site')


def test_dumbbell_rows_run_top_down_in_table_order():
    chart = i.dumbbell(SITES, y='site', x=['before', 'after'])
    assert tuple(chart.spec.options['y']) == ('Forest', 'Marsh', 'Meadow', 'Ridge')


def test_dumbbell_takes_two_value_columns():
    with pytest.raises(ValueError, match=r'x=\[start, end\]'):
        i.dumbbell(SITES, y='site', x='before')
    with pytest.raises(ValueError, match='no data'):
        i.dumbbell(y=['a'], x=['b', 'c'])


def test_dumbbell_missing_value_draws_one_dot():
    table = {**SITES, 'after': [5.6, None, 4.4, 7.0]}
    _clean(i.dumbbell(table, y='site', x=['before', 'after']))


# -- waterfall --------------------------------------------------------------

def test_waterfall_builds_and_compiles():
    _clean(i.waterfall(STEPS, x='step', y='change', totals=['Start', 'End']))
    _clean(i.waterfall(STEPS, x='step', y='change', totals=['Start', 'End'], labels=False))
    _clean(i.waterfall(STEPS, x='step', y='change', totals=('Start', 'End'), connectors=False))


def test_waterfall_fits_its_range_to_the_running_total():
    chart = i.waterfall(STEPS, x='step', y='change', totals=['Start', 'End'])
    low, high = chart.spec.options['y']
    assert low == 0.0 and high >= 165      # 120 + 45 is the highest the bars reach


def test_waterfall_keeps_steps_in_row_order_and_titles_axes():
    chart = i.waterfall(STEPS, x='step', y='change', totals=['Start', 'End'])
    assert tuple(chart.spec.options['x']) == tuple(STEPS['step'])
    assert _axis_titles(chart) == ('step', 'change')


def test_waterfall_respects_its_own_range():
    chart = i.waterfall(STEPS, x='step', y='change', totals=['Start', 'End'], ylim=(0, 300))
    assert chart.spec.options['y'] == (0, 300)


def test_waterfall_totals_must_be_steps_and_steps_unique():
    with pytest.raises(ValueError, match='not steps'):
        i.waterfall(STEPS, x='step', y='change', totals=['Opening'])
    table = {'step': ['a', 'a'], 'change': [1, 2]}
    with pytest.raises(ValueError, match='unique'):
        i.waterfall(table, x='step', y='change')


def test_waterfall_changes_may_be_missing_only_at_totals():
    table = {'step': ['Start', 'Sales'], 'change': [10, None]}
    with pytest.raises(DiagramError):
        i.waterfall(table, x='step', y='change', totals=['Start'])


# -- slope ------------------------------------------------------------------

def test_slope_builds_and_compiles():
    _clean(i.slope(SURVEY, x='year', y='share', group='country', format='{:.0f}%'))
    _clean(i.slope(SURVEY, x='year', y='share', group='country', labels='left', highlight='Spain'))


def test_slope_puts_numeric_time_points_in_order():
    reversed_years = {k: list(reversed(v)) for k, v in SURVEY.items()}
    chart = i.slope(reversed_years, x='year', y='share', group='country')
    assert tuple(chart.spec.options['x']) == ('2015', '2025')


def test_slope_has_one_series_per_group_with_values_in_time_order():
    chart = i.slope(SURVEY, x='year', y='share', group='country')
    series = _step(chart, 'slope')[2][0]
    assert {k: list(v) for k, v in series.items()} == {
        'Denmark': [42, 61], 'Spain': [30, 28], 'Italy': [25, 40]}


def test_slope_gap_where_a_group_has_no_value():
    table = {**SURVEY, 'share': [42, 30, 25, None, 28, 40]}
    chart = i.slope(table, x='year', y='share', group='country')
    assert list(_step(chart, 'slope')[2][0]['Denmark']) == [42, None]
    _clean(chart)


def test_slope_fits_the_range_to_its_values_unless_ylim_is_given():
    low, high = i.slope(SURVEY, x='year', y='share', group='country').spec.options['y']
    assert low < 25 and high > 61
    assert i.slope(SURVEY, x='year', y='share', group='country', ylim=(0, 100)).spec.options['y'] == (0, 100)


def test_slope_passes_format_and_highlight_to_the_panel():
    chart = i.slope(SURVEY, x='year', y='share', group='country', format='{:.0f}%', highlight=['Spain'])
    kwargs = _step(chart, 'slope')[3]
    assert kwargs['format'] == '{:.0f}%' and tuple(kwargs['highlight']) == ('Spain',)


def test_slope_wants_one_row_per_group_and_time_point():
    table = {**SURVEY, 'year': [2015] * 6}
    with pytest.raises(ValueError, match='appears more than once'):
        i.slope(table, x='year', y='share', group='country')
    with pytest.raises(ValueError, match='group='):
        i.slope(SURVEY, x='year', y='share')


# -- names ------------------------------------------------------------------

NEW = ('pie', 'lollipop', 'dumbbell', 'waterfall', 'slope')


@pytest.mark.parametrize('name', NEW)
def test_new_charts_are_exported_documented_and_listed(name):
    assert getattr(i, name) is getattr(quick, name)
    assert name in i.__all__ and name in quick.__all__
    assert (getattr(i, name).__doc__ or '').strip()
