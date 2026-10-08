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
| `i.line(df, x, y, color=)` | `y` may be a list of columns; no `y` plots every numeric column; points are joined in x order (`sort=False` keeps row order) | `markers=True`, `error_y='col'` draws a band, `dash='dashed'`, `linewidth=` (mm); a missing y breaks the line there (`gaps='bridge'` joins across the gap instead); `secondary_y='col'` puts series on a right-hand axis (see below) |
| `i.scatter(df, x, y, color=, size=)` | numeric `color` column with many values gets a colour ramp and colour bar | `error_y='col'`, `text='col'` labels points clear of the marks (blank or missing labels are skipped); `secondary_y='group'` puts a colour group on the right |
| `i.bar(df, x, y, color=)` | `x` categories; rows with the same `x` are summed; no `y` counts rows | `agg='mean'` with `error_y='sem'`/`'sd'`/`'ci95'` and `points=True`; `stacked=True`, `orient='h'` |
| `i.hist(df, x, color=, bins=20)` | | `density=True`, `cumulative=True` |
| `i.kde(df, x, color=)` / `i.ecdf(df, x, color=)` | | `fill=True` on kde |
| `i.boxplot(df, x, y)` / `i.violin(df, x, y)` / `i.strip(df, x, y)` | `x` category column, `y` values | `points=True` overlays the samples |
| `i.area(df, x, y, color=)` | `y` may be a list of columns; groups stack (values must be >= 0) | `stacked=False` overlays |
| `i.regression(df, x, y, color=)` | points + fitted line + confidence band | `method='linear'` or `'lowess'`; `equation=True` writes `y = 0.500x + 3.00, R^{2} = 0.667` on the plot, one per group in its colour; `chart.fits[group]` is each group's `LinearFit` (slope, intercept, r, r2, p, `slope_interval()`), known before save |
| `i.heatmap(rows, x=col_labels, y=row_labels)` | or a long table: `i.heatmap(df, x=, y=, z=)` | first row is drawn at the top; `palette='viridis'`; diverging `palette='rdbu'` (also `'brbg'`, `'piyg'`, `'rdylbu'`, `'spectral'`) with `center=0`; `colorbar_title='log2 FC'` names the bar, `colorbar=False` drops it |
| `i.survival(df, time=, event=, color=)` | Kaplan-Meier curves, one per group; `event` is 1/True for an event, 0/False for censored | `at_risk=True` table, `pvalue=True` log-rank P for 2+ groups, `band='log-log'`; survival runs 0 to 1 |
| `i.volcano(df, x=, y=)` | `x` log2 fold change, `y` raw p-value | `label='col'` and `highlight=['name', ...]`, `q='col'` adjusted p colours by FDR |
| `i.quick.forest(df, label=, estimate=, lower=, upper=)` | one row per study with its interval | `weight='col'` sizes the squares (all equal without it); `summary='col'` for diamonds, `log=True`, `right=['ci', 'n']`; `i.forest(rows)` is a different function, the rows-list diagram |
| `i.pie(df, names=, values=)` | one slice per row, sized by `values`, labelled with shares | `hole=0.5` for a donut (a fraction of the radius); `legend='bottom'` or False, not a corner; `labels='value'` or a format |
| `i.lollipop(df, x=, y=)` | one dot per category on a stem from zero | `orient='h'` lays it across, rows top to bottom; `color=` is one colour; one row per category |
| `i.dumbbell(df, y=, x=['before', 'after'])` | two dots per category joined by a line; `y` the category, `x` the two value columns | the legend names the dots after the columns; rows top to bottom; a missing value draws no dot |
| `i.waterfall(df, x=, y=)` | changes as bars on a running total | `totals=['Start', 'End']` steps stand from zero; a missing change on a total shows the running total; `ylim=` overrides the fitted range |
| `i.slope(df, x=, y=, group=)` | each group's values at two or more time points, joined | `labels='both'` names the lines at their ends (no key); `format='{:.0f}%'`; `highlight=['name']` |

`color=` that is not a column name is a literal colour: `color='#c1121f'`.

PNG output is at the preset's resolution: 300 dpi for print presets, 150 for
slides. For more, pass `chart.save('fig.png', dpi=600)`. SVG and PDF are
vector and ignore `dpi`, except a rasterised scatter layer, which is embedded
at the preset's dpi.

Big tables need no options. A scatter panel with more than 20,000 points is
drawn as one raster image of its markers (`raster=None` is the default;
`raster=True` or `False` overrides it); axes, labels and key stay vector, and
dashed marker outlines stay vector. A line thins itself with `simplify='auto'`
(drops points within 0.02 mm of the kept line, only past 40 points per mm of width);
`simplify=None` keeps every point, and a number is a tolerance in mm.

Chart options, accepted by every function above:

| Option | Values |
|---|---|
| `width` | `'single'` (89 mm, default), `'double'` (183 mm), `'slide'` (254 mm), or millimetres (`120`, `'120mm'`); unset, a Preset keeps its own page |
| `height` | millimetres; default is about 0.62 x width, 45-75 mm. With `aspect=`, the default follows the width instead |
| `style` | preset name: `'scientific.modern'` (default: colour-led marks, grey axes), `'scientific.general'`, `'scientific.nature'`, `'scientific.science'`, `'scientific.cell'`, `'educational.textbook'`, `'marketing.report'`, `'marketing.presentation'`; or a Preset object, e.g. `i.preset('scientific.modern').customize(font_pt=12)` |
| `font_pt` | the main type size in points; ticks and the key take 6/7 of it and titles 9/7 |
| `palette` | `'okabe-ito'`, `'tol-bright'`, `'tol-muted'`, `'inklet'`, `'set2'`, `'dark2'`... or a list of colours |
| `title`, `xlabel`, `ylabel` | axis titles default to the raw column names, so set them for a publication. `xlabel` is always the horizontal axis, also with `orient='h'` (where it names the values) |
| `xlim`, `ylim` | `(low, high)`; default fits the data. Explicit limits zoom: marks are cut at the axes |
| `xscale`, `yscale` | `'linear'` or `'log'` |
| `legend` | `'auto'` (default), `'direct'` (names at the line ends, no key), `'top'`, `'bottom'`, `'left'`, `'right'`, a corner `'ne'`, or `False` |
| `facet_col`, `facet_row` | column names: one chart per value, on shared axes, in a grid; `facet_col_wrap=3` wraps |
| `facet_order` | the facet values in draw order: a list for every facet, or a dict of column name to list. Default: numbers and dates ascending, text in first-appearance order; a list must name every value |
| `grid` | `True`, `False`, `'x'`, `'y'` |
| `xticks`, `yticks` | the tick values to show, e.g. `xticks=[0, 5, 10, 15, 20]` |
| `xminor`, `yminor` | `True` for unlabelled minor ticks, or an integer: how many pieces each major step divides into |
| `xformat`, `yformat` | how tick numbers are written, as the axis `format=`: a `'{}'` spec such as `'{:.0%}'` or `'{:,.0f}'`, a suffix such as `'%'`, or a callable. Not for `forest` |
| `aspect` | `'equal'` makes one data unit the same length on x and y (maps, equal-scale plots); a number is the plot area's height over its width. The plot is the largest of that shape inside its cell, centred, and `height` caps it. `'equal'` needs linear scales. Not for `forest` |

## Layering and annotating

Mark methods (`line`, `scatter`...) take the same arguments as the functions.
Every chart method changes the chart in place and returns it, so calls chain:

```python
chart = i.scatter(df, x='dose', y='response', color='strain')
chart.line(fit, x='dose', y='predicted', color='#444444', name='model')
chart.hline(0.5, label='EC50')                     # any Panel method works on a chart
chart.annotate(3.0, 0.9, 'saturation')             # text placed clear of the data
chart.labels(x='Dose / mg kg^{-1}', y='Response', title='Dose response')
chart.save('dose.pdf')
```

| Method | Use |
|---|---|
| `hline(y, label=)`, `vline(x, label=)` | rule at a data value; `span=(lo, hi)` limits it; `label_side=` |
| `hspan(y0, y1)`, `vspan(x0, x1)` | shaded stripe between two data values |
| `annotate(x, y, text, side=)` | callout on a data point, with a leader; `dot=True` marks the point |
| `text(x, y, content)` | words at a data point; `decorative=True` skips the contrast check |
| `bracket(a, b, '***')` | significance bracket between two categories; `text=` also works |
| `brackets([(a, b, p), ...])` | several at once, stacked clear; `format='p'` writes P values; `hide_ns=True` drops "ns" |
| `band(x, lo, hi)`, `fill_between(x, y0, y1)` | shaded envelope between two curves |
| `label_points(points, labels)`, `label_lines()` | name points, or each curve at its end, instead of a key |
| `labels(x=, y=, title=, y2=)` | axis titles and the chart title |
| `legend(corner=, side=, title=)` | the key; updates the one already drawn |
| `colorbar(title=, side=)` | the bar of a heatmap or numeric scatter; a chart without one raises |
| `size(width=, height=)` | set the size after creation |
| `spec` | the PlotSpec under the chart; every other `Panel` method |

`grid` and `title` are options (`grid=True`, `labels(title=)`), not methods:
`chart.grid(...)` raises TypeError. `help(chart.vline)` shows a method's
arguments; `help(i.Chart.vline)` raises AttributeError, so use `help(i.Panel.vline)`
for the signature without a chart.

Text markup: `**bold**`, `//italic//`, `x^{2}`, `H_{2}O`, `{#c1121f|coloured}`.
There is no `$...$` math: write Unicode (`α`, `µm`) or that markup instead.

Two quantities in different units go on one chart with `secondary_y=`, a
column or a list of them (for `scatter`, colour groups):
`i.line(df, x='month', y=['rain', 'temp'], secondary_y='temp')`. That series
is drawn against a right-hand axis titled `temp`, in its colour when it is the
only series there, and the left axis fits only the rest. `labels(y2=)` retitles
the right axis. Two charts or small multiples are often clearer than two y
scales, so use it only when the quantities must share one x axis. A bar chart
with a line on the right is two calls: `i.bar(df, x, y='rain')`, then
`.line(df, x, y='temp', secondary_y='temp')` on the same chart.

`hline(y, label=)` and `vline(x, label=)` name a reference line at its end, and
the label is placed clear of the data: it is searched along the line and off
every mark on the panel, including marks drawn after the rule, so it does not
land on a bar. A labelled rule is drawn in front of the data (`front=True`
unless you say otherwise), because a line under a bar chart cannot be seen.
`label_side=` keeps the label to one side: `'n'` or `'s'` for an hline, `'e'`
or `'w'` for a vline.

## Small multiples

```python
i.line(df, x='time', y='signal', color='drug', facet_col='cell_line')          # one panel per cell line
i.scatter(df, x='dose', y='response', facet_row='replicate', facet_col='strain')
```

Facets share both axes, keep one colour per group across panels, show one key,
and drop repeated tick numbers and axis titles on inner panels.

## Multi-panel figures

`|` puts charts side by side, `/` stacks them. Panels get letters a, b, c...
(a chart title of just `'a'` doubles the letter; `i.Layout(..., letters=False)` turns them off).

```python
fig = (i.line(df, x='t', y='y') | i.boxplot(df, x='group', y='y')) / i.hist(df, x='y')
fig.save('figure1.pdf', 'figure1.png')
```

A row defaults to double-column width. Set the layout width with
`i.Layout('row', [a, b], width='double')` when building one explicitly.
If every chart in a row sets its width in millimetres, the row is as wide as
they are together, with the gaps between them, and each panel keeps its width:
`(i.line(df, x='t', y='y', width=60) | i.bar(df, x='g', y='v', width=120))` is
186 mm. A chart width the layout cannot use (a different page width on a
stacked layout, say) raises a `UserWarning`; set widths on the layout instead.

Figure options. `style`, `font_pt` and `grid` apply to the whole figure.
Set them on the layout, `i.Layout('row', [a, b], style='scientific.nature')`,
or after the fact with `fig.options(font_pt=8, grid=True)`, which returns the
layout. Left unset, the charts decide: charts that agree use their value, and
charts that disagree raise one `UserWarning` per setting, naming the values,
and the first chart's value is used. Palettes are per panel: each chart's own
`palette=` colours its own series, a palette set on the layout
(`fig.options(palette='okabe-ito')`) overrides them all, and a chart without
one takes the figure's (the first chart's). A series name keeps its palette
slot across the panels, so `'control'` is the same colour in every panel that
draws it, provided the panels share a palette.

## A figure for a slide

`width='slide'` makes a 254 mm page, and its labels are 14 pt by default, so the
figure reads from the back of a room without other changes:

```python
chart = i.line(df, x='time', y='signal', color='condition', width='slide')
chart.save('slide.png')
```

For a presentation's look, with larger titles and labels (20 pt), use
`style='marketing.presentation'`. To choose the size, pass `font_pt=`: the
labels are that many points, with ticks and the key at 6/7 of it, so
`font_pt=16` reads larger than the default on a slide. A slide page is 254 x 143 mm,
which fits a 16:9 slide, so put the image in at its own size.

## Check the result (do this every time)

1. `figure = chart.save('fig.png')` returns the compiled figure.
   `print(figure.report())` lists overlapping labels, clipped or tiny text, and
   data running outside the axes (`DATA_OUTSIDE`, with the range to set), a key
   drawn over data (`KEY_COVERS_DATA`, with the corners that are clear), and
   supplied ticks dropped for lack of room (`TICKS_DROPPED`), and a series
   squashed flat beside a much taller one on the same axis
   (`SERIES_FLATTENED`, with the axis to give it), each with a
   suggested fix. `inklet lint: clean` means no problems. Mark ornamental text
   such as a pale watermark with `text(..., decorative=True)` so the contrast
   check skips it.
2. Look at the PNG. If you can view images, open it. Labels are measured, so
   overlaps are rare. Check that the right data are plotted, not just that it ran.
   A passing check is not a visual check.
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

- `i.from_matplotlib(fig)` redraws a matplotlib figure's data as Inklet charts,
  in Inklet's type and layout. Matplotlib's default colour cycle becomes the
  Inklet palette unless `keep_colors=True`; colours set explicitly are kept.
  What it does not carry (hatches, RGB images, figure-level text, twin axes,
  inset axes, and more) is listed in a `MatplotlibWarning`;
  `docs/matplotlib.md` has the full list.

## Common mistakes

- `i.box` is a diagram box, not a box plot. Use `i.boxplot`.
- Bars **sum** rows that share an `x` value. For a mean with an error bar use
  `i.bar(df, x='group', y='value', agg='mean', error_y='sem', points=True)`.
- `area` stacks; stacked values must be non-negative.
- `$...$` is not mathtext: `$\alpha$` prints the dollar signs. Use Unicode
  (`α`, `x²`) or markup (`x^{2}`, `H_{2}O`).
- `i.brackets` does not exist; significance brackets are `chart.brackets([...])`.
- `chart.twin_y(...)` is refused on a quick chart. For a second y scale use
  `secondary_y=`, as above.
- Do not call `plt.show()`-style display code; save files and inspect them.
- In the full model, `plot_spec(x=..., y=...)` does **not** clip: data past
  the domain are drawn outside the axes and reported as `DATA_OUTSIDE`. Leave
  `x`/`y` out to fit the data, or pass `clip=True`.
