"""palette= as a mapping: each series name drawn in the colour it is given,
in every panel and whatever order the series come in."""
import pytest

import inklet as i

ROWS = ([{'n': n, 'loss': 3 - n / 4, 'domain': 'chess'} for n in range(4)]
        + [{'n': n, 'loss': 2 - n / 5, 'domain': 'othello'} for n in range(4)]
        + [{'n': n, 'loss': 1 - n / 6, 'domain': 'dyck'} for n in range(4)])
COLOURS = {'chess': '#123456', 'othello': '#abcdef'}


def _series_colours(chart, method='line', **plotting):
    return {step[3].get('name'): step[3]['color'] for step in chart.plot(**plotting)._steps
            if step[1] == method and 'name' in step[3]}


def test_mapped_series_take_their_colours_and_others_the_palette():
    chart = i.line(ROWS, x='n', y='loss', color='domain', palette=COLOURS, style='scientific.nature')
    colours = _series_colours(chart)
    assert colours['chess'] == '#123456' and colours['othello'] == '#abcdef'
    assert colours['dyck'] in chart._profile().theme.palette
    assert colours['dyck'] not in COLOURS.values()


def test_a_mapping_holds_whatever_order_the_series_are_drawn_in():
    reverse = [r for r in ROWS if r['domain'] == 'othello'] + [r for r in ROWS if r['domain'] == 'chess']
    chart = i.scatter(reverse, x='n', y='loss', color='domain', palette=COLOURS)
    colours = _series_colours(chart, 'scatter')
    assert colours == {'othello': '#abcdef', 'chess': '#123456'}


def test_a_layout_mapping_colours_every_panel():
    a = i.line([r for r in ROWS if r['domain'] == 'othello'], x='n', y='loss', color='domain',
               style='scientific.nature')
    b = i.line(ROWS, x='n', y='loss', color='domain', style='scientific.nature')
    layout = (a | b).options(palette=COLOURS, style='scientific.nature')
    svg = layout.compile().to_svg()
    assert '#abcdef' in svg and '#123456' in svg
    plotting = layout._plotting([a, b])
    assert _series_colours(a, **plotting[id(a)])['othello'] == '#abcdef'
    assert _series_colours(b, **plotting[id(b)])['chess'] == '#123456'


def test_a_bad_colour_in_the_mapping_is_refused_at_the_call():
    with pytest.raises(ValueError):
        i.line(ROWS, x='n', y='loss', color='domain', palette={'chess': 'not a colour'})
