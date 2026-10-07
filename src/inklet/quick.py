"""One-call charts: `inklet.line(df, x='time', y='signal', color='group')`.

The quick API is a front door to the document model, not a second plotting
engine. Every chart is a `PlotSpec` in a preset `Document`; `.spec` and
`.document()` hand those over when a figure outgrows one call.

The keywords follow the table-first convention most plotting code (and most
coding assistants) already use: `data` is a table -- a pandas or Polars
DataFrame, a mapping of columns, or a list of records -- and `x`, `y`,
`color` name its columns. `color=` names a column to group by; any other
string is used as a literal colour.

    import inklet as i

    chart = i.line(df, x='time', y='signal', color='condition')
    chart.save('signal.pdf')

    figure = (i.scatter(df, x='dose', y='response') | i.boxplot(df, x='group', y='response'))
    figure.save('figure1.pdf', 'figure1.png')
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import inspect
import math
import warnings
from datetime import date
from numbers import Real
from pathlib import Path

__all__ = ['Chart', 'Layout', 'LayoutWarning', 'chart', 'line', 'scatter', 'bar', 'hist', 'boxplot', 'violin',
           'strip', 'kde', 'ecdf', 'area', 'heatmap', 'regression', 'survival', 'volcano', 'forest']

#: What `legend=` names besides off (False or None): a placement, a side, a corner.
_LEGEND_SIDES = ('top', 'bottom', 'left', 'right')
_LEGEND_CORNERS = ('nw', 'ne', 'sw', 'se')
_LEGEND_NAMES = ('auto', 'direct', 'best', 'none', *_LEGEND_SIDES, *_LEGEND_CORNERS)

#: Named widths, with the formats they select.
_WIDTHS = {'single': 'single-column', 'double': 'double-column', 'slide': 'slide',
           'single-column': 'single-column', 'double-column': 'double-column'}

#: Marks `label_lines` can name at their ends.
_LABELLED_CURVES = frozenset({'line', 'step', 'ecdf'})

#: Prefix of a palette slot recorded before the palette is known.
_TOKEN = '@series'

#: A pale version of a palette slot, for fills under that slot's lines, and a
#: softer one for areas that fill most of a plot.
_TINT, _TINT_AMOUNT = '@tint', 0.72
_SOFT, _SOFT_AMOUNT = '@soft', 0.45

#: Opacity of a grouped series' error band.
_BAND_OPACITY = 0.22

from .plot.paint import DASHES as _DASHES

#: A categorical `color=` column with more distinct numeric values than this
#: is read as a continuous variable and drawn with a colour ramp.
_MAX_GROUPS = 12


class LayoutWarning(UserWarning):
    """A saved chart has layout problems; the message is its lint report."""


# -- tables -----------------------------------------------------------------


class _Table(dict):
    """Columns as lists. `orders` maps a categorical column to its declared categories."""

    orders = {}


def _table(data) -> dict[str, list] | None:
    """Columns of a DataFrame, mapping or list of records, as Python lists."""
    if data is None:
        return None
    if isinstance(data, _Table):
        return data
    if isinstance(data, (str, Path)):
        return _read_table(Path(data))
    if hasattr(data, 'to_dict') and hasattr(data, 'columns') and hasattr(data, 'index'):
        # pandas: keep the index, which is the x of an index-keyed series.
        frame = data.reset_index() if _named_index(data) else data
        columns = _Table({str(name): _values(frame[name]) for name in frame.columns})
        columns.setdefault('index', _values(data.index))
        columns.orders = {str(name): _values(frame[name].cat.categories)
                          for name in frame.columns if hasattr(frame[name], 'cat')}
        return columns
    if hasattr(data, 'to_dict') and hasattr(data, 'columns') and hasattr(data, 'schema'):
        return {str(k): _values(v) for k, v in data.to_dict(as_series=False).items()}
    if isinstance(data, Mapping):
        return {str(k): _values(v) for k, v in data.items()}
    if isinstance(data, Sequence) and data and all(isinstance(r, Mapping) for r in data):
        names = list(dict.fromkeys(k for row in data for k in row))
        return {str(k): _values([row.get(k) for row in data]) for k in names}
    if _bare_values(data):
        raise TypeError('data is a sequence of values, not a table; pass the values as a '
                        'named sequence, e.g. x=[...]')
    raise TypeError('data must be a DataFrame, a mapping of columns or a list of records; '
                    f'got {type(data).__name__}')


def _bare_values(data) -> bool:
    """A plain sequence of values, which `data=` does not take: a table has columns."""
    if data is None or isinstance(data, (str, bytes, Path, Mapping)) or hasattr(data, 'columns'):
        return False
    if isinstance(data, (list, tuple)):
        return not (data and all(isinstance(row, Mapping) for row in data))
    return getattr(data, 'ndim', None) == 1


#: Cell texts read as missing values, as R, pandas and most exports write them.
_MISSING = frozenset({'', 'NA', 'N/A', 'NaN', 'nan', 'null', 'NULL'})


def _read_table(path: Path) -> dict[str, list]:
    """A CSV or TSV file as columns; numbers and ISO dates are parsed.

    A column becomes numbers when every non-empty cell is one, and dates when
    every non-empty cell is an ISO date; empty cells and `_MISSING` texts are
    missing values. Blank lines are skipped.
    """
    import csv
    from datetime import datetime
    if not path.exists():
        raise FileNotFoundError(f'no data file at {path}')
    delimiter = '\t' if path.suffix.lower() in ('.tsv', '.tab') else ','
    with path.open(newline='', encoding='utf-8-sig') as handle:
        rows = [row for row in csv.reader(handle, delimiter=delimiter) if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError(f'{path} is empty')
    header, body = rows[0], rows[1:]
    columns = {}
    for index, name in enumerate(header):
        cells = [row[index].strip() if index < len(row) else '' for row in body]
        cells = [None if c in _MISSING else c for c in cells]
        for parse in (float, datetime.fromisoformat):
            try:
                columns[name] = [parse(c) if c is not None else None for c in cells]
                break
            except ValueError:
                continue
        else:
            columns[name] = cells
        present = [v for v in columns[name] if v is not None]
        if present and all(isinstance(v, float) and v.is_integer() for v in present):
            columns[name] = [None if v is None else int(v) for v in columns[name]]
    return columns


def _named_index(frame) -> bool:
    names = getattr(frame.index, 'names', None) or ()
    return any(name is not None for name in names)


def _values(column) -> list:
    """Plain Python values: numpy scalars unwrapped, NaN and NaT as None."""
    if hasattr(column, 'dtype') and 'datetime64' in str(column.dtype):
        try:
            import pandas
            column = list(pandas.DatetimeIndex(column).to_pydatetime())
        except ImportError:
            column = [v.astype('datetime64[us]').item() for v in column]
    elif hasattr(column, 'tolist'):
        column = column.tolist()
    out = []
    for value in column:
        if hasattr(value, 'item') and not isinstance(value, (str, bytes)):
            try:
                value = value.item()
            except (ValueError, TypeError):
                pass
        if isinstance(value, float) and math.isnan(value):
            value = None
        elif type(value).__name__ in ('NaTType', 'NAType'):
            value = None
        out.append(value)
    return out


def _column(table, name, what):
    """A named column, or a literal sequence passed in its place."""
    if name is None:
        return None
    if isinstance(name, str):
        if table is None:
            raise ValueError(f'{what}={name!r} names a column, but no data was given')
        if name not in table:
            raise KeyError(f'{what}={name!r} is not a column; columns are {", ".join(table)}')
        return table[name]
    if isinstance(name, (Sequence,)) or hasattr(name, '__iter__'):
        return _values(name)
    raise TypeError(f'{what}= must be a column name or a sequence of values')


def _label(name, fallback=None):
    return name if isinstance(name, str) else fallback


def _in_category_order(table, name, keys):
    """Distinct keys in first-appearance order, or in the declared order when
    `name` is a categorical column. Declared categories no row uses are left out."""
    seen = list(dict.fromkeys(k for k in keys if k is not None))
    declared = getattr(table, 'orders', {}).get(name) if isinstance(name, str) else None
    if not declared:
        return seen
    rank = {value: k for k, value in enumerate(declared)}
    return sorted(seen, key=lambda value: rank.get(value, len(rank)))


def _groups(table, color, *columns, gaps=False):
    """Split columns by the `color=` column: [(name or None, columns...)].

    Rows with a missing value in any column are dropped, so a gap in one
    column does not shift the others. Groups follow `_in_category_order`.

    With `gaps`, rows missing a value after the first column are kept, the
    None in place, so a line can break there (see `_runs`); a row missing
    its first column (x) is still dropped.
    """
    keys = _column(table, color, 'color') if _is_column(table, color) else None
    rows = list(zip(*columns)) if columns else []
    if gaps:
        def dropped(row):
            return row[0] is None
    else:
        def dropped(row):
            return any(v is None for v in row)
    if keys is None:
        kept = [row for row in rows if not dropped(row)]
        return [(None, *map(list, zip(*kept)))] if kept else [(None, *([] for _ in columns))]
    split = {}
    for key, row in zip(keys, rows):
        if key is None or dropped(row):
            continue
        split.setdefault(key, []).append(row)
    return [(str(key), *map(list, zip(*split[key])))
            for key in _in_category_order(table, color, split)]


def _check_color(color):
    if color is not None and not isinstance(color, str):
        raise TypeError('color= is a column name or one colour; to colour each series, '
                        'pass color=<column> and palette=[...]')


def _is_column(table, name) -> bool:
    return isinstance(name, str) and table is not None and name in table


def _literal_color(table, color):
    return color if isinstance(color, str) and not _is_column(table, color) else None


def _numeric(values) -> bool:
    present = [v for v in values if v is not None]
    return bool(present) and all(isinstance(v, Real) and not isinstance(v, bool) for v in present)


def _ordered(xs, ys, err):
    """Points of a line in x order, so unsorted rows do not zigzag."""
    rows = list(zip(xs, ys, err if err is not None else [None] * len(xs)))
    try:
        rows.sort(key=lambda row: row[0])
    except TypeError:
        return xs, ys, err
    xs, ys, err_sorted = (list(column) for column in zip(*rows)) if rows else ([], [], [])
    return xs, ys, (err_sorted if err is not None else None)


def _runs(xs, ys, err):
    """A line's rows split at missing values: [(xs, ys, err)], one per run.

    A missing y, or a missing error when there is one, is a gap. Drawing each
    run on its own stops a segment from bridging the gap, which would read as
    data. Without gaps there is one run, and a series with no points at all
    gives none.
    """
    runs, current = [], []
    for k, y in enumerate(ys):
        if y is None or (err is not None and err[k] is None):
            if current:
                runs.append(current)
            current = []
        else:
            current.append(k)
    if current:
        runs.append(current)
    return [([xs[k] for k in run], [ys[k] for k in run],
             None if err is None else [err[k] for k in run]) for run in runs]


def _label_text(value):
    """A point's label text, or None for a blank one: no label, no leader line."""
    if value is None:
        return None
    text = str(value)
    return text if text.strip() else None


def _continuous(values) -> bool:
    numbers = [v for v in values if isinstance(v, Real) and not isinstance(v, bool)]
    return len(numbers) == len([v for v in values if v is not None]) and len(set(numbers)) > _MAX_GROUPS


# -- charts -----------------------------------------------------------------


class _Renderable:
    """Exports and notebook display shared by charts and layouts."""

    def compile(self):
        """Measure and place everything; returns a `CompiledFigure`.

        Category labels are set upright first. A chart whose labels then
        collide is built again with them turned 45 degrees, so labels turn
        only when they have to.
        """
        figure = self.document().compile()
        crowded = frozenset(id(chart) for chart in self._chart_list()
                            if chart._x_categories and _labels_collide(figure, chart._x_categories))
        return self.document(rotate=crowded).compile() if crowded else figure

    def save(self, *paths, **options):
        """Save to each path; the extension picks SVG, PDF or PNG.

        Returns the compiled figure, whose `report()` lists layout problems.
        """
        if not paths:
            raise ValueError('save() needs at least one path, e.g. save("figure.pdf")')
        from .render.page import check_export_options
        check_export_options([Path(p).suffix.lower() for p in paths], options)
        figure = self.compile()
        figure.save(*paths, **options)
        serious = [d for d in figure.lint() if d.severity in ('error', 'warning')]
        if serious:
            from .diagnostics import format_report
            warnings.warn(LayoutWarning(format_report(serious)), stacklevel=2)
        return figure

    def to_svg(self, **options) -> str:
        from .render.page import check_export_options
        check_export_options(['.svg'], options, 'to_svg()')
        return self.compile().to_svg(**options)

    def to_pdf(self, **options) -> bytes:
        from .render.page import check_export_options
        check_export_options(['.pdf'], options, 'to_pdf()')
        return self.compile().to_pdf(**options)

    def to_png(self, **options) -> bytes:
        from .render.page import check_export_options
        check_export_options(['.png'], options, 'to_png()')
        return self.compile().to_png(**options)

    def report(self, **options) -> str:
        """Layout and print diagnostics: overlaps, clipped text, small type."""
        return self.compile().report(**options)

    def show(self, path=None):
        """Display in a notebook, or write an SVG and print where it went.

        Outside a notebook nothing blocks: `show()` writes `path` (default
        `inklet-preview.svg`) and returns it.
        """
        try:
            from IPython import get_ipython
            from IPython.display import display
            if get_ipython() is not None:
                display(self)
                return None
        except ImportError:
            pass
        target = Path(path or 'inklet-preview.svg')
        self.save(target)
        print(f'inklet: wrote {target.resolve()}')
        return target

    def _repr_mimebundle_(self, include=None, exclude=None):
        from .notebook import mimebundle
        return mimebundle(self.compile())

    def __or__(self, other):
        return Layout('row', (self, other))

    def __truediv__(self, other):
        return Layout('column', (self, other))


class Chart(_Renderable):
    """One plot: marks on shared axes, with a size and a preset.

    Build one with `inklet.line(...)`, `inklet.scatter(...)` and friends, add
    marks with the same methods (`chart.line(...)` layers a line), and finish
    with `save()`. `spec` is the underlying `PlotSpec`; every `Panel` method
    on it (`annotate`, `hline`, `inset`...) works here too and returns the chart.
    """

    def __init__(self, *, width=None, height=None, style='scientific.modern', font_pt=None,
                 palette=None, title=None, xlabel=None, ylabel=None, xlim=None, ylim=None,
                 xscale='linear', yscale='linear', legend='auto', grid=None,
                 xticks=None, yticks=None, xminor=None, yminor=None, xformat=None, yformat=None):
        from .document import plot_spec
        for name, value in (('xscale', xscale), ('yscale', yscale)):
            if value not in ('linear', 'log'):
                raise ValueError(f"{name} must be 'linear' or 'log', got {value!r}")
        if not (legend is None or legend is False or legend in _LEGEND_NAMES):
            raise ValueError(f"legend must be False, 'auto', 'direct', 'best', a side "
                             f"({', '.join(_LEGEND_SIDES)}) or a corner "
                             f"({', '.join(_LEGEND_CORNERS)}); got {legend!r}")
        for name, value in (('xformat', xformat), ('yformat', yformat)):
            # The axis's own `format=` forms: a spec with `{}`, a suffix, or a callable.
            if value is not None and not (isinstance(value, str) or callable(value)):
                raise TypeError(f"{name} must be a format string or a callable, got {value!r}")
        if font_pt is not None and (isinstance(font_pt, bool) or not isinstance(font_pt, Real) or font_pt <= 0):
            raise ValueError(f'font_pt is the main type size in points, a positive number; got {font_pt!r}')
        # A width of None means "the style decides": a Preset keeps its own page, a name is a single column.
        self.width, self.palette, self.grid = width, palette, grid
        self.style = _check_style(style)
        self.font_pt = font_pt
        self.height = height
        self.title, self.xlabel, self.ylabel = title, xlabel, ylabel
        self.legend_side = legend
        self.xticks, self.yticks = xticks, yticks
        self.xminor, self.yminor = xminor, yminor
        self.xformat, self.yformat = xformat, yformat
        #: A forest plot's rows and options; it is a Diagram, not Panel marks.
        self._forest = None
        options = {'x': _domain(xlim, xscale), 'y': _domain(ylim, yscale)}
        if xlim is not None or ylim is not None:
            # Explicit limits zoom: marks past them are cut at the axes.
            options['clip'] = True
        self.spec = plot_spec(**options)
        self._named = 0
        self._auto_labels = {}
        self._x_categories = []
        self._tick_overrides = {}
        self._series_tokens = {}
        self._series_names = set()
        self._legend_explicit = False
        self._hide_ticks = set()
        #: A lone chart's title reads from the left edge, like its y axis;
        #: facet titles centre over their panels.
        self._title_align = 'left'
        #: What `from_matplotlib` could not convert, if this chart came from it.
        self.skipped = []

    # Marks. Each mirrors the top-level function of the same name.

    def line(self, data=None, x=None, y=None, *, color=None, name=None, markers=False,
             error_y=None, dash=None, linewidth=None, sort=True, gaps='break', **style):
        """Lines through (x, y), one per `color` group or per `y` column.

        Points are joined in x order; `sort=False` keeps row order (a path
        that doubles back, such as a phase portrait). Without `y`, every
        numeric column is a series.

        A row with a missing y (or error) is a gap. `gaps='break'`, the default,
        leaves it open, so no segment bridges it; `gaps='bridge'` joins the
        points either side as if the row were not there.
        """
        if gaps not in ('break', 'bridge'):
            raise ValueError(f"gaps must be 'break' or 'bridge', got {gaps!r}")
        table = _table(data)
        _check_color(color)
        for label, xs, ys, err in self._series(table, x, y, color, error_y, gaps=gaps == 'break'):
            if sort:
                xs, ys, err = _ordered(xs, ys, err)
            series = name or label
            options = self._style(table, color, style, dash=dash, stroke_width=linewidth,
                                  label=series, lone=True)
            # Each run is drawn alone, in the one colour; only the first is
            # named, so the key has one entry for the series.
            for number, (run_x, run_y, run_err) in enumerate(_runs(xs, ys, err)):
                points = list(zip(run_x, run_y))
                named = series if number == 0 else None
                run_options = dict(options)
                if run_err is not None and 'color' in options:
                    # Translucent, so where two groups' bands overlap both show.
                    # Unnamed: a key swatch has no opacity and would read solid.
                    spread = [(y - e, y + e) for y, e in zip(run_y, run_err)]
                    self.spec.band(run_x, [lo for lo, _ in spread], [hi for _, hi in spread],
                                   color=options['color'], fill=options['color'],
                                   fill_opacity=_BAND_OPACITY)
                elif run_err is not None:
                    run_options['err'] = run_err
                self.spec.line(points, name=named, **run_options)
                if markers:
                    self.spec.scatter(points, name=named,
                                      **self._style(table, color, {}, mark=True, label=series,
                                                    lone=True))
        return self._labelled(x, y)

    def scatter(self, data=None, x=None, y=None, *, color=None, size=None, name=None,
                marker='circle', palette=None, error_y=None, text=None, **style):
        """Points at (x, y). A numeric `color` column with many values is a ramp.

        `size` is a diameter in mm or a column of them; `text` names a column
        of point labels (None for unlabelled points), placed clear of the marks.
        """
        table = _table(data)
        _check_color(color)
        xs, ys = _column(table, x, 'x'), _column(table, y, 'y')
        if xs is None:
            xs = _index(table, None, len(ys))
        sizes = _column(table, size, 'size') if _is_column(table, size) else None
        if _is_column(table, color) and _continuous(table[color]):
            columns = [xs, ys, table[color]] + ([sizes] if sizes else [])
            _, *kept = _groups(None, None, *columns)[0]
            options = {'size': kept[3]} if sizes else _size(size, table)
            self.spec.scatter(list(zip(kept[0], kept[1])), color=kept[2],
                              ramp=palette or 'viridis', marker=marker, name=name,
                              **options, **style)
            self.spec.colorbar(title=color)
        else:
            err = _column(table, error_y, 'error_y') if error_y is not None else None
            columns = [xs, ys] + ([err] if err else []) + ([sizes] if sizes else [])
            for label, *kept in _groups(table, color, *columns):
                points = list(zip(kept[0], kept[1]))
                series = name or label
                if not points:
                    continue
                if err:
                    self.spec.errorbars(points, yerr=kept[2],
                                        **self._style(table, color, {}, label=series, lone=True))
                options = {'size': kept[-1]} if sizes else _size(size, table)
                if 'size' not in options:
                    options.update(_marker_look(len(points), len(xs)))
                self.spec.scatter(points, name=series, marker=marker, **options,
                                  **self._style(table, color, style, mark=True, label=series,
                                                lone=True))
            self._named += sum(1 for group in _groups(table, color, xs, ys) if group[0] is not None)
        if text is not None:
            labels = _column(table, text, 'text')
            # Only points that were drawn: a row without a group is not. A blank
            # label is no label, so its point gets no leader line.
            keys = table[color] if _is_column(table, color) else [True] * len(labels)
            rows = [(a, b, _label_text(t)) for a, b, t, k in zip(xs, ys, labels, keys)
                    if a is not None and b is not None and _label_text(t) is not None
                    and k is not None]
            if rows:
                self.spec.label_points([(a, b) for a, b, _ in rows], [t for _, _, t in rows])
        return self._labelled(x, y)

    def bar(self, data=None, x=None, y=None, *, color=None, name=None, orient='v',
            stacked=False, error_y=None, labels=None, agg='sum', points=False, **style):
        """Bars of `y` at each `x` category; `color` groups side by side or stacked.

        Rows sharing a category are combined by `agg`: `'sum'` (default),
        `'mean'` or `'median'`. Without `y`, bars count the rows. With a mean or
        median, `error_y` may be `'sem'`, `'sd'` or `'ci95'` (computed from the
        rows) and `points=True` shows every row as a dot.
        """
        table = _table(data)
        _check_color(color)
        if agg not in ('sum', 'mean', 'median'):
            raise ValueError("bar(agg=) is 'sum', 'mean' or 'median'")
        at = _column(table, x, 'x')
        if at is None:
            raise ValueError('bar() needs x=, the categories along the axis')
        heights = _column(table, y, 'y') if y is not None else None
        groups = _column(table, color, 'color') if _is_column(table, color) else None
        cats = _in_category_order(table, x, at)
        if agg != 'sum':
            return self._estimated(table, x, y, at, heights, groups, cats, agg, error_y, points,
                                   color, name, orient, style)
        names = _in_category_order(table, color, groups) if groups is not None else None
        series, names = _aggregate(at, heights, groups, cats, names)
        options = dict(style)
        # Bars are filled shapes: no outline drawn round them.
        options.setdefault('stroke', 'none')
        if (literal := _literal_color(table, color)) is not None:
            options['color'] = literal
        elif len(series) == 1:
            # A bar is a large area: a softened series colour, not a block.
            options.setdefault('color', f'{_SOFT}0')
        else:
            options.setdefault('color', [f'{_SOFT}{k}' for k in range(len(series))])
        if len(series) > 1:
            options['stacked' if stacked else 'grouped'] = True
            options['name'] = names
            self._named += len(names)
        elif name:
            options['name'] = name
        if labels is not None:
            options['labels'] = labels
        if orient == 'v':
            self._categories(cats)
        heights_arg = series[0] if len(series) == 1 else series
        self.spec.bars(cats, heights_arg, orient=orient, **options)
        if error_y is not None and len(series) == 1:
            err = _column(table, error_y, 'error_y')
            mean_err = _aggregate(at, err, None, cats)[0][0]
            points = [(c, h) for c, h in zip(cats, series[0])] if orient == 'v' else \
                [(h, c) for c, h in zip(cats, series[0])]
            key = 'yerr' if orient == 'v' else 'xerr'
            self.spec.errorbars(points, **{key: mean_err})
        value = y if y is not None else 'count'
        return self._labelled(x, value) if orient == 'v' else self._labelled(value, x)

    def _estimated(self, table, x, y, at, heights, groups, cats, agg, error_y, points,
                   color, name, orient, style):
        """Bars at a mean or median with an error bar, drawn by `barplot`."""
        if heights is None:
            raise ValueError(f"bar(agg='{agg}') needs y=, the values to average")
        if error_y is not None and error_y not in ('sem', 'sd', 'ci95', 'iqr'):
            raise ValueError("with agg='mean' or 'median', error_y is 'sem', 'sd', 'ci95' or 'iqr'")
        names = _in_category_order(table, color, groups) if groups is not None else [None]
        samples = {(c, g): [] for c in cats for g in names}
        for index, cat in enumerate(at):
            group = groups[index] if groups is not None else None
            if cat is None or heights[index] is None or (groups is not None and group is None):
                continue
            samples[(cat, group)].append(float(heights[index]))
        data = [[samples[(c, g)] for c in cats] for g in names]
        options = dict(style)
        if (literal := _literal_color(table, color)) is not None:
            options['color'] = literal
        elif groups is None:
            options.setdefault('color', f'{_TOKEN}0')
        if groups is not None:
            options['name'] = [str(g) for g in names]
            self._named += len(names)
        elif name:
            options['name'] = name
        if orient == 'v':
            self._categories(cats)
        options.setdefault('stroke', 'none')
        if points and 'size' not in options:
            # Dots shrink as a bar holds more of them, so the swarm stays a
            # texture over the bar rather than a second, darker bar.
            most = max((len(v) for v in samples.values()), default=0)
            options['size'] = 1.0 if most <= 12 else 0.8 if most <= 30 else 0.6
        self.spec.barplot(cats, data if groups is not None else data[0], estimator=agg,
                          error=error_y, points=points, orient=orient, **options)
        return self._labelled(x, y) if orient == 'v' else self._labelled(y, x)

    def hist(self, data=None, x=None, *, color=None, bins=20, density=False, name=None,
             cumulative=False, **style):
        """Histogram of `x`; one overlaid histogram per `color` group."""
        table = _table(data)
        _check_color(color)
        groups = self._samples(table, x, color)
        options = self._style(table, color, style, lone=len(groups) == 1)
        values = groups if len(groups) > 1 else next(iter(groups.values()))
        if len(groups) == 1 and name:
            options['name'] = name
            self._series_names.add(name)
        self.spec.hist(values, bins, density=density, cumulative=cumulative, **options)
        return self._labelled(x, 'density' if density else 'count')

    def kde(self, data=None, x=None, *, color=None, fill=False, name=None, **style):
        """Kernel density estimate of `x`, one curve per `color` group."""
        table = _table(data)
        _check_color(color)
        for label, values in self._samples(table, x, color).items():
            self.spec.kde(values, fill=fill, name=name or label,
                          **self._style(table, color, style, label=name or label, lone=True))
        return self._labelled(x, 'density')

    def ecdf(self, data=None, x=None, *, color=None, name=None, **style):
        """Empirical cumulative distribution of `x`, one step per `color` group."""
        table = _table(data)
        _check_color(color)
        for label, values in self._samples(table, x, color).items():
            self.spec.ecdf(values, name=name or label,
                           **self._style(table, color, style, label=name or label, lone=True))
        return self._labelled(x, 'proportion')

    def boxplot(self, data=None, x=None, y=None, *, color=None, points=False, **style):
        """Box plot of `y` in each `x` category."""
        self._grouped('boxplot', data, x, y, color, _tinted_shape(style, color))
        if points:
            self._grouped('strip', data, x, y, color, _dots(style))
        return self._labelled(x, y)

    def violin(self, data=None, x=None, y=None, *, color=None, points=False, **style):
        """Violin plot of `y` in each `x` category."""
        self._grouped('violin', data, x, y, color, _tinted_shape(style, color))
        if points:
            self._grouped('strip', data, x, y, color, _dots(style))
        return self._labelled(x, y)

    def strip(self, data=None, x=None, y=None, *, color=None, **style):
        """Jittered points of `y` in each `x` category."""
        self._grouped('strip', data, x, y, color, {**_dots({}), **style})
        return self._labelled(x, y)

    def area(self, data=None, x=None, y=None, *, color=None, stacked=True, **style):
        """Filled areas under `y`; groups stack unless `stacked=False`."""
        table = _table(data)
        _check_color(color)
        series = self._series(table, x, y, color, None)
        if stacked and len(series) > 1:
            xs = sorted({v for _, xs, _, _ in series for v in xs})
            stacks = []
            for _, sx, sy, _ in series:
                lookup = dict(zip(sx, sy))
                stacks.append([lookup.get(v, 0.0) for v in xs])
            labels = [label for label, *_ in series]
            tokens = [self._token(label) for label in labels]
            # Soft layers, each topped by a crisp line in its own colour: the
            # boundaries carry the reading, the fills only the grouping.
            self.spec.stackarea(xs, stacks, name=labels,
                                **{'color': [t.replace(_TOKEN, _SOFT) for t in tokens], **style})
            top = [0.0] * len(xs)
            for token, row in zip(tokens, stacks):
                top = [a + b for a, b in zip(top, row)]
                self.spec.line(list(zip(xs, top)), color=token)
        else:
            for label, xs, ys, _ in series:
                self.spec.fill_between(xs, 0.0, ys, name=label,
                                       **self._style(table, color, style, label=label, lone=True))
        return self._labelled(x, y)

    def regression(self, data=None, x=None, y=None, *, color=None, method='linear',
                   confidence=0.95, name=None, **style):
        """Points with a fitted line and its confidence band, per `color` group."""
        table = _table(data)
        _check_color(color)
        for label, xs, ys, _ in self._series(table, x, y, color, None):
            self.spec.regression(list(zip(xs, ys)), method=method, confidence=confidence,
                                 name=name or label,
                                 **self._style(table, color, style, label=name or label,
                                               lone=True))
        return self._labelled(x, y)

    def heatmap(self, data=None, x=None, y=None, z=None, *, palette='viridis', center=None,
                colorbar=True, colorbar_title=None, **style):
        """A matrix of colour cells. `colorbar` is True, False or the bar's title.

        `colorbar_title=` names the bar, as `colorbar='r'` does. Pass a 2D
        sequence (rows of values) as `data`, with `x`/`y` as the column and row
        labels; or a long table with `x`, `y` and `z` columns.
        """
        if colorbar_title is not None:
            if colorbar is not True:
                raise ValueError('heatmap takes colorbar= or colorbar_title=, not both')
            colorbar = colorbar_title
        if z is not None:
            table = _table(data)
            xs, ys, zs = (_column(table, n, w) for n, w in ((x, 'x'), (y, 'y'), (z, 'z')))
            cols = list(dict.fromkeys(xs))
            rows = list(dict.fromkeys(ys))
            cells = {(a, b): c for a, b, c in zip(xs, ys, zs)}
            values = [[cells.get((c, r)) for c in cols] for r in rows]
            xlabels, ylabels = cols, rows
            self._labelled(x, y)
        else:
            if hasattr(data, 'to_numpy') and hasattr(data, 'columns'):
                xlabels = [str(c) for c in data.columns] if x is None else x
                ylabels = [str(r) for r in data.index] if y is None else y
                data = data.to_numpy()
            else:
                xlabels, ylabels = x, y
            if any(isinstance(row, str) or not hasattr(row, '__iter__') for row in data):
                raise TypeError('heatmap data is rows of values, e.g. [[1, 2], [3, 4]], not a '
                                'flat sequence; for a long table give data=, x=, y= and z=')
            values = [_values(row) for row in data]
        xlabels = list(xlabels) if xlabels is not None else [str(i) for i in range(len(values[0]))]
        ylabels = list(ylabels) if ylabels is not None else [str(i) for i in range(len(values))]
        xlabels, ylabels = [str(v) for v in xlabels], [str(v) for v in ylabels]
        # The first row reads at the top, as it does in the table.
        self.spec.configure(x=xlabels, y=ylabels[::-1])
        self._categories(xlabels)
        style.setdefault('x', xlabels)
        style.setdefault('y', ylabels)
        numbers = [v for row in values for v in row if isinstance(v, Real)]
        if center is None and numbers and 'scale' not in style:
            from .plot.scale import linear
            lo, hi = min(numbers), max(numbers)
            style['scale'] = linear((lo, hi if hi > lo else lo + 1))
        self.spec.matrix(values, ramp=palette, center=center, **style)
        if colorbar:
            title = colorbar if isinstance(colorbar, str) else z if isinstance(z, str) else None
            self.spec.colorbar(title=title)
        return self

    def survival(self, data=None, time=None, event=None, *, color=None, at_risk=True,
                 pvalue=True, band='log-log', confidence=0.95, censors=True, **style):
        """Kaplan-Meier survival curves: `time` durations and `event` flags, one curve per `color` group.

        `event` is 1 or True where the event was observed and 0 or False where
        the subject was censored. Each curve has censor ticks and a confidence
        band: `band='log-log'` by default, or `'log'`, `'linear'` or None.
        `at_risk=True` adds the number-at-risk table under the axis, and
        `pvalue=True` writes the log-rank P when there are two or more groups.
        The survival axis runs from 0 to 1 unless `ylim=` says otherwise.

            i.survival(df, time='months', event='died', color='arm')
        """
        table = _table(data)
        _check_color(color)
        if time is None or event is None:
            raise ValueError('survival needs time= and event=, the duration and event columns')
        groups = _groups(table, color, _column(table, time, 'time'), _column(table, event, 'event'))
        self._named += sum(1 for label, *_ in groups if label is not None)
        if len(groups) == 1:
            curves = (groups[0][1], groups[0][2])
        else:
            curves = {label: (durations, events) for label, durations, events in groups}
        options = {}
        if (literal := _literal_color(table, color)) is not None:
            options['color'] = literal
        elif len(groups) > 1:
            options['color'] = [self._token(label) for label, *_ in groups]
        if len(groups) > 1 and pvalue:
            options['pvalue'] = 'logrank'
        self.spec.kaplan_meier(curves, confidence=confidence, band=band, censors=censors,
                               **options, **style)
        if at_risk:
            self.spec.at_risk()
        if self.spec.options.get('y') == 'auto':
            self.spec.configure(y=(0, 1))
        return self._labelled(time, 'Survival probability')

    def volcano(self, data=None, x=None, y=None, *, label=None, labels=None, highlight=None, q=None, **style):
        """A volcano plot: `x` the log2 fold change, `y` the raw p-value, one point per row.

        Rows missing a fold change or p-value are dropped. `q=` names an
        adjusted p-value column, which classes the points by FDR (a missing q
        makes that point "ns"). `label=` (or `labels=`, the name `Panel.volcano`
        uses) names each feature and `highlight=` lists the features to name on
        the plot. Other keywords go to `Panel.volcano`: `top=`,
        `fold_threshold=`, `p_threshold=`, `color=`.

            i.volcano(df, x='log2fc', y='p', label='gene', q='fdr', highlight=['CRISPLD2'])
        """
        if labels is not None:
            # Both spellings name the same column; passing both would be ambiguous.
            if label is not None:
                raise ValueError('volcano takes label= or labels=, not both')
            label = labels
        table = _table(data)
        if x is None or y is None:
            raise ValueError('volcano needs x= (log2 fold change) and y= (raw p-values)')
        folds = _column(table, x, 'x')
        pvalues = _column(table, y, 'y')
        names = _column(table, label, 'label')
        adjusted = _column(table, q, 'q')
        kept = [k for k, (fold, p) in enumerate(zip(folds, pvalues)) if fold is not None and p is not None]
        # A key row for the significant classes; the "ns" points need none.
        style.setdefault('name', {'up': 'up', 'down': 'down'})
        self._named += 2
        self.spec.volcano([folds[k] for k in kept], [pvalues[k] for k in kept],
                          labels=None if names is None else ['' if names[k] is None else str(names[k])
                                                             for k in kept],
                          highlight=highlight,
                          q=None if adjusted is None else [adjusted[k] for k in kept], **style)
        return self._labelled('log2 fold change', '−log10 P')

    def forest(self, data=None, label=None, estimate=None, lower=None, upper=None, *,
               weight=None, summary=None, left=('label',), right=('ci',), log=False,
               null=None, limits=None, measure='Estimate', digits=2, **style):
        """A forest plot: one row per study, with its estimate and confidence interval.

        `label=` names the study column, and `estimate=`, `lower=` and `upper=`
        the estimate and interval bounds. `weight=` sizes each square by its
        weight; `summary=` names a column of flags that draws those rows as
        diamonds. `left` and `right` are the text columns beside the plot:
        "label", "ci" (the estimate and interval), "estimate", "weight" or
        any other column of the table. Rows missing a label, estimate or
        bound are dropped. The chart's `xlabel` names the axis; other keywords
        (`width=`, `color=`, `summary_line=`) go to `inklet.plot.forest`.

            i.quick.forest(df, label='study', estimate='or', lower='lo', upper='hi',
                     weight='n', log=True, measure='OR', right=['ci', 'n'])
        """
        table = _table(data)
        if label is None or estimate is None or lower is None or upper is None:
            raise ValueError('forest needs label=, estimate=, lower= and upper=, the column names')
        names, values, lows, highs = (_column(table, name, what) for name, what in
                                      ((label, 'label'), (estimate, 'estimate'), (lower, 'lower'), (upper, 'upper')))
        weights = _column(table, weight, 'weight')
        flags = _column(table, summary, 'summary')
        extra = [name for name in dict.fromkeys([*left, *right]) if isinstance(name, str)
                 and name not in ('label', 'ci', 'estimate', 'weight', 'low', 'high', 'summary')]
        extras = {name: _column(table, name, 'left or right') for name in extra}
        rows = []
        for k in range(len(values)):
            if any(column[k] is None for column in (names, values, lows, highs)):
                continue
            row = {'label': str(names[k]), 'estimate': values[k], 'low': lows[k], 'high': highs[k]}
            if weights is not None and weights[k] is not None:
                row['weight'] = weights[k]
            if flags is not None and flags[k]:
                row['summary'] = True
            row.update({name: column[k] for name, column in extras.items()})
            rows.append(row)
        if not rows:
            raise ValueError('forest has no rows with a label, an estimate and both bounds')
        if self.xformat is not None or self.yformat is not None:
            # A forest draws its own estimate axis, and `inklet.forest` takes no format.
            raise ValueError('forest does not take xformat= or yformat=; its axis is drawn by inklet.forest')
        options = {'log': log, 'null': null, 'limits': limits, 'left': tuple(left),
                   'right': tuple(right), 'measure': measure, 'digits': digits, **style}
        self._forest = (rows, options)
        return self

    # Labels and layout.

    def labels(self, *, x=None, y=None, title=None):
        """Set axis titles and the chart title (all optional)."""
        if x is not None:
            self.xlabel = x
        if y is not None:
            self.ylabel = y
        if title is not None:
            self.title = title
        return self

    def colorbar(self, **options):
        """Draw the colour bar, or update the one already drawn.

        Takes the keywords of `Panel.colorbar` (`title=`, `side=`...). A heatmap
        or a scatter coloured by a numeric column already draws a bar; a second
        one for the same ramp is the DUPLICATE_KEY lint reports. So this never
        adds a bar when one is recorded: the new keywords are merged into the
        recorded bar's options, and the ones it did not name keep their values.
        """
        return self._once('colorbar', options, merge=True)

    def legend(self, **options):
        """Draw the key, or replace the key already recorded.

        Takes the keywords of `Panel.legend` (`corner=`, `side=`, `title=`...).
        A second call does not add a second key, which lint reports as
        DUPLICATE_KEY when both key the same entries. Its keywords replace the
        recorded key's options as a whole, so anything the first call set and
        the second leaves out goes back to the default.
        """
        return self._once('legend', options, merge=False)

    def _once(self, method, options, *, merge):
        """Record `method` on the spec, keeping one step of that kind.

        The call is recorded by the same code a first call uses, so nothing
        about it is special-cased; the step it just added is then taken back
        out and folded into the earlier one. That keeps the spec's own rules
        (a duplicate key, a bad signature) in force for the update too.
        """
        spec = self.spec
        earlier = [i for i, step in enumerate(spec._steps) if step[1] == method]
        getattr(spec, method)(**options)
        if not earlier:
            return self
        key, _, _, fresh = spec._steps.pop()
        i = earlier[-1]
        old_key, name, args, kwargs = spec._steps[i]
        spec._steps[i] = (key if key is not None else old_key, name, args,
                          (kwargs | fresh) if merge else fresh)
        return self

    def size(self, width=None, height=None):
        """Width as 'single', 'double', 'slide' or millimetres; height in mm."""
        if width is not None:
            self.width = width
        if height is not None:
            self.height = height
        return self

    def __getattr__(self, name):
        if name.startswith('_') or name == 'spec':
            raise AttributeError(name)
        method = getattr(self.spec, name)

        def forward(*args, **kwargs):
            result = method(*args, **kwargs)
            self._noticed(args, kwargs)
            return self if result is self.spec else result
        # help(chart.vline) should describe the Panel method, not this wrapper.
        forward.__name__ = name
        forward.__qualname__ = f'Chart.{name}'
        forward.__doc__ = getattr(method, '__doc__', None)
        forward.__signature__ = inspect.signature(method)
        forward.__wrapped__ = method
        return forward

    def _noticed(self, args, kwargs):
        """Count series names and categories a forwarded plot method drew,
        so the legend and label rotation treat it like the chart's own marks."""
        names = kwargs.get('name')
        if isinstance(names, str):
            self._named += 1
        elif isinstance(names, (list, tuple)):
            self._named += len(names)
        if kwargs.get('orient', 'v') != 'v' or not args:
            return
        first = args[0]
        if isinstance(first, Mapping):
            first = list(first)
        if isinstance(first, (list, tuple)) and first and all(isinstance(v, str) for v in first):
            self._categories(first)

    def __repr__(self):
        steps = ', '.join(step[1] for step in self.spec._steps) or 'empty'
        return f'<inklet.Chart {steps}>'

    # The finished recipe.

    def plot(self, width=None, profile=None, rotate=False):
        """The `PlotSpec` with axes, legend and title applied, for a document cell.

        `width` (mm) and `profile` (the `Preset`) let crowded category labels
        be turned to fit.
        """
        if self._forest is not None:
            # A forest is a Diagram, built under the document's theme at compile.
            from .document.spec import component
            rows, options = self._forest
            return component(_forest_figure, rows, options, label=self.xlabel or None)
        spec = self.spec.copy()
        if self._series_tokens or self._has_tokens():
            theme = (profile or self._profile()).theme
            spec._steps = [(key, method, args, _resolve_tokens(kwargs, theme.palette, theme.paper))
                           for key, method, args, kwargs in spec._steps]
        xlabel = self.xlabel if self.xlabel is not None else self._auto_labels.get('x')
        ylabel = self.ylabel if self.ylabel is not None else self._auto_labels.get('y')
        methods = {step[1] for step in spec._steps}
        if 'axes' not in methods:
            x_options = {**self._tick_overrides.get('x', {}), **(self._tick_options(width, profile, rotate) or {})}
            y_options = dict(self._tick_overrides.get('y', {}))
            # Inner facets keep their ticks and drop the numbers beside them.
            if self.xticks is not None:
                x_options['ticks'] = tuple(self.xticks)
            if self.yticks is not None:
                y_options['ticks'] = tuple(self.yticks)
            # `minor=` is the axis option: True, or how many pieces each step divides into.
            if self.xminor is not None:
                x_options['minor'] = self.xminor
            if self.yminor is not None:
                y_options['minor'] = self.yminor
            # `format=` as the axis takes it: a '{}' spec, a suffix or a callable.
            if self.xformat is not None:
                x_options['format'] = self.xformat
            if self.yformat is not None:
                y_options['format'] = self.yformat
            if 'x' in self._hide_ticks:
                x_options['labels'] = False
            if 'y' in self._hide_ticks:
                y_options['labels'] = False
            # An empty title is no title: it should not reserve a row.
            spec.axes(x=xlabel or None, y=ylabel or None, **({'x_options': x_options} if x_options else {}),
                      **({'y_options': y_options} if y_options else {}))
        named = max(self._named, len(self._series_names))
        wants_key = named > 1 or (named and self._legend_explicit)
        if wants_key and self.legend_side == 'direct' and methods & _LABELLED_CURVES:
            # Names at the curve ends, in their colours, instead of a key.
            spec.label_lines()
        elif wants_key and self.legend_side not in (False, None, 'none') and 'legend' not in methods:
            if self.legend_side in ('auto', 'direct'):
                spec.legend()
            elif self.legend_side in ('top', 'bottom', 'left', 'right'):
                spec.legend(side=self.legend_side)
            else:
                spec.legend(corner=self.legend_side)
        if self.title:
            spec.title(self.title, align=self._title_align)
        return spec

    def document(self, rotate=frozenset()):
        """A `Document` holding this chart, sized and styled; add cells to grow it.

        `rotate` holds ids of charts whose category labels must turn.
        """
        profile = self._profile()
        doc = profile.document()
        doc.add('chart', self.plot(doc.width - 2 * doc.margin, profile, id(self) in rotate),
                min_height=self._height(doc.width))
        return doc

    def _profile(self):
        return _preset(self.width, self.style, self.palette, self.grid, self.font_pt)

    def _height(self, page_width):
        if self.height is not None:
            from .core import mm
            return mm(self.height)
        if self._forest is not None:
            # A forest is as tall as its rows, not a plot's default height.
            return None
        return round(min(max(page_width * 0.62, 45.0), 75.0), 1)

    # Helpers.

    def _categories(self, values):
        for value in values:
            if str(value) not in self._x_categories:
                self._x_categories.append(str(value))

    def _chart_list(self):
        return [self]

    def _tick_options(self, width, profile, rotate=False):
        """Turn category labels 45 degrees when they cannot fit upright.

        `rotate=True` comes from a compiled figure whose labels collided.
        Otherwise this is a measured first guess that turns only labels
        clearly wider than their slot; `compile()` catches the rest.
        """
        if rotate:
            return {'rotate': 45}
        if not self._x_categories or width is None or profile is None:
            return None
        from . import measure
        from .core import pt
        size = pt(profile.publication.small_font_pt)
        widest = max(measure(label, size=size, font=profile.theme.font_family).width
                     for label in self._x_categories)
        # The data area is the cell less the y axis; a category gets one step.
        step = max(width - 14.0, 10.0) / len(self._x_categories)
        return {'rotate': 45} if widest > 1.3 * step else None

    def _labelled(self, x, y):
        for axis, name in (('x', x), ('y', y)):
            if isinstance(name, str) and axis not in self._auto_labels:
                self._auto_labels[axis] = name
        return self

    def _has_tokens(self):
        def token(value):
            if isinstance(value, str):
                return value.startswith((_TOKEN, _TINT, _SOFT))
            return isinstance(value, (list, tuple)) and any(token(v) for v in value)
        return any(token(v) for step in self.spec._steps for v in step[3].values())

    def _token(self, label):
        """The palette slot a named series is drawn in, stable across layers.

        Resolved to a colour in `plot()`, once the preset's palette is known,
        so a line, its markers, error bars and band share one colour and a
        series named the same in two calls keeps it.
        """
        if label is None:
            return None
        if label not in self._series_tokens:
            self._series_tokens[label] = f'{_TOKEN}{len(self._series_tokens)}'
        return self._series_tokens[label]

    def _style(self, table, color, style, *, mark=False, dash=None, stroke_width=None, label=None,
               lone=False):
        """Mark options: a literal colour, the series' palette slot, or -- for
        a lone series (`lone=True`) -- the palette's lead colour, so a chart
        with one series is in colour like one with several."""
        options = dict(style)
        if label is not None:
            # Any named series earns a key entry, whether its name came from
            # a `color=` column or from `name=`.
            self._series_names.add(label)
        if (literal := _literal_color(table, color)) is not None:
            options.setdefault('color', literal)
        elif label is not None and 'color' not in options:
            options['color'] = self._token(label)
        elif lone and 'color' not in options:
            options['color'] = f'{_TOKEN}0'
        if dash is not None:
            options['stroke_dash'] = _DASHES.get(dash, dash) if isinstance(dash, str) else tuple(dash)
        if stroke_width is not None:
            options['stroke_width'] = stroke_width
        return options

    def _series(self, table, x, y, color, error_y, gaps=False):
        """[(name, xs, ys, err)], one per `color` group or per `y` column.

        Without `y`, every numeric column other than `x` is a series, as in
        `DataFrame.plot()`. `gaps` keeps rows with a missing y for `line`
        to break its path at (see `_groups`).
        """
        if y is None and table is not None:
            y = [name for name, values in table.items()
                 if name not in (x, 'index', color) and _numeric(values)]
        if y is None or (hasattr(y, '__len__') and len(y) == 0):
            raise ValueError('this chart needs y=, a column name or a sequence of values')
        ys_names = list(y) if isinstance(y, (list, tuple)) and all(isinstance(v, str) for v in y) \
            and table is not None and all(v in table for v in y) else None
        out = []
        if ys_names:
            xs = _column(table, x, 'x') if x is not None else _index(table, ys_names[0])
            for col in ys_names:
                for _, gx, gy in _groups(table, None, xs, table[col], gaps=gaps):
                    out.append((col, gx, gy, None))
            self._named += len(ys_names)
            self._labelled(x, None)
            if len(ys_names) == 1:
                self._labelled(None, ys_names[0])
            return out
        ys = _column(table, y, 'y')
        xs = _column(table, x, 'x') if x is not None else _index(table, None, len(ys))
        err = _column(table, error_y, 'error_y') if error_y is not None else None
        columns = (xs, ys) if err is None else (xs, ys, err)
        for group in _groups(table, color, *columns, gaps=gaps):
            label, gx, gy = group[0], group[1], group[2]
            out.append((label, gx, gy, group[3] if err is not None else None))
        self._named += sum(1 for item in out if item[0] is not None)
        return out

    def _samples(self, table, x, color):
        values = _column(table, x, 'x')
        if values is None:
            raise ValueError('this chart needs x=, the column of values to summarise')
        groups = {}
        for label, vals in _groups(table, color, values):
            groups[label] = vals
        self._named += sum(1 for label in groups if label is not None)
        return groups

    def _grouped(self, method, data, x, y, color, style):
        table = _table(data)
        _check_color(color)
        if y is None:
            values = _column(table, x, 'x')
            groups = {_label(x, 'values'): [v for v in values if v is not None]}
        else:
            keys = _column(table, x, 'x') if x is not None else ['all'] * len(_column(table, y, 'y'))
            groups = {}
            for key, value in zip(keys, _column(table, y, 'y')):
                if key is None or value is None:
                    continue
                groups.setdefault(str(key), []).append(value)
            groups = {str(key): groups[str(key)] for key in _in_category_order(table, x, keys)
                      if str(key) in groups}
        if style.get('orient', 'v') == 'v':
            self._categories(list(groups))
        getattr(self.spec, method)(groups, **self._style(table, color, style, lone=True))


def _forest_figure(rows, options, label=None):
    """The forest Diagram of a `Chart.forest`, drawn under the document theme."""
    from .plot.forest import forest
    return forest(rows, label=label, **options)


def _labels_collide(figure, categories) -> bool:
    """Whether the lint report has two of these category labels touching.

    Findings quote the texts they name, shortened with '...' when long.
    """
    import re
    for diagnostic in figure.lint():
        if diagnostic.code not in ('OVERLAP', 'CROWDING'):
            continue
        quoted = [q[:-3] if q.endswith('...') else q
                  for q in re.findall(r"'([^']*)'", diagnostic.message)]
        hits = [q for q in quoted if q and any(c.startswith(q) for c in categories)]
        if len(hits) >= 2:
            return True
    return False


def _tinted_shape(style, color):
    """Boxes and violins: a pale fill with edges, whiskers and median in the colour."""
    options = dict(style)
    if color is None and 'edges' not in options:
        options.setdefault('color', f'{_TINT}0')
        options['edges'] = f'{_TOKEN}0'
    elif isinstance(color, str) and color.startswith('#'):
        options.setdefault('edges', color)
    return options


def _dots(style):
    """Samples over a box or violin: small, slightly translucent points."""
    return {'size': style.get('point_size', 0.9), 'fill_opacity': 0.75}


def _marker_look(count, total):
    """Marker size and opacity by how many points share the panel.

    A handful of points can be bold; a cloud needs smaller, translucent
    markers so overlaps show as density instead of a solid blot.
    """
    if total <= 60:
        return {'size': 1.5}
    if total <= 400:
        return {'size': 1.2, 'fill_opacity': 0.8}
    return {'size': 0.8, 'fill_opacity': 0.55}


def _resolve_tokens(kwargs, palette, paper='#ffffff'):
    """Replace palette slots (`@series2`, `@tint2`) with colours, in nested values too."""
    from .themes import mix

    def resolve(value):
        if isinstance(value, str) and value.startswith(_TOKEN):
            return palette[int(value[len(_TOKEN):]) % len(palette)]
        for prefix, amount in ((_TINT, _TINT_AMOUNT), (_SOFT, _SOFT_AMOUNT)):
            if isinstance(value, str) and value.startswith(prefix):
                colour = palette[int(value[len(prefix):]) % len(palette)]
                return mix(colour, paper, amount)
        if isinstance(value, (list, tuple)):
            return type(value)(resolve(v) for v in value)
        return value
    return {key: resolve(value) for key, value in kwargs.items()}


def _index(table, column, length=None):
    if table is not None and 'index' in table and (column is None or len(table['index']) == len(table[column])):
        return table['index']
    if length is None:
        length = len(table[column])
    return list(range(length))


def _aggregate(at, heights, groups, cats, names=None):
    """Sum (or count) bar heights per category, per group."""
    if names is None:
        names = list(dict.fromkeys(g for g in groups if g is not None)) if groups is not None else [None]
    totals = {(c, g): 0.0 for c in cats for g in names}
    for index, cat in enumerate(at):
        if cat is None:
            continue
        group = groups[index] if groups is not None else None
        if groups is not None and group is None:
            continue
        value = 1.0 if heights is None else heights[index]
        if value is None:
            continue
        totals[(cat, group)] += float(value)
    series = [[totals[(c, g)] for c in cats] for g in names]
    return series, [str(n) for n in names]


def _size(size, table):
    if size is None:
        return {}
    if _is_column(table, size):
        return {'size': table[size]}
    return {'size': size}


def _domain(lim, scale):
    if lim is None:
        return 'log' if scale == 'log' else 'auto'
    if scale == 'log':
        from .plot.scale import log
        return log(tuple(lim))
    return tuple(lim)


def _check_style(style):
    """A preset name, checked at the call so a typo fails there; or a Preset object."""
    from .document import Preset, preset_names
    if isinstance(style, Preset):
        return style
    if not isinstance(style, str):
        raise TypeError(f'style must be a preset name or a Preset, not {type(style).__name__}')
    if style.strip().lower() not in preset_names():
        raise ValueError(f'unknown style {style!r}; choose one of {", ".join(preset_names())}, '
                         'or pass a Preset such as inklet.preset(...).customize(...)')
    return style


def _length(width):
    """Millimetres for a length (120, '120mm'); None for a page name or an unset width."""
    from .core import mm
    if width is None or (isinstance(width, str) and width in _WIDTHS):
        return None
    return mm(width)


def _width_mm(width):
    """A width as millimetres, whether a page name ('double') or a length."""
    from .document.presets import _FORMATS
    if isinstance(width, str) and width in _WIDTHS:
        return _FORMATS[_WIDTHS[width]].width
    return _length(width)


def _preset(width, style, palette, grid, font_pt=None):
    from .core import mm
    from .document import Preset, preset
    from .document.presets import _FORMATS
    if isinstance(style, Preset):
        # A Preset keeps its own page unless a width is asked for; a named page sets its size.
        if width is None:
            chosen = style
        elif isinstance(width, str) and width in _WIDTHS:
            page = _FORMATS[_WIDTHS[width]]
            chosen = style.customize(width=page.width, height=page.height)
        else:
            chosen = style.customize(width=mm(width))
    elif width is None:
        chosen = preset(style, format='single-column')
    elif isinstance(width, str) and width in _WIDTHS:
        chosen = preset(style, format=_WIDTHS[width])
    else:
        chosen = preset(style, format='single-column').customize(width=mm(width))
    if font_pt is not None:
        # The labels step down from the main size as the defaults do (7, 6 and 9 pt).
        chosen = chosen.customize(font_pt=font_pt, small_font_pt=round(font_pt * 6 / 7 * 2) / 2,
                                  title_font_pt=font_pt * 9 / 7)
    overrides = {}
    if palette is not None:
        overrides['palette'] = palette
    if grid is not None:
        overrides['grid'] = {True: 'both', False: 'none'}.get(grid, grid)
    return chosen.customize(**overrides) if overrides else chosen


# -- layouts ----------------------------------------------------------------


class Layout(_Renderable):
    """Charts side by side (`a | b`) or stacked (`a / b`), with panel letters.

    `Layout('grid', charts, columns=3)` fills a grid row by row; facets use it.
    A row whose charts all set a width in mm is as wide as they are, with
    gaps between; otherwise the page takes `width=`, or the first chart's.
    """

    def __init__(self, direction, items, *, width=None, style=None, letters=True, columns=None):
        if direction not in ('row', 'column', 'grid'):
            raise ValueError("layout direction is 'row', 'column' or 'grid'")
        if direction == 'grid' and not (isinstance(columns, int) and columns >= 1):
            raise ValueError('a grid layout needs columns=, a positive integer')
        self.columns = columns
        flat = []
        for item in items:
            if isinstance(item, Layout) and item.direction == direction != 'grid':
                flat.extend(item.items)
            elif isinstance(item, (Chart, Layout)):
                flat.append(item)
            else:
                raise TypeError(f'cannot lay out a {type(item).__name__}; use inklet charts')
        self.direction, self.items = direction, tuple(flat)
        self.width, self.style, self.letters = width, style, letters

    def charts(self):
        for item in self.items:
            if isinstance(item, Layout):
                yield from item.charts()
            else:
                yield item

    def _first(self):
        return next(self.charts())

    def _chart_list(self):
        return list(self.charts())

    def document(self, rotate=frozenset()):
        """A `Document` with one lettered cell per chart.

        Two levels -- rows of charts stacked, or columns side by side -- share
        one grid, so every chart gets its own letter. Deeper nesting becomes
        subfigures.
        """
        from .document import Preset
        first = self._first()
        charts = list(self.charts())
        across = self.direction != 'column' or any(
            isinstance(item, Layout) for item in self.items)
        style = self.style or first.style
        sizes = self._column_sizes()
        width = self.width
        if width is None and sizes is None:
            width = first.width
            if width is None and across and not isinstance(style, Preset):
                width = 'double'
            elif width == 'single' and across:
                width = 'double'
        if width is None and sizes is not None:
            # Each chart keeps its own width: the page is their sum and the gaps between them.
            gap = _preset(sum(sizes), style, first.palette, first.grid).gap
            width = sum(sizes) + gap * (len(sizes) - 1)
        profile = _preset(width, style, first.palette, first.grid, first.font_pt)
        # Only a chart's own width= is noticed; a width it inherits is the page's.
        if sizes is None and any(c.width is not None and abs(_width_mm(c.width) - profile.format.width) > 1e-6
                                 for c in charts):
            warnings.warn('in a layout the page width comes from Layout(width=...) or the first chart; '
                          'set widths on the layout', UserWarning, stacklevel=2)
        grid = self._grid()
        if grid is not None:
            columns, cells = grid
            # Facets share their scales, so their plot areas should line up too.
            doc = profile.document(columns=sizes if sizes is not None else columns,
                                   share_plot_margins=self.direction == 'grid')
            # Each track takes its share of the room by its column weight.
            room = doc.width - doc.gap * (columns - 1)
            tracks = [room * weight / sum(doc.columns) for weight in doc.columns]
            for index, (item, row, column, rowspan, colspan) in enumerate(cells):
                cell_width = sum(tracks[column:column + colspan]) + doc.gap * (colspan - 1)
                # A chart spanning columns keeps its row's height, not one
                # proportional to its full width.
                doc.add(f'p{index + 1}', item.plot(cell_width, profile, id(item) in rotate),
                        row=row, column=column,
                        rowspan=rowspan, colspan=colspan,
                        min_height=item._height(tracks[column]) if rowspan == 1 else None)
        else:
            doc = profile.document(columns=len(self.items) if self.direction == 'row' else 1)
            self._fill(doc, doc.width, prefix='p', profile=profile, rotate=rotate)
        if self.letters and len(list(self.charts())) > 1:
            # Beside a chart title the letter shares its line; otherwise it
            # hangs off the plot area.
            titled = any(chart.title for chart in self.charts())
            doc.letters(anchor='cell') if titled else doc.letters()
        return doc

    def _grid(self):
        """(columns, [(chart, row, column, rowspan, colspan)]) for two levels, else None."""
        if self.direction == 'grid':
            if not all(isinstance(item, Chart) for item in self.items):
                return None
            return self.columns, [(item, k // self.columns, k % self.columns, 1, 1)
                                  for k, item in enumerate(self.items)]
        groups = []
        for item in self.items:
            if isinstance(item, Chart):
                groups.append([item])
            elif all(isinstance(child, Chart) for child in item.items):
                groups.append(list(item.items))
            else:
                return None
        span = math.lcm(*(len(group) for group in groups))
        cells = []
        for outer, group in enumerate(groups):
            share = span // len(group)
            for inner, item in enumerate(group):
                if self.direction == 'column':
                    cells.append((item, outer, inner * share, 1, share))
                else:
                    cells.append((item, inner * share, outer, share, 1))
        columns = span if self.direction == 'column' else len(groups)
        return columns, cells

    def _column_sizes(self):
        """Millimetre widths of a flat row whose charts all set a length, else None.

        Such a row is laid out by its charts' own widths, as column weights.
        """
        if self.direction != 'row' or not all(isinstance(item, Chart) for item in self.items):
            return None
        sizes = [_length(item.width) for item in self.items]
        return None if any(size is None for size in sizes) else sizes

    def _fill(self, doc, width, prefix, profile=None, rotate=frozenset()):
        from .document import subfigure
        count = len(self.items)
        # A row's cells share the width in proportion to the document's column weights.
        room = width - doc.gap * (count - 1)
        for index, item in enumerate(self.items):
            name = f'{prefix}{index + 1}'
            if self.direction == 'row':
                cell_width = room * doc.columns[index] / sum(doc.columns)
            else:
                cell_width = width
            place = dict(row=0, column=index) if self.direction == 'row' else dict(row=index, column=0)
            if isinstance(item, Chart):
                doc.add(name, item.plot(cell_width, profile, id(item) in rotate),
                        min_height=item._height(cell_width), **place)
            else:
                sub = subfigure(width=cell_width, gap=doc.gap,
                                columns=len(item.items) if item.direction == 'row' else 1)
                item._fill(sub, cell_width, prefix=name + '_', profile=profile, rotate=rotate)
                doc.add(name, sub, **place)

    def __repr__(self):
        if self.direction == 'grid':
            return f'<inklet.Layout grid of {len(self.items)} charts, {self.columns} columns>'
        joiner = ' | ' if self.direction == 'row' else ' / '
        return '(' + joiner.join(repr(item) for item in self.items) + ')'


# -- top-level functions ----------------------------------------------------

_CHART_OPTIONS = ('width', 'height', 'style', 'font_pt', 'palette', 'title', 'xlabel', 'ylabel',
                  'xlim', 'ylim', 'xscale', 'yscale', 'legend', 'grid', 'xticks', 'yticks',
                  'xminor', 'yminor', 'xformat', 'yformat')


def chart(**options) -> Chart:
    """An empty chart to add marks to: `inklet.chart(title='...').line(...)`."""
    return Chart(**options)


def _split(options):
    return ({k: options.pop(k) for k in _CHART_OPTIONS if k in options}, options)


def _facet_values(values, what, name, facet_order):
    """The distinct values of one facet, in the order they are drawn.

    `facet_order` is a list, used for every facet, or a mapping from facet
    column name to a list. Without an order, numbers and dates ascend and
    anything else keeps the order it first appears in. An explicit list must
    name every value in the data; extra names that match no row are ignored.
    """
    present = list(dict.fromkeys(v for v in values if v is not None))
    order = facet_order.get(name) if isinstance(facet_order, Mapping) else facet_order
    if order is not None:
        order = list(dict.fromkeys(order))
        missing = [v for v in present if v not in order]
        if missing:
            listed = ', '.join(repr(v) for v in missing)
            raise ValueError(f'facet_order leaves out {listed} from {what}; list every value in the data')
        return [v for v in order if v in present]
    if present and all(isinstance(v, (Real, date)) and not isinstance(v, bool) for v in present):
        return sorted(present)
    return present


def _facet(method, data, args, own, rest, facet_col, facet_row, wrap, facet_order=None):
    """One chart per facet value, on shared scales, in a grid.

    Every facet is the same chart drawn from its subset of rows: same axes,
    same colour for the same group, one key. Inner panels keep their ticks
    and drop the numbers and axis titles their neighbours already show.
    """
    table = _table(data)
    if table is None:
        raise ValueError('facets need data=, a table with the facet column')
    if isinstance(facet_order, Mapping):
        unknown = [k for k in facet_order if k not in (facet_col, facet_row)]
        if unknown:
            raise ValueError(f'facet_order names {", ".join(map(repr, unknown))}, which is not '
                             'facet_col or facet_row')
    rows_by = _column(table, facet_row, 'facet_row') if facet_row else None
    cols_by = _column(table, facet_col, 'facet_col') if facet_col else None
    row_values = (_facet_values(rows_by, 'facet_row', facet_row, facet_order)
                  if rows_by else [None])
    col_values = (_facet_values(cols_by, 'facet_col', facet_col, facet_order)
                  if cols_by else [None])
    if facet_row and facet_col:
        cells, columns = [(r, c) for r in row_values for c in col_values], len(col_values)
    elif facet_col:
        cells = [(None, c) for c in col_values]
        columns = wrap or min(len(col_values), 4)
    else:
        cells, columns = [(r, None) for r in row_values], 1
    color = rest.get('color')
    groups = ([str(v) for v in _in_category_order(table, color, table[color])]
              if _is_column(table, color) else [])
    charts = []
    for row_value, col_value in cells:
        keep = [(rows_by is None or rows_by[k] == row_value) and
                (cols_by is None or cols_by[k] == col_value) for k in range(len(next(iter(table.values()))))]
        subset = _Table({name: [v for v, k in zip(values, keep) if k] for name, values in table.items()})
        subset.orders = getattr(table, 'orders', {})
        # A bare number says nothing; name the column it came from.
        title = ' · '.join(v if isinstance(v, str) else f'{name} = {v}'
                           for name, v in ((facet_row, row_value), (facet_col, col_value))
                           if v is not None)
        chart = Chart(**{**own, 'title': title})
        chart._title_align = 'center'
        # The same group keeps its colour in every facet, even where absent.
        chart._series_tokens = {g: f'{_TOKEN}{k}' for k, g in enumerate(groups)}
        getattr(chart, method)(subset, *args, **rest)
        charts.append(chart)
    _share_domains(charts, own)
    count = len(charts)
    for index, chart in enumerate(charts):
        column = index % columns
        below = index + columns < count
        if column:
            chart._hide_ticks.add('y')
            chart.ylabel = ''
        if below:
            chart._hide_ticks.add('x')
            chart.xlabel = ''
        if index != min(columns, count) - 1:
            chart.legend_side = False
    return Layout('grid', charts, columns=columns, letters=False, width=own.get('width'))


def _share_domains(charts, own):
    """Set every facet's axes to the union of all their data."""
    from .plot.autodomain import measure
    from .plot.scale import log as log_scale
    steps = []
    neutral = ('#000000',)
    for chart in charts:
        for _, method, args, kwargs in chart.spec._steps:
            steps.append((method, args, _resolve_tokens(kwargs, neutral)))
    x, y = measure(steps, 60, 40)
    for name, axis, lim, scale in (('x', x, 'xlim', own.get('xscale', 'linear')),
                                   ('y', y, 'ylim', own.get('yscale', 'linear'))):
        if own.get(lim) is not None:
            continue
        domain = axis.domain(scale=scale)
        if domain is None:
            continue
        value = log_scale(domain) if scale == 'log' else domain
        for chart in charts:
            if chart.spec.options.get(name) in ('auto', 'log'):
                chart.spec.configure(**{name: value})


_FACET_OPTIONS = ('facet_col', 'facet_row', 'facet_col_wrap', 'facet_order')

#: The Panel methods each one-call function hands its extra keywords to. A
#: keyword none of them takes is refused at the call, not by Style at compile.
_FORWARDS = {
    'line': ('line',), 'scatter': ('scatter',), 'bar': ('bars', 'barplot'),
    'hist': ('hist',), 'kde': ('kde',), 'ecdf': ('ecdf',),
    'boxplot': ('boxplot', 'strip'), 'violin': ('violin', 'strip'), 'strip': ('strip',),
    'area': ('fill_between', 'stackarea'), 'regression': ('regression',),
    'heatmap': ('matrix',), 'survival': ('kaplan_meier',), 'volcano': ('volcano',),
}

#: A plain sequence where a table belongs, with the call that takes it.
_BARE_EXAMPLE = {'hist': 'x=[1, 2, 3]', 'kde': 'x=[1, 2, 3]', 'ecdf': 'x=[1, 2, 3]',
                 'survival': 'time=[5, 8, 12], event=[1, 0, 1]',
                 'forest': 'label=[...], estimate=[...], lower=[...], upper=[...]'}


def _accepted_options(method) -> tuple[set[str], set[str]]:
    """What a one-call function takes -- its own keywords, the chart's and the
    marks' -- and the old spellings among them, which are taken but not listed."""
    from .plot.forest import forest as forest_plot
    from .plot.panel import Panel
    kinds = (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    names = {p.name for p in inspect.signature(getattr(Chart, method)).parameters.values()
             if p.kind in kinds}
    names -= {'self', 'data'}
    names |= set(_CHART_OPTIONS) | set(_FACET_OPTIONS)
    targets = [forest_plot] if method == 'forest' else [
        getattr(Panel, name) for name in _FORWARDS.get(method, ())]
    old = set()
    for target in targets:
        # Keyword-only parameters are the ones a chart passes by name; the rest
        # are the data it passes by position.
        names |= {p.name for p in inspect.signature(target).parameters.values()
                  if p.kind is inspect.Parameter.KEYWORD_ONLY}
        old |= set(getattr(target, '__deprecated_keywords__', {}))
    return names | old, old


def _check_options(method, options) -> None:
    """Refuse a keyword no one-call function takes, listing the ones it does."""
    from .plot.paint import is_paint, keyword_hint
    accepted, old = _accepted_options(method)
    unknown = [k for k in options if k not in accepted and not is_paint(k)]
    if not unknown:
        return
    hints = []
    for key in unknown:
        better = keyword_hint(key, accepted - old)
        hints.append(f'{key}= (did you mean {better}=?)' if better else f'{key}=')
    plural = 's' if len(unknown) > 1 else ''
    raise TypeError(f"{method}() got unknown option{plural} {', '.join(hints)}; it accepts "
                    f"{', '.join(sorted(accepted - old))}, and paint keywords such as stroke=, "
                    "fill=, opacity=")


def _entry(method):
    def make(data=None, *args, **options):
        facet_col = options.pop('facet_col', None)
        facet_row = options.pop('facet_row', None)
        wrap = options.pop('facet_col_wrap', None)
        facet_order = options.pop('facet_order', None)
        own, rest = _split(options)
        if _bare_values(data) and method != 'heatmap':
            example = _BARE_EXAMPLE.get(method, 'x=[...], y=[...]')
            raise TypeError(f'i.{method}() needs data= to be a table (a DataFrame, a mapping '
                            f'of columns or a list of records); pass a plain sequence as a '
                            f'named argument instead, e.g. i.{method}({example})')
        _check_options(method, rest)
        if facet_col is not None or facet_row is not None:
            return _facet(method, data, args, own, rest, facet_col, facet_row, wrap, facet_order)
        if facet_order is not None:
            raise ValueError('facet_order= orders facet values, so it needs facet_col= or facet_row=')
        if method == 'scatter' and 'palette' in own and _is_column(_table(data), rest.get('color')):
            rest['palette'] = own['palette']
        if method == 'heatmap' and 'palette' in own:
            rest['palette'] = own.pop('palette')
        return getattr(Chart(**own), method)(data, *args, **rest)
    make.__name__ = method
    make.__qualname__ = method
    make.__doc__ = (getattr(Chart, method).__doc__ or '') + '''

    Chart options: width ('single', 'double', 'slide' or mm), height (mm),
    style (a preset name, default 'scientific.modern', or a Preset object),
    font_pt (the main type size in points), palette, title, xlabel, ylabel,
    xlim, ylim, xscale/yscale ('linear' or 'log'), legend
    ('auto', 'direct', a side, a corner or False), grid (True, False, 'x' or
    'y'), xticks/yticks (the tick values to show), xminor/yminor (True, or
    how many minor-tick pieces each major step divides into), xformat/yformat
    (how the tick numbers are written: a '{}' spec such as '{:.0%}', a suffix
    such as '%', or a callable).
    Facets: `facet_col=` / `facet_row=` name columns to split into a grid
    of charts on shared axes; `facet_col_wrap=` sets the columns per row.
    `facet_order=` lists the facet values in the order they are drawn: a
    list for every facet, or a dict of column name to list when both
    facets are set. Numbers and dates default to ascending, text to first
    appearance; an explicit list must name every value.
    Returns a `Chart` (a `Layout` when faceted); call `.save('figure.pdf')`.
    '''
    return make


line = _entry('line')
scatter = _entry('scatter')
bar = _entry('bar')
hist = _entry('hist')
boxplot = _entry('boxplot')
violin = _entry('violin')
strip = _entry('strip')
kde = _entry('kde')
ecdf = _entry('ecdf')
area = _entry('area')
heatmap = _entry('heatmap')
regression = _entry('regression')
survival = _entry('survival')
volcano = _entry('volcano')
forest = _entry('forest')
