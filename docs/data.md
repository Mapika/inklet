# Live data and provenance

Use datasets and explicit references when plots must follow data edits.
Literal lists are snapshotted when an instruction is recorded.

## A table shared by plots

```python
import inklet as i

data = i.dataset(
    {'time': [0, 1, 2], 'control': [1, 2, 3], 'treatment': [2, 4, 5]},
    name='experiment',
    units={'time': 's', 'control': 'mV', 'treatment': 'mV'},
    source=i.Source('Simulated example', method='simulated'),
)
y = i.shared_scale(data.column('control'), data.column('treatment'), include_zero=True)
doc = i.document(width=180, columns=2)
for column, name in enumerate(('control', 'treatment')):
    p = i.plot_spec(x=(0, 2), y=y)
    p.line(data.points('time', name)).axes(x='Time / s', y='Signal / mV')
    doc.add(name, p, row=0, column=column, min_height=50)
first = doc.compile()
data.update(treatment=[2, 4, 9])
second = doc.compile()
assert first.to_svg() != second.to_svg()
assert second.metadata['datasets'][0]['revision'] == 1
```

All columns must have equal lengths. `update()` validates the complete table
before changing it; failed updates leave the old table intact. Changing the
number of rows requires updating every affected column in the same call.
`column()` returns a live reference to one column; `points()` returns paired
coordinates. Use `data.columns` for the current immutable values.

Shared scales derive a domain from all supplied columns. Units must agree;
convert incompatible units before sharing. Use `kind='log'` for a logarithmic
shared scale and supply finite, positive values.

## Explicit transformations

```python
def subtract(time, control, treatment):
    return tuple((x, b - a) for x, a, b in zip(time, control, treatment))

difference = i.derive(subtract, data.column('time'),
                      data.column('control'), data.column('treatment'))
delta = i.plot_spec(x=(0, 2), y=(0, 10))
delta.line(difference, name='Difference', stroke='#198c83').legend(side='bottom')
delta.axes(x='Time / s', y='Difference / mV')
delta_doc = i.document(width=100)
delta_doc.add('difference', delta, min_height=50)
assert 'Difference' in delta_doc.compile().to_svg()
```

`derive()` materializes its explicit inputs and calls the factory during
evaluation. Keep the function deterministic. Inputs hidden in a closure are
outside dependency tracking. Inklet draws supplied values; you remain
responsible for the statistical calculation and its interpretation.

## Categories that survive filtering

```python
encoding = i.CategoryEncoding(i.categories(
    {'control': '#176b9b', 'treated': '#198c83'},
    labels={'control': 'Control', 'treated': 'Treatment'},
))
results = i.dataset({'condition': ['control', 'treated'], 'value': [3, 6]})
bars = i.plot_spec(x=encoding.scale(), y=(0, 8))
bars.bars(results.column('condition'), results.column('value'), bar_colors=encoding)
bars.axes(y='Outcome')
bar_doc = i.document(width=100)
bar_doc.add('outcome', bars, min_height=50)
before = bar_doc.compile()
results.update(condition=['treated'], value=[6])
encoding.select(['treated'])
after = bar_doc.compile()
assert 'Control' in before.to_svg() and 'Control' not in after.to_svg()
```

Selection and table edits are separate operations: update both before compiling.
An encoding supplies stable colours, display labels and scale categories.
Unknown categories raise an error. For horizontal bars read top-to-bottom, use
`y=encoding.scale(reverse=True)` with `orient='h'`.

## Source records and manifests

`Source(citation, method=..., path=...)` records the data origin. Supported
methods are `measured`, `digitized`, `simulated` and `illustrative`. If a path is
provided, the source file is hashed when the Source is constructed. Recreate
the Source when that file changes; this record is not itself a file watcher.

Compiled metadata includes dataset names, row counts, revisions, units and
content hashes, alongside source records and font hashes. Nested subfigures
retain their dataset provenance. The export bundle serializes it to
`<name>-manifest.json`. This records construction details, not source validity.

For CSV files, read and validate the file in your author script using Python's
`csv` module or your existing data tools, then create the dataset. Use
`inklet watch figure.py --watch data.csv` to rerun the script when it changes.
See [CLI reference](cli.md) for watch scope and file handling.
