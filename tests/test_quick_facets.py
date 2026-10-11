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
