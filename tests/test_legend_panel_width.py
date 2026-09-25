"""Top and bottom legends may use the whole panel width, not only the data's."""

import pytest

import inklet as i

NAMES = ['specific', 'dimorphic', 'isomorphic']


def _panel(width=38, names=NAMES):
    p = i.panel(width, 20, x=(0, 60), y=['102', '79', '81', '116'])
    p.bars(['102', '79', '81', '116'], [[51, 43, 18, 40], [1, 0, 7, 6], [0, 0, 1, 3]],
           stacked=True, orient='h', name=names)
    p.axes(x='cell types', y='cluster identifier')
    return p


def _legend(panel):
    built = panel.build()
    places = i.resolve(built)
    legend = next(p for p in places.values() if p.diagram.kind == 'legend')
    # Names on one line differ in ascenders, so rows are told apart by their
    # centres, which move by a whole line from one row to the next.
    centres = sorted(p.bbox.center.y for p in places.values()
                     if p.diagram.kind == 'label' and p.bbox.y0 >= legend.bbox.y0 - 1e-6
                     and p.bbox.y1 <= legend.bbox.y1 + 1e-6)
    rows = 1 + sum(b - a > 1 for a, b in zip(centres, centres[1:]))
    return legend.bbox, rows, i.plot_area(built), built.bbox


@pytest.mark.parametrize('side', ['top', 'bottom'])
def test_a_key_wider_than_the_data_spans_the_panel_from_its_left_edge(side):
    box, rows, area, whole = _legend(_panel().legend(side=side))
    # The three names fit on one line across the panel, not across the data.
    assert box.width > area.width
    assert rows == 1
    # Left-aligned with the outer edge of the furniture left of the data, and
    # no wider than the panel was without it.
    plain = _panel().build()
    assert box.x0 == pytest.approx(whole.x0, abs=1e-6)
    assert area.x0 - whole.x0 == pytest.approx(i.plot_area(plain).x0 - plain.bbox.x0, abs=1e-6)
    assert whole.width == pytest.approx(plain.bbox.width, abs=1e-6)


def test_a_key_that_fits_the_data_stays_centred_on_it():
    box, rows, area, _ = _legend(_panel(width=60).legend(side='top'))
    assert rows == 1
    assert box.center.x == pytest.approx(area.center.x, abs=1e-6)


def test_a_key_too_wide_even_for_the_panel_still_wraps():
    long = ['first long series', 'second long series', 'third long series']
    box, rows, area, _ = _legend(_panel(names=long).legend(side='top'))
    assert rows > 1


def test_explicit_widths_and_columns_are_respected():
    box, rows, area, _ = _legend(_panel().legend(side='top', columns=1))
    assert rows == 3
    assert box.center.x == pytest.approx(area.center.x, abs=1e-6)
    box, rows, area, _ = _legend(_panel().legend(side='top', max_width=17))
    assert rows == 3


def test_an_inside_key_moved_above_a_crowded_plot_uses_the_panel_width():
    from inklet.document.spec import _inside_legend
    panel = _panel()
    _inside_legend(panel, {})
    box, rows, area, whole = _legend(panel)
    assert box.y1 <= area.y0 + 1e-6
    assert rows == 1 and box.x0 == pytest.approx(whole.x0, abs=1e-6)
