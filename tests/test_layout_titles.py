"""A plot title too long for its cell is named as the cause of the layout failure.

A title is furniture: what it reaches past the data area is margin. One that
cannot fit used to make that margin grow every measurement pass until the
data width fell under the 5 mm floor, and the error then reported that
leftover ("leaves 3.3 mm for data"), which named neither the title nor any
real measurement.
"""
import re

import pytest

import inklet as i
from inklet.document import Document, LayoutError, plot_spec

LONG = ('Panel {k}: a very long descriptive panel title about the excess norm '
        'versus the shuffled control floor')


def _grid(title, scales=(1, 1, 1, 1)):
    charts = [i.line({'x': list(range(5)), 'y': [x * s for x in range(5)]}, x='x', y='y',
                     title=title.format(k=k))
              for k, s in enumerate(scales)]
    return (charts[0] | charts[1]) / (charts[2] | charts[3])


def _suggestion(error):
    found = re.search(r"for example '(.*)'\.$", str(error))
    assert found, str(error)
    return found.group(1).replace('\\n', '\n')


def test_a_title_wider_than_its_cell_is_named_with_both_widths():
    with pytest.raises(LayoutError) as caught:
        _grid(LONG).compile()
    message = str(caught.value)
    assert "title 'Panel 0: a very long" in message
    widths = re.search(r'is (\d+\.\d) mm wide, but the cell is only (\d+\.\d) mm wide', message)
    assert widths and float(widths.group(1)) > float(widths.group(2))
    # The old symptom, a data width the loop happened to stop at, is gone.
    assert 'for data after labels' not in message


def test_the_suggested_line_break_fits():
    with pytest.raises(LayoutError) as caught:
        _grid(LONG).compile()
    wrapped = _suggestion(caught.value)
    assert '\n' in wrapped
    figure = _grid(wrapped.replace('Panel 0', 'Panel {k}')).compile()
    assert not [d for d in figure.lint() if d.severity in ('error', 'warning')]


def test_a_title_that_starts_inside_the_cell_and_overruns_it():
    # The panel below has wide tick labels, which set the column's shared
    # left margin; the title starts at this panel's own labels, to the right
    # of the cell edge, so a title narrower than the cell can still overrun it.
    def chart(scale, title=None):
        return i.line({'x': list(range(5)), 'y': [x * scale for x in range(5)]}, x='x', y='y',
                      title=title)

    title = 'Excess norm versus shuffled control floor for every domain in the study and'
    top = chart(1, title)
    layout = (top | chart(1)) / (chart(1234567.0) | chart(1))
    with pytest.raises(LayoutError) as caught:
        layout.compile()
    message = str(caught.value)
    found = re.search(r"is (\d+\.\d) mm wide, but it starts (\d+\.\d) mm in from the cell's "
                      r"left edge.*leaves it (\d+\.\d) mm of the (\d+\.\d) mm cell", message)
    assert found, message
    width, start, room, cell = map(float, found.groups())
    assert room < width < cell and abs(room - (cell - start)) < .15
    top.title = _suggestion(caught.value)
    layout.compile()


def test_a_title_wider_than_the_data_but_not_the_cell_still_fits():
    figure = _grid('Panel {k}: excess norm versus the shuffled floor, per domain').compile()
    assert figure is not None


def test_a_long_facet_title_is_named_too():
    name = 'accuracy of the board-state probe on changed squares across every layer of every rung'
    rows = [{'x': x, 'y': x, 'm': m} for m in (name, 'loss', 'auc', 'norm') for x in range(5)]
    with pytest.raises(LayoutError, match=r"title 'accuracy of the board-state.*mm wide, but the cell"):
        i.line(rows, x='x', y='y', facet_col='m', facet_col_wrap=2).compile()


def test_no_room_for_data_lists_what_the_furniture_takes():
    doc = Document(width=60, height=14)
    doc.add('a', plot_spec().line([(0, 0), (1, 1)]).axes(x='time', y='v').title('Title'))
    with pytest.raises(LayoutError, match=r"cell 'a' leaves only .* for data after labels: of its "
                                          r".* mm, the furniture takes .* mm left, .* mm right, "
                                          r".* mm above and .* mm below\. Increase its size"):
        doc.compile()
