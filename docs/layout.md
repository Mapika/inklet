# Page layout

A document places named cells on a physical page. Start with a grid; use a
measured composition when components need an irregular arrangement.

## Rows, columns and spans

```python
import inklet as i

left = i.plot_spec(x=(0, 2), y=(0, 5)).line([(0, 1), (1, 3), (2, 2)]).axes()
right = i.plot_spec(x=(0, 2), y=(0, 5)).bars([0, 1, 2], [2, 4, 3]).axes()
doc = i.document(width=180, columns=[1, 1], gap=8, row_gap=5, margin=5)
doc.add('left', left, row=0, column=0, min_width=60, min_height=50)
doc.add('right', right, row=0, column=1, min_width=60, min_height=50)
doc.add('caption', i.component(i.text, 'Two simulated measurements'),
        row=1, colspan=2, min_height=10)
figure = doc.compile()
assert figure.cells['caption'].width == 170
```

Rows and columns are zero-based. Omitting `row` appends below existing cells;
it does not fill the next unused column. `rowspan` and `colspan` reserve multiple
tracks. Cell names start with a letter and contain letters, digits, underscores
or hyphens. Names are unique within each document.

`columns=2` creates equal columns. `columns=[1, 2]` requests a 1:2 allocation,
adjusted as needed to meet cell minima. `min_width` and `min_height` constrain
the entire cell, including axes and labels. They are not data-domain limits.

With no explicit page height, rows grow to meet their measured content and
minimum heights. A fixed `height` distributes the available space. Plot areas
resize; text and strokes retain their physical dimensions. Plot cells sharing
a row or column share relevant furniture margins within that grid.

## Nested subfigures

```python
pair = i.subfigure(columns=2, gap=6).letters()
pair.add('control', left, row=0, column=0, min_height=50)
pair.add('treatment', right, row=0, column=1, min_height=50)
page = i.publication('double-column').document()
page.add('experiment', pair)
page['experiment']['control'].configure(y=(0, 6))
assert page.compile().root.width == 183
```

Subfigures inherit the parent theme and share its geometry cache. Labels added
by `letters()` are measured and have space reserved. Local names such as
`control` can be reused in different subfigures; compiled identities include
their containing cells. Margin sharing applies inside each grid, not across
arbitrary nested grids.

## Responsive components

A deferred factory can accept its available width and height:

```python
def caption(content, *, width, height):
    return i.text(content, width=width, size=i.pt(8))

page.add('caption', i.component(caption, 'A measured caption for both panels.',
                                responsive=True), min_height=10)
assert page.compile().cells['caption'].width > 100
```

During natural-height measurement, `height` can be `None`. Return a measurable
`Diagram`; account for its full bounds, including labels. A responsive factory
receives both keywords even if it only uses one. Ordinary `component()` calls
keep their factory's authored dimensions.

## Resize and replace

```python
page.configure(width=200)
page.replace('caption', i.component(caption, 'Updated caption', responsive=True))
assert page.compile().root.width == 200
```

`replace()` retains a cell's layout constraints. The document does not change
the number of columns automatically or shrink fixed drawings to fit.
An impossible layout raises `LayoutError` with the required and available
dimensions. Increase the cell/page size, wrap labels, or revise the arrangement.

For measured x/y expressions and connections, continue with
[diagrams](diagrams.md). See [troubleshooting](troubleshooting.md) for clipping,
font sizes and common layout failures.
