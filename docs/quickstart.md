# Your first scientific figure

This tutorial uses only the core installation until the optional review step.
All data are simulated. The Python blocks on this page run in order and are
checked by the documentation tests.

## Define the data and plot

```python
import inklet as i

data = i.dataset(
    {'time': [0, 1, 2, 3], 'signal': [1, 3, 2, 4]},
    name='response',
    units={'time': 's', 'signal': 'mV'},
    source=i.Source('Quickstart demonstration', method='simulated'),
)
plot = i.plot_spec(x=(0, 3), y=(0, 6))
plot.line(data.points('time', 'signal'), name='Signal', stroke='#176b9b')
plot.axes(x='Time / s', y='Signal / mV', key='axes')
plot.legend(side='bottom')
```

`plot_spec` records drawing instructions. The numeric domains set the data
ranges, while the document determines the final physical dimensions.
`points()` keeps the plot connected to the dataset.

## Place and export

```python
doc = i.publication('single-column').document()
doc.add('response', plot, min_height=55)
first = doc.compile()
first.save('response.svg', 'response.pdf')
print(first.report())
assert first.root.width == 89
assert doc.compile() is first
```

The single-column preset is 89 mm wide with 8-point main type. It measures the
axes and legend before fitting the data region. SVG and PDF use the same
resolved geometry and embedded fonts. Open either file to inspect the result.

## Revise the figure

```python
original_svg = first.to_svg()
data.update(signal=[1, 4, 3, 5])
plot.replace('axes', x='Elapsed time / s', y='Signal / mV')
second = doc.compile()
second.save('response-revised.svg', 'response-revised.pdf')
assert second.to_svg() != original_svg
assert first.to_svg() == original_svg
assert second.metadata['datasets'][0]['revision'] == 1
```

The earlier snapshot stays unchanged. `key='axes'` lets you replace the axis
instruction; calling `axes()` again would add another instruction. The dataset
revision and new content hash are recorded in the compiled metadata.

## Add another panel

```python
summary = i.plot_spec(x=['Control', 'Treatment'], y=(0, 8))
summary.bars(['Control', 'Treatment'], [3, 6], bar_colors=['#176b9b', '#198c83'])
summary.axes(y='Outcome / a.u.')

page = i.publication('double-column').document(columns=2, gap=8)
page.add('response', plot, row=0, column=0, min_height=60)
page.add('summary', summary, row=0, column=1, min_height=60)
page.letters()
complete = page.compile()
complete.save('two-panels.svg', 'two-panels.pdf')
assert set(complete.cells) == {'response', 'summary'}
assert not any(d.severity == 'error' for d in complete.diagnostics)
```

Explicit row and column numbers place the plots beside each other. Named cells
can be retrieved later with `page['response']`. See [layout](layout.md) for
spans, nested subfigures and irregular measured arrangements.

## Open a review page

After installing the [preview dependencies](installation.md#visual-review), run
this optional block in the same Python session:

<!-- Requires preview renderers. -->

```python
paths = complete.export('out/review', name='experiment')
print(paths['review'])
```

Open the printed HTML path. It contains SVG/PDF previews, clickable diagnostics
and links to the exports and provenance manifest.

For CLI and watch support, put the construction code inside a function named
`make_document()` that returns `page`. The [README example](../README.md#your-first-figure)
already follows this pattern. Then run:

```sh
inklet watch first_figure.py --output out/review
```

Continue with [live data](data.md), [plotting](plotting.md) or the
[complete v2.5 example](../examples/v25_document.py).
