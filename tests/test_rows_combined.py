"""ROWS_COMBINED: a bar that sums replicate rows, or a line through repeated x.

An agent passed three replicates per group to `i.bar(df, x='group', y='value')`:
each bar was the sum of its three rows and the check passed clean. `bar` now
defaults to `agg=None`, which still draws the sum but is reported unless the
author passed `agg='sum'`, and `line` reports any x that repeats in a series.
"""
import json

import pytest

import inklet as i
from inklet.cli import main
from inklet.quick import LayoutWarning


REPLICATES = {
    'group': ['ctrl'] * 3 + ['drug'] * 3,
    'value': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
}
UNIQUE = {'group': ['ctrl', 'drug', 'low'], 'value': [1.0, 2.0, 3.0]}
GROUPED = {
    'group': ['ctrl', 'ctrl', 'drug', 'drug'],
    'sex': ['f', 'm', 'f', 'm'],
    'value': [1.0, 2.0, 3.0, 4.0],
}


def _findings(chart):
    figure = chart.compile()
    return [d for d in figure.lint() if d.code == 'ROWS_COMBINED']


def test_replicate_bar_is_one_warning_and_save_warns(tmp_path):
    chart = i.bar(REPLICATES, x='group', y='value')
    found = _findings(chart)
    assert len(found) == 1
    assert found[0].severity == 'warning'
    assert found[0].message == (
        "bars of 'value' sum 3 rows per category ('ctrl' has 3); replicates read as one total")
    assert "agg='mean'" in found[0].hint and "agg='sum'" in found[0].hint
    with pytest.warns(LayoutWarning, match='ROWS_COMBINED'):
        chart.save(tmp_path / 'bars.svg')


def test_the_bar_finding_is_in_the_report_and_the_cli_json(tmp_path, capsys):
    assert 'ROWS_COMBINED' in i.bar(REPLICATES, x='group', y='value').report()
    script = tmp_path / 'replicates.py'
    script.write_text("import inklet as i\n"
                      f"chart = i.bar({REPLICATES!r}, x='group', y='value')\n")
    main(['check', str(script), '--json'])
    report = json.loads(capsys.readouterr().out)
    assert [d['code'] for d in report['diagnostics']] == ['ROWS_COMBINED']


def test_explicit_sum_says_the_sum_is_meant():
    assert _findings(i.bar(REPLICATES, x='group', y='value', agg='sum')) == []


def test_explicit_mean_records_nothing():
    assert _findings(i.bar(REPLICATES, x='group', y='value', agg='mean')) == []


def test_counting_rows_records_nothing():
    assert _findings(i.bar(REPLICATES, x='group')) == []


def test_unique_categories_record_nothing():
    assert _findings(i.bar(UNIQUE, x='group', y='value')) == []


def test_grouped_bar_with_one_row_per_group_records_nothing():
    assert _findings(i.bar(GROUPED, x='group', y='value', color='sex')) == []


def test_grouped_bar_names_the_group_that_repeats():
    table = {
        'group': ['ctrl', 'ctrl', 'ctrl', 'drug', 'drug', 'drug', 'drug'],
        'sex': ['f', 'f', 'f', 'f', 'm', 'm', 'f'],
        'value': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
    }
    found = _findings(i.bar(table, x='group', y='value', color='sex'))
    assert len(found) == 1
    # ctrl/f has three rows and drug/f two, so the worst is ctrl within group f.
    assert found[0].message.startswith(
        "bars of 'value' sum 3 rows per category ('ctrl' has 3 in group 'f')")


def test_rows_without_a_value_do_not_count():
    table = {'group': ['ctrl', 'ctrl', 'drug'], 'value': [1.0, None, 3.0]}
    assert _findings(i.bar(table, x='group', y='value')) == []


def test_line_with_repeated_x_is_a_finding(tmp_path):
    table = {'x': [1, 2, 2, 3], 'value': [1.0, 2.0, 3.0, 4.0]}
    chart = i.line(table, x='x', y='value')
    found = _findings(chart)
    assert len(found) == 1
    assert found[0].message == "line 'value' has 2 rows at x=2; the line zigzags through them"
    assert "scatter()" in found[0].hint
    with pytest.warns(LayoutWarning, match='zigzags'):
        chart.save(tmp_path / 'line.svg')


def test_line_with_unique_x_records_nothing():
    table = {'x': [1, 2, 3], 'value': [1.0, 2.0, 3.0]}
    assert _findings(i.line(table, x='x', y='value')) == []


def test_line_with_repeated_x_per_colour_group_names_the_group():
    found = _findings(i.line(REPLICATES | {'time': [0, 1, 1, 0, 1, 2]},
                             x='time', y='value', color='group'))
    assert len(found) == 1
    assert found[0].message == (
        "line 'value' in group 'ctrl' has 2 rows at x=1; the line zigzags through them")


def test_an_explicit_sum_bar_does_not_hide_a_repeated_x_line_on_the_same_chart():
    # The line shares the bar's categorical x axis, so its repeated x is a category.
    chart = i.bar(REPLICATES, x='group', y='value', agg='sum').line(
        {'g': ['ctrl', 'drug', 'ctrl'], 'v': [1.0, 2.0, 3.0]}, x='g', y='v')
    found = _findings(chart)
    assert len(found) == 1
    assert found[0].message == "line 'v' has 2 rows at x='ctrl'; the line zigzags through them"


def test_the_finding_survives_copying_the_chart_spec():
    chart = i.bar(REPLICATES, x='group', y='value')
    copied = chart.spec.copy()
    assert copied._findings == chart.spec._findings
    assert copied._findings is not chart.spec._findings



def test_a_line_in_row_order_may_pass_one_x_twice():
    loop = i.line({'x': [0, 1, 1, 0, 0], 'y': [0, 0, 1, 1, 0]}, x='x', y='y', sort=False)
    assert not [d for d in loop.compile().lint() if d.code == 'ROWS_COMBINED']
