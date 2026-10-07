"""Big data in one call: a scatter panel past 20,000 points is one raster image of
its markers, a long line thins itself, and each default has an override."""
import math
import time

import pytest

import inklet as i
from inklet.quick import _RASTER_POINTS


def _cloud(count, groups=1):
    """A table of `count` points split over `groups` colours, without numpy."""
    xs = [math.sin(k * 0.37) * 10 for k in range(count)]
    ys = [math.cos(k * 0.11) * 10 + math.sin(k) for k in range(count)]
    labels = [f'g{k % groups}' for k in range(count)]
    return {'x': xs, 'y': ys, 'group': labels}


def _steps(chart, method):
    return [step for step in chart.plot()._steps if step[1] == method]


def _raster_flags(chart):
    return [step[3]['raster'] for step in _steps(chart, 'scatter')]


def test_a_panel_past_the_threshold_is_rasterised():
    chart = i.scatter(_cloud(_RASTER_POINTS + 1), x='x', y='y')
    assert _raster_flags(chart) == [True]


def test_a_panel_at_the_threshold_stays_vector():
    chart = i.scatter(_cloud(_RASTER_POINTS), x='x', y='y')
    assert _raster_flags(chart) == [False]


def test_the_threshold_counts_the_whole_panel_not_each_group():
    half = _RASTER_POINTS // 2 + 1
    together = i.scatter(_cloud(2 * half, groups=2), x='x', y='y', color='group')
    # Two groups of 10,001 are 20,002 points on one panel: both layers raster together.
    assert _raster_flags(together) == [True, True]
    apart = i.scatter(_cloud(2 * (half - 1), groups=2), x='x', y='y', color='group')
    assert _raster_flags(apart) == [False, False]


def test_a_small_panel_is_vector_and_records_its_dpi_only_when_rasterised():
    chart = i.scatter(_cloud(200), x='x', y='y')
    step = _steps(chart, 'scatter')[0]
    assert step[3]['raster'] is False
    assert 'dpi' not in step[3]


def test_raster_true_overrides_a_small_panel():
    chart = i.scatter(_cloud(50), x='x', y='y', raster=True)
    assert _raster_flags(chart) == [True]


def test_raster_false_overrides_a_big_panel():
    chart = i.scatter(_cloud(_RASTER_POINTS + 5000), x='x', y='y', raster=False)
    assert _raster_flags(chart) == [False]


def test_raster_is_refused_unless_none_true_or_false():
    with pytest.raises(ValueError, match='raster='):
        i.scatter(_cloud(10), x='x', y='y', raster='yes')


def test_the_raster_dpi_is_the_presets():
    print_chart = i.scatter(_cloud(50), x='x', y='y', raster=True)
    assert _steps(print_chart, 'scatter')[0][3]['dpi'] == 300
    slide = i.scatter(_cloud(50), x='x', y='y', raster=True, width='slide')
    assert _steps(slide, 'scatter')[0][3]['dpi'] == 150


def test_an_explicit_dpi_wins_over_the_preset():
    chart = i.scatter(_cloud(50), x='x', y='y', raster=True, dpi=600)
    assert _steps(chart, 'scatter')[0][3]['dpi'] == 600


def test_dashed_outlines_stay_vector_even_past_the_threshold():
    # A raster cannot draw dashed outlines, so the default must not pick one.
    chart = i.scatter(_cloud(_RASTER_POINTS + 1), x='x', y='y', stroke_dash=(2.0, 1.0))
    assert _raster_flags(chart) == [False]
    chart.compile()


def test_a_rasterised_panel_is_much_smaller_as_svg_and_stays_a_scatter_layer():
    cloud = _cloud(30_000)
    vector = i.scatter(cloud, x='x', y='y', raster=False).to_svg()
    raster = i.scatter(cloud, x='x', y='y', raster=True).to_svg()
    assert len(raster) * 4 < len(vector)
    # Axes stay vector text, so the rasterised figure still has its tick labels.
    assert '<image' in raster and '<image' not in vector


def test_a_long_line_is_thinned_by_default():
    count = 60_000
    xs = [k / 100 for k in range(count)]
    ys = [math.sin(x) for x in xs]
    chart = i.line(x=xs, y=ys)
    step = _steps(chart, 'line')[0]
    assert step[3]['simplify'] == 0.02
    compiled = chart.compile()
    notes = [n.notes['line_simplification'] for n in compiled.root.walk()
             if 'line_simplification' in n.notes]
    assert notes and notes[0]['output_points'] < count // 10
    assert notes[0]['input_points'] == count


def test_line_markers_follow_the_same_raster_rule():
    count = _RASTER_POINTS + 1
    xs = list(range(count))
    ys = [math.sin(k / 50) for k in range(count)]
    chart = i.line(x=xs, y=ys, markers=True)
    assert _raster_flags(chart) == [True]


def test_a_short_line_keeps_every_point_by_default():
    chart = i.line(x=list(range(200)), y=[float(k % 7) for k in range(200)])
    assert _steps(chart, 'line')[0][3]['simplify'] is None


def test_the_auto_limit_follows_the_chart_width():
    # 40 points per mm: a 89 mm single column thins past about 3,560 points, a 183 mm double past 7,320.
    count = 4000
    xs, ys = list(range(count)), [float(k % 3) for k in range(count)]
    assert _steps(i.line(x=xs, y=ys), 'line')[0][3]['simplify'] == 0.02
    assert _steps(i.line(x=xs, y=ys, width='double'), 'line')[0][3]['simplify'] is None


def test_simplify_none_or_false_keeps_every_point():
    xs = list(range(40_000))
    ys = [math.sin(k / 50) for k in range(40_000)]
    for choice in (None, False):
        assert _steps(i.line(x=xs, y=ys, simplify=choice), 'line')[0][3]['simplify'] is None


def test_an_explicit_tolerance_is_used_as_given():
    xs = list(range(40_000))
    ys = [math.sin(k / 50) for k in range(40_000)]
    assert _steps(i.line(x=xs, y=ys, simplify=0.05), 'line')[0][3]['simplify'] == 0.05


def test_a_smooth_line_is_never_thinned():
    # Panel.line draws smooth lines as curves, which simplify refuses.
    xs = list(range(5000))
    ys = [math.sin(k / 50) for k in range(5000)]
    chart = i.line(x=xs, y=ys, smooth=0.5)
    assert _steps(chart, 'line')[0][3]['simplify'] is None
    chart.compile()


@pytest.mark.parametrize('bad', ['fast', True])
def test_an_unknown_simplify_is_refused_at_the_call(bad):
    with pytest.raises(ValueError, match='simplify'):
        i.line(x=[1, 2, 3], y=[1, 2, 3], simplify=bad)


@pytest.mark.slow
def test_a_100k_point_scatter_compiles_in_a_generous_time():
    # A bound with room to spare: it catches a regression to minutes, not a slow CI box.
    chart = i.scatter(_cloud(100_000, groups=2), x='x', y='y', color='group')
    start = time.perf_counter()
    chart.compile()
    assert time.perf_counter() - start < 10
