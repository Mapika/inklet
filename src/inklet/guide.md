# Inklet: plotting guide for coding agents

Inklet makes publication figures in Python: plots sized in millimetres, text
measured so nothing overlaps, and SVG/PDF/PNG output that needs no hand fixing.
Use it like plotly express: one call per chart, columns named by string.

## One chart

```python
import inklet as i

chart = i.line(df, x='time', y='signal', color='condition')   # color= groups by a column
chart.save('signal.pdf', 'signal.png')                          # extension picks the format
```

`df` may be a pandas or Polars DataFrame, a dict of columns, a list of row
dicts, or a path to a CSV/TSV file (`i.line('results.csv', x=..., y=...)`).
Instead of a table, pass sequences: `i.line(x=[1, 2, 3], y=[2, 4, 3])`.

| Function | Columns | Notes |
|---|---|---|
| `i.line(df, x, y, color=)` | `y` may be a list of columns; no `y` plots every numeric column; points are joined in x order (`sort=False` keeps row order) | `markers=True`, `error_y='col'` draws a band, `dash='dashed'`, `linewidth=` (mm) |
| `i.scatter(df, x, y, color=, size=)` | numeric `color` column with many values gets a colour ramp and colour bar | `error_y='col'`, `text='col'` labels points clear of the marks |
| `i.bar(df, x, y, color=)` | `x` categories; rows with the same `x` are summed; no `y` counts rows | `agg='mean'` with `error_y='sem'`/`'sd'`/`'ci95'` and `points=True`; `stacked=True`, `orient='h'` |
| `i.hist(df, x, color=, bins=20)` | | `density=True`, `cumulative=True` |
| `i.kde(df, x, color=)` / `i.ecdf(df, x, color=)` | | `fill=True` on kde |
| `i.boxplot(df, x, y)` / `i.violin(df, x, y)` / `i.strip(df, x, y)` | `x` category column, `y` values | `points=True` overlays the samples |
| `i.area(df, x, y, color=)` | groups stack (values must be >= 0) | `stacked=False` overlays |
| `i.regression(df, x, y, color=)` | points + fitted line + confidence band | `method='linear'` or `'lowess'` |
| `i.heatmap(rows, x=col_labels, y=row_labels)` | or a long table: `i.heatmap(df, x=, y=, z=)` | first row is drawn at the top; `palette='viridis'` |
| `i.survival(df, time=, event=, color=)` | Kaplan-Meier curves, one per group; `event` is 1/True for an event, 0/False for censored | `at_risk=True` table, `pvalue=True` log-rank P for 2+ groups, `band='log-log'`; survival runs 0 to 1 |
| `i.volcano(df, x=, y=)` | `x` log2 fold change, `y` raw p-value | `label='col'` and `highlight=['name', ...]`, `q='col'` adjusted p colours by FDR |
| `i.quick.forest(df, label=, estimate=, lower=, upper=)` | one row per study with its interval | `weight='col'`, `summary='col'` for diamonds, `log=True`, `right=['ci', 'n']`; `i.forest(rows)` is the rows-list diagram |

`color=` that is not a column name is a literal colour: `color='#c1121f'`.

Chart options, accepted by every function above:

| Option | Values |
|---|---|
| `width` | `'single'` (89 mm, default), `'double'` (183 mm), `'slide'`, or millimetres (`120`, `'120mm'`) |
| `height` | millimetres; default is about 0.62 x width, 45-75 mm |
| `style` | preset: `'scientific.modern'` (default: colour-led marks, grey axes), `'scientific.general'`, `'scientific.nature'`, `'scientific.science'`, `'scientific.cell'`, `'educational.textbook'`, `'marketing.report'`, `'marketing.presentation'` |
| `palette` | `'okabe-ito'`, `'tol-bright'`, `'tol-muted'`, `'inklet'`, `'set2'`, `'dark2'`... or a list of colours |
| `title`, `xlabel`, `ylabel` | axis titles default to the column names |
| `xlim`, `ylim` | `(low, high)`; default fits the data. Explicit limits zoom: marks are cut at the axes |
| `xscale`, `yscale` | `'linear'` or `'log'` |
| `legend` | `'auto'` (default), `'direct'` (names at the line ends, no key), `'top'`, `'bottom'`, `'left'`, `'right'`, a corner `'ne'`, or `False` |
| `facet_col`, `facet_row` | column names: one chart per value, on shared axes, in a grid; `facet_col_wrap=3` wraps |
| `facet_order` | the facet values in draw order: a list for every facet, or a dict of column name to list. Default: numbers and dates ascending, text in first-appearance order; a list must name every value |
| `grid` | `True`, `False`, `'x'`, `'y'` |
| `xticks`, `yticks` | the tick values to show, e.g. `xticks=[0, 5, 10, 15, 20]` |
| `xminor`, `yminor` | `True` for unlabelled minor ticks, or an integer: how many pieces each major step divides into |

## Layering and annotating

Chart methods have the same names and arguments as the functions; each returns
the chart so calls chain:

```python
chart = i.scatter(df, x='dose', y='response', color='strain')
chart.line(fit, x='dose', y='predicted', color='#444444', name='model')
chart.hline(0.5, label='EC50')                     # any Panel method works on a chart
chart.annotate(3.0, 0.9, 'saturation')             # text placed clear of the data
chart.labels(x='Dose / mg kg^{-1}', y='Response', title='Dose response')
chart.save('dose.pdf')
```

Text markup: `**bold**`, `//italic//`, `x^{2}`, `H_{2}O`, `{#c1121f|coloured}`.

## Small multiples

```python
i.line(df, x='time', y='signal', color='drug', facet_col='cell_line')          # one panel per cell line
i.scatter(df, x='dose', y='response', facet_row='replicate', facet_col='strain')
```

Facets share both axes, keep one colour per group across panels, show one key,
and drop repeated tick numbers and axis titles on inner panels.

## Multi-panel figures

`|` puts charts side by side, `/` stacks them. Panels get letters a, b, c...

```python
fig = (i.line(df, x='t', y='y') | i.boxplot(df, x='group', y='y')) / i.hist(df, x='y')
fig.save('figure1.pdf', 'figure1.png')
```

A row defaults to double-column width. Set the layout width with
`i.Layout('row', [a, b], width='double')` when building one explicitly.

## Check the result (do this every time)

1. `figure = chart.save('fig.png')` returns the compiled figure.
   `print(figure.report())` lists overlapping labels, clipped or tiny text, and
   data running outside the axes (`DATA_OUTSIDE`, with the range to set), a key
   drawn over data (`KEY_COVERS_DATA`, with the corners that are clear), and
   supplied ticks dropped for lack of room (`TICKS_DROPPED`), each with a
   suggested fix. `inklet lint: clean` means no problems. Mark ornamental text
   such as a pale watermark with `text(..., decorative=True)` so the contrast
   check skips it.
2. Look at the PNG. If you can view images, open it. Labels are measured, so
   overlaps are rare. Check that the right data are plotted, not just that it ran.
3. From a shell: `inklet check script.py --png preview.png` builds the script,
   prints the report, writes a preview, and exits 1 when there are errors
   (`--strict` also fails on warnings, `--json` gives machine-readable output).

A script that `check` or `build` loads supplies its figure one of two ways.
Define `make_document()`, `make_figure()` or `make_chart()` and return the
figure; the first one defined, in that order, is called. Or leave a Document,
Chart, Layout, CompiledFigure or Figure at module level. The figure is chosen
by type, so other module-level values (a matplotlib `fig`, a DataFrame) are
ignored. Name the figure `chart`, `doc`, `fig` or `figure` (first match wins)
when the script has several inklet objects. With no such name, the only inklet
object is used. Two unnamed ones are an error, and so is a script with none;
the error lists the module-level names it found.

`chart.show()` displays inline in Jupyter; outside a notebook it writes an SVG
and returns its path. Nothing opens a window or blocks, so scripts run headless.

## Units

Every length is millimetres: `width=120` is 120 mm. Font sizes are points
via `i.pt(8)`. Text is never shrunk to make things fit; if a figure is too
crowded, inklet reports it rather than drawing overlapping labels.

## Going further

A chart is a front end to the document model. When you need more control:

```python
spec = chart.spec               # the PlotSpec; any Panel method records on it
doc = chart.document()          # a Document with the chart in cell 'chart'
doc.add('diagram', i.box('Encoder'))   # add any other content
doc.compile().save('full.pdf')
```

The full model, which the quick API wraps:

```python
doc = i.preset('scientific.nature', format='double-column').document(columns=2)
plot = i.plot_spec()                       # axes fit the data; or x=(0, 10), y=(0, 1)
plot.line([(0, 1), (1, 3), (2, 2)], name='Signal')     # points are (x, y) rows
plot.scatter([(0, 1.2), (1, 2.8)], name='Samples')
plot.axes(x='Time / s', y='Signal / mV').legend()
doc.add('a', plot)
doc.add('b', other_plot, column=1, row=0)
doc.letters()
figure = doc.compile()
print(figure.report())
figure.save('figure.pdf')
```

`inklet guide --api` prints every plot method (more than 100: forest, volcano,
manhattan, survival curves, ridgelines, raincloud, sankey, upset, treemap,
networks, ternary...) with its signature.

## Common mistakes

- `i.box` is a diagram box, not a box plot. Use `i.boxplot`.
- Bars **sum** rows that share an `x` value. For a mean with an error bar use
  `i.bar(df, x='group', y='value', agg='mean', error_y='sem', points=True)`.
- `area` stacks; stacked values must be non-negative.
- Do not call `plt.show()`-style display code; save files and inspect them.
- In the full model, `plot_spec(x=..., y=...)` does **not** clip: data past
  the domain are drawn outside the axes and reported as `DATA_OUTSIDE`. Leave
  `x`/`y` out to fit the data, or pass `clip=True`.
