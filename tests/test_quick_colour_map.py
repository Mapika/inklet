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


BARS = [{'model': m, 'part': p, 'share': v} for m in ('A', 'B')
        for p, v in (('Top head', 0.9), ('Other heads', 0.05), ('MLP', 0.05))]
PARTS = {'Top head': '#0072b2', 'Other heads': '#7fb8d8', 'MLP': '#7a7a7a'}


def _bar_colours(chart, method='bars', **plotting):
    step = next(s for s in chart.plot(**plotting)._steps if s[1] == method)
    return dict(zip(step[3]['name'], step[3]['color']))


def test_grouped_bars_take_the_mapped_colours_as_given():
    chart = i.bar(BARS, x='model', y='share', color='part', palette=PARTS, style='scientific.nature')
    assert _bar_colours(chart) == PARTS
    assert all(c in chart.compile().to_svg() for c in PARTS.values())


def test_bars_in_a_layout_take_the_mapping_too():
    line = i.line([dict(x=0, y=0), dict(x=1, y=1)], x='x', y='y', style='scientific.nature')
    bars = i.bar(BARS, x='model', y='share', color='part', palette=PARTS, style='scientific.nature')
    layout = i.Layout('row', [line, bars], width='double', style='scientific.nature')
    assert _bar_colours(bars, **layout._plotting([line, bars])[id(bars)]) == PARTS
    svg = layout.compile().to_svg()
    assert all(c in svg for c in PARTS.values())


def test_averaged_bars_take_the_mapping():
    rows = BARS + [dict(r, share=r['share'] / 2) for r in BARS]
    chart = i.bar(rows, x='model', y='share', color='part', agg='mean', palette=PARTS)
    assert _bar_colours(chart, 'barplot') == PARTS


def test_unmapped_bars_keep_their_soft_palette_colours():
    from inklet.themes import mix
    chart = i.bar(BARS, x='model', y='share', color='part', palette={'MLP': '#7a7a7a'})
    colours = _bar_colours(chart)
    palette = [c for c in chart._profile().theme.palette if c != '#7a7a7a']
    paper = chart._profile().theme.paper
    assert colours['MLP'] == '#7a7a7a'
    assert colours['Top head'] == mix(palette[0], paper, 0.45)


def test_a_named_single_bar_takes_its_mapped_colour():
    chart = i.bar({'c': ['a', 'b'], 'v': [1, 2]}, x='c', y='v', name='MLP', palette=PARTS)
    assert next(k for _, m, _, k in chart.plot()._steps if m == 'bars')['color'] == '#7a7a7a'
