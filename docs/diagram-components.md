# Scientific diagram components

`database`, `feature_matrix` and `sequence` return ordinary editable diagrams.
Use stacks and grids to arrange them, then connect their named anchors with
`fig.link`. Labels can be text or diagrams; repeated symbols are copied safely.

```python
import inklet

db = inklet.database('Sequence database', width=30)
matrix = inklet.feature_matrix([[0.2, 0.8], [0.7, 0.1]], cell=6,
                               row_labels=['A', 'B'], column_labels=['X', 'Y'])
fig = inklet.figure(width=100)
fig.add(inklet.hstack([db, matrix], gap=15))
fig.link(db.at('output'), matrix.at('row-0'))
fig.save('features.svg', 'features.pdf', text='embed')
```

All three components have `input` and `output` anchors. Matrices also expose
`row-0`, `column-0`, and subsequent indices, plus `matrix-nw` and `matrix-se`.
Sequences expose `item-0` and subsequent indices. Set a sequence's `pitch` to a
matrix's `cell` size to align symbols with columns. Choose a cell size that fits
the header labels. `highlight_rows` outlines selected matrix rows.

See [the complete example](../examples/feature_flow.py).
