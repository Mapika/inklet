"""inklet.from_matplotlib: matplotlib figures redrawn as inklet charts."""
import warnings

import pytest

mpl = pytest.importorskip('matplotlib')
mpl.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

import inklet as i  # noqa: E402


@pytest.fixture(autouse=True)
def _close():
    yield
    plt.close('all')


def _steps(chart):
    return [(step[1], step[2], step[3]) for step in chart.spec._steps]


def _clean(figure):
    compiled = figure.compile()
    assert not [d for d in compiled.lint() if d.severity == 'error'], compiled.report()
    return compiled


def test_lines_bands_rules_labels_and_legend():
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    ax.plot([0, 1, 2], [1, 3, 2], label='signal')
    ax.plot([0, 1, 2], [2, 2, 3], '--', label='model')
    ax.fill_between([0, 1, 2], [0.5, 2.5, 1.5], [1.5, 3.5, 2.5], alpha=0.3)
    ax.axhline(2, color='k')
    ax.set_xlabel('Time / s')
    ax.set_ylabel('Signal')
    ax.set_title('Response')
    ax.legend()
    chart = i.from_matplotlib(fig)
    assert isinstance(chart, i.Chart) and chart.width == 'single'
    methods = [m for m, _, _ in _steps(chart)]
    assert methods.count('line') == 2 and 'band' in methods and 'hline' in methods
    assert chart.xlabel == 'Time / s' and chart.ylabel == 'Signal' and chart.title == 'Response'
    lines = [k for m, _, k in _steps(chart) if m == 'line']
    assert lines[0]['name'] == 'signal' and lines[1]['stroke_dash']
    _clean(chart)


def test_cycle_colours_become_palette_slots_and_explicit_colours_stay():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], label='a')
    ax.plot([0, 1], [1, 0], color='#c1121f', label='b')
    chart = i.from_matplotlib(fig)
    first, second = [k for m, _, k in _steps(chart) if m == 'line']
    assert first['color'] == '@series0' and second['color'] == '#c1121f'
    resolved = [k for _, m, _, k in chart.plot()._steps if m == 'line']
    assert resolved[0]['color'] == i.preset('scientific.modern').theme.palette[0]
    kept = i.from_matplotlib(fig, keep_colors=True)
    assert [k for m, _, k in _steps(kept) if m == 'line'][0]['color'] == '#1f77b4'


def test_scatter_with_values_gets_a_ramp_and_colorbar():
    fig, ax = plt.subplots()
    ax.scatter([0, 1, 2], [1, 2, 3], c=[0.1, 0.5, 0.9], cmap='viridis', s=16)
    chart = i.from_matplotlib(fig)
    (method, _, kwargs), colorbar = _steps(chart)[0], _steps(chart)[1]
    assert method == 'scatter' and kwargs['ramp'] == 'viridis' and len(kwargs['color']) == 3
    assert colorbar[0] == 'colorbar'
    assert kwargs['size'] == pytest.approx(4 * 25.4 / 72)
    _clean(chart)


def test_categorical_bars_keep_names_and_error_bars():
    fig, ax = plt.subplots()
    ax.bar(['control', 'treated'], [3, 5], yerr=[0.3, 0.5])
    chart = i.from_matplotlib(fig)
    methods = [m for m, _, _ in _steps(chart)]
    assert 'bars' in methods and 'errorbars' in methods
    errors = next(k for m, _, k in _steps(chart) if m == 'errorbars')
    assert errors['yerr'][1] == pytest.approx((0.5, 0.5))
    ticks = chart._tick_overrides['x']
    assert [ticks['format'](v) for v in ticks['ticks']] == ['control', 'treated']
    _clean(chart)


def test_histogram_bars_and_log_axes():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.5))
    axes[0].hist([1, 2, 2, 3, 3, 3], bins=3)
    axes[1].errorbar([1, 2, 3], [2, 3, 2.5], yerr=0.2, fmt='o-', label='mean')
    axes[1].set_xscale('log')
    axes[1].legend()
    layout = i.from_matplotlib(fig)
    assert isinstance(layout, i.Layout) and layout.width == 'double'
    first, second = layout.items
    assert [m for m, _, _ in _steps(first)] == ['bars']
    assert second.spec.options['x'] == 'log' and second._legend_explicit
    assert 'legend' in {step[1] for step in second.plot()._steps}
    _clean(layout)


def test_grid_of_axes_becomes_lettered_rows():
    fig, axes = plt.subplots(2, 2)
    for ax in axes.flat:
        ax.plot([0, 1], [0, 1])
    layout = i.from_matplotlib(fig)
    assert layout.direction == 'column' and all(len(row.items) == 2 for row in layout.items)
    svg = _clean(layout).to_svg(text='names')
    assert '>d<' in svg


def test_images_become_matrices():
    fig, ax = plt.subplots()
    image = ax.imshow([[0, 1, 2], [3, 4, 5]], cmap='magma')
    fig.colorbar(image)
    chart = i.from_matplotlib(fig)
    assert [m for m, _, _ in _steps(chart)] == ['matrix', 'colorbar']
    _clean(chart)


def test_unconverted_artists_are_reported():
    from matplotlib.patches import Circle
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.add_patch(Circle((0.5, 0.5), 0.1))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        chart = i.from_matplotlib(fig)
    assert any(issubclass(w.category, i.MatplotlibWarning) and 'Circle' in str(w.message)
               for w in caught)
    assert chart.skipped == ['Circle']


def test_markevery_and_single_axes_input():
    fig, ax = plt.subplots()
    ax.plot(range(10), range(10), 'o-', markevery=3)
    chart = i.from_matplotlib(ax)
    scatter = next(a for m, a, _ in _steps(chart) if m == 'scatter')
    assert len(scatter[0]) == 4


def test_rejects_things_that_are_not_figures():
    with pytest.raises(TypeError):
        i.from_matplotlib(object())
