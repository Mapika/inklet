"""Facet options: free scales per panel and reference lines across a grid."""
import pytest

import inklet as i


# Four metrics on scales three orders of magnitude apart, two groups each.
METRICS = {'metric': [], 'step': [], 'value': [], 'run': []}
for metric, scale in (('accuracy', 1.0), ('loss', 50.0), ('auc', 0.1), ('norm', 1000.0)):
    for step in range(5):
        for run in ('a', 'b'):
            METRICS['metric'].append(metric)
            METRICS['step'].append(step * scale if metric == 'norm' else step)
            METRICS['value'].append(scale * (step + (run == 'b')) - scale)
            METRICS['run'].append(run)


def _clean(layout):
    figure = layout.compile()
    serious = [d for d in figure.lint() if d.severity in ('error', 'warning')]
    assert not serious, figure.report()
    return figure


def _grid(**options):
    return i.line(METRICS, x='step', y='value', color='run', facet_col='metric',
                  facet_col_wrap=2, **options)


# -- facet_scales --------------------------------------------------------------


def test_facets_share_both_scales_by_default():
    charts = list(_grid().charts())
    assert len({c.spec.options['y'] for c in charts}) == 1
    assert len({c.spec.options['x'] for c in charts}) == 1
    assert 'y' in charts[1]._hide_ticks and 'x' in charts[0]._hide_ticks


def test_free_y_fits_each_panel_to_its_own_rows():
    layout = _grid(facet_scales='free_y')
    charts = list(layout.charts())
    # y is left to each chart; x is still shared.
    assert all(c.spec.options['y'] == 'auto' for c in charts)
    assert len({c.spec.options['x'] for c in charts}) == 1
    # Every panel writes its own y numbers; the repeated y title still goes.
    assert not any('y' in c._hide_ticks for c in charts)
    assert charts[1]._ylabel == '' and charts[0]._ylabel is None
    # Shared x keeps hiding the numbers above the bottom row.
    assert 'x' in charts[0]._hide_ticks
    _clean(layout)


def test_free_y_panels_draw_their_own_ranges():
    figure = _grid(facet_scales='free_y').compile()
    svg = figure.to_svg()
    # The accuracy panel reads in units, the norm panel in thousands.
    assert '4000' in svg and '−1' in svg


def test_free_x_and_free_free_the_other_axes():
    free_x = list(_grid(facet_scales='free_x').charts())
    assert all(c.spec.options['x'] == 'auto' for c in free_x)
    assert len({c.spec.options['y'] for c in free_x}) == 1
    assert not any('x' in c._hide_ticks for c in free_x)
    assert free_x[0]._xlabel == ''
    free = list(_grid(facet_scales='free').charts())
    assert all(c.spec.options['x'] == 'auto' and c.spec.options['y'] == 'auto' for c in free)
    assert not any(c._hide_ticks for c in free)
    _clean(_grid(facet_scales='free'))


def test_a_free_axis_keeps_an_explicit_limit_and_a_log_scale():
    limited = list(_grid(facet_scales='free_x', ylim=(-2000, 5000)).charts())
    assert all(c.spec.options['y'] == (-2000, 5000) for c in limited)
    positive = {**METRICS, 'value': [abs(v) + 1 for v in METRICS['value']]}
    logged = i.line(positive, x='step', y='value', color='run', facet_col='metric',
                    yscale='log', facet_scales='free_y')
    assert all(c.spec.options['y'] == 'log' for c in logged.charts())
    _clean(logged)


def test_free_y_frees_the_right_hand_axis_too():
    rows = {'month': list(range(6)) * 2, 'site': ['north'] * 6 + ['south'] * 6,
            'rain': [60, 50, 58, 49, 61, 55, 600, 500, 580, 490, 610, 550],
            'temp': [1, 2, 5, 9, 13, 16, 1, 2, 5, 9, 13, 16]}
    layout = i.line(rows, x='month', y=['rain', 'temp'], secondary_y='temp',
                    facet_col='site', facet_scales='free_y')
    for chart in layout.charts():
        assert all(step[0] != 'secondary_y' or step[3].get('scale') is None
                   for step in chart.spec._steps)
    _clean(layout)


def test_facet_scales_is_checked():
    with pytest.raises(ValueError, match="'fixed', 'free_x', 'free_y' or 'free'"):
        _grid(facet_scales='independent')
    with pytest.raises(ValueError, match='needs facet_col= or facet_row='):
        i.line(METRICS, x='step', y='value', facet_scales='free_y')


def test_facet_rows_and_columns_free_y():
    layout = i.scatter(METRICS, x='step', y='value', facet_row='run', facet_col='metric',
                       facet_scales='free_y')
    charts = list(layout.charts())
    assert len(charts) == 8 and all(c.spec.options['y'] == 'auto' for c in charts)
    _clean(layout)


# -- reference lines on a faceted layout ---------------------------------------


def _rules(chart, method):
    return [args[0] for _, m, args, _ in chart.spec._steps if m == method]


def test_hline_on_a_facet_grid_draws_in_every_panel():
    layout = _grid()
    assert layout.hline(0, stroke_dash=(1.0, 0.8)) is layout
    assert all(_rules(c, 'hline') == [0] for c in layout.charts())
    _clean(layout)


def test_a_reference_line_outside_the_data_widens_every_shared_axis():
    layout = _grid().hline(-1500, label='floor')
    domains = {c.spec.options['y'] for c in layout.charts()}
    assert len(domains) == 1 and next(iter(domains))[0] <= -1500
    layout = _grid().vline(-3)
    domains = {c.spec.options['x'] for c in layout.charts()}
    assert len(domains) == 1 and next(iter(domains))[0] <= -3
    _clean(layout)


def test_an_explicit_limit_is_kept_after_a_reference_line():
    layout = _grid(ylim=(-10, 10)).hline(-1500)
    assert all(c.spec.options['y'] == (-10, 10) for c in layout.charts())


def test_hline_takes_a_value_per_facet_from_a_dict():
    layout = _grid(facet_scales='free_y').hline({'loss': 120, 'norm': [500, 3500]})
    by_title = {c.title: _rules(c, 'hline') for c in layout.charts()}
    assert by_title == {'accuracy': [], 'loss': [120], 'auc': [], 'norm': [500, 3500]}
    _clean(layout)


def test_hline_reads_a_value_per_facet_from_a_column():
    rows = dict(METRICS)
    chance = {'accuracy': 0.5, 'loss': 120, 'auc': 0.25, 'norm': 3500}
    rows['chance'] = [chance[m] for m in rows['metric']]
    layout = i.line(rows, x='step', y='value', color='run', facet_col='metric',
                    facet_col_wrap=2, facet_scales='free_y')
    layout.hline('chance', label='chance', stroke_dash=(1.0, 0.8))
    assert {c.title: _rules(c, 'hline') for c in layout.charts()} == {
        m: [v] for m, v in chance.items()}
    _clean(layout)


def test_hline_reads_values_from_another_table_by_the_facet_column():
    thresholds = {'metric': ['loss', 'loss', 'auc'], 'level': [100, 150, 0.2]}
    layout = _grid(facet_scales='free_y').hline('level', data=thresholds)
    by_title = {c.title: _rules(c, 'hline') for c in layout.charts()}
    assert by_title == {'accuracy': [], 'loss': [100, 150], 'auc': [0.2], 'norm': []}
    with pytest.raises(ValueError, match="facet column 'metric'"):
        _grid().hline('level', data={'level': [1]})
    with pytest.raises(ValueError, match='column of that table'):
        _grid().hline('nope', data=thresholds)


def test_vline_per_facet_and_on_rows_and_columns():
    layout = i.scatter(METRICS, x='step', y='value', facet_row='run', facet_col='metric',
                       facet_scales='free')
    layout.vline({'loss': 2, ('b', 'auc'): 3, 'a': 1})
    by_key = {key: _rules(c, 'vline') for key, c in zip(layout._facets.keys, layout.charts())}
    assert by_key[('a', 'loss')] == [1, 2] and by_key[('b', 'loss')] == [2]
    assert by_key[('b', 'auc')] == [3] and by_key[('a', 'auc')] == [1]
    assert by_key[('b', 'norm')] == []


def test_a_dict_naming_no_facet_raises():
    with pytest.raises(ValueError, match="'los'.*the facets are 'accuracy', 'loss'"):
        _grid().hline({'los': 1})


def test_hline_on_a_plain_layout():
    a = i.line(METRICS, x='step', y='value', color='run')
    b = i.scatter(METRICS, x='step', y='value', color='run')
    layout = (a | b).hline(0)
    assert _rules(a, 'hline') == [0] and _rules(b, 'hline') == [0]
    with pytest.raises(TypeError, match='only on a faceted layout'):
        (a | b).hline({'x': 1})
