"""Overlaid series take the next palette slot; a layout's lone series keeps its key.

Colours are read from `plot()`, where palette tokens are already resolved to
hex, so each assertion compares the colour a reader would see.
"""
import inklet as i
from inklet.themes import mix

MONTHS = ['Jan', 'Feb', 'Mar']


def _colour(chart, method, index=0):
    steps = [step for step in chart.plot()._steps if step[1] == method]
    return steps[index][3]['color']


def _palette(chart):
    return chart._profile().theme.palette


def _soft(chart, slot):
    """What a bar takes from palette `slot`: the palette colour softened into the paper."""
    theme = chart._profile().theme
    return mix(theme.palette[slot], theme.paper, 0.45)


def test_bar_then_line_overlay_takes_the_next_slot():
    chart = i.bar({'m': MONTHS, 'sales': [3, 5, 4]}, x='m', y='sales')
    chart.line({'m': MONTHS, 'target': [4, 4, 4]}, x='m', y='target')
    palette = _palette(chart)
    assert _colour(chart, 'bars') == _soft(chart, 0)
    assert _colour(chart, 'line') == palette[1]
    assert _colour(chart, 'line') != _colour(chart, 'bars')


def test_unnamed_line_then_bar_overlay_also_differs():
    chart = i.line({'m': MONTHS, 'v': [1, 2, 3]}, x='m', y='v')
    chart.bar({'m': MONTHS, 'sales': [3, 5, 4]}, x='m', y='sales')
    assert _colour(chart, 'line') == _palette(chart)[0]
    assert _colour(chart, 'bars') == _soft(chart, 1)


def test_mixed_overlays_each_take_their_own_slot():
    chart = i.bar({'m': MONTHS, 'sales': [3, 5, 4]}, x='m', y='sales')
    chart.scatter({'m': MONTHS, 'pts': [2, 2, 2]}, x='m', y='pts')
    chart.area({'m': MONTHS, 'band': [1, 1, 1]}, x='m', y='band')
    palette = _palette(chart)
    assert _colour(chart, 'bars') == _soft(chart, 0)
    assert _colour(chart, 'scatter') == palette[1]
    assert _colour(chart, 'fill_between') == palette[2]


def test_a_line_and_its_markers_share_one_slot_when_overlaid():
    chart = i.bar({'m': MONTHS, 'sales': [3, 5, 4]}, x='m', y='sales')
    chart.line({'m': MONTHS, 'target': [4, 4, 4]}, x='m', y='target', markers=True)
    line = _colour(chart, 'line')
    assert line == _palette(chart)[1]
    assert _colour(chart, 'scatter') == line


def test_single_bar_still_takes_slot_zero():
    chart = i.bar({'m': MONTHS, 'sales': [3, 5, 4]}, x='m', y='sales')
    assert _colour(chart, 'bars') == _soft(chart, 0)


def test_single_line_still_takes_slot_zero():
    chart = i.line({'m': MONTHS, 'v': [1, 2, 3]}, x='m', y='v')
    assert _colour(chart, 'line') == _palette(chart)[0]


def test_a_literal_colour_does_not_use_up_a_slot():
    chart = i.bar({'m': MONTHS, 'sales': [3, 5, 4]}, x='m', y='sales', color='#c00000')
    chart.line({'m': MONTHS, 'v': [1, 2, 3]}, x='m', y='v')
    assert _colour(chart, 'line') == _palette(chart)[0]


def test_grouped_bars_then_named_line_do_not_share_a_slot():
    rows = {'m': MONTHS * 2, 'g': ['a'] * 3 + ['b'] * 3, 'v': [1, 2, 3, 2, 3, 4]}
    chart = i.bar(rows, x='m', y='v', color='g')
    chart.line({'m': MONTHS, 'target': [2, 2, 2]}, x='m', y='target')
    palette = _palette(chart)
    assert _colour(chart, 'line') == palette[2]


def _layout_panels():
    rows = {'x': [1, 2, 3, 4, 5, 6], 'y': [2, 3, 5, 4, 6, 7],
            'group': ['control'] * 3 + ['treated'] * 3}
    both = i.scatter(rows, x='x', y='y', color='group')
    lone = i.scatter({'x': [1, 2, 3], 'y': [4, 5, 3], 'group': ['treated'] * 3},
                     x='x', y='y', color='group')
    return both, lone, both | lone


def _keys(chart, layout):
    """The step names of `chart` plotted the way `layout` plots it."""
    plotting = layout._plotting(list(layout.charts()))[id(chart)]
    return [step[1] for step in chart.plot(**plotting)._steps]


def test_a_layout_panel_with_one_shared_name_gets_its_own_key():
    _, lone, layout = _layout_panels()
    assert 'legend' in _keys(lone, layout)


def test_a_lone_name_not_drawn_elsewhere_keeps_no_key():
    solo = i.scatter({'x': [1, 2, 3], 'y': [4, 5, 3], 'group': ['treated'] * 3},
                     x='x', y='y', color='group')
    other = i.scatter({'x': [1, 2], 'y': [1, 2], 'group': ['control'] * 2}, x='x', y='y', color='group')
    layout = solo | other
    assert 'legend' not in _keys(solo, layout)
