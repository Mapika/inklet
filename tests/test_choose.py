import pytest
import inklet as i


def keyed(side=None):
    p = i.plot_spec(height=20)
    p.line([(0, 0), (1, 1)], name='alpha series').line([(0, 1), (1, 0)], name='beta series')
    return p.legend(side=side) if side else p.legend(corner='best')


def page(item, **options):
    doc = i.document(width=100, columns=2, gap=4, margin=0, **options)
    doc.add('plot', item)
    doc.add('note', i.text('note'), row=0, column=1)
    return doc.compile()


def test_a_choice_keeps_the_alternative_that_gives_the_shortest_page():
    below, inside = page(keyed('bottom')), page(keyed())
    assert inside.metadata['height_mm'] < below.metadata['height_mm']-1
    chosen = page(i.choose(below=keyed('bottom'), inside=keyed()))
    assert chosen.metadata['height_mm'] == pytest.approx(inside.metadata['height_mm'])
    assert chosen.metadata['layout']['choices'] == {'plot': 'inside'}
    assert chosen.layout_report().splitlines()[-2:] == ['chosen alternatives', '  plot: inside']


def test_equal_alternatives_keep_the_first_and_unfit_ones_are_skipped():
    tie = page(i.choose(keyed(), keyed()))
    assert tie.metadata['layout']['choices'] == {'plot': '1'}
    wide = i.component(i.box, 'x', width=200)
    fits = page(i.choose(wide, keyed()))
    assert fits.metadata['layout']['choices'] == {'plot': '2'}
    with pytest.raises(i.LayoutError):
        page(i.choose(wide, i.component(i.box, 'y', width=150)))


def test_choose_needs_two_alternatives_and_nested_grids_choose_too():
    with pytest.raises(ValueError):
        i.choose(keyed())
    with pytest.raises(TypeError):
        i.choose(i.choose(keyed(), keyed()), keyed())
    group = i.subfigure(width=100, columns=2, gap=4, stretch=False)
    group.add('plot', i.choose(keyed('bottom'), keyed()))
    group.add('note', i.text('note'), row=0, column=1)
    doc = i.document(width=100, margin=0)
    doc.add('group', group)
    assert doc.compile().metadata['height_mm'] == pytest.approx(page(keyed()).metadata['height_mm'])
