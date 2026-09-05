# Plotting

Use `plot_spec()` inside a live document. Its methods record the same marks and
furniture as the direct `Panel` API; the compiler then fits the plot to its cell.

## Scales and coordinates

Pass numeric domains such as `x=(0, 10)`, explicit scales such as
`x=i.log((1, 1000))`, or category lists such as `x=['Control', 'Treatment']`.
Cartesian y increases upward. A categorical y scale places its first category
at the bottom; reverse the category list for top-to-bottom reading.

```python
import inklet as i

p = i.plot_spec(x=(0, 3), y=(0, 5), clip=True)
p.line([(0, 1), (1, 3), (2, 2), (3, 4)], name='Signal', stroke='#176b9b')
p.scatter([(0, 1), (1, 3), (2, 2), (3, 4)], size=1.2, color='#176b9b')
p.axes(x='Time / s', y='Response / mV').legend(side='bottom')
doc = i.document(width=100)
doc.add('response', p, min_height=60)
doc.compile().save('plot.svg')
```

`clip=True` clips data marks at the plot area. It does not suppress axes or
outside legends. Inklet does not clip out-of-domain marks unless requested.
Logarithmic domains and values must be positive.

## Select a mark

| Data or task | Methods | Notes |
|---|---|---|
| Ordered observations | `line`, `step` | `step(where='post')` holds a value until the next x |
| Individual observations | `scatter` | Per-point sizes and colours; markers include `circle`, `square`, `plus` |
| Uncertainty | `band`, `errorbars`, `series` | Bands use absolute bounds; error bars use error magnitudes |
| Categories | `bars` | `bar_colors` is per category; `colors` is per series |
| Distributions | `hist`, `boxplot`, `violin` | Histograms can use density normalization |
| Composition over x | `stackarea`, `fill_between` | Stacked areas require nonnegative series-major values |
| Gridded values | `matrix` | Colour ramp and scale can feed `colorbar()` |
| Reference regions | `hline`, `vline`, `hspan`, `vspan` | Declare background spans before the marks they should sit behind |
| Explanation | `annotate`, `bracket`, `inset` | Placement uses the measured plot and its furniture |

For signatures and less common marks, see [the API reference](api.md).

## Uncertainty and legends

```python
x = [0, 1, 2, 3]
mean = [1, 2, 2.5, 3.5]
uncertain = i.plot_spec(x=(0, 3), y=(0, 5))
uncertain.series(i.Series('Treatment', x, mean, '#198c83',
                          [v - .3 for v in mean], [v + .3 for v in mean]))
uncertain.axes(x='Time', y='Response').legend(side='bottom')
doc.replace('response', uncertain)
assert 'Treatment' in doc.compile().to_svg()
```

`Series.lower` and `Series.upper` are absolute y coordinates, not error sizes.
For `errorbars(points, yerr=...)`, values are distances from each point.
Name a series with `name=` to create a legend entry; a per-point colour array
does not describe a single legend category. Use [category definitions](data.md)
when filtering should preserve category colours and labels.

## Insets and secondary axes

```python
detail = i.plot_spec(20, 14, x=(2, 3), y=(2, 4), clip=True)
detail.line(list(zip(x, mean)), stroke='#198c83').axes(count=3)
uncertain.inset(detail, corner='se', width=None, zoom=(2, 3, 2, 4), pad=2)
assert doc.compile().root.width == 100
```

`width=None` preserves the inset's physical dimensions and typography. `zoom`
marks a source rectangle; choose its limits to match the inset domains.
`side='right'` places an inset outside the parent and requires room in the cell.
See [publication plot controls](publication-plots.md) for external insets.

`p.twin_y((0, 100), label='Efficiency / %', color='#176b9b')` returns a live
handle with an independent y scale. Add marks through that handle and compile
the parent. Colour the secondary axis to identify the corresponding series.

## Instruction order and edits

The compiler resolves marks first, then axes, keys, group labels/insets,
brackets, callouts and titles. Declaration order is preserved within a phase.
A bracket can be declared before its bars and still clear their current values.

Name an instruction with `key='signal'` to revise it with
`replace('signal', ...)`, or remove it with `remove('signal')`. Calling a mark
method again adds another instruction. A callout given a literal coordinate
keeps that coordinate when data change; update it explicitly or use an explicit
derived dependency.

## Dense data and polar plots

`scatter(..., raster=True, dpi=300)` rasterizes just the marker layer.
`matrix(..., raster=True)` provides a raster field; use `raster=False` for vector
cells. These require the `images` extra. Axes and labels stay vector. Raster
scatter still has a significant construction cost at high point counts; measure
the intended workload instead of assuming raster export is faster.

For polar plots, use `i.polar(radius, r=(0, 30), zero='up', winding='cw')`, then
its `line`, `band`, grid and axis methods, and return `build()` from a component
factory. The [polar example](../examples/polar.py) and
[stress test](../examples/stress20.py) show complete integrations.
