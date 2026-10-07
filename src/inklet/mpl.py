"""Bring matplotlib figures into inklet: `inklet.from_matplotlib(fig)`.

The bridge reads what a matplotlib figure *plots* -- line and scatter data,
bars, filled bands, error bars, images, text, labels, limits and scales --
and records the same marks on inklet charts. Layout, typography and sizing
are then inklet's: text is measured at print size, axes align across panels
and panel letters are added. Nothing is rasterised.

Matplotlib's default colour cycle is treated as "no colour chosen", so the
inklet palette applies; colours a script set explicitly are kept. Artists the
bridge cannot read are listed in a warning (and on `chart.skipped`) rather
than dropped silently.

    fig, ax = plt.subplots()
    ax.plot(t, y, label='signal')
    ax.set_xlabel('Time / s')
    i.from_matplotlib(fig).save('figure.pdf')
"""
from __future__ import annotations

import warnings

__all__ = ['from_matplotlib', 'MatplotlibWarning']


class MatplotlibWarning(UserWarning):
    """Parts of a matplotlib figure that the bridge did not convert."""


_MARKERS = {'o': 'circle', '.': 'circle', 's': 'square', '^': 'triangle', 'v': 'triangle',
            'D': 'diamond', 'd': 'diamond', 'x': 'cross', 'X': 'cross', '+': 'plus', 'P': 'plus'}

_LEGEND_CORNERS = {'upper right': 'ne', 'upper left': 'nw', 'lower left': 'sw',
                   'lower right': 'se', 'right': 'e', 'center left': 'w', 'center right': 'e',
                   'lower center': 's', 'upper center': 'n', 'center': 'ne', 'best': 'ne'}

#: Points per millimetre; matplotlib widths are in points.
_PT = 72 / 25.4


def from_matplotlib(figure, *, width=None, style='scientific.modern', palette=None,
                    keep_colors=False, letters=True):
    """Convert a matplotlib `Figure` (or one `Axes`) into an inklet chart or layout.

    `width` defaults to the figure's own width, snapped to a single (89 mm)
    or double (183 mm) column when it is close to one. `keep_colors=True`
    keeps matplotlib's automatic cycle colours too. Returns a `Chart` for one
    axes and a lettered `Layout` for a grid of them.
    """
    from .quick import Layout
    axes_list, fig = _axes(figure)
    if not axes_list:
        raise ValueError('the matplotlib figure has no axes to convert')
    width = width or _width(fig)
    cycle = {} if keep_colors else _cycle_colors()
    charts, skipped = {}, []
    for ax in axes_list:
        chart = _convert(ax, cycle, style=style, palette=palette)
        skipped.extend(f'{_where(ax)}: {item}' for item in chart.skipped)
        charts[ax] = chart
    if skipped:
        warnings.warn(MatplotlibWarning('not converted: ' + '; '.join(skipped)), stacklevel=2)
    if len(charts) == 1:
        chart = next(iter(charts.values()))
        chart.size(width=width)
        return chart
    rows = _rows(axes_list)
    built = []
    for row in rows:
        items = [charts[ax] for ax in row]
        built.append(items[0] if len(items) == 1 else Layout('row', items))
    layout = built[0] if len(built) == 1 else Layout('column', built)
    if isinstance(layout, Layout):
        layout.width, layout.letters = width, letters
    return layout


# -- figure structure --------------------------------------------------------


def _axes(figure):
    if hasattr(figure, 'get_axes') and hasattr(figure, 'savefig'):
        fig = figure
        axes = [ax for ax in figure.get_axes() if ax.get_visible() and not _is_colorbar(ax)]
    elif hasattr(figure, 'get_figure') and hasattr(figure, 'plot'):
        fig = figure.get_figure()
        axes = [figure]
    else:
        raise TypeError('from_matplotlib() needs a matplotlib Figure or Axes')
    return axes, fig


def _is_colorbar(ax):
    return ax.get_label() == '<colorbar>' or hasattr(ax, '_colorbar')


def _width(fig):
    millimetres = fig.get_figwidth() * 25.4
    for name, size in (('single', 89.0), ('double', 183.0)):
        if abs(millimetres - size) <= 0.25 * size:
            return name
    return round(millimetres, 1)


def _rows(axes_list):
    """Axes grouped into rows by their grid position, top to bottom."""
    def place(ax):
        spec = ax.get_subplotspec() if hasattr(ax, 'get_subplotspec') else None
        if spec is not None:
            return spec.rowspan.start, spec.colspan.start
        box = ax.get_position()
        return -round(box.y1, 2), round(box.x0, 2)
    ordered = sorted(axes_list, key=place)
    rows, current = [], None
    for ax in ordered:
        row = place(ax)[0]
        if row != current:
            rows.append([])
            current = row
        rows[-1].append(ax)
    return rows


def _where(ax):
    title = ax.get_title()
    return f'axes {title!r}' if title else 'axes'


def _cycle_colors():
    """matplotlib's automatic colours, mapped to their slot in the cycle."""
    from matplotlib import rcParams
    from matplotlib.colors import to_hex
    try:
        colors = rcParams['axes.prop_cycle'].by_key().get('color', [])
        return {to_hex(c): index for index, c in enumerate(colors)}
    except (KeyError, ValueError):
        return {}


# -- one axes -----------------------------------------------------------------


def _convert(ax, cycle, *, style, palette):
    from matplotlib.container import BarContainer, ErrorbarContainer
    from .quick import Chart
    xlim = ax.get_xlim() if not ax.get_autoscalex_on() else None
    ylim = ax.get_ylim() if not ax.get_autoscaley_on() else None
    chart = Chart(style=style, palette=palette, title=ax.get_title() or None,
                  xlabel=ax.get_xlabel() or None, ylabel=ax.get_ylabel() or None,
                  xlim=xlim, ylim=ylim, xscale=_scale(ax.get_xscale()),
                  yscale=_scale(ax.get_yscale()), legend=_legend(ax))
    if ax.get_xscale() not in ('linear', 'log'):
        chart.skipped.append(f'{ax.get_xscale()} x scale (drawn linear)')
    if ax.get_yscale() not in ('linear', 'log'):
        chart.skipped.append(f'{ax.get_yscale()} y scale (drawn linear)')
    spec, used = chart.spec, set()
    named = 0
    for container in ax.containers:
        if isinstance(container, BarContainer):
            named += _bars(spec, container, cycle)
            used.update(id(p) for p in container.patches)
        elif isinstance(container, ErrorbarContainer):
            _errorbars(spec, container, cycle)
            line, caps, bars = container.lines
            used.update(id(a) for a in (line, *caps, *bars) if a is not None)
            if line is not None and (_label(container) or _label(line)):
                named += 1
    for line in ax.lines:
        if id(line) in used or not line.get_visible():
            continue
        named += _line(ax, spec, line, cycle, chart.skipped)
    for collection in ax.collections:
        if id(collection) in used or not collection.get_visible():
            continue
        named += _collection(ax, spec, collection, cycle, chart.skipped)
    for patch in ax.patches:
        if id(patch) not in used and patch.get_visible():
            chart.skipped.append(type(patch).__name__)
    for image in ax.images:
        _image(spec, image)
    for text in ax.texts:
        _text(ax, spec, text, chart.skipped)
    _ticks(ax, chart)
    chart._named = named
    chart._legend_explicit = ax.get_legend() is not None
    return chart


def _scale(name):
    return 'log' if name == 'log' else 'linear'


def _legend(ax):
    legend = ax.get_legend()
    if legend is None:
        return False
    loc = legend._loc if isinstance(getattr(legend, '_loc', None), str) else None
    codes = {0: 'best', 1: 'upper right', 2: 'upper left', 3: 'lower left', 4: 'lower right',
             5: 'right', 6: 'center left', 7: 'center right', 8: 'lower center',
             9: 'upper center', 10: 'center'}
    if loc is None:
        loc = codes.get(getattr(legend, '_loc', 0), 'best')
    return 'auto' if loc == 'best' else _LEGEND_CORNERS.get(loc, 'auto')


def _label(artist):
    label = artist.get_label()
    return label if label and not label.startswith('_') else None


def _color(value, cycle):
    """A hex colour, or the inklet palette slot standing in for matplotlib's cycle."""
    from matplotlib.colors import to_hex
    from .quick import _TOKEN
    try:
        hexed = to_hex(value)
    except (ValueError, TypeError):
        return None
    return f'{_TOKEN}{cycle[hexed]}' if hexed in cycle else hexed


def _style(artist, cycle, *, kind='line'):
    options = {}
    if kind == 'line':
        color = _color(artist.get_color(), cycle)
        if color:
            options['color'] = color
        style = artist.get_linestyle()
        if style in ('--', 'dashed'):
            options['stroke_dash'] = (1.6, 0.8)
        elif style in (':', 'dotted'):
            options['stroke_dash'] = (0.3, 0.6)
        elif style in ('-.', 'dashdot'):
            options['stroke_dash'] = (1.6, 0.6, 0.3, 0.6)
    alpha = artist.get_alpha()
    if alpha is not None and alpha < 1:
        options['opacity'] = float(alpha)
    return options


def _points(xs, ys):
    out = []
    for x, y in zip(xs, ys):
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            continue
        if x == x and y == y:
            out.append((x, y))
    return out


def _axes_coords(ax, artist):
    """'x' or 'y' when the artist spans the axes along that direction (axhline...)."""
    transform = artist.get_transform()
    if transform == ax.transData:
        return None
    if transform == ax.get_yaxis_transform():
        return 'x'      # x in axes fraction, y in data: a horizontal rule
    if transform == ax.get_xaxis_transform():
        return 'y'
    return 'other'


def _line(ax, spec, line, cycle, skipped):
    spanned = _axes_coords(ax, line)
    xs, ys = line.get_xdata(), line.get_ydata()
    if spanned == 'x':
        spec.hline(float(ys[0]), **_style(line, cycle))
        return 0
    if spanned == 'y':
        spec.vline(float(xs[0]), **_style(line, cycle))
        return 0
    if spanned == 'other':
        skipped.append('line drawn in axes or figure coordinates')
        return 0
    points = _points(xs, ys)
    if not points:
        return 0
    name = _label(line)
    marker = line.get_marker()
    has_line = line.get_linestyle() not in ('None', 'none', '', ' ')
    has_marker = marker not in (None, 'None', 'none', '', ' ')
    options = _style(line, cycle)
    if has_line:
        spec.line(points, name=name, **options)
    if has_marker:
        points = _every(points, line.get_markevery())
        shape = _MARKERS.get(marker, 'circle')
        size = line.get_markersize() / _PT
        spec.scatter(points, marker=shape, size=size, name=name,
                     **{k: v for k, v in options.items() if k != 'stroke_dash'})
    return 1 if name else 0


def _every(points, every):
    """The points matplotlib's `markevery` puts markers on."""
    if every is None:
        return points
    if isinstance(every, int):
        return points[::max(every, 1)]
    if isinstance(every, tuple) and len(every) == 2 and all(isinstance(v, int) for v in every):
        return points[every[0]::max(every[1], 1)]
    if isinstance(every, slice):
        return points[every]
    try:
        return [points[int(k)] for k in every]
    except (TypeError, ValueError, IndexError):
        return points


def _collection(ax, spec, collection, cycle, skipped):
    from matplotlib.collections import PathCollection, PolyCollection, LineCollection
    kind = type(collection).__name__
    name = _label(collection)
    if isinstance(collection, PathCollection):
        offsets = collection.get_offsets()
        points = _points(offsets[:, 0], offsets[:, 1]) if len(offsets) else []
        if not points:
            return 0
        options = {}
        array = collection.get_array()
        faces = collection.get_facecolors()
        if array is not None and len(array) == len(points):
            options['color'] = [float(v) for v in array]
            cmap = collection.get_cmap()
            options['ramp'] = _ramp(cmap.name if cmap is not None else 'viridis')
        elif len(faces) == 1:
            color = _color(faces[0], cycle)
            if color:
                options['color'] = color
        elif len(faces) == len(points):
            options['color'] = [_color(f, {}) for f in faces]
        sizes = collection.get_sizes()
        if len(sizes):
            # matplotlib sizes are marker areas in points squared.
            diameters = [(float(s) ** 0.5) / _PT for s in sizes]
            options['size'] = diameters[0] if len(set(diameters)) == 1 else diameters
        alpha = collection.get_alpha()
        if alpha is not None and alpha < 1:
            options['opacity'] = float(alpha)
        spec.scatter(points, name=name, **options)
        if 'ramp' in options:
            spec.colorbar()
        return 1 if name else 0
    if isinstance(collection, PolyCollection):
        drew = False
        for path in collection.get_paths():
            vertices = [tuple(map(float, v)) for v in path.vertices]
            band = _band(vertices)
            options = {}
            faces = collection.get_facecolors()
            if len(faces):
                color = _color(faces[0], cycle)
                if color:
                    options['color'] = color
                if faces[0][3] < 1:
                    options['opacity'] = float(faces[0][3])
            alpha = collection.get_alpha()
            if alpha is not None:
                options['opacity'] = float(alpha)
            if band is not None:
                xs, lo, hi = band
                spec.band(xs, lo, hi, name=None if drew else name, **options)
                drew = True
            else:
                skipped.append(f'{kind} that is not a band between two curves')
        return 1 if (name and drew) else 0
    if isinstance(collection, LineCollection):
        for segment in collection.get_segments():
            points = _points(segment[:, 0], segment[:, 1])
            if len(points) >= 2:
                spec.line(points)
        return 0
    skipped.append(kind)
    return 0


def _band(vertices):
    """(x, lower, upper) from a fill_between polygon, or None.

    The polygon runs along one curve and back along the other, with extra
    vertices at the ends; grouped by x, each x holds its lower and upper value.
    A polygon with more than two distinct y at some x is not such a band.
    """
    if len(vertices) < 4:
        return None
    at = {}
    for x, y in vertices:
        if x != x or y != y:
            continue
        at.setdefault(round(x, 12), set()).add(y)
    if len(at) < 2 or any(len(ys) > 2 for ys in at.values()):
        return None
    xs = sorted(at)
    return xs, [min(at[x]) for x in xs], [max(at[x]) for x in xs]


def _bars(spec, container, cycle):
    patches = [p for p in container.patches if p.get_visible()]
    if not patches:
        return 0
    horizontal = getattr(container, 'orientation', 'vertical') == 'horizontal'
    if horizontal:
        at = [p.get_y() + p.get_height() / 2 for p in patches]
        heights = [p.get_width() for p in patches]
        width = patches[0].get_height()
        baseline = patches[0].get_x()
    else:
        at = [p.get_x() + p.get_width() / 2 for p in patches]
        heights = [p.get_height() for p in patches]
        width = patches[0].get_width()
        baseline = patches[0].get_y()
    options = {}
    color = _color(patches[0].get_facecolor(), cycle)
    if color:
        options['color'] = color
    name = _label(container)
    spec.bars(at, heights, width=width, baseline=baseline, orient='h' if horizontal else 'v',
              name=name, **options)
    return 1 if name else 0


def _errorbars(spec, container, cycle):
    """Error bars, with the line and markers they were drawn with.

    `ax.bar(yerr=)` makes a container with no data line; its centres are the
    middles of the whiskers.
    """
    line, caps, bars = container.lines
    segments = [segment for collection in bars for segment in collection.get_segments()]
    if line is not None:
        points = _points(line.get_xdata(), line.get_ydata())
    else:
        points = [((s[0][0] + s[-1][0]) / 2, (s[0][1] + s[-1][1]) / 2) for s in segments]
    yerr, xerr = [], []
    for segment in segments:
        (x0, y0), (x1, y1) = segment[0], segment[-1]
        if abs(x0 - x1) < 1e-12:
            yerr.append((y0, y1))
        else:
            xerr.append((x0, x1))

    def spread(ends, index):
        if len(ends) != len(points):
            return None
        return [(p[index] - min(e), max(e) - p[index]) for p, e in zip(points, ends)]
    kwargs = {k: v for k, v in (('yerr', spread(yerr, 1)), ('xerr', spread(xerr, 0))) if v}
    name = _label(container) or (_label(line) if line is not None else None)
    options = {}
    if line is not None:
        options = _style(line, cycle)
        options.pop('stroke_dash', None)
    elif bars:
        color = _color(bars[0].get_colors()[0], cycle) if len(bars[0].get_colors()) else None
        if color:
            options['color'] = color
    if kwargs:
        spec.errorbars(points, **kwargs, **options)
    if line is None:
        return
    if line.get_linestyle() not in ('None', 'none', '', ' '):
        spec.line(points, name=name, **options)
    marker = line.get_marker()
    if marker not in (None, 'None', 'none', '', ' '):
        spec.scatter(points, marker=_MARKERS.get(marker, 'circle'),
                     size=line.get_markersize() / _PT, name=name, **options)


def _image(spec, image):
    data = image.get_array()
    if data is None or getattr(data, 'ndim', 0) != 2:
        return
    rows = [[float(v) for v in row] for row in data]
    norm = image.norm
    from .plot.scale import linear
    lo = norm.vmin if norm.vmin is not None else min(min(r) for r in rows)
    hi = norm.vmax if norm.vmax is not None else max(max(r) for r in rows)
    origin_upper = image.origin == 'upper'
    left, right, bottom, top = image.get_extent()
    columns = len(rows[0])
    step_x = (right - left) / columns
    step_y = (top - bottom) / len(rows)
    xs = [left + step_x * (k + 0.5) for k in range(columns)]
    ys = [bottom + step_y * (k + 0.5) for k in range(len(rows))]
    if origin_upper:
        # imshow's default puts row 0 at the top of an inverted y axis.
        ys = ys[::-1]
    cmap = image.get_cmap()
    spec.matrix(rows, x=xs, y=ys, ramp=_ramp(cmap.name if cmap else 'viridis'),
                scale=linear((lo, hi if hi > lo else lo + 1)))
    spec.colorbar()


def _ramp(name):
    from .plot.ramp import ramp
    try:
        ramp(name)
        return name
    except Exception:
        return 'viridis'


def _text(ax, spec, text, skipped):
    content = text.get_text()
    if not content.strip():
        return
    if text.get_transform() != ax.transData:
        skipped.append(f'text {content[:20]!r} placed in axes coordinates')
        return
    x, y = text.get_position()
    if hasattr(text, 'xy') and getattr(text, 'arrow_patch', None) is not None:
        spec.annotate(float(text.xy[0]), float(text.xy[1]), content)
        return
    anchor = {('left', 'center'): 'w', ('right', 'center'): 'e', ('center', 'bottom'): 's',
              ('center', 'top'): 'n'}.get((text.get_ha(), text.get_va()), 'center')
    spec.text(float(x), float(y), content, anchor=anchor)


def _ticks(ax, chart):
    """Keep category names on an axis matplotlib built from strings."""
    from matplotlib.category import StrCategoryConverter
    for axis, name, limits in ((ax.xaxis, 'x', ax.get_xlim()), (ax.yaxis, 'y', ax.get_ylim())):
        converter = axis.get_converter() if hasattr(axis, 'get_converter') else axis.converter
        if not isinstance(converter, StrCategoryConverter):
            continue
        lo, hi = sorted(limits)
        pairs = [(float(loc), tick.get_text()) for loc, tick in
                 zip(axis.get_ticklocs(), axis.get_ticklabels()) if lo <= loc <= hi]
        if not pairs:
            continue
        table = dict(pairs)
        if name == 'x':
            chart._categories([label for _, label in pairs])
        chart._tick_overrides[name] = {'ticks': [loc for loc, _ in pairs],
                                       'format': lambda v, table=table: table.get(v, '')}
