# Matrices and heatmaps

A matrix assigns a colour to each cell. Share the mapping with its colour
key, and state the units. A calibrated image or contour field has additional
coordinate semantics; see the [scientific report](scientific-report.md) and
[contour guide](contours-streamlines.md) for the experimental linked workflows.

All values below are illustrative. Each Python block is a complete example
using core Inklet. PNG previews additionally use the `render` extra; PDF export
of raster matrices needs Pillow (`images` or `render`).

## Heatmaps

A colour key describes the same mapping as the matrix.
`colorbar()` reuses the matrix ramp and scale. Pass explicit row coordinates
to associate each row with its y category. The first category is at the bottom;
the next section shows a top-first display. Missing cells use an explicit colour.

```python
import inklet as i
p = i.plot_spec(x=['A', 'B', 'C', 'D'], y=['Run 1', 'Run 2', 'Run 3'], height=45)
p.matrix([[2, 5, 7, 3], [4, None, 8, 5], [1, 3, 6, 9]],
         x=['A', 'B', 'C', 'D'], y=['Run 1', 'Run 2', 'Run 3'],
         ramp=i.ramp('tol-ylorbr'), scale=i.linear((0, 10)),
         missing='#e8e8e8', raster=False)
p.axes(x='Condition', y='Run')
p.colorbar(label='Value / a.u.')
doc = i.document(width=105)
doc.add('matrix', p)
doc.save('matrix.svg', 'matrix.pdf')
```

![Heatmaps: A colour key describes the same mapping as the matrix.](assets/guides/plots-matrix.png)

*Rendered from the code above. Grey means missing, not zero.*

Keep rows rectangular and supply `missing=` when any value is `None` or NaN.
The colourbar describes the numeric ramp; explain the missing-value colour in
the caption. Use the same ramp and scale for comparable panels instead of
normalizing each matrix independently.

## Row order and comparisons

With explicit `y=` coordinates on `matrix()`, rows follow those coordinates
through the panel's y scale. To put the first named row at the top, reverse the
category order on the plot scale and keep the matrix's row coordinates paired
with their values. If you reorder the values themselves, reorder their
coordinates too.

Without `y=` on `matrix()`, row zero starts at the **top** of the plot area and
rows divide the height evenly, independently of the y scale. This differs from
the bottom-first categorical axis. Explicit coordinates avoid a silently
mislabelled heatmap.

```python
import inklet as i

conditions = ['A', 'B', 'C']
runs = ['Run 1', 'Run 2', 'Run 3']
values = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
shades, colour_scale = i.ramp('tol-ylorbr'), i.linear((0, 10))
doc = i.document(width=180, columns=2, gap=12,
                 share_plot_margins=True).letters()
for column, labels in enumerate((runs, runs[::-1])):
    p = i.plot_spec(x=conditions, y=labels, height=42)
    p.matrix(values, x=conditions, y=runs,
             ramp=shades, scale=colour_scale, raster=False)
    p.axes(x='Condition')
    p.colorbar(label='Value / a.u.')
    doc.add(f'order-{column}', p, row=0, column=column)
doc.save('matrix-order.svg', 'matrix-order.pdf')
```

![The same heatmap with Run 1 at the bottom in panel a and at the top in panel b](assets/guides/matrix-row-order.png)

*a, First y category at the bottom. b, The category scale is reversed; the input
rows and their coordinates stay together. Each named run keeps its values, and
both colourbars use the same 0–10 scale.*

## Numeric sample positions

Without `x=` and `y=` on `matrix()`, cells divide the plot area evenly.
For measurements at uneven numeric positions, pass sample centres explicitly.
Inklet maps those positions through the panel scales and places cell boundaries
halfway between neighbouring displayed samples. The outer cells extend by half
the adjacent gap. A category scale would give every sample an equal-width slot.

```python
import inklet as i

xs, ys = [0, 1, 4], [0.5, 1.5]
p = i.plot_spec(x=(-0.5, 5.5), y=(0, 2), height=42)
p.matrix([[2, 5, 8], [4, 7, 3]], x=xs, y=ys,
         ramp=i.ramp('tol-ylorbr'), scale=i.linear((0, 10)),
         vector='seamless')
p.scatter([(x, y) for y in ys for x in xs], color='#222222', size=1)
p.axes(x='Sample position / mm', y='Height / mm',
       x_options={'ticks': xs}, y_options={'ticks': ys, 'format': '{:.1f}'})
p.colorbar(label='Value / a.u.')
doc = i.document(width=115)
doc.add('samples', p)
doc.save('matrix-samples.svg', 'matrix-samples.pdf')
```

![An unevenly sampled matrix with black dots marking the six measured positions](assets/guides/matrix-samples.png)

*Dots mark supplied sample centres; the colour between samples represents the
midpoint-based cell assignment. It does not represent extra observations.*

Numeric domains must include the intended cell edges. A singleton row or
column fills that panel dimension unless you provide a two-edge interval for
it. Uniform edge arrays with one more entry than the number of cells are also
accepted. For uneven sampling, supply centres and review the resulting cell
boundaries at the final scale.

## Choose vector or raster cells

These options change the representation of the matrix layer. Axes, labels and
colourbars remain vector artwork.

| Option | Representation | Use and limits |
| --- | --- | --- |
| `raster='auto'` (default) | Individual vector cells up to 2,048 cells; an image above that when displayed spacing is uniform | Uneven spacing stays vector |
| `raster=False` | One vector rectangle per cell | Individual editing; larger files for dense matrices |
| `vector='batched'` | Exact same-colour cells grouped into vector paths | Forces vector output and zero overlap; viewers can show pale antialiasing joins |
| `vector='seamless'` | Batched vector cells with opaque underpaint | Suppresses pale joins while preserving foreground boundaries; requires opaque colours and zero overlap |
| `raster=True` | An embedded image, one pixel per cell by default | Requires uniform displayed spacing; cells cannot be selected individually |

Ordinary vector cells overlap slightly to hide antialiasing seams; set
`overlap=0` for exact abutting rectangles. Batched and seamless modes default
to zero overlap and reject a nonzero override. Raster colour mapping uses
256 ramp levels; batched vector colours are not quantized.

Nearest-cell rendering is the default. Explicit
`raster=True, interpolation='linear', samples=4` interpolates scalar values
before applying the colour ramp. `samples` must be an integer from 2 to 16;
linear interpolation requires uniform displayed spacing and the default
`vector='cells'`. Missing values affect the interpolation footprint instead of
being filled with zero. Use interpolation only when the figure should show a
continuous field, and describe that choice in the caption.

## Next steps

[Compare plot types](plot-types.md), configure [axes and scales](axes-and-scales.md),
or [arrange several panels](layout.md). For exact options, see the [API](api.md).
