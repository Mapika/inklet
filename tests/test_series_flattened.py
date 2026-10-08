"""SERIES_FLATTENED: a series squashed flat by a taller one on the same axis.

A usability-test agent plotted `count` (0..5000) and `ratio` (0.2..0.9) on one
axis. `ratio` became a line along the floor and `inklet check` was clean. The
panel now records each series' extent (`plot/series_span.py`) and the rule
reports a named series that spans under 3% of the plot height beside one that
spans over 30%, on the same y axis, when its own values really change.
"""

import re

import inklet as i

T = list(range(10))
COUNT = [0, 500, 1200, 2100, 2900, 3400, 4100, 4600, 4900, 5000]
RATIO = [0.2, 0.3, 0.25, 0.5, 0.4, 0.6, 0.55, 0.8, 0.7, 0.9]
DATA = {'t': T, 'count': COUNT, 'ratio': RATIO}


def flattened(node):
    return [d for d in i.lint(node, page=node.bbox) if d.code == 'SERIES_FLATTENED']


def flattened_chart(chart):
    return [d for d in chart.compile().lint() if d.code == 'SERIES_FLATTENED']


def _panel(*series, y=(0, 5000)):
    p = i.plot.panel(60, 40, x=(0, 9), y=y)
    for name, values in series:
        p.line(list(zip(T, values)), name=name)
    return p


def test_quick_chart_flags_the_ratio_squashed_by_the_count():
    (finding,) = flattened_chart(i.line(DATA, x='t', y=['count', 'ratio']))
    assert finding.severity == 'warning'
    assert finding.message.startswith("series 'ratio' spans under 1% of the plot height")
    assert re.search(r"next to 'count' \(\d+%\); its changes are invisible", finding.message)
    assert finding.message.endswith('its changes are invisible')
    assert 'secondary_y=True' in finding.hint
    assert 'Panel.twin_y' in finding.hint
    assert 'log scale' in finding.hint


def test_two_comparable_series_are_silent():
    data = {'t': T, 'a': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'b': [2, 3, 2, 4, 3, 5, 4, 6, 5, 7]}
    assert flattened_chart(i.line(data, x='t', y=['a', 'b'])) == []


def test_a_constant_series_is_silent():
    data = {'t': T, 'count': COUNT, 'k': [7.0] * 10}
    assert flattened_chart(i.line(data, x='t', y=['count', 'k'])) == []


def test_secondary_y_fixes_it_and_is_silent():
    assert flattened_chart(i.line(DATA, x='t', y=['count', 'ratio'],
                                  secondary_y='ratio')) == []


def test_a_single_series_is_silent():
    assert flattened_chart(i.line(DATA, x='t', y='count')) == []


def test_panel_level_flags_a_squashed_series():
    p = _panel(('count', COUNT), ('ratio', RATIO))
    (finding,) = flattened(p.build())
    assert finding.targets == (p.build().id,)
    assert "'ratio'" in finding.message and "'count'" in finding.message


def test_a_scatter_group_squashed_by_a_line_is_flagged():
    p = i.plot.panel(60, 40, x=(0, 9), y=(0, 5000))
    p.line(list(zip(T, COUNT)), name='count')
    p.scatter(list(zip(T, RATIO)), name='ratio')
    (finding,) = flattened(p.build())
    assert "series 'ratio'" in finding.message


def test_a_twin_axis_series_is_measured_against_its_own_axis():
    p = i.plot.panel(60, 40, x=(0, 9), y=(0, 5000))
    p.line(list(zip(T, COUNT)), name='count')
    p.twin_y((0, 1)).line(list(zip(T, RATIO)), name='ratio')
    assert flattened(p.build()) == []


def test_a_lone_series_on_a_twin_axis_is_silent_whatever_the_scale():
    # Its own axis holds nothing that could squash it, so it is judged alone,
    # as a single series is anywhere.
    p = i.plot.panel(60, 40, x=(0, 9), y=(0, 5000))
    p.line(list(zip(T, COUNT)), name='count')
    p.twin_y((0, 5000)).line(list(zip(T, RATIO)), name='ratio')
    assert flattened(p.build()) == []


def test_a_log_axis_makes_the_small_series_visible():
    p = i.plot.panel(60, 40, x=(0, 9), y=i.log((0.1, 5000)))
    p.line(list(zip(T, [c or 10 for c in COUNT])), name='count')
    p.line(list(zip(T, RATIO)), name='ratio')
    assert flattened(p.build()) == []


def test_a_series_varying_by_less_than_one_percent_of_its_mean_is_silent():
    noise = [1000.0, 1000.5, 1000.2, 1000.4, 1000.1, 1000.3, 1000.5, 1000.0, 1000.2, 1000.4]
    p = _panel(('count', COUNT), ('noise', noise))
    assert flattened(p.build()) == []


def test_an_unnamed_big_series_still_squashes_a_named_one():
    p = i.plot.panel(60, 40, x=(0, 9), y=(0, 5000))
    p.line(list(zip(T, COUNT)))
    p.line(list(zip(T, RATIO)), name='ratio')
    (finding,) = flattened(p.build())
    assert 'an unnamed series' in finding.message


def test_a_lettered_panel_reports_once_not_once_per_wrapper():
    from inklet.draw.annotate import letters

    node = letters([_panel(('count', COUNT), ('ratio', RATIO)).build()])[0]
    assert len(flattened(node)) == 1


def test_a_panel_with_no_series_publishes_no_span_note():
    node = i.plot.panel(60, 40, x=(0, 9), y=(0, 5000)).build()
    assert 'series_spans' not in node.notes
