"""One-call defaults: lines break at gaps, blank labels are no labels, PNGs are print resolution."""
import pytest

import inklet as i


GAPPED = {'x': [0, 1, 2, 3, 4, 5], 'y': [1.0, 2.0, None, 4.0, 5.0, None]}


def _line_steps(chart):
    return [step for step in chart.plot()._steps if step[1] == 'line']


def test_a_gap_splits_the_line_into_runs():
    chart = i.line(GAPPED, x='x', y='y')
    runs = [step[2][0] for step in _line_steps(chart)]
    assert runs == [((0, 1.0), (1, 2.0)), ((3, 4.0), (4, 5.0))]


def test_split_runs_share_one_colour_and_only_the_first_is_named():
    chart = i.line(GAPPED, x='x', y='y', name='observed')
    steps = _line_steps(chart)
    assert len(steps) == 2
    assert steps[0][3]['color'] == steps[1][3]['color']
    assert steps[0][3]['name'] == 'observed'
    assert steps[1][3].get('name') is None
    named = [step for step in steps if step[3].get('name')]
    assert len(named) == 1


def test_split_series_in_colour_groups_keep_one_legend_entry_each():
    data = {
        'x': [0, 1, 2, 3, 0, 1, 2, 3],
        'y': [1.0, 2.0, None, 4.0, 2.0, None, 3.0, 4.0],
        'cond': ['ctrl'] * 4 + ['drug'] * 4,
    }
    chart = i.line(data, x='x', y='y', color='cond')
    steps = _line_steps(chart)
    # ctrl breaks into two runs, drug into two; each group is named once.
    assert [step[2][0] for step in steps] == [
        ((0, 1.0), (1, 2.0)), ((3, 4.0),), ((0, 2.0),), ((2, 3.0), (3, 4.0))]
    names = [step[3].get('name') for step in steps]
    assert names == ['ctrl', None, 'drug', None]
    assert steps[0][3]['color'] == steps[1][3]['color']
    assert steps[2][3]['color'] == steps[3][3]['color']
    assert steps[0][3]['color'] != steps[2][3]['color']


def test_bridge_keeps_one_line_across_the_gap():
    chart = i.line(GAPPED, x='x', y='y', gaps='bridge')
    steps = _line_steps(chart)
    assert len(steps) == 1
    assert steps[0][2][0] == ((0, 1.0), (1, 2.0), (3, 4.0), (4, 5.0))


def test_gaps_must_be_break_or_bridge():
    with pytest.raises(ValueError, match="gaps must be 'break' or 'bridge'"):
        i.line(GAPPED, x='x', y='y', gaps='skip')


def test_a_missing_error_breaks_the_band_too():
    data = {'x': [0, 1, 2, 3], 'y': [1.0, 2.0, 3.0, 4.0], 'e': [0.1, None, 0.1, 0.1]}
    chart = i.line(data, x='x', y='y', error_y='e')
    bands = [step for step in chart.plot()._steps if step[1] == 'band']
    assert len(bands) == 2
    assert list(bands[0][2][0]) == [0]
    assert list(bands[1][2][0]) == [2, 3]


def test_blank_labels_draw_no_leader_lines():
    data = {
        'x': [0, 1, 2, 3, 4, 5],
        'y': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        'name': ['alpha', '', '   ', None, float('nan'), 'omega'],
    }
    chart = i.scatter(data, x='x', y='y', text='name')
    (labelled,) = [step for step in chart.spec._steps if step[1] == 'label_points']
    points, labels = labelled[2]
    assert labels == ('alpha', 'omega')
    assert points == ((0, 1.0), (5, 6.0))


def test_blank_labels_with_a_colour_column_draw_no_leader_lines():
    data = {
        'x': [0, 1, 2],
        'y': [1.0, 2.0, 3.0],
        'g': ['a', 'a', 'b'],
        'name': ['', 'two', ' '],
    }
    chart = i.scatter(data, x='x', y='y', color='g', text='name')
    (labelled,) = [step for step in chart.spec._steps if step[1] == 'label_points']
    assert labelled[2][1] == ('two',)
    assert labelled[2][0] == ((1, 2.0),)


def test_png_is_print_resolution_by_default(tmp_path):
    pil = pytest.importorskip('PIL.Image')
    chart = i.line({'x': [0, 1, 2], 'y': [1, 2, 3]}, x='x', y='y')
    target = tmp_path / 'figure.png'
    chart.save(target)
    width, _ = pil.open(target).size
    assert abs(width - 89 / 25.4 * 300) <= 2


def test_png_dpi_can_be_overridden(tmp_path):
    pil = pytest.importorskip('PIL.Image')
    chart = i.line({'x': [0, 1, 2], 'y': [1, 2, 3]}, x='x', y='y')
    target = tmp_path / 'figure.png'
    chart.save(target, dpi=600)
    width, _ = pil.open(target).size
    assert abs(width - 89 / 25.4 * 600) <= 2


def test_slide_png_uses_slide_resolution(tmp_path):
    pil = pytest.importorskip('PIL.Image')
    chart = i.line({'x': [0, 1, 2], 'y': [1, 2, 3]}, x='x', y='y', width='slide')
    target = tmp_path / 'slide.png'
    chart.save(target)
    width, _ = pil.open(target).size
    assert abs(width - 254 / 25.4 * 150) <= 2


def test_vector_outputs_ignore_the_raster_resolution(tmp_path):
    chart = i.line({'x': [0, 1, 2], 'y': [1, 2, 3]}, x='x', y='y')
    chart.save(tmp_path / 'figure.svg', tmp_path / 'figure.pdf')
    figure = chart.compile()
    assert (tmp_path / 'figure.svg').read_text(encoding='utf-8') == figure.to_svg(
        text=figure.metadata['publication']['text'])
    assert (tmp_path / 'figure.pdf').read_bytes().startswith(b'%PDF')
