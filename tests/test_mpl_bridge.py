"""inklet.from_matplotlib: matplotlib figures redrawn as inklet charts."""
import warnings

import numpy as np
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


def _converted(figure):
    """(chart or layout, the MatplotlibWarning messages raised converting it)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result = i.from_matplotlib(figure)
    return result, [str(w.message) for w in caught if issubclass(w.category, i.MatplotlibWarning)]


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


def _rows_of(layout):
    columns, cells = layout._grid()
    return columns, sorted({row for _, row, _, _, _ in cells})


def test_grid_of_axes_keeps_its_two_columns_and_two_rows():
    fig, axes = plt.subplots(2, 2)
    for ax in axes.flat:
        ax.plot([0, 1], [0, 1])
    layout = i.from_matplotlib(fig)
    assert layout.direction == 'grid' and layout.columns == 2 and len(layout.items) == 4
    assert _rows_of(layout) == (2, [0, 1])
    svg = _clean(layout).to_svg(text='names')
    assert '>d<' in svg


@pytest.mark.parametrize('panel', [(0, 0), (1, 1)])
def test_colourbar_beside_one_panel_keeps_the_grid(panel):
    # fig.colorbar(ax=) gives the parent panel a grid of its own, so its row
    # numbers do not match the figure's; the bottom-right one used to come out 3+1.
    fig, axes = plt.subplots(2, 2)
    for ax in axes.flat:
        ax.plot([0, 1], [0, 1])
    image = axes[panel].imshow([[0, 1], [2, 3]])
    fig.colorbar(image, ax=axes[panel])
    layout = i.from_matplotlib(fig)
    assert _rows_of(layout) == (2, [0, 1]) and len(layout.items) == 4
    from inklet.mpl import _is_colorbar, _rows
    panels = [a for a in fig.get_axes() if not _is_colorbar(a)]
    assert [len(row) for row in _rows(panels)] == [2, 2]


def test_rows_of_unequal_length_keep_their_rows():
    fig, axes = plt.subplots(2, 2)
    for ax in axes.flat:
        ax.plot([0, 1], [0, 1])
    fig.delaxes(axes[1, 1])
    layout = i.from_matplotlib(fig)
    assert layout.direction == 'column' and len(layout.items) == 2
    top, bottom = layout.items
    assert isinstance(top, i.Layout) and len(top.items) == 2
    assert isinstance(bottom, i.Chart)


def test_twin_axes_are_not_drawn_as_a_second_panel():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.twinx().plot([0, 1], [1, 5])
    chart, messages = _converted(fig)
    assert isinstance(chart, i.Chart)
    assert any('twin axes' in m for m in messages)


def test_images_become_matrices():
    fig, ax = plt.subplots()
    image = ax.imshow([[0, 1, 2], [3, 4, 5]], cmap='magma')
    fig.colorbar(image)
    chart = i.from_matplotlib(fig)
    assert [m for m, _, _ in _steps(chart)] == ['matrix', 'colorbar']
    _clean(chart)


def test_image_rows_run_top_down_on_an_inverted_axis():
    # imshow's default: row 0 is at the top of an inverted y axis. The bridge keeps
    # that axis inverted, so the rows go in as matplotlib placed them.
    array = [[0, 1, 2], [3, 4, 5]]
    fig, ax = plt.subplots()
    ax.imshow(array, cmap='magma')
    chart, _ = _converted(fig)
    assert chart.spec.options['y'] == (1.5, -0.5)
    _, (rows,), matrix = next(step for step in _steps(chart) if step[0] == 'matrix')
    assert [list(map(float, row)) for row in rows] == [[0, 1, 2], [3, 4, 5]]
    assert tuple(matrix['y']) == (0.0, 1.0) and tuple(matrix['x']) == (0.0, 1.0, 2.0)


def test_inverted_axis_is_kept_even_when_autoscaled():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 2])
    ax.invert_yaxis()
    chart, _ = _converted(fig)
    assert chart.spec.options['y'] == ax.get_ylim()


def test_images_are_drawn_under_the_marks_over_them():
    fig, ax = plt.subplots()
    ax.imshow([[0, 1], [2, 3]])
    ax.plot([0, 1], [0, 1])
    chart, _ = _converted(fig)
    methods = [m for m, _, _ in _steps(chart)]
    assert methods.index('matrix') < methods.index('line')


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


def test_bars_keep_their_own_colours():
    fig, ax = plt.subplots()
    ax.bar(['a', 'b', 'c'], [1, 2, 3], color=['red', 'green', 'blue'])
    chart, messages = _converted(fig)
    assert messages == []
    resolved = next(k for _, m, _, k in chart.plot()._steps if m == 'bars')
    assert list(resolved['bar_colors']) == ['#ff0000', '#008000', '#0000ff']
    _clean(chart)


def test_bars_of_one_colour_and_transparency_keep_one_colour():
    fig, ax = plt.subplots()
    ax.bar(['a', 'b'], [1, 2], color='C2', alpha=0.4)
    chart, _ = _converted(fig)
    bars = next(k for m, _, k in _steps(chart) if m == 'bars')
    assert bars['color'] == '@series2' and 'bar_colors' not in bars
    assert bars['opacity'] == pytest.approx(0.4)


@pytest.mark.parametrize('how', ['label', 'set_label'])
def test_colourbar_label_becomes_the_colourbar_title(how):
    fig, ax = plt.subplots()
    image = ax.imshow([[0, 1], [2, 3]])
    if how == 'label':
        fig.colorbar(image, label='r')
    else:
        bar = fig.colorbar(image)
        bar.set_label('r')
    chart, messages = _converted(fig)
    assert messages == []
    assert next(k for m, _, k in _steps(chart) if m == 'colorbar')['title'] == 'r'
    _clean(chart)


def test_scatter_colourbar_label_becomes_its_title():
    fig, ax = plt.subplots()
    points = ax.scatter([0, 1, 2], [1, 2, 3], c=[0.1, 0.5, 0.9])
    fig.colorbar(points, label='density')
    chart, _ = _converted(fig)
    assert next(k for m, _, k in _steps(chart) if m == 'colorbar')['title'] == 'density'


def test_hatched_bars_are_reported():
    fig, ax = plt.subplots()
    ax.bar(['a', 'b'], [1, 2], hatch='//')
    _, messages = _converted(fig)
    assert any("hatch '//'" in m for m in messages), messages


def _figure(draw):
    fig, ax = plt.subplots()
    draw(ax, fig)
    return fig


def _labelled_line(ax):
    ax.plot([0, 1], [0, 1], label='a')


# Each property the bridge does not carry, the figure that has it, and the words
# its warning must use. Every one of them used to be dropped silently.
UNCONVERTED = {
    'bar outline': (lambda ax, fig: ax.bar(['a', 'b'], [1, 2], edgecolor='k'), 'outlines'),
    'unfilled bars': (lambda ax, fig: ax.bar(['a', 'b'], [1, 2], color='none'), 'no fill'),
    'colour image': (lambda ax, fig: ax.imshow(np.zeros((2, 2, 3))), 'colour image'),
    'log colour scale': (lambda ax, fig: ax.imshow(np.arange(1, 5).reshape(2, 2),
                                                   norm=mpl.colors.LogNorm()), 'LogNorm'),
    'colour map': (lambda ax, fig: ax.imshow([[0, 1], [2, 3]], cmap='cubehelix'),
                   "'cubehelix'"),
    'marker shape': (lambda ax, fig: ax.plot([0, 1], [0, 1], marker='*', linestyle='none'),
                     "marker '*'"),
    'marker outline': (lambda ax, fig: ax.scatter([0, 1], [0, 1], color='C0', edgecolors='k'),
                       'outlines'),
    'line drawstyle': (lambda ax, fig: ax.plot([0, 1, 2], [0, 1, 0], drawstyle='steps-mid'),
                       "'steps-mid'"),
    'figure suptitle': (lambda ax, fig: (_labelled_line(ax), fig.suptitle('Experiment 3')),
                        "figure text 'Experiment 3'"),
    'figure legend': (lambda ax, fig: (_labelled_line(ax), fig.legend()), 'figure legend'),
    'legend title': (lambda ax, fig: (_labelled_line(ax), ax.legend(title='Group')),
                     "legend title 'Group'"),
    'legend labels by hand': (lambda ax, fig: (_labelled_line(ax), ax.legend(['renamed'])),
                              'given by hand'),
    'inset axes': (lambda ax, fig: ax.inset_axes([0.6, 0.6, 0.3, 0.3]), 'inset axes'),
    'aspect ratio': (lambda ax, fig: (_labelled_line(ax), ax.set_aspect('equal')), 'set_aspect'),
    'rotated text': (lambda ax, fig: ax.text(0.5, 0.5, 'label', rotation=90), 'rotated 90'),
    'text in axes coordinates': (lambda ax, fig: ax.text(0.5, 0.5, 'label',
                                                         transform=ax.transAxes),
                                 'axes coordinates'),
    'annotation in axes coordinates': (
        lambda ax, fig: ax.annotate('corner', xy=(0.9, 0.9), xycoords='axes fraction',
                                    xytext=(0.5, 0.5)), 'not data'),
    'dashed lines': (lambda ax, fig: ax.hlines([1], 0, 1, linestyles='dashed'), 'dashed'),
    'labelled lines in several colours': (
        lambda ax, fig: ax.hlines([1, 2], 0, 1, colors=['r', 'g'], label='h'), 'label dropped'),
}


@pytest.mark.parametrize('case', sorted(UNCONVERTED))
def test_properties_not_carried_are_listed_in_the_warning(case):
    draw, expected = UNCONVERTED[case]
    _, messages = _converted(_figure(draw))
    assert any(expected in m for m in messages), messages


def test_rules_and_axes_coordinate_artists_are_not_taken_for_data():
    # With limits of exactly 0 to 1, matplotlib's transforms compare equal (the
    # matrices agree), so only identity tells an axes-fraction artist from a data one.
    fig, ax = plt.subplots()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axhline(0.5)
    ax.axvline(0.25)
    chart, messages = _converted(fig)
    assert messages == []
    assert [m for m, _, _ in _steps(chart)] == ['hline', 'vline']
    fig, ax = plt.subplots()
    ax.text(0.5, 0.5, 'corner', transform=ax.transAxes)
    _, messages = _converted(fig)
    assert any("'corner' placed in axes coordinates" in m for m in messages), messages


def test_annotations_pointing_at_data_are_converted():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.annotate('peak', xy=(0.5, 0.5), xytext=(0.2, 0.8), arrowprops=dict(arrowstyle='->'))
    chart, messages = _converted(fig)
    assert messages == []
    assert 'annotate' in [m for m, _, _ in _steps(chart)]
    _clean(chart)


def test_hollow_markers_and_rings_stay_hollow():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], 'o', mfc='none')
    ax.scatter([0, 1], [1, 0], facecolors='none', edgecolors='k')
    chart, messages = _converted(fig)
    assert messages == []
    scatters = [k for m, _, k in _steps(chart) if m == 'scatter']
    assert [k['hollow'] for k in scatters] == [True, True]
    assert scatters[1]['color'] == '#000000'
    _clean(chart)


def test_error_bar_caps_and_line_widths_are_carried():
    point = 72 / 25.4
    fig, ax = plt.subplots()
    ax.errorbar([0, 1], [1, 2], yerr=0.1, capsize=3, linewidth=3)
    chart, messages = _converted(fig)
    assert messages == []
    errors = next(k for m, _, k in _steps(chart) if m == 'errorbars')
    assert errors['cap'] == pytest.approx(3 / point)
    assert next(k for m, _, k in _steps(chart) if m == 'line')['stroke_width'] == pytest.approx(3 / point)
    fig, ax = plt.subplots()
    ax.errorbar([0, 1], [1, 2], yerr=0.1)
    chart, _ = _converted(fig)
    assert next(k for m, _, k in _steps(chart) if m == 'errorbars')['cap'] == 0


def test_ticks_set_by_hand_are_kept():
    fig, ax = plt.subplots()
    ax.plot([0, 0.5, 1], [0, 1, 0])
    ax.set_xticks([0, 0.5, 1], ['zero', 'half', 'one'])
    chart, messages = _converted(fig)
    assert messages == []
    ticks = chart._tick_overrides['x']
    assert ticks['ticks'] == [0.0, 0.5, 1.0]
    assert [ticks['format'](v) for v in ticks['ticks']] == ['zero', 'half', 'one']
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.set_xticks([])
    chart, _ = _converted(fig)
    assert 'x' in chart._hide_ticks


def test_gridlines_and_line_collection_colours_are_carried():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.grid(True, axis='y')
    ax.hlines([0.2, 0.6], 0, 1, colors=['r', 'g'])
    chart, messages = _converted(fig)
    assert messages == [] and chart.grid == 'y'
    colours = [k.get('color') for m, _, k in _steps(chart) if m == 'line']
    assert colours[1:] == ['#ff0000', '#008000']
    _clean(chart)


def test_ordinary_figures_raise_no_warning():
    fig, axes = plt.subplots(1, 3)
    axes[0].hist([1, 2, 2, 3, 3, 3], bins=3)
    axes[1].bar(['a', 'b'], [1, 2], yerr=[0.1, 0.2], capsize=3)
    axes[2].errorbar([1, 2], [1, 2], yerr=0.1, fmt='o-', capsize=2)
    _, messages = _converted(fig)
    assert messages == []
    fig, ax = plt.subplots()
    image = ax.imshow([[0, 1], [2, 3]], cmap='magma')
    fig.colorbar(image, label='count')
    ax.scatter([0, 1], [1, 0], c=[0.2, 0.8], cmap='viridis')
    _, messages = _converted(fig)
    assert messages == []
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], label='a')
    ax.plot([0, 1], [1, 0], label='b')
    ax.legend()
    _, messages = _converted(fig)
    assert messages == []
