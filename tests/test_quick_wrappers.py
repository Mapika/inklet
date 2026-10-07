"""One-call survival, volcano and forest charts, and the names they export."""
import pytest

import inklet as i
from inklet import quick
from inklet.core import Diagram, DiagramError


SURVIVAL = {
    'months': [5, 8, 12, 15, 20, 22, 25, 30, 33, 36, 3, 4, 6, 9, 10, 11, 14, 16, 18, 24],
    'died': [1, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 0, 1, 1, 0],
    'arm': ['control'] * 10 + ['drug'] * 10,
}

VOLCANO = {
    'log2fc': [2.1, -1.8, 0.2, 1.6, -0.1, 0.9, -2.4, 1.2, 0.05, -0.6, 1.4, 0.3],
    'p': [1e-5, 1e-4, 0.4, 1e-3, 0.2, 0.01, 1e-6, 0.3, 0.7, 0.04, 2e-3, 0.5],
    'gene': [f'G{k}' for k in range(12)],
    'fdr': [1e-3, 1e-2, None, 1e-2, 0.4, 0.05, 1e-4, 0.5, 0.8, 0.1, 1e-2, 0.6],
}

FOREST = [
    {'study': 'Ahmed 2019', 'or': 0.72, 'lo': 0.55, 'hi': 0.94, 'n': 812, 'w': 18.2, 'sum': False},
    {'study': 'Berg 2020', 'or': 0.91, 'lo': 0.62, 'hi': 1.33, 'n': 355, 'w': 9.4, 'sum': False},
    {'study': 'Chen 2021', 'or': 0.64, 'lo': 0.38, 'hi': 1.08, 'n': 210, 'w': 6.1, 'sum': False},
    {'study': 'Overall', 'or': 0.79, 'lo': 0.66, 'hi': 0.95, 'n': 1377, 'w': None, 'sum': True},
]


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


# -- survival ---------------------------------------------------------------

@pytest.mark.parametrize('make', [
    lambda: i.survival(SURVIVAL, time='months', event='died', color='arm'),
    lambda: i.survival(SURVIVAL, time='months', event='died'),
    lambda: i.survival(SURVIVAL, time='months', event='died', color='#c1121f'),
    lambda: i.survival(SURVIVAL, time='months', event='died', color='arm', at_risk=False),
    lambda: i.survival(SURVIVAL, time='months', event='died', color='arm', pvalue=False, band=None),
    lambda: i.survival(SURVIVAL, time='months', event='died', color='arm', band='linear'),
])
def test_survival_builds_and_compiles(make):
    _clean(make())


def test_each_group_is_one_curve():
    chart = i.survival(SURVIVAL, time='months', event='died', color='arm')
    curves = _step(chart, 'kaplan_meier')[2][0]
    assert set(curves) == {'control', 'drug'}
    assert len(curves['control'][0]) == 10 and len(curves['drug'][0]) == 10


def test_one_group_is_one_unnamed_curve():
    chart = i.survival(SURVIVAL, time='months', event='died')
    durations, events = _step(chart, 'kaplan_meier')[2][0]
    assert len(durations) == 20 and len(events) == 20


def test_logrank_pvalue_needs_two_groups():
    grouped = i.survival(SURVIVAL, time='months', event='died', color='arm')
    assert _step(grouped, 'kaplan_meier')[3]['pvalue'] == 'logrank'
    single = i.survival(SURVIVAL, time='months', event='died')
    assert 'pvalue' not in _step(single, 'kaplan_meier')[3]
    off = i.survival(SURVIVAL, time='months', event='died', color='arm', pvalue=False)
    assert 'pvalue' not in _step(off, 'kaplan_meier')[3]


def test_at_risk_table_follows_the_curves():
    assert 'at_risk' in {step[1] for step in i.survival(SURVIVAL, time='months', event='died').spec._steps}
    off = i.survival(SURVIVAL, time='months', event='died', at_risk=False)
    assert 'at_risk' not in {step[1] for step in off.spec._steps}


def test_survival_axes_are_labelled_and_run_from_zero_to_one():
    chart = i.survival(SURVIVAL, time='months', event='died', color='arm')
    assert _axis_titles(chart) == ('months', 'Survival probability')
    assert chart.spec.options['y'] == (0, 1)
    explicit = i.survival(SURVIVAL, time='months', event='died', ylim=(0, 2))
    assert explicit.spec.options['y'] == (0, 2)


def test_missing_durations_and_events_drop_the_row():
    table = {**SURVIVAL, 'died': [None] + SURVIVAL['died'][1:]}
    chart = i.survival(table, time='months', event='died')
    durations, events = _step(chart, 'kaplan_meier')[2][0]
    assert len(durations) == 19 and None not in events


def test_survival_names_missing_columns():
    with pytest.raises(KeyError, match='nope'):
        i.survival(SURVIVAL, time='nope', event='died')
    with pytest.raises(ValueError, match='time= and event='):
        i.survival(SURVIVAL, event='died')


# -- volcano ----------------------------------------------------------------

def test_volcano_builds_and_compiles():
    _clean(i.volcano(VOLCANO, x='log2fc', y='p'))
    _clean(i.volcano(VOLCANO, x='log2fc', y='p', label='gene', q='fdr', highlight=['G0', 'G6']))


def test_volcano_passes_fold_p_labels_and_highlight_through():
    chart = i.volcano(VOLCANO, x='log2fc', y='p', label='gene', highlight=['G0', 'G6'])
    fold, p = _step(chart, 'volcano')[2]
    assert list(fold) == VOLCANO['log2fc'] and list(p) == VOLCANO['p']
    kwargs = _step(chart, 'volcano')[3]
    assert list(kwargs['labels']) == VOLCANO['gene']
    assert list(kwargs['highlight']) == ['G0', 'G6']


def test_volcano_q_is_passed_with_its_missing_values_kept():
    chart = i.volcano(VOLCANO, x='log2fc', y='p', q='fdr')
    kwargs = _step(chart, 'volcano')[3]
    assert kwargs['q'][2] is None and len(kwargs['q']) == 12
    assert list(kwargs['q']) == VOLCANO['fdr']


def test_volcano_drops_rows_missing_fold_or_p():
    table = {**VOLCANO, 'p': [None] + VOLCANO['p'][1:]}
    chart = i.volcano(table, x='log2fc', y='p', label='gene')
    fold, p = _step(chart, 'volcano')[2]
    assert len(fold) == 11 and None not in p
    assert list(_step(chart, 'volcano')[3]['labels']) == VOLCANO['gene'][1:]


def test_volcano_axis_titles_are_the_defaults_and_can_be_changed():
    assert _axis_titles(i.volcano(VOLCANO, x='log2fc', y='p')) == ('log2 fold change', '−log10 P')
    relabelled = i.volcano(VOLCANO, x='log2fc', y='p').labels(x='fold')
    assert _axis_titles(relabelled)[0] == 'fold'


def test_volcano_has_a_key_for_the_significant_classes():
    chart = i.volcano(VOLCANO, x='log2fc', y='p')
    assert 'legend' in {step[1] for step in chart.plot()._steps}
    assert _step(chart, 'volcano')[3]['name'] == {'up': 'up', 'down': 'down'}


def test_volcano_names_missing_columns_and_needs_labels_for_highlight():
    with pytest.raises(KeyError, match='nope'):
        i.volcano(VOLCANO, x='nope', y='p')
    with pytest.raises(DiagramError):
        i.volcano(VOLCANO, x='log2fc', y='p', highlight=['G0']).compile()


# -- forest -----------------------------------------------------------------

@pytest.mark.parametrize('make', [
    lambda: quick.forest(FOREST, label='study', estimate='or', lower='lo', upper='hi'),
    lambda: quick.forest(FOREST, label='study', estimate='or', lower='lo', upper='hi', weight='w',
                         summary='sum', right=['ci', 'n'], log=True, measure='OR'),
])
def test_forest_builds_and_compiles(make):
    _clean(make())


def test_forest_rows_drop_missing_values():
    rows = [{**row} for row in FOREST]
    rows[1]['or'] = None
    chart = quick.forest(rows, label='study', estimate='or', lower='lo', upper='hi')
    assert [row['label'] for row in chart._forest[0]] == ['Ahmed 2019', 'Chen 2021', 'Overall']


def test_forest_marks_summaries_and_keeps_text_columns():
    chart = quick.forest(FOREST, label='study', estimate='or', lower='lo', upper='hi',
                         weight='w', summary='sum', right=['ci', 'n'])
    rows, options = chart._forest
    assert rows[-1].get('summary') is True and 'weight' not in rows[-1]
    assert rows[0]['weight'] == 18.2 and rows[0]['n'] == 812
    assert options['right'] == ('ci', 'n')


def test_forest_takes_its_axis_title_from_xlabel():
    chart = quick.forest(FOREST, label='study', estimate='or', lower='lo', upper='hi').labels(x='Odds ratio')
    _clean(chart)
    assert chart.plot().kwargs['label'] == 'Odds ratio'


def test_forest_names_missing_columns():
    with pytest.raises(KeyError, match='nope'):
        quick.forest(FOREST, label='study', estimate='nope', lower='lo', upper='hi')
    with pytest.raises(ValueError, match='label='):
        quick.forest(FOREST, estimate='or', lower='lo', upper='hi')


# -- names ------------------------------------------------------------------

def test_package_forest_is_still_the_diagram_function():
    diagram = i.forest([{'label': 'a', 'estimate': 0.8, 'low': 0.5, 'high': 1.2},
                        {'label': 'b', 'estimate': 1.1, 'low': 0.7, 'high': 1.6}], log=True)
    assert isinstance(diagram, Diagram)
    assert i.forest is not quick.forest


def test_survival_and_volcano_are_exported_and_listed():
    assert i.survival is quick.survival and i.volcano is quick.volcano
    assert {'survival', 'volcano'} <= set(i.__all__)
    assert {'survival', 'volcano', 'forest'} <= set(quick.__all__)
