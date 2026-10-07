# Bring matplotlib figures

`i.from_matplotlib()` reads what a matplotlib figure plots and redraws it as
Inklet charts. Your plotting code stays as it is; the result gets Inklet's
print-sized type, measured layout, aligned panels and panel letters.

```python
import matplotlib.pyplot as plt
import inklet as i

fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 2.8))
left.plot(times, signal, label='treated')
left.fill_between(times, lower, upper, alpha=0.25)
right.bar(groups, means, yerr=errors)
...
i.from_matplotlib(fig).save('figure.pdf')
```

The matplotlib figure, as matplotlib draws it:

![A matplotlib figure with a time course and a bar chart](assets/examples/mpl-bridge-before.png)

The same figure object after `i.from_matplotlib(fig)`:

![The same data redrawn by Inklet at double-column width with panel letters](assets/examples/mpl-bridge-after.svg)

The bridge reads data, not pixels. Every mark is vector output and the
result is an ordinary [chart](quick-charts.md) or layout. You can add marks,
change the preset or check the report like any other chart.

## What carries over

| matplotlib | Inklet |
|---|---|
| `plot` (lines, markers, `markevery`, dashes) | `line` and `scatter` |
| `scatter` (sizes, colours, `c=` with a colormap) | `scatter`, with a colour ramp and bar |
| `bar` / `barh` / `hist` | `bars` |
| `errorbar`, `bar(yerr=)` | `errorbars` with the series' line and markers |
| `fill_between` | `band` |
| `axhline` / `axvline` | `hline` / `vline` |
| `imshow` | `matrix` with a colour bar |
| `text`, `annotate` (data coordinates) | `text`, `annotate` |
| Axis labels, title, log scales, explicit limits, categorical ticks, legend | Chart options |
| A grid of subplots | A layout with panel letters |

matplotlib's automatic colour cycle (`C0`, `C1`, ...) maps onto the preset
palette slot by slot, so series that shared a colour still share one. Colours
you set explicitly are kept. Pass `keep_colors=True` to keep the cycle
colours as well.

The width follows the matplotlib figure, snapped to a single (89 mm) or
double (183 mm) column when it is close to one. Pass `width=` to override it,
and `style=` or `palette=` to choose a [preset](presets.md) or
[palette](palettes.md).

## What does not

Artists the bridge cannot read are not dropped silently. They are listed in a
`MatplotlibWarning` and on each chart's `skipped` list. These include patches
other than bars, text placed in axes or figure coordinates, polygons that are
not a band between two curves, and non-linear scales other than log. Colorbar
axes are recognised and replaced by Inklet colour bars.
